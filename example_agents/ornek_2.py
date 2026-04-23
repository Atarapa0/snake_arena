import random
import numpy as np
import os
import json
from base_agent import BaseAgent

class Ornek2(BaseAgent):
    """
    Parametre okuyan basit kural tabanlı örnek ajan.
    data_dir içindeki .json dosyasını okuyarak stratejisini (tercih ettiği meyve) belirler.
    Bu kısım, öğrencilerin PyTorch (.pth) modellerini nasıl yükleyeceğine dair bir rehberdir.
    """
    def __init__(self, name="ornek_2", data_dir=None):
        super().__init__(name=name, data_dir=data_dir)
        
        # Varsayılan değerler
        self.hedef_meyve = 6 # Normalde kırmızı elma arasın
        
        # Eğer bir klasör verildiyse, oradaki parametreleri oku (Hocanın istediği özellik)
        if self.data_dir:
            param_path = os.path.join(self.data_dir, "ornek_2_params.json")
            if os.path.exists(param_path):
                with open(param_path, "r", encoding="utf-8") as f:
                    params = json.load(f)
                    # Parametre dosyasından okunan degeri ajana öğretiyoruz
                    self.hedef_meyve = params.get("tercih_edilen_meyve", 6)

    def act(self, observation: dict) -> int:
        grid = observation["grid"]
        stats = observation["stats"]
        
        # Kendi kafamızın yerini bulalım (ID: 1)
        kendi_kafam_koordinatlari = np.argwhere(grid == 1)
        if len(kendi_kafam_koordinatlari) == 0:
            return 1 # Kafayı bulamazsa sağa git
        
        # Parametreden gelen "hedef_meyve" bilgisini kullanıyoruz (Örn JSON'dan 7 yani Altın Elma geldi)
        meyveler = np.argwhere(grid == self.hedef_meyve)
        
        # Eğer haritada hedef meyve yoksa ya da bulamadıysa, rastgele yöne git
        if len(meyveler) == 0:
            return random.randint(0, 3)
            
        # İlk bulduğu meyveye doğru kaba bir yön tahmini yapmayı dener
        kafa_r, kafa_c = kendi_kafam_koordinatlari[0]
        hedef_r, hedef_c = meyveler[0]
        
        dr = hedef_r - kafa_r
        dc = hedef_c - kafa_c
        
        # Satır veya sütundaki farka göre bir yöne yönelir. (Engelleri ve duvarları (5) umursamaz)
        if abs(dr) > abs(dc):
            if dr > 0:
                return 2  # AŞAĞI
            else:
                return 0  # YUKARI
        else:
            if dc > 0:
                return 1  # SAĞ
            else:
                return 3  # SOL
