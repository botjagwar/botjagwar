import type { ApiErrorBody, DashboardStatistic, DefinitionImpactRecord, DefinitionTranslationSettings, GemmaChatMessage, GemmaChatResponse, GemmaSettings, JsonDictionaryRecord, JsonDictionarySearchPage, JsonDictionarySearchResult, LanguageRecord, ManagedService, MaterializedViewRefreshResult, MaterializedViewRefreshStatus, OperationPage, OperationRecord, OperationService, PageCheckerAutomationSettings, PageCheckerMonitoringSettings, PageCheckJob, PageCheckJobSummary, PageCheckResult, PageCheckScoreSnapshot, PageCheckStatisticsPeriod, PageCheckStatisticsResponse, PageResult, ProcessedPageEntry, RelationDefinition, Row, SupervisorHostStatus, TranslationHealth, TranslationJob, WiktionaryPageSnapshot, WordRecord } from "./types";
import { defaultConfig, joinAddress, type AtlasConfig } from "./config";

let activeConfig: AtlasConfig = defaultConfig;
let linkableLexiconWordsPromise: Promise<ReadonlySet<string>> | null = null;
const lexiconPreviewPromises = new Map<string, Promise<JsonDictionaryRecord[]>>();
const DASHBOARD_STATISTICS_CACHE_MS = 300_000;
const DEFAULT_PAGE_CHECK_JOB_HISTORY_LIMIT = 2_500;
const DASHBOARD_STATISTICS_PATH = "atlas_dashboard_statistics_mv?select=period,period_start,period_end,entry_count,translated_languages,generated_at,missing_timestamp_count&order=period_start.desc";
let dashboardStatisticsCache: { statistics: DashboardStatistic[]; fetchedAt: number } | null = null;
let dashboardStatisticsPromise: Promise<DashboardStatistic[]> | null = null;

export class ApiResponseError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiResponseError";
    this.status = status;
  }
}

export class InvalidApiResponseError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "InvalidApiResponseError";
  }
}

export class MutationNotStartedError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "MutationNotStartedError";
  }
}

const TRANSLATION_JOB_STATUSES = new Set(["pending", "running", "done", "error"]);
const TRANSLATION_JOB_STAGES = new Set(["queued", "loading_source", "translating", "queueing_publication", "prefiltering_publication", "publication_queued", "publication_filtered", "completed", "failed"]);
const TRANSLATION_PUBLICATION_STATES = new Set(["not_queued", "queued", "filtered_out"]);

function parseTranslationJob(
  value: unknown,
  expected: { jobId: string; language: string; title?: string },
): TranslationJob {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new InvalidApiResponseError("Invalid translation job response.");
  }
  const job = value as Record<string, unknown>;
  const resultIsValid = job.result === null
    || (typeof job.result === "object" && !Array.isArray(job.result));
  if (
    typeof job.job_id !== "string" || !job.job_id
    || typeof job.language !== "string" || !job.language
    || typeof job.title !== "string" || !job.title
    || typeof job.status !== "string" || !TRANSLATION_JOB_STATUSES.has(job.status)
    || typeof job.stage !== "string" || !TRANSLATION_JOB_STAGES.has(job.stage)
    || typeof job.publication_state !== "string" || !TRANSLATION_PUBLICATION_STATES.has(job.publication_state)
    || typeof job.created_at !== "number" || !Number.isFinite(job.created_at)
    || typeof job.last_updated_at !== "number" || !Number.isFinite(job.last_updated_at)
    || !resultIsValid
    || (job.error !== null && typeof job.error !== "string")
    || typeof job.message !== "string"
    || job.job_id !== expected.jobId
    || job.language !== expected.language
    || (expected.title !== undefined && job.title !== expected.title)
  ) {
    throw new InvalidApiResponseError("Invalid translation job response.");
  }
  return job as unknown as TranslationJob;
}

export function configureApi(config: AtlasConfig): void {
  activeConfig = config;
  linkableLexiconWordsPromise = null;
  lexiconPreviewPromises.clear();
  dashboardStatisticsCache = null;
  dashboardStatisticsPromise = null;
}

