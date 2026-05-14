"""
Agentic README updater.

Reads app.py, sends it to a GitHub Models LLM, and writes the
AI-generated content back to README.md.

Environment variables required:
  GITHUB_TOKEN  – standard Actions token (used for Models API auth)
  GITHUB_REPOSITORY – e.g. "owner/repo"  (set automatically by Actions)

Optional:
  MODEL – GitHub Models model ID (default: openai/gpt-4o-mini)
"""

import os
import sys
import pathlib
import urllib.request
import urllib.error
import json

MODELS_ENDPOINT = "https://models.inference.ai.azure.com/chat/completions"
MODEL = os.getenv("MODEL", "openai/gpt-4o-mini")

SYSTEM_PROMPT = """You are a technical writer. Your job is to generate a clear,
accurate and up-to-date README.md for a Python project.

Given the full source of app.py, produce a README that covers:
1. Project title and one-sentence description
2. Features / endpoints (list every Flask route with its HTTP method and a short description)
3. Requirements
4. How to install and run the app locally
5. Usage examples (curl or browser)

Use Markdown. Be concise. Do NOT include any commentary outside the README itself."""

USER_TEMPLATE = """Here is the current app.py:\n\n```python\n{app_source}\n```\n
Generate an updated README.md for this project."""


def call_llm(app_source: str, token: str) -> str:
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": USER_TEMPLATE.format(app_source=app_source)},
        ],
        "temperature": 0.3,
        "max_tokens": 1024,
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        MODELS_ENDPOINT,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        print(f"::error::Models API returned {exc.code}: {exc.read().decode()}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as exc:
        print(f"::error::Could not reach Models API: {exc.reason}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as exc:
        print(f"::error::Invalid JSON in Models API response: {exc}", file=sys.stderr)
        sys.exit(1)

    choices = body.get("choices")
    if not choices or not isinstance(choices, list):
        print(f"::error::Unexpected API response structure (no 'choices'): {body}", file=sys.stderr)
        sys.exit(1)

    try:
        content = choices[0]["message"]["content"]
    except (KeyError, IndexError) as exc:
        print(f"::error::Could not extract content from API response: {exc}", file=sys.stderr)
        sys.exit(1)

    return content.strip()


def main() -> None:
    repo_root = pathlib.Path(__file__).resolve().parents[2]
    app_py = repo_root / "app.py"
    readme = repo_root / "README.md"

    if not app_py.exists():
        print("::error::app.py not found in repository root.", file=sys.stderr)
        sys.exit(1)

    token = os.getenv("GITHUB_TOKEN")
    if not token:
        print("::error::GITHUB_TOKEN environment variable is not set.", file=sys.stderr)
        sys.exit(1)

    print(f"Using model: {MODEL}")
    print("Reading app.py ...")
    app_source = app_py.read_text(encoding="utf-8")

    print("Calling LLM to generate README ...")
    new_readme = call_llm(app_source, token)

    print("Writing README.md ...")
    readme.write_text(new_readme + "\n", encoding="utf-8")
    print("Done.")


if __name__ == "__main__":
    main()
