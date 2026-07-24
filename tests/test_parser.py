"""Unit tests for Instagram export parser and list comparison."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

from parser import (
    compare_lists,
    extract_users_from_html,
    extract_users_from_json,
    parse_instagram_zip,
)


SAMPLE = Path(__file__).resolve().parent / "fixtures"


def _write_zip(path: Path, files: dict[str, bytes | str]) -> None:
    with zipfile.ZipFile(path, "w") as zf:
        for name, content in files.items():
            data = content.encode("utf-8") if isinstance(content, str) else content
            zf.writestr(name, data)


def test_json_followers_array(tmp_path: Path):
    payload = [
        {
            "string_list_data": [
                {
                    "href": "https://www.instagram.com/_u/alice",
                    "value": "alice",
                    "timestamp": 1700000000,
                }
            ]
        },
        {
            "string_list_data": [
                {
                    "href": "https://www.instagram.com/bob",
                    "value": "bob",
                    "timestamp": 1700001000,
                }
            ]
        },
    ]
    users = extract_users_from_json(json.dumps(payload))
    assert [u[0] for u in users] == ["alice", "bob"]


def test_json_following_wrapped():
    payload = {
        "relationships_following": [
            {
                "title": "carol",
                "string_list_data": [
                    {
                        "href": "https://www.instagram.com/carol",
                        "value": "carol",
                        "timestamp": 1700002000,
                    }
                ],
            }
        ]
    }
    users = extract_users_from_json(json.dumps(payload))
    assert users[0][0] == "carol"


def test_html_legacy_a6p():
    html = """
    <html><body>
      <div class="_a6-p">
        <div><a target="_blank" href="https://www.instagram.com/_u/dave">dave</a></div>
        <div>Jul 18, 2025 11:23 am</div>
      </div>
      <div class="_a6-p">
        <div><a href="https://www.instagram.com/erin">erin</a></div>
        <div>Jan 01, 2024 9:00 am</div>
      </div>
    </body></html>
    """
    users = extract_users_from_html(html)
    assert [u[0] for u in users] == ["dave", "erin"]
    assert users[0][2]  # date parsed


def test_compare_not_following_back():
    following = [("alice", "", ""), ("bob", "", "")]
    followers = [("alice", "", ""), ("carol", "", "")]
    not_back = compare_lists(following, followers)
    assert [u[0] for u in not_back] == ["bob"]
    you_dont = compare_lists(followers, following)
    assert [u[0] for u in you_dont] == ["carol"]


def test_parse_zip_json_and_html(tmp_path: Path):
    followers_json = [
        {
            "string_list_data": [
                {"href": "https://www.instagram.com/alice", "value": "alice", "timestamp": 1700000000}
            ]
        },
        {
            "string_list_data": [
                {"href": "https://www.instagram.com/bob", "value": "bob", "timestamp": 1700000100}
            ]
        },
    ]
    following_html = """
    <html><body>
      <div class="_a6-p">
        <div><a href="https://www.instagram.com/alice">alice</a></div>
        <div>Jul 18, 2025 11:23 am</div>
      </div>
      <div class="_a6-p">
        <div><a href="https://www.instagram.com/zoe">zoe</a></div>
        <div>Jul 19, 2025 11:23 am</div>
      </div>
    </body></html>
    """
    zip_path = tmp_path / "instagram-demo-2025-01-01.zip"
    _write_zip(
        zip_path,
        {
            "connections/followers_and_following/followers_1.json": json.dumps(followers_json),
            "connections/followers_and_following/following.html": following_html,
            "connections/followers_and_following/recently_unfollowed_profiles.json": json.dumps(
                [
                    {
                        "string_list_data": [
                            {
                                "href": "https://www.instagram.com/gone_user",
                                "value": "gone_user",
                                "timestamp": 1700000500,
                            }
                        ]
                    }
                ]
            ),
        },
    )
    result = parse_instagram_zip(str(zip_path))
    assert result["has_followers"]
    assert result["has_following"]
    assert result["counts"]["Takipçiler"] == 2
    assert result["counts"]["Takip Ettiklerim"] == 2
    # following alice+zoe, followers alice+bob → zoe not following back, bob not followed back
    names_nf = {u["username"] for u in result["lists"]["Beni Geri Takip Etmeyenler"]}
    names_yn = {u["username"] for u in result["lists"]["Benim Geri Takip Etmediklerim"]}
    assert names_nf == {"zoe"}
    assert names_yn == {"bob"}
    assert result["counts"]["Çıkan Takipçiler"] == 1
    assert result["username"] == "demo"


def test_multi_follower_files(tmp_path: Path):
    f1 = [{"string_list_data": [{"href": "https://www.instagram.com/a", "value": "a", "timestamp": 1}]}]
    f2 = [{"string_list_data": [{"href": "https://www.instagram.com/b", "value": "b", "timestamp": 2}]}]
    zip_path = tmp_path / "instagram-userx-2026.zip"
    _write_zip(
        zip_path,
        {
            "connections/followers_and_following/followers_1.json": json.dumps(f1),
            "connections/followers_and_following/followers_2.json": json.dumps(f2),
            "connections/followers_and_following/following.json": json.dumps(
                {"relationships_following": []}
            ),
        },
    )
    result = parse_instagram_zip(str(zip_path))
    assert result["counts"]["Takipçiler"] == 2
