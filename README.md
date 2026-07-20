# Pharma Technology Radar — v1

Weekly digest of emerging pharma/biotech-relevant technologies from labs and
companies worldwide, built on free public sources.

## What's in v1

**Domains monitored** (edit `config.py` to change):
Currently: 
- Basic Search Keywords
        "delivery system", "diagnostic", "biosensor", "noninvasive", "assay", "automation", "setup", "platform", "tool", "technology", "high throughput", "technique"
For Future:
- Drug delivery platforms (mRNA, ASO, LNP, etc.)
- Diagnostics & molecular/cellular detection methods
- Organ/tissue preservation & perfusion devices
- Lab automation & culture/analysis systems

**Sources — working now, no setup needed:**
Currently:
- Europe PMC (publications, worldwide)

For Future:
- bioRxiv / medRxiv (preprints)
- Semantic Scholar (cross-index, with author affiliations)
- NIH RePORTER (US federal grants)
- NSF Award Search (US federal grants)
- UKRI Gateway to Research (UK grants)

## For the Future
**Sources — need a one-time setup step:**
- FWF Austria Open API — request a free key at https://openapi.fwf.ac.at/fwfkey,
  set it as `FWF_API_KEY`. This is the source that catches things like
  SpinCell before they're publicly announced.
- CORDIS (EU Horizon projects) — grab the current bulk CSV export URL from
  https://cordis.europa.eu/projects and paste it into `HORIZON_CSV_URL` in
  `sources/cordis.py`. CORDIS doesn't offer a stable live-query API for
  third parties, so this uses their official monthly bulk export instead.

**Not yet built** (Tier 2/3 from our discussion — added once v1 is running):
- National agencies requiring scraping: Germany (DFG), France (ANR),
  Netherlands (NWO/ZonMw), Sweden, Finland, Belgium, Ireland, Denmark
- Japan (KAKEN), China, Australia, Singapore
- Conference abstracts, industry white papers (no general API/feed exists
  for either — these will likely need a separate targeted-search-agent
  approach rather than a scheduled harvester)

## Setup — running it locally (for testing)

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY="your-key-here"
export FWF_API_KEY="your-fwf-key-here"   # optional, only for Austria source
python main.py
```

Each run writes `output/digest_YYYY-MM-DD.md` and `.csv`, and updates
`state/seen_items.json` so the same project doesn't get re-flagged next week.

**Run it locally at least once before scheduling it** — check the digest
against topics you already know, and confirm nothing's obviously broken.

## Setup — running it weekly on GitHub Actions (recommended)

This runs the pipeline on GitHub's servers on a schedule, so your own
machine doesn't need to be on. It also keeps your API keys out of the code
(stored as encrypted GitHub secrets) and version-controls the whole thing.

1. **Create a new GitHub repo** and push this folder to it:
   ```bash
   cd pharma_tech_radar
   git init
   git add .
   git commit -m "Initial pharma tech radar pipeline"
   git branch -M main
   git remote add origin https://github.com/YOUR_USERNAME/pharma-tech-radar.git
   git push -u origin main
   ```

2. **Add your API keys as repo secrets** (not committed to code):
   Repo page → Settings → Secrets and variables → Actions → New repository secret
   - `ANTHROPIC_API_KEY`
   - `FWF_API_KEY` (optional)

3. **Enable Actions write permissions** so the workflow can commit the
   digest back to the repo each week:
   Repo page → Settings → Actions → General → Workflow permissions →
   "Read and write permissions"

4. **That's it.** The workflow in `.github/workflows/weekly-digest.yml`
   is already configured to run every Monday at 08:00 UTC. It will:
   - Install dependencies
   - Run `main.py`
   - Commit the new `output/` digest and updated `state/` back to the repo
   - Also attach the digest as a downloadable workflow artifact

   To test it immediately without waiting for Monday: go to the repo's
   **Actions** tab → "Weekly Pharma Tech Radar" → **Run workflow**.

5. **Reading the digest**: after each run, the new markdown/CSV files
   appear in the `output/` folder of your repo — GitHub renders markdown
   directly in the browser, so you can just click the file to read it.

### Adjusting the schedule
Edit the `cron` line in `.github/workflows/weekly-digest.yml`. Cron syntax
is `minute hour day month weekday`, always in UTC —
[crontab.guru](https://crontab.guru) is a good sanity-check tool.

## Getting the digest into Medium as a draft

Medium deprecated its publishing API and no longer supports new
integrations, so there's no reliable way to script "create a Medium draft"
directly — third-party tools that try this can silently break. The
officially supported workaround is Medium's own **"Import a story"** tool,
which fetches a public webpage and turns it into a private draft for you
to review. This pipeline is set up to feed that tool automatically:

1. **Enable GitHub Pages** (one-time setup):
   Repo page → Settings → Pages → Source: "Deploy from a branch" →
   Branch: `main`, folder: `/docs` → Save.
   GitHub will give you a URL like `https://YOUR_USERNAME.github.io/pharma-tech-radar/`

