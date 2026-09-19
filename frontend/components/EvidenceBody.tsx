"use client";

import type { EvidenceBundle } from "@/lib/types";
import { formatMass, formatMassError, formatMoney, formatProbability } from "@/lib/format";
import { CropFrame } from "./CropFrame";
import { ProbabilityBars } from "./ProbabilityBars";
import { TraceChart } from "./TraceChart";
import { SectionTitle, StatusDot } from "./ui";

const METHOD_WORDS: Record<string, string> = {
  qr: "Read the asset tag",
  memory: "Matched from memory",
  cloud: "Vision model",
  human: "Answered by a person",
  stub: "Local stand-in",
};

/**
 * Answers "where did this number come from". The drawer and the event detail page
 * both render this, so the two cannot drift.
 */
export function EvidenceBody({ evidence }: { evidence: EvidenceBundle }) {
  const id = evidence.identification;
  return (
    <div className="flex flex-col gap-6">
      <section className="flex flex-col gap-2">
        <SectionTitle>Photo and weight</SectionTitle>
        <div className="flex items-start gap-3">
          <CropFrame src={evidence.crop} label={`Crop for ${evidence.title}`} size={96} />
          <div className="flex-1">
            <TraceChart trace={evidence.trace} />
          </div>
        </div>
        <p className="text-caption text-ink-soft">
          Settled at {formatMass(evidence.trace.points[evidence.trace.points.length - 1]?.g ?? 0)},
          baseline {formatMass(evidence.trace.baseline_g)}.
        </p>
      </section>

      <section className="flex flex-col gap-2">
        <SectionTitle>How it was identified</SectionTitle>
        <p className="text-body">
          {METHOD_WORDS[id.method] ?? id.method} at {formatProbability(id.confidence)} confidence,
          in {id.latency_ms} ms.
        </p>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <ProbabilityBars title="From the photo alone" candidates={id.candidates} />
          {id.posterior ? (
            <ProbabilityBars
              title="After the weight was taken into account"
              candidates={id.posterior}
            />
          ) : (
            <p className="text-caption text-ink-soft">
              The tag was read directly, so no weight adjustment was needed.
            </p>
          )}
        </div>
      </section>

      <section className="flex flex-col gap-2">
        <SectionTitle>The arithmetic</SectionTitle>
        <dl className="m-0 grid grid-cols-[128px_1fr] gap-x-3 gap-y-1">
          {evidence.formula.map((step) => (
            <div key={step.label} className="contents">
              <dt className="text-caption text-ink-soft">{step.label}</dt>
              <dd className="m-0 text-body">{step.expression}</dd>
            </div>
          ))}
        </dl>
        {evidence.estimate && evidence.estimate.mid_cents !== null ? (
          <p className="text-caption text-ink-soft">
            Estimated range {formatMoney(evidence.estimate.low_cents ?? 0, { symbol: true })} to{" "}
            {formatMoney(evidence.estimate.high_cents ?? 0, { symbol: true })}, from the{" "}
            {evidence.estimate.source === "model_estimate" ? "value model" : evidence.estimate.source}.
          </p>
        ) : null}
      </section>

      <section className="flex flex-col gap-2">
        <SectionTitle>The rule used</SectionTitle>
        <ul className="m-0 flex list-none flex-col gap-3 p-0">
          {evidence.rules.map((rule) => (
            <li key={rule.id}>
              <p className="text-body">{rule.text}</p>
              <a
                className="text-caption text-ink underline underline-offset-2"
                href={rule.citation_url}
                target="_blank"
                rel="noreferrer"
              >
                {rule.citation_title}
              </a>
            </li>
          ))}
        </ul>
      </section>

      <section className="flex items-center gap-2 border-t border-rule pt-3">
        <StatusDot tone={evidence.human_confirmed ? "kept" : "soft"} />
        <span className="text-body">
          {evidence.human_confirmed ? "Confirmed by a person" : "Not yet reviewed"}
        </span>
      </section>
    </div>
  );
}

export function EvidenceMassLine({ grams, error }: { grams: number; error: number }) {
  return (
    <span>
      {formatMass(grams)} {formatMassError(error)}
    </span>
  );
}
