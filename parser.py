"""Robust Instagram data-export parser (HTML + JSON, old and new layouts)."""

from __future__ import annotations

import json
import re
import zipfile
from datetime import datetime
from typing import Any
from urllib.parse import unquote, urlparse

from bs4 import BeautifulSoup

# Known Instagram export filenames → logical list keys
FILE_MAP = {
    "followers": "Takipçiler",
    "following": "Takip Ettiklerim",
    "close_friends": "Yakın Arkadaşlar",
    "profiles_you've_favorited": "Favoriler",
    "blocked_profiles": "Engellenenler",
    "restricted_profiles": "Kısıtlananlar",
    "follow_requests_you've_received": "Gelen İstekler",
    "pending_follow_requests": "Gelen İstekler",
    "recent_follow_requests": "Gönderilen İstekler",
    "removed_suggestions": "Kaldırılan Öneriler",
    "recently_unfollowed_profiles": "Çıkan Takipçiler",
}

USER_ENTRY = tuple[str, str, str]  # username, url, date


def _normalize_username(raw: str) -> str:
    name = (raw or "").strip()
    if name.startswith("@"):
        name = name[1:]
    name = name.split("?")[0].strip().rstrip("/")
    return name.lower()


def _username_from_href(href: str) -> str | None:
    if not href:
        return None
    href = unquote(href.strip())
    # Common patterns: /username, /_u/username, www.instagram.com/username
    m = re.search(
        r"(?:instagram\.com)/(?:_u/)?([A-Za-z0-9._]+)/?(?:\?|$)",
        href,
        re.I,
    )
    if m:
        user = m.group(1)
        if user.lower() in {"p", "reel", "reels", "stories", "explore", "accounts"}:
            return None
        return _normalize_username(user)
    path = urlparse(href).path.strip("/")
    if path.startswith("_u/"):
        path = path[3:]
    if path and "/" not in path and re.fullmatch(r"[A-Za-z0-9._]+", path):
        return _normalize_username(path)
    return None


def _format_timestamp(ts: Any) -> str:
    try:
        if isinstance(ts, str) and ts.isdigit():
            ts = int(ts)
        if isinstance(ts, (int, float)):
            # ms vs s
            if ts > 1e12:
                ts = ts / 1000
            return datetime.fromtimestamp(ts).strftime("%d %b %Y %H:%M")
    except (OSError, OverflowError, ValueError, TypeError):
        pass
    return str(ts) if ts is not None else ""


def _parse_display_date(text: str) -> str:
    text = (text or "").strip()
    if not text:
        return ""
    # Already a human date from HTML export
    for fmt in (
        "%b %d, %Y %I:%M %p",
        "%B %d, %Y %I:%M %p",
        "%b %d, %Y, %I:%M %p",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%d %H:%M:%S",
        "%d.%m.%Y %H:%M",
    ):
        try:
            cleaned = text.replace("\u202f", " ").replace("  ", " ").strip()
            dt = datetime.strptime(cleaned, fmt)
            return dt.strftime("%d %b %Y %H:%M")
        except ValueError:
            continue
    return text


def _logical_key_from_name(name: str) -> str | None:
    base = name.rsplit("/", 1)[-1].lower()
    base = re.sub(r"\.(html|json|js)$", "", base)
    # followers_1, followers_2, ...
    if re.fullmatch(r"followers(?:_\d+)?", base):
        return "Takipçiler"
    for prefix, key in FILE_MAP.items():
        if base == prefix or base.startswith(prefix + "_"):
            return key
    return None


