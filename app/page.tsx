import { API, REPO_URL, filings } from "@/lib/data";
import { buildItems } from "@/lib/items";

import Feed from "./feed";
import Updated from "./updated";

export default function Page() {
  const { meta } = filings;
  const items = buildItems();
  const raised = items.filter((i) => i.raise).length;
  const spv = items.filter((i) => i.spv).length;
  const early = items.filter((i) => i.onNetwork && i.rolesSince !== null && i.rolesSince <= 3).length;
  const months = Math.round(meta.window_days / 30);

  return (
    <>
      <div className="glow" aria-hidden="true" />
      <nav className="topnav" aria-label="Sections">
        <a className="wordmark" href="#top">
          Just Raised
        </a>
        <a href="#feed">Feed</a>
        <a href="#how">How it works</a>
        <a className="nav-cta" href={API.collection}>
          API
        </a>
      </nav>

      <main id="top">
        <header className="hero">
          <div className="kicker">
            <Updated at={meta.generated_at} />
          </div>
          <h1>
            Just <span className="grad">raised</span>
          </h1>
          {/* DRAFT COPY: rewrite in your own voice before publishing. */}
          <p className="sub">
            {items.length} a16z and speedrun companies took in new money in the last {months} months. New roles usually
            follow a raise by one to three months. This is the window before they&apos;re posted.
          </p>
          <dl className="stats">
            <div>
              <dt>Companies with new money</dt>
              <dd>{items.length}</dd>
            </div>
            <div>
              <dt>Filed their own Form D</dt>
              <dd>{raised}</dd>
            </div>
            <div>
              <dt>Investors buying in</dt>
              <dd>{spv}</dd>
            </div>
            <div>
              <dt>Early window</dt>
              <dd>{early}</dd>
            </div>
          </dl>
        </header>

        <Feed items={items} />

        <section className="how" id="how">
          <div className="label">How it works</div>
          {/* DRAFT COPY: new heading, rewrite in your own voice. */}
          <h2>Money first. Job posts later.</h2>
          <ol>
            <li>
              <span className="step">01 →</span>
              <div>
                <strong>Find the money.</strong> Every night the list reads new Form D filings from SEC EDGAR. A Form D
                is the notice a company files when it sells stock in a private round. It names the company, how much it
                sold, and when.
              </div>
            </li>
            <li>
              <span className="step">02 →</span>
              <div>
                <strong>Match it to the portfolio.</strong> Filings are matched by name against every a16z and speedrun
                company. Only confident matches are shown, and a filing that names an a16z partner as a director counts
                as strong evidence.
              </div>
            </li>
            <li>
              <span className="step">03 →</span>
              <div>
                <strong>Compare with hiring.</strong> For companies on the talent network, the list counts open roles,
                how many were posted in the last 30 days, and how many since the money came in. Few new roles after a big
                raise is the early window.
              </div>
            </li>
          </ol>
          <p className="muted">
            Many large rounds never produce a Form D from the company itself, so the list also shows{" "}
            <em>investor SPVs</em>: vehicles named after a company, formed to buy in. They can mean a new round or a
            purchase of existing shares, so they are a weaker signal. The one-to-three-month lag is an assumption until a
            few weeks of nightly data can measure it.
          </p>
        </section>
      </main>

      <footer className="site-footer">
        <div className="footer-inner">
          <div className="footer-mark">Just Raised</div>
          <ul>
            <li>
              <a href={API.collection}>Collection JSON →</a>
            </li>
            <li>
              <a href={API.filings}>Filings JSON →</a>
            </li>
            <li>
              <a href={API.csv}>CSV →</a>
            </li>
            <li>
              <a href={API.spvCsv}>SPV CSV →</a>
            </li>
            <li>
              <a href={REPO_URL}>Source →</a>
            </li>
          </ul>
          <p>
            An independent project built on public SEC filings and the talent network&apos;s public API. The collection
            JSON uses the talent network&apos;s collection schema. Not affiliated with a16z.
          </p>
        </div>
      </footer>
    </>
  );
}
