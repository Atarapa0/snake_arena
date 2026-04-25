# 🐍 Snake AI Arena v2.5 - KULLANIM REHBERİ

Bu proje, öğrencilerin **kendi sinir ağı modellerini tasarlayıp**, **kendi rakiplerini yazıp** eğittikleri ve sonunda arenada yarıştırdıkları bir yapay zeka platformudur.

---

## 🚀 1. SİSTEMİ NASIL ÇALIŞTIRIRIM?

```bash
pip install flask numpy
python app.py
```

Tarayıcıdan `http://localhost:5001` adresine git. İki sekme göreceksin:
- **🏆 LİG ARENASI** → Eğitilmiş ajanları birbirine karşı yarıştırdığın yer
- **🏋️ EĞİTİM MERKEZİ** → Sinir ağını eğittiğin yer

---

## 🧠 2. SİSTEM NASIL ÇALIŞIYOR? (BÜYÜK RESİM)

Sistem 3 aşamadan oluşur. Hepsini **öğrenci kendi yapar**:

### AŞAMA 1: Beyin Dosyası Yaz (Sinir Ağı Modeli)
Öğrenci bir `.py` dosyası yazar. Bu dosya 3 şey içerir:
- **Mimari:** Sinir ağının kaç katman, kaç nöron olacağı
- **Ödül/Ceza Fonksiyonu:** Oyun sonunda ne ödüllendirilecek, ne cezalandırılacak
- **İleri Besleme (Forward):** Haritayı alıp yön kararı veren matematik

### AŞAMA 2: Rakip Ajanlar Yaz
Öğrenci antrenman partneri olarak `.py` dosyaları yazar. Bunlar basit kural tabanlı ajanlardır (if/else ile). Sinir ağı bunlara karşı eğitilecek.

### AŞAMA 3: Eğit ve Yarıştır
Eğitim Merkezine beyin dosyası + rakipleri yükler. Sistem **Evolution Strategy** ile sinir ağını eğitir ve `model.json` verir. Bu dosya + arena formatında bir `.py` ile arenaya yüklenir.

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  BEYİN.PY    │     │  RAKİP.PY    │     │  EĞİTİM      │
│  (Mimari +   │────▶│  (Antrenman  │────▶│  MERKEZİ      │
│   Ödül/Ceza) │     │   Partneri)  │     │  (ES ile      │
└──────────────┘     └──────────────┘     │   Eğitim)     │
                                          └──────┬───────┘
                                                 │
                                          ┌──────▼───────┐
                                          │  model.json   │
                                          │  (Eğitilmiş   │
                                          │   Ağırlıklar) │
                                          └──────┬───────┘
                                                 │
                                          ┌──────▼───────┐
                                          │  ARENA        │
                                          │  OgrenciYilan.py+ │
                                          │  model.json   │
                                          └──────────────┘
```

---

## 🎯 3. HARİTA VE NESNE KODLARI (30x30 Matris)

Modelin göreceği matristeki sayılar:

| Kod | Nesne | Açıklama |
|-----|-------|----------|
| 0 | Boş Alan | Güvenli geçilebilir |
| 1 | **Kendi Kafası** | Yılanın başı |
| 2 | **Kendi Gövdesi** | Çarparsan ölürsün |
| 3 | **Rakip Kafası** | Kafası |
| 4 | **Rakip Gövdesi** | Çarparsan ölürsün |
| 5 | **Duvar/Engel** | Çarparsan ölürsün |
| 6 | 🔴 **Kırmızı Elma** | +1 Boy, +20 Enerji |
| 7 | 🟡 **Altın Elma** | +3 Boy, +50 Enerji |
| 8 | ☠️ **Zehirli Meyve** | -2 Boy, +100 Enerji |

---

## ⚡ 4. KRİTİK OYUN MEKANİKLERİ

### Enerji (Açlık)
- Her yılan **100 enerji** ile başlar
- Her adımda **-1** azalır
- Enerji **0** olursa yılan ölür (Açlıktan ölüm)
- Maksimum enerji **200**

### Boy Yönetimi
- Yılanın başlangıç boyu **3** (1 kafa + 2 gövde)
- Minimum boy **2** — Zehirli meyve yerse ve boyu 2 ise daha kısalmaz
- Meyve yedikçe uzar, zehir yedikçe kısalır
- **Boyu büyük olan yılan, kafa kafaya çarpışmada rakibini eler**

### Hız ve Karar
- Her ajana karar vermesi için **100ms (0.1 sn)** süre tanınır
- Süreyi aşarsan **hükmen mağlup** olursun

### Torus Dünyası
- 30x30 harita **sonsuz**: sağdan çıkınca soldan, alttan çıkınca üstten girersin

---

## 📝 5. BEYİN DOSYASI NASIL YAZILIR?

Öğrenci `my_brain.py` adında bir dosya oluşturur. İçinde **3 şey** olmalı:

### 5.1 Mimari Tanımlaması (`architecture`)
```python
import numpy as np

