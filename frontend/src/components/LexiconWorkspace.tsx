import { Fragment, useEffect, useId, useRef, useState, type FormEvent, type KeyboardEvent, type MouseEvent } from "react";

import { getJsonDictionaryRefreshStatus, getJsonDictionaryWord, getLexiconWordPreview, getLinkableLexiconWords, searchJsonDictionary } from "../api";
import { createDefinitionLinkIndex, linkDefinition, type DefinitionLinkIndex } from "../definitionLinks";
import { formatDateTime, useI18n } from "../i18n";
import { useLanguageName } from "../languages";
import type { JsonDictionaryAdditionalData, JsonDictionaryRecord, JsonDictionarySearchResult } from "../types";

interface LexiconWorkspaceProps {
  initialWord: string;
  onWordChange: (word: string) => void;
}

interface SearchHistory {
  recent: string[];
  saved: string[];
}

const SEARCH_HISTORY_KEY = "botjagwar-atlas-lexicon-searches";

/** Load the bounded Word Atlas search history stored by this browser. */
function loadSearchHistory(): SearchHistory {
  try {
    const value = JSON.parse(window.localStorage.getItem(SEARCH_HISTORY_KEY) ?? "{}") as Partial<SearchHistory>;
    return {
      recent: Array.isArray(value.recent) ? value.recent.filter((item): item is string => typeof item === "string").slice(0, 6) : [],
      saved: Array.isArray(value.saved) ? value.saved.filter((item): item is string => typeof item === "string") : [],
    };
  } catch {
    return { recent: [], saved: [] };
  }
}

/** Persist Word Atlas search history when browser storage is available. */
function storeSearchHistory(history: SearchHistory): void {
  try {
    window.localStorage.setItem(SEARCH_HISTORY_KEY, JSON.stringify(history));
  } catch {
    // History remains available for this session when storage is unavailable.
  }
}

/** Add a term once using case-insensitive matching. */
function prependUnique(items: string[], term: string): string[] {
  return [term, ...items.filter((item) => item.toLocaleLowerCase() !== term.toLocaleLowerCase())];
}

