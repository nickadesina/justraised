import type { Metadata } from "next";

import { type BoardCompany, API_NOTES, TALENT, board } from "@/lib/data";
import { MIN_ROLES, boardIssues } from "@/lib/issues";

export const metadata: Metadata = { title: "Board health · Just Raised" };

const n = (x: number | null | undefined) => (x === null || x === undefined ? "—" : x.toLocaleString("en-US"));
const pct = (x: number) => `${Math.round(x * 100)}%`;
const jobsUrl = (company: string) =>
  `${TALENT}/api/v1/jobs?company=${encodeURIComponent(company)}&page_size=1&source=just-raised`;

function Company({ c }: { c: BoardCompany }) {
  return (
    <span className="t-company">
      {c.logo ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img className="logo sm" src={c.logo} alt="" loading="lazy" />
      ) : (
        <span className="logo sm monogram" aria-hidden="true">
          {c.name.slice(0, 1).toUpperCase()}
        </span>
      )}
      <a href={c.url ?? `${TALENT}/companies/${c.slug}`}>{c.name}</a>
      <span className={`chip tier-${c.tier}`}>{c.tier}</span>
    </span>
  );
}

function Issue({
  id,
  title,
  count,
  why,
  how,
  children,
}: {
  id: string;
  title: string;
  count: string;
  why: React.ReactNode;
  how: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section className="issue" id={id}>
      <header className="issue-head">
        <div>
          <h2>{title}</h2>
          <p className="issue-why">{why}</p>
        </div>
        <span className="issue-count">{count}</span>
      </header>
      <div className="panel">
        <div className="t-scroll">{children}</div>
        <p className="issue-how">{how}</p>
      </div>
    </section>
  );
}

