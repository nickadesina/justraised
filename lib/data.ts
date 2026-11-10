// The page is built from the same static files it links to as the API. The
// nightly pipeline writes them to public/api/ and the workflow redeploys, so
// nothing is read at request time and nothing can be down when a reviewer
// clicks the link.
import collectionDoc from "@/public/api/collections/just-raised.json";
import filingsDoc from "@/public/api/just-raised/filings.json";

export type Tier = "speedrun" | "a16z" | "market" | "universe";

// Exactly the member properties of the talent network's collection schema.
export interface Member {
  rank: number;
  name: string;
  slug: string | null;
  url: string | null;
  tier: Tier;
  cohort: string | null;
  open_roles: number;
  location: string | null;
  blurb: string | null;
  stage: string | null;
  remote_policy: string | null;
  investors: string[];
  functions: string[];
  cities: string[];
  logo: string | null;
}

export interface Filing {
  rank: number;
  slug: string;
  name: string;
  tier: Tier;
  stage_label: string | null;
  size_label: string | null;
  score: number;
  amount: number | null;
  amount_kind: "sold" | "offering" | "unknown";
  amount_sold: number;
  offering_amount: number | null;
  offering_indefinite: boolean;
  date_of_first_sale: string;
  first_sale_reported: boolean;
  days_since_first_sale: number;
  file_date: string;
  latest_file_date: string;
  amendments: number;
  offerings_in_window: number;
  accession: string;
  latest_accession: string;
  filing_url: string;
  issuer_name: string;
  issuer_cik: string;
  issuer_city: string | null;
  issuer_state: string | null;
  industry_group: string | null;
  roles_since_first_sale: number;
  first_post_since: string | null;
  days_to_first_post: number | null;
  match_rung: string;
  match_confidence: string;
}

export interface Meta {
  generated_at: string;
  run_date: string;
  window_days: number;
  half_life_days: number;
  formula: string;
  high_matches: number;
  members: number;
  lag_assumption: string;
}

export interface CollectionDoc {
  collection: {
    slug: string;
    title: string;
    description: string | null;
    group: "signals";
    url: string;
    companies: number;
    roles: number;
    portfolio_members: number;
    members: Member[];
    members_total: number;
    page: number;
    page_size: number;
    total_pages: number;
  };
}

export interface FilingsDoc {
  meta: Meta;
  filings: Record<string, Filing>;
}

export const collection = collectionDoc as unknown as CollectionDoc;
export const filings = filingsDoc as unknown as FilingsDoc;

export const BASE_PATH = process.env.NEXT_PUBLIC_BASE_PATH ?? "";
export const API = {
  collection: `${BASE_PATH}/api/collections/just-raised.json`,
  filings: `${BASE_PATH}/api/just-raised/filings.json`,
  csv: `${BASE_PATH}/api/just-raised.csv`,
};
export const REPO_URL = "https://github.com/nickadesina/justraised";
