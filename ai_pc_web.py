#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI PC Suitability Checker — Web Dashboard
Scans hardware, picks a free port, starts a local server, opens browser.
"""

import sys, os, subprocess, platform, json, time, math, struct, socket, threading, webbrowser
from pathlib import Path
from datetime import datetime
from typing  import Dict, List, Optional, Tuple

# ─── Auto-install dependencies ───────────────────────────────────────────────
REQUIRED = {"psutil": "psutil", "GPUtil": "gputil", "flask": "flask", "cpuinfo": "py-cpuinfo"}

def _auto_install():
    missing = []
    for imp, pkg in REQUIRED.items():
        try: __import__(imp)
        except ImportError: missing.append(pkg)
    if missing:
        print(f"[Setup] Installing: {', '.join(missing)} …")
        for pkg in missing:
            subprocess.check_call([sys.executable, "-m", "pip", "install", pkg, "-q"],
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print("[Setup] Done.\n")

_auto_install()

import psutil, GPUtil
from flask import Flask, render_template_string

try:
    import cpuinfo as py_cpuinfo; HAS_CPUINFO = True
except ImportError:
    HAS_CPUINFO = False

# ─── GPU Performance Database ────────────────────────────────────────────────
GPU_DB: Dict[str, Dict] = {
    "RTX 5090":{"tier":"S+","vram":32,"score":120,"sd_fps":40,"tok_s":200},
    "RTX 5080":{"tier":"S+","vram":16,"score":105,"sd_fps":32,"tok_s":160},
    "RTX 5070 Ti":{"tier":"S","vram":16,"score":90,"sd_fps":26,"tok_s":130},
    "RTX 5070":{"tier":"A+","vram":12,"score":78,"sd_fps":20,"tok_s":100},
    "RTX 4090":{"tier":"S","vram":24,"score":100,"sd_fps":28,"tok_s":140},
    "RTX 4080 SUPER":{"tier":"S","vram":16,"score":90,"sd_fps":23,"tok_s":115},
    "RTX 4080":{"tier":"S","vram":16,"score":85,"sd_fps":20,"tok_s":100},
    "RTX 4070 Ti SUPER":{"tier":"A+","vram":16,"score":78,"sd_fps":17,"tok_s":88},
    "RTX 4070 Ti":{"tier":"A+","vram":12,"score":72,"sd_fps":15,"tok_s":78},
    "RTX 4070 SUPER":{"tier":"A+","vram":12,"score":68,"sd_fps":14,"tok_s":72},
    "RTX 4070":{"tier":"A","vram":12,"score":60,"sd_fps":12,"tok_s":60},
    "RTX 4060 Ti":{"tier":"B+","vram":8,"score":52,"sd_fps":9,"tok_s":48},
    "RTX 4060":{"tier":"B","vram":8,"score":44,"sd_fps":7,"tok_s":38},
    "RTX 4050":{"tier":"B-","vram":6,"score":36,"sd_fps":5,"tok_s":28},
    "RTX 3090 Ti":{"tier":"A+","vram":24,"score":80,"sd_fps":14,"tok_s":76},
    "RTX 3090":{"tier":"A+","vram":24,"score":75,"sd_fps":13,"tok_s":72},
    "RTX 3080 Ti":{"tier":"A","vram":12,"score":68,"sd_fps":12,"tok_s":64},
    "RTX 3080":{"tier":"A","vram":10,"score":62,"sd_fps":11,"tok_s":58},
    "RTX 3070 Ti":{"tier":"B+","vram":8,"score":52,"sd_fps":9,"tok_s":46},
    "RTX 3070":{"tier":"B+","vram":8,"score":50,"sd_fps":8,"tok_s":42},
    "RTX 3060 Ti":{"tier":"B","vram":8,"score":44,"sd_fps":7,"tok_s":36},
    "RTX 3060":{"tier":"B","vram":12,"score":40,"sd_fps":6,"tok_s":30},
    "RTX 3050":{"tier":"C+","vram":8,"score":30,"sd_fps":4,"tok_s":22},
    "RTX 2080 Ti":{"tier":"A","vram":11,"score":58,"sd_fps":9,"tok_s":50},
    "RTX 2080 SUPER":{"tier":"B+","vram":8,"score":48,"sd_fps":7,"tok_s":38},
    "RTX 2080":{"tier":"B+","vram":8,"score":46,"sd_fps":7,"tok_s":36},
    "RTX 2070 SUPER":{"tier":"B","vram":8,"score":42,"sd_fps":6,"tok_s":32},
    "RTX 2070":{"tier":"B","vram":8,"score":40,"sd_fps":6,"tok_s":30},
    "RTX 2060 SUPER":{"tier":"B","vram":8,"score":36,"sd_fps":5,"tok_s":26},
    "RTX 2060":{"tier":"C+","vram":6,"score":32,"sd_fps":4,"tok_s":22},
    "GTX 1080 Ti":{"tier":"B","vram":11,"score":42,"sd_fps":5,"tok_s":26},
    "GTX 1080":{"tier":"C+","vram":8,"score":34,"sd_fps":4,"tok_s":20},
    "GTX 1070 Ti":{"tier":"C+","vram":8,"score":30,"sd_fps":3,"tok_s":16},
    "GTX 1070":{"tier":"C+","vram":8,"score":28,"sd_fps":3,"tok_s":14},
    "GTX 1660 Ti":{"tier":"C+","vram":6,"score":26,"sd_fps":3,"tok_s":12},
    "GTX 1660 SUPER":{"tier":"C+","vram":6,"score":25,"sd_fps":3,"tok_s":11},
    "GTX 1660":{"tier":"C","vram":6,"score":22,"sd_fps":2,"tok_s":10},
    "GTX 1060":{"tier":"C","vram":6,"score":22,"sd_fps":2,"tok_s":10},
    "GTX 1650":{"tier":"C","vram":4,"score":18,"sd_fps":2,"tok_s":8},
    "RX 7900 XTX":{"tier":"A+","vram":24,"score":82,"sd_fps":14,"tok_s":70},
    "RX 7900 XT":{"tier":"A","vram":20,"score":72,"sd_fps":12,"tok_s":60},
    "RX 7900 GRE":{"tier":"A","vram":16,"score":65,"sd_fps":10,"tok_s":52},
    "RX 7800 XT":{"tier":"B+","vram":16,"score":55,"sd_fps":8,"tok_s":40},
    "RX 7700 XT":{"tier":"B+","vram":12,"score":50,"sd_fps":7,"tok_s":34},
    "RX 7600":{"tier":"B","vram":8,"score":38,"sd_fps":5,"tok_s":24},
    "RX 6950 XT":{"tier":"A","vram":16,"score":68,"sd_fps":10,"tok_s":52},
    "RX 6900 XT":{"tier":"A","vram":16,"score":65,"sd_fps":9,"tok_s":48},
    "RX 6800 XT":{"tier":"A","vram":16,"score":60,"sd_fps":8,"tok_s":44},
    "RX 6800":{"tier":"B+","vram":16,"score":55,"sd_fps":7,"tok_s":38},
    "RX 6700 XT":{"tier":"B+","vram":12,"score":45,"sd_fps":5,"tok_s":28},
    "RX 6600 XT":{"tier":"B","vram":8,"score":34,"sd_fps":4,"tok_s":18},
    "RX 6600":{"tier":"C+","vram":8,"score":30,"sd_fps":4,"tok_s":16},
    "RX 5700 XT":{"tier":"C+","vram":8,"score":32,"sd_fps":4,"tok_s":16},
    "RX 5700":{"tier":"C+","vram":8,"score":28,"sd_fps":3,"tok_s":13},
    "Arc A770":{"tier":"B","vram":16,"score":40,"sd_fps":5,"tok_s":22},
    "Arc A750":{"tier":"B-","vram":8,"score":34,"sd_fps":4,"tok_s":18},
    "Arc A580":{"tier":"C+","vram":8,"score":28,"sd_fps":3,"tok_s":12},
    "Arc A380":{"tier":"C","vram":6,"score":20,"sd_fps":2,"tok_s":8},
    "Intel UHD":{"tier":"F","vram":2,"score":5,"sd_fps":0,"tok_s":2},
    "Intel Iris":{"tier":"F","vram":2,"score":6,"sd_fps":0,"tok_s":3},
    "Radeon Graphics":{"tier":"F","vram":2,"score":6,"sd_fps":0,"tok_s":3},
    "Vega":{"tier":"F","vram":2,"score":7,"sd_fps":0,"tok_s":3},
}

AI_MODELS: List[Dict] = [
    {"name":"Phi-3 Mini 3.8B","min_ram_gb":4,"min_vram_gb":2,"model_size_gb":2.3,"cpu_ok":True,"quality":3,"category":"Text / Chat","description":"Microsoft tiny-but-smart. Great for low-end PCs.","ollama":"ollama run phi3:mini","lmstudio":"phi-3-mini-4k-instruct","platforms":["Ollama","LM Studio","GPT4All"],"tags":["CPU-OK","Fast","Lightweight"]},
    {"name":"Llama 3.2 1B","min_ram_gb":3,"min_vram_gb":1,"model_size_gb":0.7,"cpu_ok":True,"quality":2,"category":"Text / Chat","description":"Smallest Meta model – ultra-fast even on CPU.","ollama":"ollama run llama3.2:1b","lmstudio":"llama-3.2-1b-instruct","platforms":["Ollama","LM Studio"],"tags":["CPU-OK","Ultra-Fast","Tiny"]},
    {"name":"Llama 3.2 3B","min_ram_gb":4,"min_vram_gb":2,"model_size_gb":2.0,"cpu_ok":True,"quality":3,"category":"Text / Chat","description":"Balanced Meta model for everyday tasks.","ollama":"ollama run llama3.2:3b","lmstudio":"llama-3.2-3b-instruct","platforms":["Ollama","LM Studio"],"tags":["CPU-OK","Balanced"]},
    {"name":"Gemma 2B","min_ram_gb":4,"min_vram_gb":2,"model_size_gb":1.7,"cpu_ok":True,"quality":2,"category":"Text / Chat","description":"Google compact open model.","ollama":"ollama run gemma:2b","lmstudio":"gemma-2b-it","platforms":["Ollama","LM Studio","GPT4All"],"tags":["CPU-OK","Lightweight"]},
    {"name":"TinyLlama 1.1B","min_ram_gb":3,"min_vram_gb":1,"model_size_gb":0.6,"cpu_ok":True,"quality":1,"category":"Text / Chat","description":"Runs everywhere, minimal resources.","ollama":"ollama run tinyllama","lmstudio":"tinyllama-1.1b-chat","platforms":["Ollama","LM Studio","GPT4All","llama.cpp"],"tags":["CPU-OK","Ultra-Tiny"]},
    {"name":"Mistral 7B v0.3","min_ram_gb":8,"min_vram_gb":4,"model_size_gb":4.1,"cpu_ok":True,"quality":4,"category":"Text / Chat","description":"Best-in-class 7B model. Highly recommended.","ollama":"ollama run mistral","lmstudio":"mistral-7b-instruct-v0.3","platforms":["Ollama","LM Studio","GPT4All"],"tags":["Recommended","Balanced","CPU-OK"]},
    {"name":"Llama 3.1 8B","min_ram_gb":8,"min_vram_gb":4,"model_size_gb":4.7,"cpu_ok":True,"quality":4,"category":"Text / Chat","description":"Meta flagship small model. Excellent quality.","ollama":"ollama run llama3.1:8b","lmstudio":"meta-llama-3.1-8b-instruct","platforms":["Ollama","LM Studio","GPT4All"],"tags":["Recommended","Best-Quality-7B"]},
    {"name":"Gemma 2 9B","min_ram_gb":10,"min_vram_gb":6,"model_size_gb":5.4,"cpu_ok":True,"quality":4,"category":"Text / Chat","description":"Google improved 9B model – punches above its weight.","ollama":"ollama run gemma2:9b","lmstudio":"gemma-2-9b-it","platforms":["Ollama","LM Studio"],"tags":["High-Quality","Recommended"]},
    {"name":"Qwen2.5 7B","min_ram_gb":8,"min_vram_gb":4,"model_size_gb":4.4,"cpu_ok":True,"quality":4,"category":"Text / Chat","description":"Alibaba multilingual model, top-tier 7B class.","ollama":"ollama run qwen2.5:7b","lmstudio":"qwen2.5-7b-instruct","platforms":["Ollama","LM Studio"],"tags":["Multilingual","Top-7B"]},
    {"name":"Llama 3.1 13B","min_ram_gb":12,"min_vram_gb":8,"model_size_gb":7.4,"cpu_ok":False,"quality":4,"category":"Text / Chat","description":"Great balance between quality and resource use.","ollama":"ollama run llama3.1:13b","lmstudio":"meta-llama-3.1-13b-instruct","platforms":["Ollama","LM Studio"],"tags":["High-Quality","GPU-Recommended"]},
    {"name":"Mistral Nemo 12B","min_ram_gb":12,"min_vram_gb":8,"model_size_gb":7.1,"cpu_ok":False,"quality":4,"category":"Text / Chat","description":"Latest Mistral with extended context window.","ollama":"ollama run mistral-nemo","lmstudio":"mistral-nemo-instruct-2407","platforms":["Ollama","LM Studio"],"tags":["Long-Context","High-Quality"]},
    {"name":"Llama 3.1 70B (Q4)","min_ram_gb":40,"min_vram_gb":24,"model_size_gb":39.0,"cpu_ok":False,"quality":5,"category":"Text / Chat","description":"GPT-4 level quality. Needs high-end GPU/server.","ollama":"ollama run llama3.1:70b","lmstudio":"meta-llama-3.1-70b-instruct","platforms":["Ollama","LM Studio"],"tags":["GPT-4 Class","Needs 24GB VRAM"]},
    {"name":"Mixtral 8x7B (Q4)","min_ram_gb":32,"min_vram_gb":20,"model_size_gb":26.0,"cpu_ok":False,"quality":5,"category":"Text / Chat","description":"Mixture-of-experts. Excellent reasoning.","ollama":"ollama run mixtral:8x7b","lmstudio":"mixtral-8x7b-instruct","platforms":["Ollama","LM Studio"],"tags":["Reasoning","Expert"]},
    {"name":"DeepSeek Coder 1.3B","min_ram_gb":3,"min_vram_gb":1,"model_size_gb":0.8,"cpu_ok":True,"quality":3,"category":"Code Generation","description":"Lightweight code model. Works on any PC.","ollama":"ollama run deepseek-coder:1.3b","lmstudio":"deepseek-coder-1.3b-instruct","platforms":["Ollama","LM Studio"],"tags":["Code","CPU-OK","Lightweight"]},
    {"name":"DeepSeek Coder 6.7B","min_ram_gb":8,"min_vram_gb":4,"model_size_gb":3.8,"cpu_ok":True,"quality":4,"category":"Code Generation","description":"Excellent coding assistant, better than Copilot base.","ollama":"ollama run deepseek-coder:6.7b","lmstudio":"deepseek-coder-6.7b-instruct","platforms":["Ollama","LM Studio"],"tags":["Code","Recommended"]},
    {"name":"Qwen2.5-Coder 7B","min_ram_gb":8,"min_vram_gb":4,"model_size_gb":4.5,"cpu_ok":True,"quality":5,"category":"Code Generation","description":"Best open-source code model in 7B class (2024).","ollama":"ollama run qwen2.5-coder:7b","lmstudio":"qwen2.5-coder-7b-instruct","platforms":["Ollama","LM Studio"],"tags":["Code","Best-Code-7B","Recommended"]},
    {"name":"CodeLlama 13B","min_ram_gb":12,"min_vram_gb":8,"model_size_gb":7.3,"cpu_ok":False,"quality":4,"category":"Code Generation","description":"Meta dedicated coding model.","ollama":"ollama run codellama:13b","lmstudio":"codellama-13b-instruct","platforms":["Ollama","LM Studio"],"tags":["Code","GPU-Recommended"]},
    {"name":"LLaVA 7B","min_ram_gb":8,"min_vram_gb":4,"model_size_gb":4.5,"cpu_ok":True,"quality":3,"category":"Vision / Multimodal","description":"Analyze images with a local AI model.","ollama":"ollama run llava:7b","lmstudio":"llava-v1.6-mistral-7b","platforms":["Ollama","LM Studio"],"tags":["Vision","Image-Analysis"]},
    {"name":"LLaVA 13B","min_ram_gb":14,"min_vram_gb":8,"model_size_gb":8.0,"cpu_ok":False,"quality":4,"category":"Vision / Multimodal","description":"Higher quality vision model.","ollama":"ollama run llava:13b","lmstudio":"llava-v1.6-vicuna-13b","platforms":["Ollama","LM Studio"],"tags":["Vision","GPU-Recommended"]},
    {"name":"Stable Diffusion 1.5","min_ram_gb":6,"min_vram_gb":2,"model_size_gb":2.0,"cpu_ok":True,"quality":3,"category":"Image Generation","description":"Classic image generator. 512×512 images.","ollama":None,"lmstudio":None,"platforms":["AUTOMATIC1111","ComfyUI","Invoke AI"],"tags":["Image-Gen","Classic"],"install_url":"https://github.com/AUTOMATIC1111/stable-diffusion-webui"},
    {"name":"Stable Diffusion XL","min_ram_gb":8,"min_vram_gb":6,"model_size_gb":6.5,"cpu_ok":False,"quality":4,"category":"Image Generation","description":"High-quality 1024×1024 image generator.","ollama":None,"lmstudio":None,"platforms":["AUTOMATIC1111","ComfyUI"],"tags":["Image-Gen","1024px"],"install_url":"https://github.com/comfyanonymous/ComfyUI"},
    {"name":"FLUX.1 Schnell","min_ram_gb":16,"min_vram_gb":8,"model_size_gb":11.0,"cpu_ok":False,"quality":5,"category":"Image Generation","description":"State-of-the-art open image model (2024). Ultra-realistic.","ollama":None,"lmstudio":None,"platforms":["ComfyUI"],"tags":["Image-Gen","SOTA","Best-Quality"],"install_url":"https://github.com/comfyanonymous/ComfyUI"},
    {"name":"Whisper Tiny","min_ram_gb":2,"min_vram_gb":0,"model_size_gb":0.15,"cpu_ok":True,"quality":2,"category":"Speech-to-Text","description":"Ultra-fast transcription on any PC.","ollama":None,"lmstudio":None,"platforms":["Faster-Whisper","Whisper.cpp"],"tags":["Audio","CPU-OK","Ultra-Fast"]},
    {"name":"Whisper Large v3","min_ram_gb":8,"min_vram_gb":4,"model_size_gb":1.5,"cpu_ok":True,"quality":5,"category":"Speech-to-Text","description":"Best open-source speech recognition. 99+ languages.","ollama":None,"lmstudio":None,"platforms":["Faster-Whisper","Whisper.cpp"],"tags":["Audio","Best-Quality","Multilingual"]},
    {"name":"nomic-embed-text","min_ram_gb":2,"min_vram_gb":0,"model_size_gb":0.27,"cpu_ok":True,"quality":4,"category":"Embeddings / RAG","description":"Best local embedding model for RAG pipelines.","ollama":"ollama run nomic-embed-text","lmstudio":"nomic-embed-text-v1.5","platforms":["Ollama","LM Studio"],"tags":["RAG","Embeddings","CPU-OK"]},
]

PLATFORMS = {
    "Ollama":{"url":"https://ollama.com/download","desc":"Easiest LLM runner. One-command install + system tray.","steps":["Download installer from https://ollama.com/download","Run installer (Ollama runs in system tray)","Open terminal: ollama run &lt;model-name&gt;","REST API on http://localhost:11434"]},
    "LM Studio":{"url":"https://lmstudio.ai","desc":"Best GUI — built-in model browser, chat UI, local API.","steps":["Download from https://lmstudio.ai","Install and open LM Studio","Discover tab → search &amp; download models","Load model → Chat tab or local API server (port 1234)"]},
    "GPT4All":{"url":"https://gpt4all.io","desc":"Simple offline chatbot desktop app.","steps":["Download from https://gpt4all.io","Install and open GPT4All","Model Explorer → download models","Chat directly in the app"]},
    "AUTOMATIC1111":{"url":"https://github.com/AUTOMATIC1111/stable-diffusion-webui","desc":"Most popular Stable Diffusion WebUI with 1000s of extensions.","steps":["Install Python 3.10 + Git","git clone https://github.com/AUTOMATIC1111/stable-diffusion-webui","Place .safetensors in models/Stable-diffusion/","Run webui-user.bat → opens http://127.0.0.1:7860"]},
    "ComfyUI":{"url":"https://github.com/comfyanonymous/ComfyUI","desc":"Node-based workflow UI — supports FLUX, SDXL, ControlNet.","steps":["Download portable ZIP from GitHub releases","Extract and place models in models/checkpoints/","Run run_nvidia_gpu.bat (or run_cpu.bat)","Open http://127.0.0.1:8188"]},
    "Faster-Whisper":{"url":"https://github.com/SYSTRAN/faster-whisper","desc":"4× faster Whisper transcription library in Python.","steps":["pip install faster-whisper","from faster_whisper import WhisperModel","model = WhisperModel('large-v3', device='cuda')","segments, _ = model.transcribe('audio.mp3')"]},
}

# ─── Hardware detection (reused from cli version) ────────────────────────────

def _run_ps(cmd, fallback=""):
    try:
        r = subprocess.run(["powershell","-NoProfile","-Command",cmd],
                           capture_output=True, text=True, timeout=10)
        return r.stdout.strip()
    except Exception: return fallback

def get_cpu_info():
    info={"name":platform.processor() or "Unknown CPU","cores_physical":psutil.cpu_count(logical=False) or 1,
          "cores_logical":psutil.cpu_count(logical=True) or 1,"freq_base_mhz":0.0,"freq_max_mhz":0.0,
          "arch":platform.machine(),"bits":struct.calcsize("P")*8,"avx2":False}
    freq=psutil.cpu_freq()
    if freq: info["freq_base_mhz"]=freq.current; info["freq_max_mhz"]=freq.max or freq.current
    if HAS_CPUINFO:
        try:
            ci=py_cpuinfo.get_cpu_info()
            info["name"]=ci.get("brand_raw",info["name"]); info["avx2"]="avx2" in ci.get("flags",[])
            if not info["freq_max_mhz"] and ci.get("hz_advertised"):
                info["freq_max_mhz"]=ci["hz_advertised"][0]/1_000_000
        except Exception: pass
    else:
        n=_run_ps("(Get-WmiObject Win32_Processor).Name")
        if n: info["name"]=n.splitlines()[0].strip()
        ms=_run_ps("(Get-WmiObject Win32_Processor).MaxClockSpeed")
        if ms.isdigit(): info["freq_max_mhz"]=float(ms)
    return info

def get_ram_info():
    vm=psutil.virtual_memory()
    info={"total_gb":round(vm.total/(1024**3),1),"available_gb":round(vm.available/(1024**3),1),
          "used_gb":round(vm.used/(1024**3),1),"percent":vm.percent,"speed_mhz":0,"type":"Unknown","channels":0}
    raw=_run_ps("Get-WmiObject Win32_PhysicalMemory|Select-Object Speed,SMBIOSMemoryType,DeviceLocator|ConvertTo-Json -Compress")
    if raw:
        try:
            d=json.loads(raw); d=[d] if isinstance(d,dict) else d
            speeds=[x.get("Speed",0) for x in d if x.get("Speed")]
            if speeds: info["speed_mhz"]=max(speeds)
            info["channels"]=len(d)
            info["type"]={26:"DDR4",34:"DDR5",24:"DDR3",20:"DDR2"}.get(d[0].get("SMBIOSMemoryType",0),"DDR4")
        except Exception: pass
    return info

def get_gpu_info():
    gpus=[]
    try:
        for g in GPUtil.getGPUs():
            gpus.append({"name":g.name,"vram_gb":round(g.memoryTotal/1024,1),
                         "vram_used_gb":round(g.memoryUsed/1024,1),"driver":g.driver,
                         "temp_c":g.temperature,"load_pct":round(g.load*100,1),"vendor":"NVIDIA","cuda":True})
    except Exception: pass
    raw=_run_ps("Get-WmiObject Win32_VideoController|Select-Object Name,AdapterRAM,DriverVersion|ConvertTo-Json -Compress")
    if raw:
        try:
            d=json.loads(raw); d=[d] if isinstance(d,dict) else d
            for item in d:
                n=(item.get("Name") or "Unknown GPU").strip()
                if any(g["name"] in n or n in g["name"] for g in gpus): continue
                ar=item.get("AdapterRAM") or 0
                vram=round(int(ar)/(1024**3),1) if ar else 0
                nl=n.lower()
                vendor="NVIDIA" if any(x in nl for x in ["nvidia","geforce","rtx","gtx"]) else \
                       "AMD"    if any(x in nl for x in ["amd","radeon","rx "]) else \
                       "Intel"  if any(x in nl for x in ["intel","arc","iris","uhd"]) else "Unknown"
                gpus.append({"name":n,"vram_gb":vram,"vram_used_gb":0,"driver":item.get("DriverVersion","N/A"),
                             "temp_c":None,"load_pct":None,"vendor":vendor,"cuda":vendor=="NVIDIA"})
        except Exception: pass
    if not gpus:
        gpus.append({"name":"GPU not detected","vram_gb":0,"vram_used_gb":0,"driver":"N/A",
                     "temp_c":None,"load_pct":None,"vendor":"Unknown","cuda":False})
    return gpus

def get_disk_info():
    disks=[]
    disk_types={}
    raw=_run_ps("Get-PhysicalDisk|Select-Object DeviceId,MediaType,Model|ConvertTo-Json -Compress")
    if raw:
        try:
            d=json.loads(raw); d=[d] if isinstance(d,dict) else d
            for item in d:
                mt=item.get("MediaType",""); did=str(item.get("DeviceId",""))
                disk_types[did]="SSD" if "SSD" in mt or "3"==mt else \
                                 "HDD" if "HDD" in mt or "4"==mt else \
                                 "NVMe SSD" if "nvme" in item.get("Model","").lower() else "SSD/Unknown"
        except Exception: pass
    for p in psutil.disk_partitions(all=False):
        try:
            u=psutil.disk_usage(p.mountpoint)
            dtype=list(disk_types.values())[0] if disk_types else "Unknown"
            disks.append({"mountpoint":p.mountpoint,"total_gb":round(u.total/(1024**3),1),
                          "used_gb":round(u.used/(1024**3),1),"free_gb":round(u.free/(1024**3),1),
                          "percent":u.percent,"type":dtype})
        except PermissionError: pass
    return disks

def get_os_info():
    info={"name":"Windows","build":"","directx":"DirectX 12 (est.)","cuda_version":"Not installed","python":platform.python_version()}
    n=_run_ps("(Get-WmiObject Win32_OperatingSystem).Caption")
    if n: info["name"]=n.splitlines()[0].strip()
    b=_run_ps("(Get-WmiObject Win32_OperatingSystem).BuildNumber")
    if b: info["build"]=b.strip()
    try:
        import winreg
        key=winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,r"SOFTWARE\Microsoft\DirectX")
        info["directx"]=f"DirectX ({winreg.QueryValueEx(key,'Version')[0]})"
        winreg.CloseKey(key)
    except Exception: pass
    try:
        r=subprocess.run(["nvidia-smi"],capture_output=True,text=True,timeout=5)
        for line in r.stdout.splitlines():
            if "CUDA Version" in line:
                info["cuda_version"]=line.split("CUDA Version:")[-1].strip().split()[0]; break
    except Exception: pass
    return info

def cpu_benchmark():
    import threading
    N=500_000
    def _crunch():
        s=0.0
        for i in range(1,N): s+=math.sqrt(i)*math.log(i+1)
        return s
    t0=time.perf_counter(); _crunch(); t1=time.perf_counter()
    single=round(N/(t1-t0)/1_000_000,2)
    cores=psutil.cpu_count(logical=True)
    threads=[threading.Thread(target=_crunch) for _ in range(cores)]
    t0=time.perf_counter()
    for th in threads: th.start()
    for th in threads: th.join()
    t1=time.perf_counter()
    multi=round(N*cores/(t1-t0)/1_000_000,2)
    return single, multi

def match_gpu(name):
    best=None; blen=0
    for k,v in GPU_DB.items():
        if k.upper() in name.upper() and len(k)>blen:
            best={**v,"db_key":k}; blen=len(k)
    return best

def check_compatibility(ram_gb, vram_gb, has_cuda):
    order={"excellent":0,"good":1,"cpu_only":2,"limited":3,"no":4}
    results=[]
    for m in AI_MODELS:
        if ram_gb>=m["min_ram_gb"] and vram_gb>=m["min_vram_gb"] and (has_cuda or m.get("cpu_ok")):
            status="excellent" if vram_gb>=m["min_vram_gb"]*1.5 and ram_gb>=m["min_ram_gb"]*1.5 else "good"
            note="Runs fast with headroom" if status=="excellent" else "Meets requirements"
        elif ram_gb>=m["min_ram_gb"] and m.get("cpu_ok"):
            status="cpu_only"; note="No GPU — will run on CPU (slow)"
        elif ram_gb>=m["min_ram_gb"]*0.85 and vram_gb>=m["min_vram_gb"]*0.85:
            status="limited"; note="Slightly under spec — try quantized version"
        else:
            status="no"; note=f"Need {m['min_ram_gb']}GB RAM, {m['min_vram_gb']}GB VRAM"
        results.append({**m,"status":status,"note":note})
    results.sort(key=lambda x:(order[x["status"]],x["category"],-x["quality"]))
    return results

def compute_score(cpu, ram, gpus, gpu_match):
    s=0
    r=ram["total_gb"]
    s+=25 if r>=64 else 22 if r>=32 else 18 if r>=16 else 12 if r>=8 else 6 if r>=4 else 2
    v=max((g["vram_gb"] for g in gpus),default=0)
    s+=35 if v>=24 else 30 if v>=16 else 26 if v>=12 else 22 if v>=8 else 16 if v>=6 else 10 if v>=4 else 4 if v>=2 else 0
    if gpu_match: s+=min(20,int(gpu_match.get("score",0)/5))
    cores=cpu["cores_physical"]; freq=cpu["freq_max_mhz"]/1000
    s+=15 if cores>=16 and freq>=4 else 13 if cores>=12 and freq>=3.5 else 10 if cores>=8 and freq>=3 else 7 if cores>=6 else 4 if cores>=4 else 1
    if any(g["cuda"] for g in gpus): s+=5
    s=min(100,s)
    label = "EXCELLENT — Runs top-tier local AI" if s>=90 else \
            "GREAT — Runs most local AI models" if s>=75 else \
            "GOOD — Handles mid-range AI well"  if s>=55 else \
            "FAIR — Basic models only"           if s>=35 else \
            "LOW — CPU-only / tiny models"       if s>=15 else \
            "NOT SUITABLE — Upgrade recommended"
    return s, label

def find_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]

# ─── API vs Local Comparison Data ────────────────────────────────────────────
# Real-world measured / published benchmarks (April 2026)
API_PROVIDERS = [
    # name, model_label, tok_s, first_token_ms, price_input_per_1m, price_output_per_1m, quality_5, notes
    {"name":"OpenAI",     "model":"GPT-4o",             "tok_s":75,  "latency_ms":450, "price_in":2.50,  "price_out":10.0,  "quality":5, "category":"frontier", "color":"#10a37f"},
    {"name":"OpenAI",     "model":"GPT-4o mini",        "tok_s":110, "latency_ms":280, "price_in":0.15,  "price_out":0.60,  "quality":4, "category":"fast",     "color":"#10a37f"},
    {"name":"OpenAI",     "model":"o3-mini",            "tok_s":40,  "latency_ms":1200,"price_in":1.10,  "price_out":4.40,  "quality":5, "category":"reasoning","color":"#10a37f"},
    {"name":"Anthropic",  "model":"Claude 3.5 Sonnet",  "tok_s":85,  "latency_ms":380, "price_in":3.00,  "price_out":15.0,  "quality":5, "category":"frontier", "color":"#d4a853"},
    {"name":"Anthropic",  "model":"Claude 3.5 Haiku",   "tok_s":130, "latency_ms":200, "price_in":0.80,  "price_out":4.00,  "quality":4, "category":"fast",     "color":"#d4a853"},
    {"name":"Google",     "model":"Gemini 2.0 Flash",   "tok_s":150, "latency_ms":170, "price_in":0.10,  "price_out":0.40,  "quality":4, "category":"fast",     "color":"#4285f4"},
    {"name":"Google",     "model":"Gemini 1.5 Pro",     "tok_s":65,  "latency_ms":500, "price_in":3.50,  "price_out":10.50, "quality":5, "category":"frontier", "color":"#4285f4"},
    {"name":"Groq",       "model":"Llama 3.3 70B",      "tok_s":380, "latency_ms":55,  "price_in":0.59,  "price_out":0.79,  "quality":4, "category":"fast",     "color":"#f55036"},
    {"name":"Groq",       "model":"Llama 3.1 8B",       "tok_s":750, "latency_ms":30,  "price_in":0.05,  "price_out":0.08,  "quality":3, "category":"fast",     "color":"#f55036"},
    {"name":"Together AI","model":"Mixtral 8x7B",       "tok_s":100, "latency_ms":300, "price_in":0.60,  "price_out":0.60,  "quality":4, "category":"fast",     "color":"#7b68ee"},
    {"name":"Mistral AI", "model":"Mistral Large",      "tok_s":70,  "latency_ms":420, "price_in":2.00,  "price_out":6.00,  "quality":5, "category":"frontier", "color":"#ff7000"},
    {"name":"Mistral AI", "model":"Mistral Nemo (free)","tok_s":90,  "latency_ms":300, "price_in":0.00,  "price_out":0.00,  "quality":3, "category":"free",     "color":"#ff7000"},
    {"name":"Cohere",     "model":"Command R+",         "tok_s":80,  "latency_ms":350, "price_in":2.50,  "price_out":10.0,  "quality":4, "category":"frontier", "color":"#39594d"},
    {"name":"Perplexity", "model":"Sonar Large",        "tok_s":90,  "latency_ms":350, "price_in":1.00,  "price_out":1.00,  "quality":4, "category":"frontier", "color":"#20808d"},
]

# GPU TDP database (watts) for electricity cost estimation
GPU_TDP = {
    "RTX 5090":575,"RTX 5080":360,"RTX 5070 Ti":300,"RTX 5070":250,
    "RTX 4090":450,"RTX 4080 SUPER":320,"RTX 4080":320,
    "RTX 4070 Ti SUPER":285,"RTX 4070 Ti":285,"RTX 4070 SUPER":220,"RTX 4070":200,
    "RTX 4060 Ti":165,"RTX 4060":115,"RTX 4050":70,
    "RTX 3090 Ti":450,"RTX 3090":350,"RTX 3080 Ti":350,"RTX 3080":320,
    "RTX 3070 Ti":290,"RTX 3070":220,"RTX 3060 Ti":200,"RTX 3060":170,"RTX 3050":130,
    "RTX 2080 Ti":260,"RTX 2080 SUPER":250,"RTX 2080":225,"RTX 2070 SUPER":215,
    "RTX 2070":175,"RTX 2060 SUPER":175,"RTX 2060":160,
    "GTX 1080 Ti":250,"GTX 1080":180,"GTX 1070 Ti":180,"GTX 1070":150,
    "GTX 1660 Ti":120,"GTX 1660 SUPER":125,"GTX 1660":120,"GTX 1060":120,"GTX 1650":75,
    "RX 7900 XTX":355,"RX 7900 XT":315,"RX 7900 GRE":260,"RX 7800 XT":263,
    "RX 7700 XT":245,"RX 7600":165,
    "RX 6950 XT":335,"RX 6900 XT":300,"RX 6800 XT":300,"RX 6800":250,
    "RX 6700 XT":230,"RX 6600 XT":160,"RX 6600":132,"RX 5700 XT":225,"RX 5700":185,
    "Arc A770":225,"Arc A750":225,"Arc A580":185,"Arc A380":75,
}

def build_comparison(gpu_match: Optional[Dict], gpus: List[Dict], has_cuda: bool, bench_multi: float) -> Dict:
    """Build the API vs Local comparison payload."""
    # Determine local tok/s: GPU if matched, fallback CPU estimate
    local_tok_s_gpu  = gpu_match["tok_s"] if gpu_match else 0
    # CPU inference estimate: ~2 tok/s per physical core at 7B Q4 (very rough)
    local_tok_s_cpu  = max(2, int(bench_multi * 1.5))
    local_tok_s      = local_tok_s_gpu if (has_cuda and local_tok_s_gpu > 0) else local_tok_s_cpu

    # Local latency: GPU ~200-400ms model-load sliding window (prompt eval), CPU ~800-2000ms
    local_latency_ms = 250 if (has_cuda and local_tok_s_gpu >= 20) else 600 if local_tok_s_gpu >= 8 else 1500

    # Determine real GPU name for TDP lookup
    gpu_tdp = 75  # default fallback
    for g in gpus:
        for key, tdp in GPU_TDP.items():
            if key.upper() in g["name"].upper():
                gpu_tdp = tdp; break

    # Electricity cost: assume 8h/day AI usage
    # kWh/day = TDP_watts/1000 * hours; cost at $0.12/kWh
    kwh_per_month = (gpu_tdp / 1000) * 8 * 30
    elec_cost_monthly = round(kwh_per_month * 0.12, 2)

    # Monthly API cost at "typical developer" usage: 2M input + 1M output tokens/month
    monthly_input_tokens  = 2_000_000
    monthly_output_tokens = 1_000_000

    providers_enriched = []
    for p in API_PROVIDERS:
        monthly_cost = (
            (monthly_input_tokens  / 1_000_000) * p["price_in"] +
            (monthly_output_tokens / 1_000_000) * p["price_out"]
        )
        providers_enriched.append({
            **p,
            "monthly_cost": round(monthly_cost, 2),
            "is_local": False,
        })

    # Build speed comparison rows (API + local)
    speed_rows = []
    for p in providers_enriched:
        speed_rows.append({"label": f"{p['name']} / {p['model']}", "tok_s": p["tok_s"],
                           "color": p["color"], "is_local": False})
    speed_rows.append({
        "label": f"YOUR PC (GPU) / {gpus[0]['name'] if gpus else 'Local'}",
        "tok_s": local_tok_s_gpu if (has_cuda and local_tok_s_gpu > 0) else 0,
        "color": "#3fb950", "is_local": True, "is_gpu": True,
    })
    speed_rows.append({
        "label": "YOUR PC (CPU only)",
        "tok_s": local_tok_s_cpu,
        "color": "#d29922", "is_local": True, "is_gpu": False,
    })
    max_tok = max(r["tok_s"] for r in speed_rows) or 1

    # Break-even: tokens you need to generate before local is cheaper than cheapest paid API
    # Cheapest non-free paid API per output token:
    paid_apis = [p for p in providers_enriched if p["price_out"] > 0]
    cheapest = min(paid_apis, key=lambda x: x["price_out"]) if paid_apis else None
    # Break-even tokens (output) = electricity_monthly / (price_out_per_token)
    if cheapest and cheapest["price_out"] > 0:
        price_per_token = cheapest["price_out"] / 1_000_000
        breakeven_tokens = int(elec_cost_monthly / price_per_token) if price_per_token > 0 else None
    else:
        breakeven_tokens = None

    # Feature matrix
    features = [
        {"name":"100% Private / No data sent",   "local":True,  "api":False},
        {"name":"Works Offline (no internet)",    "local":True,  "api":False},
        {"name":"Zero cost per token",            "local":True,  "api":False},
        {"name":"No rate limits / throttling",    "local":True,  "api":False},
        {"name":"Customizable / Fine-tunable",    "local":True,  "api":False},
        {"name":"Run uncensored models",          "local":True,  "api":False},
        {"name":"Frontier model quality",         "local":False, "api":True},
        {"name":"No hardware requirement",        "local":False, "api":True},
        {"name":"Multi-modal out of the box",     "local":False, "api":True},
        {"name":"Always up-to-date knowledge",    "local":False, "api":True},
        {"name":"Instant setup (no downloads)",   "local":False, "api":True},
        {"name":"Scales to thousands of users",   "local":False, "api":True},
    ]

    # Latency comparison list
    latency_rows = []
    for p in providers_enriched:
        latency_rows.append({"label": f"{p['model']}", "provider": p["name"],
                             "ms": p["latency_ms"], "color": p["color"], "is_local": False})
    latency_rows.append({"label": f"{gpus[0]['name'] if gpus else 'Local GPU'} (GPU)",
                         "provider": "Your PC", "ms": local_latency_ms,
                         "color": "#3fb950", "is_local": True})
    latency_rows.sort(key=lambda x: x["ms"])
    max_lat = max(r["ms"] for r in latency_rows) or 1

    return {
        "providers":         providers_enriched,
        "local_tok_s_gpu":   local_tok_s_gpu,
        "local_tok_s_cpu":   local_tok_s_cpu,
        "local_latency_ms":  local_latency_ms,
        "gpu_tdp_watts":     gpu_tdp,
        "elec_cost_monthly": elec_cost_monthly,
        "kwh_per_month":     round(kwh_per_month, 1),
        "speed_rows":        speed_rows,
        "max_tok":           max_tok,
        "latency_rows":      latency_rows,
        "max_lat":           max_lat,
        "features":          features,
        "breakeven_tokens":  breakeven_tokens,
        "cheapest_api":      cheapest,
        "monthly_input_tokens":  monthly_input_tokens,
        "monthly_output_tokens": monthly_output_tokens,
    }

# ─── HTML Template ────────────────────────────────────────────────────────────
HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>AI PC Checker — {{ data.os.name }}</title>
<style>
  :root{--bg:#0d1117;--bg2:#161b22;--bg3:#1c2128;--border:#30363d;--text:#e6edf3;--muted:#8b949e;
        --green:#3fb950;--blue:#58a6ff;--purple:#bc8cff;--yellow:#d29922;--orange:#f0883e;--red:#f85149;
        --cyan:#39d353;--score-color:#3fb950;}
  *{box-sizing:border-box;margin:0;padding:0}
  body{background:var(--bg);color:var(--text);font-family:'Segoe UI',system-ui,sans-serif;font-size:14px;line-height:1.6}
  a{color:var(--blue);text-decoration:none} a:hover{text-decoration:underline}
  header{background:linear-gradient(135deg,#0d1117 0%,#161b22 50%,#1a1f2e 100%);
         border-bottom:1px solid var(--border);padding:2rem 2rem 1.5rem;text-align:center;}
  header h1{font-size:2rem;font-weight:700;background:linear-gradient(90deg,#58a6ff,#bc8cff,#39d353);
             -webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text}
  header p{color:var(--muted);margin-top:.4rem;font-size:.875rem}
  .badge-scan{display:inline-block;background:#161b22;border:1px solid var(--border);
               border-radius:20px;padding:.2rem .8rem;font-size:.75rem;color:var(--muted);margin-top:.6rem}
  nav{background:var(--bg2);border-bottom:1px solid var(--border);display:flex;gap:.25rem;
      padding:.5rem 1rem;flex-wrap:wrap;position:sticky;top:0;z-index:100}
  nav a{color:var(--muted);padding:.4rem .9rem;border-radius:6px;font-size:.8rem;font-weight:500;transition:all .2s}
  nav a:hover,nav a.active{background:var(--bg3);color:var(--text);text-decoration:none}
  .container{max-width:1200px;margin:0 auto;padding:1.5rem 1.5rem}
  section{margin-bottom:2.5rem}
  section h2{font-size:1.1rem;font-weight:600;color:var(--blue);margin-bottom:1rem;
              display:flex;align-items:center;gap:.5rem;padding-bottom:.5rem;border-bottom:1px solid var(--border)}
  .grid{display:grid;gap:1rem}
  .grid-2{grid-template-columns:repeat(auto-fit,minmax(340px,1fr))}
  .grid-3{grid-template-columns:repeat(auto-fit,minmax(260px,1fr))}
  .card{background:var(--bg2);border:1px solid var(--border);border-radius:10px;padding:1.25rem;transition:border-color .2s}
  .card:hover{border-color:#58a6ff55}
  .card-header{display:flex;align-items:center;gap:.6rem;margin-bottom:1rem;padding-bottom:.75rem;border-bottom:1px solid var(--border)}
  .card-header .icon{font-size:1.4rem}
  .card-header h3{font-size:.95rem;font-weight:600}
  .card-header .vendor{font-size:.7rem;color:var(--muted);background:var(--bg3);
                        border:1px solid var(--border);padding:.1rem .5rem;border-radius:10px;margin-left:auto}
  .row{display:flex;justify-content:space-between;align-items:center;padding:.35rem 0;
        border-bottom:1px solid #21262d}
  .row:last-child{border-bottom:none}
  .row .label{color:var(--muted);font-size:.8rem}
  .row .value{font-size:.85rem;font-weight:500;text-align:right}
  .bar-wrap{display:flex;align-items:center;gap:.6rem;width:100%}
  .bar-bg{flex:1;background:#21262d;border-radius:4px;height:6px;overflow:hidden}
  .bar-fill{height:100%;border-radius:4px;transition:width 1.2s cubic-bezier(.4,0,.2,1)}
  .bar-label{font-size:.75rem;color:var(--muted);white-space:nowrap;min-width:70px;text-align:right}
  /* Score gauge */
  .score-section{background:var(--bg2);border:1px solid var(--border);border-radius:12px;
                  padding:2rem;display:flex;align-items:center;gap:2rem;flex-wrap:wrap}
  .gauge-wrap{position:relative;width:160px;height:160px;flex-shrink:0}
  .gauge-wrap svg{width:100%;height:100%;transform:rotate(-90deg)}
  .gauge-bg{fill:none;stroke:#21262d;stroke-width:12}
  .gauge-fill{fill:none;stroke-width:12;stroke-linecap:round;transition:stroke-dashoffset 1.5s cubic-bezier(.4,0,.2,1)}
  .gauge-text{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center}
  .gauge-score{font-size:2.5rem;font-weight:800;line-height:1}
  .gauge-max{font-size:.75rem;color:var(--muted)}
  .score-details h2{font-size:1.3rem;font-weight:700;margin-bottom:.5rem}
  .score-details p{color:var(--muted);font-size:.875rem;max-width:500px}
  .score-pills{display:flex;flex-wrap:wrap;gap:.4rem;margin-top:.8rem}
  .pill{background:var(--bg3);border:1px solid var(--border);border-radius:20px;
         padding:.2rem .7rem;font-size:.72rem;font-weight:500}
  /* Model table */
  .cat-tabs{display:flex;gap:.4rem;flex-wrap:wrap;margin-bottom:1rem}
  .tab-btn{background:var(--bg3);border:1px solid var(--border);color:var(--muted);
            padding:.35rem .9rem;border-radius:20px;cursor:pointer;font-size:.78rem;font-weight:500;
            transition:all .2s}
  .tab-btn:hover,.tab-btn.active{background:#58a6ff22;border-color:var(--blue);color:var(--blue)}
  .model-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:.75rem}
  .model-card{background:var(--bg2);border:1px solid var(--border);border-radius:8px;padding:1rem;
               transition:border-color .2s;position:relative;overflow:hidden}
  .model-card::before{content:'';position:absolute;inset:0;opacity:0;transition:opacity .2s}
  .model-card:hover{border-color:#58a6ff55}
  .model-card.status-excellent{border-left:3px solid var(--green)}
  .model-card.status-good{border-left:3px solid var(--blue)}
  .model-card.status-cpu_only{border-left:3px solid var(--yellow)}
  .model-card.status-limited{border-left:3px solid var(--orange)}
  .model-card.status-no{border-left:3px solid #333;opacity:.5}
  .model-card.hidden{display:none}
  .model-top{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:.5rem}
  .model-name{font-weight:600;font-size:.9rem}
  .status-badge{font-size:.65rem;font-weight:700;padding:.2rem .55rem;border-radius:10px;text-transform:uppercase;white-space:nowrap}
  .badge-excellent{background:#3fb95022;color:var(--green);border:1px solid #3fb95044}
  .badge-good{background:#58a6ff22;color:var(--blue);border:1px solid #58a6ff44}
  .badge-cpu_only{background:#d2992222;color:var(--yellow);border:1px solid #d2992244}
  .badge-limited{background:#f0883e22;color:var(--orange);border:1px solid #f0883e44}
  .badge-no{background:#f8514922;color:var(--red);border:1px solid #f8514944}
  .model-desc{font-size:.78rem;color:var(--muted);margin-bottom:.6rem}
  .model-meta{display:flex;flex-wrap:wrap;gap:.35rem}
  .meta-chip{background:var(--bg3);border:1px solid var(--border);border-radius:4px;
              font-size:.68rem;padding:.1rem .45rem;color:var(--muted)}
  .stars{color:#d29922;font-size:.85rem}
  .ollama-cmd{background:#0d1117;border:1px solid var(--border);border-radius:5px;
               padding:.4rem .7rem;font-family:'Cascadia Code','Consolas',monospace;font-size:.75rem;
               color:var(--cyan);margin-top:.6rem;display:flex;justify-content:space-between;align-items:center;gap:.5rem}
  .copy-btn{background:none;border:none;color:var(--muted);cursor:pointer;font-size:.8rem;
             padding:.1rem .3rem;border-radius:3px;transition:all .2s}
  .copy-btn:hover{background:var(--bg3);color:var(--text)}
  /* Guides */
  .guide-card{background:var(--bg2);border:1px solid var(--border);border-radius:10px;
               margin-bottom:1rem;overflow:hidden}
  .guide-head{padding:1rem 1.25rem;display:flex;justify-content:space-between;align-items:center;
               cursor:pointer;user-select:none}
  .guide-head:hover{background:var(--bg3)}
  .guide-title{font-weight:600;font-size:.95rem;display:flex;align-items:center;gap:.6rem}
  .guide-desc{font-size:.78rem;color:var(--muted)}
  .guide-body{padding:0 1.25rem;max-height:0;overflow:hidden;transition:max-height .35s ease,padding .35s}
  .guide-body.open{max-height:400px;padding:1rem 1.25rem}
  .step{display:flex;gap:.7rem;margin-bottom:.6rem;align-items:flex-start}
  .step-num{background:var(--blue);color:#0d1117;width:20px;height:20px;border-radius:50%;
             display:flex;align-items:center;justify-content:center;font-size:.7rem;font-weight:700;flex-shrink:0;margin-top:.1rem}
  .step-text{font-size:.82rem;font-family:'Cascadia Code','Consolas',monospace;color:var(--text)}
  /* Quick start */
  .qs-list{list-style:none;display:flex;flex-direction:column;gap:.5rem}
  .qs-item{background:var(--bg2);border:1px solid var(--border);border-radius:8px;
            display:flex;align-items:center;gap:.9rem;padding:.75rem 1rem}
  .qs-num{background:linear-gradient(135deg,#58a6ff,#bc8cff);color:#0d1117;
           width:24px;height:24px;border-radius:50%;display:flex;align-items:center;
           justify-content:center;font-size:.75rem;font-weight:700;flex-shrink:0}
  .qs-name{min-width:170px;font-weight:600;font-size:.85rem}
  .qs-cmd{flex:1;font-family:'Cascadia Code','Consolas',monospace;font-size:.8rem;
           color:var(--cyan);background:#0d1117;padding:.3rem .6rem;border-radius:5px;
           border:1px solid var(--border)}
  /* Upgrade tips */
  .tip-card{background:var(--bg2);border:1px solid var(--border);border-left:3px solid var(--orange);
             border-radius:8px;padding:1rem 1.25rem;margin-bottom:.75rem}
  .tip-title{font-weight:600;margin-bottom:.25rem;font-size:.9rem}
  .tip-body{color:var(--muted);font-size:.82rem}
  /* Tier badge */
  .tier-S\\+,.tier-S{color:#bc8cff}
  .tier-A\\+,.tier-A{color:#3fb950}
  .tier-B\\+,.tier-B,.tier-B-{color:#d29922}
  .tier-C\\+,.tier-C{color:#f0883e}
  .tier-F{color:#f85149}
  tag{display:inline-block;background:#58a6ff18;border:1px solid #58a6ff33;color:var(--blue);
      border-radius:10px;font-size:.65rem;padding:.1rem .45rem;margin:.1rem}
  /* ── API vs Local Comparison ── */
  .cmp-tabs{display:flex;gap:.4rem;flex-wrap:wrap;margin-bottom:1.25rem}
  .cmp-tab{background:var(--bg3);border:1px solid var(--border);color:var(--muted);
            padding:.4rem 1rem;border-radius:20px;cursor:pointer;font-size:.78rem;font-weight:500;transition:all .2s}
  .cmp-tab:hover,.cmp-tab.active{background:#bc8cff22;border-color:#bc8cff;color:#bc8cff}
  .cmp-panel{display:none} .cmp-panel.active{display:block}
  .speed-row{display:flex;align-items:center;gap:.75rem;margin-bottom:.55rem}
  .speed-label{min-width:230px;font-size:.78rem;color:var(--text);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
  .speed-bar-wrap{flex:1;display:flex;align-items:center;gap:.5rem}
  .speed-bar-bg{flex:1;background:#21262d;border-radius:4px;height:18px;overflow:hidden;position:relative}
  .speed-bar-fill{height:100%;border-radius:4px;transition:width 1.2s cubic-bezier(.4,0,.2,1);
                   display:flex;align-items:center;padding-left:.4rem;font-size:.68rem;font-weight:600;color:#0d1117}
  .speed-val{font-size:.75rem;color:var(--muted);min-width:70px;text-align:right}
  .local-row .speed-label{color:#3fb950;font-weight:600}
  .local-row .speed-val{color:#3fb950;font-weight:600}
  .cpu-row  .speed-label{color:var(--yellow)}
  .cpu-row  .speed-val{color:var(--yellow)}
  .cmp-table{width:100%;border-collapse:collapse;font-size:.8rem}
  .cmp-table th{background:var(--bg3);color:var(--muted);font-weight:600;padding:.6rem .8rem;
                 text-align:left;border-bottom:2px solid var(--border);white-space:nowrap}
  .cmp-table td{padding:.55rem .8rem;border-bottom:1px solid #21262d;vertical-align:middle}
  .cmp-table tr:hover td{background:#161b2255}
  .cmp-table tr.local-highlight td{background:#3fb95010;border-left:3px solid var(--green)}
  .provider-dot{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:.4rem;flex-shrink:0}
  .cost-green{color:#3fb950;font-weight:600}
  .cost-yellow{color:#d29922}
  .cost-red{color:#f85149}
  .cost-free{color:#58a6ff;font-weight:600}
  .feat-grid{display:grid;grid-template-columns:1fr 1fr;gap:.5rem}
  @media(max-width:700px){.feat-grid{grid-template-columns:1fr}}
  .feat-row{display:flex;align-items:center;gap:.6rem;padding:.5rem .75rem;
             background:var(--bg2);border:1px solid var(--border);border-radius:7px;font-size:.82rem}
  .feat-row .feat-name{flex:1}
  .feat-check{font-size:1rem;min-width:24px;text-align:center}
  .feat-local{border-left:3px solid var(--green)}
  .feat-api{border-left:3px solid var(--blue)}
  .finance-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:1rem;margin-bottom:1.5rem}
  .fin-card{background:var(--bg2);border:1px solid var(--border);border-radius:10px;padding:1.1rem;text-align:center}
  .fin-card .fin-val{font-size:1.8rem;font-weight:800;margin-bottom:.25rem}
  .fin-card .fin-label{font-size:.75rem;color:var(--muted)}
  .fin-card .fin-sub{font-size:.7rem;color:var(--muted);margin-top:.2rem}
  .lat-row{display:flex;align-items:center;gap:.75rem;margin-bottom:.55rem}
  .lat-label{min-width:190px;font-size:.78rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
  .lat-provider{font-size:.68rem;color:var(--muted);min-width:80px}
  .winner-badge{background:#3fb95022;border:1px solid #3fb95044;color:#3fb950;
                 border-radius:20px;font-size:.65rem;font-weight:700;padding:.1rem .5rem;margin-left:.4rem}
  footer{text-align:center;color:var(--muted);font-size:.78rem;padding:2rem 1rem;
          border-top:1px solid var(--border)}
  @media(max-width:600px){
    .score-section{flex-direction:column}
    .gauge-wrap{width:120px;height:120px}
    nav{display:none}
  }
</style>
</head>
<body>

<header>
  <h1>⚡ AI PC Suitability Checker</h1>
  <p>Full hardware analysis &amp; local AI model compatibility report</p>
  <div class="badge-scan">🕐 Scanned {{ data.scanned_at }}  &nbsp;·&nbsp;  Port {{ data.port }}</div>
</header>

<nav>
  <a href="#score" class="active">Score</a>
  <a href="#cpu">CPU</a>
  <a href="#ram">RAM</a>
  <a href="#gpu">GPU</a>
  <a href="#storage">Storage</a>
  <a href="#os">System</a>
  <a href="#models">AI Models</a>
  <a href="#quickstart">Quick Start</a>
  <a href="#guides">Install Guides</a>
  <a href="#compare">API vs Local</a>
  {% if data.upgrade_tips %}<a href="#upgrades">Upgrades</a>{% endif %}
</nav>

<div class="container">

<!-- ── SCORE ────────────────────────────────────────────────────────────────── -->
<section id="score">
  <h2>🎯 AI Suitability Score</h2>
  <div class="score-section">
    <div class="gauge-wrap">
      <svg viewBox="0 0 100 100">
        <circle class="gauge-bg" cx="50" cy="50" r="38"/>
        <circle class="gauge-fill" cx="50" cy="50" r="38"
                id="gaugeFill"
                stroke="{{ data.score_color }}"
                stroke-dasharray="{{ data.score_dash }} 999"/>
      </svg>
      <div class="gauge-text">
        <span class="gauge-score" style="color:{{ data.score_color }}">{{ data.score }}</span>
        <span class="gauge-max">/100</span>
      </div>
    </div>
    <div class="score-details">
      <h2 style="color:{{ data.score_color }}">{{ data.rating }}</h2>
      <p>Based on your CPU, RAM, GPU VRAM, CUDA availability and overall hardware tier.</p>
      <div class="score-pills">
        <span class="pill">🧠 RAM: {{ data.ram.total_gb }} GB</span>
        <span class="pill">🎮 VRAM: {{ data.best_vram }} GB</span>
        <span class="pill">⚡ CUDA: {{ "Yes" if data.has_cuda else "No" }}</span>
        <span class="pill">✅ {{ data.runnable_count }} models compatible</span>
        <span class="pill">🚫 {{ data.total_count - data.runnable_count }} models out of reach</span>
      </div>
    </div>
  </div>
</section>

<!-- ── CPU ──────────────────────────────────────────────────────────────────── -->
<section id="cpu">
  <h2>🖥️ CPU — Processor</h2>
  <div class="grid grid-2">
    <div class="card">
      <div class="card-header">
        <span class="icon">🔲</span>
        <h3>{{ data.cpu.name }}</h3>
        <span class="vendor">{{ data.cpu.arch }}</span>
      </div>
      <div class="row"><span class="label">Physical Cores</span><span class="value">{{ data.cpu.cores_physical }}</span></div>
      <div class="row"><span class="label">Logical Threads</span><span class="value">{{ data.cpu.cores_logical }}</span></div>
      <div class="row"><span class="label">Base Frequency</span><span class="value">{{ "%.2f"|format(data.cpu.freq_base_mhz/1000) }} GHz</span></div>
      <div class="row"><span class="label">Max Boost</span><span class="value">{{ "%.2f"|format(data.cpu.freq_max_mhz/1000) }} GHz</span></div>
      <div class="row"><span class="label">AVX2 Support</span>
        <span class="value" style="color:{{ '#3fb950' if data.cpu.avx2 else '#d29922' }}">{{ "✔ Yes" if data.cpu.avx2 else "Not detected" }}</span></div>
    </div>
    <div class="card">
      <div class="card-header"><span class="icon">⏱️</span><h3>CPU Benchmark</h3></div>
      <div class="row"><span class="label">Single-core</span><span class="value" style="color:#58a6ff">{{ data.bench_single }}M ops/s</span></div>
      <div class="row"><span class="label">All-core ({{ data.cpu.cores_logical }} threads)</span><span class="value" style="color:#58a6ff">{{ data.bench_multi }}M ops/s</span></div>
      <div class="row"><span class="label">Architecture</span><span class="value">{{ data.cpu.arch }} ({{ data.cpu.bits }}-bit)</span></div>
      <div style="margin-top:1rem">
        <div style="font-size:.75rem;color:var(--muted);margin-bottom:.4rem">Single-core performance</div>
        <div class="bar-wrap">
          <div class="bar-bg"><div class="bar-fill" style="width:{{ [data.bench_single/15*100,100]|min }}%;background:#58a6ff"></div></div>
          <span class="bar-label">{{ data.bench_single }}M/s</span>
        </div>
      </div>
    </div>
  </div>
</section>

<!-- ── RAM ──────────────────────────────────────────────────────────────────── -->
<section id="ram">
  <h2>💾 RAM — System Memory</h2>
  <div class="card">
    <div class="card-header">
      <span class="icon">🧩</span>
      <h3>{{ data.ram.total_gb }} GB {{ data.ram.type }}</h3>
      {% if data.ram.speed_mhz %}<span class="vendor">{{ data.ram.speed_mhz }} MHz</span>{% endif %}
    </div>
    <div class="row">
      <span class="label">Total Installed</span>
      <span class="value">{{ data.ram.total_gb }} GB</span>
    </div>
    <div class="row">
      <span class="label">Currently Used</span>
      <span class="value" style="color:{{ '#f85149' if data.ram.percent>85 else '#d29922' if data.ram.percent>60 else '#3fb950' }}">
        {{ data.ram.used_gb }} GB ({{ data.ram.percent }}%)
      </span>
    </div>
    <div class="row">
      <span class="label">Available Free</span>
      <span class="value" style="color:#3fb950">{{ data.ram.available_gb }} GB</span>
    </div>
    {% if data.ram.channels %}<div class="row"><span class="label">Memory Modules</span><span class="value">{{ data.ram.channels }} slots used</span></div>{% endif %}
    {% if data.ram.type != "Unknown" %}<div class="row"><span class="label">Memory Type</span><span class="value">{{ data.ram.type }}</span></div>{% endif %}
    <div style="margin-top:1rem">
      <div style="font-size:.75rem;color:var(--muted);margin-bottom:.4rem">Memory Usage: {{ data.ram.used_gb }} / {{ data.ram.total_gb }} GB</div>
      <div class="bar-wrap">
        <div class="bar-bg"><div class="bar-fill" style="width:{{ data.ram.percent }}%;background:{{ '#f85149' if data.ram.percent>85 else '#d29922' if data.ram.percent>60 else '#3fb950' }}"></div></div>
        <span class="bar-label">{{ data.ram.percent }}%</span>
      </div>
    </div>
  </div>
</section>

<!-- ── GPU ──────────────────────────────────────────────────────────────────── -->
<section id="gpu">
  <h2>🎮 GPU — Graphics & AI Accelerator</h2>
  <div class="grid grid-2">
    {% for gpu in data.gpus %}
    {% set match = data.gpu_matches[loop.index0] %}
    <div class="card">
      <div class="card-header">
        <span class="icon">{{ "🟢" if gpu.cuda else "⚪" }}</span>
        <h3>{{ gpu.name }}</h3>
        <span class="vendor">{{ gpu.vendor }}</span>
      </div>
      <div class="row"><span class="label">VRAM Total</span>
        <span class="value" style="font-size:.95rem;font-weight:700">{{ gpu.vram_gb }} GB</span></div>
      {% if gpu.vram_used_gb > 0 %}
      <div class="row"><span class="label">VRAM Used</span><span class="value">{{ gpu.vram_used_gb }} GB</span></div>
      {% endif %}
      <div class="row"><span class="label">CUDA Available</span>
        <span class="value" style="color:{{ '#3fb950' if gpu.cuda else '#8b949e' }}">{{ "✔ Yes" if gpu.cuda else "✗ No" }}</span></div>
      {% if gpu.driver and gpu.driver != "N/A" %}<div class="row"><span class="label">Driver</span><span class="value">{{ gpu.driver }}</span></div>{% endif %}
      {% if gpu.temp_c is not none %}<div class="row"><span class="label">Temperature</span>
        <span class="value" style="color:{{ '#f85149' if gpu.temp_c>85 else '#d29922' if gpu.temp_c>70 else '#3fb950' }}">{{ gpu.temp_c }}°C</span></div>{% endif %}
      {% if gpu.load_pct is not none %}<div class="row"><span class="label">GPU Load</span><span class="value">{{ gpu.load_pct }}%</span></div>{% endif %}
      {% if match %}
      <div style="margin-top:.75rem;padding-top:.75rem;border-top:1px solid var(--border)">
        <div class="row"><span class="label">Performance Tier</span>
          <span class="value tier-{{ match.tier }}" style="font-weight:800;font-size:1.05rem">{{ match.tier }}</span></div>
        <div class="row"><span class="label">AI Compute Score</span><span class="value">{{ match.score }} / 120</span></div>
        <div class="row"><span class="label">SD Image Gen FPS</span><span class="value">~{{ match.sd_fps }} fps <span style="color:var(--muted);font-size:.7rem">(512px SD1.5)</span></span></div>
        <div class="row"><span class="label">LLM Tokens/sec</span><span class="value">~{{ match.tok_s }} tok/s <span style="color:var(--muted);font-size:.7rem">(7B Q4)</span></span></div>
        <div style="margin-top:.75rem">
          <div style="font-size:.75rem;color:var(--muted);margin-bottom:.4rem">AI Score vs max (120)</div>
          <div class="bar-wrap">
            <div class="bar-bg"><div class="bar-fill" style="width:{{ match.score/120*100 }}%;background:#bc8cff"></div></div>
            <span class="bar-label">{{ match.score }}/120</span>
          </div>
        </div>
      </div>
      {% endif %}
      {% if gpu.vram_gb > 0 %}
      <div style="margin-top:.6rem">
        <div style="font-size:.75rem;color:var(--muted);margin-bottom:.4rem">VRAM Usage: {{ gpu.vram_used_gb }} / {{ gpu.vram_gb }} GB</div>
        <div class="bar-wrap">
          <div class="bar-bg"><div class="bar-fill" style="width:{{ (gpu.vram_used_gb/gpu.vram_gb*100) if gpu.vram_gb>0 else 0 }}%;background:#bc8cff"></div></div>
          <span class="bar-label">{{ "%.0f"|format(gpu.vram_used_gb/gpu.vram_gb*100) if gpu.vram_gb>0 else 0 }}%</span>
        </div>
      </div>
      {% endif %}
    </div>
    {% endfor %}
  </div>
</section>

<!-- ── STORAGE ──────────────────────────────────────────────────────────────── -->
<section id="storage">
  <h2>💽 Storage — Disks</h2>
  <div class="grid grid-2">
    {% for d in data.disks %}
    <div class="card">
      <div class="card-header">
        <span class="icon">💿</span>
        <h3>{{ d.mountpoint }}</h3>
        <span class="vendor">{{ d.type }}</span>
      </div>
      <div class="row"><span class="label">Total Size</span><span class="value">{{ d.total_gb }} GB</span></div>
      <div class="row"><span class="label">Used</span><span class="value">{{ d.used_gb }} GB</span></div>
      <div class="row"><span class="label">Free Space</span>
        <span class="value" style="color:{{ '#f85149' if d.free_gb<20 else '#d29922' if d.free_gb<50 else '#3fb950' }}">{{ d.free_gb }} GB</span></div>
      <div style="margin-top:.75rem">
        <div class="bar-wrap">
          <div class="bar-bg"><div class="bar-fill" style="width:{{ d.percent }}%;background:{{ '#f85149' if d.percent>90 else '#d29922' if d.percent>75 else '#3fb950' }}"></div></div>
          <span class="bar-label">{{ d.percent }}% used</span>
        </div>
      </div>
    </div>
    {% endfor %}
  </div>
</section>

<!-- ── OS ───────────────────────────────────────────────────────────────────── -->
<section id="os">
  <h2>🖥️ System — OS & Software Stack</h2>
  <div class="card" style="max-width:600px">
    <div class="card-header"><span class="icon">🪟</span><h3>{{ data.os.name }}</h3></div>
    {% if data.os.build %}<div class="row"><span class="label">Build</span><span class="value">{{ data.os.build }}</span></div>{% endif %}
    <div class="row"><span class="label">DirectX</span><span class="value">{{ data.os.directx }}</span></div>
    <div class="row"><span class="label">CUDA Toolkit</span>
      <span class="value" style="color:{{ '#3fb950' if data.os.cuda_version != 'Not installed' else '#f85149' }}">
        {{ data.os.cuda_version }}
        {% if data.os.cuda_version == "Not installed" %}
        — <a href="https://developer.nvidia.com/cuda-downloads" target="_blank">Install CUDA</a>
        {% endif %}
      </span></div>
    <div class="row"><span class="label">Python Version</span><span class="value">{{ data.os.python }}</span></div>
  </div>
</section>

<!-- ── MODELS ───────────────────────────────────────────────────────────────── -->
<section id="models">
  <h2>🤖 Local AI Model Compatibility</h2>
  <div class="cat-tabs">
    <button class="tab-btn active" onclick="filterCat('all',this)">All ({{ data.runnable_count }})</button>
    {% for cat in data.categories %}
    <button class="tab-btn" onclick="filterCat('{{ cat|replace(' ','_')|replace('/','_') }}',this)">{{ cat }}</button>
    {% endfor %}
    <button class="tab-btn" onclick="filterCat('no',this)" style="color:var(--red)">Not compatible</button>
  </div>
  <div class="model-grid">
    {% for m in data.models %}
    <div class="model-card status-{{ m.status }}" data-cat="{{ m.category|replace(' ','_')|replace('/','_') }}" data-status="{{ m.status }}">
      <div class="model-top">
        <span class="model-name">{{ m.name }}</span>
        <span class="status-badge badge-{{ m.status }}">
          {{ "✨ Excellent" if m.status=="excellent" else "✅ Good" if m.status=="good" else "🐢 CPU Only" if m.status=="cpu_only" else "⚠️ Limited" if m.status=="limited" else "❌ No" }}
        </span>
      </div>
      <div class="model-desc">{{ m.description }}</div>
      <div class="model-meta">
        <span class="meta-chip">{{ m.model_size_gb }} GB</span>
        <span class="stars">{{ "★" * m.quality }}{{ "☆" * (5-m.quality) }}</span>
        {% for tag in m.tags[:3] %}<tag>{{ tag }}</tag>{% endfor %}
        {% for p in m.platforms[:2] %}<span class="meta-chip">{{ p }}</span>{% endfor %}
      </div>
      <div style="font-size:.73rem;color:var(--muted);margin-top:.5rem">{{ m.note }}</div>
      {% if m.ollama %}
      <div class="ollama-cmd">
        <code>{{ m.ollama }}</code>
        <button class="copy-btn" onclick="copyCmd('{{ m.ollama }}',this)" title="Copy">📋</button>
      </div>
      {% endif %}
    </div>
    {% endfor %}
  </div>
</section>

<!-- ── QUICK START ──────────────────────────────────────────────────────────── -->
<section id="quickstart">
  <h2>🚀 Quick Start — Top Ollama Commands</h2>
  <p style="color:var(--muted);font-size:.82rem;margin-bottom:1rem">
    First install Ollama from <a href="https://ollama.com/download" target="_blank">ollama.com/download</a>, then run these:
  </p>
  <ul class="qs-list">
    {% for m in data.quickstart %}
    <li class="qs-item">
      <span class="qs-num">{{ loop.index }}</span>
      <span class="qs-name">{{ m.name }}</span>
      <code class="qs-cmd">{{ m.ollama }}</code>
      <button class="copy-btn" onclick="copyCmd('{{ m.ollama }}',this)" title="Copy">📋</button>
    </li>
    {% endfor %}
  </ul>
</section>

<!-- ── GUIDES ───────────────────────────────────────────────────────────────── -->
<section id="guides">
  <h2>📦 Installation Guides</h2>
  {% for pname, p in data.guides.items() %}
  <div class="guide-card">
    <div class="guide-head" onclick="toggleGuide(this)">
      <div>
        <div class="guide-title">{{ pname }}</div>
        <div class="guide-desc">{{ p.desc }}</div>
      </div>
      <span style="color:var(--muted);font-size:1.2rem;transition:transform .3s">▸</span>
    </div>
    <div class="guide-body">
      {% for step in p.steps %}
      <div class="step">
        <span class="step-num">{{ loop.index }}</span>
        <span class="step-text">{{ step }}</span>
      </div>
      {% endfor %}
      <div style="margin-top:.75rem">
        <a href="{{ p.url }}" target="_blank" style="font-size:.8rem">🔗 {{ p.url }}</a>
      </div>
    </div>
  </div>
  {% endfor %}
</section>

<!-- ── UPGRADES ─────────────────────────────────────────────────────────────── -->
{% if data.upgrade_tips %}
<section id="upgrades">
  <h2>⬆️ Upgrade Recommendations</h2>
  {% for tip in data.upgrade_tips %}
  <div class="tip-card">
    <div class="tip-title">{{ tip.title }}</div>
    <div class="tip-body">{{ tip.body }}</div>
  </div>
  {% endfor %}
</section>
{% endif %}

<!-- ── API vs LOCAL COMPARISON ──────────────────────────────────────────────── -->
<section id="compare">
  <h2>⚡ API vs Local AI — Speed, Cost & Feature Comparison</h2>
  <p style="color:var(--muted);font-size:.82rem;margin-bottom:1.25rem">
    How your PC compares to cloud AI APIs for tokens/sec, latency, cost and privacy.
    Local metrics are calculated from your detected hardware.
  </p>

  <!-- Finance summary cards -->
  <div class="finance-grid">
    <div class="fin-card">
      <div class="fin-val" style="color:#3fb950">~{{ data.compare.local_tok_s_gpu }} tok/s</div>
      <div class="fin-label">Your GPU Speed (7B Q4 model)</div>
      <div class="fin-sub">{{ data.gpus[0].name if data.gpus else 'N/A' }}</div>
    </div>
    <div class="fin-card">
      <div class="fin-val" style="color:#d29922">~{{ data.compare.local_tok_s_cpu }} tok/s</div>
      <div class="fin-label">Your CPU Speed (fallback)</div>
      <div class="fin-sub">{{ data.cpu.cores_physical }}-core inference</div>
    </div>
    <div class="fin-card">
      <div class="fin-val" style="color:#58a6ff">$0</div>
      <div class="fin-label">Cost per Token (Local)</div>
      <div class="fin-sub">Free forever after hardware</div>
    </div>
    <div class="fin-card">
      <div class="fin-val" style="color:#f0883e">${{ data.compare.elec_cost_monthly }}</div>
      <div class="fin-label">Est. Electricity / Month</div>
      <div class="fin-sub">{{ data.compare.gpu_tdp_watts }}W GPU × 8h/day × $0.12/kWh</div>
    </div>
    <div class="fin-card">
      <div class="fin-val" style="color:#bc8cff">{{ data.compare.local_latency_ms }}ms</div>
      <div class="fin-label">Your First-Token Latency</div>
      <div class="fin-sub">{{ "GPU inference (CUDA)" if data.has_cuda else "CPU inference" }}</div>
    </div>
    {% if data.compare.breakeven_tokens %}
    <div class="fin-card">
      <div class="fin-val" style="color:#39d353">{{ "{:,}".format(data.compare.breakeven_tokens) }}</div>
      <div class="fin-label">Break-even Tokens/Month</div>
      <div class="fin-sub">vs {{ data.compare.cheapest_api.name }} {{ data.compare.cheapest_api.model }}</div>
    </div>
    {% endif %}
  </div>

  <!-- Tab switcher -->
  <div class="cmp-tabs">
    <button class="cmp-tab active" onclick="showCmp('speed',this)">🚀 Speed (tok/s)</button>
    <button class="cmp-tab" onclick="showCmp('latency',this)">⏱️ Latency</button>
    <button class="cmp-tab" onclick="showCmp('cost',this)">💰 Cost Table</button>
    <button class="cmp-tab" onclick="showCmp('features',this)">🔒 Features</button>
  </div>

  <!-- SPEED panel -->
  <div class="cmp-panel active" id="cmp-speed">
    <div style="color:var(--muted);font-size:.75rem;margin-bottom:.9rem">
      Tokens per second for a 7B Q4 model. Higher = faster output generation.
    </div>
    {% for row in data.compare.speed_rows %}
    {% if row.tok_s > 0 %}
    <div class="speed-row {{ 'local-row' if (row.is_local and row.is_gpu) else 'cpu-row' if (row.is_local and not row.is_gpu) else '' }}">
      <span class="speed-label">
        {% if row.is_local %}<span style="font-size:.65rem;background:{{ '#3fb95022' if row.is_gpu else '#d2992222' }};border:1px solid {{ '#3fb95044' if row.is_gpu else '#d2992244' }};border-radius:8px;padding:.1rem .4rem;margin-right:.3rem">{{ 'YOUR PC' }}</span>{% endif %}
        {{ row.label }}
      </span>
      <div class="speed-bar-wrap">
        <div class="speed-bar-bg">
          <div class="speed-bar-fill" style="width:{{ [row.tok_s/data.compare.max_tok*100,100]|min }}%;background:{{ row.color }}">{{ row.tok_s }}</div>
        </div>
        <span class="speed-val">{{ row.tok_s }} t/s</span>
      </div>
    </div>
    {% endif %}
    {% endfor %}
  </div>

  <!-- LATENCY panel -->
  <div class="cmp-panel" id="cmp-latency">
    <div style="color:var(--muted);font-size:.75rem;margin-bottom:.9rem">
      Time to first token (ms). Lower = faster response start. Sorted fastest first.
    </div>
    {% for row in data.compare.latency_rows %}
    <div class="lat-row {{ 'local-row' if row.is_local else '' }}">
      <span class="lat-provider" style="color:{{ row.color }}">{{ row.provider }}</span>
      <span class="lat-label">
        {{ row.label }}
        {% if loop.first %}<span class="winner-badge">🏆 fastest</span>{% endif %}
      </span>
      <div class="speed-bar-wrap">
        <div class="speed-bar-bg">
          <div class="speed-bar-fill" style="width:{{ [row.ms/data.compare.max_lat*100,100]|min }}%;background:{{ row.color }}">{{ row.ms }}ms</div>
        </div>
        <span class="speed-val">{{ row.ms }}ms</span>
      </div>
    </div>
    {% endfor %}
  </div>

  <!-- COST panel -->
  <div class="cmp-panel" id="cmp-cost">
    <div style="color:var(--muted);font-size:.75rem;margin-bottom:.9rem">
      Pricing per 1M tokens (April 2026). Monthly estimate = 2M input + 1M output tokens/month (typical developer usage).
    </div>
    <div style="overflow-x:auto">
    <table class="cmp-table">
      <thead>
        <tr>
          <th>Provider</th><th>Model</th><th>Input /1M</th><th>Output /1M</th>
          <th>Est. Monthly</th><th>Speed</th><th>Quality</th>
        </tr>
      </thead>
      <tbody>
        <!-- Your local PC row first -->
        <tr class="local-highlight">
          <td><span class="provider-dot" style="background:#3fb950"></span><strong>YOUR PC</strong></td>
          <td>{{ data.gpus[0].name if data.gpus else 'Local' }} (any model)</td>
          <td class="cost-free">$0.00</td>
          <td class="cost-free">$0.00</td>
          <td class="cost-free">${{ data.compare.elec_cost_monthly }}<span style="font-size:.65rem;color:var(--muted)"> elec.</span></td>
          <td style="color:#3fb950">~{{ data.compare.local_tok_s_gpu if data.has_cuda else data.compare.local_tok_s_cpu }} t/s</td>
          <td>{{ "★★★★☆" if data.score >= 40 else "★★★☆☆" }}</td>
        </tr>
        {% for p in data.compare.providers %}
        <tr>
          <td><span class="provider-dot" style="background:{{ p.color }}"></span>{{ p.name }}</td>
          <td><span style="color:var(--text)">{{ p.model }}</span></td>
          <td class="{{ 'cost-free' if p.price_in==0 else 'cost-green' if p.price_in<0.5 else 'cost-yellow' if p.price_in<2 else 'cost-red' }}">
            {{ '$0 free' if p.price_in==0 else '$%.2f'|format(p.price_in) }}
          </td>
          <td class="{{ 'cost-free' if p.price_out==0 else 'cost-green' if p.price_out<1 else 'cost-yellow' if p.price_out<5 else 'cost-red' }}">
            {{ '$0 free' if p.price_out==0 else '$%.2f'|format(p.price_out) }}
          </td>
          <td class="{{ 'cost-free' if p.monthly_cost==0 else 'cost-green' if p.monthly_cost<5 else 'cost-yellow' if p.monthly_cost<20 else 'cost-red' }}">
            {{ '$0' if p.monthly_cost==0 else '$%.2f'|format(p.monthly_cost) }}
          </td>
          <td>{{ p.tok_s }} t/s</td>
          <td>{{ '★' * p.quality }}{{ '☆' * (5-p.quality) }}</td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
    </div>
  </div>

  <!-- FEATURES panel -->
  <div class="cmp-panel" id="cmp-features">
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:1.5rem;margin-bottom:1rem">
      <div>
        <div style="color:#3fb950;font-weight:700;margin-bottom:.75rem;font-size:.9rem">✅ Local AI Advantages</div>
        <div style="display:flex;flex-direction:column;gap:.4rem">
          {% for f in data.compare.features %}
          {% if f.local %}
          <div class="feat-row feat-local">
            <span class="feat-check">✅</span>
            <span class="feat-name">{{ f.name }}</span>
          </div>
          {% endif %}
          {% endfor %}
        </div>
      </div>
      <div>
        <div style="color:#58a6ff;font-weight:700;margin-bottom:.75rem;font-size:.9rem">✅ API / Cloud Advantages</div>
        <div style="display:flex;flex-direction:column;gap:.4rem">
          {% for f in data.compare.features %}
          {% if f.api and not f.local %}
          <div class="feat-row feat-api">
            <span class="feat-check">✅</span>
            <span class="feat-name">{{ f.name }}</span>
          </div>
          {% endif %}
          {% endfor %}
        </div>
      </div>
    </div>
    <div style="background:var(--bg2);border:1px solid var(--border);border-radius:10px;padding:1.1rem;margin-top:.5rem">
      <div style="font-weight:600;margin-bottom:.5rem">💡 Recommendation for your system (Score: {{ data.score }}/100)</div>
      <p style="font-size:.83rem;color:var(--muted);line-height:1.7">
        {% if data.score >= 75 %}
          Your PC is <strong style="color:#3fb950">well-suited for local AI</strong>. Run 7B–13B models locally via Ollama or LM Studio.
          Use APIs only for frontier tasks (GPT-4o / Claude 3.5) where quality matters most.
        {% elif data.score >= 45 %}
          Your PC can <strong style="color:#d29922">handle local AI for everyday use</strong> — 7B models run well.
          For complex reasoning or multimodal tasks, supplement with a cheap API like Gemini Flash or GPT-4o mini.
        {% else %}
          Your PC is <strong style="color:#f0883e">better suited for small local models</strong> (Phi-3, TinyLlama).
          For serious AI work, use cloud APIs (Gemini Flash is nearly free) while saving for a GPU upgrade.
        {% endif %}
      </p>
    </div>
  </div>

</section>

</div><!-- /container -->

<footer>
  AI PC Suitability Checker v2.0 &nbsp;·&nbsp; Scanned {{ data.scanned_at }}
  &nbsp;·&nbsp; Serving on <strong>http://localhost:{{ data.port }}</strong>
  &nbsp;·&nbsp; <span style="color:#3fb950">●</span> Running
</footer>

<script>
// Nav highlight on scroll
const sections = document.querySelectorAll('section[id]');
const navLinks  = document.querySelectorAll('nav a');
window.addEventListener('scroll',()=>{
  let cur='';
  sections.forEach(s=>{ if(window.scrollY>=s.offsetTop-80) cur=s.id; });
  navLinks.forEach(a=>{ a.classList.toggle('active',a.getAttribute('href')==='#'+cur); });
},{passive:true});

// Animate gauge on load
window.addEventListener('DOMContentLoaded',()=>{
  const fill = document.getElementById('gaugeFill');
  if(fill){
    const score = {{ data.score }};
    const circ  = 2*Math.PI*38;
    fill.style.strokeDasharray = '0 999';
    setTimeout(()=>{ fill.style.strokeDasharray = (circ*score/100).toFixed(1)+' 999'; },150);
  }
});

// Category filter
function filterCat(cat,btn){
  document.querySelectorAll('.tab-btn').forEach(b=>b.classList.remove('active'));
  btn.classList.add('active');
  document.querySelectorAll('.model-card').forEach(card=>{
    if(cat==='all')      card.classList.toggle('hidden', card.dataset.status==='no');
    else if(cat==='no')  card.classList.toggle('hidden', card.dataset.status!=='no');
    else                 card.classList.toggle('hidden', card.dataset.cat!==cat);
  });
}

// Copy command
function copyCmd(cmd,btn){
  navigator.clipboard.writeText(cmd).then(()=>{
    const orig=btn.textContent; btn.textContent='✅'; btn.style.color='#3fb950';
    setTimeout(()=>{ btn.textContent=orig; btn.style.color=''; },1500);
  });
}

// Toggle install guide
function toggleGuide(head){
  const body = head.nextElementSibling;
  const arrow = head.querySelector('span:last-child');
  body.classList.toggle('open');
  arrow.style.transform = body.classList.contains('open') ? 'rotate(90deg)' : '';
}

// Comparison tab switcher
function showCmp(panel, btn){
  document.querySelectorAll('.cmp-tab').forEach(b=>b.classList.remove('active'));
  document.querySelectorAll('.cmp-panel').forEach(p=>p.classList.remove('active'));
  btn.classList.add('active');
  document.getElementById('cmp-'+panel).classList.add('active');
}
</script>
</body>
</html>
"""

