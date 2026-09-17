import { startTransition, useEffect, useState, type ReactNode } from "react";
import { useI18n } from "../i18n";

interface NavigationItem {
  id: string;
  label: string;
  eyebrow: string;
}

interface LayoutProps {
  children: ReactNode;
  items: NavigationItem[];
  selected: string;
  title: string;
  subtitle: string;
  onSelect: (id: string) => void;
  utility?: ReactNode;
}

function NavigationIcon({ id }: { id: string }) {
  const drawing = id === "dashboard" ? <><rect x="1" y="2" width="14" height="10" className="win98-icon__light" /><rect x="3" y="4" width="10" height="6" className="win98-icon__screen" /><path d="M6 12h4v2h3v1H3v-1h3z" /></>
    : id === "database" ? <><ellipse cx="8" cy="3" rx="6" ry="2" className="win98-icon__light" /><path d="M2 3v9c0 1 3 2 6 2s6-1 6-2V3c0 1-3 2-6 2S2 4 2 3z" className="win98-icon__blue" /><path d="M2 7c0 1 3 2 6 2s6-1 6-2M2 11c0 1 3 2 6 2s6-1 6-2" className="win98-icon__line" /></>
    : id === "dictionary" || id === "lexicon" ? <><path d="M1 2h6c1 0 1 .5 1 1v11c0-1-1-2-3-2H1z" className="win98-icon__blue" /><path d="M15 2H9c-1 0-1 .5-1 1v11c0-1 1-2 3-2h4z" className="win98-icon__light" /><path d="M3 5h3M3 7h3M10 5h3M10 7h3" className="win98-icon__line" /></>
    : id === "translator" ? <><path d="M1 2h8v10H1z" className="win98-icon__light" /><path d="M7 5h8v9H7z" className="win98-icon__blue" /><path d="M3 5h4M3 7h3M9 8h4M9 10h3" className="win98-icon__line" /></>
    : id === "gemma" ? <><rect x="1" y="2" width="14" height="12" className="win98-icon__dark" /><path d="m3 5 3 2-3 2M7 10h5" className="win98-icon__terminal" /></>
    : id === "checker" ? <><path d="M3 1h8l3 3v11H3z" className="win98-icon__light" /><path d="M11 1v4h3M5 9l2 2 4-5" className="win98-icon__check" /></>
    : id === "services" ? <><rect x="1" y="2" width="14" height="4" className="win98-icon__light" /><rect x="1" y="7" width="14" height="4" className="win98-icon__light" /><rect x="1" y="12" width="14" height="3" className="win98-icon__light" /><path d="M3 4h1M3 9h1M3 13h1" className="win98-icon__green" /></>
    : id === "operations" ? <><path d="M3 2h10v13H3z" className="win98-icon__light" /><path d="M6 1h4v3H6z" className="win98-icon__blue" /><path d="M5 7h6M5 9h6M5 11h4" className="win98-icon__line" /></>
    : <><rect x="2" y="2" width="12" height="12" className="win98-icon__light" /><path d="M4 6h8M4 10h8M7 4v4M10 8v4" className="win98-icon__blue-line" /></>;

  return <span className="primary-nav__icon" aria-hidden="true"><svg viewBox="0 0 16 16" shapeRendering="crispEdges">{drawing}</svg></span>;
}

export function Layout({ children, items, selected, title, subtitle, onSelect, utility }: LayoutProps) {
  const { locale, setLocale, t } = useI18n();
  const [menuOpen, setMenuOpen] = useState(false);

  function select(id: string) {
    startTransition(() => onSelect(id));
    setMenuOpen(false);
  }

  useEffect(() => {
    function handleKeyboard(event: KeyboardEvent) {
      if (event.key === "Escape" && menuOpen) {
        setMenuOpen(false);
        return;
      }
      const target = event.target;
      const editing = target instanceof HTMLElement && target.matches("input, textarea, select, [contenteditable=true]");
      if ((!editing && event.key === "/") || ((event.ctrlKey || event.metaKey) && event.key.toLocaleLowerCase() === "k")) {
        const search = document.querySelector<HTMLInputElement>("[data-atlas-search]");
        if (search) {
          event.preventDefault();
          search.focus();
          search.select();
        }
      }
    }
    window.addEventListener("keydown", handleKeyboard);
    return () => window.removeEventListener("keydown", handleKeyboard);
  }, [menuOpen]);

  return (
    <div className="app-shell">
      <a className="skip-link" href="#atlas-workspace" onClick={(event) => { event.preventDefault(); document.getElementById("atlas-workspace")?.focus(); }}>{t("Mankanesa any amin'ny votoaty", "Skip to content")}</a>
      <aside className={`sidebar ${menuOpen ? "sidebar--open" : ""}`}>
        <div className="brand">
          <div className="brand__mark" aria-hidden="true">BJ</div>
          <div>
            <strong>Botjagwar</strong>
            <span>{t("Konsoly Atlas", "Atlas console")}</span>
          </div>
        </div>
        <nav className="primary-nav" aria-label={t("Fitetezana fototra", "Primary navigation")}>
          {items.map((item) => (
            <button
              className={selected === item.id ? "primary-nav__item primary-nav__item--active" : "primary-nav__item"}
              data-nav-id={item.id}
              key={item.id}
              onClick={() => select(item.id)}
              type="button"
            >
              <NavigationIcon id={item.id} />
              <span className="primary-nav__index">{item.eyebrow}</span>
              {item.label}
            </button>
          ))}
        </nav>
        <div className="sidebar__footer">
          <span className="status-dot" />
          {t("Sehatra misy tolotra telo", "Three-service workspace")}
        </div>
      </aside>

      <main className="main-panel">
        <header className="topbar">
          <button
            type="button"
            className="menu-button"
            aria-label={t("Sokafy na akatona ny fitetezana", "Toggle navigation")}
            aria-expanded={menuOpen}
            onClick={() => setMenuOpen((open) => !open)}
          >
            <span />
            <span />
          </button>
          <div>
            <p className="eyebrow">{t("Fampandehanana", "Operations")} / {items.find((item) => item.id === selected)?.label ?? selected}</p>
            <h1>{title}</h1>
            <p className="topbar__subtitle">{subtitle}</p>
          </div>
          <div className="topbar__controls">
            {utility}
            <div className="locale-switcher" role="group" aria-label={t("Fitenin'ny interface", "Interface language")}>
              <button type="button" className={locale === "mg" ? "locale-switcher__active" : ""} aria-label="Malagasy" aria-pressed={locale === "mg"} onClick={() => setLocale("mg")}><span className="locale-switcher__long">Malagasy</span><span className="locale-switcher__short" aria-hidden="true">MG</span></button>
              <button type="button" className={locale === "en" ? "locale-switcher__active" : ""} aria-label="English" aria-pressed={locale === "en"} onClick={() => setLocale("en")}><span className="locale-switcher__long">English</span><span className="locale-switcher__short" aria-hidden="true">EN</span></button>
            </div>
            <div className="environment-badge">
              <span>{t("Tontolo", "Environment")}</span>
              <strong>{import.meta.env.MODE}</strong>
            </div>
          </div>
        </header>
        <div className="workspace" id="atlas-workspace" tabIndex={-1}>{children}</div>
      </main>
      {menuOpen && <button className="sidebar-scrim" aria-label={t("Akatona ny fitetezana", "Close navigation")} onClick={() => setMenuOpen(false)} />}
    </div>
  );
}
