"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Activity, BookOpen, CheckSquare, LineChart, Tag } from "lucide-react";
import { brand } from "@/lib/brand";
import { cx } from "./ui";

const DESTINATIONS = [
  { href: "/", label: "Live", Icon: Activity },
  { href: "/books", label: "Books", Icon: BookOpen },
  { href: "/assets", label: "Assets", Icon: Tag },
  { href: "/learning", label: "Learning", Icon: LineChart },
  { href: "/close", label: "Close", Icon: CheckSquare },
];

export function Rail() {
  const pathname = usePathname();
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
            <Icon size={16} strokeWidth={1.5} aria-hidden="true" />
            {label}
          </Link>
        );
      })}
    </nav>
  );
}