function serviceAddresses(service: keyof Pick<AtlasConfig, "postgrestAddresses" | "dictionaryServiceAddresses" | "entryTranslatorAddresses">): string[] {
  if (!activeConfig) throw new Error("Tsy mbola voaray ny fikirakirana API an'i Atlas.");
  return activeConfig[service];
}

async function parseError(response: Response): Promise<ApiResponseError> {
  const fallback = `Hadisoana HTTP ${response.status}`;
  let payload: string;
  try {
    payload = await response.text();
  } catch {
    return new ApiResponseError(fallback, response.status);
  }
  if (!payload.trim()) return new ApiResponseError(fallback, response.status);
  try {
    const body = JSON.parse(payload) as ApiErrorBody;
    return new ApiResponseError(body.error_message ?? body.message ?? body.details ?? fallback, response.status);
  } catch {
    if (response.headers.get("content-type")?.startsWith("text/plain")) {
      return new ApiResponseError(payload.trim().slice(0, 500), response.status);
    }
    return new ApiResponseError(fallback, response.status);
  }
}

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init);
  if (!response.ok) {
    throw await parseError(response);
  }
  if (response.status === 204 || response.headers.get("content-length") === "0") {
    return undefined as T;
  }
  return (await response.json()) as T;
}

async function serviceRequest<T>(addresses: string[], path: string, init?: RequestInit): Promise<T> {
  let lastError: Error | null = null;
  const method = init?.method?.toUpperCase() ?? "GET";
  const candidates = method === "GET" || method === "HEAD" ? addresses : addresses.slice(0, 1);
  for (const address of candidates) {
    try {
      return await request<T>(joinAddress(address, path), init);
    } catch (caught) {
      if (init?.signal?.aborted) throw caught;
      lastError = caught instanceof Error ? caught : new Error("Tsy nahomby ny fangatahana tamin'ny tolotra.");
    }
  }
  throw lastError ?? new Error("Tsy misy adiresina tolotra voakirakira.");
}

