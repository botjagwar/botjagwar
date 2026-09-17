import { afterEach, describe, expect, it, vi } from "vitest";

import { buildJsonDictionarySearchPath, buildJsonDictionaryWordPath, buildRelationUrl, changeManagedService, checkPages, configureApi, createRow, getDashboardStatistics, getDefinitionImpact, getDefinitionTranslationSettings, getGemmaSettings, getLexiconWordPreview, getLinkableLexiconWords, getManagedServices, getPageCheckerSettings, getPageCheckJob, getPageCheckScoreHistory, getPageCheckStatistics, getPageSnapshot, getTranslationJob, listPageCheckJobs, refreshMaterializedViews, sendGemmaChat, startPageCheck, startTranslationJob, updateDefinitionTranslationSettings, updateGemmaSettings, updatePageCheckerAutonomousAgent, updatePageCheckerSettings, updatePageCheckJobHistoryLimit, updateTranslationPrefilter } from "./api";
import { relationByName } from "./schema";

afterEach(() => vi.restoreAllMocks());

describe("PostgREST relation URLs", () => {
  it("builds a paginated and ordered table query", () => {
    const relation = relationByName.get("word");
    expect(relation).toBeDefined();

    const url = new URL(buildRelationUrl(relation!, { page: 2, pageSize: 25 }), "http://localhost");

    expect(url.pathname).toBe("/api/database/word");
    expect(url.searchParams.get("limit")).toBe("25");
    expect(url.searchParams.get("offset")).toBe("50");
    expect(url.searchParams.get("order")).toBe("id.desc");
    expect(url.searchParams.get("select")).not.toContain("definition_vector");
  });

  it("adds safe multi-column text filtering", () => {
    const relation = relationByName.get("definitions");
    const url = new URL(buildRelationUrl(relation!, { search: "hello,* world" }), "http://localhost");

    expect(url.searchParams.get("or")).toBe(
      '(definition.ilike.*"hello, world"*,definition_language.ilike.*"hello, world"*)',
    );
  });

  it("escapes PostgREST reserved characters and LIKE wildcards in search", () => {
    const relation = relationByName.get("definitions");
    const url = new URL(buildRelationUrl(relation!, { search: '50%_foo"bar(baz)' }), "http://localhost");

    expect(url.searchParams.get("or")).toBe(
      '(definition.ilike.*"50\\\\%\\\\_foo\\"bar(baz)"*,definition_language.ilike.*"50\\\\%\\\\_foo\\"bar(baz)"*)',
    );
  });

  it("does not add unsupported search filters to views", () => {
    const relation = relationByName.get("db_stats");
    const url = new URL(buildRelationUrl(relation!, { search: "word" }), "http://localhost");

    expect(url.searchParams.has("or")).toBe(false);
  });
});

describe("JSON dictionary URLs", () => {
  it("builds an exact-word snapshot query with encoded input", () => {
    const url = new URL(buildJsonDictionaryWordPath("rock & roll"), "http://localhost");

    expect(url.pathname).toBe("/json_dictionary");
    expect(url.searchParams.get("word")).toBe("eq.rock & roll");
    expect(url.searchParams.get("order")).toBe("language.asc,part_of_speech.asc,id.asc");
    expect(url.searchParams.get("select")).toContain("additional_data");
  });

  it("builds a paginated ranked-search RPC query", () => {
    const url = new URL(buildJsonDictionarySearchPath("rock & roll", 2, 20), "http://localhost");

    expect(url.pathname).toBe("/rpc/search_json_dictionary");
    expect(url.searchParams.get("p_query")).toBe("rock & roll");
    expect(url.searchParams.get("p_limit")).toBe("21");
    expect(url.searchParams.get("p_offset")).toBe("40");
  });

  it("loads and caches the renderer-compatible definition link pool", async () => {
    configureApi({ databaseAddress: "", postgrestAddresses: ["/api/database"], dictionaryServiceAddresses: [], entryTranslatorAddresses: [] });
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify([{ word: "longword" }, { word: "trano fonenana" }]), { status: 200 }),
    );

    const first = await getLinkableLexiconWords();
    const second = await getLinkableLexiconWords();

    expect([...first]).toEqual(["longword", "trano fonenana"]);
    expect(second).toBe(first);
    expect(fetchMock).toHaveBeenCalledOnce();
    const url = new URL(String(fetchMock.mock.calls[0][0]), "http://localhost");
    expect(url.pathname).toBe("/api/database/rpc/linkable_lexicon_headwords");
  });

  it("retries link candidates after a failed request", async () => {
    configureApi({ databaseAddress: "", postgrestAddresses: ["/api/database"], dictionaryServiceAddresses: [], entryTranslatorAddresses: [] });
    const fetchMock = vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(new Response(JSON.stringify({ message: "offline" }), { status: 503 }))
      .mockResolvedValueOnce(new Response(JSON.stringify([{ word: "longword" }]), { status: 200 }));

    await expect(getLinkableLexiconWords()).rejects.toThrow("offline");
    await expect(getLinkableLexiconWords()).resolves.toEqual(new Set(["longword"]));
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("deduplicates previews, retries failures, and invalidates caches on reconfiguration", async () => {
    const config = { databaseAddress: "", postgrestAddresses: ["/api/database"], dictionaryServiceAddresses: [], entryTranslatorAddresses: [] };
    configureApi(config);
    const records = [{ id: 1, word: "longword", language: "mg", part_of_speech: "ana", definitions: [], additional_data: null }];
    const fetchMock = vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(new Response(JSON.stringify(records), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ message: "temporary" }), { status: 503 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(records), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(records), { status: 200 }));

    const first = getLexiconWordPreview("Longword");
    const second = getLexiconWordPreview("longword");
    expect(second).toBe(first);
    await expect(first).resolves.toEqual(records);
    await expect(getLexiconWordPreview("retryword")).rejects.toThrow("temporary");
    await expect(getLexiconWordPreview("retryword")).resolves.toEqual(records);
    configureApi(config);
    await expect(getLexiconWordPreview("longword")).resolves.toEqual(records);
    expect(fetchMock).toHaveBeenCalledTimes(4);
  });
});

