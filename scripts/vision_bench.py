"""Run the real vision model over real photographs, the way the bin will see them.

Every photograph under `sim/assets/real` is composited onto a bin background at the phone's
640 px width, the crop is cut out by `app.detect.crop.crop_item` against the empty-bin frame,
and that crop goes to the live provider through the backend's own request builder and the
backend's own reply validation. Nothing here reimplements the pipeline's arithmetic: the
distribution, the mass fusion and the confident-or-ask decision are imported from
`app.identify.pipeline`, so a threshold change on main changes this table too.

    uv run --project backend python scripts/vision_bench.py --effort low --repeat 2
    uv run --project backend python scripts/vision_bench.py --effort none --service-tier fast \
        --max-px 512 --per-item 1 --repeat 2

The knobs the adapter on main does not take yet (`--service-tier`, `--detail`, `--max-px`)
are applied to the request body in this file only. `/backend` is not touched.

Output goes to `briefs/reports/lane-k/bench_<tag>.csv` and `.md`, with every crop saved next
to it under `crops/`, so a wrong answer can be looked at rather than argued about.
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "backend"))

import cv2  # noqa: E402
import numpy as np  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.detect.crop import CropParams, crop_item  # noqa: E402
from app.engine.records import load_catalog  # noqa: E402
from app.identify.cost import cost_microusd, price_for  # noqa: E402
from app.identify.openai_provider import PROVIDER_NAME, OpenAIVisionProvider  # noqa: E402
from app.identify.openai_request import build_vision_request  # noqa: E402
from app.identify.pipeline import _distribution, top_two  # noqa: E402
from app.identify.priors import MassPrior, fuse  # noqa: E402
from app.identify.providers import IdentifyContext  # noqa: E402
from app.schemas import VisionResult  # noqa: E402

REAL = REPO / "sim" / "assets" / "real"
REPORTS = REPO / "briefs" / "reports" / "lane-k"
PHONE_WIDTH = 640
PHONE_JPEG_QUALITY = 70
MAX_CONTEXT_LABELS = 60
# The phone simulator's first slot, which is where a single tossed item lands.
SLOT = (0.30, 0.34)
# What the scale would read for each item, from the catalog's unit mass where it has one.
MASS_G = {
    "bagel": 95.0, "half_sandwich": 120.0, "banana": 120.0, "apple": 180.0,
    "soda_can": 15.0, "water_bottle": 520.0, "coffee_cup": 40.0, "pizza_slice": 110.0,
    "cardboard_box": 230.0, "keyboard": 780.0, "usbc_charger": 62.0,
    "laptop_charger": 320.0, "mouse": 95.0, "earbuds": 55.0, "phone_cracked": 172.0,
    "power_bank": 210.0, "hdmi_cable": 140.0,
}
MASS_ERR_G = 1.6


# What one photograph produced -------------------------------------------------


@dataclass
class Row:
    file: str
    item: str
    expected: str
    repeat: int
    returned: str = ""
    item_class: str = ""
    confidence: float | None = None
    top_candidates: str = ""
    correct: bool = False
    would_ask: bool = False
    best_label: str = ""
    best_p: float | None = None
    margin: float | None = None
    model_ms: int | None = None
    total_ms: int | None = None
    crop_quality: str = ""
    crop_px: str = ""
    tokens_in: int | None = None
    tokens_out: int | None = None
    cached_tokens: int | None = None
    cost_microusd: int | None = None
    visible_text: str = ""
    error: str = ""


@dataclass
class Config:
    effort: str
    service_tier: str
    max_px: int
    detail: str
    model: str

    @property
    def tag(self) -> str:
        return f"{self.effort}_{self.service_tier}_{self.max_px}_{self.detail}"

    @property
    def title(self) -> str:
        return (f"effort {self.effort}, tier {self.service_tier}, "
                f"crop {self.max_px} px, detail {self.detail}")


# Building the picture the bin would see ---------------------------------------


def background(name: str) -> np.ndarray:
    image = cv2.imread(str(REAL / name), cv2.IMREAD_COLOR)
    if image is None:
        raise FileNotFoundError(f"no bin background at {REAL / name}")
    height = round(image.shape[0] * PHONE_WIDTH / image.shape[1])
    return cv2.resize(image, (PHONE_WIDTH, height), interpolation=cv2.INTER_AREA)


def paste(frame: np.ndarray, sprite: np.ndarray, fx: float, fy: float) -> np.ndarray:
    """The phone simulator's own paste, on a copy, with the sprite clamped into the frame."""
    out = frame.copy()
    fh, fw = out.shape[:2]
    h, w = sprite.shape[:2]
    if h > fh or w > fw:
        scale = min(fh / h, fw / w) * 0.9
        sprite = cv2.resize(sprite, (max(1, round(w * scale)), max(1, round(h * scale))))
        h, w = sprite.shape[:2]
    x = max(0, min(fw - w, int(fx * fw) - w // 2))
    y = max(0, min(fh - h, int(fy * fh) - h // 2))
    out[y : y + h, x : x + w] = sprite
    return out


def jpeg(image: np.ndarray, quality: int = PHONE_JPEG_QUALITY) -> bytes:
    ok, buf = cv2.imencode(".jpg", image, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
    if not ok:
        raise RuntimeError("could not encode a frame")
    return bytes(buf.tobytes())


def shrink(crop: bytes, max_px: int) -> bytes:
    """Cap the crop's long side, which is the knob that decides how many image tokens go up."""
    image = cv2.imdecode(np.frombuffer(crop, np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        return crop
    h, w = image.shape[:2]
    if max(h, w) <= max_px:
        return crop
    scale = max_px / max(h, w)
    small = cv2.resize(image, (max(1, round(w * scale)), max(1, round(h * scale))),
                       interpolation=cv2.INTER_AREA)
    return jpeg(small, 85)


def crop_for(sprite_path: Path, bg: np.ndarray, slot: tuple[float, float],
             sprite_px: int = 0) -> Any:
    """The empty bin, then the bin with the item in it, then the difference between them.

    `sprite_px` resizes the item before it is pasted. The scenarios composite at 220 px,
    which gives a crop around 258 px: already under every `--max-px` value, so the cap
    cannot bite. A phone held over a bin sees the item much larger than that, and the only
    way to measure what the cap does is to composite it that way.
    """
    sprite = cv2.imread(str(sprite_path), cv2.IMREAD_COLOR)
    if sprite is None:
        raise FileNotFoundError(f"no sprite at {sprite_path}")
    if sprite_px:
        h, w = sprite.shape[:2]
        scale = sprite_px / max(h, w)
        sprite = cv2.resize(sprite, (max(1, round(w * scale)), max(1, round(h * scale))),
                            interpolation=cv2.INTER_CUBIC)
    before = jpeg(bg)
    after = jpeg(paste(bg, sprite, *slot))
    return crop_item(before, after, CropParams())


# Talking to the model ---------------------------------------------------------


class BenchProvider(OpenAIVisionProvider):
    """The shipped adapter, with the three request knobs main does not expose yet.

    `_parse` still does the sending, the one retry, the pydantic validation and the token
    and cost accounting, so what this measures is the code the demo runs.
    """

    def __init__(self, settings: Any, config: Config) -> None:
        super().__init__(settings)
        self.config = config
        self.cached_tokens: int | None = None

    @property
    def client(self) -> Any:
        """The real client, with a shim that reads the cached token count off every reply.

        `CallUsage` has no field for it and `/backend` is not mine to widen, so it is read
        here, where the reply object is still in hand.
        """
        inner = super().client
        if getattr(inner, "_bench_wrapped", False):
            return inner
        create = inner.chat.completions.create

        def wrapped(**kwargs: Any) -> Any:
            reply = create(**kwargs)
            self.cached_tokens = read_cached_tokens(reply)
            return reply

        inner.chat.completions.create = wrapped
        inner._bench_wrapped = True
        return inner

    def identify(self, crop: bytes, context: IdentifyContext) -> VisionResult:
        request = build_vision_request(crop, context, self.config.model, self.config.effort)
        request["messages"][1]["content"][-1]["image_url"]["detail"] = self.config.detail
        if self.config.service_tier != "default":
            request["service_tier"] = self.config.service_tier
        parsed = self._parse(request, self.config.model, VisionResult)
        if parsed is None:
            raise ValueError("the model returned nothing this code could read")
        result: VisionResult = parsed
        return result.model_copy(update={"provider": PROVIDER_NAME, "model": self.config.model})


def read_cached_tokens(reply: Any) -> int | None:
    usage = getattr(reply, "usage", None)
    details = getattr(usage, "prompt_tokens_details", None)
    value = getattr(details, "cached_tokens", None)
    return int(value) if isinstance(value, int) else None


# The decision the pipeline would have made ------------------------------------


def catalog_context() -> tuple[tuple[str, ...], dict[str, MassPrior]]:
    labels: list[str] = []
    priors: dict[str, MassPrior] = {}
    for item in load_catalog():
        labels.append(item.label)
        if item.mass_prior_mean_g is not None:
            priors[item.label] = MassPrior(mean_g=item.mass_prior_mean_g,
                                           var=item.mass_prior_var or 0.0,
                                           n=item.mass_prior_n)
    return tuple(sorted(labels)), priors


def decide(vision: VisionResult, mass_g: float, priors: dict[str, MassPrior],
           settings: Any) -> tuple[str, float, float, bool]:
    """Pipeline steps 4 and 5, on the same functions, so the ask rate here is the real one."""
    dist = _distribution(vision)
    if any(priors.get(label, MassPrior(0.0, 0.0, 0)).usable for label in dist):
        claimed = min(sum(dist.values()), 1.0)
        dist = {label: p * claimed for label, p in fuse(dist, mass_g, MASS_ERR_G, priors).items()}
    best, second = top_two(dist)
    margin = best[1] - (second[1] if second else 0.0)
    confident = best[1] >= settings.confident_p and margin >= settings.min_margin
    return best[0], best[1], margin, not confident


# The run ----------------------------------------------------------------------


def photographs(per_item: int, only: tuple[str, ...]) -> list[dict[str, Any]]:
    manifest = json.loads((REAL / "manifest.json").read_text(encoding="utf-8"))
    rows = [row for row in manifest if row["item"] != "background"]
    if only:
        rows = [row for row in rows if row["item"] in only]
    kept: list[dict[str, Any]] = []
    seen: dict[str, int] = {}
    for row in rows:
        count = seen.get(row["item"], 0)
        if count >= per_item:
            continue
        seen[row["item"]] = count + 1
        kept.append(row)
    return kept


def run(config: Config, per_item: int, repeat: int, only: tuple[str, ...],
        bg_name: str, save_crops: bool, sprite_px: int = 0) -> list[Row]:
    settings = get_settings()
    labels, priors = catalog_context()
    provider = BenchProvider(settings, config)
    bg = background(bg_name)
    crops = REPORTS / "crops"
    crops.mkdir(parents=True, exist_ok=True)
    rows: list[Row] = []
    for shot in photographs(per_item, only):
        source = REAL / shot["file"] if sprite_px else REAL / "sprites" / shot["file"]
        result = crop_for(source, bg, SLOT, sprite_px)
        crop = shrink(result.jpeg, config.max_px)
        if save_crops:
            (crops / shot["file"]).write_bytes(crop)
        mass = MASS_G.get(shot["item"], 100.0)
        context = IdentifyContext(
            event_id=0, mass_g=mass, mass_err_g=MASS_ERR_G,
            timeout_s=settings.llm_timeout_s, catalog_labels=labels[:MAX_CONTEXT_LABELS],
            asset_tags=(),
        )
        decoded = cv2.imdecode(np.frombuffer(crop, np.uint8), cv2.IMREAD_COLOR)
        for index in range(1, repeat + 1):
            row = Row(file=shot["file"], item=shot["item"], expected=shot["expected_label"],
                      repeat=index, crop_quality=result.crop_quality,
                      crop_px=f"{decoded.shape[1]}x{decoded.shape[0]}")
            started = time.perf_counter()
            try:
                vision = provider.identify(crop, context)
            except Exception as exc:
                row.error = f"{type(exc).__name__}: {exc}"[:160]
                row.total_ms = int((time.perf_counter() - started) * 1000)
                rows.append(row)
                print(f"  {shot['file']:<24} call failed, {row.error}")
                continue
            row.total_ms = int((time.perf_counter() - started) * 1000)
            usage = provider.last_call
            best, best_p, margin, would_ask = decide(vision, mass, priors, settings)
            row.returned = vision.label
            row.item_class = vision.item_class.value
            row.confidence = round(vision.confidence, 3)
            row.top_candidates = "; ".join(
                f"{c.label} {c.p:.2f}" for c in vision.candidates[:3]
            )
            row.visible_text = vision.visible_text[:60]
            row.best_label, row.best_p = best, round(best_p, 3)
            row.margin, row.would_ask = round(margin, 3), would_ask
            row.correct = best.strip().lower() == shot["expected_label"].strip().lower()
            if usage is not None:
                row.model_ms = usage.latency_ms
                row.tokens_in, row.tokens_out = usage.tokens_in, usage.tokens_out
                row.cost_microusd = usage.cost_microusd
            row.cached_tokens = provider.cached_tokens
            rows.append(row)
            mark = "ok " if row.correct else "BAD"
            ask = " ask" if would_ask else ""
            print(f"  {shot['file']:<24} {mark} {best:<22} p={best_p:.2f}{ask} "
                  f"{row.model_ms} ms")
    return rows


# What the run says ------------------------------------------------------------


@dataclass
class Summary:
    tag: str
    title: str
    calls: int = 0
    failures: int = 0
    accuracy: float = 0.0
    ask_rate: float = 0.0
    median_model_ms: float = 0.0
    p90_model_ms: float = 0.0
    median_total_ms: float = 0.0
    mean_tokens_in: float = 0.0
    mean_cached: float = 0.0
    mean_cost_microusd: float = 0.0
    wrong: list[str] = field(default_factory=list)


def percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round(fraction * (len(ordered) - 1))))
    return ordered[index]


def summarise(config: Config, rows: list[Row]) -> Summary:
    good = [r for r in rows if not r.error]
    out = Summary(tag=config.tag, title=config.title, calls=len(rows),
                  failures=len(rows) - len(good))
    if not good:
        return out
    out.accuracy = sum(r.correct for r in good) / len(good)
    out.ask_rate = sum(r.would_ask for r in good) / len(good)
    model_ms = [float(r.model_ms) for r in good if r.model_ms is not None]
    out.median_model_ms = statistics.median(model_ms) if model_ms else 0.0
    out.p90_model_ms = percentile(model_ms, 0.9)
    total_ms = [float(r.total_ms) for r in good if r.total_ms is not None]
    out.median_total_ms = statistics.median(total_ms) if total_ms else 0.0
    tokens = [float(r.tokens_in) for r in good if r.tokens_in is not None]
    out.mean_tokens_in = sum(tokens) / len(tokens) if tokens else 0.0
    cached = [float(r.cached_tokens) for r in good if r.cached_tokens is not None]
    out.mean_cached = sum(cached) / len(cached) if cached else 0.0
    costs = [float(r.cost_microusd) for r in good if r.cost_microusd is not None]
    out.mean_cost_microusd = sum(costs) / len(costs) if costs else 0.0
    out.wrong = sorted({f"{r.file}: {r.expected} -> {r.best_label}" for r in good
                        if not r.correct})
    return out


def write_csv(path: Path, rows: list[Row]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(asdict(rows[0])))
        writer.writeheader()
        for row in rows:
            writer.writerow(asdict(row))


def write_md(path: Path, config: Config, rows: list[Row], summary: Summary) -> None:
    lines = [f"# Vision bench: {config.title}", "",
             f"Model `{config.model}`. {summary.calls} calls, {summary.failures} of them failed.",
             "",
             "| Measure | Value |", "|---|---|",
             f"| Accuracy | {summary.accuracy:.1%} |",
             f"| Ask rate | {summary.ask_rate:.1%} |",
             f"| Median model call | {summary.median_model_ms:.0f} ms |",
             f"| p90 model call | {summary.p90_model_ms:.0f} ms |",
             f"| Mean input tokens | {summary.mean_tokens_in:.0f} |",
             f"| Mean cached input tokens | {summary.mean_cached:.0f} |",
             f"| Mean cost per call | {summary.mean_cost_microusd:.0f} microUSD |",
             "",
             "| File | Expected | Answered | p | Margin | Ask | Model ms | Tokens in | Cost uUSD |",
             "|---|---|---|---|---|---|---|---|---|"]
    for row in rows:
        lines.append(
            f"| {row.file} | {row.expected} | {row.best_label or row.error} | "
            f"{row.best_p if row.best_p is not None else ''} | "
            f"{row.margin if row.margin is not None else ''} | "
            f"{'yes' if row.would_ask else 'no'} | {row.model_ms or ''} | "
            f"{row.tokens_in or ''} | {row.cost_microusd or ''} |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Real photographs through the real model")
    parser.add_argument("--images", default=str(REAL), help="kept for the brief's spelling")
    parser.add_argument("--effort", default="low", choices=("none", "minimal", "low", "medium"))
    parser.add_argument("--service-tier", default="default", choices=("default", "fast",
                                                                      "priority", "flex"))
    parser.add_argument("--max-px", type=int, default=640)
    parser.add_argument("--detail", default="low", choices=("low", "high", "auto"))
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--per-item", type=int, default=9, help="photographs per item")
    parser.add_argument("--only", default="", help="comma separated item keys")
    parser.add_argument("--background", default="bin_1.jpg")
    parser.add_argument("--tag", default="", help="overrides the output file name")
    parser.add_argument("--sprite-px", type=int, default=0,
                        help="composite the item at this size instead of 220 px")
    parser.add_argument("--no-crops", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    settings = get_settings()
    if settings.llm_provider.strip().lower() != "openai" or not settings.openai_api_key:
        print("this bench needs LLM_PROVIDER=openai and a key in the repo root .env")
        return 2
    config = Config(effort=args.effort, service_tier=args.service_tier, max_px=args.max_px,
                    detail=args.detail, model=settings.llm_vision_model)
    only = tuple(part.strip() for part in args.only.split(",") if part.strip())
    print(f"bench {config.title}, repeat {args.repeat}, per item {args.per_item}")
    rows = run(config, args.per_item, args.repeat, only, args.background,
               not args.no_crops, args.sprite_px)
    if not rows:
        print("no photographs matched")
        return 1
    summary = summarise(config, rows)
    tag = args.tag or config.tag
    write_csv(REPORTS / f"bench_{tag}.csv", rows)
    write_md(REPORTS / f"bench_{tag}.md", config, rows, summary)
    price = price_for(config.model, PROVIDER_NAME)
    spend = sum(r.cost_microusd or 0 for r in rows)
    print(f"\n{config.title}")
    print(f"  calls {summary.calls} ({summary.failures} failed)")
    print(f"  accuracy {summary.accuracy:.1%}  ask rate {summary.ask_rate:.1%}")
    print(f"  model call median {summary.median_model_ms:.0f} ms, "
          f"p90 {summary.p90_model_ms:.0f} ms")
    print(f"  tokens in {summary.mean_tokens_in:.0f} (cached {summary.mean_cached:.0f}), "
          f"cost {summary.mean_cost_microusd:.0f} microUSD per call")
    print(f"  run spend {spend} microUSD, price row "
          f"{'found' if price else 'missing, cost is blank'}")
    for line in summary.wrong:
        print(f"  wrong: {line}")
    print(f"  written to briefs/reports/lane-k/bench_{tag}.csv and .md")
    (REPORTS / f"summary_{tag}.json").write_text(json.dumps(asdict(summary), indent=1),
                                                 encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
