import base64, json, os
import anthropic
from .orientacion import detectar_rotacion
from .preprocess import calidad_baja, preparar_imagen
from .guia import BUSQUEDA_MINUCIOSA, CLAVE, COMO_RECONOCER
from .schemas import DocExtraction, Lectura
from .validators import monto_en_texto, validar

client = anthropic.Anthropic()
MODEL = os.getenv("MODEL", "claude-opus-5-5")
EFFORT = os.getenv("EFFORT", "high")   # más esfuerzo = mejor lectura de letra difícil

SYSTEM = f"""Eres un capturista experto en documentos mexicanos para un analista de crédito automotriz.
Recibes UN archivo (foto o PDF). Puede traer varios documentos (ej. un PDF con 3 estados de cuenta, o INE y
solicitud en la misma foto): devuelve uno por cada documento en `documentos`. Si es foto, recibes DOS versiones: la original a color y una realzada
(grises, más contraste). Usa ambas: la de color para distinguir tinta de fondo, la realzada para trazos tenues.

Clasifica cada documento: ine, estado_cuenta, solicitud, cotizacion, comprobante_domicilio u otro.
{COMO_RECONOCER}

{BUSQUEDA_MINUCIOSA}

Cómo leer letra difícil:
- Lee carácter por carácter. Usa el contexto: nombres y apellidos mexicanos comunes, colonias y municipios reales,
  dominios de correo (gmail.com, hotmail.com, outlook.com, yahoo.com.mx, icloud.com).
- Confusiones típicas a mano: 1/7, 4/9, 5/S, 0/O/D, 2/Z, 6/b, 8/B, u/v, n/h, a/o, l/1/I, r/v, g/q, m/rn.
- Si el nombre aparece en varios lugares (ej. firma impresa, otro campo), cruza la información.
- En correos, el usuario suele parecerse al nombre de la persona: úsalo para desempatar.
- Nunca inventes: si algo es ilegible, pon null. Si lo leíste pero no estás seguro, ponlo y agrégalo a `dudas`
  indicando el campo y las alternativas posibles (ej. "correo: jperez71 o jperez77").

Por tipo:
- INE: nombre completo, fecha de nacimiento, CURP y domicilio. Si el domicilio no trae calle, calle_numero = null.
- INE: también el año de vigencia (ej. "VIGENCIA 2021-2031" -> 2031).
- Estado de cuenta: del RESUMEN copia saldo inicial/anterior, total de depósitos/abonos, total de retiros/cargos y saldo
  final; los últimos 4 dígitos de la cuenta; y en evidencia_total el renglón LITERAL donde viene el total de abonos.
  Antes de responder comprueba tú mismo: saldo inicial + abonos - cargos = saldo final. Si no cuadra, vuelve a leer
  esos números con cuidado; si sigue sin cuadrar, deja lo que dice el documento y anótalo en `dudas`.
- Estado de cuenta: total_depositos_abonos = total de 'Depósitos'/'Abonos' del RESUMEN del periodo; copia el
  total impreso, no sumes tú. suma_abonos_movimientos solo si ves toda la tabla.
- Fechas YYYY-MM-DD. Montos como número sin $ ni comas. Celular a 10 dígitos."""

VERIFICAR = """Revisa de nuevo este documento con mucho cuidado, carácter por carácter.
Otra lectura obtuvo el JSON de abajo, pero tiene estos posibles problemas:
{problemas}

No te fíes de esa lectura: vuelve a leer TODO el documento desde la imagen y devuelve tu propia extracción.
Si un problema dice "falta", ese dato no se encontró: búscalo minuciosamente con todas sus etiquetas posibles, en todas
las páginas, encabezados, pies, márgenes y recuadros. Si de verdad no aparece, déjalo en null.
Corrige lo que esté mal. Si un campo sigue siendo dudoso, déjalo en `dudas` con las alternativas.

Lectura anterior:
{json}"""

# Campos que, si cambian entre lecturas, se marcan para revisión humana
CRITICOS = {"ine": ["nombre_completo", "fecha_nacimiento", "curp", "calle_numero", "colonia", "cp"],
            "solicitud": ["nombre_completo", "correo", "telefono_celular", "calle_numero", "colonia", "cp"],
            "cotizacion": ["modelo", "anio", "precio"],
            "estado_cuenta": ["total_depositos_abonos", "periodo_fin", "banco"],
            "comprobante_domicilio": ["titular", "calle_numero", "cp", "fecha_emision"]}


class ArchivoMalo(Exception):
    pass


