
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
  Classification will use `think=False`.
- Cold load ≈ 13.7 s, paid again whenever Ollama unloads the model after 5 idle minutes.
- **Warm cost ≈ 6.5 s per document** → ~400 files in ~45 minutes. The design estimated
  3–6 s; this is the measured number.
- The model correctly identified the document type from a meaningless filename.

## Oct 23 — Day 2: the AI layer

### One door to Gemma

- All model calls go through `chat_json()`: `think=False`, `keep_alive=15m`, `num_ctx=8192`,
  temperature 0, JSON schema from Pydantic.
- Two kinds of failure, handled differently: Ollama down or model missing → `OllamaUnavailable`
  (**pause** the work); bad JSON → return `None` with the raw output kept (**review queue**,
  never a crash). No retry: at temperature 0 the same input gives the same output.
- `kaagaz doctor`: the first run FAILed (0 output tokens, 28.9 s) and the second passed in 17.9 s.
  Both included a model reload, because the model was still loaded with the 32k context from the
  manual test, and changing `num_ctx` forces a reload. `ollama ps` now confirms
  **`CONTEXT 8192, 100% GPU`**. (doctor now prints the error reason on FAIL.)

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
- Note: Gemma wrote file-name rules with literal names (`{roll}_photograph`) instead of the
  `{doctype}` token. `naming.py` keeps literal text, so the output (`12345_photograph.jpg`) still
  matches "RollNumber_DocumentName".
- **31 tests passing**, none needing a GPU.

---

## Still to measure

- Requirement parsing on 5 *real* portal instruction texts (the specimen above is one invented
  text, written by me, so it's a smoke test, not an eval)
- 1,024 vs 1,536 px long side: classification accuracy and latency on the dev split
- Per-document classification latency with the JSON schema
- Packet build time for 5 items
