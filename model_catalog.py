#!/usr/bin/env python3

import html as html_lib
import json
import math
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.request import Request, urlopen


CATALOG_URL = "https://ollama.com/library"
CATALOG_TAGS_URL = "https://ollama.com/api/tags"
USER_AGENT = "ai-pc-checker/2.0"
CACHE_TTL_SECONDS = 12 * 3600

_CARD_RE = re.compile(r"<li x-test-model\b.*?</li>", re.S)
_STATUS_ORDER = {"excellent": 0, "good": 1, "cpu_only": 2, "limited": 3, "no": 4}
_APPLE_MEMORY_TIERS = [8, 16, 18, 24, 32, 36, 48, 64, 96, 128, 192, 256]
_RUNNABLE_RANK = {"excellent": 0, "good": 0, "cpu_only": 1, "limited": 2}


def _cache_dir() -> Path:
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Caches" / "ai-pc-checker"
    if os.name == "nt":
        base = Path(os.getenv("LOCALAPPDATA", str(Path.home() / "AppData" / "Local")))
        return base / "ai-pc-checker"
    return Path.home() / ".cache" / "ai-pc-checker"


def _cache_path() -> Path:
    return _cache_dir() / "ollama-library-cache.json"


def _fetch_text(url: str, timeout: int = 20) -> str:
    req = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(req, timeout=timeout) as response:
        return response.read().decode("utf-8", "ignore")


def _strip_tags(value: str) -> str:
    return re.sub(r"<[^>]+>", "", value)


def _clean_text(value: str) -> str:
    return html_lib.unescape(_strip_tags(value)).replace("\xa0", " ").strip()


def _extract(pattern: str, text: str) -> str:
    match = re.search(pattern, text, re.S)
    return _clean_text(match.group(1)) if match else ""


def _dedupe_keep_order(values: List[str]) -> List[str]:
    seen = set()
    ordered = []
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered


def _parse_count(value: str) -> float:
    text = (value or "").strip().lower().replace(",", "")
    if not text:
        return 0.0
    mult = 1.0
    if text.endswith("k"):
        mult = 1_000.0
        text = text[:-1]
    elif text.endswith("m"):
        mult = 1_000_000.0
        text = text[:-1]
    elif text.endswith("b"):
        mult = 1_000_000_000.0
        text = text[:-1]
    try:
        return float(text) * mult
    except ValueError:
        return 0.0


def _parse_api_families(payload: str) -> Dict[str, Dict[str, Any]]:
    families: Dict[str, Dict[str, Any]] = {}
    try:
        data = json.loads(payload)
    except Exception:
        return families

    for model in data.get("models", []):
        full_name = (model.get("name") or "").strip()
        if not full_name:
            continue

        slug, _, size_label = full_name.partition(":")
        size_label = size_label.strip() or None
        family = families.setdefault(
            slug,
            {
                "slug": slug,
                "description": slug,
                "capabilities": [],
                "sizes": [],
                "pulls": 0.0,
                "pulls_text": "",
                "tag_count": 0,
                "updated": "",
                "api_variants": {},
            },
        )

        size_gb = round((model.get("size") or 0) / (1024 ** 3), 1)
        family["api_variants"][size_label or "latest"] = size_gb
        if size_label and size_label not in family["sizes"]:
            family["sizes"].append(size_label)
        if model.get("modified_at"):
            family["updated"] = str(model["modified_at"])

    return families


def _parse_library_html(html_text: str) -> List[Dict[str, Any]]:
    families = []
    for card in _CARD_RE.findall(html_text):
        slug = _extract(r'href="/library/([^"]+)"', card)
        if not slug:
            continue

        families.append(
            {
                "slug": slug,
                "description": _extract(r'<p class="max-w-lg[^>]*>(.*?)</p>', card),
                "capabilities": _dedupe_keep_order(
                    [_clean_text(item) for item in re.findall(r'<span x-test-capability[^>]*>(.*?)</span>', card, re.S)]
                ),
                "sizes": _dedupe_keep_order(
                    [_clean_text(item) for item in re.findall(r'<span x-test-size[^>]*>(.*?)</span>', card, re.S)]
                ),
                "pulls_text": _extract(r'<span x-test-pull-count>(.*?)</span>', card),
                "pulls": _parse_count(_extract(r'<span x-test-pull-count>(.*?)</span>', card)),
                "tag_count": int(_extract(r'<span x-test-tag-count>(.*?)</span>', card) or 0),
                "updated": _extract(r'<span x-test-updated>(.*?)</span>', card),
                "api_variants": {},
            }
        )
    return families


