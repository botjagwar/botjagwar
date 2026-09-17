import { Fragment, useEffect, useEffectEvent, useState } from "react";

import { createRow, deleteRow, listRows, updateRow } from "../api";
import { useI18n } from "../i18n";
import { relationMessages } from "../messages/relation";
import type { JsonValue, RelationDefinition, Row } from "../types";
import { RecordForm } from "./RecordForm";

interface RelationBrowserProps {
  relation: RelationDefinition;
  onMessage: (message: string, tone?: "success" | "error") => void;
  onOpenLexicon: (word: string) => void;
  onDirtyChange?: (dirty: boolean) => void;
}

function displayValue(value: JsonValue | undefined, field?: string, statusLabels: Record<string, string> = {}): string {
  if (value === null || value === undefined) return "-";
  if (field === "status" && typeof value === "string") {
    return statusLabels[value] ?? value;
  }
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function initialUrlState(relation: RelationDefinition): { page: number; pageSize: number; search: string; order: string } {
  const [route, query = ""] = window.location.hash.slice(1).split("?", 2);
  const defaults = { page: 0, pageSize: 25, search: "", order: relation.defaultOrder ?? "" };
  if (route !== `relation:${relation.name}`) return defaults;

  const params = new URLSearchParams(query);
  const page = Number(params.get("page"));
  const pageSize = Number(params.get("pageSize"));
  const requestedOrder = params.get("order");
  const [orderColumn, orderDirection] = requestedOrder?.split(".") ?? [];
  const configuredFields = new Set(relation.fields?.map((field) => field.name) ?? []);
  const orderIsValid = Boolean(orderColumn && ["asc", "desc"].includes(orderDirection) && (configuredFields.size === 0 || configuredFields.has(orderColumn)));
  return {
    page: Number.isInteger(page) && page >= 0 ? page : defaults.page,
    pageSize: [10, 25, 50, 100].includes(pageSize) ? pageSize : defaults.pageSize,
    search: params.get("search") ?? defaults.search,
    order: requestedOrder === "" || orderIsValid ? requestedOrder ?? "" : defaults.order,
  };
}

function downloadFile(contents: string, filename: string, type: string): void {
  const url = URL.createObjectURL(new Blob([contents], { type }));
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

function rowsToCsv(rows: Row[], columns: string[]): string {
  const quote = (value: JsonValue | undefined) => {
    const text = value === null || value === undefined ? "" : typeof value === "object" ? JSON.stringify(value) : String(value);
    return `"${text.replaceAll('"', '""')}"`;
  };
  return [columns.map((column) => quote(column)), ...rows.map((row) => columns.map((column) => quote(row[column])))].map((values) => values.join(",")).join("\n");
}

export function RelationBrowser({ relation, onMessage, onOpenLexicon, onDirtyChange }: RelationBrowserProps) {
  const { t } = useI18n();
  const [urlState] = useState(() => initialUrlState(relation));
  const [rows, setRows] = useState<Row[]>([]);
  const [total, setTotal] = useState<number | null>(null);
  const [page, setPage] = useState(urlState.page);
  const [pageSize, setPageSize] = useState(urlState.pageSize);
  const [search, setSearch] = useState(urlState.search);
  const [debouncedSearch, setDebouncedSearch] = useState(urlState.search);
  const [order, setOrder] = useState(urlState.order);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [editing, setEditing] = useState<Row | null | undefined>(undefined);
  const [busy, setBusy] = useState(false);
  const [revision, setRevision] = useState(0);
  const [hiddenColumns, setHiddenColumns] = useState<Set<string>>(() => new Set());
  const [expandedRows, setExpandedRows] = useState<Set<number>>(() => new Set());
  const statusLabels: Record<string, string> = {
    PENDING: t("Miandry", "Pending"),
    PROCESSING: t("Karakaraina", "Processing"),
    DONE: t("Vita", "Done"),
    FAILED: t("Tsy nahomby", "Failed"),
  };
  const reportLoadError = useEffectEvent((caught: unknown) => {
    setError(caught instanceof Error ? caught.message : t("Tsy voaray ity singa ity.", "Unable to load this relation."));
  });

  useEffect(() => {
    if (search === debouncedSearch) return;
    const timeout = window.setTimeout(() => {
      setPage(0);
      setDebouncedSearch(search);
      setLoading(true);
    }, 1000);
    return () => window.clearTimeout(timeout);
  }, [search, debouncedSearch]);

  useEffect(() => {
    function syncUrl() {
      const [route] = window.location.hash.slice(1).split("?", 1);
      if (route !== `relation:${relation.name}`) return;
      const params = new URLSearchParams({
        search,
        page: String(page),
        pageSize: String(pageSize),
        order,
      });
      const nextHash = `#${route}?${params.toString()}`;
      if (window.location.hash !== nextHash) window.history.replaceState(window.history.state, "", nextHash);
    }

    syncUrl();
  }, [relation.name, search, page, pageSize, order]);

  useEffect(() => {
    function restoreUrlState() {
      const next = initialUrlState(relation);
      setPage(next.page);
      setPageSize(next.pageSize);
      setSearch(next.search);
      setDebouncedSearch(next.search);
      setOrder(next.order);
      setLoading(true);
    }
    window.addEventListener("popstate", restoreUrlState);
    window.addEventListener("hashchange", restoreUrlState);
    return () => {
      window.removeEventListener("popstate", restoreUrlState);
      window.removeEventListener("hashchange", restoreUrlState);
    };
  }, [relation]);

  useEffect(() => {
    const controller = new AbortController();
    listRows(relation, { page, pageSize, search: debouncedSearch, order }, controller.signal)
      .then((result) => {
        setError("");
        setRows(result.rows);
        setTotal(result.total);
        setExpandedRows(new Set());
      })
      .catch((caught: unknown) => {
        if (!controller.signal.aborted) reportLoadError(caught);
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [relation, page, pageSize, debouncedSearch, order, revision]);

  const configuredColumns = relation.fields?.filter((field) => !field.hiddenFromList).map((field) => field.name) ?? [];
  const columns = configuredColumns.length ? configuredColumns : [...new Set(rows.flatMap((row) => Object.keys(row)))];
  const visibleColumns = columns.filter((column) => !hiddenColumns.has(column));
  const canWrite = relation.kind === "table" && !relation.readOnly;
  const pageCount = total === null ? null : Math.max(1, Math.ceil(total / pageSize));

  function changeSort(column: string) {
    const [currentColumn, direction] = order.split(".");
    setOrder(`${column}.${currentColumn === column && direction === "asc" ? "desc" : "asc"}`);
    setPage(0);
    setLoading(true);
  }

  function toggleColumn(column: string) {
    setHiddenColumns((current) => {
      const next = new Set(current);
      if (next.has(column)) next.delete(column);
      else if (visibleColumns.length > 1) next.add(column);
      return next;
    });
  }

  function toggleDetails(index: number) {
    setExpandedRows((current) => {
      const next = new Set(current);
      if (next.has(index)) next.delete(index);
      else next.add(index);
      return next;
    });
  }

  async function save(row: Row) {
    setBusy(true);
    try {
      if (editing) {
        await updateRow(relation, editing, row);
        onMessage(t("Voahavaozina ny rakitra.", "Record updated."));
      } else {
        await createRow(relation, row);
        onMessage(t("Voaforona ny rakitra.", "Record created."));
      }
      setEditing(undefined);
      setRevision((value) => value + 1);
    } catch (caught) {
      onMessage(caught instanceof Error ? caught.message : t("Tsy voatahiry ny rakitra.", "Unable to save the record."), "error");
    } finally {
      setBusy(false);
    }
  }

  async function remove(row: Row) {
    if (!window.confirm(t(`Hofafana ao amin'ny ${relation.label} ve ity rakitra ity? Tsy azo averina io asa io.`, `Delete this record from ${relation.label}? This action cannot be undone.`))) return;
    try {
      await deleteRow(relation, row);
      onMessage(t("Voafafa ny rakitra.", "Record deleted."));
      setRevision((value) => value + 1);
    } catch (caught) {
      onMessage(caught instanceof Error ? caught.message : t("Tsy voafafa ny rakitra.", "Unable to delete the record."), "error");
    }
  }

  return (
    <section className="relation-panel">
      <div className="relation-toolbar">
        <div className="relation-toolbar__summary">
          <span className={`relation-kind relation-kind--${relation.kind}`}>{relation.kind === "table" ? t("Tabilao", "Table") : relation.kind === "view" ? t("Fijery", "View") : t("Fijery voatahirina", "Materialized view")}</span>
          <p>{relation.description}</p>
        </div>
        <div className="relation-toolbar__actions">
          {relation.searchFields?.length ? (
            <label className="search-control">
              <span aria-hidden="true">⌕</span>
              <input data-atlas-search value={search} onChange={(event) => setSearch(event.target.value)} placeholder={t(`Karohy ao amin'ny ${relation.searchFields.join(", ")}`, `Search in ${relation.searchFields.join(", ")}`)} />
            </label>
          ) : null}
          <details>
            <summary>{t(...relationMessages.columns)}</summary>
            <fieldset aria-label={t(...relationMessages.visibleColumns)}>
              {columns.map((column) => (
                <label key={column}>
                  <input type="checkbox" checked={!hiddenColumns.has(column)} disabled={!hiddenColumns.has(column) && visibleColumns.length === 1} onChange={() => toggleColumn(column)} />
                  {column.replaceAll("_", " ")}
                </label>
              ))}
            </fieldset>
          </details>
          <button type="button" disabled={rows.length === 0} onClick={() => downloadFile(JSON.stringify(rows, null, 2), `${relation.name}-page-${page + 1}.json`, "application/json")}>{t("JSON", "JSON")}</button>
          <button type="button" disabled={rows.length === 0} onClick={() => downloadFile(rowsToCsv(rows, columns), `${relation.name}-page-${page + 1}.csv`, "text/csv;charset=utf-8")}>{t("CSV", "CSV")}</button>
          {canWrite && <button className="button button--primary" type="button" onClick={() => setEditing(null)}>{t("Rakitra vaovao", "New record")}</button>}
        </div>
      </div>

      {error && <div className="notice notice--error">{error}</div>}
      <div className="data-frame">
        <table className="data-table">
          <thead>
            <tr>
              {visibleColumns.map((column) => (
                <th key={column}>
                  <button type="button" onClick={() => changeSort(column)}>{column.replaceAll("_", " ")}{order.startsWith(`${column}.`) ? <span>{order.endsWith("asc") ? " ↑" : " ↓"}</span> : null}</button>
                </th>
              ))}
              <th className="data-table__actions">{t(...relationMessages.actions)}</th>
            </tr>
          </thead>
          <tbody>
            {!loading && rows.map((row, index) => {
              const detailsId = `${relation.name}-row-${index}-details`;
              return (
                <Fragment key={`${relation.name}-${index}-${relation.identity?.map((field) => displayValue(row[field])).join("-") ?? index}`}>
                  <tr>
                    {visibleColumns.map((column) => <td key={column} title={displayValue(row[column], column, statusLabels)}><span>{displayValue(row[column], column, statusLabels)}</span></td>)}
                    <td className="data-table__actions">
                      <button type="button" aria-label={expandedRows.has(index) ? t(`Afeno ny antsipirian'ny andalana ${index + 1}`, `Hide details for row ${index + 1}`) : t(`Asehoy ny antsipirian'ny andalana ${index + 1}`, `Show details for row ${index + 1}`)} aria-expanded={expandedRows.has(index)} aria-controls={detailsId} onClick={() => toggleDetails(index)}>{expandedRows.has(index) ? t(...relationMessages.hideDetails) : t(...relationMessages.showDetails)}</button>
                      {typeof row.word === "string" && <button type="button" onClick={() => onOpenLexicon(row.word as string)}>{t("Atlas", "Atlas")}</button>}
                      {canWrite && <button type="button" onClick={() => setEditing(row)}>{t("Hanova", "Edit")}</button>}
                      {canWrite && <button className="danger-link" type="button" onClick={() => void remove(row)}>{t("Hamafa", "Delete")}</button>}
                    </td>
                  </tr>
                  {expandedRows.has(index) && (
                    <tr className="data-table__detail-row" id={detailsId}>
                      <td colSpan={visibleColumns.length + 1}>
                        <strong>{t(...relationMessages.fullRowJson)}</strong>
                        <pre>{JSON.stringify(row, null, 2)}</pre>
                      </td>
                    </tr>
                  )}
                </Fragment>
              );
            })}
          </tbody>
        </table>
        {loading && <div className="table-state"><span className="spinner" />{t(`Maka ny ${relation.label.toLowerCase()}...`, `Loading ${relation.label.toLowerCase()}...`)}</div>}
        {!loading && !error && rows.length === 0 && <div className="table-state">{t("Tsy misy rakitra mifanaraka amin'ity view ity.", "No records match this view.")}</div>}
      </div>

      <footer className="pagination">
        <span>{total === null ? t(`Andalana ${rows.length} eto amin'ity pejy ity`, `${rows.length} rows on this page`) : t(`Rakitra ${total.toLocaleString()} rehetra`, `${total.toLocaleString()} records total`)}</span>
        <label>{t("Andalana", "Rows")} <select value={pageSize} onChange={(event) => { setPageSize(Number(event.target.value)); setPage(0); setLoading(true); }}><option>10</option><option>25</option><option>50</option><option>100</option></select></label>
        <div>
          <button type="button" disabled={page === 0} onClick={() => { setPage((value) => value - 1); setLoading(true); }}>{t("Teo aloha", "Previous")}</button>
          <span>{pageCount ? t(`Pejy ${page + 1} amin'ny ${pageCount}`, `Page ${page + 1} of ${pageCount}`) : t(`Pejy ${page + 1}`, `Page ${page + 1}`)}</span>
          <button type="button" disabled={rows.length < pageSize || (pageCount !== null && page + 1 >= pageCount)} onClick={() => { setPage((value) => value + 1); setLoading(true); }}>{t("Manaraka", "Next")}</button>
        </div>
      </footer>

      {editing !== undefined && <RecordForm key={`${relation.name}-${editing ? "edit" : "new"}`} relation={relation} relationLabel={relation.label} row={editing} busy={busy} onCancel={() => setEditing(undefined)} onSubmit={(row) => void save(row)} onDirtyChange={onDirtyChange} />}
    </section>
  );
}
