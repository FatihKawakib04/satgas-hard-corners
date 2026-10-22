# SATGAS — Hard Corners

A single-page marketing site for **SATGAS**, a creative unit in Central Jakarta
assembled for one mission: brand, websites, film, content, AI, and spatial
signage. Brief in, unit assembled, mission executed, task force disbanded.

Neo-brutalist art direction: 3px structural borders, hard corners, flat
surfaces, one lime accent with a single orange state pop. Built with
**Astro** (static output) and **Tailwind CSS v4**, served as plain HTML by
nginx — no runtime, no server process.

## Stack

| Layer      | Choice                                        |
| ---------- | --------------------------------------------- |
| Framework  | [Astro](https://astro.build) `^7.3.8` (static) |
| Styling    | [Tailwind CSS](https://tailwindcss.com) v4 via `@tailwindcss/vite` |
| Type       | Archivo (variable weights 400–900), Google Fonts |
| Output     | Static `dist/` — HTML, CSS, JS, images        |

No UI framework, no client router. Interactivity is a handful of small
inline `<script>` blocks (mobile nav, project dialog, case filter, form
validation + mailto hand-off).

## Getting started

Requires **Node.js 18+** (developed on v22).

```bash
npm install     # install dependencies
npm run dev     # dev server with HMR → http://localhost:4321
npm run build   # emit static site to dist/
npm run preview # serve the built dist/ locally
```

## Project structure

```
.
├── astro.config.mjs        # static output, _assets/, lightningcss minify
├── public/
│   └── assets/             # images + credits.json (third-party photo credits)
└── src/
    ├── layouts/
    │   └── Layout.astro    # <head>, meta/OG tags, skip link, reveal-on-scroll
    ├── pages/
    │   └── index.astro     # the one page: composes the sections
    ├── components/
    │   ├── Navbar.astro        # sticky header + mobile menu
    │   ├── Hero.astro          # stacked wordmark, ticker, key facts
    │   ├── CaseStudies.astro   # mission cards, filter chips, detail dialog
    │   ├── Services.astro      # six disciplines
    │   ├── Team.astro          # crew roster
    │   ├── Contact.astro       # inquiry form + unit builder
    │   └── Footer.astro        # HQ, pages, capabilities, contact, credits
    ├── data/
    │   └── site.ts         # ← single source of truth for all page content
    └── styles/
        └── global.css      # Tailwind v4 @theme tokens + component primitives
```

## Editing content

Almost all copy lives in **`src/data/site.ts`**: navigation, ticker,
key facts, projects, services, crew, disciplines, budget tiers, and office
details. Change it there and every component picks it up. Components hold
only layout plus a few short inline strings (headings, button labels).

> **Note:** project titles, crew names, and the address are placeholders for
> the client to confirm before launch. There is deliberately no invented
> proof — no client logos, no testimonials, no unverifiable statistics.

## Design tokens

Defined once in `src/styles/global.css` under `@theme`:

- **Ground / ink** — `cream`, `cream-2`, `zinc-deep`, `zinc-mid`, `ink`, `paper`
- **Accents** — `lime` (`#c8f436`), `orange` (`#ff5c1a`)
- **Type** — `--font-display: "Archivo"`
- **Structure** — `--border-w: 3px`
- Reusable primitives: `.shell`, `.badge`, `.btn`, `.chip`, `.tag`, `.field`, `.card`, `.dialog`, `.ticker`

## Deployment

`astro.config.mjs` sets `output: "static"` and writes to `dist/`. The site is
served directly by nginx from the build directory; the Cloudflare Tunnel
(`cloudflared`) fronts it, so nginx only ever listens on `localhost:80`.

Typical server layout:

```
/var/www/satgas-hard-corners/
└── site/
    └── dist/          ← nginx `root` points here
```

After content changes:

```bash
npm run build          # regenerate dist/
nginx -t               # validate config
systemctl reload nginx # only needed if nginx config changed
```

## Licensing & credits

Third-party photographs are documented in `public/assets/credits.json` with
creator, source, and licence. See the footer for the human-readable summary.
Each photo shows the world *around* SATGAS — none is client work.
