import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { changeManagedService, getManagedServices } from "../api";
import { I18nProvider } from "../i18n";
import { ServicesWorkspace } from "./ServicesWorkspace";

vi.mock("../api", () => ({ changeManagedService: vi.fn(), getManagedServices: vi.fn() }));

afterEach(() => {
  vi.useRealTimers();
  cleanup();
  vi.clearAllMocks();
  vi.restoreAllMocks();
});

describe("ServicesWorkspace", () => {
  it("summarises and filters service health", async () => {
    vi.mocked(getManagedServices).mockResolvedValue({ hosts: [
      {
        id: "dictionary",
        label: "Dictionary backend",
        available: true,
        services: [
          { id: "dictionary_service_1", host_id: "dictionary", state: "running", running: true, description: "running", pid: 123, uptime_seconds: 50 },
          { id: "dictionary_service_2", host_id: "dictionary", state: "stopped", running: false, description: "stopped", pid: 0, uptime_seconds: 0 },
        ],
      },
      { id: "translator", label: "Translator backend", available: false, services: [] },
    ] });

    render(<I18nProvider><ServicesWorkspace onMessage={vi.fn()} /></I18nProvider>);

    expect(await screen.findByText("Dictionary backend")).toBeInTheDocument();
    expect(screen.getByText("Hosts mifandray").nextElementSibling).toHaveTextContent("1 / 2");
    expect(screen.getByText("Olana hita").nextElementSibling).toHaveTextContent("1");
    fireEvent.click(screen.getByRole("button", { name: "Mandeha: 1" }));
    expect(screen.getByText("dictionary_service_1")).toBeInTheDocument();
    expect(screen.queryByText("dictionary_service_2")).not.toBeInTheDocument();
    expect(screen.queryByText("Translator backend")).not.toBeInTheDocument();
  });

  it("refreshes service status every 30 seconds", async () => {
    vi.useFakeTimers();
    vi.mocked(getManagedServices).mockResolvedValue({ hosts: [] });

    render(<I18nProvider><ServicesWorkspace onMessage={vi.fn()} /></I18nProvider>);
    await vi.advanceTimersByTimeAsync(0);
    expect(getManagedServices).toHaveBeenCalledTimes(1);
    await vi.advanceTimersByTimeAsync(30_000);
    expect(getManagedServices).toHaveBeenCalledTimes(2);
    vi.useRealTimers();
  });

  it("does not restart polling when the message callback changes", async () => {
    vi.useFakeTimers();
    vi.mocked(getManagedServices).mockRejectedValue(new Error("offline"));

    const { rerender } = render(<I18nProvider><ServicesWorkspace onMessage={vi.fn()} /></I18nProvider>);
    await vi.advanceTimersByTimeAsync(0);
    expect(getManagedServices).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("alert")).toHaveTextContent("offline");
    expect(screen.getByRole("alert")).toHaveTextContent("Haverina ho azy afaka 30 segondra");

    rerender(<I18nProvider><ServicesWorkspace onMessage={vi.fn()} /></I18nProvider>);
    await vi.advanceTimersByTimeAsync(0);
    expect(getManagedServices).toHaveBeenCalledTimes(1);

    await vi.advanceTimersByTimeAsync(30_000);
    expect(getManagedServices).toHaveBeenCalledTimes(2);
  });

  it("does not let an older poll overwrite a newer manual refresh", async () => {
    vi.useFakeTimers();
    let resolveOlderPoll: ((value: Awaited<ReturnType<typeof getManagedServices>>) => void) | undefined;
    vi.mocked(getManagedServices)
      .mockResolvedValueOnce({ hosts: [] })
      .mockImplementationOnce(() => new Promise((resolve) => { resolveOlderPoll = resolve; }))
      .mockResolvedValueOnce({ hosts: [{ id: "fresh", label: "Fresh host", available: true, services: [{ id: "fresh-service", host_id: "fresh", state: "running", running: true, description: "running", pid: 1, uptime_seconds: 1 }] }] });

    render(<I18nProvider><ServicesWorkspace onMessage={vi.fn()} /></I18nProvider>);
    await vi.advanceTimersByTimeAsync(0);
    await vi.advanceTimersByTimeAsync(30_000);
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Hanavao sata" }));
      await Promise.resolve();
    });
    expect(screen.getByText("Fresh host")).toBeInTheDocument();

    resolveOlderPoll?.({ hosts: [{ id: "stale", label: "Stale host", available: true, services: [{ id: "stale-service", host_id: "stale", state: "running", running: true, description: "running", pid: 2, uptime_seconds: 2 }] }] });
    await act(async () => { await Promise.resolve(); });
    expect(screen.getByText("Fresh host")).toBeInTheDocument();
    expect(screen.queryByText("Stale host")).not.toBeInTheDocument();
  });

  it("confirms and starts an allowlisted stopped service", async () => {
    vi.mocked(getManagedServices).mockResolvedValue({ hosts: [{
      id: "dictionary",
      label: "Dictionary backend",
      available: true,
      services: [{ id: "dictionary_service_1", host_id: "dictionary", state: "stopped", running: false, description: "stopped", pid: 0, uptime_seconds: 0 }],
    }] });
    vi.mocked(changeManagedService).mockResolvedValue({ id: "dictionary_service_1", host_id: "dictionary", state: "running", running: true, description: "running", pid: 123, uptime_seconds: 1 });
    vi.spyOn(window, "confirm").mockReturnValue(true);

    render(<I18nProvider><ServicesWorkspace onMessage={vi.fn()} /></I18nProvider>);

    fireEvent.click(await screen.findByRole("button", { name: "Halefa" }));
    await waitFor(() => expect(changeManagedService).toHaveBeenCalledWith("dictionary", "dictionary_service_1", "start"));
    expect(await screen.findByRole("button", { name: "Hajanona" })).toBeInTheDocument();
  });

  it("does not stop a service when confirmation is rejected", async () => {
    vi.mocked(getManagedServices).mockResolvedValue({ hosts: [{
      id: "dictionary",
      label: "Dictionary backend",
      available: true,
      services: [{ id: "dictionary_service_1", host_id: "dictionary", state: "running", running: true, description: "running", pid: 123, uptime_seconds: 50 }],
    }] });
    vi.spyOn(window, "confirm").mockReturnValue(false);

    render(<I18nProvider><ServicesWorkspace onMessage={vi.fn()} /></I18nProvider>);

    fireEvent.click(await screen.findByRole("button", { name: "Hajanona" }));
    expect(changeManagedService).not.toHaveBeenCalled();
  });
});
