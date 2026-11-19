"use client";

import { type MouseEvent, useLayoutEffect, useMemo, useRef, useState, useSyncExternalStore } from "react";

import type { SpvCompany } from "@/lib/data";
import { money, shortDate } from "@/lib/format";
import type { Item, Raise } from "@/lib/items";
import { hasIssuerSale, isEarly, saleLabels, vehicleStatus } from "@/lib/signals";

import CompanyBrief from "./company-brief";
import "./feed.css";

const FILTERS = {
  raised: "Company sales",
  spv: "Investor filings",
  early: "Early window",
  speedrun: "speedrun",
  all: "All filings",
};
type Filter = keyof typeof FILTERS;
type Sort = "newest" | "score" | "biggest";
const DEFAULT_FILTER: Filter = "raised";
const DEFAULT_SORT: Sort = "score";
const PAGE_SIZE = 5;
const HASH_PREFIX = "#company/";

function subscribeToHash(notify: () => void) {
  window.addEventListener("hashchange", notify);
  return () => window.removeEventListener("hashchange", notify);
}

function resolveCompany(hash: string, items: Item[]) {
  if (!hash.startsWith(HASH_PREFIX)) return null;
  const [encodedSlug, source, extra] = hash.slice(HASH_PREFIX.length).split("/");
  if (!encodedSlug || extra !== undefined || (source !== undefined && source !== "investor")) return null;
  try {
    const slug = decodeURIComponent(encodedSlug);
    const item = items.find(i => i.slug === slug);
    return item ? { item, investor: !!item.spv && (source === "investor" || !item.raise) } : null;
  } catch {
    return null;
  }
}

const STAGES: Record<string, string> = {
  "pre-seed": "Pre-seed",
  seed: "Seed",
  "series-a": "Series A",
  "series-b": "Series B",
  "series-c": "Series C",
  growth: "Growth",
};

function matchesFilter(item: Item, filter: Filter): boolean {
  switch (filter) {
    case "raised":
      return hasIssuerSale(item);
    case "spv":
      return !!item.spv;
    case "early":
      return isEarly(item);
    case "speedrun":
      return item.tier === "speedrun";
    case "all":
      return true;
  }
}

// Mixed companies retain both sources. In the investor view every column uses the vehicle evidence.
function investorFor(item: Item, filter: Filter): SpvCompany | null {
  return filter === "spv" || !item.raise ? item.spv : null;
}

function Logo({ item }: { item: Item }) {
  const [failed, setFailed] = useState(false);
  if (!item.logo || failed) {
    return (
      <div className="logo monogram" aria-hidden="true">
        {item.name
          .replace(/[^A-Za-z0-9]/g, "")
          .slice(0, 1)
          .toUpperCase()}
      </div>
    );
  }
  return <img className="logo" src={item.logo} alt="" loading="lazy" onError={() => setFailed(true)} />;
}

function IssuerSignal({ sale }: { sale: Raise }) {
  let label = "Amount unknown";
  if (sale.kind === "offering") label = "Offering target";
  if (sale.kind === "sold") label = "Reported sold";
  return (
    <div className="signal">
      <div className="figure own">{money(sale.amount)}</div>
      <div className="figure-label">{label}</div>
      <div className="figure-label">
        {sale.firstSale
          ? `First sale ${shortDate(sale.firstSale)}`
          : `Filed ${shortDate(sale.filed)} · first sale unknown`}
      </div>
    </div>
  );
}

function InvestorSignal({ spv }: { spv: SpvCompany }) {
  const status = vehicleStatus(spv.sale_status, spv.spv_amount_sold);
  return (
    <div className="signal">
      <div className="figure">
        {spv.spvs} investor {spv.spvs === 1 ? "vehicle" : "vehicles"}
      </div>
      <div className="figure-label">{saleLabels[status]}</div>
      {spv.spv_amount_sold != null && spv.spv_amount_sold > 0 && (
        <div className="figure-label">{money(spv.spv_amount_sold)} reported vehicle sales</div>
      )}
      <div className="figure-label">Latest filing {shortDate(spv.latest_spv_file_date)}</div>
    </div>
  );
}

