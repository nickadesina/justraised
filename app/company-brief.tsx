import type { ReactNode } from "react";

import type { SpvCompany, Vehicle } from "@/lib/data";
import type { Item, Raise } from "@/lib/items";
import { saleLabels, vehicleStatus } from "@/lib/signals";

import "./company-brief.css";

const currency = new Intl.NumberFormat("en-US", {
  style: "currency", currency: "USD", maximumFractionDigits: 0,
});
const day = new Intl.DateTimeFormat("en-GB", {
  day: "2-digit", month: "short", year: "numeric", timeZone: "UTC",
});

function date(iso: string) {
  return day.format(new Date(iso + "T00:00:00Z"));
}

function sales(sold: number | null, offered?: number | null) {
  const sale = sold == null ? "Amount sold unreported" : `${currency.format(sold)} sold`;
  return offered == null ? sale : `${sale} against a ${currency.format(offered)} offering`;
}

function ExternalArrow() {
  return (
    <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.4" aria-hidden="true" focusable="false">
      <path d="M2.5 9.5 9 3M3.5 3H9v5.5" />
    </svg>
  );
}

function SourceLink({ href, children }: { href: string; children: ReactNode }) {
  return <a className="brief-source" href={href} target="_blank" rel="noopener noreferrer">{children} <ExternalArrow /></a>;
}

interface EntryProps {
  when: string | null; label: string; children: ReactNode; source?: ReactNode;
}

function Entry({ when, label, children, source }: EntryProps) {
  return (
    <li className="brief-entry">
      {when ? <time dateTime={when}>{date(when)}</time> : <span className="brief-undated">Date unreported</span>}
      <div><strong>{label}</strong><p>{children}</p>{source}</div>
    </li>
  );
}

function IssuerHistory({ raise }: { raise: Raise }) {
  const knownOriginal = raise.originalSold !== null || raise.originalOffered !== null;
  const amountFromEarliest = raise.filingUrl === raise.amountUrl;
  const earliestSold = amountFromEarliest ? raise.sold : raise.originalSold;
  const earliestOffered = amountFromEarliest ? raise.offeringAmount : raise.originalOffered;
  const events: EntryProps[] = [];
  if (raise.firstSale) {
    events.push({
      when: raise.firstSale,
      label: "First sale",
      children: `${raise.issuer} reported this as the date of its first sale.`,
      source: <SourceLink href={raise.firstSaleUrl}>First-sale source</SourceLink>,
    });
  }
  const terms = earliestSold != null || earliestOffered != null
    ? `${sales(earliestSold, earliestOffered)}.` : `${raise.issuer} filed this notice.`;
  events.push({
    when: raise.filed,
    label: knownOriginal ? "Original notice" : "Earliest notice on record",
    children: terms + (raise.firstSale ? "" : " First-sale date unreported."),
    source: <SourceLink href={raise.filingUrl}>{knownOriginal ? "Read Form D" : "Read SEC filing"}</SourceLink>,
  });
  if (!amountFromEarliest) {
    const isLatestAmendment = raise.amendments > 0 && raise.amountUrl === raise.latestUrl;
    events.push({
      when: raise.amountFiled,
      label: isLatestAmendment ? "Amendment" : "Amount disclosure",
      children: sales(raise.sold, raise.offeringAmount) + ".",
      source: <SourceLink href={raise.amountUrl}>{isLatestAmendment ? "Read Form D/A" : "Read amount source"}</SourceLink>,
    });
  }
  if (raise.latestUrl !== raise.amountUrl && raise.latestUrl !== raise.filingUrl) {
    events.push({
      when: raise.latestFiled,
      label: "Latest filing",
      children: `${raise.issuer} filed a subsequent disclosure.`,
      source: <SourceLink href={raise.latestUrl}>Read latest filing</SourceLink>,
    });
  }
  // Events on the same date retain their declared order; undated evidence follows dated filings.
  events.sort((a,b) => {
    if (!a.when) return b.when ? 1 : 0;
    if (!b.when) return -1;
    return a.when.localeCompare(b.when);
  });
  return (
    <section className="brief-history" aria-label="Issuer filing history">
      <h3>Issuer filing history</h3>
      <ol className="brief-events">
        {events.map(entry => <Entry key={entry.label} {...entry} />)}
      </ol>
      {raise.additionalNotices.length > 0 && (
        <details>
          <summary>Additional issuer notices ({raise.additionalNotices.length})</summary>
          <ol className="brief-events">
            {raise.additionalNotices.map(notice => (
              <Entry key={notice.accession} when={notice.file_date} label={notice.issuer_name}
                source={<SourceLink href={notice.filing_url}>Read SEC filing</SourceLink>}>
                <a href={notice.amount_filing_url ?? notice.filing_url}>{sales(notice.amount_sold, notice.offering_amount)}</a>.
                {notice.first_sale_reported
                  ? <> First sale <a href={notice.first_sale_filing_url ?? notice.filing_url}>{date(notice.date_of_first_sale)}</a>.</>
                  : " First-sale date unreported."}
              </Entry>
            ))}
          </ol>
        </details>
      )}
      {(raise.partner || raise.score !== null) && (
        <details>
          <summary>Issuer match and ranking</summary>
          <div className="brief-note">
            {raise.partner && <p>A filing by {raise.issuer} lists {raise.partner} of a16z as a related person.</p>}
            {raise.score !== null && <p>Issuer sale score {raise.score.toFixed(3)}, based on amount sold, open roles and days since first sale.</p>}
          </div>
        </details>
      )}
    </section>
  );
}

