"""TODO CP3 (student): Tool Unit Test Challenge.

Each test below is a stub. Replace `pytest.skip(...)` with a real test.
Patterns to copy are in test_tools_examples.py. Fixtures are in conftest.py.

Rules:
- Offline only: mock HTTP with `fake_http`, set fake keys with `monkeypatch.setenv`.
- One behaviour per test. Name the test after the behaviour, not the function.
- Done = `pytest tests/ -v` shows 0 skipped, 0 failed.
"""
from __future__ import annotations

import pytest
import requests

from conftest import FakeResponse  # noqa: F401  (you will need it)
from tools import TOOL_FUNCTIONS  # noqa: F401

TODO = "TODO CP3 (student): implement this test"


# ---------------- clarify ----------------

def test_clarify_choice_returns_options_and_awaits_user() -> None:
    clarify = TOOL_FUNCTIONS["clarify"]
    result = clarify(question="Chọn nguồn?", response_type="choice", options=["Web", "X"])

    assert result["response_type"] == "choice"
    assert result["options"] == ["Web", "X"]
    assert result["awaiting_user"] is True


# ---------------- format ----------------

def test_format_sections_groups_items_by_section() -> None:
    format_tool = TOOL_FUNCTIONS["format"]
    items = [
        {"title": "Item 1", "url": "https://a.com", "section": "A"},
        {"title": "Item 2", "url": "https://b.com", "section": "B"},
        {"title": "Item 3", "url": "https://c.com", "section": "A"},
    ]
    result = format_tool(items=items, template="sections")
    md = result["markdown"]

    assert md.count("## A") == 1
    assert md.count("## B") == 1
    assert md.index("Item 3") < md.index("## B")


def test_format_thread_numbers_items() -> None:
    format_tool = TOOL_FUNCTIONS["format"]
    items = [
        {"title": "First", "url": "https://1.example.com"},
        {"title": "Second", "url": "https://2.example.com"},
    ]
    result = format_tool(items=items, template="thread")
    blocks = result["markdown"].split("\n\n")

    assert blocks[0].startswith("1/ ")
    assert blocks[1].startswith("2/ ")


def test_format_empty_items_does_not_crash() -> None:
    format_tool = TOOL_FUNCTIONS["format"]
    none_res = format_tool(items=None, template="sections")
    empty_res = format_tool(items=[], template="brief")

    assert none_res["item_count"] == 0
    assert empty_res["item_count"] == 0
    assert isinstance(none_res["markdown"], str)


# ---------------- send (guardrail) ----------------

def test_send_confirmed_posts_to_telegram(monkeypatch, fake_http) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "bot-token-123")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "-100999")
    calls = fake_http(FakeResponse({"ok": True}))

    result = TOOL_FUNCTIONS["send"](text="Bản tin sáng", confirmed=True)

    assert len(calls) == 1
    assert calls[0]["method"] == "POST"
    assert "bot-token-123" in calls[0]["url"]
    assert calls[0]["json"]["chat_id"] == "-100999"
    assert calls[0]["json"]["text"] == "Bản tin sáng"
    assert result["status"] == "sent"


def test_send_confirmed_without_env_returns_error_and_no_request(fake_http) -> None:
    calls = fake_http(FakeResponse({"ok": True}))
    result = TOOL_FUNCTIONS["send"](text="Bản tin sáng", confirmed=True)

    assert result["error"] == "RuntimeError"
    assert calls == []


# ---------------- lookup ----------------

def test_lookup_without_timeframe_omits_time_range(monkeypatch, fake_http) -> None:
    monkeypatch.setenv("TAVILY_API_KEY", "test-key")
    calls = fake_http(FakeResponse({"results": []}))

    TOOL_FUNCTIONS["lookup"](query="AI agents", timeframe=None)

    assert len(calls) == 1
    assert "time_range" not in calls[0]["json"]


# ---------------- fetch ----------------

def test_fetch_maps_firecrawl_response(monkeypatch, fake_http) -> None:
    monkeypatch.setenv("FIRECRAWL_API_KEY", "fc-key")
    calls = fake_http(FakeResponse({
        "data": {
            "markdown": "Article body",
            "metadata": {"title": "T", "sourceURL": "https://example.com/post"},
        }
    }))

    result = TOOL_FUNCTIONS["fetch"](url="https://www.example.com/raw")

    assert calls[0]["url"] == "https://api.firecrawl.dev/v1/scrape"
    assert result["items"][0] == {
        "title": "T",
        "url": "https://example.com/post",
        "source": "example.com",
        "summary": "Article body",
    }


