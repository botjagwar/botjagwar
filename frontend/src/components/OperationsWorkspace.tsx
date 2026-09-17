import { useEffect, useState } from "react";

import { getOperations } from "../api";
import { formatDateTime, useI18n } from "../i18n";
import { operationsMessages } from "../messages/operations";
import type { OperationOutcome, OperationRecord, OperationService } from "../types";
import { ClassicTitleBar } from "./ClassicTitleBar";

function downloadFile(contents: string, filename: string, type: string): void {
  const url = URL.createObjectURL(new Blob([contents], { type }));
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

function operationsToCsv(operations: OperationRecord[]): string {
  const quote = (value: string | number) => `"${String(value).replaceAll('"', '""')}"`;
  const rows = operations.map((operation) => [
    operation.id,
    operation.accepted_at,
    operation.completed_at ?? "",
    operation.username,
    operation.service,
    operation.action,
    operation.resource,
    JSON.stringify(operation.target),
    operation.changed_fields.join(","),
    operation.outcome,
    operation.error_summary ?? "",
  ]);
  return [
    ["id", "accepted_at", "completed_at", "username", "service", "action", "resource", "target", "changed_fields", "outcome", "error_summary"],
    ...rows,
  ].map((row) => row.map(quote).join(",")).join("\n");
}

function matchesSearch(operation: OperationRecord, search: string): boolean {
  const term = search.trim().toLocaleLowerCase();
  if (!term) return true;
  return [
    operation.action,
    operation.resource,
    operation.service,
    operation.username,
    JSON.stringify(operation.target),
    operation.error_summary ?? "",
  ].join(" ").toLocaleLowerCase().includes(term);
}

/** Display the server-owned audit journal for Atlas mutations. */
export function OperationsWorkspace() {
  const { locale, t } = useI18n();
  const [operations, setOperations] = useState<OperationRecord[]>([]);
  const [service, setService] = useState<OperationService | "">("");
  const [outcome, setOutcome] = useState<OperationOutcome | "">("");
  const [search, setSearch] = useState("");
  const [refreshVersion, setRefreshVersion] = useState(0);
  const [nextBefore, setNextBefore] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    const controller = new AbortController();
    getOperations({ service, outcome }, controller.signal)
      .then((page) => {
        setOperations(page.operations);
        setNextBefore(page.next_before);
      })
      .catch((caught: unknown) => {
        if (!controller.signal.aborted) setError(caught instanceof Error ? caught.message : t("Tsy azo ny audit.", "Unable to load the audit."));
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [outcome, refreshVersion, service, t]);

  async function loadMore() {
    if (nextBefore === null) return;
    setLoading(true);
    try {
      const page = await getOperations({ before: nextBefore, service, outcome });
      setOperations((current) => [...current, ...page.operations]);
      setNextBefore(page.next_before);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("Tsy azo ny audit.", "Unable to load the audit."));
    } finally {
      setLoading(false);
    }
  }

  const filteredOperations = operations.filter((operation) => matchesSearch(operation, search));
  const outcomeLabels: Record<OperationOutcome, string> = {
    pending: t("Miandry", "Pending"),
    succeeded: t("Nahomby", "Succeeded"),
    failed: t("Tsy nahomby", "Failed"),
  };

  function refresh() {
    setLoading(true);
    setError("");
    setRefreshVersion((current) => current + 1);
  }

  return <div className="operations-workspace">
    <section className="operations-intro panel">
      <ClassicTitleBar title={t("Dian'ny asa", "Operations audit")} />
      <div>
        <p className="eyebrow">{t(...operationsMessages.serverOwned)}</p>
        <h2>{t("Dian'ny asa", "Operations audit")}</h2>
        <p>{t("Firaketana maharitra momba ireo fanovana angona, famoahana, ary fanaraha-maso tolotra nataon'ireo mpampiasa voamarina.", "A persistent record of data mutations, publishing, and service-control actions made by authenticated users.")}</p>
      </div>
      <strong>{filteredOperations.length}</strong>
    </section>
    <section className="operations-filter panel">
      <ClassicTitleBar title={t("Sivana", "Filters")} />
      <label className="field operations-filter__search">
        <span>{t(...operationsMessages.search)}</span>
        <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder={t(...operationsMessages.searchPlaceholder)} type="search" />
      </label>
      <label className="field">
        <span>{t("Tolotra", "Service")}</span>
        <select value={service} onChange={(event) => { setLoading(true); setError(""); setService(event.target.value as OperationService | ""); }}>
          <option value="">{t("Rehetra", "All")}</option>
          <option value="database">{t("Database", "Database")}</option>
          <option value="dictionary">{t("Dictionary", "Dictionary")}</option>
          <option value="gemma">Gemma</option>
          <option value="translator">{t("Translator", "Translator")}</option>
          <option value="supervisor">{t("Supervisor", "Supervisor")}</option>
        </select>
      </label>
      <label className="field">
        <span>{t("Vokatra", "Outcome")}</span>
        <select value={outcome} onChange={(event) => { setLoading(true); setError(""); setOutcome(event.target.value as OperationOutcome | ""); }}>
          <option value="">{t("Rehetra", "All")}</option>
          <option value="pending">{outcomeLabels.pending}</option>
          <option value="succeeded">{outcomeLabels.succeeded}</option>
          <option value="failed">{outcomeLabels.failed}</option>
        </select>
      </label>
      <div className="operations-filter__actions" aria-label={t(...operationsMessages.auditTools)}>
        <button className="button button--ghost operations-refresh" disabled={loading} type="button" onClick={refresh}>{loading ? t("Maka...", "Loading...") : t(...operationsMessages.refresh)}</button>
        <button className="button button--ghost operations-export operations-export--json" type="button" onClick={() => downloadFile(JSON.stringify(filteredOperations, null, 2), "operations.json", "application/json")}>{t(...operationsMessages.exportJson)}</button>
        <button className="button button--ghost operations-export operations-export--csv" type="button" onClick={() => downloadFile(operationsToCsv(filteredOperations), "operations.csv", "text/csv;charset=utf-8")}>{t(...operationsMessages.exportCsv)}</button>
      </div>
    </section>
    {error && <div className="notice notice--error" role="alert">{error}</div>}
    <section className="operations-log panel" aria-label={t("Firaketana asa", "Operation records")}>
      <ClassicTitleBar title={t("Firaketana asa", "Operation records")} />
      {filteredOperations.map((operation) => <article className="operation-record" key={operation.id}>
        <span aria-hidden="true" className={`operation-record__outcome operation-record__outcome--${operation.outcome}`} />
        <div className="operation-record__summary">
          <strong>{operation.action} · {operation.resource}</strong>
          <small>{operation.service} / {operation.username}</small>
        </div>
        <code>{Object.entries(operation.target).map(([key, value]) => `${key}=${String(value)}`).join(" · ") || operation.changed_fields.join(", ") || "-"}</code>
        <time dateTime={operation.accepted_at}>{formatDateTime(locale, new Date(operation.accepted_at))}</time>
        <b>{outcomeLabels[operation.outcome]}</b>
        {operation.error_summary && <p className="operation-record__error-summary">{operation.error_summary}</p>}
        <details className="operation-record__details">
          <summary aria-label={t(`Antsipirian'ny ${operation.action} ${operation.resource}`, `Details for ${operation.action} ${operation.resource}`)}>{t(...operationsMessages.details)}</summary>
          <dl className="operation-record__detail-list">
            <div className="operation-record__detail operation-record__detail--target">
              <dt>{t(...operationsMessages.targetJson)}</dt>
              <dd><pre>{JSON.stringify(operation.target, null, 2)}</pre></dd>
            </div>
            <div className="operation-record__detail operation-record__detail--fields">
              <dt>{t(...operationsMessages.changedFields)}</dt>
              <dd>{operation.changed_fields.join(", ") || t(...operationsMessages.none)}</dd>
            </div>
            <div className="operation-record__detail operation-record__detail--accepted">
              <dt>{t(...operationsMessages.accepted)}</dt>
              <dd><time dateTime={operation.accepted_at}>{formatDateTime(locale, new Date(operation.accepted_at))}</time></dd>
            </div>
            <div className="operation-record__detail operation-record__detail--completed">
              <dt>{t(...operationsMessages.completed)}</dt>
              <dd>{operation.completed_at ? <time dateTime={operation.completed_at}>{formatDateTime(locale, new Date(operation.completed_at))}</time> : t(...operationsMessages.notCompleted)}</dd>
            </div>
            <div className="operation-record__detail operation-record__detail--error">
              <dt>{t(...operationsMessages.error)}</dt>
              <dd>{operation.error_summary || t(...operationsMessages.none)}</dd>
            </div>
          </dl>
        </details>
      </article>)}
      {!loading && !operations.length && <div className="services-state">{t("Tsy mbola misy asa voarakitra.", "No operations have been recorded yet.")}</div>}
      {!loading && operations.length > 0 && !filteredOperations.length && <div className="services-state">{t(...operationsMessages.noSearchMatches)}</div>}
      {loading && !operations.length && <div className="services-state"><span className="spinner" />{t("Maka ny audit...", "Loading audit...")}</div>}
      {nextBefore !== null && <footer><button className="button button--ghost" disabled={loading} type="button" onClick={() => void loadMore()}>{loading ? t("Maka...", "Loading...") : t("Hampiseho taloha", "Load older")}</button></footer>}
    </section>
  </div>;
}
