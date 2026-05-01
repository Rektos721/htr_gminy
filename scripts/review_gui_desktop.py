from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk

from PIL import Image, ImageTk


@dataclass
class ReviewItem:
    image: Path
    manual_text_path: Path
    status: str
    notes: str


class ReviewApp:
    def __init__(self, root: tk.Tk, manifest_path: Path) -> None:
        self.root = root
        self.manifest_path = manifest_path
        self.items: list[ReviewItem] = []
        self.current_index = -1
        self.current_photo: ImageTk.PhotoImage | None = None

        self.root.title("HTR Review Desktop")
        self.root.geometry("1400x900")
        self.root.configure(bg="#efe9dc")

        self._build_ui()
        self.load_manifest()
        if self.items:
            self.open_item(0)

        self.root.bind("<Control-s>", lambda event: self.save_current())
        self.root.bind("<Left>", lambda event: self.prev_item())
        self.root.bind("<Right>", lambda event: self.next_item())

    def _build_ui(self) -> None:
        self.root.columnconfigure(1, weight=1)
        self.root.rowconfigure(0, weight=1)

        left = tk.Frame(self.root, bg="#f7f4ec", padx=12, pady=12)
        left.grid(row=0, column=0, sticky="nsew")
        left.rowconfigure(3, weight=1)
        left.columnconfigure(0, weight=1)

        tk.Label(left, text="HTR Review", font=("Georgia", 18, "bold"), bg="#f7f4ec").grid(row=0, column=0, sticky="w")
        tk.Label(left, text="Ctrl+S zapisuje, strzałki zmieniają rekord.", bg="#f7f4ec", fg="#6b675d").grid(row=1, column=0, sticky="w", pady=(0, 8))

        self.filter_var = tk.StringVar(value="")
        self.search_var = tk.StringVar(value="")
        self.filter_var.trace_add("write", lambda *_: self.refresh_list())
        self.search_var.trace_add("write", lambda *_: self.refresh_list())

        filters = tk.Frame(left, bg="#f7f4ec")
        filters.grid(row=2, column=0, sticky="ew", pady=(0, 8))
        filters.columnconfigure(0, weight=1)
        filters.columnconfigure(1, weight=1)

        ttk.Combobox(filters, textvariable=self.filter_var, values=["", "todo", "ready", "done"], state="readonly").grid(row=0, column=0, sticky="ew", padx=(0, 4))
        ttk.Entry(filters, textvariable=self.search_var).grid(row=0, column=1, sticky="ew", padx=(4, 0))

        self.listbox = tk.Listbox(left, activestyle="none")
        self.listbox.grid(row=3, column=0, sticky="nsew")
        self.listbox.bind("<<ListboxSelect>>", self._on_select)

        right = tk.Frame(self.root, bg="#efe9dc", padx=14, pady=14)
        right.grid(row=0, column=1, sticky="nsew")
        right.columnconfigure(0, weight=1)
        right.columnconfigure(1, weight=1)
        right.rowconfigure(2, weight=1)

        topbar = tk.Frame(right, bg="#efe9dc")
        topbar.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 10))

        ttk.Button(topbar, text="Poprzedni", command=self.prev_item).pack(side="left")
        ttk.Button(topbar, text="Następny", command=self.next_item).pack(side="left", padx=6)
        ttk.Button(topbar, text="Zapisz", command=self.save_current).pack(side="left", padx=6)
        ttk.Button(topbar, text="Zapisz jako ready", command=lambda: self.save_current(force_status="ready")).pack(side="left", padx=6)
        self.counter_label = tk.Label(topbar, text="0 / 0", bg="#efe9dc", fg="#6b675d")
        self.counter_label.pack(side="right")

        meta = tk.Frame(right, bg="#efe9dc")
        meta.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        meta.columnconfigure(1, weight=1)

        tk.Label(meta, text="Status", bg="#efe9dc").grid(row=0, column=0, sticky="w")
        self.status_var = tk.StringVar(value="todo")
        ttk.Combobox(meta, textvariable=self.status_var, values=["todo", "ready", "done"], state="readonly", width=12).grid(row=0, column=1, sticky="w")
        tk.Label(meta, text="Notes", bg="#efe9dc").grid(row=1, column=0, sticky="w", pady=(8, 0))
        self.notes_var = tk.StringVar(value="")
        ttk.Entry(meta, textvariable=self.notes_var).grid(row=1, column=1, sticky="ew", pady=(8, 0))

        image_panel = tk.Frame(right, bg="#fbfaf6", bd=1, relief="solid")
        image_panel.grid(row=2, column=0, sticky="nsew", padx=(0, 8))
        image_panel.rowconfigure(1, weight=1)
        image_panel.columnconfigure(0, weight=1)
        tk.Label(image_panel, text="Obraz", font=("Georgia", 14, "bold"), bg="#fbfaf6").grid(row=0, column=0, sticky="w", padx=10, pady=10)
        self.image_label = tk.Label(image_panel, bg="#fbfaf6")
        self.image_label.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))

        edit_panel = tk.Frame(right, bg="#fbfaf6", bd=1, relief="solid")
        edit_panel.grid(row=2, column=1, sticky="nsew", padx=(8, 0))
        edit_panel.rowconfigure(1, weight=1)
        edit_panel.columnconfigure(0, weight=1)
        tk.Label(edit_panel, text="Transkrypcja", font=("Georgia", 14, "bold"), bg="#fbfaf6").grid(row=0, column=0, sticky="w", padx=10, pady=10)
        self.text = tk.Text(edit_panel, wrap="word", font=("Consolas", 12))
        self.text.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))

    def load_manifest(self) -> None:
        self.items.clear()
        with self.manifest_path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                self.items.append(
                    ReviewItem(
                        image=Path(row["image"]),
                        manual_text_path=Path(row["manual_text_path"]),
                        status=(row.get("status") or "todo").strip(),
                        notes=(row.get("notes") or "").strip(),
                    )
                )
        self.refresh_list()

    def save_manifest(self) -> None:
        rows = []
        for item in self.items:
            rows.append(
                {
                    "image": str(item.image),
                    "ocr_guess": "",
                    "manual_text_path": str(item.manual_text_path),
                    "status": item.status,
                    "notes": item.notes,
                }
            )
        with self.manifest_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["image", "ocr_guess", "manual_text_path", "status", "notes"])
            writer.writeheader()
            writer.writerows(rows)

    def filtered_indices(self) -> list[int]:
        status_filter = self.filter_var.get().strip().lower()
        query = self.search_var.get().strip().lower()
        result = []
        for idx, item in enumerate(self.items):
            if status_filter and item.status.lower() != status_filter:
                continue
            hay = f"{item.image.name} {item.notes} {item.status} {item.manual_text_path}".lower()
            if query and query not in hay:
                continue
            result.append(idx)
        return result

    def refresh_list(self) -> None:
        self.visible_indices = self.filtered_indices()
        self.listbox.delete(0, tk.END)
        for idx in self.visible_indices:
            item = self.items[idx]
            self.listbox.insert(tk.END, f"[{item.status}] {item.image.name}")
        self.counter_label.config(text=f"{0 if self.current_index < 0 else self.current_index + 1} / {len(self.visible_indices)}")

    def _on_select(self, _event=None) -> None:
        selection = self.listbox.curselection()
        if not selection:
            return
        visible_index = selection[0]
        self.open_item(visible_index)

    def open_item(self, visible_index: int) -> None:
        if visible_index < 0 or visible_index >= len(self.visible_indices):
            return
        self.current_index = visible_index
        item = self.items[self.visible_indices[visible_index]]
        self.status_var.set(item.status)
        self.notes_var.set(item.notes)
        self.text.delete("1.0", tk.END)
        if item.manual_text_path.exists():
            self.text.insert("1.0", item.manual_text_path.read_text(encoding="utf-8", errors="ignore"))

        image = Image.open(item.image)
        image.thumbnail((650, 780))
        self.current_photo = ImageTk.PhotoImage(image)
        self.image_label.configure(image=self.current_photo)
        self.listbox.selection_clear(0, tk.END)
        self.listbox.selection_set(visible_index)
        self.listbox.see(visible_index)
        self.counter_label.config(text=f"{visible_index + 1} / {len(self.visible_indices)}")

    def current_item(self) -> ReviewItem | None:
        if self.current_index < 0 or self.current_index >= len(self.visible_indices):
            return None
        return self.items[self.visible_indices[self.current_index]]

    def save_current(self, force_status: str | None = None) -> None:
        item = self.current_item()
        if not item:
            return
        item.manual_text_path.parent.mkdir(parents=True, exist_ok=True)
        item.manual_text_path.write_text(self.text.get("1.0", tk.END).rstrip() + "\n", encoding="utf-8")
        item.notes = self.notes_var.get().strip()
        item.status = force_status or self.status_var.get().strip() or "todo"
        self.save_manifest()
        self.refresh_list()
        if self.current_index >= 0:
            self.open_item(min(self.current_index, max(0, len(self.visible_indices) - 1)))

    def prev_item(self) -> None:
        if self.current_index > 0:
            self.open_item(self.current_index - 1)

    def next_item(self) -> None:
        if self.current_index + 1 < len(self.visible_indices):
            self.open_item(self.current_index + 1)


def main() -> None:
    manifest = Path(r"C:\Users\Nocna\source\handwritten-htr\outputs\ground-truth\review_manifest.csv")
    if not manifest.exists():
        raise SystemExit(f"Missing manifest: {manifest}")
    root = tk.Tk()
    try:
        ReviewApp(root, manifest)
    except Exception as exc:
        messagebox.showerror("HTR Review", str(exc))
        raise
    root.mainloop()


if __name__ == "__main__":
    main()