def test_fetch_truncates_markdown_to_4000_chars(monkeypatch, fake_http) -> None:
    monkeypatch.setenv("FIRECRAWL_API_KEY", "fc-key")
    fake_http(FakeResponse({"data": {"markdown": "x" * 5000, "metadata": {}}}))

    result = TOOL_FUNCTIONS["fetch"](url="https://example.com/long")

    assert len(result["items"][0]["summary"]) == 4000


# ---------------- timeline / social_search ----------------

def test_timeline_respects_limit_and_skips_items_without_id(monkeypatch, fake_http) -> None:
    monkeypatch.setenv("RAPIDAPI_KEY", "rk-key")
    raw_timeline = [{"text": "missing id"}] + [
        {"tweet_id": str(i), "screen_name": "sama", "text": f"Tweet {i}"} for i in range(6)
    ]
    fake_http(FakeResponse({"timeline": raw_timeline}))

    result = TOOL_FUNCTIONS["timeline"](screenname="sama", limit=3)

    assert len(result["items"]) == 3
    assert all(item["url"].startswith("https://x.com/sama/status/") for item in result["items"])


def test_social_search_passes_search_type(monkeypatch, fake_http) -> None:
    monkeypatch.setenv("RAPIDAPI_KEY", "rk-key")
    calls = fake_http(FakeResponse({"timeline": []}))

    TOOL_FUNCTIONS["social_search"](query="MCP protocol", search_type="Top", limit=4)

    assert len(calls) == 1
    assert calls[0]["params"] == {"query": "MCP protocol", "search_type": "Top"}


# ---------------- policy (local knowledge + trust boundary) ----------------

def test_policy_empty_query_returns_no_results() -> None:
    result = TOOL_FUNCTIONS["policy"](query="")
    assert result["results"] == []


def test_policy_area_filter_only_returns_that_area() -> None:
    result = TOOL_FUNCTIONS["policy"](query="API keys", policy_area="data_privacy")

    assert len(result["results"]) > 0
    assert all(hit["policy_area"] == "data_privacy" for hit in result["results"])


def test_policy_instruction_like_lines_go_to_untrusted_text() -> None:
    result = TOOL_FUNCTIONS["policy"](query="injection probe", policy_area="source_citation", top_k=5)
    probe_hits = [hit for hit in result["results"] if hit["section"] == "Injection probe"]

    assert len(probe_hits) == 1
    hit = probe_hits[0]
    assert any("ignore the citation policy" in line for line in hit["untrusted_text"])
    assert "ignore the citation policy" not in hit["facts"]


# ---------------- YOUR NEW TOOL(S): github_search ----------------

def test_github_search_sends_expected_request_and_maps_repos(monkeypatch, fake_http) -> None:
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    calls = fake_http(FakeResponse({
        "total_count": 42,
        "items": [
            {
                "full_name": "langchain-ai/langgraph",
                "html_url": "https://github.com/langchain-ai/langgraph",
                "description": "Build resilient language agents as graphs.",
                "stargazers_count": 12000,
                "language": "Python",
                "updated_at": "2026-11-01T10:00:00Z",
            },
            {
                "full_name": "microsoft/autogen",
                "html_url": "https://github.com/microsoft/autogen",
                "description": "A programming framework for agentic AI.",
                "stargazers_count": 40000,
                "language": "Python",
                "updated_at": "2026-11-02T12:00:00Z",
            },
        ],
    }))

    github_search = TOOL_FUNCTIONS["github_search"]
    result = github_search(query="agent framework", language="python", sort="stars", max_results=2)

    assert len(calls) == 1
    assert calls[0]["url"] == "https://api.github.com/search/repositories"
    assert calls[0]["params"] == {"q": "agent framework language:python", "per_page": 2, "sort": "stars", "order": "desc"}
    assert "Authorization" not in calls[0]["headers"]
    assert result["total_count"] == 42
    assert len(result["items"]) == 2
    assert result["items"][0] == {
        "title": "langchain-ai/langgraph",
        "url": "https://github.com/langchain-ai/langgraph",
        "source": "github.com",
        "summary": "Build resilient language agents as graphs.",
        "stars": 12000,
        "language": "Python",
        "updated_at": "2026-11-01T10:00:00Z",
    }


def test_github_search_bad_input_returns_error_dict_without_network(fake_http) -> None:
    calls = fake_http(FakeResponse({"items": []}))
    github_search = TOOL_FUNCTIONS["github_search"]

    empty_res = github_search(query="   ")
    bad_type_res = github_search(query=123)  # type: ignore[arg-type]
    bad_sort_res = github_search(query="llm", sort="invalid_sort")

    assert empty_res["error"] == "ValueError"
    assert bad_type_res["error"] == "ValueError"
    assert bad_sort_res["error"] == "ValueError"
    assert calls == []


