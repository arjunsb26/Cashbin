"use client";

import { useState } from "react";
import Link from "next/link";
import * as Dialog from "@radix-ui/react-dialog";
import { useReview, useReviewAnswer, useReviewDecision, useReviewRun } from "@/lib/api";
import {
  formatMoney,
  formatProbability,
  formatProvider,
  formatTag,
  formatTime,
  readLabel,
} from "@/lib/format";
import { PROPOSAL_WORDS, REVIEW_GROUPS, REVIEW_KIND_WORDS } from "@/lib/review";
import type { ReviewItemRead, ReviewKind, ReviewStatus } from "@/lib/types";
import {
  Button,
  EmptyState,
  ErrorState,
  Field,
  FinanceFooter,
  Input,
  PageHeader,
  SectionTitle,
  Skeleton,
  StatusDot,
  cx,
} from "@/components/ui";

/** What the screen has already decided, before the backend has answered. */
type Pending = Record<number, { status: ReviewStatus; note: string }>;

export default function ReviewPage() {
  const review = useReview();
  const [pending, setPending] = useState<Pending>({});
  const [refused, setRefused] = useState<Record<number, string>>({});
  const decide = useReviewDecision();
  const answer = useReviewAnswer();
  const run = useReviewRun();
  const items = review.data?.items ?? [];

  /**
   * The screen never waits on the network. The row moves the moment it is clicked
   * and the read is refetched when the backend answers, so a refusal puts the row
   * back where it was with the backend's own sentence under it.
   */
  const settle = (item: ReviewItemRead, decision: "approve" | "reject", note: string) => {
    setPending((now) => ({
      ...now,
      [item.id]: { status: decision === "approve" ? "approved" : "rejected", note },
    }));
    setRefused((now) => {
      const next = { ...now };
      delete next[item.id];
      return next;
    });
    decide.mutate(
      { id: item.id, decision, note },
      {
        onError: (error) => {
          setPending((now) => {
            const next = { ...now };
            delete next[item.id];
            return next;
          });
          setRefused((now) => ({ ...now, [item.id]: error.message }));
        },
      },
    );
  };

  const settleAsk = (item: ReviewItemRead, label: string) => {
    setPending((now) => ({ ...now, [item.id]: { status: "approved", note: label } }));
    answer.mutate(
      { id: item.id, label },
      {
        onError: (error) => {
          setPending((now) => {
            const next = { ...now };
            delete next[item.id];
            return next;
          });
          setRefused((now) => ({ ...now, [item.id]: error.message }));
        },
      },
    );
  };

  const statusOf = (item: ReviewItemRead): ReviewStatus =>
    pending[item.id]?.status ?? item.status;

  return (
    <div className="flex max-w-[860px] flex-col gap-8">
      <PageHeader
        title="Review"
        description="Everything the bin could not settle on its own, and everything a person should stand behind before it leaves the books."
        right={
          <Button loading={run.isPending} onClick={() => run.mutate()}>
            Ask the agent to look
          </Button>
        }
      />

      {/* The agent reads and proposes. It settles nothing, so the line under the
          button says how many items it got to and stops there. */}
      {run.isSuccess && run.data ? (
        <p className="-mt-6 text-caption text-ink-soft">
          The agent looked at{" "}
          {run.data.proposed === 1 ? "one item" : (run.data.proposed ?? 0) + " items"}. Nothing was
          decided: every reading below is still waiting on a person.
        </p>
      ) : null}
      {run.isError ? (
        <p className="-mt-6 text-caption text-red-ink">{(run.error as Error).message}</p>
      ) : null}

      {review.isPending ? <QueueSkeleton /> : null}

      {review.isError ? (
        <ErrorState
          title="The queue did not load. The backend is not answering."
          onRetry={() => review.refetch()}
        />
      ) : null}

      {/* A backend older than the review route answers 404, which arrives as null.
          An empty queue and a queue nobody asked are not the same thing. */}
      {!review.isPending && !review.isError && review.data === null ? (
        <ErrorState
          title="Nothing is answering for the queue. The items come from the bin's service, and it is not reporting them yet."
          onRetry={() => review.refetch()}
        />
      ) : null}

      {review.data && items.length === 0 ? (
        <EmptyState title="Nothing is waiting. Items land here when the bin cannot tell what something was, when a value came out of a model, or when something worth tagging was never on the register." />
      ) : null}

      {items.length > 0
        ? REVIEW_GROUPS.map((group) => {
            const rows = items.filter((item) =>
              (group.kinds as ReviewKind[]).includes(item.kind),
            );
            const open = rows.filter((item) => statusOf(item) === "open").length;
            return (
              <section key={group.id}>
                <SectionTitle
                  right={
                    <span className="text-caption text-ink-soft">
                      {open === 0 ? "All settled" : open + " open"}
                    </span>
                  }
                >
                  {group.title}
                </SectionTitle>
                <p className="pt-1 text-caption text-ink-soft">{group.blurb}</p>
                {rows.length === 0 ? (
                  <p className="pt-3 text-body text-ink-soft">
                    Nothing in this group. {group.blurb}
                  </p>
                ) : (
                  <ul className="m-0 list-none p-0 pt-2">
                    {rows.map((item) => (
                      <ReviewRow
                        key={item.id}
                        item={item}
                        status={statusOf(item)}
                        note={pending[item.id]?.note ?? item.note ?? null}
                        refused={refused[item.id] ?? null}
                        onSettle={settle}
                        onAnswer={settleAsk}
                      />
                    ))}
                  </ul>
                )}
              </section>
            );
          })
        : null}

      <FinanceFooter />
    </div>
  );
}

