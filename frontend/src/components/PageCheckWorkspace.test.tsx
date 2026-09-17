import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { getPageCheckJob, getPageCheckScoreHistory, getPageCheckStatistics, listPageCheckJobs, startPageCheck } from "../api";
import { I18nProvider } from "../i18n";
import type { PageCheckGrade, PageCheckJob, PageCheckJobSummary, PageCheckPeriodStatistics, PageCheckScoreSnapshot, PageCheckStatisticsPeriod, PageCheckStatisticsResponse } from "../types";
import { PageCheckWorkspace } from "./PageCheckWorkspace";

vi.mock("../api", () => ({ getPageCheckJob: vi.fn(), getPageCheckScoreHistory: vi.fn(), getPageCheckStatistics: vi.fn(), listPageCheckJobs: vi.fn(), startPageCheck: vi.fn() }));

const emptyStatistics: PageCheckStatisticsResponse = {
  language: "mg",
  generated_at: 10,
  timezone: "UTC",
  retention_limit: 200,
  retained_job_count: 0,
  statistics: [],
};

beforeEach(() => {
  vi.spyOn(window, "confirm").mockReturnValue(true);
  vi.mocked(getPageCheckStatistics).mockResolvedValue(emptyStatistics);
  vi.mocked(getPageCheckScoreHistory).mockResolvedValue([]);
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  vi.restoreAllMocks();
  vi.useRealTimers();
});

const alikaJob: PageCheckJob = {
  job_id: "job-1",
  language: "mg",
  titles: ["alika"],
  status: "pending",
  created_at: 0,
  last_updated_at: 0,
  attempts: 1,
  progress: 0,
  results: null,
  error: null,
  stage: "queued",
  message: "Waiting for a page-check worker.",
  timeline: [{ timestamp: 0, stage: "queued", message: "Waiting for a page-check worker." }],
};

const soaJob: PageCheckJob = {
  job_id: "job-2",
  language: "mg",
  titles: ["soa"],
  status: "pending",
  created_at: 0,
  last_updated_at: 0,
  attempts: 1,
  progress: 0,
  results: null,
  error: null,
  stage: "queued",
  message: "Waiting for a page-check worker.",
  timeline: [{ timestamp: 0, stage: "queued", message: "Waiting for a page-check worker." }],
};

const doneAlika: PageCheckJob = {
  ...alikaJob,
  status: "done",
  progress: 100,
  stage: "completed",
  message: "Page check completed; the full result is available.",
  results: [
    { word: "alika", status: "good", message: "The Malagasy definition matches the source.", source_language: "en", source_title: "dog", issues: [], mg_entry: { entry: "alika", sections: [{ part_of_speech: "ana", definitions: ["alika"] }] }, fixed_entry: null },
  ],
};

const doneSoa: PageCheckJob = {
  ...soaJob,
  status: "done",
  progress: 100,
  stage: "completed",
  message: "Page check completed; the full result is available.",
  results: [
    { word: "soa", status: "fixed", message: "The Malagasy definition was fixed and queued for publication.", source_language: "en", source_title: "good", issues: [{ type: "definition", description: "wrong meaning" }], mg_entry: null, fixed_entry: { entry: "soa", part_of_speech: "mpam", definitions: ["tsara"], examples: ["Soa ity trano ity."] } },
  ],
};

const doneAlikaSummary: PageCheckJobSummary = {
  job_id: "job-1",
  language: "mg",
  titles: ["alika"],
  status: "done",
  created_at: 0,
  last_updated_at: 0,
  attempts: 1,
  progress: 100,
  error: null,
  stage: "completed",
  message: "Page check completed; the full result is available.",
  queue_position: null,
  result_counts: { good: 1, fixed: 0, unverifiable: 0, error: 0 },
};

const doneSoaSummary: PageCheckJobSummary = {
  job_id: "job-2",
  language: "mg",
  titles: ["soa"],
  status: "done",
  created_at: 0,
  last_updated_at: 0,
  attempts: 1,
  progress: 100,
  error: null,
  stage: "completed",
  message: "Page check completed; the full result is available.",
  queue_position: null,
  result_counts: { good: 0, fixed: 1, unverifiable: 0, error: 0 },
};