# Katmanlar: [girdi, gizli1, gizli2, ..., çıktı]
# Girdi: 30x30 harita (900) + 4 stat = 904 nöron
# Çıktı: 4 yön (Yukarı, Sağ, Aşağı, Sol)
architecture = [904, 64, 64, 4]

# Aktivasyon: "tanh" veya "relu"
activation = "tanh"
```

**Farklı mimari örnekleri:**
```python
architecture = [904, 32, 4]              # Basit (1 gizli katman, hızlı)
architecture = [904, 128, 64, 4]         # Orta (2 gizli katman)
architecture = [904, 256, 128, 64, 4]    # Derin (3 gizli katman, yavaş ama güçlü)
```

### 5.2 Ödül/Ceza Fonksiyonu (`fitness`)
```python
def fitness(stats):
    """Her oyun sonunda çağrılır. Yüksek skor = iyi ağırlıklar."""
    score = 0.0

    # Hayatta kalma ödülü
    score += stats["survived_steps"] * 0.1

    # Boy ödülü (uzun yılan güçlü)
    score += stats["my_length"] * 15.0

    # Enerji ödülü
    score += stats["my_energy"] * 0.05

    # Kazanma büyük ödül
    if stats["won"]:
        score += 200.0
        if not stats["opp_alive"]:
            score += 100.0  # K.O. ekstra ödül!
    elif stats["lost"]:
        score -= 100.0

    # Ölüm cezası
    if not stats["my_alive"]:
        score -= 150.0
        if stats["step_count"] < 50:
            score -= 200.0  # Erken ölüm daha kötü

    return score
```

**`stats` parametresinde gelen tüm bilgiler:**

| Alan | Tip | Açıklama |
|------|-----|----------|
| `survived_steps` | int | Hayatta kalınan adım sayısı |
| `my_length` | int | Oyun sonu yılan boyu |
| `my_energy` | int | Oyun sonu enerji |
| `opp_length` | int | Rakibin oyun sonu boyu |
| `opp_alive` | bool | Rakip hayatta mı? |
| `my_alive` | bool | Ben hayatta mıyım? |
| `won` | bool | Kazandım mı? |
| `lost` | bool | Kaybettim mi? |
| `draw` | bool | Berabere mi? |
| `max_steps` | int | Oyundaki max adım |
| `step_count` | int | Toplam oynanan adım |

> **ÖNEMLİ:** Bu fonksiyon öğrencinin **en çok yaratıcı olacağı** kısım! Her öğrenci farklı ağırlıklandırma yaparak farklı stratejilere sahip modeller üretebilir.

### 5.3 İleri Besleme Fonksiyonu (`forward`)
```python
def forward(weights, grid, stats):
    """Haritayı alıp 0/1/2/3 yön döndürür."""
    grid_flat = np.array(grid, dtype=np.float32).flatten()
    stats_array = np.array(stats, dtype=np.float32)
    x = np.concatenate((grid_flat, stats_array))

    num_layers = len(architecture) - 1
    for i in range(num_layers):
        w = weights[f"w{i}"]
        b = weights[f"b{i}"]
        x = np.dot(w, x) + b
        if i < num_layers - 1:
            if activation == "tanh":
                x = np.tanh(x)
            elif activation == "relu":
                x = np.maximum(0, x)

    return int(np.argmax(x))
