# FlyNews — AJet intelligence digest

A small scheduled Python job that collects aviation and technology RSS news, evaluates
its potential value for AJet with Gemini, and publishes a concise **Turkish** daily digest
to a Telegram channel. It prioritizes useful developments in airline operations,
competitors, AI, customer experience, commercial systems, infrastructure and regulation.
It selects up to eight strong stories by default, and fewer when the evidence is weak.
There is no conversational bot, server, dashboard or paid database.

```text
RSS / Google News search feeds
  → normalize metadata and UTC timestamps
  → last 24 hours (exclude future/undated entries)
  → URL + conservative title clustering
  → previous-history check + cheap keyword filtering
  → capped Gemini batches + per-article JSON validation
  → Python weighted scoring + light category diversity
  → Turkish HTML digest split between complete items
  → SQLite outbox → Telegram channel
```

## Repository

```text
FlyNews/
├── .github/workflows/
│   ├── daily_news.yml
│   └── tests.yml
├── data/.gitkeep
├── src/
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   ├── models.py
│   ├── collector.py
│   ├── feeds.py
│   ├── filters.py
│   ├── deduplication.py
│   ├── ai_analyzer.py
│   ├── scoring.py
│   ├── formatter.py
│   ├── telegram_publisher.py
│   ├── database.py
│   ├── demo.py
│   └── utils.py
├── tests/
│   ├── conftest.py
│   ├── test_collection.py
│   ├── test_deduplication.py
│   ├── test_ai_analyzer.py
│   ├── test_scoring.py
│   ├── test_formatter.py
│   ├── test_publishing_state.py
│   ├── test_preview_report.py
│   └── test_pipeline.py
├── scripts/write_preview_report.py
├── .env.example
├── .gitignore
├── pyproject.toml
├── requirements.txt
├── requirements-dev.txt
└── README.md
```

## Local setup

