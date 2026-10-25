# Kaagaz — Dev log

# Kaagaz — Dev log

Decisions, numbers and failures, in order. Raw material for the DEV post.
Private test documents are described here, never included.

---

## Oct 21 — Design

- Wrote the design docs v1.1: System Design, PRD, Build/Eval/Demo plan.
- Core principle: **AI decides *what*, code does *how*, code verifies.**

## Oct 22 — Day 1: repo, hardware, engine

### Setup

- Created the repo. **Dropped FastAPI + React** for a single Python package (`kaagaz`) with a
  Typer CLI and a Streamlit UI. Both import the package directly, with no API layer in between.
  This is the only realistic way to ship in 4 days.
- **Python 3.12 instead of 3.11.** Only 3.12 was installed, and every dependency has cp312 wheels.
  A deliberate change to a locked decision.
- First `pip install` ran outside the venv (the venv creation had failed) and upgraded the global
  `starlette`, breaking FastAPI in other projects. Lesson: check that `(.venv)` is in the prompt
  before installing anything.

### Hardware: the GPU that wasn't there

- `nvidia-smi` was "not recognized". At first Windows listed only Intel UHD Graphics. The NVIDIA
  card then appeared as **"Microsoft Basic Display Adapter" with Status: Error**, meaning the card
  was present but had **no driver installed**.
- Identified it from the PCI ID: `VEN_10DE&DEV_28E1` = **RTX 4050 Laptop GPU**
  (ROG Strix G614JU). Installed NVIDIA driver 617.42.
- **6 GB VRAM, not the 8 GB the design assumed.**
  → **E4B-only.** Gemma 4 12B (~6.7 GB at Q4) can't stay on the GPU, so there's no 12B escalation.
  Low-confidence and `other` labels go straight to the review queue instead.
- Without a driver, Ollama would have quietly run on the CPU. Always check `ollama ps` shows
  `100% GPU` before measuring anything.

### Engine (no GPU needed)

- The **Ollama host is validated as localhost-only** when the config loads. A remote host refuses
  to start, so "nothing leaves your laptop" is enforced in code.
- Moved the schemas to `kaagaz/schemas.py` (a shared contract), so `engine/` never imports `ai/`.
- `id_last4` is cut to its last 4 digits by a Pydantic validator. A full ID number can't be stored
  even if the model returns one (tested: `1234 5678 9012` → `9012`).
- **"KB" is ambiguous on portals** (1000 or 1024?). Max limits use ×1000 and min limits use ×1024,
  so outputs pass under either reading.
- JPEG fitting: binary search on quality gives the highest quality that fits the limit
  (~7 encodes). If the portal fixes the pixel size, an impossible limit raises `CannotFit` with
  numbers instead of breaking the portal's dimensions.
- Transparent PNGs: Pillow's `convert("RGB")` turns transparency **black**, which would give a
  black signature on black. We paste onto white first.
- **OpenCV 5.0 removed `CascadeClassifier` from core.** Pinned `opencv-python-headless<5`.
  Unpinned dependencies would have broken face crop on a fresh install.
- Face crop: the crop is sized from the face (face ≈ 50% of crop height, slightly above centre),
  not just centred on it. No face → centre crop + WARN.
- PDFs: a lossless pass first (keeps selectable text), then a DPI ladder 200 → 72 with a per-page
  byte budget. Below 100 DPI the validator warns "check readability".
- The validator detects the format from the file's first bytes, not its extension, and re-opens
  every output. **The fitter never grades its own work.**
- File naming: token patterns (`{roll}_{doctype}`), Windows- and portal-safe cleaning (ASCII,
  no reserved names), case-insensitive de-duplication (on Windows, `Photo.jpg` = `photo.jpg`).
  A missing roll number drops the token and adds a warning instead of failing.

## Oct 23 (night) — First model measurements

Test: one private document photo with a WhatsApp filename, `gemma4:e4b` on the RTX 4050.

| Run                   | Total  | Load   | Prompt eval     | Output         |
| --------------------- | ------ | ------ | --------------- | -------------- |
| Default (thinking on) | 27.6 s | 13.6 s | 8.1 s (365 tok) | 275 tok, 5.8 s |
| `--think=false`     | 20.4 s | 13.8 s | 6.1 s (358 tok) | 14 tok, 0.5 s  |

