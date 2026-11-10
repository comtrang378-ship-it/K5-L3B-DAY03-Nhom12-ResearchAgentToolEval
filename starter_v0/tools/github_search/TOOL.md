---
name: github_search
track: bonus
kind: live_api
provider: GitHub REST API
requires_env: []
inputs: [query, language, sort, max_results]
outputs: [items]
side_effect: false
---
# github_search

Searches public GitHub repositories via the GitHub Search REST API
(`https://api.github.com/search/repositories`). Supports optional `language`
filtering and sorting (`stars`, `forks`, `updated`, `best_match`). Does not
require an API key (`GITHUB_TOKEN` is optional for higher rate limits).