```


---

## 🐍 6. RAKİP AJAN NASIL YAZILIR?

Rakipler kural tabanlı (if/else) ajanlardır. Sinir ağı bunlara karşı eğitilir. Format:

```python
from base_agent import BaseAgent

class OgrenciYilan(BaseAgent):
    def __init__(self):
        super().__init__()
        self.name = "RakipAjanim" # Ajanınıza bir isim verin

    def act(self, obs):
        """
        obs["grid"] : 30x30 Harita (Matris)
        obs["stats"]: Enerji, Boy, Rakip Boy, vs.
        
        Buraya kendi kural tabanlı stratejinizi (if/else) yazacaksınız.
        Dönüş değeri: 0 (YUKARI), 1 (SAĞ), 2 (AŞAĞI) veya 3 (SOL)
        """
        
        # Örnek: Rastgele hareket (Öğrenciler burayı kendi zekalarıyla dolduracak!)
        return 1

    def handle_reward(self, reward, done):
        pass
```

> **NOT:** Kendi rakip ajanınızı ne kadar akıllı yaparsanız, ona karşı eğiteceğiniz sinir ağınız da o kadar zeki olmak zorunda kalacaktır.

---

## 🏋️ 7. EĞİTİM NASIL YAPILIR?

### Adım Adım:
1. **Eğitim Merkezi** sekmesine git (`http://localhost:5001/egitim`)
2. **🧠 Beyin Dosyası:** Yazdığın `my_brain.py` dosyasını yükle (isteğe bağlı — yüklemezsen varsayılan mimari kullanılır)
3. **🐍 Rakipler:** Yazdığın rakip `.py` dosyalarını yükle (birden fazla seçebilirsin — Ctrl/Cmd tuşuna basılı tut)
4. **📥 Devam Ettir:** Daha önce eğitilmiş bir `model.json` varsa yükle (isteğe bağlı — sıfırdan başlamak istiyorsan boş bırak)
5. **Parametreleri ayarla** ve **Eğitimi Başlat** butonuna bas
6. Konsolda ilerlemeyi izle
7. **Eğitim bitince `model.json` İndir**

### 7.1 Gelişmiş Teknik: Eğitilmiş Yapay Zekayı Rakip Yapma
Yapay zekan belli bir seviyeye geldikten sonra, onu daha da geliştirmek için **eski modellerine karşı** eğitebilirsin.

**Nasıl Yapılır?**
1. **Rakipler** kısmında dosya seçerken, hem ajanın `.py` dosyasını (Örn: `arena_otcul.py`) hem de ona ait `.json` dosyasını (Örn: `arena_otcul.json`) **aynı anda** seçerek yükle.
2. Sistem bu iki dosyayı eşleştirerek, eski yapay zekanı eğitimde bir rakip olarak kullanacaktır.
3. Bu sayede yapay zekan, sadece kurallı (if/else) rakiplere karşı değil, kendisi gibi zeki rakiplere karşı da tecrübe kazanır.

### Eğitim Parametreleri:
| Parametre | Varsayılan | Açıklama |
|-----------|-----------|----------|
| Nesil Sayısı | 60 | Kaç nesil eğitilecek (fazla = daha iyi ama yavaş) |
| Popülasyon | 30 | Her nesilde kaç aday ağırlık denenecek |
| Oyun/Değerlendirme | 3 | Her adayın kaç oyun oynayacağı |
| Sigma | 0.05 | Mutasyon gücü (küçük = ince ayar, büyük = keşif) |
| Öğrenme Oranı | 0.03 | Güncelleme adımı |

