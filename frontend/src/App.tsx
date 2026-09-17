import { useEffect, useRef, useState } from "react";

import { configureApi } from "./api";
import { Dashboard } from "./components/Dashboard";
import { DictionaryWorkspace } from "./components/DictionaryWorkspace";
import { JobCenter, type JobCenterNavigationTarget } from "./components/JobCenter";
import { Layout } from "./components/Layout";
import { LexiconWorkspace } from "./components/LexiconWorkspace";
import { RelationBrowser } from "./components/RelationBrowser";
import { ServicesWorkspace } from "./components/ServicesWorkspace";
import { OperationsWorkspace } from "./components/OperationsWorkspace";
import { TranslatorWorkspace } from "./components/TranslatorWorkspace";
import { PageCheckWorkspace } from "./components/PageCheckWorkspace";
import { WiktionaryPageExplorer } from "./components/WiktionaryPageExplorer";
import { SettingsWorkspace } from "./components/SettingsWorkspace";
import { GemmaChatWorkspace } from "./components/GemmaChatWorkspace";
import { clearConfigOverride, loadConfig, saveConfig, type AtlasConfig } from "./config";
import { useI18n } from "./i18n";
import { LanguageProvider } from "./languages";
import { appMessages } from "./messages/app";
import { buildRelationCatalog, relationByName as defaultRelationByName, relationGroups } from "./schema";
import { TranslationJobsProvider } from "./translationJobs";

type Toast = { id: number; message: string; tone: "success" | "error" };

function hashState(): { checkerJobId: string; checkerLanguage: string; route: string; word: string } {
  const [hashRoute, query = ""] = window.location.hash.slice(1).split("?", 2);
  const relationName = hashRoute?.startsWith("relation:") ? hashRoute.slice("relation:".length) : "";
  const route = hashRoute && (["dashboard", "database", "dictionary", "lexicon", "translator", "gemma", "checker", "services", "operations", "settings"].includes(hashRoute) || defaultRelationByName.has(relationName)) ? hashRoute : relationName ? "database" : "dashboard";
  const params = new URLSearchParams(query);
  return {
    checkerJobId: route === "checker" ? params.get("job")?.trim() ?? "" : "",
    checkerLanguage: route === "checker" ? params.get("language")?.trim() || "mg" : "mg",
    route,
    word: route === "lexicon" ? params.get("word")?.trim() ?? "" : "",
  };
}

