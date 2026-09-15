# -*- coding: utf-8 -*-
"""Segmentación de DOCX a HTML por sección.

Convierte el DOCX completo a HTML (mammoth) y lo corta en los elementos cuyo
texto coincide con los títulos de sección que el reconciliador ya matcheó
contra la planilla. Funciona igual para títulos numerados ("1.3. Soluciones")
que para títulos sin numerar ("Onboarding digital: …"): el corte es por
coincidencia de texto normalizado, no por estilo ni numeración.

Bloques especiales que también se extraen:
  intro      : entre el marcador "Introducción" y "Objetivos"/primera sección
  objetivos  : entre "Objetivos…" y la primera sección
  conclusion : desde "Conclusión"/"Cierre" hasta referencias o el final
  referencias: desde "Referencias"/"Bibliografía" hasta el final
"""

import io
import logging
import re
from pathlib import Path

import mammoth
from bs4 import BeautifulSoup

from maquetador.ingest.folder_scanner import normalizar
from maquetador.ingest.docx_comments import extraer_comentarios, aplicar_comentarios

logger = logging.getLogger("segmenter")

# Mammoth solo mapea por defecto los estilos "Heading 1".."Heading 6" a <hN>.
# Los asesores también usan el estilo Word "Subtitle" (subtítulo debajo del
# título de sección) para subtítulos de nivel h3, y ese estilo NO tiene
# mapeo por defecto: sin esta regla, el párrafo queda como <p> suelto (sin
# negrita, sin marca alguna) y el resto del pipeline no tiene forma de
# reconocerlo como encabezado.
_MAMMOTH_STYLE_MAP = "p[style-name='Subtitle'] => h3:fresh"

_PAT_NUM = re.compile(r"^(\d+(?:\.\d+)+)\.?\s*")


class ImagenInline:
    """Acumula las imágenes embebidas del DOCX para empaquetarlas después."""

    def __init__(self):
        self.imagenes = []   # [(nombre, bytes, content_type)]

    def handler(self, image):
        with image.open() as f:
            data = f.read()
        ext = (image.content_type or "image/png").split("/")[-1]
        ext = {"jpeg": "jpg"}.get(ext, ext)
        nombre = f"img_{len(self.imagenes) + 1}.{ext}"
        self.imagenes.append((nombre, data, image.content_type))
        # La ruta definitiva la resuelve el empaquetador; placeholder estable.
        return {"src": f"__MEDIA__/{nombre}"}


def _texto_norm(el) -> str:
    return normalizar(el.get_text(" ", strip=True))


_PAT_NOTA = re.compile(r"\[\d+\]")


def _squash(texto: str) -> str:
    """Forma canónica para comparar títulos: minúsculas, sin acentos, solo
    letras y números. Inmune a los espacios que mammoth mete alrededor de
    los signos de puntuación ('endobranding :' vs 'endobranding:') y a las
    referencias de nota al pie que mammoth pega al título ('… Final [26]'),
    que la planilla no trae."""
    return re.sub(r"[^a-z0-9]+", "", normalizar(_PAT_NOTA.sub("", texto)))


def _clave_de_titulo(texto: str, marcadores: dict) -> str:
    """Devuelve la clave de sección si este texto es un título buscado."""
    t_squash = _squash(texto)
    t_sin_num = _squash(_PAT_NUM.sub("", texto.strip()))
    if not t_squash:
        return ""
    for clave, titulo in marcadores.items():
        m_squash = _squash(titulo)
        m_sin_num = _squash(_PAT_NUM.sub("", titulo.strip()))
        if t_squash == m_squash:
            return clave
        # El título del DOCX puede llevar numeración que la planilla no (o
        # al revés, p.ej. numeración automática de Word que mammoth omite).
        if t_sin_num and t_sin_num == m_sin_num:
            return clave
    return ""


def _aplanar_listas_con_titulos(soup, marcadores: dict):
    """Word con numeración automática → mammoth genera <ol><li> anidados que
    encierran títulos de sección (y a veces secciones enteras). Si una lista
    de nivel superior contiene un título buscado, se desarma: el contenido de
    cada <li> sube al nivel del documento (lo inline se envuelve en <p>).
    Se repite hasta que ningún título quede dentro de una lista."""
    _BLOQUES = ("p", "ol", "ul", "table", "h1", "h2", "h3", "h4", "h5", "h6", "div")

    def _contiene_titulo(lista) -> bool:
        for el in lista.find_all(["li", "strong", "p"]):
            if len(el.get_text(strip=True)) < 250 and \
                    _clave_de_titulo(el.get_text(" ", strip=True), marcadores):
                return True
        return False

    for _ in range(8):   # límite de profundidad por seguridad
        listas = [el for el in soup.find_all(["ol", "ul"], recursive=False)
                  if _contiene_titulo(el)]
        if not listas:
            break
        for lista in listas:
            nuevos = []
            for li in lista.find_all("li", recursive=False):
                inline = []
                for child in list(li.children):
                    nombre = getattr(child, "name", None)
                    if nombre in _BLOQUES:
                        if inline:
                            p = soup.new_tag("p")
                            for x in inline:
                                p.append(x)
                            nuevos.append(p)
                            inline = []
                        nuevos.append(child.extract())
                    else:
                        if str(child).strip():
                            inline.append(child.extract())
                if inline:
                    p = soup.new_tag("p")
                    for x in inline:
                        p.append(x)
                    nuevos.append(p)
            for nuevo in nuevos:
                lista.insert_before(nuevo)
            lista.decompose()