def _extract_users_from_json_obj(data: Any) -> list[USER_ENTRY]:
    users: list[USER_ENTRY] = []
    seen: set[str] = set()

    def add(username: str | None, href: str = "", ts: Any = None) -> None:
        if not username:
            return
        username = _normalize_username(username)
        if not username or username in seen:
            return
        seen.add(username)
        url = href or f"https://www.instagram.com/{username}/"
        users.append((username, url, _format_timestamp(ts) if ts else ""))

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            # Classic Instagram relationship entry
            sld = node.get("string_list_data")
            title = node.get("title") or node.get("name") or ""
            if isinstance(sld, list) and sld:
                for item in sld:
                    if not isinstance(item, dict):
                        continue
                    href = item.get("href") or item.get("link") or ""
                    value = item.get("value") or item.get("username") or title
                    ts = item.get("timestamp") or item.get("time")
                    uname = _username_from_href(href) if href else None
                    if not uname and value:
                        uname = _normalize_username(str(value))
                    add(uname, href, ts)
                return
            # Flat dict shapes
            if "username" in node or "value" in node:
                href = node.get("href") or node.get("link") or ""
                value = node.get("username") or node.get("value") or title
                ts = node.get("timestamp") or node.get("time")
                uname = _username_from_href(href) if href else None
                if not uname and value:
                    uname = _normalize_username(str(value))
                add(uname, href, ts)
                return
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(data)
    return users


def extract_users_from_json(raw: bytes | str) -> list[USER_ENTRY]:
    if isinstance(raw, bytes):
        text = raw.decode("utf-8-sig", errors="replace")
    else:
        text = raw
    text = text.strip()
    if not text:
        return []
    # Some exports wrap JSON in JS assignment
    if text.startswith("window.") or "=" in text[:40]:
        eq = text.find("=")
        if eq != -1:
            text = text[eq + 1 :].strip().rstrip(";")
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return []
    return _extract_users_from_json_obj(data)


def extract_users_from_html(raw: bytes | str) -> list[USER_ENTRY]:
    if isinstance(raw, bytes):
        html = raw.decode("utf-8-sig", errors="replace")
    else:
        html = raw
    soup = BeautifulSoup(html, "html.parser")
    users: list[USER_ENTRY] = []
    seen: set[str] = set()

    # Strategy 1: legacy class _a6-p / _a6-h containers
    containers = soup.find_all("div", class_=re.compile(r"^_a6-p$|^_a6-h$"))
    if not containers:
        # Strategy 2: any block that looks like a profile row
        containers = soup.find_all("div", class_=True)

    for container in containers:
        a_tag = container.find("a", href=True)
        if not a_tag:
            continue
        href = a_tag.get("href", "")
        username = _username_from_href(href) or _normalize_username(a_tag.get_text(" ", strip=True))
        if not username or username in seen:
            continue
        if "instagram.com" not in href and not href.startswith("http"):
            # Relative / local export links still OK if username looks valid
            if not re.fullmatch(r"[a-z0-9._]+", username):
                continue
        date = ""
        # Prefer next sibling div / following text that looks like a date
        date_div = a_tag.find_next("div")
        if date_div and date_div is not a_tag and not date_div.find("a"):
            date = _parse_display_date(date_div.get_text(" ", strip=True))
        if not date:
            parent = a_tag.parent
            if parent:
                texts = [t.strip() for t in parent.stripped_strings if t.strip() != username]
                for t in texts:
                    if re.search(r"\d{4}|\d{1,2}[./]\d{1,2}|am|pm|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec", t, re.I):
                        date = _parse_display_date(t)
                        break
        seen.add(username)
        url = href if href.startswith("http") else f"https://www.instagram.com/{username}/"
        users.append((username, url, date))

    # Strategy 3: fallback — all Instagram profile links in the document
    if not users:
        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"]
            username = _username_from_href(href)
            if not username or username in seen:
                continue
            date = ""
            nxt = a_tag.find_next(string=True)
            if nxt:
                candidate = str(nxt).strip()
                if candidate and candidate.lower() != username:
                    date = _parse_display_date(candidate)
            seen.add(username)
            users.append((username, href if href.startswith("http") else f"https://www.instagram.com/{username}/", date))

    return users