def _merge_catalogs(library_families: List[Dict[str, Any]], api_families: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    merged = []
    seen = set()

    for family in library_families:
        api_family = api_families.get(family["slug"])
        if api_family:
            merged_sizes = family["sizes"][:]
            for size in api_family.get("sizes", []):
                if size not in merged_sizes:
                    merged_sizes.append(size)
            family["sizes"] = merged_sizes
            family["api_variants"] = api_family.get("api_variants", {})
            if not family.get("updated"):
                family["updated"] = api_family.get("updated", "")
        merged.append(family)
        seen.add(family["slug"])

    for slug, api_family in api_families.items():
        if slug in seen:
            continue
        merged.append(api_family)

    return merged


def _load_cache() -> Optional[Dict[str, Any]]:
    path = _cache_path()
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text())
    except Exception:
        return None
    if time.time() - payload.get("fetched_at", 0) > CACHE_TTL_SECONDS:
        return None
    return payload


def _write_cache(families: List[Dict[str, Any]], source: str) -> None:
    path = _cache_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "fetched_at": time.time(),
        "source": source,
        "families": families,
    }
    path.write_text(json.dumps(payload))


def get_live_ollama_catalog() -> Dict[str, Any]:
    cached = _load_cache()

    library_families: List[Dict[str, Any]] = []
    api_families: Dict[str, Dict[str, Any]] = {}

    try:
        library_families = _parse_library_html(_fetch_text(CATALOG_URL))
    except Exception:
        library_families = []

    try:
        api_families = _parse_api_families(_fetch_text(CATALOG_TAGS_URL))
    except Exception:
        api_families = {}

    merged = _merge_catalogs(library_families, api_families) if (library_families or api_families) else []
    if merged:
        _write_cache(merged, "live")
        return {
            "families": merged,
            "family_count": len(merged),
            "source": "live",
            "source_label": "live from Ollama Library",
        }

    if cached:
        families = cached.get("families", [])
        return {
            "families": families,
            "family_count": len(families),
            "source": "cache",
            "source_label": "cached from Ollama Library",
        }

    return {
        "families": [],
        "family_count": 0,
        "source": "unavailable",
        "source_label": "catalog unavailable",
    }


def _parse_size_to_billions(size_label: Optional[str]) -> float:
    if not size_label:
        return 0.0

    token = size_label.strip().lower()
    if not token:
        return 0.0

    moe_match = re.match(r"^(\d+(?:\.\d+)?)x([a-z]?\d+(?:\.\d+)?)([mbt])$", token)
    if moe_match:
        count = float(moe_match.group(1))
        inner = moe_match.group(2)
        unit = moe_match.group(3)
        inner_value = _parse_size_to_billions(f"{inner}{unit}")
        return round(count * inner_value, 3)

    simple_match = re.search(r"(\d+(?:\.\d+)?)([mbt])$", token)
    if not simple_match:
        return 0.0

    value = float(simple_match.group(1))
    unit = simple_match.group(2)
    if unit == "m":
        return round(value / 1000.0, 3)
    if unit == "t":
        return round(value * 1000.0, 3)
    return round(value, 3)


def _infer_param_billions(family: Dict[str, Any], size_label: Optional[str], size_gb: float) -> float:
    parsed = _parse_size_to_billions(size_label)
    if parsed > 0:
        return parsed

    desc = (family.get("description") or "").lower()
    for match in re.findall(r"(?<![\w.])(\d+(?:\.\d+)?\s*[mbt])(?![a-z])", desc):
        parsed = _parse_size_to_billions(match.replace(" ", ""))
        if parsed > 0:
            return parsed

    if size_gb > 0:
        return round(size_gb / 0.58, 1)

    capabilities = {cap.lower() for cap in family.get("capabilities", [])}
    if "cloud" in capabilities:
        return 70.0
    return 7.0


