# -*- coding: utf-8 -*-
"""Reconciliación: cruza la planilla de estructura (qué debería tener el aula)
con el inventario de archivos (qué llegó) y los perfiles de los DOCX
(qué secciones hay realmente).

La planilla suele llegar incompleta, así que NO se confía ciegamente en
ninguna fuente: cada ítem queda con su fuente asignada y una confianza.
Lo que no matchea queda marcado como issue para revisión humana, nunca
se adivina en silencio.
"""

import re
from difflib import SequenceMatcher
from pathlib import Path

from maquetador.models import (CourseSpec, TipoItem, FuenteContenido,
                               Issue, Severidad)
from maquetador.ingest.folder_scanner import InventarioCurso, normalizar
from maquetador.ingest.docx_probe import perfilar_docx, PerfilDocx

_PAT_NUM = re.compile(r"^(\d+)\.((?:\d+\.)*\d+)\.?\s*(.*)")


def _similitud(a: str, b: str) -> float:
    """Similitud tolerante al reordenamiento y a las repeticiones.

    Los asesores escriben el título de la planilla y el del DOCX con las
    mismas palabras en otro orden ("Tasa de interés nominal. Tasa de interés
    real. Tasa de interés efectiva." vs "Tasa de interés nominal, real y
    efectiva"): el ratio de secuencia se hunde y el conjunto de palabras no.
    Se toma el mayor de los dos.
    """
    na, nb = normalizar(a), normalizar(b)
    seq = SequenceMatcher(None, na, nb).ratio()
    ta = {w for w in re.findall(r"\w+", na) if len(w) > 2}
    tb = {w for w in re.findall(r"\w+", nb) if len(w) > 2}
    jac = len(ta & tb) / len(ta | tb) if ta and tb else 0.0
    return max(seq, jac)


def _match_archivo(nombre_ref: str, candidatos: list) -> tuple:
    """Busca el archivo más parecido a una referencia textual.
    candidatos: list[Path] o list[(num, Path)]. Devuelve (Path|None, score)."""
    mejor, score = None, 0.0
    for c in candidatos:
        p = c[1] if isinstance(c, tuple) else c
        s = _similitud(nombre_ref, p.stem)
        if s > score:
            mejor, score = p, s
    return mejor, score


def _por_modulo(candidatos: list, num: int) -> list:
    """Filtra una lista [(num|None, Path)] por número de módulo."""
    return [(n, p) for n, p in candidatos if n == num]


# La columna "referencia" de la planilla no siempre nombra un archivo. A
# veces dice DÓNDE escribió el docente la consigna dentro de la lectura
# ("Final del 1.2 pág. 9", "En 2.1, pag 4", "3.2.1, p. 8", "En la
# lectura") y a veces pega el link de Drive del documento. Buscar un DOCX
# con ese texto da basura: en Metodología II el foro "Nuevas subjetividades"
# se quedaba con el DOCX del foro de apertura —y lo publicaba dos veces— y
# la "Actividad obligatoria 2" no encontraba su archivo, que estaba al
# lado, porque la referencia era una URL de Google Docs.
_PAT_REF_URL = re.compile(r"https?://", re.I)
_PAT_REF_EN_LA_LECTURA = re.compile(
    r"^\s*en\s+(?:la\s+lectura|el\s+m[oó]dulo)\s*$"
    r"|\bp(?:[áa]g\.?|\.)\s*\d+"
    r"|^\s*(?:final\s+del?\s+|en\s+el\s+|en\s+)?\d+\.\d+",
    re.I)

# Un foro de apertura es del curso, no de un módulo, y su DOCX sí existe
# aparte: la regla de "la consigna está en la lectura" no lo alcanza.
_KW_APERTURA_FORO = ("apertura", "presentacion", "bienvenida",
                     "introductorio", "introduccion")


# Prefijo de área/carrera con que el equipo nombra las carpetas de Drive
# ("Ed. Especial - Metodología…"). No es parte del nombre de la asignatura.
_PAT_PREFIJO_AREA = re.compile(
    r"^\s*(?:ed\.?\s*especial|educaci[óo]n\s+especial|posgrado|grado|"
    r"lic\.?|licenciatura|mgter\.?|maestr[ií]a)\s*[-–—:]\s*", re.I)


