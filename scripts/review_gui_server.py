from __future__ import annotations

import argparse
import csv
import html
import json
import mimetypes
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse


HTML_PAGE = """<!doctype html>
<html lang="pl">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>HTR Review</title>
  <style>
    :root {
      --bg: #f1efe7;
      --panel: #fbfaf6;
      --line: #d4cfbf;
      --text: #1f1d19;
      --muted: #6f6a5d;
      --accent: #1f5eff;
      --accent-2: #d94f04;
      --ok: #2f7d32;
      --todo: #8b3a14;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: Georgia, "Times New Roman", serif;
      color: var(--text);
      background:
        radial-gradient(circle at top left, #fff6d9 0, transparent 28%),
        radial-gradient(circle at bottom right, #e5ece6 0, transparent 30%),
        var(--bg);
    }
    .app {
      display: grid;
      grid-template-columns: 320px 1fr;
      min-height: 100vh;
    }
    .sidebar {
      border-right: 1px solid var(--line);
      background: rgba(251, 250, 246, 0.92);
      backdrop-filter: blur(8px);
      padding: 18px;
      overflow: auto;
    }
    .main {
      padding: 22px;
      display: grid;
      gap: 16px;
      grid-template-rows: auto auto 1fr;
    }
    h1 {
      margin: 0 0 8px;
      font-size: 24px;
      letter-spacing: 0.02em;
    }
    .muted {
      color: var(--muted);
      font-size: 14px;
    }
    .toolbar, .editor-bar {
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
      align-items: center;
    }
    .panel {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 14px;
      box-shadow: 0 14px 40px rgba(0, 0, 0, 0.06);
    }
    .toolbar.panel, .editor-bar.panel {
      padding: 12px;
    }
    .viewer {
      display: grid;
      grid-template-columns: minmax(320px, 48%) 1fr;
      gap: 16px;
      min-height: 0;
    }
    .image-wrap, .edit-wrap {
      min-height: 0;
      padding: 14px;
    }
    .image-wrap img {
      width: 100%;
      height: auto;
      border-radius: 10px;
      border: 1px solid var(--line);
      background: white;
      display: block;
    }
    .meta {
      display: grid;
      gap: 6px;
      margin-bottom: 12px;
      font-size: 14px;
    }
    .label {
      font-size: 12px;
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }
    textarea, input, select {
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 10px;
      padding: 10px 12px;
      font: inherit;
      background: #fff;
      color: var(--text);
    }
    textarea {
      min-height: 360px;
      resize: vertical;
      line-height: 1.45;
    }
    button {
      border: 0;
      border-radius: 10px;
      padding: 10px 14px;
      font: inherit;
      cursor: pointer;
      background: #e7e1d3;
      color: var(--text);
    }
    button.primary {
      background: var(--accent);
      color: white;
    }
    button.warn {
      background: var(--accent-2);
      color: white;
    }
    .list {
      margin-top: 14px;
      display: grid;
      gap: 8px;
    }
    .item {
      border: 1px solid var(--line);
      border-radius: 12px;
      padding: 10px;
      background: #fff;
      cursor: pointer;
    }
    .item.active {
      border-color: var(--accent);
      box-shadow: inset 0 0 0 1px var(--accent);
    }
    .item-title {
      font-size: 14px;
      font-weight: 700;
      word-break: break-word;
    }
    .item-sub {
      margin-top: 6px;
      display: flex;
      justify-content: space-between;
      gap: 8px;
      font-size: 12px;
      color: var(--muted);
    }
    .pill {
      display: inline-block;
      padding: 2px 8px;
      border-radius: 999px;
      font-size: 12px;
      background: #efe9db;
    }
    .pill.todo { color: var(--todo); }
    .pill.ready, .pill.done { color: var(--ok); }
    .counter {
      margin-left: auto;
      font-size: 13px;
      color: var(--muted);
    }
    .status {
      min-width: 120px;
    }
    .path {
      word-break: break-all;
      color: var(--muted);
    }
    @media (max-width: 1100px) {
      .app { grid-template-columns: 1fr; }
      .sidebar { border-right: 0; border-bottom: 1px solid var(--line); }
      .viewer { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
  <div class="app">
    <aside class="sidebar">
      <h1>HTR Review</h1>
      <div class="muted">Ctrl+S zapisuje. Strzałki lewo/prawo przechodzą między rekordami.</div>
      <div class="toolbar panel" style="margin-top: 14px;">
        <div style="flex: 1 1 180px;">
          <div class="label">Filtr statusu</div>
          <select id="filterStatus">
            <option value="">Wszystkie</option>
            <option value="todo">todo</option>
            <option value="ready">ready</option>
            <option value="done">done</option>
          </select>
        </div>
        <div style="flex: 1 1 180px;">
          <div class="label">Szukaj</div>
          <input id="searchBox" placeholder="plik, notatka, status">
        </div>
      </div>
      <div id="list" class="list"></div>
    </aside>
    <main class="main">
      <div class="toolbar panel">
        <button id="prevBtn">Poprzedni</button>
        <button id="nextBtn">Następny</button>
        <button id="saveBtn" class="primary">Zapisz</button>
        <button id="markReadyBtn" class="warn">Zapisz jako ready</button>
        <div id="counter" class="counter">0 / 0</div>
      </div>
      <div class="editor-bar panel">
        <div style="flex: 1 1 240px;">
          <div class="label">Status</div>
          <select id="statusSelect" class="status">
            <option value="todo">todo</option>
            <option value="ready">ready</option>
            <option value="done">done</option>
          </select>
        </div>
        <div style="flex: 3 1 420px;">
          <div class="label">Notatki</div>
          <input id="notesInput" placeholder="np. nieczytelne nazwisko, uszkodzony skan">
        </div>
      </div>
      <div class="viewer">
        <section class="panel image-wrap">
          <div class="meta">
            <div>
              <div class="label">Obraz</div>
              <div id="imageName"></div>
            </div>
            <div>
              <div class="label">Ścieżka</div>
              <div id="imagePath" class="path"></div>
            </div>
          </div>
          <img id="image" alt="sample">
        </section>
        <section class="panel edit-wrap">
          <div class="meta">
            <div>
              <div class="label">Plik transkrypcji</div>
              <div id="textPath" class="path"></div>
            </div>
          </div>
          <textarea id="textArea" spellcheck="false"></textarea>
        </section>
      </div>
    </main>
  </div>
  <script>
    let items = [];
    let filteredItems = [];
    let currentIndex = -1;

    async function fetchJson(url, options = {}) {
      const response = await fetch(url, options);
      if (!response.ok) {
        throw new Error(await response.text());
      }
      return await response.json();
    }

    function applyFilter() {
      const status = document.getElementById('filterStatus').value.trim().toLowerCase();
      const query = document.getElementById('searchBox').value.trim().toLowerCase();
      filteredItems = items.filter(item => {
        const statusOk = !status || item.status.toLowerCase() === status;
        const hay = [item.image_name, item.status, item.notes, item.manual_text_path].join(' ').toLowerCase();
        const queryOk = !query || hay.includes(query);
        return statusOk && queryOk;
      });
      renderList();
      if (!filteredItems.length) {
        currentIndex = -1;
        clearEditor();
        return;
      }
      const currentId = getCurrentItem()?.id;
      const nextIndex = filteredItems.findIndex(item => item.id === currentId);
      openItem(nextIndex >= 0 ? nextIndex : 0);
    }

    function renderList() {
      const list = document.getElementById('list');
      list.innerHTML = '';
      filteredItems.forEach((item, idx) => {
        const div = document.createElement('div');
        div.className = 'item' + (idx === currentIndex ? ' active' : '');
        div.onclick = () => openItem(idx);
        div.innerHTML = `
          <div class="item-title">${escapeHtml(item.image_name)}</div>
          <div class="item-sub">
            <span class="pill ${escapeHtml(item.status)}">${escapeHtml(item.status || 'todo')}</span>
            <span>${item.text_length || 0} zn.</span>
          </div>
        `;
        list.appendChild(div);
      });
    }

    function clearEditor() {
      document.getElementById('image').removeAttribute('src');
      document.getElementById('imageName').textContent = '';
      document.getElementById('imagePath').textContent = '';
      document.getElementById('textPath').textContent = '';
      document.getElementById('textArea').value = '';
      document.getElementById('notesInput').value = '';
      document.getElementById('statusSelect').value = 'todo';
      updateCounter();
    }

    function getCurrentItem() {
      if (currentIndex < 0 || currentIndex >= filteredItems.length) {
        return null;
      }
      return filteredItems[currentIndex];
    }

    async function openItem(index) {
      if (index < 0 || index >= filteredItems.length) {
        return;
      }
      currentIndex = index;
      renderList();
      updateCounter();
      const item = filteredItems[index];
      const data = await fetchJson(`/api/item?id=${item.id}`);
      document.getElementById('image').src = `/image?id=${item.id}&v=${Date.now()}`;
      document.getElementById('imageName').textContent = data.image_name;
      document.getElementById('imagePath').textContent = data.image_path;
      document.getElementById('textPath').textContent = data.manual_text_path;
      document.getElementById('textArea').value = data.text || '';
      document.getElementById('notesInput').value = data.notes || '';
      document.getElementById('statusSelect').value = data.status || 'todo';
    }

    function updateCounter() {
      const current = filteredItems.length ? currentIndex + 1 : 0;
      document.getElementById('counter').textContent = `${current} / ${filteredItems.length}`;
    }

    async function saveCurrent(forceStatus = null) {
      const item = getCurrentItem();
      if (!item) return;
      const payload = {
        id: item.id,
        text: document.getElementById('textArea').value,
        notes: document.getElementById('notesInput').value,
        status: forceStatus || document.getElementById('statusSelect').value,
      };
      const data = await fetchJson('/api/save', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(payload),
      });
      items = data.items;
      applyFilter();
      const newIndex = filteredItems.findIndex(entry => entry.id === item.id);
      if (newIndex >= 0) {
        currentIndex = newIndex;
        renderList();
        updateCounter();
      }
    }

    function escapeHtml(value) {
      return String(value ?? '')
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;')
        .replaceAll("'", '&#39;');
    }

    async function init() {
      const data = await fetchJson('/api/items');
      items = data.items;
      filteredItems = items.slice();
      renderList();
      if (filteredItems.length) {
        await openItem(0);
      }
      updateCounter();
    }

    document.getElementById('filterStatus').addEventListener('change', applyFilter);
    document.getElementById('searchBox').addEventListener('input', applyFilter);
    document.getElementById('prevBtn').addEventListener('click', () => openItem(Math.max(0, currentIndex - 1)));
    document.getElementById('nextBtn').addEventListener('click', () => openItem(Math.min(filteredItems.length - 1, currentIndex + 1)));
    document.getElementById('saveBtn').addEventListener('click', () => saveCurrent());
    document.getElementById('markReadyBtn').addEventListener('click', () => saveCurrent('ready'));
    document.addEventListener('keydown', async (event) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 's') {
        event.preventDefault();
        await saveCurrent();
      }
      if (event.key === 'ArrowLeft' && !event.ctrlKey && !event.metaKey) {
        openItem(Math.max(0, currentIndex - 1));
      }
      if (event.key === 'ArrowRight' && !event.ctrlKey && !event.metaKey) {
        openItem(Math.min(filteredItems.length - 1, currentIndex + 1));
      }
    });
    init();
  </script>
</body>
</html>
"""


