---
name: hf_search
track: bonus
kind: live_api
provider: Hugging Face Hub API
requires_env: []
inputs: [query, kind, sort, max_results]
outputs: [items]
side_effect: false
---
# hf_search

Searches public models or datasets on Hugging Face Hub (`https://huggingface.co/api/models`
or `/api/datasets`). Supports sorting by `downloads`, `likes`, or `lastModified`.
Does not require an API key (`HF_TOKEN` is optional for higher rate limits or gated access).

