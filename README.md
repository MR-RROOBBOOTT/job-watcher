# Job Watcher — Network/NOC/Telecom roles → Telegram

Polls the **official public job-board JSON APIs** of Greenhouse/Lever companies
(not scraping — these are the same APIs the companies' own career sites use)
every 30 minutes, filters postings against your profile (network engineer /
NOC / telecom / network automation / SRE-adjacent), and pushes new matches
to your Telegram bot **@Konyismrro_bot**. Runs entirely on GitHub Actions —
no server to maintain, no cost.

## What's in here

- `job_watcher.py` — the checker. Stdlib only, no dependencies to install.
- `config.json` — the list of companies to watch and the keywords to match/exclude.
  Edit this file any time to add companies or tune matching — no code changes needed.
- `seen.json` — state file (which postings have already been notified). The
  workflow commits updates to this automatically. Don't edit by hand.
- `.github/workflows/watch.yml` — the schedule (every 30 min) that runs the checker.

## One-time setup (5 minutes)

1. **Create a new GitHub repo** (private is fine) and push this folder to it:

   ```bash
   cd job-watcher
   git init
   git add .
   git commit -m "Initial job watcher"
   git branch -M main
   git remote add origin https://github.com/<your-username>/job-watcher.git
   git push -u origin main
   ```

2. **Add two repo secrets** (Settings → Secrets and variables → Actions → New repository secret):

   - `TELEGRAM_BOT_TOKEN` — your bot's token from BotFather
   - `TELEGRAM_CHAT_ID` — `8074279326`

3. **Allow the workflow to push.** Settings → Actions → General → Workflow
   permissions → select **"Read and write permissions"** → Save. Without this
   the run succeeds but the `seen.json` commit step fails with a 403, which
   means state never persists and you'd get duplicate alerts every run.

4. That's it. The workflow runs automatically every 30 minutes. You can also
   trigger it manually from the **Actions** tab → "Job Watcher" → "Run workflow"
   to test it immediately instead of waiting.

### Two gotchas worth knowing

- **First run sends nothing.** That's intentional (see "First run behavior"
  below) — it baselines the ~40 currently-open matches so you don't get a wall
  of alerts. Alerts start from the second run onward.
- **GitHub disables scheduled workflows after 60 days of repo inactivity**
  and emails you first. The bot's own `seen.json` commits usually keep it
  alive; if you get that email, just push any commit to reset the clock.

## Getting your Telegram chat ID

1. Open Telegram and send any message (e.g. `/start`) to **@Konyismrro_bot**.
2. Then run this once (replace `<TOKEN>` with your bot token):

   ```bash
   curl -s "https://api.telegram.org/bot<TOKEN>/getUpdates"
   ```

3. Look for `"chat":{"id": 123456789, ...}` in the response — that number is
   your `TELEGRAM_CHAT_ID`.

## How matching works

`config.json` has two keyword lists:

- `include_keywords` — a posting's title must contain at least one of these
  (e.g. "network engineer", "noc", "telecom", "network automation", "site
  reliability engineer") to be considered a match.
- `exclude_keywords` — if the title contains any of these (e.g. "staff",
  "principal", "director", "manager", "intern", "distributed systems"), it's
  filtered out even if it matched an include keyword. This keeps out
  senior/leadership titles and unrelated software-eng roles.

Tune both lists freely — it's just a JSON edit, commit and push, next run
picks it up.

## First run behavior

On the very first run (empty `seen.json`), the watcher **baselines silently**
— it records every currently-open matching posting as "already seen" but
does NOT send a wall of Telegram messages for postings that have been open
for weeks. From the second run onward, only genuinely new postings trigger
a notification. If you'd rather get notified about the current backlog
immediately on first run, set `"notify_on_first_run": true` in `config.json`
before the first run.

## Adding more companies

Add an entry to the `companies` list in `config.json`:

```json
{ "name": "SomeCompany", "board": "greenhouse", "slug": "somecompany" }
```

`board` is `"greenhouse"` or `"lever"`. To find a company's slug, check its
careers page URL — Greenhouse ones look like `boards.greenhouse.io/<slug>` or
`job-boards.greenhouse.io/<slug>`, Lever ones look like `jobs.lever.co/<slug>`.
Not every company uses one of these two ATS platforms (many large telecoms —
Verizon, AT&T, Comcast, T-Mobile — run on Workday, which doesn't expose a
simple public JSON API per-tenant). Those aren't included here; monitoring
them would need a heavier per-site scraper (likely Playwright) rather than
this lightweight JSON-polling approach.

## Currently watched companies

Cloudflare, Twilio, Fastly, Datadog, Netskope, Zscaler, SolarWinds, Kentik,
Samsara, Verkada, Netcracker, PagerDuty, Vonage — chosen because they
consistently post network engineering / NOC / network automation / telecom
infrastructure roles and expose a public Greenhouse API.

## Costs / limits

- GitHub Actions:
  - **Public repo → unlimited free minutes.** Keep the 30-minute cadence.
    Nothing sensitive lives in this repo (the bot token is a GitHub *secret*,
    never in the code), so public is the recommended setup.
  - **Private repo → 2,000 free minutes/month.** GitHub bills each job rounded
    **up to a full minute**, so 30-minute polling ≈ 1,440 min/month — under the
    cap but uncomfortably close. On a private repo, change the cron in
    `.github/workflows/watch.yml` to `"0 * * * *"` (hourly, ≈720 min/month).
- Telegram Bot API: free, no rate-limit concerns at this volume.
- The Greenhouse/Lever APIs used are public, unauthenticated, and intended
  for this kind of use (their own career-site widgets call the same
  endpoints) — no scraping, no ToS risk.
