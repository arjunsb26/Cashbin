"use client";

import type { EvidenceBundle } from "@/lib/derive";
import { imageSrc, useRules } from "@/lib/api";
import { ruleMap } from "@/lib/derive";
import {
  formatEstimateSource,
  formatMass,
  formatMethod,
  formatMoney,
  formatProbability,
} from "@/lib/format";
import { CropFrame } from "./CropFrame";
import { Term } from "./Term";
import { ProbabilityBars } from "./ProbabilityBars";
import { TraceChart } from "./TraceChart";
import { SectionTitle, StatusDot } from "./ui";

/**
 * Answers "where did this number come from". The drawer and the event detail page
 * both render this, so the two cannot drift.
 */
export function EvidenceBody({ evidence }: { evidence: EvidenceBundle }) {
  const id = evidence.identification;
  const rules = ruleMap(useRules().data);
  return (
    <div className="flex flex-col gap-6">
      <section className="flex flex-col gap-2">
        <SectionTitle>Photo and weight</SectionTitle>
        <div className="flex items-start gap-3">
          <CropFrame
            src={imageSrc(evidence.crop_url)}
            label={`Crop for ${evidence.title}`}
            size={96}
          />
          <div className="min-w-0 flex-1">
            {evidence.trace ? (
              <TraceChart trace={evidence.trace} />
            ) : (
              <p className="text-caption text-ink-soft">
                No trace was kept for this ticket, so there is nothing to draw.
              </p>
            )}
          </div>
        </div>
        {evidence.trace ? (
          <p className="text-caption text-ink-soft">
            The scale settled at {formatMass(evidence.trace.settled_g)}, from a baseline of{" "}
            {formatMass(evidence.trace.baseline_g)}.
          </p>
        ) : null}
      </section>

      <section className="flex flex-col gap-2">
        <SectionTitle>How it was identified</SectionTitle>
        {id ? (
          <>
            <p className="text-body">
              {formatMethod(id.method)}
              {id.confidence !== null && id.confidence !== undefined
                ? ` at ${formatProbability(id.confidence)} confidence`
                : ""}
              {id.latency_ms ? `, in ${Math.round(id.latency_ms)} ms` : ""}.
            </p>
            {id.provider && id.model ? (
              <p className="text-caption text-ink-soft">
                Served by {id.provider}, model {id.model}.
              </p>
            ) : null}
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              {evidence.candidates.length > 0 ? (
                <ProbabilityBars title="From the photo alone" candidates={evidence.candidates} />
              ) : (
                <p className="text-caption text-ink-soft">
                  Nothing was guessed from the photo, because the answer was known outright.
                </p>
              )}
              {evidence.posterior.length > 0 ? (
                <ProbabilityBars
                  title="After the weight was taken into account"
                  candidates={evidence.posterior}
                />
              ) : (
                <p className="text-caption text-ink-soft">
                  No weight adjustment was needed for this one.
                </p>
              )}
            </div>
          </>
        ) : (
          <p className="text-body text-ink-soft">
            Nothing has identified this yet. It has a mass and a picture and nothing else.
          </p>
        )}
      </section>

      {evidence.formula.length > 0 ? (
        <section className="flex flex-col gap-2">
          <SectionTitle>The arithmetic</SectionTitle>
          <dl className="m-0 grid grid-cols-[128px_1fr] gap-x-3 gap-y-1">
            {evidence.formula.map((step) => (
              <div key={step.label} className="contents">
                <dt className="text-caption text-ink-soft">
                  <Term>{step.label}</Term>
                </dt>
                <dd className="m-0 text-body">{step.expression}</dd>
              </div>
            ))}
          </dl>
        </section>
      ) : null}

      {evidence.estimates.length > 0 ? (
        <section className="flex flex-col gap-2">
          <SectionTitle>Where each figure came from</SectionTitle>
          <table className="ledger w-full border-collapse text-body">
            <tbody>
              {evidence.estimates.map((line) => (
                <tr key={line.label} className="h-row border-b border-rule">
                  <td>{line.label}</td>
                  <td className="text-right">{formatMoney(line.cents ?? 0, { symbol: true })}</td>
                  <td className="pl-3 text-caption text-ink-soft">
                    {formatEstimateSource(line.source) ?? "source not recorded"}
                    {line.low !== null && line.high !== null && line.low !== line.high
                      ? `, ${formatMoney(line.low)} to ${formatMoney(line.high)}`
                      : ""}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      ) : null}

      {evidence.rule_ids.length > 0 ? (
        <section className="flex flex-col gap-2">
          <SectionTitle>The rules applied</SectionTitle>
          <ul className="m-0 flex list-none flex-col gap-3 p-0">
            {evidence.rule_ids.map((id) => {
              const rule = rules.get(id) ?? null;
              return (
                <li key={id} className="border-l-2 border-rule pl-3">
                  <p className="text-body">{rule ? rule.title : id}</p>
                  {rule ? (
                    <p className="pt-1 text-caption text-ink-soft">{rule.plain_text}</p>
                  ) : null}
                  <p className="pt-1 text-caption text-ink-soft">
                    {rule?.citation_url ? (
                      <a
                        className="underline underline-offset-2"
                        href={rule.citation_url}
                        target="_blank"
                        rel="noreferrer"
                      >
                        Read the source
                      </a>
                    ) : (
                      `Rule ${id}`
                    )}
                    {rule?.needs_human_review ? ", worth a person's eye" : ""}
                  </p>
                </li>
              );
            })}
          </ul>
        </section>
      ) : null}

      <section className="flex items-center gap-2 border-t border-rule pt-3">
        <StatusDot tone={evidence.human_confirmed ? "kept" : "soft"} />
        <span className="text-body">
          {evidence.human_confirmed ? "Confirmed by a person" : "Not yet reviewed"}
        </span>
      </section>
    </div>
  );
}
