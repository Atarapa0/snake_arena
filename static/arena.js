// SNAKE ARENA - frontend
const GRID = 30;
const CELL = 660 / GRID;

const canvas = document.getElementById("arena");
const ctx = canvas.getContext("2d");

const COLORS = {
  bg:      "#0a0c12",
  grid:    "#161922",
  food:    "#ef4444",
  s0_body: "#16a34a",
  s0_head: "#4ade80",
  s1_body: "#3b82f6",
  s1_head: "#60a5fa",
  dead:    "#475569",
};

function drawGrid(state) {
  ctx.fillStyle = COLORS.bg;
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.strokeStyle = COLORS.grid;
  ctx.lineWidth = 1;
  for (let i = 0; i <= GRID; i++) {
    ctx.beginPath(); ctx.moveTo(i * CELL, 0); ctx.lineTo(i * CELL, canvas.height); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(0, i * CELL); ctx.lineTo(canvas.width, i * CELL); ctx.stroke();
  }
  if (!state || !state.snakes) return;

  // Duvarlar
  if (state.walls) {
    state.walls.forEach(([r, c]) => {
      ctx.fillStyle = "#374151";
      ctx.fillRect(c * CELL + 1, r * CELL + 1, CELL - 2, CELL - 2);
      // Duvar deseni
      ctx.strokeStyle = "#1f2937";
      ctx.lineWidth = 1;
      ctx.strokeRect(c * CELL + 3, r * CELL + 3, CELL - 6, CELL - 6);
    });
  }

  // Meyveler (çoklu)
  if (state.fruits) {
    const fruitColors = {
      6: { fill: "#ef4444", glow: "rgba(239,68,68,0.4)", emoji: "" },   // Kırmızı Elma
      7: { fill: "#fbbf24", glow: "rgba(251,191,36,0.4)", emoji: "" },   // Altın Elma
      8: { fill: "#a855f7", glow: "rgba(168,85,247,0.4)", emoji: "" },   // Zehirli Meyve
    };
    state.fruits.forEach(f => {
      const [r, c] = f.pos;
      const t = f.type;
      const color = fruitColors[t] || { fill: "#ef4444", glow: "rgba(239,68,68,0.3)" };
      
      // Glow efekti
      ctx.fillStyle = color.glow;
      ctx.beginPath();
      ctx.arc(c * CELL + CELL / 2, r * CELL + CELL / 2, CELL / 2 + 1, 0, Math.PI * 2);
      ctx.fill();
      
      // Ana meyve
      ctx.fillStyle = color.fill;
      ctx.beginPath();
      ctx.arc(c * CELL + CELL / 2, r * CELL + CELL / 2, CELL / 2 - 2, 0, Math.PI * 2);
      ctx.fill();
      
      // Zehirli meyve için X işareti
      if (t === 8) {
        ctx.strokeStyle = "#000";
        ctx.lineWidth = 2;
        const cx = c * CELL + CELL / 2, cy = r * CELL + CELL / 2, sz = 4;
        ctx.beginPath(); ctx.moveTo(cx - sz, cy - sz); ctx.lineTo(cx + sz, cy + sz); ctx.stroke();
        ctx.beginPath(); ctx.moveTo(cx + sz, cy - sz); ctx.lineTo(cx - sz, cy + sz); ctx.stroke();
      }
    });
  }
  
  // Eski format uyumluluğu (tek yem)
  if (state.food && !state.fruits) {
    const [r, c] = state.food;
    ctx.fillStyle = COLORS.food;
    ctx.beginPath();
    ctx.arc(c * CELL + CELL / 2, r * CELL + CELL / 2, CELL / 2 - 2, 0, Math.PI * 2);
    ctx.fill();
  }

  // Yılanlar
  state.snakes.forEach((s, idx) => {
    const body = s.alive ? COLORS[`s${idx}_body`] : COLORS.dead;
    const head = s.alive ? COLORS[`s${idx}_head`] : COLORS.dead;
    s.body.forEach((cell, i) => {
      const isHead = i === s.body.length - 1;
      ctx.fillStyle = isHead ? head : body;
      const [r, c] = cell;
      if (isHead) {
        // Kafa için yuvarlak köşeli kare
        const x = c * CELL + 1, y = r * CELL + 1, w = CELL - 2, h = CELL - 2, rad = 4;
        ctx.beginPath();
        ctx.moveTo(x + rad, y);
        ctx.lineTo(x + w - rad, y); ctx.quadraticCurveTo(x + w, y, x + w, y + rad);
        ctx.lineTo(x + w, y + h - rad); ctx.quadraticCurveTo(x + w, y + h, x + w - rad, y + h);
        ctx.lineTo(x + rad, y + h); ctx.quadraticCurveTo(x, y + h, x, y + h - rad);
        ctx.lineTo(x, y + rad); ctx.quadraticCurveTo(x, y, x + rad, y);
        ctx.closePath(); ctx.fill();
      } else {
        ctx.fillRect(c * CELL + 1, r * CELL + 1, CELL - 2, CELL - 2);
      }
    });
  });
}

