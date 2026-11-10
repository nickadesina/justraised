import { API, REPO_URL, filings } from "@/lib/data";
import { buildItems } from "@/lib/items";

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
  const months = Math.round(meta.window_days / 30);
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
          {/* DRAFT COPY: rewrite in your own voice before publishing. */}
          <p className="sub">
            {items.length} a16z and speedrun companies took in new money in the last {months} months. New roles
            usually follow a raise by one to three months. This is the window before they&apos;re posted.
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
            <strong>Find the money.</strong> Every night the list reads new Form D filings from SEC EDGAR. A Form D is
            the notice a company files when it sells stock in a private round. It names the company, how much it
            sold, and when.
          </li>
          <li>
            <strong>Match it to the portfolio.</strong> Filings are matched by name against every a16z and speedrun
            company. Only confident matches are shown, and a filing that names an a16z partner as a director counts
            as strong evidence.
          </li>
          <li>
            <strong>Compare with hiring.</strong> For companies on the talent network, the list counts open roles
            and how many were posted since the money came in. Few new roles after a big raise is the early window.
          </li>
        </ol>
        <p className="how-note">
          Many large rounds never produce a Form D from the company itself, so the list also shows{" "}
          <em>investor SPVs</em>: vehicles named after a company, formed to buy in. They can mean a new round or a
          purchase of existing shares, so they are a weaker signal. The one-to-three-month lag is an assumption until
          a few weeks of nightly data can measure it.
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
