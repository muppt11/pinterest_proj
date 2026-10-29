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

_Invite-link guessing, revoked or expired access, public trip pages, and rate limits are covered when trips land._