def _nombre_publicado(nombre_planilla: str, nombre_carpeta: str, spec) -> str:
    """El nombre de la asignatura que se publica en el aula.

    Manda la planilla, salvo que la CARPETA nombre la asignatura con más
    palabras: ahí la planilla la está abreviando. En Metodología II la
    planilla dice "Metodología de la investigación II (Lic. en Gestión de
    la Educación Especial)" y la carpeta "Ed. Especial - Metodología de la
    Investigación Educativa II" —que es como se llama el aula—.

    La carpeta NO gana cuando dice lo mismo: viene de Drive y a veces llega
    sin acentos ("Creacion de Valor en la Economia de la Experiencia"), y
    ahí la planilla está mejor escrita.
    """
    from maquetador.build.imscc_builder import nombre_de_asignatura
    planilla = nombre_de_asignatura(nombre_planilla)
    carpeta = nombre_de_asignatura(_PAT_PREFIJO_AREA.sub("", nombre_carpeta or ""))
    if not carpeta:
        return planilla
    if not planilla:
        return carpeta
    pal_planilla = set(normalizar(planilla).split())
    pal_carpeta = set(normalizar(carpeta).split())
    if pal_planilla < pal_carpeta:      # la carpeta dice todo eso y algo más
        spec.issues.append(Issue(Severidad.INFO,
            f"Nombre de la asignatura tomado de la carpeta ('{carpeta}'): la "
            f"planilla la abrevia ('{planilla}').", "Página de inicio"))
        return carpeta
    return planilla


_PAT_TITULO_NUMERADO = re.compile(r"^\s*(\d+(?:\.\d+)*)\.?\s*(.*)$", re.S)


def _sin_adornos(texto: str) -> str:
    """El título comparable: sin acentos, sin mayúsculas y sin la puntuación
    de los bordes."""
    return normalizar(texto).strip(" .,;:")


def _elegir_titulo_de_pagina(item, titulo_docx: str) -> None:
    """Deja en `item.titulo` el título que va a salir publicado.

    Gana el de la LECTURA cuando la docente reescribió el encabezado de
    verdad —en Metodología II, la planilla pedía "3.2.2. Observación y
    observación participativa: condiciones y particularidades" y la lectura
    traía "3.2.2. La observación como medio de representar la realidad"—.
    Gana el de la planilla cuando la diferencia es solo de puntuación,
    mayúsculas o acentos: es lo mismo escrito distinto, y cambiarlo movería
    el título de páginas ya entregadas sin ninguna ganancia.

    La NUMERACIÓN sale siempre de la planilla, que es la que ordena el aula.
    """
    if not titulo_docx or not titulo_docx.strip():
        return
    m_planilla = _PAT_TITULO_NUMERADO.match(item.titulo.strip())
    m_docx = _PAT_TITULO_NUMERADO.match(titulo_docx.strip())
    if not (m_planilla and m_docx):
        return
    texto_planilla, texto_docx = m_planilla.group(2), m_docx.group(2)
    if not texto_docx.strip() or _sin_adornos(texto_planilla) == _sin_adornos(texto_docx):
        return
    from maquetador.ingest.xlsx_parser import _sin_punto_final
    item.titulo = f"{m_planilla.group(1)}. {_sin_punto_final(texto_docx.strip())}"
    item.detalle["titulo_planilla_original"] = texto_planilla
    item.issues.append(Issue(Severidad.INFO,
        f"Título tomado de la lectura: la planilla decía "
        f"'{texto_planilla[:60]}'.", item.titulo[:60]))


def _referencia_nombra_archivo(ref: str) -> bool:
    """¿La referencia de la planilla sirve para buscar un archivo?"""
    if not ref or not ref.strip():
        return False
    if _PAT_REF_URL.search(ref):
        return False
    return not _PAT_REF_EN_LA_LECTURA.search(ref)


def _fila_plantilla_vacia(item) -> bool:
    """En el formato nuevo la planilla trae filas de plantilla (Tarea/Foro/
    Evaluación) que el asesor dejó sin completar. Si no hay título de
    actividad, ni referencia, ni estado, no es un ítem real del aula."""
    d = item.detalle
    es_generico = item.titulo == d.get("item_planilla", item.titulo)
    if es_generico and not d.get("referencia") and not item.estado_planilla \
            and item.titulo.strip().lower() in ("tarea", "foro", "evaluación",
                                                "evaluacion", "foro de consultas afi"):
        item.detalle["plantilla_vacia"] = True
        item.issues.append(Issue(Severidad.INFO,
            "Fila de plantilla sin completar en el XLSX; no se maqueta "
            "(confirmar si corresponde crearla en Canvas).", item.titulo))
        return True
    return False


