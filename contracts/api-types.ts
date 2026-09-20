/* Generated from backend/app/schemas.py by scripts/gen_types.py. Do not edit.
 * Run: uv run --project backend python scripts/gen_types.py
 */

/**
 * This interface was referenced by `BinBooksContracts`'s JSON-Schema
 * via the `definition` "AssetStatus".
 */
export type AssetStatus = "active" | "disposed" | "ghost_suspected";
/**
 * This interface was referenced by `BinBooksContracts`'s JSON-Schema
 * via the `definition` "TaxMethod".
 */
export type TaxMethod = "bonus_100" | "straight_line";
/**
 * This interface was referenced by `BinBooksContracts`'s JSON-Schema
 * via the `definition` "ItemClass".
 */
export type ItemClass = "inventory" | "fixed_asset" | "untracked";
/**
 * This interface was referenced by `BinBooksContracts`'s JSON-Schema
 * via the `definition` "EventStatus".
 */
export type EventStatus = "detected" | "identified" | "asking" | "confirmed" | "posted" | "void";
/**
 * This interface was referenced by `BinBooksContracts`'s JSON-Schema
 * via the `definition` "CropQuality".
 */
export type CropQuality = "ok" | "low";
/**
 * This interface was referenced by `BinBooksContracts`'s JSON-Schema
 * via the `definition` "JournalBasis".
 */
export type JournalBasis = "book" | "tax_memo";
/**
 * This interface was referenced by `BinBooksContracts`'s JSON-Schema
 * via the `definition` "OptionKind".
 */
export type OptionKind = "trash" | "recycle" | "repair" | "resell" | "donate";
/**
 * This interface was referenced by `BinBooksContracts`'s JSON-Schema
 * via the `definition` "EventKind".
 */
export type EventKind = "toss" | "bag_change" | "removal";
/**
 * This interface was referenced by `BinBooksContracts`'s JSON-Schema
 * via the `definition` "IdentifyMethod".
 */
export type IdentifyMethod = "qr" | "memory" | "cloud" | "human" | "stub";

/**
 * Generated from backend/app/schemas.py. Do not edit. Run scripts/gen_types.py after any schema change.
 */
export interface BinBooksContracts {
  AskCandidate?: AskCandidate;
  AssetCreate?: AssetCreate;
  AssetListResponse?: AssetListResponse;
  AssetRead?: AssetRead;
  AssetStatus?: AssetStatus;
  AssetUpdate?: AssetUpdate;
  BinButton?: BinButton;
  BinHello?: BinHello;
  BinPing?: BinPing;
  BinPong?: BinPong;
  BinTare?: BinTare;
  BinWeight?: BinWeight;
  BrandInfo?: BrandInfo;
  CatalogItemCreate?: CatalogItemCreate;
  CatalogItemRead?: CatalogItemRead;
  CatalogListResponse?: CatalogListResponse;
  CloseCheck?: CloseCheck;
  CloseRead?: CloseRead;
  CloseRequest?: CloseRequest;
  CorrectionCreate?: CorrectionCreate;
  CorrectionRead?: CorrectionRead;
  CorrectionResponse?: CorrectionResponse;
  CropQuality?: CropQuality;
  DeviceTareResponse?: DeviceTareResponse;
  ErrorResponse?: ErrorResponse;
  EstimateRef?: EstimateRef;
  EventDetail?: EventDetail;
  EventKind?: EventKind;
  EventListResponse?: EventListResponse;
  EventStatus?: EventStatus;
  EventSummary?: EventSummary;
  HealthResponse?: HealthResponse;
  IdentificationRead?: IdentificationRead;
  IdentifyMethod?: IdentifyMethod;
  ItemClass?: ItemClass;
  ItemRecordRead?: ItemRecordRead;
  JournalBasis?: JournalBasis;
  JournalEntryRead?: JournalEntryRead;
  JournalLineRead?: JournalLineRead;
  JournalResponse?: JournalResponse;
  MoneyRange?: MoneyRange;
  OptionKind?: OptionKind;
  OptionScoreRead?: OptionScoreRead;
  PhoneAsk?: PhoneAsk;
  PhoneHello?: PhoneHello;
  PhoneIdle?: PhoneIdle;
  PhonePing?: PhonePing;
  PhonePong?: PhonePong;
  PhoneResult?: PhoneResult;
  RoundListResponse?: RoundListResponse;
  RoundRead?: RoundRead;
  RuleRead?: RuleRead;
  RulesResponse?: RulesResponse;
  ScreenAsk?: ScreenAsk;
  ScreenIdle?: ScreenIdle;
  ScreenOffline?: ScreenOffline;
  ScreenResult?: ScreenResult;
  ScreenThinking?: ScreenThinking;
  SettingsRead?: SettingsRead;
  SettingsUpdate?: SettingsUpdate;
  SetupResponse?: SetupResponse;
  SimExpectRequest?: SimExpectRequest;
  SimExpectResponse?: SimExpectResponse;
  SimTossRequest?: SimTossRequest;
  SimTossResponse?: SimTossResponse;
  SummaryResponse?: SummaryResponse;
  TaxMethod?: TaxMethod;
  TrialBalanceRow?: TrialBalanceRow;
  UiAskOpened?: UiAskOpened;
  UiAskResolved?: UiAskResolved;
  UiDeviceStatus?: UiDeviceStatus;
  UiEventCreated?: UiEventCreated;
  UiEventUpdated?: UiEventUpdated;
  UiJournalPosted?: UiJournalPosted;
  UiMetricsUpdated?: UiMetricsUpdated;
  UiWeight?: UiWeight;
  ValueEstimate?: ValueEstimate;
  VisionCandidate?: VisionCandidate;
  VisionResult?: VisionResult;
  VoidResponse?: VoidResponse;
}
/**
 * This interface was referenced by `BinBooksContracts`'s JSON-Schema
 * via the `definition` "AskCandidate".
 */
