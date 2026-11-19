"use client";

import { useMemo, useState } from "react";

import type { SpvCompany } from "@/lib/data";
import { money, shortDate } from "@/lib/format";
import type { HiringHistory, Item, Raise } from "@/lib/items";
import { hasIssuerSale, isEarly, saleLabels, vehicleStatus } from "@/lib/signals";

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

function PostingCounts({ history, anchor }: { history: HiringHistory; anchor: string }) {
  const count = history.observed_postings_since_signal;
  const coverage = history.hiring_coverage;
  return (
    <>
      {history.openPostedSince !== null && (
        <div className="figure-label">
          {history.openPostedSince.toLocaleString("en-US")} currently open, posted since {anchor}
        </div>
      )}
      {count != null && (coverage === "partial" || coverage === "since_signal") ? (
        <div className="figure-label">
          {coverage === "partial" ? "At least " : ""}
          {count.toLocaleString("en-US")} {count === 1 ? "posting" : "postings"} observed since {anchor}
          {coverage === "partial" && " · partial history"}
        </div>
      ) : (
        <div className="figure-label">Posting history unavailable</div>
      )}
    </>
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
  const history = investor
    ? { ...investor, openPostedSince: investor.roles_since_first_spv }
    : item.raise?.hiring;
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
      {history && (investor || item.raise?.firstSale) && <PostingCounts history={history} anchor={anchor} />}
    </div>
  );
}

