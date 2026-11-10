"use client";

import { useEffect, useMemo, useState } from "react";

import { money, shortDate } from "@/lib/format";
import type { Item } from "@/lib/items";

type Filter = "all" | "raised" | "spv" | "early" | "speedrun";
type Sort = "newest" | "window" | "biggest";
type Status = "todo" | "contacted" | "later";
type StatusFilter = "any" | Status;

// "Early window": on the talent network and at most this many roles posted
// since the money came in. The row always shows the real number.
const EARLY_MAX = 3;
// A filing this many days old or newer gets the "New" chip.
const NEW_DAYS = 7;
// Triage status lives in this browser only; there is no backend.
const STATUS_KEY = "just-raised:status:v1";

const STATUS_LABEL: Record<Status, string> = { todo: "To do", contacted: "Contacted", later: "Not now" };
const STAGES: Record<string, string> = {
  "pre-seed": "Pre-seed",
  seed: "Seed",
  "series-a": "Series A",
  "series-b": "Series B",
  "series-c": "Series C",
  growth: "Growth",
};
const FUNCTIONS: Record<string, string> = {
  engineering: "Engineering",
  hardware_manufacturing: "Hardware",
  research: "Research",
  product: "Product",
  design: "Design",
  sales: "Sales",
  marketing: "Marketing",
  operations: "Operations",
  customer: "Customer",
  people: "People",
  finance: "Finance",
  legal: "Legal",
  other: "Other",
};

const isEarly = (i: Item) => i.onNetwork && i.rolesSince !== null && i.rolesSince <= EARLY_MAX;
const isNew = (i: Item) => i.filedDays <= NEW_DAYS;
const biggest = (i: Item) => i.raise?.amount ?? i.spv?.sold ?? 0;
const n = (x: number) => x.toLocaleString("en-US");
const plural = (x: number, word: string) => `${n(x)} ${word}${x === 1 ? "" : "s"}`;

function ago(days: number): string {
  if (days <= 0) return "today";
  if (days === 1) return "yesterday";
  if (days < 14) return `${days}d ago`;
  if (days < 60) return `${Math.round(days / 7)}w ago`;
  return `${Math.round(days / 30)}mo ago`;
}

function dayLabel(iso: string): string {
  return new Date(`${iso}T00:00:00Z`).toLocaleDateString("en-US", { month: "short", day: "numeric", timeZone: "UTC" });
}

function monthLabel(iso: string): string {
  return new Date(`${iso}T00:00:00Z`).toLocaleDateString("en-US", { month: "long", year: "numeric", timeZone: "UTC" });
}

function useStatuses() {
  const [map, setMap] = useState<Record<string, Status>>({});
  useEffect(() => {
    try {
      const raw = window.localStorage.getItem(STATUS_KEY);
      if (raw) setMap(JSON.parse(raw));
    } catch {
      // private window or blocked storage: statuses just don't persist
    }
  }, []);
  const set = (slug: string, s: Status) =>
    setMap((prev) => {
      const next = { ...prev };
      if (s === "todo") delete next[slug];
      else next[slug] = s;
      try {
        window.localStorage.setItem(STATUS_KEY, JSON.stringify(next));
      } catch {
        // ignore
      }
      return next;
    });
  return [map, set] as const;
}

// A paste-ready summary for Slack or an email to the founder's partner.
function brief(i: Item): string {
  const parts: string[] = [];
  if (i.raise) {
    const r = i.raise;
    parts.push(
      `${i.name}: ${r.kind === "offering" ? "raising" : "raised"} ${money(r.amount)} (Form D filed ${shortDate(r.filed)}, first sale ${shortDate(r.firstSale)}).`,
    );
    if (r.partner) parts.push(`${r.partner} (a16z) is listed as a director or officer.`);
  }
  if (i.spv) {
    parts.push(
      `${i.raise ? "Also " : `${i.name}: `}${plural(i.spv.count, "investor SPV")} filed, latest ${shortDate(i.spv.latest)}${i.spv.sold ? `, ${money(i.spv.sold)} sold` : ""}.`,
    );
  }
  if (i.onNetwork && i.openRoles !== null) {
    const since = i.rolesSince ?? 0;
    parts.push(
      `Talent network: ${plural(i.openRoles, "open role")}, ${n(since)} posted since the ${i.raise ? "raise" : "first SPV"}${i.posted30d !== null ? `, ${n(i.posted30d)} in the last 30 days` : ""}.`,
    );
  } else {
    parts.push("Not on the talent network yet.");
  }
  if (i.url) parts.push(i.url);
  if (i.raise) parts.push(`Filing: ${i.raise.filingUrl}`);
  return parts.join(" ");
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
      <div className="c-signal">
        <div>
          {r.kind === "offering" ? "Raising " : "Raised "}
          <strong>{money(r.amount)}</strong>
        </div>
        <div className="sub">{item.spv ? `Form D + ${plural(item.spv.count, "SPV")}` : "Form D"}</div>
      </div>
    );
  }
  const s = item.spv!;
  return (
    <div className="c-signal">
      <div>
        <strong>{s.count}</strong> investor SPV{s.count > 1 ? "s" : ""}
      </div>
      <div className="sub">{s.sold > 0 ? `${money(s.sold)} sold` : "amount not reported"}</div>
    </div>
  );
}