def _bloques(data: bytes, mime: str, notas: list[str]) -> list[dict]:
    b64 = lambda b: base64.standard_b64encode(b).decode()
    if mime == "application/pdf":
        return [{"type": "document", "source": {"type": "base64", "media_type": mime, "data": b64(data)}}]
    problema = calidad_baja(data)
    if problema:
        raise ArchivoMalo(problema)
    orig, realzada, hechos = preparar_imagen(data, detectar_rotacion)
    notas.extend(hechos)
    img = lambda b: {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": b64(b)}}
    return [{"type": "text", "text": "Versión original:"}, img(orig),
            {"type": "text", "text": "Versión realzada:"}, img(realzada)]


def _leer(bloques: list[dict], instruccion: str) -> list[DocExtraction] | None:
    resp = client.messages.parse(
        model=MODEL, max_tokens=16000, system=SYSTEM,
        output_config={"effort": EFFORT},
        messages=[{"role": "user", "content": bloques + [{"type": "text", "text": instruccion}]}],
        output_format=Lectura,
    )
    if resp.stop_reason == "refusal" or resp.parsed_output is None:
        return None
    return resp.parsed_output.documentos or None


def faltantes(d: DocExtraction) -> list[str]:
    """Datos clave que quedaron vacíos (el reverso de la INE no trae nombre ni CURP: no cuenta)."""
    sec = getattr(d, d.tipo, None) if d.tipo in CLAVE else None
    if d.tipo == "otro" or (d.tipo == "ine" and "reverso" in (d.descripcion or "").lower()):
        return []
    if sec is None:
        return list(CLAVE[d.tipo])
    return [k for k in CLAVE[d.tipo] if getattr(sec, k) in (None, "")]


def _criticos(d: DocExtraction) -> dict:
    sec = getattr(d, d.tipo, None) if d.tipo in CRITICOS else None
    return {k: getattr(sec, k) for k in CRITICOS[d.tipo]} if sec else {}


def _texto_pdf(data: bytes) -> str:
    """Texto de un PDF digital (vacío si es escaneado o no se puede leer)."""
    try:
        import io
        from pypdf import PdfReader
        return "\n".join((pg.extract_text() or "") for pg in PdfReader(io.BytesIO(data)).pages[:40])
    except Exception:
        return ""


def _verificar_contra_pdf(docs: list[DocExtraction], texto: str):
    """En PDFs digitales el texto es exacto: confirma que los montos leídos estén ahí."""
    if len(texto.strip()) < 300:
        return
    for d in docs:
        e = d.estado_cuenta
        if d.tipo == "estado_cuenta" and e and e.total_depositos_abonos is not None and not monto_en_texto(e.total_depositos_abonos, texto):
            d.dudas.append(f"el total de abonos {e.total_depositos_abonos:,.2f} no aparece en el texto del PDF; revísalo")


def extraer_documentos(data: bytes, mime: str) -> tuple[list[DocExtraction], list[str]]:
    """Regresa (documentos_encontrados, ajustes_que_se_le_hicieron_a_la_foto)."""
    docs, notas = _extraer(data, mime)
    if mime == "application/pdf":
        _verificar_contra_pdf(docs, _texto_pdf(data))
    return docs, notas


def _extraer(data: bytes, mime: str) -> tuple[list[DocExtraction], list[str]]:
    notas: list[str] = []
    bloques = _bloques(data, mime, notas)
    l1 = _leer(bloques, "Clasifica y extrae los documentos de este archivo.")
    if not l1:
        return [DocExtraction(tipo="otro", legible=False, dudas=["No se pudo procesar este archivo"])], notas

    prob1 = [validar(d) for d in l1]
    problemas = [f"{d.tipo}: {x}" for d, p in zip(l1, prob1) for x in p + d.dudas]
    problemas += [f"{d.tipo}: falta {k.replace('_', ' ')}" for d in l1 for k in faltantes(d)]

    def sin_segunda():
        for d, p in zip(l1, prob1):
            d.dudas = list(dict.fromkeys(p + d.dudas))
        return l1, notas

    if not problemas or all(d.tipo == "otro" or not d.legible for d in l1):
        return sin_segunda()

    # Segunda lectura independiente, enfocada en lo dudoso
    l2 = _leer(bloques, VERIFICAR.format(problemas="\n".join(f"- {x}" for x in problemas),
                                          json=Lectura(documentos=l1).model_dump_json(indent=1)))
    if not l2:
        return sin_segunda()
    vistos: dict[str, int] = {}
    for d in l2:
        n = vistos.get(d.tipo, 0)
        vistos[d.tipo] = n + 1
        mismos = [x for x in l1 if x.tipo == d.tipo]
        par = mismos[n] if n < len(mismos) else None
        nuevos = validar(d) + d.dudas
        if par:
            c1, c2 = _criticos(par), _criticos(d)
            for k in c2:
                if c1.get(k) is not None and c1.get(k) != c2.get(k):
                    nuevos.append(f"{k}: 1a lectura '{c1[k]}', 2a lectura '{c2[k]}' (usé la 2a)")
        d.dudas = list(dict.fromkeys(nuevos))
    return l2, notas


def extraer(data: bytes, mime: str) -> tuple[DocExtraction, list[str]]:
    """Versión de un solo documento (la usa el bot de WhatsApp)."""
    docs, notas = extraer_documentos(data, mime)
    return docs[0], notas
