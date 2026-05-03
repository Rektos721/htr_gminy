from __future__ import annotations

import argparse
import base64
import csv
import json
from io import BytesIO
from pathlib import Path

from PIL import Image


HTML_TEMPLATE = """<!doctype html>
<html lang="pl">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>HTR Review</title>
  <style>
    :root {
      --bg: #f4f0e6;
      --panel: #fffdf8;
      --line: #d8cfbd;
      --text: #1f1b16;
      --muted: #726a5d;
      --accent: #1358db;
      --ready: #2e7d32;
      --todo: #9a4b14;
      --focus: #d7263d;
    }
    * { box-sizing: border-box; }
    body { margin: 0; font-family: Georgia, serif; color: var(--text); background: var(--bg); }
    .app { display: grid; grid-template-columns: 260px 1fr; min-height: 100vh; }
    .sidebar {
      background: rgba(255,253,248,0.97);
      border-right: 1px solid var(--line);
      padding: 12px;
      overflow-y: auto;
      display: flex; flex-direction: column; gap: 8px;
    }
    .main { padding: 12px; display: flex; flex-direction: column; gap: 8px; min-width: 0; }
    h1 { margin: 0; font-size: 18px; }
    .hint { color: var(--muted); font-size: 12px; line-height: 1.4; }
    .panel { background: var(--panel); border: 1px solid var(--line); border-radius: 12px; box-shadow: 0 4px 14px rgba(0,0,0,0.04); }
    .toolbar { padding: 8px 12px; display: flex; gap: 6px; align-items: center; flex-wrap: wrap; }
    .viewer { display: grid; grid-template-columns: minmax(0,1fr) 320px; gap: 8px; flex: 1; min-height: 0; }
    .page-panel { display: flex; flex-direction: column; gap: 8px; min-height: 0; min-width: 0; overflow: hidden; }
    .page-panel > .panel { padding: 10px; display: flex; flex-direction: column; gap: 6px; flex: 1; min-height: 0; min-width: 0; }
    .page-viewport {
      overflow: auto; background: #fff;
      border: 1px solid var(--line); border-radius: 8px;
      flex: 1; min-height: 200px;
    }
    .page-stage { position: relative; }
    .page-stage img { display: block; }
    .focus-box {
      position: absolute;
      border: 3px solid var(--focus);
      background: rgba(215,38,61,0.10);
      box-shadow: 0 0 0 9999px rgba(0,0,0,0.18);
      pointer-events: none;
    }
    .right-panel { display: flex; flex-direction: column; gap: 8px; }
    .cell-thumb { padding: 8px; display: flex; flex-direction: column; gap: 4px; }
    .cell-thumb img { max-width: 100%; border-radius: 4px; background: #fff; }
    .edit-box { padding: 10px; display: flex; flex-direction: column; gap: 6px; flex: 1; }
    .guess-box { font-size: 13px; color: var(--muted); background: #f5f0e6; border-radius: 6px; padding: 6px 10px; display: none; }
    textarea {
      flex: 1; width: 100%; border: 1px solid var(--line); border-radius: 8px;
      padding: 10px; background: #fff; color: var(--text);
      font: inherit; font-size: 18px; resize: none; line-height: 1.5; min-height: 100px;
    }
    button {
      border: 0; border-radius: 8px; padding: 8px 12px; cursor: pointer;
      background: #e7dece; color: var(--text); font: inherit; font-size: 14px; white-space: nowrap;
    }
    button.primary { background: var(--accent); color: #fff; font-weight: bold; }
    button.danger { background: #c0392b; color: #fff; }
    .sep { width: 1px; height: 20px; background: var(--line); margin: 0 2px; }
    .counter { margin-left: auto; color: var(--muted); font-size: 13px; }
    .badge { display: inline-block; padding: 2px 8px; border-radius: 999px; background: #fff3cd; color: #8a5a00; font-size: 12px; }
    .label { font-size: 11px; text-transform: uppercase; letter-spacing: 0.07em; color: var(--muted); }
    .loc { font-size: 13px; color: var(--muted); }
    input, select { font: inherit; width: 100%; border: 1px solid var(--line); border-radius: 8px; padding: 6px 10px; background: #fff; }
    .list { display: flex; flex-direction: column; gap: 5px; flex: 1; overflow-y: auto; }
    .item { background: #fff; border: 1px solid var(--line); border-radius: 10px; padding: 8px 10px; cursor: pointer; font-size: 13px; }
    .item.active { border-color: var(--accent); box-shadow: inset 0 0 0 1px var(--accent); }
    .pill { display: inline-block; font-size: 11px; border-radius: 999px; padding: 1px 7px; background: #eee7d8; margin-top: 4px; }
    .todo, .unknown, .trash { color: var(--todo); }
    .ready, .done { color: var(--ready); }
    .zoom-row { display: flex; gap: 6px; align-items: center; }
    .zoom-row input[type=range] { flex: 1; max-width: 180px; }
    .zoom-label { font-size: 12px; color: var(--muted); min-width: 38px; }
  </style>
</head>
<body>
<div class="app">
  <aside class="sidebar">
    <h1>HTR Review</h1>
    <div class="hint">Enter&#8594;ready+dalej &nbsp; Alt+A&#8594;accept guess &nbsp; Ctrl+S&#8594;zapisz</div>
    <div>
      <div class="label">Filtr</div>
      <select id="filterStatus">
        <option value="">Wszystkie</option>
        <option value="todo">todo</option>
        <option value="ready">ready</option>
        <option value="unknown">unknown</option>
        <option value="trash">trash</option>
      </select>
    </div>
    <div>
      <div class="label">Szukaj</div>
      <input id="searchBox" placeholder="notatka lub plik">
    </div>
    <button id="exportBtn" class="primary">Eksportuj JSON</button>
    <button id="resetBtn">Reset zmian</button>
    <div class="list" id="list"></div>
  </aside>

  <main class="main">
    <div class="panel toolbar">
      <button id="prevBtn">&#8592; Poprzedni</button>
      <button id="nextBtn">Nastepny &#8594;</button>
      <div class="sep"></div>
      <button id="acceptGuessBtn" class="primary">&#10003; Accept guess</button>
      <button id="unknownBtn">? Nie wiem</button>
      <button id="trashBtn" class="danger">&#10005; Smiec</button>
      <span class="counter" id="counter">0 / 0</span>
      <span class="badge" id="uncertainBadge" style="display:none">? niepewne</span>
    </div>

    <div class="viewer">
      <div class="page-panel">
        <div class="panel">
          <div class="loc" id="cellLoc"></div>
          <div class="zoom-row">
            <button id="zoomOutBtn" type="button">&#8722;</button>
            <button id="zoomResetBtn" type="button">fit</button>
            <button id="zoomInBtn" type="button">+</button>
            <input id="zoomRange" type="range" min="10" max="150" step="5" value="40">
            <span class="zoom-label" id="zoomLabel">40%</span>
          </div>
          <div class="page-viewport" id="pageViewport">
            <div class="page-stage" id="pageStage">
              <img id="pageImage" alt="strona">
              <div class="focus-box" id="focusBox"></div>
            </div>
          </div>
        </div>
      </div>

      <div class="right-panel">
        <div class="panel cell-thumb">
          <div class="label">Wycięta komórka</div>
          <img id="cellThumb" alt="komorka">
        </div>
        <div class="panel edit-box" style="flex:1;display:flex;flex-direction:column;">
          <div class="label">Transkrypcja</div>
          <div class="guess-box" id="guessBox"></div>
          <textarea id="textArea" spellcheck="false"></textarea>
        </div>
      </div>
    </div>
  </main>
</div>
<script>
  const STORAGE_KEY = "__STORAGE_KEY__";
  const pageAssets = __PAGES__;
  const initialItems = __DATA__;
  let items = loadItems();
  let filtered = [];
  let currentIndex = -1;
  let zoomPercent = 40;

  function loadItems() {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return initialItems;
    try {
      const saved = JSON.parse(raw);
      return initialItems.map(item => {
        const override = saved.find(x => x.id === item.id);
        return override ? {...item, ...override} : item;
      });
    } catch { return initialItems; }
  }

  function persist() { localStorage.setItem(STORAGE_KEY, JSON.stringify(items)); }

  function applyFilter() {
    const status = document.getElementById("filterStatus").value.toLowerCase();
    const query = document.getElementById("searchBox").value.toLowerCase();
    filtered = items.filter(item => {
      const okS = !status || item.status.toLowerCase() === status;
      const hay = [item.page_name, item.notes, item.text, item.image_name].join(" ").toLowerCase();
      return okS && (!query || hay.includes(query));
    });
    renderList();
    if (!filtered.length) { currentIndex = -1; return; }
    const curId = getCurrent()?.id;
    const next = filtered.findIndex(x => x.id === curId);
    openItem(next >= 0 ? next : 0);
  }

  function renderList() {
    const list = document.getElementById("list");
    list.innerHTML = "";
    filtered.forEach((item, idx) => {
      const div = document.createElement("div");
      div.className = "item" + (idx === currentIndex ? " active" : "");
      div.onclick = () => openItem(idx);
      div.innerHTML =
        `<strong>${escapeHtml(item.notes || item.image_name)}</strong>` +
        `<div style="color:var(--muted);font-size:11px">${escapeHtml(item.page_name)}</div>` +
        `<div class="pill ${escapeHtml(item.status)}">${escapeHtml(item.status)}</div>`;
      list.appendChild(div);
    });
  }

  function getCurrent() {
    return (currentIndex >= 0 && currentIndex < filtered.length) ? filtered[currentIndex] : null;
  }

  function isUncertain(text) { return (text.match(/\\?/g) || []).length > 1; }

  function syncBack(item) {
    const idx = items.findIndex(x => x.id === item.id);
    if (idx >= 0) items[idx] = item;
  }

  function applyZoom() {
    document.getElementById("zoomRange").value = String(zoomPercent);
    document.getElementById("zoomLabel").textContent = zoomPercent + "%";
    const item = getCurrent();
    if (item) applyZoomToPage(item);
  }

  function applyZoomToPage(item) {
    const page = pageAssets[item.page_key];
    const scale = zoomPercent / 100;
    const dw = Math.round(page.width  * scale);
    const dh = Math.round(page.height * scale);
    const img   = document.getElementById("pageImage");
    const stage = document.getElementById("pageStage");
    const box   = document.getElementById("focusBox");
    img.style.width  = dw + "px";
    img.style.height = dh + "px";
    stage.style.width  = dw + "px";
    stage.style.height = dh + "px";
    box.style.left   = Math.round(item.box.left                      * scale) + "px";
    box.style.top    = Math.round(item.box.top                       * scale) + "px";
    box.style.width  = Math.round((item.box.right  - item.box.left)  * scale) + "px";
    box.style.height = Math.round((item.box.bottom - item.box.top)   * scale) + "px";
  }

  function setZoom(z) {
    zoomPercent = Math.max(10, Math.min(150, z));
    applyZoom();
    centerOnFocus();
  }

  function fitZoom() {
    const item = getCurrent();
    if (!item) return;
    const vp = document.getElementById("pageViewport");
    const page = pageAssets[item.page_key];
    const zx = (vp.clientWidth  - 4) / page.width  * 100;
    const zy = (vp.clientHeight - 4) / page.height * 100;
    setZoom(Math.floor(Math.min(zx, zy)));
  }

  function centerOnFocus() {
    const item = getCurrent();
    if (!item) return;
    const vp = document.getElementById("pageViewport");
    const scale = zoomPercent / 100;
    const cx = ((item.box.left + item.box.right)  / 2) * scale;
    const cy = ((item.box.top  + item.box.bottom) / 2) * scale;
    vp.scrollLeft = Math.max(0, cx - vp.clientWidth  / 2);
    vp.scrollTop  = Math.max(0, cy - vp.clientHeight / 2);
  }

  function updatePageView(item) {
    const page = pageAssets[item.page_key];
    const img = document.getElementById("pageImage");
    img.src = page.data;
    applyZoomToPage(item);
    requestAnimationFrame(centerOnFocus);
  }

  function refreshUncertaintyUi() {
    const text = document.getElementById("textArea").value || "";
    const unc = isUncertain(text);
    document.getElementById("uncertainBadge").style.display = unc ? "inline-block" : "none";
    const ta = document.getElementById("textArea");
    ta.style.borderColor = unc ? "#d18b00" : "var(--line)";
    ta.style.boxShadow = unc ? "0 0 0 2px rgba(209,139,0,0.18)" : "none";
  }

  function openItem(index) {
    if (index < 0 || index >= filtered.length) return;
    currentIndex = index;
    renderList();
    const item = filtered[index];
    document.getElementById("cellLoc").textContent = (item.notes || "") + " | " + item.page_name;
    document.getElementById("counter").textContent = (index + 1) + " / " + filtered.length;
    document.getElementById("cellThumb").src = item.cell_data;
    document.getElementById("textArea").value = item.text || item.ocr_guess || "";
    const gb = document.getElementById("guessBox");
    if (item.ocr_guess) {
      gb.style.display = "block";
      gb.innerHTML = "<strong>OCR guess:</strong> " + escapeHtml(item.ocr_guess);
    } else {
      gb.style.display = "none";
    }
    updatePageView(item);
    refreshUncertaintyUi();
  }

  function saveLocal(forceStatus, reopen) {
    const item = getCurrent();
    if (!item) return;
    item.text = document.getElementById("textArea").value;
    if (forceStatus) item.status = forceStatus;
    syncBack(item);
    persist();
    applyFilter();
    if (reopen !== false) {
      const idx = filtered.findIndex(x => x.id === item.id);
      if (idx >= 0) openItem(idx);
    }
  }

  function acceptGuessAndAdvance() {
    const item = getCurrent();
    if (!item || !item.ocr_guess) return;
    document.getElementById("textArea").value = item.ocr_guess;
    refreshUncertaintyUi();
    markAndAdvance("ready");
  }

  function markAndAdvance(status) {
    const nextId = filtered[currentIndex + 1]?.id ?? null;
    saveLocal(status, false);
    if (nextId !== null) {
      const idx = filtered.findIndex(x => x.id === nextId);
      if (idx >= 0) { openItem(idx); return; }
    }
    if (filtered.length) openItem(Math.min(currentIndex, filtered.length - 1));
  }

  function exportJson() {
    const blob = new Blob([JSON.stringify(items.map(({cell_data, ...rest}) => rest), null, 2)], {type:"application/json"});
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a"); a.href = url; a.download = "htr-review-export.json"; a.click();
    URL.revokeObjectURL(url);
  }

  function escapeHtml(v) {
    return String(v ?? "").replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;").replaceAll('"',"&quot;").replaceAll("'","&#39;");
  }

  document.getElementById("filterStatus").addEventListener("change", applyFilter);
  document.getElementById("searchBox").addEventListener("input", applyFilter);
  document.getElementById("prevBtn").addEventListener("click", () => openItem(Math.max(0, currentIndex - 1)));
  document.getElementById("nextBtn").addEventListener("click", () => openItem(Math.min(filtered.length - 1, currentIndex + 1)));
  document.getElementById("acceptGuessBtn").addEventListener("click", acceptGuessAndAdvance);
  document.getElementById("unknownBtn").addEventListener("click", () => markAndAdvance("unknown"));
  document.getElementById("trashBtn").addEventListener("click", () => markAndAdvance("trash"));
  document.getElementById("exportBtn").addEventListener("click", exportJson);
  document.getElementById("resetBtn").addEventListener("click", () => {
    if (!confirm("Usunac lokalne zmiany?")) return;
    localStorage.removeItem(STORAGE_KEY); items = initialItems; applyFilter();
  });
  document.getElementById("zoomOutBtn").addEventListener("click", () => setZoom(zoomPercent - 5));
  document.getElementById("zoomInBtn").addEventListener("click", () => setZoom(zoomPercent + 5));
  document.getElementById("zoomResetBtn").addEventListener("click", fitZoom);
  document.getElementById("zoomRange").addEventListener("input", e => setZoom(Number(e.target.value)));
  document.addEventListener("keydown", e => {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "s") { e.preventDefault(); saveLocal(null, true); }
    if (e.altKey && e.key.toLowerCase() === "a") { e.preventDefault(); acceptGuessAndAdvance(); }
  });
  document.getElementById("textArea").addEventListener("input", refreshUncertaintyUi);
  document.getElementById("textArea").addEventListener("keydown", e => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      saveLocal("ready", false);
      openItem(Math.min(filtered.length - 1, currentIndex + 1));
    }
  });

  applyFilter();
</script>
</body>
</html>
"""


