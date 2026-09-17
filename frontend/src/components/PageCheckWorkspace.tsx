import { useEffect, useEffectEvent, useRef, useState, type FormEvent } from "react";

import { getPageCheckJob, getPageCheckScoreHistory, getPageCheckStatistics, listPageCheckJobs, startPageCheck } from "../api";
import { formatDate, formatDateTime, useI18n } from "../i18n";
import { rememberPageCheckLanguage } from "../jobCenterTracking";
import { pageCheckMessages, reviewQueueStateMessages } from "../messages/pageCheck";
import type { PageCheckGrade, PageCheckJob, PageCheckJobSummary, PageCheckPeriodStatistics, PageCheckResult, PageCheckScoreSnapshot, PageCheckStatisticsPeriod, PageCheckStatisticsResponse } from "../types";
import { ClassicTitleBar } from "./ClassicTitleBar";

interface PageCheckWorkspaceProps {
  initialJobId?: string;
  initialLanguage?: string;
  onMessage: (message: string, tone?: "success" | "error") => void;
  onTargetChange?: (language: string, jobId: string) => void;
}

type JobStatusFilter = "all" | PageCheckJobSummary["status"];
const JOB_STATUS_LABELS: Record<PageCheckJobSummary["status"], [string, string]> = {
  pending: ["Miandry", "Pending"],
  running: ["Mandeha", "Running"],
  done: ["Vita", "Done"],
  error: ["Hadisoana", "Error"],
};

const JOB_STAGE_LABELS: Record<string, [string, string]> = {
  queued: ["Ao anaty filaharana", "Queued"],
  loading_target: ["Maka ny pejy", "Loading page"],
  resolving_source: ["Mitady loharano", "Resolving source"],
  loading_source: ["Maka ny loharano", "Loading source"],
  loading_reference: ["Maka fanovozan-kevitra", "Loading reference"],
  verifying: ["Mampitaha famaritana", "Verifying definitions"],
  generating_fix: ["Mamorona fanitsiana", "Generating correction"],
  queueing_publication: ["Mandefa havoaka", "Queueing publication"],
  finalising: ["Mamarana", "Finalising"],
  completed: ["Vita", "Completed"],
  failed: ["Tsy nahomby", "Failed"],
  retrying: ["Mamerina", "Retrying"],
  checking: ["Mamarina", "Checking"],
};

const STATISTICS_REFRESH_MS = 60_000;
const SCORE_HISTORY_REFRESH_MS = 5 * 60_000;
const STATISTICS_PERIODS: PageCheckStatisticsPeriod[] = ["today", "last_7_days", "current_week", "current_month", "last_3_months", "last_6_months"];
const STATISTICS_PERIOD_LABELS: Record<PageCheckStatisticsPeriod, [string, string]> = {
  today: ["Androany", "Today"],
  last_7_days: ["7 andro farany", "Last 7 days"],
  current_week: ["Ity herinandro ity", "Current week"],
  current_month: ["Ity volana ity", "Current month"],
  last_3_months: ["3 volana farany", "Last 3 months"],
  last_6_months: ["6 volana farany", "Last 6 months"],
};
const GRADE_WEATHER: Record<Exclude<PageCheckGrade, null>, { symbol: string; weather: [string, string]; quality: [string, string] }> = {
  A: { symbol: "☀", weather: ["Masoandro", "Sunny"], quality: ["Tena tsara", "Excellent"] },
  B: { symbol: "⛅", weather: ["Misy rahona kely", "Partly cloudy"], quality: ["Tsara", "Good"] },
  C: { symbol: "☁", weather: ["Rahona", "Cloudy"], quality: ["Antonony", "Fair"] },
  D: { symbol: "☂", weather: ["Orana", "Rainy"], quality: ["Mila hatsaraina", "Needs improvement"] },
  E: { symbol: "⚡", weather: ["Tafiotra", "Stormy"], quality: ["Mila jerena", "Critical"] },
};

function stageLabel(stage: string | undefined, t: (mg: string, en: string) => string) {
  const labels = JOB_STAGE_LABELS[stage ?? "queued"];
  return labels ? t(...labels) : (stage ?? "queued").replaceAll("_", " ");
}

function reviewQueueStateLabel(state: string | undefined, t: (mg: string, en: string) => string) {
  if (!state) return t(...pageCheckMessages.unknown);
  const labels = reviewQueueStateMessages[state as keyof typeof reviewQueueStateMessages];
  return labels ? t(labels[0], labels[1]) : state.replaceAll("_", " ");
}

function reviewHandoffNeedsPolling(job: Pick<PageCheckJob, "review_queue_state">): boolean {
  return job.review_queue_state === "pending" || job.review_queue_state === "publishing" || job.review_queue_state === "failed";
}

function JobBadge({ status }: { status: PageCheckJobSummary["status"] }) {
  const { t } = useI18n();
  return <span className={`check-badge check-badge--${status === "done" ? "good" : status}`}>{t(...JOB_STATUS_LABELS[status])}</span>;
}

function ProgressBar({ progress, done }: { progress: number; done: boolean }) {
  return (
    <span className={`check-progress${done ? " check-progress--complete" : ""}`} role="progressbar" aria-valuenow={progress} aria-valuemin={0} aria-valuemax={100}>
      <i style={{ width: `${Math.max(0, Math.min(100, progress))}%` }} />
    </span>
  );
}