def _classify_category(slug: str, description: str, capabilities: List[str]) -> str:
    slug_l = slug.lower()
    desc_l = description.lower()
    caps = {cap.lower() for cap in capabilities}

    code_slug_hits = (
        "coder", "codellama", "starcoder", "codegemma", "codestral", "codeqwen",
        "wizardcoder", "sqlcoder", "codegeex", "opencoder", "devstral", "granite-code",
        "deepcoder",
    )
    code_desc_hits = (
        "coding-focused", "coding model", "coding agents", "code generation",
        "code reasoning", "code fixing", "code completion", "software engineering",
        "developer use cases", "coding workflows", "code intelligence",
    )
    if any(hit in slug_l for hit in code_slug_hits) or any(hit in desc_l for hit in code_desc_hits):
        return "Code Generation"

    if "vision" in caps or any(hit in slug_l for hit in ("llava", "-vl", "ocr", "moondream", "bakllava", "minicpm-v")) or any(
        hit in desc_l for hit in ("multimodal", "vision-language", "image reasoning", "visual", "document understanding")
    ):
        return "Vision / Multimodal"

    if any(hit in slug_l for hit in ("embed", "embedding", "minilm", "rerank", "bge")) or "embedding" in desc_l:
        return "Embeddings / RAG"

    if "audio" in caps or any(hit in slug_l for hit in ("whisper", "tts", "speech")) or any(
        hit in desc_l for hit in ("speech", "transcription", "audio")
    ):
        return "Speech-to-Text"

    if any(hit in slug_l for hit in ("diffusion", "flux")) or "image generation" in desc_l:
        return "Image Generation"

    return "Text / Chat"


def _estimate_model_size_gb(param_b: float, category: str, exact_size_gb: float) -> float:
    if exact_size_gb > 0:
        return exact_size_gb

    if param_b <= 0:
        return 0.0

    factor = 0.58
    if category == "Embeddings / RAG":
        factor = 0.38
    elif category == "Vision / Multimodal":
        factor = 0.62
    return round(max(0.1, param_b * factor), 1)


def _estimate_requirements(param_b: float, category: str, capabilities: List[str]) -> Dict[str, Any]:
    caps = {cap.lower() for cap in capabilities}

    if category == "Embeddings / RAG":
        min_vram = 0 if param_b <= 0.5 else max(1, math.ceil(param_b * 0.2))
        min_ram = 2 if param_b <= 0.5 else max(3, math.ceil(param_b * 0.5))
        return {"min_ram_gb": min_ram, "min_vram_gb": min_vram, "cpu_ok": True}

    if param_b <= 0.5:
        min_vram = 0 if category == "Speech-to-Text" else 1
    elif param_b <= 1.5:
        min_vram = 1
    elif param_b <= 4:
        min_vram = 2
    else:
        min_vram = max(2, math.ceil(param_b * 0.6))

    if category == "Vision / Multimodal":
        min_vram += 1
    if "thinking" in caps and param_b >= 14:
        min_vram += 1

    min_ram = max(4, math.ceil(max(param_b * 0.75, min_vram + 2)))
    if category == "Vision / Multimodal" and param_b >= 7:
        min_ram += 2

    cpu_ok = param_b <= 8 and category != "Vision / Multimodal"
    return {"min_ram_gb": min_ram, "min_vram_gb": min_vram, "cpu_ok": cpu_ok}


def _recency_bonus(updated_text: str) -> float:
    text = (updated_text or "").lower()
    if not text:
        return 0.0
    if "hour" in text or "day" in text or "week" in text:
        return 1.0
    if "month" in text:
        digits = re.search(r"(\d+)", text)
        if digits and int(digits.group(1)) <= 3:
            return 0.75
        return 0.5
    return 0.0


