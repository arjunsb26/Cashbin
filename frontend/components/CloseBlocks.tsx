"use client";

import Link from "next/link";
import { reconciliationFoots, rollforwardParts } from "@/lib/cfo";
import type {
  Form4797Block,
  Form4797Row,
  ReconciliationBlock,
  RollforwardBlock,
} from "@/lib/types";
import { formatDate, formatMoney, formatTag } from "@/lib/format";
import { noteBlocks } from "@/lib/derive";
import { Badge, SectionTitle, cx } from "./ui";

/**
 * The close memo, in prose, under the title.
 *
 * It is written by a model from a block of numbers the engine computed, so it is
 * printed as text and nothing in it is ever read back as an instruction.
 */
export function CloseMemo({ memo }: { memo: string }) {
  const blocks = noteBlocks(memo);
  return (
    <section aria-label="Memo" className="max-w-[68ch] border-b border-rule pb-6">
      {blocks.map((block, i) => (
        <p
          key={i}
          className={cx(block.kind === "heading" ? "pt-3 text-section" : "pt-2 text-body")}
        >
          {block.text}
        </p>
      ))}
    </section>
  );
}

/**
 * The fixed asset rollforward, on a net book value basis.
 *
 * Opening, plus what was bought, less the wear written off, less what left, is
 * closing. The row that does not foot says so rather than being quietly wrong,
 * because a rollforward whose arithmetic nobody checks is decoration.
 */
export function Rollforward({ block }: { block: RollforwardBlock }) {
  const rows = block.rows ?? [];
  const total = block.total ?? null;
  const ties =
    typeof block.ties === "boolean"
      ? block.ties
      : rows.every((row) => rollforwardParts(row).foots);

  return (
    <section>
      <SectionTitle>Fixed asset rollforward</SectionTitle>
      <p className="pb-2 pt-1 text-caption text-ink-soft">
        Net book value. Opening, plus additions, less depreciation, less what left the
        register, is closing.
      </p>
      {rows.length === 0 ? (
        <p className="text-body text-ink-soft">
          Nothing on the register moved in this period, so there is nothing to roll forward.
        </p>
      ) : (
        <div className="overflow-x-auto">
          <p className="pb-2 text-caption text-ink-soft md:hidden">Swipe sideways for the rest of the columns.</p>
          <table className="ledger green-bar w-full min-w-[640px] border-collapse text-body">
            <thead>
              <tr className="border-b border-rule text-caption text-ink-soft">
                <th className="py-1 font-normal">Tag</th>
                <th className="py-1 font-normal">Asset</th>
                <th className="py-1 text-right font-normal">Opening ($)</th>
                <th className="py-1 text-right font-normal">Additions ($)</th>
                <th className="py-1 text-right font-normal">Depreciation ($)</th>
                <th className="py-1 text-right font-normal">Disposals ($)</th>
                <th className="py-1 text-right font-normal">Closing ($)</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row, i) => {
                const parts = rollforwardParts(row);
                return (
                  <tr
                    key={(row.tag ?? "") + "-" + (row.asset_id ?? i)}
                    className="h-row border-b border-rule hover:bg-bar"
                  >
                    <td className="font-condensed">{row.tag ? formatTag(row.tag) : ""}</td>
                    <td>{row.description}</td>
                    <td className="text-right">{formatMoney(parts.opening)}</td>
                    <td className="text-right">{formatMoney(parts.additions)}</td>
                    <td className="text-right">{formatMoney(-parts.depreciation)}</td>
                    <td className="text-right">{formatMoney(-parts.disposals)}</td>
                    <td className="text-right">{formatMoney(parts.closing)}</td>
                  </tr>
                );
              })}
              {total ? <TotalRow row={total} /> : null}
            </tbody>
          </table>
          <p className={cx("pt-2 text-caption", ties ? "text-ink-soft" : "text-red-ink")}>
            {ties
              ? "Every line foots: opening plus the movements equals closing."
              : "A line does not foot. The register and the ledger disagree, and the checks below name where."}
          </p>
        </div>
      )}
    </section>
  );
}

function TotalRow({ row }: { row: RollforwardBlock["total"] }) {
  const parts = rollforwardParts(row ?? {});
  return (
    <tr className="h-row border-t border-ink">
      <td colSpan={2}>Totals</td>
      <td className="text-right">{formatMoney(parts.opening, { symbol: true })}</td>
      <td className="text-right">{formatMoney(parts.additions, { symbol: true })}</td>
      <td className="text-right">{formatMoney(-parts.depreciation, { symbol: true })}</td>
      <td className="text-right">{formatMoney(-parts.disposals, { symbol: true })}</td>
      <td className="text-right">{formatMoney(parts.closing, { symbol: true })}</td>
    </tr>
  );
}

/**
 * Book to tax, in the M-1 shape: the book loss, less the differences, is the tax
 * loss. Each row says why the two numbers disagree, in one sentence.
 */
