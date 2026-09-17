import type { MessageCatalog } from "./types";

export const servicesMessages = {
  latestStatusUnavailable: ["Tsy azo ny sata farany.", "Latest status unavailable."],
  retryNow: ["Andramo indray", "Retry now"],
  retryingAutomatically: ["Haverina ho azy afaka 30 segondra.", "Retrying automatically in 30 seconds."],
} as const satisfies MessageCatalog;
