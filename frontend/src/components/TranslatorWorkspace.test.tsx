import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiResponseError, InvalidApiResponseError, MutationNotStartedError, getPageSnapshot, getTranslationJob, getTranslatorErrors, getTranslatorHealth, previewPage, previewTranslations, startTranslationJob } from "../api";
import { I18nProvider } from "../i18n";
import type { TranslationHealth, TranslationJob } from "../types";
import { TranslatorWorkspace } from "./TranslatorWorkspace";

vi.mock("../api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../api")>()),
  getTranslationJob: vi.fn(),
  getPageSnapshot: vi.fn(),
  getTranslatorErrors: vi.fn(),
  getTranslatorHealth: vi.fn(),
  previewPage: vi.fn(),
  previewTranslations: vi.fn(),
  startTranslationJob: vi.fn(),
}));

const pendingJob: TranslationJob = {
  job_id: "translation-job-1",
  language: "fr-returned",
  title: "maison",
  status: "pending",
  stage: "queued",
  publication_state: "not_queued",
  created_at: 1,
  last_updated_at: 1,
  result: null,
  error: null,
  message: "translation job queued",
};

const runningJob: TranslationJob = {
  ...pendingJob,
  status: "running",
  stage: "translating",
  last_updated_at: 2,
  message: "translating source page",
};

const doneJob: TranslationJob = {
  ...pendingJob,
  status: "done",
  stage: "completed",
  publication_state: "queued",
  last_updated_at: 3,
  result: { status: "publication_queued", published: false },
  message: "translation completed",
};

beforeEach(() => {
  window.localStorage.removeItem("botjagwar-atlas-locale");
  window.sessionStorage.removeItem("botjagwar-atlas-tracked-translation-job");
  vi.mocked(getTranslatorHealth).mockResolvedValue({ status: "healthy" });
  vi.mocked(getTranslatorErrors).mockResolvedValue({ errors: [] });
  vi.mocked(getPageSnapshot).mockResolvedValue({ language: "en", title: "house", namespace: 0, content: "==English==", content_sha256: "abc123", entries: [], parsed: true, parse_error: null, content_trust: "untrusted_wiktionary_content" });
  vi.mocked(previewPage).mockResolvedValue([]);
  vi.mocked(previewTranslations).mockResolvedValue([]);
  vi.mocked(startTranslationJob).mockResolvedValue(pendingJob);
  vi.mocked(getTranslationJob).mockResolvedValue(doneJob);
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.restoreAllMocks();
  vi.resetAllMocks();
});