function ResultCard({ result }: { result: PageCheckResult }) {
  const { t } = useI18n();
  return (
    <article className={`check-card check-card--${result.status}`}>
      <header className="check-card__header">
        <div>
          <h3>{result.word}</h3>
          {result.source_language && result.source_title && (
            <p className="check-card__source">{t("Loharano", "Source")}: {result.source_language} · {result.source_title}</p>
          )}
        </div>
        <span className={`check-badge check-badge--${result.status}`}>
          {result.status === "good" ? t("Tsara", "Good") : result.status === "fixed" ? t("Voahitsy", "Fixed") : result.status === "unverifiable" ? t("Tsy azo hamarinina", "Unverifiable") : t("Hadisoana", "Error")}
        </span>
      </header>

      <p className="check-card__message">{result.message}</p>

      {result.issues.length > 0 && (
        <details className="check-card__issues">
          <summary>{t(`Olana ${result.issues.length}`, `${result.issues.length} issues`)}</summary>
          <ul>{result.issues.map((issue, index) => <li key={`${issue.type}-${index}`}><strong>{issue.type}</strong><span>{issue.description}</span></li>)}</ul>
        </details>
      )}

      {result.mg_entry && result.mg_entry.sections && result.mg_entry.sections.length > 0 && (
        <details className="check-card__entry">
          <summary>{t("Fizoro malagasy", "Malagasy section")}</summary>
          {result.mg_entry.sections.map((section, index) => (
            <div className="check-card__section" key={`${section.part_of_speech}-${index}`}>
              <strong>{section.part_of_speech}</strong>
              <ol>{section.definitions.map((definition, defIndex) => <li key={`${definition}-${defIndex}`}>{definition}</li>)}</ol>
            </div>
          ))}
        </details>
      )}

      {result.fixed_entry && (
        <details className="check-card__entry check-card__entry--fixed" open>
          <summary>{t("Fanitsiana nalefa havoaka", "Fixed entry queued")}</summary>
          <div className="check-card__section">
            <strong>{result.fixed_entry.part_of_speech}</strong>
            <ol>{result.fixed_entry.definitions.map((definition, index) => <li key={`${definition}-${index}`}>{definition}</li>)}</ol>
            {result.fixed_entry.examples.length > 0 && (
              <ul className="check-card__examples">{result.fixed_entry.examples.map((example, index) => <li key={`${example}-${index}`}>“{example}”</li>)}</ul>
            )}
          </div>
        </details>
      )}
    </article>
  );
}

function JobRow({ job, selected, onSelect }: { job: PageCheckJobSummary; selected: boolean; onSelect: (jobId: string) => void }) {
  const { t, locale } = useI18n();
  const counts = job.result_counts;
  const active = job.status === "pending" || job.status === "running";
  const summary = job.status === "done"
    ? t(`Pejy ${job.titles.length}: ${counts.good} tsara, ${counts.fixed} voahitsy, ${counts.unverifiable} tsy voamarina, ${counts.error} hadisoana`, `${job.titles.length} pages: ${counts.good} good, ${counts.fixed} fixed, ${counts.unverifiable} unverifiable, ${counts.error} errors`)
    : job.status === "error"
      ? job.error || t("Tsy nahomby.", "Failed.")
      : job.message || (job.status === "pending"
        ? t("Miandry mpanamarina ity pejy ity.", "This page is waiting for a checker.")
        : t(`Mandeha ny fanamarinana... ${job.progress}%`, `The check is running... ${job.progress}%`));
  const queueText = job.status === "pending" && job.queue_position
    ? t(`Laharana ${job.queue_position}`, `Queue #${job.queue_position}`)
    : stageLabel(job.stage, t);
  return (
    <button type="button" aria-label={job.titles.join(", ")} className={`check-job-row${selected ? " check-job-row--selected" : ""}`} onClick={() => onSelect(job.job_id)}>
      <span className="check-job-row__line">
        <JobBadge status={job.status} />
        <b>{job.titles.slice(0, 3).join(", ")}{job.titles.length > 3 ? ` +${job.titles.length - 3}` : ""}</b>
      </span>
      <ProgressBar progress={job.progress} done={job.status === "done"} />
      <small>{queueText} · {formatDateTime(locale, new Date(job.created_at * 1000))}{active && job.attempts > 1 ? ` · ${t(`Famerenana ${job.attempts}`, `Attempt ${job.attempts}`)}` : ""}</small>
      <p>{summary}</p>
    </button>
  );
}

function StatisticCard({ statistic }: { statistic: PageCheckPeriodStatistics }) {
  const { t, locale } = useI18n();
  const number = new Intl.NumberFormat(locale === "mg" ? "mg-MG" : "en", { maximumFractionDigits: 1 });
  const presentation = statistic.grade ? GRADE_WEATHER[statistic.grade] : null;
  const gradeClass = statistic.grade?.toLowerCase() ?? "none";
  const percentage = statistic.good_percentage === null ? t("Tsy misy angona", "No data") : `${number.format(statistic.good_percentage)}%`;
  return (
    <article className={`check-statistic check-statistic--grade-${gradeClass}`}>
      <header className="check-statistic__header">
        <div>
          <h4>{t(...STATISTICS_PERIOD_LABELS[statistic.period])}</h4>
          <small>
            <time dateTime={new Date(statistic.period_start * 1000).toISOString()}>{formatDate(locale, new Date(statistic.period_start * 1000), "UTC")}</time>
            {" - "}
            <time dateTime={new Date(statistic.period_end * 1000).toISOString()}>{formatDate(locale, new Date(statistic.period_end * 1000), "UTC")}</time>
          </small>
        </div>
        <div className="check-statistic__weather">
          <span aria-hidden="true">{presentation?.symbol ?? "-"}</span>
          <small>{presentation ? t(...presentation.weather) : t("Tsy misy angona", "No data")}</small>
        </div>
      </header>
      <div className="check-statistic__score">
        <strong aria-label={statistic.grade ? t(`Naoty ${statistic.grade}`, `Grade ${statistic.grade}`) : t("Tsy misy naoty", "No grade")}>{statistic.grade ?? "-"}</strong>
        <div>
          <b>{percentage}</b>
          <span>{presentation ? t(...presentation.quality) : t("Tsy mbola misy asa", "No jobs yet")}</span>
        </div>
      </div>
      <dl className="check-statistic__counts">
        <div><dt>{t("Asa", "Jobs")}</dt><dd>{number.format(statistic.job_count)}</dd></div>
        <div><dt>{t("Voamarina", "Checked")}</dt><dd>{number.format(statistic.checked_count)}</dd></div>
        <div><dt>{t("Tsara", "Good")}</dt><dd>{number.format(statistic.result_counts.good)}</dd></div>
        <div><dt>{t("Nila fanitsiana", "Needed fix")}</dt><dd>{number.format(statistic.result_counts.fixed)}</dd></div>
        <div><dt>{t("Tsy voamarina", "Unverifiable")}</dt><dd>{number.format(statistic.result_counts.unverifiable)}</dd></div>
        <div><dt>{t("Hadisoana", "Errors")}</dt><dd>{number.format(statistic.result_counts.error)}</dd></div>
      </dl>
    </article>
  );
}

