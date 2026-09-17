import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from "react";

import { useI18n } from "../i18n";
import { relationMessages } from "../messages/relation";
import type { FieldDefinition, RelationDefinition, Row } from "../types";
import { ClassicTitleBar } from "./ClassicTitleBar";

interface RecordFormProps {
  relation: RelationDefinition;
  relationLabel: string;
  row: Row | null;
  busy: boolean;
  onCancel: () => void;
  onSubmit: (row: Row) => void;
  onDirtyChange?: (dirty: boolean) => void;
}

function initialValue(field: FieldDefinition, row: Row | null): string {
  const value = row?.[field.name];
  if (value === null || value === undefined) return "";
  if (field.kind === "datetime") return String(value).replace(" ", "T").slice(0, 16);
  if (field.kind === "json" || typeof value === "object") return JSON.stringify(value, null, 2);
  return String(value);
}

function parseValue(field: FieldDefinition, value: string) {
  if (!value && !field.required) return null;
  if (field.kind === "number") return Number(value);
  if (field.kind === "json") return JSON.parse(value);
  return value;
}

export function RecordForm({ relation, relationLabel, row, busy, onCancel, onSubmit, onDirtyChange }: RecordFormProps) {
  const { t } = useI18n();
  const editableFields = relation.fields?.filter((field) => !field.readOnly) ?? [];
  const [values, setValues] = useState<Record<string, string>>(() =>
    Object.fromEntries(editableFields.map((field) => [field.name, initialValue(field, row)])),
  );
  const [initialValues] = useState(() => JSON.stringify(values));
  const [error, setError] = useState("");
  const dialogRef = useRef<HTMLElement>(null);
  const optionLabels: Record<string, string> = {
    PENDING: t("Miandry", "Pending"),
    PROCESSING: t("Karakaraina", "Processing"),
    DONE: t("Vita", "Done"),
    FAILED: t("Tsy nahomby", "Failed"),
  };
  const dirty = JSON.stringify(values) !== initialValues;

  function cancel(): void {
    if (dirty && !window.confirm(t(...relationMessages.discardUnsavedChanges))) return;
    onCancel();
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    try {
      setError("");
      onSubmit(Object.fromEntries(editableFields.map((field) => [field.name, parseValue(field, values[field.name] ?? "")])));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("Tsy voavaky ny rakitra.", "Unable to parse the record."));
    }
  }

  useEffect(() => {
    const previousFocus = document.activeElement as HTMLElement | null;
    const firstControl = dialogRef.current?.querySelector<HTMLElement>("input, textarea, select");
    firstControl?.focus();
    return () => previousFocus?.focus();
  }, []);

  useEffect(() => {
    if (!dirty) return;
    function warnBeforeUnload(event: BeforeUnloadEvent) {
      event.preventDefault();
    }
    window.addEventListener("beforeunload", warnBeforeUnload);
    return () => window.removeEventListener("beforeunload", warnBeforeUnload);
  }, [dirty]);

  useEffect(() => {
    onDirtyChange?.(dirty);
    return () => onDirtyChange?.(false);
  }, [dirty, onDirtyChange]);

  function handleKeyDown(event: KeyboardEvent<HTMLElement>) {
    if (event.key === "Escape" && !busy) {
      event.preventDefault();
      cancel();
      return;
    }
    if (event.key !== "Tab") return;
    const controls = [...(dialogRef.current?.querySelectorAll<HTMLElement>("button:not(:disabled), input:not(:disabled), textarea:not(:disabled), select:not(:disabled), [href], [tabindex]:not([tabindex='-1'])") ?? [])];
    if (!controls.length) return;
    const first = controls[0];
    const last = controls[controls.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  }

  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={(event) => event.target === event.currentTarget && cancel()}>
      <section className="record-modal" role="dialog" aria-modal="true" aria-labelledby="record-form-title" ref={dialogRef} onKeyDown={handleKeyDown}>
        <ClassicTitleBar title={row ? t("Hanova rakitra", "Edit record") : t("Hamorona rakitra", "Create record")} />
        <div className="record-modal__header">
          <div>
            <p className="eyebrow">{row ? t("Hanova rakitra", "Edit record") : t("Hamorona rakitra", "Create record")}</p>
            <h2 id="record-form-title">{relationLabel}</h2>
          </div>
          <button className="icon-button" type="button" aria-label={t("Akatona", "Close")} onClick={cancel}>×</button>
        </div>
        <form onSubmit={submit}>
          <div className="form-grid">
            {editableFields.map((field) => (
              <label className={field.kind === "textarea" || field.kind === "json" ? "field field--wide" : "field"} key={field.name}>
                <span>{field.label ?? field.name.replaceAll("_", " ")}{field.required && <b> *</b>}</span>
                {field.kind === "textarea" || field.kind === "json" ? (
                  <textarea
                    rows={field.kind === "json" ? 8 : 4}
                    required={field.required}
                    value={values[field.name] ?? ""}
                    placeholder={field.placeholder}
                    onChange={(event) => setValues({ ...values, [field.name]: event.target.value })}
                  />
                ) : field.kind === "select" ? (
                  <select required={field.required} value={values[field.name] ?? ""} onChange={(event) => setValues({ ...values, [field.name]: event.target.value })}>
                    {!field.required && <option value="">{t("Tsy misy sanda", "No value")}</option>}
                    {field.options?.map((option) => <option key={option} value={option}>{optionLabels[option] ?? option}</option>)}
                  </select>
                ) : (
                  <input
                    type={field.kind === "number" ? "number" : field.kind === "datetime" ? "datetime-local" : field.kind === "date" ? "date" : "text"}
                    required={field.required}
                    value={values[field.name] ?? ""}
                    placeholder={field.placeholder}
                    onChange={(event) => setValues({ ...values, [field.name]: event.target.value })}
                  />
                )}
              </label>
            ))}
          </div>
          {error && <div className="notice notice--error" role="alert">{error}</div>}
          <div className="record-modal__actions">
            <button className="button button--ghost" type="button" onClick={cancel}>{t("Hanafoana", "Cancel")}</button>
            <button className="button button--primary" type="submit" disabled={busy}>{busy ? t("Mitahiry...", "Saving...") : row ? t("Hitahiry ny fanovana", "Save changes") : t("Hamorona rakitra", "Create record")}</button>
          </div>
        </form>
      </section>
    </div>
  );
}