function renderPlayersInfo(playersInfo, mbLimit) {
  document.getElementById("playerCount").textContent = playersInfo.length;
  const ul = document.getElementById("playerList");
  ul.innerHTML = "";
  if (playersInfo.length === 0) {
    ul.innerHTML = `<li style="color:#64748b;justify-content:center">— henüz yok —</li>`;
    return;
  }
  playersInfo.forEach(p => {
    const li = document.createElement("li");
    if (p.oversized) li.className = "oversized";
    const mbTxt = `${p.params_mb.toFixed(2)} MB`;
    const warn = p.oversized ? ` ⚠ >${mbLimit}` : "";
    const noParams = !p.has_params ? ` <span class="no-params">[model yok]</span>` : "";
    li.innerHTML =
      `<span>${p.name}<span class="mb-info">${mbTxt}${warn}</span>${noParams}</span>` +
      `<span style="color:${p.oversized ? '#f87171' : '#4ade80'};font-size:0.75rem">${p.oversized ? '✗' : '✓'}</span>`;
    ul.appendChild(li);
  });
}

function renderBracket(queue, currentMatch, history) {
  const div = document.getElementById("bracket");
  div.innerHTML = "";
  
  if (!queue && (!history || history.length === 0)) {
    div.innerHTML = `<div style="color:#64748b;font-size:0.8rem">Lig başlamadı veya maç yok</div>`;
    return;
  }
  
  let allMatches = [];
  if (history) allMatches = allMatches.concat(history);
  if (queue) allMatches = allMatches.concat(queue.filter(m => !m.played));
  
  allMatches.forEach((m, idx) => {
      const card = document.createElement("div");
      card.className = "match-card";
      card.style.flex = "0 0 auto";
      
      const isLive = currentMatch && currentMatch.id === m.id;
      if (isLive) card.classList.add("live");
      else if (m.played) card.classList.add("done");
      else card.style.opacity = "0.7";

      const fmt = (p, len) => {
        const winCls = m.played && m.winner === p ? "winner"
                      : (m.played && m.winner !== null) ? "loser" : "";
        const ll = (len !== null && len !== undefined) ? `<span>${len}</span>` : "<span>-</span>";
        return `<div class="player ${winCls}" style="justify-content:space-between"><span>${p}</span>${ll}</div>`;
      };
      
      let header = `<div style="font-size:0.7rem;color:#94a3b8;margin-bottom:4px">Maç #${m.id || idx+1} ${m.played ? '(Bitti)' : '(Bekliyor)'}</div>`;
      card.innerHTML = header + fmt(m.p1, m.p1_length) + fmt(m.p2, m.p2_length);
      
      if (m.reason) {
          card.innerHTML += `<div style="font-size:0.6rem;color:#ef4444;margin-top:4px">${m.reason}</div>`;
      }
      
      div.appendChild(card);
  });
}

