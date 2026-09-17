import { act, cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { getTranslationJob, listPageCheckJobs } from "../api";
import { I18nProvider } from "../i18n";
import { rememberPageCheckLanguage } from "../jobCenterTracking";
import { TranslationJobsProvider } from "../translationJobs";
import type { PageCheckJobSummary, TranslationJob } from "../types";
import { JobCenter } from "./JobCenter";

vi.mock("../api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../api")>()),
  getTranslationJob: vi.fn(),
  listPageCheckJobs: vi.fn(),
}));

const runningTranslation: TranslationJob = {
  job_id: "translation-1",
  language: "en",
  title: "house",
  status: "running",
  stage: "translating",
  publication_state: "not_queued",
  created_at: 1,
  last_updated_at: 2,
  result: null,
  error: null,
  message: "translating source page",
};

const pendingCheck: PageCheckJobSummary = {
  job_id: "check-1",
  language: "mg",
  titles: ["alika"],
  status: "pending",
  created_at: 10,
  last_updated_at: 20,
  attempts: 1,
  progress: 0,
  error: null,
  queue_position: 1,
  result_counts: { good: 0, fixed: 0, unverifiable: 0, error: 0 },
};

function renderJobCenter(onNavigate = vi.fn()) {
  return render(
    <I18nProvider>
      <TranslationJobsProvider onMessage={vi.fn()}>
        <JobCenter onNavigate={onNavigate} />
      </TranslationJobsProvider>
    </I18nProvider>,
  );
}

beforeEach(() => {
  vi.useFakeTimers();
  window.sessionStorage.clear();
  vi.mocked(getTranslationJob).mockResolvedValue(runningTranslation);
  vi.mocked(listPageCheckJobs).mockResolvedValue([pendingCheck]);
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.restoreAllMocks();
  vi.resetAllMocks();
});

describe("JobCenter", () => {
  it("updates the active count while the drawer is closed", async () => {
    renderJobCenter();
    await act(async () => vi.advanceTimersByTimeAsync(0));

    expect(screen.getByRole("button", { name: "Foiben'ny asa: 1 mandeha" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Foiben'ny asa" })).not.toBeInTheDocument();
  });

  it("combines globally tracked translation and page-check jobs", async () => {
    window.sessionStorage.setItem("botjagwar-atlas-tracked-translation-job", JSON.stringify([{ language: "en", jobId: "translation-1", title: "house" }]));
    renderJobCenter();

    fireEvent.click(screen.getByRole("button", { name: /Foiben'ny asa/ }));
    await act(async () => vi.advanceTimersByTimeAsync(0));

    expect(screen.getByRole("heading", { name: "Foiben'ny asa" })).toBeInTheDocument();
    expect(screen.getByText("house")).toBeInTheDocument();
    expect(screen.getByText("alika")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Foiben'ny asa: 2 mandeha" })).toBeInTheDocument();

    await act(async () => vi.advanceTimersByTimeAsync(3_000));
    expect(getTranslationJob).toHaveBeenCalledWith("en", "translation-1", expect.any(AbortSignal));
    expect(screen.getByText("Mandeha")).toBeInTheDocument();
  });

  it("opens the owning workspace and closes the drawer", async () => {
    const onNavigate = vi.fn();
    renderJobCenter(onNavigate);
    fireEvent.click(screen.getByRole("button", { name: /Foiben'ny asa/ }));
    await act(async () => vi.advanceTimersByTimeAsync(0));

    const pageCheckCard = screen.getByText("alika").closest("article");
    expect(pageCheckCard).not.toBeNull();
    fireEvent.click(within(pageCheckCard!).getByRole("button", { name: "Sokafy" }));

    expect(onNavigate).toHaveBeenCalledWith({ route: "checker", language: "mg", jobId: "check-1" });
    expect(screen.queryByRole("heading", { name: "Foiben'ny asa" })).not.toBeInTheDocument();
  });

  it("bounds remembered page-check languages, traps focus, and closes on Escape", async () => {
    for (const language of ["fr", "de", "es", "it", "pt", "sw", "pl"]) rememberPageCheckLanguage(language);
    vi.mocked(listPageCheckJobs).mockResolvedValue([]);
    renderJobCenter();

    const trigger = screen.getByRole("button", { name: /Foiben'ny asa/ });
    fireEvent.click(trigger);
    await act(async () => vi.advanceTimersByTimeAsync(0));

    expect(listPageCheckJobs).toHaveBeenCalledWith("mg", expect.any(AbortSignal));
    expect(listPageCheckJobs).toHaveBeenCalledWith("pl", expect.any(AbortSignal));
    expect(listPageCheckJobs).toHaveBeenCalledTimes(6);
    expect(screen.getAllByRole("button", { name: "Akatona ny foiben'ny asa" }).at(-1)).toHaveFocus();
    fireEvent.keyDown(window, { key: "Tab", shiftKey: true });
    expect(screen.getByRole("button", { name: "Havaozy" })).toHaveFocus();
    fireEvent.keyDown(window, { key: "Escape" });
    expect(screen.queryByRole("heading", { name: "Foiben'ny asa" })).not.toBeInTheDocument();
    expect(trigger).toHaveFocus();
  });

  it("shows active review handoff state instead of a terminal page-check label", async () => {
    vi.mocked(listPageCheckJobs).mockResolvedValue([{ ...pendingCheck, status: "done", review_queue_state: "failed", review_queue_error: "broker offline" }]);
    renderJobCenter();
    fireEvent.click(screen.getByRole("button", { name: /Foiben'ny asa/ }));
    await act(async () => vi.advanceTimersByTimeAsync(0));

    expect(screen.getByText("Miandry famerenana")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Foiben'ny asa: 1 mandeha" })).toBeInTheDocument();
  });
});