function ScoreTrend({ history, statistic, period, loading, error, onPeriodChange }: {
  history: PageCheckScoreSnapshot[];
  statistic: PageCheckPeriodStatistics | null;
  period: PageCheckStatisticsPeriod;
  loading: boolean;
  error: string;
  onPeriodChange: (period: PageCheckStatisticsPeriod) => void;
}) {
  const { t, locale } = useI18n();
  const number = new Intl.NumberFormat(locale === "mg" ? "mg-MG" : "en", { maximumFractionDigits: 1 });
  const chartWidth = 800;
  const chartHeight = 220;
  const chartLeft = 42;
  const chartRight = 16;
  const chartTop = 14;
  const chartBottom = 24;
  const historicalTimeline = history.flatMap((snapshot) => {
    const timestamp = Date.parse(snapshot.snapshot_at);
    return Number.isFinite(timestamp)
      ? [{ timestamp, score: snapshot.good_percentage === null ? null : Math.max(0, Math.min(100, snapshot.good_percentage)) }]
      : [];
  }).sort((left, right) => left.timestamp - right.timestamp);
  const trendSegments: Array<Array<{ timestamp: number; score: number; live: boolean }>> = [];
  let activeSegment: Array<{ timestamp: number; score: number; live: boolean }> | null = null;
  for (const point of historicalTimeline) {
    if (point.score === null) {
      activeSegment = null;
      continue;
    }
    if (activeSegment === null) {
      activeSegment = [];
      trendSegments.push(activeSegment);
    }
    activeSegment.push({ ...point, score: point.score, live: false });
  }
  const historicalPoints = trendSegments.flat();
  const livePoint = statistic?.good_percentage === null || statistic?.good_percentage === undefined
    ? null
    : {
        timestamp: statistic.period_end * 1000,
        score: Math.max(0, Math.min(100, statistic.good_percentage)),
        live: true,
      };
  if (livePoint) {
    if (activeSegment === null) {
      activeSegment = [];
      trendSegments.push(activeSegment);
    }
    activeSegment.push(livePoint);
  }
  const historicalStart = historicalTimeline[0]?.timestamp;
  const historicalEnd = historicalTimeline.at(-1)?.timestamp;
  const fallbackDurations: Record<PageCheckStatisticsPeriod, number> = {
    today: 24 * 60 * 60_000,
    last_7_days: 7 * 24 * 60 * 60_000,
    current_week: 7 * 24 * 60 * 60_000,
    current_month: 31 * 24 * 60 * 60_000,
    last_3_months: 92 * 24 * 60 * 60_000,
    last_6_months: 183 * 24 * 60 * 60_000,
  };
  const rangeStart = statistic
    ? statistic.period_start * 1000
    : historicalStart === undefined
      ? 0
      : historicalStart === historicalEnd
        ? historicalStart - fallbackDurations[period]
        : historicalStart;
  const rangeEnd = Math.max(
    statistic ? statistic.period_end * 1000 : historicalEnd ?? rangeStart + 1,
    rangeStart + 1,
  );
  const hasTimeline = statistic !== null || historicalTimeline.length > 0;
  const coordinateSegments = trendSegments.map((segment) => segment.map((point) => {
    const position = Math.max(0, Math.min(1, (point.timestamp - rangeStart) / (rangeEnd - rangeStart)));
    return {
      ...point,
      x: chartLeft + position * (chartWidth - chartLeft - chartRight),
      y: chartTop + ((100 - point.score) / 100) * (chartHeight - chartTop - chartBottom),
    };
  }));
  const coordinates = coordinateSegments.flat();
  const linePaths = coordinateSegments.map((segment) => segment.map((point, index) => `${index === 0 ? "M" : "L"}${point.x.toFixed(2)},${point.y.toFixed(2)}`).join(" "));
  const areaPaths = coordinateSegments.map((segment, index) => segment.length > 1
    ? `${linePaths[index]} L${segment.at(-1)!.x.toFixed(2)},${(chartHeight - chartBottom).toFixed(2)} L${segment[0].x.toFixed(2)},${(chartHeight - chartBottom).toFixed(2)} Z`
    : "");
  const liveCoordinates = coordinates.find((point) => point.live);
  const currentScore = statistic?.good_percentage === null || statistic?.good_percentage === undefined
    ? t("Tsy misy angona", "No data")
    : `${number.format(statistic.good_percentage)}%`;
  const periodLabel = t(...STATISTICS_PERIOD_LABELS[period]);
  const minimumScore = historicalPoints.length > 0 ? Math.min(...historicalPoints.map((point) => point.score)) : null;
  const maximumScore = historicalPoints.length > 0 ? Math.max(...historicalPoints.map((point) => point.score)) : null;
  const latestHistoricalPoint = historicalPoints.at(-1);
  const historySummary = minimumScore === null || maximumScore === null || !latestHistoricalPoint
    ? history.length > 0
      ? t("Tsy misy asa ao amin'ireo sary voatahiry.", "Saved snapshots contain no jobs.")
      : t("Tsy mbola misy sary voatahiry.", "No saved snapshots yet.")
    : t(
        `Ny isa voatahiry dia ${number.format(minimumScore)}% hatramin'ny ${number.format(maximumScore)}%; ${number.format(latestHistoricalPoint.score)}% ny farany tamin'ny ${formatDateTime(locale, new Date(latestHistoricalPoint.timestamp), "UTC")} UTC.`,
        `Saved scores range from ${number.format(minimumScore)}% to ${number.format(maximumScore)}%; the latest was ${number.format(latestHistoricalPoint.score)}% at ${formatDateTime(locale, new Date(latestHistoricalPoint.timestamp), "UTC")} UTC.`,
      );
  const chartLabel = t(
    `Fivoaran'ny isa ho an'ny ${periodLabel}, misy sary antsasak'adiny ${number.format(history.length)}. ${historySummary}`,
    `${periodLabel} score evolution with ${number.format(history.length)} half-hour snapshots. ${historySummary}`,
  );

  return (
    <section className="check-score-trend" aria-labelledby="page-check-score-trend-heading">
      <div className="check-score-trend__header">
        <div>
          <p className="eyebrow">{t("Fivoaran'ny isa", "Score evolution")}</p>
          <h4 id="page-check-score-trend-heading">{periodLabel}</h4>
          <small>{t(`Sary antsasak'adiny ${number.format(history.length)}`, `${number.format(history.length)} half-hour snapshots`)}</small>
        </div>
        <div className="check-score-trend__live">
          <span>{t("Isa mivantana", "Live score")}</span>
          <strong>{currentScore}</strong>
        </div>
      </div>
      <div className="statistics-tabs check-score-trend__periods" role="group" aria-label={t("Vanim-potoanan'ny fivoaran'ny isa", "Score evolution period")}>
        {STATISTICS_PERIODS.map((item) => (
          <button aria-pressed={period === item} className={period === item ? "statistics-tabs__active" : ""} type="button" key={item} onClick={() => onPeriodChange(item)}>
            {t(...STATISTICS_PERIOD_LABELS[item])}
          </button>
        ))}
      </div>
      <div className="check-score-trend__plot">
        <svg viewBox={`0 0 ${chartWidth} ${chartHeight}`} role="img" aria-label={chartLabel} preserveAspectRatio="none">
          <title>{chartLabel}</title>
          <desc>{historySummary}</desc>
          {[0, 25, 50, 75, 100].map((score) => {
            const y = chartTop + ((100 - score) / 100) * (chartHeight - chartTop - chartBottom);
            return (
              <g key={score}>
                <line className="check-score-trend__grid-line" x1={chartLeft} x2={chartWidth - chartRight} y1={y} y2={y} />
                <text x={chartLeft - 8} y={y + 3} textAnchor="end">{score}</text>
              </g>
            );
          })}
          {areaPaths.map((path, index) => path && <path className="check-score-trend__area" d={path} key={`area-${index}`} />)}
          {linePaths.map((path, index) => path && <path className="check-score-trend__line" d={path} key={`line-${index}`} />)}
          {coordinates.filter((point) => !point.live).map((point) => (
            <circle className="check-score-trend__snapshot-point" cx={point.x} cy={point.y} r="2" key={point.timestamp}>
              <title>{number.format(point.score)}% - {formatDateTime(locale, new Date(point.timestamp), "UTC")} UTC</title>
            </circle>
          ))}
          {liveCoordinates && <circle className="check-score-trend__live-point" cx={liveCoordinates.x} cy={liveCoordinates.y} r="5" />}
        </svg>
        <div className="check-score-trend__axis">
          {hasTimeline ? <time dateTime={new Date(rangeStart).toISOString()}>{formatDateTime(locale, new Date(rangeStart), "UTC")}</time> : <span />}
          <span>{t("Isa (%)", "Score (%)")}</span>
          {hasTimeline && <time dateTime={new Date(rangeEnd).toISOString()}>{formatDateTime(locale, new Date(rangeEnd), "UTC")}</time>}
        </div>
        {loading && history.length === 0 && <p className="check-score-trend__empty" role="status"><span className="spinner" />{t("Maka ny fivoaran'ny isa...", "Loading score history...")}</p>}
        {!loading && !error && historicalPoints.length === 0 && <p className="check-score-trend__empty">{history.length > 0
          ? t("Tsy misy asa ao amin'ireo sary antsasak'adiny; ny isa mivantana no aseho.", "Half-hour snapshots contain no jobs; the live score is shown.")
          : t("Tsy mbola misy sary antsasak'adiny; ny isa mivantana no aseho.", "No half-hour snapshots yet; the live score is shown.")}</p>}
      </div>
      {error && <p className="check-score-trend__error" role="status">{error} {statistic
        ? t("Mbola aseho etsy ambany ny isa mivantana.", "Live values remain available below.")
        : t("Tsy azo alaina koa ny isa mivantana amin'izao.", "Live values are currently unavailable too.")}</p>}
    </section>
  );
}

