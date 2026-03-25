#!/usr/bin/env python3
"""Generate a personal newspaper as a static HTML page."""

import json
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

import feedparser
import requests
import yaml
from dateutil import parser as dateparser
from jinja2 import Environment, FileSystemLoader


def load_config():
    config_path = Path(__file__).parent / "config.yaml"
    with open(config_path) as f:
        return yaml.safe_load(f)


def fetch_weather(config):
    """Fetch weather, pollen, and air quality for Cardiff from Open-Meteo."""
    lat = config["weather"]["latitude"]
    lon = config["weather"]["longitude"]

    # Current weather + daily forecast
    weather_url = (
        f"https://api.open-meteo.com/v1/forecast?"
        f"latitude={lat}&longitude={lon}"
        f"&current=temperature_2m,weather_code,wind_speed_10m,relative_humidity_2m"
        f"&daily=temperature_2m_max,temperature_2m_min,weather_code,precipitation_probability_max"
        f"&timezone=Europe%2FLondon&forecast_days=1"
    )

    # Air quality
    aqi_url = (
        f"https://air-quality-api.open-meteo.com/v1/air-quality?"
        f"latitude={lat}&longitude={lon}"
        f"&current=european_aqi,grass_pollen,birch_pollen,alder_pollen"
        f"&timezone=Europe%2FLondon"
    )

    weather_data = {}
    try:
        r = requests.get(weather_url, timeout=10)
        r.raise_for_status()
        data = r.json()
        current = data.get("current", {})
        daily = data.get("daily", {})

        weather_codes = {
            0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
            45: "Foggy", 48: "Rime fog", 51: "Light drizzle", 53: "Drizzle",
            55: "Dense drizzle", 61: "Slight rain", 63: "Moderate rain",
            65: "Heavy rain", 71: "Slight snow", 73: "Moderate snow",
            75: "Heavy snow", 80: "Slight showers", 81: "Moderate showers",
            82: "Violent showers", 95: "Thunderstorm",
        }

        weather_data = {
            "temperature": current.get("temperature_2m"),
            "condition": weather_codes.get(current.get("weather_code"), "Unknown"),
            "wind_speed": current.get("wind_speed_10m"),
            "humidity": current.get("relative_humidity_2m"),
            "high": daily.get("temperature_2m_max", [None])[0],
            "low": daily.get("temperature_2m_min", [None])[0],
            "rain_chance": daily.get("precipitation_probability_max", [None])[0],
        }
    except Exception as e:
        print(f"Warning: Could not fetch weather: {e}", file=sys.stderr)
        weather_data = {"error": True}

    # Air quality & pollen
    try:
        r = requests.get(aqi_url, timeout=10)
        r.raise_for_status()
        data = r.json()
        current_aqi = data.get("current", {})

        aqi_value = current_aqi.get("european_aqi")
        if aqi_value is not None:
            if aqi_value <= 20:
                aqi_label = "Good"
            elif aqi_value <= 40:
                aqi_label = "Fair"
            elif aqi_value <= 60:
                aqi_label = "Moderate"
            elif aqi_value <= 80:
                aqi_label = "Poor"
            else:
                aqi_label = "Very Poor"
        else:
            aqi_label = "N/A"

        pollen_values = [
            current_aqi.get("grass_pollen", 0) or 0,
            current_aqi.get("birch_pollen", 0) or 0,
            current_aqi.get("alder_pollen", 0) or 0,
        ]
        max_pollen = max(pollen_values)
        if max_pollen == 0:
            pollen_label = "None"
        elif max_pollen <= 10:
            pollen_label = "Low"
        elif max_pollen <= 30:
            pollen_label = "Moderate"
        elif max_pollen <= 60:
            pollen_label = "High"
        else:
            pollen_label = "Very High"

        weather_data["aqi"] = aqi_value
        weather_data["aqi_label"] = aqi_label
        weather_data["pollen"] = pollen_label
    except Exception as e:
        print(f"Warning: Could not fetch air quality: {e}", file=sys.stderr)
        weather_data.setdefault("aqi_label", "N/A")
        weather_data.setdefault("pollen", "N/A")

    return weather_data


def _format_published(entry):
    """Format published date nicely, e.g. 'Wed 25 Mar, 09:59'."""
    from time import mktime
    date_tuple = entry.get("published_parsed") or entry.get("updated_parsed")
    if date_tuple:
        try:
            dt = datetime.fromtimestamp(mktime(date_tuple))
            return dt.strftime("%a %d %b, %H:%M")
        except Exception:
            pass
    return entry.get("published", "")


