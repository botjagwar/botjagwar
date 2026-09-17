import { useEffect, useState, type FormEvent } from "react";

import { createWord, deleteWord, getDefinitionImpact, getWord, updateWord } from "../api";
import { useI18n } from "../i18n";
import { useLanguageName } from "../languages";
import { dictionaryMessages } from "../messages/dictionary";
import type { DefinitionImpactRecord, DefinitionRecord, WordRecord } from "../types";

interface DictionaryWorkspaceProps {
  onMessage: (message: string, tone?: "success" | "error") => void;
  onOpenLexicon: (word: string) => void;
  onDirtyChange?: (dirty: boolean) => void;
}

function emptyWord(language = "en", word = ""): WordRecord {
  return {
    id: 0,
    word,
    language,
    part_of_speech: "ana",
    definitions: [{ id: 0, definition: "", definition_language: "mg" }],
  };
}

export function DictionaryWorkspace({ onMessage, onOpenLexicon, onDirtyChange }: DictionaryWorkspaceProps) {
  const { t } = useI18n();
  const [language, setLanguage] = useState("en");
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<WordRecord[]>([]);
  const [selected, setSelected] = useState<WordRecord | null>(null);
  const [draft, setDraft] = useState<WordRecord | null>(null);
  const [draftBaseline, setDraftBaseline] = useState("");
  const [definitionImpacts, setDefinitionImpacts] = useState<Record<number, DefinitionImpactRecord | null>>({});
  const [impactLoading, setImpactLoading] = useState(false);
  const [impactError, setImpactError] = useState("");
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);
  const selectedLanguageName = useLanguageName(selected?.language);
  const draftDirty = draft !== null && JSON.stringify(draft) !== draftBaseline;

  useEffect(() => {
    if (!draftDirty) return;
    function warnBeforeUnload(event: BeforeUnloadEvent) {
      event.preventDefault();
    }
    window.addEventListener("beforeunload", warnBeforeUnload);
    return () => window.removeEventListener("beforeunload", warnBeforeUnload);
  }, [draftDirty]);

  useEffect(() => {
    onDirtyChange?.(draftDirty);
    return () => onDirtyChange?.(false);
  }, [draftDirty, onDirtyChange]);

  useEffect(() => {
    const definitionIds = selected?.definitions.map((definition) => definition.id).filter((id) => id > 0) ?? [];
    const controller = new AbortController();
    Promise.resolve()
      .then(() => {
        if (controller.signal.aborted) return [];
        setDefinitionImpacts({});
        setImpactLoading(definitionIds.length > 0);
        setImpactError("");
        if (definitionIds.length === 0) return [];
        return Promise.all(definitionIds.map(async (id) => [id, await getDefinitionImpact(id, controller.signal)] as const));
      })
      .then((entries) => { if (!controller.signal.aborted) setDefinitionImpacts(Object.fromEntries(entries)); })
      .catch((caught: unknown) => {
        if (!controller.signal.aborted) setImpactError(caught instanceof Error ? caught.message : t(...dictionaryMessages.definitionImpactLoadError));
      })
      .finally(() => { if (!controller.signal.aborted) setImpactLoading(false); });
    return () => controller.abort();
  }, [selected, t]);

  function beginDraft(nextDraft: WordRecord) {
    setDraft(nextDraft);
    setDraftBaseline(JSON.stringify(nextDraft));
  }

  function discardDraft(): boolean {
    if (draftDirty && !window.confirm(t(...dictionaryMessages.discardUnsavedChanges))) return false;
    setDraft(null);
    setDraftBaseline("");
    return true;
  }

  async function search(event?: FormEvent) {
    event?.preventDefault();
    if (!query.trim()) return;
    if (!discardDraft()) return;
    setLoading(true);
    setSearched(true);
    try {
      const words = await getWord(language.trim(), query.trim());
      setResults(words);
      setSelected(words[0] ?? null);
    } catch (caught) {
      setResults([]);
      setSelected(null);
      onMessage(caught instanceof Error ? caught.message : t("Tsy vita ny fikarohana tao amin'ny rakibolana.", "Unable to search the dictionary."), "error");
    } finally {
      setLoading(false);
    }
  }

  function updateDefinition(index: number, patch: Partial<DefinitionRecord>) {
    if (!draft) return;
    const definitions = draft.definitions.map((definition, current) => current === index ? { ...definition, ...patch } : definition);
    setDraft({ ...draft, definitions });
  }

  async function saveDraft(event: FormEvent) {
    event.preventDefault();
    if (!draft) return;
    setLoading(true);
    try {
      const saved = draft.id ? await updateWord(draft) : await createWord(draft);
      onMessage(draft.id ? t("Voahavaozina ny teny ao amin'ny rakibolana.", "Dictionary entry updated.") : t("Voaforona ny teny ao amin'ny rakibolana.", "Dictionary entry created."));
      const words = await getWord(saved.language, saved.word);
      setResults(words);
      setSelected(words.find((word) => word.id === saved.id) ?? words[0] ?? saved);
      setDraft(null);
      setDraftBaseline("");
      setQuery(saved.word);
    } catch (caught) {
      onMessage(caught instanceof Error ? caught.message : t("Tsy voatahiry ilay teny ao amin'ny rakibolana.", "Unable to save the dictionary entry."), "error");
    } finally {
      setLoading(false);
    }
  }

  async function removeEntry(word: WordRecord) {
    if (!window.confirm(t(`Hofafana ve ny "${word.word}" (${word.part_of_speech})? Hotazonina ireo famaritana.`, `Delete "${word.word}" (${word.part_of_speech})? Definitions will be retained.`))) return;
    setLoading(true);
    try {
      await deleteWord(word.id);
      onMessage(t("Voafafa ilay teny tao amin'ny rakibolana.", "Dictionary entry deleted."));
      setResults((current) => current.filter((result) => result.id !== word.id));
      setSelected(null);
    } catch (caught) {
      onMessage(caught instanceof Error ? caught.message : t("Tsy voafafa ilay teny.", "Unable to delete the entry."), "error");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="dictionary-workspace">
      <section className="dictionary-search panel">
        <div>
          <p className="eyebrow">{t("Fizotran'ny asa manokana", "Domain workflow")}</p>
          <h2>{t("Mitadiava teny ao amin'ny rakibolana", "Find a dictionary entry")}</h2>
          <p>{t("Karohy amin'ny teny fototra marina, avy eo ovay miaraka ireo famaritana rehetra mba hitovy rafitra.", "Search by exact headword, then edit all definitions as one consistent entry.")}</p>
        </div>
        <form onSubmit={(event) => void search(event)}>
          <label className="field field--compact"><span>{t("Fiteny", "Language")}</span><input value={language} onChange={(event) => setLanguage(event.target.value)} maxLength={10} required /></label>
          <label className="field field--grow"><span>{t("Teny fototra", "Headword")}</span><input data-atlas-search value={query} onChange={(event) => setQuery(event.target.value)} placeholder={t("oh: house", "e.g. house")} required /></label>
          <button className="button button--primary" disabled={loading} type="submit">{loading ? t("Mikaroka...", "Searching...") : t("Hikaroka", "Search")}</button>
          <button className="button button--ghost" type="button" onClick={() => { if (draftDirty && !discardDraft()) return; beginDraft(emptyWord(language, query)); setSelected(null); }}>{t("Teny vaovao", "New entry")}</button>
        </form>
      </section>

      <div className="dictionary-content">
        <aside className="result-list panel">
          <div className="panel__header"><div><p className="eyebrow">{t("Valiny", "Results")}</p><h3>{t(`Teny ${results.length}`, `${results.length} entries`)}</h3></div></div>
          {results.map((word) => (
            <button className={selected?.id === word.id ? "result-list__item result-list__item--active" : "result-list__item"} type="button" key={word.id} onClick={() => { if (!discardDraft()) return; setSelected(word); }}>
              <span>{word.language}</span>
              <div><strong>{word.word}</strong><small>{word.part_of_speech} · {t(`famaritana ${word.definitions.length}`, `${word.definitions.length} definitions`)}</small></div>
            </button>
          ))}
          {!results.length && <div className="empty-inline">{searched ? t("Tsy nahitana teny.", "No entries found.") : t("Hiseho eto ny valin'ny fikarohana.", "Search results will appear here.")}</div>}
        </aside>

        <section className="entry-detail panel">
          {draft ? (
            <form onSubmit={(event) => void saveDraft(event)}>
              <div className="panel__header">
                <div><p className="eyebrow">{draft.id ? t(`Teny ${draft.id}`, `Entry ${draft.id}`) : t("Teny vaovao", "New entry")}</p><h3>{draft.id ? draft.word : t("Hamorona teny fototra", "Create a headword")}</h3></div>
                <button className="icon-button" type="button" aria-label={t("Akatona", "Close")} onClick={discardDraft}>×</button>
              </div>
              <div className="form-grid">
                <label className="field"><span>{t("Teny fototra", "Headword")}</span><input value={draft.word} disabled={Boolean(draft.id)} required onChange={(event) => setDraft({ ...draft, word: event.target.value })} /></label>
                <label className="field"><span>{t("Fiteny", "Language")}</span><input value={draft.language} disabled={Boolean(draft.id)} required onChange={(event) => setDraft({ ...draft, language: event.target.value })} /></label>
                <label className="field field--wide"><span>{t("Sokajin-teny", "Part of speech")}</span><input value={draft.part_of_speech} required onChange={(event) => setDraft({ ...draft, part_of_speech: event.target.value })} /></label>
              </div>
              <div className="definition-editor__header"><h4>{t("Famaritana", "Definitions")}</h4><button className="text-button" type="button" onClick={() => setDraft({ ...draft, definitions: [...draft.definitions, { id: 0, definition: "", definition_language: "mg" }] })}>+ {t("Hanampy famaritana", "Add definition")}</button></div>
              <div className="definition-editor">
                {draft.definitions.map((definition, index) => (
                  <div className="definition-editor__row" key={`${definition.id}-${index}`}>
                    <span>{index + 1}</span>
                    <textarea value={definition.definition} required rows={2} onChange={(event) => updateDefinition(index, { definition: event.target.value })} />
                    <input aria-label={t(`Fitenin'ny famaritana ${index + 1}`, `Definition ${index + 1} language`)} value={definition.definition_language ?? definition.language ?? "mg"} required onChange={(event) => updateDefinition(index, { definition_language: event.target.value })} />
                    <button className="icon-button" aria-label={t(`Esory ny famaritana ${index + 1}`, `Remove definition ${index + 1}`)} type="button" disabled={draft.definitions.length === 1} onClick={() => setDraft({ ...draft, definitions: draft.definitions.filter((_, current) => current !== index) })}>×</button>
                  </div>
                ))}
              </div>
              <div className="record-modal__actions"><button className="button button--ghost" type="button" onClick={discardDraft}>{t("Hanafoana", "Cancel")}</button><button className="button button--primary" disabled={loading} type="submit">{t("Hitahiry ny teny", "Save entry")}</button></div>
            </form>
          ) : selected ? (
            <>
              <div className="entry-detail__masthead">
                <div><span>{selected.language}</span><h2>{selected.word}</h2><p>{selectedLanguageName} · {selected.part_of_speech} · {t(`rakitra ${selected.id}`, `record ${selected.id}`)}</p></div>
                <div><button className="button button--ghost" type="button" onClick={() => onOpenLexicon(selected.word)}>{t("Sokafy ao amin'ny Atlas", "Open in Word Atlas")}</button><button className="button button--ghost" type="button" onClick={() => beginDraft(structuredClone(selected))}>{t("Hanova ny teny", "Edit entry")}</button><button className="button button--danger" type="button" onClick={() => void removeEntry(selected)}>{t("Hamafa", "Delete")}</button></div>
              </div>
              <ol className="definition-list">
                {selected.definitions.map((definition) => <li key={definition.id}><span>{definition.language ?? definition.definition_language}</span><p>{definition.definition}</p><small>{t(`Famaritana #${definition.id}`, `Definition #${definition.id}`)}</small></li>)}
              </ol>
              <section className="definition-impact" aria-labelledby="definition-impact-heading">
                <div className="definition-editor__header"><h4 id="definition-impact-heading">{t(...dictionaryMessages.definitionImpact)}</h4>{impactLoading && <span className="spinner" />}</div>
                <p>{t(...dictionaryMessages.definitionImpactHelp)}</p>
                {impactError && <div className="notice notice--error" role="alert">{impactError}</div>}
                {!impactLoading && !impactError && <div className="definition-impact__list">{selected.definitions.map((definition) => {
                  const words = definitionImpacts[definition.id]?.words ?? [];
                  return <details key={definition.id}><summary>{t(`Famaritana #${definition.id}: teny ${words.length}`, `Definition #${definition.id}: ${words.length} entries`)}</summary>{words.length > 0 ? <ul>{words.map((word) => <li key={word.id}><strong>{word.word}</strong><span>{word.language} · {word.part_of_speech} · #{word.id}</span></li>)}</ul> : <p>{t(...dictionaryMessages.noOtherEntries)}</p>}</details>;
                })}</div>}
              </section>
              {selected.additional_data && Object.keys(selected.additional_data).length > 0 && (
                <div className="additional-data"><h4>{t("Angona fanampiny", "Additional data")}</h4><pre>{JSON.stringify(selected.additional_data, null, 2)}</pre></div>
              )}
            </>
          ) : (
            <div className="empty-detail"><span aria-hidden="true">Aa</span><h3>{t("Misafidiana na mamorona teny", "Select or create an entry")}</h3><p>{t("Hiseho eto avokoa ny famaritana sy metadata.", "The full definition set and metadata will appear here.")}</p></div>
          )}
        </section>
      </div>
    </div>
  );
}
