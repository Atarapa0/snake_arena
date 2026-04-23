"""Örnek ajan: güvenli rastgele."""
import numpy as np
from base_agent import BaseAgent


class SafeRandomAgent(BaseAgent):
    def __init__(self, name="mehmet", data_dir=None):
        super().__init__(name=name, data_dir=data_dir)
        self.rng = np.random.default_rng(42)

    def act(self, obs):
        head = tuple(np.argwhere(obs == 1)[0])
        danger = set()
        for v in (2, 3, 4):
            for c in np.argwhere(obs == v):
                danger.add(tuple(c))
        DIRS = {0: (-1, 0), 1: (0, 1), 2: (1, 0), 3: (0, -1)}
        G = obs.shape[0]
        safe_dirs = []
        for d in range(4):
            dr, dc = DIRS[d]
            nr, nc = head[0] + dr, head[1] + dc
            if 0 <= nr < G and 0 <= nc < G and (nr, nc) not in danger:
                safe_dirs.append(d)
        if safe_dirs:
            return int(self.rng.choice(safe_dirs))
        return 0
