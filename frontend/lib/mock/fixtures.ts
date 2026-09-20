// Fixtures for mock mode, in the generated contract shapes. Real demo items and
// the team's own gear, no filler names. Nothing here is imported by a production
// path; lib/api.ts holds the one switch.
import type {
  AssetRead,
  CloseRead,
  CorrectionRead,
  EventDetail,
  EventSummary,
  IdentificationRead,
  ItemRecordRead,
  JournalEntryRead,
  JournalResponse,
  OptionScoreRead,
  RoundListResponse,
  RuleRead,
  SettingsRead,
  SummaryResponse,
  TrialBalanceRow,
} from "../types";

const DAY = "2026-09-19";

function at(time: string): string {
  return `${DAY}T${time}:00`;
}

/** Pairs of seconds and grams around one step, the way the backend sends them. */
function trace(baseline: number, step: number, seed: number): number[][] {
  const points: number[][] = [];
  for (let i = 0; i < 90; i += 1) {
    const noise = Math.sin((i + seed) * 1.7) * 0.6 + Math.cos((i + seed) * 0.6) * 0.4;
    let g = baseline + noise;
    if (i >= 30 && i < 34) g = baseline + step * 1.35 + noise * 3;
    else if (i >= 34) g = baseline + step + noise;
    points.push([Number((i * 0.1).toFixed(1)), Number(g.toFixed(2))]);
  }
  return points;
}

export const ASSETS: AssetRead[] = [
  {
    id: 1,
    tag: "bb-0001",
    description: "Wireless mouse",
    category: "peripheral",
    cost_cents: 2499,
    in_service_date: "2025-06-02",
    book_life_months: 36,
    salvage_cents: 0,
    tax_method: "bonus_100",
    book_value_cents: 1458,
    tax_basis_cents: 0,
    tax_basis_cents_override: null,
    status: "active",
    disposed_event_id: null,
    insured: false,
    location: "hack table",
  },
  {
    id: 2,
    tag: "bb-0002",
    description: "Mechanical keyboard",
    category: "peripheral",
    cost_cents: 12000,
    in_service_date: "2025-03-04",
    book_life_months: 36,
    salvage_cents: 0,
    tax_method: "bonus_100",
    book_value_cents: 2000,
    tax_basis_cents: 0,
    tax_basis_cents_override: null,
    status: "disposed",
    disposed_event_id: 102,
    insured: false,
    location: "hack table",
  },
  {
    id: 3,
    tag: "bb-0003",
    description: "Laptop charger 65W",
    category: "power",
    cost_cents: 4900,
    in_service_date: "2025-01-20",
    book_life_months: 36,
    salvage_cents: 0,
    tax_method: "bonus_100",
    book_value_cents: 1769,
    tax_basis_cents: 0,
    tax_basis_cents_override: null,
    status: "active",
    disposed_event_id: null,
    insured: false,
    location: "hack table",
  },
  {
    id: 6,
    tag: "bb-0006",
    description: "Desk monitor 24 inch",
    category: "display",
    cost_cents: 18900,
    in_service_date: "2024-02-11",
    book_life_months: 60,
    salvage_cents: 0,
    tax_method: "straight_line",
    book_value_cents: 9450,
    tax_basis_cents: 9450,
    tax_basis_cents_override: null,
    status: "ghost_suspected",
    disposed_event_id: null,
    insured: false,
    location: "hack table",
  },
  {
    id: 8,
    tag: "bb-0008",
    description: "3D printer",
    category: "tool",
    cost_cents: 24900,
    in_service_date: "2025-08-14",
    book_life_months: 60,
    salvage_cents: 0,
    tax_method: "bonus_100",
    book_value_cents: 20750,
    tax_basis_cents: 0,
    tax_basis_cents_override: null,
    status: "active",
    disposed_event_id: null,
    insured: false,
    location: "hardware bench",
  },
  {
    id: 12,
    tag: "bb-0012",
    description: "Wireless earbuds",
    category: "peripheral",
    cost_cents: 7900,
    in_service_date: "2025-05-09",
    book_life_months: 36,
    salvage_cents: 0,
    tax_method: "bonus_100",
    book_value_cents: 5047,
    tax_basis_cents: 0,
    tax_basis_cents_override: null,
    status: "active",
    disposed_event_id: null,
    insured: false,
    location: "backpack",
  },
];

function options(
  eventId: number,
  rows: Partial<OptionScoreRead>[],
): OptionScoreRead[] {
  return rows.map((row, i) => ({
    id: eventId * 10 + i,
    event_id: eventId,
    option: row.option ?? "trash",
    allowed: row.allowed ?? true,
    blocked_reason: row.blocked_reason ?? null,
    cash_cents: row.cash_cents ?? 0,
    tax_effect_cents: row.tax_effect_cents ?? 0,
    net_after_tax_cents: row.net_after_tax_cents ?? 0,
    kg_co2e: row.kg_co2e ?? null,
    kg_landfill: row.kg_landfill ?? 0,
    needs_human_review: row.needs_human_review ?? false,
    notes: row.notes ?? [],
    rule_ids: row.rule_ids ?? [],
    rank: row.rank ?? null,
  }));
}