export interface AskCandidate {
  /**
   * Lowercase label. Letters, digits, spaces and hyphens only.
   */
  label: string;
  p: number;
}
/**
 * This interface was referenced by `BinBooksContracts`'s JSON-Schema
 * via the `definition` "AssetCreate".
 */
export interface AssetCreate {
  book_life_months: number;
  category?: string | null;
  cost_cents: number;
  description: string;
  in_service_date: string;
  insured?: boolean;
  location?: string | null;
  salvage_cents?: number;
  /**
   * Lowercase label. Letters, digits, spaces and hyphens only.
   */
  tag: string;
  tax_basis_cents_override?: number | null;
  tax_method?: "bonus_100" | "straight_line";
}
/**
 * This interface was referenced by `BinBooksContracts`'s JSON-Schema
 * via the `definition` "AssetListResponse".
 */
export interface AssetListResponse {
  assets?: AssetRead[];
}
/**
 * This interface was referenced by `BinBooksContracts`'s JSON-Schema
 * via the `definition` "AssetRead".
 */
export interface AssetRead {
  book_life_months: number;
  book_value_cents?: number | null;
  category?: string | null;
  cost_cents: number;
  description: string;
  disposed_event_id?: number | null;
  id: number;
  in_service_date: string;
  insured?: boolean;
  location?: string | null;
  salvage_cents?: number;
  status: AssetStatus;
  tag: string;
  tax_basis_cents?: number | null;
  tax_basis_cents_override?: number | null;
  tax_method: TaxMethod;
}
/**
 * This interface was referenced by `BinBooksContracts`'s JSON-Schema
 * via the `definition` "AssetUpdate".
 */
export interface AssetUpdate {
  book_life_months?: number | null;
  category?: string | null;
  cost_cents?: number | null;
  description?: string | null;
  in_service_date?: string | null;
  insured?: boolean | null;
  location?: string | null;
  salvage_cents?: number | null;
  status?: AssetStatus | null;
  tax_basis_cents_override?: number | null;
  tax_method?: TaxMethod | null;
}
/**
 * This interface was referenced by `BinBooksContracts`'s JSON-Schema
 * via the `definition` "BinButton".
 */
export interface BinButton {
  id: string;
  type?: "button";
}
/**
 * This interface was referenced by `BinBooksContracts`'s JSON-Schema
 * via the `definition` "BinHello".
 */
