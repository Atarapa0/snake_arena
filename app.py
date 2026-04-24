"""
SNAKE ARENA - Flask backend.

Çalıştır:
    pip install flask numpy
    python app.py
    -> http://localhost:5000
"""
import os
import sys
import json
import time
import shutil
import copy
import zipfile
import tempfile
import threading
import importlib.util
import inspect
from pathlib import Path
import logging

import numpy as np
from flask import Flask, request, jsonify, render_template

import game_engine
from base_agent import BaseAgent
# import tournament as T removed


BASE = Path(__file__).parent
UPLOADS = BASE / "uploads"
LEADERBOARD_FILE = BASE / "leaderboard.json"
UPLOADS.mkdir(exist_ok=True)
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))

app = Flask(__name__, static_folder="static", template_folder="templates")
app.config['MAX_CONTENT_LENGTH'] = 1024 * 1024 * 1024  # 1 GB max upload (toplu zip için)

# Terminali rahatlatan kod: Yalnızca hata seviyesindeki (ERROR) loglar çıksın.
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)


# ---------------- Global durum ----------------
STATE_LOCK = threading.Lock()
STATE = {
    "phase": "idle",       # idle | running | done
    "match_queue": [],     # dict lists: [{"p1", "p2", "played": False, "winner": None}]
    "current_match": None,
    "live_game": None,
    "tournament_id": 0,
    "speed_ms": 50,        # 1-300 ms
    "max_steps": 2000,     # max adim
    "mb_limit": 20,        # mb check
    "match_history": [],   # played matches
    "time_limit": 0.1,     # saniye
    "fruit_rewards": {
        6: {"len": 1, "egy": 20, "name": "Kırmızı Elma"},
        7: {"len": 3, "egy": 50, "name": "Altın Elma"},
        8: {"len": -2, "egy": 100, "name": "Zehirli Meyve"}
    }
}


