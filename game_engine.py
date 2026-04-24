import time
import numpy as np
from collections import deque
from typing import Optional

GRID_SIZE = 30
INITIAL_LENGTH = 3
INITIAL_ENERGY = 100
MAX_ENERGY = 200
DEFAULT_MAX_STEPS = 2000
TIME_LIMIT = 0.1  # 100 ms

DIRS = {0: (-1, 0), 1: (0, 1), 2: (1, 0), 3: (0, -1)}
OPPOSITE = {0: 2, 2: 0, 1: 3, 3: 1}
DIR_NAME = {0: "↑", 1: "→", 2: "↓", 3: "←", -1: "?"}

class Snake:
    def __init__(self, name, body, direction):
        self.name = name
        self.body = body  # deque, rightmost is head
        self.direction = direction
        self.alive = True
        self.death_reason = None
        self.energy = INITIAL_ENERGY
        self.target_length = INITIAL_LENGTH

    @property
    def head(self):
        return self.body[-1]

    @property
    def length(self):
        return len(self.body)

class SnakeGame:
    def __init__(self, agent_a, agent_b, seed: Optional[int] = None, max_steps: int = DEFAULT_MAX_STEPS, time_limit: float = 0.1, fruit_rewards: dict = None):
        self.agents = [agent_a, agent_b]
        self.rng = np.random.default_rng(seed)
        self.step_count = 0
        self.max_steps = int(max_steps)
        self.time_limit = float(time_limit)
        
        # Default fruit rewards if not provided
        if fruit_rewards is None:
            fruit_rewards = {
                6: {"len": 1, "egy": 20, "name": "Kırmızı Elma"},
                7: {"len": 3, "egy": 50, "name": "Altın Elma"},
                8: {"len": -2, "egy": 100, "name": "Zehirli Meyve"}
            }
        self.fruit_rewards = fruit_rewards
        
        self.events_log = []
        self.last_actions = {}
        
        self.walls = set()
        self.fruits = {} # (r,c) -> type (6, 7, 8)
        
        self._init()

    def _init(self):
        # 15, 2-4 and 15, 25-27
        s0 = deque([(15, 2 + i) for i in range(INITIAL_LENGTH)])
        s1 = deque([(15, GRID_SIZE - 3 - i) for i in range(INITIAL_LENGTH)])
        self.snakes = [
            Snake(self.agents[0].name, s0, 1),
            Snake(self.agents[1].name, s1, 3),
        ]
        self._generate_walls()
        self._spawn_fruit(6) # Red
        self._spawn_fruit(7) # Gold
        self._spawn_fruit(8) # Poison
        
        for ag in self.agents:
            try:
                ag.reset()
            except Exception:
                pass

    def _occupied(self):
        cells = set(self.walls)
        for s in self.snakes:
            if s.alive:
                cells.update(s.body)
        cells.update(self.fruits.keys())
        return cells

    def _generate_walls(self):
        # 3 random walls: L, U, I
        shapes = [
            [(0,0), (1,0), (2,0), (2,1)], # L
            [(0,0), (1,0), (2,0), (2,1), (2,2), (1,2), (0,2)], # U
            [(0,0), (1,0), (2,0), (3,0)] # I
        ]
        # To avoid blocking start paths, avoid row 13-17
        for shape in shapes:
            placed = False
            for _ in range(100):
                r = int(self.rng.integers(0, GRID_SIZE - 5))
                c = int(self.rng.integers(0, GRID_SIZE - 5))
                if 12 <= r <= 18:
                    continue # leave middle open for start
                piece = {(r+dr, c+dc) for (dr, dc) in shape}
                if not piece.intersection(self.walls):
                    self.walls.update(piece)
                    placed = True
                    break

    def _spawn_fruit(self, fruit_type):
        if self.step_count > 1000:
            return # Stop spawning after 1000 steps
        
        occ = self._occupied()
        free = [(r, c) for r in range(GRID_SIZE) for c in range(GRID_SIZE) if (r, c) not in occ]
        if not free:
            return
        idx = int(self.rng.integers(0, len(free)))
        self.fruits[free[idx]] = fruit_type

    def get_observation(self, idx: int) -> dict:
        grid = np.zeros((GRID_SIZE, GRID_SIZE), dtype=np.int8)
        
        for w in self.walls:
            grid[w] = 5
            
        for f_pos, f_type in self.fruits.items():
            grid[f_pos] = f_type
            
        me, opp = self.snakes[idx], self.snakes[1 - idx]
        if opp.alive:
            for c in opp.body: grid[c] = 4
            grid[opp.head] = 3
        if me.alive:
            for c in me.body: grid[c] = 2
            grid[me.head] = 1
            
        stats = [
            me.energy,
            me.length,
            opp.length if opp.alive else 0,
            opp.energy if opp.alive else 0
        ]
        return {"grid": grid, "stats": stats}

    def is_over(self) -> bool:
        return sum(s.alive for s in self.snakes) <= 1 or self.step_count >= self.max_steps

    def winner(self):
        s0, s1 = self.snakes
        if s0.alive and not s1.alive: return 0
        if s1.alive and not s0.alive: return 1
        if not s0.alive and not s1.alive: return None # Both died
        # Both alive (time limit)
        if s0.length > s1.length: return 0
        if s1.length > s0.length: return 1
        return None

    def step(self):
        if self.is_over():
            return
        self.step_count += 1

        # 1) Collect Actions & Decrease Energy
        last_actions = {}
        for i, (ag, s) in enumerate(zip(self.agents, self.snakes)):
            if not s.alive:
                continue
            
            s.energy -= 1
            if s.energy <= 0:
                s.alive = False
                s.death_reason = "açlıktan öldü"
                self.events_log.append((self.step_count, f"{s.name} enerjisi bitti"))
                continue
                
            obs = self.get_observation(i)
            t0 = time.perf_counter()
            try:
                # Support old agents slightly, even though obs is dict
                req = int(ag.act(obs))
            except Exception as e:
                req = -1
                self.events_log.append((self.step_count, f"{ag.name} HATA: {e}"))
            elapsed = time.perf_counter() - t0
            
            cur = s.direction
            applied = req
            if req not in (0, 1, 2, 3): applied = cur
            elif req == OPPOSITE[cur]: applied = cur
            
            if elapsed > self.time_limit:
                applied = cur
                self.events_log.append((self.step_count, f"{ag.name} zaman aşımı ({elapsed:.2f}s - Kural: eski yöne devam)"))
                
            s.direction = applied
            last_actions[i] = (req, applied)
            
        self.last_actions = last_actions

        # 2) Calculate New Heads (Torus)
        new_heads = {}
        for i, s in enumerate(self.snakes):
            if not s.alive: continue
            dr, dc = DIRS[s.direction]
            nr = (s.head[0] + dr) % GRID_SIZE
            nc = (s.head[1] + dc) % GRID_SIZE
            new_heads[i] = (nr, nc)

        # 3) Wall Collisions
        for i, h in list(new_heads.items()):
            if h in self.walls:
                self.snakes[i].alive = False
                self.snakes[i].death_reason = "duvara çarptı"
                self.events_log.append((self.step_count, f"{self.snakes[i].name} duvara çarptı"))
                del new_heads[i]

        # 4) Head-to-Head
        if len(new_heads) == 2 and new_heads[0] == new_heads[1]:
            l0, l1 = self.snakes[0].length, self.snakes[1].length
            if l0 > l1:
                self.snakes[1].alive = False
                self.snakes[1].death_reason = "kafa-kafa ezildi"
                del new_heads[1]
            elif l1 > l0:
                self.snakes[0].alive = False
                self.snakes[0].death_reason = "kafa-kafa ezildi"
                del new_heads[0]
            else:
                self.snakes[0].alive = False
                self.snakes[1].alive = False
                self.snakes[0].death_reason = "eşit kafa"
                self.snakes[1].death_reason = "eşit kafa"
                new_heads.clear()

        # 5) Fruits
        eaten_fruits = [] # (pos, type, snake_idx)
        for i, h in new_heads.items():
            if h in self.fruits:
                f_type = self.fruits[h]
                eaten_fruits.append((h, f_type, i))
                
        # 6) Apply lengths & pops & collisions
        future = {}
        for j, s in enumerate(self.snakes):
            if not s.alive: continue
            body = list(s.body)
            future[j] = body
            
        for i, h in list(new_heads.items()):
            if h in future.get(i, [])[:-1]: # own body except tail (which might move)
                self.snakes[i].alive = False
                self.snakes[i].death_reason = "kendi gövdesine çarptı"
                del new_heads[i]
                continue
            if h in future.get(1 - i, []):
                self.snakes[i].alive = False
                self.snakes[i].death_reason = "rakip gövdeye çarptı"
                del new_heads[i]
                continue

        # Process movement & ate items
        for i, h in new_heads.items():
            s = self.snakes[i]
            s.body.append(h)
            
            step_reward = 0.1 # Her hayatta kaldığı adım için ufak bir artı ödül
            ate_type = next((ft for fp, ft, si in eaten_fruits if si == i), None)
            
            if ate_type in (6, 7, 8):
                rewards = self.fruit_rewards[ate_type]
                s.target_length = max(2, s.target_length + rewards["len"])
                s.energy = min(MAX_ENERGY, s.energy + rewards["egy"])
                
                # RL Ödülü: Elma tipine göre ödül ekle (+ veya -)
                if ate_type == 6: step_reward += 10 # Normal Elma
                elif ate_type == 7: step_reward += 20 # Altın Elma
                elif ate_type == 8: step_reward -= 5 # Zehir (Enerji verse de boy kısalttığı için ceza)

                sign_len = "+" if rewards['len'] > 0 else ""
                sign_egy = "+" if rewards['egy'] > 0 else ""
                msg = f"{s.name} {rewards['name']} yedi ({sign_len}{rewards['len']} Boy, {sign_egy}{rewards['egy']} En)"
                self.events_log.append((self.step_count, msg))
            
            # === KUYRUK KESİMİ (Normal Snake Mekaniği) ===
            # Yılanın gerçek boyu (len(body)) hedef boydan büyükse kuyruktan kes
            while len(s.body) > s.target_length:
                s.body.popleft()
            
            # RL Geri Bildirimi (Başı sağ ise)
            if s.alive:
                try: self.agents[i].handle_reward(step_reward, False)
                except: pass
                
        # Ölen yılanlara ceza ödülü ve Done sinyali gönder
        for i, s in enumerate(self.snakes):
            if not s.alive:
                try: self.agents[i].handle_reward(-50, True) # Ölüm cezası
                except: pass

        # Respawn fruits
        for fp, ft, _ in eaten_fruits:
            del self.fruits[fp]
            self._spawn_fruit(ft)

    def snapshot(self) -> dict:
        return {
            "step": self.step_count,
            "max_steps": self.max_steps,
            "grid_size": GRID_SIZE,
            "walls": [list(w) for w in self.walls],
            "fruits": [{"pos": list(k), "type": v} for k, v in self.fruits.items()],
            "snakes": [
                {
                    "name": s.name,
                    "body": [list(c) for c in s.body],
                    "head": list(s.head),
                    "direction": s.direction,
                    "alive": s.alive,
                    "length": s.length,
                    "energy": s.energy,
                    "target_length": s.target_length,
                    "death_reason": s.death_reason,
                }
                for s in self.snakes
            ],
            "last_actions": {
                str(k): {"requested": DIR_NAME.get(v[0], "?"), "applied": DIR_NAME.get(v[1], "?")}
                for k, v in self.last_actions.items()
            },
            "events_tail": self.events_log[-10:],
            "is_over": self.is_over(),
            "winner": self.winner() if self.is_over() else None,
        }
