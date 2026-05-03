from __future__ import annotations
import base64
import os
import sys
from pathlib import Path
from google import genai
from google.genai import types

API_KEY = os.environ.get("GEMINI_API_KEY", "")
IMAGE_PATH = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(
    r"C:\Users\Nocna\source\handwritten-htr\samples\prepared\kowal-0039-small.png"
)

client = genai.Client(api_key=API_KEY)

image_bytes = IMAGE_PATH.read_bytes()
image_b64 = base64.standard_b64encode(image_bytes).decode()

prompt = """To jest skan strony z odręcznie wypełnioną tabelą archiwalną.
Przepisz wszystkie odczytane teksty, kolumna po kolumnie, wiersz po wierszu.
Jeśli czegoś nie możesz odczytać, napisz [?].
Zachowaj układ tabeli używając | jako separatora kolumn."""

response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents=[
        types.Part.from_bytes(data=image_bytes, mime_type="image/png"),
        prompt,
    ],
)

print(response.text)
