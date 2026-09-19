"use client";

import { useState } from "react";
import Link from "next/link";
import * as Dialog from "@radix-ui/react-dialog";
import { useAddAsset, useAssets } from "@/lib/api";
import { formatDate, readLabel } from "@/lib/format";
import type { Asset, AssetStatus, NewAsset } from "@/lib/types";
import { Money } from "@/components/Figure";
import {
  Button,
  EmptyState,
  ErrorState,
  Field,
  FinanceFooter,
  Input,
  PageHeader,
  Select,
  Skeleton,
  StatusDot,
  cx,
} from "@/components/ui";

const STATUS_WORDS: Record<AssetStatus, string> = {
  active: "Active",
  disposed: "Disposed",
  ghost_suspected: "Ghost suspected",
};

const STATUS_TONES: Record<AssetStatus, "kept" | "soft" | "caution"> = {
  active: "kept",
  disposed: "soft",
  ghost_suspected: "caution",
};

export default function AssetsPage() {
  const assets = useAssets();
  const [filter, setFilter] = useState<"all" | AssetStatus>("all");
  const rows = (assets.data ?? []).filter((a) => filter === "all" || a.status === filter);

  return (
    <div>
      <PageHeader
        title="Asset register"
        description="Tagged equipment. The tag is what the camera reads when something goes in the bin."
        right={
          <>
            <label className="flex items-center gap-2 text-caption text-ink-soft">
              Show
              <Select
                value={filter}
                onChange={(e) => setFilter(e.target.value as "all" | AssetStatus)}
                aria-label="Which assets to show"
              >
                <option value="all">Everything</option>
                <option value="active">Active</option>
                <option value="ghost_suspected">Ghost suspects</option>
                <option value="disposed">Disposed</option>
              </Select>
            </label>
            <Link
              href="/assets/tags"
              className="inline-flex h-9 items-center rounded-control border border-control-border bg-surface px-3 text-body hover:bg-bar"
            >
              Print tags
            </Link>
            <AddAssetDialog />
          </>
        }
      />

      {assets.isPending ? (
        <div className="flex flex-col gap-2">
          {[0, 1, 2, 3, 4, 5, 6].map((i) => (
            <Skeleton key={i} className="h-row w-full" />
          ))}
        </div>
      ) : null}

      {assets.isError ? (
        <ErrorState
          title="The register did not load. The backend is not answering."
          onRetry={() => assets.refetch()}
        />
      ) : null}

      {assets.data && rows.length === 0 ? (
        <EmptyState title="No assets in this view. Add one, or clear the filter." />
      ) : null}

      {rows.length > 0 ? (
        <div className="overflow-x-auto">
          <table className="ledger green-bar w-full min-w-[860px] border-collapse text-body">
            <thead>
              <tr className="border-b border-rule text-caption text-ink-soft">
                <th className="py-1 font-normal">Tag</th>
                <th className="py-1 font-normal">Description</th>
                <th className="py-1 text-right font-normal">Cost ($)</th>
                <th className="py-1 font-normal">In service</th>
                <th className="py-1 text-right font-normal">Book value ($)</th>
                <th className="py-1 text-right font-normal">Tax basis ($)</th>
                <th className="py-1 font-normal">Status</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((asset) => (
                <AssetRow key={asset.id} asset={asset} />
              ))}
            </tbody>
          </table>
        </div>
      ) : null}

      <FinanceFooter />
    </div>
  );
}

function AssetRow({ asset }: { asset: Asset }) {
  return (
    <tr className="h-row border-b border-rule hover:bg-bar">
      <td className="font-condensed">{asset.tag}</td>
      <td>{asset.description}</td>
      <td className="text-right">
        <Money cents={asset.cost_cents} eventId={asset.disposed_event_id} focus="cost" />
      </td>
      <td className="whitespace-nowrap text-ink-soft">{formatDate(asset.in_service_date)}</td>
      <td className="text-right">
        <Money
          cents={asset.book_value_cents}
          eventId={asset.disposed_event_id}
          focus="book value"
        />
      </td>
      <td className="text-right">
        <Money cents={asset.tax_basis_cents} eventId={asset.disposed_event_id} focus="tax basis" />
      </td>
      <td>
        <span className="flex items-center gap-2 whitespace-nowrap">
          <StatusDot tone={STATUS_TONES[asset.status]} />
          {STATUS_WORDS[asset.status]}
        </span>
      </td>
    </tr>
  );
}

