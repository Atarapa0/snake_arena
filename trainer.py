"""
GERÇEK SİNİR AĞI EĞİTİCİSİ - Evolution Strategy (ES)
=====================================================
Öğrencinin yazdığı beyin dosyasını (mimari + fitness + forward) kullanarak
sinir ağını Evolution Strategy ile eğitir.

Öğrenci kendi beyin dosyasını (.py) yazar:
  - architecture: [904, 128, 64, 4] gibi katman boyutları
  - activation: "tanh" veya "relu"
  - fitness(stats): oyun sonunda skor döndüren fonksiyon
  - forward(weights, grid, stats): ağırlıklarla yön hesaplayan fonksiyon

Kullanım:
    from trainer import NNTrainer
    trainer = NNTrainer(brain_module=brain, ...)
    best_weights, logs = trainer.train(generations=100, population_size=30)
"""

import numpy as np
import json
import time
import copy
from collections import deque

import game_engine


# ==================== VARSAYILAN BEYİN (brain modülü yüklenmezse) ====================

class DefaultBrain:
    """Öğrenci bir beyin dosyası yüklemezse bu kullanılır."""
    architecture = [904, 64, 64, 4]
    activation = "tanh"
    
    @staticmethod
    def fitness(stats):
        score = 0.0
        score += stats["survived_steps"] * 0.1
        score += stats["my_length"] * 15.0
        score += stats["my_energy"] * 0.05
        
        if stats["won"]:
            score += 200.0
            if not stats["opp_alive"]:
                score += 100.0
        elif stats["lost"]:
            score -= 100.0
        else:
            if stats["my_alive"] and stats["opp_alive"]:
                score += (stats["my_length"] - stats["opp_length"]) * 10.0
        
        if not stats["my_alive"]:
            score -= 150.0
            if stats["step_count"] < 50:
                score -= 200.0
            elif stats["step_count"] < 200:
                score -= 100.0
        
        return score
    
    @staticmethod
    def forward(weights, grid, stats):
        grid_flat = np.array(grid, dtype=np.float32).flatten()
        stats_array = np.array(stats, dtype=np.float32)
        x = np.concatenate((grid_flat, stats_array))
        
        arch = DefaultBrain.architecture
        num_layers = len(arch) - 1
        for i in range(num_layers):
            w = weights[f"w{i}"]
            b = weights[f"b{i}"]
            x = np.dot(w, x) + b
            if i < num_layers - 1:
                x = np.tanh(x)
        
        return int(np.argmax(x))


# ==================== HIZLI SİMÜLASYON ====================

def fast_simulate(weights, brain, opponent_agent, seed, max_steps=500, time_limit=None, fruit_rewards=None):
    """
    Verilen ağırlıklarla öğrencinin beyin modülünü kullanarak oyun oynatır.
    Dönüş: fitness skoru (öğrencinin fitness fonksiyonuyla hesaplanır)
    """
    nn_agent = NNAgentWrapper(weights, brain, name="Egitilen")
    
    game = game_engine.SnakeGame(
        nn_agent, opponent_agent,
        seed=seed,
        max_steps=max_steps,
        time_limit=time_limit if time_limit else 99.0,
        fruit_rewards=fruit_rewards
    )
    
    while not game.is_over():
        game.step()
    
    # === FITNESS İSTATİSTİKLERİNİ TOPLA ===
    me = game.snakes[0]
    opp = game.snakes[1]
    w_idx = game.winner()
    
    stats = {
        "survived_steps": game.step_count,
        "my_length": me.length,
        "my_energy": me.energy,
        "opp_length": opp.length,
        "opp_alive": opp.alive,
        "my_alive": me.alive,
        "won": w_idx == 0,
        "lost": w_idx == 1,
        "draw": w_idx is None or w_idx == -1,
        "max_steps": max_steps,
        "step_count": game.step_count,
    }
    
    # Öğrencinin fitness fonksiyonunu çağır
    try:
        return brain.fitness(stats)
    except Exception as e:
        # Öğrencinin fitness fonksiyonunda hata varsa düşük skor ver
        return -999.0


