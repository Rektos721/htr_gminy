from __future__ import annotations

import argparse
import base64
import csv
import json
from pathlib import Path

from PIL import Image


HTML_TEMPLATE = """<!doctype html>
<html lang="pl">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>HTR Review Offline</title>
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
    body {
      margin: 0;
      font-family: Georgia, "Times New Roman", serif;
      color: var(--text);
      background:
        radial-gradient(circle at top left, #fff4cf 0, transparent 28%),
        radial-gradient(circle at bottom right, #e7efe8 0, transparent 30%),
        var(--bg);
    }
    .app {
      display: grid;
      grid-template-columns: 330px 1fr;
      min-height: 100vh;
    }
    .sidebar {
      background: rgba(255, 253, 248, 0.95);
      border-right: 1px solid var(--line);
      padding: 18px;
      overflow: auto;
    }
    .main {
      padding: 20px;
      display: grid;
      gap: 14px;
      grid-template-rows: auto auto 1fr;
    }
    h1 { margin: 0 0 8px; font-size: 24px; }
    .muted { color: var(--muted); font-size: 14px; }
    .panel {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 14px;
      box-shadow: 0 14px 38px rgba(0,0,0,0.05);
    }
    .toolbar, .meta {
      padding: 12px;
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
      align-items: center;
    }
    .viewer {
      display: grid;
      grid-template-columns: minmax(420px, 60%) 1fr;
      gap: 14px;
      min-height: 0;
    }
    .image-wrap, .edit-wrap {
      padding: 14px;
      min-height: 0;
    }
    .page-viewport {
      overflow: auto;
      border: 1px solid var(--line);
      border-radius: 10px;
      background: white;
      height: min(76vh, 1100px);
    }
    .page-stage {
      position: relative;
      transform-origin: top left;
    }
    .page-stage img {
      display: block;
      max-width: none;
      width: auto;
      height: auto;
    }
    .focus-box {
      position: absolute;
      border: 3px solid var(--focus);
      background: rgba(215, 38, 61, 0.12);
      box-shadow: 0 0 0 99999px rgba(215, 38, 61, 0.03);
      pointer-events: none;
    }
    .edit-wrap textarea, input, select, button {
      font: inherit;
    }
    textarea, input, select {
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 10px;
      padding: 10px 12px;
      background: #fff;
      color: var(--text);
    }
    textarea {
      min-height: 420px;
      resize: vertical;
      line-height: 1.45;
    }
    button {
      border: 0;
      border-radius: 10px;
      padding: 10px 14px;
      cursor: pointer;
      background: #e7dece;
      color: var(--text);
    }
    button.primary { background: var(--accent); color: white; }
    .list {
      margin-top: 12px;
      display: grid;
      gap: 8px;
    }
    .item {
      background: white;
      border: 1px solid var(--line);
      border-radius: 12px;
      padding: 10px;
      cursor: pointer;
    }
    .item.active {
      border-color: var(--accent);
      box-shadow: inset 0 0 0 1px var(--accent);
    }
    .pill {
      display: inline-block;
      font-size: 12px;
      border-radius: 999px;
      padding: 2px 8px;
      background: #eee7d8;
      margin-top: 6px;
    }
    .todo, .unknown, .trash { color: var(--todo); }
    .ready, .done { color: var(--ready); }
    .uncertain-badge {
      display: inline-block;
      margin-left: 8px;
      padding: 2px 8px;
      border-radius: 999px;
      background: #fff3cd;
      color: #8a5a00;
      font-size: 12px;
    }
    .label {
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      color: var(--muted);
      margin-bottom: 4px;
    }
    .two {
      display: grid;
      grid-template-columns: 180px 1fr;
      gap: 10px;
    }
    @media (max-width: 1100px) {
      .app { grid-template-columns: 1fr; }
      .sidebar { border-right: 0; border-bottom: 1px solid var(--line); }
      .viewer { grid-template-columns: 1fr; }
      .page-viewport { height: 60vh; }
    }
  </style>
</head>
<body>
  <div class="app">
    <aside class="sidebar">
      <h1>HTR Review</h1>
      <div class="muted">Offline. Widok pokazuje cala strone z zaznaczonym obszarem. Enter zapisuje i przechodzi dalej. Shift+Enter dodaje nowa linie. Na koncu eksportujesz JSON.</div>
      <div class="panel toolbar" style="margin-top: 14px;">
        <div style="flex:1 1 160px">
          <div class="label">Filtr statusu</div>
          <select id="filterStatus">
            <option value="">Wszystkie</option>
            <option value="todo">todo</option>
            <option value="ready">ready</option>
            <option value="unknown">unknown</option>
            <option value="trash">trash</option>
            <option value="done">done</option>
          </select>
        </div>
        <div style="flex:1 1 160px">
          <div class="label">Szukaj</div>
          <input id="searchBox" placeholder="plik lub notatka">
        </div>
      </div>
      <div class="panel toolbar" style="margin-top: 12px;">
        <button id="exportBtn" class="primary">Eksportuj JSON</button>
        <button id="resetBtn">Reset lokalnych zmian</button>
      </div>
      <div id="list" class="list"></div>
    </aside>
    <main class="main">
      <div class="panel toolbar">
        <button id="prevBtn">Poprzedni</button>
        <button id="nextBtn">Nastepny</button>
        <button id="saveBtn" class="primary">Zapisz lokalnie</button>
        <button id="readyBtn">Ready</button>
        <button id="unknownBtn">Nie wiem</button>
        <button id="trashBtn">Smiec</button>
        <div id="counter" style="margin-left:auto;color:var(--muted)">0 / 0</div>
      </div>
      <div class="panel meta two">
        <div>
          <div class="label">Status</div>
          <select id="statusSelect">
            <option value="todo">todo</option>
            <option value="ready">ready</option>
            <option value="unknown">unknown</option>
            <option value="trash">trash</option>
            <option value="done">done</option>
          </select>
        </div>
        <div>
          <div class="label">Notatki <span id="uncertainBadge" class="uncertain-badge" style="display:none">niepewne</span></div>
          <input id="notesInput">
        </div>
      </div>
      <div class="viewer">
        <section class="panel image-wrap">
          <div class="label">Strona</div>
          <div id="imageName" style="margin-bottom:10px"></div>
          <div style="display:flex;gap:8px;align-items:center;margin-bottom:10px;flex-wrap:wrap">
            <button id="zoomOutBtn" type="button">-</button>
            <button id="zoomResetBtn" type="button">100%</button>
            <button id="zoomInBtn" type="button">+</button>
            <input id="zoomRange" type="range" min="40" max="240" step="10" value="100" style="max-width:220px">
            <span id="zoomLabel" style="color:var(--muted);min-width:48px">100%</span>
          </div>
          <div id="pageViewport" class="page-viewport">
            <div id="pageStage" class="page-stage">
              <img id="pageImage" alt="page">
              <div id="focusBox" class="focus-box"></div>
            </div>
          </div>
        </section>
        <section class="panel edit-wrap">
          <div class="label">Transkrypcja</div>
          <div id="guessBox" style="margin-bottom:10px;color:var(--muted);display:none"></div>
          <textarea id="textArea" spellcheck="false"></textarea>
        </section>
      </div>
    </main>
  </div>
  <script>
    const STORAGE_KEY = "htr-review-offline-v3";
    const pageAssets = __PAGES__;
    const initialItems = __DATA__;
    let items = loadItems();
    let filtered = [];
    let currentIndex = -1;
    let zoomPercent = 100;

    function loadItems() {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) return initialItems;
      try {
        const saved = JSON.parse(raw);
        return initialItems.map(item => {
          const override = saved.find(x => x.id === item.id);
          return override ? {...item, ...override} : item;
        });
      } catch {
        return initialItems;
      }
    }

    function persist() {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(items));
    }

    function applyFilter() {
      const status = document.getElementById("filterStatus").value.trim().toLowerCase();
      const query = document.getElementById("searchBox").value.trim().toLowerCase();
      filtered = items.filter(item => {
        const okStatus = !status || item.status.toLowerCase() === status;
        const hay = [item.page_name, item.notes, item.text, item.image_name].join(" ").toLowerCase();
        const okQuery = !query || hay.includes(query);
        return okStatus && okQuery;
      });
      renderList();
      if (!filtered.length) {
        currentIndex = -1;
        return;
      }
      const currentId = getCurrent()?.id;
      const next = filtered.findIndex(item => item.id === currentId);
      openItem(next >= 0 ? next : 0);
    }

    function renderList() {
      const list = document.getElementById("list");
      list.innerHTML = "";
      filtered.forEach((item, idx) => {
        const div = document.createElement("div");
        div.className = "item" + (idx === currentIndex ? " active" : "");
        div.onclick = () => openItem(idx);
        div.innerHTML = `
          <div><strong>${escapeHtml(item.notes || item.image_name)}</strong></div>
          <div style="font-size:12px;color:var(--muted)">${escapeHtml(item.page_name)}</div>
          <div class="pill ${escapeHtml(item.status)}">${escapeHtml(item.status)}</div>
        `;
        list.appendChild(div);
      });
    }

    function getCurrent() {
      if (currentIndex < 0 || currentIndex >= filtered.length) return null;
      return filtered[currentIndex];
    }

    function isUncertainText(text) {
      return (text.match(/\\?/g) || []).length > 1;
    }

    function syncCurrentBack(item) {
      const idx = items.findIndex(x => x.id === item.id);
      if (idx >= 0) items[idx] = item;
    }

    function applyZoom() {
      const stage = document.getElementById("pageStage");
      const range = document.getElementById("zoomRange");
      const label = document.getElementById("zoomLabel");
      stage.style.transform = `scale(${zoomPercent / 100})`;
      range.value = String(zoomPercent);
      label.textContent = `${zoomPercent}%`;
    }

    function setZoom(nextZoom, recenter = true) {
      zoomPercent = Math.max(40, Math.min(240, nextZoom));
      applyZoom();
      if (recenter) {
        centerOnFocus();
      }
    }

    function centerOnFocus() {
      const item = getCurrent();
      if (!item) return;
      const viewport = document.getElementById("pageViewport");
      const box = item.box;
      const scale = zoomPercent / 100;
      const targetLeft = ((box.left + box.right) / 2) * scale - viewport.clientWidth / 2;
      const targetTop = ((box.top + box.bottom) / 2) * scale - viewport.clientHeight / 2;
      viewport.scrollLeft = Math.max(0, targetLeft);
      viewport.scrollTop = Math.max(0, targetTop);
    }

    function updatePageView(item) {
      const page = pageAssets[item.page_key];
      const image = document.getElementById("pageImage");
      const stage = document.getElementById("pageStage");
      const box = document.getElementById("focusBox");
      image.src = page.data;
      image.width = page.width;
      image.height = page.height;
      stage.style.width = `${page.width}px`;
      stage.style.height = `${page.height}px`;
      box.style.left = `${item.box.left}px`;
      box.style.top = `${item.box.top}px`;
      box.style.width = `${Math.max(1, item.box.right - item.box.left)}px`;
      box.style.height = `${Math.max(1, item.box.bottom - item.box.top)}px`;
      applyZoom();
      requestAnimationFrame(centerOnFocus);
    }

    function refreshUncertaintyUi() {
      const text = document.getElementById("textArea").value || "";
      const uncertain = isUncertainText(text);
      const badge = document.getElementById("uncertainBadge");
      const textArea = document.getElementById("textArea");
      badge.style.display = uncertain ? "inline-block" : "none";
      textArea.style.borderColor = uncertain ? "#d18b00" : "var(--line)";
      textArea.style.boxShadow = uncertain ? "0 0 0 2px rgba(209,139,0,0.18)" : "none";
    }

    function openItem(index) {
      if (index < 0 || index >= filtered.length) return;
      currentIndex = index;
      renderList();
      const item = filtered[index];
      document.getElementById("imageName").textContent = `${item.page_name} | ${item.notes}`;
      document.getElementById("textArea").value = item.text || item.ocr_guess || "";
      document.getElementById("notesInput").value = item.notes || "";
      document.getElementById("statusSelect").value = item.status || "todo";
      document.getElementById("counter").textContent = `${index + 1} / ${filtered.length}`;
      const guessBox = document.getElementById("guessBox");
      if (item.ocr_guess) {
        guessBox.style.display = "block";
        guessBox.innerHTML = `<strong>OCR guess:</strong> ${escapeHtml(item.ocr_guess)}`;
      } else {
        guessBox.style.display = "none";
        guessBox.textContent = "";
      }
      updatePageView(item);
      refreshUncertaintyUi();
    }

    function saveLocal(forceStatus = null, reopenCurrent = true) {
      const item = getCurrent();
      if (!item) return;
      item.text = document.getElementById("textArea").value;
      item.notes = document.getElementById("notesInput").value;
      item.status = forceStatus || document.getElementById("statusSelect").value;
      syncCurrentBack(item);
      persist();
      applyFilter();
      if (reopenCurrent) {
        const idx = filtered.findIndex(x => x.id === item.id);
        if (idx >= 0) openItem(idx);
      }
    }

    function markAndAdvance(status) {
      const nextId = filtered[currentIndex + 1]?.id ?? null;
      const prevId = filtered[currentIndex - 1]?.id ?? null;
      saveLocal(status, false);
      if (nextId !== null) {
        const idx = filtered.findIndex(x => x.id === nextId);
        if (idx >= 0) {
          openItem(idx);
          return;
        }
      }
      if (prevId !== null) {
        const idx = filtered.findIndex(x => x.id === prevId);
        if (idx >= 0) {
          openItem(idx);
          return;
        }
      }
      if (filtered.length) {
        openItem(Math.min(currentIndex, filtered.length - 1));
      }
    }

    function exportJson() {
      const payload = items.map(({page_key, box, ...rest}) => ({...rest, page_key, box}));
      const blob = new Blob([JSON.stringify(payload, null, 2)], {type: "application/json"});
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "htr-review-export.json";
      a.click();
      URL.revokeObjectURL(url);
    }

    function resetLocal() {
      if (!confirm("Usunac lokalne zmiany z przegladarki?")) return;
      localStorage.removeItem(STORAGE_KEY);
      items = initialItems;
      applyFilter();
    }

    function escapeHtml(value) {
      return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#39;");
    }

    document.getElementById("filterStatus").addEventListener("change", applyFilter);
    document.getElementById("searchBox").addEventListener("input", applyFilter);
    document.getElementById("prevBtn").addEventListener("click", () => openItem(Math.max(0, currentIndex - 1)));
    document.getElementById("nextBtn").addEventListener("click", () => openItem(Math.min(filtered.length - 1, currentIndex + 1)));
    document.getElementById("saveBtn").addEventListener("click", () => saveLocal());
    document.getElementById("readyBtn").addEventListener("click", () => markAndAdvance("ready"));
    document.getElementById("unknownBtn").addEventListener("click", () => markAndAdvance("unknown"));
    document.getElementById("trashBtn").addEventListener("click", () => markAndAdvance("trash"));
    document.getElementById("exportBtn").addEventListener("click", exportJson);
    document.getElementById("resetBtn").addEventListener("click", resetLocal);
    document.getElementById("zoomOutBtn").addEventListener("click", () => setZoom(zoomPercent - 10));
    document.getElementById("zoomInBtn").addEventListener("click", () => setZoom(zoomPercent + 10));
    document.getElementById("zoomResetBtn").addEventListener("click", () => setZoom(100));
    document.getElementById("zoomRange").addEventListener("input", event => setZoom(Number(event.target.value), false));
    document.getElementById("zoomRange").addEventListener("change", () => centerOnFocus());
    document.addEventListener("keydown", event => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "s") {
        event.preventDefault();
        saveLocal();
      }
    });
    document.getElementById("textArea").addEventListener("input", refreshUncertaintyUi);
    document.getElementById("textArea").addEventListener("keydown", event => {
      if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        saveLocal();
        openItem(Math.min(filtered.length - 1, currentIndex + 1));
      }
    });

    applyFilter();
  </script>
</body>
</html>
"""


