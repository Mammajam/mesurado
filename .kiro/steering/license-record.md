---
inclusion: always
---

# License record

Every content item in the pack (article, image, passage, map data, font, icon) needs a license record. No record, no inclusion.

## Manifest fields (required per item)
- `id`
- `title`
- `source_url`
- `revision` (page revision id or retrieval date)
- `license` (SPDX id such as CC-BY-SA-4.0, CC-BY-4.0, CC0-1.0, or the exact license name)
- `author_or_attribution` (text to display)
- `retrieved_at`
- `modifications` (for example "split into passages")

## Allowed sources
Wikipedia (CC BY-SA), Wikimedia Commons (check each file's license), OpenStax (CC BY), and other openly licensed
sources recorded in the manifest. Government and publisher content is excluded unless the license is explicit.

## Rules
- Share-alike: the pack carries CC BY-SA with visible attribution in the app (an Attribution screen and per-article credit).
- Images: confirm the license per file. If it is unclear, leave the image out.
- Passages inherit the license and attribution of their article and keep a pointer to it.
- Third-party code and fonts are listed in docs/third-party.md with their licenses.
- The pack-validator fails the build on a missing field, an unrecognised license, or a passage that cannot be traced to its article.
- No Encarta name, logo, screenshots or content anywhere. Demo video: no third-party marks, no unlicensed music.

## Tests required
- Property: for any pack, every item has a complete license record.