def image_to_data_uri(path: Path, max_width: int = 0) -> str:
    mime = "image/png"
    if path.suffix.lower() in {".jpg", ".jpeg"}:
        mime = "image/jpeg"
    if max_width > 0:
        img = Image.open(path)
        if img.width > max_width:
            ratio = max_width / img.width
            img = img.resize((max_width, int(img.height * ratio)), Image.LANCZOS)
            buf = BytesIO()
            img.save(buf, format="JPEG", quality=72)
            data = base64.b64encode(buf.getvalue()).decode("ascii")
            return f"data:image/jpeg;base64,{data}"
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{data}"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Builds a standalone offline HTML review tool.")
    parser.add_argument("--review-manifest", required=True, type=Path)
    parser.add_argument("--output-html", required=True, type=Path)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    manifest_path = args.review_manifest.resolve()
    output_html = args.output_html.resolve()
    storage_key = f"htr-review-{manifest_path.stem}"

    pages: dict[str, dict] = {}
    items = []

    with manifest_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for idx, row in enumerate(reader):
            image_path = Path(row["image"])
            text_path = Path(row["manual_text_path"])
            text = text_path.read_text(encoding="utf-8", errors="ignore") if text_path.exists() else ""

            source_path = Path(row.get("source") or row["image"])
            page_key = str(source_path)
            if page_key not in pages:
                with Image.open(source_path) as pi:
                    width, height = pi.size
                pages[page_key] = {
                    "name": source_path.name,
                    "width": width,
                    "height": height,
                    "data": image_to_data_uri(source_path),
                }

            # współrzędne w przestrzeni source JPG — bez skalowania
            w = pages[page_key]["width"]
            h = pages[page_key]["height"]
            left   = int(float(row.get("left",   0) or 0))
            top    = int(float(row.get("top",     0) or 0))
            right  = int(float(row.get("right",   w) or w))
            bottom = int(float(row.get("bottom",  h) or h))

            cell_data = image_to_data_uri(image_path) if image_path.exists() else ""

            items.append({
                "id": idx,
                "image_name": image_path.name,
                "manual_text_path": str(text_path),
                "page_key": page_key,
                "page_name": pages[page_key]["name"],
                "status": (row.get("status") or "todo").strip() or "todo",
                "notes": (row.get("notes") or "").strip(),
                "text": text,
                "ocr_guess": (row.get("ocr_guess") or "").strip(),
                "cell_data": cell_data,
                "box": {"left": left, "top": top, "right": right, "bottom": bottom},
            })

    html = HTML_TEMPLATE.replace("__PAGES__", json.dumps(pages, ensure_ascii=False))
    html = html.replace("__DATA__", json.dumps(items, ensure_ascii=False))
    html = html.replace("__STORAGE_KEY__", storage_key)
    output_html.parent.mkdir(parents=True, exist_ok=True)
    output_html.write_text(html, encoding="utf-8")
    print(output_html)


if __name__ == "__main__":
    main()
