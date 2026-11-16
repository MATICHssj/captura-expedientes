"""Pruebas del arreglo automático de fotos con documentos sintéticos."""
import io
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from app.preprocess import angulo_inclinacion, girar, preparar_imagen, realzar, recortar_documento

FUENTE = ImageFont.load_default(size=30)


def hoja(w=1200, h=1600):
    img = Image.new("RGB", (w, h), "white")
    d = ImageDraw.Draw(img)
    for i, y in enumerate(range(80, h - 80, 60)):
        d.text((70, y), f"Nombre: JUAN PEREZ LOPEZ  calle 5 de mayo {i}23  col. Centro", fill="black", font=FUENTE)
    return np.array(img)[:, :, ::-1].copy()   # BGR


def sobre_mesa(doc):
    """Pone la hoja chueca (perspectiva) sobre una mesa oscura, como foto de celular."""
    h, w = doc.shape[:2]
    W, H = 2000, 2400
    src = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
    dst = np.float32([[300, 250], [1650, 380], [1750, 2150], [200, 2050]])
    M = cv2.getPerspectiveTransform(src, dst)
    mesa = np.full((H, W, 3), (40, 60, 90), np.uint8)
    out = cv2.warpPerspective(doc, M, (W, H), dst=mesa, borderMode=cv2.BORDER_TRANSPARENT)
    return out


def jpg(bgr):
    b = io.BytesIO(); Image.fromarray(bgr[:, :, ::-1]).save(b, "JPEG", quality=90); return b.getvalue()


def test_recorta_y_corrige_perspectiva():
    foto = sobre_mesa(hoja())
    rec, ok = recortar_documento(foto)
    assert ok
    h, w = rec.shape[:2]
    assert 1.05 < h / w < 1.6                    # vuelve a tener forma de hoja vertical (la perspectiva no da la proporción exacta)
    assert rec.mean() > 200                      # casi todo blanco: ya no hay mesa


def test_no_recorta_si_ya_es_solo_el_documento():
    _, ok = recortar_documento(hoja())
    assert not ok


def test_detecta_inclinacion():
    for ang in (-6.0, 3.0, 8.0):
        torcida = girar(hoja(), ang)
        medido = angulo_inclinacion(torcida)
        assert abs(medido + ang) < 0.6, (ang, medido)   # el ángulo para enderezar es el opuesto
    assert abs(angulo_inclinacion(hoja())) < 0.6


def test_quita_sombra():
    doc = hoja().astype(np.float32)
    sombra = np.linspace(0.35, 1.0, doc.shape[1])[None, :, None]    # lado izquierdo muy oscuro
    con_sombra = (doc * sombra).astype(np.uint8)
    limpio = realzar(con_sombra)
    izq, der = limpio[:, :200].mean(), limpio[:, -200:].mean()
    assert abs(izq - der) < 25                     # el fondo quedó parejo
    assert (limpio < 100).mean() > 0.01           # el texto sigue ahí


def test_pipeline_completo_foto_de_lado():
    """Hoja en perspectiva + de lado + inclinada 4°: el pipeline la deja derecha."""
    foto = np.rot90(sobre_mesa(girar(hoja(), 4))).copy()     # de lado
    llamado = {}

    def detector_falso(img):          # simula a Haiku: verifica que reciba la foto y responde "girar 270°"
        llamado["tam"] = img.size
        return 270

    orig, realz, notas = preparar_imagen(jpg(foto), detector_falso)
    assert "tam" in llamado
    final = Image.open(io.BytesIO(orig))
    assert final.height > final.width                        # quedó vertical
    assert any("recorté" in n for n in notas)
    assert any("de lado" in n for n in notas)
    assert any("inclinación" in n for n in notas), notas
    bgr = np.array(final)[:, :, ::-1]
    assert abs(angulo_inclinacion(bgr)) < 0.6                 # quedó derecha