Requires **Python 3.12+** and macOS or Linux (local state locking uses `fcntl`).
From the repository directory:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
cp .env.example .env
```

1. In Telegram, open [@BotFather](https://t.me/BotFather), use `/newbot`, and copy the bot token.
2. Create the target Telegram channel.
3. Add the bot as a channel administrator with permission to **post messages**.
4. For a public channel set `TELEGRAM_CHAT_ID=@your_channel`. For a private channel,
   add the bot and post a channel message, then inspect `channel_post.chat.id` in
   [getUpdates](https://core.telegram.org/bots/api#getupdates) using a local authenticated
   request. Use the full numeric ID, usually beginning `-100`; do not guess it. This app
   never polls for updates and does not need a webhook.
5. Create a Gemini key in [Google AI Studio](https://aistudio.google.com/apikey).
6. Edit `.env` with the values below. The supplied example defaults to `DRY_RUN=true`.

```dotenv
GEMINI_API_KEY=your_actual_key
GEMINI_MODEL=gemini-3.1-flash-lite
TELEGRAM_BOT_TOKEN=your_actual_token
TELEGRAM_CHAT_ID=@your_channel
```

These four values are required for publishing. A real dry run requires only
`GEMINI_API_KEY` and `GEMINI_MODEL`. The application requires an explicit model identifier;
the example and workflow suggest
[Gemini 3.1 Flash-Lite](https://ai.google.dev/gemini-api/docs/models/gemini-3.1-flash-lite),
a stable model supporting structured extraction as checked on 7 October 2026. Change the
model when needed. No Google SDK is required: requests uses the official REST API and
[structured JSON output](https://ai.google.dev/gemini-api/docs/generate-content/structured-output).

Never commit `.env`, tokens or generated state. Production logs suppress raw HTTP errors,
model responses and validation input values to avoid exposing credentials.

## Preview and tests without publishing

An offline demonstration needs no credentials or network and labels every message as
fictional. It exercises scoring and formatting, rather than pretending to perform AI analysis:

```bash
python -m src.main --demo --dry-run
```

A real preview collects current RSS and calls Gemini, prints Telegram HTML, and makes no
Telegram requests. It uses an in-memory database and neither reads nor changes production
history, so already-published stories may appear in the preview. Gemini quota still applies.

```bash
python -m src.main --dry-run
python -m src.main --dry-run --hours 24 --limit 10
python -m pytest -q
ruff check src tests
ruff format --check src tests
```

Tests mock external services and cover timestamps, RSS/Atom normalization, bad feeds,
title clustering, keyword boundaries, scoring, strict AI validation and partial batch
recovery, HTML escaping, message boundaries, retry behavior, persisted partial publication,
uncertain sends, an end-to-end pipeline and safe dry runs. Tests never send Telegram posts.

To publish locally after reviewing a preview:

```bash
DRY_RUN=false python -m src.main
```

## Production with GitHub Actions

Push this repository to GitHub. Under **Settings → Secrets and variables → Actions**,
add these repository **secrets**:

- `GEMINI_API_KEY`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

Optionally add repository **variable** `GEMINI_MODEL` to override the workflow suggestion.
Ensure Actions is enabled and `daily_news.yml` is on the default branch. The workflow
publishes every morning at **05:00 UTC / 08:00 Europe/Istanbul**. Edit its cron expression
to change the schedule. GitHub schedules can be delayed, and scheduled workflows in
inactive public repositories may be disabled; this is not a precise-time SLA.
[GitHub scheduled-workflow documentation](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule).

For a manual run: **Actions → Daily AJet intelligence → Run workflow → choose the default
branch**. Choose `dry-run` first to preview, then `publish` to send. Scheduled runs always
use `publish`. Maintenance operations are described below. Non-default branches are
skipped. The separate Tests workflow runs on pushes and pull requests without secrets.
The application is implemented locally; deployment and real publishing require your
GitHub repository, API credentials and channel configuration.

After a `dry-run`, its **Summary** page includes a **FlyNews deneme çıktısı** section
with the preview and diagnostic output. You can also download the `digest-preview-…`
artifact from that page and open `digest-preview.txt`. These remain available even when
GitHub's expandable job-log viewer fails to load. The reporting step runs on successful
and failed dry runs, preserves the original job failure, escapes HTML, and redacts the
configured credentials before writing the summary or artifact. Preview artifacts expire
after seven days. An empty digest is shown in the output rather than implying that stories
were published.

Default cost controls are 40 candidates, batches of eight, at most ten output stories,
2,400 description characters per AI input, and 15 seconds between AI requests. Missing
or malformed analyses receive one correction attempt; temporary API errors get bounded
transport retries. Free-tier availability and quotas depend on your account and model;
check [Gemini rate limits](https://ai.google.dev/gemini-api/docs/rate-limits) and
[GitHub Actions billing](https://docs.github.com/en/billing/concepts/product-billing/github-actions)
instead of assuming unlimited free execution.

Gemini requests use `generationConfig.responseMimeType` and `responseJsonSchema` on
the REST `generateContent` endpoint. A permanent request, key or model rejection
(HTTP 400/401/402/403/404) stops promptly rather than repeating the same failure for all
batches. Logs include fixed diagnostic hints for invalid/blocked keys, permissions and
schema problems; provider response bodies and credentials are never printed. Temporary
batch failures and malformed individual analyses still use the normal recovery behavior.
`GEMINI_TIMEOUT_SECONDS` defaults to 60 seconds per response read; RSS and Telegram
keep their separate 30-second `HTTP_TIMEOUT_SECONDS`. Transport retries are bounded,
and logs distinguish timeouts from connection failures without exposing exception text.

After analysis, a second duplicate check compares factual Turkish titles/summaries.
Named organization/product launch reports with the same use context can be clustered
within 36 hours even when original headlines differ. Numbered announcements, rollout
stages, cancellation events and refund/baggage/loyalty features remain separate.
Proposed AJet uses never participate in event matching. This check also compares sent
history, so a newly analyzed paraphrase of an already published event is suppressed.

## Persistent state and recovery

This MVP chooses **Option A: GitHub Actions cache**, plus a 30-day downloadable artifact
snapshot. It never commits generated state to the main branch. Each production or
maintenance run restores the newest `flynews-state-v1-` cache and saves a new immutable
key containing its run ID and attempt, **even if the Python job fails**. Workflow
concurrency serializes runs; local jobs lock the database. Keep one publishing workflow
and one database per destination channel. Changing the channel on an existing state file
fails explicitly; use a new database/cache namespace for a different destination.

SQLite keeps validated analyses, selection history and sent timestamps. Failed AI items
remain eligible for future runs. Unselected, validated items can reuse analysis if they
are still fresh. History is pruned after 30 days by default, excluding unfinished posts.
Previously processed URL and similar-title checks reduce repeat work and posting.

**Cache persistence is best effort.** GitHub can evict caches; interrupted/cancelled runners
may not save the newest checkpoint, and cache writes can fail. The workflow warns on a
missing cache. Artifact snapshots are recovery backups, not an automatic restore source.
Cross-run duplicate protection depends on retaining the database; there is no exactly-once
guarantee across cache loss or the Telegram/network boundary. See
[GitHub cache behavior](https://docs.github.com/en/actions/using-workflows/caching-dependencies-to-speed-up-workflows).
For a recovery backup, download `flynews-state-…` from the affected run, extract `news.db`
to local `data/news.db`, inspect/reconcile it, and re-seed the Actions cache through your
own recovery workflow before restarting production. Do not mix a local database and an
independently advancing Actions database when posting to the same channel.

Telegram has no idempotency key for `sendMessage`. Each complete digest message is saved
to an outbox, then marked `sending` before the HTTP request. Confirmed messages are marked
`sent` with their Telegram ID, and won't be resent. Known rejections remain `pending`;
429 responses honor `retry_after` within the run budget. Connection-establishment timeouts
are retried. Read timeouts, disconnected responses and server errors are treated as
**uncertain**, because Telegram might have accepted the message. An interrupted `sending`
state is equally ambiguous. Publication pauses until a human checks the channel.

Locally, inspect the saved message text and ID:

```bash
python -m src.main --outbox-status
# After confirming that the message IS in the channel:
python -m src.main --resolve-message FULL_OUTBOX_ID --resolution sent
# After confirming that the message is NOT in the channel:
python -m src.main --resolve-message FULL_OUTBOX_ID --resolution retry
DRY_RUN=false python -m src.main
```

You can optionally supply `--telegram-message-id 123` with `--resolution sent`.
For Actions state, use **Run workflow → outbox-status**, inspect its log and the actual
channel, then use `mark-sent` or `retry-message` with the full outbox ID. Each maintenance
run persists the corrected database. Finally run `publish`. A resumed digest finishes its
existing messages and ends that invocation; it doesn't generate another digest in the
same recovery run. Never mark a message for retry solely because a workflow failed.

## Sources and filtering

Edit `SOURCES` in `src/feeds.py`. Lower priority numbers win within a duplicate cluster:

```python
NewsSource(
    name="Verified official feed",
    url="https://your-verified-domain.example/rss",  # Replace with a real, tested RSS URL.
    category="aviation",  # or technology
    priority=1,
)
# Google News search discovery:
google_news("Airline payments", 'airline (payments OR fraud OR retailing)')
```

The shipped direct feeds (AirlineGeeks, TechCrunch, Ars Technica) and Google News RSS
endpoint were fetched and verified as RSS on 7 October 2026. Queries cover Türkiye
competitors, European and global benchmark airlines, digital systems, operations,
industry organizations and vendors. No guessed FlightGlobal, airline or regulator RSS
URLs are enabled; add official feeds only after verifying them. Google News preserves
the supplied original publisher attribution and aggregation link, without brittle link
decoding or scraping. The feed query's `when:1d` is supplemental; Python's configured
time window is authoritative, but increasing `--hours` also requires widening that query
if you want older Google News results.

Titles and descriptions are converted from HTML to plain text. RSS responses are bounded
to 5 MB and 200 entries per feed. Publication time takes precedence over update time;
undated items are skipped. `RELEVANT_KEYWORDS` and `EXCLUDED_TITLE_PHRASES` are editable.
Technology and aviation candidates alternate before the AI cap, reducing source starvation.
There is no full-body scraping. Gemini must reject entries too thin to support analysis.

## Scoring and configuration

All settings are environment variables; see `.env.example` for defaults. CLI `--hours`,
`--limit` and `--dry-run` override their corresponding settings. `--dry-run` always prevents
publication, even when `DRY_RUN=false`.

```text
final_score = relevance × 0.35 + impact × 0.25 + novelty × 0.15
            + feasibility × 0.15 + urgency × 0.10
