import { useEffect, useRef, useState, type FormEvent } from "react";

import { ApiResponseError, MutationNotStartedError, getPageSnapshot, getTranslatorErrors, getTranslatorHealth, previewPage, previewTranslations, startTranslationJob } from "../api";
import { useI18n } from "../i18n";
import { translatorMessages } from "../messages/translator";
import { MAX_TRACKED_TRANSLATION_JOBS, TranslationJobsProvider, isActiveTranslationJob, useOptionalTranslationJobs, useTranslationJobs, type TranslationJobsContextValue, type TranslationPollTarget } from "../translationJobs";
import type { ProcessedPageEntry, Row, TranslationHealth, TranslationJob, WiktionaryPageSnapshot } from "../types";
import { ProcessedEntryList } from "./WiktionaryPageExplorer";

interface TranslatorWorkspaceProps {
  onMessage: (message: string, tone?: "success" | "error") => void;
  onOpenLexicon?: (word: string) => void;
}

interface TranslationSubmissionAttempt extends TranslationPollTarget {
  title: string;
}

const JOB_STATUS_LABELS: Record<TranslationJob["status"], readonly [string, string]> = {
  pending: ["Miandry", "Pending"],
  running: ["Mandeha", "Running"],
  done: ["Vita", "Done"],
  error: ["Hadisoana", "Error"],
};

const JOB_STAGE_LABELS: Record<TranslationJob["stage"], readonly [string, string]> = {
  queued: ["Ao anaty filaharana", "Queued"],
  loading_source: ["Maka ny pejy loharano", "Loading source page"],
  translating: ["Mandika ny pejy", "Translating page"],
  queueing_publication: ["Mampiditra ny famoahana anaty filaharana", "Queueing publication"],
  prefiltering_publication: ["Manamarina alohan'ny famoahana", "Checking before publication"],
  publication_queued: ["Tafiditra anaty filaharana ny famoahana", "Publication queued"],
  publication_filtered: ["Nolavin'ny sivana", "Filtered out"],
  completed: ["Vita", "Completed"],
  failed: ["Tsy nahomby", "Failed"],
};

const PUBLICATION_STATE_LABELS: Record<TranslationJob["publication_state"], readonly [string, string]> = {
  not_queued: ["Tsy mbola anaty filaharana", "Not queued"],
  queued: ["Ao anaty filaharana", "Queued"],
  filtered_out: ["Nolavin'ny sivana", "Filtered out"],
};

const JOB_STAGE_MESSAGES: Record<TranslationJob["stage"], readonly [string, string]> = {
  queued: ["Miandry ny mpandika teny ny asa.", "The job is waiting for a translator."],
  loading_source: ["Alaina ny pejy loharano.", "Loading the source page."],
  translating: ["Adika ny pejy loharano.", "Translating the source page."],
  queueing_publication: ["Ampidirina anaty filaharana ny vokatra.", "Queueing translated entries for publication."],
  prefiltering_publication: ["Hamarinin'ny page checker ny pejy voadika.", "The page checker is verifying the translated page."],
  publication_queued: ["Tafiditra anaty filaharana ny famoahana.", "Publication is queued."],
  publication_filtered: ["Tsy nandalo ny page checker ny pejy ka nariana.", "The page did not pass the page checker and was discarded."],
  completed: ["Vita ny asa fandikana.", "The translation job completed."],
  failed: ["Tsy nahomby ny asa fandikana.", "The translation job failed."],
};

const UNKNOWN_LABEL = ["Tsy fantatra", "Unknown"] as const;

function jobLabel(labels: Readonly<Record<string, readonly [string, string]>>, value: string): readonly [string, string] {
  return labels[value] ?? UNKNOWN_LABEL;
}


