import type { MessageCatalog } from "./types";

export const relationMessages = {
  actions: ["Asa", "Actions"],
  columns: ["Tsanganana", "Columns"],
  discardUnsavedChanges: ["Harianao ve ny fanovana tsy voatahiry?", "Discard unsaved changes?"],
  fullRowJson: ["JSON fenon'ny andalana", "Full row JSON"],
  hideDetails: ["Afeno ny antsipiriany", "Hide details"],
  showDetails: ["Asehoy ny antsipiriany", "Show details"],
  visibleColumns: ["Tsanganana hita", "Visible columns"],
} as const satisfies MessageCatalog;
