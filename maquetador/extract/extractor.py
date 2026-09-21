# -*- coding: utf-8 -*-
"""Extracción del contenido HTML para cada ítem del plan.

Recorre los módulos del CourseSpec, segmenta cada DOCX una sola vez y
asigna el HTML resultante a los ítems (páginas, texto introductorio).
Las imágenes embebidas quedan registradas para el empaquetado.
"""

import logging
from collections import defaultdict
from pathlib import Path

from maquetador.models import CourseSpec, TipoItem, Issue, Severidad
from maquetador.extract.segmenter import segmentar_docx

logger = logging.getLogger("extractor")


def extraer_contenido(spec: CourseSpec) -> dict:
    """Llena item.fuente.html para los ítems con sección matcheada.

    Devuelve {nombre_imagen: (bytes, content_type)} con las imágenes
    embebidas de todos los DOCX, con nombres prefijados por módulo.
    """
    media = {}

    for modulo in spec.modulos:
        # Agrupar los ítems de este módulo por DOCX de origen
        por_docx = defaultdict(list)
        for item in modulo.items:
            if item.fuente.archivo and item.fuente.archivo.suffix.lower() == ".docx" \
                    and item.tipo in (TipoItem.PAGINA, TipoItem.INTRO_MODULO):
                por_docx[item.fuente.archivo].append(item)

        for docx_path, items in por_docx.items():
            marcadores = {}
            for item in items:
                titulo_docx = item.detalle.get("titulo_docx")
                if titulo_docx:
                    marcadores[f"item_{item.orden}"] = titulo_docx

            try:
                secciones, imagenes, faltantes, comentarios, origenes_otra_pagina = \
                    segmentar_docx(Path(docx_path), marcadores)
            except Exception as e:
                spec.issues.append(Issue(Severidad.BLOQUEANTE,
                    f"Error segmentando '{docx_path.name}': {e}",
                    f"Módulo {modulo.numero}"))
                continue

            for nombre, data, ctype in imagenes:
                media[f"m{modulo.numero}_{nombre}"] = (data, ctype)

            # Contenido (típicamente un foro) que el asesor marcó "va en otra
            # página": no es de esta página, pero sí es la consigna real de
            # otro ítem del módulo (un foro sin DOCX propio, escrito adentro
            # de la lectura) — el builder lo usa para cargar ese ítem Y para
            # ubicarlo justo después de la página de la que se sacó.
            if origenes_otra_pagina:
                pagina_por_clave = {f"item_{it.orden}": it for it in items}
                lista = getattr(modulo, "extras_otra_pagina", [])
                for o in origenes_otra_pagina:
                    pagina = pagina_por_clave.get(o["pagina_origen"])
                    lista.append({
                        "html": o["html"].replace(
                            "__MEDIA__/", f"__MEDIA__/m{modulo.numero}_"),
                        "pagina_titulo": pagina.detalle.get("titulo_docx", "")
                                         if pagina else "",
                    })
                modulo.extras_otra_pagina = lista

            # Pedidos de maquetación del asesor (comentarios del DOCX) que no se
            # aplicaron solos: se avisan para armarlos a mano en la revisión.
            for c in comentarios:
                etiqueta = {"acordeon": "armar un ACORDEÓN (editor DesignPLUS)",
                            "flip_card": "armar una FLIP CARD (editor DesignPLUS)",
                            "tabs": "armar TABS (editor DesignPLUS)",
                            "expander": "armar un EXPANDER",
                            "tooltip": "armar un TOOLTIP",
                            "cita": "marcar como CITA",
                            "quiz": "crear QUIZ/autoevaluación en Canvas (manual)",
                            "video": "insertar VIDEO desde Canvas Studio (manual)",
                            "quitar": "QUITAR contenido",
                            "faltante": "⚠ FALTA algo"}.get(
                                c["accion"], "revisar pedido")
                spec.issues.append(Issue(Severidad.AVISO,
                    f"El asesor pidió ({etiqueta}): «{c['instruccion'][:70]}» "
                    f"sobre «{(c['anclado'] or '?')[:60]}».",
                    f"Módulo {modulo.numero} (comentario del DOCX)"))

            for item in items:
                clave = f"item_{item.orden}"
                if item.tipo == TipoItem.INTRO_MODULO:
                    if secciones.get("intro"):
                        item.fuente.html = secciones["intro"].replace(
                            "__MEDIA__/", f"__MEDIA__/m{modulo.numero}_")
                    if secciones.get("objetivos"):
                        item.detalle["objetivos_html"] = secciones["objetivos"].replace(
                            "__MEDIA__/", f"__MEDIA__/m{modulo.numero}_")
                elif item.fuente.seccion == "conclusion":
                    # La planilla pide la conclusión como página propia:
                    # se consume acá (el builder ya no la anexa a la última).
                    if secciones.get("conclusion"):
                        item.fuente.html = secciones["conclusion"].replace(
                            "__MEDIA__/", f"__MEDIA__/m{modulo.numero}_")
                elif clave in secciones:
                    html = secciones[clave]
                    # Renombrar las imágenes al espacio del módulo
                    html = html.replace("__MEDIA__/", f"__MEDIA__/m{modulo.numero}_")
                    item.fuente.html = html
                elif clave in faltantes:
                    item.issues.append(Issue(Severidad.AVISO,
                        f"La sección matcheó en el análisis pero no pude "
                        f"cortarla del DOCX ('{item.detalle.get('titulo_docx', '')[:50]}').",
                        item.titulo))

            # Conclusión/referencias/intro-objetivos del módulo: disponibles
            # aunque la planilla no traiga una fila explícita para ellas (la
            # Introducción del módulo es una página FIJA del aula base, no
            # algo opcional que la planilla decida incluir) — quedan en el
            # spec como respaldo por si ningún ítem ya las consumió.
            extras = {k: v.replace("__MEDIA__/", f"__MEDIA__/m{modulo.numero}_")
                      if k in ("intro", "objetivos") else v
                      for k, v in secciones.items()
                      if k in ("conclusion", "referencias", "intro", "objetivos") and v}
            if extras:
                modulo_extras = getattr(modulo, "extras", {})
                modulo_extras.update(extras)
                modulo.extras = modulo_extras

    return media


def resumen_extraccion(spec: CourseSpec) -> str:
    L = []
    for modulo in spec.modulos:
        L.append(f"Módulo {modulo.numero}:")
        for item in modulo.items:
            if item.tipo in (TipoItem.PAGINA, TipoItem.INTRO_MODULO):
                n = len(item.fuente.html or "")
                marca = "✅" if n > 200 else ("⚠" if n else "⛔")
                L.append(f"  {marca} {item.titulo[:60]:62s} {n:7,} chars")
        extras = getattr(modulo, "extras", {})
        for k, v in extras.items():
            L.append(f"  ℹ (extra) {k:54s} {len(v):7,} chars")
    return "\n".join(L)
