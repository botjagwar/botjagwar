export type JsonValue = string | number | boolean | null | JsonValue[] | { [key: string]: JsonValue };
export type Row = Record<string, JsonValue | undefined>;

export type FieldKind = "text" | "textarea" | "number" | "datetime" | "date" | "select" | "json";

export interface FieldDefinition {
  name: string;
  label?: string;
  kind?: FieldKind;
  required?: boolean;
  readOnly?: boolean;
  hiddenFromList?: boolean;
  options?: string[];
  placeholder?: string;
}

export type RelationKind = "table" | "view" | "materialized-view";

export interface BilingualMessage {
  malagasy: string;
  english: string;
}

export interface RelationDefinition {
  name: string;
  label: string;
  group: string;
  kind: RelationKind;
  description: string;
  fields?: FieldDefinition[];
  identity?: string[];
  searchFields?: string[];
  defaultOrder?: string;
  readOnly?: boolean;
}

export type BilingualRelationDefinition = Omit<RelationDefinition, "label" | "group" | "description"> & {
  label: BilingualMessage;
  group: BilingualMessage;
  description: BilingualMessage;
};

export interface RelationCatalog {
  tableRelations: RelationDefinition[];
  viewRelations: RelationDefinition[];
  relations: RelationDefinition[];
  relationByName: Map<string, RelationDefinition>;
}

export interface PageResult {
  rows: Row[];
  total: number | null;
}

export interface ApiErrorBody {
  message?: string;
  details?: string;
  hint?: string;
  error_message?: string;
}

export interface GemmaChatMessage {
  role: "user" | "assistant";
  content: string;
}

export interface GemmaChatResponse {
  model: string;
  message: GemmaChatMessage & { role: "assistant" };
}

export interface GemmaSettings {
  api_url: string;
  model: string;
}

export interface DefinitionRecord {
  type?: string;
  id: number;
  definition: string;
  language?: string;
  definition_language?: string;
  last_modified?: string;
}

export interface DefinitionImpactRecord extends DefinitionRecord {
  words: Array<Omit<WordRecord, "definitions">>;
}

export interface WordRecord {
  type?: string;
  id: number;
  word: string;
  language: string;
  part_of_speech: string;
  definitions: DefinitionRecord[];
  additional_data?: Record<string, string[]>;
  last_modified?: string;
}

export interface JsonDictionaryAdditionalData {
  type?: string;
  data_type: string;
  data: string;
}

export interface JsonDictionaryRecord {
  type?: string;
  id: number;
  word: string;
  language: string;
  part_of_speech: string;
  last_modified?: string | null;
  definitions: DefinitionRecord[];
  additional_data: JsonDictionaryAdditionalData[] | null;
}

export type JsonDictionaryMatchField = "word" | "language" | "definitions" | "additional_data";

export interface JsonDictionarySearchResult {
  word: string;
  language: string;
  part_of_speech: string;
  definition_preview: string | null;
  match_field: JsonDictionaryMatchField;
  rank: number;
}

export interface JsonDictionarySearchPage {
  rows: JsonDictionarySearchResult[];
  hasMore: boolean;
}

export interface LanguageRecord {
  iso_code: string;
  english_name: string | null;
  malagasy_name: string | null;
}

export interface MaterializedViewRefreshStatus {
  schema_name: string;
  view_name: string;
  refreshed_at: string;
}

export interface MaterializedViewRefreshResult {
  refreshed_views: number;
  completed_at: string;
}

export type DashboardPeriod = "last_day" | "last_7_days" | "last_week" | "last_month" | "year_to_date" | "last_year";

export interface TranslatedLanguageStatistic {
  language: string;
  english_name: string | null;
  malagasy_name: string | null;
  translated_entries: number;
}

export interface DashboardStatistic {
  period: DashboardPeriod;
  period_start: string;
  period_end: string;
  entry_count: number;
  translated_languages: TranslatedLanguageStatistic[];
  generated_at: string;
  missing_timestamp_count: number;
}

export interface TranslationHealth {
  status?: string;
  message?: string;
  jobs?: number;
  counter_source?: string;
  average_job_duration_seconds?: number | null;
  recent_job_error_count?: number;
  recent_job_errors?: JsonValue[];
  running_jobs?: number;
  process_running_jobs?: number;
  process_admitted_jobs?: number;
  queued_jobs?: number;
  process_queued_jobs?: number;
  process_job_capacity?: number;
  available_slots?: number;
  available_job_slots?: number;
  max_async_workers?: number;
  accepting_async_jobs?: boolean;
  completed_job_count?: number;
  failed_job_count?: number;
  rejected_job_count?: number;
  completed_jobs?: number;
  failed_jobs?: number;
  rejected_jobs?: number;
  [key: string]: JsonValue | undefined;
}

export type TranslationJobStatus = "pending" | "running" | "done" | "error";
export type TranslationJobStage = "queued" | "loading_source" | "translating" | "queueing_publication" | "prefiltering_publication" | "publication_queued" | "publication_filtered" | "completed" | "failed";
export type TranslationPublicationState = "not_queued" | "queued" | "filtered_out";

export interface TranslationJob {
  job_id: string;
  language: string;
  title: string;
  status: TranslationJobStatus;
  stage: TranslationJobStage;
  publication_state: TranslationPublicationState;
  created_at: number;
  last_updated_at: number;
  result: Record<string, JsonValue> | null;
  error: string | null;
  message: string;
}

