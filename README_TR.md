# Instagram Rapor 3.1 (Hibrit Sürüm)

Instagram takipçi ve takip edilen verilerinizi analiz eden, geri takip etmeyenleri tespit eden ve aylık değişimleri takip eden modern Python masaüstü uygulaması.

## Yenilikler ve Özellikler

- 🌐 **Güvenli Web Veri Çekici (Ayda 1 Kez Modu)**: Kendi açık tarayıcınız üzerinden **%100 Sadece Okuma (Read-Only)** ve rastgele insani gecikmelerle (2.2–4.5 sn + periyodik mola) şifre vermeden veri çeker.
- 📜 **Yedek Pencere Kaydırıcı Modu**: Instagram arka plan API yanıtları değişirse açık Takipçi / Takip Edilen penceresini insan hızında kaydırarak doğrudan ekrandan toplar.
- 📦 **Tamir Edilmiş Resmi Veri Okuyucu (ZIP / HTML / JSON)**: Meta'nın güncel `_u/kullanici_adi` link yapısını ve hem HTML hem JSON dışa aktarımlarını tüm 10 kategoriyle okur.
- 🔍 **Canlı Arama ve Tek Tıkla Profil Açma**: Tüm listelerde anlık kullanıcı arama ve `Profili Aç ↗` butonu.
- 📊 **Aylık Takipçi Analizi (`snapshots/` + `_insta_rapor_history.json`)**: Gelen ve giden takipçileri grafikle karşılaştırır; web taramasında yeni takipten çıkanları otomatik tespit eder.
- 🎨 **Otomatik Karanlık / Açık Tema**: Windows/macOS sistem temasını algılar ve tek tıkla tema değiştirir.

## Hızlı Başlatma ve Kurulum

### En Kolay Yöntem (Çift Tık)
1. Klasördeki **`Baslat.bat`** dosyasına çift tıklayın (eksik paket varsa otomatik kurar ve uygulamayı terminal penceresi bırakmadan doğrudan açar).
2. Python bilgisayarınızda hiç kurulu değilse ilk seferde **`setup_launcher.bat`** dosyasını çalıştırabilirsiniz.

### Manuel Kurulum

- Python 3.10+ (`tkinter` dahil)

```bash
pip install -r requirements.txt
python app.py
```

## Hibrit Kullanım (2 Yöntem)

### Yöntem 1: Ayda 1 Kez Güvenli Web Veri Çekici (ZIP Beklemeden Hızlı Mod)
1. **`Baslat.bat`** dosyasına çift tıklayarak uygulamayı açın.
2. Üst menüden **🌐 Web'den Veri Çek (Güvenli Mod)** butonuna tıklayın.
3. **Tek Seferlik Kolay Kurulum (F12'siz):** **🔖 Sürükle-Bırak Yer İmi Kurulumunu Aç** butonuna basın (veya `Tarayici_Asistani_Kurulum.html` dosyasını açın). Açılan sayfadaki **🛡️ Insta Rapor Çekici** butonunu tarayıcınızın Yer İmleri Çubuğuna (`Ctrl+Shift+B`) sürükleyip bırakın. *(İsterseniz **📋 Güvenli Tarayıcı Kodunu Kopyala** ile F12 → Console yöntemini de kullanabilirsiniz.)*
4. Tarayıcınızda `instagram.com` hesabınız açıkken yer imindeki **🛡️ Insta Rapor Çekici** butonuna tıklayın ve sağ altta açılan panelde **⚡ Otomatik Güvenli Okuyucu**yu başlatın.
5. İşlem bitince veriler panoya kopyalanır ve `instagram_web_rapor_YYYY-MM-DD.json` olarak indirilir. Uygulamaya dönüp **📥 Panodan Yapıştır ve Analiz Et** (veya **📂 İndirilen JSON Dosyasını Seç**) butonuna tıklayın.

> **Güvenlik Notu:** `web_collector.js` kesinlikle otomatik takipten çıkma (`unfollow`) veya `POST` isteği göndermez; yalnızca okuma yapar.

### Yöntem 2: Resmi Instagram Veri Paketi (%0 Risk, Tüm 10 Liste)
1. Instagram → Hesaplar Merkezi → **Bilgilerinizi indirin** bölümünden verinizi (HTML veya JSON formatında) indirin ve `.zip` dosyasını `Downloads` klasörüne kaydedin (veya ayıklanan `followers_and_following` klasörünü seçin).
2. Uygulamayı çalıştırın:

```bash
python app.py
```

Uygulama en güncel kaynağı (`snapshots/`, `Downloads/instagram_web_rapor_*.json`, `Downloads/instagram-*.zip` veya yerel `followers_and_following/` klasörü) otomatik algılar; isterseniz **📂 Veri Kaynağı Seç** butonuyla değiştirebilirsiniz.

## Sekmeler ve Listeler

- **Ana Sekmeler:**
  - Beni Geri Takip Etmeyenler
  - Benim Geri Takip Etmediklerim
  - Yakın Arkadaşlar
  - Favoriler
  - Takipçi Analizi (Gelen / Giden Takipçiler ve Grafik)
- **Diğer Sekmesi:**
  - Engellenenler, Kısıtlananlar, Gelen İstekler, Gönderilen İstekler, Kaldırılan Öneriler, Çıkan / Takipten Çıkılanlar

## Geliştirici

**Can Oruckahya** - Instagram Rapor 3.1