function identification(
  eventId: number,
  over: Partial<IdentificationRead>,
): IdentificationRead {
  return {
    id: eventId,
    event_id: eventId,
    method: "cloud",
    label: null,
    class: null,
    confidence: 0.9,
    candidates: [],
    posterior: {},
    used_mass_prior: true,
    is_final: true,
    latency_ms: 1840,
    cost_microusd: 2100,
    tokens_in: 1120,
    tokens_out: 90,
    provider: "openai",
    model: "gpt-5.6-luna",
    ...over,
  };
}

// The four header numbers ---------------------------------------------------

export const SUMMARY: SummaryResponse = {
  saved_if_followed_cents: 4180,
  kg_diverted: 3.214,
  events: 27,
  first_try_accuracy: 0.89,
};

// The tape ------------------------------------------------------------------

export const EVENTS: EventSummary[] = [
  {
    id: 105,
    created_at: at("14:41"),
    kind: "toss",
    status: "asking",
    mass_g: 172,
    mass_err_g: 2,
    label: null,
    class: null,
    crop_url: null,
    crop_quality: "ok",
    net_book_cents: null,
    best_option: null,
    saved_if_followed_cents: null,
    round_id: 4,
  },
  {
    id: 104,
    created_at: at("14:36"),
    kind: "toss",
    status: "posted",
    mass_g: 12,
    mass_err_g: 1,
    label: "water bottle empty",
    class: "untracked",
    crop_url: null,
    crop_quality: "ok",
    net_book_cents: 0,
    best_option: "recycle",
    saved_if_followed_cents: 3,
    round_id: 4,
  },
  {
    id: 103,
    created_at: at("14:31"),
    kind: "toss",
    status: "posted",
    mass_g: 62,
    mass_err_g: 2,
    label: "usb-c charger",
    class: "untracked",
    crop_url: null,
    crop_quality: "ok",
    net_book_cents: 0,
    best_option: "resell",
    saved_if_followed_cents: 800,
    round_id: 4,
  },
  {
    id: 102,
    created_at: at("14:24"),
    kind: "toss",
    status: "posted",
    mass_g: 780,
    mass_err_g: 3,
    label: "mechanical keyboard",
    class: "fixed_asset",
    crop_url: null,
    crop_quality: "ok",
    net_book_cents: 2000,
    best_option: "resell",
    saved_if_followed_cents: 1200,
    round_id: 4,
  },
  {
    id: 101,
    created_at: at("14:18"),
    kind: "toss",
    status: "posted",
    mass_g: 95,
    mass_err_g: 2,
    label: "bagel",
    class: "inventory",
    crop_url: null,
    crop_quality: "low",
    net_book_cents: 0,
    best_option: "donate",
    saved_if_followed_cents: 14,
    round_id: 4,
  },
];

// The tickets ---------------------------------------------------------------

function record(over: Partial<ItemRecordRead> & { event_id: number }): ItemRecordRead {
  return {
    label: "",
    class: "untracked",
    mass_g: 0,
    condition: "unknown",
    material_mix: {},
    regulatory_flags: [],
    book_value_cents: 0,
    tax_basis_cents: 0,
    asset_id: null,
    cost_basis_cents: 0,
    fmv: { low: null, mid: null, high: null, source: null },
    repair: { low: null, mid: null, high: null, source: null },
    replacement_cents: null,
    replacement_source: null,
    scrap_cents: null,
    scrap_source: null,
    ...over,
  };
}

function entry(over: Partial<JournalEntryRead> & { id: number }): JournalEntryRead {
  return {
    event_id: null,
    close_id: null,
    posted_at: at("14:24"),
    memo: "",
    basis: "book",
    lines: [],
    evidence: {},
    ...over,
  };
}

const KEYBOARD_ENTRIES: JournalEntryRead[] = [
  entry({
    id: 301,
    event_id: 102,
    memo: "Dispose of Mechanical keyboard (bb-0002)",
    basis: "book",
    lines: [
      { id: 1, entry_id: 301, account: "1600-accum-depreciation", account_name: "Accumulated depreciation", debit_cents: 10000, credit_cents: 0 },
      { id: 2, entry_id: 301, account: "6800-loss-on-disposal", account_name: "Loss on disposal", debit_cents: 2000, credit_cents: 0 },
      { id: 3, entry_id: 301, account: "1500-fixed-assets", account_name: "Fixed assets", debit_cents: 0, credit_cents: 12000 },
    ],
    evidence: {
      event_id: 102,
      label: "mechanical keyboard",
      asset_tag: "bb-0002",
      cost_cents: 12000,
      accum_cents: 10000,
      book_value_cents: 2000,
      proceeds_cents: 0,
      gain_cents: -2000,
    },
  }),
  entry({
    id: 302,
    event_id: 102,
    memo: "Tax treatment of mechanical keyboard",
    basis: "tax_memo",
    lines: [
      { id: 4, entry_id: 302, account: "6800-loss-on-disposal", account_name: "Loss on disposal", debit_cents: 0, credit_cents: 0 },
      { id: 5, entry_id: 302, account: "1500-fixed-assets", account_name: "Fixed assets", debit_cents: 0, credit_cents: 0 },
    ],
    evidence: {
      event_id: 102,
      label: "mechanical keyboard",
      tax_basis_cents: 0,
      tax_loss_cents: 0,
      tax_gain_cents: 0,
      book_value_cents: 2000,
      book_minus_tax_cents: 2000,
      rule_ids: ["ABANDON", "BONUS_100"],
    },
  }),
];

