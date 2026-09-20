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
 * Why a ticket landed in the review queue. Lane P, PLAN.md 21a item 39.
 *
 * This interface was referenced by `BinBooksContracts`'s JSON-Schema
 * via the `definition` "ReviewKind".
 */
export type ReviewKind =
  "donation" | "estimate_above_threshold" | "possible_unrecorded_asset" | "unresolved_ask" | "confident_overruled";
/**
 * This interface was referenced by `BinBooksContracts`'s JSON-Schema
 * via the `definition` "ReviewStatus".
 */
export type ReviewStatus = "open" | "approved" | "rejected";

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
  CategoryStat?: CategoryStat;
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
  Form4797Block?: Form4797Block;
  Form4797Row?: Form4797Row;
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
  ReconciliationBlock?: ReconciliationBlock;
  ReconciliationRow?: ReconciliationRow;
  ReviewDecision?: ReviewDecision;
  ReviewDecisionResponse?: ReviewDecisionResponse;
  ReviewItemRead?: ReviewItemRead;
  ReviewKind?: ReviewKind;
  ReviewListResponse?: ReviewListResponse;
  ReviewProposal?: ReviewProposal;
  ReviewRunResponse?: ReviewRunResponse;
  ReviewStatus?: ReviewStatus;
  RollforwardBlock?: RollforwardBlock;
  RollforwardRow?: RollforwardRow;
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
  StatsAverages?: StatsAverages;
  StatsBucket?: StatsBucket;
  StatsResponse?: StatsResponse;
  SummaryResponse?: SummaryResponse;
  TaxMethod?: TaxMethod;
  ToolStep?: ToolStep;
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
 * via the `definition` "CategoryStat".
 */
export interface CategoryStat {
  category: "food" | "packaging" | "equipment" | "e-waste" | "other";
  cents?: number;
  kg?: number;
  tosses?: number;
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
  form4797?: Form4797Block | null;
  id: number;
  investigation_md?: string | null;
  investigation_steps?: ToolStep[];
  memo_md?: string | null;
  period_end: string;
  period_start: string;
  reconciliation?: ReconciliationBlock | null;
  report?: {
    [k: string]: unknown;
  };
  rollforward?: RollforwardBlock | null;
  status: string;
  totals?: {
    [k: string]: unknown;
  };
}
/**
 * This interface was referenced by `BinBooksContracts`'s JSON-Schema
 * via the `definition` "Form4797Block".
 */
export interface Form4797Block {
  disclaimer?: string;
  part_ii_line_10_cents?: number;
  part_ii_rows?: Form4797Row[];
  part_iii_recapture_cents?: number;
  part_iii_rows?: Form4797Row[];
}
/**
 * This interface was referenced by `BinBooksContracts`'s JSON-Schema
 * via the `definition` "Form4797Row".
 */
export interface Form4797Row {
  cost_cents?: number;
  date_acquired?: string;
  date_disposed?: string;
  depreciation_allowed_cents?: number;
  description?: string;
  gain_or_loss_cents?: number;
  gross_proceeds_cents?: number;
  line?: string;
  part?: "II" | "III";
  recapture_note?: string;
  rule_ids?: string[];
}
/**
 * One lookup an agent made, and what it found. This is the working, shown.
 *
 * This interface was referenced by `BinBooksContracts`'s JSON-Schema
 * via the `definition` "ToolStep".
 */
export interface ToolStep {
  args_summary?: string;
  finding?: string;
  tool?: string;
}
/**
 * The M-1 shape: book loss, less the differences, equals the tax loss.
 *
 * This interface was referenced by `BinBooksContracts`'s JSON-Schema
 * via the `definition` "ReconciliationBlock".
 */
export interface ReconciliationBlock {
  book_loss_cents?: number;
  differences_cents?: number;
  rows?: ReconciliationRow[];
  tax_loss_cents?: number;
  ties?: boolean;
  title?: string;
}
/**
 * One disposed asset, book against tax, with the reason for the gap.
 *
 * This interface was referenced by `BinBooksContracts`'s JSON-Schema
 * via the `definition` "ReconciliationRow".
 */
export interface ReconciliationRow {
  asset_id?: number | null;
  book_loss_cents?: number;
  description?: string;
  difference_cents?: number;
  event_id: number;
  reason?: string;
  rule_ids?: string[];
  tag?: string;
  tax_loss_cents?: number;
}
/**
 * This interface was referenced by `BinBooksContracts`'s JSON-Schema
 * via the `definition` "RollforwardBlock".
 */
