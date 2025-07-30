# Instagram Rapor 3.0

Instagram verilerinizi analiz eden ve takipçi değişimlerini takip eden modern bir Python uygulaması.

## Özellikler

- 📊 **Takipçi Analizi**: Gelen ve giden takipçileri karşılaştırmalı analiz
- 🎨 **Modern UI**: Karanlık/Açık tema desteği ile modern arayüz
- 📈 **Grafik Görselleştirme**: Takipçi değişimlerini grafik olarak gösterim
- 🔍 **Detaylı Listeler**: 
  - Beni geri takip etmeyenler
  - Benim geri takip etmediklerim
  - Yakın arkadaşlar
  - Favoriler
  - Engellenenler
  - Kısıtlananlar
  - Gelen/Gönderilen istekler
  - Kaldırılan öneriler
  - Çıkan takipçiler
- 📅 **Tarih Takibi**: Takipçi değişimlerini tarih bazında takip
- 🔄 **Otomatik Güncelleme**: Yeni Instagram verilerini otomatik algılama

## Kurulum

### Gereksinimler

```bash
pip install -r requirements.txt
```

### Gerekli Kütüphaneler

```
tkinter
beautifulsoup4
matplotlib
pillow
```

## Kullanım

1. Instagram'dan veri indirin (ZIP formatında)
2. ZIP dosyasını Downloads klasörüne koyun
3. Uygulamayı çalıştırın:

```bash
python app.py
```

## Özellikler Detayı

### Ana Sekmeler
- **Beni Geri Takip Etmeyenler**: Takip ettiğiniz ama sizi takip etmeyen kullanıcılar
- **Benim Geri Takip Etmediklerim**: Sizi takip eden ama siz takip etmediğiniz kullanıcılar
- **Yakın Arkadaşlar**: Yakın arkadaş listeniz
- **Favoriler**: Favori profilleriniz
- **Takipçi Analizi**: Takipçi değişimlerinin grafiksel analizi

### Diğer Sekmeler
- Engellenen profiller
- Kısıtlanan profiller
- Gelen takip istekleri
- Gönderilen takip istekleri
- Kaldırılan öneriler
- Son zamanlarda çıkan takipçiler

### Sıralama Seçenekleri
- Yeniden Eskiye
- Eskiden Yeniye
- A'dan Z'ye
- Z'den A'ya

## Tema Desteği

Uygulama otomatik olarak sistem temasını algılar ve uygun temayı uygular:
- **Açık Tema**: Modern, temiz görünüm
- **Karanlık Tema**: Göz yorgunluğunu azaltan koyu tema

## Geliştirici

**Can Oruckahya** - Instagram Rapor 3.0

## Lisans

Bu proje MIT lisansı altında lisanslanmıştır.

## Katkıda Bulunma

1. Fork yapın
2. Feature branch oluşturun (`git checkout -b feature/AmazingFeature`)
3. Commit yapın (`git commit -m 'Add some AmazingFeature'`)
4. Push yapın (`git push origin feature/AmazingFeature`)
5. Pull Request açın 