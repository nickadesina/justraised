"use client";

import { useMemo, useState } from "react";

import { money, shortDate } from "@/lib/format";
import type { Item } from "@/lib/items";

type Filter = "all" | "raised" | "spv" | "early" | "speedrun";
type Sort = "newest" | "window" | "biggest";

// "Early window": on the talent network and at most this many roles posted
// since the money came in. The card always shows the real number.
const EARLY_MAX = 3;

const STAGES: Record<string, string> = {
  "pre-seed": "Pre-seed",
  seed: "Seed",
  "series-a": "Series A",
  "series-b": "Series B",
  "series-c": "Series C",
  growth: "Growth",
};

const isEarly = (i: Item) => i.onNetwork && i.rolesSince !== null && i.rolesSince <= EARLY_MAX;
const biggest = (i: Item) => i.raise?.amount ?? i.spv?.sold ?? 0;

function ago(days: number): string {
  if (days <= 0) return "today";
  if (days === 1) return "yesterday";
  if (days < 14) return `${days} days ago`;
  if (days < 60) return `${Math.round(days / 7)} weeks ago`;
  return `${Math.round(days / 30)} months ago`;
}

function Logo({ item }: { item: Item }) {
  const [failed, setFailed] = useState(false);
  if (!item.logo || failed) {
    return (
      <div className="logo monogram" aria-hidden="true">
        {item.name.replace(/[^A-Za-z0-9]/g, "").slice(0, 1).toUpperCase()}
      </div>
    );
  }
  // eslint-disable-next-line @next/next/no-img-element
  return <img className="logo" src={item.logo} alt="" loading="lazy" onError={() => setFailed(true)} />;
}

function Signal({ item }: { item: Item }) {
  if (item.raise) {
    const r = item.raise;
    return (
      <div className="signal">
        <div className="figure own">{money(r.amount)}</div>
        <div className="figure-label">
          {r.kind === "offering" ? "Raising" : "Raised"} · {ago(r.days)}
        </div>
        {item.spv ? (
          <div className="figure-label">
            + {item.spv.count} investor SPV{item.spv.count > 1 ? "s" : ""}
          </div>
        ) : null}
      </div>
    );
  }
  const s = item.spv!;
  return (
    <div className="signal">
      <div className="figure">{s.sold > 0 ? money(s.sold) : `${s.count}×`}</div>
      <div className="figure-label">
        {s.count} investor SPV{s.count > 1 ? "s" : ""} · {ago(s.days)}
      </div>
    </div>
  );
}

function Hiring({ item }: { item: Item }) {
  if (!item.onNetwork || item.openRoles === null) {
    return (
      <div className="hiring">
        <div className="figure-label off">Not on the talent network</div>
        {item.url ? (
          <a className="figure-label link" href={item.url}>
            Company site →
          </a>
        ) : null}
      </div>
    );
  }
  const since = item.rolesSince ?? 0;
  return (
    <div className="hiring">
      <a className="figure roles" href={item.url ?? undefined}>
        {item.openRoles.toLocaleString("en-US")}
        <span className="figure-unit"> open role{item.openRoles === 1 ? "" : "s"} →</span>
      </a>
      <div className={`figure-label ${isEarly(item) ? "go" : ""}`}>
        {since === 0 ? "None posted since" : `${since.toLocaleString("en-US")} posted since`}
      </div>
    </div>
  );
}

