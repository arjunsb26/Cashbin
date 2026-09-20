"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { FinanceFooter, PageHeader, cx } from "@/components/ui";

/**
 * The three views of the books, each at its own address.
 *
 * They are routes rather than a tab widget because a person links to the register
 * and comes back to it, and because a tab that loses its place on reload is a tab
 * nobody trusts.
 */
const VIEWS = [
  { href: "/books", label: "Journal" },
  { href: "/books/register", label: "Register" },
  { href: "/books/trial-balance", label: "Trial balance" },
];

export default function BooksLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  return (
    <div>
      <PageHeader
        title="Books"
        description="What every ticket did to the ledger, and what the register still holds."
      />
      <nav className="flex gap-4 border-b border-rule" aria-label="Books views">
        {VIEWS.map((view) => {
          const current = pathname === view.href;
          return (
            <Link
              key={view.href}
              href={view.href}
              aria-current={current ? "page" : undefined}
              className={cx(
                "-mb-px border-b-2 px-1 pb-2 text-section",
                current ? "border-b-ink text-ink" : "border-b-transparent text-ink-soft",
              )}
            >
              {view.label}
            </Link>
          );
        })}
      </nav>
      <div className="pt-4">{children}</div>
      <FinanceFooter />
    </div>
  );
}