describe("Supervisor control API", () => {
  it("sends Gemma conversations through the protected same-origin gateway", async () => {
    const response = { model: "gemma-remote", message: { role: "assistant" as const, content: "Hello back" } };
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(response), { status: 200 }),
    );

    await expect(sendGemmaChat([{ role: "user", content: "Hello" }])).resolves.toEqual(response);

    expect(fetchMock).toHaveBeenCalledWith("/api/gemma/chat", expect.objectContaining({
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Atlas-Gemma": "1" },
      body: JSON.stringify({ messages: [{ role: "user", content: "Hello" }] }),
    }));
  });

  it("rejects malformed Gemma responses", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ model: "gemma-remote", message: { role: "assistant", content: "" } }), { status: 200 }),
    );

    await expect(sendGemmaChat([{ role: "user", content: "Hello" }])).rejects.toThrow("Invalid Gemma chat response.");
  });

  it("loads and updates server-managed Gemma endpoint settings", async () => {
    const initial = { api_url: "http://localhost:8891/v1/chat/completions", model: "gemma-4" };
    const updated = { api_url: "https://gemma.example/v1/chat/completions", model: "gemma-4" };
    const fetchMock = vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(new Response(JSON.stringify(initial), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(updated), { status: 200 }));

    await expect(getGemmaSettings()).resolves.toEqual(initial);
    await expect(updateGemmaSettings(updated.api_url)).resolves.toEqual(updated);

    expect(fetchMock.mock.calls[0][0]).toBe("/api/gemma/settings");
    expect(fetchMock.mock.calls[1]).toEqual(["/api/gemma/settings", {
      method: "PUT",
      headers: { "Content-Type": "application/json", "X-Atlas-Gemma": "1" },
      body: JSON.stringify({ api_url: updated.api_url }),
    }]);
  });

  it("uses the same-origin gateway and required write header", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(new Response(JSON.stringify({ hosts: [] }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ id: "service", running: true }), { status: 200 }));

    await getManagedServices();
    await changeManagedService("remote host", "dictionary/service", "start");

    expect(fetchMock.mock.calls[0][0]).toBe("/api/services/hosts");
    expect(fetchMock.mock.calls[1][0]).toBe("/api/services/hosts/remote%20host/services/dictionary%2Fservice/start");
    expect(fetchMock.mock.calls[1][1]).toMatchObject({
      method: "POST",
      headers: { "X-Atlas-Service-Control": "1" },
    });
  });

  it("routes dashboard statistics through the configured PostgREST address", async () => {
    configureApi({ databaseAddress: "", postgrestAddresses: ["/custom/postgrest"], dictionaryServiceAddresses: [], entryTranslatorAddresses: [] });
    const fetchMock = vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(new Response(JSON.stringify([]), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ refreshed_views: 9, completed_at: "2026-08-14T00:00:00+00:00" }), { status: 200 }));

    await getDashboardStatistics();
    await refreshMaterializedViews();

    expect(fetchMock.mock.calls[0][0]).toBe("/custom/postgrest/atlas_dashboard_statistics_mv?select=period,period_start,period_end,entry_count,translated_languages,generated_at,missing_timestamp_count&order=period_start.desc");
    expect(fetchMock.mock.calls[1][0]).toBe("/api/maintenance/materialized-views/refresh");
    expect(fetchMock.mock.calls[1][1]).toMatchObject({ method: "POST", headers: { "X-Atlas-Maintenance": "1" } });
  });

  it("deduplicates and caches dashboard statistics for five minutes", async () => {
    configureApi({ databaseAddress: "", postgrestAddresses: ["/api/database"], dictionaryServiceAddresses: [], entryTranslatorAddresses: [] });
    const now = vi.spyOn(Date, "now").mockReturnValue(1_000);
    const fetchMock = vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(new Response(JSON.stringify([{ period: "last_day", entry_count: 12 }]), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify([{ period: "last_day", entry_count: 13 }]), { status: 200 }));

    const [first, concurrent] = await Promise.all([getDashboardStatistics(), getDashboardStatistics()]);
    const cached = await getDashboardStatistics();

    expect(first).toEqual(concurrent);
    expect(cached).toEqual(first);
    expect(fetchMock).toHaveBeenCalledOnce();

    now.mockReturnValue(301_000);
    await expect(getDashboardStatistics()).resolves.toEqual([{ period: "last_day", entry_count: 13 }]);
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("escapes primary key values in update and delete identity filters", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(new Response(JSON.stringify({ id: 1 }), { status: 201 }))
      .mockResolvedValueOnce(new Response(JSON.stringify([{ id: 1 }]), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ id: 1, outcome: "succeeded" }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ id: 2 }), { status: 201 }))
      .mockResolvedValueOnce(new Response(undefined, { status: 204, headers: { "content-length": "0" } }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ id: 2, outcome: "succeeded" }), { status: 200 }));

    const { updateRow, deleteRow, configureApi } = await import("./api");
    configureApi({ databaseAddress: "", postgrestAddresses: ["/api/database"], dictionaryServiceAddresses: [], entryTranslatorAddresses: [] });
    const relation = relationByName.get("language")!;
    const maliciousRow = { iso_code: 'mg,"or)=(eq.1' };
    await updateRow(relation, maliciousRow, { iso_code: 'mg,"or)=(eq.1', english_name: "Malagasy" });
    await deleteRow(relation, maliciousRow);

    const updateUrl = fetchMock.mock.calls[1][0] as string;
    const deleteUrl = fetchMock.mock.calls[4][0] as string;
    expect(updateUrl).toContain("iso_code=eq.%22mg%2C%5C%22or%29%3D%28eq.1%22");
    expect(deleteUrl).toContain("iso_code=eq.%22mg%2C%5C%22or%29%3D%28eq.1%22");
  });

  it("escapes PostgREST reserved characters in JSON dictionary word lookup", () => {
    const url = new URL(buildJsonDictionaryWordPath('rock"(baz)'), "http://localhost");

    expect(url.searchParams.get("word")).toBe('eq."rock\\"(baz)"');
  });
});

