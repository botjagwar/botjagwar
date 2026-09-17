import { useEffect, useState } from "react";

import { getDashboardStatistics, getDatabaseStats, getTranslatorHealth } from "../api";
import { formatDate, formatDateTime, useI18n } from "../i18n";
import type { DashboardPeriod, DashboardStatistic, RelationDefinition, Row, TranslationHealth } from "../types";

interface DashboardProps {
  tableRelations: RelationDefinition[];
  viewRelations: RelationDefinition[];
  onOpenRelation: (name: string) => void;
}

type LoadStatus = "loading" | "ready" | "error";

const OPERATIONAL_REFRESH_MS = 60_000;
const STATISTICS_REFRESH_MS = 300_000;
const STATISTICS_STALE_MS = 600_000;

function formatBytes(value: unknown): string {
  const bytes = Number(value);
  if (!Number.isFinite(bytes)) return "-";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let size = bytes;
  let unit = 0;
  while (size >= 1024 && unit < units.length - 1) {
    size /= 1024;
    unit += 1;
  }
  return `${size.toFixed(size >= 10 ? 0 : 1)} ${units[unit]}`;
}

export function Dashboard({ tableRelations, viewRelations, onOpenRelation }: DashboardProps) {
  const { locale, t } = useI18n();
  const [stats, setStats] = useState<Row[]>([]);
  const [dashboardStats, setDashboardStats] = useState<DashboardStatistic[]>([]);
  const [languagePeriod, setLanguagePeriod] = useState<DashboardPeriod>("last_7_days");
  const [health, setHealth] = useState<TranslationHealth | null>(null);
  const [databaseStatus, setDatabaseStatus] = useState<LoadStatus>("loading");
  const [healthStatus, setHealthStatus] = useState<LoadStatus>("loading");
  const [dashboardStatus, setDashboardStatus] = useState<LoadStatus>("loading");
  const [dashboardIsStale, setDashboardIsStale] = useState(false);

  const healthStatusLabels: Record<string, string> = {
    healthy: t("Salama", "Healthy"),
    ok: t("Mandeha", "Operational"),
    online: t("Mandeha", "Online"),
    degraded: t("Misy olana", "Degraded"),
    unavailable: t("Tsy misy", "Unavailable"),
    offline: t("Tsy mandeha", "Offline"),
  };

  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    const refreshOperationalData = () => {
      getDatabaseStats(controller.signal).then((value) => {
        if (active) {
          setStats(value);
          setDatabaseStatus("ready");
        }
      }).catch(() => {
        if (active) setDatabaseStatus("error");
      });
      getTranslatorHealth(controller.signal).then((value) => {
        if (active) {
          setHealth(value);
          setHealthStatus("ready");
        }
      }).catch(() => {
        if (active) setHealthStatus("error");
      });
    };
    refreshOperationalData();

    const refreshDashboardStatistics = () => {
      getDashboardStatistics().then((value) => {
        if (active) {
          setDashboardStats(value);
          setDashboardStatus("ready");
          const generatedAt = value[0] ? Date.parse(value[0].generated_at) : Number.NaN;
          setDashboardIsStale(value.length > 0
            && (!Number.isFinite(generatedAt) || Date.now() - generatedAt > STATISTICS_STALE_MS));
        }
      }).catch(() => {
        if (active) setDashboardStatus("error");
      });
    };
    refreshDashboardStatistics();
    const operationalTimer = window.setInterval(refreshOperationalData, OPERATIONAL_REFRESH_MS);
    const statisticsTimer = window.setInterval(refreshDashboardStatistics, STATISTICS_REFRESH_MS);
    return () => {
      active = false;
      controller.abort();
      window.clearInterval(operationalTimer);
      window.clearInterval(statisticsTimer);
    };
  }, []);

  const number = new Intl.NumberFormat(locale === "mg" ? "mg-MG" : "en");
  const periodLabels: Record<DashboardPeriod, string> = {
    last_day: t("24 ora farany", "Last 24 hours"),
    last_7_days: t("7 andro farany", "Last 7 days"),
    last_week: t("Herinandro lasa", "Previous week"),
    last_month: t("Volana lasa", "Previous month"),
    year_to_date: t("Tamin'ity taona ity", "Year to date"),
    last_year: t("Taona lasa", "Previous year"),
  };
  const languagePeriods: DashboardPeriod[] = ["last_day", "last_7_days", "last_month", "last_year"];
  const selectedLanguages = dashboardStats.find((item) => item.period === languagePeriod)?.translated_languages ?? [];
  const largestLanguageCount = selectedLanguages[0]?.translated_entries ?? 1;
  const missingTimestampCount = dashboardStats[0]?.missing_timestamp_count ?? 0;
  const warning = databaseStatus === "error" || healthStatus === "error" || dashboardStatus === "error";

  return (
    <div className="dashboard-stack">
      {warning && <div className="notice notice--warning" role="alert">{t("Misy tolotra sasany tsy mandeha. Mbola azo ampiasaina amin'ireo API azo tratrarina ny konsoly.", "Some services are unavailable. The console remains usable for reachable APIs.")}</div>}
      {dashboardIsStale && <div className="notice notice--warning" role="status">{t("Lany andro ny antontanisan'ny dashboard. Mety tsy nandeha ny asa fanavaozana.", "Dashboard statistics are stale. The refresh job may not be running.")}</div>}
      <section className="hero-panel">
        <div>
          <p className="eyebrow">{t("Sarin'ny rafitra", "System map")}</p>
          <h2>{t("Konsoly iray hitantanana ny angona voambolana sy ny asa fandikan-teny.", "One console for managing lexical data and translation operations.")}</h2>
          <p>{t("Zahao ireo singa rehetra aseho, ovay amim-pitandremana ny angona, ary avadiho ho dikanteny voavoaka ny pejy loharano nefa tsy mila manova fitaovana.", "Browse every exposed relation, edit data carefully, and turn source pages into published translations without switching tools.")}</p>
        </div>
        <div className="hero-panel__glyph" aria-hidden="true">
          <span>DB</span>
          <i />
          <span>MG</span>
        </div>
      </section>

      <section className="metric-grid" aria-label={t("Topimaso momba ny rafitra", "System overview")}>
        <article className="metric-card metric-card--accent">
          <span>{t("Tabilao tantanana", "Managed tables")}</span>
          <strong>{tableRelations.length}</strong>
          <small>{t("Katalaogy CRUD PostgREST", "PostgREST CRUD catalog")}</small>
        </article>
        <article className="metric-card">
          <span>{t("Tatitra sy views", "Reports and views")}</span>
          <strong>{viewRelations.length}</strong>
          <small>{t("Mivantana sy materialized", "Live and materialized")}</small>
        </article>
        <article className="metric-card">
          <span>{t("Mpandika teny", "Translator")}</span>
          <strong>{healthStatus === "loading" ? t("Eo am-pakana...", "Loading...") : health?.status ? healthStatusLabels[health.status.toLowerCase()] ?? health.status : t("Tsy fantatra", "Unknown")}</strong>
          <small>{t(`Asa mandeha: ${String(health?.process_running_jobs ?? health?.running_jobs ?? 0)}`, `Active jobs: ${String(health?.process_running_jobs ?? health?.running_jobs ?? 0)}`)}</small>
        </article>
        <article className="metric-card">
          <span>{t("Singa lehibe indrindra", "Largest relation")}</span>
          <strong className="metric-card__compact">{stats[0]?.table_name === undefined || stats[0]?.table_name === null ? t("Tsy misy", "Unavailable") : String(stats[0].table_name)}</strong>
          <small>{formatBytes(stats[0]?.total_bytes)}</small>
        </article>
      </section>

      <section className="statistics-panel panel">
        <div className="panel__header">
          <div><p className="eyebrow">{t("Fitomboan'ny rakibolana", "Dictionary growth")}</p><h3>{t("Teny vaovao isaky ny vanim-potoana", "New entries by period")}</h3></div>
          {dashboardStats[0] && <small>{t("Nokajiana", "Calculated")} <time dateTime={dashboardStats[0].generated_at}>{formatDateTime(locale, new Date(dashboardStats[0].generated_at), "UTC")}</time> UTC</small>}
        </div>
        {dashboardStatus === "loading" ? <p className="empty-inline">{t("Eo am-pakana ny antontanisa...", "Loading statistics...")}</p> : dashboardStatus === "error" ? <p className="empty-inline">{t("Tsy azo ny antontanisa.", "Statistics are unavailable.")}</p> : dashboardStats.length === 0 ? <p className="empty-inline">{t("Tsy nisy antontanisa naverina.", "No statistics were returned.")}</p> : (
          <div className="entry-stat-grid">
            {dashboardStats.map((item) => <article key={item.period}><span>{periodLabels[item.period]}</span><strong>{number.format(item.entry_count)}</strong><small><time dateTime={item.period_start}>{formatDate(locale, new Date(item.period_start), "UTC")}</time> - <time dateTime={item.period_end}>{formatDate(locale, new Date(item.period_end), "UTC")}</time></small></article>)}
          </div>
        )}
        {missingTimestampCount > 0 && <div className="notice notice--warning">{t(`Teny ${number.format(missingTimestampCount)} no tsy manana daty namoronana ka tsy tafiditra amin'ireo isa ireo.`, `${number.format(missingTimestampCount)} entries have no creation timestamp and are excluded from these counts.`)}</div>}
      </section>

      <section className="language-statistics panel">
        <div className="panel__header">
          <div><p className="eyebrow">{t("Fandikan-teny", "Translation activity")}</p><h3>{t("Fiteny loharano nadika indrindra", "Most translated source languages")}</h3><p>{t("Teny tsy malagasy nahazo famaritana malagasy iray farafahakeliny tao anatin'ity vanim-potoana ity.", "Non-Malagasy entries that received at least one Malagasy definition during this period.")}</p></div>
        </div>
        <div className="statistics-tabs" role="group" aria-label={t("Vanim-potoanan'ny fiteny", "Language statistics period")}>
          {languagePeriods.map((period) => <button aria-pressed={languagePeriod === period} className={languagePeriod === period ? "statistics-tabs__active" : ""} type="button" key={period} onClick={() => setLanguagePeriod(period)}>{periodLabels[period]}</button>)}
        </div>
        <div className="language-ranking">
          {selectedLanguages.length === 0 && <p className="empty-inline">{t("Tsy misy dikanteny amin'ity vanim-potoana ity.", "No translated entries in this period.")}</p>}
          {selectedLanguages.map((item, index) => <div className="language-rank" key={item.language}><span>{String(index + 1).padStart(2, "0")}</span><div><strong>{(locale === "mg" ? item.malagasy_name : item.english_name) ?? item.english_name ?? item.malagasy_name ?? item.language}</strong><small>{item.language}</small></div><div className="language-rank__track"><i style={{ width: `${Math.max(3, (item.translated_entries / largestLanguageCount) * 100)}%` }} /></div><b>{number.format(item.translated_entries)}</b></div>)}
        </div>
      </section>

      <section className="split-grid">
        <article className="panel">
          <div className="panel__header">
            <div>
              <p className="eyebrow">{t("Mombamomba ny fitehirizana", "Storage profile")}</p>
              <h3>{t("Singa lehibe indrindra", "Largest relations")}</h3>
            </div>
            <button className="text-button" type="button" onClick={() => onOpenRelation("db_stats")}>{t("Hijery rehetra", "View all")}</button>
          </div>
          <div className="storage-list">
            {databaseStatus === "loading" ? <p className="empty-inline">{t("Eo am-pakana ny antontanisan'ny banky angona...", "Loading database statistics...")}</p> : stats.length === 0 && <p className="empty-inline">{t("Tsy misy ny antontanisan'ny banky angona.", "Database statistics are unavailable.")}</p>}
            {stats.slice(0, 6).map((row, index) => {
              const largest = Number(stats[0]?.total_bytes ?? 1);
              const width = Math.max(4, (Number(row.total_bytes ?? 0) / largest) * 100);
              return (
                <div className="storage-row" key={`${String(row.table_schema)}-${String(row.table_name)}-${index}`}>
                  <div><strong>{String(row.table_name)}</strong><span>{formatBytes(row.total_bytes)}</span></div>
                  <div className="storage-row__track"><i style={{ width: `${width}%` }} /></div>
                </div>
              );
            })}
          </div>
        </article>

        <article className="panel">
          <div className="panel__header">
            <div>
              <p className="eyebrow">{t("Fidirana haingana", "Quick access")}</p>
              <h3>{t("Angona fototra", "Core datasets")}</h3>
            </div>
          </div>
          <div className="quick-list">
            {tableRelations.slice(0, 5).map((relation, index) => (
              <button type="button" key={relation.name} onClick={() => onOpenRelation(relation.name)}>
                <span>{String(index + 1).padStart(2, "0")}</span>
                <div><strong>{relation.label}</strong><small>{relation.description}</small></div>
                <b aria-hidden="true">↗</b>
              </button>
            ))}
          </div>
        </article>
      </section>
    </div>
  );
}
