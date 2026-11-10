# Just Raised

A console for the speedrun talent team, built on public data. It has two
views:

- **Just raised**, an outreach queue: a16z and speedrun portfolio companies
  that filed a Form D (or had an investor SPV filed) recently, newest filing
  first, next to how many roles they have open, posted in the last 30 days, and
  posted since the money came in. It answers a question job boards don't:
  which companies have new money and haven't posted the roles yet. Each row
  has a triage status (saved in the browser) and a "copy brief" for Slack.
  "Best window" re-sorts by cash per open role, the order of the collection
  endpoint.
- **Board health**, a fix list for the job board itself: companies whose
  `company=` filter finds nothing, titles listed once per city, companies that
  post no comp, and companies with plenty of open roles and nothing new in 30
  days.

- Console: https://nickadesina.github.io/justraised/ (board health at `/board`)
- Collection (talent network schema): [`/api/collections/just-raised.json`](https://nickadesina.github.io/justraised/api/collections/just-raised.json)
- Filing detail: [`/api/just-raised/filings.json`](https://nickadesina.github.io/justraised/api/just-raised/filings.json)
- Spreadsheet: [`/api/just-raised.csv`](https://nickadesina.github.io/justraised/api/just-raised.csv)
- Board health: [`/api/just-raised/board.json`](https://nickadesina.github.io/justraised/api/just-raised/board.json)

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

**Universe.** The talent network's `/companies` lists only companies with a
live role (340 portfolio companies). The matcher also runs against every
active, private company on [a16z.com/portfolio](https://a16z.com/portfolio/),
every disclosed name on the [investment list](https://a16z.com/investment-list/)
that a16z.com doesn't mark as exited, and the public
[speedrun list](https://speedrun.a16z.com/companies) (current cohort), all read
from those pages each night (`pipeline/fetch_portfolio.py`). That is 1,446
companies, 1,106 of them not on the talent network.
[`aliases.yaml`](aliases.yaml) maps brands to legal names the matcher can't
guess (Cursor is Anysphere). Companies that aren't on the network are published in a
separate section: they have no open-role count, so they can't be ranked on cash
per role.

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

Rules that demote High to Medium:

- **Location conflict.** The names are equal, but both locations are known and
  they disagree. Many portfolio names are single common words (Arena, Basis,
  Bounce), and "Bounce, LLC" in Indianapolis is not the luggage network.
- **Off-network, no location.** An exact name match against a company that
  isn't on the talent network, with no location to compare. Many are single
  common words (Relay, Trunk, Space).
- **Ambiguous issuer.** One filing reaches two companies at its best rung.
- **Contested company.** Two different issuers reach High for one company.

One rule promotes:

- **Rung P: an a16z partner on the Form D.** A Medium from rungs 1–3 becomes
  High when the filing lists a member of the a16z investing team
  ([a16z.com/team](https://a16z.com/team/), 117 people) as a director or
  officer. Board seats are how a16z shows up on a Form D, and a similar name
  plus a16z partner on the board is near-certain. On the first run it
  confirmed Town (Alex Rampell), Stuut (Seema Amble), Mariana Minerals (Erin
  Price-Wright), Apex Space (Katherine Boyle), Databricks (Ben Horowitz),
  Whatnot (Connie Chan), BigHat Biosciences (Vineeta Agarwala) and Fly.io
  (Martin Casado). It never rescues a Low, and the ambiguity and contest rules
  still apply.

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

## Investor SPVs

The deeper search turned up an uncomfortable fact: **most large venture rounds
never produce a Form D from the company itself.** Filing is legally required
but widely skipped, and skipping it doesn't cost a company its exemption.
Anysphere (Cursor), Character.AI, Navan, Applied Intuition, Krea, Mintlify and
Ideogram have no company Form Ds for their recent rounds; ElevenLabs last filed
in 2023 and Decagon in 2024. Across all of EDGAR, only 39 Form Ds in 180 days
name any of the 117 a16z investing-team members, and 15 of those are funds.

What does file, constantly, are the vehicles investors form to buy in: "HII
Anysphere-01, a Series of HII Anysphere LLC", "Greenbird Intelligence Fund,
Series W - Shield AI", "Voyager SPV - Astro Mechanica 2026". `pipeline/spv.py`
finds Form Ds whose issuer is a vehicle and whose name contains exactly one
portfolio brand as whole words. A one-word brand counts only if it is rare in
English (wordfreq Zipf < 2.5: "saronic" passes, "titan" doesn't), and a brand
followed by a manager word ("Koru Ventures", "Celo Capital") is the manager,
not the target. `spv_ignore` in `matches.yaml` drops a slug for good.

An SPV means money is being pooled to buy in now. That can be a new round or a
purchase of existing shares from employees and early investors, so the page
shows these in their own section, "Investors buying in", ordered by the latest
SPV filing, with open roles and roles posted since the first SPV. On the first
run that section had 25 companies, including Cursor, Anduril, Shield AI,
Kalshi, Databricks, Saronic, ElevenLabs, Periodic Labs, Hadrian and Zipline.

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

The Form D side, keyed by slug, plus run metadata (window, formula, counts).
`off_network` holds the matched companies that aren't on the talent network,
keyed `a16z:<slug>` or `speedrun:<slug>`. `spv` holds the companies with
investor SPVs, each with its vehicles and their filings
([`/api/just-raised-spvs.csv`](https://nickadesina.github.io/justraised/api/just-raised-spvs.csv)
as a spreadsheet). This is additive: amount, first-sale date,
filing URL, issuer, amendments, roles posted since the raise, roles posted in
the last 30 and 7 days (`roles_posted_30d`, `roles_posted_7d`), score inputs,
and the match rung. None of it fits their member schema.

### `/api/just-raised/board.json`

One row per portfolio company on the talent network: open roles, roles posted
in the last 24 hours / 7 days / 30 days, function mix, founding roles, roles
with a posted pay band, listings vs distinct titles, and whether
`/jobs?company=<name>` finds its roles (with the name that does, when one
exists). Board-wide totals for repeat listings. The board-health view is built
from this file.

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
pipeline/fetch_portfolio.py  a16z.com portfolio, investment list, team; speedrun -> data/portfolio_universe.json, data/a16z_people.json
pipeline/spv.py              investor vehicles named after a portfolio company  -> data/spv_filings.parquet
pipeline/fetch_formd.py      EDGAR index (form.idx backfill, full-text search daily) -> data/formd_index.parquet
                             gated primary_doc.xml downloads, parsed          -> data/filings.parquet
pipeline/match.py            filters, ladder, matches.yaml                    -> data/matches.parquet, review/*.csv
pipeline/board.py            /jobs facets per portfolio company, /jobs.md     -> public/api/just-raised/board.json
pipeline/score.py            offerings, score, guardrail                      -> public/api/*, data/history.parquet
pipeline/run_all.py          all of them, in order
```

GitHub Actions runs `run_all` at 10:00 UTC (02:00 Pacific in winter), commits
the regenerated files, and redeploys GitHub Pages (`.github/workflows/pages.yml`).
The Next.js page is a static export built from the same JSON files it links
to.

**XML gate.** A 180-day backfill indexes about 31,600 Form D and D/A filings.
`fetch_formd.py` downloads a filing's `primary_doc.xml` only if its index name
isn't obviously a fund and reaches token_set_ratio 85 against some portfolio
name. That is below every ladder rung, so the gate never drops a filing the
ladder could match. Against the full 829-company universe it lets about 1,570
filings through, roughly 20x fewer SEC requests. The full index is kept, so when a company joins the talent
network, the next run gates its past filings back in. `--no-gate` fetches
everything.

**Guardrails.**

- Every EDGAR request goes through one client (`pipeline/clients.py`) with the
  User-Agent set and an 8-per-second limit (SEC allows 10). Parsed filings are
  never refetched, and raw XML is cached under `data/cache/`.
- Talent-network calls are limited to 1 per second; their API returns 429 on
  bursts.
- `board.py` makes one `/jobs?company=<name>&page_size=1` call per portfolio
  company (340, about six minutes) and reads the posting buckets, function
  mix and comp coverage from its facets, plus one download of `/jobs.md`.
  When a name returns zero rows for a company with open roles, it looks up
  the name the jobs carry (see API note 1) and retries; if that fails too the
  counts are `null`, never a false 0. `score.py` reuses tonight's buckets and
  calls `/jobs` itself only for companies the board run didn't cover.
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
- **Yield is thin on the talent network alone.** Matching only its 340
  companies, a 90-day window had 3 High matches and 180 days had 5. Adding
  the wider a16z and speedrun portfolio and rung P raised 180 days to 12
  companies with their own Form D (8 on the network, 4 off it); investor SPVs
  add 25 more, 36 distinct companies in all. Full-text search of EDGAR for every portfolio brand
  name over the window found no operating-company Form D that the matcher
  missed. The other hits were SPVs and companies with similar names. So this is
  the base rate, not a matcher that's too strict. Per the design doc's fallback,
  v1 runs a **180-day window** and the header says so. Set
  `JUST_RAISED_WINDOW_DAYS=90` to go back.
- **Many filings report an early first-sale date.** Kalshi's August filing
  reports a first sale in April; OpenRouter's July filing reports one in March.
  Anchoring on first sale, as designed, drops them.
- **Related persons are the best tiebreak.** Several Medium rows listed an
  a16z partner as a director. That became rung P.
- **Why the newest raise is weeks old.** Rule 503 allows 15 days from first
  sale to filing, and many companies file later. Town's first sale was Oct 7
  and its Form D landed Oct 22. A round that closed in the last two or three
  weeks usually isn't on EDGAR yet.
- EDGAR full-text search with `q=*` returns zero hits. Leaving `q` out returns
  every Form D. Items `3C`, `3C.1` and `3C.7` mark funds before any XML is
  fetched.

## Notes on the talent network API

I built this as a client of the [talent network API](https://speedrun-talent-network.com/developers)
and kept notes along the way. It's a good API to build on: the OpenAPI document is accurate,
CORS is open, responses are edge-cached, and the facets on `/jobs` saved a lot of
calls. These are the five things that cost me time, each reproducible with one
line. Counts are from 2026-11-10; the board had 22,985 roles.

```bash
B=https://speedrun-talent-network.com/api/v1
```

**1. `company=` takes the jobs-side display name, case-sensitive, not the slug.**
Every job object carries `company_slug`, and every Company has a `slug`, but the
filter rejects both. It also rejects the name `/companies` returns when the jobs
spell it differently.

```bash
curl -s "$B/jobs?company=Harvey" | jq .total               # 376
curl -s "$B/jobs?company=harvey" | jq .total               # 0
curl -s "$B/jobs?company=anduril-industries" | jq .total   # 0  (the slug)
curl -s "$B/jobs?company=Anduril" | jq .total              # 0  (the name /companies returns)
curl -s "$B/jobs?company=Anduril%20Industries" | jq .total # 2580
```

The board's own surfaces disagree: `/companies` and `/jobs.md` say "Anduril",
the `company` field on `/jobs` says "Anduril Industries". Checking every
portfolio company on 2026-11-10, 20 of 340 return zero rows for
the name `/companies` gives them, which hides 3,320 open roles from the filter.
The jobs spell them differently: "Saronic Technologies", "Mercury
Technologies", "Earnin" (not "EarnIn"), "Chronospace", "Runware (Picfinder)".
Just Raised works around it by searching
`q=<name>`, taking `company` from a job whose `company_slug` matches, and
retrying with that.

**2. Bad parameter values fail silently.** `stealth`, `posted` and `comp_any`
are enums in the OpenAPI document, and the developers page says errors come
back as `{"error":{"code","message"}}` with a matching status. But the server
accepts any value, ignores what it doesn't recognize, and returns 200 with no
warning. Unknown parameters are ignored the same way.

```bash
curl -s "$B/jobs?stealth=true" | jq .total                  # 22985 (stealth=only: 1)
curl -s "$B/jobs?posted=7" | jq .total                      # 22985 (posted=7d: 2284)
curl -s "$B/jobs?portfolio=true" | jq .total                # 0     (portfolio=speedrun: 208)
curl -s "$B/jobs?comp=200000&comp_any=true" | jq .total     # 2962  (comp_any=1: 21343)
curl -s "$B/jobs?company_slug=anduril-industries" | jq .total  # 22985
```

This matters most on the MCP server. An agent that asks for stealth roles with
`stealth=true` gets the whole board back and reports it confidently. A 400
naming the allowed values would fix it.

**3. `/companies` lists only companies with a live role.** A company that stopped
hiring, or hasn't started, disappears, so the API can't describe it. For a list
about companies that just raised and haven't posted yet, that's the exact
company that's missing. Just Raised keeps its own registry of every slug it has
seen (`data/company_registry.json`).

```bash
for p in $(seq 0 7); do curl -s "$B/companies?page=$p"; sleep 1; done \
  | jq -s '[.[].companies[].open_roles] | length, min'   # 778, 1
```

**4. Company has no website or domain.** Its fields are `name`, `slug`, `url`,
`tier`, `cohort`, `location`, `blurb`, `logo`, `labels`, `industries` and
`open_roles`, and `url` points back to the talent network. So every join to an
outside dataset (EDGAR, Crunchbase, LinkedIn) is a fuzzy name match. Most of
this repo's matcher exists because of that. One `domain` field would make
those joins exact.

```bash
curl -s "$B/companies/harvey" | jq '.company | {url, website, domain}'
# {"url": "https://speedrun-talent-network.com/companies/harvey", "website": null, "domain": null}
```

**5. One role in several cities counts as several roles.** Harvey's 376 rows are
235 distinct titles. "Legal Engineer, Product Specialist" appears 8 times, once
each for Madrid, Milan, Munich, Paris, Seoul, Singapore, Stockholm and Sydney.
`open_roles` inherits the inflation, so this page's role counts do too.

```bash
for p in $(seq 0 7); do curl -s "$B/jobs?company=Harvey&page=$p"; sleep 1; done \
  | jq -s '[.[].jobs[].title] | length, (unique | length)'   # 376, 235
```

Smaller things:

- API responses set four site-experiment cookies (`tn_phase2`, `tn_front_door`,
  `tn_hero_variant`, `tn_hero_fill`, 90-day `Max-Age`). An API client has no
  use for A/B assignments.
- `labels` (stage, size) is only on the company detail view, so filtering
  companies by stage is one call per company. The portfolio collections carry
  `stage`, which is the workaround used here.
- `page_size` is accepted but capped at 50 without saying so, and the edge cache
  is `s-maxage=60, stale-while-revalidate=600`.

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