describe("Operations audit", () => {
  it("records and completes a database mutation without storing row values", async () => {
    const relation = relationByName.get("word");
    expect(relation).toBeDefined();
    const fetchMock = vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(new Response(JSON.stringify({ id: 41 }), { status: 201 }))
      .mockResolvedValueOnce(new Response(JSON.stringify([{ id: 8, word: "house" }]), { status: 201 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ id: 41, outcome: "succeeded" }), { status: 200 }));

    await createRow(relation!, { word: "house", language: "en" });

    expect(fetchMock.mock.calls[0][0]).toBe("/api/operations/records");
    const auditBody = JSON.parse(String((fetchMock.mock.calls[0][1] as RequestInit).body));
    expect(auditBody).toMatchObject({ service: "database", action: "create", resource: "word", changed_fields: ["word", "language"], target: {} });
    expect(JSON.stringify(auditBody)).not.toContain("house");
    expect(fetchMock.mock.calls[1][0]).toBe("/api/database/word");
    expect(fetchMock.mock.calls[2][0]).toBe("/api/operations/records/41");
  });

  it("marks a failed mutation without hiding the original error", async () => {
    const relation = relationByName.get("word");
    const fetchMock = vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(new Response(JSON.stringify({ id: 42 }), { status: 201 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ message: "duplicate word" }), { status: 409 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ id: 42, outcome: "failed" }), { status: 200 }));

    await expect(createRow(relation!, { word: "house" })).rejects.toThrow("duplicate word");
    expect(JSON.parse(String((fetchMock.mock.calls[2][1] as RequestInit).body))).toEqual({ outcome: "failed", error_summary: "duplicate word" });
  });
});