class NNAgentWrapper:
    """Eğitim sırasında kullanılan hafif sinir ağı ajanı. Öğrencinin forward fonksiyonunu kullanır."""
    
    def __init__(self, weights, brain, name="NN"):
        self.name = name
        self.weights = weights
        self.brain = brain
    
    def act(self, obs):
        try:
            return self.brain.forward(self.weights, obs["grid"], obs["stats"])
        except Exception:
            # Öğrencinin forward fonksiyonunda hata varsa rastgele git
            return np.random.randint(0, 4)
    
    def handle_reward(self, reward, done):
        pass
    
    def reset(self):
        pass


class SimpleOpponent:
    """Basit bir rakip ajan - en yakın meyveye gider."""
    
    def __init__(self, name="Rakip"):
        self.name = name
    
    def act(self, obs):
        grid = obs["grid"]
        stats = obs["stats"]
        
        kafa = np.argwhere(grid == 1)
        if len(kafa) == 0:
            return np.random.randint(0, 4)
        
        kafa_r, kafa_c = kafa[0]
        
        meyveler = np.argwhere((grid == 6) | (grid == 7))
        
        if len(meyveler) == 0:
            return np.random.randint(0, 4)
        
        mesafeler = np.abs(meyveler[:, 0] - kafa_r) + np.abs(meyveler[:, 1] - kafa_c)
        en_yakin = meyveler[np.argmin(mesafeler)]
        
        dr = en_yakin[0] - kafa_r
        dc = en_yakin[1] - kafa_c
        
        if abs(dr) > abs(dc):
            return 2 if dr > 0 else 0  # AŞAĞI veya YUKARI
        else:
            return 1 if dc > 0 else 3  # SAĞ veya SOL
    
    def handle_reward(self, reward, done):
        pass
    
    def reset(self):
        pass


# ==================== EĞİTİM MOTORU ====================