const EMPTY_FORM: NewAsset = {
  tag: "",
  description: "",
  category: "",
  cost_cents: 0,
  in_service_date: "",
  book_life_months: 36,
  tax_method: "bonus_100",
  location: "",
};

function AddAssetDialog() {
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState<NewAsset>(EMPTY_FORM);
  const [cost, setCost] = useState("");
  const add = useAddAsset();
  const description = readLabel(form.description);
  const tagOk = /^[A-Za-z]{2}-\d{4}$/.test(form.tag);
  const costCents = Math.round(Number(cost.replace(/[^0-9.]/g, "")) * 100);
  const ready = tagOk && description.ok && Number.isFinite(costCents) && costCents > 0;

  return (
    <Dialog.Root
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        if (!next) {
          setForm(EMPTY_FORM);
          setCost("");
        }
      }}
    >
      <Dialog.Trigger asChild>
        <Button tone="primary">Add asset</Button>
      </Dialog.Trigger>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-[var(--scrim)]" />
        <Dialog.Content
          className="fixed left-1/2 top-1/2 w-[440px] max-w-[calc(100vw-32px)] -translate-x-1/2 -translate-y-1/2 rounded-control border border-rule bg-surface p-5 shadow-overlay"
          aria-describedby={undefined}
        >
          <Dialog.Title className="text-title">Add asset</Dialog.Title>
          <p className="pb-4 pt-1 text-caption text-ink-soft">
            Print its tag afterwards and stick it on the item.
          </p>
          <div className="flex flex-col gap-4">
            <Field
              label="Tag"
              hint="Two letters, a hyphen, four digits. For example BB-0013."
              htmlFor="asset-tag"
              error={form.tag.length > 0 && !tagOk ? "That is not a tag code." : null}
            >
              <Input
                id="asset-tag"
                value={form.tag}
                onChange={(e) => setForm({ ...form, tag: e.target.value })}
                placeholder="BB-0013"
              />
            </Field>
            <Field
              label="Description"
              hint="What a person would call it. Up to 40 characters."
              htmlFor="asset-description"
            >
              <Input
                id="asset-description"
                value={form.description}
                onChange={(e) => setForm({ ...form, description: e.target.value })}
                placeholder="Keychron K8 keyboard"
              />
            </Field>
            <Field label="Cost" hint="What was paid, in dollars." htmlFor="asset-cost">
              <Input
                id="asset-cost"
                value={cost}
                onChange={(e) => setCost(e.target.value)}
                placeholder="120.00"
                inputMode="decimal"
              />
            </Field>
            <Field
              label="In service date"
              hint="The day it started being used."
              htmlFor="asset-date"
            >
              <Input
                id="asset-date"
                type="date"
                value={form.in_service_date}
                onChange={(e) => setForm({ ...form, in_service_date: e.target.value })}
              />
            </Field>
            <Field
              label="Tax treatment"
              hint="Bonus depreciation writes the whole cost off in year one, so the tax basis is zero."
              htmlFor="asset-tax"
            >
              <Select
                id="asset-tax"
                value={form.tax_method}
                onChange={(e) =>
                  setForm({ ...form, tax_method: e.target.value as NewAsset["tax_method"] })
                }
              >
                <option value="bonus_100">Bonus, 100% in year one</option>
                <option value="straight_line">Straight line</option>
              </Select>
            </Field>
            <Field label="Location" hint="Where it normally lives." htmlFor="asset-location">
              <Input
                id="asset-location"
                value={form.location}
                onChange={(e) => setForm({ ...form, location: e.target.value })}
                placeholder="Desk 1"
              />
            </Field>
          </div>
          <div className={cx("flex justify-end gap-2 pt-5")}>
            <Dialog.Close asChild>
              <Button>Cancel</Button>
            </Dialog.Close>
            <Button
              tone="primary"
              disabled={!ready}
              loading={add.isPending}
              onClick={() => {
                add.mutate(
                  { ...form, description: description.label, cost_cents: costCents },
                  { onSuccess: () => setOpen(false) },
                );
              }}
            >
              Add asset
            </Button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
