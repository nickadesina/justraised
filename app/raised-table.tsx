"use client";

import { useMemo, useState } from "react";

import type { Filing, Member } from "@/lib/data";
import { money, shortDate } from "@/lib/format";

export interface Row {
  member: Member;
  filing: Filing | undefined;
}

type SortKey = "rank" | "name" | "amount" | "first_sale" | "open_roles" | "since";

const STAGE_NAMES: Record<string, string> = {
  "pre-seed": "Pre-seed",
  seed: "Seed",
  "series-a": "Series A",
  "series-b": "Series B",
  "series-c": "Series C",
  "series-d": "Series D",
  "series-e": "Series E",
  growth: "Growth",
  public: "Public",
};

function stageName(stage: string | null): string {
  if (!stage) return "—";
  return STAGE_NAMES[stage] ?? stage.replace(/-/g, " ").replace(/^\w/, (c) => c.toUpperCase());
}



const tierName = (t: string) => (t === "a16z" ? "a16z" : t === "speedrun" ? "speedrun" : t);

export default function RaisedTable({ rows }: { rows: Row[] }) {
  const [tier, setTier] = useState("all");
  const [stage, setStage] = useState("all");
  const [noNewRoles, setNoNewRoles] = useState(false);
  const [sort, setSort] = useState<{ key: SortKey; desc: boolean }>({ key: "rank", desc: false });

  const stages = useMemo(
    () => Array.from(new Set(rows.map((r) => r.member.stage).filter((s): s is string => Boolean(s)))).sort(),
    [rows],
  );

  const shown = useMemo(() => {
    const value = (r: Row): number | string => {
      const f = r.filing;
      switch (sort.key) {
        case "rank":
          return r.member.rank;
        case "name":
          return r.member.name.toLowerCase();
        case "amount":
          return f?.amount ?? -1;
        case "first_sale":
          return f?.date_of_first_sale ?? "";
        case "open_roles":
          return r.member.open_roles;
        case "since":
          return f?.roles_since_first_sale ?? -1;
      }
    };
    const out = rows.filter(
      (r) =>
        (tier === "all" || r.member.tier === tier) &&
        (stage === "all" || r.member.stage === stage) &&
        (!noNewRoles || (r.filing?.roles_since_first_sale ?? 0) === 0),
    );
    out.sort((a, b) => {
      const va = value(a);
      const vb = value(b);
      const c = va < vb ? -1 : va > vb ? 1 : a.member.rank - b.member.rank;
      return sort.desc ? -c : c;
    });
    return out;
  }, [rows, tier, stage, noNewRoles, sort]);

  const header = (key: SortKey, label: string, cls?: string, firstDesc = false) => {
    const active = sort.key === key;
    return (
      <th className={cls} aria-sort={active ? (sort.desc ? "descending" : "ascending") : undefined}>
        <button
          type="button"
          onClick={() => setSort(active ? { key, desc: !sort.desc } : { key, desc: firstDesc })}
        >
          {label}
          {active ? (sort.desc ? " ↓" : " ↑") : ""}
        </button>
      </th>
    );
  };

  return (
    <>
      <div className="controls">
        <label>
          Tier
          <select value={tier} onChange={(e) => setTier(e.target.value)}>
            <option value="all">All</option>
            <option value="speedrun">speedrun</option>
            <option value="a16z">a16z</option>
          </select>
        </label>
        <label>
          Stage
          <select value={stage} onChange={(e) => setStage(e.target.value)}>
            <option value="all">All</option>
            {stages.map((s) => (
              <option key={s} value={s}>
                {stageName(s)}
              </option>
            ))}
          </select>
        </label>
        <label>
          <input type="checkbox" checked={noNewRoles} onChange={(e) => setNoNewRoles(e.target.checked)} />
          No roles posted since the raise
        </label>
        <span className="count">
          {shown.length} of {rows.length}
        </span>
      </div>

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              {header("rank", "#", "num")}
              {header("name", "Company")}
              <th>Tier</th>
              <th>Stage</th>
              {header("amount", "Amount sold", "num", true)}
              {header("first_sale", "First sale", undefined, true)}
              {header("open_roles", "Open roles", "num", true)}
              {header("since", "Posted since raise", "num", true)}
              <th>Filing</th>
            </tr>
          </thead>
          <tbody>
            {shown.map(({ member: m, filing: f }) => (
              <tr key={m.slug ?? m.name}>
                <td className="num">{m.rank}</td>
                <td className="company">
                  {m.url ? <a href={m.url}>{m.name}</a> : m.name}
                  {m.cohort ? <span className="note"> {m.cohort}</span> : null}
                </td>
                <td>{tierName(m.tier)}</td>
                <td>{stageName(m.stage)}</td>
                <td className="num">
                  {f ? money(f.amount) : "—"}
                  {f?.amount_kind === "offering" ? <div className="note">offering, not yet sold</div> : null}
                </td>
                <td>
                  {f ? shortDate(f.date_of_first_sale) : "—"}
                  {f ? <div className="note">{f.days_since_first_sale} days ago</div> : null}
                </td>
                <td className="num">{m.open_roles}</td>
                <td className="num">{f ? f.roles_since_first_sale : "—"}</td>
                <td>
                  {f ? (
                    <a href={f.filing_url} title={f.issuer_name}>
                      Form D{f.amendments ? `/A ×${f.amendments}` : ""}
                    </a>
                  ) : (
                    "—"
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {shown.length === 0 ? <p className="empty">No companies match these filters.</p> : null}
      </div>
    </>
  );
}
