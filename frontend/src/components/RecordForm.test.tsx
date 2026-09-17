import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { I18nProvider } from "../i18n";
import type { RelationDefinition } from "../types";
import { RecordForm } from "./RecordForm";

const relation: RelationDefinition = {
  name: "word",
  label: "Teny",
  group: "Rakibolana",
  kind: "table",
  description: "Words",
  fields: [{ name: "word", required: true }],
};

afterEach(cleanup);

describe("RecordForm", () => {
  it("focuses the first control and closes with Escape", () => {
    const onCancel = vi.fn();
    render(<I18nProvider><RecordForm relation={relation} relationLabel="Teny" row={null} busy={false} onCancel={onCancel} onSubmit={vi.fn()} /></I18nProvider>);

    expect(screen.getByLabelText(/word/)).toHaveFocus();
    fireEvent.keyDown(screen.getByRole("dialog"), { key: "Escape" });
    expect(onCancel).toHaveBeenCalledOnce();
  });

  it("wraps keyboard focus within the dialog", () => {
    render(<I18nProvider><RecordForm relation={relation} relationLabel="Teny" row={null} busy={false} onCancel={vi.fn()} onSubmit={vi.fn()} /></I18nProvider>);
    const first = screen.getByRole("button", { name: "Akatona" });
    const last = screen.getByRole("button", { name: "Hamorona rakitra" });

    last.focus();
    fireEvent.keyDown(last, { key: "Tab" });
    expect(first).toHaveFocus();
    fireEvent.keyDown(first, { key: "Tab", shiftKey: true });
    expect(last).toHaveFocus();
  });

  it("confirms before discarding changed fields", () => {
    const onCancel = vi.fn();
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(false);
    render(<I18nProvider><RecordForm relation={relation} relationLabel="Teny" row={null} busy={false} onCancel={onCancel} onSubmit={vi.fn()} /></I18nProvider>);

    fireEvent.change(screen.getByLabelText(/word/), { target: { value: "house" } });
    fireEvent.click(screen.getByRole("button", { name: "Hanafoana" }));
    expect(confirm).toHaveBeenCalledWith("Harianao ve ny fanovana tsy voatahiry?");
    expect(onCancel).not.toHaveBeenCalled();

    confirm.mockReturnValue(true);
    fireEvent.click(screen.getByRole("button", { name: "Hanafoana" }));
    expect(onCancel).toHaveBeenCalledOnce();
  });
});
