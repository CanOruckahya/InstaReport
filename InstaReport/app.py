import os
import tkinter as tk
from tkinter import ttk, messagebox
import webbrowser
from bs4 import BeautifulSoup
import ctypes.wintypes
import zipfile
import glob
from pathlib import Path
import platform
import matplotlib
matplotlib.use('Agg')  # Tkinter ile uyumlu olması için
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import io
from PIL import Image, ImageTk
import json

# Masaüstü ve indirilenler konumunu bul

# Masaüstü konumunu tüm dillerde bulur (Türkçe dahil)
def get_desktop_path():
    CSIDL_DESKTOP = 0x0000
    SHGFP_TYPE_CURRENT = 0
    buf = ctypes.create_unicode_buffer(ctypes.wintypes.MAX_PATH)
    ctypes.windll.shell32.SHGetFolderPathW(None, CSIDL_DESKTOP, None, SHGFP_TYPE_CURRENT, buf)
    return buf.value

def get_downloads_path():
    # Windows'ta indirilenler klasörü
    return str(Path.home() / "Downloads")

# Zip içinden dosya okuma fonksiyonu
def read_file_from_zip(zip_path, inner_path):
    try:
        with zipfile.ZipFile(zip_path, 'r') as z:
            with z.open(inner_path) as f:
                return f.read().decode('utf-8')
    except Exception:
        return None

# HTML dosyasından kullanıcı adı ve tarihi çek (zip veya normal dosya)
def extract_users_with_dates(file_path, zip_path=None):
    if zip_path:
        html = read_file_from_zip(zip_path, file_path)
        if html is None:
            return []
        soup = BeautifulSoup(html, 'html.parser')
    else:
        if not os.path.exists(file_path):
            return []
        with open(file_path, 'r', encoding='utf-8') as file:
            soup = BeautifulSoup(file, 'html.parser')
    users = []
    for user_div in soup.find_all('div', class_='_a6-p'):
        a_tag = user_div.find('a', href=True)
        date_div = a_tag.find_next('div') if a_tag else None
        if a_tag and date_div:
            username = a_tag.text.strip()
            url = a_tag['href']
            date = date_div.text.strip()
            users.append((username, url, date))
    return users

def compare_lists(main_list, compare_list):
    compare_usernames = set(u[0] for u in compare_list)
    return [u for u in main_list if u[0] not in compare_usernames]

def compare_lists_reverse(main_list, compare_list):
    compare_usernames = set(u[0] for u in compare_list)
    return [u for u in main_list if u[0] not in compare_usernames]

def on_user_double_click(event, url):
    webbrowser.open(url)

# Modern sade renkler ve kart görünümü
theme_bg = "#f7f9fa"
tab_bg = "#e9ecf1"
tab_active = "#3a5ca8"
tab_fg = "#222"
tab_active_fg = "#fff"
tab_border = "#d1d5db"
user_card_bg = "#fff"
user_card_border = "#e0e0e0"
user_fg = "#2d5c88"
user_hover_fg = "#1a3a5a"

class ScrollableNotebook(ttk.Notebook):
    def __init__(self, master=None, **kw):
        super().__init__(master, **kw)
        self.enable_traversal()
        self._add_scrollbar()

    def _add_scrollbar(self):
        # Yatay scroll bar ekle (sekme taşarsa)
        self.canvas = tk.Canvas(self, height=32, bg=tab_bg, highlightthickness=0)
        self.scrollbar = tk.Scrollbar(self, orient="horizontal", command=self.canvas.xview)
        self.canvas.configure(xscrollcommand=self.scrollbar.set)
        self.canvas.pack(side="bottom", fill="x", expand=False)
        self.scrollbar.pack(side="bottom", fill="x", expand=False)
        self.bind("<Configure>", self._on_configure)

    def _on_configure(self, event):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

