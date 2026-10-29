# Hand-labeled provenance set

Used by the AI-label demo (feature 5) and the label eval (feature 10). Images here are **not committed**.

```
labels_handset/
  human/   # unsigned original phone photos (keep EXIF); expected: Unknown
  verified/ # camera photos with valid C2PA digitalCapture credentials; expected: Human-made
  ai/      # images you generated with tools that embed Content Credentials (C2PA)
  other/   # screenshots or re-saved files with metadata stripped (expected: Unknown)
```

Copy the original files. AirDrop, email, or re-saving can strip the metadata the labels depend on.

EXIF alone does not verify that a photo is human-made. The `human/` folder checks that unsigned
camera photos stay Unknown; use `verified/` only for signed camera captures. This evaluates the
evidence-based labels, not an image classifier's ability to guess how a picture was made.