function SnapshotInspector({ snapshot, onOpenLexicon }: { snapshot: WiktionaryPageSnapshot; onOpenLexicon?: (word: string) => void }) {
  const { t } = useI18n();
  return (
    <div className="snapshot-inspector">
      <dl>
        <div><dt>{t(...translatorMessages.page)}</dt><dd>{snapshot.language}:{snapshot.title}</dd></div>
        <div><dt>{t("Namespace", "Namespace")}</dt><dd>{snapshot.namespace ?? "-"}</dd></div>
        <div><dt>SHA-256</dt><dd><code>{snapshot.content_sha256}</code></dd></div>
        <div><dt>{t(...translatorMessages.parsing)}</dt><dd>{snapshot.parsed ? t(...translatorMessages.parsingSucceeded) : t(...translatorMessages.parsingFailed)}</dd></div>
      </dl>
      {snapshot.parse_error && <p className="notice notice--error" role="alert">{snapshot.parse_error}</p>}
      <details open><summary>{t(...translatorMessages.liveSource)}</summary><pre>{snapshot.content}</pre></details>
      {snapshot.entries.length > 0 && <details><summary>{t(`Fizarana voavaky ${snapshot.entries.length}`, `${snapshot.entries.length} parsed sections`)}</summary><ProcessedEntryList entries={snapshot.entries} onOpenLexicon={onOpenLexicon} /></details>}
      <p className="snapshot-inspector__trust">{t(...translatorMessages.untrustedEvidence)}</p>
    </div>
  );
}

export function TranslatorWorkspace(props: TranslatorWorkspaceProps) {
  const translationJobs = useOptionalTranslationJobs();
  if (translationJobs) return <TranslatorWorkspaceContent {...props} translationJobs={translationJobs} />;
  return <TranslationJobsProvider onMessage={props.onMessage}><TranslatorWorkspaceWithJobs {...props} /></TranslationJobsProvider>;
}

function TranslatorWorkspaceWithJobs(props: TranslatorWorkspaceProps) {
  return <TranslatorWorkspaceContent {...props} translationJobs={useTranslationJobs()} />;
}

