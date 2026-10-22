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
- **16 tests passing**, none needing a GPU.

## Oct 23 (night) — First model measurements
Test: one private document photo with a WhatsApp filename, `gemma4:e4b` on the RTX 4050.

| Run | Total | Load | Prompt eval | Output |
|---|---|---|---|---|
| Default (thinking on) | 27.6 s | 13.6 s | 8.1 s (365 tok) | 275 tok, 5.8 s |
| `--think=false` | 20.4 s | 13.8 s | 6.1 s (358 tok) | 14 tok, 0.5 s |

- VRAM during a vision call: **4,545 / 6,141 MiB, 100% GPU** (default 32k context).
- **Gemma 4 thinks by default in Ollama**: ~260 hidden tokens for a ~15-token answer.
  Classification will use `think=False`.
- Cold load ≈ 13.7 s, paid again whenever Ollama unloads the model after 5 idle minutes.
  Scans will set `keep_alive`.
- **Warm cost ≈ 6.5 s per document** → ~400 files in ~45 minutes. The design estimated
  3–6 s; this is the measured number.
- The model correctly identified the document type from a meaningless filename.

---

## Still to measure
- 1,024 vs 1,536 px long side: accuracy and latency on the dev split
- Latency with `format=` JSON schema and `num_ctx=8192`
- Requirement parsing accuracy on real portal texts
