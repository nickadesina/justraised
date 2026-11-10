import type { OffNetworkFiling } from "@/lib/data";

import { money, shortDate } from "@/lib/format";

// Server-rendered: no filters, it is a short list. Ordered by cash and
// recency only, since open roles are not tracked for these companies.
export default function OffNetwork({ rows }: { rows: OffNetworkFiling[] }) {
  if (rows.length === 0) return null;
  return (
    <section className="off-network">
      <h2>Raised, not on the talent network</h2>
      <p className="lede">
        Portfolio companies from a16z.com and speedrun.a16z.com with a matched Form D that have no listing on the talent
        network, so there is no open-role count to compare against. Each match is backed by an a16z investing partner
        named on the filing.
      </p>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th className="num">#</th>
              <th>Company</th>
              <th>Tier</th>
              <th className="num">Amount sold</th>
              <th>First sale</th>
              <th>On the Form D</th>
              <th>Filing</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((f) => (
              <tr key={f.slug}>
                <td className="num">{f.rank}</td>
                <td className="company">
                  {f.website ? <a href={f.website}>{f.name}</a> : f.url ? <a href={f.url}>{f.name}</a> : f.name}
                  {f.cohort ? <span className="note"> {f.cohort}</span> : null}
                </td>
                <td>{f.tier}</td>
                <td className="num">
                  {money(f.amount)}
                  {f.amount_kind === "offering" ? <div className="note">offering, not yet sold</div> : null}
                </td>
                <td>
                  {shortDate(f.date_of_first_sale)}
                  <div className="note">{f.days_since_first_sale} days ago</div>
                </td>
                <td>{f.a16z_person ?? "—"}</td>
                <td>
                  <a href={f.filing_url} title={f.issuer_name}>
                    Form D{f.amendments ? `/A ×${f.amendments}` : ""}
                  </a>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
