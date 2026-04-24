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

    def handle_reward(self, reward: float, done: bool):
        # RL EĞİTİMİ İÇİN (OPSİYONEL): 
        # Motor sana her adımda ödül (elma:+10, ölüm:-50 vb.) gönderir.
        pass
```

### Sinir Ağı Kullanmak İsteyenler İçin (model.json ile):

Eğer kendi sinir ağı modelinizi kullanmak istiyorsanız, aşağıdaki formatta bir `.py` dosyası yazın:

```python
import os
import json
import numpy as np
from base_agent import BaseAgent

class MyAgent(BaseAgent):
    def __init__(self, name="BenimAjan", data_dir=None):
        super().__init__(name=name, data_dir=data_dir)
        
        # JSON model dosyasının yolunu bul
        if self.data_dir:
            json_path = os.path.join(self.data_dir, "model.json")
        else:
            json_path = "model.json"
            
        # Modeli (Beyni) Yükle
        with open(json_path, "r") as f:
            weights = json.load(f)
            
        # Json'daki listeleri Numpy matrislerine çevir
        self.w1 = np.array(weights["w1"])
        self.b1 = np.array(weights["b1"])
        self.w2 = np.array(weights["w2"])
        self.b2 = np.array(weights["b2"])
        self.w_out = np.array(weights["w_out"])
        self.b_out = np.array(weights["b_out"])

    def act(self, obs: dict) -> int:
        grid = obs["grid"]
        stats = obs["stats"]

        # Girdi verisini düzleştir
        grid_flat = np.array(grid, dtype=np.float32).flatten()
        stats_array = np.array(stats, dtype=np.float32)
        x = np.concatenate((grid_flat, stats_array)) # 904 elemanlı veri

        # İLERİ BESLEMELİ SİNİR AĞI
        x = np.dot(self.w1, x) + self.b1
        x = np.tanh(x)
        x = np.dot(self.w2, x) + self.b2
        x = np.tanh(x)
        logits = np.dot(self.w_out, x) + self.b_out
        
        return int(np.argmax(logits))

    def handle_reward(self, reward: float, done: bool):
        pass
```

---

## 🏋️ 3. EĞİTİM (TRAINING) NASIL YAPILIR?

Eğitim sayfası, sinir ağı modelini **sıfırdan eğitir** ve size kullanıma hazır bir `model.json` dosyası verir.

### ⚠️ ÖNEMLİ: Eğitim = Gerçek Sinir Ağı Eğitimi
Sistem **Evolution Strategy (ES)** algoritması kullanır. Bu:
- 904→64→64→4 mimarisinde bir sinir ağı oluşturur
- Rakip ajana karşı **binlerce oyun simüle eder**
- Her nesilde en başarılı ağırlıkları seçip evrimleştirir
- Sonuçta **gerçekten eğitilmiş** bir `model.json` üretir

### Eğitim Adımları:
1. **Eğitim Sayfasına Git:** Üst menüden `🏋️ EĞİTİM MERKEZİ` sekmesine tıkla.
2. **Rakip Ajan Yükle:** Sinir ağının karşısında antrenman yapacağı rakip `.py` dosyasını seç.
3. **Parametreleri Ayarla:**
   - **Nesil Sayısı:** Kaç nesil eğitim yapılacak (daha fazla = daha iyi ama daha yavaş). 60-100 arası önerilir.
   - **Popülasyon Boyutu:** Her nesilde kaç aday denenecek. 20-40 arası ideal.
   - **Meyve Ödülleri:** Arenada kullanılan değerlerin **aynısını** girin! Eğer arenada zehirli meyve boy=-2 ise, eğitimde de -2 olmalı.
   - **Zaman Kısıtlaması:** Eğer arenada 0.1 sn sınır varsa, bunu açın.
4. **Eğitimi Başlat:** Butona bas ve konsolda ilerlemeyi takip et.
5. **Model İndir:** Eğitim bitince `model.json` dosyasını indir.
6. **Arenaya Yükle:** İndirdiğin `model.json` + `.py` dosyanı arenaya yükle.

### Eğitim İpuçları:
- **Güçlü rakip seç:** Ne kadar iyi bir rakibe karşı eğitirsen, modelin o kadar iyi olur.
- **Meyve ayarlarını eşleştir:** Arena'daki meyve ödülleri neyse eğitimde de aynısını kullan.
- **Nesil artır:** 60 nesilde iyi sonuç almazsan, 150-200 nesil dene.

---

## 🏆 4. ARENA VE PUANLAMA MANTIĞI
Arenada yılanları yarıştırırken puanlar şöyledir (Ayarları değiştirmezsen):

- **3 PUAN (K.O.):** Rakibi direkt öldürürsen (Senin gövdene veya duvara çarpması).
- **2 PUAN (PUANLA):** Süre (Adım) bittiğinde hayatta kalıp rakibinden daha uzunsan.
- **1 PUAN (BERABERLİK):** İkiniz de yaşarsanız ve boylarınız aynıysa.

### Arenaya Nasıl Yüklerim?
1. **Tekli Yükleme:** Sol panelde "Tekli Yükleme" bölümünden:
   - `.py` dosyanı (agent kodu) seç
   - `model.json` dosyanı (eğitilmiş ağırlıklar) seç
   - "Tekli Yükle" butonuna bas
2. **Toplu Yükleme (ZIP):** Birden fazla ajan yüklemek için ZIP kullanabilirsin.

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

---

## 📁 DOSYA YAPISI
```
arena_v2/
├── app.py              # Ana Flask sunucusu
├── game_engine.py      # Oyun motoru (grid, yılanlar, meyveler, çarpışma)
├── base_agent.py       # Tüm ajanların miras aldığı temel sınıf
├── trainer.py          # Gerçek sinir ağı eğitim motoru (ES algoritması)
├── example_agents/     # Örnek ajanlar
├── templates/          # HTML sayfaları (arena + eğitim)
├── static/             # CSS + JS
├── uploads/            # Yüklenen ajanlar buraya kaydedilir
└── README.md           # Bu dosya
```

**ÖZETLE:** Eğit (model.json al) → Kodla (Python + model.json) → Arenada Yarıştır (Şampiyon Ol)!
