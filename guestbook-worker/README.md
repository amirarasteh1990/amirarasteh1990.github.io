# Guestbook intake Worker

This Cloudflare Worker gives `/comments/` a one-button, account-free posting
flow. It validates and rate-limits a note, creates a public issue in the website
repository, and returns the canonical entry to the page immediately. The existing
GitHub workflow then writes the permanent JSON entry and rebuilds GitHub Pages.

It also serves the native-speaker check pages (`/sedaha/check/<slug>/`, written by
`build_check_pages.py`). `POST /check` takes
`{lang, page_version, name?, items: [{id, verdict: "ok"|"change"|"unsure", note?}]}`
(1 to 40 answers, name up to 60 and notes up to 600 characters), with the same
origin check, rate limiter and validation, and opens one issue titled
`Native check: <Language> (<n> answers)`, labelled `native-check`, whose body
starts with `<!-- native-check:v1 -->`. It never carries the guestbook marker or
labels, so `publish-guestbook.yml` ignores it (`npm test` reads that workflow's
conditions to prove it). The issue is opened with Amir's own token, and GitHub
does not notify anyone of their own actions: find the answers under the
`native-check` label. **The route exists only after a redeploy:** run `npm test`, then `npm run deploy`.
Until then the check pages fall back to a prefilled email.

The browser never receives a GitHub credential. The Worker token needs only
**Issues: read and write** on `amirarasteh1990/amirarasteh1990.github.io`. It must
not receive Contents, Actions, Administration, or account-wide repository access.

## Local verification without external writes

Run the contract test:

```powershell
Set-Location guestbook-worker
npm test
```

Run a mocked intake endpoint:

```powershell
$env:MOCK_GITHUB = "1"
npm run dev
```

In another terminal, serve the website root:

```powershell
python -m http.server 8000 --bind 127.0.0.1
```

Open `http://127.0.0.1:8000/comments/`. On localhost, the page automatically uses
`http://127.0.0.1:8787/`. Mock mode never contacts GitHub or creates an issue.

## Production deployment

The production Worker is deployed on the Cloudflare Workers Free plan at:

`https://arasteh-guestbook.amir-arasteh.workers.dev/`

The account uses encrypted Wrangler keyring authentication. `GITHUB_TOKEN` and
`RATE_LIMIT_SALT` are stored as Cloudflare secrets, and preview URLs are disabled.
The website origin is restricted to `https://arasteh.art`.

The one-time setup used these boundaries:

1. While signed in as the repository owner, create a fine-grained GitHub personal
   access token. Limit its repository access to `amirarasteh1990.github.io` and
   grant only **Issues: read and write**. Choose an expiry date and record a
   reminder to rotate it.
2. Create or sign in to a Cloudflare account on the Workers Free plan.
3. Install the pinned development dependency with `npm install` in this directory.
4. Authenticate Wrangler with `npx wrangler login --use-keyring`. On Windows,
   Wrangler installs its keyring helper interactively and keeps the OAuth
   credential in the OS keychain instead of a plaintext file.
5. Store `GITHUB_TOKEN` and `RATE_LIMIT_SALT` as Cloudflare secrets. Never put
   either value in this repo.
6. Run `npm test`, then `npm run deploy`.
7. Put the deployed URL in the `guestbook-endpoint` meta tag, bump the guestbook
   script and service-worker version together, and run `python check.py --quick`.

For a future code deployment, run `npm test` and then `npm run deploy`. To rotate
the GitHub credential, run `npx wrangler secret put GITHUB_TOKEN` and enter the
replacement only at Wrangler's hidden prompt.

The rate-limit binding allows three accepted attempts per source address per
minute. Its key is a SHA-256 digest salted with `RATE_LIMIT_SALT`; this code does
not persist or log the raw address. The hidden website field rejects simple form
bots before GitHub is contacted.

The first valid submission also causes the GitHub workflow to create any missing
guestbook moderation labels. The workflow recognizes that first issue by the
repository-owner identity attached to the fine-grained token and the validated
versioned guestbook marker, so a visitor cannot activate it by opening an issue
directly on GitHub.

If the GitHub token expires, is revoked, or GitHub rejects a request, the Worker
fails closed and the page does not claim that the note was posted.

## Downloads (`/dl/`) and who makes them

Every download button on arasteh.art points at
`https://arasteh-guestbook.amir-arasteh.workers.dev/dl/<release>/<file>`
(`books`, `paintings`, `first-edition-1.0`; plain file names only, so the route can
never redirect anywhere else). The Worker stores one event in the `DOWNLOADS` KV
namespace, then answers `302` to the GitHub release asset, which GitHub still counts
(`download_counts.py`, `show downloads`).

An event holds the time, the file, the country, the network owner (e.g. "Google LLC"),
whether the client is a browser or a bot, its user agent (cut to 160 characters) and
the site the click came from. It never holds an IP address, and it expires after 400
days. Recording happens after the redirect is sent, so a full or missing store never
blocks a download. The free plan allows 1,000 recorded downloads a day; past that
the downloads still work and only the record is skipped.

`GET /dl-stats?day=YYYY-MM-DD` returns one day's events to whoever presents the
`STATS_KEY` secret as a Bearer token. `python download_log.py` (repo root) reads it.

One-time setup, from this directory, signed in to the guestbook's Cloudflare account
(amirarasteh1990@gmail.com):

    npx wrangler kv namespace create sedaha-downloads --binding DOWNLOADS --update-config
    python ..\download_log.py --setup
    npm test
    npm run deploy

Deploy before pushing a site whose links point at `/dl/`: until then those links 404.