const BAGEL_ENTRY = entry({
  id: 300,
  event_id: 101,
  posted_at: at("14:18"),
  memo: "Write off bagel",
  basis: "book",
  lines: [
    { id: 6, entry_id: 300, account: "5200-waste-and-shrink", account_name: "Waste and shrink", debit_cents: 33, credit_cents: 0 },
    { id: 7, entry_id: 300, account: "1300-inventory", account_name: "Inventory", debit_cents: 0, credit_cents: 33 },
  ],
  evidence: { event_id: 101, label: "bagel", cost_basis_cents: 33, mass_g: 95 },
});

const CORRECTIONS: CorrectionRead[] = [
  {
    id: 12,
    event_id: 103,
    field: "label",
    old_value: "usb cable",
    new_value: "usb-c charger",
    by: "person",
    created_at: at("14:32"),
  },
];

export const EVENT_DETAILS: Record<number, EventDetail> = {
  101: {
    event: EVENTS[4] as EventSummary,
    trace: trace(2180, 95, 3),
    frame_before_url: null,
    frame_after_url: null,
    frame_peak_url: null,
    identifications: [
      identification(101, {
        label: "bagel",
        class: "inventory",
        confidence: 0.94,
        candidates: [
          { label: "bagel", p: 0.86 },
          { label: "cookie", p: 0.09 },
          { label: "wrap", p: 0.05 },
        ],
        posterior: { bagel: 0.94, cookie: 0.04, wrap: 0.02 },
      }),
    ],
    item_record: record({
      event_id: 101,
      label: "bagel",
      class: "inventory",
      mass_g: 95,
      material_mix: { food_waste: 1 },
      regulatory_flags: ["food"],
      cost_basis_cents: 33,
      fmv: { low: 60, mid: 66, high: 72, source: "catalog" },
    }),
    options: options(101, [
      { option: "trash", cash_cents: -5, tax_effect_cents: 0, net_after_tax_cents: -5, kg_co2e: 0.06, kg_landfill: 0.095, rank: 2, rule_ids: ["INV_COGS"] },
      { option: "donate", cash_cents: 0, tax_effect_cents: 9, net_after_tax_cents: 9, kg_co2e: 0.01, kg_landfill: 0, rank: 1, needs_human_review: true, rule_ids: ["DONATE_FOOD"] },
      { option: "recycle", cash_cents: -2, tax_effect_cents: 0, net_after_tax_cents: -2, kg_co2e: 0.02, kg_landfill: 0, rank: 3 },
      { option: "resell", allowed: false, blocked_reason: "Food that has been in a bin cannot be sold.", cash_cents: 0, tax_effect_cents: 0, net_after_tax_cents: 0, kg_co2e: null, kg_landfill: 0, rule_ids: ["FOOD_NO_RESALE"] },
    ]),
    entries: [BAGEL_ENTRY],
    corrections: [],
  },
  102: {
    event: EVENTS[3] as EventSummary,
    trace: trace(2275, 780, 11),
    frame_before_url: null,
    frame_after_url: null,
    frame_peak_url: null,
    identifications: [
      identification(102, {
        method: "qr",
        label: "mechanical keyboard",
        class: "fixed_asset",
        confidence: 1,
        candidates: [{ label: "mechanical keyboard", p: 1 }],
        posterior: {},
        used_mass_prior: false,
        latency_ms: 90,
        cost_microusd: 0,
        provider: null,
        model: null,
      }),
    ],
    item_record: record({
      event_id: 102,
      label: "mechanical keyboard",
      class: "fixed_asset",
      mass_g: 780,
      condition: "working",
      material_mix: { mixed_plastics: 0.6, steel_cans: 0.3, mixed_electronics: 0.1 },
      regulatory_flags: ["ewaste"],
      book_value_cents: 2000,
      tax_basis_cents: 0,
      asset_id: 2,
      fmv: { low: 2800, mid: 3200, high: 3800, source: "model_estimate" },
      repair: { low: 0, mid: 0, high: 0, source: "catalog" },
      replacement_cents: 12000,
      replacement_source: "register",
      scrap_cents: 42,
      scrap_source: "catalog",
    }),
    options: options(102, [
      { option: "trash", allowed: false, blocked_reason: "Electronics cannot go to landfill in this state.", cash_cents: 0, tax_effect_cents: 0, net_after_tax_cents: 0, kg_co2e: 0.42, kg_landfill: 0.78, rule_ids: ["EWASTE"] },
      { option: "resell", cash_cents: 3200, tax_effect_cents: -672, net_after_tax_cents: 2528, kg_co2e: 0, kg_landfill: 0, rank: 1, rule_ids: ["ABANDON"] },
      { option: "donate", cash_cents: 0, tax_effect_cents: 0, net_after_tax_cents: 0, kg_co2e: 0, kg_landfill: 0, rank: 3, needs_human_review: true, rule_ids: ["DONATE_EQUIP"] },
      { option: "recycle", cash_cents: 42, tax_effect_cents: 420, net_after_tax_cents: 462, kg_co2e: 0.09, kg_landfill: 0, rank: 2, rule_ids: ["ABANDON", "EWASTE"] },
    ]),
    entries: KEYBOARD_ENTRIES,
    corrections: [],
  },
  103: {
    event: EVENTS[2] as EventSummary,
    trace: trace(3055, 62, 7),
    frame_before_url: null,
    frame_after_url: null,
    frame_peak_url: null,
    identifications: [
      identification(103, {
        label: "usb cable",
        class: "untracked",
        confidence: 0.61,
        candidates: [
          { label: "usb cable", p: 0.44 },
          { label: "usb-c charger", p: 0.39 },
          { label: "power bank", p: 0.17 },
        ],
        posterior: { "usb-c charger": 0.52, "usb cable": 0.33, "power bank": 0.15 },
        is_final: false,
      }),
      identification(103, {
        id: 1031,
        method: "human",
        label: "usb-c charger",
        class: "untracked",
        confidence: 1,
        candidates: [],
        posterior: {},
        latency_ms: 0,
        cost_microusd: 0,
        provider: null,
        model: null,
      }),
    ],
    item_record: record({
      event_id: 103,
      label: "usb-c charger",
      class: "untracked",
      mass_g: 62,
      condition: "working",
      material_mix: { mixed_plastics: 0.7, mixed_electronics: 0.3 },
      regulatory_flags: ["ewaste"],
      fmv: { low: 600, mid: 800, high: 1100, source: "model_estimate" },
      replacement_cents: 1900,
      replacement_source: "model_estimate",
      scrap_cents: 4,
      scrap_source: "catalog",
    }),
    options: options(103, [
      { option: "trash", allowed: false, blocked_reason: "Electronics cannot go to landfill in this state.", cash_cents: 0, tax_effect_cents: 0, net_after_tax_cents: 0, kg_co2e: 0.04, kg_landfill: 0.062, rule_ids: ["EWASTE"] },
      { option: "resell", cash_cents: 800, tax_effect_cents: -168, net_after_tax_cents: 632, kg_co2e: 0, kg_landfill: 0, rank: 1 },
      { option: "recycle", cash_cents: 4, tax_effect_cents: 0, net_after_tax_cents: 4, kg_co2e: 0.01, kg_landfill: 0, rank: 2, rule_ids: ["EWASTE"] },
      { option: "donate", cash_cents: 0, tax_effect_cents: 0, net_after_tax_cents: 0, kg_co2e: 0, kg_landfill: 0, rank: 3, needs_human_review: true, rule_ids: ["DONATE_EQUIP"] },
    ]),
    entries: [],
    corrections: CORRECTIONS,
  },
  104: {
    event: EVENTS[1] as EventSummary,
    trace: trace(3117, 12, 19),
    frame_before_url: null,
    frame_after_url: null,
    frame_peak_url: null,
    identifications: [
      identification(104, {
        method: "memory",
        label: "water bottle empty",
        class: "untracked",
        confidence: 0.97,
        candidates: [{ label: "water bottle empty", p: 0.97 }],
        posterior: { "water bottle empty": 0.97, "plastic cup": 0.03 },
        latency_ms: 40,
        cost_microusd: 0,
        provider: null,
        model: null,
      }),
    ],
    item_record: record({
      event_id: 104,
      label: "water bottle empty",
      class: "untracked",
      mass_g: 12,
      material_mix: { pet: 1 },
      fmv: { low: 0, mid: 0, high: 1, source: "catalog" },
      scrap_cents: 3,
      scrap_source: "catalog",
    }),
    options: options(104, [
      { option: "trash", cash_cents: -1, tax_effect_cents: 0, net_after_tax_cents: -1, kg_co2e: 0.01, kg_landfill: 0.012, rank: 2 },
      { option: "recycle", cash_cents: 3, tax_effect_cents: 0, net_after_tax_cents: 3, kg_co2e: 0, kg_landfill: 0, rank: 1 },
    ]),
    entries: [],
    corrections: [],
  },
  105: {
    event: EVENTS[0] as EventSummary,
    trace: trace(3129, 172, 23),
    frame_before_url: null,
    frame_after_url: null,
    frame_peak_url: null,
    identifications: [
      identification(105, {
        label: "phone",
        class: "fixed_asset",
        confidence: 0.48,
        candidates: [
          { label: "phone", p: 0.41 },
          { label: "power bank", p: 0.33 },
          { label: "portable monitor", p: 0.16 },
        ],
        posterior: { phone: 0.48, "power bank": 0.34, "portable monitor": 0.18 },
        is_final: false,
      }),
    ],
    item_record: null,
    options: [],
    entries: [],
    corrections: [],
  },
};

