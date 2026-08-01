# Published guestbook entries

Each approved reader note is stored here as one UTF-8 JSON file. Do not add email
addresses, IP addresses, user-agent strings, moderation notes, or other private
submission data. The public browser index at `assets/data/guestbook.json` is built
from these files by `sync_guestbook.py`.

The normal workflow is to add `approved` to a human-readable guestbook issue in
the public website repository. `.github/workflows/publish-guestbook.yml` then runs:

```powershell
python sync_guestbook.py --repo amirarasteh1990/amirarasteh1990.github.io --issue NUMBER
```

The script creates the entry file and rebuilds the public index. The workflow
validates the result and commits only this directory and the compact index. Nobody
needs to edit JSON by hand. Removing `approved`, or adding `rejected`, removes a
previously published entry on the next sync, so takedowns use the same issue screen.
All submissions and moderation issues are public; there is no private-note mode.