export interface BinHello {
  device: string;
  fw: string;
  type?: "hello";
}
/**
 * This interface was referenced by `BinBooksContracts`'s JSON-Schema
 * via the `definition` "BinPing".
 */
export interface BinPing {
  type?: "ping";
}
/**
 * This interface was referenced by `BinBooksContracts`'s JSON-Schema
 * via the `definition` "BinPong".
 */
export interface BinPong {
  t: number;
  type?: "pong";
}
/**
 * This interface was referenced by `BinBooksContracts`'s JSON-Schema
 * via the `definition` "BinTare".
 */
export interface BinTare {
  type?: "tare";
}
/**
 * This interface was referenced by `BinBooksContracts`'s JSON-Schema
 * via the `definition` "BinWeight".
 */
export interface BinWeight {
  /**
   * Raw grams after calibration. The backend does the filtering.
   */
  g: number;
  /**
   * Device milliseconds. Kept for debugging only.
   */
  t: number;
  type?: "weight";
}
/**
 * The product name lives in brand.json at the repo root and nowhere else.
 *
 * This interface was referenced by `BinBooksContracts`'s JSON-Schema
 * via the `definition` "BrandInfo".
 */
export interface BrandInfo {
  name: string;
  short_name: string;
  tagline: string;
}
/**
 * This interface was referenced by `BinBooksContracts`'s JSON-Schema
 * via the `definition` "CatalogItemCreate".
 */
export interface CatalogItemCreate {
  class: ItemClass;
  fmv_per_kg_cents?: number | null;
  /**
   * Lowercase label. Letters, digits, spaces and hyphens only.
   */
  label: string;
  material_mix?: {
    /**
     * This interface was referenced by `undefined`'s JSON-Schema definition
     * via the `patternProperty` "^[a-z0-9_]+$".
     */
    [k: string]: number;
  };
  price_per_kg_cents?: number | null;
  /**
   * @maxItems 8
   */
  regulatory_flags?:
    | []
    | [string]
    | [string, string]
    | [string, string, string]
    | [string, string, string, string]
    | [string, string, string, string, string]
    | [string, string, string, string, string, string]
    | [string, string, string, string, string, string, string]
    | [string, string, string, string, string, string, string, string];
  unit_cost_cents?: number | null;
  unit_mass_g?: number | null;
}
/**
 * This interface was referenced by `BinBooksContracts`'s JSON-Schema
 * via the `definition` "CatalogItemRead".
 */
export interface CatalogItemRead {
  class: ItemClass;
  fmv_per_kg_cents?: number | null;
  id: number;
  label: string;
  mass_prior_mean_g?: number | null;
  mass_prior_n?: number;
  mass_prior_var?: number | null;
  material_mix?: {
    [k: string]: number;
  };
  price_per_kg_cents?: number | null;
  regulatory_flags?: string[];
  unit_cost_cents?: number | null;
  unit_mass_g?: number | null;
}
/**
 * This interface was referenced by `BinBooksContracts`'s JSON-Schema
 * via the `definition` "CatalogListResponse".
 */
export interface CatalogListResponse {
  items?: CatalogItemRead[];
}
/**
 * This interface was referenced by `BinBooksContracts`'s JSON-Schema
 * via the `definition` "CloseCheck".
 */
export interface CloseCheck {
  detail?: string;
  id: string;
  numbers?: {
    [k: string]: number;
  };
  result: "pass" | "warn" | "fail";
  title: string;
}
/**
 * This interface was referenced by `BinBooksContracts`'s JSON-Schema
 * via the `definition` "CloseRead".
 */
export interface CloseRead {
  checks?: CloseCheck[];
  created_at: string;
  id: number;
  investigation_md?: string | null;
  period_end: string;
  period_start: string;
  report?: {
    [k: string]: unknown;
  };
  status: string;
  totals?: {
    [k: string]: unknown;
  };
}
/**
 * This interface was referenced by `BinBooksContracts`'s JSON-Schema
 * via the `definition` "CloseRequest".
 */
export interface CloseRequest {
  period_end: string;
  period_start: string;
}
/**
 * The ask answer and the dashboard override. Free text lands here and stops here.
 *
 * This interface was referenced by `BinBooksContracts`'s JSON-Schema
 * via the `definition` "CorrectionCreate".
 */