2. Each weekly run now also writes a plain HTML version of the digest to
   `docs/digests/YYYY-MM-DD.html`, and rebuilds `docs/index.html` as an
   archive page linking to every digest so far. Both get committed and
   published automatically by the GitHub Action — no extra setup needed
   beyond step 1.

3. **Each week:** open your Pages archive URL, click through to that
   week's digest, copy its URL, and paste it into
   [medium.com/p/import](https://medium.com/p/import). Medium creates a
   private draft from it — review, edit, add tags/images as you like, and
   publish whenever you're ready.

This last step is manual by design — Medium doesn't currently offer any
supported way to skip it. If that changes (their API being un-deprecated,
or a new supported integration path appearing), the natural next step
would be a script that calls it directly from the GitHub Action instead.

## Alternative: Claude Cowork scheduled tasks

Instead of running this code, you could describe the workflow to Claude
Cowork as a recurring task (Cowork → type `/schedule`) and let it search
sources and compile a digest itself each week using its own browsing and
file tools. That's a legitimate lower-setup alternative, but it means
giving up the specific source list, keyword tuning, and two-lens
extraction logic we built here — those would become instructions in a
prompt rather than deterministic code. Worth considering once you've
validated this version and know exactly what you want automated.

## How it works

1. **Harvest** — queries every source with every keyword in `config.py`,
   for items from the last ~9 days (configurable via `LOOKBACK_DAYS`).
2. **Deduplicate** — drops anything matching a previously-seen URL or a
   near-identical title (e.g. the same project appearing first as a grant,
   later as a publication).
3. **Extract** — for each new item, asks the model two separate questions:
   what is this technology, technically, and why might it matter for pharma
   development — inferred even when the source doesn't frame it that way
   (a basic-science paper or an equipment spec sheet can still be
   translationally relevant).
4. **Digest** — writes markdown (quick read) and CSV (sortable/filterable).

## Tuning

- `config.py` → `DOMAINS`: add/remove keyword phrases per domain. Keep
  phrases specific — single broad words return huge noisy result sets.
- `config.py` → `LOOKBACK_DAYS`: widen if you skip a week; keep tight
  otherwise to limit volume.
- `dedup.py` → `TITLE_SIMILARITY_THRESHOLD`: raise if too many distinct
  items are getting merged; lower if duplicates are slipping through.

## Known limitations to keep in mind

- UKRI GtR doesn't expose a clean "date added" field, so it currently
  returns by project start date — dedup state prevents repeat flagging,
  but very old UK projects may appear once on first run.
- Semantic Scholar's free tier is rate-limited; if you see repeated
  `429` messages, add delays or request a (free) API key from Semantic
  Scholar for higher limits.
- The extraction step's `pharma_relevance` field is a model inference, not
  a certainty — treat it as a prioritization aid for your own review, not
  a final verdict on whether something's worth pursuing.