# Sistem teması algılama (Windows/macOS)
def detect_system_dark_mode():
    try:
        if platform.system() == "Windows":
            import winreg
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\\Microsoft\\Windows\\CurrentVersion\\Themes\\Personalize")
            value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            return value == 0  # 0: dark, 1: light
        elif platform.system() == "Darwin":
            import subprocess
            result = subprocess.run([
                'defaults', 'read', '-g', 'AppleInterfaceStyle'
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            return b'Dark' in result.stdout
    except Exception:
        pass
    return False

HISTORY_FILE = "_insta_rapor_history.json"

class InstaRaporApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Instagram Rapor 3.0")
        self.root.geometry("700x800")
        # Tema renkleri
        self.light_theme = {
            'theme_bg': "#f7f9fa",
            'tab_bg': "#e9ecf1",
            'tab_active': "#3a5ca8",
            'tab_fg': "#222",
            'tab_active_fg': "#fff",
            'tab_border': "#d1d5db",
            'user_card_bg': "#fff",
            'user_card_border': "#e0e0e0",
            'user_fg': "#2d5c88",
            'user_hover_fg': "#1a3a5a",
            'menu_fg': "#3a5ca8",
            'empty_fg': "#888"
        }
        self.dark_theme = {
            'theme_bg': "#181c22",
            'tab_bg': "#23272f",
            'tab_active': "#3a5ca8",
            'tab_fg': "#e0e6f0",
            'tab_active_fg': "#fff",
            'tab_border': "#23272f",
            'user_card_bg': "#23272f",
            'user_card_border': "#2a2e38",
            'user_fg': "#7ecfff",
            'user_hover_fg': "#b3e0ff",
            'menu_fg': "#7ecfff",
            'empty_fg': "#888"
        }
        self.is_dark = detect_system_dark_mode()
        self.theme = self.dark_theme.copy() if self.is_dark else self.light_theme.copy()
        self.zip_path = self.find_instagram_zip()
        self.username = self.extract_username_from_zip() if self.zip_path else "Instagram"
        self.report_date = self.get_zip_date() if self.zip_path else None
        self.sort_option = "Yeniden Eskiye"  # Varsayılan sıralama
        self.lists = self.load_all_lists()
        self.setup_style()
        self.build_ui()

    def find_instagram_zip(self):
        downloads = get_downloads_path()
        zips = glob.glob(os.path.join(downloads, "instagram-*.zip"))
        if not zips:
            return None
        # En yeni zip dosyasını seç
        zips.sort(key=os.path.getmtime, reverse=True)
        return zips[0]

    def extract_username_from_zip(self):
        # Örnek: instagram-canoruckahya-2025-07-25-xxxx.zip
        base = os.path.basename(self.zip_path)
        if base.startswith("instagram-"):
            parts = base.split("-")
            if len(parts) > 1:
                return parts[1]
        return "Instagram"

    def get_zip_date(self):
        # Dosyanın son değiştirilme tarihini oku
        try:
            ts = os.path.getmtime(self.zip_path)
            import datetime
            dt = datetime.datetime.fromtimestamp(ts)
            return dt.strftime("%d.%m.%Y %H:%M")
        except Exception:
            return None

    def setup_style(self):
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('TNotebook.Tab', background=self.theme['tab_bg'], foreground=self.theme['tab_fg'], font=('Segoe UI', 10, 'bold'), padding=[8, 2], borderwidth=0)
        style.map('TNotebook.Tab', background=[('selected', self.theme['tab_active'])], foreground=[('selected', self.theme['tab_active_fg'])])
        style.configure('TNotebook', background=self.theme['theme_bg'], borderwidth=0)
        style.configure('TFrame', background=self.theme['theme_bg'])
        style.layout('TNotebook.Tab', [
            ('Notebook.tab', {'sticky': 'nswe', 'children': [
                ('Notebook.padding', {'side': 'top', 'sticky': 'nswe', 'children': [
                    ('Notebook.label', {'side': 'top', 'sticky': ''})
                ]})
            ]})
        ])

    def build_ui(self):
        for widget in self.root.winfo_children():
            widget.destroy()
        self.root.configure(bg=self.theme['theme_bg'])
        top_frame = tk.Frame(self.root, bg=self.theme['theme_bg'])
        top_frame.pack(fill='x', pady=(10, 0))
        title = tk.Label(top_frame, text=f"{self.username} Instagram Raporu", font=("Segoe UI", 18, "bold"), bg=self.theme['theme_bg'], fg=self.theme['user_fg'])
        title.pack(side="left", padx=(18, 0), pady=8)
        self.theme_btn = tk.Button(top_frame, text="🌙 Karanlık Mod" if not self.is_dark else "☀️ Açık Mod", font=("Segoe UI", 10, "bold"), bg=self.theme['tab_bg'], fg=self.theme['tab_fg'], relief="flat", cursor="hand2", command=self.toggle_theme)
        self.theme_btn.pack(side="right", padx=(0, 18), pady=8)
        takipci_sayisi = len(self.lists.get("Takipçiler", []))
        takip_edilen_sayisi = len(self.lists.get("Takip Ettiklerim", []))
        stats_label = tk.Label(self.root, text=f"Takipçi: {takipci_sayisi}   Takip Edilen: {takip_edilen_sayisi}", font=("Segoe UI", 11, "bold"), bg=self.theme['theme_bg'], fg=self.theme['user_fg'])
        stats_label.pack(pady=(0, 4))
        if self.report_date:
            date_label = tk.Label(self.root, text=f"Raporun indirilme tarihi: {self.report_date}", font=("Segoe UI", 10, "italic"), bg=self.theme['theme_bg'], fg=self.theme['empty_fg'])
            date_label.pack(pady=(0, 2))
        footer = tk.Label(self.root, text="by instagramRapor app by can oruckahya", font=("Segoe UI", 9, "italic"), bg=self.theme['theme_bg'], fg=self.theme['empty_fg'])
        footer.pack(side="bottom", pady=(0, 6))
        self.notebook = ttk.Notebook(self.root, style='TNotebook')
        self.notebook.pack(fill='both', expand=True, padx=18, pady=8)
        self.create_tabs()

    def toggle_theme(self):
        self.is_dark = not self.is_dark
        self.theme = self.dark_theme.copy() if self.is_dark else self.light_theme.copy()
        self.setup_style()
        self.build_ui()

    def load_all_lists(self):
        # Dosya yolları zip içindeki connections/followers_and_following/ ile başlar
        base_path = "connections/followers_and_following/"
        files = {
            "Takipçiler": "followers_1.html",
            "Takip Ettiklerim": "following.html",
            "Yakın Arkadaşlar": "close_friends.html",
            "Favoriler": "profiles_you've_favorited.html",
            "Engellenenler": "blocked_profiles.html",
            "Kısıtlananlar": "restricted_profiles.html",
            "Gelen İstekler": "follow_requests_you've_received.html",
            "Gönderilen İstekler": "recent_follow_requests.html",
            "Kaldırılan Öneriler": "removed_suggestions.html",
            "Çıkan Takipçiler": "recently_unfollowed_profiles.html"
        }
        lists = {}
        for key, fname in files.items():
            if self.zip_path:
                path = base_path + fname
                lists[key] = extract_users_with_dates(path, zip_path=self.zip_path)
            else:
                # Masaüstü yolu yedeği
                desktop = get_desktop_path()
                local_path = os.path.join(desktop, "connections", "followers_and_following", fname)
                lists[key] = extract_users_with_dates(local_path)
        followers = lists["Takipçiler"]
        following = lists["Takip Ettiklerim"]
        lists["Beni Geri Takip Etmeyenler"] = compare_lists(following, followers)
        lists["Benim Geri Takip Etmediklerim"] = compare_lists_reverse(followers, following)
        return lists

    def create_tabs(self):
        main_tab_order = [
            "Beni Geri Takip Etmeyenler",
            "Benim Geri Takip Etmediklerim",
            "Yakın Arkadaşlar",
            "Favoriler",
            "Takipçi Analizi"
        ]
        other_tab_order = [
            "Engellenenler",
            "Kısıtlananlar",
            "Gelen İstekler",
            "Gönderilen İstekler",
            "Kaldırılan Öneriler",
            "Çıkan Takipçiler"
        ]
        self.tab_names = []
        self.other_tab_order = []
        for tab_name in main_tab_order:
            if tab_name == "Takipçi Analizi":
                display_name = tab_name
                self.tab_names.append(display_name)
                self.create_analysis_tab(display_name)
            else:
                count = len(self.lists.get(tab_name, []))
                display_name = f"{tab_name} ({count})"
                self.tab_names.append(display_name)
                self.create_user_tab(tab_name, self.lists.get(tab_name, []), display_name)
        for tab_name in other_tab_order:
            count = len(self.lists.get(tab_name, []))
            display_name = f"{tab_name} ({count})"
            self.other_tab_order.append(display_name)
        self.create_other_tab()
        try:
            idx = self.tab_names.index(f"Beni Geri Takip Etmeyenler ({len(self.lists.get('Beni Geri Takip Etmeyenler', []))})")
            self.notebook.select(idx)
        except ValueError:
            pass

    def create_analysis_tab(self, display_name):
        frame = tk.Frame(self.notebook, bg=self.theme['theme_bg'])
        self.notebook.add(frame, text=display_name)
        # --- Analiz sekmesi açıldığında veri kaydetme ve karşılaştırma ---
        def do_analysis():
            # Kayıt dosyasını oku
            try:
                with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                    history = json.load(f)
            except Exception:
                history = []
            takipciler = self.lists.get("Takipçiler", [])
            usernames = [u[0] for u in takipciler]
            # Eğer eski veri varsa karşılaştırmalı analiz/grafik sun
            if history:
                last = history[-1]
                eski_set = set(last["usernames"])
                yeni_set = set(usernames)
                gelenler = list(yeni_set - eski_set)
                gidenler = list(eski_set - yeni_set)
                # Grafik ve özet
                info = tk.Label(frame, text=f"Gelen Takipçi: {len(gelenler)}   Giden Takipçi: {len(gidenler)}", font=("Segoe UI", 12, "bold"), bg=self.theme['theme_bg'], fg=self.theme['user_fg'])
                info.pack(pady=(18, 8))
                # Basit çubuk grafik
                fig, ax = plt.subplots(figsize=(3.2, 2), dpi=100)
                ax.bar(["Gelen", "Giden"], [len(gelenler), len(gidenler)], color=["#00b894", "#ff7675"])
                ax.set_ylabel("Kişi Sayısı")
                ax.set_title("Takipçi Değişimi", color=self.theme['user_fg'], fontsize=11)
                fig.patch.set_facecolor(self.theme['theme_bg'])
                buf = io.BytesIO()
                plt.savefig(buf, format='png', bbox_inches='tight', transparent=True)
                plt.close(fig)
                buf.seek(0)
                img = Image.open(buf)
                photo = ImageTk.PhotoImage(img)
                canvas = tk.Canvas(frame, width=img.width, height=img.height, bg=self.theme['theme_bg'], highlightthickness=0)
                canvas.create_image(0, 0, anchor='nw', image=photo)
                canvas.image = photo
                canvas.pack(pady=(0, 10))
                # Listeler
                if gelenler:
                    yeni_label = tk.Label(frame, text="Gelen Takipçiler:", font=("Segoe UI", 11, "bold"), bg=self.theme['theme_bg'], fg=self.theme['user_fg'])
                    yeni_label.pack(pady=(10, 0))
                    for username in gelenler:
                        l = tk.Label(frame, text=username, fg=self.theme['user_fg'], bg=self.theme['theme_bg'], font=("Segoe UI", 10, "underline"))
                        l.pack(anchor="w", padx=30)
                if gidenler:
                    eski_label = tk.Label(frame, text="Giden Takipçiler:", font=("Segoe UI", 11, "bold"), bg=self.theme['theme_bg'], fg=self.theme['user_fg'])
                    eski_label.pack(pady=(10, 0))
                    for username in gidenler:
                        l = tk.Label(frame, text=username, fg=self.theme['user_fg'], bg=self.theme['theme_bg'], font=("Segoe UI", 10, "underline"))
                        l.pack(anchor="w", padx=30)
            else:
                info = tk.Label(frame, text="İlk veri kaydedildi. Sonraki raporda karşılaştırma yapılacak.", font=("Segoe UI", 12, "bold"), bg=self.theme['theme_bg'], fg=self.theme['user_fg'])
                info.pack(pady=(18, 8))
            # Son olarak mevcut veriyi kaydet
            self.save_current_followers_to_history()
        # Sadece ilk açılışta sor
        def ask_save():
            for widget in frame.winfo_children():
                widget.destroy()
            label = tk.Label(frame, text="Takipçi değişimini analiz etmek için verileri kaydetmek ve sonraki raporda karşılaştırmak ister misiniz?", font=("Segoe UI", 12), bg=self.theme['theme_bg'], fg=self.theme['user_fg'], wraplength=500)
            label.pack(pady=30)
            btn = tk.Button(frame, text="Evet, verileri kaydet ve analiz et", font=("Segoe UI", 11, "bold"), bg=self.theme['tab_bg'], fg=self.theme['user_fg'], relief="raised", cursor="hand2", command=lambda: [do_analysis()])
            btn.pack(pady=10)
        ask_save()

    def sort_user_list(self, user_list):
        # user_list: [(username, url, date), ...]
        if self.sort_option == "Eskiden Yeniye":
            return sorted(user_list, key=lambda x: self.parse_date(x[2]) or "")
        elif self.sort_option == "Yeniden Eskiye":
            return sorted(user_list, key=lambda x: self.parse_date(x[2]) or "", reverse=True)
        elif self.sort_option == "A'dan Z'ye":
            return sorted(user_list, key=lambda x: x[0].lower())
        elif self.sort_option == "Z'den A'ya":
            return sorted(user_list, key=lambda x: x[0].lower(), reverse=True)
        return user_list

    def parse_date(self, date_str):
        # Örnek: Jul 18, 2025 11:23 am
        import datetime
        try:
            return datetime.datetime.strptime(date_str, "%b %d, %Y %I:%M %p")
        except Exception:
            return None

    def create_user_tab(self, tab_name, user_list, display_name):
        frame = tk.Frame(self.notebook, bg=self.theme['theme_bg'])
        self.notebook.add(frame, text=display_name)
        # Sıralama menüsü sağ üstte
        sort_frame = tk.Frame(frame, bg=self.theme['theme_bg'])
        sort_frame.pack(fill='x', pady=(4, 0), padx=10)
        sort_frame.grid_columnconfigure(0, weight=1)
        # Boşluk bırakmak için
        tk.Label(sort_frame, text="", bg=self.theme['theme_bg']).grid(row=0, column=0, sticky="ew")
        sort_options = ["Yeniden Eskiye", "Eskiden Yeniye", "A'dan Z'ye", "Z'den A'ya"]
        sort_menu = ttk.Combobox(sort_frame, values=sort_options, state="readonly", width=15)
        sort_menu.set(self.sort_option)
        # Modern tema için style
        style = ttk.Style()
        style.configure('Custom.TCombobox',
                        fieldbackground=self.theme['tab_bg'],
                        background=self.theme['tab_bg'],
                        foreground=self.theme['user_fg'],
                        selectforeground=self.theme['user_fg'],
                        selectbackground=self.theme['tab_bg'],
                        borderwidth=0,
                        font=("Segoe UI", 10, "bold"))
        sort_menu.configure(style='Custom.TCombobox')
        sort_menu.grid(row=0, column=2, sticky="e", padx=(0, 0))
        sort_label = tk.Label(sort_frame, text="Sırala:", bg=self.theme['theme_bg'], fg=self.theme['user_fg'], font=("Segoe UI", 10, "bold"))
        sort_label.grid(row=0, column=1, sticky="e", padx=(0, 4))
        def on_sort_change(event=None):
            self.sort_option = sort_menu.get()
            for widget in frame.winfo_children():
                if isinstance(widget, tk.Canvas) or isinstance(widget, tk.Scrollbar):
                    widget.destroy()
            self.render_user_list(frame, user_list)
        sort_menu.bind("<<ComboboxSelected>>", on_sort_change)
        self.render_user_list(frame, user_list)

    def render_user_list(self, frame, user_list):
        canvas = tk.Canvas(frame, bg=self.theme['theme_bg'], highlightthickness=0)
        scrollbar = tk.Scrollbar(frame, orient="vertical", command=canvas.yview)
        scroll_frame = tk.Frame(canvas, bg=self.theme['theme_bg'])
        scroll_frame.bind(
            "<Configure>",
            lambda e, c=canvas, f=scroll_frame: c.configure(scrollregion=c.bbox("all"))
        )
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind("<Enter>", lambda e: canvas.bind_all("<MouseWheel>", _on_mousewheel))
        canvas.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))
        sorted_list = self.sort_user_list(user_list)
        for idx, (username, url, date) in enumerate(sorted_list, 1):
            card = tk.Frame(scroll_frame, bg=self.theme['user_card_bg'], highlightbackground=self.theme['user_card_border'], highlightthickness=1, bd=0)
            card.pack(anchor="w", padx=10, pady=6, fill='x')
            user_label = tk.Label(card, text=f"{idx}. {username}", fg=self.theme['user_fg'], bg=self.theme['user_card_bg'], cursor="hand2", font=("Segoe UI", 11, "bold"), anchor="w")
            user_label.pack(side="left", padx=(8, 4), pady=6)
            user_label.bind("<Double-Button-1>", lambda e, u=url: on_user_double_click(e, u))
            user_label.bind("<Enter>", lambda e, l=user_label: l.config(fg=self.theme['user_hover_fg'], font=("Segoe UI", 11, "bold", "underline")))
            user_label.bind("<Leave>", lambda e, l=user_label: l.config(fg=self.theme['user_fg'], font=("Segoe UI", 11, "bold")))
            date_label = tk.Label(card, text=date, fg=self.theme['empty_fg'], bg=self.theme['user_card_bg'], font=("Segoe UI", 10), anchor="w")
            date_label.pack(side="left", padx=(12, 0), pady=6)

    def save_current_followers_to_history(self):
        # Sadece takipçi listesini ve rapor tarihini kaydet
        if not self.zip_path:
            return
        takipciler = self.lists.get("Takipçiler", [])
        usernames = [u[0] for u in takipciler]
        data = {
            "date": self.report_date,
            "usernames": usernames
        }
        # Eski kayıtları oku
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                history = json.load(f)
        except Exception:
            history = []
        # Aynı tarihli kayıt varsa güncelle, yoksa ekle
        found = False
        for rec in history:
            if rec["date"] == self.report_date:
                rec["usernames"] = usernames
                found = True
        if not found:
            history.append(data)
        # Sadece son 10 kaydı tut
        history = sorted(history, key=lambda x: x["date"]) [-10:]
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)

    def create_other_tab(self):
        other_tab = tk.Frame(self.notebook, bg=self.theme['theme_bg'])
        self.notebook.add(other_tab, text="Diğer")
        label = tk.Label(other_tab, text="🧊 Diğer Opsiyonel Listeler", fg=self.theme['menu_fg'], bg=self.theme['theme_bg'], font=("Segoe UI", 14, "bold"))
        label.pack(pady=(30, 10))
        menu_frame = tk.Frame(other_tab, bg=self.theme['theme_bg'])
        menu_frame.pack(pady=10)
        self.other_list_frame = tk.Frame(other_tab, bg=self.theme['theme_bg'])
        self.other_list_frame.pack(fill='both', expand=True, padx=10, pady=10)
        # Butonları grid şeklinde (2 satır) göster
        max_per_row = 4
        for i, display_name in enumerate(self.other_tab_order):
            btn = tk.Button(menu_frame, text=display_name, font=("Segoe UI", 11, "bold"), bg=self.theme['tab_bg'], fg=self.theme['user_fg'], relief="flat", cursor="hand2", padx=16, pady=6,
                            command=lambda t=display_name: self.show_other_list(t))
            row = i // max_per_row
            col = i % max_per_row
            btn.grid(row=row, column=col, padx=8, pady=4, sticky="ew")
        if self.other_tab_order:
            self.show_other_list(self.other_tab_order[0])

    def show_other_list(self, display_name):
        for widget in self.other_list_frame.winfo_children():
            widget.destroy()
        # display_name: "Sekme Adı (Sayı)" → sekme adını bul
        tab_name = display_name.rsplit(" (", 1)[0]
        user_list = self.lists.get(tab_name, [])
        if not user_list:
            empty = tk.Label(self.other_list_frame, text="Veri bulunamadı.", fg=self.theme['empty_fg'], bg=self.theme['theme_bg'], font=("Segoe UI", 12))
            empty.pack(pady=30)
            return
        # Sıralama menüsü sağ üstte
        sort_frame = tk.Frame(self.other_list_frame, bg=self.theme['theme_bg'])
        sort_frame.pack(fill='x', pady=(4, 0), padx=10)
        sort_frame.grid_columnconfigure(0, weight=1)
        tk.Label(sort_frame, text="", bg=self.theme['theme_bg']).grid(row=0, column=0, sticky="ew")
        sort_options = ["Yeniden Eskiye", "Eskiden Yeniye", "A'dan Z'ye", "Z'den A'ya"]
        sort_menu = ttk.Combobox(sort_frame, values=sort_options, state="readonly", width=15)
        sort_menu.set(self.sort_option)
        style = ttk.Style()
        style.configure('Custom.TCombobox',
                        fieldbackground=self.theme['tab_bg'],
                        background=self.theme['tab_bg'],
                        foreground=self.theme['user_fg'],
                        selectforeground=self.theme['user_fg'],
                        selectbackground=self.theme['tab_bg'],
                        borderwidth=0,
                        font=("Segoe UI", 10, "bold"))
        sort_menu.configure(style='Custom.TCombobox')
        sort_menu.grid(row=0, column=2, sticky="e", padx=(0, 0))
        sort_label = tk.Label(sort_frame, text="Sırala:", bg=self.theme['theme_bg'], fg=self.theme['user_fg'], font=("Segoe UI", 10, "bold"))
        sort_label.grid(row=0, column=1, sticky="e", padx=(0, 4))
        def on_sort_change(event=None):
            self.sort_option = sort_menu.get()
            for widget in self.other_list_frame.winfo_children():
                if isinstance(widget, tk.Canvas) or isinstance(widget, tk.Scrollbar):
                    widget.destroy()
            self.render_other_user_list(user_list)
        sort_menu.bind("<<ComboboxSelected>>", on_sort_change)
        self.render_other_user_list(user_list)

    def render_other_user_list(self, user_list):
        canvas = tk.Canvas(self.other_list_frame, bg=self.theme['theme_bg'], highlightthickness=0)
        scrollbar = tk.Scrollbar(self.other_list_frame, orient="vertical", command=canvas.yview)
        scroll_frame = tk.Frame(canvas, bg=self.theme['theme_bg'])
        scroll_frame.bind(
            "<Configure>",
            lambda e, c=canvas, f=scroll_frame: c.configure(scrollregion=c.bbox("all"))
        )
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind("<Enter>", lambda e: canvas.bind_all("<MouseWheel>", _on_mousewheel))
        canvas.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))
        sorted_list = self.sort_user_list(user_list)
        for idx, (username, url, date) in enumerate(sorted_list, 1):
            card = tk.Frame(scroll_frame, bg=self.theme['user_card_bg'], highlightbackground=self.theme['user_card_border'], highlightthickness=1, bd=0)
            card.pack(anchor="w", padx=10, pady=6, fill='x')
            user_label = tk.Label(card, text=f"{idx}. {username}", fg=self.theme['user_fg'], bg=self.theme['user_card_bg'], cursor="hand2", font=("Segoe UI", 11, "bold"), anchor="w")
            user_label.pack(side="left", padx=(8, 4), pady=6)
            user_label.bind("<Double-Button-1>", lambda e, u=url: on_user_double_click(e, u))
            user_label.bind("<Enter>", lambda e, l=user_label: l.config(fg=self.theme['user_hover_fg'], font=("Segoe UI", 11, "bold", "underline")))
            user_label.bind("<Leave>", lambda e, l=user_label: l.config(fg=self.theme['user_fg'], font=("Segoe UI", 11, "bold")))
            date_label = tk.Label(card, text=date, fg=self.theme['empty_fg'], bg=self.theme['user_card_bg'], font=("Segoe UI", 10), anchor="w")
            date_label.pack(side="left", padx=(12, 0), pady=6)

if __name__ == "__main__":
    root = tk.Tk()
    app = InstaRaporApp(root)
    root.mainloop()
