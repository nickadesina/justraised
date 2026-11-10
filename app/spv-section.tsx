import type { SpvCompany } from "@/lib/data";
import { money, shortDate } from "@/lib/format";

// Server-rendered list of companies with investor SPVs in the window, newest
// SPV filing first. Each vehicle links to its EDGAR filing.
export default function SpvSection({ rows }: { rows: SpvCompany[] }) {
  if (rows.length === 0) return null;
  return (
    <section>
      <h2>Investors buying in</h2>
      <p className="lede">
        Most large rounds never produce a Form D from the company itself. The vehicles investors form to buy in do: an
        SPV named after a portfolio company filed a Form D in the window. That can be a new round or a purchase of
        existing shares from employees and early investors, so it is a weaker sign of new hiring budget than the
        company&apos;s own filing.
      </p>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th className="num">#</th>
              <th>Company</th>
              <th>Tier</th>
              <th className="num">SPVs</th>
              <th className="num">Sold into SPVs</th>
              <th>Latest SPV filing</th>
              <th className="num">Open roles</th>
              <th className="num">Posted since</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.slug}>
                <td className="num">{r.rank}</td>
                <td className="company">
                  {r.url ? <a href={r.url}>{r.name}</a> : r.name}
                  {r.cohort ? <span className="note"> {r.cohort}</span> : null}
                  <div className="note">
                    <a href={r.vehicles[0].filing_url}>{r.vehicles[0].name}</a>
                    {r.vehicles.length > 1 ? ` and ${r.vehicles.length - 1} more` : ""}
                  </div>
                </td>
                <td>{r.tier}</td>
                <td className="num">{r.spvs}</td>
                <td className="num">{r.spv_amount_sold > 0 ? money(r.spv_amount_sold) : "—"}</td>
                <td>
                  {shortDate(r.latest_spv_file_date)}
                  <div className="note">{r.days_since_latest_spv} days ago</div>
                </td>
                <td className="num">{r.open_roles ?? <span className="note">not listed</span>}</td>
                <td className="num">{r.roles_since_first_spv ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