function StatisticsPanel({ language, statistics, loading, error }: { language: string; statistics: PageCheckStatisticsResponse | null; loading: boolean; error: string }) {
  const { t, locale } = useI18n();
  const [selectedPeriod, setSelectedPeriod] = useState<PageCheckStatisticsPeriod>("last_7_days");
  const [historyState, setHistoryState] = useState<{
    language: string;
    period: PageCheckStatisticsPeriod;
    history: PageCheckScoreSnapshot[];
    loading: boolean;
    failed: boolean;
    error: string;
  } | null>(null);
  const number = new Intl.NumberFormat(locale === "mg" ? "mg-MG" : "en");
  const byPeriod = new Map(statistics?.statistics.map((item) => [item.period, item]));
  const ordered = STATISTICS_PERIODS.flatMap((period) => {
    const statistic = byPeriod.get(period);
    return statistic ? [statistic] : [];
  });
  const selectedStatistic = byPeriod.get(selectedPeriod) ?? null;
  const currentHistory = historyState?.language === language && historyState.period === selectedPeriod
    ? historyState
    : null;
  const showTrend = ordered.length > 0 || historyState !== null;

  useEffect(() => {
    const controller = new AbortController();
    let refreshTimer: ReturnType<typeof setTimeout> | undefined;

    async function loadHistory() {
      setHistoryState((previous) => previous?.language === language && previous.period === selectedPeriod
        ? { ...previous, loading: true, failed: false, error: "" }
        : { language, period: selectedPeriod, history: [], loading: true, failed: false, error: "" });
      try {
        const history = await getPageCheckScoreHistory(language, selectedPeriod, controller.signal);
        if (!controller.signal.aborted) {
          setHistoryState({ language, period: selectedPeriod, history, loading: false, failed: false, error: "" });
        }
      } catch (caught) {
        if (!controller.signal.aborted) {
          setHistoryState((previous) => ({
            language,
            period: selectedPeriod,
            history: previous?.language === language && previous.period === selectedPeriod ? previous.history : [],
            loading: false,
            failed: true,
            error: caught instanceof Error ? caught.message : "",
          }));
        }
      } finally {
        if (!controller.signal.aborted) {
          refreshTimer = setTimeout(() => void loadHistory(), SCORE_HISTORY_REFRESH_MS);
        }
      }
    }

    void loadHistory();
    return () => {
      controller.abort();
      if (refreshTimer !== undefined) {
        clearTimeout(refreshTimer);
      }
    };
  }, [language, selectedPeriod]);

  return (
    <section className="panel check-statistics" aria-labelledby="page-check-statistics-heading">
      <ClassicTitleBar title={t("Antontanisan'ny fanamarinana", "Page-check statistics")} />
      <div className="panel__header check-statistics__header">
        <div>
          <p className="eyebrow">{t("Vokatry ny fanamarinana", "Check outcomes")}</p>
          <h3 id="page-check-statistics-heading">{t("Antontanisan'ny fanamarinana", "Page-check statistics")}</h3>
          <p>{t("Ny tahan'ny pejy tsara dia isan'ny tsara zaraina amin'ny fitambaran'ny asa fanamarinana.", "The good-content rate is good divided by total check jobs.")}</p>
        </div>
        {statistics && (
          <div className="check-statistics__metadata">
            <strong>{number.format(statistics.retained_job_count)} / {number.format(statistics.retention_limit)}</strong>
            <span>{t("asa voatazona", "retained jobs")}</span>
            <small>{t("Nokajiana", "Calculated")} <time dateTime={new Date(statistics.generated_at * 1000).toISOString()}>{formatDateTime(locale, new Date(statistics.generated_at * 1000), "UTC")}</time> UTC</small>
          </div>
        )}
      </div>
      {error && <p className="check-statistics__error" role="alert">{error} {t("Hamerina ho azy.", "Retrying automatically.")}</p>}
      {loading && !statistics && <p className="empty-inline" role="status"><span className="spinner" />{t("Maka ny antontanisa...", "Loading statistics...")}</p>}
      {!loading && ordered.length === 0 && !showTrend && <p className="empty-inline">{t("Tsy mbola misy antontanisa.", "No page-check statistics yet.")}</p>}
      {showTrend && <ScoreTrend
        history={currentHistory?.history ?? []}
        statistic={selectedStatistic}
        period={selectedPeriod}
        loading={!currentHistory || currentHistory.loading}
        error={currentHistory?.failed ? currentHistory.error || t("Tsy azo nalaina ny fivoaran'ny isa.", "Score history could not be loaded.") : ""}
        onPeriodChange={setSelectedPeriod}
      />}
      {ordered.length > 0 && <div className="check-statistics__grid">{ordered.map((statistic) => <StatisticCard statistic={statistic} key={statistic.period} />)}</div>}
      <p className="check-statistics__sample-note">{statistics
        ? t(
            `Santionany avy amin'ireo asa fanamarinana ${number.format(statistics.retention_limit)} farany voatazona ireo isa mivantana sy sary antsasak'adiny ireo.`,
            `Live values and half-hour snapshots are samples based on the latest ${number.format(statistics.retention_limit)} retained check jobs.`,
          )
        : t("Santionany avy amin'ireo asa fanamarinana farany voatazona ireo isa ireo.", "These figures are samples based on the latest retained check jobs.")}</p>
    </section>
  );
}

