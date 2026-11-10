// One card per company, merging the three signals the pipeline publishes:
// the company's own Form D (on or off the talent network) and investor SPVs.
import { type Tier, collection, filings } from "@/lib/data";

export interface Raise {
  amount: number | null;
  kind: "sold" | "offering" | "unknown";
  firstSale: string;
  days: number;
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
  raise: Raise | null;
  spv: Spv | null;
  days: number; // age of the newest signal
  rank: number | null; // rank in the collection endpoint, if listed there
}

export function buildItems(): Item[] {
  const items = new Map<string, Item>();
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
      raise: {
        amount: f.amount,
        kind: f.amount_kind,
        firstSale: f.date_of_first_sale,
        days: f.days_since_first_sale,
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
      raise: {
        amount: f.amount,
        kind: f.amount_kind,
        firstSale: f.date_of_first_sale,
        days: f.days_since_first_sale,
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
      raise: null,
      spv,
      days: spv.days,
      rank: null,
    });
  }

  return Array.from(items.values());
}