export interface CorrectionCreate {
  by?: string;
  class?: ItemClass | null;
  event_id: number;
  /**
   * Lowercase label. Letters, digits, spaces and hyphens only.
   */
  label: string;
}
/**
 * This interface was referenced by `BinBooksContracts`'s JSON-Schema
 * via the `definition` "CorrectionRead".
 */
export interface CorrectionRead {
  by: string;
  created_at: string;
  event_id: number;
  field: string;
  id: number;
  new_value?: string | null;
  old_value?: string | null;
}
/**
 * This interface was referenced by `BinBooksContracts`'s JSON-Schema
 * via the `definition` "CorrectionResponse".
 */
export interface CorrectionResponse {
  class?: ItemClass | null;
  correction_id: number;
  event_id: number;
  label: string;
  status: EventStatus;
}
/**
 * This interface was referenced by `BinBooksContracts`'s JSON-Schema
 * via the `definition` "DeviceTareResponse".
 */
export interface DeviceTareResponse {
  device?: "bin";
  sent: boolean;
}
/**
 * This interface was referenced by `BinBooksContracts`'s JSON-Schema
 * via the `definition` "ErrorResponse".
 */
export interface ErrorResponse {
  code?: string;
  detail: string;
}
/**
 * PLAN.md rule 5. An estimate carries its range and where it came from.
 *
 * This interface was referenced by `BinBooksContracts`'s JSON-Schema
 * via the `definition` "EstimateRef".
 */
export interface EstimateRef {
  high?: number | null;
  low?: number | null;
  mid?: number | null;
  source?: ("catalog" | "register" | "model_estimate" | "human") | null;
}
/**
 * This interface was referenced by `BinBooksContracts`'s JSON-Schema
 * via the `definition` "EventDetail".
 */
export interface EventDetail {
  corrections?: CorrectionRead[];
  entries?: JournalEntryRead[];
  event: EventSummary;
  frame_after_url?: string | null;
  frame_before_url?: string | null;
  frame_peak_url?: string | null;
  identifications?: IdentificationRead[];
  item_record?: ItemRecordRead | null;
  options?: OptionScoreRead[];
  /**
   * Pairs of [t_seconds, grams] around the step.
   */
  trace?: number[][];
}
/**
 * This interface was referenced by `BinBooksContracts`'s JSON-Schema
 * via the `definition` "JournalEntryRead".
 */
export interface JournalEntryRead {
  basis: JournalBasis;
  close_id?: number | null;
  event_id?: number | null;
  evidence?: {
    [k: string]: unknown;
  };
  id: number;
  lines?: JournalLineRead[];
  memo?: string;
  posted_at: string;
}
/**
 * This interface was referenced by `BinBooksContracts`'s JSON-Schema
 * via the `definition` "JournalLineRead".
 */
export interface JournalLineRead {
  account: string;
  account_name?: string | null;
  credit_cents?: number;
  debit_cents?: number;
  entry_id: number;
  id: number;
}
/**
 * This interface was referenced by `BinBooksContracts`'s JSON-Schema
 * via the `definition` "EventSummary".
 */
export interface EventSummary {
  best_option?: OptionKind | null;
  class?: ItemClass | null;
  created_at: string;
  crop_quality?: CropQuality | null;
  crop_url?: string | null;
  flags?: string[];
  id: number;
  is_estimate?: boolean;
  kind: EventKind;
  label?: string | null;
  mass_err_g?: number | null;
  mass_g?: number | null;
  net_book_cents?: number | null;
  posted_cents?: number | null;
  round_id?: number | null;
  saved_if_followed_cents?: number | null;
  status: EventStatus;
}
/**
 * This interface was referenced by `BinBooksContracts`'s JSON-Schema
 * via the `definition` "IdentificationRead".
 */
