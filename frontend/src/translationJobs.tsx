/* eslint-disable react-refresh/only-export-components */
import { createContext, useContext, useEffect, useEffectEvent, useRef, useState, type ReactNode } from "react";

import { ApiResponseError, InvalidApiResponseError, getTranslationJob } from "./api";
import { useI18n } from "./i18n";
import type { TranslationJob } from "./types";

export interface TranslationPollTarget {
  language: string;
  jobId: string;
  requestedLanguage?: string;
  title?: string;
  provisionalSince?: number;
}

export const MAX_TRACKED_TRANSLATION_JOBS = 8;

const POLL_INTERVAL_MS = 3_000;
const POLL_RETRY_DELAYS_MS = [3_000, 6_000, 12_000, 24_000, 30_000] as const;
const PROVISIONAL_JOB_TIMEOUT_MS = 120_000;
const TRACKED_TRANSLATION_JOB_KEY = "botjagwar-atlas-tracked-translation-job";

export interface TranslationJobsContextValue {
  jobs: TranslationJob[];
  pollTargets: TranslationPollTarget[];
  pollingErrors: Record<string, string>;
  retryDelaySeconds: Record<string, number>;
  trackProvisional: (target: TranslationPollTarget) => void;
  acceptJob: (requestId: string, job: TranslationJob, requestedLanguage: string) => void;
  discardTarget: (jobId: string) => void;
}

const TranslationJobsContext = createContext<TranslationJobsContextValue | null>(null);

function isPollTarget(value: unknown): value is TranslationPollTarget {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const target = value as Partial<TranslationPollTarget>;
  return typeof target.language === "string" && Boolean(target.language)
    && typeof target.jobId === "string" && Boolean(target.jobId);
}

function normalizePollTarget(target: TranslationPollTarget): TranslationPollTarget {
  return {
    language: target.language,
    jobId: target.jobId,
    requestedLanguage: typeof target.requestedLanguage === "string" && target.requestedLanguage ? target.requestedLanguage : undefined,
    title: typeof target.title === "string" && target.title ? target.title : undefined,
    provisionalSince: typeof target.provisionalSince === "number" && Number.isFinite(target.provisionalSince) ? target.provisionalSince : undefined,
  };
}

function loadTrackedJobs(): TranslationPollTarget[] {
  try {
    const rawTarget = window.sessionStorage.getItem(TRACKED_TRANSLATION_JOB_KEY);
    if (!rawTarget) return [];
    const parsed = JSON.parse(rawTarget) as unknown;
    const targets = Array.isArray(parsed) ? parsed.filter(isPollTarget) : isPollTarget(parsed) ? [parsed] : [];
    return targets.map(normalizePollTarget).slice(0, MAX_TRACKED_TRANSLATION_JOBS);
  } catch {
    return [];
  }
}

function persistTrackedJobs(targets: TranslationPollTarget[]): void {
  try {
    if (targets.length > 0) {
      window.sessionStorage.setItem(TRACKED_TRANSLATION_JOB_KEY, JSON.stringify(targets.slice(0, MAX_TRACKED_TRANSLATION_JOBS)));
    } else {
      window.sessionStorage.removeItem(TRACKED_TRANSLATION_JOB_KEY);
    }
  } catch {
    // Tracking still works for the current mount when browser storage is unavailable.
  }
}

export function isActiveTranslationJob(job: TranslationJob): boolean {
  return job.status === "pending" || job.status === "running";
}

function isTerminalJob(job: TranslationJob): boolean {
  return job.status === "done" || job.status === "error";
}