class ReviewStore:
    def __init__(self, manifest_path: Path) -> None:
        self.manifest_path = manifest_path
        self.fieldnames: list[str] = []
        self.rows: list[dict[str, str]] = []
        self.load()

    def load(self) -> None:
        with self.manifest_path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            self.fieldnames = list(reader.fieldnames or [])
            self.rows = [dict(row) for row in reader]

    def save(self) -> None:
        with self.manifest_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=self.fieldnames)
            writer.writeheader()
            writer.writerows(self.rows)

    def list_items(self) -> list[dict[str, object]]:
        items: list[dict[str, object]] = []
        for idx, row in enumerate(self.rows):
            text = self._read_text(Path(row["manual_text_path"]))
            items.append(
                {
                    "id": idx,
                    "image_name": Path(row["image"]).name,
                    "manual_text_path": row["manual_text_path"],
                    "status": row.get("status", "todo"),
                    "notes": row.get("notes", ""),
                    "text_length": len(text.strip()),
                }
            )
        return items

    def get_item(self, idx: int) -> dict[str, object]:
        row = self.rows[idx]
        text_path = Path(row["manual_text_path"])
        return {
            "id": idx,
            "image_name": Path(row["image"]).name,
            "image_path": row["image"],
            "manual_text_path": row["manual_text_path"],
            "status": row.get("status", "todo"),
            "notes": row.get("notes", ""),
            "text": self._read_text(text_path),
        }

    def update_item(self, idx: int, text: str, status: str, notes: str) -> None:
        row = self.rows[idx]
        text_path = Path(row["manual_text_path"])
        text_path.parent.mkdir(parents=True, exist_ok=True)
        text_path.write_text(text, encoding="utf-8")
        row["status"] = status
        row["notes"] = notes
        self.save()

    def image_path(self, idx: int) -> Path:
        return Path(self.rows[idx]["image"])

    @staticmethod
    def _read_text(path: Path) -> str:
        if not path.exists():
            return ""
        return path.read_text(encoding="utf-8", errors="ignore")


