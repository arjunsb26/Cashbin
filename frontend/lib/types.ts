// Mirrors PLAN.md section 8 (data model) and section 14 (API).
// Replaced by /contracts/api-types.ts once Step 0 lands. Keep the names identical.
// Money is integer cents. Mass is grams. Timestamps are UTC ISO strings.

export type ItemClass = "inventory" | "fixed_asset" | "untracked";
export type EventKind = "toss" | "bag_change" | "removal";
export type EventStatus = "detected" | "identified" | "asking" | "confirmed" | "posted" | "void";
export type IdentifyMethod = "qr" | "memory" | "cloud" | "human" | "stub";
export type OptionName = "trash" | "recycle" | "repair" | "resell" | "donate";
export type AssetStatus = "active" | "disposed" | "ghost_suspected";
export type TaxMethod = "bonus_100" | "straight_line";
export type Basis = "book" | "tax_memo";
export type EstimateSource = "catalog" | "register" | "model_estimate" | "human";
export type CheckStatus = "pass" | "warn" | "fail";
export type Tone = "green" | "amber" | "red" | "neutral";

export type Estimate = {
  low_cents: number | null;
  mid_cents: number | null;
  high_cents: number | null;
  source: EstimateSource | null;
};

export type TracePoint = { t_ms: number; g: number };

export type WeightTrace = {
  points: TracePoint[];
  open_t_ms: number;
  settle_t_ms: number;
  baseline_g: number;
};

export type EventSummary = {
  id: number;
  created_at: string;
  kind: EventKind;
  status: EventStatus;
  mass_g: number;
  mass_err_g: number;
  label: string | null;
  item_class: ItemClass | null;
  book_amount_cents: number | null;
  is_estimate: boolean;
  blocked: boolean;
  round_id: number | null;
};

export type Identification = {
  method: IdentifyMethod;
  label: string;
  item_class: ItemClass;
  confidence: number;
  candidates: Candidate[];
  posterior: Candidate[] | null;
  used_mass_prior: boolean;
  latency_ms: number;
  cost_microusd: number;
  is_final: boolean;
  visible_text: string | null;
};

export type Candidate = { label: string; p: number };

export type ItemRecord = {
  event_id: number;
  label: string;
  item_class: ItemClass;
  mass_g: number;
  material_mix: Record<string, number>;
  regulatory_flags: string[];
  book_value_cents: number;
  tax_basis_cents: number;
  asset_id: number | null;
  cost_basis_cents: number;
  fmv: Estimate;
  repair: Estimate;
  replacement_cents: number | null;
  scrap_cents: number | null;
};

export type OptionScore = {
  option: OptionName;
  allowed: boolean;
  blocked_reason: string | null;
  cash_cents: number;
  tax_effect_cents: number;
  net_after_tax_cents: number;
  kg_co2e: number | null;
  kg_landfill: number;
  needs_human_review: boolean;
  notes: string[];
  rule_ids: string[];
  rank: number;
};

export type JournalLine = {
  account: string;
  debit_cents: number;
  credit_cents: number;
};

export type JournalEntry = {
  id: number;
  event_id: number | null;
  close_id: number | null;
  posted_at: string;
  memo: string;
  basis: Basis;
  lines: JournalLine[];
  evidence: Evidence | null;
};

export type Evidence = {
  event_id: number;
  frame_before: string | null;
  frame_after: string | null;
  frame_peak: string | null;
  crop: string | null;
  crop_quality: "high" | "low" | null;
  mass_g: number;
  mass_err_g: number;
  method: IdentifyMethod;
  confidence: number;
  human_confirmed: boolean;
  rule_ids: string[];
};

export type TaxRule = {
  id: string;
  text: string;
  citation_title: string;
  citation_url: string;
};

export type FormulaStep = {
  label: string;
  expression: string;
};

export type EvidenceBundle = {
  event_id: number;
  title: string;
  figure: string;
  crop: string | null;
  trace: WeightTrace;
  identification: Identification;
  formula: FormulaStep[];
  rules: TaxRule[];
  human_confirmed: boolean;
  estimate: Estimate | null;
};

