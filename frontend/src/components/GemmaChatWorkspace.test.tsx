import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { sendGemmaChat } from "../api";
import { I18nProvider } from "../i18n";
import { GemmaChatWorkspace } from "./GemmaChatWorkspace";

vi.mock("../api", () => ({ sendGemmaChat: vi.fn() }));

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("GemmaChatWorkspace", () => {
  it("keeps conversation history in follow-up requests", async () => {
    vi.mocked(sendGemmaChat)
      .mockResolvedValueOnce({ model: "gemma-remote", message: { role: "assistant", content: "First answer" } })
      .mockResolvedValueOnce({ model: "gemma-remote", message: { role: "assistant", content: "Second answer" } });
    render(<I18nProvider><GemmaChatWorkspace /></I18nProvider>);
    const message = screen.getByLabelText("Hafatra");

    fireEvent.change(message, { target: { value: "First question" } });
    fireEvent.click(screen.getByRole("button", { name: /Handefa hafatra/ }));
    expect(await screen.findByText("First answer")).toBeInTheDocument();
    expect(screen.getByText("gemma-remote")).toBeInTheDocument();

    fireEvent.change(message, { target: { value: "Follow up" } });
    fireEvent.keyDown(message, { key: "Enter" });
    expect(await screen.findByText("Second answer")).toBeInTheDocument();
    expect(sendGemmaChat).toHaveBeenLastCalledWith([
      { role: "user", content: "First question" },
      { role: "assistant", content: "First answer" },
      { role: "user", content: "Follow up" },
    ], expect.any(AbortSignal));
  });

  it("shows endpoint errors and can clear the conversation", async () => {
    vi.mocked(sendGemmaChat).mockRejectedValue(new Error("Gemma unavailable"));
    render(<I18nProvider><GemmaChatWorkspace /></I18nProvider>);

    fireEvent.change(screen.getByLabelText("Hafatra"), { target: { value: "Hello" } });
    fireEvent.click(screen.getByRole("button", { name: /Handefa hafatra/ }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Gemma unavailable");
    expect(screen.getByText("Hello")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Hamafa ny resaka" }));
    await waitFor(() => expect(screen.queryByText("Hello")).not.toBeInTheDocument());
    expect(screen.getByText("Inona no tianao ho fantatra?")).toBeInTheDocument();
  });
});
