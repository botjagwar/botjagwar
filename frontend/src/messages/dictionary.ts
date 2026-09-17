import type { MessageCatalog } from "./types";

export const dictionaryMessages = {
  definitionImpact: ["Fiantraikan'ny famaritana", "Definition impact"],
  definitionImpactHelp: ["Aseho eto ireo teny rehetra mizara ireo famaritana ireo alohan'ny hanovana na hamafana azy.", "Review all entries sharing these definitions before editing or deleting them."],
  definitionImpactLoadError: ["Tsy azo ny fiantraikan'ny famaritana.", "Unable to load definition impact."],
  noOtherEntries: ["Tsy misy teny hafa hita.", "No other entries found."],
  discardUnsavedChanges: ["Harianao ve ny fanovana tsy voatahiry?", "Discard unsaved changes?"],
} as const satisfies MessageCatalog;
