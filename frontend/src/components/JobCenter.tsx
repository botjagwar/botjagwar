import { useEffect, useRef, useState } from "react";

import { listPageCheckJobs } from "../api";
import { formatDateTime, useI18n } from "../i18n";
import { loadPageCheckLanguages, PAGE_CHECK_LANGUAGES_EVENT } from "../jobCenterTracking";
import { jobCenterMessages } from "../messages/jobCenter";
import type { BilingualMessage } from "../messages/types";
import { isActiveTranslationJob, useTranslationJobs } from "../translationJobs";
import type { PageCheckJobSummary, TranslationJob } from "../types";
import { ClassicTitleBar } from "./ClassicTitleBar";

export interface JobCenterNavigationTarget {
  jobId?: string;
  language?: string;
  route: "translator" | "checker";
}

interface JobCenterProps {
  onNavigate: (target: JobCenterNavigationTarget) => void;
}

interface JobCenterRow {
  active: boolean;
  error?: string | null;
  id: string;
  kind: "translator" | "checker";
  language: string;
  statusLabel?: BilingualMessage;
  status: string;
  title: string;
  updatedAt: number;
}

const TRANSLATION_STATUS_LABELS: Record<TranslationJob["status"], readonly [string, string]> = {
  pending: ["Miandry", "Pending"],
  running: ["Mandeha", "Running"],
  done: ["Vita", "Done"],
  error: ["Hadisoana", "Error"],
};

const PAGE_CHECK_STATUS_LABELS: Record<PageCheckJobSummary["status"], readonly [string, string]> = {
  pending: ["Miandry", "Pending"],
  running: ["Mandeha", "Running"],
  done: ["Vita", "Done"],
  error: ["Hadisoana", "Error"],
};

const REVIEW_STATUS_LABELS = {
  pending: jobCenterMessages.reviewPending,
  publishing: jobCenterMessages.reviewPublishing,
  failed: jobCenterMessages.reviewFailed,
} as const;

function pageCheckIsActive(job: PageCheckJobSummary): boolean {
  return job.status === "pending" || job.status === "running"
    || job.review_queue_state === "pending" || job.review_queue_state === "publishing" || job.review_queue_state === "failed";
}