export function Reconciliation({ block }: { block: ReconciliationBlock }) {
  const rows = block.rows ?? [];
  const foots = reconciliationFoots(block);

  return (
    <section>
      <SectionTitle>Book to tax reconciliation</SectionTitle>
      <p className="pb-2 pt-1 text-caption text-ink-soft">
        {block.title ?? "Schedule M-1 shape. The books lose one number, the return another, and the gap has a reason on every line."}
      </p>
      {rows.length === 0 ? (
        <p className="text-body text-ink-soft">
          Nothing disposed in this period, so the books and the return agree.
        </p>
      ) : (
        <div className="overflow-x-auto">
          <p className="pb-2 text-caption text-ink-soft md:hidden">Swipe sideways for the rest of the columns.</p>
          <table className="ledger green-bar w-full min-w-[620px] border-collapse text-body">
            <thead>
              <tr className="border-b border-rule text-caption text-ink-soft">
                <th className="py-1 font-normal">Item</th>
                <th className="py-1 text-right font-normal">Book loss ($)</th>
                <th className="py-1 text-right font-normal">Tax loss ($)</th>
                <th className="py-1 text-right font-normal">Difference ($)</th>
                <th className="py-1 font-normal">Why</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.event_id} className="h-row border-b border-rule hover:bg-bar">
                  <td>
                    <Link
                      className="underline underline-offset-2"
                      href={"/events/" + row.event_id}
                    >
                      {row.description || "Ticket " + row.event_id}
                    </Link>
                    {row.tag ? (
                      <Badge tone="ink" condensed>
                        {formatTag(row.tag)}
                      </Badge>
                    ) : null}
                  </td>
                  <td className="text-right">{formatMoney(row.book_loss_cents ?? 0)}</td>
                  <td className="text-right">{formatMoney(row.tax_loss_cents ?? 0)}</td>
                  <td className="text-right">{formatMoney(row.difference_cents ?? 0)}</td>
                  <td className="text-ink-soft">{row.reason}</td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr className="h-row border-t border-ink">
                <td>Totals</td>
                <td className="text-right">
                  {formatMoney(block.book_loss_cents ?? 0, { symbol: true })}
                </td>
                <td className="text-right">
                  {formatMoney(block.tax_loss_cents ?? 0, { symbol: true })}
                </td>
                <td className="text-right">
                  {formatMoney(block.differences_cents ?? 0, { symbol: true })}
                </td>
                <td />
              </tr>
            </tfoot>
          </table>
          <p className={cx("pt-2 text-caption", foots ? "text-ink-soft" : "text-red-ink")}>
            {foots
              ? "The book loss less the differences is the tax loss."
              : "The book loss less the differences does not come to the tax loss. Something is missing from this schedule."}
          </p>
        </div>
      )}
    </section>
  );
}

/**
 * The Form 4797 schedule: Part II for ordinary losses, Part III for the assets
 * that carry depreciation recapture. The disclaimer is the backend's own, because
 * this is a working paper and not a filing.
 */
export function Form4797({ block }: { block: Form4797Block }) {
  const partII = block.part_ii_rows ?? [];
  const partIII = block.part_iii_rows ?? [];

  return (
    <section>
      <SectionTitle>Form 4797 schedule</SectionTitle>
      <p className="pb-2 pt-1 text-caption text-ink-soft">
        Sales of business property, as the return would carry it.
      </p>
      {partII.length === 0 && partIII.length === 0 ? (
        <p className="text-body text-ink-soft">
          No business property was disposed of in this period, so nothing reaches the form.
        </p>
      ) : (
        <>
          {partII.length > 0 ? (
            <PartTable
              title="Part II, ordinary gains and losses"
              rows={partII}
              total={block.part_ii_line_10_cents ?? 0}
              totalLabel="Line 10"
            />
          ) : null}
          {partIII.length > 0 ? (
            <div className="pt-6">
              <PartTable
                title="Part III, recapture on depreciated property"
                rows={partIII}
                total={block.part_iii_recapture_cents ?? 0}
                totalLabel="Recapture"
              />
            </div>
          ) : null}
        </>
      )}
      {block.disclaimer ? (
        <p className="pt-3 text-caption text-ink-soft">{block.disclaimer}</p>
      ) : null}
    </section>
  );
}

function PartTable({
  title,
  rows,
  total,
  totalLabel,
}: {
  title: string;
  rows: Form4797Row[];
  total: number;
  totalLabel: string;
}) {
  return (
    <div>
      <h3 className="pb-2 text-section">{title}</h3>
      <div className="overflow-x-auto">
        <table className="ledger green-bar w-full min-w-[720px] border-collapse text-body">
          <thead>
            <tr className="border-b border-rule text-caption text-ink-soft">
              <th className="py-1 font-normal">Property</th>
              <th className="py-1 font-normal">Acquired</th>
              <th className="py-1 font-normal">Disposed</th>
              <th className="py-1 text-right font-normal">Proceeds ($)</th>
              <th className="py-1 text-right font-normal">Cost ($)</th>
              <th className="py-1 text-right font-normal">Depreciation ($)</th>
              <th className="py-1 text-right font-normal">Gain or loss ($)</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row, i) => (
              <tr
                key={(row.description ?? "") + "-" + i}
                className="h-row border-b border-rule hover:bg-bar"
              >
                <td>
                  {row.description}
                  {row.recapture_note ? (
                    <span className="block text-caption text-ink-soft">{row.recapture_note}</span>
                  ) : null}
                </td>
                <td className="whitespace-nowrap text-ink-soft">
                  {row.date_acquired ? formatDate(row.date_acquired) : ""}
                </td>
                <td className="whitespace-nowrap text-ink-soft">
                  {row.date_disposed ? formatDate(row.date_disposed) : ""}
                </td>
                <td className="text-right">{formatMoney(row.gross_proceeds_cents ?? 0)}</td>
                <td className="text-right">{formatMoney(row.cost_cents ?? 0)}</td>
                <td className="text-right">
                  {formatMoney(row.depreciation_allowed_cents ?? 0)}
                </td>
                <td className="text-right">{formatMoney(row.gain_or_loss_cents ?? 0)}</td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr className="h-row border-t border-ink">
              <td colSpan={6}>{totalLabel}</td>
              <td className="text-right">{formatMoney(total, { symbol: true })}</td>
            </tr>
          </tfoot>
        </table>
      </div>
    </div>
  );
}