def _parse_feed_entries(source):
    """Parse a single news source, returning a list of article dicts."""
    articles = []
    feed = feedparser.parse(source["url"])
    filter_tag = source.get("filter_tag", "").lower()
    max_articles = source.get("max_articles", 5)
    count = 0
    for entry in feed.entries:
        if count >= max_articles:
            break
        # Filter by tag if specified
        if filter_tag:
            entry_tags = [t.get("term", "").lower() for t in entry.get("tags", [])]
            if filter_tag not in entry_tags:
                continue
        count += 1
        image = None
        if "media_thumbnail" in entry and entry.media_thumbnail:
            image = entry.media_thumbnail[0].get("url")
        elif "media_content" in entry and entry.media_content:
            best = max(entry.media_content, key=lambda m: int(m.get("width", 0)))
            image = best.get("url")

        title = entry.get("title", "")
        # Google News appends " - Source Name" to titles
        if source.get("google_news") and " - " in title:
            title = title.rsplit(" - ", 1)[0]

        articles.append({
            "source": source["name"],
            "title": title,
            "summary": entry.get("summary", entry.get("description", "")),
            "link": entry.get("link", ""),
            "published": _format_published(entry),
            "image": image,
        })
    return articles


def fetch_news(config):
    """Fetch headlines from all news RSS feeds."""
    articles = []
    for source in config["news_sources"]:
        try:
            articles.extend(_parse_feed_entries(source))
        except Exception as e:
            print(f"Warning: Could not fetch {source['name']}: {e}", file=sys.stderr)
    return articles


def _detect_sport(article):
    """Detect sport name from URL path or title keywords."""
    import re
    # Try URL path: /sport/football/, /sport/snooker/ etc.
    url = article.get("link", "")
    m = re.search(r'/sport/([a-z-]+)', url)
    if m:
        sport = m.group(1).replace("-", " ").title()
        # Filter out generic paths
        if sport.lower() not in ("articles", "live", "av", "news"):
            return sport

    # Keyword fallback
    title = article.get("title", "").lower()
    sports = [
        "football", "cricket", "rugby", "tennis", "golf", "snooker",
        "boxing", "cycling", "athletics", "formula 1", "f1", "motorsport",
        "swimming", "basketball", "baseball", "hockey", "darts",
    ]
    for s in sports:
        if s in title:
            return s.title()
    return None


def fetch_section(config, key):
    """Fetch articles for a generic section (science, tech, etc.)."""
    articles = []
    for source in config.get(key, []):
        try:
            articles.extend(_parse_feed_entries(source))
        except Exception as e:
            print(f"Warning: Could not fetch {source['name']}: {e}", file=sys.stderr)
    return articles


def _group_by_source(articles):
    """Group articles by source, preserving order."""
    from collections import OrderedDict
    groups = OrderedDict()
    for article in articles:
        groups.setdefault(article["source"], []).append(article)
    return groups


def fetch_sport(config):
    """Fetch sport headlines with sport name detection."""
    articles = []
    for source in config.get("sports_sources", []):
        try:
            entries = _parse_feed_entries(source)
            for article in entries:
                article["sport"] = _detect_sport(article)
            articles.extend(entries)
        except Exception as e:
            print(f"Warning: Could not fetch {source['name']}: {e}", file=sys.stderr)
    return articles


def fetch_hacker_news(config):
    """Fetch top stories from Hacker News API."""
    num = config["hacker_news"]["num_stories"]
    stories = []
    try:
        r = requests.get("https://hacker-news.firebaseio.com/v0/topstories.json", timeout=10)
        r.raise_for_status()
        story_ids = r.json()[:num]

        for sid in story_ids:
            sr = requests.get(
                f"https://hacker-news.firebaseio.com/v0/item/{sid}.json", timeout=5
            )
            sr.raise_for_status()
            item = sr.json()
            stories.append({
                "title": item.get("title", ""),
                "url": item.get("url", f"https://news.ycombinator.com/item?id={sid}"),
                "score": item.get("score", 0),
                "comments": item.get("descendants", 0),
                "hn_link": f"https://news.ycombinator.com/item?id={sid}",
            })
    except Exception as e:
        print(f"Warning: Could not fetch Hacker News: {e}", file=sys.stderr)
    return stories