export type EventDetail = {
  event: EventSummary;
  item: ItemRecord | null;
  identification: Identification | null;
  options: OptionScore[];
  entries: JournalEntry[];
  evidence: EvidenceBundle | null;
  ask: AskState | null;
  corrections: Correction[];
  saved_if_followed_cents: number;
  tone: Tone;
};

export type AskState = {
  event_id: number;
  candidates: Candidate[];
  crop: string | null;
  mass_g: number;
  mass_err_g: number;
};

export type Correction = {
  id: number;
  event_id: number;
  field: string;
  old_value: string;
  new_value: string;
  by: string;
  created_at: string;
};

export type Asset = {
  id: number;
  tag: string;
  description: string;
  category: string;
  cost_cents: number;
  in_service_date: string;
  book_life_months: number;
  salvage_cents: number;
  tax_method: TaxMethod;
  book_value_cents: number;
  tax_basis_cents: number;
  status: AssetStatus;
  disposed_event_id: number | null;
  insured: boolean;
  location: string;
};

export type NewAsset = {
  tag: string;
  description: string;
  category: string;
  cost_cents: number;
  in_service_date: string;
  book_life_months: number;
  tax_method: TaxMethod;
  location: string;
};

export type Summary = {
  saved_if_followed_cents: number;
  kg_diverted: number;
  n_events: number;
  first_try_accuracy: number;
  cheapest_equals_greenest: number;
};

export type Round = {
  id: number;
  started_at: string;
  ended_at: string | null;
  n_events: number;
  first_try_accuracy: number;
  ask_rate: number;
  n_corrected_after_confident: number;
  mean_latency_ms: number;
  cost_per_event_microusd: number;
  local_share: number;
};

export type LearnedNote = {
  id: number;
  text: string;
  created_at: string;
};

export type Thresholds = {
  confident_p: number;
  min_margin: number;
  memory_max_dist: number;
  round_size: number;
  tax_rate: number;
  capitalization_threshold_cents: number;
};

export type TrialBalanceRow = {
  account: string;
  debit_cents: number;
  credit_cents: number;
};

export type CloseCheck = {
  id: string;
  name: string;
  status: CheckStatus;
  detail: string;
  numbers: { label: string; value: string }[];
  investigation_md: string | null;
  suspect_event_ids: number[];
};

export type CloseReport = {
  id: number;
  period_start: string;
  period_end: string;
  created_at: string;
  write_offs: { label: string; mass_g: number; amount_cents: number; event_id: number }[];
  disposals: {
    tag: string;
    description: string;
    book_loss_cents: number;
    tax_loss_cents: number;
    event_id: number;
  }[];
  tax_items: { label: string; amount_cents: number; rule_id: string }[];
  sustainability: {
    kg_landfill: number;
    kg_diverted_if_followed: number;
    kg_co2e_actual: number;
    kg_co2e_best: number;
    cheapest_equals_greenest: number;
    kg_ewaste: number;
  };
  missed: { option: OptionName; amount_cents: number }[];
  ghost_assets: { tag: string; description: string; reason: string }[];
  checks: CloseCheck[];
};

export type SetupItem = {
  id: string;
  file: string;
  field: string;
  what: string;
  done: boolean;
};

export type DeviceStatus = {
  bin: "connected" | "offline";
  phone: "connected" | "offline";
  last_weight_g: number;
};

// WebSocket topics, PLAN.md section 6
export type UiMessage =
  | { type: "weight"; t_ms: number; g: number; step: boolean }
  | { type: "event.created"; event: EventSummary }
  | { type: "event.updated"; event: EventSummary; detail?: EventDetail }
  | { type: "journal.posted"; entry: JournalEntry }
  | { type: "ask.opened"; ask: AskState }
  | { type: "ask.resolved"; event_id: number; label: string }
  | { type: "metrics.updated"; summary: Summary }
  | { type: "device.status"; status: DeviceStatus };
