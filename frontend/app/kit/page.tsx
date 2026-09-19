"use client";

import { useState } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import * as Popover from "@radix-ui/react-popover";
import * as Tabs from "@radix-ui/react-tabs";
import * as Tooltip from "@radix-ui/react-tooltip";
import { sampleData as fixtures } from "@/lib/api";
import type { EventDetail } from "@/lib/types";
import { AskPanel } from "@/components/AskPanel";
import { AssetTag } from "@/components/AssetTag";
import { CropFrame } from "@/components/CropFrame";
import { EvidenceBody } from "@/components/EvidenceBody";
import { Co2, Mass, Money } from "@/components/Figure";
import { LearningChart } from "@/components/LearningChart";
import { ProbabilityBars } from "@/components/ProbabilityBars";
import { ScaleStrip } from "@/components/ScaleStrip";
import { TAccounts } from "@/components/TAccounts";
import { Tape } from "@/components/Tape";
import { Ticket } from "@/components/Ticket";
import { TraceChart } from "@/components/TraceChart";
import {
  Button,
  EmptyState,
  ErrorState,
  Field,
  FinanceFooter,
  Input,
  PageHeader,
  SectionTitle,
  Select,
  Skeleton,
  StatusDot,
  cx,
} from "@/components/ui";

// Every component in every state, on one page. Nothing is used in a page before it
// appears here. Not linked from the rail.
export default function KitPage() {
  const keyboard = fixtures.EVENT_DETAILS[102] as EventDetail;
  const asking = fixtures.EVENT_DETAILS[105] as EventDetail;
  const charger = fixtures.EVENT_DETAILS[103] as EventDetail;

  return (
    <div className="flex flex-col gap-10">
      <PageHeader title="Kit" description="Every component in every state, for review." />

      <Block title="Type scale">
        <div className="flex flex-col gap-2">
          <p className="font-condensed text-figure leading-none">2,412</p>
          <p className="font-condensed text-total">$41.80</p>
          <p className="text-title">Page title</p>
          <p className="text-section">Section title</p>
          <p className="text-body">Body and table cells, 14 over 20.</p>
          <p className="text-caption text-ink-soft">Secondary, units and captions.</p>
        </div>
      </Block>

      <Block title="Colour, each one carrying its meaning">
        <ul className="m-0 flex list-none flex-wrap gap-4 p-0 text-caption">
          {[
            ["paper", "App background"],
            ["bar", "Green-bar rows"],
            ["ink", "Text and primary buttons"],
            ["ink-soft", "Units and secondary text"],
            ["rule", "Ruled lines"],
            ["control-border", "Control edges"],
            ["red-ink", "Losses and errors"],
            ["kept", "Money kept, checks passing"],
            ["caution", "A better option existed"],
            ["surface", "The ticket and overlays"],
          ].map(([name, use]) => (
            <li key={name} className="w-[168px]">
              <span
                className="block h-8 border border-rule"
                style={{ background: `var(--${name})` }}
              />
              <span className="block pt-1">{name}</span>
              <span className="block text-ink-soft">{use}</span>
            </li>
          ))}
        </ul>
      </Block>

      <Block title="Buttons">
        <div className="flex flex-wrap items-center gap-3">
          <Button tone="primary">Run close</Button>
          <Button>Print tags</Button>
          <Button tone="danger">Void ticket</Button>
          <Button disabled>Not available</Button>
          <Button loading>Saving</Button>
          <Button autoFocus>Focused on load</Button>
        </div>
        <p className="pt-2 text-caption text-ink-soft">
          Hover fills with the green-bar tint. Focus draws a 2 px ink ring, 2 px out.
        </p>
      </Block>

      <Block title="Fields">
        <div className="grid max-w-[520px] grid-cols-1 gap-4">
          <Field label="Tag" hint="Two letters, a hyphen, four digits." htmlFor="kit-tag">
            <Input id="kit-tag" placeholder="BB-0013" />
          </Field>
          <Field
            label="Cost"
            hint="What was paid, in dollars."
            htmlFor="kit-cost"
            error="That is not a number."
          >
            <Input id="kit-cost" defaultValue="twelve" />
          </Field>
          <Field label="Tax treatment" hint="Bonus writes it all off in year one." htmlFor="kit-tax">
            <Select id="kit-tax" defaultValue="bonus_100">
              <option value="bonus_100">Bonus, 100% in year one</option>
              <option value="straight_line">Straight line</option>
            </Select>
          </Field>
          <Field label="Location" hint="Where it normally lives." htmlFor="kit-loc">
            <Input id="kit-loc" disabled value="Desk 1" readOnly />
          </Field>
        </div>
      </Block>

      <Block title="Numbers, all of them clickable">
        <div className="flex flex-wrap items-baseline gap-6 text-body">
          <Money cents={-2000} eventId={102} focus="book loss" />
          <Money cents={4180} symbol eventId={102} focus="saved" />
          <Money cents={800} estimate eventId={103} focus="resale" />
          <Mass grams={212} eventId={102} focus="mass" />
          <Mass grams={2412} eventId={102} focus="scale" />
          <Co2 kg={0.41} eventId={102} focus="carbon" />
          <Co2 kg={null} />
        </div>
        <p className="pt-2 text-caption text-ink-soft">
          Nothing at rest, a dotted rule on hover, and a click opens the evidence.
        </p>
      </Block>

      <Block title="Status">
        <ul className="m-0 flex list-none flex-wrap gap-6 p-0 text-body">
          <li className="flex items-center gap-2">
            <StatusDot tone="kept" /> Active
          </li>
          <li className="flex items-center gap-2">
            <StatusDot tone="caution" /> Ghost suspected
          </li>
          <li className="flex items-center gap-2">
            <StatusDot tone="red" /> Blocked
          </li>
          <li className="flex items-center gap-2">
            <StatusDot tone="soft" /> Disposed
          </li>
        </ul>
      </Block>

      <Block title="Loading, empty and error">
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          <div className="flex flex-col gap-2">
            <Skeleton className="h-row w-full" />
            <Skeleton className="h-row w-full" />
            <Skeleton className="h-row w-2/3" />
          </div>
          <EmptyState
            title="No tickets yet. Toss something in the bin, or run the simulator."
            action={<Button>Run the simulator</Button>}
          />
          <ErrorState title="The phone camera disconnected. Tickets will be weighed but not photographed until it reconnects." />
        </div>
      </Block>

      <Block title="Overlays">
        <div className="flex flex-wrap items-center gap-3">
          <Dialog.Root>
            <Dialog.Trigger asChild>
              <Button>Open a dialog</Button>
            </Dialog.Trigger>
            <Dialog.Portal>
              <Dialog.Overlay className="fixed inset-0 bg-[var(--scrim)]" />
              <Dialog.Content
                className="fixed left-1/2 top-1/2 w-[360px] -translate-x-1/2 -translate-y-1/2 rounded-control border border-rule bg-surface p-5 shadow-overlay"
                aria-describedby={undefined}
              >
                <Dialog.Title className="text-title">Void this ticket</Dialog.Title>
                <p className="pt-2 text-body">
                  A void posts a reversing entry. The original stays on the tape.
                </p>
                <div className="flex justify-end gap-2 pt-4">
                  <Dialog.Close asChild>
                    <Button>Keep it</Button>
                  </Dialog.Close>
                  <Dialog.Close asChild>
                    <Button tone="danger">Void ticket</Button>
                  </Dialog.Close>
                </div>
              </Dialog.Content>
            </Dialog.Portal>
          </Dialog.Root>

          <Popover.Root>
            <Popover.Trigger asChild>
              <Button>Open a popover</Button>
            </Popover.Trigger>
            <Popover.Portal>
              <Popover.Content
                sideOffset={6}
                className="max-w-[280px] rounded-control border border-control-border bg-surface p-3 text-body shadow-overlay"
              >
                Resale, donation and repair count as source reduction, because they displace a new
                item.
              </Popover.Content>
            </Popover.Portal>
          </Popover.Root>

          <Tooltip.Root>
            <Tooltip.Trigger asChild>
              <Button>Hover for a tooltip</Button>
            </Tooltip.Trigger>
            <Tooltip.Portal>
              <Tooltip.Content
                sideOffset={6}
                className="rounded-control border border-control-border bg-surface px-2 py-1 text-caption shadow-overlay"
              >
                Estimated range 5.00 to 12.00, from the value model.
              </Tooltip.Content>
            </Tooltip.Portal>
          </Tooltip.Root>
        </div>
      </Block>

      <Block title="Tabs">
        <Tabs.Root defaultValue="journal">
          <Tabs.List className="flex gap-4 border-b border-rule">
            {["journal", "trial"].map((value) => (
              <Tabs.Trigger
                key={value}
                value={value}
                className={cx(
                  "-mb-px border-b-2 border-transparent px-1 pb-2 text-section text-ink-soft",
                  "data-[state=active]:border-b-ink data-[state=active]:text-ink",
                )}
              >
                {value === "journal" ? "Journal" : "Trial balance"}
              </Tabs.Trigger>
            ))}
          </Tabs.List>
          <Tabs.Content value="journal" className="pt-3 text-body">
            Entries, newest first.
          </Tabs.Content>
          <Tabs.Content value="trial" className="pt-3 text-body">
            Accounts with their debit and credit totals.
          </Tabs.Content>
        </Tabs.Root>
      </Block>

      <Block title="Green-bar table">
        <table className="green-bar w-full max-w-[640px] border-collapse text-body">
          <thead>
            <tr className="border-b border-rule text-caption text-ink-soft">
              <th className="py-1 pl-2 font-normal">Account</th>
              <th className="py-1 text-right font-normal">Debit ($)</th>
              <th className="py-1 pr-2 text-right font-normal">Credit ($)</th>
            </tr>
          </thead>
          <tbody>
            {fixtures.TRIAL_BALANCE.slice(0, 4).map((row) => (
              <tr key={row.account} className="h-row border-b border-rule hover:bg-bar">
                <td className="pl-2">{row.account}</td>
                <td className="text-right">
                  <Money cents={row.debit_cents} />
                </td>
                <td className="pr-2 text-right">
                  <Money cents={row.credit_cents} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Block>

      <Block title="Scale strip">
        <ScaleStrip
          samples={Array.from({ length: 120 }, (_, i) => 2412 + Math.sin(i / 4) * 3)}
          steps={[40, 88]}
          weight_g={2412}
          connected
        />
        <ScaleStrip samples={Array.from({ length: 120 }, () => 0)} steps={[]} weight_g={0} connected={false} />
      </Block>

      <Block title="The ticket">
        <div className="flex flex-wrap items-start gap-6">
          <Ticket detail={keyboard} phase="weighing" />
          <Ticket detail={keyboard} phase="identified" />
        </div>
        <div className="flex flex-wrap items-start gap-6 pt-6">
          <Ticket detail={charger} />
          <Ticket detail={asking} phase="weighing">
            {asking.ask ? <AskPanel ask={asking.ask} /> : undefined}
          </Ticket>
        </div>
        <div className="pt-6">
          <p className="pb-2 text-caption text-ink-soft">At phone width, 390 px.</p>
          <Ticket detail={keyboard} width={358} showMenu={false} />
        </div>
      </Block>

      <Block title="Tape">
        <div className="max-w-[420px]">
          <Tape events={fixtures.EVENTS} />
        </div>
        <div className="max-w-[420px] pt-4">
          <Tape events={[]} />
        </div>
      </Block>

      <Block title="Evidence">
        <div className="max-w-[420px]">
          <EvidenceBody evidence={fixtures.EVIDENCE[102]!} />
        </div>
      </Block>

      <Block title="Pieces of the evidence">
        <div className="flex flex-wrap items-start gap-8">
          <CropFrame src={null} label="Empty crop" size={96} />
          <div className="w-[360px]">
            <TraceChart trace={fixtures.EVIDENCE[101]!.trace} />
          </div>
          <div className="w-[240px]">
            <ProbabilityBars
              title="From the photo alone"
              candidates={fixtures.EVIDENCE[101]!.identification.candidates}
            />
          </div>
        </div>
      </Block>

      <Block title="T-accounts">
        <TAccounts
          entries={fixtures.ENTRIES.filter((e) => e.event_id === 102)}
          difference="The books lose 20.00. The tax deduction is 0.00 because this asset was fully expensed when it was bought."
        />
      </Block>

      <Block title="Learning chart">
        <LearningChart rounds={fixtures.ROUNDS} />
      </Block>

      <Block title="Asset tag">
        <div className="flex flex-wrap gap-3">
          <AssetTag asset={fixtures.ASSETS[1]!} />
          <AssetTag asset={fixtures.ASSETS[8]!} />
        </div>
      </Block>

      <Block title="Finance footer">
        <FinanceFooter />
      </Block>
    </div>
  );
}

function Block({ title, children }: { title: string; children: React.ReactNode }) {
  const [open, setOpen] = useState(true);
  return (
    <section>
      <SectionTitle
        right={
          <button
            type="button"
            className="text-caption text-ink-soft underline underline-offset-2"
            onClick={() => setOpen((v) => !v)}
          >
            {open ? "Hide" : "Show"}
          </button>
        }
      >
        {title}
      </SectionTitle>
      {open ? <div className="pt-4">{children}</div> : null}
    </section>
  );
}