function Mix({ item }: { item: Item }) {
  const b = item.board;
  if (!b || !b.functions.length) return null;
  return (
    <div>
      <h4>Hiring mix</h4>
      <div className="mix-bar" aria-hidden="true">
        {b.functions.map((f, k) => (
          <span key={f.function} className={`mix-seg m${k}`} style={{ flexGrow: f.n }} />
        ))}
      </div>
      <ul className="mix-legend">
        {b.functions.map((f, k) => (
          <li key={f.function}>
            <span className={`mix-dot m${k}`} aria-hidden="true" />
            {FUNCTIONS[f.function] ?? f.function} <span className="muted">{n(f.n)}</span>
          </li>
        ))}
      </ul>
      <p className="muted small">
        {b.founding ? `${plural(b.founding, "founding role")} · ` : ""}
        {b.comp_posted !== null ? `comp posted on ${n(b.comp_posted)} of ${n(b.open_roles)}` : ""}
        {b.posted_7d !== null ? ` · ${n(b.posted_7d)} posted in the last 7 days` : ""}
      </p>
    </div>
  );
}

function Detail({ item }: { item: Item }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(brief(item));
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    } catch {
      window.prompt("Copy the brief:", brief(item));
    }
  };
  return (
    <div className="detail">
      <div className="detail-main">
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
              <p className="muted small">
                Window score {item.raise.score.toFixed(3)} = log₁₀(amount + 1) ÷ (open roles + 1) × 0.5^(days ÷ 45)
              </p>
            ) : null}
          </div>
        ) : null}
        {item.spv ? (
          <div>
            <h4>Investor SPVs</h4>
            <p className="muted small">Vehicles formed to buy in: a new round or a purchase of existing shares.</p>
            <ul className="vehicles">
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
      <div className="detail-side">
        <Mix item={item} />
        <div className="actions">
          <button type="button" className="btn primary" onClick={copy}>
            {copied ? "Copied" : "Copy brief"}
          </button>
          {item.url ? (
            <a className="btn" href={item.url}>
              {item.onNetwork ? "Talent network page" : "Company site"}
            </a>
          ) : null}
        </div>
      </div>
    </div>
  );
}

function Row({ item, status, onStatus }: { item: Item; status: Status; onStatus: (s: Status) => void }) {
  const [open, setOpen] = useState(false);
  const meta = [item.stage ? (STAGES[item.stage] ?? item.stage) : null, item.location].filter(Boolean).join(" · ");
  const since = item.rolesSince;
  return (
    <li className={`row ${open ? "open" : ""} st-${status}`}>
      <div className="row-main">
        <button
          type="button"
          className="row-toggle"
          aria-expanded={open}
          aria-label={`${open ? "Hide" : "Show"} details for ${item.name}`}
          onClick={() => setOpen((o) => !o)}
        />
        <div className="c-filed">
          <time dateTime={item.filed}>{dayLabel(item.filed)}</time>
          <span className="sub">{ago(item.filedDays)}</span>
        </div>
        <div className="c-company">
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
            <div className="blurb">{item.blurb ?? meta}</div>
          </div>
        </div>
        <Signal item={item} />
        <div className="c-nums">
        {item.onNetwork && item.openRoles !== null ? (
          <>
            <div className="c-num">
              <a href={item.url ?? undefined} className="num-link">
                {n(item.openRoles)}
              </a>
              <span className="lbl">open</span>
            </div>
            <div className="c-num">
              <span>{item.posted30d === null ? "—" : n(item.posted30d)}</span>
              <span className="lbl">30 days</span>
            </div>
            <div className={`c-num ${isEarly(item) ? "early-text" : ""}`}>
              <span>{since === null ? "—" : n(since)}</span>
              <span className="lbl">since {item.raise ? "raise" : "SPV"}</span>
            </div>
          </>
        ) : (
          <div className="c-off">Not on the talent network</div>
        )}
        </div>
        <div className="c-status">
          <select
            value={status}
            onChange={(e) => onStatus(e.target.value as Status)}
            aria-label={`Status for ${item.name}`}
            className={`status st-${status}`}
          >
            {(Object.keys(STATUS_LABEL) as Status[]).map((s) => (
              <option key={s} value={s}>
                {STATUS_LABEL[s]}
              </option>
            ))}
          </select>
        </div>
        <span className="chev" aria-hidden="true" />
      </div>
      {open ? <Detail item={item} /> : null}
    </li>
  );
}