/** The ask the Live page shows when the query string asks for it. */
export const ASK = {
  type: "ask.opened" as const,
  event_id: 105,
  crop_url: null,
  candidates: [
    { label: "phone", p: 0.48 },
    { label: "power bank", p: 0.34 },
    { label: "portable monitor", p: 0.18 },
  ] as [{ label: string; p: number }, { label: string; p: number }, { label: string; p: number }],
};

// Books ---------------------------------------------------------------------

const TRIAL_BALANCE: TrialBalanceRow[] = [
  { account: "1300-inventory", account_name: "Inventory", debit_cents: 0, credit_cents: 33 },
  { account: "1500-fixed-assets", account_name: "Fixed assets", debit_cents: 0, credit_cents: 12000 },
  { account: "1600-accum-depreciation", account_name: "Accumulated depreciation", debit_cents: 10000, credit_cents: 0 },
  { account: "5200-waste-and-shrink", account_name: "Waste and shrink", debit_cents: 33, credit_cents: 0 },
  { account: "6800-loss-on-disposal", account_name: "Loss on disposal", debit_cents: 2000, credit_cents: 0 },
];

export const JOURNAL: JournalResponse = {
  basis: null,
  entries: [BAGEL_ENTRY, ...KEYBOARD_ENTRIES],
  trial_balance: TRIAL_BALANCE,
  balanced: true,
};

