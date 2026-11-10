import { API, REPO_URL, filings } from "@/lib/data";
import { buildItems } from "@/lib/items";

import Feed from "./feed";

export default function Page() {
  const { meta } = filings;
  const items = buildItems();
  const raised = items.filter((i) => i.raise).length;
  const spv = items.filter((i) => i.spv).length;
  const early = items.filter((i) => i.onNetwork && i.rolesSince !== null && i.rolesSince <= 3).length;
  const months = Math.round(meta.window_days / 30);
  const refreshed = new Date(meta.generated_at).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    timeZone: "UTC",
  });

  return (
    <main>
      <header className="hero">
        <div className="kicker">Signals · SEC Form D · updated {refreshed}</div>
        <h1>Just raised</h1>
        {/* DRAFT COPY: rewrite in your own voice before publishing. */}
        <p className="sub">
          {items.length} a16z and speedrun companies took in new money in the last {months} months. New roles usually
          follow a raise by one to three months. This is the window before they&apos;re posted.
        </p>
        <dl className="stats">
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

      <section className="how">
        <h2>How this works</h2>
        <ol>
          <li>
            <strong>Find the money.</strong> Every night the list reads new Form D filings from SEC EDGAR. A Form D is
            the notice a company files when it sells stock in a private round. It names the company, how much it sold,
            and when.
          </li>
          <li>
            <strong>Match it to the portfolio.</strong> Filings are matched by name against every a16z and speedrun
            company. Only confident matches are shown, and a filing that names an a16z partner as a director counts as
            strong evidence.
          </li>
          <li>
            <strong>Compare with hiring.</strong> For companies on the talent network, the list counts open roles and
            how many were posted since the money came in. Few new roles after a big raise is the early window.
          </li>
        </ol>
        <p className="muted">
          Many large rounds never produce a Form D from the company itself, so the list also shows{" "}
          <em>investor SPVs</em>: vehicles named after a company, formed to buy in. They can mean a new round or a
          purchase of existing shares, so they are a weaker signal. The one-to-three-month lag is an assumption until a
          few weeks of nightly data can measure it.
        </p>
      </section>

      <footer>
        <p>
          Data: <a href={API.collection}>collection JSON</a> (the talent network&apos;s collection schema) ·{" "}
          <a href={API.filings}>filings JSON</a> · <a href={API.csv}>CSV</a> · <a href={API.spvCsv}>SPV CSV</a> ·{" "}
          <a href={REPO_URL}>source</a>
        </p>
        <p>
          An independent project built on public SEC filings and the talent network&apos;s public API. Not affiliated
          with a16z.
        </p>
      </footer>
    </main>
  );
}
