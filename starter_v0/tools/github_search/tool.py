from __future__ import annotations

import os
from typing import Any

import requests

from tools._shared import TIMEOUT, err


GITHUB_REPOS_URL = "https://api.github.com/search/repositories"
ALLOWED_SORTS = {"stars", "forks", "updated", "best_match"}


def _parse_max_results(max_results: Any) -> int:
    if isinstance(max_results, bool):
        raise TypeError("max_results must be an integer, not bool")
    if max_results is None or max_results == "":
        return 5
    parsed = int(max_results)
    return max(1, min(parsed, 10))


def _normalize_sort(sort: Any) -> str:
    if sort is None or sort == "":
        return "stars"
    if not isinstance(sort, str):
        raise TypeError("sort must be a string")
    clean = sort.strip()
    if clean not in ALLOWED_SORTS:
        raise ValueError(f"Unsupported sort '{clean}'; expected one of {sorted(ALLOWED_SORTS)}")
    return clean


def search_github_repos(
    query: str = "",
    language: str = "",
    sort: str = "stars",
    max_results: int = 5,
) -> dict[str, Any]:
    """Search public GitHub repositories and return normalized items or an error dict."""
    try:
        if not isinstance(query, str) or not query.strip():
            raise ValueError("query must be a non-empty string")
        if language is not None and not isinstance(language, str):
            raise TypeError("language must be a string")

        clean_query = " ".join(query.split())
        clean_lang = (language or "").strip()
        clean_sort = _normalize_sort(sort)
        limit = _parse_max_results(max_results)

        q = f"{clean_query} language:{clean_lang}" if clean_lang else clean_query
        params: dict[str, Any] = {"q": q, "per_page": limit}
        if clean_sort != "best_match":
            params["sort"] = clean_sort
            params["order"] = "desc"

        headers: dict[str, str] = {
            "Accept": "application/vnd.github+json",
            "User-Agent": os.getenv("GITHUB_USER_AGENT", "AI20k-Day03-Research-Agent/1.0"),
        }
        token = os.getenv("GITHUB_TOKEN", "").strip()
        if token:
            headers["Authorization"] = f"Bearer {token}"

        response = requests.get(GITHUB_REPOS_URL, params=params, headers=headers, timeout=TIMEOUT)
        response.raise_for_status()
        data = response.json()

        items = [
            {
                "title": item.get("full_name") or item.get("name") or "",
                "url": item.get("html_url") or "",
                "source": "github.com",
                "summary": item.get("description") or "",
                "stars": item.get("stargazers_count", 0),
                "language": item.get("language") or "",
                "updated_at": item.get("updated_at") or "",
            }
            for item in data.get("items", [])[:limit]
        ]
        return {
            "tool": "github_search",
            "query": clean_query,
            "language": clean_lang,
            "sort": clean_sort,
            "total_count": data.get("total_count", len(items)),
            "items": items,
        }
    except Exception as exc:
        return err("github_search", exc)

