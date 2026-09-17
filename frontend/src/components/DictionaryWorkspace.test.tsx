import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { getDefinitionImpact, getWord } from "../api";
import { I18nProvider } from "../i18n";
import type { WordRecord } from "../types";
import { DictionaryWorkspace } from "./DictionaryWorkspace";

vi.mock("../api", () => ({
  createWord: vi.fn(),
  deleteWord: vi.fn(),
  getDefinitionImpact: vi.fn(),
  getWord: vi.fn(),
  updateWord: vi.fn(),
}));

const house: WordRecord = {
  id: 7,
  word: "house",
  language: "en",
  part_of_speech: "ana",
  definitions: [{ id: 42, definition: "trano", language: "mg" }],
};

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.resetAllMocks();
});

describe("DictionaryWorkspace", () => {
  it("shows the entries sharing each definition", async () => {
    vi.mocked(getWord).mockResolvedValue([house]);
    vi.mocked(getDefinitionImpact).mockResolvedValue({
      ...house.definitions[0],
      words: [
        { id: 7, word: "house", language: "en", part_of_speech: "ana", additional_data: {} },
        { id: 8, word: "home", language: "en", part_of_speech: "ana", additional_data: {} },
      ],
    });
    render(<I18nProvider><DictionaryWorkspace onMessage={vi.fn()} onOpenLexicon={vi.fn()} /></I18nProvider>);

    fireEvent.change(screen.getByLabelText("Teny fototra"), { target: { value: "house" } });
    fireEvent.click(screen.getByRole("button", { name: "Hikaroka" }));

    await waitFor(() => expect(getDefinitionImpact).toHaveBeenCalledWith(42, expect.any(AbortSignal)));
    expect(await screen.findByText("Famaritana #42: teny 2")).toBeInTheDocument();
    fireEvent.click(screen.getByText("Famaritana #42: teny 2"));
    expect(screen.getByText("home")).toBeInTheDocument();
  });

  it("confirms before discarding a changed entry draft", async () => {
    vi.mocked(getWord).mockResolvedValue([house]);
    vi.mocked(getDefinitionImpact).mockResolvedValue({ ...house.definitions[0], words: [] });
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(false);
    render(<I18nProvider><DictionaryWorkspace onMessage={vi.fn()} onOpenLexicon={vi.fn()} /></I18nProvider>);

    fireEvent.change(screen.getByLabelText("Teny fototra"), { target: { value: "house" } });
    fireEvent.click(screen.getByRole("button", { name: "Hikaroka" }));
    fireEvent.click(await screen.findByRole("button", { name: "Hanova ny teny" }));
    fireEvent.change(screen.getByLabelText("Sokajin-teny"), { target: { value: "mpam" } });
    fireEvent.click(screen.getByRole("button", { name: "Hanafoana" }));

    expect(confirm).toHaveBeenCalledWith("Harianao ve ny fanovana tsy voatahiry?");
    expect(screen.getByLabelText("Sokajin-teny")).toHaveValue("mpam");
  });

  it("ignores definition impact returned for a previously selected entry", async () => {
    const home: WordRecord = {
      ...house,
      id: 8,
      word: "home",
      definitions: [{ id: 43, definition: "fonenana", language: "mg" }],
    };
    let resolveHouseImpact: ((value: Awaited<ReturnType<typeof getDefinitionImpact>>) => void) | undefined;
    vi.mocked(getWord).mockResolvedValue([house, home]);
    vi.mocked(getDefinitionImpact).mockImplementation((definitionId) => {
      if (definitionId === 42) return new Promise((resolve) => { resolveHouseImpact = resolve; });
      return Promise.resolve({ ...home.definitions[0], words: [{ id: 8, word: "home", language: "en", part_of_speech: "ana", additional_data: {} }] });
    });
    render(<I18nProvider><DictionaryWorkspace onMessage={vi.fn()} onOpenLexicon={vi.fn()} /></I18nProvider>);

    fireEvent.change(screen.getByLabelText("Teny fototra"), { target: { value: "house" } });
    fireEvent.click(screen.getByRole("button", { name: "Hikaroka" }));
    await waitFor(() => expect(getDefinitionImpact).toHaveBeenCalledWith(42, expect.any(AbortSignal)));
    fireEvent.click(await screen.findByRole("button", { name: /home/ }));
    expect(await screen.findByText("Famaritana #43: teny 1")).toBeInTheDocument();

    resolveHouseImpact?.({ ...house.definitions[0], words: [{ id: 7, word: "stale", language: "en", part_of_speech: "ana", additional_data: {} }] });
    await waitFor(() => expect(screen.queryByText(/Famaritana #42/)).not.toBeInTheDocument());
    expect(screen.getByText("Famaritana #43: teny 1")).toBeInTheDocument();
  });
});
