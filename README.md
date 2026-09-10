# Instagram Rapor / InstaRapor

Instagram veri arşivinden (ZIP) takipçi ve takip analizi yapan web uygulaması.

## Özellikler

- **Beni geri takip etmeyenler** / **Benim geri takip etmediklerim**
- **Çıkan takipçiler** (Instagram’ın “recently unfollowed” listesi)
- Önceki yüklemeyle **gelen / giden takipçi** karşılaştırması
- Yakın arkadaşlar, favoriler, engellenenler, istekler vb.
- Hem **HTML** hem **JSON** Instagram dışa aktarma formatı
- Arama ve sıralama (tarih / A–Z)

## Kurulum

```bash
pip install -r requirements.txt
python app.py
```

Tarayıcıda: http://127.0.0.1:5000

## Kullanım

1. Instagram → Ayarlar → Merkezin → **Bilgilerinizi indirin**
2. “Bağlantılar” / takipçi–takip verisini içeren ZIP’i indir
3. ZIP’i InstaRapor’a yükle

Eski masaüstü (Tkinter) sürümü Instagram export formatı değişince kırılıyordu.
Bu web sürümü dosya adlarını ZIP içinde tarar ve birden fazla HTML/JSON yapısını destekler.

## Geliştirici

Can Oruckahya — InstaRapor