def _estimate_quality(param_b: float, category: str, capabilities: List[str], pulls: float, updated_text: str) -> int:
    score = 1.5
    if param_b >= 1:
        score += 0.5
    if param_b >= 7:
        score += 0.75
    if param_b >= 14:
        score += 0.5
    if param_b >= 30:
        score += 0.25
    if pulls >= 1_000_000:
        score += 0.5
    if pulls >= 10_000_000:
        score += 0.5
    score += _recency_bonus(updated_text)
    caps = {cap.lower() for cap in capabilities}
    if "thinking" in caps:
        score += 0.5
    if category == "Code Generation":
        score += 0.5
    if category == "Embeddings / RAG" and param_b < 1:
        score = max(score, 4.0)
    return max(1, min(5, round(score)))


def _annotate_variant(
    family: Dict[str, Any],
    category: str,
    size_label: Optional[str],
    ram_gb: float,
    vram_gb: float,
    has_gpu_accel: bool,
) -> Dict[str, Any]:
    exact_size_key = size_label or "latest"
    exact_size_gb = family.get("api_variants", {}).get(exact_size_key, 0.0)
    param_b = _infer_param_billions(family, size_label, exact_size_gb)
    model_size_gb = _estimate_model_size_gb(param_b, category, exact_size_gb)
    requirements = _estimate_requirements(param_b, category, family.get("capabilities", []))
    min_ram_gb = requirements["min_ram_gb"]
    min_vram_gb = requirements["min_vram_gb"]
    cpu_ok = requirements["cpu_ok"]

    if ram_gb >= min_ram_gb and vram_gb >= min_vram_gb and (has_gpu_accel or min_vram_gb == 0):
        status = "excellent" if ram_gb >= max(min_ram_gb * 1.5, min_ram_gb + 4) and vram_gb >= max(min_vram_gb * 1.5, min_vram_gb + 2) else "good"
        note = "Runs fast with headroom" if status == "excellent" else "Meets requirements"
    elif ram_gb >= min_ram_gb and cpu_ok:
        status = "cpu_only"
        note = "Will run on CPU, but slower than GPU/Metal acceleration"
    elif ram_gb >= min_ram_gb * 0.85 and vram_gb >= min_vram_gb * 0.85:
        status = "limited"
        note = "Close to the requirement line; smaller variants are safer"
    else:
        status = "no"
        note = f"Needs {min_ram_gb}GB RAM and {min_vram_gb}GB VRAM"

    command = f"ollama run {family['slug']}:{size_label}" if size_label else f"ollama run {family['slug']}"
    return {
        "size_label": size_label or "latest",
        "param_b": param_b,
        "model_size_gb": model_size_gb,
        "min_ram_gb": min_ram_gb,
        "min_vram_gb": min_vram_gb,
        "cpu_ok": cpu_ok,
        "status": status,
        "note": note,
        "ollama": command,
    }