// Learning ------------------------------------------------------------------

export const ROUNDS: RoundListResponse = {
  rounds: [
    {
      id: 1,
      started_at: at("11:02"),
      ended_at: at("12:10"),
      n_events: 20,
      n_correct_first_try: 11,
      n_asked: 8,
      n_corrected_after_confident: 2,
      first_try_accuracy: 0.55,
      ask_rate: 0.4,
      mean_latency_ms: 2210,
      cloud_cost_microusd: 56000,
      cost_per_event_microusd: 2800,
      local_share: 0.1,
    },
    {
      id: 2,
      started_at: at("12:12"),
      ended_at: at("13:14"),
      n_events: 20,
      n_correct_first_try: 14,
      n_asked: 5,
      n_corrected_after_confident: 1,
      first_try_accuracy: 0.7,
      ask_rate: 0.25,
      mean_latency_ms: 1980,
      cloud_cost_microusd: 44000,
      cost_per_event_microusd: 2200,
      local_share: 0.25,
    },
    {
      id: 3,
      started_at: at("13:16"),
      ended_at: at("14:12"),
      n_events: 20,
      n_correct_first_try: 17,
      n_asked: 3,
      n_corrected_after_confident: 0,
      first_try_accuracy: 0.85,
      ask_rate: 0.15,
      mean_latency_ms: 1740,
      cloud_cost_microusd: 26000,
      cost_per_event_microusd: 1300,
      local_share: 0.45,
    },
    {
      id: 4,
      started_at: at("14:14"),
      ended_at: null,
      n_events: 5,
      n_correct_first_try: 4,
      n_asked: 1,
      n_corrected_after_confident: 0,
      first_try_accuracy: 0.89,
      ask_rate: 0.11,
      mean_latency_ms: 1610,
      cloud_cost_microusd: 4200,
      cost_per_event_microusd: 840,
      local_share: 0.6,
    },
  ],
  learned: [
    "usb cable against usb-c charger: now recognised from 6 examples.",
    "wrap against burrito: now recognised from 4 examples.",
    "Anything tagged bb-0002 is read straight off the tag, so it is never asked about.",
  ],
};

export const SETTINGS: SettingsRead = {
  tax_rate: 0.21,
  capitalization_threshold_cents: 250000,
  confident_p: 0.72,
  min_margin: 0.15,
  memory_max_dist: 0.32,
  round_size: 20,
  step_min_g: 3,
  settle_ms: 700,
  bag_change_g: 1500,
  disposal_fee_cents: 5,
  recycle_fee_cents: 2,
  llm_timeout_s: 8,
  tone_co2e_kg: 0.02,
};

// Close ---------------------------------------------------------------------

