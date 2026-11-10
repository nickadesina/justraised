"use client";

import { useMemo, useState } from "react";

import { money, shortDate } from "@/lib/format";
import type { Item } from "@/lib/items";

type Filter = "all" | "raised" | "spv" | "early" | "speedrun";
type Sort = "newest" | "window" | "biggest";

// "Early window": on the talent network and at most this many roles posted
// since the money came in. The card always shows the real number.
const EARLY_MAX = 3;
// A filing this many days old or newer gets the "New" chip.
const NEW_DAYS = 7;

const STAGES: Record<string, string> = {
  "pre-seed": "Pre-seed",
  seed: "Seed",
  "series-a": "Series A",
  "series-b": "Series B",
  "series-c": "Series C",
  growth: "Growth",
};

const isEarly = (i: Item) => i.onNetwork && i.rolesSince !== null && i.rolesSince <= EARLY_MAX;
const isNew = (i: Item) => i.filedDays <= NEW_DAYS;
const biggest = (i: Item) => i.raise?.amount ?? i.spv?.sold ?? 0;
const plural = (n: number, word: string) => `${n.toLocaleString("en-US")} ${word}${n === 1 ? "" : "s"}`;

function ago(days: number): string {
  if (days <= 0) return "today";
  if (days === 1) return "yesterday";
  if (days < 14) return `${days} days ago`;
  if (days < 60) return `${Math.round(days / 7)} weeks ago`;
  return `${Math.round(days / 30)} months ago`;
}

function dayLabel(iso: string): string {
  return new Date(`${iso}T00:00:00Z`).toLocaleDateString("en-US", { month: "short", day: "numeric", timeZone: "UTC" });
}

