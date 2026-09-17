import { describe, expect, it } from "vitest";

import contract from "../../definition_linking_contract.json";
import { createDefinitionLinkIndex, linkDefinition } from "./definitionLinks";

describe("definition linking contract", () => {
  for (const example of contract) {
    it(example.name, () => {
      const index = createDefinitionLinkIndex(new Set(example.candidates));

      expect(linkDefinition(example.definition, example.currentWord, index)).toEqual(example.expected);
    });
  }
});
