# Design

The page reads like a command-center title card: a black field, heavy mincho
lettering, and an orange that carries structure. It is still a working list.
Filters, search, sort and expandable rows are ordinary web controls; the
world supplies type, palette, density and one signature move, nothing else.

## Palette (`app/globals.css` `:root`)

| Token | Value | Job |
|---|---|---|
| `--void` | `#050505` | Ground |
| `--panel` / `--hover` | `#0d0b09` / `#110d0a` | Inputs, hovered and open rows |
| `--ink` / `--ink-2` / `--dim` | `#f2ede4` / `#cfc8bc` / `#9a9284` | Primary, body, secondary text (all ≥ 4.5:1 on void) |
| `--rule` / `--rule-strong` | `#24201c` / `#3d3630` | Hairlines, control borders |
| `--signal` | `#ff7a1a` | Structure rules, links, active filter, the company's own Form D money |
| `--go` | `#8cf03c` | Early window only |
| `--unit` | `#a684ff` | speedrun tier only |
| `--plate` | `#ece6da` | Logo plate, so dark marks stay visible |

Colour means something every time it appears: orange money is a company's own
Form D, ink money is investor SPVs (the weaker signal), green is the early
window. Don't add accents for decoration.

## Type

- **Display:** Noto Serif JP 900 (`--font-display`), via `next/font`. Company
  names, section headings, the Japanese labels.
- **UI:** Archivo with its width axis (`--font-ui`). Body at normal width;
  labels, figures and controls condensed (`font-stretch: 70%`), uppercase,
  tabular numerals.
- No monospace. Numbers get condensed Archivo, not a code face.

## Signature move

The title card: "JUST / RAISED" set in the display face and compressed to 70%
width in SVG (`TitleCard` in `app/page.tsx`, `textLength` with
`lengthAdjust="spacingAndGlyphs"`), with a vertical Japanese subtitle beside it.
It cuts in once on load (clip-path), and the orange rule under the hero
draws in from the left. That is the page's only animation; reduced motion
turns it off.

Japanese words are decorative translations (`資金調達` fundraising, `仕組み`
how it works, `早期` early), always `lang="ja"` and `aria-hidden`.

## Layout

- Hazard strip (8px orange/black stripes) at the very top, nowhere else.
- Feed rows, not cards: hairline-separated, a shared five-column grid that the
  column header row also uses. Below 820px, rows stack into logo / who /
  money / roles.
- Square corners everywhere. No shadows, glows, gradients or rounded pills.
- No eyebrow labels above headings; metadata lives in the hero readout.

## Don't

No fan-franchise logos, names, characters or insignia. The look borrows a
genre of screen typography, not anyone's marks.
