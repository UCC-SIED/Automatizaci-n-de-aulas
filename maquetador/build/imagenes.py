# -*- coding: utf-8 -*-
"""Recorte de la foto del docente centrado en el rostro.

La foto va en un círculo en la página de inicio (CSS: border-radius: 50% +
object-fit: cover), pero si la cara no está centrada en la foto original el
recorte automático del navegador la deja descentrada o con poco aire
alrededor. El equipo lo resuelve a mano con la herramienta de recorte
circular de Fotor: sube la foto, ubica el círculo sobre el rostro y descarga
el PNG. Acá se automatiza esa misma idea: detectar el rostro (Haar cascade
de OpenCV) y recortar un cuadrado centrado en él, con aire alrededor para
cuello/hombros — el círculo final lo sigue poniendo el CSS.
"""

from pathlib import Path

import cv2
import numpy as np
from PIL import Image

_CASCADA = cv2.CascadeClassifier(
    cv2.data.haarcascades + "haarcascade_frontalface_default.xml")

# Aire alrededor del rostro, como proporción de su tamaño (1.0 = el cuadrado
# de recorte mide el doble del rostro detectado, centrado en él).
_MARGEN_ROSTRO = 1.0


def _detectar_rostro(ruta: Path):
    """(x, y, w, h) del rostro más grande de la foto, o None si no hay.

    cv2.imread no abre rutas con acentos en Windows (todo el árbol del curso
    los tiene: "Gestión de la Calidad", "Módulo 1"…): se lee el archivo con
    Python y se decodifica el buffer, en vez de pasarle la ruta a OpenCV.
    """
    datos = np.fromfile(str(ruta), dtype=np.uint8)
    if datos.size == 0:
        return None
    img = cv2.imdecode(datos, cv2.IMREAD_COLOR)
    if img is None:
        return None
    gris = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    rostros = _CASCADA.detectMultiScale(
        gris, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60))
    if len(rostros) == 0:
        return None
    return max(rostros, key=lambda r: r[2] * r[3])


def recortar_rostro_circular(ruta: Path, destino: Path) -> Path:
    """Recorta `ruta` a un cuadrado centrado en el rostro detectado y lo
    guarda en `destino` como PNG. Sin rostro detectado, recorta centrado en
    la imagen completa (mismo resultado que el object-fit:cover de siempre,
    no hay regresión). Devuelve `destino`.
    """
    with Image.open(ruta) as im:
        img = im.convert("RGB")
    ancho, alto = img.size
    rostro = _detectar_rostro(ruta)
    if rostro is not None:
        x, y, w, h = (float(v) for v in rostro)
        cx, cy = x + w / 2, y + h / 2
        lado = max(w, h) * (1 + _MARGEN_ROSTRO)
    else:
        cx, cy = ancho / 2, alto / 2
        lado = min(ancho, alto)
    lado = min(lado, ancho, alto)
    izq = min(max(cx - lado / 2, 0), ancho - lado)
    arriba = min(max(cy - lado / 2, 0), alto - lado)
    recorte = img.crop((int(izq), int(arriba),
                        int(izq + lado), int(arriba + lado)))
    destino.parent.mkdir(parents=True, exist_ok=True)
    recorte.save(destino, "PNG")
    return destino
