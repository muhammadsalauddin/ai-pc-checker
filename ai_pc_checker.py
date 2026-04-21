#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
====================================================================
   AI PC SUITABILITY CHECKER v2.0
   Full Hardware Analysis + Local AI Compatibility Report
====================================================================
   Checks: CPU, RAM, VRAM, Disk, GPU Tier, AI Inference FPS
   Recommends: Best local AI models for your hardware
   Provides: Installation commands & setup guides
====================================================================
"""

import sys
import os
import subprocess
import platform
import json
import time
import math
import struct
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any

# ─────────────────────────────────────────────────────────────────
# STEP 0 ─ AUTO-INSTALL MISSING DEPENDENCIES
# ─────────────────────────────────────────────────────────────────
REQUIRED = {
    "psutil":  "psutil",
    "rich":    "rich",
    "GPUtil":  "gputil",
    "cpuinfo": "py-cpuinfo",
}

def _auto_install():
    import importlib
    # Python version check
    vi = sys.version_info
    if vi < (3, 9):
        print(f"\n[Setup] WARNING: Python {vi.major}.{vi.minor} detected. Python 3.9+ required.", flush=True)
    # Upgrade pip first to avoid install failures on Python 3.12/3.13/3.14
    try:
        subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade", "pip", "-q"],
                       capture_output=True, timeout=60)
    except Exception:
        pass
    missing = []
    for imp, pkg in REQUIRED.items():
        try:
            importlib.import_module(imp)
        except ImportError:
            missing.append((imp, pkg))
    if not missing:
        return
    print(f"\n[Setup] Installing packages: {', '.join(p for _,p in missing)} …", flush=True)
    for imp, pkg in missing:
        ok = False
        for extra in ([], ["--user"]):
            try:
                r = subprocess.run(
                    [sys.executable, "-m", "pip", "install", pkg, "-q"] + extra,
                    capture_output=True, text=True, timeout=120
                )
                if r.returncode == 0:
                    ok = True; break
            except Exception:
                pass
        if not ok:
            print(f"[Setup] ERROR: Could not auto-install '{pkg}'.", flush=True)
            print(f"  Please run manually:  pip install {pkg}", flush=True)
            print(f"  Then restart this script.\n", flush=True)
    print("[Setup] Done – re-importing...\n", flush=True)

_auto_install()

# ─────────────────────────────────────────────────────────────────
# IMPORTS (after auto-install)
# ─────────────────────────────────────────────────────────────────
import psutil
import GPUtil

from rich.console   import Console
from rich.table     import Table
from rich.panel     import Panel
from rich.text      import Text
from rich.columns   import Columns
from rich.rule      import Rule
from rich.progress  import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
from rich           import box
from rich.padding   import Padding
from rich.markup    import escape

try:
    import cpuinfo as py_cpuinfo
    HAS_CPUINFO = True
except ImportError:
    HAS_CPUINFO = False

console = Console(highlight=False)

# ─────────────────────────────────────────────────────────────────
# GPU PERFORMANCE DATABASE  (VRAM GB, AI-score, SD fps, token/s)
# ─────────────────────────────────────────────────────────────────
GPU_DB: Dict[str, Dict] = {
    # ── NVIDIA RTX 50 Series ──────────────────────────────────────
    "RTX 5090":     {"tier":"S+","vram":32,"score":120,"sd_fps":40,"tok_s":200},
    "RTX 5080":     {"tier":"S+","vram":16,"score":105,"sd_fps":32,"tok_s":160},
    "RTX 5070 Ti":  {"tier":"S", "vram":16,"score": 90,"sd_fps":26,"tok_s":130},
    "RTX 5070":     {"tier":"A+","vram":12,"score": 78,"sd_fps":20,"tok_s":100},
    # ── NVIDIA RTX 40 Series ──────────────────────────────────────
    "RTX 4090":     {"tier":"S", "vram":24,"score":100,"sd_fps":28,"tok_s":140},
    "RTX 4080 SUPER":{"tier":"S","vram":16,"score": 90,"sd_fps":23,"tok_s":115},
    "RTX 4080":     {"tier":"S", "vram":16,"score": 85,"sd_fps":20,"tok_s":100},
    "RTX 4070 Ti SUPER":{"tier":"A+","vram":16,"score":78,"sd_fps":17,"tok_s":88},
    "RTX 4070 Ti":  {"tier":"A+","vram":12,"score": 72,"sd_fps":15,"tok_s":78},
    "RTX 4070 SUPER":{"tier":"A+","vram":12,"score":68,"sd_fps":14,"tok_s":72},
    "RTX 4070":     {"tier":"A", "vram":12,"score": 60,"sd_fps":12,"tok_s":60},
    "RTX 4060 Ti":  {"tier":"B+","vram": 8,"score": 52,"sd_fps": 9,"tok_s":48},
    "RTX 4060":     {"tier":"B", "vram": 8,"score": 44,"sd_fps": 7,"tok_s":38},
    "RTX 4050":     {"tier":"B-","vram": 6,"score": 36,"sd_fps": 5,"tok_s":28},
    # ── NVIDIA RTX 30 Series ──────────────────────────────────────
    "RTX 3090 Ti":  {"tier":"A+","vram":24,"score": 80,"sd_fps":14,"tok_s":76},
    "RTX 3090":     {"tier":"A+","vram":24,"score": 75,"sd_fps":13,"tok_s":72},
    "RTX 3080 Ti":  {"tier":"A", "vram":12,"score": 68,"sd_fps":12,"tok_s":64},
    "RTX 3080":     {"tier":"A", "vram":10,"score": 62,"sd_fps":11,"tok_s":58},
    "RTX 3070 Ti":  {"tier":"B+","vram": 8,"score": 52,"sd_fps": 9,"tok_s":46},
    "RTX 3070":     {"tier":"B+","vram": 8,"score": 50,"sd_fps": 8,"tok_s":42},
    "RTX 3060 Ti":  {"tier":"B", "vram": 8,"score": 44,"sd_fps": 7,"tok_s":36},
    "RTX 3060":     {"tier":"B", "vram":12,"score": 40,"sd_fps": 6,"tok_s":30},
    "RTX 3050":     {"tier":"C+","vram": 8,"score": 30,"sd_fps": 4,"tok_s":22},
    # ── NVIDIA RTX 20 Series ──────────────────────────────────────
    "RTX 2080 Ti":  {"tier":"A", "vram":11,"score": 58,"sd_fps": 9,"tok_s":50},
    "RTX 2080 SUPER":{"tier":"B+","vram":8,"score": 48,"sd_fps": 7,"tok_s":38},
    "RTX 2080":     {"tier":"B+","vram": 8,"score": 46,"sd_fps": 7,"tok_s":36},
    "RTX 2070 SUPER":{"tier":"B","vram": 8,"score": 42,"sd_fps": 6,"tok_s":32},
    "RTX 2070":     {"tier":"B", "vram": 8,"score": 40,"sd_fps": 6,"tok_s":30},
    "RTX 2060 SUPER":{"tier":"B","vram": 8,"score": 36,"sd_fps": 5,"tok_s":26},
    "RTX 2060":     {"tier":"C+","vram": 6,"score": 32,"sd_fps": 4,"tok_s":22},
    # ── NVIDIA GTX Series ─────────────────────────────────────────
    "GTX 1080 Ti":  {"tier":"B", "vram":11,"score": 42,"sd_fps": 5,"tok_s":26},
    "GTX 1080":     {"tier":"C+","vram": 8,"score": 34,"sd_fps": 4,"tok_s":20},
    "GTX 1070 Ti":  {"tier":"C+","vram": 8,"score": 30,"sd_fps": 3,"tok_s":16},
    "GTX 1070":     {"tier":"C+","vram": 8,"score": 28,"sd_fps": 3,"tok_s":14},
    "GTX 1060":     {"tier":"C", "vram": 6,"score": 22,"sd_fps": 2,"tok_s":10},
    "GTX 1650":     {"tier":"C", "vram": 4,"score": 18,"sd_fps": 2,"tok_s": 8},
    "GTX 1660 Ti":  {"tier":"C+","vram": 6,"score": 26,"sd_fps": 3,"tok_s":12},
    "GTX 1660 SUPER":{"tier":"C+","vram":6,"score": 25,"sd_fps": 3,"tok_s":11},
    "GTX 1660":     {"tier":"C", "vram": 6,"score": 22,"sd_fps": 2,"tok_s":10},
    # ── AMD RX 7000 Series ────────────────────────────────────────
    "RX 7900 XTX":  {"tier":"A+","vram":24,"score": 82,"sd_fps":14,"tok_s":70},
    "RX 7900 XT":   {"tier":"A", "vram":20,"score": 72,"sd_fps":12,"tok_s":60},
    "RX 7900 GRE":  {"tier":"A", "vram":16,"score": 65,"sd_fps":10,"tok_s":52},
    "RX 7800 XT":   {"tier":"B+","vram":16,"score": 55,"sd_fps": 8,"tok_s":40},
    "RX 7700 XT":   {"tier":"B+","vram":12,"score": 50,"sd_fps": 7,"tok_s":34},
    "RX 7600":      {"tier":"B", "vram": 8,"score": 38,"sd_fps": 5,"tok_s":24},
    # ── AMD RX 6000 Series ────────────────────────────────────────
    "RX 6950 XT":   {"tier":"A", "vram":16,"score": 68,"sd_fps":10,"tok_s":52},
    "RX 6900 XT":   {"tier":"A", "vram":16,"score": 65,"sd_fps": 9,"tok_s":48},
    "RX 6800 XT":   {"tier":"A", "vram":16,"score": 60,"sd_fps": 8,"tok_s":44},
    "RX 6800":      {"tier":"B+","vram":16,"score": 55,"sd_fps": 7,"tok_s":38},
    "RX 6750 XT":   {"tier":"B+","vram":12,"score": 48,"sd_fps": 6,"tok_s":32},
    "RX 6700 XT":   {"tier":"B+","vram":12,"score": 45,"sd_fps": 5,"tok_s":28},
    "RX 6700":      {"tier":"B", "vram":10,"score": 40,"sd_fps": 5,"tok_s":24},
    "RX 6650 XT":   {"tier":"B", "vram": 8,"score": 36,"sd_fps": 4,"tok_s":20},
    "RX 6600 XT":   {"tier":"B", "vram": 8,"score": 34,"sd_fps": 4,"tok_s":18},
    "RX 6600":      {"tier":"C+","vram": 8,"score": 30,"sd_fps": 4,"tok_s":16},
    # ── AMD RX 5000 Series ────────────────────────────────────────
    "RX 5700 XT":   {"tier":"C+","vram": 8,"score": 32,"sd_fps": 4,"tok_s":16},
    "RX 5700":      {"tier":"C+","vram": 8,"score": 28,"sd_fps": 3,"tok_s":13},
    "RX 5600 XT":   {"tier":"C", "vram": 6,"score": 24,"sd_fps": 3,"tok_s":10},
    # ── Intel Arc Series ──────────────────────────────────────────
    "Arc A770":     {"tier":"B", "vram":16,"score": 40,"sd_fps": 5,"tok_s":22},
    "Arc A750":     {"tier":"B-","vram": 8,"score": 34,"sd_fps": 4,"tok_s":18},
    "Arc A580":     {"tier":"C+","vram": 8,"score": 28,"sd_fps": 3,"tok_s":12},
    "Arc A380":     {"tier":"C", "vram": 6,"score": 20,"sd_fps": 2,"tok_s": 8},
    # ── Integrated / Mobile ───────────────────────────────────────
    "Intel UHD":    {"tier":"F", "vram": 2,"score":  5,"sd_fps": 0,"tok_s": 2},
    "Intel Iris":   {"tier":"F", "vram": 2,"score":  6,"sd_fps": 0,"tok_s": 3},
    "Radeon Graphics":{"tier":"F","vram": 2,"score": 6,"sd_fps": 0,"tok_s": 3},
    "Vega":         {"tier":"F", "vram": 2,"score":  7,"sd_fps": 0,"tok_s": 3},
}

TIER_COLORS = {
    "S+": "bright_magenta", "S": "bright_cyan",
    "A+": "bright_green",   "A": "green",
    "B+": "yellow",         "B": "yellow",
    "B-": "dark_orange",    "C+": "orange3",
    "C":  "orange1",        "F": "red",
}

# ─────────────────────────────────────────────────────────────────
# AI MODELS DATABASE
#  keys: name, min_ram_gb, min_vram_gb, model_size_gb,
#        cpu_ok, quality (1-5), category, description,
#        ollama, lmstudio, platforms, tags
# ─────────────────────────────────────────────────────────────────
AI_MODELS: List[Dict] = [
    # ── Ultra-Light (can run on almost anything) ──────────────────
    {
        "name": "Phi-3 Mini 3.8B",
        "min_ram_gb": 4,   "min_vram_gb": 2,  "model_size_gb": 2.3,
        "cpu_ok": True,    "quality": 3,       "category": "Text / Chat",
        "description": "Microsoft's tiny-but-smart model. Great for low-end PCs.",
        "ollama": "ollama run phi3:mini",
        "lmstudio": "phi-3-mini-4k-instruct",
        "platforms": ["Ollama","LM Studio","GPT4All"],
        "tags": ["CPU-OK","Fast","Lightweight"],
    },
    {
        "name": "Llama 3.2 1B",
        "min_ram_gb": 3,   "min_vram_gb": 1,  "model_size_gb": 0.7,
        "cpu_ok": True,    "quality": 2,       "category": "Text / Chat",
        "description": "Smallest Meta model – ultra-fast even on CPU.",
        "ollama": "ollama run llama3.2:1b",
        "lmstudio": "llama-3.2-1b-instruct",
        "platforms": ["Ollama","LM Studio"],
        "tags": ["CPU-OK","Ultra-Fast","Tiny"],
    },
    {
        "name": "Llama 3.2 3B",
        "min_ram_gb": 4,   "min_vram_gb": 2,  "model_size_gb": 2.0,
        "cpu_ok": True,    "quality": 3,       "category": "Text / Chat",
        "description": "Balanced Meta model for everyday tasks.",
        "ollama": "ollama run llama3.2:3b",
        "lmstudio": "llama-3.2-3b-instruct",
        "platforms": ["Ollama","LM Studio"],
        "tags": ["CPU-OK","Balanced"],
    },
    {
        "name": "Gemma 2B",
        "min_ram_gb": 4,   "min_vram_gb": 2,  "model_size_gb": 1.7,
        "cpu_ok": True,    "quality": 2,       "category": "Text / Chat",
        "description": "Google's compact open model.",
        "ollama": "ollama run gemma:2b",
        "lmstudio": "gemma-2b-it",
        "platforms": ["Ollama","LM Studio","GPT4All"],
        "tags": ["CPU-OK","Lightweight"],
    },
    {
        "name": "TinyLlama 1.1B",
        "min_ram_gb": 3,   "min_vram_gb": 1,  "model_size_gb": 0.6,
        "cpu_ok": True,    "quality": 1,       "category": "Text / Chat",
        "description": "Runs everywhere, minimal resources.",
        "ollama": "ollama run tinyllama",
        "lmstudio": "tinyllama-1.1b-chat",
        "platforms": ["Ollama","LM Studio","GPT4All","llama.cpp"],
        "tags": ["CPU-OK","Ultra-Tiny"],
    },
    # ── Mid-Range (7B) ─────────────────────────────────────────────
    {
        "name": "Mistral 7B v0.3",
        "min_ram_gb": 8,   "min_vram_gb": 4,  "model_size_gb": 4.1,
        "cpu_ok": True,    "quality": 4,       "category": "Text / Chat",
        "description": "Best-in-class 7B model. Highly recommended.",
        "ollama": "ollama run mistral",
        "lmstudio": "mistral-7b-instruct-v0.3",
        "platforms": ["Ollama","LM Studio","GPT4All"],
        "tags": ["Recommended","Balanced","CPU-OK"],
    },
    {
        "name": "Llama 3.1 8B",
        "min_ram_gb": 8,   "min_vram_gb": 4,  "model_size_gb": 4.7,
        "cpu_ok": True,    "quality": 4,       "category": "Text / Chat",
        "description": "Meta's flagship small model. Excellent quality.",
        "ollama": "ollama run llama3.1:8b",
        "lmstudio": "meta-llama-3.1-8b-instruct",
        "platforms": ["Ollama","LM Studio","GPT4All"],
        "tags": ["Recommended","Best-Quality-7B"],
    },
    {
        "name": "Gemma 2 9B",
        "min_ram_gb": 10,  "min_vram_gb": 6,  "model_size_gb": 5.4,
        "cpu_ok": True,    "quality": 4,       "category": "Text / Chat",
        "description": "Google's improved 9B model – punches above its weight.",
        "ollama": "ollama run gemma2:9b",
        "lmstudio": "gemma-2-9b-it",
        "platforms": ["Ollama","LM Studio"],
        "tags": ["High-Quality","Recommended"],
    },
    {
        "name": "Qwen2.5 7B",
        "min_ram_gb": 8,   "min_vram_gb": 4,  "model_size_gb": 4.4,
        "cpu_ok": True,    "quality": 4,       "category": "Text / Chat",
        "description": "Alibaba's multilingual model, top-tier for 7B class.",
        "ollama": "ollama run qwen2.5:7b",
        "lmstudio": "qwen2.5-7b-instruct",
        "platforms": ["Ollama","LM Studio"],
        "tags": ["Multilingual","Top-7B"],
    },
    # ── Performance (13B) ─────────────────────────────────────────
    {
        "name": "Llama 3.1 13B",
        "min_ram_gb": 12,  "min_vram_gb": 8,  "model_size_gb": 7.4,
        "cpu_ok": False,   "quality": 4,       "category": "Text / Chat",
        "description": "Great balance between quality and resource use.",
        "ollama": "ollama run llama3.1:13b",
        "lmstudio": "meta-llama-3.1-13b-instruct",
        "platforms": ["Ollama","LM Studio"],
        "tags": ["High-Quality","GPU-Recommended"],
    },
    {
        "name": "Mistral Nemo 12B",
        "min_ram_gb": 12,  "min_vram_gb": 8,  "model_size_gb": 7.1,
        "cpu_ok": False,   "quality": 4,       "category": "Text / Chat",
        "description": "Latest Mistral model with extended context.",
        "ollama": "ollama run mistral-nemo",
        "lmstudio": "mistral-nemo-instruct-2407",
        "platforms": ["Ollama","LM Studio"],
        "tags": ["Long-Context","High-Quality"],
    },
    # ── High-End (30-70B) ─────────────────────────────────────────
    {
        "name": "Llama 3.1 70B (Q4)",
        "min_ram_gb": 40,  "min_vram_gb": 24, "model_size_gb": 39.0,
        "cpu_ok": False,   "quality": 5,       "category": "Text / Chat",
        "description": "GPT-4 level quality. Needs high-end GPU/server.",
        "ollama": "ollama run llama3.1:70b",
        "lmstudio": "meta-llama-3.1-70b-instruct",
        "platforms": ["Ollama","LM Studio"],
        "tags": ["GPT-4 Class","Needs 24GB+ VRAM"],
    },
    {
        "name": "Mixtral 8x7B (Q4)",
        "min_ram_gb": 32,  "min_vram_gb": 20, "model_size_gb": 26.0,
        "cpu_ok": False,   "quality": 5,       "category": "Text / Chat",
        "description": "Mixture-of-experts model. Excellent reasoning.",
        "ollama": "ollama run mixtral:8x7b",
        "lmstudio": "mixtral-8x7b-instruct",
        "platforms": ["Ollama","LM Studio"],
        "tags": ["Reasoning","Expert"],
    },
    # ── 2025 New Models ───────────────────────────────────────────
    {
        "name": "Phi-4 14B",
        "min_ram_gb": 12,  "min_vram_gb": 8,  "model_size_gb": 8.2,
        "cpu_ok": False,   "quality": 5,       "category": "Text / Chat",
        "description": "Microsoft Phi-4 — punches well above its size for reasoning.",
        "ollama": "ollama run phi4",
        "lmstudio": "phi-4-14b-instruct",
        "platforms": ["Ollama","LM Studio"],
        "tags": ["Reasoning","High-Quality","2025"],
    },
    {
        "name": "Phi-4 Mini 3.8B",
        "min_ram_gb": 4,   "min_vram_gb": 2,  "model_size_gb": 2.5,
        "cpu_ok": True,    "quality": 4,       "category": "Text / Chat",
        "description": "Compact Phi-4 — great reasoning on low-end hardware.",
        "ollama": "ollama run phi4-mini",
        "lmstudio": "phi-4-mini-instruct",
        "platforms": ["Ollama","LM Studio"],
        "tags": ["CPU-OK","Reasoning","2025"],
    },
    {
        "name": "Gemma 3 4B",
        "min_ram_gb": 6,   "min_vram_gb": 3,  "model_size_gb": 3.3,
        "cpu_ok": True,    "quality": 4,       "category": "Text / Chat",
        "description": "Google Gemma 3 — 128K context, multimodal support.",
        "ollama": "ollama run gemma3:4b",
        "lmstudio": "gemma-3-4b-it",
        "platforms": ["Ollama","LM Studio"],
        "tags": ["CPU-OK","Long-Context","2025"],
    },
    {
        "name": "Gemma 3 12B",
        "min_ram_gb": 14,  "min_vram_gb": 8,  "model_size_gb": 8.1,
        "cpu_ok": False,   "quality": 5,       "category": "Text / Chat",
        "description": "Google Gemma 3 12B — strong multilingual + vision.",
        "ollama": "ollama run gemma3:12b",
        "lmstudio": "gemma-3-12b-it",
        "platforms": ["Ollama","LM Studio"],
        "tags": ["High-Quality","Vision","2025"],
    },
    {
        "name": "Gemma 3 27B (Q4)",
        "min_ram_gb": 20,  "min_vram_gb": 16, "model_size_gb": 17.0,
        "cpu_ok": False,   "quality": 5,       "category": "Text / Chat",
        "description": "Google Gemma 3 27B — Gemini-class quality, open weights.",
        "ollama": "ollama run gemma3:27b",
        "lmstudio": "gemma-3-27b-it",
        "platforms": ["Ollama","LM Studio"],
        "tags": ["Flagship","Gemini-Class","2025"],
    },
    {
        "name": "Llama 3.3 70B (Q4)",
        "min_ram_gb": 40,  "min_vram_gb": 24, "model_size_gb": 40.0,
        "cpu_ok": False,   "quality": 5,       "category": "Text / Chat",
        "description": "Meta Llama 3.3 70B — best open-source instruction model.",
        "ollama": "ollama run llama3.3:70b",
        "lmstudio": "meta-llama-3.3-70b-instruct",
        "platforms": ["Ollama","LM Studio"],
        "tags": ["Best-Open","GPT-4-Class","2025"],
    },
    {
        "name": "Mistral Small 3 22B",
        "min_ram_gb": 16,  "min_vram_gb": 12, "model_size_gb": 13.5,
        "cpu_ok": False,   "quality": 5,       "category": "Text / Chat",
        "description": "Mistral Small 3 22B — beats GPT-4o-mini, best mid-size (2025).",
        "ollama": "ollama run mistral-small3",
        "lmstudio": "mistral-small-3-22b-instruct",
        "platforms": ["Ollama","LM Studio"],
        "tags": ["Best-Mid","Recommended","2025"],
    },
    {
        "name": "Qwen2.5 14B",
        "min_ram_gb": 16,  "min_vram_gb": 10, "model_size_gb": 9.0,
        "cpu_ok": False,   "quality": 5,       "category": "Text / Chat",
        "description": "Alibaba Qwen2.5 14B — excellent multilingual & reasoning.",
        "ollama": "ollama run qwen2.5:14b",
        "lmstudio": "qwen2.5-14b-instruct",
        "platforms": ["Ollama","LM Studio"],
        "tags": ["Multilingual","Reasoning","2025"],
    },
    {
        "name": "Qwen2.5 72B (Q4)",
        "min_ram_gb": 48,  "min_vram_gb": 32, "model_size_gb": 43.0,
        "cpu_ok": False,   "quality": 5,       "category": "Text / Chat",
        "description": "Alibaba Qwen2.5 72B — GPT-4 class, top open multilingual.",
        "ollama": "ollama run qwen2.5:72b",
        "lmstudio": "qwen2.5-72b-instruct",
        "platforms": ["Ollama","LM Studio"],
        "tags": ["GPT-4-Class","Multilingual","2025"],
    },
    {
        "name": "Qwen3 8B",
        "min_ram_gb": 10,  "min_vram_gb": 6,  "model_size_gb": 5.5,
        "cpu_ok": True,    "quality": 5,       "category": "Text / Chat",
        "description": "Alibaba Qwen3 8B — hybrid thinking/chat, SOTA at its size.",
        "ollama": "ollama run qwen3:8b",
        "lmstudio": "qwen3-8b-instruct",
        "platforms": ["Ollama","LM Studio"],
        "tags": ["Thinking","SOTA-8B","2025"],
    },
    {
        "name": "Qwen3 14B",
        "min_ram_gb": 16,  "min_vram_gb": 10, "model_size_gb": 9.5,
        "cpu_ok": False,   "quality": 5,       "category": "Text / Chat",
        "description": "Alibaba Qwen3 14B — hybrid thinking mode, strong reasoning.",
        "ollama": "ollama run qwen3:14b",
        "lmstudio": "qwen3-14b-instruct",
        "platforms": ["Ollama","LM Studio"],
        "tags": ["Thinking","Reasoning","2025"],
    },
    {
        "name": "Qwen3 32B (Q4)",
        "min_ram_gb": 24,  "min_vram_gb": 20, "model_size_gb": 20.0,
        "cpu_ok": False,   "quality": 5,       "category": "Text / Chat",
        "description": "Alibaba Qwen3 32B — rivals GPT-4o, thinking + non-thinking modes.",
        "ollama": "ollama run qwen3:32b",
        "lmstudio": "qwen3-32b-instruct",
        "platforms": ["Ollama","LM Studio"],
        "tags": ["GPT-4o-Rival","Thinking","2025"],
    },
    {
        "name": "DeepSeek-V3 (Q4)",
        "min_ram_gb": 48,  "min_vram_gb": 32, "model_size_gb": 42.0,
        "cpu_ok": False,   "quality": 5,       "category": "Text / Chat",
        "description": "DeepSeek V3 685B MoE — #1 open model. Multi-GPU needed.",
        "ollama": "ollama run deepseek-v3",
        "lmstudio": "deepseek-v3",
        "platforms": ["Ollama","LM Studio"],
        "tags": ["#1-Open","MoE","Multi-GPU","2025"],
    },
    {
        "name": "Kimi K2 (Q4)",
        "min_ram_gb": 64,  "min_vram_gb": 48, "model_size_gb": 60.0,
        "cpu_ok": False,   "quality": 5,       "category": "Text / Chat",
        "description": "Moonshot Kimi K2 1T MoE — top agentic & coding model (2025).",
        "ollama": "ollama run kimi-k2",
        "lmstudio": "kimi-k2",
        "platforms": ["Ollama","LM Studio"],
        "tags": ["Agentic","MoE","Multi-GPU","2025"],
    },
    {
        "name": "Claude 3.5 Haiku (via API)",
        "min_ram_gb": 4,   "min_vram_gb": 0,  "model_size_gb": 0,
        "cpu_ok": True,    "quality": 4,       "category": "Text / Chat",
        "description": "Anthropic Claude 3.5 Haiku — fastest Claude, API-only.",
        "ollama": None,    "lmstudio": None,
        "platforms": ["Anthropic API"],
        "tags": ["API-Only","Fast","Claude"],
    },
    {
        "name": "Claude Sonnet 4.5 (via API)",
        "min_ram_gb": 4,   "min_vram_gb": 0,  "model_size_gb": 0,
        "cpu_ok": True,    "quality": 5,       "category": "Text / Chat",
        "description": "Anthropic Claude Sonnet 4.5 — balanced intelligence & speed, API-only.",
        "ollama": None,    "lmstudio": None,
        "platforms": ["Anthropic API"],
        "tags": ["API-Only","Recommended","Claude","2025"],
    },
    {
        "name": "Claude Sonnet 4.7 (via API)",
        "min_ram_gb": 4,   "min_vram_gb": 0,  "model_size_gb": 0,
        "cpu_ok": True,    "quality": 5,       "category": "Text / Chat",
        "description": "Anthropic Claude Sonnet 4.7 — enhanced reasoning, extended thinking, API-only.",
        "ollama": None,    "lmstudio": None,
        "platforms": ["Anthropic API"],
        "tags": ["API-Only","Extended-Thinking","Claude","2025"],
    },
    {
        "name": "Claude Opus 4 (via API)",
        "min_ram_gb": 4,   "min_vram_gb": 0,  "model_size_gb": 0,
        "cpu_ok": True,    "quality": 5,       "category": "Text / Chat",
        "description": "Anthropic Claude Opus 4 — most powerful Claude, API-only.",
        "ollama": None,    "lmstudio": None,
        "platforms": ["Anthropic API"],
        "tags": ["API-Only","Most-Powerful","Claude","2025"],
    },
    # ── Code Models ───────────────────────────────────────────────
    {
        "name": "DeepSeek Coder 1.3B",
        "min_ram_gb": 3,   "min_vram_gb": 1,  "model_size_gb": 0.8,
        "cpu_ok": True,    "quality": 3,       "category": "Code Generation",
        "description": "Lightweight code model. Works on any PC.",
        "ollama": "ollama run deepseek-coder:1.3b",
        "lmstudio": "deepseek-coder-1.3b-instruct",
        "platforms": ["Ollama","LM Studio"],
        "tags": ["Code","CPU-OK","Lightweight"],
    },
    {
        "name": "DeepSeek Coder 6.7B",
        "min_ram_gb": 8,   "min_vram_gb": 4,  "model_size_gb": 3.8,
        "cpu_ok": True,    "quality": 4,       "category": "Code Generation",
        "description": "Excellent coding assistant, better than Copilot base.",
        "ollama": "ollama run deepseek-coder:6.7b",
        "lmstudio": "deepseek-coder-6.7b-instruct",
        "platforms": ["Ollama","LM Studio"],
        "tags": ["Code","Recommended"],
    },
    {
        "name": "Qwen2.5-Coder 7B",
        "min_ram_gb": 8,   "min_vram_gb": 4,  "model_size_gb": 4.5,
        "cpu_ok": True,    "quality": 5,       "category": "Code Generation",
        "description": "Best open-source code model in 7B class (2024).",
        "ollama": "ollama run qwen2.5-coder:7b",
        "lmstudio": "qwen2.5-coder-7b-instruct",
        "platforms": ["Ollama","LM Studio"],
        "tags": ["Code","Best-Code-7B","Recommended"],
    },
    {
        "name": "Qwen2.5-Coder 32B (Q4)",
        "min_ram_gb": 24,  "min_vram_gb": 20, "model_size_gb": 20.0,
        "cpu_ok": False,   "quality": 5,       "category": "Code Generation",
        "description": "SOTA open-source code model — rivals GPT-4o for coding.",
        "ollama": "ollama run qwen2.5-coder:32b",
        "lmstudio": "qwen2.5-coder-32b-instruct",
        "platforms": ["Ollama","LM Studio"],
        "tags": ["Code","SOTA-Code","2025"],
    },
    {
        "name": "DeepSeek-R1 7B (Q4)",
        "min_ram_gb": 8,   "min_vram_gb": 5,  "model_size_gb": 4.7,
        "cpu_ok": True,    "quality": 5,       "category": "Code Generation",
        "description": "DeepSeek R1 distil 7B — chain-of-thought reasoning for code.",
        "ollama": "ollama run deepseek-r1:7b",
        "lmstudio": "deepseek-r1-7b",
        "platforms": ["Ollama","LM Studio"],
        "tags": ["Code","Reasoning","Chain-of-Thought","2025"],
    },
    {
        "name": "DeepSeek-R1 14B (Q4)",
        "min_ram_gb": 16,  "min_vram_gb": 10, "model_size_gb": 9.0,
        "cpu_ok": False,   "quality": 5,       "category": "Code Generation",
        "description": "DeepSeek R1 distil 14B — o1-level reasoning, best local reasoning model.",
        "ollama": "ollama run deepseek-r1:14b",
        "lmstudio": "deepseek-r1-14b",
        "platforms": ["Ollama","LM Studio"],
        "tags": ["Code","o1-Rival","Reasoning","2025"],
    },
    {
        "name": "Kimi K2 Coder (Q4)",
        "min_ram_gb": 64,  "min_vram_gb": 48, "model_size_gb": 60.0,
        "cpu_ok": False,   "quality": 5,       "category": "Code Generation",
        "description": "Moonshot Kimi K2 — #1 agentic coding model (2025), rivals Claude Sonnet.",
        "ollama": "ollama run kimi-k2",
        "lmstudio": "kimi-k2",
        "platforms": ["Ollama","LM Studio"],
        "tags": ["Code","Agentic","#1-Code","2025"],
    },
    {
        "name": "CodeLlama 13B",
        "min_ram_gb": 12,  "min_vram_gb": 8,  "model_size_gb": 7.3,
        "cpu_ok": False,   "quality": 4,       "category": "Code Generation",
        "description": "Meta's dedicated coding model.",
        "ollama": "ollama run codellama:13b",
        "lmstudio": "codellama-13b-instruct",
        "platforms": ["Ollama","LM Studio"],
        "tags": ["Code","GPU-Recommended"],
    },
    # ── Vision / Multimodal ───────────────────────────────────────
    {
        "name": "LLaVA 7B",
        "min_ram_gb": 8,   "min_vram_gb": 4,  "model_size_gb": 4.5,
        "cpu_ok": True,    "quality": 3,       "category": "Vision / Multimodal",
        "description": "Analyze images with a local AI model.",
        "ollama": "ollama run llava:7b",
        "lmstudio": "llava-v1.6-mistral-7b",
        "platforms": ["Ollama","LM Studio"],
        "tags": ["Vision","Image-Analysis"],
    },
    {
        "name": "LLaVA 13B",
        "min_ram_gb": 14,  "min_vram_gb": 8,  "model_size_gb": 8.0,
        "cpu_ok": False,   "quality": 4,       "category": "Vision / Multimodal",
        "description": "Higher quality vision model.",
        "ollama": "ollama run llava:13b",
        "lmstudio": "llava-v1.6-vicuna-13b",
        "platforms": ["Ollama","LM Studio"],
        "tags": ["Vision","GPU-Recommended"],
    },
    {
        "name": "Llama 3.2 Vision 11B",
        "min_ram_gb": 12,  "min_vram_gb": 8,  "model_size_gb": 8.0,
        "cpu_ok": False,   "quality": 5,       "category": "Vision / Multimodal",
        "description": "Meta's latest vision model — analyze images + documents.",
        "ollama": "ollama run llama3.2-vision:11b",
        "lmstudio": "llama-3.2-11b-vision-instruct",
        "platforms": ["Ollama","LM Studio"],
        "tags": ["Vision","2025","Recommended"],
    },
    {
        "name": "Gemma 3 Vision 12B",
        "min_ram_gb": 14,  "min_vram_gb": 8,  "model_size_gb": 8.1,
        "cpu_ok": False,   "quality": 5,       "category": "Vision / Multimodal",
        "description": "Google Gemma 3 with native vision and 128K context.",
        "ollama": "ollama run gemma3:12b",
        "lmstudio": "gemma-3-12b-vision",
        "platforms": ["Ollama","LM Studio"],
        "tags": ["Vision","Long-Context","2025"],
    },
    {
        "name": "Qwen2.5-VL 7B",
        "min_ram_gb": 10,  "min_vram_gb": 6,  "model_size_gb": 6.5,
        "cpu_ok": False,   "quality": 5,       "category": "Vision / Multimodal",
        "description": "Alibaba vision-language model — top open-source VLM (2025).",
        "ollama": "ollama run qwen2.5-vl:7b",
        "lmstudio": "qwen2.5-vl-7b-instruct",
        "platforms": ["Ollama","LM Studio"],
        "tags": ["Vision","SOTA-VLM","2025"],
    },
    # ── Image Generation ──────────────────────────────────────────
    {
        "name": "Stable Diffusion 1.5",
        "min_ram_gb": 6,   "min_vram_gb": 2,  "model_size_gb": 2.0,
        "cpu_ok": True,    "quality": 3,       "category": "Image Generation",
        "description": "Classic image generator. 512×512 images.",
        "ollama": None,
        "lmstudio": None,
        "platforms": ["AUTOMATIC1111","ComfyUI","Invoke AI"],
        "tags": ["Image-Gen","Classic"],
        "install_note": "Auto1111: https://github.com/AUTOMATIC1111/stable-diffusion-webui",
    },
    {
        "name": "Stable Diffusion XL",
        "min_ram_gb": 8,   "min_vram_gb": 6,  "model_size_gb": 6.5,
        "cpu_ok": False,   "quality": 4,       "category": "Image Generation",
        "description": "High-quality 1024×1024 image generator.",
        "ollama": None, "lmstudio": None,
        "platforms": ["AUTOMATIC1111","ComfyUI","Invoke AI"],
        "tags": ["Image-Gen","High-Quality","1024px"],
        "install_note": "ComfyUI: https://github.com/comfyanonymous/ComfyUI",
    },
    {
        "name": "FLUX.1 Schnell",
        "min_ram_gb": 16,  "min_vram_gb": 8,  "model_size_gb": 11.0,
        "cpu_ok": False,   "quality": 5,       "category": "Image Generation",
        "description": "State-of-the-art open image model (2024). Ultra-realistic.",
        "ollama": None, "lmstudio": None,
        "platforms": ["ComfyUI"],
        "tags": ["Image-Gen","SOTA","Best-Quality"],
        "install_note": "ComfyUI: https://github.com/comfyanonymous/ComfyUI",
    },
    # ── Audio / Speech ────────────────────────────────────────────
    {
        "name": "Whisper Tiny",
        "min_ram_gb": 2,   "min_vram_gb": 0,  "model_size_gb": 0.15,
        "cpu_ok": True,    "quality": 2,       "category": "Speech-to-Text",
        "description": "Ultra-fast transcription on any PC.",
        "ollama": None, "lmstudio": None,
        "platforms": ["Faster-Whisper","Whisper.cpp","OpenedAI-Speech"],
        "tags": ["Audio","CPU-OK","Ultra-Fast"],
        "install_note": "pip install faster-whisper",
    },
    {
        "name": "Whisper Large v3",
        "min_ram_gb": 8,   "min_vram_gb": 4,  "model_size_gb": 1.5,
        "cpu_ok": True,    "quality": 5,       "category": "Speech-to-Text",
        "description": "Best open-source speech recognition. 99+ languages.",
        "ollama": None, "lmstudio": None,
        "platforms": ["Faster-Whisper","Whisper.cpp"],
        "tags": ["Audio","Best-Quality","Multilingual"],
        "install_note": "pip install faster-whisper",
    },
    # ── Embedding Models ──────────────────────────────────────────
    {
        "name": "nomic-embed-text",
        "min_ram_gb": 2,   "min_vram_gb": 0,  "model_size_gb": 0.27,
        "cpu_ok": True,    "quality": 4,       "category": "Embeddings / RAG",
        "description": "Best local embedding model for RAG pipelines.",
        "ollama": "ollama run nomic-embed-text",
        "lmstudio": "nomic-embed-text-v1.5",
        "platforms": ["Ollama","LM Studio"],
        "tags": ["RAG","Embeddings","CPU-OK"],
    },
]

# ─────────────────────────────────────────────────────────────────
# PLATFORM INSTALLATION GUIDES
# ─────────────────────────────────────────────────────────────────
PLATFORMS = {
    "Ollama": {
        "url":   "https://ollama.com/download",
        "steps": [
            "Download from https://ollama.com/download (Windows installer)",
            "Run installer → Ollama runs as a system tray app",
            "Open Terminal and run your model: ollama run <model-name>",
            "API available at http://localhost:11434",
        ],
        "desc": "Easiest way to run LLMs locally. One-click install.",
    },
    "LM Studio": {
        "url":   "https://lmstudio.ai",
        "steps": [
            "Download from https://lmstudio.ai (Windows .exe)",
            "Install and open LM Studio",
            "Go to Discover tab → search and download models",
            "Load model and use Chat tab or API server (port 1234)",
        ],
        "desc": "Best GUI for local LLMs. Built-in model browser.",
    },
    "GPT4All": {
        "url":   "https://gpt4all.io",
        "steps": [
            "Download from https://gpt4all.io (Windows installer)",
            "Install and open GPT4All",
            "Use Model Explorer to download models",
            "Chat directly in the app",
        ],
        "desc": "User-friendly desktop chatbot app.",
    },
    "AUTOMATIC1111": {
        "url":   "https://github.com/AUTOMATIC1111/stable-diffusion-webui",
        "steps": [
            "Install Python 3.10 + Git",
            "git clone https://github.com/AUTOMATIC1111/stable-diffusion-webui",
            "Place model .safetensors in models/Stable-diffusion/",
            "Run webui-user.bat to install and launch",
            "Open http://127.0.0.1:7860 in browser",
        ],
        "desc": "Most popular Stable Diffusion WebUI.",
    },
    "ComfyUI": {
        "url":   "https://github.com/comfyanonymous/ComfyUI",
        "steps": [
            "Download portable version from GitHub releases",
            "Extract and place models in models/checkpoints/",
            "Run run_nvidia_gpu.bat (or run_cpu.bat for CPU)",
            "Open http://127.0.0.1:8188",
        ],
        "desc": "Node-based image generation. Supports FLUX.1.",
    },
    "Faster-Whisper": {
        "url":   "https://github.com/SYSTRAN/faster-whisper",
        "steps": [
            "pip install faster-whisper",
            "Python usage:",
            "  from faster_whisper import WhisperModel",
            "  model = WhisperModel('large-v3', device='cuda')",
            "  segments, _ = model.transcribe('audio.mp3')",
        ],
        "desc": "Fast Python Whisper library for transcription.",
    },
}

# ─────────────────────────────────────────────────────────────────
# HARDWARE DETECTION
# ─────────────────────────────────────────────────────────────────

def _run_ps(cmd: str, fallback="") -> str:
    """Run a PowerShell command, return stdout text."""
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command", cmd],
            capture_output=True, text=True, timeout=10
        )
        return r.stdout.strip()
    except Exception:
        return fallback


def _run_wmic(query: str, fallback="") -> str:
    try:
        r = subprocess.run(query.split(), capture_output=True, text=True, timeout=8)
        return r.stdout.strip()
    except Exception:
        return fallback


def get_cpu_info() -> Dict:
    info = {
        "name": platform.processor() or "Unknown CPU",
        "cores_physical": psutil.cpu_count(logical=False) or 1,
        "cores_logical":  psutil.cpu_count(logical=True)  or 1,
        "freq_base_mhz":  0.0,
        "freq_max_mhz":   0.0,
        "arch": platform.machine(),
        "bits": struct.calcsize("P") * 8,
        "avx2": False,
    }
    freq = psutil.cpu_freq()
    if freq:
        info["freq_base_mhz"] = freq.current
        info["freq_max_mhz"]  = freq.max or freq.current

    if HAS_CPUINFO:
        try:
            ci = py_cpuinfo.get_cpu_info()
            info["name"]  = ci.get("brand_raw", info["name"])
            info["avx2"]  = "avx2" in ci.get("flags", [])
            if not info["freq_max_mhz"] and ci.get("hz_advertised_friendly"):
                hz = ci["hz_advertised"][0]
                info["freq_max_mhz"] = hz / 1_000_000
        except Exception:
            pass
    else:
        # Fallback to PowerShell
        name = _run_ps("(Get-WmiObject Win32_Processor).Name")
        if name:
            info["name"] = name.splitlines()[0].strip()
        maxspeed = _run_ps("(Get-WmiObject Win32_Processor).MaxClockSpeed")
        if maxspeed.isdigit():
            info["freq_max_mhz"] = float(maxspeed)

    return info


def get_ram_info() -> Dict:
    vm = psutil.virtual_memory()
    info = {
        "total_gb": round(vm.total / (1024**3), 1),
        "available_gb": round(vm.available / (1024**3), 1),
        "used_gb": round(vm.used / (1024**3), 1),
        "percent": vm.percent,
        "speed_mhz": 0,
        "type": "Unknown",
        "channels": 0,
    }
    # Try to get RAM speed & type via WMI
    raw = _run_ps(
        "Get-WmiObject Win32_PhysicalMemory | "
        "Select-Object Speed,MemoryType,SMBIOSMemoryType,DeviceLocator | "
        "ConvertTo-Json -Compress"
    )
    if raw:
        try:
            data = json.loads(raw)
            if isinstance(data, dict):
                data = [data]
            speeds = [d.get("Speed", 0) for d in data if d.get("Speed")]
            if speeds:
                info["speed_mhz"] = max(speeds)
            info["channels"] = len(data)
            t = data[0].get("SMBIOSMemoryType", 0)
            type_map = {26: "DDR4", 34: "DDR5", 24: "DDR3", 20: "DDR2"}
            info["type"] = type_map.get(t, "DDR4")
        except Exception:
            pass
    return info


def get_gpu_info() -> List[Dict]:
    gpus = []

    # Method 1 – GPUtil (NVIDIA via nvidia-smi)
    try:
        nvidia_gpus = GPUtil.getGPUs()
        for g in nvidia_gpus:
            gpus.append({
                "name":     g.name,
                "vram_gb":  round(g.memoryTotal / 1024, 1),
                "vram_used_gb": round(g.memoryUsed / 1024, 1),
                "driver":   g.driver,
                "temp_c":   g.temperature,
                "load_pct": round(g.load * 100, 1),
                "vendor":   "NVIDIA",
                "cuda":     True,
            })
    except Exception:
        pass

    # Method 2 – Registry 64-bit VRAM lookup (fixes Win32_VideoController AdapterRAM 4 GB cap)
    _vram_reg: Dict[str, float] = {}
    reg_raw = _run_ps(
        "$path='HKLM:\\SYSTEM\\ControlSet001\\Control\\Class\\{4d36e968-e325-11ce-bfc1-08002be10318}';"
        "Get-ChildItem $path -EA SilentlyContinue|"
        "Where-Object{$_.PSChildName -match '^\\d{4}$'}|"
        "ForEach-Object{$p=Get-ItemProperty $_.PSPath -EA SilentlyContinue;"
        "if($p.DriverDesc){[PSCustomObject]@{Name=$p.DriverDesc;VRAM=$p.'HardwareInformation.qwMemorySize'}}}|"
        "ConvertTo-Json -Compress"
    )
    if reg_raw:
        try:
            rd = json.loads(reg_raw)
            if isinstance(rd, dict): rd = [rd]
            for entry in rd:
                rn = (entry.get("Name") or "").strip()
                rv = entry.get("VRAM") or 0
                if rn and rv:
                    _vram_reg[rn.lower()] = round(int(rv) / (1024**3), 1)
        except Exception:
            pass

    # Method 3 – PowerShell WMI (all GPUs including AMD/Intel)
    raw = _run_ps(
        "Get-WmiObject Win32_VideoController | "
        "Select-Object Name,AdapterRAM,DriverVersion,VideoProcessor | "
        "ConvertTo-Json -Compress"
    )
    if raw:
        try:
            data = json.loads(raw)
            if isinstance(data, dict):
                data = [data]
            for d in data:
                name = (d.get("Name") or "Unknown GPU").strip()
                # Skip if we already have from GPUtil
                if any(g["name"] in name or name in g["name"] for g in gpus):
                    continue
                # Prefer 64-bit registry value over 32-bit WMI AdapterRAM (which caps at ~4 GB)
                vram = _vram_reg.get(name.lower(), 0)
                if not vram:
                    ar = d.get("AdapterRAM") or 0
                    vram = round(int(ar) / (1024**3), 1) if ar else 0

                vendor = "Unknown"
                nl = name.lower()
                if "nvidia" in nl or "geforce" in nl or "rtx" in nl or "gtx" in nl:
                    vendor = "NVIDIA"
                elif "amd" in nl or "radeon" in nl or "rx " in nl:
                    vendor = "AMD"
                elif "intel" in nl or "arc" in nl or "iris" in nl or "uhd" in nl:
                    vendor = "Intel"

                gpus.append({
                    "name":     name,
                    "vram_gb":  vram,
                    "vram_used_gb": 0,
                    "driver":   d.get("DriverVersion", "N/A"),
                    "temp_c":   None,
                    "load_pct": None,
                    "vendor":   vendor,
                    "cuda":     vendor == "NVIDIA",
                })
        except Exception:
            pass

    # Fallback – at least show something
    if not gpus:
        gpus.append({
            "name": "GPU info unavailable",
            "vram_gb": 0, "vram_used_gb": 0,
            "driver": "N/A", "temp_c": None,
            "load_pct": None, "vendor": "Unknown", "cuda": False,
        })

    return gpus


def get_disk_info() -> List[Dict]:
    disks = []
    partitions = psutil.disk_partitions(all=False)

    # Get disk types via PowerShell
    disk_types: Dict[str, str] = {}
    raw = _run_ps(
        "Get-PhysicalDisk | Select-Object DeviceId,MediaType,Model,Size | ConvertTo-Json -Compress"
    )
    if raw:
        try:
            data = json.loads(raw)
            if isinstance(data, dict):
                data = [data]
            for d in data:
                mt = d.get("MediaType", "")
                did = str(d.get("DeviceId", ""))
                if "SSD" in mt or "3" in mt:
                    disk_types[did] = "SSD"
                elif "HDD" in mt or "4" in mt or "Rotating" in mt:
                    disk_types[did] = "HDD"
                elif "NVMe" in mt or mt == "Unspecified":
                    # Try to detect NVMe from model name
                    model = d.get("Model", "")
                    disk_types[did] = "NVMe SSD" if "nvme" in model.lower() else "SSD/Unknown"
        except Exception:
            pass

    for p in partitions:
        try:
            usage = psutil.disk_usage(p.mountpoint)
            disk_type = disk_types.get("0", "Unknown") if not disk_types else (
                list(disk_types.values())[0] if disk_types else "Unknown"
            )
            disks.append({
                "mountpoint": p.mountpoint,
                "fstype":    p.fstype,
                "total_gb":  round(usage.total  / (1024**3), 1),
                "used_gb":   round(usage.used   / (1024**3), 1),
                "free_gb":   round(usage.free   / (1024**3), 1),
                "percent":   usage.percent,
                "type":      disk_type,
            })
        except PermissionError:
            pass
    return disks


def get_os_info() -> Dict:
    info = {
        "system": platform.system(),
        "release": platform.release(),
        "version": platform.version(),
        "name": "Windows",
        "build": "",
        "edition": "",
        "directx": "Unknown",
        "cuda_version": "Not installed",
        "python": platform.python_version(),
    }
    # Windows edition
    raw = _run_ps("(Get-WmiObject Win32_OperatingSystem).Caption")
    if raw:
        info["name"] = raw.splitlines()[0].strip()
    build = _run_ps("(Get-WmiObject Win32_OperatingSystem).BuildNumber")
    if build:
        info["build"] = build.strip()

    # DirectX version
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\DirectX"
        )
        dxver = winreg.QueryValueEx(key, "Version")[0]
        info["directx"] = f"DirectX ({dxver})"
        winreg.CloseKey(key)
    except Exception:
        info["directx"] = "DirectX 12 (estimated)"

    # CUDA
    try:
        r = subprocess.run(
            ["nvidia-smi", "--query-gpu=driver_version", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=5
        )
        if r.returncode == 0:
            r2 = subprocess.run(
                ["nvcc", "--version"],
                capture_output=True, text=True, timeout=5
            )
            if r2.returncode == 0:
                for line in r2.stdout.splitlines():
                    if "release" in line.lower():
                        info["cuda_version"] = line.split("release")[-1].strip().split(",")[0].strip()
                        break
            else:
                r3 = subprocess.run(
                    ["nvidia-smi"],
                    capture_output=True, text=True, timeout=5
                )
                for line in r3.stdout.splitlines():
                    if "CUDA Version" in line:
                        info["cuda_version"] = line.split("CUDA Version:")[-1].strip().split()[0]
                        break
    except Exception:
        pass

    return info


def cpu_benchmark() -> Tuple[float, float]:
    """Quick single-core and multi-core benchmark. Returns (single, multi) scores."""
    import threading

    N = 500_000

    def _crunch():
        s = 0.0
        for i in range(1, N):
            s += math.sqrt(i) * math.log(i + 1)
        return s

    # Single-core
    t0 = time.perf_counter()
    _crunch()
    t1 = time.perf_counter()
    single = round(N / (t1 - t0) / 1_000_000, 2)  # Millions ops/sec

    # Multi-core
    cores = psutil.cpu_count(logical=True)
    threads_list = [threading.Thread(target=_crunch) for _ in range(cores)]
    t0 = time.perf_counter()
    for th in threads_list:
        th.start()
    for th in threads_list:
        th.join()
    t1 = time.perf_counter()
    multi = round(N * cores / (t1 - t0) / 1_000_000, 2)

    return single, multi


# ─────────────────────────────────────────────────────────────────
# GPU MATCHING
# ─────────────────────────────────────────────────────────────────

def match_gpu(gpu_name: str) -> Optional[Dict]:
    """Match a GPU name to our database (fuzzy, longest-match wins)."""
    name_upper = gpu_name.upper()
    best_match = None
    best_len = 0
    for key, val in GPU_DB.items():
        if key.upper() in name_upper and len(key) > best_len:
            best_match = {**val, "db_key": key}
            best_len = len(key)
    return best_match


# ─────────────────────────────────────────────────────────────────
# AI COMPATIBILITY ENGINE
# ─────────────────────────────────────────────────────────────────

def check_ai_compatibility(
    ram_total: float,
    vram_total: float,
    has_cuda: bool,
) -> List[Dict]:
    """
    Returns each model annotated with:
      status: "excellent" / "good" / "limited" / "cpu_only" / "no"
      note: reasoning
    """
    results = []
    for m in AI_MODELS:
        r = ram_total
        v = vram_total
        mram  = m["min_ram_gb"]
        mvram = m["min_vram_gb"]

        if r >= mram and v >= mvram and (has_cuda or m.get("cpu_ok")):
            if v >= mvram * 1.5 and r >= mram * 1.5:
                status = "excellent"
                note   = "Runs fast with headroom"
            else:
                status = "good"
                note   = "Meets requirements"
        elif r >= mram and m.get("cpu_ok"):
            status = "cpu_only"
            note   = f"No suitable GPU — will run on CPU (slow)"
        elif r >= mram * 0.85 and v >= mvram * 0.85:
            status = "limited"
            note   = "Slightly under spec — may run with quantization"
        else:
            status = "no"
            note   = (
                f"Need {mram}GB RAM, {mvram}GB VRAM "
                f"(have {r}GB / {v}GB)"
            )
        results.append({**m, "status": status, "note": note})

    # Sort: excellent first, then good, cpu_only, limited, no
    order = {"excellent": 0, "good": 1, "cpu_only": 2, "limited": 3, "no": 4}
    results.sort(key=lambda x: (order[x["status"]], x["category"], -x["quality"]))
    return results


# ─────────────────────────────────────────────────────────────────
# OVERALL AI SCORE (0-100)
# ─────────────────────────────────────────────────────────────────

def compute_ai_score(
    cpu:       Dict,
    ram:       Dict,
    gpu_list:  List[Dict],
    gpu_match: Optional[Dict],
) -> Tuple[int, str]:
    score = 0

    # RAM (0-25 pts)
    r = ram["total_gb"]
    if   r >= 64: score += 25
    elif r >= 32: score += 22
    elif r >= 16: score += 18
    elif r >= 8:  score += 12
    elif r >= 4:  score += 6
    else:         score += 2

    # VRAM (0-35 pts)
    vram = max((g["vram_gb"] for g in gpu_list), default=0)
    if   vram >= 24: score += 35
    elif vram >= 16: score += 30
    elif vram >= 12: score += 26
    elif vram >= 8:  score += 22
    elif vram >= 6:  score += 16
    elif vram >= 4:  score += 10
    elif vram >= 2:  score += 4
    else:            score += 0

    # GPU DB score (0-20 pts)
    if gpu_match:
        gs = gpu_match.get("score", 0)
        score += min(20, int(gs / 5))

    # CPU (0-15 pts)
    cores = cpu["cores_physical"]
    freq  = cpu["freq_max_mhz"] / 1000
    if   cores >= 16 and freq >= 4.0: score += 15
    elif cores >= 12 and freq >= 3.5: score += 13
    elif cores >=  8 and freq >= 3.0: score += 10
    elif cores >=  6:                 score += 7
    elif cores >=  4:                 score += 4
    else:                             score += 1

    # CUDA bonus (0-5 pts)
    has_cuda = any(g["cuda"] for g in gpu_list)
    if has_cuda:
        score += 5

    score = min(100, score)

    if   score >= 90: rating = "EXCELLENT  — Runs top-tier local AI"
    elif score >= 75: rating = "GREAT  — Runs most local AI models"
    elif score >= 55: rating = "GOOD  — Handles mid-range AI well"
    elif score >= 35: rating = "FAIR  — Basic models only"
    elif score >= 15: rating = "LOW  — CPU-only / tiny models"
    else:             rating = "NOT SUITABLE  — Upgrade recommended"

    return score, rating


# ─────────────────────────────────────────────────────────────────
# PROGRESS BAR HELPER
# ─────────────────────────────────────────────────────────────────

def _bar(value: float, maximum: float, width: int = 20, color: str = "green") -> str:
    pct = min(1.0, value / maximum) if maximum > 0 else 0
    filled = int(pct * width)
    bar = "█" * filled + "░" * (width - filled)
    return f"[{color}]{bar}[/{color}] {value:.1f}/{maximum:.1f}"


def _status_badge(status: str) -> str:
    badges = {
        "excellent": "[bold bright_green] EXCELLENT [/]",
        "good":      "[bold green]   GOOD    [/]",
        "cpu_only":  "[bold yellow]  CPU-ONLY [/]",
        "limited":   "[bold orange3]  LIMITED  [/]",
        "no":        "[bold red]    NO     [/]",
    }
    return badges.get(status, status)


def _quality_stars(q: int) -> str:
    return "[yellow]" + "★" * q + "☆" * (5 - q) + "[/yellow]"


# ─────────────────────────────────────────────────────────────────
# DISPLAY SECTIONS
# ─────────────────────────────────────────────────────────────────

def print_banner():
    banner = """