const POSTGREST_RESERVED = /[,.:*()"\\]/;

function escapePostgrestValue(value: string): string {
  let escaped = value.replaceAll("\\", "\\\\").replaceAll('"', '\\"');
  if (POSTGREST_RESERVED.test(value)) {
    escaped = `"${escaped}"`;
  }
  return escaped;
}

function escapeLikePattern(value: string): string {
  return value.replaceAll("\\", "\\\\").replaceAll("%", "\\%").replaceAll("_", "\\_");
}

async function auditedMutation<T>(metadata: { service: OperationService; action: string; resource: string; target?: Row; changed_fields?: string[] }, operation: () => Promise<T>, isAmbiguous: (error: Error) => boolean = () => false): Promise<T> {
  let audit: OperationRecord;
  try {
    audit = await request<OperationRecord>("/api/operations/records", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Atlas-Operation-Audit": "1" },
      body: JSON.stringify({ ...metadata, target: metadata.target ?? {}, changed_fields: metadata.changed_fields ?? [] }),
    });
  } catch (caught) {
    const error = caught instanceof Error ? caught : new Error("Tsy azo natomboka ny firaketana ny asa Atlas.");
    throw new MutationNotStartedError(error.message);
  }
  let result: T;
  try {
    result = await operation();
  } catch (caught) {
    const error = caught instanceof Error ? caught : new Error("Tsy nahomby ny asa Atlas.");
    if (!isAmbiguous(error)) {
      try {
        await request<OperationRecord>(`/api/operations/records/${audit.id}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json", "X-Atlas-Operation-Audit": "1" },
          body: JSON.stringify({ outcome: "failed", error_summary: error.message }),
        });
      } catch {
        // A pending record preserves evidence when completion cannot be written.
      }
    }
    throw error;
  }
  try {
    await request<OperationRecord>(`/api/operations/records/${audit.id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json", "X-Atlas-Operation-Audit": "1" },
      body: JSON.stringify({ outcome: "succeeded" }),
    });
  } catch {
    // The pending record still proves the mutation was initiated.
  }
  return result;
}

function selectedFields(relation: RelationDefinition): string {
  const visibleFields = relation.fields?.filter((field) => !field.hiddenFromList).map((field) => field.name);
  return visibleFields?.length ? visibleFields.join(",") : "*";
}

export function buildRelationUrl(
  relation: RelationDefinition,
  options: { page?: number; pageSize?: number; search?: string; order?: string } = {},
  address = serviceAddresses("postgrestAddresses")[0],
): string {
  const page = options.page ?? 0;
  const pageSize = options.pageSize ?? 25;
  const params = new URLSearchParams({
    select: selectedFields(relation),
    limit: String(pageSize),
    offset: String(page * pageSize),
  });
  if (options.order ?? relation.defaultOrder) {
    params.set("order", options.order ?? relation.defaultOrder ?? "");
  }
  if (options.search && relation.searchFields?.length) {
    const safeSearch = options.search.replaceAll("*", "").trim();
    if (safeSearch) {
      const pattern = escapePostgrestValue(escapeLikePattern(safeSearch));
      params.set("or", `(${relation.searchFields.map((field) => `${field}.ilike.*${pattern}*`).join(",")})`);
    }
  }
  return `${joinAddress(address, relation.name)}?${params.toString()}`;
}

export async function listRows(
  relation: RelationDefinition,
  options: { page: number; pageSize: number; search: string; order?: string },
  signal?: AbortSignal,
): Promise<PageResult> {
  let lastError: Error | null = null;
  for (const address of serviceAddresses("postgrestAddresses")) {
    try {
      const response = await fetch(buildRelationUrl(relation, options, address), {
        headers: { Prefer: "count=exact" },
        signal,
      });
      if (!response.ok) throw await parseError(response);
      const rows = (await response.json()) as Row[];
      const range = response.headers.get("content-range");
      const totalPart = range?.split("/")[1];
      return { rows, total: totalPart && totalPart !== "*" ? Number(totalPart) : null };
    } catch (caught) {
      if (signal?.aborted) throw caught;
      lastError = caught instanceof Error ? caught : new Error("Tsy nahomby ny fangatahana PostgREST.");
    }
  }
  throw lastError ?? new Error("Tsy misy adiresy PostgREST voakirakira.");
}

function identityQuery(relation: RelationDefinition, row: Row): string {
  if (!relation.identity?.length) {
    throw new Error(`Tsy manana mari-panondro andalana marin-toerana ny ${relation.label}.`);
  }
  const params = new URLSearchParams();
  for (const field of relation.identity) {
    const value = row[field];
    if (value === undefined || value === null) {
      throw new Error(`Tsy fantatra ity andalana ity satria tsy misy sanda ny ${field}.`);
    }
    params.set(field, `eq.${escapePostgrestValue(String(value))}`);
  }
  return params.toString();
}

export async function createRow(relation: RelationDefinition, row: Row): Promise<Row[]> {
  return auditedMutation({ service: "database", action: "create", resource: relation.name, changed_fields: Object.keys(row) }, () => serviceRequest<Row[]>(serviceAddresses("postgrestAddresses"), relation.name, {
    method: "POST",
    headers: { "Content-Type": "application/json", Prefer: "return=representation" },
    body: JSON.stringify(row),
  }));
}

export async function updateRow(relation: RelationDefinition, original: Row, row: Row): Promise<Row[]> {
  return auditedMutation({ service: "database", action: "update", resource: relation.name, target: Object.fromEntries((relation.identity ?? []).map((field) => [field, original[field]])), changed_fields: Object.keys(row) }, () => serviceRequest<Row[]>(serviceAddresses("postgrestAddresses"), `${relation.name}?${identityQuery(relation, original)}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", Prefer: "return=representation" },
    body: JSON.stringify(row),
  }));
}

export async function deleteRow(relation: RelationDefinition, row: Row): Promise<void> {
  await auditedMutation({ service: "database", action: "delete", resource: relation.name, target: Object.fromEntries((relation.identity ?? []).map((field) => [field, row[field]])) }, () => serviceRequest<void>(serviceAddresses("postgrestAddresses"), `${relation.name}?${identityQuery(relation, row)}`, { method: "DELETE" }));
}

export async function getDatabaseStats(signal?: AbortSignal): Promise<Row[]> {
  return serviceRequest<Row[]>(serviceAddresses("postgrestAddresses"), "db_stats?select=*&order=total_bytes.desc&limit=8", { signal });
}

export function getDashboardStatistics(): Promise<DashboardStatistic[]> {
  const now = Date.now();
  if (dashboardStatisticsCache && now - dashboardStatisticsCache.fetchedAt < DASHBOARD_STATISTICS_CACHE_MS) {
    return Promise.resolve(dashboardStatisticsCache.statistics);
  }
  if (!dashboardStatisticsPromise) {
    dashboardStatisticsPromise = serviceRequest<DashboardStatistic[]>(serviceAddresses("postgrestAddresses"), DASHBOARD_STATISTICS_PATH)
      .then((statistics) => {
        dashboardStatisticsCache = { statistics, fetchedAt: Date.now() };
        return statistics;
      })
      .finally(() => {
        dashboardStatisticsPromise = null;
      });
  }
  return dashboardStatisticsPromise;
}

export function buildJsonDictionaryWordPath(word: string): string {
  const params = new URLSearchParams({
    select: "type,id,word,language,part_of_speech,last_modified,definitions,additional_data",
    word: `eq.${escapePostgrestValue(word)}`,
    order: "language.asc,part_of_speech.asc,id.asc",
  });
  return `json_dictionary?${params.toString()}`;
}

export async function getJsonDictionaryWord(word: string, signal?: AbortSignal): Promise<JsonDictionaryRecord[]> {
  return serviceRequest<JsonDictionaryRecord[]>(serviceAddresses("postgrestAddresses"), buildJsonDictionaryWordPath(word), { signal });
}

/** Load the Malagasy headwords used for automatic definition links once per API configuration. */
export function getLinkableLexiconWords(): Promise<ReadonlySet<string>> {
  if (!linkableLexiconWordsPromise) {
    linkableLexiconWordsPromise = serviceRequest<Array<{ word: string }>>(
      serviceAddresses("postgrestAddresses"),
      "rpc/linkable_lexicon_headwords",
    )
      .then((rows) => new Set(rows.map((row) => row.word)))
      .catch((error: unknown) => {
        linkableLexiconWordsPromise = null;
        throw error;
      });
  }
  return linkableLexiconWordsPromise;
}

/** Load and cache exact-headword records used by definition link previews. */
export function getLexiconWordPreview(word: string): Promise<JsonDictionaryRecord[]> {
  const key = word.toLocaleLowerCase();
  let preview = lexiconPreviewPromises.get(key);
  if (!preview) {
    preview = getJsonDictionaryWord(word).catch((error: unknown) => {
      lexiconPreviewPromises.delete(key);
      throw error;
    });
    lexiconPreviewPromises.set(key, preview);
  }
  return preview;
}

export function buildJsonDictionarySearchPath(query: string, page: number, pageSize = 20): string {
  const params = new URLSearchParams({
    p_query: query,
    p_limit: String(pageSize + 1),
    p_offset: String(page * pageSize),
  });
  return `rpc/search_json_dictionary?${params.toString()}`;
}

export async function searchJsonDictionary(query: string, page: number, pageSize = 20, signal?: AbortSignal): Promise<JsonDictionarySearchPage> {
  const rows = await serviceRequest<JsonDictionarySearchResult[]>(serviceAddresses("postgrestAddresses"), buildJsonDictionarySearchPath(query, page, pageSize), { signal });
  return { rows: rows.slice(0, pageSize), hasMore: rows.length > pageSize };
}

export async function getLanguages(signal?: AbortSignal): Promise<LanguageRecord[]> {
  return serviceRequest<LanguageRecord[]>(serviceAddresses("postgrestAddresses"), "language?select=iso_code,english_name,malagasy_name&order=iso_code.asc", { signal });
}

export async function getJsonDictionaryRefreshStatus(signal?: AbortSignal): Promise<MaterializedViewRefreshStatus | null> {
  const rows = await serviceRequest<MaterializedViewRefreshStatus[]>(serviceAddresses("postgrestAddresses"), "materialized_view_refresh_status?schema_name=eq.public&view_name=eq.json_dictionary&select=*&limit=1", { signal });
  return rows[0] ?? null;
}

export async function refreshMaterializedViews(): Promise<MaterializedViewRefreshResult> {
  return request<MaterializedViewRefreshResult>("/api/maintenance/materialized-views/refresh", {
    method: "POST",
    headers: { "X-Atlas-Maintenance": "1" },
  });
}

export async function getManagedServices(signal?: AbortSignal): Promise<{ hosts: SupervisorHostStatus[] }> {
  return request<{ hosts: SupervisorHostStatus[] }>("/api/services/hosts", { signal });
}

export async function changeManagedService(hostId: string, serviceId: string, action: "start" | "stop"): Promise<ManagedService> {
  return request<ManagedService>(
    `/api/services/hosts/${encodeURIComponent(hostId)}/services/${encodeURIComponent(serviceId)}/${action}`,
    { method: "POST", headers: { "X-Atlas-Service-Control": "1" } },
  );
}

export async function sendGemmaChat(messages: GemmaChatMessage[], signal?: AbortSignal): Promise<GemmaChatResponse> {
  const response = await request<GemmaChatResponse>("/api/gemma/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-Atlas-Gemma": "1" },
    body: JSON.stringify({ messages }),
    signal,
  });
  if (
    !response || typeof response.model !== "string" || !response.model
    || response.message?.role !== "assistant"
    || typeof response.message.content !== "string" || !response.message.content.trim()
  ) {
    throw new InvalidApiResponseError("Invalid Gemma chat response.");
  }
  return response;
}

function requireGemmaSettings(value: unknown): asserts value is GemmaSettings {
  if (
    !value || typeof value !== "object"
    || typeof (value as Record<string, unknown>).api_url !== "string"
    || !(value as Record<string, unknown>).api_url
    || typeof (value as Record<string, unknown>).model !== "string"
    || !(value as Record<string, unknown>).model
  ) {
    throw new InvalidApiResponseError("Invalid Gemma settings response.");
  }
}

export async function getGemmaSettings(signal?: AbortSignal): Promise<GemmaSettings> {
  const settings = await request<unknown>("/api/gemma/settings", { signal });
  requireGemmaSettings(settings);
  return settings;
}

export async function updateGemmaSettings(apiUrl: string): Promise<GemmaSettings> {
  const settings = await request<unknown>("/api/gemma/settings", {
    method: "PUT",
    headers: { "Content-Type": "application/json", "X-Atlas-Gemma": "1" },
    body: JSON.stringify({ api_url: apiUrl }),
  });
  requireGemmaSettings(settings);
  return settings;
}

export async function getWord(language: string, word: string): Promise<WordRecord[]> {
  return serviceRequest<WordRecord[]>(serviceAddresses("dictionaryServiceAddresses"), `entry/${encodeURIComponent(language)}/${encodeURIComponent(word)}`);
}

export async function getDefinitionImpact(definitionId: number, signal?: AbortSignal): Promise<DefinitionImpactRecord | null> {
  const definitions = await serviceRequest<DefinitionImpactRecord[]>(serviceAddresses("dictionaryServiceAddresses"), `definition_words/${encodeURIComponent(String(definitionId))}`, { signal });
  return definitions[0] ?? null;
}

export async function createWord(payload: Omit<WordRecord, "id">): Promise<WordRecord> {
  return auditedMutation({ service: "dictionary", action: "create", resource: "entry", target: { language: payload.language, word: payload.word }, changed_fields: ["word", "language", "part_of_speech", "definitions"] }, () => serviceRequest<WordRecord>(serviceAddresses("dictionaryServiceAddresses"), `entry/${encodeURIComponent(payload.language)}/create`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      word: payload.word,
      part_of_speech: payload.part_of_speech,
      definitions: payload.definitions.map((definition) => ({
        definition: definition.definition,
        definition_language: definition.definition_language ?? definition.language,
      })),
    }),
  }));
}

export async function updateWord(word: WordRecord): Promise<WordRecord> {
  return auditedMutation({ service: "dictionary", action: "update", resource: "entry", target: { id: word.id, language: word.language, word: word.word }, changed_fields: ["part_of_speech", "definitions"] }, () => serviceRequest<WordRecord>(serviceAddresses("dictionaryServiceAddresses"), `entry/${word.id}/edit`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      part_of_speech: word.part_of_speech,
      definitions: word.definitions.map((definition) => ({
        id: definition.id,
        definition: definition.definition,
        definition_language: definition.definition_language ?? definition.language,
      })),
    }),
  }));
}

export async function deleteWord(id: number): Promise<void> {
  await auditedMutation({ service: "dictionary", action: "delete", resource: "entry", target: { id } }, () => serviceRequest<void>(serviceAddresses("dictionaryServiceAddresses"), `entry/${id}/delete`, { method: "DELETE" }));
}

export async function getTranslatorHealth(signal?: AbortSignal): Promise<TranslationHealth> {
  return serviceRequest<TranslationHealth>(serviceAddresses("entryTranslatorAddresses"), "health", { signal });
}

export async function getTranslatorErrors(): Promise<{ errors: Row[] }> {
  return serviceRequest<{ errors: Row[] }>(serviceAddresses("entryTranslatorAddresses"), "jobs/errors");
}

export async function previewPage(language: string, title: string): Promise<ProcessedPageEntry[]> {
  return serviceRequest<ProcessedPageEntry[]>(serviceAddresses("entryTranslatorAddresses"), `wiktionary-pages/${encodeURIComponent(language)}/${encodeURIComponent(title)}`);
}

export async function previewTranslations(language: string, title: string): Promise<Row[]> {
  return serviceRequest<Row[]>(serviceAddresses("entryTranslatorAddresses"), `wiktionary-pages/${encodeURIComponent(language)}/${encodeURIComponent(title)}/translations`);
}

export async function getPageSnapshot(language: string, title: string, signal?: AbortSignal): Promise<WiktionaryPageSnapshot> {
  const params = new URLSearchParams({ title });
  return serviceRequest<WiktionaryPageSnapshot>(serviceAddresses("entryTranslatorAddresses"), `wiktionary-page-snapshots/${encodeURIComponent(language)}?${params.toString()}`, { cache: "no-store", signal });
}

export async function startTranslationJob(language: string, title: string, requestId: string = crypto.randomUUID()): Promise<TranslationJob> {
  return auditedMutation({ service: "translator", action: "queue", resource: "wiktionary-page", target: { language, title, request_id: requestId } }, async () => parseTranslationJob(await serviceRequest<unknown>(serviceAddresses("entryTranslatorAddresses"), `wiktionary-pages/${encodeURIComponent(language)}/jobs`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title, request_id: requestId }),
    }), { jobId: requestId, language, title }), (error) => !(error instanceof ApiResponseError));
}

export async function getTranslationJob(language: string, jobId: string, signal?: AbortSignal): Promise<TranslationJob> {
  const job = await serviceRequest<unknown>(serviceAddresses("entryTranslatorAddresses"), `wiktionary-pages/${encodeURIComponent(language)}/jobs/${encodeURIComponent(jobId)}`, {
    cache: "no-store",
    signal,
  });
  return parseTranslationJob(job, { jobId, language });
}

export async function checkPages(language: string, titles: string[]): Promise<PageCheckResult[]> {
  const results = await auditedMutation({ service: "translator", action: "check", resource: "wiktionary-page", target: { language, titles } }, () => serviceRequest<{ results: PageCheckResult[] }>(serviceAddresses("entryTranslatorAddresses"), `wiktionary-pages/${encodeURIComponent(language)}/check`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ titles }),
  }));
  return results.results;
}

export async function startPageCheck(language: string, titles: string[]): Promise<PageCheckJob[]> {
  const page = await auditedMutation({ service: "translator", action: "check", resource: "wiktionary-page", target: { language, titles } }, () => serviceRequest<{ jobs: PageCheckJob[] }>(serviceAddresses("entryTranslatorAddresses"), `wiktionary-pages/${encodeURIComponent(language)}/check-jobs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ titles }),
  }));
  return page.jobs;
}