function renderMatchInfo(state) {
  const info = document.getElementById("matchInfo");
  if (state.phase === "idle") { info.textContent = "Henüz turnuva başlamadı"; return; }
  if (state.phase === "done") { info.textContent = "🏆 Turnuva bitti!"; return; }
  if (state.current_match) {
    const m = state.current_match;
    info.innerHTML = `<b>${m.round_name}</b> — ${m.p1} <span style="color:#94a3b8">vs</span> ${m.p2}`;
  } else {
    info.textContent = "Sonraki maç hazırlanıyor...";
  }
}

function renderSnakeStats(game) {
  const div = document.getElementById("snakeStats");
  if (!game || !game.snakes || game.snakes.length === 0) { div.innerHTML = ""; return; }
  div.innerHTML = game.snakes.map((s, i) => {
    const cls = `s${i}` + (s.alive ? "" : " dead");
    const dr = s.death_reason ? ` (${s.death_reason})` : "";
    const act = (game.last_actions && game.last_actions[i])
      ? ` ${game.last_actions[i].applied}` : "";
    return `<span class="${cls}"><b>${s.name}</b> <span style="color:#fbbf24">En:${s.energy}</span> Boy:${s.length}${act}${dr}</span>`;
  }).join("") + `<span style="color:#94a3b8">${game.step}/${game.max_steps}</span>`;
}

function renderEvents(game) {
  const div = document.getElementById("events");
  if (!game || !game.events_tail) { div.innerHTML = ""; return; }
  div.innerHTML = game.events_tail.map((e, i) =>
    `<div class="${i === game.events_tail.length - 1 ? 'new' : ''}">[${e[0]}] ${e[1]}</div>`
  ).join("");
  div.scrollTop = div.scrollHeight;
}

