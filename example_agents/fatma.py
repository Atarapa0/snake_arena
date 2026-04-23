"""Örnek ajan: en yakın yeme Manhattan."""
import numpy as np
from base_agent import BaseAgent


class ManhattanAgent(BaseAgent):
    def __init__(self, name="zeynep", data_dir=None):
        super().__init__(name=name, data_dir=data_dir)

    def act(self, obs):
        head = tuple(np.argwhere(obs == 1)[0])
        food_cells = np.argwhere(obs == 5)
        food = tuple(food_cells[0]) if len(food_cells) > 0 else (15, 15)

        danger = set()
        for v in (2, 3, 4):
            for c in np.argwhere(obs == v):
                danger.add(tuple(c))

        DIRS = {0: (-1, 0), 1: (0, 1), 2: (1, 0), 3: (0, -1)}
        G = obs.shape[0]

        best, best_d = 1e9, 0
        for d in range(4):
            dr, dc = DIRS[d]
            nr, nc = head[0] + dr, head[1] + dc
            if not (0 <= nr < G and 0 <= nc < G): continue
            if (nr, nc) in danger: continue
            dist = abs(nr - food[0]) + abs(nc - food[1])
            if dist < best:
                best = dist; best_d = d
        return best_d