export async function getPageCheckJob(language: string, jobId: string): Promise<PageCheckJob> {
  return serviceRequest<PageCheckJob>(serviceAddresses("entryTranslatorAddresses"), `wiktionary-pages/${encodeURIComponent(language)}/check-jobs/${encodeURIComponent(jobId)}`);
}

export async function listPageCheckJobs(language: string, signal?: AbortSignal): Promise<PageCheckJobSummary[]> {
  const page = await serviceRequest<{ jobs: PageCheckJobSummary[] }>(serviceAddresses("entryTranslatorAddresses"), `wiktionary-pages/${encodeURIComponent(language)}/check-jobs?limit=100000`, { signal });
  return page.jobs;
}

export async function getPageCheckStatistics(language: string, signal?: AbortSignal): Promise<PageCheckStatisticsResponse> {
  return serviceRequest<PageCheckStatisticsResponse>(serviceAddresses("entryTranslatorAddresses"), `wiktionary-pages/${encodeURIComponent(language)}/check-jobs/statistics`, { signal });
}

export async function getPageCheckScoreHistory(language: string, period: PageCheckStatisticsPeriod, signal?: AbortSignal): Promise<PageCheckScoreSnapshot[]> {
  const params = new URLSearchParams({
    p_language: language,
    p_period: period,
    p_max_points: "480",
  });
  return serviceRequest<PageCheckScoreSnapshot[]>(serviceAddresses("postgrestAddresses"), `rpc/page_check_score_history?${params.toString()}`, { signal });
}

