# Published guestbook entries

Each approved reader note is stored here as one UTF-8 JSON file. Do not add email
addresses, IP addresses, user-agent strings, moderation notes, or other private
submission data. The public browser index at `assets/data/guestbook.json` is built
from these files by `sync_guestbook.py`.

The normal workflow is to approve a human-readable issue in the private moderation
repository and run:

```powershell
python sync_guestbook.py --repo OWNER/PRIVATE_REPOSITORY
```

The script creates the entry file and rebuilds the public index. Nobody needs to
edit JSON by hand. Removing `approved`, or adding `rejected`, removes a previously
published entry on the next sync, so takedowns use the same issue screen. Notes
marked for the author only are never imported, even if they receive `approved` by
mistake.