[bold bright_cyan]
 ██████╗  ██████╗    ██████╗  ██████╗    ██████╗██╗  ██╗███████╗ ██████╗██╗  ██╗
██╔═══██╗██╔═══██╗   ██╔══██╗██╔════╝   ██╔════╝██║  ██║██╔════╝██╔════╝██║ ██╔╝
███████║ ██║   ██║   ██████╔╝██║        ██║     ███████║█████╗  ██║     █████╔╝
██╔══██║ ██║   ██║   ██╔═══╝ ██║        ██║     ██╔══██║██╔══╝  ██║     ██╔═██╗
██║  ██║ ╚██████╔╝   ██║     ╚██████╗   ╚██████╗██║  ██║███████╗╚██████╗██║  ██╗
╚═╝  ╚═╝  ╚═════╝    ╚═╝      ╚═════╝    ╚═════╝╚═╝  ╚═╝╚══════╝ ╚═════╝╚═╝  ╚═╝
[/bold bright_cyan]"""
    console.print(banner)
    console.print(
        Panel(
            "[bold white]  LOCAL AI SUITABILITY CHECKER  v2.0[/bold white]\n"
            "[dim]  Full hardware analysis · AI model recommendations · Installation guides[/dim]",
            style="bright_cyan", expand=False, padding=(0, 4)
        )
    )
    console.print(f"[dim]  Scan started: {datetime.now().strftime('%Y-%m-%d  %H:%M:%S')}[/dim]\n")


def print_cpu_section(cpu: Dict, bench_single: float, bench_multi: float):
    console.print(Rule("[bold yellow]  CPU  —  PROCESSOR[/bold yellow]", style="yellow"))
    t = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
    t.add_column("Key",   style="dim", min_width=22)
    t.add_column("Value", style="white")

    t.add_row("Model",      f"[bold]{cpu['name']}[/bold]")
    t.add_row("Architecture", f"{cpu['arch']} ({cpu['bits']}-bit)")
    t.add_row("Physical Cores", str(cpu["cores_physical"]))
    t.add_row("Logical Threads", str(cpu["cores_logical"]))
    base = f"{cpu['freq_base_mhz']/1000:.2f} GHz"
    mx   = f"{cpu['freq_max_mhz']/1000:.2f} GHz" if cpu["freq_max_mhz"] else "N/A"
    t.add_row("Base / Boost Freq", f"{base}  /  {mx}")
    avx2 = "[green]✔ Supported[/green]" if cpu["avx2"] else "[yellow]Not detected[/yellow]"
    t.add_row("AVX2 Support", avx2)
    t.add_row("Benchmark (1-core)",  f"[cyan]{bench_single:.2f}M ops/s[/cyan]")
    t.add_row("Benchmark (all-core)", f"[cyan]{bench_multi:.2f}M ops/s[/cyan]")
    console.print(t)


def print_ram_section(ram: Dict):
    console.print(Rule("[bold blue]  RAM  —  SYSTEM MEMORY[/bold blue]", style="blue"))
    t = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
    t.add_column("Key",   style="dim", min_width=22)
    t.add_column("Value", style="white")

    pct_color = "green" if ram["percent"] < 60 else ("yellow" if ram["percent"] < 85 else "red")
    ram_bar = _bar(ram["used_gb"], ram["total_gb"], 24, pct_color)

    t.add_row("Total RAM",    f"[bold]{ram['total_gb']} GB[/bold]")
    t.add_row("Used / Free",  f"{ram['used_gb']} GB  /  [green]{ram['available_gb']} GB free[/green]")
    t.add_row("Usage",        ram_bar)
    if ram["type"] != "Unknown":
        t.add_row("Type",     f"{ram['type']}")
    if ram["speed_mhz"]:
        t.add_row("Speed",    f"{ram['speed_mhz']} MHz")
    if ram["channels"]:
        t.add_row("Modules installed", str(ram["channels"]))

    console.print(t)


def print_gpu_section(gpus: List[Dict], gpu_matches: List[Optional[Dict]]):
    console.print(Rule("[bold magenta]  GPU  —  GRAPHICS & AI ACCELERATOR[/bold magenta]", style="magenta"))

    for idx, (gpu, match) in enumerate(zip(gpus, gpu_matches)):
        gpu_num = f" GPU {idx+1} " if len(gpus) > 1 else ""
        console.print(f"[bold magenta]{gpu_num}[/bold magenta]" if gpu_num else "")

        t = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
        t.add_column("Key",   style="dim", min_width=22)
        t.add_column("Value", style="white")

        t.add_row("Model", f"[bold]{gpu['name']}[/bold]")
        t.add_row("Vendor", gpu.get("vendor", "Unknown"))

        vram_bar = _bar(gpu["vram_used_gb"], gpu["vram_gb"], 24, "magenta") if gpu["vram_gb"] > 0 else "N/A"
        t.add_row("VRAM Total",  f"[bold]{gpu['vram_gb']} GB[/bold]")
        if gpu["vram_used_gb"] > 0:
            t.add_row("VRAM Usage", vram_bar)

        cuda_str = "[green]✔ CUDA Available[/green]" if gpu["cuda"] else "[dim]Not available[/dim]"
        t.add_row("CUDA / GPU Compute", cuda_str)

        if gpu["driver"] and gpu["driver"] != "N/A":
            t.add_row("Driver",  gpu["driver"])
        if gpu["temp_c"] is not None:
            temp_color = "green" if gpu["temp_c"] < 70 else ("yellow" if gpu["temp_c"] < 85 else "red")
            t.add_row("Temperature", f"[{temp_color}]{gpu['temp_c']}°C[/{temp_color}]")
        if gpu["load_pct"] is not None:
            t.add_row("GPU Load", f"{gpu['load_pct']}%")

        if match:
            tier_color = TIER_COLORS.get(match["tier"], "white")
            t.add_row("Performance Tier",  f"[{tier_color}][bold]{match['tier']}[/bold][/{tier_color}]")
            t.add_row("AI Compute Score", f"{match['score']}/120")
            t.add_row("SD Image Gen FPS",  f"~{match['sd_fps']} fps  [dim](512×512, SD1.5 CUDA)[/dim]")
            t.add_row("LLM Tokens/sec",    f"~{match['tok_s']} tok/s  [dim](7B Q4 model)[/dim]")

        console.print(t)


def print_disk_section(disks: List[Dict]):
    console.print(Rule("[bold green]  STORAGE  —  DISKS[/bold green]", style="green"))
    t = Table(show_header=True, header_style="bold green", box=box.SIMPLE, padding=(0, 2))
    t.add_column("Drive",   style="dim",    min_width=6)
    t.add_column("Type",    min_width=10)
    t.add_column("Total",   min_width=8)
    t.add_column("Used",    min_width=8)
    t.add_column("Free",    min_width=8, style="green")
    t.add_column("Usage",   min_width=26)

    for d in disks:
        pct = d["percent"]
        color = "green" if pct < 60 else ("yellow" if pct < 85 else "red")
        bar_w = 18
        filled = int((pct / 100) * bar_w)
        bar = f"[{color}]{'█'*filled}{'░'*(bar_w-filled)}[/{color}] {pct:.0f}%"
        t.add_row(
            d["mountpoint"],
            f"[cyan]{d['type']}[/cyan]",
            f"{d['total_gb']} GB",
            f"{d['used_gb']} GB",
            f"{d['free_gb']} GB",
            bar,
        )
    console.print(t)


def print_os_section(os_info: Dict):
    console.print(Rule("[bold cyan]  SYSTEM  —  OS & SOFTWARE STACK[/bold cyan]", style="cyan"))
    t = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
    t.add_column("Key",   style="dim", min_width=22)
    t.add_column("Value", style="white")

    t.add_row("Operating System",  f"[bold]{os_info['name']}[/bold]")
    if os_info["build"]:
        t.add_row("Build",         os_info["build"])
    t.add_row("DirectX",           os_info["directx"])
    cuda_style = "green" if os_info["cuda_version"] != "Not installed" else "red"
    t.add_row("CUDA",              f"[{cuda_style}]{os_info['cuda_version']}[/{cuda_style}]")
    t.add_row("Python",            os_info["python"])
    console.print(t)


def print_score_section(score: int, rating: str):
    console.print()
    color = (
        "bright_green" if score >= 90 else
        "green"        if score >= 75 else
        "yellow"       if score >= 55 else
        "orange3"      if score >= 35 else "red"
    )
    bar_w = 40
    filled = int((score / 100) * bar_w)
    score_bar = f"[{color}]{'█'*filled}{'░'*(bar_w-filled)}[/{color}]"

    console.print(
        Panel(
            f"[bold {color}]  AI SUITABILITY SCORE:  {score} / 100[/bold {color}]\n\n"
            f"  {score_bar}  [bold {color}]{score}%[/bold {color}]\n\n"
            f"  [bold white]{rating}[/bold white]",
            title="[bold white]  OVERALL RATING  [/bold white]",
            style=color, expand=False, padding=(1, 4)
        )
    )
    console.print()


def print_compatible_models(
    results: List[Dict],
    max_show: int = 20,
    show_all: bool = False,
):
    console.print(Rule("[bold white]  LOCAL AI MODEL COMPATIBILITY[/bold white]", style="white"))

    # Group by category
    categories: Dict[str, List] = {}
    for r in results:
        cat = r["category"]
        categories.setdefault(cat, []).append(r)

    runnable = [r for r in results if r["status"] != "no"]
    console.print(
        f"  [bold green]{len(runnable)}[/bold green] models can run on your PC   "
        f"([dim]{len(results) - len(runnable)} require more resources[/dim])\n"
    )

    for cat, models in categories.items():
        runnable_cat = [m for m in models if m["status"] != "no"]
        if not runnable_cat and not show_all:
            continue

        console.print(f"[bold cyan]  ▸ {cat}[/bold cyan]")
        t = Table(
            show_header=True, header_style="bold dim",
            box=box.SIMPLE_HEAVY, padding=(0, 1),
            expand=False,
        )
        t.add_column("Status",   min_width=11, no_wrap=True)
        t.add_column("Model",    min_width=22, style="bold")
        t.add_column("Size",     min_width=7,  justify="right")
        t.add_column("Quality",  min_width=12)
        t.add_column("Platform", min_width=22)
        t.add_column("Note",     min_width=30, style="dim")

        for m in models:
            if m["status"] == "no" and not show_all:
                continue
            badge   = _status_badge(m["status"])
            stars   = _quality_stars(m["quality"])
            size    = f"{m['model_size_gb']:.1f} GB"
            plat    = ", ".join(m["platforms"][:2])
            t.add_row(badge, m["name"], size, stars, plat, m["note"])

        console.print(Padding(t, (0, 2)))
        console.print()


def print_install_guides(results: List[Dict]):
    console.print(Rule("[bold yellow]  INSTALLATION GUIDES[/bold yellow]", style="yellow"))

    # Collect needed platforms
    needed = set()
    for r in results:
        if r["status"] in ("excellent", "good", "cpu_only"):
            needed.update(r["platforms"])

    for plat_name in sorted(needed):
        if plat_name not in PLATFORMS:
            continue
        p = PLATFORMS[plat_name]
        steps_text = "\n".join(
            f"  [dim]{i+1}.[/dim] {escape(s)}" for i, s in enumerate(p["steps"])
        )
        console.print(
            Panel(
                f"[bold cyan]{plat_name}[/bold cyan]  —  [dim]{p['desc']}[/dim]\n\n"
                f"{steps_text}\n\n"
                f"  [dim]URL:[/dim] [link={p['url']}]{p['url']}[/link]",
                style="dim",
                padding=(1, 3),
            )
        )


def print_quick_start(results: List[Dict]):
    console.print(Rule("[bold bright_green]  QUICK START — TOP 5 COMMANDS[/bold bright_green]", style="bright_green"))
    console.print("  [dim]Run these in your terminal after installing Ollama:[/dim]\n")

    top = [r for r in results if r["status"] in ("excellent","good") and r.get("ollama")][:5]
    if not top:
        top = [r for r in results if r.get("ollama")][:5]

    t = Table(box=box.SIMPLE, show_header=True, header_style="bold dim", padding=(0, 2))
    t.add_column("#",       min_width=3,  justify="right", style="dim")
    t.add_column("Model",   min_width=22, style="bold")
    t.add_column("Command", min_width=38, style="bright_cyan")
    t.add_column("Good For",min_width=28, style="dim")

    for i, r in enumerate(top, 1):
        tags = r.get("tags", [])
        tag_str = " · ".join(tags[:3])
        t.add_row(str(i), r["name"], r["ollama"], tag_str)

    console.print(Padding(t, (0, 2)))
    console.print()


def print_upgrade_tips(score: int, ram: Dict, gpus: List[Dict]):
    """Targeted upgrade advice if score is below 75."""
    if score >= 90:
        return

    console.print(Rule("[bold orange3]  UPGRADE RECOMMENDATIONS[/bold orange3]", style="orange3"))
    tips = []
    vram = max((g["vram_gb"] for g in gpus), default=0)

    if vram < 8:
        tips.append(
            "🎯 [bold]Priority #1 — GPU:[/bold] Upgrade to a GPU with 8GB+ VRAM (RTX 3060 or better)\n"
            "   This single upgrade will unlock most 7B language models with GPU acceleration."
        )
    if vram < 16:
        tips.append(
            "🎯 [bold]GPU VRAM:[/bold] 16GB VRAM (RTX 3080 / RX 6800 XT) enables 13B+ models and SDXL."
        )
    if ram["total_gb"] < 16:
        tips.append(
            "💾 [bold]RAM:[/bold] Upgrade to 16GB+ RAM for comfortable CPU inference of 7B models."
        )
    if ram["total_gb"] < 32:
        tips.append(
            "💾 [bold]RAM:[/bold] 32GB RAM allows running larger models and multiple tools simultaneously."
        )
    if not any(g["cuda"] for g in gpus):
        tips.append(
            "⚡ [bold]CUDA:[/bold] An NVIDIA GPU provides CUDA acceleration — 10-30× faster AI inference."
        )

    for tip in tips[:4]:
        console.print(Padding(f"  {tip}", (0, 2, 1, 2)))


def save_report(
    cpu: Dict, ram: Dict, gpus: List[Dict],
    disks: List[Dict], os_info: Dict,
    score: int, rating: str,
    results: List[Dict],
):
    report = {
        "generated":  datetime.now().isoformat(),
        "score":      score,
        "rating":     rating,
        "cpu":        cpu,
        "ram":        ram,
        "gpus":       gpus,
        "disks":      disks,
        "os":         os_info,
        "models":     [
            {k: v for k, v in r.items() if k not in ("ollama","lmstudio","install_note")}
            for r in results if r["status"] != "no"
        ],
    }
    path = Path("ai_pc_report.json")
    path.write_text(json.dumps(report, indent=2, default=str))
    console.print(f"\n  [dim]📄 Full report saved to:[/dim] [cyan]{path.resolve()}[/cyan]\n")


# ─────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────

def main():
    print_banner()

    # ── Gather with spinner ───────────────────────────────────────
    with Progress(
        SpinnerColumn("dots"),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(bar_width=30),
        TimeElapsedColumn(),
        console=console, transient=True,
    ) as p:
        t1 = p.add_task("Scanning CPU...",                  total=None)
        cpu = get_cpu_info()
        p.update(t1, description="[green]CPU ✓[/green]", completed=True, total=1)

        t2 = p.add_task("Scanning RAM...",                  total=None)
        ram = get_ram_info()
        p.update(t2, description="[green]RAM ✓[/green]", completed=True, total=1)

        t3 = p.add_task("Scanning GPU / VRAM...",           total=None)
        gpus = get_gpu_info()
        p.update(t3, description="[green]GPU ✓[/green]", completed=True, total=1)

        t4 = p.add_task("Scanning disks...",                total=None)
        disks = get_disk_info()
        p.update(t4, description="[green]Disks ✓[/green]", completed=True, total=1)

        t5 = p.add_task("Scanning OS & software...",        total=None)
        os_info = get_os_info()
        p.update(t5, description="[green]OS ✓[/green]", completed=True, total=1)

        t6 = p.add_task("Running CPU benchmark...",         total=None)
        bench_single, bench_multi = cpu_benchmark()
        p.update(t6, description="[green]Benchmark ✓[/green]", completed=True, total=1)

    # ── Match GPUs to DB ─────────────────────────────────────────
    gpu_matches = [match_gpu(g["name"]) for g in gpus]
    best_vram   = max((g["vram_gb"] for g in gpus), default=0)
    has_cuda    = any(g["cuda"] for g in gpus)

    # ── Check model compatibility ─────────────────────────────────
    results = check_ai_compatibility(ram["total_gb"], best_vram, has_cuda)

    # ── Compute score ─────────────────────────────────────────────
    score, rating = compute_ai_score(cpu, ram, gpus, gpu_matches[0] if gpu_matches else None)

    # ── Print all sections ────────────────────────────────────────
    console.print()
    print_cpu_section(cpu, bench_single, bench_multi)
    print_ram_section(ram)
    print_gpu_section(gpus, gpu_matches)
    print_disk_section(disks)
    print_os_section(os_info)
    print_score_section(score, rating)
    print_compatible_models(results, show_all=False)
    print_quick_start(results)
    print_install_guides(results)
    print_upgrade_tips(score, ram, gpus)
    save_report(cpu, ram, gpus, disks, os_info, score, rating, results)

    console.print(Rule("[bold bright_cyan]  SCAN COMPLETE[/bold bright_cyan]", style="bright_cyan"))
    console.print(
        f"\n  [dim]Tip: Re-run with[/dim] [cyan]python ai_pc_checker.py[/cyan] "
        "[dim]any time to refresh the analysis.[/dim]\n"
    )


if __name__ == "__main__":
    main()