def _strip_ansi(text):
    """Remove ANSI escape codes from text."""
    import re
    return re.sub(r'\x1b\[[0-9;]*m', '', text)


def _parse_time_duration_hours(time_str):
    """Parse 'HH:MM - HH:MM' and return duration in hours, or None."""
    import re
    m = re.search(r'(\d{1,2}):(\d{2})\s*-\s*(\d{1,2}):(\d{2})', time_str)
    if not m:
        return None
    start = int(m.group(1)) * 60 + int(m.group(2))
    end = int(m.group(3)) * 60 + int(m.group(4))
    if end < start:
        end += 24 * 60
    return (end - start) / 60


def _parse_icalbuddy_output(output, exclude_titles=None):
    """Parse icalBuddy output into structured events."""
    import re
    exclude_titles = [t.lower() for t in (exclude_titles or [])]
    events = []
    current_time = None
    current_title = None

    for line in output.strip().split("\n"):
        line = _strip_ansi(line)
        if not line.strip():
            continue

        # Time lines are not indented, event details are indented
        if not line.startswith(" ") and not line.startswith("\t"):
            if current_time and current_title:
                events.append({"time": current_time, "title": current_title})
            current_time = line.strip()
            current_title = None
        else:
            stripped = line.strip()
            if stripped.startswith("location:") or stripped.startswith("url:"):
                continue
            if current_title is None:
                # Strip calendar name in parentheses at the end
                stripped = re.sub(r'\s*\([^)]+\)\s*$', '', stripped)
                current_title = stripped

    if current_time and current_title:
        events.append({"time": current_time, "title": current_title})

    # Filter excluded titles
    events = [e for e in events if e["title"].lower() not in exclude_titles]

    # Deduplicate by time+title
    seen = set()
    unique = []
    for e in events:
        key = (e["time"], e["title"])
        if key not in seen:
            seen.add(key)
            # If event is longer than 5 hours, treat as all-day
            duration = _parse_time_duration_hours(e["time"])
            if duration is not None and duration > 5:
                # Preserve date prefix if present (e.g. "Wed 25 Mar at 08:00 - 17:00")
                at_idx = e["time"].find(" at ")
                if at_idx > 0:
                    e["time"] = e["time"][:at_idx] + " — All day"
                else:
                    e["time"] = "All day"
            unique.append(e)

    return unique


def fetch_calendar(config):
    """Fetch calendar events using icalBuddy (macOS)."""
    if not config["calendar"]["enabled"]:
        return {"today": [], "week": []}

    today_events = []
    week_events = []
    exclude = config["calendar"].get("exclude_calendars", "")

    try:
        # Today's events
        cmd = ["icalBuddy", "-nrd",
               "-ea", "-df", "%H:%M", "-tf", "%H:%M",
               "-iep", "title,datetime",
               "-po", "datetime,title",
               "-b", "",
               "eventsToday"]
        if exclude:
            cmd.extend(["-ec", exclude])

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            today_events = _parse_icalbuddy_output(result.stdout, exclude_titles=["Stand-up"])

        # Events until end of Sunday
        today = datetime.now()
        days_until_sunday = (6 - today.weekday()) % 7
        if days_until_sunday == 0:
            days_until_sunday = 7  # If it's Sunday, show next week
        cmd2 = ["icalBuddy", "-nrd",
                "-ea", "-df", "%a %d %b", "-tf", "%H:%M",
                "-iep", "title,datetime",
                "-po", "datetime,title",
                "-b", "",
                f"eventsToday+{days_until_sunday}"]
        if exclude:
            cmd2.extend(["-ec", exclude])

        result2 = subprocess.run(cmd2, capture_output=True, text=True, timeout=10)
        if result2.returncode == 0:
            week_events = _parse_icalbuddy_output(result2.stdout, exclude_titles=["Stand-up"])

    except FileNotFoundError:
        print("Warning: icalBuddy not found. Install with: brew install icalbuddy", file=sys.stderr)
    except Exception as e:
        print(f"Warning: Could not fetch calendar: {e}", file=sys.stderr)

    return {"today": today_events[:8], "week": week_events[:15]}


