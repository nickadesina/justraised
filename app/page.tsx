import { filings } from "@/lib/data";
import { buildItems } from "@/lib/items";

import Queue from "./queue";

export default function Page() {
  const items = buildItems();
  const months = Math.round(filings.meta.window_days / 30);
  const raised = items.filter((i) => i.raise).length;
  const spv = items.filter((i) => i.spv).length;
  const early = items.filter((i) => i.onNetwork && i.rolesSince !== null && i.rolesSince <= 3).length;
  const week = items.filter((i) => i.filedDays <= 7).length;

  return (
    <main className="page">
      <header className="page-head">
        <div>
          <div className="eyebrow">Workspace · outreach queue</div>
          <h1>
            Just <span className="grad">raised</span>
          </h1>
          {/* DRAFT COPY: rewrite in your own voice before publishing. */}
          <p className="lede">
            Portfolio companies with new money in the last {months} months, newest filing first. New roles usually
            follow a raise by one to three months, so this is the window to reach founders while they&apos;re still
            planning the hires.
          </p>
        </div>
      </header>

      <dl className="kpis">
        <div>
          <dt>Companies</dt>
          <dd>{items.length}</dd>
        </div>
        <div>
          <dt>Filed this week</dt>
          <dd>{week}</dd>
        </div>
        <div>
          <dt>Own Form D</dt>
          <dd>{raised}</dd>
        </div>
        <div>
          <dt>Investor SPVs</dt>
          <dd>{spv}</dd>
        </div>
        <div>
          <dt>Early window</dt>
          <dd>{early}</dd>
        </div>
      </dl>

      <Queue items={items} />

      <section className="explain">
        <div>
          <span className="step">01</span>
          <strong>Find the money.</strong> Each night the pipeline reads new Form D filings from SEC EDGAR: the notice
          a company files when it sells stock in a private round, with the amount and the date of first sale.
        </div>
        <div>
          <span className="step">02</span>
          <strong>Match it to the portfolio.</strong> Filings are matched by name against every a16z and speedrun
          company. Only confident matches are shown; an a16z partner listed as a director counts as strong evidence.
          Investor SPVs named after a company are a weaker signal: a new round or a secondary purchase.
        </div>
        <div>
          <span className="step">03</span>
          <strong>Compare with hiring.</strong> For companies on the talent network: open roles, roles posted in the
          last 30 days, and roles posted since the money came in. Three or fewer since the raise is the early window.
        </div>
      </section>
    </main>
  );
}
