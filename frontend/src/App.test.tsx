import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import App from "./App";
import { getDefinitionImpact, getJsonDictionaryWord, getLexiconWordPreview, getLinkableLexiconWords, getWord } from "./api";
import { I18nProvider } from "./i18n";
import { ThemeProvider } from "./theme";

vi.mock("./api", async (importOriginal) => {
  const original = await importOriginal<typeof import("./api")>();
  return { ...original, configureApi: vi.fn(), getDefinitionImpact: vi.fn(), getJsonDictionaryWord: vi.fn(), getLexiconWordPreview: vi.fn(), getLinkableLexiconWords: vi.fn().mockResolvedValue(new Set()), getWord: vi.fn() };
});

afterEach(() => {
  cleanup();
  window.history.replaceState(null, "", "/");
  vi.restoreAllMocks();
});

describe("App lexicon route", () => {
  it("loads a deep-linked json_dictionary word", async () => {
    window.location.hash = "#lexicon?word=rock+%26+roll";
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response("{}", { status: 500 }));
    vi.mocked(getJsonDictionaryWord).mockResolvedValue([]);

    render(<I18nProvider><App /></I18nProvider>);

    expect(await screen.findByRole("heading", { name: "Atlas-n'ny teny" })).toBeInTheDocument();
    await waitFor(() => expect(getJsonDictionaryWord).toHaveBeenCalledWith("rock & roll", expect.any(AbortSignal)));
    expect(screen.getByLabelText("Teny karohina")).toHaveValue("rock & roll");
  });

  it("focuses the active search field with the global shortcut", async () => {
    window.location.hash = "#lexicon";
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response("{}", { status: 500 }));

    render(<I18nProvider><App /></I18nProvider>);

    const search = await screen.findByLabelText("Teny karohina");
    fireEvent.keyDown(window, { key: "k", ctrlKey: true });
    expect(search).toHaveFocus();
    expect(screen.getByRole("link", { name: "Mankanesa any amin'ny votoaty" })).toHaveAttribute("href", "#atlas-workspace");
    fireEvent.click(screen.getByRole("link", { name: "Mankanesa any amin'ny votoaty" }));
    expect(document.getElementById("atlas-workspace")).toHaveFocus();
    expect(window.location.hash).toBe("#lexicon");
  });

  it("pushes linked words and restores previous words on popstate", async () => {
    window.history.replaceState(null, "", "#lexicon?word=source");
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response("{}", { status: 500 }));
    vi.mocked(getLinkableLexiconWords).mockResolvedValue(new Set(["longword"]));
    vi.mocked(getLexiconWordPreview).mockResolvedValue([]);
    vi.mocked(getJsonDictionaryWord).mockImplementation(async (word) => word === "source" ? [{ id: 1, word: "source", language: "mg", part_of_speech: "ana", definitions: [{ id: 11, definition: "longword", language: "mg" }], additional_data: null }] : []);
    const pushState = vi.spyOn(window.history, "pushState");

    render(<I18nProvider><App /></I18nProvider>);
    const link = await screen.findByRole("link", { name: "longword" });
    fireEvent.click(link);

    await waitFor(() => expect(pushState).toHaveBeenCalledWith(window.history.state, "", "#lexicon?word=longword"));
    expect(window.location.hash).toBe("#lexicon?word=longword");

    pushState.mockClear();
    window.history.replaceState(null, "", "#lexicon?word=source");
    fireEvent(window, new PopStateEvent("popstate"));
    await waitFor(() => expect(screen.getByLabelText("Teny karohina")).toHaveValue("source"));
    expect(pushState).not.toHaveBeenCalled();
  });
});