function ReviewRow({
  item,
  status,
  note,
  refused,
  onSettle,
  onAnswer,
}: {
  item: ReviewItemRead;
  status: ReviewStatus;
  note: string | null;
  refused: string | null;
  onSettle: (item: ReviewItemRead, decision: "approve" | "reject", note: string) => void;
  onAnswer: (item: ReviewItemRead, label: string) => void;
}) {
  const [other, setOther] = useState(false);
  const [raw, setRaw] = useState("");
  const read = readLabel(raw);
  const settled = status !== "open";
  const isAsk = item.kind === "unresolved_ask";
  const candidates = (item.candidates ?? []).slice(0, 4);

  return (
    <li className={cx("border-b border-rule py-3", settled && "text-ink-soft")}>
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <span className="text-section">
          {item.label || "Unidentified"}
          {item.asset_tag ? (
            <span className="pl-2 font-condensed text-body">{formatTag(item.asset_tag)}</span>
          ) : null}
        </span>
        <span className="text-body">
          {formatMoney(item.amount_cents ?? 0, { symbol: true })}
        </span>
      </div>
      <p className="pt-1 text-caption text-ink-soft">
        {item.reason ? "" : REVIEW_KIND_WORDS[item.kind] + ". "}
        {item.created_at ? formatTime(item.created_at) + ". " : ""}
        <Link className="underline underline-offset-2" href={"/events/" + item.event_id}>
          Ticket {item.event_id}
        </Link>
      </p>
      {item.reason ? <p className="pt-1 text-body">{item.reason}</p> : null}

      <Proposal item={item} />

      {settled ? (
        <p className="flex items-center gap-2 pt-2 text-body">
          <StatusDot tone={status === "approved" ? "kept" : "red"} />
          {status === "approved" ? "Approved" : "Rejected"}
          {note ? ", " + note : ""}
        </p>
      ) : isAsk ? (
        <div className="pt-3">
          <p className="pb-2 text-caption text-ink-soft">Which is it?</p>
          <div className="flex flex-wrap gap-2">
            {candidates.map((candidate) => (
              <Button key={candidate.label} onClick={() => onAnswer(item, candidate.label)}>
                {candidate.label}
                <span className="pl-2 text-caption text-ink-soft">
                  {formatProbability(candidate.p)}
                </span>
              </Button>
            ))}
            {other ? null : <Button onClick={() => setOther(true)}>Something else</Button>}
          </div>
          {other ? (
            <div className="flex max-w-[360px] flex-col gap-2 pt-3">
              <Field
                label="What it really is"
                hint="Up to 40 characters. Letters, digits, spaces and hyphens."
                htmlFor={"review-other-" + item.id}
              >
                <Input
                  id={"review-other-" + item.id}
                  value={raw}
                  onChange={(e) => setRaw(e.target.value)}
                  placeholder="cable coil"
                />
              </Field>
              {raw.length > 0 ? (
                <p className={cx("text-caption", read.ok ? "text-ink-soft" : "text-red-ink")}>
                  {read.ok
                    ? 'Understood as "' + read.label + '".'
                    : "Nothing usable in that. Try letters and digits."}
                  {read.dropped ? " Left out: " + read.dropped : ""}
                </p>
              ) : null}
              <div className="flex gap-2">
                <Button
                  tone="primary"
                  disabled={!read.ok}
                  onClick={() => onAnswer(item, read.label)}
                >
                  Use this label
                </Button>
                <Button onClick={() => setOther(false)}>Back to the candidates</Button>
              </div>
            </div>
          ) : null}
        </div>
      ) : (
        <div className="flex flex-wrap gap-2 pt-3">
          <NoteDialog item={item} decision="approve" onSettle={onSettle} />
          <NoteDialog item={item} decision="reject" onSettle={onSettle} />
        </div>
      )}

      {refused ? <p className="pt-2 text-body text-red-ink">{refused}</p> : null}
    </li>
  );
}

/**
 * What the review agent made of the row, and the lookups behind it.
 *
 * The agent proposes and never acts, so this block says what it would do and
 * leaves the two buttons exactly where they were. Its words are model output, so
 * they are printed as text and nothing in them is read back as an instruction.
 * The working folds away, because a person who already agrees does not need it,
 * and a person who does not can open it and read every lookup that was made.
 */
