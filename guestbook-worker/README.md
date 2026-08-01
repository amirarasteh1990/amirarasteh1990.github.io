# Guestbook intake endpoint

This small Cloudflare Worker accepts the account-free form on `/comments/` and
creates a private GitHub issue for moderation. It is intentionally only an intake
pipe: approved public notes live in the website repository, so a future endpoint
change cannot make the published guestbook disappear.

## Run locally, without Cloudflare

The local adapter runs the exact `worker.mjs` handler at
`http://127.0.0.1:8787/`. When the site is opened on localhost or 127.0.0.1,
`guestbook.js` uses that address automatically if the production endpoint meta is
empty.

In one PowerShell window, from the website repository:

```powershell
$env:GITHUB_TOKEN = gh auth token
$env:GITHUB_OWNER = "amirarasteh1990"
$env:GITHUB_REPO = "arasteh-guestbook-moderation"
$env:ALLOWED_ORIGIN = "http://127.0.0.1:8000"
node guestbook-worker/dev-server.mjs
```

In a second window:

```powershell
python -m http.server 8000 --bind 127.0.0.1
```

Open `http://127.0.0.1:8000/comments/`. The GitHub token stays only in the local
intake process and is never written to a file or sent to the browser.

## One-time setup

1. Create a private GitHub repository for the moderation queue.
2. Add labels named `guestbook`, `pending`, `private`, `shareable`, `approved`,
   `featured`, and `rejected`.
3. Create a fine-grained GitHub token limited to that private repository with
   Issues read/write permission and no Contents permission.
4. Copy `wrangler.toml.example` to `wrangler.toml` and set `GITHUB_REPO`.
5. Store the token as a Worker secret: `npx wrangler secret put GITHUB_TOKEN`.
6. Deploy from this directory with `npx wrangler deploy`.
7. Put the deployed `/` endpoint in the `guestbook-endpoint` meta tag in
   `comments/index.html`.
8. Add a managed rate-limit rule for the Worker route. The form also carries a
   hidden bot field, but the edge rate limit is the durable spam boundary.

The Worker does not collect email, persist IP addresses, or expose its GitHub
credential. It accepts requests only from the configured site origin.

A successful response is returned only after GitHub answers with a created issue
number. The page uses the accompanying `received: true` value to show “Amir has
received your note.” Errors and ambiguous responses never produce a receipt.

Run the mocked intake contract test without network access:

```powershell
node guestbook-worker/test.mjs
```

It checks both audience paths, issue labels, the durable encoded payload, origin
rejection, and that a GitHub response without an issue number cannot create a
false receipt. `python check.py` runs this test automatically.

## Moderation

Read each private issue normally. A note labelled `private` is for the author only
and the sync script refuses to publish it. For a note labelled `shareable`, add
`approved` to publish it on the next sync and optionally add `featured` for the
curated reader-note group. Add `rejected`, or remove `approved`, to unpublish a
previously approved note.

From the website repository, import everything approved and rebuild the public
index:

```powershell
python sync_guestbook.py --repo OWNER/PRIVATE_REPOSITORY
```

Review the ordinary working-tree diff, then use the site's normal author-managed
commit and publish workflow. The sync script never writes to GitHub.
