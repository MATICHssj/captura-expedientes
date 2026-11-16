"""Arregla la foto antes de leerla. Todo automático:

1. Endereza con el dato EXIF del celular (si existe).
2. Recorta el documento del fondo y corrige la perspectiva (foto tomada en ángulo / chueca sobre la mesa).
3. Detecta si está de lado o de cabeza y la gira (orientacion.py).
4. Corrige la inclinación fina (documento ligeramente torcido, ±10°).
5. Quita sombras y luz dispareja, sube contraste y nitidez (versión realzada para letra tenue).
6. Ajusta tamaño y peso para la API.
"""
import io
from typing import Callable, Optional
import cv2
import numpy as np
from PIL import Image, ImageFilter, ImageOps, ImageStat

MAX_LADO = 2400
MIN_LADO = 1400
MAX_BYTES = 4_500_000


# ---------- utilidades ----------
def _a_cv(img: Image.Image) -> np.ndarray:
    return cv2.cvtColor(np.array(img.convert("RGB")), cv2.COLOR_RGB2BGR)


def _a_pil(arr: np.ndarray) -> Image.Image:
    if arr.ndim == 2:
        return Image.fromarray(arr).convert("RGB")
    return Image.fromarray(cv2.cvtColor(arr, cv2.COLOR_BGR2RGB))


