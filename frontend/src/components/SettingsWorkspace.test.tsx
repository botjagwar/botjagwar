import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";

import { ApiResponseError, getDefinitionTranslationSettings, getGemmaSettings, getPageCheckerSettings, refreshMaterializedViews, updateDefinitionTranslationSettings, updateGemmaSettings, updatePageCheckerAutonomousAgent, updatePageCheckerSettings, updatePageCheckJobHistoryLimit, updateTranslationPrefilter } from "../api";
import { defaultConfig } from "../config";
import { I18nProvider } from "../i18n";
import { ThemeProvider } from "../theme";
import type { PageCheckerAutomationSettings, PageCheckerMonitoringSettings } from "../types";
import { SettingsWorkspace } from "./SettingsWorkspace";

vi.mock("../api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../api")>();
  return { ApiResponseError: actual.ApiResponseError, getDefinitionTranslationSettings: vi.fn(), getGemmaSettings: vi.fn(), getPageCheckerSettings: vi.fn(), refreshMaterializedViews: vi.fn(), updateDefinitionTranslationSettings: vi.fn(), updateGemmaSettings: vi.fn(), updatePageCheckerAutonomousAgent: vi.fn(), updatePageCheckerSettings: vi.fn(), updatePageCheckJobHistoryLimit: vi.fn(), updateTranslationPrefilter: vi.fn() };
});

beforeEach(() => {
  window.localStorage.removeItem("botjagwar-atlas-theme");
  delete document.documentElement.dataset.theme;
  vi.mocked(getPageCheckerSettings).mockResolvedValue({ watched_users: ["Alice"], check_probability: 25, cooldown_seconds: 60, ignored_edit_summaries: ["fanitsiana famaritana", "Dikanteny: es"], job_history_limit: 2500, autonomous_agent_enabled: false, translation_prefilter_enabled: false });
  vi.mocked(getDefinitionTranslationSettings).mockResolvedValue({ basic_english_gate_enabled: false, nllb_roundtrip_validation_enabled: true });
  vi.mocked(getGemmaSettings).mockResolvedValue({ api_url: "http://127.0.0.1:8891/v1/chat/completions", model: "gemma-4" });
  vi.mocked(updateDefinitionTranslationSettings).mockImplementation(async (settings) => settings);
  vi.mocked(updatePageCheckerAutonomousAgent).mockImplementation(async (enabled) => ({ autonomous_agent_enabled: enabled }));
  vi.mocked(updateTranslationPrefilter).mockImplementation(async (enabled) => ({ translation_prefilter_enabled: enabled }));
  vi.mocked(updatePageCheckJobHistoryLimit).mockImplementation(async (limit) => ({ job_history_limit: limit }));
});

afterEach(() => {
  cleanup();
  vi.resetAllMocks();
});

it("changes and persists the Mac OS interface theme immediately", () => {
  render(<ThemeProvider><I18nProvider><SettingsWorkspace config={defaultConfig} onSave={vi.fn()} onReset={vi.fn()} onReload={vi.fn()} onMessage={vi.fn()} /></I18nProvider></ThemeProvider>);

  const macOsTheme = screen.getByRole("radio", { name: /Mac OS/ });
  expect(macOsTheme).not.toBeChecked();
  fireEvent.click(macOsTheme);

  expect(macOsTheme).toBeChecked();
  expect(document.documentElement).toHaveAttribute("data-theme", "mac-os");
  expect(window.localStorage.getItem("botjagwar-atlas-theme")).toBe("mac-os");
});

it("reloads runtime configuration and refreshes materialized views", async () => {
  const onReload = vi.fn().mockResolvedValue(undefined);
  const onMessage = vi.fn();
  vi.mocked(refreshMaterializedViews).mockResolvedValue({ refreshed_views: 9, completed_at: "2026-08-14T00:00:00Z" });
  render(<ThemeProvider><I18nProvider><SettingsWorkspace config={defaultConfig} onSave={vi.fn()} onReset={vi.fn()} onReload={onReload} onMessage={onMessage} /></I18nProvider></ThemeProvider>);

  fireEvent.click(screen.getByRole("button", { name: "Hamerina haka ny fikirana" }));
  await waitFor(() => expect(onReload).toHaveBeenCalledOnce());

  fireEvent.click(screen.getByRole("button", { name: "Hanavao ny views rehetra" }));
  await waitFor(() => expect(refreshMaterializedViews).toHaveBeenCalledOnce());
  expect(onMessage).toHaveBeenCalledWith("Materialized views 9 no nohavaozina.");
});

