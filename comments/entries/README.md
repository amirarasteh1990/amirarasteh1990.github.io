# Published guestbook entries

Each published reader note is stored here as one UTF-8 JSON file. Do not add email
addresses, IP addresses, user-agent strings, moderation notes, or other private
submission data. The public browser index at `assets/data/guestbook.json` is built
from these files by `sync_guestbook.py`.

The account-free page sends a note to the Cloudflare Worker, which creates a
human-readable guestbook issue in the public website repository using an
issue-only credential. `.github/workflows/publish-guestbook.yml` validates and
publishes the new note with:

```powershell
python sync_guestbook.py --repo amirarasteh1990/amirarasteh1990.github.io --issue NUMBER --new-submission
```

The script creates the entry file and rebuilds the public index. The workflow
validates the result, normalizes its labels, assigns it to Amir for notification,
and commits only this directory and the compact index. Nobody needs to edit JSON
by hand. Adding `rejected` removes a published entry on the next sync; removing
`rejected` restores it. All submissions and moderation issues are public; there is
no private-note mode.
