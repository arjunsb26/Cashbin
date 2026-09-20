// Every wire type comes from the generated contract at /contracts/api-types.ts.
// Nothing here restates a backend field, so a schema change reaches the dashboard
// as a type error rather than as a wrong number on the screen.
//
// The shapes the screens make out of these live in lib/derive.ts. They are built
// by pure functions and are never sent or received.

export type {
  AskCandidate,
  AssetCreate,
  AssetListResponse,
  AssetRead,
  AssetStatus,
  BrandInfo,
  CloseCheck,
  CloseRead,
  CloseRequest,
  CorrectionCreate,
  CorrectionRead,
  CorrectionResponse,
  CropQuality,
  DeviceTareResponse,
  EstimateRef,
  EventDetail,
  EventKind,
  EventListResponse,
  EventStatus,
  EventSummary,
  HealthResponse,
  IdentificationRead,
  IdentifyMethod,
  ItemClass,
  ItemRecordRead,
  JournalBasis,
  JournalEntryRead,
  JournalLineRead,
  JournalResponse,
  OptionKind,
  OptionScoreRead,
  RoundListResponse,
  RoundRead,
  RuleRead,
  RulesResponse,
  SettingsRead,
  SettingsUpdate,
  SetupResponse,
  SummaryResponse,
  TaxMethod,
  TrialBalanceRow,
  VisionCandidate,
  VoidResponse,
} from "../../contracts/api-types";

import type {
  UiAskOpened,
  UiAskResolved,
  UiDeviceStatus,
  UiEventCreated,
  UiEventUpdated,
  UiJournalPosted,
  UiMetricsUpdated,
  UiWeight,
} from "../../contracts/api-types";

export type {
  UiAskOpened,
  UiAskResolved,
  UiDeviceStatus,
  UiEventCreated,
  UiEventUpdated,
  UiJournalPosted,
  UiMetricsUpdated,
  UiWeight,
};

/**
 * The topic field is optional in the generated types, because the backend gives it
 * a default. On the wire it is always there, and the reducer needs it to narrow,
 * so the union states it.
 */
type Tagged<T, K extends string> = Omit<T, "type"> & { type: K };

export type UiMessage =
  | Tagged<UiWeight, "weight">
  | Tagged<UiEventCreated, "event.created">
  | Tagged<UiEventUpdated, "event.updated">
  | Tagged<UiJournalPosted, "journal.posted">
  | Tagged<UiAskOpened, "ask.opened">
  | Tagged<UiAskResolved, "ask.resolved">
  | Tagged<UiMetricsUpdated, "metrics.updated">
  | Tagged<UiDeviceStatus, "device.status">;

/** Which device the status line is about. */
export type DeviceName = "bin" | "phone";