export const CLOSE: CloseRead = {
  id: 1,
  period_start: DAY,
  period_end: DAY,
  created_at: at("14:45"),
  status: "needs_review",
  investigation_md:
    "The scale is 14 g heavier than the tickets account for. The gap opened between ticket 103 and ticket 104, when two things went in within a second of each other. Recount those two.",
  totals: {
    period: { start: DAY, end: DAY },
    events: { tosses: 5, counted: 4, bag_changes: 1, removals: 0, asking: 1, void: 0 },
    write_offs: {
      rows: [
        { label: "mechanical keyboard", class: "fixed_asset", count: 1, mass_g: 780, cents: 2000 },
        { label: "bagel", class: "inventory", count: 1, mass_g: 95, cents: 33 },
      ],
      total_cents: 2033,
      total_mass_g: 875,
      count: 2,
    },
    asset_disposals: {
      rows: [
        {
          event_id: 102,
          label: "mechanical keyboard",
          asset_id: 2,
          tag: "bb-0002",
          description: "Mechanical keyboard",
          book_value_cents: 2000,
          proceeds_cents: 0,
          book_loss_cents: 2000,
          tax_basis_cents: 0,
          tax_loss_cents: 0,
          tax_gain_cents: 0,
          abandonment: true,
          book_minus_tax_cents: 2000,
          rule_ids: ["ABANDON", "BONUS_100"],
        },
      ],
      count: 1,
      book_loss_cents: 2000,
      tax_loss_cents: 0,
      tax_gain_cents: 0,
    },
    missed_opportunity: {
      total_cents: 4180,
      by_option: {
        would_have_donated_cents: 14,
        would_have_resold_cents: 3960,
        would_have_repaired_cents: 0,
        would_have_recycled_cents: 206,
        already_the_best_cents: 0,
      },
      rows: [],
    },
    sustainability: {
      title: "Scope 3, Category 5 (waste generated in operations)",
      kg_to_landfill: 0.107,
      kg_diverted_if_followed: 3.214,
      kg_co2e_actual: 0.53,
      kg_co2e_best: 0.1,
      kg_co2e_avoided: 0.43,
      cheapest_equals_greenest_pct: 75,
      kg_ewaste: 0.842,
      events_scored: 4,
      events_without_carbon: 0,
      source: "EPA WARM",
    },
    ghost_assets: {
      rows: [
        {
          id: 6,
          tag: "bb-0006",
          description: "Desk monitor 24 inch",
          location: "hack table",
          event_id: null,
        },
      ],
      count: 1,
      ghost_suspected: 1,
      possible_unrecorded_assets: 0,
    },
  },
  checks: [
    {
      id: "mass_conservation",

      title: "Mass conservation",

      result: "fail",
      detail:
        "Scale reads            2,412 g\nTickets sum to         2,398 g\nDifference                14 g    within +/- 21 g    Fail\n\nThe tare is the last bag change.\n5 tickets, 1 bag change, 0 removals, 0 g taken back out.",
      numbers: {
        scale_reads_g: 2412,
        tickets_g: 2398,
        difference_g: 14,
        tolerance_g: 21,
        tickets: 5,
      },
    },
    {
      id: "ledger_balance",

      title: "Ledger balance",

      result: "pass",
      detail: "Every entry balances and the trial balance agrees.",
      numbers: { entries: 3, unbalanced_entries: 0, debit_cents: 12033, credit_cents: 12033 },
    },
    {
      id: "register_consistency",

      title: "Register consistency",

      result: "pass",
      detail: "Every asset the bin disposed of has exactly one disposal entry.",
      numbers: { disposed_assets: 1, missing_entries: 0, duplicate_entries: 0 },
    },
    {
      id: "unresolved_asks",

      title: "Unresolved asks",

      result: "warn",
      detail: "1 ticket is still waiting on an answer: 105.",
      numbers: { asking: 1, tosses: 5 },
    },
    {
      id: "low_confidence_share",

      title: "Settled by a person",

      result: "pass",
      detail: "A person settled 1 of 4 tickets, 25 percent.",
      numbers: { settled_by_person: 1, tickets: 4 },
    },
  ],
  report: {},
};

// Setup ---------------------------------------------------------------------

export const SETUP: string[] = [
  "assets_seed.csv, row bb-0001, what the wireless mouse cost.",
  "assets_seed.csv, row bb-0001, the day the wireless mouse went into service.",
  "assets_seed.csv, row bb-0002, the tax treatment of the mechanical keyboard.",
  "catalog.csv, row water bottle empty, where its price came from.",
];

/**
 * Two of the rules the engine cites, quoted from the file the backend serves at
 * `GET /api/rules`. The live page reads them from there; this copy exists only so
 * the kit and the mock screenshots show the drawer as a person will see it.
 */
export const RULES: RuleRead[] = [
  {
    id: "ABANDON",
    title: "Abandoned business property",
    plain_text:
      "Throwing out business property that still has tax basis left is generally an ordinary loss you can deduct. It goes on Form 4797 Part II.",
    citation_url: "https://www.irs.gov/publications/p544",
    needs_human_review: false,
  },
  {
    id: "EWASTE",
    title: "Electronic waste disposal",
    plain_text:
      "Many states forbid putting electronics in household or office trash, so the bin is not a legal answer for them wherever that is the rule.",
    citation_url: null,
    needs_human_review: true,
  },
];

// Trends. The same run the rest of these fixtures come from, bucketed.
import type { ReviewListResponse, StatsResponse } from "../types";

