"use client";

import { useAssets } from "@/lib/api";
import { AssetTag } from "@/components/AssetTag";
import { Button, EmptyState, ErrorState, PageHeader, Skeleton } from "@/components/ui";

export default function TagSheetPage() {
  const assets = useAssets();
  const rows = (assets.data ?? []).filter((a) => a.status !== "disposed");

  return (
    <div>
      <div className="no-print">
        <PageHeader
          title="Asset tags"
          description="One label per active asset. Print the sheet, or hold a tag up to the camera from this screen."
          right={
            <Button tone="primary" onClick={() => window.print()}>
              Print tags
            </Button>
          }
        />
      </div>

      {assets.isPending ? (
        <div className="flex flex-wrap gap-3">
          {[0, 1, 2, 3, 4, 5].map((i) => (
            <Skeleton key={i} className="h-[120px] w-[232px]" />
          ))}
        </div>
      ) : null}

      {assets.isError ? (
        <ErrorState
          title="The register did not load, so there are no tags to print."
          onRetry={() => assets.refetch()}
        />
      ) : null}

      {assets.data && rows.length === 0 ? (
        <EmptyState title="No active assets, so there is nothing to print. Add an asset first." />
      ) : null}

      <div className="flex flex-wrap gap-3">
        {rows.map((asset) => (
          <AssetTag key={asset.id} asset={asset} />
        ))}
      </div>
    </div>
  );
}