# ---------------- Leaderboard ----------------
def load_leaderboard():
    if LEADERBOARD_FILE.exists():
        try:
            return json.loads(LEADERBOARD_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_leaderboard(lb):
    LEADERBOARD_FILE.write_text(json.dumps(lb, indent=2, ensure_ascii=False), encoding="utf-8")


def points_for_rank(rank):
    table = {1: 100, 2: 70, 3: 50, 4: 50,
             5: 30, 6: 30, 7: 30, 8: 30,
             9: 15, 10: 15, 11: 15, 12: 15,
             13: 15, 14: 15, 15: 15, 16: 15}
    return table.get(rank, 5)


def update_leaderboard(rounds):
    """
    Turnuva bitince çağrılır.
    """
    standings = T.get_final_standings(rounds)
    lb = load_leaderboard()
    
    with STATE_LOCK:
        tid = STATE["tournament_id"]
        wp = STATE.get("win_points", 50)
        fp = STATE.get("food_points", 10)
        
    pts_map = {}
    for rnd in rounds:
        for m in rnd:
            if not m["played"]: continue
            p1, p2 = m["p1"], m["p2"]
            if p1 and p1 != "__BYE__":
                pts_map.setdefault(p1, 0)
                l1 = m["p1_length"] if m.get("p1_length") is not None else 0
                if l1 >= 3: pts_map[p1] += (l1 - 3) * fp
            if p2 and p2 != "__BYE__":
                pts_map.setdefault(p2, 0)
                l2 = m["p2_length"] if m.get("p2_length") is not None else 0
                if l2 >= 3: pts_map[p2] += (l2 - 3) * fp
            if m["winner"] and m["winner"] != "__BYE__":
                pts_map.setdefault(m["winner"], 0)
                if p1 != "__BYE__" and p2 != "__BYE__":
                    pts_map[m["winner"]] += wp
                    
    for name, rank in standings.items():
        pts = pts_map.get(name, 0)
        if name not in lb:
            lb[name] = {"total": 0, "history": []}
        existing = [h for h in lb[name]["history"] if h["tournament"] == tid]
        if existing:
            existing[0].update({"rank": rank, "points": pts})
        else:
            lb[name]["history"].append({"tournament": tid, "rank": rank, "points": pts})
        lb[name]["total"] = lb[name]["history"][-1]["points"]
    save_leaderboard(lb)


# ---------------- Ajan yükleme ----------------
def load_agent_from_dir(player_dir: Path):
    """player_dir içinde .py bul, BaseAgent miras alan ilk sınıfı örnekle."""
    py_files = list(player_dir.glob("*.py"))
    if not py_files:
        raise RuntimeError(f"{player_dir.name}: .py dosyası yok")
    py_path = py_files[0]
    player_name = player_dir.name

    mod_name = f"agent_{player_name}_{int(time.time() * 1000)}"
    spec = importlib.util.spec_from_file_location(mod_name, py_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    agent_cls = None
    for _, obj in inspect.getmembers(mod, inspect.isclass):
        try:
            if issubclass(obj, BaseAgent) and obj is not BaseAgent:
                agent_cls = obj
                break
        except TypeError:
            continue
    if agent_cls is None:
        raise RuntimeError(f"{player_name}: BaseAgent miras alan sınıf bulunamadı")

    # data_dir destekli init dene, yoksa eski imzaya düş
    try:
        agent = agent_cls(name=player_name, data_dir=str(player_dir))
    except TypeError:
        try:
            agent = agent_cls(name=player_name)
        except TypeError:
            agent = agent_cls()
        agent.data_dir = str(player_dir)
    agent.name = player_name
    return agent


def list_players():
    return sorted([p.name for p in UPLOADS.iterdir() if p.is_dir()])


def player_params_size_mb(player_name: str) -> float:
    """Oyuncunun parametre (.py olmayan) dosyalarının toplam boyutu, MB."""
    pdir = UPLOADS / player_name
    if not pdir.exists():
        return 0.0
    total = 0
    for f in pdir.iterdir():
        if f.is_file() and f.suffix.lower() != ".py":
            total += f.stat().st_size
    return total / (1024 * 1024)


def player_is_oversized(player_name: str) -> bool:
    with STATE_LOCK:
        limit = STATE["mb_limit"]
    return player_params_size_mb(player_name) > limit


def player_info_list():
    """UI için: her oyuncunun ismi, param MB'si, oversized mi, param dosyası var mı."""
    with STATE_LOCK:
        limit = STATE["mb_limit"]
    rows = []
    for name in list_players():
        pdir = UPLOADS / name
        size = player_params_size_mb(name)
        has_params = False
        if pdir.exists():
            has_params = any(f.is_file() and f.suffix.lower() != ".py" for f in pdir.iterdir())
        rows.append({
            "name": name,
            "params_mb": round(size, 3),
            "oversized": size > limit,
            "has_params": has_params,
        })
    return rows


def safe_name(raw: str) -> str:
    return "".join(c for c in raw if c.isalnum() or c in "_-")


def validate_agent_dir(pdir: Path):
    """Ajanı yükleyip 1 hamle çalıştırarak doğrular. Exception fırlatır başarısızsa."""
    ag = load_agent_from_dir(pdir)
    test_grid = np.zeros((30, 30), dtype=np.int8)
    test_grid[15, 4] = 1    # kafa
    test_grid[15, 3] = 2    # gövde
    test_grid[15, 2] = 2
    test_grid[15, 25] = 3   # rakip kafa
    test_grid[15, 26] = 4
    test_grid[10, 10] = 6   # Yeni id ile yem
    test_obs = {
        "grid": test_grid,
        "stats": [100, 3, 3, 100]
    }
    action = ag.act(test_obs)
    if action not in (0, 1, 2, 3):
        raise RuntimeError(f"act() {action!r} döndürdü, 0/1/2/3 olmalı")


# ---------------- Maç oynatma ----------------
def play_match_blocking(player_a: str, player_b: str):
    """Blocking olarak bir maç oynat. Returns (winner, l1, l2, steps)."""
    with STATE_LOCK:
        current_max_steps = STATE["max_steps"]
        mb_limit = STATE["mb_limit"]
        time_limit = STATE["time_limit"]
        fruit_rewards = STATE["fruit_rewards"]

    # 0) MB sınırı kontrolü: aşan hükmen mağlup
    a_over = player_is_oversized(player_a)
    b_over = player_is_oversized(player_b)
    if a_over and b_over:
        with STATE_LOCK:
            STATE["live_game"] = {
                "snakes": [], "step": 0, "max_steps": current_max_steps,
                "events_tail": [(0, f"⚠ {player_a} ({player_params_size_mb(player_a):.2f} MB) ve {player_b} ({player_params_size_mb(player_b):.2f} MB) — ikisi de {mb_limit} MB sınırını aştı")],
                "error": "Her iki oyuncu da MB sınırını aştı",
            }
        time.sleep(2)
        # İkisi de diskalifiye — boyları 0, ilki kazanmış say (sonraki turda o da elenir sonunda)
        return player_a, 0, 0, 0
    if a_over:
        with STATE_LOCK:
            STATE["live_game"] = {
                "snakes": [], "step": 0, "max_steps": current_max_steps,
                "events_tail": [(0, f"⚠ {player_a}: {player_params_size_mb(player_a):.2f} MB > {mb_limit} MB sınırı — hükmen mağlup")],
                "error": f"{player_a} MB sınırını aştı",
            }
        time.sleep(2)
        return player_b, 0, 0, 0
    if b_over:
        with STATE_LOCK:
            STATE["live_game"] = {
                "snakes": [], "step": 0, "max_steps": current_max_steps,
                "events_tail": [(0, f"⚠ {player_b}: {player_params_size_mb(player_b):.2f} MB > {mb_limit} MB sınırı — hükmen mağlup")],
                "error": f"{player_b} MB sınırını aştı",
            }
        time.sleep(2)
        return player_a, 0, 0, 0

    # 1) Ajanları yükle
    try:
        a = load_agent_from_dir(UPLOADS / player_a)
    except Exception as e:
        with STATE_LOCK:
            STATE["live_game"] = {"error": f"{player_a} yüklenemedi: {e}",
                                  "snakes": [], "step": 0, "max_steps": current_max_steps,
                                  "events_tail": [(0, str(e))]}
        time.sleep(2)
        return player_b, 0, 0, 0
    try:
        b = load_agent_from_dir(UPLOADS / player_b)
    except Exception as e:
        with STATE_LOCK:
            STATE["live_game"] = {"error": f"{player_b} yüklenemedi: {e}",
                                  "snakes": [], "step": 0, "max_steps": current_max_steps,
                                  "events_tail": [(0, str(e))]}
        time.sleep(2)
        return player_a, 0, 0, 0

    # 2) Oyunu başlat
    game = game_engine.SnakeGame(a, b, seed=int(time.time()) % 100000,
                                 max_steps=current_max_steps,
                                 time_limit=time_limit,
                                 fruit_rewards=fruit_rewards)
    with STATE_LOCK:
        STATE["live_game"] = game.snapshot()

    while not game.is_over():
        game.step()
        with STATE_LOCK:
            STATE["live_game"] = game.snapshot()
            speed = STATE["speed_ms"]
        time.sleep(max(speed, 1) / 1000.0)

    w_idx = game.winner()
    if w_idx is None:
        winner = player_a if game.snakes[0].length >= game.snakes[1].length else player_b
    else:
        winner = game.agents[w_idx].name
    return winner, game.snakes[0].length, game.snakes[1].length, game.step_count


def process_match_points(m):
    """
    Lig usulü puanlama sistemi:
    - Rakibi Doğrudan Elemek (Çarpma/Açlık): 3 Puan
    - Adım Süresi Sonunda Boy Farkıyla Kazanmak: 2 Puan
    - Beraberlik: 1 Puan
    - Kaybetmek: 0 Puan
    """
    if not m.get("played"):
        return
    
    p1 = m["p1"]
    p2 = m["p2"]
    winner = m.get("winner")
    reason = m.get("reason", "")
    
    # Puanları hesapla
    p1_pts = 0
    p2_pts = 0
    
    # Kazananı belirle ve puan tipini saptla
    ko_keywords = ["duvara çarptı", "gövdesine çarptı", "gövdeye çarptı", "enerjisi bitti", 
                    "açlıktan", "kafa-kafa", "eşit kafa", "zaman aşımı", "HATA"]
    
    is_ko = any(kw in reason for kw in ko_keywords)
    
    if winner == p1:
        if is_ko:
            p1_pts = 3  # K.O. - rakibi direkt eledi
        else:
            p1_pts = 2  # Boy farkıyla kazandı
        p2_pts = 0
    elif winner == p2:
        if is_ko:
            p2_pts = 3
        else:
            p2_pts = 2
        p1_pts = 0
    else:
        # Beraberlik
        p1_pts = 1
        p2_pts = 1
    
    # Leaderboard'u güncelle
    lb = load_leaderboard()
    
    for name, pts in [(p1, p1_pts), (p2, p2_pts)]:
        if name and name != "__BYE__":
            if name not in lb:
                lb[name] = {"total": 0, "wins": 0, "draws": 0, "losses": 0, "played": 0}
            
            lb[name]["played"] = lb[name].get("played", 0) + 1
            lb[name]["total"] = lb[name].get("total", 0) + pts
            
            if pts == 3 or pts == 2:
                lb[name]["wins"] = lb[name].get("wins", 0) + 1
            elif pts == 1:
                lb[name]["draws"] = lb[name].get("draws", 0) + 1
            else:
                lb[name]["losses"] = lb[name].get("losses", 0) + 1
    
    save_leaderboard(lb)

def tournament_runner():
    """Arka planda lig sırayla yürüt."""
    while True:
        with STATE_LOCK:
            if STATE["phase"] != "running":
                return
            
            m_idx = None
            m = None
            for i, qm in enumerate(STATE["match_queue"]):
                if not qm["played"]:
                    m_idx = i
                    m = qm
                    break
                    
            if m is None:
                STATE["phase"] = "done"
                return
            else:
                STATE["current_match"] = {
                    "p1": m["p1"], "p2": m["p2"],
                    "id": m["id"], "round_name": f"Maç #{m['id']} - Lig"
                }

        winner, l1, l2, steps = play_match_blocking(m["p1"], m["p2"])
        
        with STATE_LOCK:
            reason = ""
            lg = STATE["live_game"]
            if lg is not None:
                snakes_list = lg.get("snakes", []) if isinstance(lg, dict) else lg.snakes
                for s in snakes_list:
                    # Eger item bir dict ise dict'ten oku, obje ise attribute'tan
                    alive = s.get("alive") if isinstance(s, dict) else s.alive
                    if not alive:
                        s_name = s.get("name") if isinstance(s, dict) else s.name
                        d_reaz = s.get("death_reason") if isinstance(s, dict) else s.death_reason
                        reason += f"{str(s_name)}: {str(d_reaz)} "
            
            m["winner"] = winner
            m["p1_length"] = l1
            m["p2_length"] = l2
            m["steps"] = steps
            m["reason"] = reason
            m["played"] = True
            
            STATE["match_history"].append({
                "id": m["id"],
                "p1": m["p1"], "p2": m["p2"],
                "winner": winner,
                "p1_length": l1,
                "p2_length": l2,
                "steps": steps,
                "reason": reason
            })
            STATE["current_match"] = None
            STATE["live_game"] = None
            
        process_match_points(m)
        time.sleep(1.0)


# ---------------- Routes ----------------
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/egitim")
def egitim():
    return render_template("egitim.html")



# ------------- Eğitim durumu (SSE progress) -------------
TRAIN_STATE = {
    "running": False,
    "logs": [],
    "progress": 0,        # 0-100
    "best_fitness": 0,
    "best_weights": None,  # JSON-ready dict
    "done": False,
    "error": None,
}
TRAIN_LOCK = threading.Lock()


def _train_worker(opponents, fruit_rewards, time_limit, max_steps,
                  generations, population_size, games_per_eval, sigma, learning_rate, base_weights=None):
    """Arka planda sinir ağı eğitimi çalıştırır. Birden fazla rakibe karşı eğitir."""
    from trainer import NNTrainer
    
    def log_callback(msg):
        with TRAIN_LOCK:
            TRAIN_STATE["logs"].append(msg)
    
    try:
        # İlk rakibe karşı trainer oluştur
        trainer = NNTrainer(
            opponent_agent=opponents[0],
            fruit_rewards=fruit_rewards,
            time_limit=time_limit,
            max_steps=max_steps,
            callback=log_callback,
        )
        
        # Eğer 2 rakip varsa, trainer'a ikinci rakibi de ekle
        if len(opponents) > 1:
            trainer.opponents = opponents
            log_callback(f"🐍 {len(opponents)} rakip yüklendi: " + ", ".join(o.name for o in opponents))
        
        best_weights, logs, final_fitness = trainer.train(
            base_weights=base_weights,
            generations=generations,
            population_size=population_size,
            sigma=sigma,
            learning_rate=learning_rate,
            games_per_eval=games_per_eval,
        )
        
        with TRAIN_LOCK:
            TRAIN_STATE["best_weights"] = NNTrainer.weights_to_json(best_weights)
            TRAIN_STATE["best_fitness"] = final_fitness
            TRAIN_STATE["done"] = True
            TRAIN_STATE["running"] = False
            TRAIN_STATE["logs"].append(f"✅ Eğitim tamamlandı! Final fitness: {final_fitness:.1f}")
            TRAIN_STATE["logs"].append("📥 'Model İndir' butonuna basarak model.json dosyanızı alabilirsiniz.")
    except Exception as e:
        import traceback
        with TRAIN_LOCK:
            TRAIN_STATE["error"] = str(e)
            TRAIN_STATE["running"] = False
            TRAIN_STATE["logs"].append(f"❌ HATA: {e}")
            TRAIN_STATE["logs"].append(traceback.format_exc())


@app.route("/api/train", methods=["POST"])
def train():
    """
    Gerçek sinir ağı eğitimi - Evolution Strategy (ES) ile.
    İki ajan yüklenir, sinir ağı her ikisine karşı eğitilir.
    Arena ayarlarını (meyve ödülleri, süre limiti vb.) kullanır.
    """
    with TRAIN_LOCK:
        if TRAIN_STATE["running"]:
            return jsonify({"ok": False, "error": "Eğitim zaten devam ediyor!"}), 400
    
    opponents_files = request.files.getlist("opponents")
    base_model_f = request.files.get("base_model")
    
    if not opponents_files or len(opponents_files) == 0:
        return jsonify({"ok": False, "error": "En az bir rakip ajan dosyası seçmelisiniz!"}), 400
        
    # Mevcut ağırlıkları oku (Transfer Learning / Continual Learning için)
    base_weights = None
    if base_model_f and base_model_f.filename:
        try:
            import json
            import numpy as np
            raw_weights = json.loads(base_model_f.read().decode('utf-8'))
            base_weights = {k: np.array(v) for k, v in raw_weights.items()}
        except Exception as e:
            return jsonify({"ok": False, "error": f"model.json okunamadı: {e}"}), 400
    
    # Eğitim parametrelerini al
    generations = int(request.form.get("generations", 60))
    if generations > 500:
        generations = 500
    
    population_size = int(request.form.get("population_size", 30))
    if population_size > 100:
        population_size = 100
    if population_size % 2 != 0:
        population_size += 1
    
    games_per_eval = int(request.form.get("games_per_eval", 3))
    sigma = float(request.form.get("sigma", 0.05))
    learning_rate = float(request.form.get("learning_rate", 0.03))
    
    time_limit_raw = float(request.form.get("time_limit", 0))
    time_limit = time_limit_raw if time_limit_raw > 0 else None
    
    max_steps = int(request.form.get("max_steps", 500))
    
    # Meyve ödüllerini al (formdan veya arena ayarlarından)
    with STATE_LOCK:
        fruit_rewards = copy.deepcopy(STATE["fruit_rewards"])
    
    # Form'dan gelen meyve ayarlarını kontrol et
    for fid in [6, 7, 8]:
        fid_str = str(fid)
        len_key = f"f{fid}_len"
        egy_key = f"f{fid}_egy"
        if len_key in request.form and egy_key in request.form:
            try:
                fruit_rewards[fid]["len"] = int(request.form[len_key])
                fruit_rewards[fid]["egy"] = int(request.form[egy_key])
            except (ValueError, KeyError):
                pass
    
    # Her rakip ajanı yükle
    import tempfile as _tempfile
    tmp_dir_obj = _tempfile.mkdtemp()
    tmp_dir = Path(tmp_dir_obj)
    
    opponents = []
    
    for i, opp_f in enumerate(opponents_files):
        if not opp_f or opp_f.filename == "":
            continue
            
        opp_dir = tmp_dir / f"rakip_{i}"
        opp_dir.mkdir()
        opp_f.save(opp_dir / opp_f.filename)
        try:
            ag = load_agent_from_dir(opp_dir)
            ag.name = opp_f.filename.replace(".py", "")
            opponents.append(ag)
        except Exception as e:
            shutil.rmtree(tmp_dir, ignore_errors=True)
            return jsonify({"ok": False, "error": f"{opp_f.filename} yüklenemedi: {e}"})
            
    if not opponents:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        return jsonify({"ok": False, "error": "Geçerli bir rakip yüklenemedi."}), 400
    
    # Eğitim durumunu sıfırla
    with TRAIN_LOCK:
        TRAIN_STATE["running"] = True
        TRAIN_STATE["logs"] = []
        TRAIN_STATE["progress"] = 0
        TRAIN_STATE["best_fitness"] = 0
        TRAIN_STATE["best_weights"] = None
        TRAIN_STATE["done"] = False
        TRAIN_STATE["error"] = None
    
    # Arka planda eğitimi başlat
    threading.Thread(
        target=_train_worker,
        args=(opponents, fruit_rewards, time_limit, max_steps,
              generations, population_size, games_per_eval, sigma, learning_rate, base_weights),
        daemon=True
    ).start()
    
    return jsonify({
        "ok": True,
        "message": "Eğitim başlatıldı! İlerlemeyi takip edebilirsiniz."
    })


@app.route("/api/train/status")
def train_status():
    """Eğitim durumunu döndürür (polling ile takip)."""
    with TRAIN_LOCK:
        return jsonify({
            "running": TRAIN_STATE["running"],
            "logs": TRAIN_STATE["logs"][-50:],  # Son 50 log
            "all_logs_count": len(TRAIN_STATE["logs"]),
            "done": TRAIN_STATE["done"],
            "error": TRAIN_STATE["error"],
            "best_fitness": TRAIN_STATE["best_fitness"],
            "has_weights": TRAIN_STATE["best_weights"] is not None,
        })


@app.route("/api/train/download")
def train_download():
    """Eğitilmiş model ağırlıklarını JSON olarak indir."""
    with TRAIN_LOCK:
        if TRAIN_STATE["best_weights"] is None:
            return jsonify({"ok": False, "error": "Henüz eğitilmiş model yok!"}), 400
        weights = TRAIN_STATE["best_weights"]
    
    response = app.response_class(
        response=json.dumps(weights),
        status=200,
        mimetype='application/json'
    )
    response.headers["Content-Disposition"] = "attachment; filename=model.json"
    return response

@app.route("/api/upload", methods=["POST"])
def upload():
    if "agent_file" not in request.files:
        return jsonify({"ok": False, "error": "agent_file (.py) yüklemek zorunludur"}), 400
    
    af = request.files["agent_file"]
    mf = request.files.get("model_file", None)
    
    if not af.filename.endswith(".py"):
        return jsonify({"ok": False, "error": "agent_file .py uzantılı olmalı"}), 400

    name = Path(af.filename).stem.strip()
    safe = safe_name(name)
    if not safe:
        return jsonify({"ok": False, "error": "Geçerli bir dosya ismi gir"}), 400

    pdir = UPLOADS / safe
    if pdir.exists():
        shutil.rmtree(pdir)
    pdir.mkdir(parents=True)

    af.save(str(pdir / f"{safe}.py"))
    
    # Model dosyası varsa kaydet
    if mf and mf.filename:
        mf.save(str(pdir / mf.filename))

    try:
        validate_agent_dir(pdir)
    except Exception as e:
        shutil.rmtree(pdir, ignore_errors=True)
        return jsonify({"ok": False, "error": f"Ajan doğrulanamadı. (Not: Model (.json) gerektiren bir ajan yüklüyorsanız model dosyasını da seçmelisiniz): {e}"}), 400

    mb = player_params_size_mb(safe)
    with STATE_LOCK:
        limit = STATE["mb_limit"]
    return jsonify({"ok": True, "name": safe, "params_mb": round(mb, 3),
                    "oversized": mb > limit})


@app.route("/api/upload_zip", methods=["POST"])
def upload_zip():
    """
    Toplu yükleme:
      - agents_zip: içinde .py dosyaları (isim = oyuncu adı)
      - models_zip: içinde model dosyaları (dosya ismi .py'lerle eşleşmeli)
    Sadece biri de verilebilir (önce .py'leri yükleyip sonra modelleri yollamak için).
    Eşleşme kuralı:
      - agents_zip içinde 'ahmet.py' -> oyuncu 'ahmet'
      - models_zip içinde 'ahmet.pt' veya 'ahmet/weights.bin' -> 'ahmet' oyuncusuna gider
      - Klasör varsa klasör adı oyuncu adıdır; yoksa dosya stem'i.
    """
    agents_zip = request.files.get("agents_zip")
    models_zip = request.files.get("models_zip")
    if not agents_zip and not models_zip:
        return jsonify({"ok": False, "error": "En az bir zip gerekli"}), 400

    report = {"added": [], "updated": [], "errors": [], "model_matched": [], "model_orphan": []}

    # ---- agents_zip ----
    if agents_zip:
        with tempfile.TemporaryDirectory() as tmpd:
            zpath = Path(tmpd) / "a.zip"
            agents_zip.save(str(zpath))
            try:
                z = zipfile.ZipFile(zpath)
            except zipfile.BadZipFile:
                return jsonify({"ok": False, "error": "agents_zip geçerli bir zip değil"}), 400
            with z:
                py_files = [n for n in z.namelist()
                            if n.endswith(".py") and not n.startswith("__MACOSX")
                            and not Path(n).name.startswith(".")]
                if not py_files:
                    return jsonify({"ok": False, "error": "agents_zip içinde .py yok"}), 400
                for entry in py_files:
                    fname = Path(entry).name
                    raw_name = Path(fname).stem
                    safe = safe_name(raw_name)
                    if not safe:
                        report["errors"].append({"name": raw_name, "error": "Geçersiz isim"})
                        continue

                    pdir = UPLOADS / safe
                    existed = pdir.exists()
                    # Eski katılımı tamamen sil (model dahil — kullanıcı isterse modeli tekrar yükler)
                    if existed:
                        shutil.rmtree(pdir)
                    pdir.mkdir(parents=True)

                    # .py'yi çıkar
                    data = z.read(entry)
                    (pdir / f"{safe}.py").write_bytes(data)

                    # Doğrulama: yalnızca .py var, model yok. Bu durumda "model yok" hatası
                    # verebilir. Validate'i esnek yapmak için try-except:
                    try:
                        validate_agent_dir(pdir)
                        if existed:
                            report["updated"].append(safe)
                        else:
                            report["added"].append(safe)
                    except Exception as e:
                        # Model dosyası olmayınca ajan yüklenemiyor olabilir — yine de kabul et,
                        # kullanıcı models_zip'i sonra yollar. Ama not düş.
                        report["errors"].append({
                            "name": safe,
                            "error": f"Uyarı: {e} (model yüklendiğinde tekrar denenecek)"
                        })
                        if existed:
                            report["updated"].append(safe)
                        else:
                            report["added"].append(safe)

    # ---- models_zip ----
    if models_zip:
        with tempfile.TemporaryDirectory() as tmpd:
            zpath = Path(tmpd) / "m.zip"
            models_zip.save(str(zpath))
            try:
                z = zipfile.ZipFile(zpath)
            except zipfile.BadZipFile:
                return jsonify({"ok": False, "error": "models_zip geçerli bir zip değil"}), 400
            with z:
                # Eşleşme için mevcut oyuncuları önceden al
                existing_players = set(list_players())
                for entry in z.namelist():
                    if entry.endswith("/") or entry.startswith("__MACOSX"):
                        continue
                    p = Path(entry)
                    if p.name.startswith("."):
                        continue

                    # Eşleşme stratejisi (sırayla):
                    # 1) Klasör ismi: 'ahmet/params.json' → 'ahmet'
                    # 2) Dosya stem'i tam eşleşme: 'ahmet.pt' → 'ahmet'
                    # 3) Dosya stem'i prefix eşleşmesi: 'ahmet_params.json' → 'ahmet'
                    #    (en uzun eşleşen oyuncu adı seçilir)
                    owner = None
                    if len(p.parts) >= 2 and safe_name(p.parts[0]) in existing_players:
                        owner = safe_name(p.parts[0])
                    else:
                        stem = safe_name(p.stem)
                        if stem in existing_players:
                            owner = stem
                        else:
                            # prefix match (en uzun)
                            candidates = [pl for pl in existing_players
                                          if stem.startswith(pl) or stem.startswith(pl + "_")]
                            if candidates:
                                owner = max(candidates, key=len)

                    if owner is None:
                        report["model_orphan"].append({"file": entry, "stem": p.stem})
                        continue

                    pdir = UPLOADS / owner
                    out_name = p.name
                    data = z.read(entry)
                    (pdir / out_name).write_bytes(data)
                    report["model_matched"].append({"owner": owner, "file": out_name})

                # Model eklenen oyuncuları yeniden doğrula
                rechecked = set(r["owner"] for r in report["model_matched"])
                for owner in rechecked:
                    pdir = UPLOADS / owner
                    try:
                        validate_agent_dir(pdir)
                    except Exception as e:
                        report["errors"].append({"name": owner, "error": f"Model sonrası doğrulama: {e}"})

    # Özet
    with STATE_LOCK:
        limit = STATE["mb_limit"]
    oversized_now = [n for n in list_players() if player_params_size_mb(n) > limit]
    report["oversized"] = oversized_now
    report["total_players"] = len(list_players())
    return jsonify({"ok": True, "report": report})


@app.route("/api/config", methods=["GET", "POST"])
def config():
    if request.method == "POST":
        body = request.get_json(silent=True) or {}
        with STATE_LOCK:
            if "speed_ms" in body:
                v = int(body["speed_ms"])
                STATE["speed_ms"] = max(1, min(300, v))
            if "max_steps" in body:
                v = int(body["max_steps"])
                STATE["max_steps"] = max(50, min(5000, v))
            if "mb_limit" in body:
                v = float(body["mb_limit"])
                STATE["mb_limit"] = max(0.1, min(500, v))
            if "win_points" in body:
                v = int(body["win_points"])
                STATE["win_points"] = max(0, min(1000, v))
            if "food_points" in body:
                v = int(body["food_points"])
                STATE["food_points"] = max(0, min(100, v))
            if "time_limit" in body:
                v = float(body["time_limit"])
                STATE["time_limit"] = max(0.01, min(5.0, v))
            for fid in [6, 7, 8]:
                if f"f{fid}_len" in body and f"f{fid}_egy" in body:
                    # Int dönüşümü yapalım string gelse bile
                    try:
                        STATE["fruit_rewards"][fid]["len"] = int(body[f"f{fid}_len"])
                        STATE["fruit_rewards"][fid]["egy"] = int(body[f"f{fid}_egy"])
                    except ValueError:
                        pass
    with STATE_LOCK:
        return jsonify({
            "ok": True,
            "speed_ms": STATE["speed_ms"],
            "max_steps": STATE["max_steps"],
            "mb_limit": STATE["mb_limit"],
            "win_points": STATE.get("win_points", 50),
            "food_points": STATE.get("food_points", 10),
            "time_limit": STATE.get("time_limit", 0.1),
            "fruit_rewards": STATE.get("fruit_rewards")
        })


@app.route("/api/players")
def api_players():
    return jsonify({"players": list_players()})


@app.route("/api/players_info")
def api_players_info():
    with STATE_LOCK:
        limit = STATE["mb_limit"]
    return jsonify({"players": player_info_list(), "mb_limit": limit})


@app.route("/api/delete/<n>", methods=["POST"])
def delete_player(n):
    safe = "".join(c for c in n if c.isalnum() or c in "_-")
    pdir = UPLOADS / safe
    if pdir.exists():
        shutil.rmtree(pdir)
    return jsonify({"ok": True})


import random

def generate_random_matches(players, per_player=3):
    matches = []
    # Very basic: each player plays 'per_player' matches approximately
    counts = {p: 0 for p in players}
    for p in players:
        opponents = [x for x in players if x != p]
        random.shuffle(opponents)
        for opp in opponents:
            if counts[p] >= per_player: break
            if counts[opp] >= per_player: continue
            if (p, opp) not in [(m[0], m[1]) for m in matches] and (opp, p) not in [(m[0], m[1]) for m in matches]:
                matches.append([p, opp])
                counts[p] += 1
                counts[opp] += 1
    return matches

@app.route("/api/start", methods=["POST"])
def start_league():
    with STATE_LOCK:
        if STATE["phase"] == "running":
            return jsonify({"ok": False, "error": "Lig zaten devam ediyor"}), 400
            
        limit = STATE["mb_limit"]
        valid_players = []
        for name in list_players():
            size = player_params_size_mb(name)
            pdir = UPLOADS / name
            has_params = any(f.is_file() and f.suffix.lower() != ".py" for f in pdir.iterdir())
            if size <= limit and has_params:
                valid_players.append(name)
        
        players = valid_players
        if len(players) < 2:
            return jsonify({"ok": False, "error": "En az 2 geçerli oyuncu gerekli."}), 400
        
        data = request.get_json(silent=True) or {}
        
        manual_matches = data.get("manual_matches")
        if manual_matches and isinstance(manual_matches, list):
            matches = manual_matches
        else:
            per_player = int(data.get("per_player", 3))
            matches = generate_random_matches(players, per_player)
            
        queue = []
        for i, pair in enumerate(matches):
            p1, p2 = pair[0], pair[1]
            if p1 not in players: p1 = players[0]
            if p2 not in players: p2 = players[1]
            queue.append({
                "id": i + 1,
                "p1": p1,
                "p2": p2,
                "played": False,
                "winner": None,
                "p1_length": None,
                "p2_length": None,
                "steps": None,
                "reason": None
            })
            
        STATE["match_queue"] = queue
        STATE["phase"] = "running"
        STATE["tournament_id"] += 1
        STATE["current_match"] = None
        STATE["live_game"] = None
        STATE["match_history"] = []
        
        # Log config settings
        print(f"\n=======================")
        print(f"🏆 TURNUVA BAŞLATILDI:")
        print(f"- Time Limit: {STATE.get('time_limit', 0.1)}s")
        print(f"- Max Steps: {STATE.get('max_steps', 2000)}")
        print(f"- MB Sınırı: {STATE.get('mb_limit', 20)} MB")
        print(f"=======================\n")

    threading.Thread(target=tournament_runner, daemon=True).start()
    return jsonify({"ok": True})


@app.route("/api/state")
def api_state():
    with STATE_LOCK:
        return jsonify({
            "phase": STATE["phase"],
            "rounds": STATE.get("rounds", []),  # 'rounds' olmayabilir o yüzden güvenli okuyoruz
            "current_match": STATE["current_match"],
            "live_game": STATE["live_game"],
            "tournament_id": STATE["tournament_id"],
            "speed_ms": STATE["speed_ms"],
            "max_steps": STATE["max_steps"],
            "mb_limit": STATE["mb_limit"],
            "time_limit": STATE.get("time_limit", 0.1),
            "fruit_rewards": STATE.get("fruit_rewards"),
            "win_points": STATE.get("win_points", 50),
            "food_points": STATE.get("food_points", 10),
            "match_history": STATE["match_history"][-30:],
        })


@app.route("/api/speed", methods=["POST"])
def set_speed():
    # Backward-compat: /api/config'e yönlendir
    ms = int(request.json.get("ms", 50))
    ms = max(1, min(300, ms))
    with STATE_LOCK:
        STATE["speed_ms"] = ms
    return jsonify({"ok": True, "ms": ms})


@app.route("/api/leaderboard")
def api_leaderboard():
    lb = load_leaderboard()
    rows = []
    for name, data in lb.items():
        played = data.get("played", 0)
        wins = data.get("wins", 0)
        draws = data.get("draws", 0)
        losses = data.get("losses", 0)
        total = data.get("total", 0)
        avg = round(total / played, 2) if played > 0 else 0
        rows.append({
            "name": name,
            "played": played,
            "wins": wins,
            "draws": draws,
            "losses": losses,
            "total": total,
            "avg": avg,
        })
    rows.sort(key=lambda r: (-r["total"], -r["avg"]))
    return jsonify({"leaderboard": rows})


@app.route("/api/reset", methods=["POST"])
def reset():
    with STATE_LOCK:
        STATE["phase"] = "idle"
        STATE["rounds"] = []
        STATE["current_match"] = None
        STATE["live_game"] = None
        STATE["match_history"] = []
    
    # Bütün kayıtlı oyuncuları (klasörleri) sil
    for item in UPLOADS.iterdir():
        if item.is_dir():
            shutil.rmtree(item)
        else:
            item.unlink()

    return jsonify({"ok": True})


@app.route("/api/reset_leaderboard", methods=["POST"])
def reset_leaderboard():
    if LEADERBOARD_FILE.exists():
        LEADERBOARD_FILE.unlink()
    return jsonify({"ok": True})


if __name__ == "__main__":
    print("=" * 50)
    print(" 🐍 Snake Arena çalışıyor: http://localhost:5001")
    print("=" * 50)
    app.run(host="0.0.0.0", port=5001, debug=False, threaded=True)
