"""
Örnek ajan: greedy. data_dir/*.json varsa içinden 'aggression' okur.
NOT: Bu sadece test ajanı. Gerçek teslimde öğrenme tabanlı olması gerekiyor.
"""
import os
import glob
import json
import numpy as np
from base_agent import BaseAgent


class GreedyAgent(BaseAgent):
    def __init__(self, name="ahmet", data_dir=None):
        super().__init__(name=name, data_dir=data_dir)
        self.aggression = 1.0
        if data_dir:
            for jf in glob.glob(os.path.join(data_dir, "*.json")):
                try:
                    with open(jf) as f:
                        d = json.load(f)
                    if isinstance(d, dict) and "aggression" in d:
                        self.aggression = float(d["aggression"])
                        break
                except Exception:
                    pass

    def act(self, obs):
        head = tuple(np.argwhere(obs == 1)[0])
        food_cells = np.argwhere(obs == 5)
        food = tuple(food_cells[0]) if len(food_cells) > 0 else None

        danger = set()
        for v in (2, 3, 4):
            for c in np.argwhere(obs == v):
                danger.add(tuple(c))

        DIRS = {0: (-1, 0), 1: (0, 1), 2: (1, 0), 3: (0, -1)}
        G = obs.shape[0]

        def safe(d):
            dr, dc = DIRS[d]
            nr, nc = head[0] + dr, head[1] + dc
            return 0 <= nr < G and 0 <= nc < G and (nr, nc) not in danger

        if food is not None:
            dr_f = food[0] - head[0]; dc_f = food[1] - head[1]
            if abs(dr_f) >= abs(dc_f):
                pref = [2 if dr_f > 0 else 0, 1 if dc_f > 0 else 3,
                        0 if dr_f > 0 else 2, 3 if dc_f > 0 else 1]
            else:
                pref = [1 if dc_f > 0 else 3, 2 if dr_f > 0 else 0,
                        3 if dc_f > 0 else 1, 0 if dr_f > 0 else 2]
        else:
            pref = [0, 1, 2, 3]

        for d in pref:
            if safe(d): return d
        for d in range(4):
            if safe(d): return d
        return 0
