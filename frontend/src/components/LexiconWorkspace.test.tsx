import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { getJsonDictionaryRefreshStatus, getJsonDictionaryWord, getLexiconWordPreview, getLinkableLexiconWords, searchJsonDictionary } from "../api";
import { I18nProvider } from "../i18n";
import { LexiconWorkspace } from "./LexiconWorkspace";

vi.mock("../api", () => ({ getJsonDictionaryRefreshStatus: vi.fn().mockResolvedValue(null), getJsonDictionaryWord: vi.fn(), getLexiconWordPreview: vi.fn(), getLinkableLexiconWords: vi.fn().mockResolvedValue(new Set()), searchJsonDictionary: vi.fn() }));

afterEach(() => {
  cleanup();
  window.localStorage.clear();
  vi.clearAllMocks();
});

describe("LexiconWorkspace", () => {
  it("shows the recorded snapshot refresh time", async () => {
    vi.mocked(getJsonDictionaryRefreshStatus).mockResolvedValue({ schema_name: "public", view_name: "json_dictionary", refreshed_at: "2026-08-12T10:00:00Z" });
    render(<I18nProvider><LexiconWorkspace initialWord="" onWordChange={vi.fn()} /></I18nProvider>);
    expect(await screen.findByText(/Nohavaozina:/)).toBeInTheDocument();
  });

  it("groups exact-headword records by language and renders nested data", async () => {
    vi.mocked(getJsonDictionaryWord).mockResolvedValue([
      {
        id: 1,
        word: "house",
        language: "en",
        part_of_speech: "noun",
        definitions: [{ id: 11, definition: "A building used as a home.", language: "en" }],
        additional_data: [{ data_type: "synonyms", data: "home" }],
      },
      {
        id: 2,
        word: "house",
        language: "en",
        part_of_speech: "verb",
        definitions: [{ id: 12, definition: "To provide shelter.", language: "en" }],
        additional_data: null,
      },
      {
        id: 3,
        word: "house",
        language: "fr",
        part_of_speech: "noun",
        definitions: [{ id: 13, definition: "Une maison.", language: "fr" }],
        additional_data: null,
      },
    ]);

    render(<I18nProvider><LexiconWorkspace initialWord="house" onWordChange={vi.fn()} /></I18nProvider>);

    await waitFor(() => expect(getJsonDictionaryWord).toHaveBeenCalledWith("house", expect.any(AbortSignal)));
    expect(await screen.findByRole("heading", { name: "house" })).toBeInTheDocument();
    expect(screen.getAllByRole("heading", { name: "en" })).not.toHaveLength(0);
    expect(screen.getAllByRole("heading", { name: "fr" })).not.toHaveLength(0);
    expect(screen.getAllByText("A building used as a home.")).not.toHaveLength(0);
    expect(screen.getAllByText("To provide shelter.")).not.toHaveLength(0);
    expect(screen.getAllByText("Une maison.")).not.toHaveLength(0);
    const metadata = screen.getAllByText("synonyms")[0].closest("div");
    expect(metadata).not.toBeNull();
    expect(within(metadata!).getByText("home")).toBeInTheDocument();
  });

  it("compares two loaded languages side by side", async () => {
    vi.mocked(getJsonDictionaryWord).mockResolvedValue([
      { id: 1, word: "house", language: "en", part_of_speech: "noun", definitions: [{ id: 11, definition: "A home.", language: "en" }], additional_data: null },
      { id: 2, word: "house", language: "fr", part_of_speech: "noun", definitions: [{ id: 12, definition: "Une maison.", language: "fr" }], additional_data: null },
      { id: 3, word: "house", language: "de", part_of_speech: "noun", definitions: [{ id: 13, definition: "Ein Haus.", language: "de" }], additional_data: null },
    ]);

    render(<I18nProvider><LexiconWorkspace initialWord="house" onWordChange={vi.fn()} /></I18nProvider>);
    const comparison = await screen.findByRole("heading", { name: "Ampitahao ny fiteny" });
    const panel = comparison.closest("section");
    expect(panel).not.toBeNull();
    expect(within(panel!).getByText("A home.")).toBeInTheDocument();
    expect(within(panel!).getByText("Une maison.")).toBeInTheDocument();
    fireEvent.change(within(panel!).getByLabelText("Fiteny faharoa"), { target: { value: "de" } });
    expect(within(panel!).getByText("Ein Haus.")).toBeInTheDocument();
    expect(within(panel!).queryByText("Une maison.")).not.toBeInTheDocument();
    expect(getJsonDictionaryWord).toHaveBeenCalledTimes(1);
  });

  it("links each known word once per definition and opens it inside Atlas", async () => {
    const onWordChange = vi.fn();
    vi.mocked(getLinkableLexiconWords).mockResolvedValue(new Set(["source", "longword", "anotherword", "another longword"]));
    vi.mocked(getLexiconWordPreview).mockResolvedValue([{ id: 2, word: "longword", language: "mg", part_of_speech: "ana", definitions: [{ id: 21, definition: "Preview definition", language: "mg" }], additional_data: null }]);
    vi.mocked(getJsonDictionaryWord).mockResolvedValue([
      {
        id: 1,
        word: "source",
        language: "mg",
        part_of_speech: "ana",
        definitions: [
          { id: 11, definition: "Longword longword, anotherword.", language: "mg" },
          { id: 12, definition: "longword and [[anotherword]]", language: "mg" },
          { id: 13, definition: "another Longword source", language: "mg" },
        ],
        additional_data: null,
      },
    ]);

    render(<I18nProvider><LexiconWorkspace initialWord="source" onWordChange={onWordChange} /></I18nProvider>);

    await screen.findByRole("heading", { name: "source" });
    await waitFor(() => expect(getLinkableLexiconWords).toHaveBeenCalledOnce());
    const definitions = document.querySelector<HTMLElement>(".lexicon-entry-grid .lexicon-definitions");
    expect(definitions).not.toBeNull();
    const items = within(definitions!).getAllByRole("listitem");
    expect(within(items[0]).getAllByRole("link", { name: /longword/i })).toHaveLength(1);
    expect(within(items[0]).getByRole("link", { name: "anotherword" })).toHaveAttribute("href", "#lexicon?word=anotherword");
    expect(within(items[1]).queryByRole("link")).not.toBeInTheDocument();
    expect(within(items[2]).getByRole("link", { name: "another Longword" })).toBeInTheDocument();
    expect(within(items[2]).queryByRole("link", { name: "source" })).not.toBeInTheDocument();

    const link = within(items[0]).getByRole("link", { name: "Longword" });
    fireEvent.focus(link);
    expect(await screen.findByRole("tooltip")).toHaveTextContent("Preview definition");
    expect(link).toHaveAttribute("aria-describedby", screen.getByRole("tooltip").id);
    fireEvent.keyDown(link, { key: "Escape" });
    expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();
    fireEvent.click(link);
    expect(onWordChange).toHaveBeenCalledWith("longword");

    onWordChange.mockClear();
    fireEvent.click(link, { ctrlKey: true });
    expect(onWordChange).not.toHaveBeenCalled();
  });

  it("reports unavailable word links and retries without blocking definitions", async () => {
    vi.mocked(getLinkableLexiconWords)
      .mockRejectedValueOnce(new Error("missing RPC"))
      .mockResolvedValueOnce(new Set(["longword"]));
    vi.mocked(getJsonDictionaryWord).mockResolvedValue([{ id: 1, word: "source", language: "mg", part_of_speech: "ana", definitions: [{ id: 11, definition: "longword", language: "mg" }], additional_data: null }]);

    render(<I18nProvider><LexiconWorkspace initialWord="source" onWordChange={vi.fn()} /></I18nProvider>);

    expect(await screen.findByText("Tsy misy ny rohin-teny")).toBeInTheDocument();
    expect(screen.getByText("longword")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Andramo indray" }));
    expect(await screen.findByText("Vonona ny rohin-teny")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "longword" })).toBeInTheDocument();
  });

  it("exports loaded records and copies the shareable URL", async () => {
    vi.mocked(getJsonDictionaryWord).mockResolvedValue([{ id: 1, word: "house", language: "en", part_of_speech: "noun", definitions: [{ id: 11, definition: "A home.", language: "en" }], additional_data: null }]);
    const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined);
    const createObjectURL = vi.fn().mockReturnValue("blob:atlas-export");
    const revokeObjectURL = vi.fn();
    Object.defineProperty(URL, "createObjectURL", { configurable: true, value: createObjectURL });
    Object.defineProperty(URL, "revokeObjectURL", { configurable: true, value: revokeObjectURL });
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", { configurable: true, value: { writeText } });

    render(<I18nProvider><LexiconWorkspace initialWord="house" onWordChange={vi.fn()} /></I18nProvider>);
    await screen.findByRole("heading", { name: "house" });
    fireEvent.click(screen.getByRole("button", { name: "JSON" }));
    fireEvent.click(screen.getByRole("button", { name: "CSV" }));
    fireEvent.click(screen.getByRole("button", { name: "Hizara" }));

    expect(createObjectURL).toHaveBeenCalledTimes(2);
    expect(click).toHaveBeenCalledTimes(2);
    expect(revokeObjectURL).toHaveBeenCalledTimes(2);
    await waitFor(() => expect(writeText).toHaveBeenCalledWith(window.location.href));
    expect(await screen.findByText("Voakopia ny rohy.")).toBeInTheDocument();
  });

  it("submits trimmed terms to ranked search and opens a result", async () => {
    const onWordChange = vi.fn();
    vi.mocked(searchJsonDictionary).mockResolvedValue({ rows: [{ word: "house", language: "en", part_of_speech: "noun", definition_preview: "A home.", match_field: "word", rank: 5 }], hasMore: false });
    render(<I18nProvider><LexiconWorkspace initialWord="" onWordChange={onWordChange} /></I18nProvider>);

    fireEvent.change(screen.getByLabelText("Teny karohina"), { target: { value: "  house  " } });
    fireEvent.click(screen.getByRole("button", { name: "Hikaroka" }));

    await waitFor(() => expect(searchJsonDictionary).toHaveBeenCalledWith("house", 0, 20, expect.any(AbortSignal)));
    const resultList = document.querySelector<HTMLElement>(".lexicon-search-list");
    expect(resultList).not.toBeNull();
    fireEvent.click(within(resultList!).getByRole("button", { name: /house/ }));
    expect(onWordChange).toHaveBeenCalledWith("house");
  });

  it("persists recent and saved searches and reopens them", async () => {
    vi.mocked(searchJsonDictionary).mockResolvedValue({ rows: [], hasMore: false });
    const first = render(<I18nProvider><LexiconWorkspace initialWord="" onWordChange={vi.fn()} /></I18nProvider>);

    fireEvent.change(screen.getByLabelText("Teny karohina"), { target: { value: "house" } });
    fireEvent.click(screen.getByRole("button", { name: "Hikaroka" }));
    await waitFor(() => expect(searchJsonDictionary).toHaveBeenCalledWith("house", 0, 20, expect.any(AbortSignal)));
    fireEvent.click(screen.getByRole("button", { name: "Tehirizo “house”" }));
    first.unmount();

    render(<I18nProvider><LexiconWorkspace initialWord="" onWordChange={vi.fn()} /></I18nProvider>);
    const saved = screen.getByText("Voatahiry").parentElement;
    expect(saved).not.toBeNull();
    fireEvent.click(within(saved!).getByRole("button", { name: "house" }));
    await waitFor(() => expect(searchJsonDictionary).toHaveBeenCalledTimes(2));
    fireEvent.click(within(saved!).getByRole("button", { name: "Esory house" }));
    expect(within(saved!).queryByRole("button", { name: "house" })).not.toBeInTheDocument();
  });

  it("aborts a superseded ranked search and keeps the newest results", async () => {
    vi.mocked(searchJsonDictionary).mockImplementation((term) => term === "old"
      ? new Promise(() => undefined)
      : Promise.resolve({ rows: [{ word: "new", language: "en", part_of_speech: "ana", definition_preview: "new result", match_field: "word", rank: 5 }], hasMore: false }));
    render(<I18nProvider><LexiconWorkspace initialWord="" onWordChange={vi.fn()} /></I18nProvider>);

    const input = screen.getByLabelText("Teny karohina");
    fireEvent.change(input, { target: { value: "old" } });
    fireEvent.click(screen.getByRole("button", { name: "Hikaroka" }));
    const firstSignal = vi.mocked(searchJsonDictionary).mock.calls[0][3];
    fireEvent.change(input, { target: { value: "new" } });
    fireEvent.submit(input.closest("form")!);

    expect(firstSignal?.aborted).toBe(true);
    expect(await screen.findByText("new result")).toBeInTheDocument();
    expect(screen.queryByText("old result")).not.toBeInTheDocument();
  });
});