class NNTrainer:
    """
    Evolution Strategy (ES) tabanlı sinir ağı eğiticisi.
    
    Öğrencinin yazdığı beyin modülünü kullanarak:
    - Mimariyi (architecture) beyin dosyasından okur
    - Fitness fonksiyonunu beyin dosyasından çağırır
    - Forward fonksiyonunu beyin dosyasından çağırır
    
    OpenAI ES yaklaşımı:
    - Bir "ana" ağırlık seti tutulur
    - Her nesilde, bu ağırlıklara küçük gürültüler eklenerek popülasyon oluşturulur
    - Her birey birkaç oyun oynar, fitness hesaplanır
    - En iyilerin gürültü yönünde ağırlıklar güncellenir
    """
    
    def __init__(self, brain=None, opponent_agent=None, fruit_rewards=None, time_limit=None, 
                 max_steps=500, callback=None):
        """
        Args:
            brain: Öğrencinin beyin modülü (architecture, fitness, forward içermeli)
            opponent_agent: Rakip ajan (act, handle_reward, reset metotlarına sahip)
            fruit_rewards: Meyve ödülleri dict'i (arena ayarlarından)
            time_limit: Karar süresi limiti
            max_steps: Oyun başına max adım
            callback: Her nesil sonunda çağrılacak fonksiyon (log mesajı için)
        """
        self.brain = brain or DefaultBrain()
        self.opponent = opponent_agent or SimpleOpponent()
        self.opponents = [self.opponent]
        self.fruit_rewards = fruit_rewards
        self.time_limit = time_limit
        self.max_steps = max_steps
        self.callback = callback or (lambda msg: None)
        
        # Mimariyi beyin modülünden oku
        self.architecture = getattr(self.brain, 'architecture', [904, 64, 64, 4])
        self.activation = getattr(self.brain, 'activation', 'tanh')
    
    def _init_weights(self):
        """Öğrencinin mimarisine göre Xavier initialization ile ağırlıklar oluştur."""
        rng = np.random.default_rng()
        weights = {}
        
        for i in range(len(self.architecture) - 1):
            fan_in = self.architecture[i]
            fan_out = self.architecture[i + 1]
            scale = np.sqrt(2.0 / (fan_in + fan_out))
            
            weights[f"w{i}"] = rng.normal(0, scale, (fan_out, fan_in))
            weights[f"b{i}"] = np.zeros(fan_out)
        
        return weights
    
    def _weights_to_vector(self, weights):
        """Ağırlık dict'ini düz vektöre çevir ve shape'leri kaydet."""
        self.shapes = {k: v.shape for k, v in weights.items()}
        self.keys = list(weights.keys())
        return np.concatenate([weights[k].flatten() for k in self.keys])
    
    def _vector_to_weights(self, vec):
        """Düz vektörü ağırlık dict'ine çevir."""
        idx = 0
        weights = {}
        
        for key in self.keys:
            shape = self.shapes[key]
            size = int(np.prod(shape))
            weights[key] = vec[idx:idx+size].reshape(shape)
            idx += size
        
        return weights
    
    def _evaluate(self, weights, num_games=5, base_seed=0):
        """Birden fazla oyun oynayarak fitness hesapla. Tüm rakiplere karşı oynatır."""
        total_fitness = 0.0
        
        for g in range(num_games):
            seed = base_seed + g
            opp = self.opponents[g % len(self.opponents)]
            try:
                fitness = fast_simulate(
                    weights, self.brain, opp,
                    seed=seed,
                    max_steps=self.max_steps,
                    time_limit=self.time_limit,
                    fruit_rewards=self.fruit_rewards
                )
                total_fitness += fitness
            except Exception as e:
                total_fitness -= 500
        
        return total_fitness / num_games
    
    def train(self, base_weights=None, generations=100, population_size=30, sigma=0.05, 
              learning_rate=0.03, games_per_eval=3, stop_event=None):
        """
        Evolution Strategy ile eğitim yap.
        
        Args:
            base_weights: Devam edilecek mevcut ağırlıklar (dict). Yoksa sıfırdan başlar.
            generations: Toplam nesil sayısı
            population_size: Her nesildeki birey sayısı (çift olmalı)
            sigma: Gürültü şiddeti
            learning_rate: Öğrenme oranı
            games_per_eval: Her bireyin oynayacağı oyun sayısı
            stop_event: Dışarıdan durdurma sinyali (threading.Event)
            
        Returns:
            (best_weights_dict, logs_list, final_fitness)
        """
        logs = []
        
        # Başlangıç ağırlıkları
        if base_weights is not None:
            weights = base_weights
            self.callback("📥 Mevcut model.json yüklendi, eğitim kaldığı yerden devam ediyor...")
        else:
            weights = self._init_weights()
            self.callback("🌱 Yeni model sıfırdan oluşturuldu.")
            
        theta = self._weights_to_vector(weights)
        n_params = len(theta)
        
        # Mimari bilgisini logla
        arch_str = " → ".join(str(x) for x in self.architecture)
        self.callback(f"🧠 Sinir Ağı Mimarisi: {arch_str}")
        self.callback(f"🎯 Aktivasyon: {self.activation}")
        self.callback(f"📊 Toplam parametre: {n_params:,}")
        self.callback(f"🏋 Eğitim: {generations} nesil × {population_size} birey × {games_per_eval} oyun")
        self.callback(f"⚙ Meyve ödülleri: {self.fruit_rewards}")
        self.callback(f"⏱ Süre limiti: {self.time_limit}")
        self.callback("─" * 40)
        
        logs.append(f"Mimari: {arch_str}")
        logs.append(f"Parametre sayısı: {n_params}")
        
        if population_size % 2 != 0:
            population_size += 1
        
        best_ever_fitness = -9999
        best_ever_theta = theta.copy()
        stale_count = 0
        
        rng = np.random.default_rng(42)
        
        for gen in range(generations):
            if stop_event and stop_event.is_set():
                self.callback("⚠ Eğitim durduruldu!")
                break
            
            t0 = time.time()
            
            # Antithetik örnekleme: epsilon ve -epsilon çiftleri kullan
            half_pop = population_size // 2
            epsilons = rng.standard_normal((half_pop, n_params))
            
            # Her epsilon ve -epsilon için fitness hesapla
            fitness_pos = np.zeros(half_pop)
            fitness_neg = np.zeros(half_pop)
            
            base_seed = gen * 1000
            
            for i in range(half_pop):
                # Pozitif mutasyon
                w_pos = self._vector_to_weights(theta + sigma * epsilons[i])
                fitness_pos[i] = self._evaluate(w_pos, games_per_eval, base_seed)
                
                # Negatif mutasyon (antithetik)
                w_neg = self._vector_to_weights(theta - sigma * epsilons[i])
                fitness_neg[i] = self._evaluate(w_neg, games_per_eval, base_seed)
            
            # Tüm fitness'ları birleştir
            all_fitness = np.concatenate([fitness_pos, fitness_neg])
            
            # Fitness'ları normalize et (rank-based)
            ranks = np.zeros_like(all_fitness)
            sorted_idx = np.argsort(all_fitness)
            for rank, idx in enumerate(sorted_idx):
                ranks[idx] = rank
            # Normalize: [-0.5, 0.5] aralığına çek
            ranks = (ranks / (len(ranks) - 1)) - 0.5
            
            # Gradyan tahmini
            gradient = np.zeros(n_params)
            for i in range(half_pop):
                gradient += ranks[i] * epsilons[i]         # pozitif
                gradient -= ranks[half_pop + i] * epsilons[i]  # negatif
            gradient /= (half_pop * sigma)
            
            # Ağırlık güncellemesi
            theta += learning_rate * gradient
            
            # Adaptif sigma: iyileşme durmazsa sigma'yı artır
            gen_best = float(np.max(all_fitness))
            gen_mean = float(np.mean(all_fitness))
            
            if gen_best > best_ever_fitness:
                best_ever_fitness = gen_best
                best_ever_theta = theta.copy()
                stale_count = 0
            else:
                stale_count += 1
            
            # Adaptif ayarlar
            if stale_count > 10:
                sigma = min(sigma * 1.05, 0.2)
                stale_count = 0
                self.callback(f"   📈 Sigma artırıldı: {sigma:.4f}")
            
            elapsed = time.time() - t0
            
            # Her 5 nesilde veya son nesilde log
            if gen % 5 == 0 or gen == generations - 1:
                msg = f"Nesil {gen+1}/{generations} | En iyi: {gen_best:.1f} | Ort: {gen_mean:.1f} | Rekor: {best_ever_fitness:.1f} | σ={sigma:.4f} | {elapsed:.1f}s"
                self.callback(msg)
                logs.append(msg)
        
        # En iyi ağırlıkları döndür
        best_weights = self._vector_to_weights(best_ever_theta)
        
        # Son değerlendirme (daha fazla oyunla)
        self.callback("─" * 40)
        self.callback("🏆 Final değerlendirmesi (10 oyun)...")
        final_fitness = self._evaluate(best_weights, num_games=10, base_seed=99999)
        self.callback(f"🏆 Final fitness: {final_fitness:.1f}")
        logs.append(f"Final fitness: {final_fitness:.1f}")
        
        return best_weights, logs, final_fitness
    
    @staticmethod
    def weights_to_json(weights):
        """Ağırlıkları JSON-serializable dict'e çevir."""
        return {
            key: val.tolist()
            for key, val in weights.items()
        }
    
    @staticmethod
    def save_weights(weights, filepath):
        """Ağırlıkları JSON dosyasına kaydet."""
        data = NNTrainer.weights_to_json(weights)
        with open(filepath, "w") as f:
            json.dump(data, f)
