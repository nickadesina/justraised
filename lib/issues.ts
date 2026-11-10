// The board-health checks, as plain functions over board.json so the sidebar
// count and the page always agree.
import { type BoardCompany, board } from "@/lib/data";

// A company is flagged for missing comp or stale postings only when it has
// enough roles for the pattern to mean something.
export const MIN_ROLES = 10;

export interface Repeat extends BoardCompany {
  repeats: number;
  share: number; // repeats / listings
}

export function boardIssues() {
  const cs = board.companies;
  const filter = cs.filter((c) => !c.filter_ok);
  const repeats: Repeat[] = cs
    .filter((c) => c.listings && c.distinct_titles !== null && c.listings - c.distinct_titles >= 5)
    .map((c) => {
      const repeats = c.listings! - c.distinct_titles!;
      return { ...c, repeats, share: repeats / c.listings! };
    })
    .filter((c) => c.share >= 0.2)
    .sort((a, b) => b.repeats - a.repeats);
  const noComp = cs
    .filter((c) => c.open_roles >= MIN_ROLES && c.comp_posted === 0)
    .sort((a, b) => b.open_roles - a.open_roles);
  const stale = cs
    .filter((c) => c.open_roles >= MIN_ROLES && c.posted_30d === 0)
    .sort((a, b) => b.open_roles - a.open_roles);
  const flagged = new Set([...filter, ...repeats, ...noComp, ...stale].map((c) => c.slug)).size;
  return { filter, repeats, noComp, stale, flagged };
}
