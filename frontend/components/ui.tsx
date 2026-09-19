"use client";

import type { ButtonHTMLAttributes, InputHTMLAttributes, ReactNode } from "react";
import { forwardRef } from "react";
import { ChevronDown } from "lucide-react";
import { FINANCE_FOOTER } from "@/lib/format";

export function cx(...parts: (string | false | null | undefined)[]): string {
  return parts.filter(Boolean).join(" ");
}

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  tone?: "primary" | "quiet" | "danger";
  loading?: boolean;
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { tone = "quiet", loading = false, className, children, disabled, ...rest },
  ref,
) {
  const base =
    "inline-flex h-9 items-center justify-center rounded-control border px-3 text-body transition-colors duration-fast ease-standard disabled:cursor-not-allowed disabled:opacity-45";
  const tones = {
    primary: "border-ink bg-ink text-paper hover:bg-ink/90",
    quiet: "border-control-border bg-surface text-ink hover:bg-bar",
    danger: "border-control-border bg-surface text-red-ink hover:bg-bar",
  } as const;
  return (
    <button
      ref={ref}
      className={cx(base, tones[tone], className)}
      disabled={disabled || loading}
      {...rest}
    >
      {loading ? "Working" : children}
    </button>
  );
});

export function Field({
  label,
  hint,
  htmlFor,
  children,
  error,
}: {
  label: string;
  hint?: string;
  htmlFor: string;
  children: ReactNode;
  error?: string | null;
}) {
  return (
    <div className="flex flex-col gap-1">
      <label htmlFor={htmlFor} className="text-body font-semibold">
        {label}
      </label>
      {hint ? <span className="text-caption text-ink-soft">{hint}</span> : null}
      {children}
      {error ? <span className="text-caption text-red-ink">{error}</span> : null}
    </div>
  );
}

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(
  function Input({ className, ...rest }, ref) {
    return (
      <input
        ref={ref}
        className={cx(
          "h-9 w-full rounded-control border border-control-border bg-surface px-2 text-body text-ink placeholder:text-ink-soft disabled:bg-bar disabled:text-ink-soft",
          className,
        )}
        {...rest}
      />
    );
  },
);

export function Select({
  className,
  children,
  ...rest
}: InputHTMLAttributes<HTMLSelectElement> & { children: ReactNode }) {
  return (
    <span className="relative inline-flex items-center">
      <select
        className={cx(
          "h-9 appearance-none rounded-control border border-control-border bg-surface pl-2 pr-8 text-body text-ink",
          className,
        )}
        {...rest}
      >
        {children}
      </select>
      <ChevronDown
        size={16}
        strokeWidth={1.5}
        aria-hidden="true"
        className="pointer-events-none absolute right-2 text-ink-soft"
      />
    </span>
  );
}

export function StatusDot({ tone }: { tone: "kept" | "caution" | "red" | "soft" }) {
  const fill = {
    kept: "bg-kept",
    caution: "bg-caution",
    red: "bg-red-ink",
    soft: "bg-ink-soft",
  }[tone];
  return <span className={cx("inline-block h-2 w-2 rounded-full align-middle", fill)} />;
}

export function Skeleton({ className }: { className?: string }) {
  return <span className={cx("block animate-skeleton bg-rule", className)} aria-hidden="true" />;
}

export function PageHeader({
  title,
  right,
  description,
}: {
  title: string;
  right?: ReactNode;
  description?: string;
}) {
  return (
    <div className="flex flex-col gap-3 pb-4 sm:flex-row sm:items-start sm:justify-between sm:gap-4">
      <div>
        <h1 className="text-title">{title}</h1>
        {description ? <p className="pt-1 text-caption text-ink-soft">{description}</p> : null}
      </div>
      {right ? <div className="flex flex-wrap items-center gap-2">{right}</div> : null}
    </div>
  );
}

export function SectionTitle({ children, right }: { children: ReactNode; right?: ReactNode }) {
  return (
    <div className="flex items-baseline justify-between border-b border-rule pb-1">
      <h2 className="text-section">{children}</h2>
      {right}
    </div>
  );
}

export function EmptyState({ title, action }: { title: string; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-start gap-3 border border-dashed border-rule px-4 py-8">
      <p className="text-body text-ink-soft">{title}</p>
      {action}
    </div>
  );
}

export function ErrorState({ title, onRetry }: { title: string; onRetry?: () => void }) {
  return (
    <div className="flex flex-col items-start gap-3 border-l-2 border-red-ink bg-surface px-4 py-4">
      <p className="text-body text-ink">{title}</p>
      {onRetry ? <Button onClick={onRetry}>Try again</Button> : null}
    </div>
  );
}

/** The one place the finance disclaimer is rendered. The words live in lib/format.ts. */
export function FinanceFooter() {
  return <p className="pt-6 text-caption text-ink-soft">{FINANCE_FOOTER}</p>;
}
