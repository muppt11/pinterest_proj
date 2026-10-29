# Threat model

What could go wrong, and what MoodBoards does about it. Production would add real authentication, a CDN with abuse protection, and rate limiting at the edge; this is a local portfolio demo.

## Uploads (photo search, Analyze board)

| Threat | Mitigation | Where |
|---|---|---|
| Huge files exhausting memory | 10 MB limit per file; extra bytes rejected with 413 before decoding | `app/uploads.py` |
| Decompression bombs (tiny file, enormous pixels) | Pillow's `MAX_IMAGE_PIXELS` capped at 40 MP; bombs rejected with 400 | `app/uploads.py` |
| Non-image or disguised files | Only JPEG, PNG, WebP content types; the file must actually decode | `app/uploads.py` |
| **Location leaks**: phone photos carry GPS coordinates | GPS EXIF is removed and the image re-encoded before any further use. Only the capture date is kept, for repost credit | `app/services/upload_pipeline.py` |
| Stripping destroys evidence (C2PA labels lost) | Provenance and capture date are read from the *original* bytes first, then stripped; tested | `tests/test_provenance.py` |
| Fake "verified human" claims | Only a *valid C2PA signature* earns "verified"; unsigned IPTC claims and tampered manifests stay Unknown | `app/services/provenance.py` |
| Uploads stored forever | Photo-search and board uploads are processed in memory and not stored | routers |

## Accounts (lightweight sign-up)

| Threat | Mitigation |
|---|---|
| Stolen database used to impersonate users | The cookie holds a random 256-bit token; only its SHA-256 hash is stored |
| Scripts reading the session cookie (XSS) | Cookie is `HttpOnly` and `SameSite=Lax` |
| Account recovery | None: there are no passwords. Clearing cookies loses the profile. Production would use real auth |

## User text (board names, display names)

| Threat | Mitigation |
|---|---|
| XSS through stored text | React escapes all text when rendering, and nothing uses `dangerouslySetInnerHTML`. Names are also normalized and stripped of control characters and `< >` before storage (`app/text.py`) |
| Oversized input | Length limits on every text field (Pydantic) |

## Trips and sharing (feature 9)

| Threat | Mitigation | Tested |
|---|---|---|
| **Guessing invite links** | `secrets.token_urlsafe(24)` gives 192 bits, far beyond guessing. Only the SHA-256 hash is stored, so a database leak doesn't reveal live links. Joining is rate limited | `test_trips.py` |
| **Revoked or expired access** | Owners revoke links (`revoked = 1`) and links expire after 1–30 days. Both fail with the same 404 as an unknown token, so the response doesn't reveal which | `test_revoked_and_expired_links_fail` |
| Viewers editing | Every write checks the minimum role (editor or owner) through one helper | `test_viewer_cannot_edit` |
| Discovering private trips | Non-members get 404 rather than 403 | `test_trip_flow…` |
| Invite or publish spam | Per-user limits: 10 invites a minute, 5 publishes a minute; returns 429 | `test_unpublished_page_404s_and_rate_limits` |
| **Public page leaking personal info** | The public endpoint returns no names, emails, IDs or cookies, only the plan, weather, lineup, notes and a traveler count. The slug is a 96-bit random token | `test_trip_flow…` |
| Unpublished pages staying reachable | Unpublishing clears the slug; the old URL returns 404 | `test_trip_flow…` |
| **XSS in notes, trip names and event labels** | Stored as plain text and rendered by React as text (`<b>` shows literally). Names are cleaned (`app/text.py`), and every field has a length limit | `test_trip_flow…` |
| **Location leaks from inspiration photos** | Uploads go through the pipeline (GPS stripped). Only the embedding and dominant colors are stored, never the photo | `upload_pipeline.py` |
| AI notes inventing facts | Drafts are always stored and shown as "AI suggestion". The prompt forbids prices, opening hours, bookings and named businesses | `trips.py` |