export const STATS_DAY: StatsResponse = {
  bucket: "day",
  period_start: "2026-09-19",
  period_end: "2026-09-19",
  buckets: [
    {
      start: "2026-09-19",
      tosses: 27,
      wasted_cents: 1583,
      book_loss_cents: 2000,
      estimated_value_cents: 600,
      kg_landfill: 3.2,
      kg_co2e_avoided: 1.32,
      asks: 2,
      first_try_accuracy: 0.81,
      by_category: [
        { category: "equipment", tosses: 4, cents: 2600, kg: 1.102 },
        { category: "e-waste", tosses: 6, cents: 1099, kg: 0.618 },
        { category: "food", tosses: 11, cents: 414, kg: 1.204 },
        { category: "packaging", tosses: 5, cents: 70, kg: 0.498 },
        { category: "other", tosses: 1, cents: 0, kg: 0.012 },
      ],
    },
  ],
  averages: { days: 1, tosses_per_day: 27, wasted_cents_per_day: 1583, kg_per_day: 3.2 },
  suggestions: [
    "Equipment is the biggest group at 26.00 dollars across 4 tickets, 62 percent of the 41.83 dollars in the range.",
    "12.00 dollars of resale value went in the bin across 1 ticket. The keyboard was the largest single one.",
    "2 questions are still open in the range.",
  ],
  summary_md:
    "Twenty seven tosses today, and 41.83 dollars of them left the books. Equipment is where the money is: four items, 26.00 dollars, and a keyboard that would have fetched 12.00 dollars secondhand. Food is the most frequent at eleven tosses but only 4.14 dollars. Two questions are still waiting on a person.",
};

export const STATS_WEEK: StatsResponse = {
  bucket: "week",
  period_start: "2026-09-07",
  period_end: "2026-09-20",
  buckets: [
    {
      start: "2026-09-07",
      tosses: 34,
      wasted_cents: 2420,
      book_loss_cents: 1800,
      estimated_value_cents: 840,
      kg_landfill: 4.2,
      kg_co2e_avoided: 1.81,
      asks: 3,
      first_try_accuracy: 0.74,
      by_category: [
        { category: "equipment", tosses: 5, cents: 2500, kg: 1.378 },
        { category: "food", tosses: 15, cents: 1106, kg: 1.686 },
        { category: "e-waste", tosses: 7, cents: 1241, kg: 0.792 },
        { category: "packaging", tosses: 7, cents: 210, kg: 0.662 },
      ],
    },
    {
      start: "2026-09-14",
      tosses: 27,
      wasted_cents: 1583,
      book_loss_cents: 2000,
      estimated_value_cents: 600,
      kg_landfill: 3.2,
      kg_co2e_avoided: 1.32,
      asks: 2,
      first_try_accuracy: 0.81,
      by_category: [
        { category: "equipment", tosses: 4, cents: 2600, kg: 1.102 },
        { category: "e-waste", tosses: 6, cents: 1099, kg: 0.618 },
        { category: "food", tosses: 11, cents: 414, kg: 1.204 },
        { category: "packaging", tosses: 5, cents: 70, kg: 0.498 },
        { category: "other", tosses: 1, cents: 0, kg: 0.012 },
      ],
    },
  ],
  averages: { days: 14, tosses_per_day: 4.357, wasted_cents_per_day: 286, kg_per_day: 0.5286 },
  suggestions: [
    "Equipment is the biggest group at 51.00 dollars across 9 tickets, 55 percent of the 92.40 dollars in the range.",
    "The range averages 2.86 dollars a day across 14 days.",
    "Food is 26 of 61 tickets but 15.20 dollars of 92.40 dollars.",
  ],
  summary_md:
    "Sixty one tosses over the fortnight and 92.40 dollars off the books. Equipment is nine tosses and more than half the money. Food is the most frequent by a distance and the cheapest per item. Packaging is twelve tosses and 2.80 dollars, so it is a carbon line rather than a money one.",
};

/** The read came back and there is nothing in it yet. */
export const STATS_NONE: StatsResponse = {
  bucket: "day",
  period_start: "2026-09-19",
  period_end: "2026-09-19",
  buckets: [],
  averages: { days: 1, tosses_per_day: 0, wasted_cents_per_day: 0, kg_per_day: 0 },
  suggestions: [],
  summary_md: null,
};

