"use client";

import { useEffect, useRef, useState } from "react";
import QRCode from "qrcode";
import type { Asset } from "@/lib/types";
import { brand } from "@/lib/brand";

/**
 * A printed asset tag. The code in the QR is the tag itself, which is what the
 * camera reads back when the item is tossed.
 */
export function AssetTag({ asset, size = 96 }: { asset: Asset; size?: number }) {
  const [src, setSrc] = useState<string | null>(null);
  const host = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const element = host.current;
    if (!element) return;
    const style = getComputedStyle(element);
    void QRCode.toDataURL(asset.tag, {
      margin: 0,
      width: size * 2,
      color: {
        dark: style.getPropertyValue("--ink").trim(),
        light: style.getPropertyValue("--surface").trim(),
      },
    }).then(setSrc);
  }, [asset.tag, size]);

  return (
    <div
      ref={host}
      className="flex w-[232px] items-center gap-3 border border-ink bg-surface p-3"
    >
      {src ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={src} alt={`QR code for ${asset.tag}`} width={size} height={size} />
      ) : (
        <span
          className="block animate-skeleton bg-bar"
          style={{ width: size, height: size }}
          aria-hidden="true"
        />
      )}
      <div className="min-w-0">
        <p className="font-condensed text-section">{asset.tag}</p>
        <p className="truncate text-caption">{asset.description}</p>
        <p className="truncate text-caption text-ink-soft">{asset.location}</p>
        <p className="pt-1 text-caption text-ink-soft">{brand.short_name}</p>
      </div>
    </div>
  );
}
