# Changelog

Newest first. Each lane writes under its own heading.

## Lane B

- Added `backend/data/README.md` explaining every seed file, where its numbers
  came from and how to refresh the WARM factors.
- Seeded `backend/data/catalog.csv` with 30 items across food, packaging and
  small electronics, every price carrying the listing URL it was read from, and
  `backend/data/assets_seed.csv` with twelve register rows whose cost, in service
  date and tax method are all `NEEDS_HUMAN`. Added `backend/data/llm_prices.csv`
  with three empty openai rows.
- Added `app/ledger/register.py`: `mark_disposed`, `find_ghosts` and
  `book_summary` as pure functions over the register.
- Added `app/ledger/journal.py`: the chart of accounts, balanced entry builders
  for an inventory write off, a fixed asset disposal with its gain or loss
  branch, and the tax memo that puts book and tax side by side. Added the void
  reversal, the trial balance, and the unrecorded asset flag. Every builder
  checks its own balance before returning.
- Added `app/engine/options.py`: all five options scored, ranked by net after
  tax with ties inside 50 cents broken by lower carbon, blocked options kept
  with no rank, plus the best, greenest, saved and tone summary.
- Added `app/engine/carbon.py` and `app/engine/tax.py`: EPA WARM factors
  converted from MTCO2E per short ton to kg CO2e per kg, and one pure function
  per cell of the tax table, including the enhanced food donation deduction and
  the electronics block on binning.
- Added `app/engine/depreciation.py` and `app/engine/rules.py`: straight line
  book value with salvage, tax basis for bonus and straight line methods with an
  override, and the loader for the seven cited tax rules.
- Added `app/engine/records.py`: the typed records the engine works on, the
  builder that assembles an item record from a catalog row or an asset row, and
  `list_needs_human()` for the setup checklist.
- Added `scripts/extract_warm.py` and generated `backend/data/warm_factors.csv`
  from the EPA WARM version 16 workbook. 61 materials, real numbers, blanks
  where the workbook publishes none.