describe("Translation job API", () => {
  const acceptedJob = {
    job_id: "translation/job-1",
    language: "en gb",
    title: "hello",
    status: "pending" as const,
    stage: "queued" as const,
    publication_state: "not_queued" as const,
    created_at: 1,
    last_updated_at: 1,
    result: null,
    error: null,
    message: "translation job queued",
  };

  it("starts one translation job through the complete audit chain", async () => {
    configureApi({ databaseAddress: "", postgrestAddresses: [], dictionaryServiceAddresses: [], entryTranslatorAddresses: ["/translator-primary", "/translator-secondary"] });
    const requestId = "9c9a6a48-2304-4505-9cfe-57fbddc88bb1";
    const acceptedRequestJob = { ...acceptedJob, job_id: requestId };
    const fetchMock = vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(new Response(JSON.stringify({ id: 71 }), { status: 201 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(acceptedRequestJob), { status: 202 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ id: 71, outcome: "succeeded" }), { status: 200 }));

    await expect(startTranslationJob("en gb", "hello", requestId)).resolves.toEqual(acceptedRequestJob);

    expect(fetchMock.mock.calls.map(([url]) => url)).toEqual([
      "/api/operations/records",
      "/translator-primary/wiktionary-pages/en%20gb/jobs",
      "/api/operations/records/71",
    ]);
    expect(JSON.parse(String((fetchMock.mock.calls[0][1] as RequestInit).body))).toEqual({
      service: "translator",
      action: "queue",
      resource: "wiktionary-page",
      target: { language: "en gb", title: "hello", request_id: requestId },
      changed_fields: [],
    });
    expect(fetchMock.mock.calls[1][1]).toMatchObject({ method: "POST", headers: { "Content-Type": "application/json" } });
    expect(JSON.parse(String((fetchMock.mock.calls[1][1] as RequestInit).body))).toEqual({ title: "hello", request_id: requestId });
    expect(JSON.parse(String((fetchMock.mock.calls[2][1] as RequestInit).body))).toEqual({ outcome: "succeeded" });
  });

  it("does not retry a failed translation job POST on another translator", async () => {
    configureApi({ databaseAddress: "", postgrestAddresses: [], dictionaryServiceAddresses: [], entryTranslatorAddresses: ["/translator-primary", "/translator-secondary"] });
    const requestId = "9c9a6a48-2304-4505-9cfe-57fbddc88bb2";
    const fetchMock = vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(new Response(JSON.stringify({ id: 72 }), { status: 201 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ message: "translator busy" }), { status: 503 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ id: 72, outcome: "failed" }), { status: 200 }));

    await expect(startTranslationJob("en", "hello", requestId)).rejects.toThrow("translator busy");

    expect(fetchMock.mock.calls.map(([url]) => url)).toEqual([
      "/api/operations/records",
      "/translator-primary/wiktionary-pages/en/jobs",
      "/api/operations/records/72",
    ]);
    expect(JSON.parse(String((fetchMock.mock.calls[2][1] as RequestInit).body))).toEqual({ outcome: "failed", error_summary: "translator busy" });
  });

  it("fails over status GETs with the caller signal and no-store caching", async () => {
    configureApi({ databaseAddress: "", postgrestAddresses: [], dictionaryServiceAddresses: [], entryTranslatorAddresses: ["/translator-primary", "/translator-secondary"] });
    const controller = new AbortController();
    const doneJob = { ...acceptedJob, status: "done" as const, stage: "completed" as const, publication_state: "queued" as const, result: { status: "publication_queued" }, last_updated_at: 2 };
    const fetchMock = vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(new Response(JSON.stringify({ message: "primary unavailable" }), { status: 503 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(doneJob), { status: 200 }));

    await expect(getTranslationJob("en gb", "translation/job-1", controller.signal)).resolves.toEqual(doneJob);

    expect(fetchMock.mock.calls.map(([url]) => url)).toEqual([
      "/translator-primary/wiktionary-pages/en%20gb/jobs/translation%2Fjob-1",
      "/translator-secondary/wiktionary-pages/en%20gb/jobs/translation%2Fjob-1",
    ]);
    expect(fetchMock.mock.calls[0][1]).toMatchObject({ cache: "no-store", signal: controller.signal });
    expect(fetchMock.mock.calls[1][1]).toMatchObject({ cache: "no-store", signal: controller.signal });
  });

  it("rejects malformed translation job payloads", async () => {
    configureApi({ databaseAddress: "", postgrestAddresses: [], dictionaryServiceAddresses: [], entryTranslatorAddresses: ["/translator-primary"] });
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(new Response(JSON.stringify({
      ...acceptedJob,
      title: { unsafe: true },
    }), { status: 200 }));

    await expect(getTranslationJob("en", "translation-job-1")).rejects.toThrow("Invalid translation job response.");
  });

  it("rejects a shape-valid job with the wrong response identity", async () => {
    configureApi({ databaseAddress: "", postgrestAddresses: [], dictionaryServiceAddresses: [], entryTranslatorAddresses: ["/translator-primary"] });
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(new Response(JSON.stringify(acceptedJob), { status: 200 }));

    await expect(getTranslationJob("en gb", "different-job")).rejects.toThrow("Invalid translation job response.");
  });

  it("does not mark an ambiguous malformed acceptance as failed", async () => {
    configureApi({ databaseAddress: "", postgrestAddresses: [], dictionaryServiceAddresses: [], entryTranslatorAddresses: ["/translator-primary"] });
    const requestId = "9c9a6a48-2304-4505-9cfe-57fbddc88bb3";
    const fetchMock = vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(new Response(JSON.stringify({ id: 73 }), { status: 201 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ accepted: true }), { status: 202 }));

    await expect(startTranslationJob("en", "hello", requestId)).rejects.toThrow("Invalid translation job response.");

    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("does not call the translator when audit creation fails", async () => {
    configureApi({ databaseAddress: "", postgrestAddresses: [], dictionaryServiceAddresses: [], entryTranslatorAddresses: ["/translator-primary"] });
    const fetchMock = vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(new Response(JSON.stringify({ message: "audit offline" }), { status: 503 }));

    await expect(startTranslationJob("en", "hello", "9c9a6a48-2304-4505-9cfe-57fbddc88bb4")).rejects.toThrow("audit offline");

    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("loads an exact live page snapshot with encoded input", async () => {
    configureApi({ databaseAddress: "", postgrestAddresses: [], dictionaryServiceAddresses: [], entryTranslatorAddresses: ["/translator"] });
    const controller = new AbortController();
    const snapshot = { language: "en", title: "rock & roll", namespace: 0, content: "source", content_sha256: "abc", entries: [], parsed: true, parse_error: null, content_trust: "untrusted_wiktionary_content" };
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(new Response(JSON.stringify(snapshot), { status: 200 }));

    await expect(getPageSnapshot("en", "rock & roll", controller.signal)).resolves.toEqual(snapshot);

    const url = new URL(String(fetchMock.mock.calls[0][0]), "http://localhost");
    expect(url.pathname).toBe("/translator/wiktionary-page-snapshots/en");
    expect(url.searchParams.get("title")).toBe("rock & roll");
    expect(fetchMock.mock.calls[0][1]).toMatchObject({ cache: "no-store", signal: controller.signal });
  });
});

describe("Dictionary provenance API", () => {
  it("loads the entries sharing a definition", async () => {
    configureApi({ databaseAddress: "", postgrestAddresses: [], dictionaryServiceAddresses: ["/dictionary"], entryTranslatorAddresses: [] });
    const impact = { id: 42, definition: "trano", language: "mg", words: [{ id: 7, word: "house", language: "en", part_of_speech: "ana" }] };
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(new Response(JSON.stringify([impact]), { status: 200 }));

    await expect(getDefinitionImpact(42)).resolves.toEqual(impact);
    expect(fetchMock.mock.calls[0][0]).toBe("/dictionary/definition_words/42");
  });
});

describe("Page checker API", () => {
  it("loads automation settings with translator failover", async () => {
    configureApi({ databaseAddress: "", postgrestAddresses: [], dictionaryServiceAddresses: [], entryTranslatorAddresses: ["/translator-primary", "/translator-secondary"] });
    const controller = new AbortController();
    const fetchMock = vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(new Response(JSON.stringify({ message: "primary unavailable" }), { status: 503 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ watched_users: ["Alice"], check_probability: 40, cooldown_seconds: 90, ignored_edit_summaries: ["fanitsiana famaritana"], job_history_limit: 2500, autonomous_agent_enabled: false }), { status: 200 }));

    await expect(getPageCheckerSettings(controller.signal)).resolves.toEqual({ watched_users: ["Alice"], check_probability: 40, cooldown_seconds: 90, ignored_edit_summaries: ["fanitsiana famaritana"], job_history_limit: 2500, autonomous_agent_enabled: false, translation_prefilter_enabled: false });

    expect(fetchMock.mock.calls.map(([url]) => url)).toEqual([
      "/translator-primary/page-checker/settings",
      "/translator-secondary/page-checker/settings",
    ]);
    expect(fetchMock.mock.calls[0][1]).toMatchObject({ signal: controller.signal });
    expect(fetchMock.mock.calls[1][1]).toMatchObject({ signal: controller.signal });
  });

  it("loads settings from an older translator with the default job-history limit", async () => {
    configureApi({ databaseAddress: "", postgrestAddresses: [], dictionaryServiceAddresses: [], entryTranslatorAddresses: ["/translator-primary"] });
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(new Response(JSON.stringify({ watched_users: ["Alice"], check_probability: 40, cooldown_seconds: 90, ignored_edit_summaries: [], autonomous_agent_enabled: false }), { status: 200 }));

    await expect(getPageCheckerSettings()).resolves.toMatchObject({
      job_history_limit: 2500,
      autonomous_agent_enabled: false,
      translation_prefilter_enabled: false,
    });
  });

  it("rejects an invalid explicit job-history limit", async () => {
    configureApi({ databaseAddress: "", postgrestAddresses: [], dictionaryServiceAddresses: [], entryTranslatorAddresses: ["/translator-primary"] });
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(new Response(JSON.stringify({ watched_users: ["Alice"], check_probability: 40, cooldown_seconds: 90, ignored_edit_summaries: [], job_history_limit: 0, autonomous_agent_enabled: false }), { status: 200 }));

    await expect(getPageCheckerSettings()).rejects.toThrow("response is invalid");
  });

  it("updates every automation field through an audited translator mutation", async () => {
    configureApi({ databaseAddress: "", postgrestAddresses: [], dictionaryServiceAddresses: [], entryTranslatorAddresses: ["/translator-primary", "/translator-secondary"] });
    const submitted = { watched_users: ["PrivateEditor"], check_probability: 35, cooldown_seconds: 120, ignored_edit_summaries: ["fanitsiana famaritana", "Dikanteny: es"] };
    const canonical = { watched_users: ["PrivateEditor"], check_probability: 35, cooldown_seconds: 180, ignored_edit_summaries: ["fanitsiana famaritana", "Dikanteny: es"] };
    const fetchMock = vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(new Response(JSON.stringify({ id: 61 }), { status: 201 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(canonical), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ id: 61, outcome: "succeeded" }), { status: 200 }));

    await expect(updatePageCheckerSettings(submitted)).resolves.toEqual(canonical);

    expect(fetchMock.mock.calls[0][0]).toBe("/api/operations/records");
    const auditBody = JSON.parse(String((fetchMock.mock.calls[0][1] as RequestInit).body));
    expect(auditBody).toEqual({
      service: "translator",
      action: "configure",
      resource: "page-checker-settings",
      target: {},
      changed_fields: ["watched_users", "check_probability", "cooldown_seconds", "ignored_edit_summaries"],
    });
    expect(JSON.stringify(auditBody.target)).not.toContain("PrivateEditor");

    expect(fetchMock.mock.calls[1][0]).toBe("/translator-primary/page-checker/settings");
    expect(fetchMock.mock.calls[1][1]).toMatchObject({ method: "PUT", headers: { "Content-Type": "application/json" } });
    expect(JSON.parse(String((fetchMock.mock.calls[1][1] as RequestInit).body))).toEqual(submitted);
    expect(fetchMock.mock.calls[2][0]).toBe("/api/operations/records/61");
  });

  it("surfaces a plain-text audit rejection before updating settings", async () => {
    configureApi({ databaseAddress: "", postgrestAddresses: [], dictionaryServiceAddresses: [], entryTranslatorAddresses: ["/translator-primary"] });
    const submitted = { watched_users: ["Alice"], check_probability: 10, cooldown_seconds: 5, ignored_edit_summaries: [] };
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response("Invalid operation classification.", { status: 400, headers: { "Content-Type": "text/plain" } }),
    );

    await expect(updatePageCheckerSettings(submitted)).rejects.toThrow("Invalid operation classification.");
    expect(fetchMock).toHaveBeenCalledOnce();
    expect(fetchMock.mock.calls[0][0]).toBe("/api/operations/records");
  });

  it("updates the autonomous agent without sending monitoring settings", async () => {
    configureApi({ databaseAddress: "", postgrestAddresses: [], dictionaryServiceAddresses: [], entryTranslatorAddresses: ["/translator-primary"] });
    const fetchMock = vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(new Response(JSON.stringify({ id: 62 }), { status: 201 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ autonomous_agent_enabled: true }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ id: 62, outcome: "succeeded" }), { status: 200 }));

    await expect(updatePageCheckerAutonomousAgent(true)).resolves.toEqual({ autonomous_agent_enabled: true });

    expect(JSON.parse(String((fetchMock.mock.calls[0][1] as RequestInit).body))).toMatchObject({
      service: "translator",
      action: "configure",
      resource: "page-checker-settings",
      changed_fields: ["autonomous_agent_enabled"],
    });
    expect(fetchMock.mock.calls[1][0]).toBe("/translator-primary/page-checker/settings/autonomous-agent");
    expect(JSON.parse(String((fetchMock.mock.calls[1][1] as RequestInit).body))).toEqual({ enabled: true });
  });

  it("updates the translation prefilter through an audited mutation", async () => {
    configureApi({ databaseAddress: "", postgrestAddresses: [], dictionaryServiceAddresses: [], entryTranslatorAddresses: ["/translator-primary"] });
    const fetchMock = vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(new Response(JSON.stringify({ id: 64 }), { status: 201 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ translation_prefilter_enabled: true }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ id: 64, outcome: "succeeded" }), { status: 200 }));

    await expect(updateTranslationPrefilter(true)).resolves.toEqual({ translation_prefilter_enabled: true });

    expect(JSON.parse(String((fetchMock.mock.calls[0][1] as RequestInit).body))).toMatchObject({
      service: "translator",
      action: "configure",
      resource: "page-checker-settings",
      changed_fields: ["translation_prefilter_enabled"],
    });
    expect(fetchMock.mock.calls[1][0]).toBe("/translator-primary/page-checker/settings/translation-prefilter");
    expect(JSON.parse(String((fetchMock.mock.calls[1][1] as RequestInit).body))).toEqual({ enabled: true });
  });

  it("updates the job-history limit through an audited translator mutation", async () => {
    configureApi({ databaseAddress: "", postgrestAddresses: [], dictionaryServiceAddresses: [], entryTranslatorAddresses: ["/translator-primary"] });
    const fetchMock = vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(new Response(JSON.stringify({ id: 63 }), { status: 201 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ job_history_limit: 7500 }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ id: 63, outcome: "succeeded" }), { status: 200 }));

    await expect(updatePageCheckJobHistoryLimit(7500)).resolves.toEqual({ job_history_limit: 7500 });

    expect(JSON.parse(String((fetchMock.mock.calls[0][1] as RequestInit).body))).toMatchObject({
      service: "translator",
      action: "configure",
      resource: "page-checker-settings",
      changed_fields: ["job_history_limit"],
    });
    expect(fetchMock.mock.calls[1][0]).toBe("/translator-primary/page-checker/settings/job-history");
    expect(JSON.parse(String((fetchMock.mock.calls[1][1] as RequestInit).body))).toEqual({ limit: 7500 });
  });

  it("posts titles to the check endpoint and returns results", async () => {
    configureApi({ databaseAddress: "", postgrestAddresses: ["/api/database"], dictionaryServiceAddresses: [], entryTranslatorAddresses: ["/api/translator"] });
    const fetchMock = vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(new Response(JSON.stringify({ id: 50 }), { status: 201 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ results: [{ word: "alika", status: "good", message: "ok", source_language: "en", source_title: "dog", issues: [], mg_entry: null, fixed_entry: null }] }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ id: 50, outcome: "succeeded" }), { status: 200 }));

    const results = await checkPages("mg", ["alika"]);

    expect(results).toHaveLength(1);
    expect(results[0].word).toBe("alika");
    expect(fetchMock.mock.calls[1][0]).toBe("/api/translator/wiktionary-pages/mg/check");
    const body = JSON.parse(String((fetchMock.mock.calls[1][1] as RequestInit).body));
    expect(body).toEqual({ titles: ["alika"] });
    const auditBody = JSON.parse(String((fetchMock.mock.calls[0][1] as RequestInit).body));
    expect(auditBody).toMatchObject({ service: "translator", action: "check", resource: "wiktionary-page", target: { language: "mg" } });
    expect(auditBody.target.titles).toEqual(["alika"]);
  });

  it("queues asynchronous check jobs and returns them", async () => {
    configureApi({ databaseAddress: "", postgrestAddresses: ["/api/database"], dictionaryServiceAddresses: [], entryTranslatorAddresses: ["/api/translator"] });
    const fetchMock = vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(new Response(JSON.stringify({ id: 50 }), { status: 201 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ jobs: [{ job_id: "job-1", status: "pending" }, { job_id: "job-2", status: "pending" }] }), { status: 202 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ id: 50, outcome: "succeeded" }), { status: 200 }));

    const jobs = await startPageCheck("mg", ["alika", "soa"]);

    expect(jobs).toEqual([{ job_id: "job-1", status: "pending" }, { job_id: "job-2", status: "pending" }]);
    expect(fetchMock.mock.calls[1][0]).toBe("/api/translator/wiktionary-pages/mg/check-jobs");
    const body = JSON.parse(String((fetchMock.mock.calls[1][1] as RequestInit).body));
    expect(body).toEqual({ titles: ["alika", "soa"] });
  });

  it("fetches the state of an asynchronous check job", async () => {
    configureApi({ databaseAddress: "", postgrestAddresses: ["/api/database"], dictionaryServiceAddresses: [], entryTranslatorAddresses: ["/api/translator"] });
    const fetchMock = vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(new Response(JSON.stringify({ job_id: "job-1", status: "done", results: [] }), { status: 200 }));

    const job = await getPageCheckJob("mg", "job-1");

    expect(job.status).toBe("done");
    expect(fetchMock.mock.calls[0][0]).toBe("/api/translator/wiktionary-pages/mg/check-jobs/job-1");
  });

  it("lists page check job summaries", async () => {
    configureApi({ databaseAddress: "", postgrestAddresses: ["/api/database"], dictionaryServiceAddresses: [], entryTranslatorAddresses: ["/api/translator"] });
    const fetchMock = vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(new Response(JSON.stringify({ jobs: [{ job_id: "job-1", status: "done", result_counts: { good: 1, fixed: 0, unverifiable: 0, error: 0 } }] }), { status: 200 }));

    const jobs = await listPageCheckJobs("mg");

    expect(jobs).toHaveLength(1);
    expect(jobs[0].job_id).toBe("job-1");
    expect(fetchMock.mock.calls[0][0]).toBe("/api/translator/wiktionary-pages/mg/check-jobs?limit=100000");
  });

  it("loads retained page check statistics", async () => {
    configureApi({ databaseAddress: "", postgrestAddresses: [], dictionaryServiceAddresses: [], entryTranslatorAddresses: ["/api/translator"] });
    const controller = new AbortController();
    const response = { language: "mg test", generated_at: 10, timezone: "UTC", retention_limit: 200, retained_job_count: 12, statistics: [] } as const;
    const fetchMock = vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(new Response(JSON.stringify(response), { status: 200 }));

    await expect(getPageCheckStatistics("mg test", controller.signal)).resolves.toEqual(response);

    expect(fetchMock.mock.calls[0][0]).toBe("/api/translator/wiktionary-pages/mg%20test/check-jobs/statistics");
    expect(fetchMock.mock.calls[0][1]).toMatchObject({ signal: controller.signal });
  });

  it("loads bounded page check score history through PostgREST", async () => {
    configureApi({ databaseAddress: "", postgrestAddresses: ["/api/database"], dictionaryServiceAddresses: [], entryTranslatorAddresses: [] });
    const controller = new AbortController();
    const response = [{ snapshot_at: "2026-08-19T12:00:00+00:00", generated_at: "2026-08-19T12:00:05+00:00", good_percentage: 75, assessable_count: 8, retained_job_count: 12, retention_limit: 200 }];
    const fetchMock = vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(new Response(JSON.stringify(response), { status: 200 }));

    await expect(getPageCheckScoreHistory("mg test", "last_7_days", controller.signal)).resolves.toEqual(response);

    const url = new URL(String(fetchMock.mock.calls[0][0]), "http://localhost");
    expect(url.pathname).toBe("/api/database/rpc/page_check_score_history");
    expect(url.searchParams.get("p_language")).toBe("mg test");
    expect(url.searchParams.get("p_period")).toBe("last_7_days");
    expect(url.searchParams.get("p_max_points")).toBe("480");
    expect(fetchMock.mock.calls[0][1]).toMatchObject({ signal: controller.signal });
  });
});

