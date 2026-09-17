import type { MessageCatalog } from "./types";

export const operationsMessages = {
  accepted: ["Nekena", "Accepted"],
  auditTools: ["Fitaovan'ny audit", "Audit tools"],
  changedFields: ["Saha niova", "Changed fields"],
  completed: ["Vita", "Completed"],
  details: ["Antsipiriany", "Details"],
  error: ["Hadisoana", "Error"],
  exportCsv: ["Avoahy CSV", "Export CSV"],
  exportJson: ["Avoahy JSON", "Export JSON"],
  noSearchMatches: ["Tsy misy asa mifanaraka amin'ny fikarohana.", "No operations match the search."],
  none: ["Tsy misy", "None"],
  notCompleted: ["Tsy mbola vita", "Not completed"],
  refresh: ["Havaozy", "Refresh"],
  search: ["Karohy", "Search"],
  searchPlaceholder: ["Asa, loharano, tolotra, mpampiasa, tanjona, na hadisoana", "Action, resource, service, user, target, or error"],
  serverOwned: ["An'ny lohamilina / tsy azo ovaina", "Server-owned / append-only"],
  targetJson: ["Tanjona JSON", "Target JSON"],
} as const satisfies MessageCatalog;