/** Download text content without sending dictionary records to another service. */
function downloadFile(contents: string, filename: string, type: string): void {
  const url = URL.createObjectURL(new Blob([contents], { type }));
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

/** Convert exact-headword records to a compact CSV export. */
function recordsToCsv(records: JsonDictionaryRecord[]): string {
  const quote = (value: string | number) => `"${String(value).replaceAll('"', '""')}"`;
  const rows = records.flatMap((record) => record.definitions.map((definition) => [
    record.id,
    record.word,
    record.language,
    record.part_of_speech,
    definition.language ?? definition.definition_language ?? "",
    definition.definition,
  ]));
  return [["record_id", "word", "language", "part_of_speech", "definition_language", "definition"], ...rows].map((row) => row.map(quote).join(",")).join("\n");
}

function LanguageLabel({ code }: { code: string }) {
  return <>{useLanguageName(code)}</>;
}

function groupAdditionalData(items: JsonDictionaryAdditionalData[] | null): Map<string, string[]> {
  const groups = new Map<string, string[]>();
  for (const item of items ?? []) {
    const values = groups.get(item.data_type) ?? [];
    values.push(item.data);
    groups.set(item.data_type, values);
  }
  return groups;
}

/** Build the canonical internal Atlas URL for a headword. */
function lexiconHref(word: string): string {
  return `#lexicon?${new URLSearchParams({ word }).toString()}`;
}

function DefinitionLink({ text, target, onWordChange }: { text: string; target: string; onWordChange: (word: string) => void }) {
  const { t } = useI18n();
  const tooltipId = useId();
  const [open, setOpen] = useState(false);
  const [preview, setPreview] = useState<JsonDictionaryRecord[] | null>(null);
  const [previewState, setPreviewState] = useState<"idle" | "loading" | "ready" | "unavailable">("idle");

  function showPreview(): void {
    setOpen(true);
    if (previewState !== "idle") return;
    setPreviewState("loading");
    getLexiconWordPreview(target)
      .then((records) => { setPreview(records); setPreviewState("ready"); })
      .catch(() => setPreviewState("unavailable"));
  }

  function followLink(event: MouseEvent<HTMLAnchorElement>): void {
    if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    onWordChange(target);
  }

  function handleKeyDown(event: KeyboardEvent<HTMLAnchorElement>): void {
    if (event.key === "Escape") {
      event.preventDefault();
      setOpen(false);
    }
  }

  const firstDefinition = preview?.flatMap((entry) => entry.definitions)[0]?.definition;
  return (
    <span className="lexicon-definition-link" onMouseEnter={showPreview} onMouseLeave={() => setOpen(false)}>
      <a
        href={lexiconHref(target)}
        aria-describedby={open ? tooltipId : undefined}
        onClick={followLink}
        onFocus={showPreview}
        onBlur={() => setOpen(false)}
        onKeyDown={handleKeyDown}
      >{text}</a>
      {open && (
        <span className="lexicon-definition-preview" id={tooltipId} role="tooltip">
          <strong>{target}</strong>
          {previewState === "loading" && <span>{t("Maka topi-maso...", "Loading preview...")}</span>}
          {previewState === "unavailable" && <span>{t("Tsy misy ny topi-maso.", "Preview unavailable.")}</span>}
          {previewState === "ready" && <span>{firstDefinition ?? t("Tsy misy famaritana.", "No definition available.")}</span>}
        </span>
      )}
    </span>
  );
}

/** Link each longest known headword no more than once within one definition. */
function DefinitionLinks({ definition, currentWord, index, onWordChange }: { definition: string; currentWord: string; index: DefinitionLinkIndex; onWordChange: (word: string) => void }) {
  return <>{linkDefinition(definition, currentWord, index).map((segment, segmentIndex) => (
    segment.target
      ? <DefinitionLink text={segment.text} target={segment.target} onWordChange={onWordChange} key={`${segmentIndex}-${segment.target}`} />
      : <Fragment key={segmentIndex}>{segment.text}</Fragment>
  ))}</>;
}

function EntryCard({ entry, linkIndex, onWordChange }: { entry: JsonDictionaryRecord; linkIndex: DefinitionLinkIndex; onWordChange: (word: string) => void }) {
  const { t } = useI18n();
  const additionalData = groupAdditionalData(entry.additional_data);
  const languageName = useLanguageName(entry.language);

  return (
    <article className="lexicon-entry">
      <header>
        <div>
          <span>{entry.part_of_speech}</span>
          <small>{languageName} · {t(`Rakitra #${entry.id}`, `Record #${entry.id}`)}</small>
        </div>
        <strong>{t(`Famaritana ${entry.definitions.length}`, `${entry.definitions.length} definitions`)}</strong>
      </header>
      <ol className="lexicon-definitions">
        {entry.definitions.map((definition) => (
          <li key={definition.id}>
            <span>{definition.language ?? definition.definition_language ?? "-"}</span>
            <p><DefinitionLinks definition={definition.definition} currentWord={entry.word} index={linkIndex} onWordChange={onWordChange} /></p>
          </li>
        ))}
      </ol>
      {additionalData.size > 0 && (
        <details className="lexicon-metadata">
          <summary>{t(`Angona fanampiny ${entry.additional_data?.length ?? 0}`, `${entry.additional_data?.length ?? 0} additional data items`)}</summary>
          <dl>
            {[...additionalData.entries()].map(([type, values]) => (
              <div key={type}>
                <dt>{type}</dt>
                <dd>{values.map((value) => <span key={value}>{value}</span>)}</dd>
              </div>
            ))}
          </dl>
        </details>
      )}
    </article>
  );
}

/** Render one language column in the Word Atlas comparison view. */
function ComparisonColumn({ language, entries, linkIndex, onWordChange }: { language: string; entries: JsonDictionaryRecord[]; linkIndex: DefinitionLinkIndex; onWordChange: (word: string) => void }) {
  const { t } = useI18n();
  const languageName = useLanguageName(language);
  return (
    <article className="lexicon-comparison__column">
      <header><span>{language}</span><div><p className="eyebrow">{t("Fiteny", "Language")}</p><h4>{languageName}</h4></div><strong>{t(`Rakitra ${entries.length}`, `${entries.length} entries`)}</strong></header>
      <div>{entries.map((entry) => <EntryCard entry={entry} linkIndex={linkIndex} onWordChange={onWordChange} key={entry.id} />)}</div>
    </article>
  );
}

export function LexiconWorkspace({ initialWord, onWordChange }: LexiconWorkspaceProps) {
  const { locale, t } = useI18n();
  const initialHistory = loadSearchHistory();
  const [query, setQuery] = useState(initialWord);
  const [results, setResults] = useState<JsonDictionaryRecord[]>([]);
  const [loading, setLoading] = useState(Boolean(initialWord));
  const [error, setError] = useState("");
  const [searchResults, setSearchResults] = useState<JsonDictionarySearchResult[]>([]);
  const [searchPage, setSearchPage] = useState(0);
  const [searchHasMore, setSearchHasMore] = useState(false);
  const [searching, setSearching] = useState(false);
  const [searchTerm, setSearchTerm] = useState("");
  const [refreshedAt, setRefreshedAt] = useState<string | null>(null);
  const [snapshotStale, setSnapshotStale] = useState(false);
  const [recentSearches, setRecentSearches] = useState(initialHistory.recent);
  const [savedSearches, setSavedSearches] = useState(initialHistory.saved);
  const [shareMessage, setShareMessage] = useState("");
  const [comparison, setComparison] = useState<[string, string]>(["", ""]);
  const [linkIndex, setLinkIndex] = useState<DefinitionLinkIndex>(new Map());
  const [linkState, setLinkState] = useState<"loading" | "ready" | "unavailable">("loading");
  const rankedSearchController = useRef<AbortController | null>(null);
  const searched = Boolean(initialWord) || Boolean(searchTerm);
  const fallbackError = t("Tsy vita ny fikarohana tao amin'ny rakibolana JSON.", "Unable to search the JSON dictionary.");

  useEffect(() => {
    let active = true;
    getLinkableLexiconWords().then((words) => {
      if (active) { setLinkIndex(createDefinitionLinkIndex(words)); setLinkState("ready"); }
    }).catch(() => { if (active) setLinkState("unavailable"); });
    return () => { active = false; };
  }, []);

  useEffect(() => () => rankedSearchController.current?.abort(), []);

  function retryDefinitionLinks(): void {
    setLinkState("loading");
    getLinkableLexiconWords()
      .then((words) => { setLinkIndex(createDefinitionLinkIndex(words)); setLinkState("ready"); })
      .catch(() => setLinkState("unavailable"));
  }

  useEffect(() => {
    if (!initialWord) return;

    const controller = new AbortController();
    getJsonDictionaryWord(initialWord, controller.signal)
      .then(setResults)
      .catch((caught: unknown) => {
        if (controller.signal.aborted) return;
        setResults([]);
        setError(caught instanceof Error ? caught.message : fallbackError);
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [fallbackError, initialWord]);

  useEffect(() => {
    const controller = new AbortController();
    getJsonDictionaryRefreshStatus(controller.signal).then((status) => {
      setRefreshedAt(status?.refreshed_at ?? null);
      setSnapshotStale(Boolean(status && Date.now() - new Date(status.refreshed_at).getTime() > 14 * 60 * 60 * 1000));
    }).catch(() => undefined);
    return () => controller.abort();
  }, []);

  /** Run a ranked search and add its term to the recent history. */
  function runSearch(term: string) {
    const word = term.trim();
    if (!word) return;
    setQuery(word);
    setSearchTerm(word);
    setSearchPage(0);
    setSearching(true);
    setError("");
    rankedSearchController.current?.abort();
    const controller = new AbortController();
    rankedSearchController.current = controller;
    const recent = prependUnique(recentSearches, word).slice(0, 6);
    setRecentSearches(recent);
    storeSearchHistory({ recent, saved: savedSearches });
    searchJsonDictionary(word, 0, 20, controller.signal)
      .then((page) => { if (!controller.signal.aborted) { setSearchResults(page.rows); setSearchHasMore(page.hasMore); } })
      .catch((caught: unknown) => { if (!controller.signal.aborted) { setSearchResults([]); setSearchHasMore(false); setError(caught instanceof Error ? caught.message : fallbackError); } })
      .finally(() => { if (!controller.signal.aborted) setSearching(false); });
  }

  /** Submit the current search field. */
  function search(event: FormEvent) {
    event.preventDefault();
    runSearch(query);
  }

  /** Save the active ranked search for future sessions. */
  function saveSearch() {
    if (!searchTerm) return;
    const saved = prependUnique(savedSearches, searchTerm);
    setSavedSearches(saved);
    storeSearchHistory({ recent: recentSearches, saved });
  }

  /** Remove one saved search term. */
  function removeSavedSearch(term: string) {
    const saved = savedSearches.filter((item) => item !== term);
    setSavedSearches(saved);
    storeSearchHistory({ recent: recentSearches, saved });
  }

  /** Share the canonical URL for the selected headword. */
  async function shareWord() {
    if (!initialWord) return;
    const url = window.location.href;
    try {
      if (navigator.share) {
        await navigator.share({ title: `${initialWord} · Botjagwar Atlas`, url });
        setShareMessage(t("Nozaraina ny rohy.", "Link shared."));
      } else {
        await navigator.clipboard.writeText(url);
        setShareMessage(t("Voakopia ny rohy.", "Link copied."));
      }
    } catch (caught) {
      if (caught instanceof DOMException && caught.name === "AbortError") return;
      setShareMessage(t("Tsy voakopia ny rohy.", "Unable to copy the link."));
    }
  }

  function changeSearchPage(page: number) {
    setSearching(true);
    setError("");
    rankedSearchController.current?.abort();
    const controller = new AbortController();
    rankedSearchController.current = controller;
    searchJsonDictionary(searchTerm, page, 20, controller.signal)
      .then((response) => { if (!controller.signal.aborted) { setSearchPage(page); setSearchResults(response.rows); setSearchHasMore(response.hasMore); } })
      .catch((caught: unknown) => { if (!controller.signal.aborted) { setSearchResults([]); setSearchHasMore(false); setError(caught instanceof Error ? caught.message : fallbackError); } })
      .finally(() => { if (!controller.signal.aborted) setSearching(false); });
  }

  const languages = [...new Set(results.map((entry) => entry.language))];
  const comparisonLanguages: [string, string] = [comparison[0] || languages[0] || "", comparison[1] || languages[1] || ""];

  return (
    <div className="lexicon-workspace">
      <section className="lexicon-command panel">
        <div>
          <p className="eyebrow">json_dictionary / ranked search</p>
          <h2>{t("Karohy ny rakibolana manontolo", "Search the complete dictionary")}</h2>
          <p>{t("Ny valiny dia alahatra araka ny teny, fiteny, famaritana, ary angona fanampiny. Sokafy ny valiny iray hahitana ny pejiny amin'ny fiteny rehetra.", "Results are ranked by word, language, definitions, then additional data. Open a result to view its complete cross-language page.")}</p>
        </div>
        <form onSubmit={search}>
          <label className="field field--grow">
            <span>{t("Teny karohina", "Search terms")}</span>
            <input data-atlas-search value={query} onChange={(event) => setQuery(event.target.value)} placeholder={t("oh: house", "e.g. house")} required />
          </label>
          <button className="button button--primary" disabled={searching} type="submit">{searching ? t("Mikaroka...", "Searching...") : t("Hikaroka", "Search")}</button>
        </form>
      </section>

      <div className="lexicon-snapshot notice">
        <strong>{t("Sary raikitra", "Snapshot")}</strong>
        <span>{refreshedAt ? t(`Nohavaozina: ${formatDateTime(locale, new Date(refreshedAt))}`, `Last refreshed: ${formatDateTime(locale, new Date(refreshedAt))}`) : t("Tsy mbola fantatra ny fotoana nanavaozana farany.", "The last refresh time is not yet available.")}</span>
        {snapshotStale && <b>{t("Efa lany andro", "Stale snapshot")}</b>}
        <span className={`lexicon-link-state lexicon-link-state--${linkState}`} role="status">
          {linkState === "loading" && t("Maka rohin-teny...", "Loading word links...")}
          {linkState === "ready" && t("Vonona ny rohin-teny", "Word links ready")}
          {linkState === "unavailable" && <>{t("Tsy misy ny rohin-teny", "Word links unavailable")} <button type="button" onClick={retryDefinitionLinks}>{t("Andramo indray", "Retry")}</button></>}
        </span>
      </div>

      {(recentSearches.length > 0 || savedSearches.length > 0 || searchTerm) && (
        <section className="lexicon-history panel">
          <div className="panel__header"><div><p className="eyebrow">Browser history</p><h3>{t("Fikarohana haingana", "Quick searches")}</h3></div>{searchTerm && !savedSearches.some((item) => item.toLocaleLowerCase() === searchTerm.toLocaleLowerCase()) && <button className="text-button" type="button" onClick={saveSearch}>{t(`Tehirizo “${searchTerm}”`, `Save “${searchTerm}”`)}</button>}</div>
          <div className="lexicon-history__columns">
            <div><h4>{t("Vao haingana", "Recent")}</h4><div className="lexicon-history__list">{recentSearches.map((term) => <button type="button" key={term} onClick={() => runSearch(term)}>{term}</button>)}{!recentSearches.length && <span>{t("Tsy mbola misy", "None yet")}</span>}</div></div>
            <div><h4>{t("Voatahiry", "Saved")}</h4><div className="lexicon-history__list">{savedSearches.map((term) => <span className="lexicon-history__saved" key={term}><button type="button" onClick={() => runSearch(term)}>{term}</button><button type="button" aria-label={t(`Esory ${term}`, `Remove ${term}`)} onClick={() => removeSavedSearch(term)}>×</button></span>)}{!savedSearches.length && <span>{t("Tsy mbola misy", "None yet")}</span>}</div></div>
          </div>
        </section>
      )}

      {error && <div className="notice notice--error" role="alert">{error}</div>}
      {searchResults.length > 0 && (
        <section className="lexicon-search-results panel">
          <div className="panel__header"><div><p className="eyebrow">{t("Valin'ny fikarohana", "Search results")}</p><h3>{searchTerm}</h3></div><span>{t(`Pejy ${searchPage + 1}`, `Page ${searchPage + 1}`)}</span></div>
          <div className="lexicon-search-list">
            {searchResults.map((result) => <button type="button" key={`${result.word}-${result.language}-${result.part_of_speech}-${result.match_field}`} onClick={() => onWordChange(result.word)}><span>{result.match_field}</span><div><strong>{result.word}</strong><small><LanguageLabel code={result.language} /> · {result.part_of_speech}</small><p>{result.definition_preview}</p></div><b>↗</b></button>)}
          </div>
          <footer className="pagination"><span>{t(`Valiny ${searchResults.length}`, `${searchResults.length} results`)}</span><div><button type="button" disabled={searchPage === 0 || searching} onClick={() => changeSearchPage(searchPage - 1)}>{t("Teo aloha", "Previous")}</button><button type="button" disabled={!searchHasMore || searching} onClick={() => changeSearchPage(searchPage + 1)}>{t("Manaraka", "Next")}</button></div></footer>
        </section>
      )}
      {loading && <div className="lexicon-state panel"><span className="spinner" />{t("Maka ny fiteny sy famaritana...", "Loading languages and definitions...")}</div>}

      {!loading && !error && results.length > 0 && (
        <section className="lexicon-results">
          <header className="lexicon-summary panel">
            <div><p className="eyebrow">{t("Teny voafantina", "Selected headword")}</p><h2>{results[0].word}</h2></div>
            <div><strong>{languages.length}</strong><span>{t("fiteny", "languages")}</span></div>
            <div><strong>{results.length}</strong><span>{t("rakitra", "entries")}</span></div>
            <div><strong>{results.reduce((total, entry) => total + entry.definitions.length, 0)}</strong><span>{t("famaritana", "definitions")}</span></div>
            <nav className="lexicon-actions" aria-label={t("Fanondranana sy fizarana", "Export and sharing")}>
              <button type="button" onClick={() => downloadFile(JSON.stringify(results, null, 2), `${initialWord}.json`, "application/json")}>JSON</button>
              <button type="button" onClick={() => downloadFile(recordsToCsv(results), `${initialWord}.csv`, "text/csv;charset=utf-8")}>CSV</button>
              <button type="button" onClick={() => void shareWord()}>{t("Hizara", "Share")}</button>
            </nav>
          </header>

          {shareMessage && <div className="notice" role="status">{shareMessage}</div>}

          {languages.length > 1 && (
            <section className="lexicon-comparison panel">
              <div className="panel__header"><div><p className="eyebrow">Side by side</p><h3>{t("Ampitahao ny fiteny", "Compare languages")}</h3></div><span>{t("Rakitra efa voaray", "Uses loaded records")}</span></div>
              <div className="lexicon-comparison__controls">
                <label className="field"><span>{t("Fiteny voalohany", "First language")}</span><select value={comparisonLanguages[0]} onChange={(event) => setComparison([event.target.value, comparisonLanguages[1]])}>{languages.map((language) => <option value={language} key={language}>{language}</option>)}</select></label>
                <span aria-hidden="true">⇄</span>
                <label className="field"><span>{t("Fiteny faharoa", "Second language")}</span><select value={comparisonLanguages[1]} onChange={(event) => setComparison([comparisonLanguages[0], event.target.value])}>{languages.map((language) => <option value={language} key={language}>{language}</option>)}</select></label>
              </div>
              <div className="lexicon-comparison__grid">
                <ComparisonColumn language={comparisonLanguages[0]} entries={results.filter((entry) => entry.language === comparisonLanguages[0])} linkIndex={linkIndex} onWordChange={onWordChange} />
                <ComparisonColumn language={comparisonLanguages[1]} entries={results.filter((entry) => entry.language === comparisonLanguages[1])} linkIndex={linkIndex} onWordChange={onWordChange} />
              </div>
            </section>
          )}

          <div className="lexicon-languages">
            {languages.map((language, index) => {
              const entries = results.filter((entry) => entry.language === language);
              const languageName = <LanguageLabel code={language} />;
              return (
                <section className="lexicon-language panel" key={language}>
                  <header>
                    <span>{String(index + 1).padStart(2, "0")}</span>
                    <div><p className="eyebrow">{t("Fiteny", "Language")}</p><h3>{languageName}</h3></div>
                    <small>{t(`Sokajin-teny ${entries.length}`, `${entries.length} parts of speech`)}</small>
                  </header>
                  <div className="lexicon-entry-grid">{entries.map((entry) => <EntryCard entry={entry} linkIndex={linkIndex} onWordChange={onWordChange} key={entry.id} />)}</div>
                </section>
              );
            })}
          </div>
        </section>
      )}

      {!loading && !error && !results.length && (
        <section className="lexicon-empty panel">
          <span aria-hidden="true">Aa</span>
          <h3>{searched ? t("Tsy nahitana io teny io", "No matching headword") : t("Mitadiava teny iray", "Look up a headword")}</h3>
          <p>{searched ? t("Tsy misy rakitra mitovy tanteraka ao amin'ny json_dictionary.", "No exact match exists in json_dictionary.") : t("Hiseho eto ireo fiteny rehetra mampiasa ilay teny sy ny famaritany.", "Every language using that word and its definitions will appear here.")}</p>
        </section>
      )}
    </div>
  );
}