def build_live_catalog_results(
    catalog: Dict[str, Any],
    ram_gb: float,
    vram_gb: float,
    has_gpu_accel: bool,
) -> List[Dict[str, Any]]:
    results = []
    for family in catalog.get("families", []):
        category = _classify_category(family["slug"], family.get("description", ""), family.get("capabilities", []))
        size_labels = family.get("sizes") or [None]
        variants = [
            _annotate_variant(family, category, size_label, ram_gb, vram_gb, has_gpu_accel)
            for size_label in size_labels
        ]

        runnable = [variant for variant in variants if variant["status"] != "no"]
        if runnable:
            selected = sorted(
                runnable,
                key=lambda item: (_RUNNABLE_RANK[item["status"]], -item["param_b"], item["min_vram_gb"], item["min_ram_gb"]),
            )[0]
        else:
            selected = sorted(
                variants,
                key=lambda item: (item["min_vram_gb"], item["min_ram_gb"], item["param_b"]),
            )[0]

        larger_unavailable = [
            variant for variant in variants
            if variant["param_b"] > selected["param_b"] and variant["status"] in {"limited", "no"}
        ]
        next_variant = sorted(larger_unavailable, key=lambda item: (item["min_vram_gb"], item["min_ram_gb"], item["param_b"]))[0] if larger_unavailable else None

        if selected["status"] == "no":
            family_note = f"Smallest practical size is {selected['size_label']} and needs {selected['min_ram_gb']}GB RAM / {selected['min_vram_gb']}GB VRAM"
        else:
            size_list = ", ".join(family.get("sizes", [])[:6]) if family.get("sizes") else "latest"
            family_note = f"Best fit size: {selected['size_label']} · Available sizes: {size_list}"
            if next_variant:
                family_note += f" · Next jump: {next_variant['size_label']} needs {next_variant['min_ram_gb']}GB RAM / {next_variant['min_vram_gb']}GB VRAM"

        quality = _estimate_quality(selected["param_b"], category, family.get("capabilities", []), family.get("pulls", 0.0), family.get("updated", ""))
        results.append(
            {
                "name": family["slug"],
                "description": family.get("description") or family["slug"],
                "category": category,
                "quality": quality,
                "model_size_gb": selected["model_size_gb"],
                "min_ram_gb": selected["min_ram_gb"],
                "min_vram_gb": selected["min_vram_gb"],
                "cpu_ok": selected["cpu_ok"],
                "status": selected["status"],
                "note": family_note,
                "ollama": selected["ollama"],
                "platforms": ["Ollama"],
                "tags": family.get("capabilities", [])[:],
                "selected_size": selected["size_label"],
                "available_sizes": family.get("sizes", [])[:],
                "updated": family.get("updated", ""),
                "pulls": family.get("pulls", 0.0),
                "variant_count": len(family.get("sizes", []) or [None]),
                "next_variant": next_variant,
            }
        )

    results.sort(key=lambda item: (_STATUS_ORDER[item["status"]], item["category"], -item["quality"], -item["pulls"], item["name"]))
    return results


def build_coding_recommendations(results: List[Dict[str, Any]], limit: int = 5) -> List[Dict[str, Any]]:
    coding = [item for item in results if item["category"] == "Code Generation"]
    coding.sort(key=lambda item: (_STATUS_ORDER[item["status"]], -item["quality"], -item["model_size_gb"], -item["pulls"]))
    return coding[:limit]


def build_quickstart(results: List[Dict[str, Any]], limit: int = 5) -> List[Dict[str, Any]]:
    quickstart = []
    seen = set()

    for item in build_coding_recommendations(results, limit=limit):
        if item.get("ollama") and item["name"] not in seen and item["status"] != "no":
            quickstart.append(item)
            seen.add(item["name"])
        if len(quickstart) >= limit:
            return quickstart

    remaining = sorted(
        [item for item in results if item["status"] in {"excellent", "good", "cpu_only"} and item.get("ollama")],
        key=lambda item: (_STATUS_ORDER[item["status"]], -item["quality"], -item["pulls"]),
    )
    for item in remaining:
        if item["name"] in seen:
            continue
        quickstart.append(item)
        seen.add(item["name"])
        if len(quickstart) >= limit:
            break
    return quickstart


def _format_examples(candidates: List[Dict[str, Any]], limit: int = 3) -> str:
    names = []
    for candidate in candidates[:limit]:
        name = candidate.get("name") or candidate.get("family", {}).get("name")
        size_label = candidate.get("size_label") or candidate.get("selected_size")
        if name:
            names.append(f"{name} ({size_label})" if size_label else name)
    return ", ".join(names)


def _normalize_apple_target(required: int, current: float) -> int:
    for tier in _APPLE_MEMORY_TIERS:
        if tier >= required and tier > current:
            return tier
    return max(required, int(current))


