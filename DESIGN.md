# Design

Light and restrained, with one loud move: the page title set like an anime
title card, in heavy serif capitals compressed narrow. An orange rule and
orange money figures carry structure. Everything else is a plain working list.
Filters, search, sort and expandable rows are ordinary web controls.

## Palette (`app/globals.css` `:root`)

| Token | Value | Job |
|---|---|---|
| `--ground` | `#f5f5f3` | Page background (neutral, not cream) |
| `--panel` / `--hover` | `#ffffff` / `#ececea` | Inputs; hovered and open rows |
| `--ink` / `--ink-2` / `--dim` | `#0a0a0a` / `#34342f` / `#66665f` | Primary, body, secondary text (all ≥ 4.5:1) |
| `--rule` / `--rule-strong` | `#dcdcd7` / `#b4b4ad` | Hairlines, control borders |
| `--signal` | `#ff6200` | Fills and rules only: hero rule, active filter, section rule |
| `--signal-ink` | `#bf3d00` | Orange as text: links, the company's own Form D money |
| `--go` / `--go-text` | `#8cf03c` / `#2c7408` | Early window chip / early window text |
| `--unit` | `#6234e0` | speedrun tier only |

Colour always means something. Orange money is the company's own Form D, and
black money is investor SPVs (the weaker signal). Green is the early window.
Bright `--signal` fails text contrast on the light ground, so never use it for text.

## Type

- **Display:** Noto Serif JP 900 (`--font-display`, via `next/font`), used for
  its heavy Latin capitals. It sets the title, company names, the section
  heading and step titles.
- **UI:** Archivo with its width axis (`--font-ui`). Body text at normal
  width. Labels, figures and controls are condensed (`font-stretch: 70%`),
  uppercase, with tabular numerals.
- No monospace. All copy is English.

## Signature move

The title is `TitleCard` in `app/page.tsx`. "JUST RAISED" sits on one line,
compressed in SVG (`textLength`, `lengthAdjust="spacingAndGlyphs"`). It cuts
in once on load. Nothing else animates, apart from hover colour changes and
the row chevron, and reduced motion turns both the cut-in and the transitions
off.

## Layout

- Feed rows, not cards. Rows are separated by hairlines, and the column
  header row uses the same five-column grid. Below 820px each row stacks:
  logo, then name and blurb, then money, then roles.
- Square corners. No shadows, gradients, glows or rounded pills.
- No eyebrow labels above headings. Metadata lives in the hero readout.
- Keep it to one move. Earlier passes with hazard stripes and Japanese
  labels were too much.
