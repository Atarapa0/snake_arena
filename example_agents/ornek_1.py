import random
from base_agent import BaseAgent

class Ornek1(BaseAgent):
    """
    Çok basit (biraz da salak) bir örnek ajan.
    Kurallara (yeni Dict formatı) harfiyen uyar ancak rastgele veya sabit hareket eder.
    Sürekli rastgele hareket eder, bir stratejisi yoktur. Öğrencilere örnek olması amaçlanmıştır.
    """
    def __init__(self, name="ornek_1", data_dir=None):
        super().__init__(name=name, data_dir=data_dir)

    def act(self, observation: dict) -> int:
        grid = observation["grid"]
        stats = observation["stats"]
        
        my_energy = stats[0]
        my_length = stats[1]
        opp_length = stats[2]
        opp_energy = stats[3]
        
        # Tamamen akılsız bir şekilde rastgele 0, 1, 2 veya 3 döner
        # 0=↑ 1=→ 2=↓ 3=←
        return random.randint(0, 3)
