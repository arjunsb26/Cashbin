"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAssets, useJournal } from "@/lib/api";
import type { AssetRead } from "@/lib/types";
import { formatCount, formatMoney } from "@/lib/format";
import { AskBooks } from "@/components/AskBooks";
import { FinanceFooter, PageHeader, Skeleton, cx } from "@/components/ui";

/**
 * The three views of the books, each at its own address, each with the one
 * sentence that says what it is for.
 *
 * They are routes rather than a tab widget because a person links to the register
 * and comes back to it, and because a tab that loses its place on reload is a tab
 * nobody trusts.
 */
const VIEWS = [
  {
    href: "/books",
    label: "Journal",
    what: "Every toss becomes a balanced entry: what was debited, what was credited, and the ticket it came from.",
  },
  {
    href: "/books/register",
    label: "Register",
    what: "The equipment on the books, what it cost, what it is worth today on the book side and the tax side, and what has left.",
  },
  {
    href: "/books/trial-balance",
    label: "Trial balance",
    what: "Every account totalled. Debits must equal credits, or the period cannot close.",
  },
];

export default function BooksLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const view = VIEWS.find((v) => v.href === pathname) ?? VIEWS[0]!;

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Books"
        description="A real double-entry ledger, kept by the bin. Two sets of figures for every toss: what it did to your books, and what it does at tax time."
      />

      <HowToRead />

      <div className="grid grid-cols-1 gap-8 lg:grid-cols-[minmax(0,1fr)_minmax(320px,360px)]">
        <div className="min-w-0">
          <nav className="flex gap-4 border-b border-rule" aria-label="Books views">
            {VIEWS.map((item) => {
              const current = pathname === item.href;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  aria-current={current ? "page" : undefined}
                  className={cx(
                    "-mb-px border-b-2 px-1 pb-2 text-section",
                    current ? "border-b-ink text-ink" : "border-b-transparent text-ink-soft",
                  )}
                >
                  {item.label}
                </Link>
              );
            })}
          </nav>
          <p className="pt-2 text-caption text-ink-soft">{view.what}</p>
          <div className="pt-4">{children}</div>
        </div>
        <AskBooks where="books" className="self-start lg:sticky lg:top-6" />
      </div>

      <FinanceFooter />
    </div>
  );
}

/**
 * Four short cards that say what the books are, with the live figure that proves
 * each one. A CFO reads these and knows what they are looking at; anyone else
 * reads them and learns what a ledger is in four sentences.
 */
function HowToRead() {
  const journal = useJournal();
  const assets = useAssets();
  const entries = journal.data?.entries ?? [];
  const book = entries.filter((e) => e.basis === "book");
  const tax = entries.filter((e) => e.basis === "tax_memo");
  const rows: AssetRead[] = assets.data ?? [];
  const active = rows.filter((a) => a.status === "active");
  const bookValue = active.reduce((sum, a) => sum + (a.book_value_cents ?? 0), 0);
  const taxBasis = active.reduce((sum, a) => sum + (a.tax_basis_cents ?? 0), 0);
  const trial = journal.data?.trial_balance ?? [];
  const balanced = journal.data?.balanced ?? null;

  const cards = [
    {
      title: "Every toss posts an entry",
      figure: journal.data ? formatCount(book.length) : null,
      unit: book.length === 1 ? "book entry" : "book entries",
      text: "Food that goes in is written off inventory. Equipment comes off the register at its book value. Both sides of every entry are shown, and they always agree.",
    },
    {
      title: "Book and tax are two columns",
      figure: journal.data ? formatCount(tax.length) : null,
      unit: tax.length === 1 ? "tax memo entry" : "tax memo entries",
      text: "The book side is what your accounts say. The tax side follows the tax rules, which can differ, for example when equipment was expensed in full the year it was bought.",
    },
    {
      title: "The register is what you own",
      figure: assets.data ? formatMoney(bookValue, { symbol: true }) : null,
      unit:
        formatCount(active.length) +
        (active.length === 1 ? " item, " : " items, ") +
        formatMoney(taxBasis, { symbol: true }) +
        " tax basis",
      text: "Each piece of equipment carries its cost, its remaining book value and its tax basis. A tag on the item ties a toss to its row, and the row is closed the moment it is binned.",
    },
    {
      title: "The trial balance is the proof",
      figure: journal.data
        ? balanced === false
          ? "Out of balance"
          : trial.length > 0
            ? "Balanced"
            : "Empty"
        : null,
      unit: formatCount(trial.length) + (trial.length === 1 ? " account" : " accounts"),
      text: "All accounts totalled on one page. Debits equal credits, or the close refuses to sign off and says which entry broke it.",
    },
  ];

  return (
    <section aria-label="How to read the books">
      <ul className="m-0 grid list-none grid-cols-1 gap-3 p-0 sm:grid-cols-2 xl:grid-cols-4">
        {cards.map((card) => (
          <li key={card.title} className="flex flex-col gap-1 border-l-2 border-l-ink bg-bar px-4 py-3">
            <p className="text-body font-semibold">{card.title}</p>
            <p className="font-condensed text-total text-ink">
              {card.figure ?? <Skeleton className="mt-1 h-7 w-24" />}
            </p>
            <p className="text-caption text-ink-soft">{card.unit}</p>
            <p className="pt-1 text-caption">{card.text}</p>
          </li>
        ))}
      </ul>
    </section>
  );
}
