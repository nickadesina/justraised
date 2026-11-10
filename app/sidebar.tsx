"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { API, API_NOTES, REPO_URL } from "@/lib/data";

import Updated from "./updated";

export default function Sidebar({ counts, updatedAt }: { counts: { raised: number; board: number }; updatedAt: string }) {
  const path = usePathname();
  const nav = [
    { href: "/", label: "Just raised", count: counts.raised, hint: "Outreach queue" },
    { href: "/board", label: "Board health", count: counts.board, hint: "Fix list" },
  ];
  return (
    <aside className="sidebar">
      <div className="brand">
        <Link href="/" className="brand-name">
          Just Raised
        </Link>
        <span className="brand-tag">Talent ops</span>
      </div>

      <nav aria-label="Workspace">
        <div className="side-label">Workspace</div>
        {nav.map((n) => {
          const on = n.href === "/" ? path === "/" : path.startsWith(n.href);
          return (
            <Link key={n.href} href={n.href} className={`side-link ${on ? "on" : ""}`} aria-current={on ? "page" : undefined}>
              <span>{n.label}</span>
              <span className="side-count">{n.count}</span>
            </Link>
          );
        })}
      </nav>

      <div className="side-group">
        <div className="side-label">Data</div>
        <a className="side-link sub" href={API.collection}>
          Collection JSON
        </a>
        <a className="side-link sub" href={API.board}>
          Board JSON
        </a>
        <a className="side-link sub" href={API.csv}>
          CSV
        </a>
        <a className="side-link sub" href={API_NOTES}>
          API notes
        </a>
        <a className="side-link sub" href={REPO_URL}>
          Source
        </a>
      </div>

      <div className="side-foot">
        <Updated at={updatedAt} />
        <p>Nightly from SEC EDGAR and the talent network&apos;s public API. Independent prototype, not affiliated with a16z.</p>
      </div>
    </aside>
  );
}
