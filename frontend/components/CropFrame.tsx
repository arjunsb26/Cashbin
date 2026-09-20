"use client";

import { useEffect, useState } from "react";
import { ImageOff } from "lucide-react";
import { cx } from "./ui";

/**
 * The crop from the phone camera. With no phone connected the frame says what
 * fills it rather than showing a fake picture.
 */
export function CropFrame({
  src,
  label,
  size = 96,
  className,
}: {
  src: string | null;
  label: string;
  size?: number;
  className?: string;
}) {
  const [failed, setFailed] = useState(false);
  useEffect(() => setFailed(false), [src]);

  if (src && !failed) {
    return (
      // eslint-disable-next-line @next/next/no-img-element
      <img
        src={src}
        alt={label}
        width={size}
        height={size}
        onError={() => setFailed(true)}
        className={cx("border border-rule object-cover", className)}
        style={{ width: size, height: size }}
      />
    );
  }
  return (
    <div
      className={cx(
        "flex flex-col items-center justify-center gap-1 border border-dashed border-rule bg-bar p-2 text-center text-caption text-ink-soft",
        className,
      )}
      style={{ width: size, height: size }}
      title="Photo arrives with the phone camera"
    >
      <ImageOff size={16} strokeWidth={1.5} aria-hidden="true" />
      {size >= 96 ? <span>Photo arrives with the phone camera</span> : null}
    </div>
  );
}
