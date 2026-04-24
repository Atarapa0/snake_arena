"""
BASE AGENT - Standart arayüz.
Hocanın belirlediği yeni lig kuralları:
- Girdi (Observation): Bir sözlük (Dictionary) döner.
    obs = {
        "grid": 30x30 numpy array,
        "stats": [benim_enerjim, benim_boyum, rakibin_boyu, rakibin_enerjisi]
    }
- Grid (Matris) ID'leri:
    0 = boş hücre
    1 = kendi kafan
    2 = kendi gövden
    3 = rakip yılanın kafası
    4 = rakip yılanın gövdesi
    5 = duvar (sabit engel, çarpan ölür)
    6 = kırmızı elma (boy +1, enerji +20)
    7 = altın elma (boy +3, enerji +50)
    8 = zehirli meyve (boy -2, enerji +100)
- Çıktı: 0/1/2/3
    0 = YUKARI
    1 = SAĞ
    2 = AŞAĞI
    3 = SOL
- 180° dönüş yasak (platform engeller)
- Karar süresi: 0.1 saniye (TIME_LIMIT)
  -> ÖNEMLİ KURAL: Eğer karar vermeniz 0.1 saniyeyi geçerse veya kodunuz hata verirse, yılanınız en son gittiği yönde ilerlemeye otomatik olarak devam eder!
- Model boyutu: max 20 MB
- Kural tabanlı yaklaşım yasak (öğrenme tabanlı olmalı)

Her ajan bu sınıfı miras alır:

    from base_agent import BaseAgent
    import numpy as np

    class MyAgent(BaseAgent):
        def __init__(self, name="MyAgent", data_dir=None):
            super().__init__(name=name, data_dir=data_dir)
            # data_dir verilirse oradan model dosyanı yükleyebilirsin

        def act(self, observation: dict) -> int:
            grid = observation["grid"]
            stats = observation["stats"]
            return 1  # 0=↑ 1=→ 2=↓ 3=←
"""
from abc import ABC, abstractmethod
import numpy as np


class BaseAgent(ABC):
    UP, RIGHT, DOWN, LEFT = 0, 1, 2, 3

    def __init__(self, name: str = "Agent", data_dir: str = None):
        self.name = name
        self.data_dir = data_dir  # 2. yüklenen dosyanın bulunduğu klasör

    @abstractmethod
    def act(self, observation: dict) -> int:
        """Sözlük (dict) formatında obs al, 0/1/2/3 döndür."""
        ...

    def handle_reward(self, reward: float, done: bool):
        """RL eğitimi için ödül sinyali gönderir. İsteğe bağlı override."""
        pass

    def reset(self):
        """Yeni oyun başlarken çağrılır. İsteğe bağlı override."""
        pass