function Hiring({ item, investor }: { item: Item; investor: SpvCompany | null }) {
  if (!item.onNetwork) {
    return (
      <div className="hiring">
        <div className="figure-label off">Hiring data unavailable</div>
        {item.url && (
          <a className="figure-label link" href={item.url}>
            Company site →
          </a>
        )}
      </div>
    );
  }
  const openPostedSince = investor ? investor.roles_since_first_spv : item.raise?.hiring.openPostedSince;
  const anchor = investor ? "first vehicle filing" : "first sale";
  const roles =
    item.openRoles == null ? (
      "Open roles unavailable"
    ) : (
      <>
        {item.openRoles.toLocaleString("en-US")}
        <span className="figure-unit"> open {item.openRoles === 1 ? "role" : "roles"}</span>
      </>
    );
  return (
    <div className="hiring">
      {item.url ? (
        <a className="figure roles" aria-label={`Open ${item.name} hiring profile`} href={item.url}>
          {roles} →
        </a>
      ) : (
        <div className="figure roles">{roles}</div>
      )}
      {openPostedSince != null && (investor || item.raise?.firstSale) && (
        <span className="open-posted-since">{openPostedSince.toLocaleString("en-US")} open, posted since {anchor}</span>
      )}
    </div>
  );
}

function CompanyRow({
  item, filter, onOpen,
}: {
  item: Item;
  filter: Filter;
  onOpen: (event: MouseEvent<HTMLAnchorElement>) => void;
}) {
  const investor = investorFor(item, filter);
  const href = HASH_PREFIX + encodeURIComponent(item.slug) + (investor ? "/investor" : "");
  const meta = [item.stage ? (STAGES[item.stage] ?? item.stage) : null, item.location].filter(Boolean);
  return (
    <li className="company-row">
      <Logo item={item} />
      <div className="who">
        <div className="name-row">
          <a
            className="name company-link"
            href={href}
            id={`company-link-${item.slug}`}
            aria-label={`Open ${item.name} company brief`}
            onClick={onOpen}
          >
            {item.name}
          </a>
          <span className={`chip tier-${item.tier}`}>
            {item.tier}{item.cohort && ` ${item.cohort}`}
          </span>
          {!investor && isEarly(item) && <span className="chip early">Early window</span>}
        </div>
        {item.blurb && <p className="blurb">{item.blurb}</p>}
        {meta.length > 0 && <div className="meta">{meta.join(" · ")}</div>}
      </div>
      {investor ? <InvestorSignal spv={investor} /> : item.raise && <IssuerSignal sale={item.raise} />}
      <Hiring item={item} investor={investor} />
      <span className="chev" aria-hidden="true" />
    </li>
  );
}

