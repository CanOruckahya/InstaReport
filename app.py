import ctypes.wintypes
import datetime
import glob
import io
import json
import os
import platform
import re
import urllib.parse
import webbrowser
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from bs4 import BeautifulSoup
import matplotlib
matplotlib.use("Agg")  # Tkinter ile uyumlu olması için
import matplotlib.pyplot as plt
from PIL import Image, ImageTk


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HISTORY_FILE = os.path.join(BASE_DIR, "_insta_rapor_history.json")
SNAPSHOTS_DIR = os.path.join(BASE_DIR, "snapshots")
WEB_COLLECTOR_JS_PATH = os.path.join(BASE_DIR, "web_collector.js")
BOOKMARKLET_HTML_PATH = os.path.join(BASE_DIR, "Tarayici_Asistani_Kurulum.html")

TAB_LABELS = {
    "Beni_Geri_Takip_Etmeyenler": "Beni Geri Takip Etmeyenler",
    "Benim_Geri_Takip_Etmediklerim": "Benim Geri Takip Etmediklerim",
    "Yakin_Arkadaslar": "Yakın Arkadaşlar",
    "Favoriler": "Favoriler",
    "Engellenenler": "Engellenenler",
    "Kisitlananlar": "Kısıtlananlar",
    "Gelen_Istekler": "Gelen İstekler",
    "Gonderilen_Istekler": "Gönderilen İstekler",
    "Kaldirilan_Oneriler": "Kaldırılan Öneriler",
    "Cikan_Takipciler": "Çıkan / Takipten Çıkılanlar",
}

OFFICIAL_LIST_FILE_MAP = {
    "Takipciler": ["followers"],
    "Takip_Ettiklerim": ["following"],
    "Yakin_Arkadaslar": ["close_friends"],
    "Favoriler": ["profiles_you've_favorited"],
    "Engellenenler": ["blocked_profiles"],
    "Kisitlananlar": ["restricted_profiles"],
    "Gelen_Istekler": ["follow_requests_you've_received"],
    "Gonderilen_Istekler": ["recent_follow_requests", "pending_follow_requests"],
    "Kaldirilan_Oneriler": ["removed_suggestions"],
    "Cikan_Takipciler": ["recently_unfollowed_profiles"],
}


def get_desktop_path():
    try:
        CSIDL_DESKTOP = 0x0000
        SHGFP_TYPE_CURRENT = 0
        buf = ctypes.create_unicode_buffer(ctypes.wintypes.MAX_PATH)
        ctypes.windll.shell32.SHGetFolderPathW(None, CSIDL_DESKTOP, None, SHGFP_TYPE_CURRENT, buf)
        return buf.value
    except Exception:
        return str(Path.home() / "Desktop")


def get_downloads_path():
    return str(Path.home() / "Downloads")


def _extract_username_from_url(url_or_text):
    if not url_or_text:
        return ""
    raw = str(url_or_text).strip()
    if "instagram.com" not in raw and not raw.startswith("http"):
        return raw.lstrip("@").strip("/")
    parsed = urllib.parse.urlparse(raw if raw.startswith("http") else f"https://{raw}")
    parts = [p for p in parsed.path.split("/") if p]
    if not parts:
        return ""
    if parts[0] == "_u" and len(parts) > 1:
        return parts[1].strip()
    return parts[0].strip()


def normalize_user_entry(username, url="", date_str=""):
    """Kullanıcı adını ve Instagram profil URL'sini temizler (_u/ önekini kaldırır)."""
    clean_username = _extract_username_from_url(username)
    raw_url = str(url or "").strip()

    if not clean_username and raw_url:
        clean_username = _extract_username_from_url(raw_url)

    clean_username = clean_username.lstrip("@").strip()

    if raw_url and "instagram.com" in raw_url:
        extracted = _extract_username_from_url(raw_url)
        if not clean_username and extracted:
            clean_username = extracted
        if clean_username:
            clean_url = f"https://www.instagram.com/{clean_username}"
        else:
            clean_url = re.sub(r"https?://(www\.)?instagram\.com/_u/", "https://www.instagram.com/", raw_url).rstrip("/")
    elif clean_username:
        clean_url = f"https://www.instagram.com/{clean_username}"
    else:
        clean_url = ""

    return (clean_username, clean_url, str(date_str or "").strip())


def dedupe_user_entries(entries):
    seen = set()
    result = []
    for entry in entries:
        uname, url, date_str = normalize_user_entry(*entry)
        if not uname:
            continue
        key = uname.lower()
        if key not in seen:
            seen.add(key)
            result.append((uname, url, date_str))
    return result


def read_file_from_zip(zip_path, inner_path):
    try:
        import zipfile
        with zipfile.ZipFile(zip_path, "r") as z:
            with z.open(inner_path) as f:
                return f.read().decode("utf-8", errors="replace")
    except Exception:
        return None


def extract_users_from_html_content(html_text):
    if not html_text:
        return []
    soup = BeautifulSoup(html_text, "html.parser")
    users = []

    for container in soup.find_all("div", class_="pam"):
        classes = container.get("class", [])
        if "uiBoxWhite" not in classes:
            continue

        username = ""
        url = ""
        date_str = ""

        h2_tag = container.find("h2")
        a_tag = container.find("a", href=True)

        if h2_tag:
            username = h2_tag.get_text(strip=True)
            url = a_tag["href"] if a_tag else ""
        else:
            user_div = container.find("div", class_="_a6-p")
            if user_div:
                inner_a = user_div.find("a", href=True)
                if inner_a:
                    username = inner_a.get_text(strip=True)
                    url = inner_a["href"]
            elif a_tag:
                username = a_tag.get_text(strip=True)
                url = a_tag["href"]

        date_div = container.find("div", class_="_a6-p")
        if date_div:
            date_text_div = date_div.find("div")
            if date_text_div:
                date_divs = date_text_div.find_all("div")
                if len(date_divs) >= 2:
                    date_str = date_divs[1].get_text(strip=True)

        uname, clean_url, clean_date = normalize_user_entry(username, url, date_str)
        if uname:
            users.append((uname, clean_url, clean_date))

    return dedupe_user_entries(users)


def extract_users_from_official_json_content(json_text):
    if not json_text:
        return []
    try:
        data = json.loads(json_text)
    except Exception:
        return []

    records = []
    if isinstance(data, list):
        records = data
    elif isinstance(data, dict):
        for val in data.values():
            if isinstance(val, list):
                records.extend(val)

    users = []
    for item in records:
        if not isinstance(item, dict):
            continue
        sld = item.get("string_list_data")
        first = sld[0] if isinstance(sld, list) and sld else {}
        if not isinstance(first, dict):
            first = {}

        username = first.get("value") or item.get("title") or ""
        url = first.get("href") or ""
        ts = first.get("timestamp")
        date_str = ""
        if isinstance(ts, (int, float)) and ts > 0:
            try:
                dt = datetime.datetime.fromtimestamp(ts)
                date_str = dt.strftime("%b %d, %Y %I:%M %p")
            except Exception:
                date_str = ""

        uname, clean_url, clean_date = normalize_user_entry(username, url, date_str)
        if uname:
            users.append((uname, clean_url, clean_date))

    return dedupe_user_entries(users)


