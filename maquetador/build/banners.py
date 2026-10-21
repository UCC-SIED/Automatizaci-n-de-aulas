# -*- coding: utf-8 -*-
"""Render de los banners de aula, con el diseño oficial de la UCC.

El diseño vive en Figma ("Recursos Aulas EDAD") y hasta ahora los banners
se generaban a mano con un plugin: el asesor cargaba la planilla, capturaba
los frames, exportaba un ZIP y alguien lo subía a Canvas página por página.

Acá se arma el mismo banner con las piezas que el propio Figma entrega:
el fondo y el logo salen renderizados de su API y quedan como plantilla, y
el texto se dibuja encima con las medidas exactas del componente —tipografía
Montserrat, los mismos cuerpos, interlineados, colores y posiciones que el
archivo de diseño declara. La plantilla no se inventa: es el render del
diseño sin la capa de texto.

Medidas del componente "Portada de HEADER AULA" (1080x217 a escala 1):

    Bg-Banner   (0, 0)      1080x248   fondo con la foto
    Frame 5     (33, 33)    268x151    logo
    Line 2      (334, 33)   0x151      separador vertical, 1.378 de grosor
    Frame 2     (367, 33)   680x151    caja del texto, centrada en vertical,
                                       11.02 de padding izquierdo y 11.02
                                       entre renglones del bloque
"""

import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# Todo se arma al doble y se entrega así: es lo que exporta el plugin y lo
# que se ve nítido en una pantalla retina.
ESCALA = 2
ANCHO, ALTO = 1080, 217

_DIR_DATOS = Path(__file__).resolve().parent.parent / "data"
FUENTE = _DIR_DATOS / "fuentes" / "Montserrat-variable.ttf"
PLANTILLAS = _DIR_DATOS / "banners"

# Colores y medidas que declara el archivo de Figma.
COLOR_TEXTO = "#FCFCFC"
# El separador (amarillo #F4E600 en posgrado, #BAC0DB en educación) viene
# dibujado en la plantilla: no se redibuja acá.
CAJA_X, CAJA_Y = 367.123779296875, 33.061279296875
CAJA_ANCHO, CAJA_ALTO = 679.8148803710938, 150.8775634765625
PADDING_IZQ = 11.020407676696777
ESPACIO_ENTRE = 11.020407676696777

# Los dos renglones del banner de módulo. El de sección usa solo el título.
TIPO_ROTULO = ("Bold", 22.040815353393555, 33.061222076416016)
TIPO_TITULO = ("SemiBold", 33.061222076416016, 44.08163070678711)


def _fuente(variante: str, tamano: float) -> ImageFont.FreeTypeFont:
    f = ImageFont.truetype(str(FUENTE), int(round(tamano * ESCALA)))
    f.set_variation_by_name(variante)
    return f


def _cortar_en_lineas(texto: str, fuente, ancho_max: float) -> list:
    """Corta como Figma: por palabra, respetando el ancho de la caja."""
    lineas, actual = [], ""
    for palabra in texto.split():
        prueba = (actual + " " + palabra).strip()
        if actual and fuente.getlength(prueba) > ancho_max:
            lineas.append(actual)
            actual = palabra
        else:
            actual = prueba
    if actual:
        lineas.append(actual)
    return lineas


def _plantilla(tema: str) -> Image.Image:
    """Fondo + logo renderizados del diseño, sin la capa de texto."""
    ruta = PLANTILLAS / f"plantilla-{tema}.png"
    if not ruta.exists():
        raise FileNotFoundError(
            f"Falta la plantilla del banner para '{tema}' ({ruta}). "
            "Se genera con herramientas/figma_plantillas.py.")
    return Image.open(ruta).convert("RGBA")


def render(titulo: str, rotulo: str = "", tema: str = "posgrado") -> Image.Image:
    """Un banner. `rotulo` es el renglón chico de arriba ("Módulo 1")."""
    # La plantilla ya trae el fondo, el logo y el separador: es el render
    # del componente sin su capa de texto.
    img = _plantilla(tema)
    dib = ImageDraw.Draw(img)

    # Bloque de texto: se arma primero para poder centrarlo en vertical.
    ancho_texto = (CAJA_ANCHO - PADDING_IZQ * 2) * ESCALA
    bloques = []
    if rotulo:
        variante, cuerpo, interlineado = TIPO_ROTULO
        f = _fuente(variante, cuerpo)
        bloques.append((_cortar_en_lineas(rotulo, f, ancho_texto), f,
                        interlineado * ESCALA))
    variante, cuerpo, interlineado = TIPO_TITULO
    f = _fuente(variante, cuerpo)
    bloques.append((_cortar_en_lineas(titulo, f, ancho_texto), f,
                    interlineado * ESCALA))

    alto_total = sum(len(ls) * il for ls, _f, il in bloques)
    alto_total += ESPACIO_ENTRE * ESCALA * (len(bloques) - 1)

    x_texto = (CAJA_X + PADDING_IZQ) * ESCALA
    y = (CAJA_Y * ESCALA) + (CAJA_ALTO * ESCALA - alto_total) / 2
    for i, (lineas, fuente, interlineado) in enumerate(bloques):
        if i:
            y += ESPACIO_ENTRE * ESCALA
        for linea in lineas:
            # El renglón se centra dentro de su propio interlineado, que es
            # como lo resuelve Figma.
            caja = fuente.getbbox(linea)
            y_linea = y + (interlineado - (caja[3] - caja[1])) / 2 - caja[1]
            dib.text((x_texto, y_linea), linea, font=fuente, fill=COLOR_TEXTO)
            y += interlineado
    return img


_PAT_NUMERO = re.compile(r"^\s*(\d+(?:\.\d+)*)\.?\s*(.*)$", re.S)


def banner_de_pagina(titulo: str, tema: str = "posgrado") -> Image.Image:
    """Banner de una página de contenido: "1.3.1. La arquitectura…"."""
    return render(titulo.strip(), tema=tema)


def banner_de_modulo(numero: int, nombre: str, tema: str = "posgrado"):
    """Banner de módulo: "Módulo 1" arriba y el nombre abajo."""
    return render(nombre.strip(), rotulo=f"Módulo {numero}", tema=tema)