export interface RollforwardBlock {
  period_end?: string;
  period_start?: string;
  rows?: RollforwardRow[];
  ties?: boolean;
  total?: RollforwardRow;
}
/**
 * One asset's movement through the period, cost and accumulated depreciation.
 *
 * This interface was referenced by `BinBooksContracts`'s JSON-Schema
 * via the `definition` "RollforwardRow".
 */
export interface RollforwardRow {
  additions_cents?: number;
  asset_id?: number | null;
  closing_accum_cents?: number;
  closing_cost_cents?: number;
  closing_nbv_cents?: number;
  depreciation_cents?: number;
  description?: string;
  disposals_accum_cents?: number;
  disposals_cost_cents?: number;
  opening_accum_cents?: number;
  opening_cost_cents?: number;
  opening_nbv_cents?: number;
  tag?: string;
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
  sense_check?: {
    [k: string]: unknown;
  } | null;
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
  question?: string | null;
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
 * Who decided and why. Both fields are outside text, so both are cleaned.
 *
 * This interface was referenced by `BinBooksContracts`'s JSON-Schema
 * via the `definition` "ReviewDecision".
 */
export interface ReviewDecision {
  by?: string;
  note?: string;
}
/**
 * What the decision did: the item as it now stands, and what it moved.
 *
 * This interface was referenced by `BinBooksContracts`'s JSON-Schema
 * via the `definition` "ReviewDecisionResponse".
 */
export interface ReviewDecisionResponse {
  agreed_with_agent?: boolean | null;
  detail?: string;
  difference_cents?: number;
  item: ReviewItemRead;
  reversing_entry_ids?: number[];
}
/**
 * One open question, as the Review tab lists it.
 *
 * This interface was referenced by `BinBooksContracts`'s JSON-Schema
 * via the `definition` "ReviewItemRead".
 */
export interface ReviewItemRead {
  agreed_with_agent?: boolean | null;
  amount_cents?: number;
  asset_id?: number | null;
  asset_tag?: string | null;
  candidates?: AskCandidate[];
  created_at?: string;
  decided_at?: string | null;
  decided_by?: string | null;
  event_id: number;
  id: number;
  kind: ReviewKind;
  label?: string | null;
  note?: string | null;
  proposal?: ReviewProposal | null;
  reason?: string;
  status: ReviewStatus;
}
/**
 * What the review agent thinks, and how it got there. It never acts on this.
 *
 * This interface was referenced by `BinBooksContracts`'s JSON-Schema
 * via the `definition` "ReviewProposal".
 */
export interface ReviewProposal {
  decision?: "approve" | "reject" | "ask_person";
  downgraded_reason?: string | null;
  evidence?: string[];
  latency_ms?: number | null;
  model?: string;
  provider?: string;
  reason?: string;
  steps?: ToolStep[];
  tool_calls?: number;
}
/**
 * This interface was referenced by `BinBooksContracts`'s JSON-Schema
 * via the `definition` "ReviewListResponse".
 */
export interface ReviewListResponse {
  items?: ReviewItemRead[];
  open_count?: number;
}
/**
 * What one run of the review agent produced.
 *
 * This interface was referenced by `BinBooksContracts`'s JSON-Schema
 * via the `definition` "ReviewRunResponse".
 */
export interface ReviewRunResponse {
  items?: ReviewItemRead[];
  proposed?: number;
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
  speak_up_cents?: number;
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
  speak_up_cents?: number | null;
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
 * This interface was referenced by `BinBooksContracts`'s JSON-Schema
 * via the `definition` "StatsAverages".
 */
export interface StatsAverages {
  days?: number;
  kg_per_day?: number;
  tosses_per_day?: number;
  wasted_cents_per_day?: number;
}
/**
 * One day or one week of tickets, totalled.
 *
 * This interface was referenced by `BinBooksContracts`'s JSON-Schema
 * via the `definition` "StatsBucket".
 */
export interface StatsBucket {
  asks?: number;
  book_loss_cents?: number;
  by_category?: CategoryStat[];
  estimated_value_cents?: number;
  first_try_accuracy?: number | null;
  kg_co2e_avoided?: number;
  kg_landfill?: number;
  start: string;
  tosses?: number;
  wasted_cents?: number;
}
/**
 * What the bin saw over a range, by day or by week.
 *
 * This interface was referenced by `BinBooksContracts`'s JSON-Schema
 * via the `definition` "StatsResponse".
 */
export interface StatsResponse {
  averages?: StatsAverages;
  bucket?: "day" | "week";
  buckets?: StatsBucket[];
  period_end?: string;
  period_start?: string;
  suggestions?: string[];
  summary_md?: string | null;
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
  question?: string | null;
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