def image_to_data_uri(path: Path) -> str:
    mime = "image/png"
    if path.suffix.lower() in {".jpg", ".jpeg"}:
        mime = "image/jpeg"
    elif path.suffix.lower() == ".gif":
        mime = "image/gif"
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
                with Image.open(source_path) as page_image:
                    width, height = page_image.size
                pages[page_key] = {
                    "name": source_path.name,
                    "width": width,
                    "height": height,
                    "data": image_to_data_uri(source_path),
                }

            left = int(float(row.get("left", 0) or 0))
            top = int(float(row.get("top", 0) or 0))
            right = int(float(row.get("right", pages[page_key]["width"]) or pages[page_key]["width"]))
            bottom = int(float(row.get("bottom", pages[page_key]["height"]) or pages[page_key]["height"]))

            items.append(
                {
                    "id": idx,
                    "image_name": image_path.name,
                    "manual_text_path": str(text_path),
                    "page_key": page_key,
                    "page_name": pages[page_key]["name"],
                    "status": (row.get("status") or "todo").strip() or "todo",
                    "notes": (row.get("notes") or "").strip(),
                    "text": text,
                    "ocr_guess": (row.get("ocr_guess") or "").strip(),
                    "box": {
                        "left": left,
                        "top": top,
                        "right": right,
                        "bottom": bottom,
                    },
                }
            )

    html = HTML_TEMPLATE.replace("__PAGES__", json.dumps(pages, ensure_ascii=False))
    html = html.replace("__DATA__", json.dumps(items, ensure_ascii=False))
    output_html.parent.mkdir(parents=True, exist_ok=True)
    output_html.write_text(html, encoding="utf-8")
    print(output_html)


if __name__ == "__main__":
    main()
