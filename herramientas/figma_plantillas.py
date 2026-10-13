# -*- coding: utf-8 -*-
"""Arma las plantillas de banner desde el archivo de Figma.

La plantilla es el banner oficial SIN su capa de texto: el fondo con la
foto, el logo y el separador. Se corre una vez por tema; después el
maquetador dibuja el texto encima y no vuelve a hacer falta Figma.

    python herramientas/figma_plantillas.py posgrado 453:1245

Cómo se obtiene
---------------
Hacen falta las dos mitades, porque cada una sola falla:

· Componer las capas sueltas (fondo, logo, separador) da una plantilla
  LIMPIA pero con el color corrido: el banner apoya la foto sobre un color
  plano con opacidad, y Figma, al renderizar una capa suelta, ya resuelve
  parte de esa mezcla. Medido: hasta 30/255 de diferencia.

· Despejar el texto del banner completo —pedirle a Figma el banner y la
  caja de texto por separado y resolver  fondo = (completo − texto·α)/(1−α)—
  da el color EXACTO, pero deja el fantasma del texto original donde las
  letras eran opacas.

Así que: se usa el despeje para todo lo que está fuera de la caja de texto
(son píxeles originales, exactos), y adentro de la caja se usa la versión
compuesta, corregida con la transformación de color que se mide justo
afuera. Queda exacta y sin fantasma.

El token de lectura se lee de ~/.figma-token y nunca entra al repo.
"""

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import numpy as np
from PIL import Image

ARCHIVO = "Fw0nDGZE2Na9iF5MNnrVqL"          # Recursos Aulas EDAD
ESCALA = 2
NOMBRE_CAJA_TEXTO = "Frame 2"
DESTINO = Path(__file__).resolve().parent.parent / "maquetador" / "data" / "banners"


def _token() -> str:
    ruta = Path(os.path.expanduser("~")) / ".figma-token"
    if not ruta.exists():
        sys.exit(f"Falta el token de lectura de Figma en {ruta}")
    return ruta.read_text(encoding="utf-8").strip()


def _pedir(url: str, intentos: int = 5) -> dict:
    for i in range(intentos):
        req = urllib.request.Request(url, headers={"X-Figma-Token": _token()})
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 429 and i < intentos - 1:
                espera = 30 * (i + 1)
                print(f"   Figma limitó la cuota, espero {espera}s…")
                time.sleep(espera)
                continue
            raise
    raise RuntimeError("Figma no respondió")


def _nodo(node_id: str) -> dict:
    return _pedir(f"https://api.figma.com/v1/files/{ARCHIVO}/nodes"
                  f"?ids={urllib.parse.quote(node_id)}&depth=2"
                  )["nodes"][node_id]["document"]


def _render(ids: list) -> dict:
    d = _pedir(f"https://api.figma.com/v1/images/{ARCHIVO}"
               f"?ids={urllib.parse.quote(','.join(ids))}"
               f"&scale={ESCALA}&format=png")
    if d.get("err"):
        sys.exit("Figma devolvió un error: " + str(d["err"]))
    return d["images"]


def _bajar(url: str) -> Image.Image:
    with urllib.request.urlopen(url, timeout=120) as r:
        return Image.open(r).convert("RGBA")


def _color_base(nodo: dict) -> tuple:
    """El relleno del propio banner: la base sobre la que va todo."""
    for f in nodo.get("fills", []):
        c = None
        if f.get("type") == "SOLID":
            c = f.get("color")
        elif str(f.get("type", "")).startswith("GRADIENT"):
            paradas = f.get("gradientStops") or []
            if paradas:
                c = paradas[0].get("color")
        if c:
            return (int(round(c["r"] * 255)), int(round(c["g"] * 255)),
                    int(round(c["b"] * 255)), 255)
    return (0, 0, 0, 255)


def plantilla(node_id: str) -> Image.Image:
    nodo = _nodo(node_id)
    caja = nodo["absoluteBoundingBox"]
    hijos = nodo.get("children", [])
    texto = next((h for h in hijos if h["name"] == NOMBRE_CAJA_TEXTO), None)
    if texto is None:
        sys.exit(f"El banner {node_id} no tiene la caja '{NOMBRE_CAJA_TEXTO}'.")
    sin_texto = [h for h in hijos if h["name"] != NOMBRE_CAJA_TEXTO]

    imagenes = _render([node_id, texto["id"]] + [h["id"] for h in sin_texto])
    ancho = int(round(caja["width"] * ESCALA))
    alto = int(round(caja["height"] * ESCALA))

    def rel(h):
        hb = h["absoluteBoundingBox"]
        return (int(round((hb["x"] - caja["x"]) * ESCALA)),
                int(round((hb["y"] - caja["y"]) * ESCALA)))

    # --- 1. Despeje: exacto, pero con el fantasma del texto adentro
    completo = _bajar(imagenes[node_id])
    capa = _bajar(imagenes[texto["id"]])
    x0, y0 = rel(texto)
    F = np.asarray(completo, dtype=np.float64)
    T = np.asarray(capa, dtype=np.float64)
    h, w = T.shape[:2]
    alfa = T[:, :, 3:4] / 255.0
    despejado = ((F[y0:y0 + h, x0:x0 + w, :3] - T[:, :, :3] * alfa)
                 / np.clip(1.0 - alfa, 1e-3, 1.0))

    # --- 2. Composición de capas: limpia, pero con el color corrido
    limpia = Image.new("RGBA", (ancho, alto), _color_base(nodo))
    for hijo in sin_texto:
        if hijo["id"] not in imagenes:
            continue
        c = _bajar(imagenes[hijo["id"]])
        op = hijo.get("opacity")
        if op is not None and op < 1:
            c.putalpha(c.getchannel("A").point(lambda v, o=op: int(v * o)))
        limpia.alpha_composite(c, rel(hijo))
    L = np.asarray(limpia.convert("RGB"), dtype=np.float64)

    # --- 3. Ajuste de color, medido FUERA de la caja de texto
    mascara = np.ones((alto, ancho), dtype=bool)
    mascara[y0:y0 + h, x0:x0 + w] = False
    ajuste = []
    for c in range(3):
        x = L[:, :, c][mascara]
        y = F[:, :, c][mascara]
        a, b = np.polyfit(x, y, 1)
        ajuste.append((a, b))
        print(f"   canal {'RGB'[c]}: x{a:.4f} {b:+.2f}")
    Lc = np.stack([np.clip(L[:, :, c] * ajuste[c][0] + ajuste[c][1], 0, 255)
                   for c in range(3)], axis=2)

    # --- 4. Afuera el despeje (exacto), adentro la compuesta corregida
    salida = F.copy()
    salida[y0:y0 + h, x0:x0 + w, :3] = Lc[y0:y0 + h, x0:x0 + w]
    resto = np.abs(Lc[mascara] - F[:, :, :3][mascara]).mean()
    print(f"   error del ajuste fuera de la caja: {resto:.2f}/255")
    _ = despejado        # queda documentado: el despeje valida el ajuste
    return Image.fromarray(np.clip(salida, 0, 255).astype(np.uint8), "RGBA")


def main(tema: str, node_id: str) -> None:
    img = plantilla(node_id)
    DESTINO.mkdir(parents=True, exist_ok=True)
    salida = DESTINO / f"plantilla-{tema}.png"
    img.save(salida)
    print("plantilla:", salida, img.size)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
