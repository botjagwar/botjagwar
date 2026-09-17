import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { previewPage } from "../api";
import { I18nProvider } from "../i18n";
import type { DescendantNode } from "../types";
import { WiktionaryPageExplorer } from "./WiktionaryPageExplorer";

vi.mock("../api", () => ({ previewPage: vi.fn() }));
afterEach(() => cleanup());

describe("WiktionaryPageExplorer", () => {
  it("renders the processed dictionary page as readable sections", async () => {
    vi.mocked(previewPage).mockResolvedValue([{
      entry: "house",
      language: "en",
      part_of_speech: "noun",
      definitions: ["A building used as a home."],
      translations: [{ word: "trano", language: "mg", part_of_speech: "ana", definition: "A house." }],
      additional_data: { synonyms: ["home"] },
    }]);
    const onOpenLexicon = vi.fn();
    render(<I18nProvider><WiktionaryPageExplorer onMessage={vi.fn()} onOpenLexicon={onOpenLexicon} /></I18nProvider>);

    fireEvent.change(screen.getByLabelText("Lohatenin'ny pejy"), { target: { value: "house" } });
    fireEvent.click(screen.getByRole("button", { name: "Hampiseho pejy" }));

    await waitFor(() => expect(previewPage).toHaveBeenCalledWith("en", "house"));
    expect(await screen.findByRole("heading", { name: "house" })).toBeInTheDocument();
    expect(screen.getByText("A building used as a home.")).toBeInTheDocument();
    expect(screen.getByText("trano")).toBeInTheDocument();
    expect(screen.getByText("synonyms")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Sokafy ao amin'ny Atlas" }));
    expect(onOpenLexicon).toHaveBeenCalledWith("house");
  });

  it("renders recursive descendants while retaining complete flat metadata", async () => {
    vi.mocked(previewPage).mockResolvedValue([{
      entry: "word",
      language: "en",
      part_of_speech: "noun",
      definitions: ["A word."],
      additional_data: { descendant: ["mot", "motet"], synonym: ["term"] },
      descendants: [{
        lang: "Balkan Romance",
        lang_code: "unknown",
        descendants: [{
          lang: "French",
          lang_code: "fr",
          word: "mot",
          roman: "mo",
          sense: "word",
          tags: ["dated"],
          raw_tags: ["dated"],
          descendants: [{ lang: "Middle French", lang_code: "frm", word: "motet" }],
        }],
      }],
    }]);
    const onOpenLexicon = vi.fn();
    render(<I18nProvider><WiktionaryPageExplorer onMessage={vi.fn()} onOpenLexicon={onOpenLexicon} /></I18nProvider>);

    fireEvent.change(screen.getByLabelText("Lohatenin'ny pejy"), { target: { value: "word" } });
    fireEvent.click(screen.getByRole("button", { name: "Hampiseho pejy" }));

    expect(await screen.findByRole("heading", { name: "Taranaka" })).toBeInTheDocument();
    expect(screen.getByText("Balkan Romance")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "mot" })).toBeInTheDocument();
    expect(screen.getByText("mo")).toBeInTheDocument();
    expect(screen.getByText("word", { selector: "small" })).toBeInTheDocument();
    expect(screen.getByText("dated")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "motet" }));
    expect(onOpenLexicon).toHaveBeenCalledWith("motet");
    expect(screen.getByText("descendant")).toBeInTheDocument();
    expect(screen.getByText("mot, motet")).toBeInTheDocument();
    expect(screen.getAllByText("dated")).toHaveLength(1);
    expect(screen.getByText("synonym")).toBeInTheDocument();
  });

  it("bounds recursive descendant rendering", async () => {
    let descendants: DescendantNode[] = [];
    for (let depth = 39; depth >= 0; depth -= 1) {
      descendants = [{ lang: "French", lang_code: "fr", word: `node-${depth}`, descendants }];
    }
    vi.mocked(previewPage).mockResolvedValue([{
      entry: "word",
      language: "en",
      part_of_speech: "noun",
      descendants,
    }]);
    render(<I18nProvider><WiktionaryPageExplorer onMessage={vi.fn()} onOpenLexicon={vi.fn()} /></I18nProvider>);

    fireEvent.change(screen.getByLabelText("Lohatenin'ny pejy"), { target: { value: "word" } });
    fireEvent.click(screen.getByRole("button", { name: "Hampiseho pejy" }));

    expect(await screen.findByRole("button", { name: "node-31" })).toBeInTheDocument();
    expect(screen.getByText("31", { selector: ".wiki-descendant-tree__depth" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "node-32" })).not.toBeInTheDocument();
  });
});