export function JobCenter({ onNavigate }: JobCenterProps) {
  const { locale, t } = useI18n();
  const { jobs: translationJobs, pollTargets, pollingErrors } = useTranslationJobs();
  const [open, setOpen] = useState(false);
  const [languages, setLanguages] = useState(loadPageCheckLanguages);
  const [pageCheckJobs, setPageCheckJobs] = useState<PageCheckJobSummary[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [refreshVersion, setRefreshVersion] = useState(0);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);
  const panelRef = useRef<HTMLElement>(null);

  useEffect(() => {
    function updateLanguages() {
      setLanguages(loadPageCheckLanguages());
    }
    window.addEventListener(PAGE_CHECK_LANGUAGES_EVENT, updateLanguages);
    return () => window.removeEventListener(PAGE_CHECK_LANGUAGES_EVENT, updateLanguages);
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    let pollTimer: ReturnType<typeof setTimeout> | undefined;

    async function loadJobs() {
      setLoading(true);
      const results = await Promise.allSettled(languages.map((language) => listPageCheckJobs(language, controller.signal)));
      if (controller.signal.aborted) return;
      const loadedJobs = results.flatMap((result) => result.status === "fulfilled" ? result.value : []);
      const uniqueJobs = new Map(loadedJobs.map((job) => [`${job.language}\u0000${job.job_id}`, job]));
      setPageCheckJobs([...uniqueJobs.values()].sort((left, right) => right.last_updated_at - left.last_updated_at));
      const rejected = results.find((result) => result.status === "rejected");
      setError(rejected?.status === "rejected" ? (rejected.reason instanceof Error ? rejected.reason.message : t("Tsy azo nalaina ny asa fanamarinana.", "Page-check jobs could not be loaded.")) : "");
      setLoading(false);
      const nextDelay = rejected ? 5_000 : [...uniqueJobs.values()].some(pageCheckIsActive) ? 3_000 : 30_000;
      pollTimer = setTimeout(() => void loadJobs(), nextDelay);
    }

    void loadJobs();
    return () => {
      controller.abort();
      if (pollTimer !== undefined) clearTimeout(pollTimer);
    };
  }, [languages, refreshVersion, t]);

  useEffect(() => {
    if (!open) return;
    closeRef.current?.focus();
    function closeOnEscape(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setOpen(false);
        triggerRef.current?.focus();
        return;
      }
      if (event.key === "Tab" && panelRef.current) {
        const focusable = [...panelRef.current.querySelectorAll<HTMLElement>('button:not(:disabled), [href], input:not(:disabled), select:not(:disabled), textarea:not(:disabled), [tabindex]:not([tabindex="-1"])')];
        const first = focusable[0];
        const last = focusable.at(-1);
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault();
          last?.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          first?.focus();
        }
      }
    }
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [open]);

  const unresolvedRows: JobCenterRow[] = pollTargets
    .filter((target) => !translationJobs.some((job) => job.job_id === target.jobId))
    .map((target) => ({
      active: true,
      error: pollingErrors[target.jobId],
      id: target.jobId,
      kind: "translator",
      language: target.requestedLanguage ?? target.language,
      status: "unresolved",
      title: target.title ?? target.jobId,
      updatedAt: target.provisionalSince ? target.provisionalSince / 1_000 : 0,
    }));
  const translationRows: JobCenterRow[] = translationJobs.map((job) => ({
    active: isActiveTranslationJob(job),
    error: job.error ?? pollingErrors[job.job_id],
    id: job.job_id,
    kind: "translator",
    language: job.language,
    status: job.status,
    title: job.title,
    updatedAt: job.last_updated_at,
  }));
  const pageCheckRows: JobCenterRow[] = pageCheckJobs.map((job) => ({
    active: pageCheckIsActive(job),
    error: job.error ?? job.review_queue_error,
    id: job.job_id,
    kind: "checker",
    language: job.language,
    statusLabel: job.review_queue_state && job.review_queue_state in REVIEW_STATUS_LABELS
      ? REVIEW_STATUS_LABELS[job.review_queue_state as keyof typeof REVIEW_STATUS_LABELS]
      : undefined,
    status: job.status,
    title: job.titles.join(", "),
    updatedAt: job.last_updated_at,
  }));
  const rows = [...unresolvedRows, ...translationRows, ...pageCheckRows]
    .sort((left, right) => right.updatedAt - left.updatedAt)
    .slice(0, 30);
  const activeCount = pollTargets.length + pageCheckJobs.filter(pageCheckIsActive).length;

  function close() {
    setOpen(false);
    triggerRef.current?.focus();
  }

  return <>
    <button
      aria-label={t(`Foiben'ny asa: ${activeCount} mandeha`, `Job center: ${activeCount} active`)}
      aria-controls="atlas-job-center"
      aria-expanded={open}
      className="job-center-trigger"
      onClick={() => setOpen((current) => !current)}
      ref={triggerRef}
      type="button"
    >
      <span>{t(...jobCenterMessages.jobs)}</span>
      <strong aria-hidden="true">{activeCount}</strong>
    </button>
    {open && <>
      <button className="job-center-scrim" aria-label={t(...jobCenterMessages.close)} onClick={close} type="button" />
      <aside aria-modal="true" className="job-center" id="atlas-job-center" aria-labelledby="atlas-job-center-heading" ref={panelRef} role="dialog">
        <ClassicTitleBar title={t(...jobCenterMessages.heading)} />
        <header>
          <div><p className="eyebrow">{t(...jobCenterMessages.eyebrow)}</p><h2 id="atlas-job-center-heading">{t(...jobCenterMessages.heading)}</h2></div>
          <button className="icon-button" aria-label={t(...jobCenterMessages.close)} onClick={close} ref={closeRef} type="button">×</button>
        </header>
        <p className="job-center__help">{t(...jobCenterMessages.recentHelp)}</p>
        <div className="job-center__toolbar">
          <span>{t(`${activeCount} mandeha`, `${activeCount} active`)}</span>
          <button className="text-button" disabled={loading} onClick={() => setRefreshVersion((current) => current + 1)} type="button">{t(...jobCenterMessages.refresh)}</button>
        </div>
        {error && <div className="notice notice--error" role="alert">{error} {t(...jobCenterMessages.retrying)}</div>}
        {loading && rows.length === 0 ? <div className="empty-inline"><span className="spinner" />{t(...jobCenterMessages.loading)}</div> : rows.length === 0 ? <div className="empty-inline">{t(...jobCenterMessages.empty)}</div> : (
          <div className="job-center__list">
            {rows.map((row) => {
              const labels = row.statusLabel ?? (row.status === "unresolved" ? jobCenterMessages.unresolved : row.kind === "translator" ? TRANSLATION_STATUS_LABELS[row.status as TranslationJob["status"]] : PAGE_CHECK_STATUS_LABELS[row.status as PageCheckJobSummary["status"]]);
              return <article className={`job-center__job${row.active ? " job-center__job--active" : ""}`} key={`${row.kind}-${row.language}-${row.id}`}>
                <div className="job-center__job-heading"><span>{row.kind === "translator" ? t(...jobCenterMessages.translator) : t(...jobCenterMessages.pageCheck)}</span><b>{t(labels[0], labels[1])}</b></div>
                <strong>{row.title}</strong>
                <small>{row.language} · {row.id}</small>
                {row.error && <p className="job-center__error">{row.error}</p>}
                <footer><time dateTime={new Date(row.updatedAt * 1_000).toISOString()}>{row.updatedAt ? formatDateTime(locale, new Date(row.updatedAt * 1_000)) : "-"}</time><button className="text-button" onClick={() => { onNavigate({ route: row.kind, language: row.language, jobId: row.id }); close(); }} type="button">{t(...jobCenterMessages.open)}</button></footer>
              </article>;
            })}
          </div>
        )}
      </aside>
    </>}
  </>;
}
