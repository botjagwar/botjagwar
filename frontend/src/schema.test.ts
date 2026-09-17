import { describe, expect, it } from "vitest";

import { relationByName, relations, tableRelations, viewRelations } from "./schema";

describe("database schema catalog", () => {
  it("contains every physical table", () => {
    expect(tableRelations.map((relation) => relation.name)).toEqual([
      "word",
      "definitions",
      "dictionary",
      "language",
      "additional_word_information",
      "mt_translated_definition",
      "nllb_translations",
      "template_translations",
      "translation_method",
      "new_associations",
      "events_definition_changed",
      "events_rel_definition_word_deleted",
      "events_malagasy_translation_created",
    ]);
  });

  it("defines stable identities for writable tables", () => {
    const writableTables = tableRelations.filter((relation) => !relation.readOnly);
    expect(writableTables.length).toBeGreaterThan(0);
    for (const relation of writableTables) {
      expect(relation.identity, relation.name).toBeTruthy();
      expect(relation.identity?.length, relation.name).toBeGreaterThan(0);
      expect(relation.fields?.length, relation.name).toBeGreaterThan(0);
    }
  });

  it("keeps views read-only and relation names unique", () => {
    expect(viewRelations.every((relation) => relation.readOnly)).toBe(true);
    expect(relationByName.size).toBe(relations.length);
  });
});
