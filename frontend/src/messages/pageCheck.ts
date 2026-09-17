import type { MessageCatalog } from "./types";

export const pageCheckMessages = {
  all: ["Rehetra", "All"],
  confirmCheck: ["Hamarina ireo pejy ireo ve? Mety hamorona fanitsiana hapetraka ao amin'ny filaharana havoaka ny fanamarinana.", "Check these pages? Checks may create fixes that are queued for publication."],
  filterByTitleOrId: ["Sivana amin'ny lohateny na ID-n'ny asa", "Filter by title or job ID"],
  noFilterMatches: ["Tsy misy asa mifanaraka amin'ny sivana.", "No jobs match the filters."],
  reviewEventId: ["ID-n'ny hetsika hojerena", "Review event ID"],
  reviewHandoff: ["Fandefasana hojerena", "Review handoff"],
  reviewHandoffError: ["Hadisoana tamin'ny fandefasana hojerena", "Review handoff error"],
  retryingAutomatically: ["Hamerina ho azy.", "Retrying automatically."],
  status: ["Sata", "Status"],
  titleOrJobId: ["Lohateny na ID-n'ny asa", "Title or job ID"],
  unknown: ["Tsy fantatra", "Unknown"],
} as const satisfies MessageCatalog;

export const reviewQueueStateMessages = {
  not_needed: ["Tsy ilaina", "Not needed"],
  disabled: ["Tsy mandeha", "Disabled"],
  invalid: ["Tsy manan-kery", "Invalid"],
  pending: ["Miandry", "Pending"],
  publishing: ["Alefa", "Sending"],
  queued: ["Ao anaty filaharana", "Queued"],
  failed: ["Tsy nahomby", "Failed"],
} as const satisfies MessageCatalog;
