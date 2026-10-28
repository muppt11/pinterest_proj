# Threat model

_Filled in during features 5 and 9._ It will cover:

- Invite-link guessing (token entropy, rate limits)
- Revoked or expired access
- XSS in user text (notes, board names, display names)
- Upload abuse (file types, sizes, decompression bombs)
- Location leaks (GPS EXIF is stripped after provenance and DateTimeOriginal are read)
- The public trip page (no emails or personal info)