def fetch_rss_feeds(config):
    """Fetch articles from configured RSS feeds, published in the last 24 hours."""
    from time import mktime
    cutoff = datetime.now() - timedelta(hours=24)
    articles = []
    for feed_config in config.get("rss_feeds", []):
        try:
            feed = feedparser.parse(feed_config["url"])
            for entry in feed.entries[:10]:
                # Check published or updated date
                date_tuple = entry.get("published_parsed") or entry.get("updated_parsed")
                if date_tuple:
                    entry_dt = datetime.fromtimestamp(mktime(date_tuple))
                    if entry_dt < cutoff:
                        continue
                articles.append({
                    "source": feed_config["name"],
                    "title": entry.get("title", ""),
                    "link": entry.get("link", ""),
                    "summary": entry.get("summary", "")[:150],
                })
        except Exception as e:
            print(f"Warning: Could not fetch {feed_config['name']}: {e}", file=sys.stderr)
    return articles[:12]


def generate_briefing(config, data):
    """Use Claude to generate a short briefing from all content."""
    import os

    briefing_config = config.get("briefing", {})
    if not briefing_config.get("enabled"):
        return ""

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("Warning: ANTHROPIC_API_KEY not set, skipping briefing", file=sys.stderr)
        return ""

    # Build a digest of all content for the LLM
    lines = []
    for article in data.get("news", []):
        lines.append(f"[News / {article['source']}] {article['title']}: {article.get('summary', '')}")
    for article in data.get("wales", []):
        lines.append(f"[Wales / {article['source']}] {article['title']}")
    for article in data.get("sport", []):
        sport_tag = f" ({article.get('sport', '')})" if article.get("sport") else ""
        lines.append(f"[Sport{sport_tag} / {article['source']}] {article['title']}")
    for article in data.get("science", []):
        lines.append(f"[Science / {article['source']}] {article['title']}")
    for article in data.get("tech", []):
        lines.append(f"[Tech / {article['source']}] {article['title']}")
    for story in data.get("hacker_news", []):
        lines.append(f"[Tech / Hacker News] {story['title']} ({story['score']} pts)")
    for source, articles in data.get("papers", {}).items():
        for article in articles:
            lines.append(f"[Papers / {source}] {article['title']}")

    content_digest = "\n".join(lines)
    user_context = os.environ.get("BRIEFING_CONTEXT", briefing_config.get("context", ""))

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=600,
            messages=[{
                "role": "user",
                "content": f"""You are writing a short personal briefing for a daily newspaper.
Given the reader's context and today's content, write two or three short paragraphs
summarising the most important, surprising, or personally relevant stories.
Write in a natural, conversational tone — like a knowledgeable friend giving a quick overview of the day.
No bullet points, no headings, no preamble. Just the paragraphs.

Reader context:
{user_context}

Today's content:
{content_digest}"""
            }],
        )
        return message.content[0].text
    except Exception as e:
        print(f"Warning: Could not generate briefing: {e}", file=sys.stderr)
        return ""


def generate_html(config, data):
    """Render the newspaper template."""
    env = Environment(loader=FileSystemLoader(Path(__file__).parent / "templates"))
    template = env.get_template("newspaper.html")

    now = datetime.now()
    if now.hour < 12:
        edition = "Morning Edition"
    elif now.hour < 18:
        edition = "Afternoon Edition"
    else:
        edition = "Evening Edition"

    html = template.render(
        newspaper_name=config["newspaper_name"],
        tagline=config["tagline"],
        edition=edition,
        date=now.strftime("%A, %B %d, %Y"),
        generated_at=now.strftime("%H:%M"),
        city=config["weather"]["city"],
        weather=data["weather"],
        news=data["news"],
        wales=data["wales"],
        science=data["science"],
        tech=data["tech"],
        sport=data["sport"],
        hacker_news=data["hacker_news"],
        calendar=data["calendar"],
        rss_articles=data["rss_articles"],
        papers=data["papers"],
        briefing=data["briefing"],
    )

    output_path = Path(__file__).parent / config["output"]["file"]
    output_path.write_text(html)
    print(f"Generated {output_path}")


def main():
    config = load_config()

    # Add PyYAML to handle config
    print("Fetching data...")

    data = {
        "weather": fetch_weather(config),
        "news": fetch_news(config),
        "wales": fetch_section(config, "wales_sources"),
        "science": fetch_section(config, "science_sources"),
        "tech": fetch_section(config, "tech_sources"),
        "sport": fetch_sport(config),
        "hacker_news": fetch_hacker_news(config),
        "calendar": fetch_calendar(config),
        "rss_articles": fetch_rss_feeds(config),
        "papers": _group_by_source(fetch_section(config, "papers_sources")),
    }

    data["briefing"] = generate_briefing(config, data)

    generate_html(config, data)


if __name__ == "__main__":
    main()
