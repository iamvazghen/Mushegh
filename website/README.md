# Mushegh documentation site

A [Next.js](https://nextjs.org) (App Router) static documentation site for **Mushegh**.

## Local development

```bash
cd website
npm install
npm run dev      # http://localhost:3000
npm run build    # production build (what Vercel runs)
```

## Deploy to Vercel

The site lives in the `website/` subdirectory of the repo, so point Vercel at it:

**Option A — dashboard (recommended)**
1. Push the repo to GitHub. It currently lives at `iamvazghen/OpenWatari` — the GitHub repo has
   not been renamed to match the package yet; renaming it on GitHub is a one-click change that
   redirects old URLs, and this line should be updated when that happens.
2. In Vercel → **Add New… → Project** → import the repo.
3. Set **Root Directory** = `website`. Framework preset auto-detects **Next.js**.
4. Deploy. You get `https://<project>.vercel.app` (e.g. `https://<your-project>.vercel.app`).

**Option B — CLI**
```bash
npm i -g vercel
vercel --cwd website          # first run links/creates the project (set root dir = ./)
vercel --cwd website --prod   # production deploy
```

No environment variables are needed — the site is fully static content.

## Structure

```
website/
  app/
    layout.tsx          # shared shell + sidebar nav
    globals.css         # styling
    page.tsx            # Overview
    quickstart/         # install + setup wizard
    architecture/       # edge/brain split + memory layers
    networking/         # the Tailnet requirement
    devices/            # all 7 device setups (Mentra, HA, laptop±headphones, phone±headphones, PC control)
    configuration/      # env knobs
    security/           # enforced safety model
    license/            # MIT + third-party + naming
```
