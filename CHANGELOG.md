# Changelog

Newest first. Each lane writes under its own heading.

## 2026-09-19, lane d: the dashboard

- Next.js App Router in `/frontend`, TypeScript strict with
  `noUncheckedIndexedAccess`, Tailwind mapped onto one CSS variable file. Radix
  primitives only, styled from the tokens. No prestyled kit.
- DESIGN.md section 2 tokens live in `app/tokens.css` and nowhere else.
  `pnpm check:hex` fails the build when a colour literal appears outside it.
- IBM Plex Sans and IBM Plex Sans Condensed ship as local woff2 files with the
  OFL licence beside them, loaded through `next/font/local`, so the venue never
  needs the network.
- `lib/format.ts` is the only place a number is turned into text: accounting
  money with parentheses and the symbol under the caller's control, mass with a
  thin space and an ink-soft unit, carbon, percentages, the `est.` marker, the
  cost per toss, and the reader that turns typed free text into a validated
  label. Nineteen tests cover it.
- Pages: Live, Books, Assets, Asset tags, Learning, Close, event detail,
  `/setup` and `/kit`. The last two are not linked from the rail.
- The ticket is one component. Live, the tape, the event page and the kit all
  render it, and the phone page can copy its markup.
- Every money, mass and carbon figure opens the evidence drawer: photo and
  crop, the weight trace with the step shaded, how it was identified with both
  probability sets, the substituted formula, the rule with its citation, and
  whether a person confirmed it.
- Mock mode sits behind `NEXT_PUBLIC_API_MOCK=1` and one switch in
  `lib/api.ts`. Nothing else in the app imports from `lib/mock`. `?state=` picks
  empty, loading or error, `?ask=1` opens an ask and `?replay=1` replays the
  demo tosses on a timer.
- `pnpm screenshots` builds in mock mode, starts the app and captures every
  route at 1440x900 and 390x844 in every state.
- PWA: manifest read from the brand file, icons at 192 and 512, and a service
  worker that caches the app shell and never API or socket traffic.