def compare_lists(main_list: list[USER_ENTRY], compare_list: list[USER_ENTRY]) -> list[USER_ENTRY]:
    compare_usernames = {u[0] for u in compare_list}
    return [u for u in main_list if u[0] not in compare_usernames]


def merge_user_lists(*lists: list[USER_ENTRY]) -> list[USER_ENTRY]:
    seen: set[str] = set()
    out: list[USER_ENTRY] = []
    for lst in lists:
        for entry in lst:
            if entry[0] in seen:
                continue
            seen.add(entry[0])
            out.append(entry)
    return out


def extract_username_from_zip_name(filename: str) -> str:
    base = filename.rsplit("/", 1)[-1]
    if base.lower().startswith("instagram-"):
        parts = base.split("-")
        if len(parts) > 1 and parts[1] and not parts[1].isdigit():
            return parts[1]
    return "Instagram"


def parse_instagram_zip(zip_path: str) -> dict[str, Any]:
    """Parse an Instagram data download ZIP into analysis-ready lists."""
    lists: dict[str, list[USER_ENTRY]] = {key: [] for key in set(FILE_MAP.values())}
    lists.setdefault("Takipçiler", [])
    lists.setdefault("Takip Ettiklerim", [])

    found_files: list[str] = []

    with zipfile.ZipFile(zip_path, "r") as zf:
        names = zf.namelist()
        for name in names:
            if name.endswith("/") or "__MACOSX" in name or name.startswith("."):
                continue
            key = _logical_key_from_name(name)
            if not key:
                # Also accept nested paths containing followers_and_following
                lower = name.lower()
                if "followers_and_following" not in lower and "connections" not in lower:
                    continue
                key = _logical_key_from_name(name)
                if not key:
                    continue

            lower_name = name.lower()
            try:
                raw = zf.read(name)
            except KeyError:
                continue

            users: list[USER_ENTRY] = []
            if lower_name.endswith((".json", ".js")):
                users = extract_users_from_json(raw)
            elif lower_name.endswith((".html", ".htm")):
                users = extract_users_from_html(raw)
            else:
                continue

            if users:
                found_files.append(name)
                lists[key] = merge_user_lists(lists.get(key, []), users)

    followers = lists.get("Takipçiler", [])
    following = lists.get("Takip Ettiklerim", [])
    lists["Beni Geri Takip Etmeyenler"] = compare_lists(following, followers)
    lists["Benim Geri Takip Etmediklerim"] = compare_lists(followers, following)

    username = extract_username_from_zip_name(zip_path)
    # Prefer username inferred from following/followers if zip name is generic
    if username == "Instagram":
        for entry_name in found_files:
            # path often contains personal_information or username folder
            m = re.search(r"instagram-([A-Za-z0-9._]+)-", entry_name, re.I)
            if m:
                username = m.group(1)
                break

    return {
        "username": username,
        "lists": {k: [{"username": u, "url": url, "date": d} for u, url, d in v] for k, v in lists.items()},
        "counts": {k: len(v) for k, v in lists.items()},
        "files_found": found_files,
        "has_followers": len(followers) > 0,
        "has_following": len(following) > 0,
    }


def sort_users(
    users: list[dict[str, str]],
    option: str = "newest",
) -> list[dict[str, str]]:
    def parse_date(date_str: str) -> datetime:
        for fmt in ("%d %b %Y %H:%M", "%b %d, %Y %I:%M %p", "%Y-%m-%d %H:%M:%S"):
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue
        return datetime.min

    if option == "oldest":
        return sorted(users, key=lambda x: parse_date(x.get("date") or ""))
    if option == "az":
        return sorted(users, key=lambda x: (x.get("username") or "").lower())
    if option == "za":
        return sorted(users, key=lambda x: (x.get("username") or "").lower(), reverse=True)
    # newest default
    return sorted(users, key=lambda x: parse_date(x.get("date") or ""), reverse=True)
