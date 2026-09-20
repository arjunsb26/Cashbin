# Seed data and reference tables

Lane B owns this directory. Everything the decision engine reads lives here, and
every number in it either came from a named source or is blank. A blank cell is
never a zero. Anything a person still has to fill in says `NEEDS_HUMAN`, and
`list_needs_human()` in `app/engine/records.py` collects those so the setup
checklist can show them.

## catalog.csv

Fifty common items: hackathon food, the packaging it comes in, small
electronics, and the everyday things a table at a hackathon actually holds
(a pen, a notebook, a flash drive, a lanyard, a laptop, an AA battery). Columns match the `catalog_item` table in PLAN.md section 8, plus
`price_source`, which holds the URL the price came from or, for food, the words
`estimate: 50 percent of retail` followed by that URL.

- `unit_cost_cents` and `unit_mass_g` price a countable item. `price_per_kg_cents`
  prices something sold by weight, which today is the banana and the apple.
- `fmv_per_kg_cents` is fair market value, which the engine uses for donation
  math. It is filled for food only, and it is the retail listing price.
- Food cost, the `unit_cost_cents` or `price_per_kg_cents` cell, is what the
  business paid, not what the shelf says. Nobody published that, so it is set at
  half the retail listing and the `price_source` cell says so. That gives the
  enhanced food deduction a mark up to work on. Replacing these eleven cells
  with the kitchen's real invoice prices is the most valuable edit in this file.
- Every food row carries the `food` regulatory flag. The engine reads it to
  block the resale option, because food that has reached the bin cannot be sold
  (rule `FOOD_NO_RESALE`). The row still shows, struck through, with the reason.
- `material_mix_json` fractions must sum to 1 and every key must exist in
  `warm_factors.csv`. A test enforces both.
- Eighteen of the twenty everyday rows were priced against a listing in
  September 2026, one unit at a time: a pack price divided by the pack size
  where a thing is sold in packs. Two of them, the sticker sheet and the lanyard
  badge, have no price at all and say `NEEDS_HUMAN`, because no listing was
  found that priced one unit of the thing. A blank cell is never a zero.
- `mass_prior_mean_g` is a typical mass, not a measurement. It ships with
  `mass_prior_n = 3` and a wide variance, so the first real weighing of an item
  moves the prior almost all the way. Four rows (usb cable, earbuds, hdmi cable,
  webcam) have a prior mass but no `unit_mass_g`, because no spec page published
  a weight.
- Prices were read in September 2026. Refresh them by opening the URL in
  `price_source` and editing the cell.

## warm_factors.csv

Greenhouse gas factors from the EPA Waste Reduction Model, version 16, December
2023, in MTCO2E per short ton exactly as the workbook publishes them. The code
converts to kg CO2e per kg at load, using 907.18474 kg per short ton.

Sixty one materials, one row each. A blank cell means WARM does not publish that
fate for that material, for example there is no recycling factor for food waste.
Blank loads as unknown and an option built on it reports no carbon figure at all
rather than a zero.

To refresh:

```
curl -L -o warm_v16.xls https://www.epa.gov/system/files/documents/2023-12/warm_v16.xls
cd backend
uv run --with xlrd python ../scripts/extract_warm.py ../warm_v16.xls
```

The workbook is a .xls, so the script needs `xlrd`. It is not a project
dependency, which is why it comes in through `uv run --with`. A .xlsx workbook
would need `--with openpyxl` instead. The script reads the sheet named
"Summary Data" and copies the Source Reduction, Recycling, Landfilling National
Average, Combustion and Composting columns. Download the workbook from
https://www.epa.gov/waste-reduction-model/versions-waste-reduction-model

## tax_rules.yaml

The eight rules the engine cites, with the citations PLAN.md section 10 names.
`plain_text` is the only copy of each explanation; the evidence drawer and the
close report both read it from here so the words cannot drift from the maths.
Four rules carry no citation link. Three because the plan gives none for
them, and `FOOD_NO_RESALE` because it is a policy, not a tax rule.

## assets_seed.csv

Twelve rows of typical team gear as a template. Every `cost_cents`,
`in_service_date` and `tax_method` is `NEEDS_HUMAN` on purpose. Fill them with
what the team actually paid and when, and set at least two rows bought after
19 January 2025 to `bonus_100` so the difference between book value and tax
basis shows on the ticket. Two rows carry a note saying which ones were meant
for that.

`book_life_months` is set to 36 for small electronics and 60 for tools and
displays. That is a policy choice, not a measured fact, and it is editable.

## llm_prices.csv

Per model prices for the cost chart, in US dollars per million tokens. Five
`openai` rows, read from https://developers.openai.com/api/docs/pricing on
19 September 2026, short context and the standard tier. `cached_input` is the
lower rate a repeated prompt prefix gets, which matters here because the vision
prompt is the same every time.

Refresh by opening that page and retyping the numbers. Change the model ids in
one place, this file, and set the runtime settings to match.
