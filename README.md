# Just Raised

A daily list of a16z and speedrun portfolio companies that filed a Form D with
the SEC recently, ranked by how much they raised relative to how many roles they
have open. It answers a question job boards don't: which companies have new
money and haven't posted the roles yet.

- Page: https://nickadesina.github.io/justraised/
- Collection (talent network schema): [`/api/collections/just-raised.json`](https://nickadesina.github.io/justraised/api/collections/just-raised.json)
- Filing detail: [`/api/just-raised/filings.json`](https://nickadesina.github.io/justraised/api/just-raised/filings.json)
- Spreadsheet: [`/api/just-raised.csv`](https://nickadesina.github.io/justraised/api/just-raised.csv)

Built as the "one idea, with a link" for the speedrun talent team's
[Product Engineer](https://speedrun-talent-network.com/product-engineer/) role.

Everything here is public data: SEC EDGAR and the
[speedrun talent network API](https://speedrun-talent-network.com/developers).
The ranking uses those two sources and nothing else.

## The signal

A Form D is the notice a company files when it sells securities under
Regulation D, which covers nearly every venture round. Rule 503 says to file it
within 15 days of the first sale. It names the issuer, the amount sold, the
date of first sale, and the directors and officers.

New roles usually show up on a careers page one to three months after a round
closes. That lag is an **assumption** in v1. `data/history.parquet` records
every listed company's open roles each night, so after a few weeks the gap
between first sale and new postings can be measured per company and the
assumption replaced.

What the list tells a job seeker: this company has cash it did not have a few
months ago, roughly how much, and whether its postings have caught up. What it
does not tell them: that any particular role is coming, or when.

## Score

```
score = log10(amount + 1) / (open_roles + 1) * 0.5 ^ (days_since_first_sale / 45)
```

- **amount** is `totalAmountSold`, or `totalOfferingAmount` when nothing is sold
  yet (shown as "offering, not yet sold"). The log keeps a $500M growth round
  from burying every seed round.
- **open_roles** is the company's live role count on the talent network at run
  time. The +1 avoids dividing by zero. A company with 300 open roles has
  already told the market what it needs.
- **The decay** has a 45-day half-life, the middle of the assumed lag. Filings
  past the window drop off.
- **The window** runs from `dateOfFirstSale` on the original notice. An
  amendment (D/A) updates the amount and nothing else; it never restarts the
  window.

The page and the CSV print every input next to the score.

## Matching

Form D names are legal names ("Harvey AI Corp"); talent-network names are brand
names ("Harvey"). There is no shared key. A false positive puts the wrong
company on the page next to a dollar figure, so the matcher is tuned for
precision, and only High rows are published.

**Normalization** (`packages/edgar_names`) runs on both sides: lowercase,
strip punctuation, drop a leading "the", then strip legal suffixes from the end
(inc, corp, co, llc, ltd, holdings, labs, technologies, ai, io, pbc, ...). A
second "brand" form keeps labs, ai and technologies, because sometimes that
word is the brand. d/b/a and f/k/a parts become extra names. On the company
side, the slug is a second name ("anduril-industries" for Anduril).

**Ladder** (first hit wins):

| Rung | Rule | Confidence |
|---|---|---|
| 1 | Strict normalized names equal | High |
| 2 | Brand-form names equal | High |
| 3 | token_set_ratio ≥ 95, token_sort_ratio ≥ 85, issuer state = company state | High |
| 3′ | As rung 3, but token_sort_ratio < 85 (the legal name has extra words) | Medium |
| 4 | token_set_ratio ≥ 90, location match, a related person's surname is in the company blurb | Medium |
| 5 | token_set_ratio ≥ 90, no corroboration | Low (logged, dropped) |

`token_set_ratio` scores 100 whenever one name's words are a subset of the
other's. That is how "Anduril Industries" matches "Anduril", but also how
"Modal Health Group" would match "Modal". Strings can't tell those two apart,
so rung 3′ sends them to a person.

Three rules only ever demote High to Medium:

- **Location conflict.** The names are equal, but both locations are known and
  they disagree. Many portfolio names are single common words (Arena, Basis,
  Bounce), and "Bounce, LLC" in Indianapolis is not the luggage network.
- **Ambiguous issuer.** One filing reaches two companies at its best rung.
- **Contested company.** Two different issuers reach High for one company.

**Fund filters** run before matching. A filing is dropped if its industry group
is Pooled Investment Fund, its entity type is Limited Partnership, it claims an
Investment Company Act 3(c) exclusion, or its name contains fund, capital,
partners, ventures, SPV, "holdings LP", "a series of", or a Roman-numeral
series marker. A name that exactly equals a portfolio company skips the
name-word check.

**Review loop.** `review/medium.csv` lists every Medium pair with the Form D's
related persons, both locations, the amount, and ready-to-paste YAML. Confirmed
pairs go in [`matches.yaml`](matches.yaml) and never need review again;
`reject` and `block_cik` remove pairs for good. `review/low.csv` shows what was
dropped and why.

## Endpoints

The site is static (GitHub Pages), so each endpoint is a file the nightly run
regenerates. GitHub Pages serves them with open CORS and a 10-minute cache.

### `/api/collections/just-raised.json`

Exactly the response the talent network's `GET /api/v1/collections/{slug}` returns,
so the list can be mounted in their **signals** group without a translation
layer. It is a strict subset of their schema: every key is one they define, and
`scripts/check_schema.py --strict` checks it against their OpenAPI document in
CI.

| Field | Value |
|---|---|
| `collection.slug` / `title` / `group` | `just-raised` / `Just raised` / `signals` |
| `collection.description` | Portfolio companies with a Form D in the last N days, ranked by cash per open role |
| `collection.companies`, `roles`, `portfolio_members` | Counts over the member list |
| `members[].rank` | Position by score |
| `members[].name, slug, url, tier, cohort, open_roles, location, blurb, logo` | Passed through from their Company object |
| `members[].stage, remote_policy, functions, cities, investors` | Passed through from their `speedrun-companies` and `a16z-portfolio` collections |
| `members_total`, `page` (0-based), `page_size` (100), `total_pages` | Standard paging; past 100 members, later pages are `just-raised/page-N.json` |

### `/api/just-raised/filings.json`

The Form D side, keyed by slug, plus run metadata (window, formula, counts). This is additive: amount, first-sale date,
filing URL, issuer, amendments, roles posted since the raise, score inputs, and
the match rung. None of it fits their member schema.

### `/api/just-raised.csv`

Every column, for a spreadsheet.

If the talent team mounts it, the collection file drops into their API as-is.
Hosting it statically gives up one of their conventions: a `?source=` tag is
accepted but not logged, because GitHub Pages keeps no request logs.

## Pipeline

A nightly batch job writes JSON files and the site reads them. There is no live
query path and no database the page depends on.

```
pipeline/fetch_companies.py  talent network /companies + portfolio collections -> data/companies.json
pipeline/fetch_formd.py      EDGAR index (form.idx backfill, full-text search daily) -> data/formd_index.parquet
                             gated primary_doc.xml downloads, parsed          -> data/filings.parquet
pipeline/match.py            filters, ladder, matches.yaml                    -> data/matches.parquet, review/*.csv
pipeline/score.py            offerings, score, guardrail                      -> public/api/*, data/history.parquet
pipeline/run_all.py          all four, in order
```

GitHub Actions runs `run_all` at 10:00 UTC (02:00 Pacific in winter), commits
the regenerated files, and redeploys GitHub Pages (`.github/workflows/pages.yml`).
The Next.js page is a static export built from the same JSON files it links
to.

**XML gate.** A 180-day backfill indexes about 31,600 Form D and D/A filings.
`fetch_formd.py` downloads a filing's `primary_doc.xml` only if its index name
isn't obviously a fund and reaches token_set_ratio 85 against some portfolio
name. That is below every ladder rung, so the gate never drops a filing the
ladder could match. On the first run it let 236 filings through, roughly 130x
fewer SEC requests. The full index is kept, so when a company joins the talent
network, the next run gates its past filings back in. `--no-gate` fetches
everything.

**Guardrails.**

- Every EDGAR request goes through one client (`pipeline/clients.py`) with the
  User-Agent set and an 8-per-second limit (SEC allows 10). Parsed filings are
  never refetched, and raw XML is cached under `data/cache/`.
- Talent-network calls are limited to 1 per second; their API returns 429 on
  bursts.
- `score.py` refuses to publish if the High match count falls more than 30%
  from the previous run, which catches a broken normalizer before it empties
  the page. `--force` overrides it.
- A company whose talent-network name is "Stealth" is never published,
  whatever the join key.
- Public companies are excluded (Roblox filed a Form D in June 2026; that's not
  a venture round).

## What the first run found (2026-11-10)

These numbers shaped v1 and differ from the original design doc:

- **The talent network lists 778 companies, not 1,300**: 438 market tier, 291
  a16z, 49 speedrun. Only the 340 portfolio companies are matched. `/companies`
  lists **only companies with at least one live role**, so a company that raised
  and has posted nothing is invisible until it posts one. The page's toggle is
  "No roles posted since the raise" rather than "no open roles". A registry of
  every slug ever seen (`data/company_registry.json`) lets a company that drops
  to zero roles still be looked up.
- **Yield is thin.** A 90-day window has 3 High matches; 180 days has 5 (6
  before excluding Roblox). Full-text search of EDGAR for every portfolio brand
  name over the window found no operating-company Form D that the matcher
  missed. The other hits were SPVs and companies with similar names. So this is
  the base rate, not a matcher that's too strict. Per the design doc's fallback,
  v1 runs a **180-day window** and the header says so. Set
  `JUST_RAISED_WINDOW_DAYS=90` to go back.
- **Many filings report an early first-sale date.** Kalshi's August filing
  reports a first sale in April; OpenRouter's July filing reports one in March.
  Anchoring on first sale, as designed, drops them.
- **Related persons are the best tiebreak.** Several Medium rows list an a16z
  partner as a director, which is near-certain corroboration. This is a
  candidate rung for v2. For now it is review evidence, and the suggestions sit
  commented out in `matches.yaml`.
- EDGAR full-text search with `q=*` returns zero hits. Leaving `q` out returns
  every Form D. Items `3C`, `3C.1` and `3C.7` mark funds before any XML is
  fetched.

## Run it locally

```bash
uv sync
export SEC_USER_AGENT="Just Raised you@example.com"   # SEC fair access: name and contact
uv run python -m pipeline.run_all
uv run pytest
uv run --with jsonschema python scripts/check_schema.py public/api/collections/just-raised.json --strict
npm ci && npm run build && npx serve out      # static site in out/
```

One-time GitHub setup:

- Settings → Pages → Source: **GitHub Actions**.
- The nightly workflow sends `Just Raised nick@yuurei.ai` as the SEC
  User-Agent (fair access requires a contact address). A repository variable
  `SEC_USER_AGENT` overrides it.

## Shared package

`packages/edgar_names` holds the normalizer, fund filters, location keys and
override loader. It is the same issuer-name problem as matching N-PORT fund
holdings to private companies in PrivateMarks, which installs it from here:

```bash
uv add "edgar-names @ git+https://github.com/nickadesina/justraised#subdirectory=packages/edgar_names"
```

## License

MIT