export function TranslationJobsProvider({ children, onMessage }: { children: ReactNode; onMessage: (message: string, tone?: "success" | "error") => void }) {
  const { t } = useI18n();
  const [jobs, setJobs] = useState<TranslationJob[]>([]);
  const [pollTargets, setPollTargets] = useState<TranslationPollTarget[]>(loadTrackedJobs);
  const [pollingErrors, setPollingErrors] = useState<Record<string, string>>({});
  const [retryDelaySeconds, setRetryDelaySeconds] = useState<Record<string, number>>({});
  const terminalToastsRef = useRef(new Set<string>());

  function reportTerminalJob(job: TranslationJob): void {
    const key = `${job.language}\u0000${job.job_id}`;
    if (terminalToastsRef.current.has(key)) return;
    terminalToastsRef.current.add(key);
    if (job.status === "error") {
      onMessage(job.error || t("Tsy nahomby ny asa fandikana.", "The translation job failed."), "error");
    } else {
      onMessage(t("Vita ny asa fandikana.", "The translation job completed."));
    }
  }

  const reportTerminalJobFromEffect = useEffectEvent(reportTerminalJob);

  const pollingErrorMessage = useEffectEvent((caught: unknown): string =>
    caught instanceof Error ? caught.message : t("Tsy azo ny satan'ny asa fandikana.", "The translation job status could not be loaded."),
  );

  const permanentPollingErrorMessage = useEffectEvent((caught: unknown): string => {
    if (caught instanceof InvalidApiResponseError) {
      return t("Tsy manankery ny valin'ny satan'ny asa fandikana.", "The translation job status response is invalid.");
    }
    if (caught instanceof ApiResponseError && caught.status === 404) {
      return t("Tsy hita intsony ny asa fandikana.", "The translation job no longer exists.");
    }
    return pollingErrorMessage(caught);
  });

  const unknownJobStatusMessage = useEffectEvent(() =>
    t("Tsy fantatra ny satan'ny asa fandikana.", "The translation job returned an unknown status."),
  );

  const reportStoppedPolling = useEffectEvent((message: string) => onMessage(message, "error"));

  function discardTarget(jobId: string): void {
    setPollTargets((current) => {
      const next = current.filter((target) => target.jobId !== jobId);
      persistTrackedJobs(next);
      return next;
    });
  }

  function trackProvisional(target: TranslationPollTarget): void {
    setPollingErrors((current) => { const next = { ...current }; delete next[target.jobId]; return next; });
    setRetryDelaySeconds((current) => { const next = { ...current }; delete next[target.jobId]; return next; });
    setPollTargets((current) => {
      const next = [target, ...current.filter((item) => item.jobId !== target.jobId)];
      persistTrackedJobs(next);
      return next;
    });
  }

  function acceptJob(requestId: string, job: TranslationJob, requestedLanguage: string): void {
    setJobs((current) => [job, ...current.filter((item) => item.job_id !== job.job_id)].slice(0, MAX_TRACKED_TRANSLATION_JOBS));
    if (isActiveTranslationJob(job)) {
      setPollTargets((current) => {
        const target = { language: job.language, jobId: job.job_id, requestedLanguage, title: job.title };
        const next = [target, ...current.filter((item) => item.jobId !== requestId && item.jobId !== job.job_id)];
        persistTrackedJobs(next);
        return next;
      });
    } else {
      discardTarget(requestId);
      reportTerminalJob(job);
    }
  }

  useEffect(() => {
    if (pollTargets.length === 0) return;
    const controllers = new Map<string, AbortController>();
    const timers = new Map<string, ReturnType<typeof setTimeout>>();

    for (const target of pollTargets) {
      const controller = new AbortController();
      controllers.set(target.jobId, controller);
      let retryAttempt = 0;

      function schedulePoll(delay: number): void {
        timers.set(target.jobId, setTimeout(() => void poll(), delay));
      }

      async function poll(): Promise<void> {
        try {
          const currentJob = await getTranslationJob(target.language, target.jobId, controller.signal);
          if (controller.signal.aborted) return;
          setJobs((current) => [currentJob, ...current.filter((job) => job.job_id !== currentJob.job_id)].slice(0, MAX_TRACKED_TRANSLATION_JOBS));
          setPollingErrors((current) => { const next = { ...current }; delete next[target.jobId]; return next; });
          setRetryDelaySeconds((current) => { const next = { ...current }; delete next[target.jobId]; return next; });
          retryAttempt = 0;
          if (isActiveTranslationJob(currentJob)) {
            schedulePoll(POLL_INTERVAL_MS);
          } else if (isTerminalJob(currentJob)) {
            reportTerminalJobFromEffect(currentJob);
            discardTarget(target.jobId);
          } else {
            throw new Error(unknownJobStatusMessage());
          }
        } catch (caught) {
          if (controller.signal.aborted) return;
          const provisionalStillPending = caught instanceof ApiResponseError
            && caught.status === 404
            && target.provisionalSince !== undefined
            && Date.now() - target.provisionalSince < PROVISIONAL_JOB_TIMEOUT_MS;
          const permanentFailure = caught instanceof InvalidApiResponseError
            || (caught instanceof ApiResponseError && [400, 404].includes(caught.status) && !provisionalStillPending);
          const message = permanentFailure ? permanentPollingErrorMessage(caught) : pollingErrorMessage(caught);
          setPollingErrors((current) => ({ ...current, [target.jobId]: message }));
          if (permanentFailure) {
            setRetryDelaySeconds((current) => { const next = { ...current }; delete next[target.jobId]; return next; });
            discardTarget(target.jobId);
            reportStoppedPolling(message);
            return;
          }
          const delay = POLL_RETRY_DELAYS_MS[Math.min(retryAttempt, POLL_RETRY_DELAYS_MS.length - 1)];
          retryAttempt += 1;
          setRetryDelaySeconds((current) => ({ ...current, [target.jobId]: delay / 1_000 }));
          schedulePoll(delay);
        }
      }

      schedulePoll(POLL_INTERVAL_MS);
    }
    return () => {
      controllers.forEach((controller) => controller.abort());
      timers.forEach((timer) => clearTimeout(timer));
    };
  }, [pollTargets]);

  return <TranslationJobsContext.Provider value={{ jobs, pollTargets, pollingErrors, retryDelaySeconds, trackProvisional, acceptJob, discardTarget }}>{children}</TranslationJobsContext.Provider>;
}

export function useTranslationJobs(): TranslationJobsContextValue {
  const value = useContext(TranslationJobsContext);
  if (!value) throw new Error("useTranslationJobs must be used inside TranslationJobsProvider");
  return value;
}

export function useOptionalTranslationJobs(): TranslationJobsContextValue | null {
  return useContext(TranslationJobsContext);
}