_MARCAS_ESPECIALES = (
    ("intro", re.compile(r"^introducci[óo]n\b")),
    ("objetivos", re.compile(r"^objetivos?\b|^objetivos? del m[óo]dulo")),
    # "Contenido:" abre la agenda/temario del módulo, que NO va en la página
    # de introducción (el aula ya muestra los módulos); se separa y descarta.
    ("agenda", re.compile(r"^contenidos?\s*:?\s*$|^temario\b|^agenda\b")),
    ("conclusion", re.compile(r"^conclusi[óo]n|^cierre\b|^reflexi[óo]n final")),
    ("referencias", re.compile(r"^referencias?\b|^bibliograf[íi]a")),
)

# Marcadores que solo abren el módulo (van ANTES de la primera sección numerada).
# Una vez que empezó una página real, un texto como "Objetivo financiero" es un
# sub-título del cuerpo, no el bloque "Objetivos" del módulo: no debe cambiar de
# sección. (Conclusión/referencias sí aparecen después de las secciones.)
_MARCAS_APERTURA = {"intro", "objetivos", "agenda"}


def segmentar_docx(docx_path: Path, marcadores: dict) -> tuple:
    """Corta el DOCX en secciones HTML.

    marcadores: {clave: texto_del_titulo_en_el_docx} — lo que matcheó el
    reconciliador (p.ej. {"1.1": "1.1. El problema de la corrupción",
    "3.1": "Onboarding digital: …"}).

    Devuelve ({clave: html}, [imagenes], [no_encontrados], [comentarios],
    [origenes_otra_pagina]). El 4º elemento son los pedidos de maquetación del
    asesor (comentarios del DOCX) que no se pudieron aplicar solos y hay que
    revisar/armar a mano. El 5º son los pedidos "va en otra página" que SÍ se
    aplicaron (ver aplicar_comentarios): [{"anclado", "pagina_origen", "html"}],
    con la clave de la sección de la que se sacó cada uno (la pista de dónde
    ubicar ese ítem —un foro, típicamente— en el flujo del módulo) y el HTML
    que se sacó (la consigna real, para cargarla en el ítem que corresponde).
    """
    img = ImagenInline()
    with open(docx_path, "rb") as f:
        html = mammoth.convert_to_html(
            f, convert_image=mammoth.images.img_element(img.handler),
            style_map=_MAMMOTH_STYLE_MAP).value
    soup = BeautifulSoup(html, "html.parser")
    _aplanar_listas_con_titulos(soup, marcadores)
    elementos = [el for el in soup.find_all(recursive=False)]

    secciones = {}
    clave_actual = None
    acumulado = []
    en_seccion_real = False   # ¿ya empezó una página numerada de la planilla?

    def _guardar():
        if clave_actual is not None and acumulado:
            previo = secciones.get(clave_actual, "")
            secciones[clave_actual] = previo + "".join(str(e) for e in acumulado)

    for i, el in enumerate(elementos):
        tn = _texto_norm(el)
        if not tn:
            acumulado.append(el)
            continue

        # ¿Es el título de una sección pedida?
        if len(tn) < 200:
            clave = _clave_de_titulo(tn, marcadores)
            if clave:
                _guardar()
                clave_actual = clave
                acumulado = []   # el título no va dentro del cuerpo
                en_seccion_real = True
                continue
            # ¿Es un marcador especial (intro/objetivos/conclusión/refs)?
            especial = next((nombre for nombre, pat in _MARCAS_ESPECIALES
                             if pat.match(tn)), "")
            # Los marcadores de apertura no valen una vez dentro de una página.
            if especial in _MARCAS_APERTURA and en_seccion_real:
                especial = ""
            if especial and len(tn) < 60:
                _guardar()
                clave_actual = especial
                acumulado = []
                continue

        # La tabla de metadatos con que arrancan algunos DOCX no es contenido.
        if clave_actual is None and el.name == "table" and i < 3:
            continue
        acumulado.append(el)

    _guardar()

    # Pedidos de maquetación del asesor (comentarios del DOCX): se aplican AHORA,
    # sobre cada sección ya cortada, para no romper los límites de sección.
    # Cada comentario se aplica en la sección que contiene su texto anclado.
    comentarios = extraer_comentarios(docx_path)
    # "otra_pagina" (p.ej. el foro "directamente en siguiente pág") se saca de
    # la sección que lo contiene, pero esa sección es justo la pista de dónde
    # debe ubicarse el ítem real (el foro) en el flujo del aula: se registra
    # qué clave lo contenía para que el builder pueda ordenar el módulo.
    origenes_otra_pagina = []
    if comentarios:
        for clave, html_sec in list(secciones.items()):
            soup_sec = BeautifulSoup(html_sec, "html.parser")
            aplicar_comentarios(soup_sec, comentarios)
            secciones[clave] = str(soup_sec)
            for c in comentarios:
                if c.get("accion") == "otra_pagina" and c.get("_aplicado") \
                        and not any(o["anclado"] == c["anclado"]
                                    for o in origenes_otra_pagina):
                    origenes_otra_pagina.append({
                        "anclado": c["anclado"], "pagina_origen": clave,
                        "html": c.get("_contenido_extraido", "")})
    comentarios_pendientes = [c for c in comentarios if not c.get("_aplicado")]

    no_encontrados = [c for c in marcadores if c not in secciones]
    return (secciones, img.imagenes, no_encontrados, comentarios_pendientes,
            origenes_otra_pagina)
