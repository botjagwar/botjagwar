import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { listRows } from "../api";
import { I18nProvider } from "../i18n";
import type { RelationDefinition } from "../types";
import { RelationBrowser } from "./RelationBrowser";

vi.mock("../api", () => ({
  createRow: vi.fn(),
  deleteRow: vi.fn(),
  listRows: vi.fn().mockResolvedValue({ rows: [], total: 0 }),
  updateRow: vi.fn(),
}));

const relation: RelationDefinition = {
  name: "word",
  label: "Teny",
  group: "Rakibolana",
  kind: "table",
  description: "Teny ao amin'ny rakibolana.",
  searchFields: ["word"],
  identity: ["id"],
  fields: [{ name: "id", kind: "number" }, { name: "word" }],
};

describe("RelationBrowser search", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers();
    window.history.replaceState(null, "", "#relation:word");
  });

  afterEach(() => {
    cleanup();
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it("waits one second after the final keystroke before querying PostgREST", async () => {
    render(<I18nProvider><RelationBrowser relation={relation} onMessage={vi.fn()} onOpenLexicon={vi.fn()} /></I18nProvider>);
    await act(async () => undefined);
    expect(listRows).toHaveBeenCalledTimes(1);

    const input = screen.getByPlaceholderText("Karohy ao amin'ny word");
    fireEvent.change(input, { target: { value: "h" } });
    await act(async () => vi.advanceTimersByTime(700));
    fireEvent.change(input, { target: { value: "house" } });
    await act(async () => vi.advanceTimersByTime(999));
    expect(listRows).toHaveBeenCalledTimes(1);

    await act(async () => vi.advanceTimersByTime(1));
    expect(listRows).toHaveBeenCalledTimes(2);
    expect(listRows).toHaveBeenLastCalledWith(
      relation,
      expect.objectContaining({ search: "house" }),
      expect.any(AbortSignal),
    );
  });

  it("shows full row JSON and never allows all columns to be hidden", async () => {
    vi.mocked(listRows).mockResolvedValueOnce({ rows: [{ id: 1, word: "house", metadata: { languages: ["en"] } }], total: 1 });
    render(<I18nProvider><RelationBrowser relation={relation} onMessage={vi.fn()} onOpenLexicon={vi.fn()} /></I18nProvider>);
    await act(async () => undefined);

    fireEvent.click(screen.getByLabelText("Asehoy ny antsipirian'ny andalana 1"));
    expect(screen.getByText(/"languages": \[/)).toBeInTheDocument();

    fireEvent.click(screen.getByLabelText("id"));
    expect(screen.getByLabelText("id")).not.toBeChecked();
    expect(screen.getByLabelText("word")).toBeDisabled();
  });

  it("exports the current page as JSON and CSV", async () => {
    vi.mocked(listRows).mockResolvedValueOnce({ rows: [{ id: 1, word: "house" }], total: 1 });
    const downloads: string[] = [];
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (this: HTMLAnchorElement) {
      downloads.push(this.download);
    });
    const createObjectURL = vi.fn().mockReturnValue("blob:relation-export");
    const revokeObjectURL = vi.fn();
    Object.defineProperty(URL, "createObjectURL", { configurable: true, value: createObjectURL });
    Object.defineProperty(URL, "revokeObjectURL", { configurable: true, value: revokeObjectURL });

    render(<I18nProvider><RelationBrowser relation={relation} onMessage={vi.fn()} onOpenLexicon={vi.fn()} /></I18nProvider>);
    await act(async () => undefined);
    fireEvent.click(screen.getByRole("button", { name: "JSON" }));
    fireEvent.click(screen.getByRole("button", { name: "CSV" }));

    expect(downloads).toEqual(["word-page-1.json", "word-page-1.csv"]);
    expect(createObjectURL).toHaveBeenCalledTimes(2);
    expect(revokeObjectURL).toHaveBeenCalledTimes(2);
  });

  it("initializes browsing state from the relation hash and replaces it after changes", async () => {
    window.history.replaceState(null, "", "#relation:word?search=house&page=2&pageSize=50&order=word.asc");
    render(<I18nProvider><RelationBrowser relation={relation} onMessage={vi.fn()} onOpenLexicon={vi.fn()} /></I18nProvider>);
    await act(async () => undefined);

    expect(listRows).toHaveBeenCalledWith(
      relation,
      { page: 2, pageSize: 50, search: "house", order: "word.asc" },
      expect.any(AbortSignal),
    );
    fireEvent.change(screen.getByLabelText("Andalana"), { target: { value: "100" } });

    const [route, query] = window.location.hash.slice(1).split("?", 2);
    expect(route).toBe("relation:word");
    const params = new URLSearchParams(query);
    expect(Object.fromEntries(params)).toEqual({ search: "house", page: "0", pageSize: "100", order: "word.asc" });
  });

  it("restores valid relation state from browser history events", async () => {
    render(<I18nProvider><RelationBrowser relation={relation} onMessage={vi.fn()} onOpenLexicon={vi.fn()} /></I18nProvider>);
    await act(async () => undefined);

    window.history.replaceState(null, "", "#relation:word?search=home&page=3&pageSize=10&order=word.desc");
    fireEvent(window, new PopStateEvent("popstate"));
    await act(async () => undefined);

    expect(screen.getByPlaceholderText("Karohy ao amin'ny word")).toHaveValue("home");
    expect(screen.getByLabelText("Andalana")).toHaveValue("10");
    expect(listRows).toHaveBeenLastCalledWith(
      relation,
      { page: 3, pageSize: 10, search: "home", order: "word.desc" },
      expect.any(AbortSignal),
    );
  });

  it("rejects invalid ordering from the relation hash", async () => {
    window.history.replaceState(null, "", "#relation:word?order=secret.sideways");
    render(<I18nProvider><RelationBrowser relation={relation} onMessage={vi.fn()} onOpenLexicon={vi.fn()} /></I18nProvider>);
    await act(async () => undefined);

    expect(listRows).toHaveBeenCalledWith(
      relation,
      expect.objectContaining({ order: "" }),
      expect.any(AbortSignal),
    );
  });
});
