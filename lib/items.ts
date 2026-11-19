// Merge evidence by company while retaining the dates and hiring observations for each signal.
import { readFileSync } from "node:fs";
import { join } from "node:path";

import {
  type AdditionalNotice,
  type CollectionDoc,
  type Filing,
  type OffNetworkFiling,
  type PostingHistory,
  type SpvCompany,
  type Tier,
  collection,
  filings,
} from "@/lib/data";

export interface HiringHistory extends PostingHistory {
  openPostedSince: number | null;
}

export interface Raise {
  amount: number | null;
  sold: number | null;
  originalSold: number | null;
  originalOffered: number | null;
  offeringAmount: number | null;
  kind: Filing["amount_kind"];
  firstSale: string | null;
  filed: string;
  latestFiled: string | null;
  amountFiled: string | null;
  days: number;
  filingUrl: string;
  latestUrl: string;
  firstSaleUrl: string;
  amountUrl: string;
  issuer: string;
  amendments: number;
  partner: string | null;
  score: number | null;
  hiring: HiringHistory;
  additionalNotices: AdditionalNotice[];
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
  raise: Raise | null;
  spv: SpvCompany | null;
}

function raiseFrom(f: Filing | OffNetworkFiling): Raise {
  const sameFiling = f.latest_accession === f.accession;
  const latestUrl =
    sameFiling
      ? f.filing_url
      : `https://www.sec.gov/Archives/edgar/data/${f.issuer_cik}/${f.latest_accession.replaceAll("-", "")}/${f.latest_accession}-index.htm`;
  const amountUrl = f.amount_filing_url ?? latestUrl;
  const latestFiled = f.latest_file_date ?? (sameFiling ? f.file_date : null);
  return {
    amount: f.amount,
    sold: f.amount_sold,
    originalSold: f.original_amount_sold ?? null,
    originalOffered: f.original_offering_amount ?? null,
    offeringAmount: f.offering_amount,
    kind: f.amount_kind,
    firstSale: f.first_sale_reported ? f.date_of_first_sale : null,
    filed: f.file_date,
    latestFiled,
    amountFiled: amountUrl === latestUrl ? latestFiled : amountUrl === f.filing_url ? f.file_date : null,
    days: f.days_since_first_sale,
    filingUrl: f.filing_url,
    latestUrl,
    firstSaleUrl: f.first_sale_filing_url ?? f.filing_url,
    amountUrl,
    issuer: f.issuer_name,
    amendments: f.amendments,
    additionalNotices: f.additional_notices ?? [],
    partner: f.a16z_person,
    score: f.on_network && f.amount_kind === "sold" && f.first_sale_reported ? f.score : null,
    hiring: {
      openPostedSince:
        "roles_since_first_sale" in f && f.first_sale_reported ? f.roles_since_first_sale : null,
      observed_postings_since_signal: f.observed_postings_since_signal,
      hiring_coverage: f.hiring_coverage,
      hiring_tracked_since: f.hiring_tracked_since,
    },
  };
}

export function buildItems(): Item[] {
  const items = new Map<string, Item>();
  const members = new Map(collection.collection.members.map((m) => [m.slug ?? m.name, m]));
  for (let page = 1; page < collection.collection.total_pages; page++) {
    const path = join(process.cwd(), "public/api/collections/just-raised", `page-${page}.json`);
    const doc: CollectionDoc = JSON.parse(readFileSync(path, "utf8"));
    for (const member of doc.collection.members) members.set(member.slug ?? member.name, member);
  }
  for (const f of Object.values(filings.filings)) {
    const m = members.get(f.slug);
    items.set(f.slug, {
      slug: f.slug,
      name: f.name,
      tier: f.tier,
      cohort: m?.cohort ?? f.cohort ?? null,
      logo: m?.logo ?? f.logo ?? null,
      blurb: m?.blurb ?? f.blurb ?? null,
      location: m?.location ?? f.location ?? null,
      stage: m?.stage ?? f.stage ?? null,
      url: m?.url ?? f.url ?? null,
      onNetwork: true,
      openRoles: m?.open_roles ?? f.open_roles ?? null,
      raise: raiseFrom(f),
      spv: null,
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
      raise: raiseFrom(f),
      spv: null,
    });
  }
  for (const s of Object.values(filings.spv ?? {})) {
    const existing = items.get(s.slug);
    if (existing) {
      existing.spv = s;
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
      raise: null,
      spv: s,
    });
  }
  return Array.from(items.values());
}