describe("TranslatorWorkspace", () => {
  it("shows full health telemetry and inspects a live snapshot", async () => {
    vi.mocked(getTranslatorHealth).mockResolvedValue({ status: "degraded", message: "Capacity full", counter_source: "redis", process_admitted_jobs: 25, process_job_capacity: 25, completed_job_count: 12, failed_job_count: 3, rejected_job_count: 4, average_job_duration_seconds: 91, recent_job_error_count: 2, accepting_async_jobs: false });
    render(<I18nProvider><TranslatorWorkspace onMessage={vi.fn()} /></I18nProvider>);

    expect(await screen.findByText("Capacity full")).toBeInTheDocument();
    expect(screen.getByText("91 seg")).toBeInTheDocument();
    expect(screen.getByText("12")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Lohatenin'ny pejy"), { target: { value: "house" } });
    fireEvent.click(screen.getByRole("button", { name: "Sary mivantana" }));

    expect(await screen.findByText("==English==")).toBeInTheDocument();
    expect(screen.getByText("abc123")).toBeInTheDocument();
    expect(getPageSnapshot).toHaveBeenCalledWith("en", "house");
  });

  it("shows a completed preview immediately without refreshing or awaiting health", async () => {
    vi.mocked(getTranslatorHealth).mockReturnValue(new Promise<TranslationHealth>(() => undefined));
    vi.mocked(previewPage).mockResolvedValue([{ entry: "preview-ready" }]);
    const onMessage = vi.fn();
    render(<I18nProvider><TranslatorWorkspace onMessage={onMessage} /></I18nProvider>);

    fireEvent.change(screen.getByLabelText("Lohatenin'ny pejy"), { target: { value: "house" } });
    fireEvent.click(screen.getByRole("button", { name: "Hijery topi-maso" }));

    expect(await screen.findByRole("heading", { name: "preview-ready" })).toBeInTheDocument();
    expect(screen.queryByText("Miandry ny mpandika teny...")).not.toBeInTheDocument();
    expect(previewPage).toHaveBeenCalledWith("en", "house");
    expect(getTranslatorHealth).toHaveBeenCalledTimes(1);
    expect(onMessage).toHaveBeenCalledWith("Vita ny topi-maso amin'ny pejy.");
  }, 15_000);

  it("polls the returned job every three seconds and emits one terminal toast", async () => {
    vi.useFakeTimers();
    vi.spyOn(window, "confirm").mockReturnValue(true);
    vi.mocked(getTranslationJob)
      .mockResolvedValueOnce(runningJob)
      .mockResolvedValueOnce(doneJob);
    const onMessage = vi.fn();
    render(<I18nProvider><TranslatorWorkspace onMessage={onMessage} /></I18nProvider>);

    fireEvent.change(screen.getByLabelText("Fiteny loharano"), { target: { value: "fr" } });
    fireEvent.change(screen.getByLabelText("Lohatenin'ny pejy"), { target: { value: "maison" } });
    fireEvent.click(screen.getByRole("button", { name: "Handika sy hampiditra ny famoahana anaty filaharana" }));
    await act(async () => vi.advanceTimersByTimeAsync(0));

    expect(startTranslationJob).toHaveBeenCalledWith("fr", "maison", expect.any(String));
    expect(screen.getByText("translation-job-1")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Fiteny loharano"), { target: { value: "de" } });

    await act(async () => vi.advanceTimersByTimeAsync(2_999));
    expect(getTranslationJob).not.toHaveBeenCalled();
    await act(async () => vi.advanceTimersByTimeAsync(1));
    expect(getTranslationJob).toHaveBeenCalledWith("fr-returned", "translation-job-1", expect.any(AbortSignal));
    expect(screen.getAllByText("Mandika ny pejy").length).toBeGreaterThan(0);

    await act(async () => vi.advanceTimersByTimeAsync(3_000));
    expect(getTranslationJob).toHaveBeenCalledTimes(2);
    expect(screen.getByText(/publication_queued/)).toBeInTheDocument();
    expect(screen.getByText("Toetry ny famoahana").closest("div")).toHaveTextContent("Ao anaty filaharana");
    expect(onMessage).toHaveBeenCalledTimes(1);
    expect(onMessage).toHaveBeenCalledWith("Vita ny asa fandikana.");
    expect(getTranslatorHealth).toHaveBeenCalledTimes(1);

    await act(async () => vi.advanceTimersByTimeAsync(60_000));
    expect(getTranslationJob).toHaveBeenCalledTimes(2);
    expect(onMessage).toHaveBeenCalledTimes(1);
  });

  it("uses 3/6/12/24/30-second status retry backoff capped at 30 seconds", async () => {
    vi.useFakeTimers();
    vi.spyOn(window, "confirm").mockReturnValue(true);
    vi.mocked(getTranslationJob).mockRejectedValue(new Error("status offline"));
    const onMessage = vi.fn();
    render(<I18nProvider><TranslatorWorkspace onMessage={onMessage} /></I18nProvider>);

    fireEvent.change(screen.getByLabelText("Lohatenin'ny pejy"), { target: { value: "maison" } });
    fireEvent.click(screen.getByRole("button", { name: "Handika sy hampiditra ny famoahana anaty filaharana" }));
    await act(async () => vi.advanceTimersByTimeAsync(0));

    await act(async () => vi.advanceTimersByTimeAsync(3_000));
    expect(getTranslationJob).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("alert")).toHaveTextContent("Haverina afaka 3 segondra.");

    for (const [delay, calls] of [[3_000, 2], [6_000, 3], [12_000, 4], [24_000, 5], [30_000, 6], [30_000, 7]] as const) {
      await act(async () => vi.advanceTimersByTimeAsync(delay - 1));
      expect(getTranslationJob).toHaveBeenCalledTimes(calls - 1);
      await act(async () => vi.advanceTimersByTimeAsync(1));
      expect(getTranslationJob).toHaveBeenCalledTimes(calls);
    }
    expect(screen.getByRole("alert")).toHaveTextContent("Haverina afaka 30 segondra.");
    expect(onMessage).not.toHaveBeenCalled();
  });

  it("stops on a failed job and exposes its error as an alert", async () => {
    vi.useFakeTimers();
    vi.spyOn(window, "confirm").mockReturnValue(true);
    const failedJob: TranslationJob = {
      ...pendingJob,
      status: "error",
      stage: "failed",
      last_updated_at: 2,
      error: "DeepSeek timeout",
      message: "translation failed",
    };
    vi.mocked(getTranslationJob).mockResolvedValue(failedJob);
    const onMessage = vi.fn();
    render(<I18nProvider><TranslatorWorkspace onMessage={onMessage} /></I18nProvider>);

    fireEvent.change(screen.getByLabelText("Lohatenin'ny pejy"), { target: { value: "maison" } });
    fireEvent.click(screen.getByRole("button", { name: "Handika sy hampiditra ny famoahana anaty filaharana" }));
    await act(async () => vi.advanceTimersByTimeAsync(0));
    await act(async () => vi.advanceTimersByTimeAsync(3_000));

    expect(screen.getByText("DeepSeek timeout")).toHaveAttribute("role", "alert");
    expect(screen.getAllByText("Tsy nahomby").length).toBeGreaterThan(0);
    expect(onMessage).toHaveBeenCalledTimes(1);
    expect(onMessage).toHaveBeenCalledWith("DeepSeek timeout", "error");
    await act(async () => vi.advanceTimersByTimeAsync(30_000));
    expect(getTranslationJob).toHaveBeenCalledTimes(1);
  });

  it("does not start a job when confirmation is cancelled", () => {
    vi.spyOn(window, "confirm").mockReturnValue(false);
    render(<I18nProvider><TranslatorWorkspace onMessage={vi.fn()} /></I18nProvider>);

    fireEvent.change(screen.getByLabelText("Lohatenin'ny pejy"), { target: { value: "house" } });
    fireEvent.click(screen.getByRole("button", { name: "Handika sy hampiditra ny famoahana anaty filaharana" }));

    expect(window.confirm).toHaveBeenCalledWith(expect.stringContaining("house"));
    expect(startTranslationJob).not.toHaveBeenCalled();
    expect(getTranslationJob).not.toHaveBeenCalled();
  });

  it("discovers an accepted job after a malformed successful response", async () => {
    vi.useFakeTimers();
    vi.spyOn(window, "confirm").mockReturnValue(true);
    vi.mocked(startTranslationJob).mockRejectedValueOnce(new InvalidApiResponseError("Invalid translation job response."));
    vi.mocked(getTranslationJob).mockImplementation((jobLanguage, jobId) => Promise.resolve({
      ...doneJob,
      language: jobLanguage,
      job_id: jobId,
    }));
    const onMessage = vi.fn();
    render(<I18nProvider><TranslatorWorkspace onMessage={onMessage} /></I18nProvider>);

    fireEvent.change(screen.getByLabelText("Lohatenin'ny pejy"), { target: { value: "maison" } });
    fireEvent.click(screen.getByRole("button", { name: "Handika sy hampiditra ny famoahana anaty filaharana" }));
    await act(async () => vi.advanceTimersByTimeAsync(0));
    expect(onMessage).toHaveBeenCalledWith("Invalid translation job response.", "error");
    expect(screen.getByText("Karohina ny asa nalefa...")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Handika sy hampiditra ny famoahana anaty filaharana" })).toBeEnabled();

    const calls = vi.mocked(startTranslationJob).mock.calls;
    await act(async () => vi.advanceTimersByTimeAsync(3_000));
    expect(getTranslationJob).toHaveBeenCalledWith("en", calls[0][2], expect.any(AbortSignal));
    expect(window.sessionStorage.getItem("botjagwar-atlas-tracked-translation-job")).toBeNull();
  });

  it("allows an immediate retry when auditing fails before submission", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    vi.mocked(startTranslationJob).mockRejectedValueOnce(new MutationNotStartedError("audit offline"));
    const onMessage = vi.fn();
    render(<I18nProvider><TranslatorWorkspace onMessage={onMessage} /></I18nProvider>);

    fireEvent.change(screen.getByLabelText("Lohatenin'ny pejy"), { target: { value: "maison" } });
    fireEvent.click(screen.getByRole("button", { name: "Handika sy hampiditra ny famoahana anaty filaharana" }));
    await act(async () => Promise.resolve());

    expect(onMessage).toHaveBeenCalledWith("audit offline", "error");
    expect(screen.getByRole("button", { name: "Handika sy hampiditra ny famoahana anaty filaharana" })).toBeEnabled();
    expect(window.sessionStorage.getItem("botjagwar-atlas-tracked-translation-job")).toBeNull();
  });

  it("allows another submission while an existing job remains active", async () => {
    vi.useFakeTimers();
    vi.spyOn(window, "confirm").mockReturnValue(true);
    let firstSignal: AbortSignal | undefined;
    vi.mocked(getTranslationJob).mockImplementation((_jobLanguage, _jobId, signal) => {
      firstSignal = signal;
      return new Promise<TranslationJob>(() => undefined);
    });
    vi.mocked(startTranslationJob)
      .mockResolvedValueOnce(pendingJob)
      .mockResolvedValueOnce({ ...pendingJob, job_id: "translation-job-2", language: "de", title: "Haus" });
    render(<I18nProvider><TranslatorWorkspace onMessage={vi.fn()} /></I18nProvider>);

    fireEvent.change(screen.getByLabelText("Lohatenin'ny pejy"), { target: { value: "maison" } });
    fireEvent.click(screen.getByRole("button", { name: "Handika sy hampiditra ny famoahana anaty filaharana" }));
    await act(async () => vi.advanceTimersByTimeAsync(0));
    await act(async () => vi.advanceTimersByTimeAsync(3_000));
    expect(firstSignal?.aborted).toBe(false);

    fireEvent.change(screen.getByLabelText("Fiteny loharano"), { target: { value: "de" } });
    fireEvent.change(screen.getByLabelText("Lohatenin'ny pejy"), { target: { value: "Haus" } });
    const trackedButton = screen.getByRole("button", { name: "Handika sy hampiditra ny famoahana anaty filaharana" });
    expect(trackedButton).toBeEnabled();
    fireEvent.click(trackedButton);
    await act(async () => vi.advanceTimersByTimeAsync(0));
    expect(startTranslationJob).toHaveBeenCalledTimes(2);
    expect(screen.getByText("translation-job-2")).toBeInTheDocument();
  });

  it("disables submission for a page that is already tracked", () => {
    window.sessionStorage.setItem("botjagwar-atlas-tracked-translation-job", JSON.stringify([
      { language: "en", jobId: "existing-job", title: "house" },
    ]));
    render(<I18nProvider><TranslatorWorkspace onMessage={vi.fn()} /></I18nProvider>);

    fireEvent.change(screen.getByLabelText("Lohatenin'ny pejy"), { target: { value: "HOUSE" } });

    expect(screen.getByRole("button", { name: "Handika sy hampiditra ny famoahana anaty filaharana" })).toBeDisabled();
    expect(screen.getByText("Efa araha-maso ity pejy ity")).toBeInTheDocument();
    expect(startTranslationJob).not.toHaveBeenCalled();
  });

  it("does not evict active jobs when the tracking list is full", () => {
    const targets = Array.from({ length: 8 }, (_, index) => ({ language: "en", jobId: `existing-job-${index}`, title: `page-${index}` }));
    window.sessionStorage.setItem("botjagwar-atlas-tracked-translation-job", JSON.stringify(targets));
    render(<I18nProvider><TranslatorWorkspace onMessage={vi.fn()} /></I18nProvider>);

    fireEvent.change(screen.getByLabelText("Lohatenin'ny pejy"), { target: { value: "new-page" } });

    expect(screen.getByRole("button", { name: "Handika sy hampiditra ny famoahana anaty filaharana" })).toBeDisabled();
    expect(screen.getByText("Feno ny lisitra")).toBeInTheDocument();
    expect(JSON.parse(window.sessionStorage.getItem("botjagwar-atlas-tracked-translation-job") ?? "[]")).toEqual(targets);
  });

  it("resumes a tracked job after the workspace remounts", async () => {
    vi.useFakeTimers();
    window.sessionStorage.setItem("botjagwar-atlas-tracked-translation-job", JSON.stringify({ language: "fr-returned", jobId: "translation-job-1" }));
    vi.mocked(getTranslationJob).mockResolvedValue(doneJob);
    const onMessage = vi.fn();

    render(<I18nProvider><TranslatorWorkspace onMessage={onMessage} /></I18nProvider>);
    await act(async () => vi.advanceTimersByTimeAsync(3_000));

    expect(getTranslationJob).toHaveBeenCalledWith("fr-returned", "translation-job-1", expect.any(AbortSignal));
    expect(screen.getByText(/publication_queued/)).toBeInTheDocument();
    expect(window.sessionStorage.getItem("botjagwar-atlas-tracked-translation-job")).toBeNull();
    expect(onMessage).toHaveBeenCalledWith("Vita ny asa fandikana.");
  });

  it("keeps looking up a provisional job while its POST outcome is unknown", async () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-01-01T00:00:00Z"));
    window.sessionStorage.setItem("botjagwar-atlas-tracked-translation-job", JSON.stringify({
      language: "fr-returned",
      jobId: "translation-job-1",
      provisionalSince: Date.now(),
    }));
    vi.mocked(getTranslationJob)
      .mockRejectedValueOnce(new ApiResponseError("Unknown translation job.", 404))
      .mockResolvedValueOnce(doneJob);

    render(<I18nProvider><TranslatorWorkspace onMessage={vi.fn()} /></I18nProvider>);
    await act(async () => vi.advanceTimersByTimeAsync(3_000));

    expect(getTranslationJob).toHaveBeenCalledTimes(1);
    expect(window.sessionStorage.getItem("botjagwar-atlas-tracked-translation-job")).not.toBeNull();

    await act(async () => vi.advanceTimersByTimeAsync(3_000));
    expect(getTranslationJob).toHaveBeenCalledTimes(2);
    expect(window.sessionStorage.getItem("botjagwar-atlas-tracked-translation-job")).toBeNull();
  });

  it("stops retrying a permanently missing restored job", async () => {
    vi.useFakeTimers();
    window.sessionStorage.setItem("botjagwar-atlas-tracked-translation-job", JSON.stringify({ language: "fr", jobId: "expired-job" }));
    vi.mocked(getTranslationJob).mockRejectedValue(new ApiResponseError("Unknown translation job.", 404));
    const onMessage = vi.fn();

    render(<I18nProvider><TranslatorWorkspace onMessage={onMessage} /></I18nProvider>);
    await act(async () => vi.advanceTimersByTimeAsync(3_000));
    await act(async () => vi.advanceTimersByTimeAsync(60_000));

    expect(getTranslationJob).toHaveBeenCalledTimes(1);
    expect(window.sessionStorage.getItem("botjagwar-atlas-tracked-translation-job")).toBeNull();
    expect(onMessage).toHaveBeenCalledWith("Tsy hita intsony ny asa fandikana.", "error");
  });

  it("keeps polling sequential and aborts in-flight status and health requests on cleanup", async () => {
    vi.useFakeTimers();
    vi.spyOn(window, "confirm").mockReturnValue(true);
    let healthSignal: AbortSignal | undefined;
    let jobSignal: AbortSignal | undefined;
    vi.mocked(getTranslatorHealth).mockImplementation((signal) => {
      healthSignal = signal;
      return new Promise<TranslationHealth>(() => undefined);
    });
    vi.mocked(getTranslationJob).mockImplementation((_language, _jobId, signal) => {
      jobSignal = signal;
      return new Promise<TranslationJob>(() => undefined);
    });
    const view = render(<I18nProvider><TranslatorWorkspace onMessage={vi.fn()} /></I18nProvider>);

    fireEvent.change(screen.getByLabelText("Lohatenin'ny pejy"), { target: { value: "maison" } });
    fireEvent.click(screen.getByRole("button", { name: "Handika sy hampiditra ny famoahana anaty filaharana" }));
    await act(async () => vi.advanceTimersByTimeAsync(0));
    await act(async () => vi.advanceTimersByTimeAsync(3_000));
    expect(getTranslationJob).toHaveBeenCalledTimes(1);

    await act(async () => vi.advanceTimersByTimeAsync(60_000));
    expect(getTranslationJob).toHaveBeenCalledTimes(1);
    view.unmount();
    expect(jobSignal?.aborted).toBe(true);
    expect(healthSignal?.aborted).toBe(true);

    await act(async () => vi.advanceTimersByTimeAsync(60_000));
    expect(getTranslationJob).toHaveBeenCalledTimes(1);
  });
});