const dollars = (amount: number) =>
  amount.toLocaleString("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });

function IssuerEvidence({ sale }: { sale: Raise }) {
  const knownSold = sale.sold !== null ? `${dollars(sale.sold)} sold` : "Amount sold undisclosed";
  return (
    <div>
      <h3>Company filing</h3>
      <p>
        {sale.issuer} · <a href={sale.amountUrl}>{knownSold}</a>
        {sale.kind === "offering" && sale.amount !== null && (
          <>
            {" "}
            · <a href={sale.amountUrl}>{dollars(sale.amount)} offered</a>
          </>
        )}
        .
      </p>
      <p>
        <a href={sale.filingUrl}>Earliest notice on record</a> filed {shortDate(sale.filed)}.
        {sale.firstSale ? (
          <>
            {" "}
            <a href={sale.firstSaleUrl}>First sale</a> on {shortDate(sale.firstSale)}.
          </>
        ) : (
          " First sale date not reported."
        )}
        {sale.amendments > 0 && (
          <>
            {" "}
            <a href={sale.amountUrl}>Latest amendment</a> supplies the amount.
          </>
        )}
        {sale.partner && <> The filing lists {sale.partner} of a16z as a director or officer.</>}
      </p>
      {sale.additionalNotices.length > 0 && (
        <>
          <h3>Other company notices</h3>
          <ul>
            {sale.additionalNotices.map((notice) => (
              <li key={notice.accession}>
                {notice.issuer_name} · <a href={notice.filing_url}>Filed {shortDate(notice.file_date)}</a>
                {" · "}
                <a href={notice.amount_filing_url ?? notice.filing_url}>
                  {notice.amount_sold === null
                    ? "Amount sold undisclosed"
                    : `${dollars(notice.amount_sold)} sold`}
                </a>
                {notice.offering_amount != null && ` · offering target ${dollars(notice.offering_amount)}`}
                {notice.first_sale_reported && (
                  <>
                    {" "}
                    ·{" "}
                    <a href={notice.first_sale_filing_url ?? notice.filing_url}>
                      First sale {shortDate(notice.date_of_first_sale)}
                    </a>
                  </>
                )}
              </li>
            ))}
          </ul>
        </>
      )}
      {sale.score !== null && (
        <p className="muted">
          Issuer sale score {sale.score.toFixed(3)}. The score uses the amount sold, the current number of
          open roles and the age of the first sale.
        </p>
      )}
    </div>
  );
}

function InvestorEvidence({ spv }: { spv: SpvCompany }) {
  return (
    <div>
      <h3>Investor filings</h3>
      <p>
        These vehicles may buy newly issued or existing shares. Amounts are the latest reported totals for the offerings shown.
      </p>
      <p className="muted">
        Reported vehicle sales {spv.spv_amount_sold == null ? "unknown" : dollars(spv.spv_amount_sold)}.
        Earliest vehicle filing in view {shortDate(spv.first_spv_file_date)}.
      </p>
      <ul>
        {spv.vehicles.map((v) => (
          <li key={v.filing_url}>
            <a href={v.filing_url}>{v.name}</a> · {v.is_amendment ? "amendment" : "filing"}{" "}
            {shortDate(v.file_date)}
            {" · "}
            {v.amount_sold === null ? "amount sold unknown" : `${dollars(v.amount_sold)} sold`}
            {v.offering_amount != null &&
              v.offering_amount > 0 &&
              ` · offering target ${dollars(v.offering_amount)}`}
            {" · "}
            {saleLabels[vehicleStatus(v.sale_status, v.amount_sold)]}
            {v.date_of_first_sale && ` (${shortDate(v.date_of_first_sale)})`}
          </li>
        ))}
      </ul>
    </div>
  );
}

function Card({ item, filter }: { item: Item; filter: Filter }) {
  const meta = [item.stage ? (STAGES[item.stage] ?? item.stage) : null, item.location].filter(Boolean);
  const investor = investorFor(item, filter);
  return (
    <li className="card">
      <details>
        <summary>
          <Logo item={item} />
          <div className="who">
            <div className="name-row">
              <span className="name">{item.name}</span>
              <span className={`chip tier-${item.tier}`}>
                {item.tier}
                {item.cohort && ` ${item.cohort}`}
              </span>
              {!investor && isEarly(item) && <span className="chip early">Early window</span>}
            </div>
            {item.blurb && <p className="blurb">{item.blurb}</p>}
            {meta.length > 0 && <div className="meta">{meta.join(" · ")}</div>}
          </div>
          {investor ? <InvestorSignal spv={investor} /> : item.raise && <IssuerSignal sale={item.raise} />}
          <Hiring item={item} investor={investor} />
          <span className="chev" aria-hidden="true" />
        </summary>
        <div className="evidence">
          {!investor && item.raise && <IssuerEvidence sale={item.raise} />}
          {item.spv && <InvestorEvidence spv={item.spv} />}
          {investor && item.raise && <IssuerEvidence sale={item.raise} />}
        </div>
      </details>
    </li>
  );
}

export default function Feed({ items }: { items: Item[] }) {
  const [filter, setFilter] = useState<Filter>(DEFAULT_FILTER);
  const [sort, setSort] = useState<Sort>(DEFAULT_SORT);
  const [query, setQuery] = useState("");
  const shown = useMemo(() => {
    const q = query.trim().toLowerCase();
    const out = items.filter(
      (i) =>
        matchesFilter(i, filter) &&
        (!q || [i.name, i.blurb, i.location].some((t) => t?.toLowerCase().includes(q))),
    );
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
  }, [items, filter, sort, query]);
  return (
    <section aria-label="Companies">
      <div className="toolbar">
        <div className="pills" role="group" aria-label="Filter companies">
          {(Object.keys(FILTERS) as Filter[]).map((key) => (
            <button
              key={key}
              type="button"
              aria-pressed={filter === key}
              className={`pill ${filter === key ? "on" : ""}`}
              onClick={() => setFilter(key)}
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
            onChange={(e) => setQuery(e.target.value)}
            aria-label="Search companies"
          />
          <label className="sort">
            <span className="sort-label">Sort</span>
            <select
              aria-label="Sort companies"
              value={filter === "spv" && sort === "score" ? "newest" : sort}
              onChange={(e) => setSort(e.target.value as Sort)}
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
      <p className="sr-only" aria-live="polite">
        {shown.length} of {items.length} companies shown
      </p>
      <ol className="cards">
        {shown.map((i) => (
          <Card key={i.slug} item={i} filter={filter} />
        ))}
      </ol>
      {shown.length === 0 && (
        <p className="empty">
          {filter === "early" && !query
            ? "No company currently has a recent issuer sale and enough posting history to qualify."
            : "No companies match. Try another filter or clear the search."}
        </p>
      )}
    </section>
  );
}