describe("App settings route", () => {
  it("discards unsaved fields when configuration is reloaded", async () => {
    window.location.hash = "#settings";
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      if (String(input).startsWith("/config.json")) {
        return new Response(JSON.stringify({ postgrestAddresses: ["/api/database"] }), { status: 200 });
      }
      return new Response("{}", { status: 500 });
    });

    render(<ThemeProvider><I18nProvider><App /></I18nProvider></ThemeProvider>);

    const postgrest = await screen.findByDisplayValue("/api/database");
    fireEvent.change(postgrest, { target: { value: "/api/unsaved" } });
    expect(postgrest).toHaveValue("/api/unsaved");
    fireEvent.click(screen.getByRole("button", { name: "Hamerina haka ny fikirana" }));

    expect(await screen.findByDisplayValue("/api/database")).toBeInTheDocument();
    expect(screen.queryByDisplayValue("/api/unsaved")).not.toBeInTheDocument();
  });
});

describe("App Gemma route", () => {
  it("opens the chat workspace from a deep link", async () => {
    window.location.hash = "#gemma";
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response("{}", { status: 500 }));

    render(<I18nProvider><App /></I18nProvider>);

    expect(await screen.findByRole("heading", { name: "Efitra firesahana" })).toBeInTheDocument();
    expect(screen.getByLabelText("Resaka amin'i Gemma")).toBeInTheDocument();
    expect(window.location.hash).toBe("#gemma");
  });
});

describe("App page-check route", () => {
  it("restores a job-center target from the checker hash", async () => {
    window.location.hash = "#checker?language=fr&job=check-1";
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => String(input).startsWith("/config.json")
      ? new Response(JSON.stringify({ postgrestAddresses: ["/api/database"] }), { status: 200 })
      : new Response("{}", { status: 500 }));

    render(<I18nProvider><App /></I18nProvider>);

    expect(await screen.findByLabelText("Fiteny")).toHaveValue("fr");
    expect(window.location.hash).toBe("#checker?language=fr&job=check-1");
    fireEvent.click(screen.getByRole("button", { name: /Topimaso$/ }));
    await waitFor(() => expect(window.location.hash).toBe("#dashboard"));
    fireEvent.click(screen.getByRole("button", { name: /Mpanamarina$/ }));
    await waitFor(() => expect(window.location.hash).toBe("#checker"));
    expect(await screen.findByLabelText("Fiteny")).toHaveValue("mg");
  });
});

describe("App relation route", () => {
  it("falls back to the data explorer for an unknown relation", async () => {
    window.location.hash = "#relation:not-a-real-relation";
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response("{}", { status: 500 }));

    render(<I18nProvider><App /></I18nProvider>);

    expect(await screen.findByRole("heading", { name: "Misafidiana singa iray ao amin'ny schema" })).toBeInTheDocument();
    await waitFor(() => expect(window.location.hash).toBe("#database"));
  });
});

describe("App dirty navigation", () => {
  it("keeps a changed dictionary draft when workspace navigation is cancelled", async () => {
    window.location.hash = "#dictionary";
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => String(input).startsWith("/config.json")
      ? new Response(JSON.stringify({ postgrestAddresses: ["/api/database"] }), { status: 200 })
      : new Response("{}", { status: 500 }));
    vi.mocked(getWord).mockResolvedValue([{ id: 7, word: "house", language: "en", part_of_speech: "ana", definitions: [{ id: 42, definition: "trano", language: "mg" }] }]);
    vi.mocked(getDefinitionImpact).mockResolvedValue({ id: 42, definition: "trano", language: "mg", words: [] });
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(false);
    render(<I18nProvider><App /></I18nProvider>);

    fireEvent.change(await screen.findByLabelText("Teny fototra"), { target: { value: "house" } });
    fireEvent.click(screen.getByRole("button", { name: "Hikaroka" }));
    fireEvent.click(await screen.findByRole("button", { name: "Hanova ny teny" }));
    fireEvent.change(screen.getByLabelText("Sokajin-teny"), { target: { value: "mpam" } });
    fireEvent.click(screen.getByRole("button", { name: /Topimaso$/ }));

    expect(confirm).toHaveBeenCalledWith("Harianao ve ny fanovana tsy voatahiry?");
    expect(screen.getByLabelText("Sokajin-teny")).toHaveValue("mpam");
    expect(window.location.hash).toBe("#dictionary");
  });
});