- VRAM during a vision call: **4,545 / 6,141 MiB, 100% GPU** (default 32k context).
- **Gemma 4 thinks by default in Ollama**: ~260 hidden tokens for a ~15-token answer.
  All Kaagaz calls use `think=False`.
- Cold load ≈ 13.7 s, paid again whenever Ollama unloads the model after 5 idle minutes.
- This test sent the full-resolution phone photo. See Oct 24 for the real per-document number
  after downscaling.

## Oct 23 — Day 2: the AI layer

### One door to Gemma

- All model calls go through `chat_json()`: `think=False`, `keep_alive=15m`, `num_ctx=8192`,
  temperature 0, JSON schema from Pydantic.
- Two kinds of failure, handled differently: Ollama down or model missing → `OllamaUnavailable`
  (**pause** the work); bad JSON → return `None` with the raw output kept (**review queue**,
  never a crash). No retry on bad JSON: at temperature 0 the same input gives the same output.
- `kaagaz doctor`: the first run FAILed (0 output tokens, 28.9 s) and the second passed in 17.9 s.
  Both included a model reload, because the model was still loaded with the 32k context from the
  manual test, and changing `num_ctx` forces a reload. `ollama ps` now confirms
  **`CONTEXT 8192, 100% GPU`**.

### Requirement parser: v1 → v2

Test input: an invented NSP-style instruction text (6 documents, mixed units: KB, MB, cm; a range;
an "issued on or after" date; an optional item; a typed-in Aadhaar field that must be ignored;
a file-name rule stated once at the bottom).

|              | Limits correct           | File-name rule  | Time   | Output tokens |
| ------------ | ------------------------ | --------------- | ------ | ------------- |
| v1           | 22 / 27 (81%)            | 0 / 6           | 8.9 s  | 721           |
| **v2** | **27 / 27 (100%)** | **6 / 6** | 13.7 s | 1,236         |

- Correct from v1 on: ignored the typed-in Aadhaar field; 0.3 MB → 300 KB and 1 MB → 1000 KB;
  `issued_after` 2026-04-01; front + back → `merge_all`; "first page" → `first_only`;
  "if applicable" → `mandatory: false`.
- **Every v1 error was an omission, never a wrong value**: photo min 20 KB, 3.5 × 4.5 cm,
  white background; signature min 10 KB; the file-name rule everywhere.
- Cause: fields with defaults are *optional* in the JSON schema, and Ollama's constrained
  decoding lets the model skip optional keys. A small model skips whatever it can.
- Fixes:
  1. **Every key is required in the schema sent to Ollama** (null still allowed), so the model
     must consider each field.
  2. **Code checks the output in both directions.** The model must quote its source sentence.
     *Grounding*: every number it returns must appear in that sentence (with MB↔KB and mm↔cm
     conversions), or the field is flagged. *Coverage*: every number-with-unit in the sentence
     must be used by some field, or the field it belongs to is flagged. Grounding catches
     invented values; coverage catches omitted ones. Only numbers with units count, so
     "Class 12" and "01-04-2026" are never treated as limits.
  3. One prompt line: a file-name rule stated once applies to every item.
- Cost of v2: +4.8 s and +515 tokens per checklist (the model now writes out every `null`).
  Worth it, since parsing runs once per form, not once per document.
- Gemma writes file-name rules with literal names (`{roll}_Photograph`) instead of the
  `{doctype}` token. `naming.py` keeps literal text, so the output still matches
  "RollNumber_DocumentName".

### Validity rules (no AI)

- Chain, strongest evidence first: printed expiry → the portal's "issued on or after" rule →
  a labelled per-type estimate → CHECK DATE.
- The portal rule is a separate constraint, not a fallback: a certificate printed "valid until
  2027" but issued before the form's cutoff still fails that form.
- **EXPIRED comes only from facts** (a printed date, or a year clearly before the cutoff). A rule
  of thumb like "income certificates last ~12 months" can only produce CHECK DATE with
  "probably expired", labelled as an estimate. Kaagaz never tells you a document is expired based
  on a guess.
- Year-only dates are treated as a Jan–Dec range: pass if the whole range passes, fail if the
  whole range fails, CHECK DATE if it straddles the cutoff.

## Oct 24 — Day 2 (night): scan, classify, match, build

### Scan

- **Two phases:** register (walk, hash, insert as `pending`: seconds), then classify
  (~2 s/doc). Unfinished rows stay `pending`, so a scan resumes after sleep or Ctrl+C with no
  job queue.