function periodStatistic(period: PageCheckStatisticsPeriod, grade: PageCheckGrade, goodPercentage: number | null): PageCheckPeriodStatistics {
  return {
    period,
    period_start: 0,
    period_end: 10,
    job_count: 12,
    checked_count: 10,
    assessable_count: 8,
    result_counts: { good: 6, fixed: 2, unverifiable: 1, error: 1 },
    good_percentage: goodPercentage,
    grade,
  };
}

describe("PageCheckWorkspace", () => {
  it("shows retained statistics in canonical period order with accessible grades", async () => {
    vi.mocked(listPageCheckJobs).mockResolvedValue([]);
    vi.mocked(getPageCheckStatistics).mockResolvedValue({
      ...emptyStatistics,
      retained_job_count: 12,
      statistics: [
        periodStatistic("current_month", "D", 65),
        periodStatistic("last_6_months", null, null),
        periodStatistic("today", "A", 95),
        periodStatistic("last_3_months", "E", 55),
        periodStatistic("current_week", "C", 75),
        periodStatistic("last_7_days", "B", 85),
      ],
    });

    const { container } = render(<I18nProvider><PageCheckWorkspace onMessage={vi.fn()} /></I18nProvider>);

    expect(await screen.findByRole("heading", { name: "Androany" })).toBeInTheDocument();
    expect([...container.querySelectorAll(".check-statistic h4")].map((heading) => heading.textContent)).toEqual([
      "Androany",
      "7 andro farany",
      "Ity herinandro ity",
      "Ity volana ity",
      "3 volana farany",
      "6 volana farany",
    ]);
    expect(screen.getByLabelText("Naoty A")).toHaveTextContent("A");
    expect(screen.getByLabelText("Tsy misy naoty")).toHaveTextContent("-");
    expect(screen.getByText("95%")).toBeInTheDocument();
    expect(screen.getByText("Ny tahan'ny pejy tsara dia isan'ny tsara zaraina amin'ny fitambaran'ny asa fanamarinana.")).toBeInTheDocument();
    expect(screen.getByText("12 / 200")).toBeInTheDocument();
    expect(screen.getAllByText("Nila fanitsiana")).toHaveLength(6);
    expect([...container.querySelectorAll(".check-statistic__weather > span")].every((symbol) => symbol.getAttribute("aria-hidden") === "true")).toBe(true);
    expect(getPageCheckStatistics).toHaveBeenCalledWith("mg", expect.any(AbortSignal));
  }, 10_000);

  it("plots half-hour score history and switches among the existing periods", async () => {
    vi.mocked(listPageCheckJobs).mockResolvedValue([]);
    vi.mocked(getPageCheckStatistics).mockResolvedValue({
      ...emptyStatistics,
      retained_job_count: 12,
      statistics: [
        periodStatistic("today", "A", 95),
        periodStatistic("last_7_days", "B", 85),
        periodStatistic("current_week", "C", 75),
        periodStatistic("current_month", "D", 65),
        periodStatistic("last_3_months", "E", 55),
        periodStatistic("last_6_months", null, null),
      ],
    });
    vi.mocked(getPageCheckScoreHistory)
      .mockResolvedValueOnce([
        { snapshot_at: "1970-01-01T00:00:02.000Z", generated_at: "1970-01-01T00:00:03.000Z", good_percentage: 70, assessable_count: 7, retained_job_count: 10, retention_limit: 200 },
        { snapshot_at: "1970-01-01T00:00:06.000Z", generated_at: "1970-01-01T00:00:07.000Z", good_percentage: 80, assessable_count: 8, retained_job_count: 11, retention_limit: 200 },
      ])
      .mockResolvedValueOnce([
        { snapshot_at: "1970-01-01T00:00:04.000Z", generated_at: "1970-01-01T00:00:05.000Z", good_percentage: 30, assessable_count: 7, retained_job_count: 10, retention_limit: 200 },
        { snapshot_at: "1970-01-01T00:00:08.000Z", generated_at: "1970-01-01T00:00:09.000Z", good_percentage: 40, assessable_count: 8, retained_job_count: 11, retention_limit: 200 },
      ]);

    const { container } = render(<I18nProvider><PageCheckWorkspace onMessage={vi.fn()} /></I18nProvider>);

    expect(await screen.findByRole("img", { name: /7 andro farany.*sary antsasak'adiny 2/i })).toBeInTheDocument();
    const initialPath = container.querySelector(".check-score-trend__line")?.getAttribute("d");
    expect(initialPath).toContain("L");
    expect(container.querySelector(".check-score-trend__live strong")).toHaveTextContent("85%");
    expect(getPageCheckScoreHistory).toHaveBeenCalledWith("mg", "last_7_days", expect.any(AbortSignal));

    fireEvent.click(screen.getByRole("button", { name: "Androany" }));
    await waitFor(() => expect(getPageCheckScoreHistory).toHaveBeenCalledWith("mg", "today", expect.any(AbortSignal)));
    await screen.findByRole("img", { name: /Androany.*30% hatramin'ny 40%/i });
    expect(container.querySelector("#page-check-score-trend-heading")).toHaveTextContent("Androany");
    expect(container.querySelector(".check-score-trend__live strong")).toHaveTextContent("95%");
    expect(container.querySelector(".check-score-trend__line")?.getAttribute("d")).not.toBe(initialPath);
  });

  it("breaks the score line across snapshots without assessable results", async () => {
    vi.mocked(listPageCheckJobs).mockResolvedValue([]);
    vi.mocked(getPageCheckStatistics).mockResolvedValue({
      ...emptyStatistics,
      statistics: [periodStatistic("last_7_days", "B", 85)],
    });
    vi.mocked(getPageCheckScoreHistory).mockResolvedValue([
      { snapshot_at: "1970-01-01T00:00:02.000Z", generated_at: "1970-01-01T00:00:03.000Z", good_percentage: 70, assessable_count: 7, retained_job_count: 10, retention_limit: 200 },
      { snapshot_at: "1970-01-01T00:00:04.000Z", generated_at: "1970-01-01T00:00:05.000Z", good_percentage: null, assessable_count: 0, retained_job_count: 10, retention_limit: 200 },
      { snapshot_at: "1970-01-01T00:00:06.000Z", generated_at: "1970-01-01T00:00:07.000Z", good_percentage: 80, assessable_count: 8, retained_job_count: 11, retention_limit: 200 },
    ]);

    const { container } = render(<I18nProvider><PageCheckWorkspace onMessage={vi.fn()} /></I18nProvider>);

    await screen.findByRole("img", { name: /sary antsasak'adiny 3/i });
    expect(container.querySelectorAll(".check-score-trend__line")).toHaveLength(2);
  });

  it("keeps saved score history visible when live statistics are unavailable", async () => {
    vi.mocked(listPageCheckJobs).mockResolvedValue([]);
    vi.mocked(getPageCheckStatistics).mockRejectedValue(new Error("statistics offline"));
    vi.mocked(getPageCheckScoreHistory).mockResolvedValue([
      { snapshot_at: "2026-08-19T12:00:00.000Z", generated_at: "2026-08-19T12:00:05.000Z", good_percentage: 75, assessable_count: 8, retained_job_count: 12, retention_limit: 200 },
    ]);

    render(<I18nProvider><PageCheckWorkspace onMessage={vi.fn()} /></I18nProvider>);

    expect(await screen.findByRole("alert")).toHaveTextContent("statistics offline");
    expect(await screen.findByRole("img", { name: /sary antsasak'adiny 1/i })).toBeInTheDocument();
  });

  it("shows a statistics error without hiding the checker", async () => {
    vi.mocked(listPageCheckJobs).mockResolvedValue([]);
    vi.mocked(getPageCheckStatistics).mockRejectedValue(new Error("statistics offline"));

    render(<I18nProvider><PageCheckWorkspace onMessage={vi.fn()} /></I18nProvider>);

    expect(await screen.findByRole("alert")).toHaveTextContent("statistics offline");
    expect(screen.getByRole("button", { name: "Hamarina pejy" })).toBeInTheDocument();
  });

  it("does not show statistics from the previous language while reloading", async () => {
    vi.mocked(listPageCheckJobs).mockResolvedValue([]);
    vi.mocked(getPageCheckStatistics)
      .mockResolvedValueOnce({
        ...emptyStatistics,
        statistics: [periodStatistic("today", "A", 95)],
      })
      .mockImplementationOnce(() => new Promise<PageCheckStatisticsResponse>(() => undefined));

    render(<I18nProvider><PageCheckWorkspace onMessage={vi.fn()} /></I18nProvider>);
    expect(await screen.findByRole("heading", { name: "Androany" })).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Fiteny"), { target: { value: "en" } });

    await waitFor(() => expect(getPageCheckStatistics).toHaveBeenCalledWith("en", expect.any(AbortSignal)));
    expect(screen.queryByRole("heading", { name: "Androany" })).not.toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("Maka ny antontanisa");
  });

  it("waits for a statistics request to finish before scheduling the next refresh", async () => {
    vi.useFakeTimers();
    vi.mocked(listPageCheckJobs).mockResolvedValue([]);
    let resolveFirst: (value: PageCheckStatisticsResponse) => void = () => undefined;
    const firstRequest = new Promise<PageCheckStatisticsResponse>((resolve) => {
      resolveFirst = resolve;
    });
    vi.mocked(getPageCheckStatistics)
      .mockReturnValueOnce(firstRequest)
      .mockResolvedValue(emptyStatistics);

    render(<I18nProvider><PageCheckWorkspace onMessage={vi.fn()} /></I18nProvider>);
    expect(getPageCheckStatistics).toHaveBeenCalledTimes(1);

    act(() => vi.advanceTimersByTime(120_000));
    expect(getPageCheckStatistics).toHaveBeenCalledTimes(1);

    await act(async () => resolveFirst(emptyStatistics));
    act(() => vi.advanceTimersByTime(59_999));
    expect(getPageCheckStatistics).toHaveBeenCalledTimes(1);
    act(() => vi.advanceTimersByTime(1));
    expect(getPageCheckStatistics).toHaveBeenCalledTimes(2);
  });

  it("waits for score history to settle before refreshing it after five minutes", async () => {
    vi.useFakeTimers();
    vi.mocked(listPageCheckJobs).mockResolvedValue([]);
    let resolveFirst: (value: PageCheckScoreSnapshot[]) => void = () => undefined;
    const firstRequest = new Promise<PageCheckScoreSnapshot[]>((resolve) => {
      resolveFirst = resolve;
    });
    vi.mocked(getPageCheckScoreHistory)
      .mockReturnValueOnce(firstRequest)
      .mockResolvedValue([]);

    render(<I18nProvider><PageCheckWorkspace onMessage={vi.fn()} /></I18nProvider>);
    expect(getPageCheckScoreHistory).toHaveBeenCalledTimes(1);

    act(() => vi.advanceTimersByTime(600_000));
    expect(getPageCheckScoreHistory).toHaveBeenCalledTimes(1);

    await act(async () => resolveFirst([]));
    act(() => vi.advanceTimersByTime(299_999));
    expect(getPageCheckScoreHistory).toHaveBeenCalledTimes(1);
    act(() => vi.advanceTimersByTime(1));
    expect(getPageCheckScoreHistory).toHaveBeenCalledTimes(2);
  });

  it("checks a list of pages asynchronously and shows status badges", async () => {
    vi.mocked(listPageCheckJobs).mockResolvedValue([doneAlikaSummary, doneSoaSummary]);
    vi.mocked(startPageCheck).mockResolvedValue([alikaJob, soaJob]);
    vi.mocked(getPageCheckJob).mockImplementation((_language, jobId) =>
      Promise.resolve(jobId === "job-1" ? doneAlika : doneSoa),
    );
    const onMessage = vi.fn();
    render(<I18nProvider><PageCheckWorkspace onMessage={onMessage} /></I18nProvider>);

    fireEvent.change(screen.getByLabelText("Lohateny (iray isaky ny andalana)"), { target: { value: "alika\nsoa" } });
    fireEvent.click(screen.getByRole("button", { name: "Hamarina pejy" }));

    await waitFor(() => expect(startPageCheck).toHaveBeenCalledWith("mg", ["alika", "soa"]));
    await waitFor(() => expect(getPageCheckJob).toHaveBeenCalledWith("mg", "job-1"));
    expect(await screen.findByRole("heading", { name: "alika" })).toBeInTheDocument();
    expect(screen.getByText("Tsara")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /soa/ }));
    expect(await screen.findByRole("heading", { name: "soa" })).toBeInTheDocument();
    expect(screen.getByText("Voahitsy")).toBeInTheDocument();
    expect(screen.getByText("wrong meaning")).toBeInTheDocument();
    await waitFor(() => expect(onMessage).toHaveBeenCalledWith("Nampidirina anaty filaharana ny pejy 2."));
  }, 10_000);

  it("does not submit checks when publication queue confirmation is cancelled", () => {
    vi.mocked(listPageCheckJobs).mockResolvedValue([]);
    vi.mocked(window.confirm).mockReturnValue(false);
    render(<I18nProvider><PageCheckWorkspace onMessage={vi.fn()} /></I18nProvider>);

    fireEvent.change(screen.getByLabelText("Lohateny (iray isaky ny andalana)"), { target: { value: "alika" } });
    fireEvent.click(screen.getByRole("button", { name: "Hamarina pejy" }));

    expect(window.confirm).toHaveBeenCalledWith(expect.stringContaining("filaharana havoaka"));
    expect(startPageCheck).not.toHaveBeenCalled();
  });

  it("shows the job error message when the check job fails", async () => {
    vi.mocked(listPageCheckJobs).mockResolvedValue([]);
    vi.mocked(startPageCheck).mockResolvedValue([{ ...alikaJob, status: "error", error: "DeepSeek timeout" }]);
    const onMessage = vi.fn();
    render(<I18nProvider><PageCheckWorkspace onMessage={onMessage} /></I18nProvider>);

    fireEvent.change(screen.getByLabelText("Lohateny (iray isaky ny andalana)"), { target: { value: "alika" } });
    fireEvent.click(screen.getByRole("button", { name: "Hamarina pejy" }));

    await waitFor(() => expect(onMessage).toHaveBeenCalledWith("DeepSeek timeout", "error"));
    expect(getPageCheckJob).not.toHaveBeenCalled();
  });

  it("shows an error message when submitting the check fails", async () => {
    vi.mocked(listPageCheckJobs).mockResolvedValue([]);
    vi.mocked(startPageCheck).mockRejectedValue(new Error("network down"));
    const onMessage = vi.fn();
    render(<I18nProvider><PageCheckWorkspace onMessage={onMessage} /></I18nProvider>);

    fireEvent.change(screen.getByLabelText("Lohateny (iray isaky ny andalana)"), { target: { value: "alika" } });
    fireEvent.click(screen.getByRole("button", { name: "Hamarina pejy" }));

    await waitFor(() => expect(onMessage).toHaveBeenCalledWith("network down", "error"));
  });

  it("does not call the API when no title is provided", async () => {
    vi.mocked(listPageCheckJobs).mockResolvedValue([]);
    const onMessage = vi.fn();
    render(<I18nProvider><PageCheckWorkspace onMessage={onMessage} /></I18nProvider>);

    fireEvent.submit(screen.getByRole("button", { name: "Hamarina pejy" }).closest("form")!);

    await waitFor(() => expect(onMessage).toHaveBeenCalledWith("Ampidiro farafahakeliny lohateny iray.", "error"));
    expect(startPageCheck).not.toHaveBeenCalled();
  });

  it("lists the job history and opens a job to see its details", async () => {
    vi.mocked(listPageCheckJobs).mockResolvedValue([doneAlikaSummary, doneSoaSummary]);
    vi.mocked(getPageCheckJob).mockResolvedValue(doneAlika);
    render(<I18nProvider><PageCheckWorkspace onMessage={vi.fn()} /></I18nProvider>);

    expect(await screen.findByText("alika")).toBeInTheDocument();
    expect(screen.getByText("soa")).toBeInTheDocument();
    expect(screen.getByText("Pejy 1: 1 tsara, 0 voahitsy, 0 tsy voamarina, 0 hadisoana")).toBeInTheDocument();
    expect(screen.getByText("Pejy 1: 0 tsara, 1 voahitsy, 0 tsy voamarina, 0 hadisoana")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /alika/ }));

    await waitFor(() => expect(getPageCheckJob).toHaveBeenCalledWith("mg", "job-1"));
    expect(await screen.findByRole("heading", { name: "alika" })).toBeInTheDocument();
    expect(screen.getByText("Tsara")).toBeInTheDocument();
  });

  it("opens an initial job and language supplied by the global job center", async () => {
    const frenchSummary = { ...doneAlikaSummary, language: "fr" };
    const frenchJob = { ...doneAlika, language: "fr" };
    vi.mocked(listPageCheckJobs).mockResolvedValue([frenchSummary]);
    vi.mocked(getPageCheckJob).mockResolvedValue(frenchJob);

    render(<I18nProvider><PageCheckWorkspace initialJobId="job-1" initialLanguage="fr" onMessage={vi.fn()} /></I18nProvider>);

    await waitFor(() => expect(listPageCheckJobs).toHaveBeenCalledWith("fr", expect.any(AbortSignal)));
    await waitFor(() => expect(getPageCheckJob).toHaveBeenCalledWith("fr", "job-1"));
    expect(screen.getByLabelText("Fiteny")).toHaveValue("fr");
    expect(await screen.findByRole("heading", { name: "alika" })).toBeInTheDocument();
  });

  it("filters job history by status, title, and job ID", async () => {
    const pending = { ...doneAlikaSummary, job_id: "pending-1", titles: ["alika"], status: "pending" as const, progress: 0 };
    const running = { ...doneSoaSummary, job_id: "running-2", titles: ["hazakazaka"], status: "running" as const, progress: 50 };
    const done = { ...doneAlikaSummary, job_id: "done-3", titles: ["vita"] };
    const error = { ...doneSoaSummary, job_id: "error-4", titles: ["ratsy"], status: "error" as const, error: "failed" };
    vi.mocked(listPageCheckJobs).mockResolvedValue([pending, running, done, error]);
    render(<I18nProvider><PageCheckWorkspace onMessage={vi.fn()} /></I18nProvider>);

    expect(await screen.findByRole("button", { name: "alika" })).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Sata"), { target: { value: "done" } });
    expect(screen.getByRole("button", { name: "vita" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "alika" })).not.toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Sata"), { target: { value: "all" } });
    fireEvent.change(screen.getByLabelText("Sivana amin'ny lohateny na ID-n'ny asa"), { target: { value: "RUNNING-2" } });
    expect(screen.getByRole("button", { name: "hazakazaka" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "vita" })).not.toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Sivana amin'ny lohateny na ID-n'ny asa"), { target: { value: "RATS" } });
    expect(screen.getByRole("button", { name: "ratsy" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "hazakazaka" })).not.toBeInTheDocument();
  });

  it("shows review handoff state, event ID, and error in selected job details", async () => {
    const reviewJob = {
      ...doneAlika,
      review_queue_state: "failed" as const,
      review_event_id: "page-check:job-1",
      review_queue_error: "review broker unavailable",
    };
    vi.mocked(listPageCheckJobs).mockResolvedValue([doneAlikaSummary]);
    vi.mocked(getPageCheckJob).mockResolvedValue(reviewJob);
    render(<I18nProvider><PageCheckWorkspace onMessage={vi.fn()} /></I18nProvider>);

    fireEvent.click(await screen.findByRole("button", { name: "alika" }));

    expect(await screen.findByText("Fandefasana hojerena")).toBeInTheDocument();
    expect(screen.getByText("Tsy nahomby")).toBeInTheDocument();
    expect(screen.getByText("page-check:job-1")).toBeInTheDocument();
    expect(screen.getByText("review broker unavailable")).toBeInTheDocument();
  });

  it("restores persisted job history after the workspace is remounted", async () => {
    vi.mocked(listPageCheckJobs).mockResolvedValue([doneAlikaSummary]);
    const firstRender = render(<I18nProvider><PageCheckWorkspace onMessage={vi.fn()} /></I18nProvider>);

    expect(await screen.findByText("alika")).toBeInTheDocument();
    firstRender.unmount();

    render(<I18nProvider><PageCheckWorkspace onMessage={vi.fn()} /></I18nProvider>);

    expect(await screen.findByText("alika")).toBeInTheDocument();
    expect(listPageCheckJobs).toHaveBeenCalledTimes(2);
    expect(startPageCheck).not.toHaveBeenCalled();
  });

  it("continues polling an active job restored from history", async () => {
    const runningSummary: PageCheckJobSummary = {
      ...doneAlikaSummary,
      status: "running",
      progress: 45,
      stage: "verifying",
      message: "Comparing the current definitions with their sources.",
      result_counts: { good: 0, fixed: 0, unverifiable: 0, error: 0 },
    };
    vi.mocked(listPageCheckJobs)
      .mockResolvedValueOnce([runningSummary])
      .mockResolvedValue([doneAlikaSummary]);

    render(<I18nProvider><PageCheckWorkspace onMessage={vi.fn()} /></I18nProvider>);

    expect(await screen.findByText("Comparing the current definitions with their sources.")).toBeInTheDocument();
    await waitFor(
      () => expect(screen.getByText("Pejy 1: 1 tsara, 0 voahitsy, 0 tsy voamarina, 0 hadisoana")).toBeInTheDocument(),
      { timeout: 4500 },
    );
    expect(listPageCheckJobs).toHaveBeenCalledTimes(2);
  });

  it("shows the waiting queue and verbose activity for a selected running job", async () => {
    const runningSummary: PageCheckJobSummary = {
      ...doneAlikaSummary,
      status: "running",
      progress: 65,
      stage: "verifying",
      message: "Comparing the current definitions with their sources.",
      result_counts: { good: 0, fixed: 0, unverifiable: 0, error: 0 },
    };
    const pendingSummary: PageCheckJobSummary = {
      ...doneSoaSummary,
      status: "pending",
      progress: 0,
      stage: "queued",
      message: "Waiting for a page-check worker.",
      queue_position: 1,
      result_counts: { good: 0, fixed: 0, unverifiable: 0, error: 0 },
    };
    const runningJob: PageCheckJob = {
      ...alikaJob,
      status: "running",
      progress: 65,
      stage: "verifying",
      message: "Comparing the current definitions with their sources.",
      timeline: [
        { timestamp: 0, stage: "queued", message: "Waiting for a page-check worker." },
        { timestamp: 1, stage: "loading_target", message: "Loading the current Wiktionary page." },
        { timestamp: 2, stage: "verifying", message: "Comparing the current definitions with their sources." },
      ],
    };
    vi.mocked(listPageCheckJobs).mockResolvedValue([runningSummary, pendingSummary]);
    vi.mocked(getPageCheckJob).mockResolvedValue(runningJob);

    render(<I18nProvider><PageCheckWorkspace onMessage={vi.fn()} /></I18nProvider>);

    expect(await screen.findByText("Eo am-panamarinana")).toBeInTheDocument();
    expect(screen.getByText("Pejy miandry")).toBeInTheDocument();
    expect(screen.getByText(/Laharana 1/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /alika/ }));

    expect(await screen.findByText("Dian'ny fanamarinana")).toBeInTheDocument();
    expect(screen.getAllByText("Mampitaha famaritana").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Comparing the current definitions with their sources.").length).toBeGreaterThan(0);
    expect(screen.getByText("65%")).toBeInTheDocument();
  });
});
