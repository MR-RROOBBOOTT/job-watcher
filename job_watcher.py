#!/usr/bin/env python3
"""
Job posting watcher for Ravi Teja Koneru.

Polls public, official job-board JSON APIs (Greenhouse / Lever) for a
configured list of companies, filters postings by keyword against a
network/telecom/NOC-engineering profile, and pushes new matches to
Telegram. Designed to run unattended on a schedule (GitHub Actions cron).

State (which job IDs have already been seen/notified) is kept in seen.json
next to this script, so re-runs never re-notify the same posting.

Env vars required:
  TELEGRAM_BOT_TOKEN
  TELEGRAM_CHAT_ID

Config (companies, keywords) lives in config.json next to this script.
"""

import json
import os
import sys
import time
import urllib.request
import urllib.error

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(SCRIPT_DIR, "config.json")
SEEN_PATH = os.path.join(SCRIPT_DIR, "seen.json")

TIMEOUT = 15
USER_AGENT = "job-watcher/1.0 (personal automation; contact via telegram)"


def http_get_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_greenhouse(slug):
    """Official public Greenhouse job board API."""
    url = f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"
    data = http_get_json(url)
    jobs = []
    for j in data.get("jobs", []):
        jobs.append({
            "id": str(j.get("id")),
            "title": j.get("title", ""),
            "location": (j.get("location") or {}).get("name", ""),
            "url": j.get("absolute_url", ""),
        })
    return jobs


def fetch_lever(slug):
    """Official public Lever job board API."""
    url = f"https://api.lever.co/v0/postings/{slug}?mode=json"
    data = http_get_json(url)
    jobs = []
    for j in data:
        jobs.append({
            "id": str(j.get("id")),
            "title": j.get("text", ""),
            "location": (j.get("categories") or {}).get("location", ""),
            "url": j.get("hostedUrl", ""),
        })
    return jobs


FETCHERS = {
    "greenhouse": fetch_greenhouse,
    "lever": fetch_lever,
}


def matches(title, include_keywords, exclude_keywords):
    t = title.lower()
    if any(bad in t for bad in exclude_keywords):
        return False
    return any(good in t for good in include_keywords)


def load_json(path, default):
    if not os.path.exists(path):
        return default
    with open(path, "r") as f:
        return json.load(f)


def save_json(path, obj):
    with open(path, "w") as f:
        json.dump(obj, f, indent=2, sort_keys=True)


def send_telegram(token, chat_id, text):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = json.dumps({
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }).encode("utf-8")
    req = urllib.request.Request(
        url, data=payload,
        headers={"Content-Type": "application/json", "User-Agent": USER_AGENT},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        print(f"  ! Telegram send failed: {e.code} {e.read().decode('utf-8', 'ignore')}", file=sys.stderr)
        return None


def main():
    config = load_json(CONFIG_PATH, {})
    seen = set(load_json(SEEN_PATH, []))
    first_run = len(seen) == 0

    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print("ERROR: TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID env vars not set.", file=sys.stderr)
        sys.exit(1)

    include_kw = [k.lower() for k in config.get("include_keywords", [])]
    exclude_kw = [k.lower() for k in config.get("exclude_keywords", [])]
    notify_on_first_run = config.get("notify_on_first_run", False)
    max_notifs = config.get("max_notifications_per_run", 15)

    new_matches = []
    total_checked = 0
    errors = []

    for company in config.get("companies", []):
        fetcher = FETCHERS.get(company.get("board"))
        if not fetcher:
            errors.append(f"{company.get('name')}: unknown board type {company.get('board')}")
            continue
        try:
            jobs = fetcher(company["slug"])
        except Exception as e:
            errors.append(f"{company.get('name')}: fetch failed ({e})")
            continue

        total_checked += len(jobs)
        for job in jobs:
            if not matches(job["title"], include_kw, exclude_kw):
                continue
            uid = f"{company['name']}:{job['id']}"
            if uid in seen:
                continue
            new_matches.append({
                "uid": uid,
                "company": company["name"],
                "title": job["title"],
                "location": job["location"],
                "url": job["url"],
            })

    print(f"Checked {total_checked} postings across {len(config.get('companies', []))} companies.")
    print(f"New matching postings this run: {len(new_matches)}")
    if errors:
        print("Errors:")
        for e in errors:
            print(f"  - {e}")

    if first_run and not notify_on_first_run:
        # Baseline silently so we don't blast dozens of historical postings at once.
        for m in new_matches:
            seen.add(m["uid"])
        save_json(SEEN_PATH, sorted(seen))
        print(f"First run: baselined {len(new_matches)} existing postings without notifying. "
              f"Future new postings will trigger Telegram alerts.")
        return

    sent = 0
    for m in new_matches:
        if sent >= max_notifs:
            print(f"Hit max_notifications_per_run ({max_notifs}); remaining matches will notify next run.")
            break
        text = (
            f"🟢 <b>New match: {m['title']}</b>\n"
            f"Company: {m['company']}\n"
            f"Location: {m['location'] or 'n/a'}\n"
            f"{m['url']}"
        )
        result = send_telegram(token, chat_id, text)
        seen.add(m["uid"])  # mark seen regardless, so a Telegram outage doesn't cause infinite retries
        if result and result.get("ok"):
            sent += 1
            print(f"  -> notified: {m['company']} | {m['title']}")
        time.sleep(0.5)  # be gentle on Telegram's rate limits

    save_json(SEEN_PATH, sorted(seen))
    print(f"Done. Sent {sent} Telegram notifications.")


if __name__ == "__main__":
    main()