- Rescans skip hashing when path + size + mtime are unchanged (13 files: second scan instant).
  The content hash is the identity: renamed or moved files keep their label, and duplicate copies
  are one document.
- Never indexes its own packets folder or app data. **Skips OneDrive online-only files**: reading
  them would download from the cloud, which breaks the offline promise and fails with Wi-Fi off.

### Render + privacy

- Gemma sees **page 1 only**, downscaled to 1,024 px, plus the PDF text layer (first 2 pages,
  ≤ 1,500 chars). Each extra page image would add ~260 tokens.
- Second privacy guard: a regex scrubber masks Aadhaar / VID / PAN / long digit runs in **every**
  string, including the raw model output, before anything is saved. Dates and years are untouched.

### Classification

- The prompt gives cues (Class X / Secondary / माध्यमिक vs Class XII / Senior Secondary /
  उच्च माध्यमिक; Hindi certificate titles). **The filename is not sent**, so the eval measures
  reading, not filenames.
- Three review triggers: type `other`; confidence < 0.75 (with no 12B, the escalation threshold
  became the review threshold); or the **PDF text names a different type**, a free check that
  doesn't rely on the model judging itself.
- **Speed: downscaling to 1,024 px cut per-document time from ~6.5 s (full-res smoke test) to
  p50 1.8 s / p95 2.2 s warm.** After making every key required: **p50 2.1 s / p95 2.8 s.**
  ~400 files ≈ 14 minutes.

**Dev set v1: 13 specimen documents** (made by me; specimens are easier than real phone photos,
so this is a dev set, not the eval):

