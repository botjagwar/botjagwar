import { useEffect, useEffectEvent, useState } from "react";

import { ApiResponseError, getDefinitionTranslationSettings, getGemmaSettings, getPageCheckerSettings, refreshMaterializedViews, updateDefinitionTranslationSettings, updateGemmaSettings, updatePageCheckerAutonomousAgent, updatePageCheckerSettings, updatePageCheckJobHistoryLimit, updateTranslationPrefilter } from "../api";
import { joinAddress, normaliseConfig, type AtlasConfig } from "../config";
import { useI18n } from "../i18n";
import { useTheme } from "../theme";
import type { DefinitionTranslationSettings, PageCheckerAutomationSettings } from "../types";

interface SettingsWorkspaceProps {
  config: AtlasConfig;
  onSave: (config: AtlasConfig) => void;
  onReset: () => void;
  onReload: () => Promise<void>;
  onMessage: (message: string, tone?: "success" | "error") => void;
}

type ServiceField = "postgrestAddresses" | "dictionaryServiceAddresses" | "entryTranslatorAddresses";
const MAX_COOLDOWN_SECONDS = 86_400;
const MAX_JOB_HISTORY_LIMIT = 100_000;

interface PageCheckerSettingsDraft {
  watchedUsers: string;
  checkProbability: string;
  cooldownSeconds: string;
  ignoredEditSummaries: string;
  jobHistoryLimit: string;
  autonomousAgentEnabled: boolean;
  translationPrefilterEnabled: boolean;
}

function toTextarea(addresses: string[]): string {
  return addresses.join("\n");
}

function fromTextarea(value: string): string[] {
  return value.split(/[\n,]/).map((address) => address.trim()).filter(Boolean);
}

function fromLines(value: string): string[] {
  return value.split("\n").map((line) => line.trim()).filter(Boolean);
}

function pageCheckerSettingsDraft(settings: PageCheckerAutomationSettings): PageCheckerSettingsDraft {
  return {
    watchedUsers: settings.watched_users.join("\n"),
    checkProbability: String(settings.check_probability),
    cooldownSeconds: String(settings.cooldown_seconds),
    ignoredEditSummaries: settings.ignored_edit_summaries.join("\n"),
    jobHistoryLimit: String(settings.job_history_limit),
    autonomousAgentEnabled: settings.autonomous_agent_enabled,
    translationPrefilterEnabled: settings.translation_prefilter_enabled,
  };
}

