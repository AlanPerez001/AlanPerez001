#!/usr/bin/env python3

import json
import os
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from xml.sax.saxutils import escape


GITHUB_GRAPHQL_URL = "https://api.github.com/graphql"

USERNAME = os.environ.get("GITHUB_REPOSITORY_OWNER", "AlanPerez001")
TOKEN = os.environ["GITHUB_TOKEN"]

OUTPUT = Path("dist/streak.svg")
OUTPUT.parent.mkdir(parents=True, exist_ok=True)


def graphql(query: str, variables: dict) -> dict:
    payload = json.dumps(
        {
            "query": query,
            "variables": variables,
        }
    ).encode("utf-8")

    request = urllib.request.Request(
        GITHUB_GRAPHQL_URL,
        data=payload,
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": "github-profile-stats",
        },
        method="POST",
    )

    with urllib.request.urlopen(request) as response:
        result = json.loads(response.read().decode("utf-8"))

    if "errors" in result:
        raise RuntimeError(json.dumps(result["errors"], indent=2))

    return result["data"]


def get_contributions():
    # GitHub's contributionsCollection supports a maximum 1-year window.
    today = datetime.now(timezone.utc).date()
    start = today - timedelta(days=364)

    query = """
    query($login: String!, $from: DateTime!, $to: DateTime!) {
      user(login: $login) {
        contributionsCollection(from: $from, to: $to) {
          contributionCalendar {
            totalContributions
            weeks {
              contributionDays {
                date
                contributionCount
              }
            }
          }
        }
      }
    }
    """

    variables = {
        "login": USERNAME,
        "from": f"{start.isoformat()}T00:00:00Z",
        "to": f"{today.isoformat()}T23:59:59Z",
    }

    data = graphql(query, variables)

    user = data.get("user")
    if not user:
        raise RuntimeError(f"GitHub user not found: {USERNAME}")

    calendar = user["contributionsCollection"]["contributionCalendar"]

    days = {}

    for week in calendar["weeks"]:
        for contribution_day in week["contributionDays"]:
            day = date.fromisoformat(contribution_day["date"])

            if start <= day <= today:
                days[day] = contribution_day["contributionCount"]

    return days, calendar["totalContributions"], today


def calculate_current_streak(days: dict, today: date):
    """
    GitHub-style behavior:
    - If today has contributions, count backwards from today.
    - Otherwise count backwards from yesterday.
    """

    cursor = today

    if days.get(cursor, 0) == 0:
        cursor -= timedelta(days=1)

    streak_end = cursor

    while days.get(cursor, 0) > 0:
        cursor -= timedelta(days=1)

    streak_start = cursor + timedelta(days=1)

    if streak_start > streak_end:
        return 0, None, None

    count = (streak_end - streak_start).days + 1

    return count, streak_start, streak_end


def calculate_longest_streak(days: dict):
    longest = 0
    longest_start = None
    longest_end = None

    current = 0
    current_start = None

    for day in sorted(days):
        if days[day] > 0:
            if current == 0:
                current_start = day

            current += 1

            if current > longest:
                longest = current
                longest_start = current_start
                longest_end = day
        else:
            current = 0
            current_start = None

    return longest, longest_start, longest_end


def format_date(value):
    if value is None:
        return "—"

    return value.strftime("%b %d, %Y")


def range_label(start, end):
    if not start or not end:
        return "No active streak"

    if start == end:
        return format_date(start)

    return f"{format_date(start)} → {format_date(end)}"


def generate_svg(
    total,
    current,
    current_start,
    current_end,
    longest,
    longest_start,
    longest_end,
):
    width = 720
    height = 195

    current_range = escape(range_label(current_start, current_end))
    longest_range = escape(range_label(longest_start, longest_end))

    return f"""<svg
  xmlns="http://www.w3.org/2000/svg"
  width="{width}"
  height="{height}"
  viewBox="0 0 {width} {height}"
  role="img"
  aria-label="GitHub contribution streak"
>
  <style>
    .background {{
      fill: #0D1117;
    }}

    .border {{
      fill: none;
      stroke: #30363D;
      stroke-width: 1;
    }}

    .divider {{
      stroke: #30363D;
      stroke-width: 1;
    }}

    .value {{
      fill: #C9D1D9;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
      font-size: 30px;
      font-weight: 600;
    }}

    .accent {{
      fill: #00D9FF;
    }}

    .label {{
      fill: #00D9FF;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
      font-size: 14px;
      font-weight: 600;
    }}

    .date {{
      fill: #8B949E;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
      font-size: 11px;
    }}
  </style>

  <rect
    class="background"
    x="0.5"
    y="0.5"
    width="{width - 1}"
    height="{height - 1}"
    rx="8"
  />

  <rect
    class="border"
    x="0.5"
    y="0.5"
    width="{width - 1}"
    height="{height - 1}"
    rx="8"
  />

  <line class="divider" x1="240" y1="38" x2="240" y2="157"/>
  <line class="divider" x1="480" y1="38" x2="480" y2="157"/>

  <!-- Total Contributions -->
  <text
    class="value"
    x="120"
    y="87"
    text-anchor="middle"
  >
    {total:,}
  </text>

  <text
    class="label"
    x="120"
    y="116"
    text-anchor="middle"
  >
    Total Contributions
  </text>

  <text
    class="date"
    x="120"
    y="139"
    text-anchor="middle"
  >
    Last 365 days
  </text>

  <!-- Current Streak -->
  <text
    class="value accent"
    x="360"
    y="87"
    text-anchor="middle"
  >
    {current}
  </text>

  <text
    class="label"
    x="360"
    y="116"
    text-anchor="middle"
  >
    Current Streak
  </text>

  <text
    class="date"
    x="360"
    y="139"
    text-anchor="middle"
  >
    {current_range}
  </text>

  <!-- Longest Streak -->
  <text
    class="value"
    x="600"
    y="87"
    text-anchor="middle"
  >
    {longest}
  </text>

  <text
    class="label"
    x="600"
    y="116"
    text-anchor="middle"
  >
    Longest Streak
  </text>

  <text
    class="date"
    x="600"
    y="139"
    text-anchor="middle"
  >
    {longest_range}
  </text>
</svg>
"""


def main():
    days, total, today = get_contributions()

    current, current_start, current_end = calculate_current_streak(
        days,
        today,
    )

    longest, longest_start, longest_end = calculate_longest_streak(days)

    svg = generate_svg(
        total=total,
        current=current,
        current_start=current_start,
        current_end=current_end,
        longest=longest,
        longest_start=longest_start,
        longest_end=longest_end,
    )

    OUTPUT.write_text(svg, encoding="utf-8")

    print(f"Generated: {OUTPUT}")
    print(f"Total contributions: {total}")
    print(f"Current streak: {current}")
    print(f"Longest streak: {longest}")


if __name__ == "__main__":
    main()