|                      | Result                                                                                                                                |
| -------------------- | ------------------------------------------------------------------------------------------------------------------------------------- |
| Gemma alone          | 12 / 13 correct types (a college ID → `other` is correct, since there's no such type; the miss was a signature → `other`, 0.10) |
| Gemma + code checks  | **13 / 13 handled correctly**: 11 indexed, 2 sent to review with the right reason                                               |
| Hindi documents      | 2 / 2 correct (domicile certificate, JPG and scanned PDF, 0.95–0.98)                                                                 |
| WhatsApp-named files | 4 / 4 correct (income certificate, bank passbook, 10th marksheet, domicile)                                                           |

- **Signature miss.** A clearer prompt cue did not fix it (still `other`). A visual **ink check**
  in code did: mostly one background tone, < 12% dark ink, no face. It runs only when Gemma says
  `other`, *suggests* `signature`, and still sends it to review. Code suggestions show confidence
  0.00 rather than borrowing the model's confidence in a different label.
- Re-running the full set after the prompt edit changed none of the 11 indexed labels
  (`classify --redo`).
- **Ollama's runner crashed during a cold load** (exit 0xc0000409, "CUDA error: shared object
  initialization failed"); the next call loaded fine. Kaagaz had wrongly blamed the document.
  Now: server errors are retried, then the run pauses (rows stay pending). Document errors go to
  review.

### Extraction bugs found by looking at the database

The classify output looked perfect. The database didn't.

- **Same bug as the parser:** optional keys → Gemma left `person_name` and `year` empty on
  **13 / 13** documents. Rule now: **every model-facing schema makes all keys required.**
- **Worse: dates typed as `date` let constrained decoding squeeze day-first Indian dates into
  ISO slots** (`14-06-2020` → `"1406-06-20"`), and Pydantic accepted that as a valid date. A silent
  error. Fix: **the model copies dates exactly as printed**; a tested day-first parser in code
  converts them (DD-MM-YYYY, 2-digit years, month names, Devanagari digits) and rejects anything
  implausible. *"The AI reads, code converts"* now covers dates as well as sizes.
- Out-of-range values are repaired, not rejected: year `207` → null, confidence `1.2` → 1.0.
  Previously either would have failed the whole classification.
- **Gemma copied a date of birth as a marksheet's issue date** (2006 on a 2024 marksheet). Code now
  cross-checks the issue date against the printed year and drops the date if they disagree by more
  than a year: two model outputs checking each other.
- After the fix: names (including Devanagari), years and issue dates filled in. The income
  certificate's real date (12 Aug 2026) moved its row from CHECK DATE to built.

### Matcher (no AI)

- Ranking, in order: validity (OK > CHECK DATE > EXPIRED) → confirmed label > in review →
  name matches the profile → newest → model confidence. Plain, explainable rules.
- Documents still in review can be picked, with a "label not confirmed" note, instead of the row
  showing MISSING while the file is right there.
- Checklists save as JSON you can edit by hand, re-validated on load, so the 14 s parse runs once.

### Builder: the first packet

- One pipeline per row: load → choose format (least conversion) → shape (face crop, signature
  cleanup, exact px) → fit to KB → name → **validate** → write.
- **Only outputs that pass validation are written.** A FAIL is reported, never saved, so it can't
  be uploaded by mistake. Expired and missing rows are never built.
- Signature cleanup: paper → pure white, ink kept, cropped to the ink.
- Photo backgrounds are **checked, not edited**.
- **First specimen packet: 6 items built in 0.3 s** (PRD target < 30 s), with `checklist.md` and
  `manifest.json`. Signature whitened to 11.0 KB (rule: 10–20 KB). Marksheet, income certificate,
  passbook and caste certificate built as PDFs under their limits.
- **The photo FAILed, honestly:** a smooth 413 × 531 specimen image couldn't reach the portal's
  20 KB minimum even at quality 95 without chroma subsampling. Not padded, and not written to
  the packet. Real phone photos have more detail and usually land at 30–50 KB.
- **My bug:** the photo background check included the bottom edge, where shoulders and clothes
  always are, so it would have failed nearly every real passport photo. Now it checks the top and
  upper sides only.
- Face detection tries a second OpenCV cascade (`alt2`, looser) if the first finds nothing.

### Workflow note

- Several bugs came from paste mistakes (a lost newline, a block indented into an `if`). The
  privacy test (*"raw output is scrubbed before saving"*) caught one of them before it could be
  committed. Whole-file replacements avoid most of these.

## Oct 25 — Day 3: the app, the demo set, and an Ollama surprise

### UI

- Streamlit app with six screens: first-run welcome, Library, Review, New packet (4-step wizard),
  Packets, Settings & privacy. Every button calls the same tested package as the CLI.
- Visual design started from AI-generated mockups (ink teal, marigold saffron, paper cream,
  raised "paper" cards). The mockups loaded Tailwind, Google Fonts, icon fonts and images from the
  internet; all of that was removed so **the app looks the same with Wi-Fi off**: system fonts
  (Georgia, Segoe UI, Nirmala UI for Hindi) and inline CSS only.
- The mockups also invented features ("trains local weights", "PDF/A compatible", "integrity
  hash", "1.2 s parse"). None of that text made it into the app; it shows Kaagaz's real numbers.
- **Streamlit sends anonymous usage statistics by default.** Turned off in
  `.streamlit/config.toml`, and the server listens on `127.0.0.1` only.
- Review queue has keyboard shortcuts (Ctrl+Enter confirm, Ctrl+→ skip). Labels you confirm are
  marked "confirmed by you" instead of showing Gemma's old confidence.
- The match step lets you switch to an alternative file; a packet's checklist is saved inside its
  folder so it can be rebuilt later.
- All four manual checks passed on my laptop: library loads, review confirm, specimen packet built,
  app reloads correctly with Wi-Fi off.

### Demo documents

- `samples/make_specimens.py` generates the demo set: one invented person (Riya Sharma), invented
  institutions, a SPECIMEN watermark on every page, two documents as tilted "WhatsApp photos",
  a scanned PDF, a Hindi domicile certificate and a script-font signature.
- The set is built to show the whole story against the specimen NSP rules: an income certificate
  issued 12 Mar 2026 (form needs on/after 01 Apr 2026 → **EXPIRED**) and no bank passbook
  (**MISSING**). Expected: **4 ready · 1 expired · 1 missing**.

### Ollama auto-updated and broke cold loads

- With Wi-Fi off, labelling paused: the model runner crashed while loading Gemma
  (`exit 0xc0000409`, `CUDA error: shared object initialization failed`).
- It looked like a Wi-Fi problem. It wasn't: in 9 cold loads (`ollama stop` → `ollama run`), only
  2 succeeded, with Wi-Fi both on and off.
- **Ollama's own log** pinpointed it: the crash happens during the model **warm-up run**, inside
  `ggml_cuda_kernel_can_use_pdl` in the **CUDA 13** backend (`llama-server-cuda_v13`).
- Ollama's library folder was rewritten on 24 Oct and 25 Oct (the CUDA folders at 16:52), hours
  before the crashes started: the Windows app had **auto-updated** to **0.40.11**.
- The log also showed `ollama run`'s default 32k context only fits 34 of 43 layers on the 6 GB
  GPU. Kaagaz's 8k context keeps it fully on the GPU.
- Kaagaz's side: server errors now get **3 tries with longer waits (3 s, 8 s)**, then the run
  pauses with a plain-language message; Windows' alarming crash text is kept behind
  "Technical details". Nothing is lost: unread files stay queued.
- Workaround tried: force the CUDA 12 backend (`setx OLLAMA_LLM_LIBRARY cuda_v12`, restart
  Ollama). Result: **PENDING**. Fallback: reinstall an earlier Ollama release.
- Once a model is loaded it runs fully offline; the problem is only the load.
- Lesson: pin or freeze every moving part of a local AI stack during a deadline, not just Python
  packages. The model server can change under you.

### Guide page

- Static guide page in `docs/` (setup, how to use, measured results, privacy, troubleshooting,
  limitations), hosted on Vercel. Single HTML file, no external scripts. Every claim checked
  against the code; the generated draft had overclaimed privacy ("hard-disabled at the socket
  level") and invented features, which were rewritten. Video embed is in place but commented out.

**71 tests passing**, none needing a GPU.

---

## Not done (honest)

- Held-out eval on ~30 real documents. Only the 13-document specimen dev set was run.
- Requirement parsing on real portal texts (only the specimen text, written by me).
- 1,024 vs 1,536 px comparison.
- Timed "by hand vs with Kaagaz" comparison on a real form.
- Demo vide

Decisions, numbers and failures, in order. Raw material for the DEV post.
Private test documents are described here, never included.

---

## Oct 21 — Design

- Wrote the design docs v1.1: System Design, PRD, Build/Eval/Demo plan.
- Core principle: **AI decides *what*, code does *how*, code verifies.**

## Oct 22 — Day 1: repo, hardware, engine

### Setup

- Created the repo. **Dropped FastAPI + React** for a single Python package (`kaagaz`) with a
  Typer CLI and a Streamlit UI. Both import the package directly, with no API layer in between.
  This is the only realistic way to ship in 4 days.
- **Python 3.12 instead of 3.11.** Only 3.12 was installed, and every dependency has cp312 wheels.
  A deliberate change to a locked decision.
- First `pip install` ran outside the venv (the venv creation had failed) and upgraded the global
  `starlette`, breaking FastAPI in other projects. Lesson: check that `(.venv)` is in the prompt
  before installing anything.

### Hardware: the GPU that wasn't there

- `nvidia-smi` was "not recognized". At first Windows listed only Intel UHD Graphics. The NVIDIA
  card then appeared as **"Microsoft Basic Display Adapter" with Status: Error**, meaning the card
  was present but had **no driver installed**.
- Identified it from the PCI ID: `VEN_10DE&DEV_28E1` = **RTX 4050 Laptop GPU**
  (ROG Strix G614JU). Installed NVIDIA driver 617.42.
- **6 GB VRAM, not the 8 GB the design assumed.**
  → **E4B-only.** Gemma 4 12B (~6.7 GB at Q4) can't stay on the GPU, so there's no 12B escalation.
  Low-confidence and `other` labels go straight to the review queue instead.
- Without a driver, Ollama would have quietly run on the CPU. Always check `ollama ps` shows
  `100% GPU` before measuring anything.

### Engine (no GPU needed)

- The **Ollama host is validated as localhost-only** when the config loads. A remote host refuses
  to start, so "nothing leaves your laptop" is enforced in code.
- Moved the schemas to `kaagaz/schemas.py` (a shared contract), so `engine/` never imports `ai/`.
- `id_last4` is cut to its last 4 digits by a Pydantic validator. A full ID number can't be stored
  even if the model returns one (tested: `1234 5678 9012` → `9012`).
- **"KB" is ambiguous on portals** (1000 or 1024?). Max limits use ×1000 and min limits use ×1024,
  so outputs pass under either reading.
- JPEG fitting: binary search on quality gives the highest quality that fits the limit
  (~7 encodes). If the portal fixes the pixel size, an impossible limit raises `CannotFit` with
  numbers instead of breaking the portal's dimensions.
- Transparent PNGs: Pillow's `convert("RGB")` turns transparency **black**, which would give a
  black signature on black. We paste onto white first.
- **OpenCV 5.0 removed `CascadeClassifier` from core.** Pinned `opencv-python-headless<5`.
  Unpinned dependencies would have broken face crop on a fresh install.
- Face crop: the crop is sized from the face (face ≈ 50% of crop height, slightly above centre),
  not just centred on it. No face → centre crop + WARN.
- PDFs: a lossless pass first (keeps selectable text), then a DPI ladder 200 → 72 with a per-page
  byte budget. Below 100 DPI the validator warns "check readability".
- The validator detects the format from the file's first bytes, not its extension, and re-opens
  every output. **The fitter never grades its own work.**
- File naming: token patterns (`{roll}_{doctype}`), Windows- and portal-safe cleaning (ASCII,
  no reserved names), case-insensitive de-duplication (on Windows, `Photo.jpg` = `photo.jpg`).
  A missing roll number drops the token and adds a warning instead of failing.

## Oct 23 (night) — First model measurements

Test: one private document photo with a WhatsApp filename, `gemma4:e4b` on the RTX 4050.

| Run                   | Total  | Load   | Prompt eval     | Output         |
| --------------------- | ------ | ------ | --------------- | -------------- |
| Default (thinking on) | 27.6 s | 13.6 s | 8.1 s (365 tok) | 275 tok, 5.8 s |
| `--think=false`     | 20.4 s | 13.8 s | 6.1 s (358 tok) | 14 tok, 0.5 s  |

- VRAM during a vision call: **4,545 / 6,141 MiB, 100% GPU** (default 32k context).
- **Gemma 4 thinks by default in Ollama**: ~260 hidden tokens for a ~15-token answer.
  All Kaagaz calls use `think=False`.
- Cold load ≈ 13.7 s, paid again whenever Ollama unloads the model after 5 idle minutes.
- This test sent the full-resolution phone photo. See Oct 24 for the real per-document number
  after downscaling.

## Oct 23 — Day 2: the AI layer

### One door to Gemma

- All model calls go through `chat_json()`: `think=False`, `keep_alive=15m`, `num_ctx=8192`,
  temperature 0, JSON schema from Pydantic.
- Two kinds of failure, handled differently: Ollama down or model missing → `OllamaUnavailable`
  (**pause** the work); bad JSON → return `None` with the raw output kept (**review queue**,
  never a crash). No retry on bad JSON: at temperature 0 the same input gives the same output.
- `kaagaz doctor`: the first run FAILed (0 output tokens, 28.9 s) and the second passed in 17.9 s.
  Both included a model reload, because the model was still loaded with the 32k context from the
  manual test, and changing `num_ctx` forces a reload. `ollama ps` now confirms
  **`CONTEXT 8192, 100% GPU`**.

### Requirement parser: v1 → v2

Test input: an invented NSP-style instruction text (6 documents, mixed units: KB, MB, cm; a range;
an "issued on or after" date; an optional item; a typed-in Aadhaar field that must be ignored;
a file-name rule stated once at the bottom).

|              | Limits correct           | File-name rule  | Time   | Output tokens |
| ------------ | ------------------------ | --------------- | ------ | ------------- |
| v1           | 22 / 27 (81%)            | 0 / 6           | 8.9 s  | 721           |
| **v2** | **27 / 27 (100%)** | **6 / 6** | 13.7 s | 1,236         |

- Correct from v1 on: ignored the typed-in Aadhaar field; 0.3 MB → 300 KB and 1 MB → 1000 KB;
  `issued_after` 2026-04-01; front + back → `merge_all`; "first page" → `first_only`;
  "if applicable" → `mandatory: false`.
- **Every v1 error was an omission, never a wrong value**: photo min 20 KB, 3.5 × 4.5 cm,
  white background; signature min 10 KB; the file-name rule everywhere.
- Cause: fields with defaults are *optional* in the JSON schema, and Ollama's constrained
  decoding lets the model skip optional keys. A small model skips whatever it can.
- Fixes:
  1. **Every key is required in the schema sent to Ollama** (null still allowed), so the model
     must consider each field.
  2. **Code checks the output in both directions.** The model must quote its source sentence.
     *Grounding*: every number it returns must appear in that sentence (with MB↔KB and mm↔cm
     conversions), or the field is flagged. *Coverage*: every number-with-unit in the sentence
     must be used by some field, or the field it belongs to is flagged. Grounding catches
     invented values; coverage catches omitted ones. Only numbers with units count, so
     "Class 12" and "01-04-2026" are never treated as limits.
  3. One prompt line: a file-name rule stated once applies to every item.
- Cost of v2: +4.8 s and +515 tokens per checklist (the model now writes out every `null`).
  Worth it, since parsing runs once per form, not once per document.
- Gemma writes file-name rules with literal names (`{roll}_Photograph`) instead of the
  `{doctype}` token. `naming.py` keeps literal text, so the output still matches
  "RollNumber_DocumentName".

### Validity rules (no AI)

- Chain, strongest evidence first: printed expiry → the portal's "issued on or after" rule →
  a labelled per-type estimate → CHECK DATE.
- The portal rule is a separate constraint, not a fallback: a certificate printed "valid until
  2027" but issued before the form's cutoff still fails that form.
- **EXPIRED comes only from facts** (a printed date, or a year clearly before the cutoff). A rule
  of thumb like "income certificates last ~12 months" can only produce CHECK DATE with
  "probably expired", labelled as an estimate. Kaagaz never tells you a document is expired based
  on a guess.
- Year-only dates are treated as a Jan–Dec range: pass if the whole range passes, fail if the
  whole range fails, CHECK DATE if it straddles the cutoff.

## Oct 24 — Day 2 (night): scan, classify, match, build

### Scan

- **Two phases:** register (walk, hash, insert as `pending`: seconds), then classify
  (~2 s/doc). Unfinished rows stay `pending`, so a scan resumes after sleep or Ctrl+C with no
  job queue.
- Rescans skip hashing when path + size + mtime are unchanged (13 files: second scan instant).
  The content hash is the identity: renamed or moved files keep their label, and duplicate copies
  are one document.
- Never indexes its own packets folder or app data. **Skips OneDrive online-only files**: reading
  them would download from the cloud, which breaks the offline promise and fails with Wi-Fi off.

### Render + privacy

- Gemma sees **page 1 only**, downscaled to 1,024 px, plus the PDF text layer (first 2 pages,
  ≤ 1,500 chars). Each extra page image would add ~260 tokens.
- Second privacy guard: a regex scrubber masks Aadhaar / VID / PAN / long digit runs in **every**
  string, including the raw model output, before anything is saved. Dates and years are untouched.

### Classification

- The prompt gives cues (Class X / Secondary / माध्यमिक vs Class XII / Senior Secondary /
  उच्च माध्यमिक; Hindi certificate titles). **The filename is not sent**, so the eval measures
  reading, not filenames.
- Three review triggers: type `other`; confidence < 0.75 (with no 12B, the escalation threshold
  became the review threshold); or the **PDF text names a different type**, a free check that
  doesn't rely on the model judging itself.
- **Speed: downscaling to 1,024 px cut per-document time from ~6.5 s (full-res smoke test) to
  p50 1.8 s / p95 2.2 s warm.** After making every key required: **p50 2.1 s / p95 2.8 s.**
  ~400 files ≈ 14 minutes.

**Dev set v1: 13 specimen documents** (made by me; specimens are easier than real phone photos,
so this is a dev set, not the eval):

|                      | Result                                                                                                                                |
| -------------------- | ------------------------------------------------------------------------------------------------------------------------------------- |
| Gemma alone          | 12 / 13 correct types (a college ID → `other` is correct, since there's no such type; the miss was a signature → `other`, 0.10) |
| Gemma + code checks  | **13 / 13 handled correctly**: 11 indexed, 2 sent to review with the right reason                                               |
| Hindi documents      | 2 / 2 correct (domicile certificate, JPG and scanned PDF, 0.95–0.98)                                                                 |
| WhatsApp-named files | 4 / 4 correct (income certificate, bank passbook, 10th marksheet, domicile)                                                           |

- **Signature miss.** A clearer prompt cue did not fix it (still `other`). A visual **ink check**
  in code did: mostly one background tone, < 12% dark ink, no face. It runs only when Gemma says
  `other`, *suggests* `signature`, and still sends it to review. Code suggestions show confidence
  0.00 rather than borrowing the model's confidence in a different label.
- Re-running the full set after the prompt edit changed none of the 11 indexed labels
  (`classify --redo`).
- **Ollama's runner crashed during a cold load** (exit 0xc0000409, "CUDA error: shared object
  initialization failed"); the next call loaded fine. Kaagaz had wrongly blamed the document.
  Now: server errors get one retry, then pause (rows stay pending). Document errors go to review.

### Extraction bugs found by looking at the database

The classify output looked perfect. The database didn't.

- **Same bug as the parser:** optional keys → Gemma left `person_name` and `year` empty on
  **13 / 13** documents. Rule now: **every model-facing schema makes all keys required.**
- **Worse: dates typed as `date` let constrained decoding squeeze day-first Indian dates into
  ISO slots** (`14-06-2020` → `"1406-06-20"`), and Pydantic accepted that as a valid date. A silent
  error. Fix: **the model copies dates exactly as printed**; a tested day-first parser in code
  converts them (DD-MM-YYYY, 2-digit years, month names, Devanagari digits) and rejects anything
  implausible. *"The AI reads, code converts"* now covers dates as well as sizes.
- Out-of-range values are repaired, not rejected: year `207` → null, confidence `1.2` → 1.0.
  Previously either would have failed the whole classification.
- **Gemma copied a date of birth as a marksheet's issue date** (2006 on a 2024 marksheet). Code now
  cross-checks the issue date against the printed year and drops the date if they disagree by more
  than a year: two model outputs checking each other.
- After the fix: names (including Devanagari), years and issue dates filled in. The income
  certificate's real date (12 Aug 2026) moved its row from CHECK DATE to built.

### Matcher (no AI)

- Ranking, in order: validity (OK > CHECK DATE > EXPIRED) → confirmed label > in review →
  name matches the profile → newest → model confidence. Plain, explainable rules.
- Documents still in review can be picked, with a "label not confirmed" note, instead of the row
  showing MISSING while the file is right there.
- Checklists save as JSON you can edit by hand, re-validated on load, so the 14 s parse runs once.

### Builder: the first packet

- One pipeline per row: load → choose format (least conversion) → shape (face crop, signature
  cleanup, exact px) → fit to KB → name → **validate** → write.
- **Only outputs that pass validation are written.** A FAIL is reported, never saved, so it can't
  be uploaded by mistake. Expired and missing rows are never built.
- Signature cleanup: paper → pure white, ink kept, cropped to the ink.
- Photo backgrounds are **checked, not edited**.
- **First specimen packet: 6 items built in 0.3 s** (PRD target < 30 s), with `checklist.md` and
  `manifest.json`. Signature whitened to 11.0 KB (rule: 10–20 KB). Marksheet, income certificate,
  passbook and caste certificate built as PDFs under their limits.
- **The photo FAILed, honestly:** this smooth 413 × 531 image can't reach the portal's 20 KB
  minimum even at quality 95 without chroma subsampling. Not padded, and not written to the
  packet. Real phone photos have more detail and usually land at 30–50 KB.
- **My bug:** the photo background check included the bottom edge, where shoulders and clothes
  always are, so it would have failed nearly every real passport photo. Now it checks the top and
  upper sides only.
- Face detection now tries a second OpenCV cascade (`alt2`, looser) if the first finds nothing.
  The specimen photo still gets "No face found", so it's honestly reported.

### Known limitations (for the post)

- Name matching is word-based, so a Devanagari name (अमित कुमार) doesn't match an English profile
  name. Needs transliteration.
- The matcher picks one file per row; merging a separate front and back photo of a marksheet
  isn't automatic yet.
- Photo backgrounds are checked, not replaced.

### Workflow note

- Several bugs came from paste mistakes (a lost newline, a block indented into an `if`). The
  privacy test (*"raw output is scrubbed before saving"*) caught one of them before it could be
  committed. Whole-file replacements avoid most of these.

**71 tests passing**, none needing a GPU.

---

## Still to do / measure

- Demo specimen set for **one** invented person (Riya Sharma), including an expired income
  certificate and no passbook (to show EXPIRED and MISSING)
- Streamlit UI
- Held-out eval on ~30 real documents (accuracy, review rate, p50/p95)
- Requirement parsing on 5 *real* portal instruction texts (the specimen text is a smoke test I
  wrote myself, not an eval)
- 1,024 vs 1,536 px comparison
- Lazy payoff: one real form, timed by hand vs with Kaagaz
