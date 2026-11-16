import hashlib, hmac, os
import httpx

TOKEN = os.getenv("WA_TOKEN", "")
PHONE_ID = os.getenv("WA_PHONE_NUMBER_ID", "")
API = "https://graph.facebook.com/v21.0"
H = lambda: {"Authorization": f"Bearer {TOKEN}"}


def firma_valida(body: bytes, header: str) -> bool:
    secret = os.getenv("WA_APP_SECRET", "").encode()
    esperado = "sha256=" + hmac.new(secret, body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(esperado, header or "")


def descargar_media(media_id: str) -> tuple[bytes, str]:
    with httpx.Client(timeout=60) as c:
        info = c.get(f"{API}/{media_id}", headers=H()).raise_for_status().json()
        r = c.get(info["url"], headers=H()).raise_for_status()
        return r.content, info.get("mime_type", r.headers.get("content-type", "image/jpeg"))


def enviar(to: str, texto: str):
    with httpx.Client(timeout=30) as c:
        c.post(f"{API}/{PHONE_ID}/messages", headers=H(),
               json={"messaging_product": "whatsapp", "to": to, "type": "text", "text": {"body": texto}}).raise_for_status()
