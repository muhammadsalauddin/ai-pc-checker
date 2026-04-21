# 🤖 AI PC Suitability Checker

> Instantly discover whether your PC is ready for **local AI** — and how it compares to cloud APIs.

![Dashboard Screenshot](screenshot.png)

---

## ✨ Features

| Feature | Details |
|---|---|
| **Hardware Scanner** | CPU, RAM (speed + type), GPU (VRAM + tier), Disk, OS |
| **AI Suitability Score** | 0–100 score with S+ → F tier rating |
| **Live Model Catalog** | Pulls the latest Ollama Library families automatically and caches them locally |
| **Model Compatibility** | Hardware-fit recommendations across live Text, Code, Vision, Embedding and other model families |
| **Coding Recommendations** | Dedicated local coding-model picks based on your RAM, VRAM and GPU acceleration backend |
| **Install Commands** | One-click Ollama commands for the best-fit size of each model family |
| **API vs Local** | Speed (tok/s), Latency, Cost/month, Feature matrix vs 14 cloud providers |
| **Web Dashboard** | Dark-themed browser UI, auto-opens on a free port |
| **CLI Version** | Rich terminal output, saves `ai_pc_report.json` |
| **Cross-platform** | Windows, Linux, macOS (web + CLI) with OS-aware detection |

## Platform Update

The hardware detection layer now correctly adapts to each operating system:

- **Windows**: Detects Windows edition/build, DirectX, CUDA, and WMI-based GPU details
- **Linux**: Detects Linux distro/version and uses native system info plus NVIDIA tooling when available
- **macOS**: Detects macOS version correctly and supports Apple Silicon GPU reporting through Metal

Apple Silicon Macs now report:

- Correct **macOS** version instead of showing Windows
- **Apple GPU / Metal** instead of "GPU unavailable"
- **Unified memory** as usable AI VRAM for local model recommendations and scoring

## Live Catalog Update

The app no longer depends on a manually maintained model list.

- It pulls the current Ollama Library catalog automatically
- It chooses the **best-fit size** for each family based on your machine
- It shows a dedicated **Best Local Coding Models For This PC** section
- It suggests **hardware upgrades** based on the next better coding models you are close to running
- If Ollama is running locally, installed models automatically show an **Installed** badge in the dashboard
- If the live catalog is temporarily unavailable, the app falls back to a local cache instead of breaking

---

## 📸 Screenshot

![AI PC Checker Web Dashboard](screenshot.png)

---

## 🚀 Quick Start

### Option A — Bash (Linux / macOS / WSL / Git Bash)

```bash
git clone https://github.com/muhammadsalauddin/ai-pc-checker.git
cd ai-pc-checker
chmod +x install.sh start.sh
./install.sh          # sets up venv + installs dependencies
./start.sh            # opens web dashboard in browser
```

### Option B — Windows (PowerShell / CMD)

```bat
git clone https://github.com/muhammadsalauddin/ai-pc-checker.git
cd "ai-pc-checker"
pip install -r requirements.txt
python ai_pc_web.py
```

Or just double-click **`run_checker.bat`**.

### Option C — CLI only (no browser)

```bash
./start.sh --cli           # bash
python ai_pc_checker.py    # any OS
```

When you start the app, it automatically:

- scans your hardware
- fetches the latest Ollama Library families
- picks the best local coding models for your configuration
- shows which memory / VRAM upgrade unlocks the next tier of models

---

## 🛠️ Scripts

| Script | Purpose |
|---|---|
| `install.sh` | Creates `.venv`, installs all packages, verifies GPU tooling when available |
| `start.sh` | Activates venv, launches web server (or `--cli` flag for terminal mode) |
| `run_checker.bat` | Windows double-click launcher for web dashboard |
| `ai_pc_web.py` | Main Flask web application |
| `ai_pc_checker.py` | Standalone CLI version (Rich terminal UI) |
| `model_catalog.py` | Shared live Ollama catalog parser + recommendation engine |

---

## 📦 Requirements

```
psutil>=5.9.0       # CPU, RAM, Disk info
rich>=13.0.0        # Terminal UI (CLI version)
gputil>=1.4.0       # NVIDIA GPU info via nvidia-smi
py-cpuinfo>=9.0.0   # Detailed CPU info (AVX2, flags)
flask>=3.0.0        # Web dashboard
```

All packages are **auto-installed** on first run if missing. Python **3.9+** required.

---

## 🖥️ Hardware Detection