def build_upgrade_recommendations(
    results: List[Dict[str, Any]],
    ram_gb: float,
    vram_gb: float,
    unified_memory: bool = False,
    has_gpu_accel: bool = False,
    limit: int = 3,
) -> List[Dict[str, str]]:
    candidates = []
    for item in results:
        if item["category"] != "Code Generation" or item["quality"] < 4:
            continue
        next_variant = item.get("next_variant")
        if next_variant:
            candidates.append({"family": item, **next_variant})
        elif item["status"] in {"limited", "no"}:
            candidates.append(
                {
                    "family": item,
                    "size_label": item.get("selected_size", "latest"),
                    "min_ram_gb": item["min_ram_gb"],
                    "min_vram_gb": item["min_vram_gb"],
                }
            )

    tips: List[Dict[str, str]] = []
    if not candidates:
        return tips

    if unified_memory:
        grouped: Dict[int, List[Dict[str, Any]]] = {}
        for candidate in candidates:
            target = _normalize_apple_target(max(candidate["min_ram_gb"], candidate["min_vram_gb"]), ram_gb)
            grouped.setdefault(target, []).append(candidate)

        ranked = sorted(grouped.items(), key=lambda item: (-len(item[1]), item[0]))
        for target, unlocked in ranked[:limit]:
            tips.append(
                {
                    "title": f"Unified Memory: {target}GB+ tier",
                    "body": (
                        f"A {target}GB+ Apple Silicon memory tier unlocks {len(unlocked)} more strong coding models, "
                        f"including {_format_examples(unlocked)}."
                    ),
                }
            )
        return tips

    if not has_gpu_accel:
        tips.append(
            {
                "title": "GPU acceleration unlocks better code models",
                "body": "CUDA or Metal-class GPU acceleration moves many coding models out of CPU-only mode and makes 7B to 14B code models practical.",
            }
        )

    vram_only = [candidate for candidate in candidates if candidate["min_ram_gb"] <= ram_gb and candidate["min_vram_gb"] > vram_gb]
    if vram_only:
        target = min(candidate["min_vram_gb"] for candidate in vram_only)
        unlocked = [candidate for candidate in vram_only if candidate["min_vram_gb"] <= target]
        tips.append(
            {
                "title": f"GPU memory: move to {target}GB VRAM",
                "body": f"That unlocks {len(unlocked)} more strong coding models, including {_format_examples(unlocked)}.",
            }
        )

    ram_only = [candidate for candidate in candidates if candidate["min_vram_gb"] <= vram_gb and candidate["min_ram_gb"] > ram_gb]
    if ram_only:
        target = min(candidate["min_ram_gb"] for candidate in ram_only)
        unlocked = [candidate for candidate in ram_only if candidate["min_ram_gb"] <= target]
        tips.append(
            {
                "title": f"System RAM: move to {target}GB",
                "body": f"That unlocks {len(unlocked)} more coding models that already fit your current VRAM, including {_format_examples(unlocked)}.",
            }
        )

    if len(tips) < limit:
        combined = sorted(
            candidates,
            key=lambda item: (
                (item["min_vram_gb"] - vram_gb) + (item["min_ram_gb"] - ram_gb),
                item["min_vram_gb"],
                item["min_ram_gb"],
            ),
        )
        for candidate in combined:
            title = f"Next big unlock: {candidate['family']['name']} ({candidate['size_label']})"
            body = f"Target {candidate['min_ram_gb']}GB RAM and {candidate['min_vram_gb']}GB VRAM to reach this higher-tier coding model."
            tips.append({"title": title, "body": body})
            if len(tips) >= limit:
                break

    deduped = []
    seen_titles = set()
    for tip in tips:
        if tip["title"] in seen_titles:
            continue
        seen_titles.add(tip["title"])
        deduped.append(tip)
        if len(deduped) >= limit:
            break
    return deduped


def has_gpu_acceleration(gpus: List[Dict[str, Any]]) -> bool:
    return any(gpu.get("cuda") or gpu.get("metal") for gpu in gpus)


def is_ollama_model_installed(model_record: Dict[str, Any], installed: Dict[str, Dict[str, Any]]) -> bool:
    if not installed:
        return False

    wanted = (model_record.get("ollama") or "").replace("ollama run ", "").strip().lower()
    wanted_base = wanted.split(":")[0]
    for info in installed.values():
        full_name = (info.get("full_name") or "").lower()
        base_name = full_name.split(":")[0]
        if full_name == wanted or base_name == wanted_base:
            return True
    return False