function Proposal({ item }: { item: ReviewItemRead }) {
  const [open, setOpen] = useState(false);
  const proposal = item.proposal;
  if (!proposal) return null;
  const steps = proposal.steps ?? [];
  const served = formatProvider(proposal.provider, proposal.model);

  return (
    <div className="mt-2 border-l-2 border-rule pl-3">
      <p className="text-body">
        {proposal.decision ? PROPOSAL_WORDS[proposal.decision] : "The agent read this"}
        {proposal.reason ? ". " + proposal.reason : "."}
      </p>
      {proposal.downgraded_reason ? (
        <p className="pt-1 text-caption text-ink-soft">
          It stopped short of a view: {proposal.downgraded_reason}
        </p>
      ) : null}
      {steps.length > 0 ? (
        <>
          <button
            type="button"
            onClick={() => setOpen(!open)}
            aria-expanded={open}
            className="mt-1 block text-caption text-ink-soft underline underline-offset-2"
          >
            {open
              ? "Hide the working"
              : "Looked at " + (steps.length === 1 ? "one thing" : steps.length + " things")}
          </button>
          {open ? (
            <ul className="m-0 list-none p-0 pt-2">
              {steps.map((step, i) => (
                <li key={i} className="border-t border-rule py-1 first:border-t-0">
                  <p className="text-caption text-ink-soft">
                    {step.tool ?? "Looked something up"}
                    {step.args_summary ? ": " + step.args_summary : ""}
                  </p>
                  {step.finding ? <p className="text-body">{step.finding}</p> : null}
                </li>
              ))}
            </ul>
          ) : null}
        </>
      ) : null}
      {served || proposal.latency_ms ? (
        <p className="pt-1 text-caption text-ink-soft">
          {served}
          {served && proposal.latency_ms ? ", " : ""}
          {proposal.latency_ms ? Math.round(proposal.latency_ms / 100) / 10 + " s" : ""}
        </p>
      ) : null}
    </div>
  );
}

/**
 * The note that goes with a decision, in a dialog.
 *
 * Approving and rejecting are the page's whole job, but writing the sentence that
 * goes with one is the secondary step, and a box that unfolds inside a list moves
 * every row under it. The dialog takes the focus, keeps the row still, and says
 * in its own title which row is being settled.
 */
function NoteDialog({
  item,
  decision,
  onSettle,
}: {
  item: ReviewItemRead;
  decision: "approve" | "reject";
  onSettle: (item: ReviewItemRead, decision: "approve" | "reject", note: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const [typed, setTyped] = useState("");
  const approving = decision === "approve";

  return (
    <Dialog.Root open={open} onOpenChange={setOpen}>
      <Dialog.Trigger asChild>
        <Button tone={approving ? "primary" : "danger"}>
          {approving ? "Approve" : "Reject"}
        </Button>
      </Dialog.Trigger>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-[var(--scrim)]" />
        <Dialog.Content
          className="fixed left-1/2 top-1/2 max-h-[calc(100dvh-32px)] w-[440px] max-w-[calc(100vw-32px)] -translate-x-1/2 -translate-y-1/2 overflow-y-auto rounded-control border border-rule bg-surface p-5 shadow-overlay"
          aria-describedby={undefined}
        >
          <Dialog.Title className="text-title">
            {approving ? "Approve" : "Reject"} {item.label || "this ticket"}
          </Dialog.Title>
          <p className="pb-4 pt-1 text-caption text-ink-soft">
            {approving
              ? "The posting stands and the question closes. The ledger does not move."
              : "What the ticket claimed is undone. The entries are reversed, never deleted."}
          </p>
          <div className="flex flex-col gap-3">
            <Field
              label="Why"
              hint="One line, for whoever reads the books after you. It is kept with the decision."
              htmlFor={"review-note-" + item.id}
            >
              <Input
                id={"review-note-" + item.id}
                value={typed}
                onChange={(e) => setTyped(e.target.value)}
                placeholder={approving ? "Checked against the receipt" : "Not ours"}
              />
            </Field>
            <div className="flex gap-2">
              <Button
                tone={approving ? "primary" : "danger"}
                onClick={() => {
                  onSettle(item, decision, typed.trim().slice(0, 120));
                  setOpen(false);
                }}
              >
                {approving ? "Approve it" : "Reject it"}
              </Button>
              <Dialog.Close asChild>
                <Button>Cancel</Button>
              </Dialog.Close>
            </div>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

function QueueSkeleton() {
  return (
    <div className="flex flex-col gap-6">
      {[0, 1, 2].map((i) => (
        <div key={i} className="flex flex-col gap-2">
          <Skeleton className="h-5 w-48" />
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-row w-full" />
          <Skeleton className="h-row w-full" />
        </div>
      ))}
    </div>
  );
}