### Eğitim Stratejisi (İpuçları):
1. **İlk eğitim:** 1 basit rakiple 30-50 nesil eğit. `model.json`'u indir.
2. **2. tur:** İndirdiğin `model.json`'u "Devam Ettir" kısmına yükle + daha zor bir rakip ekle + 50 nesil daha eğit.
3. **3. tur:** Yine devam ettir + farklı bir rakip + 50 nesil daha.
4. **Sonuç:** 3 farklı rakibe karşı eğitilmiş güçlü bir model!

---

## 🏆 8. ARENAYA NASIL YÜKLERİM?

Eğitim sonucunda aldığın `model.json` dosyasını arenada kullanmak için bir **Arena Ajanı (.py)** yazman gerekiyor. Bu dosya `model.json`'daki ağırlıkları yükleyip oyunda karar verir:

```python
import os
import json
import numpy as np
from base_agent import BaseAgent

class OgrenciYilan(BaseAgent):
    def __init__(self, name="BenimAjan", data_dir=None):
        super().__init__(name=name, data_dir=data_dir)

        if self.data_dir:
            json_path = os.path.join(self.data_dir, "model.json")
        else:
            json_path = "model.json"

        with open(json_path, "r") as f:
            weights = json.load(f)

        # Ağırlıkları yükle (beyin dosyandaki mimariyle AYNI olmalı!)
        self.weights = {k: np.array(v) for k, v in weights.items()}

    def act(self, obs: dict) -> int:
        grid = obs["grid"]
        stats = obs["stats"]

        grid_flat = np.array(grid, dtype=np.float32).flatten()
        stats_array = np.array(stats, dtype=np.float32)
        x = np.concatenate((grid_flat, stats_array))

        # Beyin dosyandaki forward fonksiyonunun AYNISI olmalı!
        num_layers = (len(self.weights)) // 2
        for i in range(num_layers):
            x = np.dot(self.weights[f"w{i}"], x) + self.weights[f"b{i}"]
            if i < num_layers - 1:
                x = np.tanh(x)  # Beyin dosyandaki aktivasyonla aynı olmalı!

        return int(np.argmax(x))

    def handle_reward(self, reward: float, done: bool):
        pass
```

### Yükleme:
1. Sol panelde **Tekli Yükleme** kısmından `.py` dosyanı ve `model.json`'u yükle
2. **Toplu Yükleme (ZIP):** Birden fazla ajan yüklemek için ZIP kullanabilirsin

---

## 🏅 9. PUANLAMA (LİG SİSTEMİ)

| Durum | Puan | Açıklama |
|-------|------|----------|
| **K.O. Galibiyeti** | **3** | Rakip duvara çarptı, aç kaldı veya gövdene çarptı |
| **Puanla Galibiyet** | **2** | Süre bitti, sen daha uzunsun |
| **Beraberlik** | **1** | Süre bitti, boy eşit |
| **Mağlubiyet** | **0** | Kaybettin |

Lider tablosunda: O (Oynanan), G (Galibiyet), B (Beraberlik), M (Mağlubiyet), Puan, Averaj gösterilir.

---

## 💡 10. STRATEJİ İPUÇLARI

1. **Fitness fonksiyonun HER ŞEYİ belirler:** "Hayatta kal" dersen hayatta kalır, "Rakibi öldür" dersen saldırgan olur, "Uzun ol" dersen meyve toplar.
2. **Zehir Stratejisi:** Enerjin düşükken zehir (8) ye — boyun kısalır ama enerjin +100 dolar, ölmezsin.
3. **Torus Kullan:** Harita kenarları bağlıdır. Sağdan çıkıp soldan girebilirsin. Kaçış yolu olarak kullan.
4. **Çok rakiple eğit:** Sadece 1 rakibe karşı eğitirsen o rakibe özel strateji öğrenir. 3-5 farklı rakiple eğitirsen daha genel bir model çıkar.
5. **Model.json'u devam ettir:** Aynı modeli farklı rakiplere karşı sırayla eğiterek giderek güçlendir.
6. **Ödül İstismarına (Reward Hacking) Dikkat Et:** Yapay zeka senin koyduğun ödül/ceza mantığındaki açıkları arar! Örneğin, sadece rakibi öldürmeye +5000 puan verirsen, yapay zeka hiçbir şey yapmadan rakibinin yanlışlıkla ölmesini beklemeyi "en karlı" strateji sanacaktır. Buna "Yapay Zeka Tembelliği" denir. Çözüm: **Ölüm cezası ekle**. `if not stats["my_alive"]: score -= 5000.0` ekleyerek intihar etmesini veya hiçbir şey yapmadan ölmesini kesin bir dille yasakla!

