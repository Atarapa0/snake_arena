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
import zipfile
import tempfile
import threading
import importlib.util
import inspect
from pathlib import Path

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
        "6": {"len": 1, "egy": 20, "name": "Kırmızı Elma"},
        "7": {"len": 3, "egy": 50, "name": "Altın Elma"},
        "8": {"len": -2, "egy": 100, "name": "Zehirli Meyve"}
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
            if STATE["live_game"] is not None:
                for s in STATE["live_game"].snakes:
                    if not s.alive:
                        reason += f"{s.name}: {s.death_reason} "
            
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


@app.route("/api/train", methods=["POST"])
def train():
    """
    Sadece Local sunucuda çalışan Genetik Eğitim simülasyonu.
    İki ajanın yüklenmesi ZORUNLUDUR. Kendileriyle kapıştırarak en iyi parametreleri bulur.
    """
    if "agent1_file" not in request.files or "agent2_file" not in request.files:
        return jsonify({"ok": False, "error": "Eğitim için her iki ajanın da (.py) yüklenmesi zorunludur!"}), 400
        
    a1_f = request.files["agent1_file"]
    a2_f = request.files["agent2_file"]
    
    if not a2_f or a2_f.filename == "":
        return jsonify({"ok": False, "error": "2. Rakip ajan dosyası eksik!"}), 400
    
    episodes = int(request.form.get("episodes", 50))
    if episodes > 500: episodes = 500 # Local server çok donmasın diye limit
    
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        
        # Ajan 1'i kaydet ve yükle
        a1_path = tmp_dir / "agent1"
        a1_path.mkdir()
        a1_f.save(a1_path / "agent.py")
        try:
            ag1 = load_agent_from_dir(a1_path)
            ag1.name = "Egitilen_Ajan"
        except Exception as e:
            return jsonify({"ok": False, "error": f"Ana Ajan yüklenemedi: {e}"})

        a2_path = tmp_dir / "agent2"
        a2_path.mkdir()
        a2_f.save(a2_path / "rakip.py")
        try:
            ag2 = load_agent_from_dir(a2_path)
            ag2.name = "Rakip_Ajan"
        except Exception as e:
            return jsonify({"ok": False, "error": f"Rakip Ajan yüklenemedi: {e}"})
            
        # Basit Genetik Evrim Simülasyonu (Ajan1'in parametrelerini geliştireceğiz)
        # Amacımız Ajan 1'e json okutarak en iyi meyveyi bulma veya rastgelelik oranını öğretmek.
        # Not: Gerçek RL olmadığı için .py kodunun yapısını değiştiremeyiz, 
        # sadece dışarıdan bir Puan (Fitness) sistemi ile en iyi JSON ayarını bulup öğrenciye veririz.
        
        episodes = int(request.form.get("episodes", 50))
        time_limit_raw = float(request.form.get("time_limit", 0))
        # Eğer time_limit 0 gelirse kısıtlama yok demektir (None veya çok yüksek bir sayı)
        time_limit = time_limit_raw if time_limit_raw > 0 else None
        
        best_fitness = -9999
        best_params = {"tercih_edilen_meyve": 6, "rastgelelik_orani": 1.0}
        logs = []
        
        logs.append(f"Harika! Kendi yüklediğiniz 2. Güçlü modele karşı 'Kıyasıya (Self-Play)' eğitim başladı.")
        logs.append(f"Zaman Limiti: {time_limit} saniye.")

        logs.append(f"Genetik Algoritma Başlıyor. Jenerasyon: {episodes}")
        
        # Her Episode'da ajanımıza yeni "Genetik Mutasyon" (JSON parametresi) uygulayıp hayatta kalma süresine bakacağız
        import random
        for ep in range(episodes):
            test_fruit = random.choice([6, 7, 8]) # Kırmızı, Altın veya Zehirli yemeyi denesin
            test_random = random.uniform(0.0, 0.5)
            
            # Öğrencinin ajanı JSON okuyacak şekilde yazıldıysa diye bu test_param ı ona vereceğiz
            # (Lokal testlerde doğrudan ajanın içine inject edebiliriz)
            if hasattr(ag1, "hedef_meyve"): ag1.hedef_meyve = test_fruit
            
            # Simüle et
            game = game_engine.SnakeGame(ag1, ag2, max_steps=500, time_limit=time_limit, fruit_rewards=STATE["fruit_rewards"])
            while not game.is_over():
                game.step()
                
            fitness = (game.snakes[0].length * 10) + game.snakes[0].energy + (game.step_count)
            # Eğer Dummy robota oynuyorsa cezalandır, puanını suni olarak düşür (kalitesiz öğrensin)
            if is_dummy:
                fitness -= 100 
                
            if fitness > best_fitness:
                best_fitness = fitness
                best_params = {"tercih_edilen_meyve": test_fruit, "rastgelelik_orani": round(test_random, 3)}
                if ep % (episodes // 5 + 1) == 0 or ep == episodes - 1:
                    logs.append(f"-> Tur {ep+1}: Yeni en iyi gen bulundu! Skor: {fitness}")

        logs.append("---------")
        logs.append(f"Eğitim Bitti. En iyi Fitness Skoru: {best_fitness}")
        logs.append(f"Evrimleşen Parametre: {best_params}")
        
        return jsonify({
            "ok": True,
            "log": logs,
            "best_params": best_params
        })
def upload():
    if "agent_file" not in request.files:
        return jsonify({"ok": False, "error": "agent_file (.py) yüklemek zorunludur"}), 400
    
    af = request.files["agent_file"]
    mf = request.files.get("model_file") # Artık opsiyonel (get ile alıyoruz)
    
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
            for fid in ["6", "7", "8"]:
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

    threading.Thread(target=tournament_runner, daemon=True).start()
    return jsonify({"ok": True})


@app.route("/api/state")
def api_state():
    with STATE_LOCK:
        return jsonify({
            "phase": STATE["phase"],
            "rounds": STATE["rounds"],
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
        last = data["history"][-1] if data["history"] else None
        rows.append({
            "name": name,
            "total": data["total"],
            "last_rank": last["rank"] if last else None,
            "last_tournament": last["tournament"] if last else None,
            "attempts": len(data["history"]),
        })
    rows.sort(key=lambda r: -r["total"])
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