function TranslatorWorkspaceContent({ onMessage, onOpenLexicon, translationJobs }: TranslatorWorkspaceProps & { translationJobs: TranslationJobsContextValue }) {
  const { t } = useI18n();
  const { jobs, pollTargets, pollingErrors, retryDelaySeconds, trackProvisional, acceptJob, discardTarget } = translationJobs;
  const [health, setHealth] = useState<TranslationHealth | null>(null);
  const [language, setLanguage] = useState("en");
  const [title, setTitle] = useState("");
  const [result, setResult] = useState<unknown>(null);
  const [resultLabel, setResultLabel] = useState<{ malagasy: string; english: string } | null>(null);
  const [resultKind, setResultKind] = useState<"page" | "snapshot" | "json">("json");
  const [previewBusy, setPreviewBusy] = useState(false);
  const [submittingJob, setSubmittingJob] = useState(false);
  const [submissionAttempt, setSubmissionAttempt] = useState<TranslationSubmissionAttempt | null>(null);
  const mountedRef = useRef(true);

  const healthStatusLabels: Record<string, string> = {
    healthy: t("Salama", "Healthy"),
    ok: t("Mandeha", "Operational"),
    online: t("Mandeha", "Online"),
    degraded: t("Misy olana", "Degraded"),
    unavailable: t("Tsy misy", "Unavailable"),
    offline: t("Tsy mandeha", "Offline"),
  };

  useEffect(() => {
    mountedRef.current = true;
    const controller = new AbortController();
    void getTranslatorHealth(controller.signal)
      .then((value) => {
        if (!controller.signal.aborted) setHealth(value);
      })
      .catch(() => {
        if (!controller.signal.aborted) setHealth(null);
      });
    return () => {
      mountedRef.current = false;
      controller.abort();
    };
  }, []);

  async function runPreview(malagasyLabel: string, englishLabel: string, operation: () => Promise<unknown>, requiresTitle = true, kind: "page" | "snapshot" | "json" = "json"): Promise<void> {
    if (requiresTitle && !title.trim()) return;
    setPreviewBusy(true);
    setResultLabel({ malagasy: malagasyLabel, english: englishLabel });
    setResultKind(kind);
    try {
      const value = await operation();
      if (!mountedRef.current) return;
      setResult(value);
      setPreviewBusy(false);
      onMessage(t(`Vita ny ${malagasyLabel.toLowerCase()}.`, `${englishLabel} completed.`));
    } catch (caught) {
      if (mountedRef.current) {
        onMessage(caught instanceof Error ? caught.message : t(`Tsy nahomby ny ${malagasyLabel.toLowerCase()}.`, `${englishLabel} failed.`), "error");
      }
    } finally {
      if (mountedRef.current) setPreviewBusy(false);
    }
  }

  function submitPreview(event: FormEvent): void {
    event.preventDefault();
    const previewLanguage = language.trim();
    const previewTitle = title.trim();
    if (!previewLanguage || !previewTitle) return;
    void runPreview("Topi-maso amin'ny pejy", "Page preview", () => previewPage(previewLanguage, previewTitle) as Promise<Row[]>, true, "page");
  }

  async function startTrackedJob(): Promise<void> {
    const jobLanguage = language.trim();
    const jobTitle = title.trim();
    if (!jobLanguage || !jobTitle) return;
    const previousAttempt = submissionAttempt;
    const retryingAmbiguousAttempt = previousAttempt?.language === jobLanguage && previousAttempt.title === jobTitle
      && pollTargets.some((target) => target.jobId === previousAttempt.jobId);
    if (pollTargets.length >= MAX_TRACKED_TRANSLATION_JOBS && !retryingAmbiguousAttempt) {
      onMessage(t(...translatorMessages.trackedJobListFull), "error");
      return;
    }
    const duplicateActiveJob = pollTargets.some((target) => (target.requestedLanguage ?? target.language) === jobLanguage && target.title?.toLocaleLowerCase() === jobTitle.toLocaleLowerCase())
      || jobs.some((job) => isActiveTranslationJob(job) && job.language === jobLanguage && job.title.toLocaleLowerCase() === jobTitle.toLocaleLowerCase());
    if (duplicateActiveJob && !retryingAmbiguousAttempt) {
      onMessage(t(...translatorMessages.trackedJobDuplicate), "error");
      return;
    }
    if (!window.confirm(t(
      `Hadika ary hampidirina anaty filaharana havoaka ve ny "${jobTitle}"? Mety hanavao ny Wiktionary izany.`,
      `Translate and queue publication for "${jobTitle}"? This can update Wiktionary.`,
    ))) return;

    setSubmittingJob(true);
    const requestId = previousAttempt?.language === jobLanguage && previousAttempt.title === jobTitle
      ? previousAttempt.jobId
      : crypto.randomUUID();
    setSubmissionAttempt({ language: jobLanguage, title: jobTitle, jobId: requestId });
    const provisionalTarget = { language: jobLanguage, jobId: requestId, requestedLanguage: jobLanguage, title: jobTitle, provisionalSince: Date.now() };
    trackProvisional(provisionalTarget);
    try {
      const acceptedJob = await startTranslationJob(jobLanguage, jobTitle, requestId);
      if (!mountedRef.current) return;
      setSubmissionAttempt(null);
      acceptJob(requestId, acceptedJob, jobLanguage);
    } catch (caught) {
      const definitiveRejection = caught instanceof MutationNotStartedError
        || (caught instanceof ApiResponseError && caught.status >= 400 && caught.status < 500);
      if (definitiveRejection) {
        discardTarget(requestId);
        if (!(caught instanceof ApiResponseError) || caught.status !== 429) {
          setSubmissionAttempt(null);
        }
      }
      if (mountedRef.current) {
        onMessage(caught instanceof Error ? caught.message : t("Tsy azo natomboka ny asa fandikana.", "The translation job could not be started."), "error");
      }
    } finally {
      if (mountedRef.current) setSubmittingJob(false);
    }
  }

  const canRun = Boolean(language.trim() && title.trim());
  const unresolvedTargets = pollTargets.filter((target) => !jobs.some((job) => job.job_id === target.jobId));
  const averageDuration = health?.average_job_duration_seconds;
  const retryingAmbiguousAttempt = submissionAttempt?.language === language.trim() && submissionAttempt.title === title.trim()
    && pollTargets.some((target) => target.jobId === submissionAttempt.jobId);
  const matchingActiveJob = !retryingAmbiguousAttempt && (pollTargets.some((target) => (target.requestedLanguage ?? target.language) === language.trim() && target.title?.toLocaleLowerCase() === title.trim().toLocaleLowerCase())
    || jobs.some((job) => isActiveTranslationJob(job) && job.language === language.trim() && job.title.toLocaleLowerCase() === title.trim().toLocaleLowerCase()));
  const trackingAtCapacity = !retryingAmbiguousAttempt && pollTargets.length >= MAX_TRACKED_TRANSLATION_JOBS;

  return (
    <div className="translator-workspace">
      <section className="translator-command panel">
        <div className="translator-command__intro">
          <p className="eyebrow">{t("Fizotran'ny Wiktionary", "Wiktionary pipeline")}</p>
          <h2>{t("Zahao, adikao, ary araho ny famoahana.", "Inspect, translate, and track publication.")}</h2>
          <p>{t("Ampiasao ny topi-maso, avy eo araho mandra-pahatapitry ny asa fandikana sy fampidirana anaty filaharana.", "Use previews, then track translation and publication queueing through completion.")}</p>
        </div>
        <form onSubmit={submitPreview}>
          <label className="field"><span>{t("Fiteny loharano", "Source language")}</span><input required value={language} onChange={(event) => setLanguage(event.target.value)} /></label>
          <label className="field field--grow"><span>{t("Lohatenin'ny pejy", "Page title")}</span><input required value={title} onChange={(event) => setTitle(event.target.value)} placeholder={t("Lohatenin'ny pejy Wiktionary", "Wiktionary page title")} /></label>
          <button className="button button--primary" type="submit" disabled={previewBusy || submittingJob}>{previewBusy ? t("Mijery...", "Previewing...") : t("Hijery topi-maso", "Preview page")}</button>
        </form>
        <div className="translator-actions">
          <button type="button" disabled={previewBusy || submittingJob || !canRun} onClick={() => void runPreview("Topi-maso amin'ny dikanteny", "Translation preview", () => previewTranslations(language.trim(), title.trim()))}><span>01</span><strong>{t("Hijery topi-maso amin'ny dikanteny", "Preview translations")}</strong><small>{t("Tsy misy famoahana", "No publishing")}</small></button>
          <button className="translator-actions__tracked" type="button" aria-label={submittingJob ? t("Mandefa ny asa...", "Starting job...") : t("Handika sy hampiditra ny famoahana anaty filaharana", "Translate and queue publication")} disabled={previewBusy || submittingJob || !canRun || matchingActiveJob || trackingAtCapacity} onClick={() => void startTrackedJob()}><span>02</span><strong>{submittingJob ? t("Mandefa ny asa...", "Starting job...") : t("Handika sy hampiditra ny famoahana anaty filaharana", "Translate and queue publication")}</strong><small>{matchingActiveJob ? t(...translatorMessages.trackedPage) : trackingAtCapacity ? t(...translatorMessages.trackedJobListFullShort) : t(...translatorMessages.trackMultipleJobs)}</small></button>
        </div>
      </section>

      <section className="metric-grid metric-grid--translator">
        {[
          [t("Tolotra", "Service"), health?.status ? healthStatusLabels[health.status.toLowerCase()] ?? health.status : t("Tsy fantatra", "Unknown")],
          [t("Mandeha", "Running"), health?.process_running_jobs ?? health?.running_jobs ?? 0],
          [t("Anaty filaharana", "Queued"), health?.process_queued_jobs ?? health?.queued_jobs ?? health?.jobs ?? 0],
          [t("Toerana malalaka", "Available slots"), health?.available_job_slots ?? health?.available_slots ?? "-"],
          [t(...translatorMessages.completed), health?.completed_job_count ?? health?.completed_jobs ?? 0],
          [t(...translatorMessages.failed), health?.failed_job_count ?? health?.failed_jobs ?? 0],
          [t(...translatorMessages.rejected), health?.rejected_job_count ?? health?.rejected_jobs ?? 0],
          [t(...translatorMessages.averageDuration), typeof averageDuration === "number" ? t(`${Math.round(averageDuration)} seg`, `${Math.round(averageDuration)} sec`) : "-"],
        ].map(([label, value]) => <article className="metric-card" key={String(label)}><span>{label}</span><strong>{String(value)}</strong></article>)}
      </section>

      {health && <section className={`notice translator-health${health.status === "degraded" || health.accepting_async_jobs === false ? " notice--error" : ""}`}>
        <strong>{health.message ?? t(...translatorMessages.noHealthMessage)}</strong>
        <span>{t(...translatorMessages.counterSource)}: {health.counter_source ?? t(...translatorMessages.unknown)}</span>
        <span>{t(...translatorMessages.capacity)}: {health.process_admitted_jobs ?? 0} / {health.process_job_capacity ?? "-"}</span>
        <span>{t(...translatorMessages.recentErrors)}: {health.recent_job_error_count ?? 0}</span>
        <span>{health.accepting_async_jobs === false ? t(...translatorMessages.notAcceptingJobs) : t(...translatorMessages.acceptingJobs)}</span>
      </section>}

      {unresolvedTargets.map((target) => (
        <section className="panel translation-job translation-job--pending translation-job--provisional" role="status" aria-live="polite" key={target.jobId}>
          <div className="translation-job__provisional-status">
            <span className="spinner" aria-hidden="true" />
            <div>
              <p className="eyebrow">{t("Asa fandikana araha-maso", "Tracked translation job")}</p>
              <h3>{target.title || t(...translatorMessages.resolvingJob)}</h3>
              <p><strong>{t(...translatorMessages.resolvingJob)}</strong> {t(...translatorMessages.retainedRequestId)}</p>
            </div>
          </div>
          {pollingErrors[target.jobId] && (
            <p className="translation-job__error" role="alert">
              <strong>{t("Tsy mbola azo ny sata.", "Status not available yet.")}</strong> {pollingErrors[target.jobId]} {retryDelaySeconds[target.jobId] !== undefined && t(`Haverina afaka ${retryDelaySeconds[target.jobId]} segondra.`, `Retrying in ${retryDelaySeconds[target.jobId]} seconds.`)}
            </p>
          )}
        </section>
      ))}

      {jobs.map((job) => {
        const jobStatusLabel = jobLabel(JOB_STATUS_LABELS, job.status);
        const jobStageLabel = jobLabel(JOB_STAGE_LABELS, job.stage);
        const publicationStateLabel = jobLabel(PUBLICATION_STATE_LABELS, job.publication_state);
        const fallbackJobMessage = jobLabel(JOB_STAGE_MESSAGES, job.stage);
        const activeTarget = pollTargets.find((target) => target.jobId === job.job_id);
        return <section className={`panel translation-job translation-job--${job.status}`} aria-labelledby={`translation-job-heading-${job.job_id}`} key={job.job_id}>
          <header className="translation-job__header">
            <div>
              <p className="eyebrow">{t("Asa fandikana araha-maso", "Tracked translation job")}</p>
              <h3 id={`translation-job-heading-${job.job_id}`}>{job.title}</h3>
            </div>
            <div className="translation-job__live" role="status" aria-live="polite" aria-atomic="true">
              {activeTarget && isActiveTranslationJob(job) && <span className="spinner" aria-hidden="true" />}
              <span>{t(...jobStatusLabel)}</span>
              <strong>{t(...jobStageLabel)}</strong>
            </div>
          </header>

          <dl className="translation-job__metadata">
            <div><dt>{t("Mari-panondro ny asa", "Job ID")}</dt><dd><code>{job.job_id}</code></dd></div>
            <div><dt>{t("Fiteny", "Language")}</dt><dd>{job.language}</dd></div>
            <div><dt>{t("Dingana", "Stage")}</dt><dd>{t(...jobStageLabel)}</dd></div>
            <div><dt>{t("Toetry ny famoahana", "Publication state")}</dt><dd>{t(...publicationStateLabel)}</dd></div>
          </dl>

          <p className="translation-job__message"><span>{t("Hafatra", "Message")}</span>{job.message || t(...fallbackJobMessage)}</p>

          {pollingErrors[job.job_id] && (
            <p className="translation-job__error" role="alert">
              <strong>{t("Tsy azo ny sata farany.", "Latest status unavailable.")}</strong> {pollingErrors[job.job_id]} {retryDelaySeconds[job.job_id] !== undefined && t(`Haverina afaka ${retryDelaySeconds[job.job_id]} segondra.`, `Retrying in ${retryDelaySeconds[job.job_id]} seconds.`)}
            </p>
          )}

          <div className="translation-job__outputs">
            <section>
              <h4>{t("Vokatra", "Result")}</h4>
              {job.result === null ? <p>{t("Tsy mbola misy vokatra.", "No result yet.")}</p> : <pre>{JSON.stringify(job.result, null, 2)}</pre>}
            </section>
            <section>
              <h4>{t("Hadisoana", "Error")}</h4>
              {job.error ? <p className="translation-job__terminal-error" role="alert">{job.error}</p> : <p>{t("Tsy misy hadisoana.", "No error.")}</p>}
            </section>
          </div>
        </section>;
      })}

      <section className="panel inspector-panel">
        <div className="panel__header">
          <div><p className="eyebrow">{t("Mpizaha valiny", "Response inspector")}</p><h3>{resultLabel ? t(resultLabel.malagasy, resultLabel.english) : t("Tsy mbola misy asa voafidy", "No operation selected")}</h3></div>
          <div className="inspector-panel__actions">
            <button className="text-button" type="button" disabled={previewBusy || submittingJob || !canRun || !["en", "mg"].includes(language.trim())} onClick={() => void runPreview(...translatorMessages.liveSnapshotLabel, () => getPageSnapshot(language.trim(), title.trim()), true, "snapshot")}>{t(...translatorMessages.liveSnapshot)}</button>
            <button className="text-button" type="button" disabled={previewBusy || submittingJob} onClick={() => void runPreview("Hadisoana farany tamin'ny asa", "Recent job errors", async () => (await getTranslatorErrors()).errors, false)}>{t("Hadisoana farany", "Recent errors")}</button>
          </div>
        </div>
        {previewBusy ? <div className="table-state"><span className="spinner" />{t("Miandry ny mpandika teny...", "Waiting for translator...")}</div> : result === null ? <div className="empty-inline">{t(...translatorMessages.operationResults)}</div> : resultKind === "page" ? <>
          <ProcessedEntryList entries={result as ProcessedPageEntry[]} onOpenLexicon={onOpenLexicon} />
          <details className="inspector-raw"><summary>{t(...translatorMessages.rawJson)}</summary><pre>{JSON.stringify(result, null, 2)}</pre></details>
        </> : resultKind === "snapshot" ? <SnapshotInspector snapshot={result as WiktionaryPageSnapshot} onOpenLexicon={onOpenLexicon} /> : <pre>{JSON.stringify(result, null, 2)}</pre>}
      </section>
    </div>
  );
}
