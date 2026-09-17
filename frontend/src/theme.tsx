/* eslint-disable react-refresh/only-export-components */
import { createContext, useContext, useLayoutEffect, useState, type ReactNode } from "react";

export type AtlasTheme = "atlas" | "windows-98" | "windows-xp" | "mac-os";

interface ThemeContextValue {
  theme: AtlasTheme;
  setTheme: (theme: AtlasTheme) => void;
}

const STORAGE_KEY = "botjagwar-atlas-theme";
const ThemeContext = createContext<ThemeContextValue | null>(null);

export function getInitialTheme(): AtlasTheme {
  try {
    const storedTheme = window.localStorage.getItem(STORAGE_KEY);
    return storedTheme === "windows-98" || storedTheme === "windows-xp" || storedTheme === "mac-os" ? storedTheme : "atlas";
  } catch {
    return "atlas";
  }
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<AtlasTheme>(getInitialTheme);

  useLayoutEffect(() => {
    document.documentElement.dataset.theme = theme;
    const themeColor = theme === "windows-98" ? "#008080" : theme === "windows-xp" ? "#245edb" : theme === "mac-os" ? "#547da5" : "#17231d";
    document.querySelector<HTMLMetaElement>('meta[name="theme-color"]')?.setAttribute("content", themeColor);
  }, [theme]);

  function setTheme(nextTheme: AtlasTheme) {
    setThemeState(nextTheme);
    try {
      window.localStorage.setItem(STORAGE_KEY, nextTheme);
    } catch {
      // The selected theme still applies for this session when storage is unavailable.
    }
  }

  return <ThemeContext.Provider value={{ theme, setTheme }}>{children}</ThemeContext.Provider>;
}

export function useTheme(): ThemeContextValue {
  const value = useContext(ThemeContext);
  if (!value) throw new Error("useTheme must be used inside ThemeProvider");
  return value;
}
