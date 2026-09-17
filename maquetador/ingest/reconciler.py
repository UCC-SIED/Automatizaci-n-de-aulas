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
    spec.issues.extend(inv.issues)
    # Las figuras de DISEÑO las usa el generador para reemplazar las
    # imágenes embebidas de los DOCX (mejor calidad).
    spec.imagenes_diseno = list(inv.imagenes_diseno)
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
                ref = item.detalle.get("referencia") or item.detalle.get("item_planilla", item.titulo)
                archivo, score = _match_archivo(ref, cand)
                # Un foro de apertura/presentación matchea con un DOCX de foro
                # cuyo nombre lo indica, aunque la 'referencia' de la planilla
                # sea una URL de Google Docs (inútil para matchear por nombre) y
                # el nombre del archivo traiga el sufijo del docente que baja el
                # parecido textual por debajo del umbral del generador.
                titulo_foro = normalizar(
                    item.titulo + " " + item.detalle.get("item_planilla", ""))
                _KW_APERTURA = ("apertura", "presentacion", "bienvenida",
                               "introductorio", "introduccion")
                if any(k in titulo_foro for k in _KW_APERTURA):
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
                ref = item.detalle.get("referencia") or item.titulo
                archivo, score = _match_archivo(ref, cand)
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
