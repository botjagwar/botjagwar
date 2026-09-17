/* eslint-disable react-refresh/only-export-components */
import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

export type Locale = "mg" | "en";
export type Translate = (malagasy: string, english: string) => string;

interface I18nContextValue {
  locale: Locale;
  setLocale: (locale: Locale) => void;
  t: Translate;
}

const STORAGE_KEY = "botjagwar-atlas-locale";
const I18nContext = createContext<I18nContextValue | null>(null);

export function getInitialLocale(): Locale {
  try {
    return window.localStorage.getItem(STORAGE_KEY) === "en" ? "en" : "mg";
  } catch {
    return "mg";
  }
}

export function translate(locale: Locale, malagasy: string, english: string): string {
  return locale === "mg" ? malagasy : english;
}

const MALAGASY_MONTHS = [
  "Jan",
  "Feb",
  "Mar",
  "Apr",
  "Mey",
  "Jon",
  "Jol",
  "Aog",
  "Sep",
  "Okt",
  "Nov",
  "Des",
];

function malagasyDateParts(value: Date, timeZone?: string) {
  const utc = timeZone === "UTC";
  return {
    year: utc ? value.getUTCFullYear() : value.getFullYear(),
    month: utc ? value.getUTCMonth() : value.getMonth(),
    day: utc ? value.getUTCDate() : value.getDate(),
  };
}

function padTimePart(part: number): string {
  return String(part).padStart(2, "0");
}

export function formatDate(locale: Locale, value: Date, timeZone?: string): string {
  if (locale === "mg") {
    const { year, month, day } = malagasyDateParts(value, timeZone);
    return `${day} ${MALAGASY_MONTHS[month]} ${year}`;
  }
  return value.toLocaleDateString("en", timeZone ? { timeZone } : undefined);
}

export function formatDateTime(locale: Locale, value: Date, timeZone?: string): string {
  if (locale === "mg") {
    const { year, month, day } = malagasyDateParts(value, timeZone);
    const utc = timeZone === "UTC";
    const hours = utc ? value.getUTCHours() : value.getHours();
    const minutes = utc ? value.getUTCMinutes() : value.getMinutes();
    const seconds = utc ? value.getUTCSeconds() : value.getSeconds();
    return `${day} ${MALAGASY_MONTHS[month]} ${year}, ${padTimePart(hours)}:${padTimePart(minutes)}:${padTimePart(seconds)}`;
  }
  return value.toLocaleString("en", timeZone ? { timeZone } : undefined);
}

export function I18nProvider({ children }: { children: ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>(getInitialLocale);

  useEffect(() => {
    document.documentElement.lang = locale;
    document.title = translate(locale, "Botjagwar Atlas - Konsoly fitantanana", "Botjagwar Atlas - Administration console");
  }, [locale]);

  function setLocale(nextLocale: Locale) {
    setLocaleState(nextLocale);
    try {
      window.localStorage.setItem(STORAGE_KEY, nextLocale);
    } catch {
      // The selected language still applies for this session when storage is unavailable.
    }
  }

  const t: Translate = (malagasy, english) => translate(locale, malagasy, english);

  return <I18nContext.Provider value={{ locale, setLocale, t }}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18nContextValue {
  const value = useContext(I18nContext);
  if (!value) throw new Error("useI18n must be used inside I18nProvider");
  return value;
}
