"""Aplicación web para vender: tus clientes entran con usuario y contraseña; la IA corre con TU clave de API."""
import logging, os, time
from contextlib import asynccontextmanager
from collections import defaultdict
from pathlib import Path
from fastapi import FastAPI, File, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from . import db

log = logging.getLogger("captura")


@asynccontextmanager
async def _vida(app):
    db.iniciar()
    _cuenta_beta()
    yield


def _cuenta_beta():
    """Beta: crea (o actualiza) una cuenta de acceso desde variables de entorno.

    Sirve en servidores gratuitos que borran el disco al reiniciar: la cuenta se vuelve a crear sola.
    BETA_EMAIL, BETA_PASSWORD y opcional BETA_LIMITE (documentos al mes, 200 por defecto).
    """
    email, pw = os.getenv("BETA_EMAIL"), os.getenv("BETA_PASSWORD")
    if not (email and pw):
        return
    limite = int(os.getenv("BETA_LIMITE", "200"))
    if db.cliente_por_email(email):
        db.actualizar_cliente(email, password=pw, limite_mes=limite, activo=1)
    else:
        db.crear_cliente(email, "Beta", pw, limite)

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None, lifespan=_vida)
WEB = Path(__file__).resolve().parent.parent / "web"
COOKIE = "sesion"
MAX_BYTES = 20 * 1024 * 1024
COOKIE_SEGURA = os.getenv("COOKIE_SECURE", "1") != "0"     # en local sin https: COOKIE_SECURE=0
_fallos: dict[str, list[float]] = defaultdict(list)       # intentos de login fallidos por email


@app.middleware("http")
async def cabeceras(request: Request, call_next):
    # Bloquea envíos desde otros sitios (CSRF) y agrega cabeceras de seguridad
    if request.method == "POST":
        origen = request.headers.get("origin")
        if origen and origen.split("://", 1)[-1] != request.headers.get("host"):
            return JSONResponse({"error": "Origen no permitido"}, status_code=403)
    r = await call_next(request)
    r.headers["X-Content-Type-Options"] = "nosniff"
    r.headers["X-Frame-Options"] = "DENY"
    r.headers["Referrer-Policy"] = "same-origin"
    r.headers["Cache-Control"] = "no-store"
    return r


def _cliente(request: Request):
    cl = db.cliente_de_sesion(request.cookies.get(COOKIE))
    if not cl:
        raise HTTPException(401, "Inicia sesión")
    return cl


def _uso(cl) -> dict:
    return {"usados": db.usados(cl["id"]), "limite": cl["limite_mes"], "mes": db.mes_actual()}


@app.get("/")
def inicio():
    return FileResponse(WEB / "app.html", media_type="text/html")


@app.get("/privacidad")
def privacidad():
    return FileResponse(WEB / "privacidad.html", media_type="text/html")


class Login(BaseModel):
    email: str
    password: str


@app.post("/api/login")
def login(datos: Login, response: Response):
    email = datos.email.strip().lower()
    ahora = time.time()
    _fallos[email] = [t for t in _fallos[email] if ahora - t < 900]
    if len(_fallos[email]) >= 5:
        raise HTTPException(429, "Demasiados intentos. Espera 15 minutos.")
    cl = db.cliente_por_email(email)
    if not cl or not db.password_ok(datos.password, cl["pass_hash"]) or not cl["activo"]:
        _fallos[email].append(ahora)
        raise HTTPException(401, "Correo o contraseña incorrectos")
    _fallos.pop(email, None)
    response.set_cookie(COOKIE, db.crear_sesion(cl["id"]), max_age=db.SESION_DIAS * 86400,
                        httponly=True, secure=COOKIE_SEGURA, samesite="lax")
    return {"ok": True}


@app.post("/api/logout")
def logout(request: Request, response: Response):
    db.cerrar_sesion(request.cookies.get(COOKIE))
    response.delete_cookie(COOKIE)
    return {"ok": True}


@app.get("/api/me")
def me(request: Request):
    cl = _cliente(request)
    return {"email": cl["email"], "empresa": cl["empresa"], "uso": _uso(cl)}


def _tipo_real(data: bytes) -> str | None:
    """Revisa el contenido real del archivo, no solo su nombre."""
    if data[:4] == b"%PDF":
        return "application/pdf"
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if data[4:8] == b"ftyp" and data[8:12] in (b"heic", b"heix", b"hevc", b"hevx", b"mif1", b"msf1", b"heim", b"heis"):
        return "image/heic"
    if data[:4] in (b"II*\x00", b"MM\x00*"):
        return "image/tiff"
    if data[:4] == b"GIF8" or data[:2] == b"BM":
        return "image/otra"
    return None


def _convertir(data: bytes, mime: str) -> tuple[bytes, str]:
    """HEIC (iPhone), TIFF de escáner, GIF o BMP → JPEG (o PDF si el TIFF trae varias páginas)."""
    if mime in ("application/pdf", "image/jpeg", "image/png", "image/webp"):
        return data, mime
    import io
    from PIL import Image, ImageOps, ImageSequence
    if mime == "image/heic":
        try:
            import pillow_heif
            pillow_heif.register_heif_opener()
        except ImportError:
            raise HTTPException(415, "Foto HEIC de iPhone: compártela como JPG o activa Ajustes › Cámara › Formatos › Más compatible.")
    try:
        img = Image.open(io.BytesIO(data))
        paginas = [ImageOps.exif_transpose(p.convert("RGB")) for p in ImageSequence.Iterator(img)][:30]
    except Exception:
        raise HTTPException(415, "No se pudo abrir la imagen. Guárdala como JPG o PDF y súbela de nuevo.")
    buf = io.BytesIO()
    if len(paginas) > 1:
        paginas[0].save(buf, "PDF", save_all=True, append_images=paginas[1:], resolution=200)
        return buf.getvalue(), "application/pdf"
    paginas[0].save(buf, "JPEG", quality=92)
    return buf.getvalue(), "image/jpeg"


@app.post("/api/leer")
def leer(request: Request, archivo: UploadFile = File(...)):
    from .extractor import ArchivoMalo, extraer_documentos   # import tardío: no exige clave de API para arrancar
    cl = _cliente(request)
    data = archivo.file.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise HTTPException(413, "El archivo pasa de 20 MB. Sube solo las páginas necesarias.")
    mime = _tipo_real(data)
    if not mime:
        raise HTTPException(415, "Formato no soportado. Usa foto (JPG, PNG, HEIC, TIFF) o PDF. Un Word o Excel guárdalo como PDF.")
    data, mime = _convertir(data, mime)
    if not db.reservar_documento(cl["id"], cl["limite_mes"]):
        raise HTTPException(402, f"Llegaste al límite de {cl['limite_mes']} documentos de tu plan este mes.")
    try:
        docs, ajustes = extraer_documentos(data, mime)
    except ArchivoMalo as e:
        db.devolver_documento(cl["id"])
        raise HTTPException(422, f"No se procesó: {e}. Toma la foto de nuevo, de frente y con buena luz.")
    except Exception:
        db.devolver_documento(cl["id"])
        log.exception("Fallo leyendo archivo del cliente %s", cl["id"])     # nunca se registra el contenido
        raise HTTPException(502, "No se pudo leer el archivo en este momento. Intenta de nuevo.")
    finally:
        del data                                                          # no se guarda nada
    return {"documentos": [d.model_dump() for d in docs], "ajustes": ajustes, "uso": _uso(cl)}
