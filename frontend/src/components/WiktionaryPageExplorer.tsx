import { useState, type FormEvent } from "react";

import { previewPage } from "../api";
import { useI18n } from "../i18n";
import { useLanguageName } from "../languages";
import type { DescendantNode, JsonValue, ProcessedPageEntry } from "../types";

interface WiktionaryPageExplorerProps {
  onMessage: (message: string, tone?: "success" | "error") => void;
  onOpenLexicon: (word: string) => void;
}

const MAX_DESCENDANT_DEPTH = 32;

function readableValue(value: JsonValue): string {
  if (Array.isArray(value)) return value.map((item) => typeof item === "string" ? item : JSON.stringify(item)).join(", ");
  if (value && typeof value === "object") return JSON.stringify(value, null, 2);
  return String(value ?? "");
}

function DescendantTree({ nodes, onOpenLexicon, path = "root", depth = 0 }: { nodes: DescendantNode[]; onOpenLexicon: (word: string) => void; path?: string; depth?: number }) {
  const { t } = useI18n();
  return (
    <ul className="wiki-descendant-tree" role="list">
      {nodes.map((node, index) => {
        const nodePath = `${path}-${index}`;
        const language = node.lang !== "unknown" ? node.lang : node.lang_code !== "unknown" ? node.lang_code : t("Tsy fantatra", "Unknown");
        const tags = [...new Set([...(node.tags ?? []), ...(node.raw_tags ?? [])])];
        const word = node.word;
        return (
          <li key={nodePath}>
            <div className="wiki-descendant-tree__node" style={{ paddingInlineStart: `${Math.min(depth, 6) * 8}px` }}>
              {depth > 0 && <i className="wiki-descendant-tree__depth" aria-hidden="true">{depth}</i>}
              {word ? <button type="button" onClick={() => onOpenLexicon(word)}>{word}</button> : <strong>{language}</strong>}
              {word && <span>{language}</span>}
              {node.roman && <code>{node.roman}</code>}
              {node.sense && <small>{node.sense}</small>}
              {tags.map((tag) => <em key={`${nodePath}-${tag}`}>{tag}</em>)}
            </div>
            {node.descendants?.length && depth + 1 < MAX_DESCENDANT_DEPTH ? <DescendantTree nodes={node.descendants} onOpenLexicon={onOpenLexicon} path={nodePath} depth={depth + 1} /> : null}
          </li>
        );
      })}
    </ul>
  );
}

function EntryCard({ entry, onOpenLexicon }: { entry: ProcessedPageEntry; onOpenLexicon: (word: string) => void }) {
  const { t } = useI18n();
  const definitions = entry.definitions ?? [];
  const translations = entry.translations ?? [];
  const descendants = entry.descendants ?? [];
  const additionalData = Object.entries(entry.additional_data ?? {});
  const languageName = useLanguageName(entry.language);

  return (
    <article className="wiki-entry-card">
      <header>
        <div>
          <span>{languageName}</span>
          <h3>{entry.entry || t("Teny tsy voatonona", "Unnamed entry")}</h3>
          <p>{entry.part_of_speech || t("Tsy misy sokajin-teny", "No part of speech")}</p>
          {entry.entry && <button className="text-button" type="button" onClick={() => onOpenLexicon(entry.entry!)}>{t("Sokafy ao amin'ny Atlas", "Open in Word Atlas")}</button>}
        </div>
        <div className="wiki-entry-card__counts">
          <strong>{definitions.length}</strong><small>{t("famaritana", "definitions")}</small>
          <strong>{translations.length}</strong><small>{t("dikanteny", "translations")}</small>
        </div>
      </header>

      <div className="wiki-entry-card__columns">
        <section>
          <h4>{t("Famaritana", "Definitions")}</h4>
          {definitions.length ? <ol>{definitions.map((definition, index) => <li key={`${definition}-${index}`}>{definition}</li>)}</ol> : <p className="empty-inline">{t("Tsy misy famaritana.", "No definitions.")}</p>}
        </section>
        <section>
          <h4>{t("Dikanteny", "Translations")}</h4>
          {translations.length ? <ul className="wiki-translation-list">{translations.map((translation, index) => (
            <li key={`${translation.word}-${translation.definition}-${index}`}>
              <strong>{translation.word || translation.definition || "-"}</strong>
              <span>{[translation.language, translation.part_of_speech].filter(Boolean).join(" · ")}</span>
              {translation.word && translation.definition && <p>{translation.definition}</p>}
              {translation.word && <button className="text-button" type="button" onClick={() => onOpenLexicon(translation.word!)}>{t("Atlas-n'ny teny", "Word Atlas")}</button>}
            </li>
          ))}</ul> : <p className="empty-inline">{t("Tsy misy dikanteny.", "No translations.")}</p>}
        </section>
      </div>

      {descendants.length > 0 && (
        <section className="wiki-descendants">
          <h4>{t("Taranaka", "Descendants")}</h4>
          <DescendantTree nodes={descendants} onOpenLexicon={onOpenLexicon} />
        </section>
      )}

      {additionalData.length > 0 && (
        <details className="wiki-additional-data">
          <summary>{t("Angona fanampiny", "Additional data")} ({additionalData.length})</summary>
          <dl>{additionalData.map(([key, value]) => <div key={key}><dt>{key.replaceAll("_", " ")}</dt><dd>{readableValue(value)}</dd></div>)}</dl>
        </details>
      )}
    </article>
  );
}