export interface IdentificationRead {
  candidates?: VisionCandidate[];
  class?: ItemClass | null;
  confidence?: number | null;
  cost_microusd?: number | null;
  description?: string | null;
  event_id: number;
  id: number;
  is_final?: boolean;
  label?: string | null;
  latency_ms?: number | null;
  method: IdentifyMethod;
  model?: string | null;
  posterior?: {
    [k: string]: number;
  };
  provider?: string | null;
  tokens_in?: number | null;
  tokens_out?: number | null;
  used_mass_prior?: boolean;
}
/**
 * This interface was referenced by `BinBooksContracts`'s JSON-Schema
 * via the `definition` "VisionCandidate".
 */
export interface VisionCandidate {
  /**
   * Lowercase label. Letters, digits, spaces and hyphens only.
   */
  label: string;
  p: number;
}
/**
 * This interface was referenced by `BinBooksContracts`'s JSON-Schema
 * via the `definition` "ItemRecordRead".
 */
export interface ItemRecordRead {
  asset_id?: number | null;
  book_value_cents?: number;
  class: ItemClass;
  condition?: "working" | "broken" | "unknown";
  cost_basis_cents?: number;
  event_id: number;
  fmv?: EstimateRef;
  label: string;
  mass_g: number;
  material_mix?: {
    [k: string]: number;
  };
  regulatory_flags?: string[];
  repair?: EstimateRef;
  replacement_cents?: number | null;
  replacement_source?: string | null;
  scrap_cents?: number | null;
  scrap_source?: string | null;
  tax_basis_cents?: number;
}
/**
 * This interface was referenced by `BinBooksContracts`'s JSON-Schema
 * via the `definition` "OptionScoreRead".
 */
export interface OptionScoreRead {
  allowed: boolean;
  blocked_reason?: string | null;
  cash_cents: number;
  event_id: number;
  id: number;
  kg_co2e?: number | null;
  kg_co2e_avoided?: number | null;
  kg_landfill?: number;
  needs_human_review?: boolean;
  net_after_tax_cents: number;
  notes?: string[];
  option: OptionKind;
  rank?: number | null;
  rule_ids?: string[];
  tax_effect_cents: number;
}
/**
 * This interface was referenced by `BinBooksContracts`'s JSON-Schema
 * via the `definition` "EventListResponse".
 */
export interface EventListResponse {
  events?: EventSummary[];
}
/**
 * This interface was referenced by `BinBooksContracts`'s JSON-Schema
 * via the `definition` "HealthResponse".
 */
export interface HealthResponse {
  db: boolean;
  product_name: string;
  status: "ok" | "degraded";
  version: string;
}
/**
 * This interface was referenced by `BinBooksContracts`'s JSON-Schema
 * via the `definition` "JournalResponse".
 */
export interface JournalResponse {
  balanced?: boolean;
  basis?: JournalBasis | null;
  entries?: JournalEntryRead[];
  trial_balance?: TrialBalanceRow[];
}
/**
 * This interface was referenced by `BinBooksContracts`'s JSON-Schema
 * via the `definition` "TrialBalanceRow".
 */
export interface TrialBalanceRow {
  account: string;
  account_name: string;
  credit_cents?: number;
  debit_cents?: number;
}
/**
 * An estimate in integer cents with its rationale. Low, mid and high must be ordered.
 *
 * This interface was referenced by `BinBooksContracts`'s JSON-Schema
 * via the `definition` "MoneyRange".
 */
export interface MoneyRange {
  high: number;
  low: number;
  mid: number;
  rationale?: string;
}
/**
 * This interface was referenced by `BinBooksContracts`'s JSON-Schema
 * via the `definition` "PhoneAsk".
 */
export interface PhoneAsk {
  /**
   * @maxItems 4
   */
  candidates?:
    | []
    | [AskCandidate]
    | [AskCandidate, AskCandidate]
    | [AskCandidate, AskCandidate, AskCandidate]
    | [AskCandidate, AskCandidate, AskCandidate, AskCandidate];
  crop_url?: string | null;
  event_id: number;
  looks_like?: string | null;
  type?: "ask";
}
/**
 * This interface was referenced by `BinBooksContracts`'s JSON-Schema
 * via the `definition` "PhoneHello".
 */
export interface PhoneHello {
  type?: "hello";
  ua?: string;
}
/**
 * This interface was referenced by `BinBooksContracts`'s JSON-Schema
 * via the `definition` "PhoneIdle".
 */
