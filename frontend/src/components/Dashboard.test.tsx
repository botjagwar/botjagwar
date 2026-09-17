import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { getDashboardStatistics, getDatabaseStats, getTranslatorHealth } from "../api";
import { I18nProvider } from "../i18n";
import type { DashboardStatistic } from "../types";
import { Dashboard } from "./Dashboard";

vi.mock("../api", () => ({
  getDashboardStatistics: vi.fn(),
  getDatabaseStats: vi.fn(),
  getTranslatorHealth: vi.fn(),
}));

const baseStatistic = {
  period_start: "2026-08-07T00:00:00Z",
  period_end: "2026-08-14T00:00:00Z",
  entry_count: 0,
  translated_languages: [],
  generated_at: "2026-08-14T00:00:00Z",
  missing_timestamp_count: 2,
};

afterEach(() => {
  cleanup();
  window.localStorage.clear();
  vi.clearAllMocks();
  vi.useRealTimers();
});

describe("Atlas dashboard statistics", () => {
  it("renders period counts and switches translated-language rankings", async () => {
    const statistics: DashboardStatistic[] = [
      { ...baseStatistic, period: "last_day", entry_count: 14, translated_languages: [{ language: "fr", english_name: "French", malagasy_name: "Frantsay", translated_entries: 5 }] },
      { ...baseStatistic, period: "last_7_days", entry_count: 72, translated_languages: [{ language: "en", english_name: "English", malagasy_name: "Anglisy", translated_entries: 42 }] },
      { ...baseStatistic, period: "last_week", entry_count: 60 },
      { ...baseStatistic, period: "last_month", entry_count: 280 },
      { ...baseStatistic, period: "year_to_date", entry_count: 1900 },
      { ...baseStatistic, period: "last_year", entry_count: 3100 },
    ];
    vi.mocked(getDatabaseStats).mockResolvedValue([]);
    vi.mocked(getTranslatorHealth).mockResolvedValue({ status: "healthy", jobs: 12, process_running_jobs: 3 });
    vi.mocked(getDashboardStatistics).mockResolvedValue(statistics);

    render(<I18nProvider><Dashboard tableRelations={[]} viewRelations={[]} onOpenRelation={vi.fn()} /></I18nProvider>);

    expect(await screen.findByText("1,900")).toBeInTheDocument();
    expect(screen.getByText("Anglisy")).toBeInTheDocument();
    expect(screen.getByText(/Teny 2 no tsy manana daty namoronana/)).toBeInTheDocument();
    expect(screen.getByText("Asa mandeha: 3")).toBeInTheDocument();

    const lastDayButton = screen.getByRole("button", { name: "24 ora farany" });
    expect(lastDayButton).toHaveAttribute("aria-pressed", "false");
    fireEvent.click(lastDayButton);
    await waitFor(() => expect(screen.getByText("Frantsay")).toBeInTheDocument());
    expect(lastDayButton).toHaveAttribute("aria-pressed", "true");
    expect(screen.queryByText("Anglisy")).not.toBeInTheDocument();
  });

  it("renders fast dashboard data without waiting for statistics", async () => {
    vi.mocked(getDatabaseStats).mockResolvedValue([{ table_name: "word", total_bytes: 1024 }]);
    vi.mocked(getTranslatorHealth).mockResolvedValue({ status: "healthy" });
    vi.mocked(getDashboardStatistics).mockReturnValue(new Promise(() => undefined));

    render(<I18nProvider><Dashboard tableRelations={[]} viewRelations={[]} onOpenRelation={vi.fn()} /></I18nProvider>);

    expect(await screen.findAllByText("word")).toHaveLength(2);
    expect(screen.getByText("Salama")).toBeInTheDocument();
  });

  it("refreshes cached statistics once every five minutes", async () => {
    vi.useFakeTimers();
    vi.mocked(getDatabaseStats).mockResolvedValue([]);
    vi.mocked(getTranslatorHealth).mockResolvedValue({ status: "healthy" });
    vi.mocked(getDashboardStatistics).mockResolvedValue([]);

    render(<I18nProvider><Dashboard tableRelations={[]} viewRelations={[]} onOpenRelation={vi.fn()} /></I18nProvider>);
    await act(async () => undefined);

    expect(getDashboardStatistics).toHaveBeenCalledOnce();
    await act(async () => {
      vi.advanceTimersByTime(299_999);
    });
    expect(getDashboardStatistics).toHaveBeenCalledOnce();
    await act(async () => {
      vi.advanceTimersByTime(1);
    });
    expect(getDashboardStatistics).toHaveBeenCalledTimes(2);
  });

  it("distinguishes loading and stale statistics", async () => {
    vi.mocked(getDatabaseStats).mockResolvedValue([]);
    vi.mocked(getTranslatorHealth).mockResolvedValue({ status: "healthy" });
    let resolveStatistics: ((value: DashboardStatistic[]) => void) | undefined;
    vi.mocked(getDashboardStatistics).mockReturnValue(new Promise((resolve) => {
      resolveStatistics = resolve;
    }));

    render(<I18nProvider><Dashboard tableRelations={[]} viewRelations={[]} onOpenRelation={vi.fn()} /></I18nProvider>);

    expect(screen.getByText("Eo am-pakana ny antontanisa...")).toBeInTheDocument();
    expect(screen.queryByText(/migration 006/)).not.toBeInTheDocument();

    await act(async () => {
      resolveStatistics?.([{ ...baseStatistic, period: "last_7_days" }]);
    });

    expect(screen.getByRole("status")).toHaveTextContent("Lany andro ny antontanisan'ny dashboard");
  });
});