# ─── Flask app ────────────────────────────────────────────────────────────────
app = Flask(__name__)
_data_cache: Dict = {}

@app.route("/")
def index():
    return render_template_string(HTML, data=_data_cache)

@app.route("/api/data")
def api_data():
    return json.dumps(_data_cache, default=str)

# ─── Collect all data ────────────────────────────────────────────────────────
def collect(port: int) -> Dict:
    print("  Scanning CPU …", end=" ", flush=True)
    cpu = get_cpu_info(); print("✓")
    print("  Scanning RAM …", end=" ", flush=True)
    ram = get_ram_info(); print("✓")
    print("  Scanning GPU …", end=" ", flush=True)
    gpus = get_gpu_info(); print("✓")
    print("  Scanning disks …", end=" ", flush=True)
    disks = get_disk_info(); print("✓")
    print("  Scanning OS …", end=" ", flush=True)
    os_info = get_os_info(); print("✓")
    print("  Running CPU benchmark …", end=" ", flush=True)
    bench_single, bench_multi = cpu_benchmark(); print("✓")

    gpu_matches = [match_gpu(g["name"]) for g in gpus]
    best_vram   = max((g["vram_gb"] for g in gpus), default=0)
    has_cuda    = any(g["cuda"] for g in gpus)
    results     = check_compatibility(ram["total_gb"], best_vram, has_cuda)
    score, rating = compute_score(cpu, ram, gpus, gpu_matches[0] if gpu_matches else None)

    score_color = "#3fb950" if score>=75 else "#d29922" if score>=45 else "#f0883e" if score>=25 else "#f85149"

    # Quick-start: top 5 with ollama command
    quickstart = [r for r in results if r["status"] in ("excellent","good") and r.get("ollama")][:5]
    if not quickstart:
        quickstart = [r for r in results if r.get("ollama")][:5]

    # Guides — only for platforms the user can actually run
    needed_platforms = set()
    for r in results:
        if r["status"] in ("excellent","good","cpu_only"):
            needed_platforms.update(r.get("platforms", []))
    guides = {k: v for k,v in PLATFORMS.items() if k in needed_platforms}

    # Categories
    cats = list(dict.fromkeys(m["category"] for m in results if m["status"] != "no"))

    # Upgrade tips
    tips = []
    vram = best_vram
    if vram < 8:
        tips.append({"title":"🎯 Priority: GPU VRAM Upgrade",
                     "body":"Upgrade to a GPU with 8GB+ VRAM (e.g. RTX 3060 / RX 6600 XT). "
                            "This single change unlocks most 7B language models with GPU acceleration."})
    if vram < 16:
        tips.append({"title":"🎯 GPU: 16GB VRAM Tier",
                     "body":"16GB VRAM (RTX 3080 / RX 6800 XT) enables 13B+ models, Stable Diffusion XL, and FLUX.1."})
    if ram["total_gb"] < 16:
        tips.append({"title":"💾 RAM: Add More Memory",
                     "body":"16GB+ RAM allows comfortable CPU inference of 7B models and running multiple tools in parallel."})
    if ram["total_gb"] < 32:
        tips.append({"title":"💾 RAM: 32GB for Power Users",
                     "body":"32GB RAM enables larger quantized models, multiple AI tools simultaneously, and smooth multitasking."})
    if not has_cuda:
        tips.append({"title":"⚡ Consider an NVIDIA GPU",
                     "body":"NVIDIA GPUs with CUDA provide 10–30× faster AI inference vs CPU. "
                            "Even an RTX 3060 would massively improve your AI capabilities."})

    # Serialize gpu_matches (may contain None)
    gpu_matches_safe = [m if m else {} for m in gpu_matches]

    return {
        "scanned_at":   datetime.now().strftime("%Y-%m-%d  %H:%M:%S"),
        "port":         port,
        "cpu":          cpu,
        "ram":          ram,
        "gpus":         gpus,
        "gpu_matches":  gpu_matches_safe,
        "disks":        disks,
        "os":           os_info,
        "score":        score,
        "score_color":  score_color,
        "rating":       rating,
        "best_vram":    best_vram,
        "has_cuda":     has_cuda,
        "bench_single": bench_single,
        "bench_multi":  bench_multi,
        "models":       results,
        "runnable_count": len([r for r in results if r["status"] != "no"]),
        "total_count":  len(results),
        "quickstart":   quickstart,
        "guides":       guides,
        "categories":   cats,
        "upgrade_tips": tips,
        "compare":      build_comparison(gpu_matches[0] if gpu_matches else None, gpus, has_cuda, bench_multi),
    }

# ─── Main ─────────────────────────────────────────────────────────────────────
def main():
    print("\n" + "="*55)
    print("  AI PC SUITABILITY CHECKER  v2.0  —  Web Dashboard")
    print("="*55 + "\n")

    port = find_free_port()
    print(f"  Selected port: {port}\n")
    print("  Scanning hardware…")

    global _data_cache
    _data_cache = collect(port)

    url = f"http://localhost:{port}"
    print(f"\n  ✅ Scan complete!")
    print(f"  🌐 Dashboard URL: {url}")
    print(f"  📄 Opening in browser…\n")
    print("  Press Ctrl+C to stop the server.\n")
    print("="*55 + "\n")

    # Open browser after a short delay so Flask is ready
    def _open():
        time.sleep(1.2)
        webbrowser.open(url)
    threading.Thread(target=_open, daemon=True).start()

    # Suppress Flask's noisy startup log
    import logging
    log = logging.getLogger("werkzeug")
    log.setLevel(logging.WARNING)

    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

if __name__ == "__main__":
    main()
