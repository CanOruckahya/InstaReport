"""InstaRapor — Instagram follower / unfollow analysis web app."""

from __future__ import annotations

import json
import os
import secrets
import tempfile
import uuid
from datetime import datetime
from pathlib import Path

from flask import Flask, flash, redirect, render_template, request, session, url_for
from werkzeug.utils import secure_filename

from parser import parse_instagram_zip

APP_ROOT = Path(__file__).resolve().parent
HISTORY_FILE = APP_ROOT / "_insta_rapor_history.json"
UPLOAD_DIR = APP_ROOT / "uploads"
REPORT_DIR = APP_ROOT / "reports"
MAX_CONTENT = 200 * 1024 * 1024  # 200 MB

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", secrets.token_hex(16))
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT
UPLOAD_DIR.mkdir(exist_ok=True)
REPORT_DIR.mkdir(exist_ok=True)

MAIN_TABS = [
    ("Beni Geri Takip Etmeyenler", "not_following_back"),
    ("Benim Geri Takip Etmediklerim", "not_followed_back"),
    ("Çıkan Takipçiler", "unfollowed"),
    ("Yakın Arkadaşlar", "close_friends"),
    ("Favoriler", "favorites"),
]

OTHER_TABS = [
    ("Engellenenler", "blocked"),
    ("Kısıtlananlar", "restricted"),
    ("Gelen İstekler", "incoming"),
    ("Gönderilen İstekler", "outgoing"),
    ("Kaldırılan Öneriler", "removed"),
]


def load_history() -> list[dict]:
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (OSError, json.JSONDecodeError):
        return []


def save_history_entry(username: str, followers: list[str], report_label: str) -> dict:
    history = load_history()
    now = datetime.now().strftime("%d.%m.%Y %H:%M")
    entry = {
        "date": now,
        "label": report_label,
        "account": username,
        "usernames": followers,
        "count": len(followers),
    }

    prev = None
    for rec in reversed(history):
        if rec.get("account") == username:
            prev = rec
            break
    if prev is None and history:
        prev = history[-1]

    gained: list[str] = []
    lost: list[str] = []
    if prev:
        old = set(prev.get("usernames") or [])
        new = set(followers)
        gained = sorted(new - old)
        lost = sorted(old - new)

    identical = (
        history
        and history[-1].get("usernames") == followers
        and history[-1].get("account") == username
    )
    if not identical:
        history.append(entry)
        history = history[-15:]
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)

    return {
        "saved": not identical,
        "previous_date": prev.get("date") if prev else None,
        "previous_count": prev.get("count") if prev else None,
        "gained": gained,
        "lost": lost,
        "gained_count": len(gained),
        "lost_count": len(lost),
        "is_first": prev is None,
    }


def store_report(data: dict) -> str:
    report_id = uuid.uuid4().hex
    path = REPORT_DIR / f"{report_id}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    return report_id


def load_report(report_id: str | None) -> dict | None:
    if not report_id:
        return None
    path = REPORT_DIR / f"{report_id}.json"
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def delete_report(report_id: str | None) -> None:
    if not report_id:
        return
    path = REPORT_DIR / f"{report_id}.json"
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/analyze", methods=["POST"])
def analyze():
    file = request.files.get("zipfile")
    if not file or not file.filename:
        flash("Lütfen Instagram ZIP dosyanızı seçin.", "error")
        return redirect(url_for("index"))

    filename = secure_filename(file.filename)
    if not filename.lower().endswith(".zip"):
        flash("Sadece .zip dosyası yükleyebilirsiniz.", "error")
        return redirect(url_for("index"))

    save_history = request.form.get("save_history") == "on"

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".zip", dir=UPLOAD_DIR)
    try:
        file.save(tmp.name)
        tmp.close()
        result = parse_instagram_zip(tmp.name)
    except Exception as exc:  # noqa: BLE001
        flash(f"ZIP okunamadı: {exc}", "error")
        return redirect(url_for("index"))
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass

    if not result["has_followers"] and not result["has_following"]:
        flash(
            "ZIP içinde takipçi / takip listesi bulunamadı. "
            "Instagram → Ayarlar → Bilgilerinizi indirin → Bağlantılar bölümünü içeren arşivi yükleyin. "
            "HTML veya JSON formatı desteklenir.",
            "error",
        )
        return redirect(url_for("index"))

    # Prefer username from uploaded filename when parser got a generic one
    if result["username"] == "Instagram" and filename.lower().startswith("instagram-"):
        parts = filename.split("-")
        if len(parts) > 1 and parts[1] and not parts[1].isdigit():
            result["username"] = parts[1]

    followers = [u["username"] for u in result["lists"].get("Takipçiler", [])]
    comparison = None
    if save_history:
        comparison = save_history_entry(
            result["username"],
            followers,
            f"{result['username']} · {datetime.now().strftime('%d.%m.%Y %H:%M')}",
        )
    else:
        history = load_history()
        prev = None
        for rec in reversed(history):
            if rec.get("account") == result["username"]:
                prev = rec
                break
        if prev:
            old = set(prev.get("usernames") or [])
            new = set(followers)
            gained = sorted(new - old)
            lost = sorted(old - new)
            comparison = {
                "saved": False,
                "previous_date": prev.get("date"),
                "previous_count": prev.get("count"),
                "gained": gained,
                "lost": lost,
                "gained_count": len(gained),
                "lost_count": len(lost),
                "is_first": False,
            }

    report = {
        "username": result["username"],
        "lists": result["lists"],
        "counts": result["counts"],
        "files_found": result["files_found"],
        "analyzed_at": datetime.now().strftime("%d.%m.%Y %H:%M"),
        "comparison": comparison,
    }

    # Drop previous report file for this session
    delete_report(session.get("report_id"))
    session["report_id"] = store_report(report)
    return redirect(url_for("report"))


@app.route("/report")
def report():
    data = load_report(session.get("report_id"))
    if not data:
        flash("Önce bir Instagram ZIP dosyası yükleyin.", "error")
        return redirect(url_for("index"))
    return render_template(
        "report.html",
        report=data,
        main_tabs=MAIN_TABS,
        other_tabs=OTHER_TABS,
    )


@app.route("/clear")
def clear():
    delete_report(session.get("report_id"))
    session.pop("report_id", None)
    flash("Rapor temizlendi. Yeni bir ZIP yükleyebilirsiniz.", "info")
    return redirect(url_for("index"))


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