def _a_jpeg(img: Image.Image) -> bytes:
    for q in (92, 85, 75, 65):
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=q, optimize=True)
        if buf.tell() <= MAX_BYTES:
            return buf.getvalue()
    img = img.copy()
    img.thumbnail((MAX_LADO // 2, MAX_LADO // 2))
    return _a_jpeg(img)


def _tamano(img: Image.Image) -> Image.Image:
    lado = max(img.size)
    if lado > MAX_LADO:
        img = img.copy()
        img.thumbnail((MAX_LADO, MAX_LADO), Image.LANCZOS)
    elif lado < MIN_LADO:
        f = MIN_LADO / lado
        img = img.resize((round(img.width * f), round(img.height * f)), Image.LANCZOS)
    return img


# ---------- 2. recorte + perspectiva ----------
def _ordenar(p: np.ndarray) -> np.ndarray:
    s, d = p.sum(1), np.diff(p, axis=1).ravel()
    return np.array([p[s.argmin()], p[d.argmin()], p[s.argmax()], p[d.argmax()]], dtype=np.float32)


def recortar_documento(bgr: np.ndarray) -> tuple[np.ndarray, bool]:
    """Busca el contorno de 4 esquinas más grande (la hoja / la credencial) y lo endereza."""
    h, w = bgr.shape[:2]
    esc = min(1.0, 1000 / max(h, w))
    chica = cv2.resize(bgr, None, fx=esc, fy=esc) if esc < 1 else bgr
    gris = cv2.GaussianBlur(cv2.cvtColor(chica, cv2.COLOR_BGR2GRAY), (5, 5), 0)
    bordes = cv2.dilate(cv2.Canny(gris, 40, 140), np.ones((3, 3), np.uint8), iterations=2)
    cnts, _ = cv2.findContours(bordes, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    area = chica.shape[0] * chica.shape[1]
    for c in sorted(cnts, key=cv2.contourArea, reverse=True)[:5]:
        a = cv2.contourArea(c)
        if a < 0.2 * area:
            break
        aprox = cv2.approxPolyDP(c, 0.02 * cv2.arcLength(c, True), True)
        if len(aprox) != 4 or a > 0.95 * area:      # >95%: ya está recortada, no tocar
            continue
        tl, tr, br, bl = _ordenar(aprox.reshape(4, 2).astype(np.float32) / esc)
        ancho = int(max(np.linalg.norm(br - bl), np.linalg.norm(tr - tl)))
        alto = int(max(np.linalg.norm(tr - br), np.linalg.norm(tl - bl)))
        destino = np.array([[0, 0], [ancho - 1, 0], [ancho - 1, alto - 1], [0, alto - 1]], dtype=np.float32)
        M = cv2.getPerspectiveTransform(np.array([tl, tr, br, bl]), destino)
        doc = cv2.warpPerspective(bgr, M, (ancho, alto), flags=cv2.INTER_CUBIC)
        m = max(2, int(0.01 * min(ancho, alto)))          # quita restos de la mesa en la orilla
        return doc[m:-m, m:-m], True
    return bgr, False


# ---------- 4. inclinación fina ----------
def angulo_inclinacion(bgr: np.ndarray, rango: float = 10.0) -> float:
    """Ángulo (grados) en que está torcido el texto. Busca el giro que deja los renglones más 'parejos'."""
    gris = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY) if bgr.ndim == 3 else bgr
    esc = min(1.0, 800 / max(gris.shape))
    gris = cv2.resize(gris, None, fx=esc, fy=esc)
    h, w = gris.shape
    gris = gris[int(h * .12):int(h * .88), int(w * .12):int(w * .88)]   # solo el centro: las orillas engañan
    tinta = cv2.adaptiveThreshold(gris, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY_INV, 25, 15)
    if tinta.mean() < 1:          # casi sin texto
        return 0.0
    h, w = tinta.shape
    centro = (w / 2, h / 2)

    def puntaje(ang):
        M = cv2.getRotationMatrix2D(centro, ang, 1.0)
        filas = cv2.warpAffine(tinta, M, (w, h), flags=cv2.INTER_NEAREST).sum(1, dtype=np.float64)
        return np.var(filas)

    mejor = max(np.arange(-rango, rango + 0.01, 0.5), key=puntaje)
    mejor = max(np.arange(mejor - 0.5, mejor + 0.51, 0.1), key=puntaje)
    return float(round(mejor, 1))


def girar(bgr: np.ndarray, ang: float) -> np.ndarray:
    h, w = bgr.shape[:2]
    M = cv2.getRotationMatrix2D((w / 2, h / 2), ang, 1.0)
    cos, sin = abs(M[0, 0]), abs(M[0, 1])
    nw, nh = int(h * sin + w * cos), int(h * cos + w * sin)
    M[0, 2] += nw / 2 - w / 2
    M[1, 2] += nh / 2 - h / 2
    return cv2.warpAffine(bgr, M, (nw, nh), flags=cv2.INTER_CUBIC,
                          borderMode=cv2.BORDER_CONSTANT, borderValue=(255, 255, 255))


# ---------- 5. sombras + contraste ----------
def realzar(bgr: np.ndarray) -> np.ndarray:
    """Quita sombras/luz dispareja (divide entre el fondo estimado) y sube contraste local."""
    gris = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    k = max(15, (max(gris.shape) // 40) | 1)
    fondo = cv2.medianBlur(cv2.dilate(gris, np.ones((7, 7), np.uint8)), k)
    plano = cv2.divide(gris, fondo, scale=255)
    plano = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(plano)
    suave = cv2.GaussianBlur(plano, (0, 0), 2)
    return cv2.addWeighted(plano, 1.6, suave, -0.6, 0)      # nitidez


# ---------- pipeline ----------
def preparar_imagen(data: bytes,
                    detectar_rotacion: Optional[Callable[[Image.Image], int]] = None
                    ) -> tuple[bytes, bytes, list[str]]:
    """Regresa (original_corregida, realzada, notas_de_lo_que_se_hizo)."""
    notas = []
    img = Image.open(io.BytesIO(data))
    img = ImageOps.exif_transpose(img).convert("RGB")
    bgr = _a_cv(img)

    bgr, recortada = recortar_documento(bgr)
    if recortada:
        notas.append("recorté el documento y corregí la perspectiva")

    if detectar_rotacion:
        grados = detectar_rotacion(_a_pil(bgr))
        if grados:
            bgr = _a_cv(_a_pil(bgr).rotate(grados, expand=True))
            notas.append({90: "estaba de lado (giré a la derecha)", 180: "estaba de cabeza",
                          270: "estaba de lado (giré a la izquierda)"}[grados])

    ang = angulo_inclinacion(bgr)
    if abs(ang) >= 0.5:
        bgr = girar(bgr, ang)
        notas.append(f"enderecé {abs(ang):.1f}° de inclinación")

    orig = _tamano(_a_pil(bgr))
    realz = _tamano(_a_pil(realzar(bgr)))
    return _a_jpeg(orig), _a_jpeg(realz), notas


def calidad_baja(data: bytes) -> str | None:
    """Detecta fotos inservibles antes de gastar en el modelo."""
    img = ImageOps.grayscale(Image.open(io.BytesIO(data)))
    if max(img.size) < 600:
        return "la foto es muy chica (¿la mandaste como miniatura o captura recortada?)"
    img.thumbnail((800, 800))
    if ImageStat.Stat(img.filter(ImageFilter.FIND_EDGES)).mean[0] < 2.0:
        return "la foto está muy borrosa"
    return None