export function SettingsWorkspace({ config, onSave, onReset, onReload, onMessage }: SettingsWorkspaceProps) {
  const { t } = useI18n();
  const { theme, setTheme } = useTheme();
  const [databaseAddress, setDatabaseAddress] = useState(config.databaseAddress);
  const [addresses, setAddresses] = useState<Record<ServiceField, string>>({
    postgrestAddresses: toTextarea(config.postgrestAddresses),
    dictionaryServiceAddresses: toTextarea(config.dictionaryServiceAddresses),
    entryTranslatorAddresses: toTextarea(config.entryTranslatorAddresses),
  });
  const [checks, setChecks] = useState<Record<string, "checking" | "online" | "offline">>({});
  const [reloading, setReloading] = useState(false);
  const [refreshingViews, setRefreshingViews] = useState(false);
  const [pageCheckerDraft, setPageCheckerDraft] = useState<PageCheckerSettingsDraft>({ watchedUsers: "", checkProbability: "", cooldownSeconds: "", ignoredEditSummaries: "", jobHistoryLimit: "", autonomousAgentEnabled: false, translationPrefilterEnabled: false });
  const [pageCheckerLoaded, setPageCheckerLoaded] = useState(false);
  const [autonomousAgentKnown, setAutonomousAgentKnown] = useState(false);
  const [translationPrefilterKnown, setTranslationPrefilterKnown] = useState(false);
  const [loadingPageChecker, setLoadingPageChecker] = useState(true);
  const [savingPageChecker, setSavingPageChecker] = useState(false);
  const [savingAutonomousAgent, setSavingAutonomousAgent] = useState(false);
  const [savingTranslationPrefilter, setSavingTranslationPrefilter] = useState(false);
  const [savingJobHistory, setSavingJobHistory] = useState(false);
  const [basicEnglishGateEnabled, setBasicEnglishGateEnabled] = useState(false);
  const [nllbRoundtripValidationEnabled, setNllbRoundtripValidationEnabled] = useState(true);
  const [definitionSettingsKnown, setDefinitionSettingsKnown] = useState(false);
  const [loadingDefinitionSettings, setLoadingDefinitionSettings] = useState(true);
  const [savingDefinitionSettings, setSavingDefinitionSettings] = useState(false);
  const [gemmaEndpoint, setGemmaEndpoint] = useState("");
  const [gemmaModel, setGemmaModel] = useState("");
  const [gemmaSettingsKnown, setGemmaSettingsKnown] = useState(false);
  const [loadingGemmaSettings, setLoadingGemmaSettings] = useState(true);
  const [savingGemmaSettings, setSavingGemmaSettings] = useState(false);
  const serviceFields: { field: ServiceField; label: string; description: string; healthPath: string }[] = [
    { field: "postgrestAddresses", label: t("Adiresy PostgREST", "PostgREST addresses"), description: t("Lisitra voalahatry ny REST gateways mampiseho ny schema Botjagwar.", "Ordered list of REST gateways exposing the Botjagwar schema."), healthPath: "word?select=id&limit=1" },
    { field: "dictionaryServiceAddresses", label: t("Adiresin'ny dictionary_service", "dictionary_service addresses"), description: t("Lisitra voalahatry ny API endpoints ho an'ny teny feno ao amin'ny rakibolana.", "Ordered list of API endpoints for complete dictionary entries."), healthPath: "ping" },
    { field: "entryTranslatorAddresses", label: t("Adiresin'ny entry_translator", "entry_translator addresses"), description: t("Lisitra voalahatry ny endpoints an'ny tolotra fandikana sy famoahana.", "Ordered list of translation and publishing service endpoints."), healthPath: "health" },
  ];
  const reportPageCheckerLoadError = useEffectEvent((caught: unknown) => {
    onMessage(caught instanceof Error ? caught.message : t("Tsy azo ny fikirakirana fanamarinana pejy mandeha ho azy.", "Unable to load page-check automation settings."), "error");
  });
  const reportDefinitionSettingsLoadError = useEffectEvent((caught: unknown) => {
    onMessage(caught instanceof Error ? caught.message : t("Tsy azo ny fikirakirana fandikana famaritana.", "Unable to load definition-translation settings."), "error");
  });
  const reportGemmaSettingsLoadError = useEffectEvent((caught: unknown) => {
    onMessage(caught instanceof Error ? caught.message : t("Tsy azo ny fikirakirana endpoint Gemma.", "Unable to load Gemma endpoint settings."), "error");
  });

  useEffect(() => {
    const controller = new AbortController();
    getPageCheckerSettings(controller.signal)
      .then((settings) => {
        if (!controller.signal.aborted) {
          const draft = pageCheckerSettingsDraft(settings);
          setPageCheckerDraft(draft);
          setPageCheckerLoaded(true);
          setAutonomousAgentKnown(true);
          setTranslationPrefilterKnown(true);
        }
      })
      .catch((caught: unknown) => {
        if (!controller.signal.aborted) {
          setAutonomousAgentKnown(false);
          setTranslationPrefilterKnown(false);
          reportPageCheckerLoadError(caught);
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoadingPageChecker(false);
      });
    return () => controller.abort();
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    getGemmaSettings(controller.signal)
      .then((settings) => {
        if (!controller.signal.aborted) {
          setGemmaEndpoint(settings.api_url);
          setGemmaModel(settings.model);
          setGemmaSettingsKnown(true);
        }
      })
      .catch((caught: unknown) => {
        if (!controller.signal.aborted) {
          setGemmaSettingsKnown(false);
          reportGemmaSettingsLoadError(caught);
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoadingGemmaSettings(false);
      });
    return () => controller.abort();
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    getDefinitionTranslationSettings(controller.signal)
      .then((settings) => {
        if (!controller.signal.aborted) {
          setBasicEnglishGateEnabled(settings.basic_english_gate_enabled);
          setNllbRoundtripValidationEnabled(settings.nllb_roundtrip_validation_enabled);
          setDefinitionSettingsKnown(true);
        }
      })
      .catch((caught: unknown) => {
        if (!controller.signal.aborted) {
          setDefinitionSettingsKnown(false);
          reportDefinitionSettingsLoadError(caught);
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoadingDefinitionSettings(false);
      });
    return () => controller.abort();
  }, []);

  function draftConfig(): AtlasConfig {
    return normaliseConfig({
      databaseAddress,
      postgrestAddresses: fromTextarea(addresses.postgrestAddresses),
      dictionaryServiceAddresses: fromTextarea(addresses.dictionaryServiceAddresses),
      entryTranslatorAddresses: fromTextarea(addresses.entryTranslatorAddresses),
    });
  }

  function saveRuntimeConfiguration() {
    const hasEmptyService = (Object.keys(addresses) as ServiceField[])
      .some((field) => fromTextarea(addresses[field]).length === 0);
    if (hasEmptyService) {
      onMessage(t("Tsy maintsy manana URL iray farafahakeliny ny tolotra tsirairay.", "Each service must have at least one URL."), "error");
      return;
    }
    onSave(draftConfig());
  }

  async function testAddress(address: string, path: string) {
    const key = `${address}-${path}`;
    setChecks((current) => ({ ...current, [key]: "checking" }));
    try {
      const response = await fetch(joinAddress(address, path), { signal: AbortSignal.timeout(5000) });
      setChecks((current) => ({ ...current, [key]: response.ok ? "online" : "offline" }));
    } catch {
      setChecks((current) => ({ ...current, [key]: "offline" }));
    }
  }

  async function reloadConfiguration() {
    setReloading(true);
    try {
      await onReload();
    } finally {
      setReloading(false);
    }
  }

  async function refreshViews() {
    setRefreshingViews(true);
    try {
      const result = await refreshMaterializedViews();
      onMessage(t(`Materialized views ${result.refreshed_views} no nohavaozina.`, `${result.refreshed_views} materialized views refreshed.`));
    } catch (error) {
      onMessage(error instanceof Error ? error.message : t("Tsy nahomby ny fanavaozana materialized views.", "Materialized-view refresh failed."), "error");
    } finally {
      setRefreshingViews(false);
    }
  }

  async function reloadGemmaSettings() {
    setLoadingGemmaSettings(true);
    try {
      const settings = await getGemmaSettings();
      setGemmaEndpoint(settings.api_url);
      setGemmaModel(settings.model);
      setGemmaSettingsKnown(true);
      onMessage(t("Naverina nalaina tamin'ny mpizara ny endpoint Gemma.", "Gemma endpoint reloaded from the server."));
    } catch (caught) {
      setGemmaSettingsKnown(false);
      onMessage(caught instanceof Error ? caught.message : t("Tsy azo ny fikirakirana endpoint Gemma.", "Unable to load Gemma endpoint settings."), "error");
    } finally {
      setLoadingGemmaSettings(false);
    }
  }

  async function saveGemmaSettings() {
    const endpoint = gemmaEndpoint.trim();
    if (!endpoint) {
      onMessage(t("Tsy maintsy misy ny URL endpoint Gemma.", "The Gemma endpoint URL is required."), "error");
      return;
    }
    setSavingGemmaSettings(true);
    try {
      const settings = await updateGemmaSettings(endpoint);
      setGemmaEndpoint(settings.api_url);
      setGemmaModel(settings.model);
      setGemmaSettingsKnown(true);
      onMessage(t("Voatahiry tao amin'ny mpizara ny endpoint Gemma.", "Gemma endpoint saved on the server."));
    } catch (caught) {
      onMessage(caught instanceof Error ? caught.message : t("Tsy voatahiry ny endpoint Gemma.", "Unable to save the Gemma endpoint."), "error");
    } finally {
      setSavingGemmaSettings(false);
    }
  }

  async function reloadPageCheckerSettings() {
    setLoadingPageChecker(true);
    try {
      const settings = await getPageCheckerSettings();
      const draft = pageCheckerSettingsDraft(settings);
      setPageCheckerDraft(draft);
      setPageCheckerLoaded(true);
      setAutonomousAgentKnown(true);
      setTranslationPrefilterKnown(true);
      onMessage(t("Naverina nalaina tamin'ny mpizara ny fikirakirana fanamarinana pejy.", "Page-check automation settings reloaded from the server."));
    } catch (caught) {
      setAutonomousAgentKnown(false);
      setTranslationPrefilterKnown(false);
      onMessage(caught instanceof Error ? caught.message : t("Tsy azo ny fikirakirana fanamarinana pejy mandeha ho azy.", "Unable to load page-check automation settings."), "error");
    } finally {
      setLoadingPageChecker(false);
    }
  }

  async function savePageCheckerSettings() {
    const probabilityValue = pageCheckerDraft.checkProbability.trim();
    const checkProbability = Number(probabilityValue);
    if (!probabilityValue || !Number.isFinite(checkProbability) || checkProbability < 0 || checkProbability > 100) {
      onMessage(t("Tokony ho isa eo anelanelan'ny 0 sy 100 ny tahan'ny fanamarinana.", "Check probability must be a number from 0 to 100."), "error");
      return;
    }

    const cooldownValue = pageCheckerDraft.cooldownSeconds.trim();
    const cooldownSeconds = Number(cooldownValue);
    if (!cooldownValue || !Number.isFinite(cooldownSeconds) || cooldownSeconds < 0 || cooldownSeconds > MAX_COOLDOWN_SECONDS) {
      onMessage(t("Tokony ho isa eo anelanelan'ny 0 sy 86400 ny fotoana fiandrasana.", "Cooldown seconds must be a number from 0 to 86400."), "error");
      return;
    }

    setSavingPageChecker(true);
    try {
      const settings = await updatePageCheckerSettings({
        watched_users: fromTextarea(pageCheckerDraft.watchedUsers),
        check_probability: checkProbability,
        cooldown_seconds: cooldownSeconds,
        ignored_edit_summaries: fromLines(pageCheckerDraft.ignoredEditSummaries),
      });
      setPageCheckerDraft((current) => ({
        ...current,
        watchedUsers: settings.watched_users.join("\n"),
        checkProbability: String(settings.check_probability),
        cooldownSeconds: String(settings.cooldown_seconds),
        ignoredEditSummaries: settings.ignored_edit_summaries.join("\n"),
      }));
      setPageCheckerLoaded(true);
      onMessage(t("Voatahiry tao amin'ny mpizara ny fikirakirana fanamarinana pejy.", "Page-check automation settings saved on the server."));
    } catch (caught) {
      onMessage(caught instanceof Error ? caught.message : t("Tsy voatahiry ny fikirakirana fanamarinana pejy mandeha ho azy.", "Unable to save page-check automation settings."), "error");
    } finally {
      setSavingPageChecker(false);
    }
  }

  async function setAutonomousAgentEnabled(enabled: boolean) {
    const previousValue = pageCheckerDraft.autonomousAgentEnabled;
    setPageCheckerDraft((current) => ({ ...current, autonomousAgentEnabled: enabled }));
    setSavingAutonomousAgent(true);
    try {
      const result = await updatePageCheckerAutonomousAgent(enabled);
      setPageCheckerDraft((current) => ({ ...current, autonomousAgentEnabled: result.autonomous_agent_enabled }));
      setAutonomousAgentKnown(true);
      onMessage(result.autonomous_agent_enabled
        ? t("Nalefa ny mpiasa fanitsiana GitHub mandeha ho azy.", "Autonomous GitHub fix agent enabled.")
        : t("Najano ny mpiasa fanitsiana GitHub mandeha ho azy.", "Autonomous GitHub fix agent disabled."));
    } catch (caught) {
      try {
        const settings = await getPageCheckerSettings();
        setPageCheckerDraft((current) => ({ ...current, autonomousAgentEnabled: settings.autonomous_agent_enabled }));
        setAutonomousAgentKnown(true);
      } catch {
        setPageCheckerDraft((current) => ({ ...current, autonomousAgentEnabled: previousValue }));
        setAutonomousAgentKnown(false);
      }
      onMessage(caught instanceof Error ? caught.message : t("Tsy voatahiry ny satan'ny mpiasa fanitsiana mandeha ho azy.", "Unable to save the autonomous-agent state."), "error");
    } finally {
      setSavingAutonomousAgent(false);
    }
  }

  async function setTranslationPrefilterEnabled(enabled: boolean) {
    const previousValue = pageCheckerDraft.translationPrefilterEnabled;
    setPageCheckerDraft((current) => ({ ...current, translationPrefilterEnabled: enabled }));
    setSavingTranslationPrefilter(true);
    try {
      const result = await updateTranslationPrefilter(enabled);
      setPageCheckerDraft((current) => ({ ...current, translationPrefilterEnabled: result.translation_prefilter_enabled }));
      setTranslationPrefilterKnown(true);
      onMessage(result.translation_prefilter_enabled
        ? t("Nalefa ny sivana page checker alohan'ny famoahana.", "Page-check publication prefilter enabled.")
        : t("Najano ny sivana page checker alohan'ny famoahana.", "Page-check publication prefilter disabled."));
    } catch (caught) {
      try {
        const settings = await getPageCheckerSettings();
        setPageCheckerDraft((current) => ({ ...current, translationPrefilterEnabled: settings.translation_prefilter_enabled }));
        setTranslationPrefilterKnown(true);
      } catch {
        setPageCheckerDraft((current) => ({ ...current, translationPrefilterEnabled: previousValue }));
        setTranslationPrefilterKnown(false);
      }
      onMessage(caught instanceof Error ? caught.message : t("Tsy voatahiry ny satan'ny sivana famoahana.", "Unable to save the publication-prefilter state."), "error");
    } finally {
      setSavingTranslationPrefilter(false);
    }
  }

  async function saveJobHistoryLimit() {
    const value = pageCheckerDraft.jobHistoryLimit.trim();
    const limit = Number(value);
    if (!value || !Number.isInteger(limit) || limit < 1 || limit > MAX_JOB_HISTORY_LIMIT) {
      onMessage(t("Tokony ho isa manontolo eo anelanelan'ny 1 sy 100000 ny isan'ny asa tehirizina.", "Stored jobs must be a whole number from 1 to 100000."), "error");
      return;
    }
    setSavingJobHistory(true);
    try {
      const settings = await updatePageCheckJobHistoryLimit(limit);
      setPageCheckerDraft((current) => ({ ...current, jobHistoryLimit: String(settings.job_history_limit) }));
      onMessage(t("Voatahiry tao amin'ny mpizara ny isan'ny asa aseho.", "The displayed job history limit was saved on the server."));
    } catch (caught) {
      onMessage(caught instanceof ApiResponseError && caught.status === 404
        ? t("Tsy mbola manohana ity fikirana ity ny entry_translator. Havaozy na avereno alefa ny instances rehetra.", "The entry_translator does not support this setting yet. Update or restart every instance.")
        : caught instanceof Error ? caught.message : t("Tsy voatahiry ny isan'ny asa aseho.", "Unable to save the job history limit."), "error");
    } finally {
      setSavingJobHistory(false);
    }
  }

  function applyDefinitionSettings(settings: DefinitionTranslationSettings) {
    setBasicEnglishGateEnabled(settings.basic_english_gate_enabled);
    setNllbRoundtripValidationEnabled(settings.nllb_roundtrip_validation_enabled);
  }

  async function setDefinitionSetting(
    setting: keyof DefinitionTranslationSettings,
    enabled: boolean,
  ) {
    const previousSettings = {
      basic_english_gate_enabled: basicEnglishGateEnabled,
      nllb_roundtrip_validation_enabled: nllbRoundtripValidationEnabled,
    };
    const requestedSettings = { ...previousSettings, [setting]: enabled };
    applyDefinitionSettings(requestedSettings);
    setSavingDefinitionSettings(true);
    try {
      const settings = await updateDefinitionTranslationSettings(requestedSettings);
      applyDefinitionSettings(settings);
      setDefinitionSettingsKnown(true);
      if (setting === "basic_english_gate_enabled") {
        onMessage(settings.basic_english_gate_enabled
          ? t("Nalefa ny sivana voambolana Basic English.", "Basic English vocabulary gate enabled.")
          : t("Najano ny sivana voambolana Basic English.", "Basic English vocabulary gate disabled."));
      } else {
        onMessage(settings.nllb_roundtrip_validation_enabled
          ? t("Nalefa ny fanamarinana fandikana miverina NLLB.", "NLLB round-trip validation enabled.")
          : t("Najano ny fanamarinana fandikana miverina NLLB.", "NLLB round-trip validation disabled."));
      }
    } catch (caught) {
      try {
        const settings = await getDefinitionTranslationSettings();
        applyDefinitionSettings(settings);
        setDefinitionSettingsKnown(true);
      } catch {
        applyDefinitionSettings(previousSettings);
        setDefinitionSettingsKnown(false);
      }
      onMessage(caught instanceof Error ? caught.message : t("Tsy voatahiry ny fikirakirana fandikana famaritana.", "Unable to save definition-translation settings."), "error");
    } finally {
      setSavingDefinitionSettings(false);
    }
  }

  return (
    <div className="settings-workspace">
      <section className="settings-intro panel">
        <div><p className="eyebrow">{t("Fikirakirana runtime", "Runtime configuration")}</p><h2>{t("Firafitry ny tolotra", "Service configuration")}</h2><p>{t("Tehirizina ho an'ity mpitety tranonkala ity ny fanovana ary mihatra avy hatrany, tsy mila manorina an'i Atlas indray.", "Changes are stored for this browser and take effect immediately, without rebuilding Atlas.")}</p></div>
        <div className="settings-intro__actions"><button className="button button--ghost" type="button" onClick={() => void reloadConfiguration()} disabled={reloading || savingPageChecker || savingAutonomousAgent || savingTranslationPrefilter || savingJobHistory || savingDefinitionSettings || savingGemmaSettings}>{reloading ? t("Mamerina maka...", "Reloading...") : t("Hamerina haka ny fikirana", "Reload configuration")}</button><button className="button button--ghost" type="button" onClick={onReset} disabled={savingPageChecker || savingAutonomousAgent || savingTranslationPrefilter || savingJobHistory || savingDefinitionSettings || savingGemmaSettings}>{t("Hampiasa ny sanda mahazatra an'ny deployment", "Use deployment defaults")}</button><button className="button button--primary" type="button" onClick={saveRuntimeConfiguration} disabled={savingPageChecker || savingAutonomousAgent || savingTranslationPrefilter || savingJobHistory || savingDefinitionSettings || savingGemmaSettings}>{t("Hitahiry ny fikirana", "Save settings")}</button></div>
      </section>

      <section className="panel settings-gemma" aria-labelledby="job-history-settings-title">
        <div className="settings-appearance__header">
          <div>
            <p className="eyebrow">{t("Fitahirizana asa", "Job storage")}</p>
            <h3 id="job-history-settings-title">{t("Haben'ny tantaran'ny asa", "Job history size")}</h3>
            <p>{t("Safidio ny isan'ny asa fanamarinana farany asehon'i Atlas sy ampiasainy amin'ny antontan'isa. Mitahiry asa hatramin'ny 100000 ao amin'ny Redis ny mpizara mba tsy ho very avy hatrany ny tantara rehefa ovaina ity sanda ity.", "Choose how many recent check jobs Atlas shows and uses for statistics. The server keeps up to 100000 jobs in Redis so changing this value does not immediately discard history.")}</p>
          </div>
          <span className="settings-appearance__ownership">{t("tantanan'ny mpizara", "server-managed")}</span>
        </div>
        <div className="settings-gemma__connection">
          <label className="field field--grow">
            <span>{t("Isan'ny asa ao amin'ny tantara", "Jobs in history")}</span>
            <input aria-label={t("Isan'ny asa ao amin'ny tantara", "Jobs in history")} type="number" min="1" max={MAX_JOB_HISTORY_LIMIT} step="1" value={pageCheckerDraft.jobHistoryLimit} disabled={!pageCheckerLoaded || loadingPageChecker || savingJobHistory} onChange={(event) => setPageCheckerDraft((current) => ({ ...current, jobHistoryLimit: event.target.value }))} />
            <small>{t("Isa manontolo eo anelanelan'ny 1 sy 100000. Ny sanda mahazatra dia 2500.", "A whole number from 1 to 100000. The default is 2500.")}</small>
          </label>
        </div>
        <div className="settings-gemma__footer">
          <span aria-live="polite">{loadingPageChecker ? t("Maka ny sanda amin'ny mpizara...", "Loading server value...") : savingJobHistory ? t("Mitahiry ny isan'ny asa...", "Saving job history size...") : pageCheckerLoaded ? t("Ity sanda ity dia mihatra amin'ny Atlas sy ny antontan'isa.", "This value applies to Atlas and its statistics.") : t("Tsy mbola azo ny sanda avy amin'ny mpizara.", "The server value is not available yet.")}</span>
          <button className="button button--primary" type="button" disabled={!pageCheckerLoaded || loadingPageChecker || savingJobHistory} onClick={() => void saveJobHistoryLimit()}>{savingJobHistory ? t("Mitahiry...", "Saving...") : t("Hitahiry ny haben'ny tantara", "Save history size")}</button>
        </div>
      </section>

      <section className="panel settings-appearance" aria-labelledby="appearance-settings-title">
        <div className="settings-appearance__header">
          <div>
            <p className="eyebrow">{t("Endrika", "Appearance")}</p>
            <h3 id="appearance-settings-title">{t("Endriky ny interface", "Interface theme")}</h3>
            <p>{t("Safidio ny endrika ampiasain'i Atlas. Tehirizina ato amin'ity mpitety tranonkala ity ny safidy ary mihatra avy hatrany.", "Choose how Atlas looks. Your selection is stored in this browser and applies immediately.")}</p>
          </div>
          <span className="settings-appearance__ownership">{t("voatahiry amin'ny navigateur", "saved in this browser")}</span>
        </div>
        <div className="theme-options" role="radiogroup" aria-label={t("Endriky ny interface", "Interface theme")}>
          <label className={`theme-option${theme === "atlas" ? " theme-option--selected" : ""}`}>
            <input type="radio" name="atlas-theme" value="atlas" checked={theme === "atlas"} onChange={() => setTheme("atlas")} />
            <span className="theme-option__preview theme-option__preview--atlas" aria-hidden="true"><i /><b /><em /></span>
            <span><strong>Atlas</strong><small>{t("Ny endrika maoderina ampiasaina ankehitriny.", "The current modern Atlas design.")}</small></span>
            <span className="theme-option__status">{theme === "atlas" ? t("Mavitrika", "Active") : t("Safidio", "Select")}</span>
          </label>
          <label className={`theme-option${theme === "windows-98" ? " theme-option--selected" : ""}`}>
            <input type="radio" name="atlas-theme" value="windows-98" checked={theme === "windows-98"} onChange={() => setTheme("windows-98")} />
            <span className="theme-option__preview theme-option__preview--windows" aria-hidden="true"><i /><b /><em /></span>
            <span><strong>Windows 98</strong><small>{t("Varavarankely, bokotra ary loko amin'ny endrika mahazatra.", "Classic windows, buttons, and desktop colors.")}</small></span>
            <span className="theme-option__status">{theme === "windows-98" ? t("Mavitrika", "Active") : t("Safidio", "Select")}</span>
          </label>
          <label className={`theme-option${theme === "windows-xp" ? " theme-option--selected" : ""}`}>
            <input type="radio" name="atlas-theme" value="windows-xp" checked={theme === "windows-xp"} onChange={() => setTheme("windows-xp")} />
            <span className="theme-option__preview theme-option__preview--xp" aria-hidden="true"><i /><b /><em /></span>
            <span><strong>Windows XP</strong><small>{t("Loko Luna, varavarankely boribory ary fanaraha-maso mamirapiratra.", "Luna colors, rounded windows, and glossy controls.")}</small></span>
            <span className="theme-option__status">{theme === "windows-xp" ? t("Mavitrika", "Active") : t("Safidio", "Select")}</span>
          </label>
          <label className={`theme-option${theme === "mac-os" ? " theme-option--selected" : ""}`}>
            <input type="radio" name="atlas-theme" value="mac-os" checked={theme === "mac-os"} onChange={() => setTheme("mac-os")} />
            <span className="theme-option__preview theme-option__preview--mac" aria-hidden="true"><i /><b /><em /></span>
            <span><strong>Mac OS</strong><small>{t("Endrika Aqua misy fitaratra, aliminioma ary bokotra miloko.", "Aqua glass, aluminum surfaces, and colorful window controls.")}</small></span>
            <span className="theme-option__status">{theme === "mac-os" ? t("Mavitrika", "Active") : t("Safidio", "Select")}</span>
          </label>
        </div>
      </section>

      <section className="panel settings-gemma" aria-labelledby="gemma-settings-title">
        <div className="settings-appearance__header">
          <div>
            <p className="eyebrow">Gemma</p>
            <h3 id="gemma-settings-title">{t("Endpoint modely lavitra", "Remote model endpoint")}</h3>
            <p>{t("Ity URL ity dia tehirizina ao amin'ny config.ini voaaro ary ampiasain'ny resaka Atlas sy ny fanatsorana famaritana. HTTPS no takiana amin'ny endpoint ampahibemaso; azo ampiasaina amin'ny HTTP ny adiresy IP manokana sy loopback.", "This URL is stored in protected config.ini and used by Atlas chat and definition reformulation. Public endpoints require HTTPS; private and loopback IP addresses may use HTTP.")}</p>
          </div>
          <span className="settings-appearance__ownership">{t("tantanan'ny mpizara", "server-managed")}</span>
        </div>
        <div className="settings-gemma__connection">
          <label className="field field--grow">
            <span>{t("URL endpoint Gemma", "Gemma endpoint URL")}</span>
            <input aria-label={t("URL endpoint Gemma", "Gemma endpoint URL")} type="url" value={gemmaEndpoint} disabled={loadingGemmaSettings || savingGemmaSettings} onChange={(event) => setGemmaEndpoint(event.target.value)} placeholder="https://gemma.example/v1/chat/completions" />
          </label>
          <div className="settings-gemma__model"><span>{t("Modely", "Model")}</span><strong>{gemmaModel || t("Tsy fantatra", "Unknown")}</strong></div>
        </div>
        <div className="settings-gemma__footer">
          <span aria-live="polite">{loadingGemmaSettings ? t("Maka ny endpoint amin'ny mpizara...", "Loading endpoint from the server...") : savingGemmaSettings ? t("Mitahiry ny endpoint...", "Saving endpoint...") : gemmaSettingsKnown ? t("Ny endpoint aseho no ampiasain'ny mpizara ankehitriny.", "The displayed endpoint is currently active on the server.") : t("Tsy mbola azo ny endpoint avy amin'ny mpizara.", "The server endpoint is not available yet.")}</span>
          <div>
            <button className="button button--ghost" type="button" disabled={loadingGemmaSettings || savingGemmaSettings} onClick={() => void reloadGemmaSettings()}>{loadingGemmaSettings ? t("Mamerina maka...", "Reloading...") : t("Hamerina haka ny endpoint", "Reload endpoint")}</button>
            <button className="button button--primary" type="button" disabled={loadingGemmaSettings || savingGemmaSettings || !gemmaEndpoint.trim()} onClick={() => void saveGemmaSettings()}>{savingGemmaSettings ? t("Mitahiry...", "Saving...") : t("Hitahiry ny endpoint", "Save endpoint")}</button>
          </div>
        </div>
      </section>

      <section className="panel settings-automation" aria-labelledby="definition-translation-settings-title">
        <div className="settings-automation__header">
          <div>
            <p className="eyebrow">{t("Fandikana famaritana", "Definition translation")}</p>
            <h3 id="definition-translation-settings-title">{t("Fanaraha-maso ny fandikana NLLB", "NLLB translation controls")}</h3>
            <p>{t("Fehezo ny fanatsorana amin'ny Gemma sy ny fanamarinana fandikana miverina ampiasaina amin'ny famaritana alefa any amin'ny NLLB.", "Control Gemma simplification and round-trip validation for definitions sent to NLLB.")}</p>
          </div>
          <span className="settings-automation__ownership">{t("tantanan'ny mpizara", "server-managed")}</span>
        </div>
        <div className="settings-automation__fields">
          <div className={`settings-agent-control${basicEnglishGateEnabled ? " settings-agent-control--enabled" : ""}`}>
            <div className="settings-agent-control__copy">
              <span>{savingDefinitionSettings ? t("MITAHIRY", "SAVING") : !definitionSettingsKnown ? t("TSY FANTATRA", "UNKNOWN") : basicEnglishGateEnabled ? t("MANDEHA", "ACTIVE") : t("TSY MANDEHA", "INACTIVE")}</span>
              <h4>{t("Ampiasao Gemma 4 amin'ny famaritana sarotra", "Use Gemma 4 for complex definitions")}</h4>
              <p>{t("Ho an'ny famaritana anglisy mihoatra ny teny enina, alefa mivantana any amin'ny NLLB izay manana teny 75% farafahakeliny ao amin'ny lisitra Basic English. Gemma 4 aloha no manatsotra ireo ambanin'izany. Rehefa ajanona dia alefa mivantana any amin'ny NLLB ny famaritana rehetra.", "For English definitions longer than six words, those with at least 75% of words in the Basic English list go directly to NLLB. Gemma 4 first simplifies definitions below that score. When disabled, every definition goes directly to NLLB.")}</p>
            </div>
            <label className="settings-agent-control__toggle">
              <input aria-label={t("Sivana voambolana Basic English", "Basic English vocabulary gate")} role="switch" type="checkbox" checked={basicEnglishGateEnabled} disabled={!definitionSettingsKnown || loadingDefinitionSettings || savingDefinitionSettings || reloading} onChange={(event) => void setDefinitionSetting("basic_english_gate_enabled", event.target.checked)} />
              <span aria-hidden="true" />
              <strong>{savingDefinitionSettings ? t("Mitahiry", "Saving") : !definitionSettingsKnown ? t("Tsy fantatra", "Unknown") : basicEnglishGateEnabled ? t("Alefa", "Enabled") : t("Ajanona", "Disabled")}</strong>
            </label>
          </div>
          <div className={`settings-agent-control${nllbRoundtripValidationEnabled ? " settings-agent-control--enabled" : ""}`}>
            <div className="settings-agent-control__copy">
              <span>{savingDefinitionSettings ? t("MITAHIRY", "SAVING") : !definitionSettingsKnown ? t("TSY FANTATRA", "UNKNOWN") : nllbRoundtripValidationEnabled ? t("MANDEHA", "ACTIVE") : t("TSY MANDEHA", "INACTIVE")}</span>
              <h4>{t("Hamarino amin'ny fandikana miverina", "Validate with back-translation")}</h4>
              <p>{t("Rehefa alefa, adikan'ny NLLB hiverina amin'ny teny anglisy ny vokatra ary laviny raha tsy mitahiry ny hevitra tany am-boalohany. Mbola ampiharina foana ny fiarovana amin'ny teny miverimberina.", "When enabled, NLLB translates the result back into English and rejects it when the original meaning is not preserved. Repeated-output protection remains active either way.")}</p>
            </div>
            <label className="settings-agent-control__toggle">
              <input aria-label={t("Fanamarinana fandikana miverina NLLB", "NLLB round-trip validation")} role="switch" type="checkbox" checked={nllbRoundtripValidationEnabled} disabled={!definitionSettingsKnown || loadingDefinitionSettings || savingDefinitionSettings || reloading} onChange={(event) => void setDefinitionSetting("nllb_roundtrip_validation_enabled", event.target.checked)} />
              <span aria-hidden="true" />
              <strong>{savingDefinitionSettings ? t("Mitahiry", "Saving") : !definitionSettingsKnown ? t("Tsy fantatra", "Unknown") : nllbRoundtripValidationEnabled ? t("Alefa", "Enabled") : t("Ajanona", "Disabled")}</strong>
            </label>
          </div>
        </div>
      </section>

      <section className="panel settings-automation" aria-labelledby="page-checker-settings-title">
        <div className="settings-automation__header">
          <div>
            <p className="eyebrow">{t("Automation an'ny fanamarinana pejy", "Page-check automation")}</p>
            <h3 id="page-checker-settings-title">{t("Fitsipika fanaraha-maso ny mpanova", "Editor monitoring rules")}</h3>
            <p>{t("Ny entry_translator no mitahiry ireo sanda ary ny mpihaino IRC no mampihatra azy. Ny fanamarinana mandeha ho azy dia afaka mamoaka fanitsiana ao amin'ny Wiktionary.", "The entry_translator stores these values and the IRC listener applies them. Automated checks can publish fixes to Wiktionary.")}</p>
          </div>
          <span className="settings-automation__ownership">{t("tantanan'ny mpizara", "server-managed")}</span>
        </div>
        <div className="settings-automation__fields">
          <div className={`settings-agent-control${pageCheckerDraft.translationPrefilterEnabled ? " settings-agent-control--enabled" : ""}`}>
            <div className="settings-agent-control__copy">
              <span>{savingTranslationPrefilter ? t("MITAHIRY", "SAVING") : !translationPrefilterKnown ? t("TSY FANTATRA", "UNKNOWN") : pageCheckerDraft.translationPrefilterEnabled ? t("MANDEHA", "ACTIVE") : t("TSY MANDEHA", "INACTIVE")}</span>
              <h4>{t("Sivano amin'ny page checker alohan'ny famoahana", "Prefilter translations with the page checker")}</h4>
              <p>{t("Rehefa alefa, ny pejy voadika voamariky ny page checker ho good ihany no ampidirina anaty filaharana havoaka. Ario ny vokatra hafa rehetra.", "When enabled, only translated pages marked good by the page checker are queued for publication. Every other result is discarded.")}</p>
            </div>
            <label className="settings-agent-control__toggle">
              <input aria-label={t("Sivana page checker alohan'ny famoahana", "Page-check publication prefilter")} aria-describedby="translation-prefilter-warning" role="switch" type="checkbox" checked={pageCheckerDraft.translationPrefilterEnabled} disabled={!pageCheckerLoaded || !translationPrefilterKnown || loadingPageChecker || savingPageChecker || savingTranslationPrefilter || reloading} onChange={(event) => void setTranslationPrefilterEnabled(event.target.checked)} />
              <span aria-hidden="true" />
              <strong>{savingTranslationPrefilter ? t("Mitahiry", "Saving") : !translationPrefilterKnown ? t("Tsy fantatra", "Unknown") : pageCheckerDraft.translationPrefilterEnabled ? t("Alefa", "Enabled") : t("Ajanona", "Disabled")}</strong>
            </label>
            <p id="translation-prefilter-warning" className="settings-agent-control__warning">{t("Mihatra amin'ny asa fandikana vaovao izany ary tsy manafoana ireo famoahana efa ao anaty filaharana. Raha tsy azo ny fikirana na tsy vita ny fanamarinana dia tsy avoaka ny pejy.", "This applies to new translation jobs and does not cancel publications already queued. If settings or verification are unavailable, the page is not published.")}</p>
          </div>
          <div className={`settings-agent-control${pageCheckerDraft.autonomousAgentEnabled ? " settings-agent-control--enabled" : ""}`}>
            <div className="settings-agent-control__copy">
              <span>{savingAutonomousAgent ? t("MITAHIRY", "SAVING") : !autonomousAgentKnown ? t("TSY FANTATRA", "UNKNOWN") : pageCheckerDraft.autonomousAgentEnabled ? t("MANDEHA HO AZY", "AUTONOMOUS") : t("FANEKENA TANANA", "MANUAL APPROVAL")}</span>
              <h4>{t("Mpiasa fanitsiana GitHub mandeha ho azy", "Autonomous GitHub fix agent")}</h4>
              <p>{t("Rehefa alefa, dia asiana marika ho azy ireo olana vaovao ary atolotra an'i GitHub Copilot mba hanolotra fanitsiana kaody amin'ny fihodinana manaraka.", "When enabled, new page-check issues are automatically queued and assigned to GitHub Copilot to propose code fixes on the next automation run.")}</p>
            </div>
            <label className="settings-agent-control__toggle">
              <input aria-label={t("Mpiasa fanitsiana GitHub mandeha ho azy", "Autonomous GitHub fix agent")} aria-describedby="autonomous-agent-warning" role="switch" type="checkbox" checked={pageCheckerDraft.autonomousAgentEnabled} disabled={!pageCheckerLoaded || !autonomousAgentKnown || loadingPageChecker || savingPageChecker || savingAutonomousAgent || reloading} onChange={(event) => void setAutonomousAgentEnabled(event.target.checked)} />
              <span aria-hidden="true" />
              <strong>{savingAutonomousAgent ? t("Mitahiry", "Saving") : !autonomousAgentKnown ? t("Tsy fantatra", "Unknown") : pageCheckerDraft.autonomousAgentEnabled ? t("Alefa", "Enabled") : t("Ajanona", "Disabled")}</strong>
            </label>
            <p id="autonomous-agent-warning" className="settings-agent-control__warning">{t("Mampita porofo tsy azo itokisana avy amin'ny fanamarinana pejy amin'ny mpiasa afaka manatanteraka kaody izany. Tsy mifehy ny famoahana fanitsiana ao amin'ny Wiktionary ity safidy ity, ary tsy manafoana asa efa natomboka. Mbola azon'ny mpikarakara ekena tanana ao amin'ny GitHub ny olana.", "This sends untrusted page-check evidence to a code-executing agent. It does not control Wiktionary fix publication or cancel work already started; maintainers can still approve issues manually in GitHub.")}</p>
          </div>
          <label className="field settings-automation__users">
            <span>{t("Mpampiasa arahi-maso", "Watched users")}</span>
            <textarea aria-label={t("Mpampiasa arahi-maso", "Watched users")} rows={4} value={pageCheckerDraft.watchedUsers} disabled={!pageCheckerLoaded || loadingPageChecker || savingPageChecker || savingAutonomousAgent || reloading} onChange={(event) => setPageCheckerDraft((current) => ({ ...current, watchedUsers: event.target.value }))} placeholder={t("Anarana iray isaky ny andalana na saraho amin'ny faingo", "One username per line or separated by commas")} />
            <small>{t("Esorina ny elanelana sy andalana foana alohan'ny handefasana azy.", "Whitespace and empty lines are removed before sending.")}</small>
          </label>
          <label className="field">
            <span>{t("Tahan'ny fanamarinana (%)", "Check probability (%)")}</span>
            <input aria-label={t("Tahan'ny fanamarinana (%)", "Check probability (%)")} type="number" min="0" max="100" step="any" value={pageCheckerDraft.checkProbability} disabled={!pageCheckerLoaded || loadingPageChecker || savingPageChecker || savingAutonomousAgent || reloading} onChange={(event) => setPageCheckerDraft((current) => ({ ...current, checkProbability: event.target.value }))} />
            <small>{t("Isa eo anelanelan'ny 0 sy 100.", "A number from 0 to 100.")}</small>
          </label>
          <label className="field">
            <span>{t("Fotoana fiandrasana (segondra)", "Cooldown (seconds)")}</span>
            <input aria-label={t("Fotoana fiandrasana (segondra)", "Cooldown (seconds)")} type="number" min="0" max={MAX_COOLDOWN_SECONDS} step="any" value={pageCheckerDraft.cooldownSeconds} disabled={!pageCheckerLoaded || loadingPageChecker || savingPageChecker || savingAutonomousAgent || reloading} onChange={(event) => setPageCheckerDraft((current) => ({ ...current, cooldownSeconds: event.target.value }))} />
            <small>{t("Fiandrasana 0 hatramin'ny 86400 segondra alohan'ny fanamarinana manaraka.", "A delay from 0 to 86400 seconds before the next check.")}</small>
          </label>
          <label className="field settings-automation__summaries">
            <span>{t("Famintinana fanovana tsy raharahaina", "Ignored edit summaries")}</span>
            <textarea aria-label={t("Famintinana fanovana tsy raharahaina", "Ignored edit summaries")} rows={3} value={pageCheckerDraft.ignoredEditSummaries} disabled={!pageCheckerLoaded || loadingPageChecker || savingPageChecker || savingAutonomousAgent || reloading} onChange={(event) => setPageCheckerDraft((current) => ({ ...current, ignoredEditSummaries: event.target.value }))} placeholder={t("Famintinana iray isaky ny andalana", "One exact summary per line")} />
            <small>{t("Tsy ampidirina anaty filaharana ny fanovana mitovy tanteraka amin'ny iray amin'ireo famintinana ireo.", "Edits with an exact matching summary are not added to the queue.")}</small>
          </label>
        </div>
        <div className="settings-automation__footer">
          <span aria-live="polite">{loadingPageChecker ? t("Maka ny sanda amin'ny mpizara...", "Loading server values...") : savingTranslationPrefilter ? t("Mitahiry ny satan'ny sivana famoahana...", "Saving publication-prefilter state...") : savingAutonomousAgent ? t("Mitahiry ny satan'ny mpiasa mandeha ho azy...", "Saving autonomous-agent state...") : savingPageChecker ? t("Mitahiry amin'ny mpizara...", "Saving to the server...") : pageCheckerLoaded ? t("Ny sanda aseho dia avy amin'ny entry_translator.", "Values shown are from entry_translator.") : t("Tsy mbola azo ny sanda avy amin'ny mpizara.", "Server values are not available yet.")}</span>
          <div>
            <button className="button button--ghost" type="button" disabled={loadingPageChecker || savingPageChecker || savingAutonomousAgent || savingTranslationPrefilter || reloading} onClick={() => void reloadPageCheckerSettings()}>{loadingPageChecker ? t("Mamerina maka...", "Reloading...") : t("Hamerina haka ny automation", "Reload automation")}</button>
            <button className="button button--primary" type="button" disabled={!pageCheckerLoaded || loadingPageChecker || savingPageChecker || savingAutonomousAgent || savingTranslationPrefilter || reloading} onClick={() => void savePageCheckerSettings()}>{savingPageChecker ? t("Mitahiry...", "Saving...") : t("Hitahiry ny automation", "Save automation")}</button>
          </div>
        </div>
      </section>

      <section className="panel settings-maintenance">
        <div><p className="eyebrow">{t("Fikojakojana", "Maintenance")}</p><h3>{t("Materialized views", "Materialized views")}</h3><p>{t("Havaozy araka ny filaharana miankina aminy ireo materialized views rehetra. Mety haharitra minitra maromaro izany.", "Refresh every materialized view in dependency order. This can take several minutes.")}</p></div>
        <button className="button button--primary" type="button" onClick={() => void refreshViews()} disabled={refreshingViews}>{refreshingViews ? t("Manavao...", "Refreshing...") : t("Hanavao ny views rehetra", "Refresh all views")}</button>
      </section>

      <section className="panel settings-database">
        <div className="panel__header"><div><p className="eyebrow">{t("Banky angona", "Database")}</p><h3>{t("Adiresin'ny banky angona", "Database address")}</h3></div><span className="relation-kind relation-kind--view">{t("tantanan'ny mpizara", "server-managed")}</span></div>
        <label className="field"><span>{t("Anaran'ny host an'ny banky angona", "Database hostname")}</span><input value={databaseAddress} onChange={(event) => setDatabaseAddress(event.target.value)} placeholder="db.internal:5432/botjagwar" /></label>
        <div className="notice notice--warning">{t("Tehirizin'i Atlas ity anarana ity mba hahitana ny fampandehanana, saingy tsy mampifandray mivantana mpitety tranonkala amin'ny PostgreSQL mihitsy izy. Ampiasao ao amin'ny mpizara ny `configure-atlas.sh --database-uri ...` hanavaozana ny URI backend voaaro.", "Atlas stores this name for deployment visibility, but never connects the browser directly to PostgreSQL. Run `configure-atlas.sh --database-uri ...` on the server to update the protected backend URI.")}</div>
      </section>

      <div className="settings-grid">
        {serviceFields.map((service) => {
          const configuredAddresses = fromTextarea(addresses[service.field]);
          return (
            <section className="panel settings-service" key={service.field}>
              <div className="panel__header"><div><p className="eyebrow">{t("Vondrona failover", "Failover group")}</p><h3>{service.label}</h3></div><strong>{configuredAddresses.length}</strong></div>
              <p>{service.description} {t("Andraman'i Atlas araka ny filaharany avy any ambony ireo adiresy.", "Atlas tries the addresses in order from the top.")}</p>
              <label className="field"><span>{t("URL iray isaky ny andalana", "One URL per line")}</span><textarea rows={5} value={addresses[service.field]} onChange={(event) => setAddresses({ ...addresses, [service.field]: event.target.value })} required /></label>
              <div className="address-checks">
                {configuredAddresses.map((address) => {
                  const status = checks[`${address}-${service.healthPath}`];
                  return <button type="button" key={address} onClick={() => void testAddress(address, service.healthPath)}><span className={`address-status address-status--${status ?? "idle"}`} /><div><strong>{address}</strong><small>{status === "checking" ? t("Manamarina...", "Checking...") : status === "online" ? t("Mandeha", "Online") : status === "offline" ? t("Tsy mandeha", "Offline") : t("Hitsapa fifandraisana", "Test connection")}</small></div></button>;
                })}
              </div>
            </section>
          );
        })}
      </div>
    </div>
  );
}
