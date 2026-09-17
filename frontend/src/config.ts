export interface AtlasConfig {
  databaseAddress: string;
  postgrestAddresses: string[];
  dictionaryServiceAddresses: string[];
  entryTranslatorAddresses: string[];
}

const STORAGE_KEY = "botjagwar-atlas-config";

export const defaultConfig: AtlasConfig = {
  databaseAddress: "",
  postgrestAddresses: [import.meta.env.VITE_POSTGREST_URL ?? "/api/database"],
  dictionaryServiceAddresses: [import.meta.env.VITE_DICTIONARY_URL ?? "/api/dictionary"],
  entryTranslatorAddresses: [import.meta.env.VITE_TRANSLATOR_URL ?? "/api/translator"],
};

function isSameOriginOrRelative(address: string): boolean {
  const isRelativePath = address.startsWith("/") && !address.startsWith("//");
  const isAbsoluteUrl = /^[a-z][a-z\d+.-]*:\/\//i.test(address);
  if (!isRelativePath && !isAbsoluteUrl) return false;
  try {
    const parsed = new URL(address, window.location.origin);
    return (
      parsed.origin === window.location.origin
      && !parsed.username
      && !parsed.password
      && !parsed.search
      && !parsed.hash
    );
  } catch {
    return false;
  }
}

function cleanAddresses(value: unknown, fallback: string[], requireSameOrigin: boolean): string[] {
  if (!Array.isArray(value)) return requireSameOrigin ? fallback.filter(isSameOriginOrRelative) : fallback;
  let addresses = [...new Set(value.filter((item): item is string => typeof item === "string").map((item) => item.trim().replace(/\/$/, "")).filter(Boolean))];
  if (requireSameOrigin) {
    const safeAddresses = addresses.filter(isSameOriginOrRelative);
    addresses = safeAddresses.length ? safeAddresses : fallback.filter(isSameOriginOrRelative);
  }
  return addresses.length ? addresses : fallback;
}

function cleanDatabaseAddress(value: unknown, fallback: string): string {
  if (typeof value !== "string" || !value.trim()) return fallback;
  const address = value.trim();
  if (!address.includes("://")) return address;
  try {
    const parsed = new URL(address);
    const port = parsed.port ? `:${parsed.port}` : "";
    return `${parsed.hostname}${port}${parsed.pathname}`.replace(/\/$/, "");
  } catch {
    return fallback;
  }
}

export function normaliseConfig(
  value: Partial<AtlasConfig> | null | undefined,
  fallback: AtlasConfig = defaultConfig,
  requireSameOrigin = false,
): AtlasConfig {
  return {
    databaseAddress: cleanDatabaseAddress(value?.databaseAddress, fallback.databaseAddress),
    postgrestAddresses: cleanAddresses(value?.postgrestAddresses, fallback.postgrestAddresses, requireSameOrigin),
    dictionaryServiceAddresses: cleanAddresses(value?.dictionaryServiceAddresses, fallback.dictionaryServiceAddresses, requireSameOrigin),
    entryTranslatorAddresses: cleanAddresses(value?.entryTranslatorAddresses, fallback.entryTranslatorAddresses, requireSameOrigin),
  };
}

export async function loadConfig(): Promise<AtlasConfig> {
  let deployed = defaultConfig;
  try {
    const response = await fetch(`/config.json?cache=${Date.now()}`, { cache: "no-store" });
    if (response.ok) deployed = normaliseConfig(await response.json(), defaultConfig);
  } catch {
    // Relative defaults keep development and partially configured deployments usable.
  }

  try {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    return stored ? normaliseConfig(JSON.parse(stored) as Partial<AtlasConfig>, deployed, true) : deployed;
  } catch {
    return deployed;
  }
}

export function saveConfig(config: AtlasConfig): AtlasConfig {
  const normalised = normaliseConfig(config, defaultConfig, true);
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(normalised));
  return normalised;
}

export function clearConfigOverride(): void {
  window.localStorage.removeItem(STORAGE_KEY);
}

export function joinAddress(address: string, path: string): string {
  return `${address.replace(/\/$/, "")}/${path.replace(/^\//, "")}`;
}