export function PageCheckWorkspace({ initialJobId = "", initialLanguage = "mg", onMessage, onTargetChange }: PageCheckWorkspaceProps) {
  const { t, locale } = useI18n();
  const startingLanguage = initialLanguage.trim() || "mg";
  const [language, setLanguage] = useState(startingLanguage);
  const [effectiveLanguage, setEffectiveLanguage] = useState(startingLanguage);
  const [titles, setTitles] = useState("");
  const [loading, setLoading] = useState(false);
  const [jobs, setJobs] = useState<PageCheckJobSummary[]>([]);
  const [selectedJobId, setSelectedJobId] = useState<string | null>(initialJobId || null);
  const [selectedJob, setSelectedJob] = useState<PageCheckJob | null>(null);
  const [statusFilter, setStatusFilter] = useState<JobStatusFilter>("all");
  const [historyTextFilter, setHistoryTextFilter] = useState("");
  const [historyLoading, setHistoryLoading] = useState(true);
  const [historyError, setHistoryError] = useState("");
  const [detailError, setDetailError] = useState("");
  const [statistics, setStatistics] = useState<PageCheckStatisticsResponse | null>(null);
  const [statisticsError, setStatisticsError] = useState<{ language: string; message: string } | null>(null);
  const [historyRefresh, setHistoryRefresh] = useState(0);
  const mountedRef = useRef(true);
  const reportLanguageTargetChange = useEffectEvent((nextLanguage: string) => {
    onTargetChange?.(nextLanguage, "");
  });

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  useEffect(() => {
    const nextLanguage = language.trim() || "mg";
    if (nextLanguage === effectiveLanguage) return;
    const timer = setTimeout(() => {
      setEffectiveLanguage(nextLanguage);
      reportLanguageTargetChange(nextLanguage);
    }, 500);
    return () => clearTimeout(timer);
  }, [effectiveLanguage, language]);

  const reportLoadError = useEffectEvent((caught: unknown) => {
    onMessage(caught instanceof Error ? caught.message : t("Tsy azo nalaina ny tantaran'ny asa.", "The job history could not be loaded."), "error");
  });

  const reportDetailError = useEffectEvent((caught: unknown) => {
    onMessage(caught instanceof Error ? caught.message : t("Tsy azo nalaina ny antsipirian'ny asa.", "The job details could not be loaded."), "error");
  });

  useEffect(() => {
    const controller = new AbortController();
    let pollTimer: ReturnType<typeof setTimeout> | undefined;
    let reportedError = false;

    async function loadHistory() {
      try {
        const summaries = await listPageCheckJobs(effectiveLanguage, controller.signal);
        if (controller.signal.aborted) {
          return;
        }
        setJobs(summaries);
        setHistoryLoading(false);
        setHistoryError("");
        reportedError = false;
        if (summaries.some((job) => job.status === "pending" || job.status === "running" || reviewHandoffNeedsPolling(job))) {
          pollTimer = setTimeout(() => void loadHistory(), 3000);
        }
      } catch (caught) {
        if (!controller.signal.aborted) {
          const message = caught instanceof Error ? caught.message : t("Tsy azo nalaina ny tantaran'ny asa.", "The job history could not be loaded.");
          setHistoryLoading(false);
          setHistoryError(message);
          if (!reportedError) {
            reportLoadError(caught);
            reportedError = true;
          }
          pollTimer = setTimeout(() => void loadHistory(), 5000);
        }
      }
    }

    void loadHistory();
    return () => {
      controller.abort();
      if (pollTimer !== undefined) {
        clearTimeout(pollTimer);
      }
    };
  }, [effectiveLanguage, historyRefresh, t]);

  useEffect(() => {
    const controller = new AbortController();
    let refreshTimer: ReturnType<typeof setTimeout> | undefined;

    async function loadStatistics() {
      try {
        const value = await getPageCheckStatistics(effectiveLanguage, controller.signal);
        if (!controller.signal.aborted) {
          setStatistics(value);
          setStatisticsError(null);
        }
      } catch (caught) {
        if (!controller.signal.aborted) {
          setStatisticsError({
            language: effectiveLanguage,
            message: caught instanceof Error ? caught.message : t("Tsy azo nalaina ny antontanisa.", "Statistics could not be loaded."),
          });
        }
      } finally {
        if (!controller.signal.aborted) {
          refreshTimer = setTimeout(() => void loadStatistics(), STATISTICS_REFRESH_MS);
        }
      }
    }

    void loadStatistics();
    return () => {
      controller.abort();
      if (refreshTimer !== undefined) {
        clearTimeout(refreshTimer);
      }
    };
  }, [effectiveLanguage, t]);

  const selectedSummary = jobs.find((job) => job.job_id === selectedJobId);
  const selectedLanguage = selectedSummary?.language ?? effectiveLanguage;

  useEffect(() => {
    if (!selectedJobId) {
      return;
    }
    let cancelled = false;
    let pollTimer: ReturnType<typeof setTimeout> | undefined;
    let reportedError = false;

    async function loadDetails() {
      try {
        const job = await getPageCheckJob(selectedLanguage, selectedJobId!);
        if (cancelled) {
          return;
        }
        setSelectedJob(job);
        setDetailError("");
        reportedError = false;
        if (job.status === "pending" || job.status === "running" || reviewHandoffNeedsPolling(job)) {
          pollTimer = setTimeout(() => void loadDetails(), 3000);
        }
      } catch (caught) {
        if (!cancelled) {
          const message = caught instanceof Error ? caught.message : t("Tsy azo nalaina ny antsipirian'ny asa.", "The job details could not be loaded.");
          setDetailError(message);
          if (!reportedError) {
            reportDetailError(caught);
            reportedError = true;
          }
          pollTimer = setTimeout(() => void loadDetails(), 5000);
        }
      }
    }

    void loadDetails();
    return () => {
      cancelled = true;
      if (pollTimer !== undefined) {
        clearTimeout(pollTimer);
      }
    };
  }, [selectedJobId, selectedLanguage, t]);

  function changeLanguage(value: string) {
    setLanguage(value);
    setSelectedJobId(null);
    setSelectedJob(null);
    setDetailError("");
  }

  function openJob(jobId: string) {
    setDetailError("");
    if (jobId !== selectedJobId) {
      setSelectedJob(null);
    }
    setSelectedJobId(jobId);
    onTargetChange?.(jobs.find((job) => job.job_id === jobId)?.language ?? effectiveLanguage, jobId);
  }

  async function runCheck(event: FormEvent) {
    event.preventDefault();
    const list = titles.split("\n").map((title) => title.trim()).filter(Boolean);
    if (list.length === 0) {
      onMessage(t("Ampidiro farafahakeliny lohateny iray.", "Enter at least one page title."), "error");
      return;
    }
    if (!window.confirm(t(...pageCheckMessages.confirmCheck))) return;
    setLoading(true);
    try {
      const nextLanguage = language.trim() || "mg";
      setEffectiveLanguage(nextLanguage);
      rememberPageCheckLanguage(nextLanguage);
      const jobs = await startPageCheck(nextLanguage, list);
      if (jobs.every((job) => job.status === "error")) {
        onMessage(jobs[0]?.error || t("Tsy nahomby ny fanamarinana.", "The page check failed."), "error");
      } else {
        setJobs((previous) => {
          const merged = new Map(previous.map((job) => [job.job_id, job]));
          for (const job of jobs) {
            merged.set(job.job_id, {
              job_id: job.job_id,
              language: job.language,
              titles: job.titles,
              status: job.status,
              created_at: job.created_at,
              last_updated_at: job.last_updated_at,
              attempts: job.attempts,
              progress: job.progress,
              error: job.error,
              stage: job.stage,
              message: job.message,
              queue_position: null,
              result_counts: { good: 0, fixed: 0, unverifiable: 0, error: 0 },
            });
          }
          return [...merged.values()].sort((a, b) => b.created_at - a.created_at);
        });
        setSelectedJob(null);
        setDetailError("");
        setSelectedJobId(jobs[0]?.job_id ?? null);
        onTargetChange?.(nextLanguage, jobs[0]?.job_id ?? "");
        setHistoryRefresh((current) => current + 1);
        onMessage(t(
          `Nampidirina anaty filaharana ny pejy ${jobs.length}.`,
          `${jobs.length} page check jobs were added to the queue.`,
        ));
      }
    } catch (caught) {
      onMessage(caught instanceof Error ? caught.message : t("Tsy nahomby ny fanamarinana.", "The page check failed."), "error");
    } finally {
      if (mountedRef.current) {
        setLoading(false);
      }
    }
  }

  const normalizedHistoryFilter = historyTextFilter.trim().toLocaleLowerCase();
  const filteredJobs = jobs.filter((job) => (
    (statusFilter === "all" || job.status === statusFilter)
    && (!normalizedHistoryFilter
      || job.job_id.toLocaleLowerCase().includes(normalizedHistoryFilter)
      || job.titles.some((title) => title.toLocaleLowerCase().includes(normalizedHistoryFilter)))
  ));
  const runningJobs = filteredJobs.filter((job) => job.status === "running");
  const pendingJobs = filteredJobs
    .filter((job) => job.status === "pending")
    .sort((left, right) => (left.queue_position ?? Number.MAX_SAFE_INTEGER) - (right.queue_position ?? Number.MAX_SAFE_INTEGER));
  const finishedJobs = filteredJobs.filter((job) => job.status === "done" || job.status === "error");
  const selectedStage = stageLabel(selectedJob?.stage ?? selectedSummary?.stage, t);
  const selectedMessage = selectedJob?.message ?? selectedSummary?.message;
  const selectedQueuePosition = selectedSummary?.queue_position;
  const showReviewHandoff = selectedJob !== null && (
    (selectedJob.review_queue_state !== undefined && selectedJob.review_queue_state !== "not_needed")
    || Boolean(selectedJob.review_event_id)
    || Boolean(selectedJob.review_queue_error)
  );
  const currentStatistics = statistics?.language === effectiveLanguage ? statistics : null;
  const currentStatisticsError = statisticsError?.language === effectiveLanguage ? statisticsError.message : "";

  return (
    <section className="check-workspace">
      <div className="check-command panel">
        <ClassicTitleBar title={t("Mpanamarina pejy", "Page checker")} />
        <div className="check-command__intro">
          <p className="eyebrow">page_checker</p>
          <h2>{t("Mpanamarina pejy", "Page checker")}</h2>
          <p>{t("Hamarinina amin'ny alalan'ny DeepSeek ny famaritana malagasy amin'ny loharano (wikibolana sy tenymalagasy.org). Ny fizarana diso dia ahitsy ary alefa amin'ny filaharana havoaka.", "Verify Malagasy definitions against the source wiktionary and tenymalagasy.org using DeepSeek. Wrong sections are fixed and queued for publication.")}</p>
        </div>
        <form onSubmit={(event) => void runCheck(event)}>
          <label className="field field--compact"><span>{t("Fiteny", "Language")}</span><input required maxLength={10} value={language} onChange={(event) => changeLanguage(event.target.value)} /></label>
          <label className="field field--grow"><span>{t("Lohateny (iray isaky ny andalana)", "Page titles (one per line)")}</span><textarea required rows={4} value={titles} onChange={(event) => setTitles(event.target.value)} placeholder={t("oh: alika\nsoa", "e.g. alika\nsoa")} /></label>
          <button className="button button--primary" type="submit" disabled={loading}>{loading ? t("Mamarina...", "Checking...") : t("Hamarina pejy", "Check pages")}</button>
        </form>
      </div>

      <StatisticsPanel language={effectiveLanguage} statistics={currentStatistics} loading={!currentStatistics && !currentStatisticsError} error={currentStatisticsError} />

      <div className="check-overview">
        <aside className="panel check-job-list">
          <ClassicTitleBar title={t("Asa fanamarinana", "Check jobs")} />
          <p className="eyebrow">{t("Tantaran'ny asa", "Job history")}</p>
          <h3>{t("Asa fanamarinana", "Check jobs")}</h3>
          <div className="check-job-list__summary">
            <span><strong>{jobs.filter((job) => job.status === "running").length}</strong>{t("mandeha", "running")}</span>
            <span><strong>{jobs.filter((job) => job.status === "pending").length}</strong>{t("miandry", "waiting")}</span>
          </div>
          <div className="check-job-list__filters">
            <label className="field">
              <span>{t(...pageCheckMessages.status)}</span>
              <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value as JobStatusFilter)}>
                <option value="all">{t(...pageCheckMessages.all)}</option>
                {Object.entries(JOB_STATUS_LABELS).map(([status, labels]) => <option value={status} key={status}>{t(...labels)}</option>)}
              </select>
            </label>
            <label className="field">
              <span>{t(...pageCheckMessages.filterByTitleOrId)}</span>
              <input type="search" value={historyTextFilter} onChange={(event) => setHistoryTextFilter(event.target.value)} placeholder={t(...pageCheckMessages.titleOrJobId)} />
            </label>
          </div>
          {historyError && <p className="check-job-list__error" role="alert">{historyError} {t(...pageCheckMessages.retryingAutomatically)}</p>}
          {historyLoading && jobs.length === 0 ? (
            <div className="empty-inline"><span className="spinner" />{t("Maka ny filaharana...", "Loading the queue...")}</div>
          ) : jobs.length === 0 ? (
            <div className="empty-inline">{t("Mbola tsy misy asa fanamarinana.", "No page check jobs yet.")}</div>
          ) : filteredJobs.length === 0 ? (
            <div className="empty-inline">{t(...pageCheckMessages.noFilterMatches)}</div>
          ) : (
            <div className="check-job-list__rows">
              {runningJobs.length > 0 && <h4>{t("Eo am-panamarinana", "Checking now")}</h4>}
              {runningJobs.map((job) => <JobRow job={job} key={job.job_id} selected={job.job_id === selectedJobId} onSelect={openJob} />)}
              {pendingJobs.length > 0 && <h4>{t("Pejy miandry", "Waiting pages")}</h4>}
              {pendingJobs.map((job) => <JobRow job={job} key={job.job_id} selected={job.job_id === selectedJobId} onSelect={openJob} />)}
              {finishedJobs.length > 0 && <h4>{t("Vokatra farany", "Recent results")}</h4>}
              {finishedJobs.map((job) => <JobRow job={job} key={job.job_id} selected={job.job_id === selectedJobId} onSelect={openJob} />)}
            </div>
          )}
        </aside>

        <section className="panel check-job-detail">
          <ClassicTitleBar title={t("Antsipirian'ny asa", "Job details")} />
          {!selectedJob ? (
            detailError ? (
              <div className="empty-inline" role="alert">{detailError} {t("Hamerina ho azy.", "Retrying automatically.")}</div>
            ) : selectedJobId ? (
              <div className="empty-inline"><span className="spinner" />{t("Maka ny antsipirian'ny asa...", "Loading job details...")}</div>
            ) : (
              <div className="empty-inline">{t("Misafidiana asa raha hijerena ny antsipiriany.", "Select a job to see its details.")}</div>
            )
          ) : (
            <>
              <div className="check-job-detail__header">
                <div>
                  <p className="eyebrow">{t("Antsipirian'ny asa", "Job details")}</p>
                  <h3>{t("Pejy voamarina", "Checked pages")}</h3>
                  <p className="check-card__source">{selectedJob.language} · {selectedJob.job_id.slice(0, 8)} · {formatDateTime(locale, new Date(selectedJob.created_at * 1000))}</p>
                </div>
                <JobBadge status={selectedJob.status} />
              </div>

              {selectedJob.titles.length > 0 && (
                <ul className="check-job-detail__titles">{selectedJob.titles.map((title) => <li key={title}>{title}</li>)}</ul>
              )}

              <dl className="check-job-detail__facts">
                <div><dt>{t("Dingana", "Stage")}</dt><dd>{selectedStage}</dd></div>
                <div><dt>{t("Fandrosoana", "Progress")}</dt><dd>{selectedJob.progress}%</dd></div>
                <div><dt>{t("Nohavaozina", "Updated")}</dt><dd>{formatDateTime(locale, new Date(selectedJob.last_updated_at * 1000))}</dd></div>
                <div><dt>{t("Fanandramana", "Attempt")}</dt><dd>{Math.max(1, selectedJob.attempts)}</dd></div>
                {selectedQueuePosition && <div><dt>{t("Filaharana", "Queue")}</dt><dd>#{selectedQueuePosition}</dd></div>}
                {showReviewHandoff && <div><dt>{t(...pageCheckMessages.reviewHandoff)}</dt><dd>{reviewQueueStateLabel(selectedJob.review_queue_state, t)}</dd></div>}
                {showReviewHandoff && selectedJob.review_event_id && <div><dt>{t(...pageCheckMessages.reviewEventId)}</dt><dd>{selectedJob.review_event_id}</dd></div>}
                {showReviewHandoff && selectedJob.review_queue_error && <div><dt>{t(...pageCheckMessages.reviewHandoffError)}</dt><dd>{selectedJob.review_queue_error}</dd></div>}
              </dl>

              {selectedMessage && <p className="check-job-detail__message">{selectedMessage}</p>}

              {selectedJob.timeline && selectedJob.timeline.length > 0 && (
                <section className="check-job-timeline">
                  <h4>{t("Dian'ny fanamarinana", "Check activity")}</h4>
                  <ol>
                    {selectedJob.timeline.map((event, index) => (
                      <li key={`${event.timestamp}-${event.stage}-${index}`}>
                        <time dateTime={new Date(event.timestamp * 1000).toISOString()}>{formatDateTime(locale, new Date(event.timestamp * 1000))}</time>
                        <strong>{stageLabel(event.stage, t)}</strong>
                        <p>{event.message}</p>
                      </li>
                    ))}
                  </ol>
                </section>
              )}

              {selectedJob.status === "done" ? (
                selectedJob.results && selectedJob.results.length > 0 ? (
                  <div className="check-results">{selectedJob.results.map((result) => <ResultCard result={result} key={result.word} />)}</div>
                ) : (
                  <div className="empty-inline">{t("Tsy nisy valiny ity asa ity.", "This job returned no results.")}</div>
                )
              ) : selectedJob.status === "error" ? (
                <p className="check-card__message">{selectedJob.error}</p>
              ) : (
                <div className="check-job-detail__running">
                  <span className="spinner" />
                  <p>{selectedMessage || t("Miandry ny fanamarinana...", "Waiting for the page checks...")}</p>
                  <ProgressBar progress={selectedJob.progress} done={false} />
                  {selectedJob.attempts > 1 && <small>{t(`Famerenana ${selectedJob.attempts}`, `Attempt ${selectedJob.attempts}`)}</small>}
                </div>
              )}
            </>
          )}
        </section>
      </div>
    </section>
  );
}