```

Change `WEIGHT_AJET_RELEVANCE`, `WEIGHT_BUSINESS_IMPACT`, `WEIGHT_NOVELTY`,
`WEIGHT_FEASIBILITY`, and `WEIGHT_URGENCY` together; weights must sum to one.
`MIN_RELEVANCE_SCORE=6` and `MIN_FINAL_SCORE=6.5` are independent gates in addition to
Gemini's `relevant` flag. Category diversity favors a new category only within
`DIVERSITY_SCORE_GAP=0.6` of the strongest remaining article. No quota is filled with
below-threshold stories. No qualifying stories means no Telegram post. A total feed
failure or complete AI failure on new candidates exits nonzero instead of silently
reporting an empty successful digest; one failed feed or batch doesn't discard the rest.

## Assumptions and limitations

- AJet context is generic airline applicability; no confidential roadmap, systems,
  strategy or implementation claims have been supplied.
- Summaries and AJet interpretations are Turkish; category keys remain stable English
  identifiers internally. Facts and proposed uses occupy separate labeled sections.
- JSON validation bounds scores, categories and text sizes. The prompt prohibits
  fabricated facts and treats RSS as untrusted data; schema validation cannot prove
  factual correctness. This is an intelligence aid, not an authoritative corporate
  recommendation system. Review initial previews and monitor actual output quality.
- RSS coverage and summary quality vary. Google News often supplies headline-level
  detail, some links lead to paywalls, and semantically equivalent headlines can evade
  conservative text deduplication. Entity/number guards reduce mistaken clustering.
- Telegram HTML is escaped and messages stay within its 4,096-character limit, counting
  rendered UTF-16 units conservatively. A news item is never split midway. See the
  [official sendMessage API](https://core.telegram.org/bots/api#sendmessage).
- Scheduled execution, caches, artifacts and API free quotas are operational dependencies.
  This repository supplies the implementation, not an already-deployed channel service.