export async function getPageCheckerSettings(signal?: AbortSignal): Promise<PageCheckerAutomationSettings> {
  const settings = await serviceRequest<unknown>(serviceAddresses("entryTranslatorAddresses"), "page-checker/settings", { signal });
  return parsePageCheckerSettings(settings);
}

export async function updatePageCheckerSettings(settings: PageCheckerMonitoringSettings): Promise<PageCheckerMonitoringSettings> {
  return auditedMutation({
    service: "translator",
    action: "configure",
    resource: "page-checker-settings",
    changed_fields: ["watched_users", "check_probability", "cooldown_seconds", "ignored_edit_summaries"],
  }, () => serviceRequest<PageCheckerMonitoringSettings>(serviceAddresses("entryTranslatorAddresses"), "page-checker/settings", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(settings),
  }));
}

export async function updatePageCheckerAutonomousAgent(enabled: boolean): Promise<{ autonomous_agent_enabled: boolean }> {
  return auditedMutation({
    service: "translator",
    action: "configure",
    resource: "page-checker-settings",
    changed_fields: ["autonomous_agent_enabled"],
  }, async () => {
    const result = await serviceRequest<{ autonomous_agent_enabled: boolean }>(serviceAddresses("entryTranslatorAddresses"), "page-checker/settings/autonomous-agent", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ enabled }),
    });
    requireAutonomousAgentFlag(result);
    return result;
  });
}

