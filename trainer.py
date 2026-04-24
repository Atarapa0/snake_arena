"""
GERÇEK SİNİR AĞI EĞİTİCİSİ - Evolution Strategy (ES)
=====================================================
Bu modül, 904→64→64→4 sinir ağı mimarisini gerçekten eğitir.
Oyun motorunu kullanarak binlerce oyun simüle eder ve ağırlıkları evrimleştirir.

Kullanım:
    from trainer import NNTrainer
    trainer = NNTrainer(agent_a_cls, agent_b, fruit_rewards, time_limit, ...)
    best_weights, logs = trainer.train(generations=100, population_size=30)
"""

import numpy as np
import json
import time
import copy
from collections import deque

import game_engine


# ==================== HIZLI SİMÜLASYON ====================
# Eğitim sırasında zaman kaybetmemek için time.sleep olmadan oyun oynatırız

def fast_simulate(weights, opponent_agent, seed, max_steps=500, time_limit=None, fruit_rewards=None):
    """
    Verilen ağırlıklarla bir sinir ağı ajanı oluşturur ve rakibe karşı oynatır.
    Dönüş: fitness skoru
    """
    nn_agent = NNAgentWrapper(weights, name="Egitilen")
    
    game = game_engine.SnakeGame(
        nn_agent, opponent_agent,
        seed=seed,
        max_steps=max_steps,
        time_limit=time_limit if time_limit else 99.0,  # Eğitimde süre limiti opsiyonel
        fruit_rewards=fruit_rewards
    )
    
    while not game.is_over():
        game.step()
    
    # === FITNESS HESAPLA ===
    me = game.snakes[0]
    opp = game.snakes[1]
    
    fitness = 0.0
    
    # 1) Hayatta kalma süresi (daha uzun yaşamak iyi)
    fitness += game.step_count * 0.1
    
    # 2) Boy (uzun yılan iyi)
    fitness += me.length * 15.0
    
    # 3) Enerji (daha fazla enerji iyi - açlıktan ölme riski az)
    fitness += me.energy * 0.05
    
    # 4) Kazanma/Kaybetme büyük ödül
    w_idx = game.winner()
    if w_idx == 0:
        # Biz kazandık
        fitness += 200.0
        if not opp.alive:
            # Rakibi öldürdük (K.O.) - ekstra büyük ödül
            fitness += 100.0
    elif w_idx == 1:
        # Kaybettik
        fitness -= 100.0
    else:
        # Berabere - boyumuza göre hafif ödül/ceza
        if me.alive and opp.alive:
            fitness += (me.length - opp.length) * 10.0
    
    # 5) Ölüm cezası
    if not me.alive:
        fitness -= 150.0
        # Erken ölüm daha kötü
        if game.step_count < 50:
            fitness -= 200.0
        elif game.step_count < 200:
            fitness -= 100.0
    
    return fitness


