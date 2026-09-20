"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Activity, BookOpen, CheckSquare, ClipboardCheck, TrendingUp } from "lucide-react";
import { useWaiting } from "@/lib/api";
import { brand } from "@/lib/brand";
import { SettingsDialog } from "./SettingsDialog";
import { cx } from "./ui";

/**
 * Five destinations for two readers. Live and Trends answer "what did I waste".
 * Review, Books and Close answer "what does this do to my accounts". Nothing
 * else is on the rail: the kit and the setup checklist are reachable by address,
 * because they are for the people building the thing, not using it.
 */
const DESTINATIONS = [
  { href: "/", label: "Live", Icon: Activity },
  { href: "/trends", label: "Trends", Icon: TrendingUp },
  { href: "/review", label: "Review", Icon: ClipboardCheck },
  { href: "/books", label: "Books", Icon: BookOpen },
  { href: "/close", label: "Close", Icon: CheckSquare },
];

export function Rail() {
  const pathname = usePathname();
  // One waiting count for the whole app, read from the queue itself.
  const open = useWaiting();

  return (
    <nav
      aria-label="Sections"
      className="sticky top-0 flex h-dvh w-rail shrink-0 flex-col items-stretch gap-1 bg-paper py-3"
    >
      <span className="px-2 pb-3 text-center text-caption text-ink-soft">{brand.short_name}</span>
      {DESTINATIONS.map(({ href, label, Icon }) => {
        const current = href === "/" ? pathname === "/" : pathname.startsWith(href);
        return (
          <Link
            key={href}
            href={href}
            aria-current={current ? "page" : undefined}
            className={cx(
              "flex flex-col items-center gap-1 border-l-2 py-2 text-caption transition-colors duration-fast ease-standard hover:bg-bar",
              current ? "border-l-ink text-ink" : "border-l-transparent text-ink-soft",
            )}
          >
            <span className="relative">
              <Icon size={16} strokeWidth={1.5} aria-hidden="true" />
              {/* How many things are waiting on a person, on the one item that
                  waits on one. It is a count, so it is a number, not a dot. */}
              {href === "/review" && open > 0 ? (
                <span
                  className="absolute -right-3 -top-2 min-w-4 rounded-control bg-caution px-1 text-center text-caption leading-4 text-paper"
                  aria-hidden="true"
                >
                  {open}
                </span>
              ) : null}
            </span>
            {label}
            {href === "/review" && open > 0 ? (
              <span className="sr-only">{open} waiting on a person</span>
            ) : null}
          </Link>
        );
      })}
      <div className="mt-auto">
        <SettingsDialog />
      </div>
    </nav>
  );
}