export async function updateTranslationPrefilter(enabled: boolean): Promise<{ translation_prefilter_enabled: boolean }> {
  return auditedMutation({
    service: "translator",
    action: "configure",
    resource: "page-checker-settings",
    changed_fields: ["translation_prefilter_enabled"],
  }, async () => {
    const result = await serviceRequest<{ translation_prefilter_enabled: boolean }>(serviceAddresses("entryTranslatorAddresses"), "page-checker/settings/translation-prefilter", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ enabled }),
    });
    if (typeof result?.translation_prefilter_enabled !== "boolean") {
      throw new Error("Page-checker settings response has an invalid translation-prefilter flag.");
    }
    return result;
  });
}

export async function updatePageCheckJobHistoryLimit(limit: number): Promise<{ job_history_limit: number }> {
  return auditedMutation({
    service: "translator",
    action: "configure",
    resource: "page-checker-settings",
    changed_fields: ["job_history_limit"],
  }, () => serviceRequest<{ job_history_limit: number }>(serviceAddresses("entryTranslatorAddresses"), "page-checker/settings/job-history", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ limit }),
  }));
}

function parsePageCheckerSettings(value: unknown): PageCheckerAutomationSettings {
  const historyLimit = value && typeof value === "object"
    ? (value as Record<string, unknown>).job_history_limit
    : undefined;
  const translationPrefilter = value && typeof value === "object"
    ? (value as Record<string, unknown>).translation_prefilter_enabled
    : undefined;
  if (
    typeof value !== "object"
    || value === null
    || typeof (value as Record<string, unknown>).autonomous_agent_enabled !== "boolean"
    || (translationPrefilter !== undefined && typeof translationPrefilter !== "boolean")
    || (historyLimit !== undefined && (
      !Number.isInteger(historyLimit)
      || Number(historyLimit) < 1
      || Number(historyLimit) > 100_000
    ))
  ) {
    throw new Error("Page-checker settings response is invalid.");
  }
  return {
    ...(value as PageCheckerAutomationSettings),
    job_history_limit: historyLimit === undefined
      ? DEFAULT_PAGE_CHECK_JOB_HISTORY_LIMIT
      : Number(historyLimit),
    translation_prefilter_enabled: translationPrefilter === undefined
      ? false
      : translationPrefilter,
  };
}