function renderLeaderboard(rows) {
  const tbody = document.querySelector("#leaderboard tbody");
  tbody.innerHTML = "";
  if (!rows || rows.length === 0) {
    tbody.innerHTML = `<tr><td colspan="8" style="color:#94a3b8;text-align:center">Henüz veri yok</td></tr>`;
    return;
  }
  rows.forEach((r, i) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td>${i+1}</td><td>${r.name}</td>
                    <td>${r.played || 0}</td>
                    <td>${r.wins || 0}</td>
                    <td>${r.draws || 0}</td>
                    <td>${r.losses || 0}</td>
                    <td><b>${r.total || 0}</b></td>
                    <td>${r.avg || 0}</td>`;
    tbody.appendChild(tr);
  });
}

function renderHistory(hist) {
  const div = document.getElementById("history");
  if (!div) return;
  if (!hist || hist.length === 0) {
    div.innerHTML = `<div style="color:#94a3b8">Maç yok</div>`; return;
  }
  div.innerHTML = [...hist].reverse().map(m =>
    `<div>${m.round_name}: <span class="w">${m.winner}</span> def. ${m.winner === m.p1 ? m.p2 : m.p1}
     <span style="color:#64748b">(${m.p1_length}-${m.p2_length}, ${m.steps} adım)</span></div>`
  ).join("");
}

function setPhase(phase, tid) {
  const b = document.getElementById("phaseBadge");
  b.textContent = phase;
  b.className = "phase-badge " + phase;
  document.getElementById("tid").textContent = tid;
}

// ---- Polling ----
let configSyncedOnce = false;
let globalPlayersList = []; // store for modal
async function poll() {
  try {
    const [s, pi, lb] = await Promise.all([
      fetch("/api/state").then(r => r.json()),
      fetch("/api/players_info").then(r => r.json()),
      fetch("/api/leaderboard").then(r => r.json()),
    ]);
    globalPlayersList = pi.players.filter(p => !p.oversized).map(p => p.name);
    setPhase(s.phase, s.tournament_id);
    renderPlayersInfo(pi.players, pi.mb_limit);
    renderBracket(s.queue, s.current_match, s.match_history);
    renderMatchInfo(s);
    if (s.live_game) {
      drawGrid(s.live_game);
      renderSnakeStats(s.live_game);
      renderEvents(s.live_game);
    } else {
      drawGrid(null);
      renderSnakeStats(null);
      renderEvents(null);
    }
    renderLeaderboard(lb.leaderboard);
    renderHistory(s.match_history);

    // İlk açılışta config alanlarını server'dan al
    if (!configSyncedOnce) {
      document.getElementById("maxStepsInput").value = s.max_steps;
      document.getElementById("mbLimitInput").value = s.mb_limit;
      if (document.getElementById("foodPointsInput")) document.getElementById("foodPointsInput").value = s.food_points;
      if (document.getElementById("winPointsInput")) document.getElementById("winPointsInput").value = s.win_points;
      document.getElementById("speedSlider").value = s.speed_ms;
      document.getElementById("speedVal").textContent = s.speed_ms;
      if (s.time_limit) document.getElementById("timeLimitInput").value = s.time_limit;
      if (s.fruit_rewards) {
        ["6", "7", "8"].forEach(id => {
            if (s.fruit_rewards[id]) {
                document.getElementById(`f${id}_len`).value = s.fruit_rewards[id].len;
                document.getElementById(`f${id}_egy`).value = s.fruit_rewards[id].egy;
            }
        });
      }
      configSyncedOnce = true;
    }
  } catch (e) {
    console.error("poll err", e);
  }
}

setInterval(poll, 200);
poll();

// ---- Form & buttons ----
document.getElementById("uploadForm").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const fd = new FormData(ev.target);
  const msg = document.getElementById("uploadMsg");
  msg.textContent = "Yükleniyor..."; msg.className = "";
  try {
    const r = await fetch("/api/upload", { method: "POST", body: fd });
    const j = await r.json();
    if (j.ok) {
      msg.textContent = `✓ ${j.name} yüklendi`; msg.className = "ok";
      ev.target.reset();
    } else {
      msg.textContent = "✗ " + j.error; msg.className = "err";
    }
  } catch (e) {
    msg.textContent = "✗ " + e; msg.className = "err";
  }
});

document.getElementById("startBtn").addEventListener("click", async () => {
  const perPlayer = document.getElementById("perPlayerInput").value;
  // Başlamadan önce ayarları beklemeden gönder (debounce iptal)
  if (configDebounce) { clearTimeout(configDebounce); }
  const t_lim = parseFloat(document.getElementById("timeLimitInput").value);
  await postConfig({ time_limit: isNaN(t_lim) ? 0.1 : t_lim });
  
  const r = await fetch("/api/start", { 
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ per_player: perPlayer })
  });
  const j = await r.json();
  if (!j.ok) alert(j.error);
});

let myCustomMatches = [];
document.getElementById("startManualBtn").addEventListener("click", () => {
  if (globalPlayersList.length < 2) return alert("En az 2 geçerli oyuncu lazım.");
  
  const p1Select = document.getElementById("p1Select");
  const p2Select = document.getElementById("p2Select");
  p1Select.innerHTML = ""; p2Select.innerHTML = "";
  
  globalPlayersList.forEach(p => {
      p1Select.innerHTML += `<option value="${p}">${p}</option>`;
      p2Select.innerHTML += `<option value="${p}">${p}</option>`;
  });
  p2Select.selectedIndex = Math.min(1, globalPlayersList.length - 1);
  
  myCustomMatches = [];
  renderCustomMatches();
  document.getElementById("manualBracketModal").showModal();
});

document.getElementById("addMatchBtn").addEventListener("click", () => {
   const p1 = document.getElementById("p1Select").value;
   const p2 = document.getElementById("p2Select").value;
   if (p1 === p2) return alert("Farklı oyuncular seçin.");
   myCustomMatches.push([p1, p2]);
   renderCustomMatches();
});

function renderCustomMatches() {
   const ul = document.getElementById("manualMatchList");
   ul.innerHTML = "";
   myCustomMatches.forEach((m, i) => {
       const li = document.createElement("li");
       li.style.cssText = "display:flex; justify-content:space-between; background:#1e293b; padding:0.5rem; border-radius:4px;";
       li.innerHTML = `<span>${m[0]} <span style="color:#94a3b8;margin:0 10px">vs</span> ${m[1]}</span>
                       <button class="secondary tiny" onclick="myCustomMatches.splice(${i},1); renderCustomMatches();" style="border:none;background:none;color:#ef4444;cursor:pointer">Sil</button>`;
       ul.appendChild(li);
   });
}

document.getElementById("cancelManualStartBtn").addEventListener("click", () => {
  document.getElementById("manualBracketModal").close();
});

document.getElementById("confirmManualStartBtn").addEventListener("click", async () => {
  if (myCustomMatches.length === 0) return alert("Lütfen en az 1 maç ekleyin.");
  if (configDebounce) { clearTimeout(configDebounce); }
  const t_lim = parseFloat(document.getElementById("timeLimitInput").value);
  await postConfig({ time_limit: isNaN(t_lim) ? 0.1 : t_lim });

  const r = await fetch("/api/start", { 
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ manual_matches: myCustomMatches })
  });
  const j = await r.json();
  if (j.ok) {
    document.getElementById("manualBracketModal").close();
  } else {
    alert(j.error);
  }
});

// Remove old manual things

// ---- Manual Bracket Modal ----
let manualList = [];
const manualModal = document.getElementById("manualBracketModal");

document.getElementById("startManualBtn").addEventListener("click", () => {
  if (globalPlayersList.length < 2) return alert("En az 2 oyuncu gerekli.");
  manualList = [...globalPlayersList];
  renderManualList();
  manualModal.showModal();
});

document.getElementById("cancelManualStartBtn").addEventListener("click", () => {
  manualModal.close();
});

function moveManualItem(index, dir) {
  if (index + dir < 0 || index + dir >= manualList.length) return;
  const temp = manualList[index];
  manualList[index] = manualList[index + dir];
  manualList[index + dir] = temp;
  renderManualList();
}

// Global for HTML onclick / drag
window.moveManualItem = moveManualItem;

let draggedIndex = null;
window.handleDragStart = (e, i) => {
  draggedIndex = i;
  e.dataTransfer.effectAllowed = "move";
  setTimeout(() => e.target.style.opacity = "0.5", 0);
};
window.handleDragOver = (e) => {
  e.preventDefault();
  e.dataTransfer.dropEffect = "move";
  return false;
};
window.handleDrop = (e, targetIndex) => {
  e.stopPropagation();
  if (draggedIndex !== null && draggedIndex !== targetIndex) {
    const item = manualList.splice(draggedIndex, 1)[0];
    manualList.splice(targetIndex, 0, item);
  }
};
window.handleDragEnd = (e) => {
  e.target.style.opacity = "1";
  draggedIndex = null;
  renderManualList();
};

window.handleMatchChange = (e, currentIndex) => {
  let matchNum = parseInt(e.target.value);
  const maxMatch = Math.ceil(manualList.length / 2);
  if (isNaN(matchNum) || matchNum < 1) matchNum = 1;
  if (matchNum > maxMatch) matchNum = maxMatch;
  
  let targetIndex = (matchNum - 1) * 2;
  if (targetIndex !== currentIndex && targetIndex !== currentIndex - 1) {
    const item = manualList.splice(currentIndex, 1)[0];
    if (targetIndex >= manualList.length) {
      manualList.push(item);
    } else {
      manualList.splice(targetIndex, 0, item);
    }
    renderManualList();
  }
};

function renderManualList() {
  const container = document.getElementById("sortablePlayers");
  if (!container) return;
  let html = "";
  
  for (let i = 0; i < manualList.length; i++) {
    const p = manualList[i];
    const isPairStart = (i % 2 === 0);
    
    if (isPairStart) {
      html += `<div style="border:1px solid #334155; padding:0.5rem; border-radius:6px; background:#0f172a; display:flex; flex-direction:column; gap:0.4rem; box-sizing:border-box;">`;
      html += `<div style="font-size:0.75rem; color:#94a3b8; text-transform:uppercase; letter-spacing:0.05em; font-weight:bold; margin-bottom:0.2rem;">⚔️ Eşleşme ${Math.floor(i/2) + 1}</div>`;
    }
    
    html += `
      <div draggable="true"
           ondragstart="handleDragStart(event, ${i})"
           ondragover="handleDragOver(event)"
           ondrop="handleDrop(event, ${i})"
           ondragend="handleDragEnd(event)"
           style="display:flex; justify-content:space-between; align-items:center; background:#1e293b; padding:0.3rem 0.5rem; border-radius:4px; cursor:grab; border-left:3px solid #6366f1; transition: background 0.2s; gap:0.5rem;">
        <span style="font-size:0.85rem; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; flex:1;"><b>${i + 1}.</b> ${p}</span>
        <input type="number" min="1" max="${Math.ceil(manualList.length/2)}" value="${Math.floor(i/2) + 1}"
               onchange="handleMatchChange(event, ${i})"
               style="width:2.5rem; padding:0.1rem; background:#0f172a; color:#fff; border:1px solid #475569; border-radius:3px; text-align:center; font-size:0.8rem;" title="Gitmek istediği eşleşme numarası">
        <span style="color:#64748b; font-size:1.1rem; cursor:grab; line-height:1; padding-left:0.2rem;">≡</span>
      </div>`;
      
    if (!isPairStart || i === manualList.length - 1) {
      html += `</div>`; // Close pair container
    }
  }
  container.innerHTML = html;
}

document.getElementById("confirmManualStartBtn").addEventListener("click", async () => {
  if (configDebounce) { clearTimeout(configDebounce); }
  const t_lim = parseFloat(document.getElementById("timeLimitInput").value);
  await postConfig({ time_limit: isNaN(t_lim) ? 0.1 : t_lim });

  const r = await fetch("/api/start", { 
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ players: manualList })
  });
  const j = await r.json();
  if (j.ok) {
    manualModal.close();
  } else {
    alert(j.error);
  }
});

document.getElementById("resetBtn").addEventListener("click", async () => {
  if (!confirm("Turnuvayı ve tüm kayıtlı oyuncuları tamamen sıfırlamak (SİLMEK) istediğinize emin misiniz? Bu işlem geri alınamaz!")) return;
  await fetch("/api/reset", { method: "POST" });
});

const resetBracketBtn = document.getElementById("resetBracketBtn");
if (resetBracketBtn) {
  resetBracketBtn.addEventListener("click", async (e) => {
    e.stopPropagation();
    if (!confirm("Fikstürü ve oynanan turnuvayı tamamen sıfırlamak istiyor musunuz?")) return;
    await fetch("/api/reset", { method: "POST" });
  });
}

document.getElementById("resetLbBtn").addEventListener("click", async (e) => {
  e.stopPropagation();
  if (!confirm("Tüm leaderboard puanları silinsin mi?")) return;
  await fetch("/api/reset_leaderboard", { method: "POST" });
});

const slider = document.getElementById("speedSlider");
const speedVal = document.getElementById("speedVal");
slider.addEventListener("input", async () => {
  speedVal.textContent = slider.value;
  await fetch("/api/config", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({speed_ms: parseInt(slider.value)})
  });
});

// ---- Config inputs: hamle sayısı & MB sınırı ----
async function postConfig(patch) {
  await fetch("/api/config", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(patch),
  });
}

const maxStepsInput = document.getElementById("maxStepsInput");
let configDebounce = null;

function handleConfigInput() {
  clearTimeout(configDebounce);
  configDebounce = setTimeout(() => {
    const patch = {};
    const max_s = parseInt(document.getElementById("maxStepsInput").value);
    if (!isNaN(max_s)) patch.max_steps = max_s;
    
    const mb_l = parseFloat(document.getElementById("mbLimitInput").value);
    if (!isNaN(mb_l)) patch.mb_limit = mb_l;
    
    const t_lim = parseFloat(document.getElementById("timeLimitInput").value);
    if (!isNaN(t_lim)) patch.time_limit = t_lim;
    
    for (let id of ["6", "7", "8"]) {
        const len = parseInt(document.getElementById(`f${id}_len`).value);
        const egy = parseInt(document.getElementById(`f${id}_egy`).value);
        if (!isNaN(len) && !isNaN(egy)) {
            patch[`f${id}_len`] = len;
            patch[`f${id}_egy`] = egy;
        }
    }
    
    postConfig(patch);
  }, 400);
}

document.getElementById("maxStepsInput").addEventListener("input", handleConfigInput);
document.getElementById("mbLimitInput").addEventListener("input", handleConfigInput);
document.getElementById("timeLimitInput").addEventListener("input", handleConfigInput);
["6", "7", "8"].forEach(id => {
    document.getElementById(`f${id}_len`).addEventListener("input", handleConfigInput);
    document.getElementById(`f${id}_egy`).addEventListener("input", handleConfigInput);
});

// Eski event listenerları eziyoruz, handleConfigInput hepsini toplu gönderiyor

const foodPointsInput = document.getElementById("foodPointsInput");
if (foodPointsInput) {
  let fpDebounce = null;
  foodPointsInput.addEventListener("input", () => {
    clearTimeout(fpDebounce);
    fpDebounce = setTimeout(() => {
      const v = parseInt(foodPointsInput.value);
      if (!isNaN(v)) postConfig({food_points: v});
    }, 400);
  });
}

const winPointsInput = document.getElementById("winPointsInput");
if (winPointsInput) {
  let wpDebounce = null;
  winPointsInput.addEventListener("input", () => {
    clearTimeout(wpDebounce);
    wpDebounce = setTimeout(() => {
      const v = parseInt(winPointsInput.value);
      if (!isNaN(v)) postConfig({win_points: v});
    }, 400);
  });
}

// ---- Zip upload ----
document.getElementById("zipForm").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const form = ev.target;
  const agentsFile = form.querySelector('input[name="agents_zip"]').files[0];
  const modelsFile = form.querySelector('input[name="models_zip"]').files[0];
  const msg = document.getElementById("zipMsg");
  if (!agentsFile && !modelsFile) {
    msg.textContent = "✗ En az bir zip seç"; msg.className = "err";
    return;
  }
  const fd = new FormData();
  if (agentsFile) fd.append("agents_zip", agentsFile);
  if (modelsFile) fd.append("models_zip", modelsFile);
  msg.textContent = "Yükleniyor..."; msg.className = "";
  try {
    const r = await fetch("/api/upload_zip", {method: "POST", body: fd});
    const j = await r.json();
    if (!j.ok) {
      msg.textContent = "✗ " + j.error; msg.className = "err";
      return;
    }
    const rep = j.report;
    const parts = [];
    if (rep.added.length) parts.push(`<b>Eklendi:</b> ${rep.added.join(", ")}`);
    if (rep.updated.length) parts.push(`<b>Güncellendi:</b> ${rep.updated.join(", ")}`);
    if (rep.model_matched.length) parts.push(`<b>Model eşleşti:</b> ${rep.model_matched.length} dosya`);
    if (rep.model_orphan.length) parts.push(`<b>Eşleşmeyen model:</b> ${rep.model_orphan.map(o => o.file).join(", ")}`);
    if (rep.oversized.length) parts.push(`<b style="color:#f87171">⚠ MB aşan:</b> ${rep.oversized.join(", ")}`);
    if (rep.errors.length) parts.push(`<b style="color:#fbbf24">Uyarılar:</b> ${rep.errors.map(e => `${e.name}: ${e.error}`).join(" | ")}`);
    msg.innerHTML = `<div class="zip-report">${parts.join("<br>") || "Hiçbir şey eklenmedi"}</div>`;
    msg.className = "ok";
    form.reset();
  } catch (e) {
    msg.textContent = "✗ " + e; msg.className = "err";
  }
});
