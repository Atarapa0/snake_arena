# 🐍 Snake Arena v2.5 - KOLAY KULLANIM REHBERİ

Bu proje, öğrencilerin kendi yılan botlarını (AI) yazıp yarıştırdığı bir platformdur. **Öğretmene sormadan her şeyi buradan halledebilirsiniz.**

---

## 🚀 1. SİSTEMİ NASIL ÇALIŞTIRIRIM?
1. Bilgisayarında terminali aç.
2. `pip install flask numpy` komutunu çalıştır.
3. `python app.py` komutuyla sistemi başlat.
4. Tarayıcıdan `http://localhost:5001` adresine gir.

---

## 🐍 2. KODU HANGİ FORMATTA YAZACAĞIM?
Ajanın `/example_agents/ahmet.py` dosyasındaki gibi olmalıdır. **Tek geçerli format budur:**

```python
from base_agent import BaseAgent
import numpy as np

class MyAgent(BaseAgent):
    def act(self, obs: dict) -> int:
        # SİSTEM SANA ŞUNLARI GÖNDERİR:
        grid = obs["grid"]   # 30x30 Harita (Matris)
        stats = obs["stats"] # [Kendi_Enerjin, Kendi_Boyun, Rakip_Boyu, Rakip_Enerjisi]

        # SENİN YAPMAN GEREKEN: 0, 1, 2 veya 3 dönmek.
        # 0: YUKARI, 1: SAĞ, 2: AŞAĞI, 3: SOL
        return 1 
```

---

## 🏋️ 3. EĞİTİM (TRAINING) NASIL YAPILIR?
Eğitim sayfası, yazdığın kodun hangi meyveye odaklanacağını senin yerine test ederek sana en iyi **zeka dosyasını (.json)** verir.
1. **Modelini Yükle:** Kendi yazdığın `.py` dosyasını seç.
2. **Rakibini Yükle:** Karşısında yarışacağı bir rakip `.py` dosyası seç (Eğitim için rakip şarttır!).
3. **Eğitimi Başlat:** Sistem 50-100 maç yapar ve en iyi parametreleri bulur.
4. **Zaman Kısıtlaması (Opsiyonel):** Eğer kutucuğu işaretlersen, yılanın 0.1 saniye gibi kısıtlı sürede karar vermeye zorlanır.
5. **İndir:** Eğitim bitince sana bir `.json` dosyası verir. Bu senin "beynin"dir.

---

## 🏆 4. ARENA VE PUANLAMA MANTIĞI
Arenada yılanları yarıştırırken puanlar şöyledir (Ayarları değiştirmezsen):

- **3 PUAN (K.O.):** Rakibi direkt öldürürsen (Senin gövdene veya duvara çarpması).
- **2 PUAN (PUANLA):** Süre (Adım) bittiğinde hayatta kalıp rakibinden daha uzunsan.
- **1 PUAN (BERABERLİK):** İkiniz de yaşarsanız ve boylarınız aynıysa.

### 🍎 MEYVE REHBERİ (Matris ID'leri)
- **ID 6 (Kırmızı):** Boy +1, Enerji +20
- **ID 7 (Altın):** Boy +3, Enerji +50
- **ID 8 (Zehir):** **Boy -2**, Enerji +100 (Açlıktan ölmemek için hayat kurtarır!)
- **ID 5 (Duvar):** Çarparsan direk ölürsün.

---

## 💡 ÖNEMLİ İPUÇLARI (TİYOLAR)
1. **Zehir Stratejisi:** Enerjin 10-20 altına düştüğünde eğer elma uzaktaysa **zehir (8)** ye! Boyun kısalır ama enerjin dolar, ölmessin.
2. **Alan Daraltma:** Rakibin kafasını duvara veya kendi gövdene doğru sıkıştırmaya çalış. Onu hata yapmaya (v2.5'te buna zorlanıyor) itersen 3 puan senindir.
3. **Torus Dünyası:** Harita kenarları sonsuzdur; sağdan çıkarsan soldan girersin. Bunu kaçış yolu olarak kullan.
4. **Kod Güvenliği:** Kodun hata verirse veya belirlenen saniyeyi (örn: 0.1 sn) aşarsan o maçta hükmen mağlup sayılırsın.

**ÖZETLE:** Kodla (Python) -> Eğit (JSON al) -> Arenada Yarıştır (Şampiyon Ol)!