export const REVIEW: ReviewListResponse = {
  open_count: 4,
  items: [
    {
      id: 1,
      event_id: 105,
      kind: "unresolved_ask",
      status: "open",
      label: null,
      reason: "Nobody answered before the next toss landed.",
      amount_cents: 16999,
      created_at: "2026-09-19T14:31:00",
      candidates: [
        { label: "phone", p: 0.48 },
        { label: "power bank", p: 0.34 },
        { label: "portable monitor", p: 0.18 },
      ],
    },
    {
      id: 2,
      event_id: 103,
      kind: "estimate_above_threshold",
      status: "open",
      label: "usb-c charger",
      reason: "Valued by a model at $12.00, over the $10.00 that needs a person.",
      amount_cents: 1200,
      created_at: "2026-09-19T14:28:00",
    },
    {
      id: 3,
      event_id: 101,
      kind: "donation",
      status: "open",
      label: "bagel",
      reason: "Claimed as a donation, which carries an enhanced deduction.",
      amount_cents: 62,
      created_at: "2026-09-19T14:24:00",
    },
    {
      id: 4,
      event_id: 102,
      kind: "possible_unrecorded_asset",
      status: "open",
      label: "mechanical keyboard",
      reason: "Worth $120.00 when bought and the register has never heard of it.",
      amount_cents: 12000,
      asset_tag: null,
      created_at: "2026-09-19T14:26:00",
    },
    {
      id: 5,
      event_id: 104,
      kind: "estimate_above_threshold",
      status: "approved",
      label: "water bottle empty",
      reason: "Valued by a model at $0.00.",
      amount_cents: 0,
      decided_at: "2026-09-19T14:33:00",
      decided_by: "person",
      note: "Nothing on it either way.",
      created_at: "2026-09-19T14:30:00",
    },
  ],
};

// The four blocks a CFO reads, on the same close the rest of these fixtures use.
export const CLOSE_BLOCKS: Pick<
  CloseRead,
  "memo_md" | "rollforward" | "reconciliation" | "form4797"
> = {
  memo_md:
    "Five things went in the bin today and four of them were counted. The books lose 20.62, almost all of it the mechanical keyboard, which left the register at its book value of 20.00 with nothing left to deduct because it was fully expensed in the year it was bought.\n\nThe return sees 0.62. The 20.00 gap is bonus depreciation already taken, and it appears on the reconciliation below with the rule that caused it.\n\nOne ticket is still waiting on a person, and the scale reads 14 g more than the tickets account for. Both are in the checks.",
  rollforward: {
    period_start: DAY,
    period_end: DAY,
    ties: true,
    rows: [
      {
        asset_id: 1,
        tag: "bb-0001",
        description: "Dell 24 inch monitor",
        opening_cost_cents: 18900,
        additions_cents: 0,
        disposals_cost_cents: 0,
        closing_cost_cents: 18900,
        opening_accum_cents: 5250,
        depreciation_cents: 525,
        disposals_accum_cents: 0,
        closing_accum_cents: 5775,
        opening_nbv_cents: 13650,
        closing_nbv_cents: 13125,
      },
      {
        asset_id: 2,
        tag: "bb-0002",
        description: "Keychron K8 keyboard",
        opening_cost_cents: 12000,
        additions_cents: 0,
        disposals_cost_cents: 12000,
        closing_cost_cents: 0,
        opening_accum_cents: 10000,
        depreciation_cents: 0,
        disposals_accum_cents: 10000,
        closing_accum_cents: 0,
        opening_nbv_cents: 2000,
        closing_nbv_cents: 0,
      },
    ],
    total: {
      description: "Totals",
      opening_cost_cents: 30900,
      additions_cents: 0,
      disposals_cost_cents: 12000,
      closing_cost_cents: 18900,
      opening_accum_cents: 15250,
      depreciation_cents: 525,
      disposals_accum_cents: 10000,
      closing_accum_cents: 5775,
      opening_nbv_cents: 15650,
      closing_nbv_cents: 13125,
    },
  },
  reconciliation: {
    title:
      "Schedule M-1 shape. The books lose one number, the return another, and the gap has a reason on every line.",
    ties: true,
    book_loss_cents: 2062,
    differences_cents: 2000,
    tax_loss_cents: 62,
    rows: [
      {
        event_id: 102,
        asset_id: 2,
        tag: "bb-0002",
        description: "Keychron K8 keyboard",
        book_loss_cents: 2000,
        tax_loss_cents: 0,
        difference_cents: 2000,
        reason: "Fully expensed under bonus depreciation when it was bought, so the basis is nil.",
        rule_ids: ["BONUS_168K"],
      },
      {
        event_id: 101,
        description: "Bagel",
        book_loss_cents: 62,
        tax_loss_cents: 62,
        difference_cents: 0,
        reason: "Inventory written off at cost. The books and the return agree.",
        rule_ids: ["INV_WRITE_OFF"],
      },
    ],
  },
  form4797: {
    disclaimer:
      "A working paper prepared from the register and the tickets. It is not a filing and it has not been reviewed.",
    part_ii_line_10_cents: -2000,
    part_ii_rows: [
      {
        part: "II",
        line: "10",
        description: "Keychron K8 keyboard, tag BB-0002",
        date_acquired: "2025-11-04",
        date_disposed: DAY,
        gross_proceeds_cents: 0,
        cost_cents: 12000,
        depreciation_allowed_cents: 12000,
        gain_or_loss_cents: -2000,
        recapture_note: "Book basis 20.00 against a tax basis of nil.",
        rule_ids: ["SEC_1231"],
      },
    ],
    part_iii_recapture_cents: 0,
    part_iii_rows: [],
  },
};
