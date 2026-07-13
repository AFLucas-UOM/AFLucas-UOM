#!/usr/bin/env python3
"""Build the GitHub profile card and refresh its dynamic statistics."""

from __future__ import annotations

import base64
import calendar
import datetime as dt
from html import escape
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

ROW_WIDTH = 84
STAT_ROW_WIDTH = 40


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


def profile_image_data_uri() -> str:
    ensure_profile_image()
    image_bytes = PROFILE_IMAGE.read_bytes()

    if image_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        mime_type = "image/png"
    elif image_bytes.startswith(b"\xff\xd8\xff"):
        mime_type = "image/jpeg"
    else:
        raise ValueError("Unsupported profile image format; expected PNG or JPEG.")

    encoded = base64.b64encode(image_bytes).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


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


def terminal_row(
    label: str,
    value: str,
    *,
    x: int,
    y: int,
    width: int,
    value_id: str | None = None,
) -> str:
    """Render one terminal row with uniform dotted leaders and a fixed right edge."""
    dots = max(width - len(label) - len(value) - 2, 3)
    value_id_attribute = f' id="{escape(value_id)}"' if value_id else ""

    return (
        f'<text x="{x}" y="{y}" class="row">'
        f'<tspan class="key">{escape(label)}</tspan>'
        f'<tspan class="dots"> {"." * dots} </tspan>'
        f'<tspan class="row-value"{value_id_attribute}>{escape(value)}</tspan>'
        f'</text>'
    )


def render_rows(
    items: list[tuple[str, str, str | None]],
    *,
    start_y: int,
    x: int = 356,
    step: int = 25,
    width: int = ROW_WIDTH,
) -> str:
    rows = []
    for index, (label, value, value_id) in enumerate(items):
        rows.append(
            terminal_row(
                label,
                value,
                x=x,
                y=start_y + index * step,
                width=width,
                value_id=value_id,
            )
        )
    return "\n  ".join(rows)


def render_profile_card(values: dict[str, str]) -> None:
    template = SVG_TEMPLATE.read_text(encoding="utf-8")

    overview_rows = render_rows(
        [
            ("Alias", "Fili", None),
            ("Location", "Malta, EU", None),
            ("Uptime", values["uptime"], "uptime_data"),
            ("Host", "DAWL AI Lab @ University of Malta", None),
            ("Kernel", "Research Support Officer & MSc AI Student", None),
            (
                "Passion.Creativity",
                "Piano · Vinyl Collecting · Digital Design · PC Building",
                None,
            ),
            (
                "Passion.Community",
                "GDG Malta Marketing Lead · Medium Writer",
                None,
            ),
        ],
        start_y=112,
    )

    research_rows = render_rows(
        [
            (
                "Research.Areas",
                "Computer Vision · Multimodal AI Systems · AI Literacy",
                None,
            ),
            (
                "Research.Current",
                "Cross-Paradigm Visual Perception for Municipal Monitoring",
                None,
            ),
            ("Research.Projects", "AICOM & EMBAT", None),
        ],
        start_y=330,
    )

    contact_rows = render_rows(
        [
            ("Email.Personal", "contact@aflucas.com", None),
            ("Email.Research", "andrea.f.lucas@um.edu.mt", None),
            ("Social.LinkedIn", "aflucas26", None),
        ],
        start_y=448,
    )

    stats_rows = "\n  ".join(
        [
            terminal_row(
                "Followers",
                values["followers"],
                x=372,
                y=581,
                width=STAT_ROW_WIDTH,
                value_id="follower_data",
            ),
            terminal_row(
                "Stars",
                values["stars"],
                x=714,
                y=581,
                width=STAT_ROW_WIDTH,
                value_id="star_data",
            ),
            terminal_row(
                "Public.Repos",
                values["repos"],
                x=372,
                y=611,
                width=STAT_ROW_WIDTH,
                value_id="repo_data",
            ),
            terminal_row(
                f"Contrib.{values['year']}",
                values["contributions"],
                x=714,
                y=611,
                width=STAT_ROW_WIDTH,
                value_id="contrib_data",
            ),
        ]
    )

    replacements = {
        "{{PROFILE_IMAGE_DATA_URI}}": profile_image_data_uri(),
        "{{OVERVIEW_ROWS}}": overview_rows,
        "{{RESEARCH_ROWS}}": research_rows,
        "{{CONTACT_ROWS}}": contact_rows,
        "{{STATS_ROWS}}": stats_rows,
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
        "year": str(year),
        "contributions": f"{contributions:,}",
        "uptime": age_string(BIRTH_DATE),
    }

    render_profile_card(values)
    print(f"Updated {SVG_OUTPUT.relative_to(ROOT)}")
    print(f"Profile image: {PROFILE_IMAGE.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
