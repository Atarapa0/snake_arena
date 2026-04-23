"""
BASE AGENT - Standart arayüz.
Hocanın belirlediği kurallar:
- Girdi: 30x30 numpy array
    0 = boş hücre
    1 = kendi kafan
    2 = kendi gövden
    3 = rakip yılanın kafası
    4 = rakip yılanın gövdesi
    5 = yem
- Çıktı: 0/1/2/3
    0 = YUKARI
    1 = SAĞ
    2 = AŞAĞI
    3 = SOL
- 180° dönüş yasak (platform engeller)
- Karar süresi: 0.5 saniye
- Model boyutu: max 20 MB
- Kural tabanlı yaklaşım yasak (öğrenme tabanlı olmalı)

Her ajan bu sınıfı miras alır:

    from base_agent import BaseAgent
    import numpy as np

    class MyAgent(BaseAgent):
        def __init__(self, name="MyAgent", data_dir=None):
            super().__init__(name=name, data_dir=data_dir)
            # data_dir verilirse oradan model dosyanı yükleyebilirsin

        def act(self, observation: np.ndarray) -> int:
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
    def act(self, observation: np.ndarray) -> int:
        """30x30 numpy array al, 0/1/2/3 döndür."""
        ...

    def reset(self):
        """Yeni oyun başlarken çağrılır. İsteğe bağlı override."""
        pass
