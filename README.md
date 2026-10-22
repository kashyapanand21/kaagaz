# Kaagaz 📄🦥

**A local, offline document assistant for Indian forms.**

Every scholarship, admission and exam portal in India wants the same documents in a different
format: "photo 3.5 × 4.5 cm, JPG, 20–50 KB", "marksheet PDF under 200 KB", "signature on white
background". Kaagaz scans your folders, recognises your documents with **Gemma 4 running locally
through Ollama**, and when you paste a portal's upload instructions, it builds a folder of files
converted, cropped, compressed and renamed to the exact rules. Then it **measures every output**.

> **AI decides *what*. Code does *how*. Code verifies.**

Nothing leaves your laptop. No uploads, no online compressors, no cloud API.

> 🚧 **Work in progress.** Built for the DEV Hacktoberfest Open-Source AI Challenge, Week 3
> ("Slow and Steady"), Oct 22–25, 2026.

---

## Status

| Part                                                                                    | State             |
| --------------------------------------------------------------------------------------- | ----------------- |
| Document engine: JPEG/PDF fitting to KB limits, face crop, image↔PDF, merge, validator | ✅ done, 16 tests |
| Config with localhost-only model host                                                   | ✅ done           |
| Requirement parser (portal instructions → checklist)                                   | 🔨 in progress    |
| Scan + classify with Gemma 4 E4B                                                        | ⏳ next           |
| Matcher + packet builder + CLI                                                          | ⏳                |
| Streamlit UI                                                                            | ⏳                |
| Evaluation numbers                                                                      | ⏳                |

## How it works

1. **Scan.** Kaagaz reads your chosen folders (read-only) and skips files it has already seen
   (sha256).
2. **Label.** Gemma 4 E4B looks at each document and returns a type (`marksheet_12`,
   `income_certificate`, `photo`, …), plus the name, issuer and year, as schema-checked JSON.
   Unsure results go to a review queue.
3. **Paste rules.** Paste a portal's "documents to upload" section, and Kaagaz turns it into an
   editable checklist.
4. **Build.** Kaagaz picks a file for each row, then plain Python converts, crops, resizes,
   compresses and renames it.
5. **Verify.** Every output is re-opened and measured: **PASS / WARN / FAIL** with real numbers
   (e.g. `46.2 KB, 413×531 px, PASS`). Missing and expired documents are flagged before you start
   the form.

## Requirements

- Windows 11 (developed on an ASUS ROG Strix G16)
- NVIDIA GPU with **6 GB+ VRAM** and a current driver (check `nvidia-smi`)
- Python 3.12
- [Ollama](https://ollama.com)

## Setup

```powershell
ollama pull gemma4:e4b

git clone https://github.com/YOUR_USERNAME/kaagaz.git
cd kaagaz
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[ui,dev]"

copy config.example.toml config.toml   # then edit folders and profile
kaagaz config                          # show effective settings
pytest -q                              # engine tests, no GPU needed
```

Check that the model runs fully on your GPU:

```powershell
ollama run gemma4:e4b "ready?"
ollama ps        # PROCESSOR should say 100% GPU
```

## Measured so far

On an RTX 4050 Laptop GPU (6 GB):

| Metric                           | Value                   |
| -------------------------------- | ----------------------- |
| VRAM during a vision call        | 4.5 GB, 100% GPU        |
| Per document, warm, thinking off | ~6.5 s                  |
| Model cold load                  | ~13.7 s (once per scan) |

Full evaluation (accuracy, parsing, compliance, time saved) coming.

## Privacy

- The only network peer is Ollama on `127.0.0.1`. A non-local host is rejected when the config
  loads.
- Your original files are never modified, moved or deleted. Outputs go to a separate packets
  folder.
- ID numbers are stored as the **last 4 digits only**, enforced in code.
- All demo material uses **specimen documents** with invented details.

## Credits

- [Gemma 4](https://ai.google.dev/gemma) by Google
- [Ollama](https://ollama.com)
- [PyMuPDF](https://pymupdf.readthedocs.io) (AGPL-3.0)
- [Pillow](https://python-pillow.org), [pillow-heif](https://github.com/bigcat88/pillow_heif)
- [OpenCV](https://opencv.org) and its Haar cascade face detector
- [Pydantic](https://docs.pydantic.dev), [Typer](https://typer.tiangolo.com),
  [Streamlit](https://streamlit.io)

## License

Apache-2.0. See [LICENSE](LICENSE).

Note: Kaagaz depends on PyMuPDF, which is licensed under AGPL-3.0. Distributing Kaagaz together
with PyMuPDF is subject to PyMuPDF's licence terms.