export default function Queue({ items }: { items: Item[] }) {
  const [filter, setFilter] = useState<Filter>("all");
  const [sort, setSort] = useState<Sort>("newest");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("any");
  const [query, setQuery] = useState("");
  const [statuses, setStatus] = useStatuses();
  const statusOf = (slug: string): Status => statuses[slug] ?? "todo";

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
  const statusCounts = useMemo(() => {
    const c = { any: items.length, todo: 0, contacted: 0, later: 0 };
    for (const i of items) c[statuses[i.slug] ?? "todo"] += 1;
    return c;
  }, [items, statuses]);

  const groups = useMemo(() => {
    const q = query.trim().toLowerCase();
    const shown = items.filter((i) => {
      if (filter === "raised" && !i.raise) return false;
      if (filter === "spv" && !i.spv) return false;
      if (filter === "early" && !isEarly(i)) return false;
      if (filter === "speedrun" && i.tier !== "speedrun") return false;
      if (statusFilter !== "any" && (statuses[i.slug] ?? "todo") !== statusFilter) return false;
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
  }, [items, filter, sort, query, statusFilter, statuses]);

  const total = groups.reduce((t, g) => t + g.items.length, 0);
  const pills: [Filter, string][] = [
    ["all", "All"],
    ["raised", "Own Form D"],
    ["spv", "Investor SPVs"],
    ["early", "Early window"],
    ["speedrun", "speedrun"],
  ];
  const sorts: [Sort, string][] = [
    ["newest", "Newest"],
    ["window", "Best window"],
    ["biggest", "Biggest"],
  ];

  return (
    <section aria-label="Outreach queue" className="queue">
      <div className="toolbar">
        <div className="segment" role="tablist" aria-label="Filter">
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
            placeholder="Search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            aria-label="Search companies"
          />
          <label className="select">
            <span>Status</span>
            <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value as StatusFilter)}>
              <option value="any">Any ({statusCounts.any})</option>
              {(Object.keys(STATUS_LABEL) as Status[]).map((s) => (
                <option key={s} value={s}>
                  {STATUS_LABEL[s]} ({statusCounts[s]})
                </option>
              ))}
            </select>
          </label>
          <div className="segment" role="radiogroup" aria-label="Sort">
            {sorts.map(([key, label]) => (
              <button
                key={key}
                type="button"
                role="radio"
                aria-checked={sort === key}
                className={`seg ${sort === key ? "on sort-on" : ""}`}
                onClick={() => setSort(key)}
              >
                {label}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="panel">
        <div className="row-head" aria-hidden="true">
          <span>Filed</span>
          <span>Company</span>
          <span>Signal</span>
          <span className="r">Open</span>
          <span className="r">30 days</span>
          <span className="r">Since</span>
          <span>Status</span>
          <span />
        </div>
        {groups.map((g) => (
          <div className="group" key={g.label ?? "all"}>
            {g.label ? (
              <h3 className="group-head">
                {g.label} <span className="count">{g.items.length}</span>
              </h3>
            ) : null}
            <ol className="rows">
              {g.items.map((i) => (
                <Row key={i.slug} item={i} status={statusOf(i.slug)} onStatus={(s) => setStatus(i.slug, s)} />
              ))}
            </ol>
          </div>
        ))}
        {total === 0 ? <p className="empty">Nothing matches. Try another filter.</p> : null}
      </div>
      <p className="footnote">Status is saved in this browser only.</p>
    </section>
  );
}
