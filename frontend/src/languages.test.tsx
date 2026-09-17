import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { getLanguages } from "./api";
import { I18nProvider } from "./i18n";
import { LanguageProvider, useLanguageName } from "./languages";

vi.mock("./api", () => ({ getLanguages: vi.fn() }));

function LanguageName({ code }: { code: string }) {
  return <span>{useLanguageName(code)}</span>;
}

describe("LanguageProvider", () => {
  it("uses Malagasy names and keeps the ISO code visible", async () => {
    vi.mocked(getLanguages).mockResolvedValue([{ iso_code: "en", english_name: "English", malagasy_name: "Anglisy" }]);

    render(<I18nProvider><LanguageProvider><LanguageName code="en" /></LanguageProvider></I18nProvider>);

    await waitFor(() => expect(screen.getByText("Anglisy (en)")).toBeInTheDocument());
  });

  it("falls back to an unknown code", () => {
    render(<I18nProvider><LanguageName code="zzz" /></I18nProvider>);
    expect(screen.getByText("zzz")).toBeInTheDocument();
  });
});