function VehicleEntry({ vehicle, showSaleDate }: { vehicle: Vehicle; showSaleDate: boolean }) {
  const status = vehicleStatus(vehicle.sale_status, vehicle.amount_sold);
  return (
    <Entry when={vehicle.file_date} label={vehicle.name}
      source={<SourceLink href={vehicle.filing_url}>{vehicle.is_amendment ? "Read vehicle amendment" : "Read vehicle filing"}</SourceLink>}>
      {sales(vehicle.amount_sold, vehicle.offering_amount)}. {saleLabels[status]}.
      {showSaleDate && vehicle.date_of_first_sale && ` First sale ${date(vehicle.date_of_first_sale)}.`}
    </Entry>
  );
}

function InvestorHistory({ spv }: { spv: SpvCompany }) {
  const vehicles = [...spv.vehicles].sort((a,b) => b.file_date.localeCompare(a.file_date));
  const sole = vehicles.length === 1 ? vehicles[0] : null;
  return (
    <section className="brief-history" aria-label="Vehicle filing history">
      <h3>Vehicle filing history</h3>
      <p className="brief-intro">These vehicles may buy newly issued or existing shares. Whether {spv.name} received any proceeds is unknown.</p>
      <ol className="brief-events">
        {sole?.date_of_first_sale && (
          <Entry when={sole.date_of_first_sale} label="Vehicle’s first sale">
            {sole.name} reported this date for its sale of securities.
          </Entry>
        )}
        {vehicles.slice(0,3).map(v => <VehicleEntry key={v.filing_url} vehicle={v} showSaleDate={!sole} />)}
      </ol>
      {vehicles.length > 3 && (
        <details>
          <summary>Earlier vehicle filings ({vehicles.length - 3})</summary>
          <ol className="brief-events">
            {vehicles.slice(3).map(v => <VehicleEntry key={v.filing_url} vehicle={v} showSaleDate />)}
          </ol>
        </details>
      )}
      {vehicles.length > 1 && (
        <p className="brief-note">Earliest vehicle filing in view {date(spv.first_spv_file_date)}. Latest filing {date(spv.latest_spv_file_date)}.</p>
      )}
    </section>
  );
}