def extract_users_with_dates(file_path, zip_path=None):
    if zip_path:
        content = read_file_from_zip(zip_path, file_path)
    else:
        if not file_path or not os.path.exists(file_path):
            return []
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()

    if content is None:
        return []

    if file_path.lower().endswith(".json"):
        return extract_users_from_official_json_content(content)
    return extract_users_from_html_content(content)


def parse_web_collector_json(data_or_text):
    if isinstance(data_or_text, str):
        data = json.loads(data_or_text)
    else:
        data = data_or_text

    if not isinstance(data, dict):
        raise ValueError("Geçersiz JSON formatı: nesne bekleniyordu.")

    is_web_source = data.get("source") == "insta_check_web_collector"
    has_lists = "followers" in data and "following" in data
    if not (is_web_source or has_lists):
        raise ValueError("Bu JSON verisi Insta Rapor Web Veri Çekici formatında değil.")

    def _parse_items(raw_list):
        parsed = []
        if not isinstance(raw_list, list):
            return parsed
        for item in raw_list:
            if isinstance(item, dict):
                uname = item.get("username") or ""
                url = item.get("url") or ""
                date_str = item.get("date") or ""
                parsed.append(normalize_user_entry(uname, url, date_str))
            elif isinstance(item, str):
                parsed.append(normalize_user_entry(item))
        return dedupe_user_entries(parsed)

    return {
        "username": str(data.get("username") or "Instagram").strip() or "Instagram",
        "exported_at": str(data.get("exported_at") or "").strip(),
        "followers": _parse_items(data.get("followers", [])),
        "following": _parse_items(data.get("following", [])),
    }


def compare_lists(main_list, compare_list):
    compare_usernames = {u[0].lower() for u in compare_list}
    return [u for u in main_list if u[0].lower() not in compare_usernames]


def compare_lists_reverse(main_list, compare_list):
    compare_usernames = {u[0].lower() for u in compare_list}
    return [u for u in main_list if u[0].lower() not in compare_usernames]


def _empty_lists_dict():
    return {
        "Takipciler": [],
        "Takip_Ettiklerim": [],
        "Yakin_Arkadaslar": [],
        "Favoriler": [],
        "Engellenenler": [],
        "Kisitlananlar": [],
        "Gelen_Istekler": [],
        "Gonderilen_Istekler": [],
        "Kaldirilan_Oneriler": [],
        "Cikan_Takipciler": [],
        "Beni_Geri_Takip_Etmeyenler": [],
        "Benim_Geri_Takip_Etmediklerim": [],
    }


def _match_official_filename(filename_lower, prefix):
    stem, ext = os.path.splitext(filename_lower)
    if ext not in (".html", ".json"):
        return False
    if prefix == "followers":
        return stem == "followers" or bool(re.match(r"^followers_\d+$", stem))
    return stem == prefix


def load_lists_from_local_dir(local_dir):
    lists = _empty_lists_dict()
    if not local_dir or not os.path.isdir(local_dir):
        return lists

    # Alt klasör varsa (örneğin seçilen ana klasör içinde followers_and_following) kontrol et
    candidate_dirs = [local_dir]
    for sub in ("followers_and_following", os.path.join("connections", "followers_and_following")):
        sub_path = os.path.join(local_dir, sub)
        if os.path.isdir(sub_path):
            candidate_dirs.insert(0, sub_path)

    target_dir = candidate_dirs[0]
    try:
        entries = sorted(os.listdir(target_dir))
    except Exception:
        entries = []

    for list_key, prefixes in OFFICIAL_LIST_FILE_MAP.items():
        collected = []
        matched_files = []
        for fname in entries:
            lower = fname.lower()
            if any(_match_official_filename(lower, p) for p in prefixes):
                matched_files.append(os.path.join(target_dir, fname))
        # Aynı listede hem html hem json varsa önceliği json veya ilke göre verip tekrarları temizle
        for fpath in matched_files:
            collected.extend(extract_users_with_dates(fpath))
        lists[list_key] = dedupe_user_entries(collected)

    lists["Beni_Geri_Takip_Etmeyenler"] = compare_lists(lists["Takip_Ettiklerim"], lists["Takipciler"])
    lists["Benim_Geri_Takip_Etmediklerim"] = compare_lists_reverse(lists["Takipciler"], lists["Takip_Ettiklerim"])
    return lists


def load_lists_from_zip(zip_path):
    import zipfile
    lists = _empty_lists_dict()
    if not zip_path or not os.path.exists(zip_path):
        return lists

    try:
        with zipfile.ZipFile(zip_path, "r") as z:
            all_names = sorted(z.namelist())
    except Exception:
        return lists

    preferred_dirs = ("connections/followers_and_following/", "followers_and_following/")

    for list_key, prefixes in OFFICIAL_LIST_FILE_MAP.items():
        collected = []
        matched_inner = []
        # Önce bilinen Meta yollarında ara
        for name in all_names:
            norm = name.replace("\\", "/")
            lower_norm = norm.lower()
            base = os.path.basename(lower_norm)
            if any(p in lower_norm for p in preferred_dirs) and any(_match_official_filename(base, p) for p in prefixes):
                matched_inner.append(norm)

        # Bulunamazsa ZIP içindeki tüm dosyalarda dosya adına göre ara
        if not matched_inner:
            for name in all_names:
                norm = name.replace("\\", "/")
                base = os.path.basename(norm.lower())
                if any(_match_official_filename(base, p) for p in prefixes):
                    matched_inner.append(norm)

        for inner_path in matched_inner:
            collected.extend(extract_users_with_dates(inner_path, zip_path=zip_path))

        lists[list_key] = dedupe_user_entries(collected)

    lists["Beni_Geri_Takip_Etmeyenler"] = compare_lists(lists["Takip_Ettiklerim"], lists["Takipciler"])
    lists["Benim_Geri_Takip_Etmediklerim"] = compare_lists_reverse(lists["Takipciler"], lists["Takip_Ettiklerim"])
    return lists


def on_user_double_click(event, url):
    if url:
        webbrowser.open(url)