export default function BoardPage() {
  const { filter, repeats, noComp, stale, flagged } = boardIssues();
  const b = board.board;
  const p = board.portfolio;
  const repeatShare = b.repeat_listings / b.roles;

  return (
    <main className="page">
      <header className="page-head">
        <div>
          <div className="eyebrow">Workspace · fix list</div>
          <h1>
            Board <span className="grad">health</span>
          </h1>
          <p className="lede">
            What on the job board is worth fixing, read from the same public API candidates and agents use. Rechecked
            every night across {n(p.companies)} portfolio companies and all {n(b.roles)} live roles.
          </p>
        </div>
      </header>

      <dl className="kpis">
        <div>
          <dt>Companies flagged</dt>
          <dd>{n(flagged)}</dd>
        </div>
        <div>
          <dt>Filter misses</dt>
          <dd>{n(p.filter_misses)}</dd>
        </div>
        <div>
          <dt>Repeat listings</dt>
          <dd>{pct(repeatShare)}</dd>
        </div>
        <div>
          <dt>No comp posted</dt>
          <dd>{n(noComp.length)}</dd>
        </div>
        <div>
          <dt>Nothing new in 30d</dt>
          <dd>{n(stale.length)}</dd>
        </div>
      </dl>

      <nav className="jump" aria-label="Checks">
        <a href="#filter">Company filter</a>
        <a href="#repeats">Repeat listings</a>
        <a href="#comp">No comp</a>
        <a href="#stale">Nothing new</a>
      </nav>

      <Issue
        id="filter"
        title="Company filter finds nothing"
        count={`${n(p.filter_misses)} companies · ${n(p.roles_behind_filter_misses)} roles`}
        why={
          <>
            <code>/jobs?company=</code> matches the name on the jobs, which for these companies differs from the name{" "}
            <code>/companies</code> returns. An agent on the MCP server that looks a company up by the name it was just
            given gets zero roles and no error.
          </>
        }
        how={
          <>
            Each row links to the live API call that returns nothing. Fix: accept the slug, or normalize both names.{" "}
            <a href={API_NOTES}>More in the API notes →</a>
          </>
        }
      >
        <table>
          <thead>
            <tr>
              <th>Company</th>
              <th>/companies name</th>
              <th>Name /jobs accepts</th>
              <th className="r">Open roles</th>
              <th className="r">Try it</th>
            </tr>
          </thead>
          <tbody>
            {filter.map((c) => (
              <tr key={c.slug}>
                <td>
                  <Company c={c} />
                </td>
                <td>
                  <code>{c.name}</code>
                </td>
                <td>{c.jobs_name ? <code>{c.jobs_name}</code> : <span className="muted">not found</span>}</td>
                <td className="r">{n(c.open_roles)}</td>
                <td className="r">
                  <a href={jobsUrl(c.name)}>0 results →</a>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Issue>

      <Issue
        id="repeats"
        title="One role, many listings"
        count={`${n(b.repeat_listings)} of ${n(b.roles)} board-wide`}
        why={
          <>
            The same title at the same company, usually posted once per city. It inflates role counts on company pages,
            in collections and in the API, and fills search results with copies.
          </>
        }
        how={
          <>
            From <a href={`${TALENT}/jobs.md`}>/jobs.md</a>: listings vs distinct titles per company. Shown when at
            least 5 listings and 20% of a company&apos;s rows repeat a title. Fix: one listing with several locations.
          </>
        }
      >
        <table>
          <thead>
            <tr>
              <th>Company</th>
              <th className="r">Listings</th>
              <th className="r">Distinct titles</th>
              <th className="r">Repeats</th>
              <th className="bar-col">Share repeated</th>
            </tr>
          </thead>
          <tbody>
            {repeats.slice(0, 25).map((c) => (
              <tr key={c.slug}>
                <td>
                  <Company c={c} />
                </td>
                <td className="r">{n(c.listings)}</td>
                <td className="r">{n(c.distinct_titles)}</td>
                <td className="r strong">{n(c.repeats)}</td>
                <td className="bar-col">
                  <span className="bar">
                    <span style={{ width: pct(c.share) }} />
                  </span>
                  <span className="bar-val">{pct(c.share)}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {repeats.length > 25 ? <p className="more">+ {repeats.length - 25} more in board.json</p> : null}
      </Issue>

      <Issue
        id="comp"
        title="No comp posted"
        count={`${n(noComp.length)} companies`}
        why={
          <>
            Candidates filter by pay. A role without a posted band drops out of every <code>comp=</code> search unless
            they also pass <code>comp_any=1</code>, so these companies are invisible to anyone searching by salary.
          </>
        }
        how={<>Companies with at least {MIN_ROLES} open roles and none posting a pay band. Fix: a nudge to the founder.</>}
      >
        <table>
          <thead>
            <tr>
              <th>Company</th>
              <th className="r">Open roles</th>
              <th className="r">Posted in 30 days</th>
              <th>Top functions</th>
            </tr>
          </thead>
          <tbody>
            {noComp.slice(0, 25).map((c) => (
              <tr key={c.slug}>
                <td>
                  <Company c={c} />
                </td>
                <td className="r">{n(c.open_roles)}</td>
                <td className="r">{n(c.posted_30d)}</td>
                <td className="muted">{c.functions.slice(0, 3).map((f) => `${f.function.replace(/_/g, " ")} ${f.n}`).join(" · ")}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {noComp.length > 25 ? <p className="more">+ {noComp.length - 25} more in board.json</p> : null}
      </Issue>

      <Issue
        id="stale"
        title="Nothing new in 30 days"
        count={`${n(stale.length)} companies`}
        why={
          <>
            Plenty of open roles, none posted in the last month. Some are long-running searches; some are listings the
            company has quietly stopped hiring for. Worth a check before candidates spend time on them.
          </>
        }
        how={
          <>
            Companies with at least {MIN_ROLES} open roles and <code>facets.posted.30d</code> of 0. The role detail
            endpoint returns <code>status: &quot;closed&quot;</code> for closed roles, which a follow-up could check per
            listing.
          </>
        }
      >
        <table>
          <thead>
            <tr>
              <th>Company</th>
              <th className="r">Open roles</th>
              <th className="r">Comp posted</th>
              <th>Top functions</th>
            </tr>
          </thead>
          <tbody>
            {stale.slice(0, 25).map((c) => (
              <tr key={c.slug}>
                <td>
                  <Company c={c} />
                </td>
                <td className="r">{n(c.open_roles)}</td>
                <td className="r">{n(c.comp_posted)}</td>
                <td className="muted">{c.functions.slice(0, 3).map((f) => `${f.function.replace(/_/g, " ")} ${f.n}`).join(" · ")}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {stale.length > 25 ? <p className="more">+ {stale.length - 25} more in board.json</p> : null}
      </Issue>
    </main>
  );
}