export default function App() {
  const { t } = useI18n();
  const navigation = [
    { id: "dashboard", label: t("Topimaso", "Overview"), eyebrow: "01" },
    { id: "database", label: t("Mpizaha angona", "Data explorer"), eyebrow: "02" },
    { id: "dictionary", label: t("Rakibolana", "Dictionary"), eyebrow: "03" },
    { id: "lexicon", label: t("Atlas-n'ny teny", "Word Atlas"), eyebrow: "04" },
    { id: "translator", label: t("Mpandika teny", "Translator"), eyebrow: "05" },
    { id: "gemma", label: "Gemma", eyebrow: "06" },
    { id: "checker", label: t("Mpanamarina", "Page checker"), eyebrow: "07" },
    { id: "services", label: t("Tolotra", "Services"), eyebrow: "08" },
    { id: "operations", label: t("Dian'ny asa", "Operations"), eyebrow: "09" },
    { id: "settings", label: t("Fikirana", "Settings"), eyebrow: "10" },
  ];
  const { relationByName, relations, tableRelations, viewRelations } = buildRelationCatalog(t);
  const [route, setRoute] = useState(() => hashState().route);
  const [lexiconWord, setLexiconWord] = useState(() => hashState().word);
  const [checkerJobId, setCheckerJobId] = useState(() => hashState().checkerJobId);
  const [checkerLanguage, setCheckerLanguage] = useState(() => hashState().checkerLanguage);
  const [checkerWorkspaceVersion, setCheckerWorkspaceVersion] = useState(0);
  const [catalogQuery, setCatalogQuery] = useState("");
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [config, setConfig] = useState<AtlasConfig | null>(null);
  const [configRevision, setConfigRevision] = useState(0);
  const [navigationDirty, setNavigationDirty] = useState(false);
  const initialHistorySync = useRef(true);
  const lastAcceptedHash = useRef(window.location.hash || "#dashboard");
  const relation = route.startsWith("relation:") ? relationByName.get(route.slice("relation:".length)) : undefined;
  const writableTableCount = tableRelations.filter((item) => !item.readOnly).length;

  useEffect(() => {
    const params = new URLSearchParams();
    if (route === "lexicon" && lexiconWord) params.set("word", lexiconWord);
    if (route === "checker" && checkerJobId) {
      params.set("language", checkerLanguage);
      params.set("job", checkerJobId);
    }
    const [currentRoute, currentQuery = ""] = window.location.hash.slice(1).split("?", 2);
    const preservedQuery = !["lexicon", "checker"].includes(route) && currentRoute === route ? currentQuery : "";
    const query = params.size ? params.toString() : preservedQuery;
    const nextHash = `#${route}${query ? `?${query}` : ""}`;
    if (window.location.hash !== nextHash) {
      window.history[initialHistorySync.current ? "replaceState" : "pushState"](window.history.state, "", nextHash);
    }
    lastAcceptedHash.current = nextHash;
    initialHistorySync.current = false;
  }, [checkerJobId, checkerLanguage, route, lexiconWord]);

  useEffect(() => {
    function syncHash() {
      const next = hashState();
      const changesWorkspace = next.route !== route || (next.route === "lexicon" && next.word !== lexiconWord);
      if (navigationDirty && changesWorkspace && !window.confirm(t(...appMessages.discardUnsavedChanges))) {
        window.history.pushState(window.history.state, "", lastAcceptedHash.current);
        return;
      }
      if (changesWorkspace) setNavigationDirty(false);
      setRoute(next.route);
      setLexiconWord(next.word);
      setCheckerJobId(next.checkerJobId);
      setCheckerLanguage(next.checkerLanguage);
      if (next.route === "checker") setCheckerWorkspaceVersion((current) => current + 1);
      lastAcceptedHash.current = window.location.hash;
    }
    window.addEventListener("hashchange", syncHash);
    window.addEventListener("popstate", syncHash);
    return () => {
      window.removeEventListener("hashchange", syncHash);
      window.removeEventListener("popstate", syncHash);
    };
  }, [lexiconWord, navigationDirty, route, t]);

  useEffect(() => {
    if (navigationDirty) lastAcceptedHash.current = window.location.hash;
  }, [navigationDirty]);

  useEffect(() => {
    loadConfig().then((loaded) => {
      configureApi(loaded);
      setConfig(loaded);
    });
  }, []);

  function message(text: string, tone: "success" | "error" = "success") {
    const id = Date.now();
    setToasts((current) => [...current, { id, message: text, tone }]);
    window.setTimeout(() => setToasts((current) => current.filter((toast) => toast.id !== id)), 4500);
  }

  function openLexicon(word: string) {
    if (navigationDirty && !window.confirm(t(...appMessages.discardUnsavedChanges))) return;
    setNavigationDirty(false);
    setLexiconWord(word);
    setRoute("lexicon");
  }

  function selectRoute(nextRoute: string): boolean {
    if (nextRoute === route) return true;
    if (navigationDirty && !window.confirm(t(...appMessages.discardUnsavedChanges))) return false;
    setNavigationDirty(false);
    if (nextRoute === "checker") {
      setCheckerLanguage("mg");
      setCheckerJobId("");
    }
    setRoute(nextRoute);
    return true;
  }

  function updateCheckerTarget(language: string, jobId: string) {
    setCheckerLanguage(language);
    setCheckerJobId(jobId);
  }

  function openJobCenterTarget(target: JobCenterNavigationTarget) {
    if (!selectRoute(target.route)) return;
    if (target.route === "checker") {
      setCheckerLanguage(target.language || "mg");
      setCheckerJobId(target.jobId || "");
      setCheckerWorkspaceVersion((current) => current + 1);
    }
  }

  async function reloadConfiguration() {
    const loaded = await loadConfig();
    configureApi(loaded);
    setConfig(loaded);
    setConfigRevision((current) => current + 1);
    message(t("Naverina nalaina ny fikirakirana Atlas.", "Atlas configuration reloaded."));
  }

  const title = relation?.label ?? navigation.find((item) => item.id === route)?.label ?? t("Mpizaha angona", "Data explorer");
  const subtitle = relation?.description ?? (route === "dashboard" ? t("Topazo maso ny fahasalaman'ny banky angona, ny fitehirizana ary ny asan'ny tolotra.", "View database health, storage, and service activity at a glance.") : route === "dictionary" ? t("Tantano amin'ny alalan'ny dictionary_service ny teny sy ny famaritana rehetra ao aminy.", "Manage complete word entries through dictionary_service.") : route === "lexicon" ? t("Karohy araka ny lanjan'ny saha ny rakibolana JSON ary sokafy ny pejin'ny teny amin'ny fiteny rehetra.", "Search the JSON dictionary by weighted field relevance and open cross-language word pages.") : route === "translator" ? t("Tantano ny fizotran'ny fandikana sy famoahana teny.", "Operate the entry translation and publishing pipeline.") : route === "gemma" ? t("Miresaha amin'ny modely Gemma lavitra amin'ny alalan'ny fifandraisana voaaro.", "Chat with the remote Gemma model through the protected server connection.") : route === "checker" ? t("Hamarinina ny famaritana malagasy amin'ny loharano ary hofoanana ny diso.", "Verify Malagasy definitions against their sources and fix wrong ones.") : route === "services" ? t("Jereo ary fehezo ireo tolotra Supervisor navela manokana amin'ny mpizara lavitra.", "Inspect and control explicitly allowlisted Supervisor services on remote hosts.") : route === "operations" ? t("Zahao ny firaketana maharitra momba ny fanovana sy ny asa ivelany rehetra.", "Review the persistent record of mutations and external operations.") : route === "settings" ? t("Amboary ny fahitana ny banky angona sy ny adiresy failover an'ireo tolotra.", "Configure database visibility and service failover addresses.") : t("Zahao ireo tabilao, materialized views ary tatitra rehetra asehon'ny PostgREST.", "Browse all tables, materialized views, and reports exposed by PostgREST."));

  const filteredRelations = relations.filter((item) => `${item.label} ${item.name} ${item.group}`.toLowerCase().includes(catalogQuery.toLowerCase()));
  const groups = relationGroups(filteredRelations);

  if (!config) {
    return <div className="bootstrap-screen"><span className="spinner" /><strong>{t("Maka ny fikirakirana Atlas...", "Loading Atlas configuration...")}</strong></div>;
  }

  return (
    <TranslationJobsProvider onMessage={message}><LanguageProvider><Layout items={navigation} selected={relation ? "database" : route} title={title} subtitle={subtitle} onSelect={selectRoute} utility={<JobCenter onNavigate={openJobCenterTarget} />}>
      {route === "dashboard" && <Dashboard tableRelations={tableRelations} viewRelations={viewRelations} onOpenRelation={(name) => selectRoute(`relation:${name}`)} />}
      {route === "dictionary" && <DictionaryWorkspace onMessage={message} onOpenLexicon={openLexicon} onDirtyChange={setNavigationDirty} />}
      {route === "lexicon" && <LexiconWorkspace key={lexiconWord} initialWord={lexiconWord} onWordChange={setLexiconWord} />}
      {route === "translator" && <TranslatorWorkspace onMessage={message} onOpenLexicon={openLexicon} />}
      {route === "gemma" && <GemmaChatWorkspace />}
      {route === "checker" && <PageCheckWorkspace key={checkerWorkspaceVersion} initialJobId={checkerJobId} initialLanguage={checkerLanguage} onMessage={message} onTargetChange={updateCheckerTarget} />}
      {route === "services" && <ServicesWorkspace onMessage={message} />}
      {route === "operations" && <OperationsWorkspace />}
      {route === "settings" && <SettingsWorkspace key={configRevision} config={config} onSave={(updated) => { const saved = saveConfig(updated); configureApi(saved); setConfig(saved); setConfigRevision((current) => current + 1); message(t("Voatahiry ny fikirana Atlas.", "Atlas settings saved.")); }} onReload={reloadConfiguration} onMessage={message} onReset={() => { clearConfigOverride(); loadConfig().then((deployed) => { configureApi(deployed); setConfig(deployed); setConfigRevision((current) => current + 1); message(t("Naverina ny sanda mahazatra an'ny deployment.", "Deployment defaults restored.")); }); }} />}
      {(route === "database" || relation) && (
        <div className="data-explorer-stack">
          <WiktionaryPageExplorer onMessage={message} onOpenLexicon={openLexicon} />
          <div className="catalog-layout">
          <aside className="catalog-sidebar panel">
            <label className="search-control search-control--catalog"><span aria-hidden="true">⌕</span><input value={catalogQuery} onChange={(event) => setCatalogQuery(event.target.value)} placeholder={t("Sivano ny schema", "Filter schema")} /></label>
            <div className="catalog-sidebar__count">{t(`Tabilao ${writableTableCount} azo ovana · singa ${relations.length}`, `${writableTableCount} writable tables · ${relations.length} relations`)}</div>
            <div className="catalog-groups">
              {[...groups.entries()].map(([group, items]) => (
                <section key={group}>
                  <h3>{group}</h3>
                  {items.map((item) => (
                    <button className={relation?.name === item.name ? "catalog-link catalog-link--active" : "catalog-link"} type="button" key={item.name} onClick={() => selectRoute(`relation:${item.name}`)}>
                      <span className={`catalog-link__kind catalog-link__kind--${item.kind}`} />
                      <div><strong>{item.label}</strong><small>{item.name}</small></div>
                    </button>
                  ))}
                </section>
              ))}
            </div>
          </aside>
          <div className="catalog-main">
            {relation ? <RelationBrowser key={relation.name} relation={relation} onMessage={message} onOpenLexicon={openLexicon} onDirtyChange={setNavigationDirty} /> : (
              <section className="schema-welcome panel">
                <span aria-hidden="true">{"{ }"}</span>
                <p className="eyebrow">{t("Schema PostgREST", "PostgREST schema")}</p>
                <h2>{t("Misafidiana singa iray ao amin'ny schema", "Select a relation")}</h2>
                <p>{t("Ny tabilao dia azo amoronana, ovana ary famafana rakitra araka ny schema. Ny views sy materialized views kosa dia read-only mba ho azo antoka.", "Tables support schema-aware create, edit, and delete operations. Views and materialized views are safely read-only.")}</p>
                <div><strong>{tableRelations.length}</strong><span>{t("tabilao", "tables")}</span><strong>{viewRelations.length}</strong><span>views</span></div>
              </section>
            )}
          </div>
          </div>
        </div>
      )}
      <div className="toast-stack" aria-live="polite" aria-atomic="false">
        {toasts.map((toast) => <div className={`toast toast--${toast.tone}`} key={toast.id}><span />{toast.message}<button type="button" aria-label={t("Akatona", "Dismiss")} onClick={() => setToasts((current) => current.filter((item) => item.id !== toast.id))}>×</button></div>)}
      </div>
    </Layout></LanguageProvider></TranslationJobsProvider>
  );
}
