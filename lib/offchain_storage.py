from __future__ import annotations

import re
import time
from typing import Optional

import requests


def check_token_gist_scope(github_api_token: str) -> bool:
    if not github_api_token:
        raise ValueError("Github API token is required")

    response = requests.get(
        "https://api.github.com/user",
        headers={"Authorization": f"Bearer {github_api_token}"},
        timeout=30,
    )
    response.raise_for_status()
    scopes_raw: Optional[str] = response.headers.get("x-oauth-scopes")
    if not scopes_raw:
        return True

    scopes = [s.strip() for s in scopes_raw.split(",") if s.strip()]
    if scopes and scopes[0] != "gist":
        raise PermissionError("The provided Github API token does not have Gist permissions")
    if len(scopes) > 1:
        print("WARNING: Github API token has permissions beyond Gists")
    return True


def create_gist(github_api_token: str, content: str) -> str:
    if not isinstance(content, str):
        raise TypeError("Gist content must be a string")
    check_token_gist_scope(github_api_token)

    body = {
        "public": False,
        "files": {
            f"encrypted-functions-request-data-{int(time.time() * 1000)}.json": {
                "content": content
            }
        },
    }
    response = requests.post(
        "https://api.github.com/gists",
        json=body,
        headers={"Authorization": f"token {github_api_token}"},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()["html_url"] + "/raw"


def delete_gist(github_api_token: str, gist_url: str) -> bool:
    if not github_api_token:
        raise ValueError("Github API token is required")
    if not gist_url:
        raise ValueError("Github Gist URL is required")

    match = re.search(r"gist\.github\.com/[^/]+/([a-zA-Z0-9]+)", gist_url)
    if not match:
        raise ValueError("Invalid Gist URL")

    response = requests.delete(
        f"https://api.github.com/gists/{match.group(1)}",
        headers={"Authorization": f"Bearer {github_api_token}"},
        timeout=30,
    )
    response.raise_for_status()
    return True


# JS toolkit names.
createGist = create_gist
deleteGist = delete_gist


__all__ = ["check_token_gist_scope", "create_gist", "delete_gist", "createGist", "deleteGist"]
