"use client";

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
  if (src) {
    return (
      // eslint-disable-next-line @next/next/no-img-element
      <img
        src={src}
        alt={label}
        width={size}
        height={size}
        className={cx("border border-rule object-cover", className)}
        style={{ width: size, height: size }}
      />
    );
  }
  return (
    <div
      className={cx(
        "flex items-center justify-center border border-dashed border-rule bg-bar p-2 text-center text-caption text-ink-soft",
        className,
      )}
      style={{ width: size, height: size }}
    >
      Photo arrives with the phone camera
    </div>
  );
}
