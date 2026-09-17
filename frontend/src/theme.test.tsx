import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { getInitialTheme, ThemeProvider, useTheme } from "./theme";

function ThemeProbe() {
  const { theme, setTheme } = useTheme();
  return <div><output>{theme}</output><button type="button" onClick={() => setTheme("windows-98")}>Windows 98</button><button type="button" onClick={() => setTheme("windows-xp")}>Windows XP</button><button type="button" onClick={() => setTheme("mac-os")}>Mac OS</button></div>;
}

describe("Atlas themes", () => {
  beforeEach(() => {
    window.localStorage.clear();
    delete document.documentElement.dataset.theme;
  });

  afterEach(cleanup);

  it("uses Atlas as the default and ignores unknown stored values", () => {
    window.localStorage.setItem("botjagwar-atlas-theme", "unknown");

    expect(getInitialTheme()).toBe("atlas");
  });

  it("applies and persists the Windows 98 theme", () => {
    render(<ThemeProvider><ThemeProbe /></ThemeProvider>);
    fireEvent.click(screen.getByRole("button", { name: "Windows 98" }));

    expect(screen.getByText("windows-98")).toBeInTheDocument();
    expect(document.documentElement).toHaveAttribute("data-theme", "windows-98");
    expect(window.localStorage.getItem("botjagwar-atlas-theme")).toBe("windows-98");
  });

  it("applies, persists, and restores the Windows XP theme", () => {
    const first = render(<ThemeProvider><ThemeProbe /></ThemeProvider>);
    fireEvent.click(screen.getByRole("button", { name: "Windows XP" }));

    expect(screen.getByText("windows-xp")).toBeInTheDocument();
    expect(document.documentElement).toHaveAttribute("data-theme", "windows-xp");
    expect(window.localStorage.getItem("botjagwar-atlas-theme")).toBe("windows-xp");

    first.unmount();

    render(<ThemeProvider><ThemeProbe /></ThemeProvider>);

    expect(screen.getByText("windows-xp")).toBeInTheDocument();
    expect(document.documentElement).toHaveAttribute("data-theme", "windows-xp");
  });

  it("applies and persists the Mac OS theme", () => {
    render(<ThemeProvider><ThemeProbe /></ThemeProvider>);
    fireEvent.click(screen.getByRole("button", { name: "Mac OS" }));

    expect(screen.getByText("mac-os")).toBeInTheDocument();
    expect(document.documentElement).toHaveAttribute("data-theme", "mac-os");
    expect(window.localStorage.getItem("botjagwar-atlas-theme")).toBe("mac-os");
  });
});
