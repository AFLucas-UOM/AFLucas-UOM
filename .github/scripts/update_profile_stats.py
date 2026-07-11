#!/usr/bin/env python3
"""Build the GitHub profile card and refresh its dynamic statistics."""

from __future__ import annotations

import base64
import calendar
import datetime as dt
import json
import os
from pathlib import Path
import urllib.request

USERNAME = os.getenv("PROFILE_USERNAME", "AFLucas-UOM")
TOKEN = os.getenv("GITHUB_TOKEN", "")
ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / "assets"
SVG_TEMPLATE = ASSETS / "profile-card.template.svg"
SVG_OUTPUT = ASSETS / "profile-card.svg"
PROFILE_IMAGE = ASSETS / "profile-photo.jpg"
IMAGE_PARTS = tuple(sorted((ROOT / ".github").glob("profile-image.hex.part*")))
BIRTH_DATE = dt.date(2004, 8, 26)


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


def ensure_profile_image() -> None:
    """Reconstruct the supplied portrait without removing or replacing its background."""
    if PROFILE_IMAGE.exists():
        return
    if not IMAGE_PARTS:
        raise FileNotFoundError("No profile image or encoded image parts were found.")

    encoded_hex = "".join(
        part.read_text(encoding="ascii").strip() for part in IMAGE_PARTS
    )
    PROFILE_IMAGE.write_bytes(bytes.fromhex(encoded_hex))


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
            return repositories
        page += 1


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


def age_string(birth_date: dt.date) -> str:
    today = dt.datetime.now(dt.timezone.utc).date()
    years = today.year - birth_date.year
    months = today.month - birth_date.month
    days = today.day - birth_date.day

    if days < 0:
        months -= 1
        previous_month = today.month - 1 or 12
        previous_year = today.year if today.month > 1 else today.year - 1
        days += calendar.monthrange(previous_year, previous_month)[1]

    if months < 0:
        years -= 1
        months += 12

    def unit(value: int, name: str) -> str:
        return f"{value} {name}{'' if value == 1 else 's'}"

    return f"{unit(years, 'year')}, {unit(months, 'month')}, {unit(days, 'day')}"


def render_profile_card(values: dict[str, str]) -> None:
    ensure_profile_image()
    template = SVG_TEMPLATE.read_text(encoding="utf-8")
    image_base64 = base64.b64encode(PROFILE_IMAGE.read_bytes()).decode("ascii")

    replacements = {
        "{{PROFILE_IMAGE_BASE64}}": image_base64,
        "{{UPTIME}}": values["uptime"],
        "{{REPO_DATA}}": values["repos"],
        "{{FOLLOWER_DATA}}": values["followers"],
        "{{STAR_DATA}}": values["stars"],
        "{{CONTRIB_LABEL}}": values["contrib_label"],
        "{{CONTRIB_DATA}}": values["contrib_data"],
    }

    for token, replacement in replacements.items():
        template = template.replace(token, replacement)

    unresolved = [token for token in replacements if token in template]
    if unresolved:
        raise RuntimeError(f"Unresolved SVG tokens: {', '.join(unresolved)}")

    SVG_OUTPUT.write_text(template, encoding="utf-8")


def main() -> None:
    user = github_request(f"https://api.github.com/users/{USERNAME}")
    if not isinstance(user, dict):
        raise RuntimeError("Unexpected user response.")

    repositories = fetch_all_public_repositories()
    stars = sum(int(repo.get("stargazers_count", 0)) for repo in repositories)
    year, contributions = contribution_count()

    values = {
        "repos": f"{int(user['public_repos']):,}",
        "followers": f"{int(user['followers']):,}",
        "stars": f"{stars:,}",
        "contrib_label": f"Contribs.{year}",
        "contrib_data": f"{contributions:,}",
        "uptime": age_string(BIRTH_DATE),
    }

    render_profile_card(values)
    print(f"Updated {SVG_OUTPUT.relative_to(ROOT)}")
    print(f"Profile image: {PROFILE_IMAGE.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