def detect_system_dark_mode():
    try:
        if platform.system() == "Windows":
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
            )
            value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            return value == 0
        if platform.system() == "Darwin":
            import subprocess
            result = subprocess.run(
                ["defaults", "read", "-g", "AppleInterfaceStyle"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            return b"Dark" in result.stdout
    except Exception:
        pass
    return False


class InstaRaporApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Instagram Rapor 3.1")
        self.root.geometry("820x840")

        self.light_theme = {
            "theme_bg": "#f7f9fa",
            "tab_bg": "#e9ecf1",
            "tab_active": "#3a5ca8",
            "tab_fg": "#222",
            "tab_active_fg": "#fff",
            "tab_border": "#d1d5db",
            "user_card_bg": "#fff",
            "user_card_border": "#e0e0e0",
            "user_fg": "#2d5c88",
            "user_hover_fg": "#1a3a5a",
            "menu_fg": "#3a5ca8",
            "empty_fg": "#6b7280",
            "accent_green": "#009975",
            "input_bg": "#ffffff",
            "input_fg": "#111827",
        }
        self.dark_theme = {
            "theme_bg": "#181c22",
            "tab_bg": "#23272f",
            "tab_active": "#3a5ca8",
            "tab_fg": "#e0e6f0",
            "tab_active_fg": "#fff",
            "tab_border": "#2d333f",
            "user_card_bg": "#23272f",
            "user_card_border": "#2f3542",
            "user_fg": "#7ecfff",
            "user_hover_fg": "#b3e0ff",
            "menu_fg": "#7ecfff",
            "empty_fg": "#9aa5b1",
            "accent_green": "#00b894",
            "input_bg": "#1e232b",
            "input_fg": "#e0e6f0",
        }

        self.is_dark = detect_system_dark_mode()
        self.theme = self.dark_theme.copy() if self.is_dark else self.light_theme.copy()

        self.source_type = None  # "web_json", "zip", "local_dir", None
        self.source_path = None
        self.zip_path = None
        self.source_label = "Veri kaynağı seçilmedi"
        self.username = "Instagram"
        self.report_date = None
        self.sort_option = "Yeniden Eskiye"

        self.detect_initial_source()
        self.lists = self.load_all_lists()
        self.setup_style()
        self.build_ui()

    def detect_initial_source(self):
        downloads = get_downloads_path()
        candidates = []

        if os.path.isdir(SNAPSHOTS_DIR):
            for path in glob.glob(os.path.join(SNAPSHOTS_DIR, "*.json")):
                candidates.append(("web_json", path, os.path.getmtime(path)))

        if os.path.isdir(downloads):
            for path in glob.glob(os.path.join(downloads, "instagram_web_rapor_*.json")):
                candidates.append(("web_json", path, os.path.getmtime(path)))
            for path in glob.glob(os.path.join(downloads, "instagram-*.zip")):
                candidates.append(("zip", path, os.path.getmtime(path)))

        if candidates:
            candidates.sort(key=lambda x: x[2], reverse=True)
            best_type, best_path, _ = candidates[0]
            self.set_source(best_type, best_path)
            return

        # Yerel followers_and_following klasörüne geri dön
        local_candidates = [
            os.path.join(BASE_DIR, "followers_and_following"),
            os.path.join(os.getcwd(), "followers_and_following"),
        ]
        for local_dir in local_candidates:
            if os.path.isdir(local_dir):
                self.set_source("local_dir", local_dir)
                return

        self.source_type = None
        self.source_path = None
        self.zip_path = None
        self.source_label = "Veri kaynağı bulunamadı"
        self.username = "Instagram"
        self.report_date = None

    def set_source(self, source_type, path):
        self.source_type = source_type
        self.source_path = path
        self.zip_path = path if source_type == "zip" else None

        if source_type == "zip" and path:
            self.username = self.extract_username_from_zip(path)
            self.report_date = self.get_file_date(path)
            self.source_label = f"ZIP Arşivi ({os.path.basename(path)})"
        elif source_type == "web_json" and path:
            self.report_date = self.get_file_date(path)
            self.source_label = f"Web Tarayıcı Verisi ({os.path.basename(path)})"
        elif source_type == "local_dir" and path:
            self.username = "Instagram"
            self.report_date = self.get_local_dir_date(path)
            self.source_label = f"Yerel Klasör ({os.path.basename(path)})"
        else:
            self.username = "Instagram"
            self.report_date = None
            self.source_label = "Veri kaynağı seçilmedi"

    def extract_username_from_zip(self, zip_path):
        base = os.path.basename(zip_path)
        if base.startswith("instagram-"):
            parts = base.split("-")
            if len(parts) > 1 and parts[1]:
                return parts[1]
        return "Instagram"

    def get_file_date(self, path):
        try:
            ts = os.path.getmtime(path)
            return datetime.datetime.fromtimestamp(ts).strftime("%d.%m.%Y %H:%M")
        except Exception:
            return None

    def get_local_dir_date(self, dir_path):
        try:
            mtimes = [
                os.path.getmtime(os.path.join(dir_path, f))
                for f in os.listdir(dir_path)
                if f.lower().endswith((".html", ".json"))
            ]
            if mtimes:
                return datetime.datetime.fromtimestamp(max(mtimes)).strftime("%d.%m.%Y %H:%M")
            return self.get_file_date(dir_path)
        except Exception:
            return None

    def load_history_records(self):
        try:
            if os.path.exists(HISTORY_FILE):
                with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        return data
        except Exception:
            pass
        return []

    def _find_previous_history_record(self, history):
        if not history:
            return None
        for rec in reversed(history):
            if rec.get("date") != self.report_date:
                return rec
        if len(history) >= 2:
            return history[-2]
        return None

    def load_all_lists(self):
        if self.source_type == "web_json" and self.source_path and os.path.exists(self.source_path):
            try:
                with open(self.source_path, "r", encoding="utf-8") as f:
                    parsed = parse_web_collector_json(f.read())
                self.username = parsed["username"]
                if parsed["exported_at"]:
                    self.report_date = parsed["exported_at"]

                lists = _empty_lists_dict()
                lists["Takipciler"] = parsed["followers"]
                lists["Takip_Ettiklerim"] = parsed["following"]
                lists["Beni_Geri_Takip_Etmeyenler"] = compare_lists(
                    lists["Takip_Ettiklerim"], lists["Takipciler"]
                )
                lists["Benim_Geri_Takip_Etmediklerim"] = compare_lists_reverse(
                    lists["Takipciler"], lists["Takip_Ettiklerim"]
                )

                # Önceki kayıt varsa yeni takipten çıkanları tespit et
                history = self.load_history_records()
                prev_rec = self._find_previous_history_record(history)
                if prev_rec and lists["Takipciler"]:
                    prev_followers = set(u.lower() for u in prev_rec.get("usernames", []))
                    curr_followers = {u[0].lower() for u in lists["Takipciler"]}
                    unfollowed_you = []
                    for old_user in prev_rec.get("usernames", []):
                        if old_user.lower() not in curr_followers and old_user.lower() in prev_followers:
                            unfollowed_you.append(
                                normalize_user_entry(old_user, date_str="Son Taramada Takipten Çıktı")
                            )
                    lists["Cikan_Takipciler"] = dedupe_user_entries(unfollowed_you)

                return lists
            except Exception as err:
                messagebox.showerror("JSON Okuma Hatası", f"Web verisi okunamadı:\n{err}")
                return _empty_lists_dict()

        if self.source_type == "zip" and self.source_path:
            return load_lists_from_zip(self.source_path)

        if self.source_type == "local_dir" and self.source_path:
            return load_lists_from_local_dir(self.source_path)

        return _empty_lists_dict()

    def setup_style(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(
            "TNotebook.Tab",
            background=self.theme["tab_bg"],
            foreground=self.theme["tab_fg"],
            font=("Segoe UI", 10, "bold"),
            padding=[10, 4],
            borderwidth=0,
        )
        style.map(
            "TNotebook.Tab",
            background=[("selected", self.theme["tab_active"])],
            foreground=[("selected", self.theme["tab_active_fg"])],
        )
        style.configure("TNotebook", background=self.theme["theme_bg"], borderwidth=0)
        style.configure("TFrame", background=self.theme["theme_bg"])
        style.configure(
            "Custom.TCombobox",
            fieldbackground=self.theme["tab_bg"],
            background=self.theme["tab_bg"],
            foreground=self.theme["user_fg"],
            selectforeground=self.theme["user_fg"],
            selectbackground=self.theme["tab_bg"],
            borderwidth=0,
            font=("Segoe UI", 10, "bold"),
        )
        style.layout(
            "TNotebook.Tab",
            [
                (
                    "Notebook.tab",
                    {
                        "sticky": "nswe",
                        "children": [
                            (
                                "Notebook.padding",
                                {
                                    "side": "top",
                                    "sticky": "nswe",
                                    "children": [("Notebook.label", {"side": "top", "sticky": ""})],
                                },
                            )
                        ],
                    },
                )
            ],
        )

    def build_ui(self):
        for widget in self.root.winfo_children():
            widget.destroy()

        self.root.configure(bg=self.theme["theme_bg"])

        # Üst Başlık Satırı
        top_frame = tk.Frame(self.root, bg=self.theme["theme_bg"])
        top_frame.pack(fill="x", pady=(10, 0), padx=18)

        title = tk.Label(
            top_frame,
            text=f"{self.username} Instagram Raporu",
            font=("Segoe UI", 18, "bold"),
            bg=self.theme["theme_bg"],
            fg=self.theme["user_fg"],
        )
        title.pack(side="left", pady=4)

        self.theme_btn = tk.Button(
            top_frame,
            text="🌙 Karanlık Mod" if not self.is_dark else "☀️ Açık Mod",
            font=("Segoe UI", 10, "bold"),
            bg=self.theme["tab_bg"],
            fg=self.theme["tab_fg"],
            relief="flat",
            cursor="hand2",
            padx=10,
            pady=4,
            command=self.toggle_theme,
        )
        self.theme_btn.pack(side="right", pady=4)

        # Kontrol Butonları Çubuğu
        controls_frame = tk.Frame(self.root, bg=self.theme["theme_bg"])
        controls_frame.pack(fill="x", padx=18, pady=(4, 6))

        web_btn = tk.Button(
            controls_frame,
            text="🌐 Web'den Veri Çek (Güvenli Mod)",
            font=("Segoe UI", 10, "bold"),
            bg=self.theme["accent_green"],
            fg="#ffffff",
            relief="flat",
            cursor="hand2",
            padx=12,
            pady=5,
            command=self.open_web_collector_dialog,
        )
        web_btn.pack(side="left", padx=(0, 8))

        source_btn = tk.Button(
            controls_frame,
            text="📂 Veri Kaynağı Seç",
            font=("Segoe UI", 10, "bold"),
            bg=self.theme["tab_bg"],
            fg=self.theme["user_fg"],
            relief="flat",
            cursor="hand2",
            padx=12,
            pady=5,
            command=self.choose_data_source,
        )
        source_btn.pack(side="left", padx=(0, 8))

        refresh_btn = tk.Button(
            controls_frame,
            text="🔄 Yenile",
            font=("Segoe UI", 10, "bold"),
            bg=self.theme["tab_bg"],
            fg=self.theme["tab_fg"],
            relief="flat",
            cursor="hand2",
            padx=10,
            pady=5,
            command=self.reload_current_source,
        )
        refresh_btn.pack(side="left")

        # İstatistik ve Kaynak Bilgi Satırı
        takipci_sayisi = len(self.lists.get("Takipciler", []))
        takip_edilen_sayisi = len(self.lists.get("Takip_Ettiklerim", []))
        unfollowers_count = len(self.lists.get("Beni_Geri_Takip_Etmeyenler", []))

        stats_label = tk.Label(
            self.root,
            text=(
                f"Takipçi: {takipci_sayisi}   •   "
                f"Takip Edilen: {takip_edilen_sayisi}   •   "
                f"Geri Takip Etmeyen: {unfollowers_count}"
            ),
            font=("Segoe UI", 11, "bold"),
            bg=self.theme["theme_bg"],
            fg=self.theme["user_fg"],
        )
        stats_label.pack(pady=(2, 2))

        date_text = f"   |   Tarih: {self.report_date}" if self.report_date else ""
        source_info = tk.Label(
            self.root,
            text=f"Kaynak: {self.source_label}{date_text}",
            font=("Segoe UI", 9, "italic"),
            bg=self.theme["theme_bg"],
            fg=self.theme["empty_fg"],
        )
        source_info.pack(pady=(0, 4))

        footer = tk.Label(
            self.root,
            text="Instagram Rapor 3.1 • Hibrit Güvenli Analiz Aracı",
            font=("Segoe UI", 9, "italic"),
            bg=self.theme["theme_bg"],
            fg=self.theme["empty_fg"],
        )
        footer.pack(side="bottom", pady=(0, 6))

        self.notebook = ttk.Notebook(self.root, style="TNotebook")
        self.notebook.pack(fill="both", expand=True, padx=18, pady=6)
        self.create_tabs()

    def toggle_theme(self):
        self.is_dark = not self.is_dark
        self.theme = self.dark_theme.copy() if self.is_dark else self.light_theme.copy()
        self.setup_style()
        self.build_ui()

    def reload_current_source(self):
        if not self.source_type:
            self.detect_initial_source()
        self.lists = self.load_all_lists()
        self.build_ui()

    def choose_data_source(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("Veri Kaynağı Seç")
        dialog.geometry("460x230")
        dialog.configure(bg=self.theme["theme_bg"])
        dialog.transient(self.root)
        dialog.grab_set()

        tk.Label(
            dialog,
            text="Hangi veri kaynağını yüklemek istiyorsunuz?",
            font=("Segoe UI", 12, "bold"),
            bg=self.theme["theme_bg"],
            fg=self.theme["user_fg"],
        ).pack(pady=(18, 12))

        def pick_file():
            initial_dir = get_downloads_path()
            if not os.path.isdir(initial_dir):
                initial_dir = BASE_DIR
            selected = filedialog.askopenfilename(
                parent=dialog,
                title="Instagram ZIP veya Web JSON Dosyası Seçin",
                initialdir=initial_dir,
                filetypes=[
                    ("Desteklenen Dosyalar", "*.zip *.json"),
                    ("Instagram ZIP Arşivi", "*.zip"),
                    ("Web Collector JSON", "*.json"),
                ],
            )
            if not selected:
                return
            if selected.lower().endswith(".zip"):
                self.set_source("zip", selected)
            else:
                try:
                    with open(selected, "r", encoding="utf-8") as f:
                        parse_web_collector_json(f.read())
                    self.set_source("web_json", selected)
                except Exception as err:
                    messagebox.showerror("Geçersiz JSON", f"Seçilen JSON dosyası okunamadı:\n{err}", parent=dialog)
                    return
            dialog.destroy()
            self.lists = self.load_all_lists()
            self.build_ui()

        def pick_folder():
            initial_dir = BASE_DIR
            selected_dir = filedialog.askdirectory(
                parent=dialog,
                title="followers_and_following Klasörünü Seçin",
                initialdir=initial_dir,
            )
            if not selected_dir:
                return
            self.set_source("local_dir", selected_dir)
            dialog.destroy()
            self.lists = self.load_all_lists()
            self.build_ui()

        def auto_detect():
            self.detect_initial_source()
            dialog.destroy()
            self.lists = self.load_all_lists()
            self.build_ui()

        btn_cfg = {
            "font": ("Segoe UI", 10, "bold"),
            "bg": self.theme["tab_bg"],
            "fg": self.theme["user_fg"],
            "relief": "flat",
            "cursor": "hand2",
            "pady": 8,
            "width": 38,
        }
        tk.Button(dialog, text="📦 ZIP veya Web JSON Dosyası Seç (.zip / .json)", command=pick_file, **btn_cfg).pack(pady=5)
        tk.Button(dialog, text="📁 Yerel Klasör Seç (followers_and_following)", command=pick_folder, **btn_cfg).pack(pady=5)
        tk.Button(dialog, text="✨ En Güncel Kaynağı Otomatik Algıla", command=auto_detect, **btn_cfg).pack(pady=5)

    def _save_web_json_snapshot(self, json_text):
        parsed = parse_web_collector_json(json_text)
        os.makedirs(SNAPSHOTS_DIR, exist_ok=True)
        stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        snapshot_path = os.path.join(SNAPSHOTS_DIR, f"web_snapshot_{stamp}.json")

        with open(snapshot_path, "w", encoding="utf-8") as f:
            try:
                raw_obj = json.loads(json_text)
                json.dump(raw_obj, f, ensure_ascii=False, indent=2)
            except Exception:
                f.write(json_text)

        return snapshot_path, parsed

    def open_web_collector_dialog(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("Web'den Güvenli Veri Çek (Ayda 1 Kez Modu)")
        dialog.geometry("650x575")
        dialog.configure(bg=self.theme["theme_bg"])
        dialog.transient(self.root)

        tk.Label(
            dialog,
            text="🛡️ Güvenli Web Veri Çekici (Sadece Okuma Modu)",
            font=("Segoe UI", 14, "bold"),
            bg=self.theme["theme_bg"],
            fg=self.theme["user_fg"],
        ).pack(anchor="w", padx=20, pady=(16, 4))

        tk.Label(
            dialog,
            text=(
                "Şifre veya harici giriş istemez. Kendi açık tarayıcınızda rastgele insani "
                "beklemelerle (2.2–4.5 sn) çalışarak hesabınızı korur."
            ),
            font=("Segoe UI", 10),
            bg=self.theme["theme_bg"],
            fg=self.theme["empty_fg"],
            wraplength=580,
            justify="left",
        ).pack(anchor="w", padx=20, pady=(0, 12))

        feedback_var = tk.StringVar(value="")

        def create_step_box(step_title, step_desc):
            box = tk.Frame(
                dialog,
                bg=self.theme["user_card_bg"],
                highlightbackground=self.theme["user_card_border"],
                highlightthickness=1,
            )
            box.pack(fill="x", padx=20, pady=6)
            tk.Label(
                box,
                text=step_title,
                font=("Segoe UI", 11, "bold"),
                bg=self.theme["user_card_bg"],
                fg=self.theme["user_fg"],
            ).pack(anchor="w", padx=12, pady=(10, 2))
            tk.Label(
                box,
                text=step_desc,
                font=("Segoe UI", 9),
                bg=self.theme["user_card_bg"],
                fg=self.theme["tab_fg"],
                wraplength=555,
                justify="left",
            ).pack(anchor="w", padx=12, pady=(0, 8))
            btn_row = tk.Frame(box, bg=self.theme["user_card_bg"])
            btn_row.pack(fill="x", padx=12, pady=(0, 10))
            return btn_row

        # Adım 1
        step1_btns = create_step_box(
            "Adım 1: Tarayıcı Asistanını Aç veya Kodu Kopyala",
            "En kolay yol: Sürükle-bırak Yer İmi kurulum sayfasını bir kez açıp butonu Yer İmleri Çubuğunuza ekleyin (F12 gerekmez). "
            "İsterseniz doğrudan tarayıcı kodunu da kopyalayabilirsiniz.",
        )

        def open_bookmarklet_setup():
            if not os.path.exists(BOOKMARKLET_HTML_PATH):
                messagebox.showerror("Dosya Eksik", f"Bulunamadı:\n{BOOKMARKLET_HTML_PATH}", parent=dialog)
                return
            webbrowser.open(Path(BOOKMARKLET_HTML_PATH).as_uri())
            feedback_var.set("🔖 Kurulum sayfası tarayıcıda açıldı!")

        def copy_collector_script():
            if not os.path.exists(WEB_COLLECTOR_JS_PATH):
                messagebox.showerror("Dosya Eksik", f"Bulunamadı:\n{WEB_COLLECTOR_JS_PATH}", parent=dialog)
                return
            with open(WEB_COLLECTOR_JS_PATH, "r", encoding="utf-8") as f:
                js_code = f.read()
            self.root.clipboard_clear()
            self.root.clipboard_append(js_code)
            self.root.update()
            feedback_var.set("✅ Güvenli tarayıcı kodu panoya kopyalandı!")

        step1_top_row = tk.Frame(step1_btns, bg=self.theme["user_card_bg"])
        step1_top_row.pack(fill="x", pady=(0, 6))

        tk.Button(
            step1_top_row,
            text="🔖 Sürükle-Bırak Yer İmi Kurulumunu Aç (F12'siz Kolay Yöntem)",
            font=("Segoe UI", 10, "bold"),
            bg=self.theme["accent_green"],
            fg="#ffffff",
            relief="flat",
            cursor="hand2",
            padx=10,
            pady=5,
            command=open_bookmarklet_setup,
        ).pack(side="left")

        step1_bottom_row = tk.Frame(step1_btns, bg=self.theme["user_card_bg"])
        step1_bottom_row.pack(fill="x")

        tk.Button(
            step1_bottom_row,
            text="📋 Güvenli Tarayıcı Kodunu Kopyala",
            font=("Segoe UI", 10, "bold"),
            bg=self.theme["tab_active"],
            fg="#ffffff",
            relief="flat",
            cursor="hand2",
            padx=10,
            pady=5,
            command=copy_collector_script,
        ).pack(side="left", padx=(0, 8))

        tk.Button(
            step1_bottom_row,
            text="🌐 Instagram'ı Aç",
            font=("Segoe UI", 10, "bold"),
            bg=self.theme["tab_bg"],
            fg=self.theme["user_fg"],
            relief="flat",
            cursor="hand2",
            padx=10,
            pady=5,
            command=lambda: webbrowser.open("https://www.instagram.com/"),
        ).pack(side="left")

        # Adım 2
        create_step_box(
            "Adım 2: Tarayıcıda Taramayı Başlat",
            "• Kolay Yöntem: Instagram açıkken Yer İmleri Çubuğundaki '🛡️ Insta Rapor Çekici'ye tıklayın.\n"
            "• Konsol Yöntemi: F12 → Console sekmesine kodu yapıştırıp Enter'a basın.\n"
            "Ardından sağ altta açılan panelde '⚡ Otomatik Güvenli Okuyucu' butonuna basın ve bitmesini bekleyin.",
        )

        # Adım 3
        step3_btns = create_step_box(
            "Adım 3: Çekilen Veriyi Uygulamaya Aktar",
            "Tarama bittiğinde veriler otomatik olarak panoya kopyalanır ve Downloads klasörüne JSON olarak indirilir. "
            "Aşağıdaki butonlardan biriyle hemen analiz edin:",
        )

        def import_from_clipboard():
            try:
                clip_text = self.root.clipboard_get()
            except Exception:
                messagebox.showwarning("Pano Boş", "Panoda okunabilir bir JSON metni bulunamadı.", parent=dialog)
                return

            try:
                snapshot_path, _ = self._save_web_json_snapshot(clip_text)
            except Exception as err:
                messagebox.showerror(
                    "Geçersiz Pano Verisi",
                    f"Panodaki veri geçerli Web Collector JSON formatında değil:\n{err}",
                    parent=dialog,
                )
                return

            self.set_source("web_json", snapshot_path)
            self.lists = self.load_all_lists()
            dialog.destroy()
            self.build_ui()

        def import_from_json_file():
            initial_dir = get_downloads_path()
            if not os.path.isdir(initial_dir):
                initial_dir = BASE_DIR
            selected = filedialog.askopenfilename(
                parent=dialog,
                title="İndirilen Web Collector JSON Dosyasını Seçin",
                initialdir=initial_dir,
                filetypes=[("JSON Dosyaları", "*.json")],
            )
            if not selected:
                return
            try:
                with open(selected, "r", encoding="utf-8") as f:
                    json_text = f.read()
                snapshot_path, _ = self._save_web_json_snapshot(json_text)
            except Exception as err:
                messagebox.showerror("Dosya Okuma Hatası", f"JSON dosyası yüklenemedi:\n{err}", parent=dialog)
                return

            self.set_source("web_json", snapshot_path)
            self.lists = self.load_all_lists()
            dialog.destroy()
            self.build_ui()

        tk.Button(
            step3_btns,
            text="📥 Panodan Yapıştır ve Analiz Et",
            font=("Segoe UI", 10, "bold"),
            bg=self.theme["accent_green"],
            fg="#ffffff",
            relief="flat",
            cursor="hand2",
            padx=10,
            pady=5,
            command=import_from_clipboard,
        ).pack(side="left", padx=(0, 8))

        tk.Button(
            step3_btns,
            text="📂 İndirilen JSON Dosyasını Seç",
            font=("Segoe UI", 10, "bold"),
            bg=self.theme["tab_bg"],
            fg=self.theme["user_fg"],
            relief="flat",
            cursor="hand2",
            padx=10,
            pady=5,
            command=import_from_json_file,
        ).pack(side="left")

        tk.Label(
            dialog,
            textvariable=feedback_var,
            font=("Segoe UI", 10, "bold"),
            bg=self.theme["theme_bg"],
            fg=self.theme["accent_green"],
        ).pack(anchor="w", padx=20, pady=(6, 10))

    def create_tabs(self):
        main_tab_order = [
            "Beni_Geri_Takip_Etmeyenler",
            "Benim_Geri_Takip_Etmediklerim",
            "Yakin_Arkadaslar",
            "Favoriler",
            "Takipci_Analizi",
        ]
        other_tab_order = [
            "Engellenenler",
            "Kisitlananlar",
            "Gelen_Istekler",
            "Gonderilen_Istekler",
            "Kaldirilan_Oneriler",
            "Cikan_Takipciler",
        ]

        self.tab_names = []
        self.other_display_to_key = {}
        self.other_tab_order = []

        for tab_name in main_tab_order:
            if tab_name == "Takipci_Analizi":
                display_name = "Takipçi Analizi"
                self.tab_names.append(display_name)
                self.create_analysis_tab(display_name)
            else:
                label = TAB_LABELS.get(tab_name, tab_name)
                count = len(self.lists.get(tab_name, []))
                display_name = f"{label} ({count})"
                self.tab_names.append(display_name)
                self.create_user_tab(tab_name, self.lists.get(tab_name, []), display_name)

        for tab_name in other_tab_order:
            label = TAB_LABELS.get(tab_name, tab_name)
            count = len(self.lists.get(tab_name, []))
            display_name = f"{label} ({count})"
            self.other_display_to_key[display_name] = tab_name
            self.other_tab_order.append(display_name)

        self.create_other_tab()

        if self.tab_names:
            self.notebook.select(0)

    def create_analysis_tab(self, display_name):
        frame = tk.Frame(self.notebook, bg=self.theme["theme_bg"])
        self.notebook.add(frame, text=display_name)

        def render_analysis_content():
            for widget in frame.winfo_children():
                widget.destroy()

            history = self.load_history_records()
            prev_rec = self._find_previous_history_record(history)
            takipciler = self.lists.get("Takipciler", [])
            current_map = {u[0].lower(): u for u in takipciler}

            if prev_rec:
                old_map = {u.lower(): u for u in prev_rec.get("usernames", [])}
                gelenler = [current_map[k] for k in current_map if k not in old_map]
                gidenler = [
                    normalize_user_entry(old_map[k], date_str="Takipten Çıktı")
                    for k in old_map
                    if k not in current_map
                ]

                prev_date = prev_rec.get("date") or "Önceki Kayıt"
                info = tk.Label(
                    frame,
                    text=(
                        f"Karşılaştırma: {prev_date} → {self.report_date or 'Şimdi'}\n"
                        f"Gelen Takipçi: {len(gelenler)}   •   Giden Takipçi: {len(gidenler)}"
                    ),
                    font=("Segoe UI", 12, "bold"),
                    bg=self.theme["theme_bg"],
                    fg=self.theme["user_fg"],
                )
                info.pack(pady=(14, 6))

                fig, ax = plt.subplots(figsize=(3.4, 2.0), dpi=100)
                ax.bar(["Gelen", "Giden"], [len(gelenler), len(gidenler)], color=["#00b894", "#ff7675"])
                ax.set_ylabel("Kişi Sayısı", color=self.theme["tab_fg"])
                ax.set_title("Takipçi Değişimi", color=self.theme["user_fg"], fontsize=11)
                ax.tick_params(colors=self.theme["tab_fg"])
                ax.set_facecolor(self.theme["theme_bg"])
                fig.patch.set_facecolor(self.theme["theme_bg"])

                buf = io.BytesIO()
                plt.savefig(buf, format="png", bbox_inches="tight", transparent=True)
                plt.close(fig)
                buf.seek(0)
                img = Image.open(buf)
                photo = ImageTk.PhotoImage(img)

                chart_label = tk.Label(frame, image=photo, bg=self.theme["theme_bg"])
                chart_label.image = photo
                chart_label.pack(pady=(0, 8))

                # Kaydırılabilir Gelen/Giden Listesi
                list_container = tk.Frame(frame, bg=self.theme["theme_bg"])
                list_container.pack(fill="both", expand=True, padx=10, pady=4)
                combined_sections = []
                for u in gelenler:
                    combined_sections.append((u[0], u[1], f"+ Yeni Takipçi ({u[2]})" if u[2] else "+ Yeni Takipçi"))
                for u in gidenler:
                    combined_sections.append((u[0], u[1], "- Takipten Çıktı"))

                if combined_sections:
                    self._render_scrollable_cards(list_container, combined_sections)
                else:
                    tk.Label(
                        list_container,
                        text="Son kayıttan bu yana takipçi listenizde değişiklik yok.",
                        font=("Segoe UI", 11),
                        bg=self.theme["theme_bg"],
                        fg=self.theme["empty_fg"],
                    ).pack(pady=16)
            else:
                tk.Label(
                    frame,
                    text="İlk veri kaydedildi. Sonraki raporda veya taramada karşılaştırma yapılacak.",
                    font=("Segoe UI", 12, "bold"),
                    bg=self.theme["theme_bg"],
                    fg=self.theme["user_fg"],
                    wraplength=520,
                ).pack(pady=(24, 10))

            self.save_current_followers_to_history()

        def show_initial_prompt():
            for widget in frame.winfo_children():
                widget.destroy()
            tk.Label(
                frame,
                text=(
                    "Takipçi değişimini analiz etmek için mevcut verileri geçmişe kaydetmek ve "
                    "önceki kayıtla karşılaştırmak ister misiniz?"
                ),
                font=("Segoe UI", 12),
                bg=self.theme["theme_bg"],
                fg=self.theme["user_fg"],
                wraplength=520,
            ).pack(pady=(36, 14))
            tk.Button(
                frame,
                text="📊 Evet, Verileri Kaydet ve Analiz Et",
                font=("Segoe UI", 11, "bold"),
                bg=self.theme["tab_active"],
                fg="#ffffff",
                relief="flat",
                cursor="hand2",
                padx=14,
                pady=8,
                command=render_analysis_content,
            ).pack(pady=8)

        show_initial_prompt()

    def parse_date(self, date_str):
        if not date_str:
            return None
        cleaned = str(date_str).replace("(Web)", "").strip()
        for fmt in ("%b %d, %Y %I:%M %p", "%d.%m.%Y %H:%M", "%d.%m.%Y", "%Y-%m-%d"):
            try:
                return datetime.datetime.strptime(cleaned, fmt)
            except Exception:
                continue
        return None

    def sort_user_list(self, user_list):
        if self.sort_option == "Eskiden Yeniye":
            return sorted(user_list, key=lambda x: self.parse_date(x[2]) or datetime.datetime.min)
        if self.sort_option == "Yeniden Eskiye":
            return sorted(user_list, key=lambda x: self.parse_date(x[2]) or datetime.datetime.min, reverse=True)
        if self.sort_option == "A'dan Z'ye":
            return sorted(user_list, key=lambda x: x[0].lower())
        if self.sort_option == "Z'den A'ya":
            return sorted(user_list, key=lambda x: x[0].lower(), reverse=True)
        return user_list

    def _build_filter_bar_and_list(self, parent_frame, user_list):
        """Arama kutusu, sıralama menüsü ve kaydırılabilir kullanıcı kartlarını oluşturur."""
        for widget in parent_frame.winfo_children():
            widget.destroy()

        toolbar = tk.Frame(parent_frame, bg=self.theme["theme_bg"])
        toolbar.pack(fill="x", pady=(6, 4), padx=10)
        toolbar.grid_columnconfigure(1, weight=1)

        tk.Label(
            toolbar,
            text="🔍 Ara:",
            bg=self.theme["theme_bg"],
            fg=self.theme["user_fg"],
            font=("Segoe UI", 10, "bold"),
        ).grid(row=0, column=0, sticky="w", padx=(0, 6))

        search_var = tk.StringVar()
        search_entry = tk.Entry(
            toolbar,
            textvariable=search_var,
            bg=self.theme["input_bg"],
            fg=self.theme["input_fg"],
            insertbackground=self.theme["input_fg"],
            relief="flat",
            highlightbackground=self.theme["user_card_border"],
            highlightthickness=1,
            font=("Segoe UI", 10),
        )
        search_entry.grid(row=0, column=1, sticky="ew", padx=(0, 14), ipady=3)

        tk.Label(
            toolbar,
            text="Sırala:",
            bg=self.theme["theme_bg"],
            fg=self.theme["user_fg"],
            font=("Segoe UI", 10, "bold"),
        ).grid(row=0, column=2, sticky="e", padx=(0, 6))

        sort_options = ["Yeniden Eskiye", "Eskiden Yeniye", "A'dan Z'ye", "Z'den A'ya"]
        sort_menu = ttk.Combobox(
            toolbar,
            values=sort_options,
            state="readonly",
            width=16,
            style="Custom.TCombobox",
        )
        sort_menu.set(self.sort_option)
        sort_menu.grid(row=0, column=3, sticky="e")

        list_container = tk.Frame(parent_frame, bg=self.theme["theme_bg"])
        list_container.pack(fill="both", expand=True)

        def refresh_cards(*_):
            query = search_var.get().strip().lower()
            filtered = [u for u in user_list if query in u[0].lower()] if query else list(user_list)
            self._render_scrollable_cards(list_container, filtered)

        def on_sort_change(_=None):
            self.sort_option = sort_menu.get()
            refresh_cards()

        search_var.trace_add("write", refresh_cards)
        sort_menu.bind("<<ComboboxSelected>>", on_sort_change)
        refresh_cards()

    def _render_scrollable_cards(self, container, user_list):
        for widget in container.winfo_children():
            widget.destroy()

        if not user_list:
            tk.Label(
                container,
                text="Eşleşen kullanıcı bulunamadı.",
                fg=self.theme["empty_fg"],
                bg=self.theme["theme_bg"],
                font=("Segoe UI", 11),
            ).pack(pady=30)
            return

        canvas = tk.Canvas(container, bg=self.theme["theme_bg"], highlightthickness=0)
        scrollbar = tk.Scrollbar(container, orient="vertical", command=canvas.yview)
        scroll_frame = tk.Frame(canvas, bg=self.theme["theme_bg"])

        window_id = canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        scroll_frame.bind(
            "<Configure>",
            lambda e, c=canvas: c.configure(scrollregion=c.bbox("all")),
        )
        canvas.bind(
            "<Configure>",
            lambda e, c=canvas, wid=window_id: c.itemconfigure(wid, width=e.width),
        )
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        canvas.bind("<Enter>", lambda e: canvas.bind_all("<MouseWheel>", _on_mousewheel))
        canvas.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))

        sorted_list = self.sort_user_list(user_list)
        for idx, (username, url, date) in enumerate(sorted_list, 1):
            card = tk.Frame(
                scroll_frame,
                bg=self.theme["user_card_bg"],
                highlightbackground=self.theme["user_card_border"],
                highlightthickness=1,
                bd=0,
            )
            card.pack(anchor="w", padx=10, pady=4, fill="x")

            user_label = tk.Label(
                card,
                text=f"{idx}. {username}",
                fg=self.theme["user_fg"],
                bg=self.theme["user_card_bg"],
                cursor="hand2",
                font=("Segoe UI", 11, "bold"),
                anchor="w",
            )
            user_label.pack(side="left", padx=(10, 6), pady=6)
            user_label.bind("<Double-Button-1>", lambda e, u=url: on_user_double_click(e, u))
            user_label.bind(
                "<Enter>",
                lambda e, l=user_label: l.config(
                    fg=self.theme["user_hover_fg"], font=("Segoe UI", 11, "bold", "underline")
                ),
            )
            user_label.bind(
                "<Leave>",
                lambda e, l=user_label: l.config(
                    fg=self.theme["user_fg"], font=("Segoe UI", 11, "bold")
                ),
            )

            if date:
                date_label = tk.Label(
                    card,
                    text=date,
                    fg=self.theme["empty_fg"],
                    bg=self.theme["user_card_bg"],
                    font=("Segoe UI", 9),
                    anchor="w",
                )
                date_label.pack(side="left", padx=(8, 0), pady=6)

            open_btn = tk.Button(
                card,
                text="Profili Aç ↗",
                font=("Segoe UI", 9, "bold"),
                bg=self.theme["tab_bg"],
                fg=self.theme["user_fg"],
                relief="flat",
                cursor="hand2",
                padx=8,
                pady=2,
                command=lambda u=url: webbrowser.open(u) if u else None,
            )
            open_btn.pack(side="right", padx=10, pady=5)

    def create_user_tab(self, tab_name, user_list, display_name):
        frame = tk.Frame(self.notebook, bg=self.theme["theme_bg"])
        self.notebook.add(frame, text=display_name)
        self._build_filter_bar_and_list(frame, user_list)

    def save_current_followers_to_history(self):
        takipciler = self.lists.get("Takipciler", [])
        takip_edilenler = self.lists.get("Takip_Ettiklerim", [])
        if not takipciler and not takip_edilenler:
            return

        date_key = self.report_date or datetime.datetime.now().strftime("%d.%m.%Y %H:%M")
        data = {
            "date": date_key,
            "source": self.source_type or "unknown",
            "username": self.username,
            "usernames": [u[0] for u in takipciler],
            "following": [u[0] for u in takip_edilenler],
        }

        history = self.load_history_records()
        found = False
        for rec in history:
            if rec.get("date") == date_key and rec.get("username", self.username) == self.username:
                rec.update(data)
                found = True
                break
        if not found:
            history.append(data)

        history = history[-10:]
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)

    def create_other_tab(self):
        other_tab = tk.Frame(self.notebook, bg=self.theme["theme_bg"])
        self.notebook.add(other_tab, text="Diğer")

        label = tk.Label(
            other_tab,
            text="🧊 Diğer Opsiyonel Listeler",
            fg=self.theme["menu_fg"],
            bg=self.theme["theme_bg"],
            font=("Segoe UI", 14, "bold"),
        )
        label.pack(pady=(16, 8))

        menu_frame = tk.Frame(other_tab, bg=self.theme["theme_bg"])
        menu_frame.pack(pady=6)

        self.other_list_frame = tk.Frame(other_tab, bg=self.theme["theme_bg"])
        self.other_list_frame.pack(fill="both", expand=True, padx=10, pady=6)

        max_per_row = 3
        for i, display_name in enumerate(self.other_tab_order):
            btn = tk.Button(
                menu_frame,
                text=display_name,
                font=("Segoe UI", 10, "bold"),
                bg=self.theme["tab_bg"],
                fg=self.theme["user_fg"],
                relief="flat",
                cursor="hand2",
                padx=14,
                pady=6,
                command=lambda t=display_name: self.show_other_list(t),
            )
            row = i // max_per_row
            col = i % max_per_row
            btn.grid(row=row, column=col, padx=6, pady=4, sticky="ew")

        if self.other_tab_order:
            self.show_other_list(self.other_tab_order[0])

    def show_other_list(self, display_name):
        for widget in self.other_list_frame.winfo_children():
            widget.destroy()

        tab_name = self.other_display_to_key.get(display_name)
        if not tab_name:
            tab_name = display_name.rsplit(" (", 1)[0]

        user_list = self.lists.get(tab_name, [])
        if not user_list:
            tk.Label(
                self.other_list_frame,
                text="Bu kategori için veri bulunamadı (Web modunda sadece Takipçi/Takip Edilen çekilir; tüm listeler için resmi ZIP kullanabilirsiniz).",
                fg=self.theme["empty_fg"],
                bg=self.theme["theme_bg"],
                font=("Segoe UI", 11),
                wraplength=540,
            ).pack(pady=30)
            return

        self._build_filter_bar_and_list(self.other_list_frame, user_list)


if __name__ == "__main__":
    root = tk.Tk()
    app = InstaRaporApp(root)
    root.mainloop()