function monthLabel(iso: string): string {
  return new Date(`${iso}T00:00:00Z`).toLocaleDateString("en-US", { month: "long", year: "numeric", timeZone: "UTC" });
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

function When({ item }: { item: Item }) {
  return (
    <div className="when">
      <time dateTime={item.filed} className="when-date">
        {dayLabel(item.filed)}
      </time>
      <span className="when-ago">{ago(item.filedDays)}</span>
    </div>
  );
}

function Signal({ item }: { item: Item }) {
  if (item.raise) {
    const r = item.raise;
    return (
      <div className="signal">
        <div className="signal-main">
          {r.kind === "offering" ? "Raising " : "Raised "}
          <strong>{money(r.amount)}</strong>
        </div>
        <div className="signal-sub">
          {item.spv ? `+ ${plural(item.spv.count, "investor SPV")}` : `first sale ${dayLabel(r.firstSale)}`}
        </div>
      </div>
    );
  }
  const s = item.spv!;
  return (
    <div className="signal">
      <div className="signal-main">
        <strong>{s.count}</strong> investor SPV{s.count > 1 ? "s" : ""}
      </div>
      <div className="signal-sub">{s.sold > 0 ? `${money(s.sold)} sold` : "amount not reported"}</div>
    </div>
  );
}

function Hiring({ item }: { item: Item }) {
  if (!item.onNetwork || item.openRoles === null) {
    return (
      <div className="hiring">
        <div className="hiring-main muted">Not on the talent network</div>
        {item.url ? (
          <a className="hiring-sub" href={item.url} onClick={(e) => e.stopPropagation()}>
            Company site →
          </a>
        ) : null}
      </div>
    );
  }
  const since = item.rolesSince ?? 0;
  const sinceWhat = item.raise ? "raise" : "first SPV";
  return (
    <div className="hiring">
      <a className="hiring-main" href={item.url ?? undefined} onClick={(e) => e.stopPropagation()}>
        {plural(item.openRoles, "open role")} →
      </a>
      <div className="hiring-sub">
        {item.posted30d !== null ? (
          <span className="h-30d">{item.posted30d.toLocaleString("en-US")} posted in last 30 days</span>
        ) : null}
        <span className={`h-since ${isEarly(item) ? "early-text" : ""}`}>
          {since === 0 ? `none since ${sinceWhat}` : `${since.toLocaleString("en-US")} since ${sinceWhat}`}
        </span>
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
            , first sale {shortDate(item.raise.firstSale)}, filed {shortDate(item.raise.filed)}
            {item.raise.amendments ? ` (amended ${item.raise.amendments}×)` : ""}.
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
          <p className="muted">Vehicles formed to buy in. Could be a new round or a purchase of existing shares.</p>
          <ul>
            {item.spv.vehicles.map((v) => (
              <li key={v.filing_url}>
                <a href={v.filing_url}>{v.name}</a>
                <span className="muted">
                  {" "}
                  · filed {shortDate(v.file_date)}
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
  const meta = [item.stage ? (STAGES[item.stage] ?? item.stage) : null, item.location].filter(Boolean);
  return (
    <li className="card">
      <details>
        <summary>
          <When item={item} />
          <Logo item={item} />
          <div className="who">
            <div className="name-row">
              <span className="name">{item.name}</span>
              {isNew(item) ? <span className="chip new">New</span> : null}
              <span className={`chip tier-${item.tier}`}>
                {item.tier}
                {item.cohort ? ` ${item.cohort}` : ""}
              </span>
              {isEarly(item) ? <span className="chip early">Early window</span> : null}
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
  const [sort, setSort] = useState<Sort>("newest");
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

  const groups = useMemo(() => {
    const q = query.trim().toLowerCase();
    const shown = items.filter((i) => {
      if (filter === "raised" && !i.raise) return false;
      if (filter === "spv" && !i.spv) return false;
      if (filter === "early" && !isEarly(i)) return false;
      if (filter === "speedrun" && i.tier !== "speedrun") return false;
      if (!q) return true;
      return [i.name, i.blurb, i.location].some((t) => t?.toLowerCase().includes(q));
    });
    shown.sort((a, b) => {
      if (sort === "biggest") return biggest(b) - biggest(a);
      if (sort === "window") {
        // Early-window companies first, then the cash-per-role score.
        const ea = isEarly(a) ? 1 : 0;
        const eb = isEarly(b) ? 1 : 0;
        if (ea !== eb) return eb - ea;
        const sa = a.raise?.score ?? -1;
        const sb = b.raise?.score ?? -1;
        if (sa !== sb) return sb - sa;
      }
      return b.filed.localeCompare(a.filed) || a.name.localeCompare(b.name);
    });
    if (sort !== "newest") return [{ label: null as string | null, items: shown }];
    // Newest first reads as a log: one heading per month of filing.
    const out: { label: string | null; items: Item[] }[] = [];
    for (const i of shown) {
      const label = monthLabel(i.filed);
      if (out.at(-1)?.label !== label) out.push({ label, items: [] });
      out.at(-1)!.items.push(i);
    }
    return out;
  }, [items, filter, sort, query]);

  const total = groups.reduce((n, g) => n + g.items.length, 0);

  const pills: [Filter, string][] = [
    ["all", "All"],
    ["raised", "Raised"],
    ["spv", "Investors buying in"],
    ["early", "Early window"],
    ["speedrun", "speedrun"],
  ];
  const sorts: [Sort, string][] = [
    ["newest", "Newest"],
    ["window", "Best window"],
    ["biggest", "Biggest"],
  ];

  return (
    <section id="feed" aria-label="Companies">
      <div className="toolbar">
        <div className="segment pills" role="tablist" aria-label="Filter">
          {pills.map(([key, label]) => (
            <button
              key={key}
              type="button"
              role="tab"
              aria-selected={filter === key}
              className={`seg ${filter === key ? "on" : ""}`}
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
          <div className="segment sorts" role="radiogroup" aria-label="Sort">
            {sorts.map(([key, label]) => (
              <button
                key={key}
                type="button"
                role="radio"
                aria-checked={sort === key}
                className={`seg ${sort === key ? "on" : ""}`}
                onClick={() => setSort(key)}
              >
                {label}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="feed">
        {groups.map((g) => (
          <div className="group" key={g.label ?? "all"}>
            {g.label ? (
              <h3 className="group-head">
                {g.label} <span className="count">{g.items.length}</span>
              </h3>
            ) : null}
            <ol className="cards">
              {g.items.map((i) => (
                <Card key={i.slug} item={i} />
              ))}
            </ol>
          </div>
        ))}
        {total === 0 ? <p className="empty">No companies match. Try another filter.</p> : null}
      </div>
    </section>
  );
}