def make_handler(store: ReviewStore):
    class Handler(BaseHTTPRequestHandler):
        def _send_json(self, payload: object, status: int = 200) -> None:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _send_html(self, body: str, status: int = 200) -> None:
            data = body.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _send_file(self, path: Path) -> None:
            if not path.exists():
                self.send_error(HTTPStatus.NOT_FOUND, "File not found")
                return
            mime, _ = mimetypes.guess_type(path.name)
            data = path.read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", mime or "application/octet-stream")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path == "/":
                self._send_html(HTML_PAGE)
                return
            if parsed.path == "/api/items":
                self._send_json({"items": store.list_items()})
                return
            if parsed.path == "/api/item":
                params = parse_qs(parsed.query)
                idx = int(params.get("id", ["0"])[0])
                self._send_json(store.get_item(idx))
                return
            if parsed.path == "/image":
                params = parse_qs(parsed.query)
                idx = int(params.get("id", ["0"])[0])
                self._send_file(store.image_path(idx))
                return
            self.send_error(HTTPStatus.NOT_FOUND, "Not found")

        def do_POST(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path != "/api/save":
                self.send_error(HTTPStatus.NOT_FOUND, "Not found")
                return
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length)
            payload = json.loads(raw.decode("utf-8"))
            idx = int(payload["id"])
            text = payload.get("text", "")
            status = payload.get("status", "todo")
            notes = payload.get("notes", "")
            store.update_item(idx=idx, text=text, status=status, notes=notes)
            self._send_json({"ok": True, "items": store.list_items()})

        def log_message(self, fmt: str, *args) -> None:
            return

    return Handler


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Local GUI for correcting handwritten HTR samples.")
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    manifest_path = args.manifest.resolve()
    if not manifest_path.exists():
        raise SystemExit(f"Manifest not found: {manifest_path}")

    store = ReviewStore(manifest_path)
    server = ThreadingHTTPServer((args.host, args.port), make_handler(store))
    print(f"Serving review GUI on http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