export interface PhoneIdle {
  type?: "idle";
}
/**
 * This interface was referenced by `BinBooksContracts`'s JSON-Schema
 * via the `definition` "PhonePing".
 */
export interface PhonePing {
  type?: "ping";
}
/**
 * This interface was referenced by `BinBooksContracts`'s JSON-Schema
 * via the `definition` "PhonePong".
 */
export interface PhonePong {
  type?: "pong";
}
/**
 * This interface was referenced by `BinBooksContracts`'s JSON-Schema
 * via the `definition` "PhoneResult".
 */
export interface PhoneResult {
  best_option: OptionKind;
  big: string;
  event_id: number;
  line: string;
  title: string;
  tone: "green" | "amber" | "red" | "neutral";
  type?: "result";
}
/**
 * This interface was referenced by `BinBooksContracts`'s JSON-Schema
 * via the `definition` "RoundListResponse".
 */
export interface RoundListResponse {
  /**
   * The most recent corrections in plain words, newest first.
   */
  learned?: string[];
  rounds?: RoundRead[];
}
/**
 * This interface was referenced by `BinBooksContracts`'s JSON-Schema
 * via the `definition` "RoundRead".
 */
export interface RoundRead {
  ask_rate?: number | null;
  cloud_cost_microusd?: number;
  cost_per_event_microusd?: number | null;
  ended_at?: string | null;
  first_try_accuracy?: number | null;
  id: number;
  local_share?: number | null;
  mean_latency_ms?: number | null;
  n_asked?: number;
  n_correct_first_try?: number;
  n_corrected_after_confident?: number;
  n_events?: number;
  started_at: string;
}
/**
 * One tax rule as the evidence drawer shows it.
 *
 * The words and the link come from `tax_rules.yaml`, which is the only copy of either.
 * DESIGN.md 4.2 asks the drawer for the rule in plain language with its citation as a link,
 * so retyping the text into a client would be a second copy that drifts.
 *
 * This interface was referenced by `BinBooksContracts`'s JSON-Schema
 * via the `definition` "RuleRead".
 */
export interface RuleRead {
  citation_url?: string | null;
  id: string;
  needs_human_review?: boolean;
  plain_text: string;
  title: string;
}
/**
 * This interface was referenced by `BinBooksContracts`'s JSON-Schema
 * via the `definition` "RulesResponse".
 */
export interface RulesResponse {
  rules?: RuleRead[];
}
/**
 * This interface was referenced by `BinBooksContracts`'s JSON-Schema
 * via the `definition` "ScreenAsk".
 */
export interface ScreenAsk {
  l1: string;
  l2: string;
  s?: "ask";
  type?: "screen";
}
/**
 * This interface was referenced by `BinBooksContracts`'s JSON-Schema
 * via the `definition` "ScreenIdle".
 */
export interface ScreenIdle {
  s?: "idle";
  type?: "screen";
}
/**
 * This interface was referenced by `BinBooksContracts`'s JSON-Schema
 * via the `definition` "ScreenOffline".
 */
export interface ScreenOffline {
  s?: "offline";
  type?: "screen";
}
/**
 * This interface was referenced by `BinBooksContracts`'s JSON-Schema
 * via the `definition` "ScreenResult".
 */
export interface ScreenResult {
  big: string;
  c: "green" | "amber" | "red" | "neutral";
  l1: string;
  l2: string;
  s?: "result";
  type?: "screen";
}
/**
 * This interface was referenced by `BinBooksContracts`'s JSON-Schema
 * via the `definition` "ScreenThinking".
 */
export interface ScreenThinking {
  s?: "thinking";
  type?: "screen";
}
/**
 * Only the keys /api/settings may change. Nothing here is a secret.
 *
 * This interface was referenced by `BinBooksContracts`'s JSON-Schema
 * via the `definition` "SettingsRead".
 */