export interface DescendantNode {
  lang_code: string;
  lang: string;
  word?: string;
  roman?: string;
  tags?: string[];
  raw_tags?: string[];
  ruby?: Array<[string, string]>;
  sense?: string;
  descendants?: DescendantNode[];
}

export interface ProcessedPageEntry {
  entry?: string;
  language?: string;
  part_of_speech?: string;
  definitions?: string[];
  translations?: Array<{
    word?: string;
    language?: string;
    part_of_speech?: string;
    definition?: string;
    [key: string]: JsonValue | undefined;
  }>;
  additional_data?: Record<string, JsonValue>;
  descendants?: DescendantNode[];
}

export interface WiktionaryPageSnapshot {
  language: string;
  title: string;
  namespace: number | null;
  content: string;
  content_sha256: string;
  entries: ProcessedPageEntry[];
  parsed: boolean;
  parse_error: string | null;
  content_trust: "untrusted_wiktionary_content";
}

export interface PageCheckerAutomationSettings {
  watched_users: string[];
  check_probability: number;
  cooldown_seconds: number;
  ignored_edit_summaries: string[];
  job_history_limit: number;
  autonomous_agent_enabled: boolean;
  translation_prefilter_enabled: boolean;
}

export type PageCheckerMonitoringSettings = Omit<PageCheckerAutomationSettings, "autonomous_agent_enabled" | "job_history_limit" | "translation_prefilter_enabled">;

export interface DefinitionTranslationSettings {
  basic_english_gate_enabled: boolean;
  nllb_roundtrip_validation_enabled: boolean;
}

export interface PageCheckResultCounts {
  good: number;
  fixed: number;
  unverifiable: number;
  error: number;
}

export type PageCheckStatisticsPeriod = "today" | "last_7_days" | "current_week" | "current_month" | "last_3_months" | "last_6_months";
export type PageCheckGrade = "A" | "B" | "C" | "D" | "E" | null;

export interface PageCheckPeriodStatistics {
  period: PageCheckStatisticsPeriod;
  period_start: number;
  period_end: number;
  job_count: number;
  checked_count: number;
  assessable_count: number;
  result_counts: PageCheckResultCounts;
  good_percentage: number | null;
  grade: PageCheckGrade;
}

export interface PageCheckStatisticsResponse {
  language: string;
  generated_at: number;
  timezone: "UTC";
  retention_limit: number;
  retained_job_count: number;
  statistics: PageCheckPeriodStatistics[];
}

export interface PageCheckScoreSnapshot {
  snapshot_at: string;
  generated_at: string;
  good_percentage: number | null;
  assessable_count: number;
  retained_job_count: number;
  retention_limit: number;
}

export interface PageCheckIssue {
  type: string;
  description: string;
}

export interface PageCheckResult {
  word: string;
  status: "good" | "fixed" | "unverifiable" | "error";
  message: string;
  source_language: string | null;
  source_title: string | null;
  issues: PageCheckIssue[];
  mg_entry: { entry?: string; sections?: Array<{ part_of_speech: string; definitions: string[] }> } | null;
  fixed_entry: { entry: string; part_of_speech: string; definitions: string[]; examples: string[] } | null;
}

export interface PageCheckTimelineEvent {
  timestamp: number;
  stage: string;
  message: string;
}

export interface PageCheckJob {
  job_id: string;
  language: string;
  titles: string[];
  status: "pending" | "running" | "done" | "error";
  created_at: number;
  last_updated_at: number;
  attempts: number;
  progress: number;
  results: PageCheckResult[] | null;
  error: string | null;
  stage?: string;
  message?: string;
  timeline?: PageCheckTimelineEvent[];
  review_queue_state?: PageCheckReviewQueueState;
  review_event_id?: string | null;
  review_queue_error?: string | null;
}

export type PageCheckReviewQueueState = "not_needed" | "disabled" | "invalid" | "pending" | "publishing" | "queued" | "failed";

export interface PageCheckJobSummary {
  job_id: string;
  language: string;
  titles: string[];
  status: "pending" | "running" | "done" | "error";
  created_at: number;
  last_updated_at: number;
  attempts: number;
  progress: number;
  error: string | null;
  stage?: string;
  message?: string;
  queue_position?: number | null;
  result_counts: PageCheckResultCounts;
  review_queue_state?: PageCheckReviewQueueState;
  review_event_id?: string | null;
  review_queue_error?: string | null;
}

export interface ManagedService {
  id: string;
  host_id: string;
  state: string;
  running: boolean;
  description: string;
  pid: number;
  uptime_seconds: number;
}

export interface SupervisorHostStatus {
  id: string;
  label: string;
  available: boolean;
  services: ManagedService[];
}

export type OperationService = "database" | "dictionary" | "gemma" | "translator" | "supervisor";
export type OperationOutcome = "pending" | "succeeded" | "failed";

export interface OperationRecord {
  id: number;
  accepted_at: string;
  completed_at: string | null;
  username: string;
  service: OperationService;
  action: string;
  resource: string;
  target: Record<string, JsonValue>;
  changed_fields: string[];
  outcome: OperationOutcome;
  error_summary: string | null;
}

export interface OperationPage {
  operations: OperationRecord[];
  next_before: number | null;
}
