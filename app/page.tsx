import { API, REPO_URL, collection, filings } from "@/lib/data";

import RaisedTable, { type Row } from "./raised-table";

export default function Page() {
  const { meta } = filings;
  const rows: Row[] = collection.collection.members.map((m) => ({ member: m, filing: filings.filings[m.slug ?? ""] }));
  const refreshed = new Date(meta.generated_at).toUTCString().replace(" GMT", " UTC");

  return (
    <main>
      <h1>Just raised</h1>
      {/* DRAFT COPY: rewrite in your own voice before publishing. */}
      <p className="lede">
        a16z and speedrun portfolio companies that filed a Form D with the SEC for a sale of securities in the last{" "}
        {meta.window_days} days, ranked by cash raised per open role. A company that just raised and has not posted many
        roles yet ranks high; one that has already posted heavily ranks low. The usual pattern is that new roles appear one
        to three months after a raise. That is an assumption for now: this list records open roles every night, and the
        measured gap will replace it. The ranking comes from public filings and the talent network&apos;s live role
        counts, nothing else.
      </p>

      <RaisedTable rows={rows} />

      <footer>
        <p>
          Score = log<sub>10</sub>(amount + 1) ÷ (open roles + 1) × 0.5<sup>days since first sale ÷ {meta.half_life_days}</sup>.
          Amount is the amount sold on the Form D, or the offering size when nothing is sold yet. Only high-confidence
          matches between the SEC issuer and the talent-network company are shown.
        </p>
        <p>
          Last refreshed {refreshed}. Data: <a href={API.collection}>collection JSON</a> (the talent
          network&apos;s collection schema)
          {" · "}
          <a href={API.filings}>filings JSON</a>
          {" · "}
          <a href={API.csv}>CSV</a>
          {" · "}
          <a href={REPO_URL}>source</a>
        </p>
      </footer>
    </main>
  );
}
