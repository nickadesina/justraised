import { API, REPO_URL, filings } from "@/lib/data";
import { buildItems } from "@/lib/items";
import { EARLY_MAX_DAYS, EARLY_MAX_POSTINGS, hasIssuerSale } from "@/lib/signals";

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
  const sales = items.filter(hasIssuerSale).length;
  const investors = items.filter(item => item.spv).length;
  const refreshed = new Date(meta.generated_at)
    .toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric", timeZone: "UTC" })
    .replace(",", "");

  return (
    <main>
      <header className="hero">
        <h1>
          <span className="sr-only">Just raised</span>
          <TitleCard />
        </h1>
        <div className="hero-side">
          <p className="sub">
            {sales} portfolio {sales === 1 ? "company reported" : "companies reported"} a securities sale with a first sale
            in the last {meta.window_days} days. Compare those filings with open jobs across a16z and speedrun.
            Investor vehicles filed notices naming {investors} {investors === 1 ? "company" : "companies"}.
          </p>
          <dl className="readout">
            <div>
              <dt>Source</dt>
              <dd>SEC EDGAR · Form D</dd>
            </div>
            <div>
              <dt>Refreshed</dt>
              <dd>{refreshed}</dd>
            </div>
            <div>
              <dt>Window</dt>
              <dd>{meta.window_days} days</dd>
            </div>
          </dl>
        </div>
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