export function ProcessedEntryList({ entries, onOpenLexicon = () => undefined }: { entries: ProcessedPageEntry[]; onOpenLexicon?: (word: string) => void }) {
  return <div className="wiki-entry-grid">{entries.map((entry, index) => <EntryCard entry={entry} onOpenLexicon={onOpenLexicon} key={`${entry.language}-${entry.part_of_speech}-${index}`} />)}</div>;
}

export function WiktionaryPageExplorer({ onMessage, onOpenLexicon }: WiktionaryPageExplorerProps) {
  const { t } = useI18n();
  const [language, setLanguage] = useState("en");
  const [title, setTitle] = useState("");
  const [entries, setEntries] = useState<ProcessedPageEntry[]>([]);
  const [queriedTitle, setQueriedTitle] = useState("");
  const [loading, setLoading] = useState(false);

  async function queryPage(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    try {
      const result = await previewPage(language.trim(), title.trim());
      setEntries(result);
      setQueriedTitle(title.trim());
      onMessage(t("Voaray ny pejy Wiktionary.", "Wiktionary page loaded."));
    } catch (caught) {
      setEntries([]);
      setQueriedTitle("");
      onMessage(caught instanceof Error ? caught.message : t("Tsy voaray ny pejy Wiktionary.", "Unable to load the Wiktionary page."), "error");
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="wiki-page-explorer panel">
      <div className="wiki-page-explorer__header">
        <div><p className="eyebrow">entry_translator</p><h2>{t("Mpizaha pejy Wiktionary", "Wiktionary page explorer")}</h2><p>{t("Asehoy amin'ny endrika mora vakina ny teny, famaritana, dikanteny ary angona fanampiny voahodina.", "Display processed entries, definitions, translations, and additional data in a readable format.")}</p></div>
        <form onSubmit={(event) => void queryPage(event)}>
          <label className="field field--compact"><span>{t("Fiteny", "Language")}</span><input required maxLength={10} value={language} onChange={(event) => setLanguage(event.target.value)} /></label>
          <label className="field field--grow"><span>{t("Lohatenin'ny pejy", "Page title")}</span><input required value={title} onChange={(event) => setTitle(event.target.value)} placeholder={t("oh: house", "e.g. house")} /></label>
          <button className="button button--primary" type="submit" disabled={loading}>{loading ? t("Maka pejy...", "Loading page...") : t("Hampiseho pejy", "Show page")}</button>
        </form>
      </div>
      {queriedTitle && <div className="wiki-page-explorer__result-title"><span>{t("Pejy", "Page")}</span><strong>{queriedTitle}</strong><small>{t(`Fizarana ${entries.length}`, `${entries.length} sections`)}</small></div>}
      {queriedTitle && entries.length === 0 && <div className="empty-inline">{t("Tsy misy fizarana voahodina hita.", "No processed sections were found.")}</div>}
      <ProcessedEntryList entries={entries} onOpenLexicon={onOpenLexicon} />
    </section>
  );
}