- **CPU**: Name, cores (physical/logical), frequency, benchmark score, AVX2 support
- **RAM**: Total, used, and platform-specific memory details when available
- **GPU**: VRAM, driver, CUDA/Metal acceleration — NVIDIA via `nvidia-smi`, AMD/Intel via WMI on Windows, Apple Silicon via `system_profiler` on macOS
- **Disk**: Total/free space, read/write speed, SSD vs HDD detection
- **OS**: Automatically shows Windows build, Linux distro, or macOS version depending on the current system

The recommendation engine uses this hardware profile to decide:

- which coding models fit comfortably right now
- which larger model size in a family is still realistic
- which RAM / VRAM / unified-memory upgrade would unlock stronger local models

---

## 🤖 Live Model Recommendations

Instead of shipping a static shortlist, the app now builds recommendations from the live Ollama catalog.

What you get:

- **Coding-first picks** for local development machines
- **Best size per family** such as `7b`, `14b`, `24b`, `32b`, etc.
- **Next jump** guidance showing which larger size needs more RAM or VRAM
- **Auto-updating model coverage** when new families appear in Ollama Library

Typical families that can appear in recommendations include:

- `qwen2.5-coder`
- `deepseek-coder-v2`
- `starcoder2`
- `codestral`
- `devstral`
- `codellama`
- `gemma4`
- `deepseek-r1`
- `qwen3`
- `nomic-embed-text`

The exact list changes over time because it is driven by the live catalog rather than hardcoded entries.

---

## ☁️ API vs Local Comparison

Compares your hardware against **14 cloud AI providers**:

`OpenAI` · `Anthropic` · `Google Gemini` · `Groq` · `Together AI` · `Mistral` · `Cohere` · `Perplexity` · `Fireworks` · `DeepInfra` · `Anyscale` · `Replicate` · `Hugging Face` · `AWS Bedrock`

**Metrics compared:**
- ✅ Inference speed (tokens/sec)
- ✅ First-token latency (ms)
- ✅ Cost per 1M tokens (input + output)
- ✅ Estimated monthly electricity cost
- ✅ Break-even point (when local becomes cheaper)
- ✅ Feature matrix (offline, privacy, customisation, no rate limits)

---

## 📊 AI Suitability Score

| Score | Tier | Meaning |
|---|---|---|
| 85–100 | **S+** | Flagship AI workstation — runs everything |
| 70–84 | **S** | Excellent — handles most large models |
| 55–69 | **A** | Great — runs 13B+ models smoothly |
| 40–54 | **B** | Good — best with 7B models |
| 25–39 | **C** | Fair — 3B models, CPU inference |
| 10–24 | **D** | Limited — small/quantised models only |
| 0–9 | **F** | Not recommended for local AI |

---

## 🔧 Troubleshooting

**GPU not detected?**
- Install NVIDIA drivers: https://www.nvidia.com/drivers
- For AMD/Intel, WMI fallback is used automatically on Windows
- On Apple Silicon Macs, the app uses Metal + unified memory detection instead of CUDA/DirectX

**New models are not showing up yet?**
- The app fetches the live Ollama Library catalog on startup
- If Ollama Library cannot be reached, it uses a cached copy until the next successful refresh
- Re-run `./start.sh` or `python ai_pc_checker.py` to refresh recommendations

**OS name looks wrong?**
- The latest version now detects Windows, Linux, and macOS separately in both the web and CLI apps
- If you still see the wrong OS, pull the latest changes and rerun `./start.sh` or `python ai_pc_checker.py`

**Flask port already in use?**
The app auto-selects a free port on every run — this should never happen.

**Import errors?**
```bash
pip install -r requirements.txt --force-reinstall
```

**nvidia-smi not found?**
Install NVIDIA CUDA Toolkit: https://developer.nvidia.com/cuda-downloads

---

## 📁 Project Structure

```
ai-pc-checker/
├── model_catalog.py    # Live Ollama catalog parser + recommendation logic
├── ai_pc_web.py        # Flask web dashboard (main app)
├── ai_pc_checker.py    # CLI version (Rich terminal UI)
├── requirements.txt    # Python dependencies
├── install.sh          # Linux/macOS/WSL install script
├── start.sh            # Linux/macOS/WSL start script
├── run_checker.bat     # Windows launcher
├── screenshot.png      # Dashboard screenshot
└── README.md           # This file
```

---

## 📄 License

MIT License — free to use, modify, and distribute.

---

## 🤝 Contributing

1. Fork the repo
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Commit your changes: `git commit -m 'Add my feature'`
4. Push: `git push origin feature/my-feature`
5. Open a Pull Request

---

## ⭐ Star this repo if it helped you choose the right AI setup!