function Evidence({ item }: { item: Item }) {
  return (
    <div className="evidence">
      {item.raise ? (
        <div>
          <h4>The company&apos;s own Form D</h4>
          <p>
            <a href={item.raise.filingUrl}>{item.raise.issuer}</a> reported{" "}
            {item.raise.kind === "offering"
              ? `an offering of ${money(item.raise.amount)} (nothing sold yet)`
              : `${money(item.raise.amount)} sold`}
            , first sale {shortDate(item.raise.firstSale)}
            {item.raise.amendments ? `, amended ${item.raise.amendments}×` : ""}.
            {item.raise.partner ? ` Lists ${item.raise.partner} of a16z as a director or officer.` : ""}
          </p>
          {item.raise.score !== null ? (
            <p className="muted">
              Window score {item.raise.score.toFixed(3)} = log₁₀(amount + 1) ÷ (open roles + 1) × 0.5^(days ÷ 45).
            </p>
          ) : null}
        </div>
      ) : null}
      {item.spv ? (
        <div>
          <h4>Investor SPVs</h4>
          <p className="muted">
            Vehicles formed to buy in. Could be a new round or a purchase of existing shares.
          </p>
          <ul>
            {item.spv.vehicles.map((v) => (
              <li key={v.filing_url}>
                <a href={v.filing_url}>{v.name}</a>
                <span className="muted">
                  {" "}
                  · {shortDate(v.file_date)}
                  {v.amount_sold ? ` · ${money(v.amount_sold)}` : ""}
                </span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}

function Card({ item }: { item: Item }) {
  const meta = [item.stage ? STAGES[item.stage] ?? item.stage : null, item.location].filter(Boolean);
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
                {item.cohort ? ` ${item.cohort}` : ""}
              </span>
              {isEarly(item) ? (
<span className="chip early">Early window</span>
              ) : null}
            </div>
            {item.blurb ? <p className="blurb">{item.blurb}</p> : null}
            {meta.length ? <div className="meta">{meta.join(" · ")}</div> : null}
          </div>
          <Signal item={item} />
          <Hiring item={item} />
          <span className="chev" aria-hidden="true" />
        </summary>
        <Evidence item={item} />
      </details>
    </li>
  );
}

export default function Feed({ items }: { items: Item[] }) {
  const [filter, setFilter] = useState<Filter>("all");
  const [sort, setSort] = useState<Sort>("window");
  const [query, setQuery] = useState("");

  const counts: Record<Filter, number> = useMemo(
    () => ({
      all: items.length,
      raised: items.filter((i) => i.raise).length,
      spv: items.filter((i) => i.spv).length,
      early: items.filter(isEarly).length,
      speedrun: items.filter((i) => i.tier === "speedrun").length,
    }),
    [items],
  );

  const shown = useMemo(() => {
    const q = query.trim().toLowerCase();
    const out = items.filter((i) => {
      if (filter === "raised" && !i.raise) return false;
      if (filter === "spv" && !i.spv) return false;
      if (filter === "early" && !isEarly(i)) return false;
      if (filter === "speedrun" && i.tier !== "speedrun") return false;
      if (!q) return true;
      return [i.name, i.blurb, i.location].some((t) => t?.toLowerCase().includes(q));
    });
    out.sort((a, b) => {
      if (sort === "biggest") return biggest(b) - biggest(a);
      if (sort === "window") {
        // Early-window companies first, then the cash-per-role score, then recency.
        const ea = isEarly(a) ? 1 : 0;
        const eb = isEarly(b) ? 1 : 0;
        if (ea !== eb) return eb - ea;
        const sa = a.raise?.score ?? -1;
        const sb = b.raise?.score ?? -1;
        if (sa !== sb) return sb - sa;
      }
      return a.days - b.days || a.name.localeCompare(b.name);
    });
    return out;
  }, [items, filter, sort, query]);

  const pills: [Filter, string][] = [
    ["all", "All"],
    ["raised", "Raised"],
    ["spv", "Investors buying in"],
    ["early", "Early window"],
    ["speedrun", "speedrun"],
  ];

  return (
    <section aria-label="Companies">
      <div className="toolbar">
        <div className="pills" role="group" aria-label="Filter companies">
          {pills.map(([key, label]) => (
            <button
              key={key}
              type="button"
              aria-pressed={filter === key}
              className={`pill ${filter === key ? "on" : ""}`}
              onClick={() => setFilter(key)}
            >
              {label} <span className="count">{counts[key]}</span>
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
            <select value={sort} onChange={(e) => setSort(e.target.value as Sort)}>
              <option value="window">Best window</option>
              <option value="newest">Newest money</option>
              <option value="biggest">Biggest</option>
            </select>
          </label>
        </div>
      </div>

      <div className="columns" aria-hidden="true">
        <span>Company</span>
        <span>Money in</span>
        <span>Open roles</span>
      </div>
      <p className="sr-only" aria-live="polite">
        {shown.length} of {items.length} companies shown
      </p>
      <ol className="cards">
        {shown.map((i) => (
          <Card key={i.slug} item={i} />
        ))}
      </ol>
      {shown.length === 0 ? <p className="empty">No companies match. Try another filter or clear the search.</p> : null}
    </section>
  );
}
