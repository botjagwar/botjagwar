import { beforeEach, describe, expect, it } from "vitest";

import { clearConfigOverride, defaultConfig, joinAddress, normaliseConfig, saveConfig } from "./config";

describe("Atlas runtime configuration", () => {
  beforeEach(() => window.localStorage.clear());

  it("normalises and deduplicates service addresses", () => {
    const config = normaliseConfig({
      postgrestAddresses: ["http://db:8100/", "http://db:8100", ""],
      dictionaryServiceAddresses: [" /api/dictionary/ "],
      entryTranslatorAddresses: [],
    });

    expect(config.postgrestAddresses).toEqual(["http://db:8100"]);
    expect(config.dictionaryServiceAddresses).toEqual(["/api/dictionary"]);
    expect(config.entryTranslatorAddresses).toEqual(defaultConfig.entryTranslatorAddresses);
  });

  it("rejects cross-origin addresses when loading from browser storage", () => {
    const config = normaliseConfig(
      {
        postgrestAddresses: ["http://db:8100/", "http://db:8100", ""],
        dictionaryServiceAddresses: [" /api/dictionary/ "],
        entryTranslatorAddresses: [],
      },
      defaultConfig,
      true,
    );

    expect(config.postgrestAddresses).toEqual(defaultConfig.postgrestAddresses);
    expect(config.dictionaryServiceAddresses).toEqual(["/api/dictionary"]);
  });

  it("rejects protocol-relative and ambiguous service addresses", () => {
    const config = normaliseConfig(
      {
        postgrestAddresses: ["//evil.example/database", "///evil.example/database"],
        dictionaryServiceAddresses: ["api/dictionary", "/api/dictionary?token=secret"],
        entryTranslatorAddresses: ["/api/translator#unexpected"],
      },
      defaultConfig,
      true,
    );

    expect(config).toEqual(defaultConfig);
  });

  it("accepts same-origin absolute service addresses", () => {
    const address = `${window.location.origin}/api/database`;
    const config = normaliseConfig({ postgrestAddresses: [address] }, defaultConfig, true);

    expect(config.postgrestAddresses).toEqual([address]);
  });

  it("stores and clears browser overrides", () => {
    const config = saveConfig({ ...defaultConfig, databaseAddress: "database.internal/botjagwar" });
    expect(config.databaseAddress).toBe("database.internal/botjagwar");
    expect(window.localStorage.length).toBe(1);

    clearConfigOverride();
    expect(window.localStorage.length).toBe(0);
  });

  it("removes credentials from database URI labels", () => {
    const config = normaliseConfig({ databaseAddress: "postgresql://user:secret@db.internal:5432/botjagwar" });
    expect(config.databaseAddress).toBe("db.internal:5432/botjagwar");
  });

  it("joins relative and absolute service roots", () => {
    expect(joinAddress("/api/database/", "/word")).toBe("/api/database/word");
    expect(joinAddress("http://localhost:8100", "word")).toBe("http://localhost:8100/word");
  });
});
