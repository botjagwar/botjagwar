import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { getOperations } from "../api";
import { I18nProvider } from "../i18n";
import type { OperationRecord } from "../types";
import { OperationsWorkspace } from "./OperationsWorkspace";

vi.mock("../api", () => ({ getOperations: vi.fn() }));

const baseOperation: OperationRecord = {
  id: 2,
  accepted_at: "2026-08-13T10:00:00Z",
  completed_at: null,
  username: "alice",
  service: "translator",
  action: "publish",
  resource: "wiktionary-page",
  target: { language: "en", title: "house" },
  changed_fields: [],
  outcome: "pending",
  error_summary: null,
};

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.resetAllMocks();
  window.localStorage.clear();
});

describe("OperationsWorkspace", () => {
  it("preserves pagination and service/outcome filters when refreshing", async () => {
    const olderOperation = { ...baseOperation, id: 1, action: "update" };
    vi.mocked(getOperations)
      .mockResolvedValueOnce({ operations: [baseOperation], next_before: 2 })
      .mockResolvedValueOnce({ operations: [olderOperation], next_before: null })
      .mockResolvedValue({ operations: [baseOperation], next_before: null });

    render(<I18nProvider><OperationsWorkspace /></I18nProvider>);

    expect(await screen.findByText("publish · wiktionary-page")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Hampiseho taloha" }));
    await waitFor(() => expect(getOperations).toHaveBeenLastCalledWith({ before: 2, service: "", outcome: "" }));
    expect(await screen.findByText("update · wiktionary-page")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Tolotra"), { target: { value: "database" } });
    await waitFor(() => expect(getOperations).toHaveBeenLastCalledWith({ service: "database", outcome: "" }, expect.any(AbortSignal)));
    fireEvent.change(screen.getByLabelText("Vokatra"), { target: { value: "failed" } });
    await waitFor(() => expect(getOperations).toHaveBeenLastCalledWith({ service: "database", outcome: "failed" }, expect.any(AbortSignal)));
    const refresh = screen.getByRole("button", { name: "Havaozy" });
    await waitFor(() => expect(refresh).toBeEnabled());
    fireEvent.click(refresh);
    await waitFor(() => expect(getOperations).toHaveBeenLastCalledWith({ service: "database", outcome: "failed" }, expect.any(AbortSignal)));
    expect(getOperations).toHaveBeenCalledTimes(5);
  });

  it("searches loaded records across operation text, target JSON, and errors", async () => {
    const operations: OperationRecord[] = [
      { ...baseOperation, id: 1, action: "action-only", username: "user-1", service: "database" },
      { ...baseOperation, id: 2, action: "resource-match", resource: "resource-only", username: "user-2", service: "database" },
      { ...baseOperation, id: 3, action: "service-match", username: "user-3", service: "supervisor" },
      { ...baseOperation, id: 4, action: "user-match", username: "username-only", service: "database" },
      { ...baseOperation, id: 5, action: "target-match", username: "user-5", service: "database", target: { nested: { value: "target-only" } } },
      { ...baseOperation, id: 6, action: "error-match", username: "user-6", service: "database", error_summary: "error-only" },
    ];
    vi.mocked(getOperations).mockResolvedValue({ operations, next_before: null });
    render(<I18nProvider><OperationsWorkspace /></I18nProvider>);
    await screen.findByText("action-only · wiktionary-page");

    const cases = [
      ["action-only", "action-only · wiktionary-page"],
      ["resource-only", "resource-match · resource-only"],
      ["supervisor", "service-match · wiktionary-page"],
      ["username-only", "user-match · wiktionary-page"],
      ["target-only", "target-match · wiktionary-page"],
      ["error-only", "error-match · wiktionary-page"],
    ];
    for (const [term, heading] of cases) {
      fireEvent.change(screen.getByLabelText("Karohy"), { target: { value: term } });
      expect(screen.getAllByRole("article")).toHaveLength(1);
      expect(screen.getByText(heading)).toBeInTheDocument();
    }
  });

  it("expands accessible record details", async () => {
    const operation = {
      ...baseOperation,
      completed_at: "2026-08-13T10:05:00Z",
      changed_fields: ["definitions", "language"],
      outcome: "failed" as const,
      error_summary: "Publication failed",
    };
    vi.mocked(getOperations).mockResolvedValue({ operations: [operation], next_before: null });
    render(<I18nProvider><OperationsWorkspace /></I18nProvider>);
    await screen.findByText("publish · wiktionary-page");

    const summary = screen.getByText("Antsipiriany");
    const details = summary.closest("details");
    expect(details).not.toHaveAttribute("open");
    fireEvent.click(summary);
    expect(details).toHaveAttribute("open");
    const detailView = within(details as HTMLDetailsElement);
    expect(detailView.getByText("Tanjona JSON")).toBeInTheDocument();
    expect(detailView.getByText(/"title": "house"/)).toBeInTheDocument();
    expect(detailView.getByText("definitions, language")).toBeInTheDocument();
    expect(detailView.getByText("Nekena")).toBeInTheDocument();
    expect(detailView.getByText("Vita")).toBeInTheDocument();
    expect(detailView.getByText("Publication failed")).toBeInTheDocument();
  });

  it("exports only currently filtered loaded records as JSON and CSV", async () => {
    const bobOperation = { ...baseOperation, id: 3, username: "bob", action: "delete" };
    vi.mocked(getOperations).mockResolvedValue({ operations: [baseOperation, bobOperation], next_before: null });
    const blobs: Blob[] = [];
    Object.defineProperty(URL, "createObjectURL", { configurable: true, value: vi.fn((blob: Blob) => { blobs.push(blob); return "blob:operations-export"; }) });
    Object.defineProperty(URL, "revokeObjectURL", { configurable: true, value: vi.fn() });
    const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined);
    render(<I18nProvider><OperationsWorkspace /></I18nProvider>);
    await screen.findByText("publish · wiktionary-page");

    fireEvent.change(screen.getByLabelText("Karohy"), { target: { value: "alice" } });
    fireEvent.click(screen.getByRole("button", { name: "Avoahy JSON" }));
    fireEvent.click(screen.getByRole("button", { name: "Avoahy CSV" }));

    expect(click).toHaveBeenCalledTimes(2);
    expect(blobs).toHaveLength(2);
    expect(JSON.parse(await blobs[0].text())).toEqual([baseOperation]);
    const csv = await blobs[1].text();
    expect(csv).toContain('"alice"');
    expect(csv).not.toContain('"bob"');
    expect(URL.revokeObjectURL).toHaveBeenCalledTimes(2);
  });
});
