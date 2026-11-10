// One card per company, merging the three signals the pipeline publishes:
// the company's own Form D (on or off the talent network) and investor SPVs.
import { type BoardCompany, type Tier, boardBySlug, collection, filings } from "@/lib/data";

export interface Raise {
  amount: number | null;
  kind: "sold" | "offering" | "unknown";
  firstSale: string;
  days: number;
  filed: string; // latest filing for this offering (original or amendment)
  filingUrl: string;
  issuer: string;
  amendments: number;
  partner: string | null;
  score: number | null; // only for companies on the talent network
}

export interface Spv {
  count: number;
  sold: number;
  latest: string;
  days: number;
  vehicles: { name: string; file_date: string; amount_sold: number | null; filing_url: string }[];
}

export interface Item {
  slug: string;
  name: string;
  tier: Tier;
  cohort: string | null;
  logo: string | null;
  blurb: string | null;
  location: string | null;
  stage: string | null;
  url: string | null;
  onNetwork: boolean;
  openRoles: number | null;
  rolesSince: number | null; // since the raise, or since the first SPV
  posted30d: number | null; // roles posted in the last 30 days, from the talent network's facets
  raise: Raise | null;
  spv: Spv | null;
  days: number; // age of the newest money signal (first sale or SPV filing)
  filed: string; // newest SEC filing date across both signals: the feed's sort key
  filedDays: number; // days from that filing to the run date
  filedKind: "Form D" | "SPV";
  rank: number | null; // rank in the collection endpoint, if listed there
  board: BoardCompany | null; // hiring mix and comp coverage, if on the talent network
}

const RUN_DATE = filings.meta.run_date;

function daysBefore(iso: string, until: string = RUN_DATE): number {
  const ms = Date.parse(`${until}T00:00:00Z`) - Date.parse(`${iso}T00:00:00Z`);
  return Math.max(0, Math.round(ms / 86_400_000));
}

function withFiled(base: Omit<Item, "filed" | "filedDays" | "filedKind" | "board">): Item {
  const raiseFiled = base.raise?.filed ?? "";
  const spvFiled = base.spv?.latest ?? "";
  const spvNewer = spvFiled > raiseFiled;
  const filed = spvNewer ? spvFiled : raiseFiled;
  return {
    ...base,
    filed,
    filedDays: daysBefore(filed),
    filedKind: spvNewer ? "SPV" : "Form D",
    board: base.onNetwork ? (boardBySlug.get(base.slug) ?? null) : null,
  };
}

export function buildItems(): Item[] {
  const items = new Map<string, Omit<Item, "filed" | "filedDays" | "filedKind" | "board">>();
  const members = new Map(collection.collection.members.map((m) => [m.slug ?? m.name, m]));

  for (const f of Object.values(filings.filings)) {
    const m = members.get(f.slug);
    items.set(f.slug, {
      slug: f.slug,
      name: f.name,
      tier: f.tier,
      cohort: m?.cohort ?? null,
      logo: m?.logo ?? null,
      blurb: m?.blurb ?? null,
      location: m?.location ?? null,
      stage: m?.stage ?? null,
      url: m?.url ?? null,
      onNetwork: true,
      openRoles: m?.open_roles ?? null,
      rolesSince: f.roles_since_first_sale,
      posted30d: f.roles_posted_30d ?? null,
      raise: {
        amount: f.amount,
        kind: f.amount_kind,
        firstSale: f.date_of_first_sale,
        days: f.days_since_first_sale,
        filed: f.latest_file_date,
        filingUrl: f.filing_url,
        issuer: f.issuer_name,
        amendments: f.amendments,
        partner: f.a16z_person,
        score: f.score,
      },
      spv: null,
      days: f.days_since_first_sale,
      rank: f.rank,
    });
  }

  for (const f of Object.values(filings.off_network ?? {})) {
    items.set(f.slug, {
      slug: f.slug,
      name: f.name,
      tier: f.tier,
      cohort: f.cohort,
      logo: f.logo,
      blurb: f.blurb,
      location: f.location,
      stage: null,
      url: f.website ?? f.url,
      onNetwork: false,
      openRoles: null,
      rolesSince: null,
      posted30d: null,
      raise: {
        amount: f.amount,
        kind: f.amount_kind,
        firstSale: f.date_of_first_sale,
        days: f.days_since_first_sale,
        filed: f.latest_file_date,
        filingUrl: f.filing_url,
        issuer: f.issuer_name,
        amendments: f.amendments,
        partner: f.a16z_person,
        score: null,
      },
      spv: null,
      days: f.days_since_first_sale,
      rank: null,
    });
  }

  for (const s of Object.values(filings.spv ?? {})) {
    const spv: Spv = {
      count: s.spvs,
      sold: s.spv_amount_sold,
      latest: s.latest_spv_file_date,
      days: s.days_since_latest_spv,
      vehicles: s.vehicles,
    };
    const existing = items.get(s.slug);
    if (existing) {
      existing.spv = spv;
      existing.days = Math.min(existing.days, spv.days);
      continue;
    }
    items.set(s.slug, {
      slug: s.slug,
      name: s.name,
      tier: s.tier,
      cohort: s.cohort,
      logo: s.logo,
      blurb: s.blurb,
      location: s.location,
      stage: s.stage,
      url: s.url,
      onNetwork: s.on_network,
      openRoles: s.open_roles,
      rolesSince: s.roles_since_first_spv,
      posted30d: s.roles_posted_30d ?? null,
      raise: null,
      spv,
      days: spv.days,
      rank: null,
    });
  }

  // Newest filing first: what showed up on EDGAR most recently leads the page.
  return Array.from(items.values(), withFiled).sort(
    (a, b) => b.filed.localeCompare(a.filed) || a.name.localeCompare(b.name),
  );
}
