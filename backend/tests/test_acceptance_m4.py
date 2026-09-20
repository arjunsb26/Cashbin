"""M4: the soak run with every ask answered, and what three rounds of it look like.

PLAN.md section 20 M4. Sixty tosses from `sim/scenarios/soak.yaml` go in through the dev
toss route, every ask is answered through `POST /api/corrections` with the label the
scenario says was thrown, and the rounds table is read back off `GET /api/metrics/rounds`.

The provider here is the OpenAI adapter driven by a scripted fake client, not the stub.
That is deliberate: the stub reports a cost of zero for every call, so the cost per event
column cannot fall, and the cost column is half of what this milestone is for. The fake
answers with the label the scenario queued and charges the real price table for the tokens,
so the money on the chart is arithmetic over real prices rather than a number anyone typed.

Nothing here reaches the network. There is no key and no client, only a scripted object.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml
from fastapi.testclient import TestClient

from app.config import Settings, reset_settings
from app.db import dispose_db, session_scope
from app.main import create_app
from app.models import Event, EventStatus, Exemplar
from app.notify.bus import reset_bus

REPO_DIR = Path(__file__).resolve().parents[2]
if str(REPO_DIR) not in sys.path:
    sys.path.insert(0, str(REPO_DIR))

from scripts.seed_db import seed_all  # noqa: E402

SOAK = REPO_DIR / "sim" / "scenarios" / "soak.yaml"
ROUND_SIZE = 20

VISION_MODEL = "gpt-5.6-luna"
TEXT_MODEL = "gpt-5.6-terra"

# What one call uses. A vision call carries an image, so it is the expensive one.
VISION_TOKENS = (1450, 80)
TEXT_TOKENS = (420, 210)

# The fake is as sure of a catalog label as the stub is, and as unsure of anything else.
# Those are the two cases the confidence gate exists to tell apart.
CONFIDENT_P = 0.93
UNSURE_P = 0.55


class _Message:
    def __init__(self, content: str) -> None:
        self.content = content


class _Choice:
    def __init__(self, content: str) -> None:
        self.message = _Message(content)


class _Usage:
    def __init__(self, tokens: tuple[int, int]) -> None:
        self.prompt_tokens, self.completion_tokens = tokens


class _Reply:
    def __init__(self, content: str, tokens: tuple[int, int]) -> None:
        self.choices = [_Choice(content)]
        self.usage = _Usage(tokens)


class ScriptedCompletions:
    """Answers whatever the test said was coming, and counts what it was asked."""

    def __init__(self) -> None:
        self.label = "unknown object"
        self.known = False
        self.visible_text = ""
        self.vision_calls = 0
        self.text_calls = 0

    def create(self, **kwargs: Any) -> _Reply:
        model = str(kwargs.get("model"))
        if model == VISION_MODEL:
            self.vision_calls += 1
            return _Reply(self._vision(), VISION_TOKENS)
        self.text_calls += 1
        return _Reply(self._estimate(), TEXT_TOKENS)

    def _vision(self) -> str:
        p = CONFIDENT_P if self.known else UNSURE_P
        return json.dumps(
            {
                "label": self.label,
                "class": "inventory" if self.known else "untracked",
                "confidence": p,
                "candidates": [{"label": self.label, "p": p}],
                "material": "mixed_plastics",
                "condition": "unknown",
                "visible_text": self.visible_text,
            }
        )

    def _estimate(self) -> str:
        return json.dumps(
            {
                "label": self.label,
                "fmv": {"low": 200, "mid": 800, "high": 2000, "rationale": "listings"},
                "repair": {"low": 500, "mid": 1500, "high": 4000, "rationale": "parts"},
                "replacement": {"low": 1000, "mid": 3000, "high": 8000, "rationale": "retail"},
                "scrap": {"low": 10, "mid": 50, "high": 200, "rationale": "materials"},
                "material_mix": {"mixed_plastics": 1.0},
                "regulatory_flags": [],
            }
        )


class ScriptedOpenAI:
    """A stand-in for the OpenAI client. No key, no base url, no socket."""

    def __init__(self) -> None:
        self.completions = ScriptedCompletions()
        self.chat = self


def soak_steps() -> list[dict[str, Any]]:
    data = yaml.safe_load(SOAK.read_text(encoding="utf-8"))
    return list(data["steps"])


@pytest.fixture
def soak_settings(tmp_path: Path) -> Any:
    conf = Settings(
        _env_file=None,
        db_path=tmp_path / "binbooks.db",
        media_dir=tmp_path / "media",
        cert_dir=tmp_path / "certs",
        recordings_dir=tmp_path / "recordings",
        dev_tools=True,
        seed_on_start=False,
        round_size=ROUND_SIZE,
        llm_provider="openai",
        openai_api_key="not-a-real-key",
        llm_vision_model=VISION_MODEL,
        llm_text_model=TEXT_MODEL,
    )
    reset_settings(conf)
    reset_bus()
    yield conf
    dispose_db()
    reset_settings(Settings(_env_file=None))


def catalog_labels(client: TestClient) -> set[str]:
    return {item["label"] for item in client.get("/api/catalog").json()["items"]}


def rounds_table(rows: list[dict[str, Any]]) -> str:
    """The M4 table, printed the way the report shows it."""
    head = (
        f"{'round':>5} {'events':>7} {'first try':>10} {'asked':>6} "
        f"{'ask rate':>9} {'cost uUSD':>10} {'per event':>10} {'local':>7}"
    )
    lines = [head]
    for row in rows:
        lines.append(
            f"{row['id']:>5} {row['n_events']:>7} {row['first_try_accuracy'] or 0:>10.2f} "
            f"{row['n_asked']:>6} {row['ask_rate'] or 0:>9.2f} "
            f"{row['cloud_cost_microusd']:>10} "
            f"{row['cost_per_event_microusd'] or 0:>10.1f} {row['local_share'] or 0:>7.2f}"
        )
    return "\n".join(lines)




def play_the_soak(
    client: TestClient, fake: ScriptedOpenAI, *, cold: bool = False
) -> dict[str, Any]:
    """Every toss in the scenario, with a person behind it.

    A person answers every ask with the label the scenario says was thrown, and overturns
    a confident answer that came back under the wrong name. Both are one call to
    `POST /api/corrections`, which is the only way in.

    `cold` makes the model unsure of everything, which is a bin meeting a vocabulary it has
    never been shown. Without it the model is sure of anything the catalog already holds.
    """
    known = catalog_labels(client)
    answered = 0
    overturned = 0
    for step in soak_steps():
        if step["kind"] != "toss":
            # A bag going out is not identified and does not join a round, so it has
            # nothing to say about learning. The mass path for it is covered by M5.
            continue
        label = str(step["label"])
        fake.completions.label = label
        fake.completions.known = (not cold) and label in known
        posted = client.post(
            "/api/sim/toss",
            json={
                "label": label,
                "mass_g": float(step["mass_g"]),
                "image": str(step["image"]),
            },
        ).json()
        event_id = posted["event_id"]
        asked = posted["status"] == EventStatus.asking
        if not asked and _label_of(client, event_id) == label:
            continue
        reply = client.post(
            "/api/corrections",
            json={"event_id": event_id, "label": label, "by": "acceptance"},
        )
        assert reply.status_code == 200, reply.text
        answered += int(asked)
        overturned += int(not asked)
    return {"answered": answered, "overturned": overturned}


def _label_of(client: TestClient, event_id: int) -> str | None:
    label = client.get(f"/api/events/{event_id}").json()["event"]["label"]
    return str(label) if label is not None else None


def run_the_soak(soak_settings: Settings, *, cold: bool) -> dict[str, Any]:
    """One whole soak run, and the rounds table it leaves behind."""
    app = create_app(soak_settings)
    fake = ScriptedOpenAI()
    with TestClient(app) as client:
        with session_scope() as session:
            seed_all(session)
        pipeline = app.state.pipeline
        pipeline.vision.inner._client = fake
        pipeline.providers.estimator._client = fake

        played = play_the_soak(client, fake, cold=cold)
        rows = client.get("/api/metrics/rounds").json()["rounds"]
        print("\n" + rounds_table(rows))
        print(
            f"\nasks answered {played['answered']}, "
            f"confident answers overturned {played['overturned']}, "
            f"vision calls {fake.completions.vision_calls} of 60 tosses"
        )
        with session_scope() as session:
            exemplars = session.query(Exemplar).count()
            stuck = session.query(Event).filter(Event.status == EventStatus.asking).count()
    return {
        "rows": rows,
        "played": played,
        "vision_calls": fake.completions.vision_calls,
        "exemplars": exemplars,
        "stuck": stuck,
    }


def columns(rows: list[dict[str, Any]]) -> dict[str, list[float]]:
    return {
        "accuracy": [row["first_try_accuracy"] or 0.0 for row in rows],
        "ask_rate": [row["ask_rate"] or 0.0 for row in rows],
        "per_event": [row["cost_per_event_microusd"] or 0.0 for row in rows],
        "local": [row["local_share"] or 0.0 for row in rows],
    }


def test_a_vocabulary_it_has_to_learn_improves_round_over_round(
    soak_settings: Settings,
) -> None:
    """The M4 check. A bin shown a vocabulary it does not know, and a person answering.

    Every first sighting opens an ask, the answer becomes an exemplar, and the next time
    that thing goes in the bin memory answers it for nothing. Accuracy climbs, the ask rate
    falls, and the money per ticket falls with it, because the calls stop happening.
    """
    run = run_the_soak(soak_settings, cold=True)
    rows = run["rows"]
    assert len(rows) >= 3, "sixty tosses at twenty a round is three rounds"
    assert sum(row["n_events"] for row in rows) == 60
    assert run["stuck"] == 0, "every ask in this run was answered"
    assert run["exemplars"] > 0

    column = columns(rows)
    assert column["accuracy"][-1] > column["accuracy"][0], column["accuracy"]
    assert column["ask_rate"][-1] < column["ask_rate"][0], column["ask_rate"]
    assert column["per_event"][-1] < column["per_event"][0], column["per_event"]
    assert column["local"][-1] > column["local"][0], column["local"]
    assert rows[0]["cloud_cost_microusd"] > 0, "a priced call has to cost something"
    assert rows[-1]["cloud_cost_microusd"] < rows[0]["cloud_cost_microusd"]


def test_the_soak_as_written_barely_learns_because_memory_is_only_human_fed(
    soak_settings: Settings,
) -> None:
    """The same run against the shipped catalog, which is where the curve nearly flattens.

    Almost every label in `soak.yaml` is in `catalog.csv`, so the model is confident about
    almost every toss, so almost nothing asks, so almost nothing becomes an exemplar. An
    exemplar is written only when a person answers or overturns an answer
    (`learn/corrections.py`), which means the local-first path never takes over the tosses
    the model already gets right. What little it does learn here comes from the six unknown
    objects that share one picture, which the model keeps naming wrongly and a person keeps
    putting right.

    This is a measurement, not a wish. If somebody changes what writes an exemplar, this
    test fails, and the numbers in it are the ones to argue with.
    """
    run = run_the_soak(soak_settings, cold=False)
    rows = run["rows"]
    column = columns(rows)
    played = run["played"]

    assert run["vision_calls"] >= 45, "the catalog path calls the model on most tosses"
    assert played["answered"] <= 3, "a seeded catalog barely ever asks"
    assert sum(row["n_asked"] for row in rows) <= 5
    # The local share does climb, but only over the handful of pictures a person touched.
    assert column["local"][-1] < 0.25, column["local"]
    # And the money per ticket stays within a quarter of where it started, against the
    # cold run above where it reaches zero.
    assert column["per_event"][-1] > column["per_event"][0] * 0.75, column["per_event"]