function requireAutonomousAgentFlag(value: unknown): asserts value is { autonomous_agent_enabled: boolean } {
  if (typeof value !== "object" || value === null || typeof (value as Record<string, unknown>).autonomous_agent_enabled !== "boolean") {
    throw new Error("Page-checker settings response has an invalid autonomous-agent flag.");
  }
}

export async function getDefinitionTranslationSettings(signal?: AbortSignal): Promise<DefinitionTranslationSettings> {
  const settings = await serviceRequest<DefinitionTranslationSettings>(serviceAddresses("entryTranslatorAddresses"), "definition-translation/settings", { signal });
  requireDefinitionTranslationSettings(settings);
  return settings;
}

export async function updateDefinitionTranslationSettings(settings: DefinitionTranslationSettings): Promise<DefinitionTranslationSettings> {
  return auditedMutation({
    service: "translator",
    action: "configure",
    resource: "definition-translation-settings",
    changed_fields: ["basic_english_gate_enabled", "nllb_roundtrip_validation_enabled"],
  }, async () => {
    const updatedSettings = await serviceRequest<DefinitionTranslationSettings>(serviceAddresses("entryTranslatorAddresses"), "definition-translation/settings", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(settings),
    });
    requireDefinitionTranslationSettings(updatedSettings);
    return updatedSettings;
  });
}

function requireDefinitionTranslationSettings(value: unknown): asserts value is DefinitionTranslationSettings {
  if (
    typeof value !== "object"
    || value === null
    || typeof (value as Record<string, unknown>).basic_english_gate_enabled !== "boolean"
    || typeof (value as Record<string, unknown>).nllb_roundtrip_validation_enabled !== "boolean"
  ) {
    throw new Error("Definition-translation settings response is invalid.");
  }
}

export async function getOperations(options: { before?: number; service?: OperationService | ""; outcome?: string } = {}, signal?: AbortSignal): Promise<OperationPage> {
  const params = new URLSearchParams({ limit: "30" });
  if (options.before) params.set("before", String(options.before));
  if (options.service) params.set("service", options.service);
  if (options.outcome) params.set("outcome", options.outcome);
  return request<OperationPage>(`/api/operations/records?${params.toString()}`, { signal });
}
