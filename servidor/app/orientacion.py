"""Detecta si la foto está de lado o de cabeza (WhatsApp suele borrar el dato EXIF de orientación).

Le mostramos a un modelo barato (Haiku) la misma foto girada 0°, 90°, 180° y 270°
y elegimos la versión en la que el texto se lee derecho.
"""
import base64, io, os
from typing import Literal
import anthropic
from PIL import Image
from pydantic import BaseModel

MODEL = os.getenv("ORIENT_MODEL", "claude-haiku-5-5")
GIROS = {"A": 0, "B": 90, "C": 180, "D": 270}   # grados antihorario (PIL.Image.rotate)
_client = None


class _Respuesta(BaseModel):
    opcion: Literal["A", "B", "C", "D"]


def detectar_rotacion(img: Image.Image) -> int:
    """Regresa los grados (antihorario) para enderezar la imagen. 0 si ya está derecha o si falla."""
    global _client
    _client = _client or anthropic.Anthropic()
    mini = img.copy()
    mini.thumbnail((700, 700))
    contenido = []
    for letra, grados in GIROS.items():
        b = io.BytesIO()
        mini.rotate(grados, expand=True).convert("RGB").save(b, "JPEG", quality=80)
        contenido += [{"type": "text", "text": f"Opción {letra}:"},
                      {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg",
                                                   "data": base64.standard_b64encode(b.getvalue()).decode()}}]
    contenido.append({"type": "text", "text":
        "Son la misma foto de un documento girada de 4 formas. ¿En qué opción el texto principal "
        "se lee derecho: horizontal, de izquierda a derecha y no de cabeza?"})
    try:
        r = _client.messages.parse(model=MODEL, max_tokens=2000, output_config={"effort": "low"},
                                   messages=[{"role": "user", "content": contenido}], output_format=_Respuesta)
        return GIROS[r.parsed_output.opcion] if r.parsed_output else 0
    except Exception:
        return 0   # si falla, seguimos sin girar; el modelo principal aún puede leer texto girado
