import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";

import { formatDate, formatDateTime, getInitialLocale, I18nProvider, translate, useI18n } from "./i18n";

function LanguageProbe() {
  const { locale, setLocale, t } = useI18n();
  return <button type="button" onClick={() => setLocale(locale === "mg" ? "en" : "mg")}>{t("Malagasy", "English")}</button>;
}

describe("Atlas internationalization", () => {
  beforeEach(() => window.localStorage.clear());

  it("uses Malagasy as the source and default language", () => {
    expect(getInitialLocale()).toBe("mg");
    expect(translate("mg", "Fikirana", "Settings")).toBe("Fikirana");
  });

  it("switches immediately and persists English", () => {
    render(<I18nProvider><LanguageProbe /></I18nProvider>);
    fireEvent.click(screen.getByRole("button", { name: "Malagasy" }));

    expect(screen.getByRole("button", { name: "English" })).toBeInTheDocument();
    expect(window.localStorage.getItem("botjagwar-atlas-locale")).toBe("en");
    expect(document.documentElement.lang).toBe("en");
  });

  it("formats dates in day-month-year order in Malagasy", () => {
    expect(formatDate("mg", new Date(Date.UTC(2026, 7, 14)), "UTC")).toBe("14 Aog 2026");
    expect(formatDate("mg", new Date(2026, 7, 14))).toBe("14 Aog 2026");
  });

  it("formats dates and times in day-month-year order in Malagasy", () => {
    expect(formatDateTime("mg", new Date(Date.UTC(2026, 7, 14, 9, 5, 3)), "UTC")).toBe("14 Aog 2026, 09:05:03");
  });

  it("keeps English date formatting unchanged", () => {
    expect(formatDate("en", new Date(Date.UTC(2026, 7, 14)), "UTC")).toBe("8/14/2026");
    expect(formatDateTime("en", new Date(Date.UTC(2026, 7, 14, 9, 5, 3)), "UTC")).toContain("2026");
  });
});