def reconciliar(spec: CourseSpec, inv: InventarioCurso) -> CourseSpec:
    spec.carpeta_origen = inv.raiz
    # Si el nombre vino del título/archivo de la planilla (no es el del curso),
    # se usa el de la carpeta. Cubre "Estructura general - Para maquetación".
    _n = (spec.nombre or "").lower()
    if not spec.nombre or any(k in _n for k in ("estructura", "para maquetacion",
                                                "para maquetación", "planilla")):
        spec.nombre = inv.nombre_curso
    spec.nombre = _nombre_publicado(spec.nombre, inv.nombre_curso, spec)
    spec.issues.extend(inv.issues)
    # Las figuras de DISEÑO las usa el generador para reemplazar las
    # imágenes embebidas de los DOCX (mejor calidad).
    spec.imagenes_diseno = list(inv.imagenes_diseno)
    # Archivos sueltos de la carpeta que el asesor puede estar enlazando
    # desde una actividad (el protocolo de transparencia, una plantilla):
    # el builder los adjunta al paquete si alguien los enlaza de verdad.
    spec.adjuntos = list(inv.otros)
    spec.fotos_docente = list(inv.fotos_docente)
    # Repositorio de casos: las fichas se suben como archivos del curso (la
    # planilla las pide como repositorio, no como página de contenido). Se
    # prefiere el PDF —la versión que sale de diseño— sobre el DOCX fuente.
    def _clave_caso(path):
        """'Modulo 3 - Ficha_Caso_Quibi.docx.pdf' y 'M3 - Ficha_Caso_Quibi.docx'
        son el mismo caso: la clave es el nombre del caso, no el archivo."""
        m = re.search(r"caso[_\s-]+(.+)$", path.stem, re.I)
        base = (m.group(1) if m else path.stem)
        return re.sub(r"[^a-z0-9]", "", base.lower().replace(".docx", ""))

    _con_pdf = {_clave_caso(p) for _n, p in inv.casos if p.suffix.lower() == ".pdf"}
    spec.casos = [p for _n, p in inv.casos
                  if p.suffix.lower() == ".pdf" or _clave_caso(p) not in _con_pdf]
    spec.recursos_html = [p for _n, p in inv.recursos_html]
    spec.material_suelto = list(inv.otros)

    perfiles = {}  # {num_modulo: PerfilDocx}
    for num, path in inv.docx_modulos.items():
        try:
            perfiles[num] = perfilar_docx(path)
        except Exception as e:
            spec.issues.append(Issue(Severidad.BLOQUEANTE,
                f"No pude leer el DOCX del módulo {num} ({path.name}): {e}"))

    # ---------- Ítems de inicio ----------
    for item in spec.items_inicio:
        n = normalizar(item.detalle.get("item_planilla", item.titulo))
        if "programa" in n:
            pdfs = [p for p in inv.programa if p.suffix.lower() == ".pdf"]
            item.fuente = FuenteContenido(
                archivo=(pdfs or inv.programa or [None])[0],
                confianza=0.9 if (pdfs or inv.programa) else 0.0)
        elif "hoja de ruta" in n:
            item.fuente = FuenteContenido(
                archivo=(inv.hoja_de_ruta or [None])[0],
                confianza=0.9 if inv.hoja_de_ruta else 0.0)
        elif "esquema" in n:
            item.fuente = FuenteContenido(
                archivo=(inv.esquema or [None])[0],
                confianza=0.85 if inv.esquema else 0.0)
        elif "fotografia" in n:
            item.fuente = FuenteContenido(
                archivo=(inv.fotos_docente or [None])[0],
                confianza=0.7 if inv.fotos_docente else 0.0)
        elif "titulacion" in n or "biografia" in n:
            item.fuente = FuenteContenido(
                archivo=(inv.biografia or [None])[0],
                confianza=0.85 if inv.biografia else 0.0)
        elif "video" in n:
            item.issues.append(Issue(Severidad.INFO,
                "Los videos se cargan en Canvas Studio; queda como paso manual.",
                item.titulo))
            continue
        if item.fuente.archivo is None and item.tipo != TipoItem.VIDEO:
            item.issues.append(Issue(Severidad.AVISO,
                "No encontré un archivo para este ítem en la carpeta del curso.",
                item.titulo))

    # ---------- Módulos ----------
    for modulo in spec.modulos:
        perfil = perfiles.get(modulo.numero)
        docx_mod = inv.docx_modulos.get(modulo.numero)
        ctx = f"Módulo {modulo.numero}"

        if perfil is None:
            spec.issues.append(Issue(Severidad.BLOQUEANTE,
                f"No hay DOCX de desarrollo teórico para el módulo {modulo.numero}.",
                ctx))
        elif not modulo.titulo:
            # 1) La plantilla institucional del DOCX trae "Nombre del módulo"
            #    en su tabla de metadatos: fuente más confiable. Se usa aunque
            #    coincida con el nombre de la asignatura (caso de 1 módulo: el
            #    equipo titula "Módulo 1: <nombre de la asignatura>").
            meta_titulo = perfil.metadatos.get("nombre del módulo") \
                or perfil.metadatos.get("nombre del modulo") or ""
            if meta_titulo:
                modulo.titulo = meta_titulo
            else:
                # 2) Deducirlo del nombre del archivo
                limpio = re.sub(r"m[óo]dulo\s*\d+\s*[-–:_]*", "", docx_mod.stem,
                                flags=re.I).strip(" -–_")
                limpio = re.sub(r"\(.*?\)", "", limpio).strip(" -–_.")
                limpio = re.sub(r"[-_\s]m\s?\d+\b", "", limpio, flags=re.I).strip(" -–_.")
                if len(limpio) > 8 and "_" not in limpio \
                        and _similitud(limpio, spec.nombre) < 0.75:
                    modulo.titulo = limpio
                else:
                    spec.issues.append(Issue(Severidad.AVISO,
                        f"El módulo {modulo.numero} no tiene título ni en la "
                        f"planilla ni en los metadatos del DOCX. Completar a mano.",
                        ctx))

        # El DOCX también declara el docente; útil si la planilla no lo trae
        if perfil and not spec.docentes:
            docente = perfil.metadatos.get("docente", "")
            if docente:
                spec.docentes.append(docente)

        secciones_usadas = set()
        for item in modulo.items:
            ctx_item = f"{ctx} > {item.titulo[:60]}"

            if item.tipo == TipoItem.PAGINA:
                if perfil is None:
                    continue
                m = _PAT_NUM.match(item.detalle.get("item_planilla", item.titulo))
                fuente = FuenteContenido(archivo=docx_mod)
                if m:
                    num_planilla = f"{modulo.numero}.{m.group(2)}"
                    titulo_planilla = m.group(3) or item.titulo
                    # 1) match exacto por número
                    cand = [s for s in perfil.secciones
                            if s.numero == num_planilla
                            or s.numero == f"{m.group(1)}.{m.group(2)}"]
                    if cand:
                        fuente.seccion = cand[0].numero
                        fuente.confianza = min(
                            0.95, 0.7 + 0.25 * _similitud(titulo_planilla, cand[0].titulo))
                        item.detalle["titulo_docx"] = cand[0].texto_completo
                        _elegir_titulo_de_pagina(item, cand[0].texto_completo)
                    elif normalizar(titulo_planilla).startswith("conclusi") \
                            and perfil.tiene_conclusion:
                        # La planilla pide la conclusión como página propia y el
                        # DOCX la trae como bloque de cierre (sin numerar).
                        fuente.seccion = "conclusion"
                        fuente.confianza = 0.85
                    else:
                        # 2) match por similitud de título contra secciones
                        #    numeradas Y candidatos sin numerar
                        mejor, score, es_numerada = None, 0.0, True
                        for s in perfil.secciones:
                            sc = _similitud(titulo_planilla, s.titulo)
                            if sc > score:
                                mejor, score, es_numerada = s, sc, True
                        for c in perfil.candidatos:
                            sc = _similitud(titulo_planilla, c.titulo)
                            if sc > score:
                                mejor, score, es_numerada = c, sc, False
                        umbral = 0.55 if es_numerada else 0.7
                        if mejor and score >= umbral:
                            fuente.seccion = (mejor.numero if es_numerada
                                              else f"título: {mejor.titulo[:60]}")
                            fuente.confianza = round(score * 0.9, 2)
                            item.detalle["titulo_docx"] = (
                                mejor.texto_completo if es_numerada else mejor.titulo)
                            _elegir_titulo_de_pagina(
                                item, item.detalle["titulo_docx"])
                            if score < 0.85:
                                item.issues.append(Issue(Severidad.AVISO,
                                    f"Asigné por similitud de título ({score:.0%}): "
                                    f"planilla '{num_planilla} {titulo_planilla[:50]}' → "
                                    f"DOCX '{mejor.titulo[:60]}'. Verificar.", ctx_item))
                        else:
                            disponibles = [f"{s.numero} {s.titulo[:40]}"
                                           for s in perfil.secciones
                                           if s.numero not in secciones_usadas]
                            item.issues.append(Issue(Severidad.BLOQUEANTE,
                                f"No encontré en el DOCX una sección que corresponda a "
                                f"'{item.titulo}'. Secciones numeradas disponibles: "
                                + (", ".join(disponibles) or "ninguna"),
                                ctx_item))
                if fuente.seccion:
                    secciones_usadas.add(fuente.seccion)
                item.fuente = fuente

            elif item.tipo == TipoItem.INTRO_MODULO:
                if perfil and perfil.tiene_intro:
                    item.fuente = FuenteContenido(
                        archivo=docx_mod, seccion="intro", confianza=0.9)
                else:
                    item.issues.append(Issue(Severidad.AVISO,
                        "El DOCX del módulo no tiene un bloque 'Introducción' "
                        "detectable.", ctx_item))

            elif item.tipo == TipoItem.FORO:
                if _fila_plantilla_vacia(item):
                    continue
                cand = _por_modulo(inv.foros, modulo.numero) or inv.foros
                ref_planilla = item.detalle.get("referencia") or ""
                es_apertura = any(
                    k in normalizar(item.titulo + " "
                                    + item.detalle.get("item_planilla", ""))
                    for k in _KW_APERTURA_FORO)
                # La consigna la escribió el docente dentro de la lectura y
                # la planilla solo dice en qué punto: no hay archivo que
                # buscar, y buscarlo igual termina en el DOCX de otro foro.
                if ref_planilla and not es_apertura \
                        and not _referencia_nombra_archivo(ref_planilla):
                    item.issues.append(Issue(Severidad.INFO,
                        f"La consigna de este foro está en la lectura "
                        f"({ref_planilla}): se toma del DOCX del módulo y no "
                        "de un archivo aparte.", ctx_item))
                    continue
                ref = (ref_planilla if _referencia_nombra_archivo(ref_planilla)
                       else item.detalle.get("item_planilla", item.titulo))
                archivo, score = _match_archivo(ref, cand)
                # Un foro de apertura/presentación matchea con un DOCX de foro
                # cuyo nombre lo indica, aunque la 'referencia' de la planilla
                # sea una URL de Google Docs (inútil para matchear por nombre) y
                # el nombre del archivo traiga el sufijo del docente que baja el
                # parecido textual por debajo del umbral del generador.
                _KW_APERTURA = _KW_APERTURA_FORO
                if es_apertura:
                    # El foro de apertura/introductorio es de curso (sin número
                    # de módulo), así que se busca en TODOS los foros, no solo
                    # en los del módulo actual.
                    dedicado = next(
                        (p for _n, p in inv.foros
                         if any(k in normalizar(p.stem) for k in _KW_APERTURA)), None)
                    if dedicado:
                        archivo, score = dedicado, max(score, 0.9)
                    else:
                        # Sin archivo que se llame "apertura/presentación": el
                        # foro de apertura es de curso, así que un DOCX de foro
                        # SIN número de módulo es mejor candidato que el del
                        # módulo 1 (que es el foro obligatorio de ese módulo).
                        sueltos = [p for n, p in inv.foros if n is None]
                        if sueltos:
                            suelto, sc = _match_archivo(ref, sueltos)
                            archivo, score = suelto, max(sc, 0.7)
                            item.issues.append(Issue(Severidad.AVISO,
                                f"Foro de apertura asignado a '{archivo.name}' "
                                "por ser el único DOCX de foro sin módulo. "
                                "Verificar.", ctx_item))
                # Si el título del foro (una frase con entidad, p.ej. "Akio
                # Toyoda y la crisis Toyota") aparece dentro del nombre del DOCX,
                # es el foro dedicado a ese tema aunque el parecido global no
                # llegue al umbral (el archivo trae prefijos como "Foro
                # Participativo - ").
                titulo_item = normalizar(item.titulo)
                if archivo is not None and len(titulo_item) >= 12 \
                        and titulo_item in normalizar(archivo.stem):
                    score = max(score, 0.9)
                if archivo:
                    item.fuente = FuenteContenido(archivo=archivo,
                                                  confianza=round(max(score, 0.5), 2))
                else:
                    item.issues.append(Issue(Severidad.AVISO,
                        "No encontré el DOCX de este foro.", ctx_item))

            elif item.tipo in (TipoItem.TAREA, TipoItem.EVALUACION):
                if _fila_plantilla_vacia(item):
                    continue
                cand = _por_modulo(inv.actividades, modulo.numero) or inv.actividades
                # Con una URL de Drive en la referencia hay que buscar por el
                # título del ítem: la "Actividad obligatoria 2" de Metodología
                # II quedaba sin fuente teniendo su DOCX en la carpeta.
                ref_planilla = item.detalle.get("referencia") or ""
                ref = (ref_planilla if _referencia_nombra_archivo(ref_planilla)
                       else item.titulo)
                archivo, score = _match_archivo(ref, cand)
                # Si el título del ítem está textual dentro del nombre del
                # archivo, es ese y no hay duda: el parecido global lo diluye
                # el sufijo que esta cátedra le pone a todos los archivos
                # ("… (Metodología de la Investigación II- Adriana Di
                # Francesco)"). "Actividad obligatoria 2" matcheaba su propio
                # DOCX al 44% y el builder lo saltaba por baja confianza,
                # dejando el buzón del módulo 3 con el placeholder del aula
                # base. Es el mismo refuerzo que ya usan los foros.
                titulo_item = normalizar(item.titulo)
                if archivo is not None and len(titulo_item) >= 12 \
                        and titulo_item in normalizar(archivo.stem):
                    score = max(score, 0.9)
                en_modulo = _por_modulo(inv.actividades, modulo.numero)
                if archivo and score >= 0.3:
                    item.fuente = FuenteContenido(archivo=archivo,
                                                  confianza=round(score, 2))
                elif len(en_modulo) == 1:
                    # Un solo DOCX de actividad para este módulo: es ese.
                    item.fuente = FuenteContenido(archivo=en_modulo[0][1],
                                                  confianza=0.6)
                    item.issues.append(Issue(Severidad.INFO,
                        f"Única actividad del módulo: asigné '{en_modulo[0][1].name}'.",
                        ctx_item))
                elif len(en_modulo) > 1:
                    item.issues.append(Issue(Severidad.AVISO,
                        "Hay varios DOCX de actividad para este módulo y no pude "
                        "decidir cuál corresponde: "
                        + ", ".join(p.name for _, p in en_modulo), ctx_item))
                elif ref_planilla and not _referencia_nombra_archivo(ref_planilla) \
                        and not _PAT_REF_URL.search(ref_planilla):
                    # Igual que con los foros: la consigna la escribió el
                    # docente dentro de la lectura y la planilla solo dice
                    # en qué punto ("en 1.3, p. 14"). No falta ningún
                    # archivo, así que no es un aviso.
                    item.issues.append(Issue(Severidad.INFO,
                        f"La consigna de esta actividad está en la lectura "
                        f"({ref_planilla}): se toma del DOCX del módulo y no "
                        "de un archivo aparte.", ctx_item))
                else:
                    item.issues.append(Issue(Severidad.AVISO,
                        "No pude asociar esta actividad con un DOCX de la carpeta.",
                        ctx_item))

            elif item.tipo == TipoItem.VIDEO:
                item.issues.append(Issue(Severidad.INFO,
                    "Video: se carga en Canvas Studio (paso manual).", ctx_item))

        # Secciones del DOCX que la planilla no pide
        if perfil:
            sobrantes = [s for s in perfil.secciones if s.numero not in secciones_usadas]
            for s in sobrantes:
                spec.issues.append(Issue(Severidad.AVISO,
                    f"El DOCX del módulo {modulo.numero} tiene la sección "
                    f"'{s.numero} {s.titulo}' que la planilla no menciona. "
                    "¿Debe ir al aula?", ctx))

    # ---------- AFI ----------
    for item in spec.afi:
        if _fila_plantilla_vacia(item):
            continue
        if item.tipo in (TipoItem.TAREA, TipoItem.EVALUACION, TipoItem.OTRO):
            cand = [(n, p) for n, p in inv.actividades
                    if re.search(r"(afi|integradora)", normalizar(p.name))] or inv.actividades
            ref = item.detalle.get("referencia") or item.titulo
            archivo, score = _match_archivo(ref, cand)
            if archivo:
                item.fuente = FuenteContenido(archivo=archivo,
                                              confianza=round(max(score, 0.5), 2))
            else:
                item.issues.append(Issue(Severidad.AVISO,
                    "No encontré el DOCX de la actividad final integradora.",
                    item.titulo))

    return spec
