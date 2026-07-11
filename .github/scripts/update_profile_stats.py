#!/usr/bin/env python3
"""Refresh the dynamic values embedded in the profile-card SVG files.

Uses only Python's standard library and the GitHub token supplied by GitHub Actions.
"""

from __future__ import annotations

import calendar
import datetime as dt
import json
import os
from pathlib import Path
import urllib.request
import xml.etree.ElementTree as ET

USERNAME = os.getenv("PROFILE_USERNAME", "AFLucas-UOM")
TOKEN = os.getenv("GITHUB_TOKEN", "")
ROOT = Path(__file__).resolve().parents[2]
SVG_FILES = (ROOT / "assets" / "profile-card.svg",)


def github_request(url: str, *, data: dict | None = None) -> dict | list:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": f"{USERNAME}-profile-readme",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"

    payload = None
    if data is not None:
        payload = json.dumps(data).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = urllib.request.Request(url, data=payload, headers=headers)
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def fetch_all_public_repositories() -> list[dict]:
    repositories: list[dict] = []
    page = 1
    while True:
        url = (
            f"https://api.github.com/users/{USERNAME}/repos"
            f"?type=owner&sort=updated&per_page=100&page={page}"
        )
        batch = github_request(url)
        if not isinstance(batch, list):
            raise RuntimeError("Unexpected repositories response.")
        repositories.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    return repositories


def contribution_count() -> tuple[int, int]:
    year = dt.datetime.now(dt.timezone.utc).year
    query = """
    query($login: String!, $from: DateTime!, $to: DateTime!) {
      user(login: $login) {
        contributionsCollection(from: $from, to: $to) {
          contributionCalendar {
            totalContributions
          }
        }
      }
    }
    """
    variables = {
        "login": USERNAME,
        "from": f"{year}-01-01T00:00:00Z",
        "to": f"{year}-12-31T23:59:59Z",
    }
    response = github_request(
        "https://api.github.com/graphql",
        data={"query": query, "variables": variables},
    )
    count = int(
        response["data"]["user"]["contributionsCollection"]
        ["contributionCalendar"]["totalContributions"]
    )
    return year, count


def account_uptime(created_at: str) -> str:
    created = dt.datetime.fromisoformat(created_at.replace("Z", "+00:00")).date()
    today = dt.datetime.now(dt.timezone.utc).date()

    years = today.year - created.year
    months = today.month - created.month
    days = today.day - created.day

    if days < 0:
        months -= 1
        previous_month = today.month - 1 or 12
        previous_year = today.year if today.month > 1 else today.year - 1
        days += calendar.monthrange(previous_year, previous_month)[1]

    if months < 0:
        years -= 1
        months += 12

    return f"{years}y {months}m {days}d"


def replace_text(root: ET.Element, element_id: str, value: str) -> None:
    for element in root.iter():
        if element.attrib.get("id") == element_id:
            element.text = value
            return
    raise KeyError(f"SVG element with id={element_id!r} was not found.")


def update_svg(path: Path, values: dict[str, str]) -> None:
    ET.register_namespace("", "http://www.w3.org/2000/svg")
    tree = ET.parse(path)
    root = tree.getroot()

    for element_id, value in values.items():
        replace_text(root, element_id, value)

    tree.write(path, encoding="utf-8", xml_declaration=True)


def main() -> None:
    user = github_request(f"https://api.github.com/users/{USERNAME}")
    if not isinstance(user, dict):
        raise RuntimeError("Unexpected user response.")

    repositories = fetch_all_public_repositories()
    stars = sum(int(repo.get("stargazers_count", 0)) for repo in repositories)
    year, contributions = contribution_count()

    values = {
        "repo_data": f"{int(user['public_repos']):,}",
        "follower_data": f"{int(user['followers']):,}",
        "star_data": f"{stars:,}",
        "contrib_label": f"Contribs.{year}",
        "contrib_data": f"{contributions:,}",
        "uptime_data": account_uptime(str(user["created_at"])),
    }

    for svg_path in SVG_FILES:
        update_svg(svg_path, values)
        print(f"Updated {svg_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
