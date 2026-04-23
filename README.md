# 🐍 Snake Arena v2.5 (Lig ve Hayatta Kalma Modu)

Derin Öğrenme ve Pekiştirmeli Öğrenme (Reinforcement Learning) tabanlı yılan ajanları için geliştirilmiş, **kural tabanlı algoritmaların (If-Else) işe yaramadığı**, tamamen hayatta kalma ve strateji üzerine kurulu kapalı arena sistemidir.

Bu projede öğrencilerin "Şurada duvar varsa sağa dön" gibi sabit kurallar yazması değil; **Pekiştirmeli Öğrenme (Self-Play / Ödül-Ceza)** mantığıyla ajanların kendi kendilerine oynayarak tecrübe kazanması ve optimum hayatta kalma stratejisini derin sinir ağlarıyla (Deep Neural Networks) keşfetmesi hedeflenmektedir.

## Ne Değişti? (Devasa v2.5 Güncellemesi)
- **Açlık Sistemi (Enerji):** Her yılan *100 Enerji* ile başlar (Maks: 200). Her adımda enerji 1 azalır. Enerjisi biten yılan direk ölür! Kırmızı elma (+20), Altın elma (+50), Zehirli meyve (+100) enerji verir.
- **Zehir Makinesi:** Haritada artık zehirli meyveler var (Tür 8). Zehir yerseniz boyunuz 2 birim kisalir ama enerjiniz anında fulle yakın artar. Bazen açlıktan ölmemek için bilerek zehir yemeniz gerekecek!
- **Sabit Duvarlar (Engeller):** Haritanın 3 rastgele yerine (orta alan hariç) L, U ve I şeklinde beton bloklar konuldu. Çarpan parçalanır. Torus (Wrap-Around) kenarlar hala aktif, ama içerisi artık boş değil.
- **Turnuva Ağacı Yok, Lig Var!** Eleme usülü iptal edildi. Rastgele lig fikstürü veya sizin seçeceğiniz manuel maçlarla herkes herkesle oynar.
- **Puanlama (Lig Usulü):** 
  - Rakibi ezerek, duvara çarptırarak veya yavaşlatıp aç bırakarak direkt **ÖLDÜRÜRSEN: 3 Puan**
  - İkiniz de süre sonuna kadar hayatta kalırsanız, **BOYU UZUN OLAN: 2 Puan**
  - İkiniz de süre sonuna kadar yaşar ve boylarınız eşitse, beraberlik: **1'er Puan**

## Öğrenciler İçin Mimari / Geliştirme Rehberi

Öğrenciler modellerini eğitirken **Pekiştirmeli Öğrenme (Reinforcement Learning)** tekniklerini kullanacaklardır. (Örn: DQN, PPO, A2C).
İki yılan modelini (Agent A ve Agent B) sürekli birbiriyle savaştırarak (Self-Play) oyunu öğrenmelerini sağlamanız bekleniyor. Sistemin size sağladığı "Gözlem (Observation)" artık sadece bir matris değil; enerjinizi ve boyunuzu da içeren detaylı bir sözlüktür (Dictionary).

### Gözlem Uzayı (Observation Space)
Oyun motoru size her adımda şu sözlüğü verir:
```python
{
    "grid": np.ndarray,  # 30x30'luk harita matrisi
    "stats": [
        benim_enerjim,   # (int) 0-200 arası
        benim_boyum,     # (int) > 0
        rakibin_boyu,    # (int) (rakip ölüyse 0)
        rakibin_enerjisi # (int) (rakip ölüyse 0)
    ]
}
```

**Grid (Matris) Üzerindeki ID'ler:**
- `0`: Boş
- `1`: Kendi Kafam  | `2`: Kendi Gövdem
- `3`: Rakip Kafa   | `4`: Rakip Gövde
- `5`: Duvar (Çarparsan ölürsün)
- `6`: Kırmızı Elma (Boy +1, Enerji +20)
- `7`: Altın Elma   (Boy +3, Enerji +50)
- `8`: Zehirli Meyve (Boy -2, Enerji +100 - Kurtarıcı zehir!)

### Ajan Sınıfı (Örnek)
Yeni formata göre örnek bir ajan sınıfı (Bu dosyalar Github'da `/example_agents` altında yer alır):

```python
from base_agent import BaseAgent
import numpy as np

class RL_Agent(BaseAgent):
    def __init__(self, name="RL_Agent", data_dir=None):
        super().__init__(name, data_dir)
        # data_dir içinden neural network modelini (PyTorch vs.) yükle
        # self.model = load_model(data_dir + "/model.pth")

    def act(self, obs: dict) -> int:
        grid = obs["grid"]
        stats = obs["stats"]
        
        my_energy = stats[0]
        my_length = stats[1]
        
        # RL modelinizi kullanarak grid ve stats bilgilerini ağdan geçirin
        # action = self.model.predict(grid, stats)
        
        # Aksiyonlar: 0=YUKARI, 1=SAĞ, 2=AŞAĞI, 3=SOL
        return action
```

### Ödül ve Ceza Fikirleri (RL Reward Shaping)
Kendi simülasyonlarınızı (gym environment) yazarken eğitmek için kullanabileceğiniz ödüller:
- Kırmızı/Altın elma yediğinde: `+Ödül`
- Yaşadığı her bir step için: `+Ufak Ödül`
- Duvara / Rakibe çarpıp öldüğünde: `-Büyük Ceza`
- Rakibi öldürecek hamleye (rakibin alanını daraltma): `+Büyük Ödül`
- Açlıktan öldüğünde: `-Ceza` (Zehir yiyip hayatta kaldığında ödüllendirin)

## Kurulum
```bash
pip install flask numpy
python arena_v2/app.py
```
Tarayıcıdan: `http://localhost:5001`