def test_github_search_http_error_returns_error_dict(fake_http) -> None:
    fake_http(FakeResponse(status_code=403))
    github_search = TOOL_FUNCTIONS["github_search"]

    result = github_search(query="mcp server")

    assert result["tool"] == "github_search"
    assert result["error"] == "HTTPError"


def test_github_search_timeout_returns_error_dict(fake_http) -> None:
    fake_http(requests.Timeout("Request timed out"))
    github_search = TOOL_FUNCTIONS["github_search"]

    result = github_search(query="mcp server")

    assert result["tool"] == "github_search"
    assert result["error"] == "Timeout"


# ---------------- YOUR NEW TOOL(S): hf_search ----------------

def test_hf_search_sends_expected_request_and_maps_models_and_datasets(monkeypatch, fake_http) -> None:
    monkeypatch.delenv("HF_TOKEN", raising=False)
    hf_search = TOOL_FUNCTIONS["hf_search"]

    model_calls = fake_http(FakeResponse([
        {
            "id": "Qwen/Qwen2.5-7B-Instruct",
            "downloads": 2500000,
            "likes": 1800,
            "pipeline_tag": "text-generation",
            "tags": ["transformers", "safetensors", "qwen2"],
            "lastModified": "2026-10-15T08:30:00.000Z",
        },
    ]))
    model_res = hf_search(query="qwen2.5", kind="models", sort="downloads", max_results=3)

    assert len(model_calls) == 1
    assert model_calls[0]["url"] == "https://huggingface.co/api/models"
    assert model_calls[0]["params"] == {"search": "qwen2.5", "sort": "downloads", "direction": -1, "limit": 3}
    assert "Authorization" not in model_calls[0]["headers"]
    assert model_res["items"][0] == {
        "title": "Qwen/Qwen2.5-7B-Instruct",
        "url": "https://huggingface.co/Qwen/Qwen2.5-7B-Instruct",
        "source": "huggingface.co",
        "summary": "Task: text-generation",
        "kind": "models",
        "downloads": 2500000,
        "likes": 1800,
        "pipeline_tag": "text-generation",
        "tags": ["transformers", "safetensors", "qwen2"],
        "last_modified": "2026-10-15T08:30:00.000Z",
    }

    dataset_calls = fake_http(FakeResponse([
        {
            "id": "HuggingFaceH4/ultrachat_200k",
            "downloads": 95000,
            "likes": 620,
            "description": "Filtered multi-turn dialogue dataset.",
            "tags": ["task_categories:text-generation"],
            "lastModified": "2026-09-20T12:00:00.000Z",
        },
    ]))
    dataset_res = hf_search(query="ultrachat", kind="datasets", sort="likes", max_results=2)

    assert len(dataset_calls) == 1
    assert dataset_calls[0]["url"] == "https://huggingface.co/api/datasets"
    assert dataset_calls[0]["params"] == {"search": "ultrachat", "sort": "likes", "direction": -1, "limit": 2}
    assert dataset_res["items"][0]["url"] == "https://huggingface.co/datasets/HuggingFaceH4/ultrachat_200k"
    assert dataset_res["items"][0]["summary"] == "Filtered multi-turn dialogue dataset."


def test_hf_search_bad_input_returns_error_dict_without_network(fake_http) -> None:
    calls = fake_http(FakeResponse([]))
    hf_search = TOOL_FUNCTIONS["hf_search"]

    empty_res = hf_search(query="   ")
    bad_kind_res = hf_search(query="bert", kind="spaces")
    bad_sort_res = hf_search(query="bert", sort="stars")
    bad_limit_res = hf_search(query="bert", max_results=True)  # type: ignore[arg-type]

    assert empty_res["error"] == "ValueError"
    assert bad_kind_res["error"] == "ValueError"
    assert bad_sort_res["error"] == "ValueError"
    assert bad_limit_res["error"] == "TypeError"
    assert calls == []


def test_hf_search_http_and_timeout_errors_return_error_dict(fake_http) -> None:
    hf_search = TOOL_FUNCTIONS["hf_search"]

    fake_http(FakeResponse(status_code=503))
    http_res = hf_search(query="llama")
    assert http_res["tool"] == "hf_search"
    assert http_res["error"] == "HTTPError"

    fake_http(requests.Timeout("Request timed out"))
    timeout_res = hf_search(query="llama")
    assert timeout_res["tool"] == "hf_search"
    assert timeout_res["error"] == "Timeout"