---

## 📁 11. DOSYA YAPISI

```
arena_v2/
├── app.py                      # Flask sunucusu (Arena + Eğitim API)
├── game_engine.py              # Oyun motoru (harita, yılanlar, çarpışma)
├── trainer.py                  # Eğitim motoru (Evolution Strategy)
├── base_agent.py               # Tüm ajanların miras aldığı temel sınıf
├── templates/
│   ├── index.html              # Arena arayüzü
│   └── egitim.html             # Eğitim merkezi arayüzü
├── static/
│   ├── style.css               # CSS stilleri
│   └── arena.js                # Arena JavaScript mantığı

├── uploads/                    # Arenaya yüklenen ajanlar
├── leaderboard.json            # Lig tablosu verileri
└── README.md                   # Bu dosya
```

---

## 🔄 12. HIZLI BAŞLANGIÇ (ÖZET)

```
1. Beyin dosyası yaz    →  my_brain.py (mimari + ödül/ceza + forward)
2. Rakip yaz            →  rakip.py (kural tabanlı basit ajan)
3. Eğitim Merkezine git →  Beyin + Rakipleri yükle → Eğitimi Başlat
4. model.json indir     →  Eğitilmiş ağırlıklar
5. Arena ajanı yaz      →  OgrenciYilan.py (model.json'u okuyup forward yapan)
6. Arenaya yükle        →  OgrenciYilan.py + model.json
7. Yarıştır!            →  Diğer öğrencilere karşı maç yap
```

**ÖZETLE:** Tasarla → Eğit → Yarıştır → Şampiyon Ol! 🏆

---

## ⚠️ 13. ALTIN KURAL: EĞİTİM VE ARENA UYUMU (ÖNEMLİ)

Sistem **iki farklı ortamdan** oluştuğu için dosyalarınız da iki farklı formatta olmak zorundadır. Ancak **mantıkları tamamen aynı** olmalıdır!

**Eğitim Merkezine (my_brain.py):**
Sadece saf matematik yüklersiniz. Class veya nesne (object) yoktur. Eğitim motoru binlerce oyunu saniyeler içinde simüle edebilmek için bu hafif yapıya ihtiyaç duyar.
- `forward(weights, grid, stats)` fonksiyonunu yazarsınız.

**Arenaya (OgrenciYilan.py):**
Arena bir turnuva motorudur ve sizden resmi bir "Oyuncu Sınıfı" (`BaseAgent`'tan miras alan) bekler.
- Eğittiğiniz modeli arenaya yüklerken yapmanız gereken **TEK ŞEY**, beyin dosyanızdaki `forward` mantığını kopyalayıp arena ajanınızın `act(self, obs)` fonksiyonunun içine yapıştırmaktır.

### Dönüşüm Şeması:
`my_brain.py` içindeki:
`x = np.dot(weights["w0"], x) + weights["b0"]`

`OgrenciYilan.py` içinde şuna dönüşür:
`x = np.dot(self.weights["w0"], x) + self.weights["b0"]`

Mimariniz neyse, ağırlık isimleriniz neyse, aktivasyon fonksiyonunuz (`tanh` veya `relu`) neyse; **ikisinde de birebir aynı olmak zorundadır!** Aksi takdirde Arena, `model.json`'daki ağırlıkları okuyamaz veya yanlış bir matematiksel işlem yaparak anlamsız hareketler sergiler.
