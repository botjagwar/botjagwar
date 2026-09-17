import type { MessageCatalog } from "./types";

export const jobCenterMessages = {
  active: ["mandeha", "active"],
  close: ["Akatona ny foiben'ny asa", "Close job center"],
  empty: ["Tsy misy asa hita amin'izao.", "No jobs are currently available."],
  eyebrow: ["Atlas / asa mivantana", "Atlas / live work"],
  heading: ["Foiben'ny asa", "Job center"],
  jobs: ["Asa", "Jobs"],
  loading: ["Maka ny asa...", "Loading jobs..."],
  open: ["Sokafy", "Open"],
  pageCheck: ["Mpanamarina", "Page checker"],
  refresh: ["Havaozy", "Refresh"],
  recentHelp: ["Araho eto ny fandikana sy fanamarinana pejy na aiza na aiza misy anao ao Atlas.", "Track translation and page-check work from anywhere in Atlas."],
  reviewFailed: ["Miandry famerenana", "Waiting to retry review"],
  reviewPending: ["Miandry fandefasana", "Review pending"],
  reviewPublishing: ["Alefa hojerena", "Sending for review"],
  retrying: ["Haverina ho azy ny fakana ny asa mandeha.", "Active jobs will retry automatically."],
  translator: ["Mpandika teny", "Translator"],
  unresolved: ["Karohina", "Resolving"],
} as const satisfies MessageCatalog;