it("loads, canonicalizes, and saves server-managed page-checker settings", async () => {
  const onMessage = vi.fn();
  vi.mocked(updatePageCheckerSettings).mockResolvedValue({ watched_users: ["Alice", "Bob", "Carol"], check_probability: 76, cooldown_seconds: 5, ignored_edit_summaries: ["fanitsiana famaritana", "Rule, with comma"] });
  render(<ThemeProvider><I18nProvider><SettingsWorkspace config={defaultConfig} onSave={vi.fn()} onReset={vi.fn()} onReload={vi.fn()} onMessage={onMessage} /></I18nProvider></ThemeProvider>);

  expect(await screen.findByLabelText("Mpampiasa arahi-maso")).toHaveValue("Alice");
  expect(getPageCheckerSettings).toHaveBeenCalledWith(expect.any(AbortSignal));
  const agentSwitch = screen.getByRole("switch", { name: "Mpiasa fanitsiana GitHub mandeha ho azy" });
  expect(agentSwitch).not.toBeChecked();
  expect(screen.getByText(/Tsy mifehy ny famoahana fanitsiana ao amin'ny Wiktionary/)).toBeInTheDocument();

  fireEvent.change(screen.getByLabelText("Mpampiasa arahi-maso"), { target: { value: " Alice \n,\n Bob,  Carol  " } });
  fireEvent.change(screen.getByLabelText("Tahan'ny fanamarinana (%)"), { target: { value: "75.5" } });
  fireEvent.change(screen.getByLabelText("Fotoana fiandrasana (segondra)"), { target: { value: "0" } });
  fireEvent.change(screen.getByLabelText("Famintinana fanovana tsy raharahaina"), { target: { value: " fanitsiana famaritana \n Rule, with comma " } });
  fireEvent.click(agentSwitch);
  await waitFor(() => expect(updatePageCheckerAutonomousAgent).toHaveBeenCalledWith(true));
  expect(agentSwitch).toBeChecked();
  const saveButton = screen.getByRole("button", { name: "Hitahiry ny automation" });
  expect(saveButton).toHaveAttribute("type", "button");
  fireEvent.click(saveButton);

  await waitFor(() => expect(updatePageCheckerSettings).toHaveBeenCalledWith({
    watched_users: ["Alice", "Bob", "Carol"],
    check_probability: 75.5,
    cooldown_seconds: 0,
    ignored_edit_summaries: ["fanitsiana famaritana", "Rule, with comma"],
  }));
  await waitFor(() => expect(screen.getByLabelText("Tahan'ny fanamarinana (%)")).toHaveValue(76));
  expect(screen.getByLabelText("Mpampiasa arahi-maso")).toHaveValue("Alice\nBob\nCarol");
  expect(screen.getByLabelText("Fotoana fiandrasana (segondra)")).toHaveValue(5);
  expect(screen.getByLabelText("Famintinana fanovana tsy raharahaina")).toHaveValue("fanitsiana famaritana\nRule, with comma");
  expect(agentSwitch).toBeChecked();
  expect(onMessage).toHaveBeenCalledWith("Nalefa ny mpiasa fanitsiana GitHub mandeha ho azy.");
  expect(onMessage).toHaveBeenCalledWith("Voatahiry tao amin'ny mpizara ny fikirakirana fanamarinana pejy.");
});

it("loads and saves the server-managed job-history size", async () => {
  const onMessage = vi.fn();
  vi.mocked(updatePageCheckJobHistoryLimit).mockResolvedValue({ job_history_limit: 7500 });
  render(<ThemeProvider><I18nProvider><SettingsWorkspace config={defaultConfig} onSave={vi.fn()} onReset={vi.fn()} onReload={vi.fn()} onMessage={onMessage} /></I18nProvider></ThemeProvider>);

  const historyLimit = await screen.findByLabelText("Isan'ny asa ao amin'ny tantara");
  expect(historyLimit).toHaveValue(2500);
  fireEvent.change(historyLimit, { target: { value: "7500" } });
  fireEvent.click(screen.getByRole("button", { name: "Hitahiry ny haben'ny tantara" }));

  await waitFor(() => expect(updatePageCheckJobHistoryLimit).toHaveBeenCalledWith(7500));
  expect(historyLimit).toHaveValue(7500);
  expect(onMessage).toHaveBeenCalledWith("Voatahiry tao amin'ny mpizara ny isan'ny asa aseho.");
});

it("toggles the server-managed translation publication prefilter", async () => {
  const onMessage = vi.fn();
  render(<ThemeProvider><I18nProvider><SettingsWorkspace config={defaultConfig} onSave={vi.fn()} onReset={vi.fn()} onReload={vi.fn()} onMessage={onMessage} /></I18nProvider></ThemeProvider>);

  const prefilterSwitch = await screen.findByRole("switch", { name: "Sivana page checker alohan'ny famoahana" });
  await waitFor(() => expect(prefilterSwitch).toBeEnabled());
  expect(prefilterSwitch).not.toBeChecked();
  expect(screen.getByText(/good ihany/)).toBeInTheDocument();

  fireEvent.click(prefilterSwitch);

  await waitFor(() => expect(updateTranslationPrefilter).toHaveBeenCalledWith(true));
  expect(prefilterSwitch).toBeChecked();
  expect(onMessage).toHaveBeenCalledWith("Nalefa ny sivana page checker alohan'ny famoahana.");
});

it("rejects a job-history size outside the supported range", async () => {
  const onMessage = vi.fn();
  render(<ThemeProvider><I18nProvider><SettingsWorkspace config={defaultConfig} onSave={vi.fn()} onReset={vi.fn()} onReload={vi.fn()} onMessage={onMessage} /></I18nProvider></ThemeProvider>);

  const historyLimit = await screen.findByLabelText("Isan'ny asa ao amin'ny tantara");
  fireEvent.change(historyLimit, { target: { value: "100001" } });
  fireEvent.click(screen.getByRole("button", { name: "Hitahiry ny haben'ny tantara" }));

  expect(updatePageCheckJobHistoryLimit).not.toHaveBeenCalled();
  expect(onMessage).toHaveBeenCalledWith("Tokony ho isa manontolo eo anelanelan'ny 1 sy 100000 ny isan'ny asa tehirizina.", "error");
});

it("explains when the translator has not been updated for job-history settings", async () => {
  const onMessage = vi.fn();
  vi.mocked(updatePageCheckJobHistoryLimit).mockRejectedValue(new ApiResponseError("Hadisoana HTTP 404", 404));
  render(<ThemeProvider><I18nProvider><SettingsWorkspace config={defaultConfig} onSave={vi.fn()} onReset={vi.fn()} onReload={vi.fn()} onMessage={onMessage} /></I18nProvider></ThemeProvider>);

  await screen.findByLabelText("Isan'ny asa ao amin'ny tantara");
  fireEvent.click(screen.getByRole("button", { name: "Hitahiry ny haben'ny tantara" }));

  await waitFor(() => expect(onMessage).toHaveBeenCalledWith("Tsy mbola manohana ity fikirana ity ny entry_translator. Havaozy na avereno alefa ny instances rehetra.", "error"));
});

it("loads and toggles the server-managed Basic English gate", async () => {
  const onMessage = vi.fn();
  vi.mocked(getDefinitionTranslationSettings).mockResolvedValue({ basic_english_gate_enabled: true, nllb_roundtrip_validation_enabled: true });
  render(<ThemeProvider><I18nProvider><SettingsWorkspace config={defaultConfig} onSave={vi.fn()} onReset={vi.fn()} onReload={vi.fn()} onMessage={onMessage} /></I18nProvider></ThemeProvider>);

  const gateSwitch = await screen.findByRole("switch", { name: "Sivana voambolana Basic English" });
  await waitFor(() => expect(gateSwitch).toBeEnabled());
  expect(gateSwitch).toBeChecked();
  expect(screen.getByText(/75% farafahakeliny/)).toBeInTheDocument();

  fireEvent.click(gateSwitch);

  await waitFor(() => expect(updateDefinitionTranslationSettings).toHaveBeenCalledWith({
    basic_english_gate_enabled: false,
    nllb_roundtrip_validation_enabled: true,
  }));
  expect(gateSwitch).not.toBeChecked();
  expect(onMessage).toHaveBeenCalledWith("Najano ny sivana voambolana Basic English.");
});

it("loads and saves the server-managed Gemma endpoint", async () => {
  const onMessage = vi.fn();
  vi.mocked(updateGemmaSettings).mockResolvedValue({ api_url: "https://gemma.example/v1/chat/completions", model: "gemma-4" });
  render(<ThemeProvider><I18nProvider><SettingsWorkspace config={defaultConfig} onSave={vi.fn()} onReset={vi.fn()} onReload={vi.fn()} onMessage={onMessage} /></I18nProvider></ThemeProvider>);

  const endpoint = await screen.findByLabelText("URL endpoint Gemma");
  expect(endpoint).toHaveValue("http://127.0.0.1:8891/v1/chat/completions");
  expect(screen.getByText("gemma-4")).toBeInTheDocument();
  fireEvent.change(endpoint, { target: { value: " https://gemma.example/v1/chat/completions " } });
  fireEvent.click(screen.getByRole("button", { name: "Hitahiry ny endpoint" }));

  await waitFor(() => expect(updateGemmaSettings).toHaveBeenCalledWith("https://gemma.example/v1/chat/completions"));
  expect(endpoint).toHaveValue("https://gemma.example/v1/chat/completions");
  expect(onMessage).toHaveBeenCalledWith("Voatahiry tao amin'ny mpizara ny endpoint Gemma.");
});

it("toggles server-managed NLLB round-trip validation", async () => {
  const onMessage = vi.fn();
  render(<ThemeProvider><I18nProvider><SettingsWorkspace config={defaultConfig} onSave={vi.fn()} onReset={vi.fn()} onReload={vi.fn()} onMessage={onMessage} /></I18nProvider></ThemeProvider>);

  const roundtripSwitch = await screen.findByRole("switch", { name: "Fanamarinana fandikana miverina NLLB" });
  await waitFor(() => expect(roundtripSwitch).toBeEnabled());
  expect(roundtripSwitch).toBeChecked();
  expect(screen.getByText(/Mbola ampiharina foana ny fiarovana/)).toBeInTheDocument();

  fireEvent.click(roundtripSwitch);

  await waitFor(() => expect(updateDefinitionTranslationSettings).toHaveBeenCalledWith({
    basic_english_gate_enabled: false,
    nllb_roundtrip_validation_enabled: false,
  }));
  expect(roundtripSwitch).not.toBeChecked();
  expect(onMessage).toHaveBeenCalledWith("Najano ny fanamarinana fandikana miverina NLLB.");
});

it("restores the Basic English gate after a failed update", async () => {
  const onMessage = vi.fn();
  vi.mocked(updateDefinitionTranslationSettings).mockRejectedValue(new Error("save failed"));
  render(<ThemeProvider><I18nProvider><SettingsWorkspace config={defaultConfig} onSave={vi.fn()} onReset={vi.fn()} onReload={vi.fn()} onMessage={onMessage} /></I18nProvider></ThemeProvider>);

  const gateSwitch = await screen.findByRole("switch", { name: "Sivana voambolana Basic English" });
  await waitFor(() => expect(gateSwitch).toBeEnabled());
  fireEvent.click(gateSwitch);

  await waitFor(() => expect(onMessage).toHaveBeenCalledWith("save failed", "error"));
  expect(gateSwitch).not.toBeChecked();
});

it("uses the authoritative Basic English gate after an ambiguous update failure", async () => {
  const onMessage = vi.fn();
  vi.mocked(getDefinitionTranslationSettings)
    .mockResolvedValueOnce({ basic_english_gate_enabled: false, nllb_roundtrip_validation_enabled: true })
    .mockResolvedValueOnce({ basic_english_gate_enabled: true, nllb_roundtrip_validation_enabled: true });
  vi.mocked(updateDefinitionTranslationSettings).mockRejectedValue(new Error("response lost"));
  render(<ThemeProvider><I18nProvider><SettingsWorkspace config={defaultConfig} onSave={vi.fn()} onReset={vi.fn()} onReload={vi.fn()} onMessage={onMessage} /></I18nProvider></ThemeProvider>);

  const gateSwitch = await screen.findByRole("switch", { name: "Sivana voambolana Basic English" });
  await waitFor(() => expect(gateSwitch).toBeEnabled());
  fireEvent.click(gateSwitch);

  await waitFor(() => expect(gateSwitch).toBeChecked());
  expect(getDefinitionTranslationSettings).toHaveBeenCalledTimes(2);
  expect(onMessage).toHaveBeenCalledWith("response lost", "error");
});

it("reloads page-checker settings independently from runtime configuration", async () => {
  const onReload = vi.fn();
  const onMessage = vi.fn();
  vi.mocked(getPageCheckerSettings)
    .mockResolvedValueOnce({ watched_users: ["Alice"], check_probability: 25, cooldown_seconds: 60, ignored_edit_summaries: ["first"], job_history_limit: 2500, autonomous_agent_enabled: false, translation_prefilter_enabled: false })
    .mockResolvedValueOnce({ watched_users: ["Bob"], check_probability: 80, cooldown_seconds: 120, ignored_edit_summaries: ["second"], job_history_limit: 4000, autonomous_agent_enabled: true, translation_prefilter_enabled: true });
  render(<ThemeProvider><I18nProvider><SettingsWorkspace config={defaultConfig} onSave={vi.fn()} onReset={vi.fn()} onReload={onReload} onMessage={onMessage} /></I18nProvider></ThemeProvider>);

  expect(await screen.findByLabelText("Mpampiasa arahi-maso")).toHaveValue("Alice");
  const reloadButton = screen.getByRole("button", { name: "Hamerina haka ny automation" });
  expect(reloadButton).toHaveAttribute("type", "button");
  fireEvent.click(reloadButton);

  await waitFor(() => expect(screen.getByLabelText("Mpampiasa arahi-maso")).toHaveValue("Bob"));
  expect(screen.getByLabelText("Famintinana fanovana tsy raharahaina")).toHaveValue("second");
  expect(screen.getByRole("switch", { name: "Mpiasa fanitsiana GitHub mandeha ho azy" })).toBeChecked();
  expect(screen.getByRole("switch", { name: "Sivana page checker alohan'ny famoahana" })).toBeChecked();
  expect(getPageCheckerSettings).toHaveBeenCalledTimes(2);
  expect(onReload).not.toHaveBeenCalled();
  expect(onMessage).toHaveBeenCalledWith("Naverina nalaina tamin'ny mpizara ny fikirakirana fanamarinana pejy.");
});

it("restores the authoritative autonomous-agent value after a failed toggle", async () => {
  const enabledSettings: PageCheckerAutomationSettings = { watched_users: ["Alice"], check_probability: 25, cooldown_seconds: 60, ignored_edit_summaries: ["first"], job_history_limit: 2500, autonomous_agent_enabled: true, translation_prefilter_enabled: false };
  const onMessage = vi.fn();
  vi.mocked(getPageCheckerSettings).mockResolvedValue(enabledSettings);
  vi.mocked(updatePageCheckerAutonomousAgent).mockRejectedValue(new Error("save failed"));
  render(<ThemeProvider><I18nProvider><SettingsWorkspace config={defaultConfig} onSave={vi.fn()} onReset={vi.fn()} onReload={vi.fn()} onMessage={onMessage} /></I18nProvider></ThemeProvider>);

  const agentSwitch = await screen.findByRole("switch", { name: "Mpiasa fanitsiana GitHub mandeha ho azy" });
  fireEvent.click(agentSwitch);

  await waitFor(() => expect(onMessage).toHaveBeenCalledWith("save failed", "error"));
  expect(agentSwitch).toBeChecked();
});

it("shows an unknown disabled switch after an ambiguous toggle failure", async () => {
  const enabledSettings: PageCheckerAutomationSettings = { watched_users: ["Alice"], check_probability: 25, cooldown_seconds: 60, ignored_edit_summaries: ["first"], job_history_limit: 2500, autonomous_agent_enabled: true, translation_prefilter_enabled: false };
  vi.mocked(getPageCheckerSettings)
    .mockResolvedValueOnce(enabledSettings)
    .mockRejectedValueOnce(new Error("offline"));
  vi.mocked(updatePageCheckerAutonomousAgent).mockRejectedValue(new Error("save failed"));
  render(<ThemeProvider><I18nProvider><SettingsWorkspace config={defaultConfig} onSave={vi.fn()} onReset={vi.fn()} onReload={vi.fn()} onMessage={vi.fn()} /></I18nProvider></ThemeProvider>);

  const agentSwitch = await screen.findByRole("switch", { name: "Mpiasa fanitsiana GitHub mandeha ho azy" });
  fireEvent.click(agentSwitch);

  await waitFor(() => expect(screen.getByText("Tsy fantatra")).toBeInTheDocument());
  expect(agentSwitch).toBeDisabled();
});

it("reports invalid page-checker values without sending an update", async () => {
  const onMessage = vi.fn();
  render(<ThemeProvider><I18nProvider><SettingsWorkspace config={defaultConfig} onSave={vi.fn()} onReset={vi.fn()} onReload={vi.fn()} onMessage={onMessage} /></I18nProvider></ThemeProvider>);

  await screen.findByDisplayValue("Alice");
  fireEvent.change(screen.getByLabelText("Tahan'ny fanamarinana (%)"), { target: { value: "101" } });
  fireEvent.click(screen.getByRole("button", { name: "Hitahiry ny automation" }));

  expect(updatePageCheckerSettings).not.toHaveBeenCalled();
  expect(onMessage).toHaveBeenCalledWith("Tokony ho isa eo anelanelan'ny 0 sy 100 ny tahan'ny fanamarinana.", "error");
});

it("keeps runtime saving independent from an invalid automation draft", async () => {
  const onSave = vi.fn();
  const onMessage = vi.fn();
  render(<ThemeProvider><I18nProvider><SettingsWorkspace config={defaultConfig} onSave={onSave} onReset={vi.fn()} onReload={vi.fn()} onMessage={onMessage} /></I18nProvider></ThemeProvider>);

  await screen.findByDisplayValue("Alice");
  fireEvent.change(screen.getByLabelText("Fotoana fiandrasana (segondra)"), { target: { value: "86401" } });
  fireEvent.click(screen.getByRole("button", { name: "Hitahiry ny fikirana" }));

  expect(onSave).toHaveBeenCalledOnce();
  fireEvent.click(screen.getByRole("button", { name: "Hitahiry ny automation" }));
  expect(updatePageCheckerSettings).not.toHaveBeenCalled();
  expect(onMessage).toHaveBeenCalledWith("Tokony ho isa eo anelanelan'ny 0 sy 86400 ny fotoana fiandrasana.", "error");
});

it("rejects runtime settings with an empty service address list", async () => {
  const onSave = vi.fn();
  const onMessage = vi.fn();
  render(<ThemeProvider><I18nProvider><SettingsWorkspace config={defaultConfig} onSave={onSave} onReset={vi.fn()} onReload={vi.fn()} onMessage={onMessage} /></I18nProvider></ThemeProvider>);

  await screen.findByDisplayValue("Alice");
  const serviceAddresses = screen.getAllByLabelText("URL iray isaky ny andalana");
  fireEvent.change(serviceAddresses[0], { target: { value: "" } });
  fireEvent.click(screen.getByRole("button", { name: "Hitahiry ny fikirana" }));

  expect(onSave).not.toHaveBeenCalled();
  expect(onMessage).toHaveBeenCalledWith("Tsy maintsy manana URL iray farafahakeliny ny tolotra tsirairay.", "error");
});

it("prevents runtime actions while automation settings are being saved", async () => {
  let finishSave: ((settings: PageCheckerMonitoringSettings) => void) | undefined;
  vi.mocked(updatePageCheckerSettings).mockImplementation(() => new Promise((resolve) => { finishSave = resolve; }));
  render(<ThemeProvider><I18nProvider><SettingsWorkspace config={defaultConfig} onSave={vi.fn()} onReset={vi.fn()} onReload={vi.fn()} onMessage={vi.fn()} /></I18nProvider></ThemeProvider>);

  await screen.findByDisplayValue("Alice");
  fireEvent.click(screen.getByRole("button", { name: "Hitahiry ny automation" }));

  await waitFor(() => expect(screen.getByRole("button", { name: "Hitahiry ny fikirana" })).toBeDisabled());
  expect(screen.getByRole("button", { name: "Hampiasa ny sanda mahazatra an'ny deployment" })).toBeDisabled();
  finishSave?.({ watched_users: ["Alice"], check_probability: 25, cooldown_seconds: 60, ignored_edit_summaries: ["fanitsiana famaritana"] });
  await waitFor(() => expect(screen.getByRole("button", { name: "Hitahiry ny fikirana" })).toBeEnabled());
});

it("surfaces page-checker load errors through the workspace message handler", async () => {
  const onMessage = vi.fn();
  vi.mocked(getPageCheckerSettings).mockRejectedValue(new Error("translator unavailable"));
  render(<ThemeProvider><I18nProvider><SettingsWorkspace config={defaultConfig} onSave={vi.fn()} onReset={vi.fn()} onReload={vi.fn()} onMessage={onMessage} /></I18nProvider></ThemeProvider>);

  await waitFor(() => expect(onMessage).toHaveBeenCalledWith("translator unavailable", "error"));
  expect(screen.getByRole("button", { name: "Hamerina haka ny automation" })).toBeEnabled();
  expect(screen.getByRole("button", { name: "Hitahiry ny automation" })).toBeDisabled();
});
