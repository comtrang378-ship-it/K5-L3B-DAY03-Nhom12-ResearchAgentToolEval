from __future__ import annotations

import os
from typing import Any

import requests

from tools._shared import TIMEOUT, err


HF_API_BASE = "https://huggingface.co/api"
ALLOWED_KINDS = {"models", "datasets"}
ALLOWED_SORTS = {"downloads", "likes", "lastModified"}


def _parse_max_results(max_results: Any) -> int:
    if isinstance(max_results, bool):
        raise TypeError("max_results must be an integer, not bool")
    if max_results is None or max_results == "":
        return 5
    parsed = int(max_results)
    return max(1, min(parsed, 10))


def _normalize_choice(value: Any, default: str, allowed: set[str], field: str) -> str:
    if value is None or value == "":
        return default
    if not isinstance(value, str):
        raise TypeError(f"{field} must be a string")
    clean = value.strip()
    if clean not in allowed:
        raise ValueError(f"Unsupported {field} '{clean}'; expected one of {sorted(allowed)}")
    return clean


def _build_item_url(kind: str, item_id: str) -> str:
    if not item_id:
        return ""
    if kind == "datasets":
        return f"https://huggingface.co/datasets/{item_id}"
    return f"https://huggingface.co/{item_id}"


def search_huggingface(
    query: str = "",
    kind: str = "models",
    sort: str = "downloads",
    max_results: int = 5,
) -> dict[str, Any]:
    """Search public Hugging Face models or datasets and return normalized items or an error dict."""
    try:
        if not isinstance(query, str) or not query.strip():
            raise ValueError("query must be a non-empty string")

        clean_query = " ".join(query.split())
        clean_kind = _normalize_choice(kind, "models", ALLOWED_KINDS, "kind")
        clean_sort = _normalize_choice(sort, "downloads", ALLOWED_SORTS, "sort")
        limit = _parse_max_results(max_results)

        params: dict[str, Any] = {
            "search": clean_query,
            "sort": clean_sort,
            "direction": -1,
            "limit": limit,
        }
        headers: dict[str, str] = {
            "Accept": "application/json",
            "User-Agent": os.getenv("HF_USER_AGENT", "AI20k-Day03-Research-Agent/1.0"),
        }
        token = os.getenv("HF_TOKEN", "").strip()
        if token:
            headers["Authorization"] = f"Bearer {token}"

        response = requests.get(
            f"{HF_API_BASE}/{clean_kind}",
            params=params,
            headers=headers,
            timeout=TIMEOUT,
        )
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, list):
            raise ValueError("Unexpected Hugging Face API response format")

        items = []
        for item in data[:limit]:
            item_id = item.get("id") or item.get("modelId") or ""
            pipeline_tag = item.get("pipeline_tag") or ""
            raw_summary = item.get("description") or (f"Task: {pipeline_tag}" if pipeline_tag else "")
            summary = raw_summary[:300] if isinstance(raw_summary, str) else ""
            items.append({
                "title": item_id,
                "url": _build_item_url(clean_kind, item_id),
                "source": "huggingface.co",
                "summary": summary,
                "kind": clean_kind,
                "downloads": item.get("downloads", 0),
                "likes": item.get("likes", 0),
                "pipeline_tag": pipeline_tag,
                "tags": list(item.get("tags") or [])[:5],
                "last_modified": item.get("lastModified") or "",
            })

        return {
            "tool": "hf_search",
            "query": clean_query,
            "kind": clean_kind,
            "sort": clean_sort,
            "items": items,
        }
    except Exception as exc:
        return err("hf_search", exc)

