import { API, REPO_URL, filings } from "@/lib/data";
import { buildItems } from "@/lib/items";
import { EARLY_MAX_DAYS, EARLY_MAX_POSTINGS } from "@/lib/signals";

import Feed from "./feed";

// Title-card lettering: the display face compressed to about 70% of its natural
// width in SVG, so the words keep their weight but sit narrow and tall.
function TitleCard() {
  return (
    <svg className="title-card" viewBox="0 0 960 206" aria-hidden="true" focusable="false">
      <text x="0" y="148" textLength="960" lengthAdjust="spacingAndGlyphs">
        JUST RAISED
      </text>
    </svg>
  );
}

export default function Page() {
  const { meta } = filings;
  const items = buildItems();
  const refreshed = new Date(meta.generated_at);
  const shortDate = refreshed.toLocaleDateString("en-US", { month: "short", day: "numeric", timeZone: "UTC" });
  const fullDate = refreshed.toLocaleDateString("en-US", {
    month: "long", day: "numeric", year: "numeric", timeZone: "UTC",
  });

  return (
    <main>
      <header className="masthead">
        <div className="masthead-row">
          <h1>
            <span className="sr-only">Just Raised</span>
            <TitleCard />
          </h1>
          <p className="masthead-context">Funding and hiring across a16z and speedrun</p>
          <time className="masthead-updated" dateTime={meta.generated_at}>Updated {shortDate}</time>
        </div>
        <details className="data-notes">
          <summary>Data notes</summary>
          <div className="data-notes-body">
            <dl>
              <div>
                <dt>Source</dt>
                <dd><a href="https://www.sec.gov/edgar/search/">SEC EDGAR · Form D</a></dd>
              </div>
              <div>
                <dt>Window</dt>
                <dd>{meta.window_days} days</dd>
              </div>
              <div>
                <dt>Updated</dt>
                <dd><time dateTime={meta.generated_at}>{fullDate}</time></dd>
              </div>
            </dl>
            <p>
              Company sales use the issuer’s reported first sale. Investor filings describe separate vehicles.
              Open roles come from the <a href="https://speedrun-talent-network.com/">talent network</a>.
            </p>
          </div>
        </details>
      </header>

      <Feed items={items} />

      <section className="how" aria-labelledby="how-title">
        <h2 id="how-title">How this works</h2>
        <ol>
          <li>
            <strong>Read the issuer filing.</strong> Company sales require a positive amount sold and a reported
            first sale date in the window. Each company card links to its SEC Form D and any amendment supporting
            the amount.
          </li>
          <li>
            <strong>Check the investor activity.</strong> A special purpose vehicle (SPV) may buy new securities or existing
            shares. The investor view shows its filing date, reported sales and first sale date when available.
            A recent filing can describe a much older sale.
          </li>
          <li>
            <strong>Compare with hiring.</strong> Open roles are a current snapshot. Observed postings include
            roles that have since closed. When tracking began after the signal or missed days, the observed
            count is a lower bound.
          </li>
        </ol>
        <p className="how-note">
          “Early window” means a company reported a sale within {EARLY_MAX_DAYS} days and the tracker has
          observed at most {EARLY_MAX_POSTINGS} postings with daily coverage since that sale.
          The idea that hiring follows a raise by one to three months is a hypothesis.
        </p>
      </section>

      <footer>
        <p className="links">
          <a href={API.collection}>Collection JSON</a>
          <a href={API.filings}>Filings JSON</a>
          <a href={API.csv}>CSV</a>
          <a href={API.spvCsv}>SPV CSV</a>
          <a href={REPO_URL}>Source</a>
        </p>
        <p>
          The collection file follows the talent network&apos;s collection schema. An independent project built on
          public SEC filings and the talent network&apos;s public API. Not affiliated with a16z.
        </p>
      </footer>
    </main>
  );
}