function FundingFact({ raise, spv }: { raise: Raise | null; spv: SpvCompany | null }) {
  const offering = raise?.kind === "offering";
  const label = spv ? "Vehicle reported sold" : offering ? "Issuer offering target" : "Issuer reported sold";
  const amount = spv ? spv.spv_amount_sold : offering ? raise?.offeringAmount : raise?.sold;
  const sole = spv?.vehicles.length === 1 ? spv.vehicles[0] : null;
  const amountUrl = spv ? sole?.filing_url : raise?.amountUrl;
  const value = amount == null ? "Unreported" : currency.format(amount);
  return (
    <div className="brief-fact">
      <dt>{label}</dt>
      <dd className="brief-value">{amountUrl ? <a href={amountUrl} target="_blank" rel="noopener noreferrer">{value}</a> : value}</dd>
      <dd className="brief-caption">
        {spv && (sole ? `Securities sold by ${sole.name}` : `Cumulative sales across ${spv.spvs} investor vehicles`)}
        {!spv && raise && (
          <>
            {raise.amendments > 0 && raise.amountUrl === raise.latestUrl ? "Total as amended" : "Reported"}{raise.amountFiled && ` on ${date(raise.amountFiled)}`}.
            {offering && (raise.sold === 0 ? " The issuer reported $0 sold." : " Amount sold unreported.")}
          </>
        )}
      </dd>
    </div>
  );
}

function HiringFact({ item, spv }: { item: Item; spv: SpvCompany | null }) {
  const history = spv ?? item.raise?.hiring;
  const current = spv ? spv.roles_since_first_spv : item.raise?.hiring.openPostedSince;
  const anchor = spv ? "first vehicle filing" : item.raise?.firstSale ? "first sale" : "earliest issuer filing";
  const observed = history?.observed_postings_since_signal;
  const partial = history?.hiring_coverage === "partial";
  const tracked = history?.hiring_coverage === "since_signal" || partial;
  return (
    <div className="brief-fact">
      <dt>Current hiring</dt>
      <dd className="brief-value">{item.openRoles == null ? "Untracked" : `${item.openRoles.toLocaleString("en-US")} open ${item.openRoles === 1 ? "role" : "roles"}`}</dd>
      <dd className="brief-caption">
        {!item.onNetwork ? "Outside the talent network’s jobs coverage" : (
          <>
            {item.openRoles == null && <p>Current role count unavailable.</p>}
            {current != null && <p>{current.toLocaleString("en-US")} currently open, posted since the {anchor}.</p>}
            {observed != null && tracked ? (
              <p>{partial ? "At least " : ""}{observed.toLocaleString("en-US")} {observed === 1 ? "posting" : "postings"} observed since the {anchor}.
                {partial && ` Partial history${history?.hiring_tracked_since ? ` from ${date(history.hiring_tracked_since)}` : ""}.`}</p>
            ) : <p>Posting history unavailable.</p>}
          </>
        )}
      </dd>
    </div>
  );
}

export default function CompanyBrief({ item, investor, onBack }: { item: Item; investor: boolean; onBack: () => void }) {
  const primarySpv = investor || !item.raise ? item.spv : null;
  const context = [item.stage?.replaceAll("-", " "), item.location].filter(Boolean).join(" · ");
  const companyLabel = item.onNetwork && (item.openRoles ?? 0) > 0 ? "View open roles" : item.onNetwork ? "View company profile" : "Visit company site";
  return (
    <section className="company-brief" aria-labelledby="company-brief-title">
      <div className="brief-body">
        <button className="brief-back" type="button" onClick={onBack}><span aria-hidden="true">← </span>Back to companies</button>
        <header className="brief-heading">
          <div>
            <p className="brief-kicker">{primarySpv ? "Investor vehicle filing" : "Issuer filing"}</p>
            <h2 id="company-brief-title" tabIndex={-1}>{item.name}</h2>
            {context && <p className="brief-context">{context}</p>}
          </div>
          {item.url && <a className="brief-action" href={item.url} target="_blank" rel="noopener noreferrer">{companyLabel} <ExternalArrow /></a>}
        </header>
        <dl className="brief-facts"><FundingFact raise={item.raise} spv={primarySpv} /><HiringFact item={item} spv={primarySpv} /></dl>
        {primarySpv && <InvestorHistory spv={primarySpv} />}
        {item.raise && <IssuerHistory raise={item.raise} />}
        {item.spv && !primarySpv && <InvestorHistory spv={item.spv} />}
        {item.blurb && <details className="brief-profile"><summary>Company profile</summary><p className="brief-note">{item.blurb}</p></details>}
      </div>
    </section>
  );
}