export interface SettingsRead {
  bag_change_g: number;
  capitalization_threshold_cents: number;
  confident_p: number;
  disposal_fee_cents: number;
  llm_estimate_effort?: "none" | "minimal" | "low" | "medium" | "high";
  llm_service_tier?: "auto" | "default" | "flex" | "scale" | "priority" | "fast";
  llm_text_effort?: "none" | "minimal" | "low" | "medium" | "high";
  llm_timeout_s: number;
  llm_vision_effort?: "none" | "minimal" | "low" | "medium" | "high";
  memory_max_dist: number;
  min_margin: number;
  recycle_fee_cents: number;
  round_size: number;
  settle_ms: number;
  step_min_g: number;
  tax_rate: number;
  tone_co2e_kg: number;
}
/**
 * This interface was referenced by `BinBooksContracts`'s JSON-Schema
 * via the `definition` "SettingsUpdate".
 */
export interface SettingsUpdate {
  bag_change_g?: number | null;
  capitalization_threshold_cents?: number | null;
  confident_p?: number | null;
  disposal_fee_cents?: number | null;
  llm_estimate_effort?: ("none" | "minimal" | "low" | "medium" | "high") | null;
  llm_service_tier?: ("auto" | "default" | "flex" | "scale" | "priority" | "fast") | null;
  llm_text_effort?: ("none" | "minimal" | "low" | "medium" | "high") | null;
  llm_timeout_s?: number | null;
  llm_vision_effort?: ("none" | "minimal" | "low" | "medium" | "high") | null;
  memory_max_dist?: number | null;
  min_margin?: number | null;
  recycle_fee_cents?: number | null;
  round_size?: number | null;
  settle_ms?: number | null;
  step_min_g?: number | null;
  tax_rate?: number | null;
  tone_co2e_kg?: number | null;
}
/**
 * The setup checklist: every seed cell a person still has to fill in.
 *
 * PLAN.md section 17. One line per cell, so nothing fake can slip into the demo
 * unnoticed. An empty list means the seed files are complete.
 *
 * This interface was referenced by `BinBooksContracts`'s JSON-Schema
 * via the `definition` "SetupResponse".
 */
export interface SetupResponse {
  items?: string[];
}
/**
 * Dev only. Tells the stub identification provider what the simulator is about to toss.
 *
 * This interface was referenced by `BinBooksContracts`'s JSON-Schema
 * via the `definition` "SimExpectRequest".
 */
export interface SimExpectRequest {
  /**
   * Lowercase label. Letters, digits, spaces and hyphens only.
   */
  label: string;
  mass_g?: number | null;
}
/**
 * This interface was referenced by `BinBooksContracts`'s JSON-Schema
 * via the `definition` "SimExpectResponse".
 */
export interface SimExpectResponse {
  label: string;
  mass_g?: number | null;
}
/**
 * Dev only. Mounted only when DEV_TOOLS is on.
 *
 * With no `image` the frames come from whatever the camera is looking at right now, so
 * the Add button on the dashboard and the phone can make a ticket out of a real item and
 * a weight somebody typed in. With an `image` it is the old simulator path.
 *
 * This interface was referenced by `BinBooksContracts`'s JSON-Schema
 * via the `definition` "SimTossRequest".
 */
export interface SimTossRequest {
  image?: string | null;
  label?: string | null;
  mass_g: number;
}
/**
 * This interface was referenced by `BinBooksContracts`'s JSON-Schema
 * via the `definition` "SimTossResponse".
 */
export interface SimTossResponse {
  event_id: number;
  status: EventStatus;
}
/**
 * The four header numbers on the Live page.
 *
 * This interface was referenced by `BinBooksContracts`'s JSON-Schema
 * via the `definition` "SummaryResponse".
 */
export interface SummaryResponse {
  events?: number;
  first_try_accuracy?: number | null;
  kg_diverted?: number;
  saved_if_followed_cents?: number;
}
/**
 * This interface was referenced by `BinBooksContracts`'s JSON-Schema
 * via the `definition` "UiAskOpened".
 */
export interface UiAskOpened {
  /**
   * @maxItems 4
   */
  candidates?:
    | []
    | [AskCandidate]
    | [AskCandidate, AskCandidate]
    | [AskCandidate, AskCandidate, AskCandidate]
    | [AskCandidate, AskCandidate, AskCandidate, AskCandidate];
  crop_url?: string | null;
  event_id: number;
  looks_like?: string | null;
  type?: "ask.opened";
}
/**
 * This interface was referenced by `BinBooksContracts`'s JSON-Schema
 * via the `definition` "UiAskResolved".
 */