describe("Definition translation settings API", () => {
  it("loads and validates the definition translation flags", async () => {
    configureApi({ databaseAddress: "", postgrestAddresses: [], dictionaryServiceAddresses: [], entryTranslatorAddresses: ["/translator"] });
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response(JSON.stringify({ basic_english_gate_enabled: false, nllb_roundtrip_validation_enabled: true }), { status: 200 }),
    );

    await expect(getDefinitionTranslationSettings()).resolves.toEqual({ basic_english_gate_enabled: false, nllb_roundtrip_validation_enabled: true });
  });

  it("updates definition translation settings through an audited mutation", async () => {
    configureApi({ databaseAddress: "", postgrestAddresses: [], dictionaryServiceAddresses: [], entryTranslatorAddresses: ["/translator"] });
    const fetchMock = vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(new Response(JSON.stringify({ id: 63 }), { status: 201 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ basic_english_gate_enabled: true, nllb_roundtrip_validation_enabled: false }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ id: 63, outcome: "succeeded" }), { status: 200 }));

    await expect(updateDefinitionTranslationSettings({ basic_english_gate_enabled: true, nllb_roundtrip_validation_enabled: false })).resolves.toEqual({ basic_english_gate_enabled: true, nllb_roundtrip_validation_enabled: false });

    expect(JSON.parse(String((fetchMock.mock.calls[0][1] as RequestInit).body))).toMatchObject({
      service: "translator",
      action: "configure",
      resource: "definition-translation-settings",
      changed_fields: ["basic_english_gate_enabled", "nllb_roundtrip_validation_enabled"],
    });
    expect(fetchMock.mock.calls[1][0]).toBe("/translator/definition-translation/settings");
    expect(JSON.parse(String((fetchMock.mock.calls[1][1] as RequestInit).body))).toEqual({ basic_english_gate_enabled: true, nllb_roundtrip_validation_enabled: false });
  });

  it("rejects a settings response without both boolean flags", async () => {
    configureApi({ databaseAddress: "", postgrestAddresses: [], dictionaryServiceAddresses: [], entryTranslatorAddresses: ["/translator"] });
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response(JSON.stringify({ basic_english_gate_enabled: false }), { status: 200 }),
    );

    await expect(getDefinitionTranslationSettings()).rejects.toThrow("Definition-translation settings response is invalid");
  });
});
