# Guestbook intake Worker

This Cloudflare Worker gives `/comments/` a one-button, account-free posting
flow. It validates and rate-limits a note, creates a public issue in the website
repository, and returns the canonical entry to the page immediately. The existing
GitHub workflow then writes the permanent JSON entry and rebuilds GitHub Pages.

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

## One-time free-plan deployment

1. While signed in as the repository owner, create a fine-grained GitHub personal
   access token. Limit its repository access to `amirarasteh1990.github.io` and
   grant only **Issues: read and write**. Choose an expiry date and record a
   reminder to rotate it.
2. Create or sign in to a Cloudflare account on the Workers Free plan.
3. Install the pinned development dependency with `npm install` in this directory.
4. Authenticate Wrangler with `npx wrangler login --use-keyring`. On Windows,
   Wrangler installs its keyring helper interactively and keeps the OAuth
   credential in the OS keychain instead of a plaintext file.
5. Store the GitHub token with `npx wrangler secret put GITHUB_TOKEN`.
6. Generate a random rate-limit salt, then store it with
   `npx wrangler secret put RATE_LIMIT_SALT`. Never put either value in this repo.
7. Run `npm test`, then `npm run deploy`.
8. Copy the resulting `https://...workers.dev/` URL into the
   `guestbook-endpoint` meta tag in `comments/index.html`.
9. Bump the guestbook script and service-worker version together, run
   `python check.py --quick`, and let the author commit and push the reviewed files.

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