export interface UiAskResolved {
  by?: string;
  event_id: number;
  /**
   * Lowercase label. Letters, digits, spaces and hyphens only.
   */
  label: string;
  type?: "ask.resolved";
}
/**
 * This interface was referenced by `BinBooksContracts`'s JSON-Schema
 * via the `definition` "UiDeviceStatus".
 */
export interface UiDeviceStatus {
  connected: boolean;
  detail?: string | null;
  device: "bin" | "phone";
  last_seen?: string | null;
  type?: "device.status";
}
/**
 * This interface was referenced by `BinBooksContracts`'s JSON-Schema
 * via the `definition` "UiEventCreated".
 */
export interface UiEventCreated {
  event: EventSummary;
  type?: "event.created";
}
/**
 * This interface was referenced by `BinBooksContracts`'s JSON-Schema
 * via the `definition` "UiEventUpdated".
 */
export interface UiEventUpdated {
  event: EventSummary;
  type?: "event.updated";
}
/**
 * This interface was referenced by `BinBooksContracts`'s JSON-Schema
 * via the `definition` "UiJournalPosted".
 */
export interface UiJournalPosted {
  entry: JournalEntryRead;
  type?: "journal.posted";
}
/**
 * This interface was referenced by `BinBooksContracts`'s JSON-Schema
 * via the `definition` "UiMetricsUpdated".
 */
export interface UiMetricsUpdated {
  round?: RoundRead | null;
  summary: SummaryResponse;
  type?: "metrics.updated";
}
/**
 * Downsampled to 10 Hz. `t` is backend arrival seconds, one clock for everything.
 *
 * This interface was referenced by `BinBooksContracts`'s JSON-Schema
 * via the `definition` "UiWeight".
 */
export interface UiWeight {
  device_t?: number | null;
  g: number;
  t: number;
  type?: "weight";
}
/**
 * The only shape an estimator call may produce.
 *
 * This interface was referenced by `BinBooksContracts`'s JSON-Schema
 * via the `definition` "ValueEstimate".
 */
export interface ValueEstimate {
  fmv: MoneyRange;
  /**
   * Lowercase label. Letters, digits, spaces and hyphens only.
   */
  label: string;
  material_mix?: {
    /**
     * This interface was referenced by `undefined`'s JSON-Schema definition
     * via the `patternProperty` "^[a-z0-9_]+$".
     */
    [k: string]: number;
  };
  model?: string;
  provider?: string;
  /**
   * @maxItems 8
   */
  regulatory_flags?:
    | []
    | [string]
    | [string, string]
    | [string, string, string]
    | [string, string, string, string]
    | [string, string, string, string, string]
    | [string, string, string, string, string, string]
    | [string, string, string, string, string, string, string]
    | [string, string, string, string, string, string, string, string];
  repair: MoneyRange;
  replacement: MoneyRange;
  scrap: MoneyRange;
}
/**
 * The only shape a vision call may produce. Nothing outside these fields is read.
 *
 * This interface was referenced by `BinBooksContracts`'s JSON-Schema
 * via the `definition` "VisionResult".
 */
export interface VisionResult {
  /**
   * @maxItems 5
   */
  candidates?:
    | []
    | [VisionCandidate]
    | [VisionCandidate, VisionCandidate]
    | [VisionCandidate, VisionCandidate, VisionCandidate]
    | [VisionCandidate, VisionCandidate, VisionCandidate, VisionCandidate]
    | [VisionCandidate, VisionCandidate, VisionCandidate, VisionCandidate, VisionCandidate];
  class: ItemClass;
  condition?: "working" | "broken" | "unknown";
  confidence: number;
  description?: string;
  /**
   * Lowercase label. Letters, digits, spaces and hyphens only.
   */
  label: string;
  material?: string | null;
  model?: string;
  provider?: string;
  visible_text?: string;
}
/**
 * This interface was referenced by `BinBooksContracts`'s JSON-Schema
 * via the `definition` "VoidResponse".
 */
export interface VoidResponse {
  event_id: number;
  reversing_entry_ids?: number[];
  status: EventStatus;
}
