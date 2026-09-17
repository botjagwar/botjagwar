const PAGE_CHECK_LANGUAGES_KEY = "botjagwar-atlas-page-check-languages";
export const PAGE_CHECK_LANGUAGES_EVENT = "botjagwar:page-check-languages";

export function loadPageCheckLanguages(): string[] {
  try {
    const parsed = JSON.parse(window.sessionStorage.getItem(PAGE_CHECK_LANGUAGES_KEY) ?? "[]") as unknown;
    if (Array.isArray(parsed)) {
      const languages = parsed.filter((value): value is string => typeof value === "string" && Boolean(value.trim())).map((value) => value.trim()).filter((value) => value !== "mg");
      return ["mg", ...new Set(languages)].slice(0, 6);
    }
  } catch {
    // Malagasy remains discoverable when browser storage is unavailable.
  }
  return ["mg"];
}

export function rememberPageCheckLanguage(language: string): void {
  const normalized = language.trim() || "mg";
  const languages = ["mg", ...new Set([normalized, ...loadPageCheckLanguages()].filter((value) => value !== "mg"))].slice(0, 6);
  try {
    window.sessionStorage.setItem(PAGE_CHECK_LANGUAGES_KEY, JSON.stringify(languages));
  } catch {
    // The current event still informs the mounted job center.
  }
  window.dispatchEvent(new CustomEvent(PAGE_CHECK_LANGUAGES_EVENT, { detail: languages }));
}