class NNAgentWrapper:
    """Eğitim sırasında kullanılan hafif sinir ağı ajanı. BaseAgent'a gerek yok."""
    
    def __init__(self, weights, name="NN"):
        self.name = name
        self.w1 = weights["w1"]
        self.b1 = weights["b1"]
        self.w2 = weights["w2"]
        self.b2 = weights["b2"]
        self.w_out = weights["w_out"]
        self.b_out = weights["b_out"]
    
    def act(self, obs):
        grid = obs["grid"]
        stats = obs["stats"]
        
        grid_flat = np.array(grid, dtype=np.float32).flatten()
        stats_array = np.array(stats, dtype=np.float32)
        x = np.concatenate((grid_flat, stats_array))
        
        # Forward pass
        x = np.dot(self.w1, x) + self.b1
        x = np.tanh(x)
        x = np.dot(self.w2, x) + self.b2
        x = np.tanh(x)
        logits = np.dot(self.w_out, x) + self.b_out
        
        return int(np.argmax(logits))
    
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
        
        # Kendi kafamızı bul (bu ajan 2. oyuncu olarak yüklenecek, yani kafası 1)
        kafa = np.argwhere(grid == 1)
        if len(kafa) == 0:
            return np.random.randint(0, 4)
        
        kafa_r, kafa_c = kafa[0]
        
        # Meyveleri bul (6, 7)
        meyveler = np.argwhere((grid == 6) | (grid == 7))
        
        if len(meyveler) == 0:
            return np.random.randint(0, 4)
        
        # En yakın meyveyi bul
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
    
    OpenAI ES yaklaşımı:
    - Bir "ana" ağırlık seti tutulur
    - Her nesilde, bu ağırlıklara küçük gürültüler eklenerek popülasyon oluşturulur
    - Her birey birkaç oyun oynar, fitness hesaplanır
    - En iyilerin gürültü yönünde ağırlıklar güncellenir
    """
    
    def __init__(self, opponent_agent=None, fruit_rewards=None, time_limit=None, 
                 max_steps=500, callback=None):
        """
        Args:
            opponent_agent: Rakip ajan (act, handle_reward, reset metotlarına sahip)
            fruit_rewards: Meyve ödülleri dict'i (arena ayarlarından)
            time_limit: Karar süresi limiti
            max_steps: Oyun başına max adım
            callback: Her nesil sonunda çağrılacak fonksiyon (log mesajı için)
        """
        self.opponent = opponent_agent or SimpleOpponent()
        self.opponents = [self.opponent]  # Birden fazla rakip destekler
        self.fruit_rewards = fruit_rewards
        self.time_limit = time_limit
        self.max_steps = max_steps
        self.callback = callback or (lambda msg: None)
        
        # Ağ boyutları
        self.input_size = 904   # 30*30 + 4
        self.hidden1 = 64
        self.hidden2 = 64
        self.output_size = 4
    
    def _init_weights(self):
        """Xavier initialization ile rastgele ağırlıklar oluştur."""
        rng = np.random.default_rng()
        
        # Xavier initialization (tanh için uygun)
        w1_scale = np.sqrt(2.0 / (self.input_size + self.hidden1))
        w2_scale = np.sqrt(2.0 / (self.hidden1 + self.hidden2))
        wout_scale = np.sqrt(2.0 / (self.hidden2 + self.output_size))
        
        return {
            "w1": rng.normal(0, w1_scale, (self.hidden1, self.input_size)),
            "b1": np.zeros(self.hidden1),
            "w2": rng.normal(0, w2_scale, (self.hidden2, self.hidden1)),
            "b2": np.zeros(self.hidden2),
            "w_out": rng.normal(0, wout_scale, (self.output_size, self.hidden2)),
            "b_out": np.zeros(self.output_size),
        }
    
    def _weights_to_vector(self, weights):
        """Ağırlık dict'ini düz vektöre çevir."""
        return np.concatenate([weights[k].flatten() for k in ["w1", "b1", "w2", "b2", "w_out", "b_out"]])
    
    def _vector_to_weights(self, vec):
        """Düz vektörü ağırlık dict'ine çevir."""
        idx = 0
        weights = {}
        
        shapes = {
            "w1": (self.hidden1, self.input_size),
            "b1": (self.hidden1,),
            "w2": (self.hidden2, self.hidden1),
            "b2": (self.hidden2,),
            "w_out": (self.output_size, self.hidden2),
            "b_out": (self.output_size,),
        }
        
        for key in ["w1", "b1", "w2", "b2", "w_out", "b_out"]:
            shape = shapes[key]
            size = int(np.prod(shape))
            weights[key] = vec[idx:idx+size].reshape(shape)
            idx += size
        
        return weights
    
    def _evaluate(self, weights, num_games=5, base_seed=0):
        """Birden fazla oyun oynayarak fitness hesapla. Tüm rakiplere karşı oynatır."""
        total_fitness = 0.0
        
        for g in range(num_games):
            seed = base_seed + g
            # Rakipleri dönüşümlü kullan
            opp = self.opponents[g % len(self.opponents)]
            try:
                fitness = fast_simulate(
                    weights, opp,
                    seed=seed,
                    max_steps=self.max_steps,
                    time_limit=self.time_limit,
                    fruit_rewards=self.fruit_rewards
                )
                total_fitness += fitness
            except Exception as e:
                total_fitness -= 500  # Hata varsa çok kötü skor
        
        return total_fitness / num_games
    
    def train(self, generations=100, population_size=30, sigma=0.05, 
              learning_rate=0.03, games_per_eval=3, stop_event=None):
        """
        Evolution Strategy ile eğitim yap.
        
        Args:
            generations: Toplam nesil sayısı
            population_size: Her nesildeki birey sayısı (çift olmalı)
            sigma: Gürültü şiddeti
            learning_rate: Öğrenme oranı
            games_per_eval: Her bireyin oynayacağı oyun sayısı
            stop_event: Dışarıdan durdurma sinyali (threading.Event)
            
        Returns:
            (best_weights_dict, logs_list)
        """
        logs = []
        
        # Başlangıç ağırlıkları
        weights = self._init_weights()
        theta = self._weights_to_vector(weights)
        n_params = len(theta)
        
        self.callback(f"🧠 Sinir Ağı: {self.input_size} → {self.hidden1} → {self.hidden2} → {self.output_size}")
        self.callback(f"📊 Toplam parametre: {n_params:,}")
        self.callback(f"🏋 Eğitim: {generations} nesil × {population_size} birey × {games_per_eval} oyun")
        self.callback(f"⚙ Meyve ödülleri: {self.fruit_rewards}")
        self.callback(f"⏱ Süre limiti: {self.time_limit}")
        self.callback("─" * 40)
        
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
                sigma = min(sigma * 1.05, 0.2)  # Gürültüyü artır
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
