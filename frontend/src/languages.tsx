/* eslint-disable react-refresh/only-export-components */
import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

import { getLanguages } from "./api";
import { useI18n } from "./i18n";
import type { LanguageRecord } from "./types";

const LanguageContext = createContext<Map<string, LanguageRecord>>(new Map());

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [languages, setLanguages] = useState<Map<string, LanguageRecord>>(new Map());

  useEffect(() => {
    const controller = new AbortController();
    getLanguages(controller.signal)
      .then((records) => setLanguages(new Map(records.map((record) => [record.iso_code, record]))))
      .catch(() => {
        // Language codes remain usable when the optional display-name lookup fails.
      });
    return () => controller.abort();
  }, []);

  return <LanguageContext.Provider value={languages}>{children}</LanguageContext.Provider>;
}

export function useLanguageName(code: string | undefined): string {
  const { locale } = useI18n();
  const languages = useContext(LanguageContext);
  if (!code) return "-";
  const language = languages.get(code);
  const name = locale === "mg" ? language?.malagasy_name ?? language?.english_name : language?.english_name ?? language?.malagasy_name;
  return name ? `${name} (${code})` : code;
}
