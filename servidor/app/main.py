import os
from fastapi import BackgroundTasks, FastAPI, HTTPException, Request, Response
from . import whatsapp as wa
from .calc import armar_resumen, faltantes, formato_whatsapp
from .extractor import ArchivoMalo, extraer

app = FastAPI()
EXPEDIENTES: dict[str, list] = {}
ENVIADOS: set[str] = set()
CORRECCIONES: dict[str, dict] = {}
CAMPOS = {"nombre", "nacimiento", "direccion", "correo", "celular", "modelo", "anio", "precio"}
ALIAS = {"nacimiento": "fecha_nacimiento"}   # en memoria; para producción usa SQLite/Redis
PERMITIDOS = {n.strip() for n in os.getenv("ALLOWED_NUMBERS", "").split(",") if n.strip()}
ETIQ = {"ine": "INE", "estado_cuenta": "Estado de cuenta", "solicitud": "Solicitud",
        "cotizacion": "Cotización", "otro": "Documento no reconocido"}
AYUDA = ("Mándame fotos o PDFs: INE, solicitud, cotización y los 3 estados de cuenta.\n"
         "Escribe *listo* para el resumen, *nuevo* para empezar otro expediente.\n"
         "Si algo salió mal leído: *corregir correo juan@gmail.com* (campos: nombre, nacimiento, direccion, correo, celular, modelo, anio, precio).\n"
         "Tip: las fotos enviadas como *documento/archivo* llegan sin compresión y se leen mejor.")


@app.get("/webhook")
def verificar(request: Request):
    q = request.query_params
    if q.get("hub.verify_token") == os.getenv("WA_VERIFY_TOKEN") and q.get("hub.mode") == "subscribe":
        return Response(q.get("hub.challenge"))
    raise HTTPException(403)


def procesar_media(tel: str, media_id: str):
    try:
        data, mime = wa.descargar_media(media_id)
        if mime not in ("image/jpeg", "image/png", "image/webp", "application/pdf"):
            return wa.enviar(tel, f"Formato no soportado ({mime}). Manda foto o PDF.")
        d, ajustes = extraer(data, mime)
        EXPEDIENTES.setdefault(tel, []).append(d)
        msg = f"✅ Recibido: {ETIQ[d.tipo]}"
        if ajustes:
            msg += "\n🔧 Foto: " + "; ".join(ajustes)
        if not d.legible:
            msg = f"❌ No pude leer este {ETIQ[d.tipo]}. ¿Lo mandas de nuevo, de frente y con buena luz?"
        elif d.dudas:
            msg += "\n⚠️ Dudas: " + "; ".join(d.dudas)
        falta = faltantes(EXPEDIENTES[tel])
        if not falta:
            if tel not in ENVIADOS:      # resumen automático al completarse
                ENVIADOS.add(tel)
                msg += "\n\n🎉 Expediente completo:\n\n" + formato_whatsapp(armar_resumen(EXPEDIENTES[tel], CORRECCIONES.get(tel)))
        elif d.legible:
            msg += "\n\n📋 Aún falta: " + ", ".join(falta)
        wa.enviar(tel, msg)
    except ArchivoMalo as e:
        wa.enviar(tel, f"📷 No lo procesé: {e}. Tómala de nuevo de frente, con buena luz, sin sombra, y mándala como *documento*.")
    except Exception as e:
        wa.enviar(tel, f"Error procesando el archivo: {type(e).__name__}. Intenta de nuevo.")


@app.post("/webhook")
async def recibir(request: Request, bg: BackgroundTasks):
    body = await request.body()
    if not wa.firma_valida(body, request.headers.get("X-Hub-Signature-256", "")):
        raise HTTPException(403)
    for entry in (await request.json()).get("entry", []):
        for ch in entry.get("changes", []):
            for m in ch.get("value", {}).get("messages", []):
                tel = m["from"]
                if tel not in PERMITIDOS:
                    continue
                t = m["type"]
                if t in ("image", "document"):
                    bg.add_task(procesar_media, tel, m[t]["id"])
                elif t == "text":
                    txt = m["text"]["body"].strip().lower()
                    if txt in ("listo", "resumen"):
                        docs = EXPEDIENTES.get(tel, [])
                        bg.add_task(wa.enviar, tel, formato_whatsapp(armar_resumen(docs, CORRECCIONES.get(tel))) if docs else "Aún no hay documentos.")
                    elif txt == "nuevo":
                        EXPEDIENTES[tel] = []
                        ENVIADOS.discard(tel)
                        CORRECCIONES.pop(tel, None)
                        bg.add_task(wa.enviar, tel, "Expediente nuevo. " + AYUDA)
                    elif txt.startswith("corregir "):
                        partes = m["text"]["body"].strip().split(maxsplit=2)
                        if len(partes) == 3 and partes[1].lower() in CAMPOS:
                            campo = ALIAS.get(partes[1].lower(), partes[1].lower())
                            CORRECCIONES.setdefault(tel, {})[campo] = partes[2]
                            bg.add_task(wa.enviar, tel, f"✏️ {partes[1]} = {partes[2]}. Escribe *listo* para ver el resumen.")
                        else:
                            bg.add_task(wa.enviar, tel, "Formato: corregir <campo> <valor>. Campos: " + ", ".join(sorted(CAMPOS)))
                    else:
                        bg.add_task(wa.enviar, tel, AYUDA)
    return {"ok": True}