export default function Feed({ items }: { items: Item[] }) {
  const [filter, setFilter] = useState<Filter>(DEFAULT_FILTER);
  const [sort, setSort] = useState<Sort>(DEFAULT_SORT);
  const [query, setQuery] = useState("");
  const [limit, setLimit] = useState(PAGE_SIZE);
  const hash = useSyncExternalStore(subscribeToHash, () => window.location.hash, () => "");
  const view = useMemo(() => resolveCompany(hash, items), [hash, items]);
  const origin = useRef<{ link: HTMLAnchorElement; hash: string; scrollY: number } | null>(null);
  const wasInBrief = useRef(false);
  const firstNewSlug = useRef<string | null>(null);
  const searchInput = useRef<HTMLInputElement>(null);
  const allMatches = useMemo(() => {
    const q = query.trim().toLowerCase();
    return q ? items.filter(i => [i.name, i.blurb, i.location].some(t => t?.toLowerCase().includes(q))) : items;
  }, [items, query]);

  useLayoutEffect(() => {
    if (view) {
      wasInBrief.current = true;
      document.getElementById("company-brief-title")?.focus({ preventScroll: true });
      window.scrollTo(0, 0);
    } else if (wasInBrief.current) {
      wasInBrief.current = false;
      const from = origin.current;
      if (from && hash === from.hash && from.link.isConnected) {
        from.link.focus({ preventScroll: true });
        window.scrollTo(0, from.scrollY);
      } else if (!hash) {
        searchInput.current?.focus({ preventScroll: true });
        window.scrollTo(0, 0);
      }
    }
  }, [view, hash]);

  useLayoutEffect(() => {
    if (firstNewSlug.current) {
      document.getElementById(`company-link-${firstNewSlug.current}`)?.focus();
      firstNewSlug.current = null;
    }
  }, [limit]);

  function rememberOpener(event: MouseEvent<HTMLAnchorElement>) {
    if (!event.metaKey && !event.ctrlKey && !event.shiftKey && !event.altKey && event.button === 0) {
      origin.current = { link: event.currentTarget, hash: window.location.hash, scrollY: window.scrollY };
    }
  }

  function backToFeed() {
    if (origin.current?.link.hash === hash) window.history.back();
    else window.location.replace("#");
  }

  function selectFilter(next: Filter) {
    setFilter(next);
    setLimit(PAGE_SIZE);
  }

  const shown = useMemo(() => {
    const out = allMatches.filter(i => matchesFilter(i, filter));
    function facts(i: Item) {
      const investor = investorFor(i, filter);
      if (investor)
        return { days: investor.days_since_latest_spv, sold: investor.spv_amount_sold, score: null };
      const sale = i.raise!;
      return { days: sale.days, sold: sale.sold, score: sale.score };
    }
    return out.sort((a, b) => {
      const left = facts(a),
        right = facts(b);
      if (sort === "biggest" && left.sold !== right.sold) return (right.sold ?? -1) - (left.sold ?? -1);
      if (sort === "score" && left.score !== right.score) return (right.score ?? -1) - (left.score ?? -1);
      return left.days - right.days || a.name.localeCompare(b.name);
    });
  }, [allMatches, filter, sort]);
  const visible = shown.slice(0, limit);

  return (
    <>
      <section id="company-feed" className="company-feed" aria-label="Companies" hidden={!!view}>
        <div className="toolbar">
          <div className="pills" role="group" aria-label="Filter companies">
            {(Object.keys(FILTERS) as Filter[]).map((key) => (
              <button
                key={key}
                type="button"
                aria-pressed={filter === key}
                className={`pill ${filter === key ? "on" : ""}`}
                onClick={() => selectFilter(key)}
              >
                {FILTERS[key]}{" "}
                <span className="count">{items.filter((i) => matchesFilter(i, key)).length}</span>
              </button>
            ))}
          </div>
          <div className="tools">
            <input
              type="search"
              placeholder="Search companies"
              value={query}
              ref={searchInput}
              onChange={(e) => {
                setQuery(e.target.value);
                setLimit(PAGE_SIZE);
              }}
              aria-label="Search companies"
            />
            <label className="sort">
              <span className="sort-label">Sort</span>
              <select
                aria-label="Sort companies"
                value={filter === "spv" && sort === "score" ? "newest" : sort}
                onChange={(e) => {
                  setSort(e.target.value as Sort);
                  setLimit(PAGE_SIZE);
                }}
              >
                {filter !== "spv" && <option value="score">Issuer sale score</option>}
                <option value="newest">{filter === "spv" ? "Latest filing" : "Most recent"}</option>
                <option value="biggest">
                  {filter === "spv" ? "Most sold by vehicles" : "Most reported sold"}
                </option>
              </select>
            </label>
          </div>
        </div>
        <div className="columns" aria-hidden="true">
          <span>Company</span>
          <span>{filter === "spv" ? "Investor disclosures" : "Filing evidence"}</span>
          <span>Hiring</span>
        </div>
        <ol className="cards">
          {visible.map(item => <CompanyRow key={item.slug} item={item} filter={filter} onOpen={rememberOpener} />)}
        </ol>
        {shown.length === 0 && (
          <div className="empty">
            {filter === "early" && !query
              ? "No company currently has a recent issuer sale and enough posting history to qualify."
              : "No companies match this filter."}
            {query.trim() && allMatches.length > 0 && filter !== "all" && (
              <button type="button" className="feed-action cross-filter" onClick={() => {
                selectFilter("all");
                searchInput.current?.focus();
              }}>
                Show {allMatches.length} {allMatches.length === 1 ? "match" : "matches"} in All filings
              </button>
            )}
          </div>
        )}
        <div className="feed-pagination">
          <span aria-live="polite">{visible.length} of {shown.length} companies shown</span>
          {limit < shown.length && (
            <button type="button" className="feed-action" onClick={() => {
              firstNewSlug.current = shown[limit].slug;
              setLimit(limit + PAGE_SIZE);
            }}>Show more companies</button>
          )}
        </div>
      </section>
      {view && <CompanyBrief key={view.item.slug} item={view.item} investor={view.investor} onBack={backToFeed} />}
    </>
  );
}
