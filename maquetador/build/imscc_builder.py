# -*- coding: utf-8 -*-
"""Generador del paquete .imscc a partir del CourseSpec con contenido extraído.

Estrategia: clonar el aula base del tema elegido (que ya trae foros,
autoevaluaciones, actividades, encuesta y diseño aprobados) y reemplazar
quirúrgicamente lo que es contenido del curso:

  por cada módulo N:
    - Introducción MN      → se sobreescribe con intro + objetivos del DOCX
    - placeholder "N.1."   → se reemplaza por las K páginas de contenido reales
    - Bibliografía MN      → se sobreescribe con las referencias del DOCX
    - título "Módulo N: …" → título real

Las imágenes embebidas de los DOCX van a web_resources/Multimedia cargada/
Generadas/ y se registran en el manifiesto. Lo que el aula base trae y la
planilla no pide (foros, autoevaluaciones) queda intacto: se configura en
Canvas como siempre.
"""

import logging
import re
import shutil
import uuid
import zipfile
from pathlib import Path

from xml.sax.saxutils import escape as xml_escape, unescape as xml_unescape
import xml.etree.ElementTree as ET

import warnings

import mammoth
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning

# Leemos XML de topics/quizzes con el parser HTML de BeautifulSoup a propósito
# (solo medimos longitud de texto); silenciamos el aviso correspondiente.
warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

from maquetador.models import CourseSpec, TipoItem, Issue, Severidad
from maquetador.build.pages import (slugify, pagina_intro, pagina_contenido,
                                    pagina_bibliografia)
from maquetador.build.snippets import (separar_consignas, procesar_contenido,
                                       indexar_figuras_diseno,
                                       reemplazar_figuras_diseno,
                                       maquetar_actividad,
                                       _FIG_CLASES_ESTATICA)
from maquetador.build.bibliography import construir_bibliografia
from maquetador.extract.segmenter import ImagenInline, _MAMMOTH_STYLE_MAP
from maquetador.ingest.folder_scanner import normalizar
from maquetador.ingest.docx_comments import extraer_comentarios, aplicar_comentarios
from processors.cidilabs_builder import DP_WRAPPER_CLASSES

logger = logging.getLogger("imscc_builder")

BASE_DIR = Path(__file__).resolve().parent.parent.parent
TEMAS = {
    "educacion": BASE_DIR / "Elementos de las aulas" / "_extracted_educacion",
    "posgrado": BASE_DIR / "Elementos de las aulas" / "_extracted_posgrado",
}
MEDIA_SUBDIR = "web_resources/Multimedia cargada/Generadas"
MEDIA_URL = "$IMS-CC-FILEBASE$/Multimedia%20cargada/Generadas"


def _gen_id() -> str:
    return "g" + uuid.uuid4().hex


def _genero_texto(texto: str) -> str:
    """Infiere género ('m'/'f'/None) por marcadores en la bio del docente, para
    elegir 'Profesor autor' vs 'Profesora autora'. Conservador: solo decide si
    hay evidencia clara mayoritaria."""
    t = normalizar(texto)
    fem = len(re.findall(
        r"\b(doctora|licenciada|profesora|investigadora|directora|abogada|"
        r"ingeniera|contadora|magistra|egresada|graduada|especialista en|nacida|"
        r"autora|docente e investigadora)\b", t))
    masc = len(re.findall(
        r"\b(doctor|licenciado|profesor|investigador|director|abogado|ingeniero|"
        r"contador|magister|egresado|graduado|nacido|autor)\b", t))
    if masc > fem:
        return "m"
    if fem > masc:
        return "f"
    return None


def _elegir_foto_docente(candidatas: list, nombre: str):
    """De las fotos candidatas, la que más se parece al retrato del docente.

    En la carpeta de grabación conviven la foto del profesor con fotogramas y
    capturas; el escáner ya descarta los nombres que se delatan, pero cuando
    quedan varias hay que elegir bien: gana la que menciona el nombre o el
    apellido del docente. Si ninguna lo menciona, la primera (orden estable).
    """
    if not candidatas:
        return None
    partes = [normalizar(p) for p in (nombre or "").split() if len(p) >= 4]
    if partes:
        for path in candidatas:
            stem = normalizar(path.stem)
            if any(p in stem for p in partes):
                return path
    return candidatas[0]


def _leer(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _escribir(path: Path, texto: str):
    path.write_text(texto, encoding="utf-8")


def _extraer_identifier(html: str) -> str:
    m = re.search(r'<meta name="identifier" content="([^"]+)"', html)
    return m.group(1) if m else _gen_id()


def _extraer_banner(html: str) -> str:
    m = re.search(r'class="dp-banner-image">\s*<img[^>]*src="([^"]+)"', html)
    return m.group(1) if m else ""


def _buscar_archivo_wiki(working: Path, patron: str) -> Path:
    cand = sorted((working / "wiki_content").glob(patron))
    return cand[0] if cand else None


def _copytree_longpath(src: Path, dst: Path) -> None:
    r"""shutil.copytree con soporte de rutas largas en Windows (prefijo \\?\).

    El proyecto se usa en Windows, pero el prefijo se aplica solo si el SO es
    ese: aplicado a una ruta POSIX queda '\\?\/home/...', que no existe, y
    entonces os.walk no itera y la copia sale VACÍA sin lanzar ningún error —
    el fallo recién aparece más tarde, al leer el imsmanifest. Fallar en
    silencio es peor que no soportarlo. (Mismo criterio que _rmtree_longpath.)
    """
    import os
    src_s = str(src.resolve())
    dst_s = str(dst.resolve())
    es_windows = os.name == "nt"
    lp_src = "\\\\?\\" + src_s if es_windows and not src_s.startswith("\\\\") else src_s
    lp_dst = "\\\\?\\" + dst_s if es_windows and not dst_s.startswith("\\\\") else dst_s

    for root, dirs, files in os.walk(lp_src):
        rel = root[len(lp_src):].lstrip("\\/")
        dest_dir = os.path.join(lp_dst, rel) if rel else lp_dst
        os.makedirs(dest_dir, exist_ok=True)
        for f in files:
            src_file = os.path.join(root, f)
            dst_file = os.path.join(dest_dir, f)
            try:
                import shutil as _shutil
                _shutil.copy2(src_file, dst_file)
            except Exception:
                # último recurso: lectura/escritura binaria
                with open(src_file, "rb") as fin, open(dst_file, "wb") as fout:
                    fout.write(fin.read())


def _rmtree_longpath(path: Path) -> None:
    r"""shutil.rmtree con soporte de rutas largas en Windows (prefijo \\?\).

    Los nombres de página del aula base pueden superar los 260 caracteres de
    MAX_PATH; shutil.rmtree normal falla al recorrerlos (WinError 3) y deja el
    working dir a medio borrar, rompiendo la siguiente generación."""
    import os
    if not path.exists():
        return
    p = str(path.resolve())
    lp = "\\\\?\\" + p if os.name == "nt" and not p.startswith("\\\\") else p
    # Borrado bottom-up: primero archivos, después carpetas ya vacías.
    for root, dirs, files in os.walk(lp, topdown=False):
        for f in files:
            try:
                os.chmod(os.path.join(root, f), 0o777)
            except OSError:
                pass
            try:
                os.remove(os.path.join(root, f))
            except OSError:
                pass
        for d in dirs:
            try:
                os.rmdir(os.path.join(root, d))
            except OSError:
                pass
    try:
        os.rmdir(lp)
    except OSError:
        pass


class GeneradorAula:
    def __init__(self, spec: CourseSpec, media: dict, output_dir: Path):
        self.spec = spec
        self.media = media          # {nombre: (bytes, content_type)}
        self.output_dir = Path(output_dir)
        self.working = None
        self.manifest = ""
        self.meta = ""
        self.recursos_nuevos = []   # [(identifier, href)]
        self.topics_escritos = set()       # rids de foros ya llenados
        self.assignments_escritos = set()  # rids de actividades ya llenadas
        self._reorders_pendientes = []     # [(rid, pagina_titulo)] p/ organizations
        self.paginas_por_modulo = {}       # {n: [(page_id, titulo)]} para el syllabus
        self.indice_diseno = indexar_figuras_diseno(
            getattr(spec, "imagenes_diseno", []))
        self.figuras_usadas = set()        # paths de DISEÑO aprovechados

    # ------------------------------------------------------------------ #
    def generar(self) -> Path:
        spec = self.spec
        base = TEMAS.get(spec.tema)
        if not base or not base.is_dir():
            raise ValueError(f"No existe el aula base para el tema '{spec.tema}'")

        nombre_corto = (spec.codigo or re.sub(r"[^A-Za-z0-9]+", "_",
                                              spec.nombre)[:40]).strip("_")
        self.working = self.output_dir / f"working_{nombre_corto}"
        if self.working.exists():
            _rmtree_longpath(self.working)
        _copytree_longpath(base, self.working)
        logger.info(f"Aula base '{spec.tema}' clonada en {self.working}")

        self.manifest = _leer(self.working / "imsmanifest.xml")
        self.meta = _leer(self.working / "course_settings" / "module_meta.xml")

        self._titulo_curso()
        self._asegurar_modulos()
        for modulo in spec.modulos:
            self._procesar_modulo(modulo)
        self._eliminar_modulos_sobrantes()
        self._eliminar_encuesta_valoracion()
        self._limpiar_recursos_no_usados()
        self._inyectar_afi()
        self._avisar_recursos_vacios()
        self._personalizar_inicio()
        self._construir_syllabus()
        self._empaquetar_media()
        self._unificar_tema_wrapper()
        self._registrar_recursos()
        self._renumerar_posiciones()
        # Con todos los archivos válidos ya en su sitio, cualquier <resource>
        # que apunte a un archivo inexistente es basura (módulos eliminados o
        # referencias colgadas que el aula base ya traía): se elimina.
        self._purgar_referencias_rotas()

        _escribir(self.working / "imsmanifest.xml", self.manifest)
        _escribir(self.working / "course_settings" / "module_meta.xml", self.meta)

        # Chequeos finales sobre el paquete YA armado: para que estos errores
        # aparezcan en los avisos de esta misma corrida (los mismos que ya se
        # leen siempre) en vez de descubrirse recién al importar en Canvas.
        self._validar_xml_generado()
        self._avisar_contenido_duplicado()

        salida = self.output_dir / f"{nombre_corto}.imscc"
        with zipfile.ZipFile(salida, "w", zipfile.ZIP_DEFLATED) as zf:
            for f in sorted(self.working.rglob("*")):
                if f.is_file():
                    zf.write(f, f.relative_to(self.working))
        logger.info(f"Paquete generado: {salida}")
        return salida

    # ------------------------------------------------------------------ #
    def _titulo_curso(self):
        nombre = self.spec.nombre
        if not nombre:
            return
        nombre = xml_escape(nombre)
        self.manifest = re.sub(
            r"(<lomimscc:title>\s*<lomimscc:string[^>]*>)[^<]*(</lomimscc:string>)",
            lambda m: m.group(1) + nombre + m.group(2), self.manifest, count=1)
        settings = self.working / "course_settings" / "course_settings.xml"
        if settings.exists():
            txt = _leer(settings)
            txt = re.sub(r"(<title>)[^<]*(</title>)",
                         lambda m: m.group(1) + nombre + m.group(2), txt, count=1)
            _escribir(settings, txt)

    # ------------------------------------------------------------------ #
    def _procesar_modulo(self, modulo):
        n = modulo.numero
        ctx = f"Módulo {n}"

        # --- título del módulo ---
        if modulo.titulo:
            titulo_full = xml_escape(f"Módulo {n}: {modulo.titulo}")
            patron = re.compile(rf"<title>\s*M[óo]dulo\s*{n}\s*:[^<]*</title>")
            self.manifest = patron.sub(lambda _: f"<title>{titulo_full}</title>", self.manifest)
            self.meta = patron.sub(lambda _: f"<title>{titulo_full}</title>", self.meta)

        # --- Introducción MN ---
        # Preferí el ítem de planilla si existe (puede traer objetivos_html
        # curados a mano); si la planilla no listó una fila de introducción
        # para este módulo, la página se llena igual desde el respaldo en
        # extras (el DOCX del módulo siempre trae Introducción/Objetivos al
        # principio — es una página fija del aula base, no algo opcional).
        intro_item = next((i for i in modulo.items
                           if i.tipo == TipoItem.INTRO_MODULO and i.fuente.html), None)
        extras_mod = getattr(modulo, "extras", {})
        if intro_item:
            intro_html = intro_item.fuente.html
            objetivos_html = intro_item.detalle.get("objetivos_html", "")
        else:
            intro_html = extras_mod.get("intro", "")
            objetivos_html = extras_mod.get("objetivos", "")
        archivo_intro = _buscar_archivo_wiki(self.working, f"introduccion-m{n}*.html")
        if intro_html and archivo_intro:
            viejo = _leer(archivo_intro)
            nuevo = pagina_intro(
                titulo=f"Introducción M{n}",
                intro_html=self._rutear_media(intro_html),
                objetivos_html=self._rutear_media(objetivos_html),
                banner_src=_extraer_banner(viejo),
                identifier=_extraer_identifier(viejo),
                tema=self.spec.tema)
            _escribir(archivo_intro, nuevo)
            logger.info(f"  [M{n}] Introducción sobreescrita")
        elif intro_html:
            self.spec.issues.append(Issue(Severidad.AVISO,
                f"No encontré 'introduccion-m{n}*.html' en el aula base.", ctx))

        # --- figuras de DISEÑO reemplazan a las embebidas del DOCX ---
        if self.indice_diseno:
            for item in modulo.items:
                if item.fuente.html:
                    item.fuente.html = reemplazar_figuras_diseno(
                        item.fuente.html, n, self.indice_diseno,
                        self.figuras_usadas)

        # --- consignas embebidas en el contenido → al recurso de Canvas ---
        consignas = []
        for item in modulo.items:
            if item.fuente.html:
                nuevo_html, cs = separar_consignas(item.fuente.html)
                if cs:
                    item.fuente.html = nuevo_html
                    consignas.extend(cs)
        foros_emb = [(t, b) for tipo, t, b in consignas if tipo == "foro"]
        if foros_emb:
            self._inyectar_consigna_foro(n, foros_emb, ctx)
        # Un DOCX dedicado de actividad (p.ej. "Actividad obligatoria I.docx")
        # manda sobre un puntero embebido en el texto ("te invito a realizar la
        # actividad obligatoria…"): si el módulo trae el archivo, se deja el slot
        # para él y no se vuelca la consigna embebida, que suele ser solo un
        # anuncio de un par de líneas y pisaría al contenido real.
        hay_docx_actividad = any(
            it.tipo == TipoItem.TAREA and it.fuente.archivo
            and it.fuente.archivo.suffix.lower() == ".docx"
            for it in modulo.items)
        for tipo, titulo, body in consignas:
            if tipo == "actividad":
                if hay_docx_actividad:
                    self.spec.issues.append(Issue(Severidad.INFO,
                        f"El puntero embebido '{titulo[:50]}' no se volcó: el "
                        f"módulo {n} trae la actividad como DOCX dedicado, que "
                        "es el que se carga.", ctx))
                    continue
                self._inyectar_consigna_actividad(n, titulo, body, ctx)
            elif tipo == "autoevaluacion":
                extras = getattr(modulo, "extras", {})
                extras[f"autoevaluacion_{len(extras)}"] = body
                modulo.extras = extras
                self.spec.issues.append(Issue(Severidad.AVISO,
                    f"Autoevaluación '{titulo[:50]}' extraída del contenido del "
                    f"módulo {n}: los quizzes se cargan a mano en Canvas "
                    "(la consigna quedó en el plan JSON).", ctx))

        # --- foros con la consigna escrita en la planilla (no como DOCX) ---
        self._inyectar_foros_de_planilla(modulo, ctx)

        # --- foros con la consigna escrita adentro de otra página ---
        self._inyectar_otra_pagina(modulo, ctx)

        # --- foros y actividades que llegan como DOCX separados ---
        self._inyectar_foros_y_actividades(modulo, ctx)

        # --- páginas de contenido (reemplazan el placeholder N.1.) ---
        paginas = [i for i in modulo.items
                   if i.tipo == TipoItem.PAGINA and i.fuente.html]

        # La Conclusión del módulo va al final de la última página de
        # contenido (así lo hace el equipo en todas las aulas).
        extras = getattr(modulo, "extras", {})
        conclusion = extras.pop("conclusion", "")
        if conclusion and paginas:
            ultima = paginas[-1]
            if "conclusi" not in normalizar(ultima.titulo):
                ultima.fuente.html += "<h3>Conclusión</h3>" + conclusion
                logger.info(f"  [M{n}] Conclusión anexada a '{ultima.titulo[:40]}'")

        if paginas:
            self._inyectar_paginas(n, paginas, ctx)
        else:
            self.spec.issues.append(Issue(Severidad.AVISO,
                f"El módulo {n} no tiene páginas con contenido extraído; "
                "queda el placeholder del aula base.", ctx))

        # Recién ahora existen en organizations los <item> de las páginas:
        # se resuelven los reordenamientos que quedaron pendientes de
        # _inyectar_otra_pagina (si el módulo no tenía páginas, no hay
        # después de qué ubicarlos: quedan donde ya estaban).
        for rid, pagina_titulo in self._reorders_pendientes:
            self._reordenar_item_despues_de_pagina(rid, pagina_titulo)
        self._reorders_pendientes = []

        # --- Bibliografía MN ---
        referencias = getattr(modulo, "extras", {}).get("referencias", "")
        archivo_bib = _buscar_archivo_wiki(self.working, f"bibliografia-m{n}*.html")
        if referencias and archivo_bib:
            viejo = _leer(archivo_bib)
            nuevo = pagina_bibliografia(
                titulo=f"Bibliografía M{n}",
                body_html=self._rutear_media(referencias),
                banner_src=_extraer_banner(viejo),
                identifier=_extraer_identifier(viejo),
                tema=self.spec.tema)
            _escribir(archivo_bib, nuevo)
            logger.info(f"  [M{n}] Bibliografía sobreescrita")

    # ------------------------------------------------------------------ #
    def _inyectar_paginas(self, n: int, paginas: list, ctx: str):
        # Banner: el del placeholder del aula base para este módulo
        placeholder_file = _buscar_archivo_wiki(self.working, f"{n}-dot-1-*.html")
        banner = _extraer_banner(_leer(placeholder_file)) if placeholder_file else ""

        nuevos = []   # (identifier_recurso, href, titulo)
        for item in paginas:
            page_id = _gen_id()
            slug = slugify(item.titulo)
            href = f"wiki_content/{slug}.html"
            html = pagina_contenido(
                titulo=item.titulo,
                body_html=self._rutear_media(item.fuente.html),
                banner_src=banner, identifier=page_id,
                tema=self.spec.tema)
            _escribir(self.working / href, html)
            nuevos.append((page_id, href, item.titulo))
        # Para el índice del programa (syllabus): páginas reales del módulo.
        self.paginas_por_modulo[n] = [(pid, t) for pid, _h, t in nuevos]
        logger.info(f"  [M{n}] {len(nuevos)} páginas de contenido escritas")

        # ---- imsmanifest: organización ----
        pat_item = re.compile(
            rf'<item identifier="[^"]+" identifierref="([^"]+)">\s*'
            rf'<title>\s*{n}\.1\.[^<]*</title>\s*</item>')
        m = pat_item.search(self.manifest)
        if not m:
            self.spec.issues.append(Issue(Severidad.BLOQUEANTE,
                f"No encontré el placeholder '{n}.1.' en imsmanifest.xml "
                "del aula base.", ctx))
            return
        recurso_placeholder = m.group(1)
        items_xml = "".join(
            f'<item identifier="{_gen_id()}" identifierref="{pid}">'
            f'<title>{xml_escape(t)}</title></item>' for pid, _, t in nuevos)
        self.manifest = pat_item.sub(lambda _: items_xml, self.manifest, count=1)

        # quitar el recurso del placeholder y su archivo
        pat_res = re.compile(
            rf'<resource identifier="{recurso_placeholder}"[^>]*>.*?</resource>',
            re.DOTALL)
        self.manifest = pat_res.sub("", self.manifest, count=1)
        if placeholder_file:
            placeholder_file.unlink()

        self.recursos_nuevos.extend((pid, href) for pid, href, _ in nuevos)

        # ---- module_meta ----
        pat_meta = re.compile(
            rf'<item identifier="[^"]+">\s*<content_type>WikiPage</content_type>\s*'
            rf'<workflow_state>active</workflow_state>\s*'
            rf'<title>\s*{n}\.1\.[^<]*</title>.*?</item>', re.DOTALL)
        meta_items = "".join(f"""<item identifier="{_gen_id()}">
        <content_type>WikiPage</content_type>
        <workflow_state>active</workflow_state>
        <title>{xml_escape(t)}</title>
        <identifierref>{pid}</identifierref>
        <position>0</position>
        <new_tab>false</new_tab>
        <indent>0</indent>
        <link_settings_json>null</link_settings_json>
      </item>""" for pid, _, t in nuevos)
        if not pat_meta.search(self.meta):
            self.spec.issues.append(Issue(Severidad.BLOQUEANTE,
                f"No encontré el placeholder '{n}.1.' en module_meta.xml.", ctx))
            return
        self.meta = pat_meta.sub(lambda _: meta_items, self.meta, count=1)

    # ------------------------------------------------------------------ #
    def _personalizar_inicio(self):
        """Página de inicio: foto del docente, nombre y titulación/biografía
        en el popup 'Equipo docente'. El video de bienvenida queda manual
        (Canvas Studio)."""
        from urllib.parse import quote
        pagina = _buscar_archivo_wiki(self.working, "pagina-de-inicio.html")
        if pagina is None:
            return
        html = _leer(pagina)
        items = {normalizar(i.detalle.get("item_planilla", i.titulo)): i
                 for i in self.spec.items_inicio}
        cambios = []

        # --- nombre del docente ---
        nombre = self.spec.docentes[0] if self.spec.docentes else ""
        bio_item = next((i for k, i in items.items()
                         if "titulacion" in k or "biografia" in k), None)
        if not nombre and bio_item and bio_item.fuente.archivo:
            # A veces el nombre solo está en el archivo de biografía
            nombre = re.sub(r"biograf[íi]a[_\s-]*", "", bio_item.fuente.archivo.stem,
                            flags=re.I).strip(" -_") or ""
        if nombre:
            html, n = re.subn(
                r"(>)\s*Nombre y Apellido del docente contenidista\s*(<)",
                lambda m: m.group(1) + xml_escape(nombre) + m.group(2), html)
            if n:
                cambios.append("nombre del docente")
            # Tutor de la Sección 1: por defecto, el mismo docente autor.
            html, nt = re.subn(
                r"(>)\s*Nombre y Apellido del docente tutor\s*(<)",
                lambda m: m.group(1) + xml_escape(nombre) + m.group(2), html, count=1)
            if nt:
                cambios.append("tutor sección 1 (= docente)")

        # --- banner de la portada ---
        # El aula base trae el placeholder "Nombre de la asignatura - EP.png"
        # y, como alt, el propio nombre del archivo. El alt tiene que describir
        # la imagen: va el nombre de la asignatura.
        if self.spec.nombre:
            html, nb = re.subn(r'alt="Nombre de la asignatura[^"]*"',
                               f'alt="{xml_escape(self.spec.nombre)}"', html)
            if nb:
                cambios.append("alt del banner")

        # --- foto del docente ---
        foto_item = next((i for k, i in items.items() if "fotografia" in k), None)
        foto = (foto_item.fuente.archivo if foto_item and foto_item.fuente.archivo
                else _elegir_foto_docente(
                    getattr(self.spec, "fotos_docente", []) or [], nombre))
        if foto and foto.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp"):
            (self.working / "web_resources" / "Multimedia cargada").mkdir(
                parents=True, exist_ok=True)
            # Recorte cuadrado centrado en el rostro (como hace el equipo a
            # mano con la herramienta de recorte circular de Fotor): el
            # círculo final lo sigue poniendo el CSS de abajo, pero sin la
            # foto centrada en la cara el object-fit la dejaba descentrada o
            # "estirada" según el encuadre original. Si el recorte falla por
            # cualquier motivo (foto corrupta, sin OpenCV, etc.) se sigue con
            # la foto original: no bloquea la generación del paquete.
            nombre_final = foto.name
            try:
                from maquetador.build.imagenes import recortar_rostro_circular
                recorte = (self.working / "web_resources" / "Multimedia cargada"
                          / f"{foto.stem}_circular.png")
                recortar_rostro_circular(foto, recorte)
                nombre_final = recorte.name
            except Exception as e:
                logger.warning(f"  No pude recortar la foto del docente "
                               f"centrada en el rostro ({e}): uso la original.")
                shutil.copy2(foto, self.working / "web_resources"
                            / "Multimedia cargada" / foto.name)
            destino_rel = f"web_resources/Multimedia cargada/{nombre_final}"
            self.recursos_nuevos.append((_gen_id(), destino_rel))
            url = "$IMS-CC-FILEBASE$/Multimedia%20cargada/" + quote(nombre_final)
            html, n = re.subn(
                r'(<img[^>]*alt="Avatar docente"[^>]*src=")[^"]*(")',
                lambda m: m.group(1) + url + m.group(2), html)
            if not n:   # orden de atributos invertido
                html, n = re.subn(
                    r'(<img[^>]*src=")[^"]*Avatar[^"]*("[^>]*>)',
                    lambda m: m.group(1) + url + m.group(2), html, count=1)
            if n:
                # El alt del aula base queda "Avatar docente": ponerle el del
                # docente (como el equipo a mano: "Fotografía del docente N").
                if nombre:
                    html = html.replace(
                        'alt="Avatar docente"',
                        f'alt="Fotografía del docente {xml_escape(nombre)}"')
                # La foto del docente va en círculo: el border-radius la
                # redondea y object-fit evita que se deforme si el recorte de
                # arriba no llegó a dejarla perfectamente cuadrada (o si se
                # usó la original sin recortar, por algún error).
                html = re.sub(
                    r'(<img[^>]*alt="Fotograf[íi]a del docente[^"]*")',
                    r'\1 style="border-radius: 50%; object-fit: cover; '
                    r'width: 150px; height: 150px;"', html, count=1)
                cambios.append("foto del docente")
            # Tutor de la Sección 1 = mismo docente autor por defecto (foto).
            html, nt = re.subn(
                r'<img[^>]*alt="Avatar tutor"[^>]*>',
                lambda m: re.sub(r'src="[^"]*"', f'src="{url}"', m.group(0), count=1),
                html, count=1)
            if nt:
                if nombre:
                    html = html.replace(
                        'alt="Avatar tutor"',
                        f'alt="Fotografía del tutor {xml_escape(nombre)}"')
                # La del tutor va con el borde institucional (no en círculo).
                html = re.sub(
                    r'(<img)([^>]*alt="Fotograf[íi]a del tutor[^"]*")',
                    r'\1 class="dp-image-rounded-10 dp-image-bordered"'
                    r' style="height: auto; width: 100px;"\2', html, count=1)
                cambios.append("foto del tutor (= docente)")

        # --- titulación / biografía ---
        if bio_item and bio_item.fuente.archivo \
                and bio_item.fuente.archivo.suffix.lower() == ".docx":
            try:
                from docx import Document
                doc = Document(str(bio_item.fuente.archivo))
                parrafos = [p.text.strip() for p in doc.paragraphs
                            if p.text.strip()
                            and not normalizar(p.text).startswith("biograf")]
                bio = " ".join(parrafos)
                if nombre and normalizar(bio).startswith(normalizar(nombre)):
                    bio = bio[len(nombre):].lstrip(" .,:;-–")
            except Exception:
                bio = ""
            if bio:
                bio = bio.replace("\\", "").strip()
                html, n = re.subn(r"(>)\s*Titulación relevante\.?\s*(<)",
                                  lambda m: m.group(1) + xml_escape(bio) + m.group(2),
                                  html, count=1)
                if n:
                    cambios.append("titulación/biografía")
                # Género para "Profesor/a autor/a" (el aula base trae el
                # femenino por defecto): se ajusta a masculino si la bio lo
                # indica claramente.
                if _genero_texto(bio + " " + nombre) == "m":
                    html, ng = re.subn(r">\s*Profesora autora\s*<",
                                       ">Profesor autor<", html, count=1)
                    if ng:
                        cambios.append("género docente")

        # Si no hubo biografía que poner, el placeholder del aula base no puede
        # quedar publicado: "Titulación relevante." ya salió así en un curso.
        # Se vacía el campo y se avisa para completarlo a mano.
        html, np = re.subn(r"(>)\s*Titulación relevante\.?\s*(<)",
                           lambda m: m.group(1) + "&nbsp;" + m.group(2),
                           html, count=1)
        if np:
            cambios.append("placeholder de titulación vaciado")
            self.spec.issues.append(Issue(Severidad.INFO,
                "No se encontró la biografía/titulación del docente: el campo "
                "quedó vacío en la página de inicio, hay que completarlo a mano.",
                "Página de inicio"))

        if cambios:
            _escribir(pagina, html)
            logger.info(f"  [Inicio] personalizado: {', '.join(cambios)}")
            self.spec.issues.append(Issue(Severidad.INFO,
                "Página de inicio personalizada ("
                + ", ".join(cambios) + "). El video de bienvenida se carga "
                "a mano en Canvas Studio.", "Página de inicio"))

    # ------------------------------------------------------------------ #
    def _construir_syllabus(self):
        """Arma la página 'Programa' (course_settings/syllabus.html): enlaza
        el PDF del programa y construye el índice de contenidos (acordeón con
        cada módulo y sus páginas reales). El aula base lo trae con
        'Placeholder Placeholder…'."""
        from urllib.parse import quote
        syl_path = self.working / "course_settings" / "syllabus.html"
        if not syl_path.exists():
            return
        html = _leer(syl_path)
        cambios = []

        # --- Bloque 1: link al PDF del programa ---
        prog = self._buscar_programa()
        if prog:
            destino_rel = f"web_resources/Multimedia cargada/{prog.name}"
            (self.working / "web_resources" / "Multimedia cargada").mkdir(
                parents=True, exist_ok=True)
            shutil.copy2(prog, self.working / destino_rel)
            self.recursos_nuevos.append((_gen_id(), destino_rel))
            url = ("$IMS-CC-FILEBASE$/Multimedia%20cargada/" + quote(prog.name)
                   + "?canvas_=1&amp;canvas_qs_wrap=1")
            etiqueta = f"Programa {self.spec.nombre}" if self.spec.nombre else "Programa"
            bloque1 = (
                '<div class="dp-content-block kl_custom_block_1">\n'
                '<h2 class="dp-has-icon"><i class="fas fa-list-ul" aria-hidden="true">'
                '<span class="dp-icon-content" style="display: none;">&nbsp;</span>'
                '</i></h2>\n'
                f'<p><a class="instructure_file_link instructure_scribd_file auto_open" '
                f'title="{prog.name}" href="{url}" target="_blank" '
                f'data-canvas-previewable="false">{etiqueta}</a></p>\n</div>')
            nuevo = self._reemplazar_bloque_div(html, "kl_custom_block_1", bloque1)
            if nuevo != html:
                html = nuevo
                cambios.append("programa (PDF)")
        else:
            self.spec.issues.append(Issue(Severidad.AVISO,
                "No encontré el PDF del programa para enlazar en la página "
                "'Programa'. Se carga a mano en Canvas.", "Programa"))

        # --- Bloque 2: índice de contenidos (acordeón módulos → páginas) ---
        grupos = []
        for modulo in self.spec.modulos:
            paginas = self.paginas_por_modulo.get(modulo.numero, [])
            if not paginas:
                continue
            titulo_mod = xml_escape(f"Módulo {modulo.numero}. {modulo.titulo}".strip(". "))
            links = "\n".join(
                f'<p><a class="dp-course-link" title="{t}" '
                f'href="$WIKI_REFERENCE$/pages/{pid}">{t}</a></p>'
                for pid, t in paginas)
            grupos.append(
                '<div class="dp-panel-group">\n'
                f'<h3 class="dp-panel-heading"><strong>{titulo_mod}</strong></h3>\n'
                f'<div class="dp-panel-content">\n{links}\n</div>\n</div>')
        if grupos:
            bloque2 = (
                '<div class="dp-content-block kl_custom_block_2">\n'
                '<h2 class="dp-has-icon"><i class="fas fa-book-open" aria-hidden="true">'
                '<span class="dp-icon-content" style="display: none;">&nbsp;</span>'
                '</i> Contenido</h2>\n'
                '<div class="dp-panels-wrapper dp-expander-default '
                'dp-panel-color-dp-primary dp-panel-active-color-dp-secondary '
                'dp-panel-hover-color-dp-secondary" '
                'title="contenido insertado">\n' + "\n".join(grupos)
                + '\n</div>\n</div>')
            nuevo = self._reemplazar_bloque_div(html, "kl_custom_block_2", bloque2)
            if nuevo != html:
                html = nuevo
                cambios.append(f"índice ({len(grupos)} módulos)")

        # --- Bloque "Visión General": el esquema de la asignatura ---
        # El aula base ya trae el bloque (viene de un curso real), así que se
        # REEMPLAZA el que está en vez de agregar otro: agregándolo quedaban
        # dos, y el de arriba sin imagen.
        esquema = self._bloque_esquema()
        if esquema:
            html, reemplazado = self._reemplazar_bloque_por_data_title(
                html, "Esquema del módulo", esquema.lstrip("\n"))
            if not reemplazado:
                html = self._reemplazar_bloque_div(
                    html, "kl_custom_block_2", bloque2 + esquema) \
                    if grupos else html
            cambios.append("esquema de la asignatura")

        # --- Bloque 3: bibliografía consolidada (todos los módulos juntos) ---
        bloque3 = self._construir_bibliografia_consolidada(html)
        if bloque3:
            nuevo = self._reemplazar_bloque_div(html, "kl_custom_block_3", bloque3)
            if nuevo != html:
                html = nuevo
                cambios.append("bibliografía consolidada")

        if cambios:
            _escribir(syl_path, html)
            logger.info(f"  [Programa] syllabus armado: {', '.join(cambios)}")

    def _unificar_tema_wrapper(self):
        """Deja TODAS las páginas con el tema de encabezados vigente.

        Las páginas que el generador arma ya salen con el string correcto, pero
        las que se clonan del aula base conservan el que traían. El editor
        DesignPLUS lo reescribe cuando alguien abre y guarda la página, así que
        el aula base puede tener páginas al día y otras no: el syllabus quedaba
        con el tema anterior. Se normaliza al final, cuando ya están todos los
        archivos en su sitio.
        """
        pat = re.compile(r'(id="dp-wrapper"\s+class=")([^"]*)(")')
        tocados = 0
        for archivo in self.working.rglob("*.html"):
            html = _leer(archivo)
            nuevo, n = pat.subn(
                lambda m: m.group(1) + DP_WRAPPER_CLASSES + m.group(3), html)
            if n and nuevo != html:
                _escribir(archivo, nuevo)
                tocados += 1
        if tocados:
            logger.info(f"  [Tema] wrapper actualizado en {tocados} página(s)")

    def _bloque_esquema(self) -> str:
        """Bloque 'Visión General' del programa con el esquema de la asignatura.

        La planilla lo pide como ítem de inicio ("Esquema introductorio a la
        asignatura") y el equipo lo maqueta en el syllabus, debajo del índice
        de contenidos. Devuelve "" si no hay un esquema utilizable.
        """
        from urllib.parse import quote
        item = next((i for i in self.spec.items_inicio
                     if "esquema" in normalizar(i.detalle.get("item_planilla",
                                                              i.titulo))), None)
        esquema = item.fuente.archivo if item and item.fuente.archivo else None
        if esquema is None or esquema.suffix.lower() not in (
                ".jpg", ".jpeg", ".png", ".webp"):
            if item is not None:
                self.spec.issues.append(Issue(Severidad.AVISO,
                    "La planilla pide el esquema introductorio pero no encontré "
                    "la imagen en la carpeta de diseño. Se carga a mano en el "
                    "programa, debajo del índice.", "Programa"))
            return ""

        destino_rel = f"web_resources/Multimedia cargada/{esquema.name}"
        (self.working / "web_resources" / "Multimedia cargada").mkdir(
            parents=True, exist_ok=True)
        shutil.copy2(esquema, self.working / destino_rel)
        self.recursos_nuevos.append((_gen_id(), destino_rel))
        url = "$IMS-CC-FILEBASE$/Multimedia%20cargada/" + quote(esquema.name)
        return (
            '\n<div class="dp-content-block content-block" '
            'data-title="Esquema del módulo" data-category="Instructional">\n'
            '<h2 class="dp-has-icon"><i class="fas fa-network-wired" '
            'aria-hidden="true"><span class="dp-icon-content" '
            'style="display: none;">&nbsp;</span></i>Visión General</h2>\n'
            '<p style="text-align: center;">'
            f'<img class="{_FIG_CLASES_ESTATICA}" style="width: 600px; height: auto;" '
            f'src="{url}" '
            'alt="Esquema de la asignatura" loading="lazy"></p>\n</div>')

    def _construir_bibliografia_consolidada(self, syl_html: str) -> str:
        """Bloque kl_custom_block_3 del programa: la bibliografía de TODOS los
        módulos junta, con jerarquía clara — 'Módulo N: título' (destacado) y
        debajo 'Obligatoria' / 'Sugerida y referente' con sus referencias en
        columnas (reutiliza construir_bibliografia, mismo formato que las
        páginas de Bibliografía de cada módulo)."""
        # Estilo del encabezado y del título de módulo según el aula base (cada
        # tema trae el suyo): se reusa el del placeholder para respetar el formato.
        m_h2 = re.search(
            r'(<h2 class="dp-has-icon"><i class="fas fa-bookmark".*?</h2>)',
            syl_html, re.S)
        h2 = m_h2.group(1) if m_h2 else (
            '<h2 class="dp-has-icon"><i class="fas fa-bookmark" aria-hidden="true">'
            '<span class="dp-icon-content" style="display: none;">&nbsp;</span>'
            '</i> Bibliografía</h2>')
        secciones = []
        for modulo in self.spec.modulos:
            refs = getattr(modulo, "extras", {}).get("referencias", "")
            cuerpo = construir_bibliografia(self._rutear_media(refs)) if refs else ""
            if not cuerpo:
                continue
            titulo_mod = xml_escape(f"Módulo {modulo.numero}: {modulo.titulo}".strip(": "))
            # El título de módulo va SIN el estilo de encabezado del tema
            # (dp-ignore-theme), solo en negrita: si no, compite visualmente
            # con los rótulos Obligatoria / Sugerida de cada bloque.
            secciones.append(
                '<h3 class="dp-ignore-theme" '
                'style="border-top: 0px; text-align: left;">'
                f'<strong><span style="font-size: 18pt;">{titulo_mod}</span>'
                f'</strong></h3>\n<p>&nbsp;</p>\n{cuerpo}')
        if not secciones:
            return ""
        return ('<div class="dp-content-block kl_custom_block_3">\n'
                + h2 + "\n" + "\n".join(secciones) + "\n</div>")

    def _buscar_programa(self) -> Path:
        """El PDF (o DOCX) del programa, desde los ítems de inicio."""
        for item in self.spec.items_inicio:
            clave = normalizar(item.detalle.get("item_planilla", item.titulo))
            if "programa" in clave and item.fuente.archivo \
                    and item.fuente.archivo.exists():
                return item.fuente.archivo
        return None

    def _reemplazar_bloque_por_data_title(self, html: str, titulo: str,
                                          nuevo: str) -> tuple:
        """Reemplaza el <div data-title="…"> por `nuevo`. (html, reemplazado)."""
        ancla = re.search(rf'<div[^>]*\bdata-title="{re.escape(titulo)}"[^>]*>',
                          html)
        if not ancla:
            return html, False
        inicio = ancla.start()
        depth = 0
        fin = inicio
        for mm in re.finditer(r'<div\b[^>]*>|</div>', html[inicio:]):
            depth += -1 if mm.group(0).startswith("</div") else 1
            if depth == 0:
                fin = inicio + mm.end()
                break
        return html[:inicio] + nuevo + html[fin:], True

    def _reemplazar_bloque_div(self, html: str, clase: str, nuevo: str) -> str:
        """Reemplaza el <div class="…clase…">…</div> (con divs anidados) por
        `nuevo`, cortando en el </div> balanceado. Si no lo encuentra, devuelve
        el html sin cambios."""
        ancla = re.search(rf'<div class="[^"]*\b{clase}\b[^"]*">', html)
        if not ancla:
            return html
        inicio = ancla.start()
        depth = 0
        fin = inicio
        for mm in re.finditer(r'<div\b[^>]*>|</div>', html[inicio:]):
            depth += -1 if mm.group(0).startswith("</div") else 1
            if depth == 0:
                fin = inicio + mm.end()
                break
        return html[:inicio] + nuevo + html[fin:]

    # ------------------------------------------------------------------ #
    #  Helpers de inyección en foros (topics) y actividades (assignments)
    # ------------------------------------------------------------------ #
    def _docx_a_html(self, path: Path, prefijo: str, es_actividad: bool = False) -> str:
        """Convierte un DOCX (foro/actividad) a HTML con snippets UCC.
        Las imágenes embebidas se suman al paquete con el prefijo dado.

        `es_actividad=True` deja el h1/h2 nativo del DOCX sin bajar a h3:
        maquetar_actividad necesita esa distinción (título del caso vs.
        sub-encabezados) para armar sus propios niveles."""
        img = ImagenInline()
        with open(path, "rb") as f:
            html = mammoth.convert_to_html(
                f, convert_image=mammoth.images.img_element(img.handler),
                style_map=_MAMMOTH_STYLE_MAP).value
        soup = BeautifulSoup(html, "html.parser")
        primeros = soup.find_all(recursive=False)
        if primeros and primeros[0].name == "table":
            primeros[0].decompose()   # tabla de metadatos de la plantilla
        # Pedidos de maquetación del asesor (comentarios del DOCX): igual que
        # en las páginas de contenido, un foro/actividad puede traer un link
        # real en un comentario (p.ej. el protocolo de transparencia) u otro
        # pedido anclado a texto del documento.
        comentarios = extraer_comentarios(path)
        if comentarios:
            aplicar_comentarios(soup, comentarios)
        for nombre, data, ctype in img.imagenes:
            self.media[f"{prefijo}_{nombre}"] = (data, ctype)
        html = str(soup).replace("__MEDIA__/", f"__MEDIA__/{prefijo}_")
        return procesar_contenido(self._rutear_media(html), self.spec.tema,
                                  bajar_h1_h2=not es_actividad)

    def _rid_en_meta(self, content_type: str, patron_titulo: str) -> str:
        pat = re.compile(
            rf"<content_type>{content_type}</content_type>\s*"
            r"<workflow_state>active</workflow_state>\s*"
            rf"<title>{patron_titulo}</title>\s*"
            r"<identifierref>([^<]+)</identifierref>")
        m = pat.search(self.meta)
        return m.group(1) if m else ""

    def _cuerpo_topic_con_diseno(self, base_body: str, contenido: str) -> str:
        """Inserta `contenido` en el cuerpo del foro CONSERVANDO el diseño del
        aula base (banner, bloque de navegación, h2): pone el contenido dentro
        del content-block, después del h2, reemplazando los <p>&nbsp;</p>
        placeholder. Devuelve None si el cuerpo base no tiene la estructura."""
        soup = BeautifulSoup(base_body, "html.parser")
        cont_div, h2 = None, None
        # "dp-content-block" es la clase universal (todo bloque la tiene);
        # la bare "content-block" es solo una variante que traen ALGUNOS
        # topics (p.ej. "Foro de apertura") — otros, como los foros
        # obligatorios de módulo ("kl_lectures2"), no la tienen y quedaban
        # sin encontrar nunca su bloque de contenido real.
        for cb in soup.find_all("div", class_="dp-content-block"):
            if cb.find("h2"):
                cont_div, h2 = cb, cb.find("h2")
                break
        if h2 is None:                      # sin estructura esperada
            return None
        for sib in list(h2.find_next_siblings()):
            sib.decompose()                 # quita los <p>&nbsp;</p> placeholder
        cont_div.append(BeautifulSoup(contenido, "html.parser"))
        # El aula base siempre cierra el bloque con aire abajo (los placeholder
        # que acabamos de quitar lo tenían): sin esto el foro queda pegado al
        # borde del content-block, el contenido pierda el margen inferior.
        cont_div.append(BeautifulSoup("<p>&nbsp;</p>", "html.parser"))
        return str(soup)

    def _escribir_topic(self, rid: str, body_html: str, ctx: str) -> bool:
        """Llena el <text> del DiscussionTopic conservando el diseño del aula
        base (banner + navegación + h2) e insertando el contenido debajo."""
        mr = re.search(rf'<resource[^>]*identifier="{rid}"[^>]*>.*?'
                       r'<file href="([^"]+\.xml)"', self.manifest, re.DOTALL)
        if not mr or not (self.working / mr.group(1)).exists():
            self.spec.issues.append(Issue(Severidad.AVISO,
                "No encontré el XML del foro en el aula base.", ctx))
            return False
        topic_path = self.working / mr.group(1)
        topic_xml = _leer(topic_path)
        mt = re.search(r'<text texttype="text/html">(.*?)</text>', topic_xml, re.DOTALL)
        base_body = xml_unescape(mt.group(1)) if mt else ""
        nuevo = self._cuerpo_topic_con_diseno(base_body, body_html)
        if nuevo is None:   # el aula base no tenía la estructura: envoltura mínima
            nuevo = (f'<div id="dp-wrapper" class="{DP_WRAPPER_CLASSES}">'
                     f'<div class="dp-content-block">{body_html}</div></div>')
        topic_xml = re.sub(
            r'(<text texttype="text/html">).*?(</text>)',
            lambda mm: mm.group(1) + xml_escape(nuevo) + mm.group(2),
            topic_xml, count=1, flags=re.DOTALL)
        _escribir(topic_path, topic_xml)
        self.topics_escritos.add(rid)
        return True

    def _escribir_assignment(self, rid: str, body_html: str, ctx: str) -> bool:
        """Llena el bloque 'Actividad' del assignment del aula base."""
        carpeta = self.working / rid
        archivos = list(carpeta.glob("*.html")) if carpeta.is_dir() else []
        if not archivos:
            self.spec.issues.append(Issue(Severidad.AVISO,
                "No encontré el HTML del assignment en el aula base.", ctx))
            return False
        html = _leer(archivos[0])
        # Agrega la consigna al final del bloque 'Actividad', conservando el
        # encabezado y los textos de diseño que el aula base ya trae.
        pat = re.compile(
            r'(data-title="Actividad"[^>]*>)(.*?)'
            r'(</div>\s*(?:<p>&nbsp;</p>\s*)*</div>\s*</body>)', re.DOTALL)
        if not pat.search(html):
            self.spec.issues.append(Issue(Severidad.AVISO,
                "El assignment del aula base no tiene el bloque 'Actividad' "
                "esperado.", ctx))
            return False
        html = pat.sub(
            lambda m: (m.group(1) + m.group(2) + "\n"
                       + maquetar_actividad(body_html, self.spec.tema)
                       + "\n" + m.group(3)),
            html, count=1)
        _escribir(archivos[0], html)
        self.assignments_escritos.add(rid)
        return True

    def _rid_actividad(self, n: int, etiqueta: str) -> tuple:
        """Elige el assignment del aula base según la etiqueta de la consigna."""
        ne = normalizar(etiqueta)
        if "integradora" in ne or "final" in ne:
            return self._rid_en_meta(
                "Assignment", r"[^<]*[Aa]ctividad final[^<]*"), "Actividad final integradora"
        if "sugerida" in ne or "optativa" in ne:
            rid = self._rid_en_meta(
                "Assignment", rf"[^<]*[Aa]ctividad (sugerida|optativa)[^<]*M{n}[^<]*")
            if rid:
                return rid, f"Actividad sugerida M{n}"
        return self._rid_en_meta(
            "Assignment", rf"[^<]*[Aa]ctividad[^<]*M{n}[^<]*"), f"Actividad obligatoria M{n}"

    def _inyectar_consigna_actividad(self, n: int, titulo: str, body: str,
                                     ctx: str):
        """Consigna de actividad embebida en el multimedial → assignment."""
        rid, destino = self._rid_actividad(n, titulo)
        if not rid:
            self.spec.issues.append(Issue(Severidad.AVISO,
                f"Extraje la consigna '{titulo[:50]}' del contenido pero no "
                f"encontré un assignment para el módulo {n} en el aula base.",
                ctx))
            return
        if rid in self.assignments_escritos:
            self.spec.issues.append(Issue(Severidad.AVISO,
                f"El assignment '{destino}' ya tenía contenido cargado; la "
                f"consigna embebida '{titulo[:50]}' quedó sin volcar. Revisar.",
                ctx))
            return
        if self._escribir_assignment(rid, self._rutear_media(body), ctx):
            self.spec.issues.append(Issue(Severidad.INFO,
                f"La consigna '{titulo[:60]}' se quitó del contenido y se "
                f"cargó en {destino}.", ctx))
            logger.info(f"  [M{n}] {destino} ← consigna embebida")

    def _inyectar_foros_de_planilla(self, modulo, ctx: str):
        """Foros cuya consigna el asesor escribió directo en la planilla de
        montaje ('Texto del foro: …') en vez de adjuntar un DOCX: se vuelca ese
        texto en el topic del aula base (apertura o foro del módulo). Corre antes
        que la carga por DOCX y marca el topic como escrito, así el fallback por
        nombre de archivo no lo pisa con contenido equivocado."""
        n = modulo.numero
        for item in modulo.items:
            if item.tipo != TipoItem.FORO:
                continue
            texto = item.detalle.get("texto_planilla")
            if not texto:
                continue
            titulo_n = normalizar(item.detalle.get("item_planilla", "") + " "
                                  + item.titulo)
            if "apertura" in titulo_n or "presentacion" in titulo_n:
                rid = self._rid_en_meta("DiscussionTopic",
                                        r"[^<]*[Ff]oro de apertura[^<]*")
                destino = "Foro de apertura"
            else:
                rid = self._rid_en_meta("DiscussionTopic",
                                        rf"[^<]*[Ff]oro[^<]*M{n}[^<]*")
                destino = f"Foro del módulo {n}"
            if not rid:
                self.spec.issues.append(Issue(Severidad.AVISO,
                    f"El foro '{item.titulo[:50]}' trae su consigna en la "
                    f"planilla pero no encontré un foro destino en el aula base "
                    f"para el módulo {n}: cargar a mano.", ctx))
                continue
            if rid in self.topics_escritos:
                continue
            html = "".join(f"<p>{xml_escape(linea.strip())}</p>"
                           for linea in texto.splitlines() if linea.strip())
            if self._escribir_topic(rid, html, ctx):
                item.issues.append(Issue(Severidad.INFO,
                    f"Consigna del foro (escrita en la planilla) cargada en "
                    f"{destino}.", item.titulo))
                logger.info(f"  [M{n}] {destino} ← consigna de la planilla")

    def _inyectar_otra_pagina(self, modulo, ctx: str):
        """Contenido marcado 'va en otra página' (típicamente un foro sin DOCX
        propio, escrito adentro de la lectura de otra sección): se carga en el
        foro del módulo y ese ítem se reordena para quedar justo después de la
        página de la que se sacó."""
        n = modulo.numero
        for extra in getattr(modulo, "extras_otra_pagina", []):
            html = extra.get("html", "")
            if not html:
                continue
            rid = self._rid_en_meta("DiscussionTopic",
                                    rf"[^<]*[Ff]oro[^<]*M{n}[^<]*")
            if not rid or rid in self.topics_escritos:
                continue
            cuerpo = procesar_contenido(self._rutear_media(html), self.spec.tema)
            if self._escribir_topic(rid, cuerpo, ctx):
                logger.info(f"  [M{n}] Foro del módulo {n} ← contenido "
                           "embebido en la lectura")
                # El <item> de la página todavía no existe en organizations
                # (las páginas se inyectan más adelante, en _inyectar_
                # paginas): el reordenamiento se hace después, no acá.
                self._reorders_pendientes.append(
                    (rid, extra.get("pagina_titulo", "")))

    def _reordenar_item_despues_de_pagina(self, rid: str, pagina_titulo: str):
        """Mueve, dentro de organizations, el <item> cuyo identifierref es
        `rid` para que quede justo después del <item> de la página
        `pagina_titulo` (mismo módulo). No hace nada si no encuentra alguno
        de los dos — el ítem queda donde ya estaba, en su lugar del aula
        base, en vez de arriesgar un manifiesto roto."""
        if not rid or not pagina_titulo:
            return
        m_item = re.search(
            rf'<item identifier="[^"]+" identifierref="{rid}">.*?</item>',
            self.manifest, re.DOTALL)
        if not m_item:
            return
        bloque = m_item.group(0)
        sin_item = self.manifest[:m_item.start()] + self.manifest[m_item.end():]
        m_pag = re.search(
            r'<item identifier="[^"]+" identifierref="[^"]+">\s*'
            rf'<title>{re.escape(pagina_titulo)}</title>\s*</item>', sin_item)
        if not m_pag:
            return
        self.manifest = (sin_item[:m_pag.end()] + bloque
                         + sin_item[m_pag.end():])

    def _inyectar_foros_y_actividades(self, modulo, ctx: str):
        """Vuelca los DOCX de foros y actividades en los topics/assignments
        que el aula base ya trae para el módulo."""
        n = modulo.numero
        assignment_escrito = False

        for item in modulo.items:
            archivo = item.fuente.archivo
            if not archivo or archivo.suffix.lower() != ".docx":
                continue
            if item.tipo in (TipoItem.FORO, TipoItem.TAREA) \
                    and item.fuente.confianza < 0.6:
                item.issues.append(Issue(Severidad.AVISO,
                    f"Match de baja confianza ({item.fuente.confianza:.0%}) con "
                    f"'{archivo.name}': no lo cargué automáticamente; revisar.",
                    item.titulo))
                continue
            titulo_n = normalizar(item.detalle.get("item_planilla", "") + " "
                                  + item.titulo)

            if item.tipo == TipoItem.FORO:
                if "apertura" in titulo_n or "presentacion" in titulo_n:
                    rid = self._rid_en_meta("DiscussionTopic",
                                            r"[^<]*[Ff]oro de apertura[^<]*")
                    destino = "Foro de apertura"
                else:
                    rid = self._rid_en_meta("DiscussionTopic",
                                            rf"[^<]*[Ff]oro[^<]*M{n}[^<]*")
                    destino = f"Foro del módulo {n}"
                if not rid or rid in self.topics_escritos:
                    continue
                html = self._docx_a_html(archivo, f"foro_m{n}")
                if self._escribir_topic(rid, html, ctx):
                    item.issues.append(Issue(Severidad.INFO,
                        f"Contenido de '{archivo.name}' cargado en {destino}.",
                        item.titulo))
                    logger.info(f"  [M{n}] {destino} ← {archivo.name}")

            elif item.tipo == TipoItem.TAREA and not assignment_escrito:
                es_obligatoria = "obligatoria" in titulo_n
                tareas_modulo = [i for i in modulo.items
                                 if i.tipo == TipoItem.TAREA and i.fuente.archivo]
                if not es_obligatoria and len(tareas_modulo) > 1:
                    # Actividad sugerida/opcional con DOCX propio: el aula base
                    # solo trae una Assignment por módulo (la obligatoria), así
                    # que se clona como assignment nuevo en vez de perderla.
                    rid_sug = self._clonar_actividad_sugerida(n)
                    if not rid_sug:
                        item.issues.append(Issue(Severidad.AVISO,
                            f"'{archivo.name}' es una actividad sugerida/opcional "
                            "con DOCX propio, pero no pude clonar un assignment "
                            f"nuevo para cargarla en el módulo {n}: crearla a mano "
                            "en Canvas (Completo/Incompleto, no cuenta para la "
                            "nota final).", item.titulo))
                        continue
                    html = self._docx_a_html(archivo, f"act_sugerida_m{n}",
                                             es_actividad=True)
                    if self._escribir_assignment(rid_sug, html, ctx):
                        item.issues.append(Issue(Severidad.INFO,
                            f"Contenido de '{archivo.name}' cargado en un "
                            f"assignment nuevo 'Actividad sugerida M{n}' "
                            "(Completo/Incompleto, no cuenta para la nota "
                            "final). Verificar en Canvas.", item.titulo))
                        logger.info(f"  [M{n}] Actividad sugerida (nueva) ← {archivo.name}")
                    continue
                rid = self._rid_en_meta(
                    "Assignment", rf"[^<]*[Aa]ctividad[^<]*M{n}[^<]*")
                if not rid or rid in self.assignments_escritos:
                    continue
                html = self._docx_a_html(archivo, f"act_m{n}", es_actividad=True)
                if self._escribir_assignment(rid, html, ctx):
                    assignment_escrito = True
                    item.issues.append(Issue(Severidad.INFO,
                        f"Contenido de '{archivo.name}' cargado en la "
                        f"Actividad obligatoria M{n}.", item.titulo))
                    logger.info(f"  [M{n}] Actividad obligatoria ← {archivo.name}")

    def _inyectar_afi(self):
        # Foro de consultas de la AFI con la consigna escrita en la planilla:
        # el aula base no trae un foro de AFI, así que se avisa para crearlo a
        # mano en Canvas con ese texto (queda además en el plan JSON).
        for foro in self.spec.afi:
            if foro.tipo == TipoItem.FORO and foro.detalle.get("texto_planilla"):
                self.spec.issues.append(Issue(Severidad.AVISO,
                    f"El '{foro.titulo[:50]}' trae su consigna en la planilla, "
                    "pero el aula base no tiene un foro de AFI: crearlo a mano en "
                    "Canvas con ese texto.", "AFI"))

        item = next((i for i in self.spec.afi
                     if i.fuente.archivo
                     and i.fuente.archivo.suffix.lower() == ".docx"), None)
        if not item:
            return
        rid = self._rid_en_meta(
            "Assignment", r"[^<]*[Aa]ctividad final[^<]*")
        if not rid:
            self.spec.issues.append(Issue(Severidad.AVISO,
                "No encontré la 'Actividad final integradora' en el aula base.",
                "AFI"))
            return
        if rid in self.assignments_escritos:
            return
        html = self._docx_a_html(item.fuente.archivo, "afi", es_actividad=True)
        if self._escribir_assignment(rid, html, "AFI"):
            item.issues.append(Issue(Severidad.INFO,
                f"Contenido de '{item.fuente.archivo.name}' cargado en la "
                "Actividad final integradora.", item.titulo))
            logger.info(f"  [AFI] ← {item.fuente.archivo.name}")

    # ------------------------------------------------------------------ #
    def _inyectar_consigna_foro(self, n: int, consignas: list, ctx: str):
        """Escribe la consigna extraída del DOCX dentro del DiscussionTopic
        'Foro (obligatorio) MN' del aula base."""
        # 1. Encontrar el item DiscussionTopic del módulo N en module_meta
        pat_item = re.compile(
            r"<item identifier=\"[^\"]+\">\s*"
            r"<content_type>DiscussionTopic</content_type>\s*"
            r"<workflow_state>active</workflow_state>\s*"
            rf"<title>[^<]*[Ff]oro[^<]*M{n}[^<]*</title>\s*"
            r"<identifierref>([^<]+)</identifierref>", re.DOTALL)
        m = pat_item.search(self.meta)
        if not m:
            self.spec.issues.append(Issue(Severidad.AVISO,
                f"Extraje la consigna del foro del módulo {n} del contenido, "
                f"pero no encontré el foro 'Foro … M{n}' en el aula base para "
                "volcarla. Queda para carga manual.", ctx))
            return
        recurso_id = m.group(1)

        # 2. Recurso → archivo XML del topic
        pat_res = re.compile(
            rf'<resource[^>]*identifier="{recurso_id}"[^>]*>.*?'
            r'<file href="([^"]+\.xml)"', re.DOTALL)
        mr = pat_res.search(self.manifest)
        if not mr:
            self.spec.issues.append(Issue(Severidad.AVISO,
                f"No encontré el recurso XML del foro del módulo {n}.", ctx))
            return
        topic_path = self.working / mr.group(1)
        if not topic_path.exists():
            self.spec.issues.append(Issue(Severidad.AVISO,
                f"No existe {mr.group(1)} en el aula base.", ctx))
            return

        # 3. Volcar la consigna conservando el diseño del aula base
        titulo, cuerpo = consignas[0]
        if len(consignas) > 1:
            cuerpo = "\n".join(c[1] for c in consignas)
        topic_xml = _leer(topic_path)
        mt = re.search(r'<text texttype="text/html">(.*?)</text>', topic_xml, re.DOTALL)
        base_body = xml_unescape(mt.group(1)) if mt else ""
        nuevo = self._cuerpo_topic_con_diseno(base_body, cuerpo)
        if nuevo is None:
            nuevo = (f'<div id="dp-wrapper" class="{DP_WRAPPER_CLASSES}">'
                     f'<div class="dp-content-block">{cuerpo}</div></div>')
        topic_xml = re.sub(
            r'(<text texttype="text/html">).*?(</text>)',
            lambda mm: mm.group(1) + xml_escape(nuevo) + mm.group(2),
            topic_xml, count=1, flags=re.DOTALL)
        _escribir(topic_path, topic_xml)
        self.topics_escritos.add(recurso_id)
        logger.info(f"  [M{n}] Consigna del foro inyectada en {topic_path.name}")
        self.spec.issues.append(Issue(Severidad.INFO,
            f"La consigna '{titulo[:60]}' se quitó de la página de contenido "
            f"y se cargó en el foro del módulo {n}.", ctx))

    # ------------------------------------------------------------------ #
    def _asegurar_modulos(self):
        """Si el curso tiene más módulos que el aula base, clona el último
        módulo base para crear los faltantes (posgrado trae 3; un curso puede
        tener 4+). El inverso (sobrantes) lo maneja _eliminar_modulos_sobrantes."""
        presentes = sorted(set(int(x) for x in re.findall(
            r"<title>\s*M[óo]dulo\s*(\d+)\s*:", self.meta)))
        if not presentes:
            return
        template = presentes[-1]
        for num in sorted(m.numero for m in self.spec.modulos):
            if num in presentes:
                continue
            self._clonar_modulo(template, num)
            presentes.append(num)
            logger.info(f"  Módulo {num} clonado desde el módulo base {template}")
            self.spec.issues.append(Issue(Severidad.INFO,
                f"El aula base no traía módulo {num} (tiene {template}); se clonó "
                f"la estructura del módulo {template} para alojarlo.", "Estructura"))

    def _item_org_balanceado(self, item_id: str) -> str:
        """Bloque <item identifier="item_id">…</item> de organizations (con
        sub-ítems), por corte balanceado de <item>/</item>."""
        ancla = f'<item identifier="{item_id}">'
        ini = self.manifest.find(ancla)
        if ini == -1:
            return ""
        depth = 0
        for mm in re.finditer(r"<item\b[^>]*>|</item>", self.manifest[ini:]):
            depth += -1 if mm.group(0).startswith("</item") else 1
            if depth == 0:
                return self.manifest[ini:ini + mm.end()]
        return ""

    def _resource_block(self, rid: str) -> str:
        m = re.search(rf'<resource identifier="{rid}"[^>]*>.*?</resource>',
                      self.manifest, re.DOTALL)
        return m.group(0) if m else ""

    def _remap_texto(self, texto: str, idmap: dict, t: int, n: int) -> str:
        """Aplica el remapeo de ids + el renombrado de números de módulo
        (M{t}→M{n}, {t}.1→{n}.1, -m{t}.→-m{n}., {t}-dot-→{n}-dot-) y títulos."""
        for old, new in idmap.items():
            texto = texto.replace(old, new)
        texto = texto.replace(f"-m{t}.", f"-m{n}.")
        texto = re.sub(rf"(/|>){t}-dot-", rf"\g<1>{n}-dot-", texto)
        texto = re.sub(
            rf"(Introducci[óo]n|Foro obligatorio|Foro de apertura|Autoevaluaci[óo]n|"
            rf"Actividad obligatoria|Bibliograf[íi]a)\s*M{t}\b", rf"\1 M{n}", texto)
        texto = re.sub(rf"M[óo]dulo\s*{t}\s*:", f"Módulo {n}:", texto)
        texto = re.sub(rf"\b{t}\.1\.", f"{n}.1.", texto)
        return texto

    def _copiar_archivo_clonado(self, old_href: str, new_href: str, idmap: dict,
                                t: int, n: int):
        src = self.working / old_href
        dst = self.working / new_href
        if not src.exists() or dst.exists():
            return
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.suffix.lower() in (".xml", ".html"):
            # No solo remapear ids: también renombrar el número de módulo en el
            # contenido (p.ej. el <title> del assignment 'Actividad obligatoria
            # M{t}' → 'M{n}'), igual que en los bloques meta/org.
            txt = self._remap_texto(src.read_text(encoding="utf-8"), idmap, t, n)
            dst.write_text(txt, encoding="utf-8")
        else:
            shutil.copy2(src, dst)

    def _clonar_actividad_sugerida(self, n: int) -> str:
        """Clona el assignment 'Actividad obligatoria M{n}' del aula base como
        'Actividad sugerida M{n}': mismo diseño/wrapper, pero SIN calificar
        (Complete/Incomplete, omitida de la nota final) — para actividades
        opcionales que llegan como DOCX propio y no tienen slot propio en el
        aula base (que solo trae una Assignment por módulo). Devuelve el rid
        del nuevo assignment, o '' si no pudo clonarlo.

        Hay dos árboles de <item> paralelos que comparten el mismo identifier:
        el de module_meta.xml (rico: content_type/workflow_state/title/
        identifierref/position, lo que usa Canvas) y el de imsmanifest.xml
        <organizations> (simple: identifier+identifierref+title, el estándar
        Common Cartridge). Hay que clonar los dos, más el <resource> y los
        archivos de la carpeta del assignment."""
        rid_base = self._rid_en_meta("Assignment", rf"[^<]*[Aa]ctividad[^<]*M{n}[^<]*")
        if not rid_base:
            return ""
        bloque_res = self._resource_block(rid_base)
        carpeta_base = self.working / rid_base
        if not (bloque_res and carpeta_base.is_dir()):
            return ""
        # El <item> de module_meta.xml es una hoja (sin <item> anidados): se
        # ubica por posición (ancla más cercana hacia atrás/adelante) en vez de
        # con .*? DOTALL, que en un documento con varios módulos podía cruzar
        # de un <item> a otro y capturar el identifier equivocado.
        marca = f"<identifierref>{rid_base}</identifierref>"
        idx = self.meta.find(marca)
        ini = self.meta.rfind('<item identifier="', 0, idx) if idx != -1 else -1
        fin = self.meta.find("</item>", idx) + len("</item>") if idx != -1 else -1
        if idx == -1 or ini == -1 or fin < len("</item>"):
            return ""
        bloque_meta_item = self.meta[ini:fin]
        m_id = re.match(r'<item identifier="([^"]+)">', bloque_meta_item)
        if not m_id:
            return ""
        item_id_base = m_id.group(1)
        m_org_item = re.search(
            rf'<item identifier="{item_id_base}" identifierref="{rid_base}">.*?</item>',
            self.manifest, re.DOTALL)
        if not m_org_item:
            return ""

        nuevo_rid = _gen_id()
        nuevo_item_id = _gen_id()
        carpeta_nueva = self.working / nuevo_rid
        if carpeta_nueva.exists():
            shutil.rmtree(carpeta_nueva)
        shutil.copytree(carpeta_base, carpeta_nueva)

        settings = carpeta_nueva / "assignment_settings.xml"
        if settings.exists():
            xml = _leer(settings)
            xml = xml.replace(f'identifier="{rid_base}"', f'identifier="{nuevo_rid}"', 1)
            xml = re.sub(r"<title>[^<]*</title>",
                        f"<title>Actividad sugerida M{n}</title>", xml, count=1)
            xml = re.sub(r"<grading_type>[^<]*</grading_type>",
                        "<grading_type>pass_fail</grading_type>", xml)
            xml = re.sub(r"<points_possible>[^<]*</points_possible>",
                        "<points_possible>0.0</points_possible>", xml)
            xml = re.sub(r"<omit_from_final_grade>[^<]*</omit_from_final_grade>",
                        "<omit_from_final_grade>true</omit_from_final_grade>", xml)
            _escribir(settings, xml)

        nuevo_res = bloque_res.replace(rid_base, nuevo_rid)
        self.manifest = self.manifest.replace(
            "</resources>", "    " + nuevo_res + "\n  </resources>", 1)

        nuevo_meta_item = bloque_meta_item.replace(
            f'identifier="{item_id_base}"', f'identifier="{nuevo_item_id}"', 1)
        nuevo_meta_item = nuevo_meta_item.replace(
            f"<identifierref>{rid_base}</identifierref>",
            f"<identifierref>{nuevo_rid}</identifierref>")
        nuevo_meta_item = re.sub(r"<title>[^<]*</title>",
                                 f"<title>Actividad sugerida M{n}</title>",
                                 nuevo_meta_item, count=1)
        self.meta = self.meta.replace(
            bloque_meta_item, bloque_meta_item + "\n      " + nuevo_meta_item, 1)

        nuevo_org_item = m_org_item.group(0).replace(
            f'identifier="{item_id_base}" identifierref="{rid_base}"',
            f'identifier="{nuevo_item_id}" identifierref="{nuevo_rid}"', 1)
        nuevo_org_item = re.sub(r"<title>[^<]*</title>",
                                f"<title>Actividad sugerida M{n}</title>",
                                nuevo_org_item, count=1)
        self.manifest = self.manifest.replace(
            m_org_item.group(0), m_org_item.group(0) + "\n            " + nuevo_org_item, 1)
        return nuevo_rid

    def _clonar_modulo(self, template: int, nuevo: int):
        """Clona el módulo `template` del aula base como módulo `nuevo`:
        duplica su <module> (meta), su <item> (organizations), sus <resource>
        y todos los archivos, con ids nuevos y números renombrados."""
        m_meta = re.search(
            rf'<module identifier="([^"]+)">\s*<title>\s*M[óo]dulo\s*{template}\s*:'
            r".*?</module>", self.meta, re.DOTALL)
        if not m_meta:
            return
        bloque_meta, mod_id = m_meta.group(0), m_meta.group(1)
        bloque_org = self._item_org_balanceado(mod_id)
        if not bloque_org:
            return

        # Recursos del módulo (identifierref del org) + sus dependencias
        rids = list(dict.fromkeys(re.findall(r'identifierref="([^"]+)"', bloque_org)))
        todos = list(rids)
        for rid in rids:
            for dep in re.findall(r'<dependency identifierref="([^"]+)"',
                                  self._resource_block(rid)):
                if dep not in todos:
                    todos.append(dep)

        # Mapa ids viejos→nuevos: módulo + ítems (meta y org) + recursos
        idmap = {}
        for iid in re.findall(r'identifier="([^"]+)"', bloque_meta + bloque_org):
            idmap.setdefault(iid, _gen_id())
        for rid in todos:
            idmap.setdefault(rid, _gen_id())

        # Clonar recursos: copiar archivos (remap interno) + nuevo <resource>
        nuevos_res = []
        for rid in todos:
            bloque_res = self._resource_block(rid)
            if not bloque_res:
                continue
            for href in re.findall(r'href="([^"]+)"', bloque_res):
                self._copiar_archivo_clonado(
                    href, self._remap_texto(href, idmap, template, nuevo),
                    idmap, template, nuevo)
            nuevos_res.append(self._remap_texto(bloque_res, idmap, template, nuevo))

        # Clonar bloques meta y org (con remap + retitulado) e insertarlos
        nuevo_meta = self._remap_texto(bloque_meta, idmap, template, nuevo)
        nuevo_org = self._remap_texto(bloque_org, idmap, template, nuevo)
        self.meta = self.meta.replace(
            bloque_meta, bloque_meta + "\n  " + nuevo_meta, 1)
        self.manifest = self.manifest.replace(
            bloque_org, bloque_org + "\n        " + nuevo_org, 1)
        self.manifest = self.manifest.replace(
            "</resources>", "\n    ".join([""] + nuevos_res) + "\n  </resources>", 1)

    # ------------------------------------------------------------------ #
    def _eliminar_modulos_sobrantes(self):
        """El aula base trae más módulos (educación: 4, posgrado: 6) de los que
        el curso usa. Los que el curso NO ocupa quedarían como placeholder
        ('Módulo N: (Nombre del módulo)', 'Bibliografía Bibliografía…') en el
        paquete. El equipo los borra a mano; acá se eliminan automáticamente:
        el <module> del meta, el <item> de organizations, los <resource> de sus
        ítems y los archivos físicos. Los módulos especiales (Actividad final
        integradora, Encuesta de valoración) no matchean 'Módulo N' y se
        conservan."""
        usados = {m.numero for m in self.spec.modulos}
        pat_mod = re.compile(
            r'<module identifier="([^"]+)">\s*<title>\s*M[óo]dulo\s*(\d+)\s*:',
            re.IGNORECASE)
        sobrantes = [(mid, int(num)) for mid, num in pat_mod.findall(self.meta)
                     if int(num) not in usados]
        for mod_id, num in sobrantes:
            self._eliminar_un_modulo(mod_id, num)
        # El aula base trae recursos huérfanos (no listados en ningún módulo:
        # actividad sugerida, foros optativos, banners) con el número del
        # módulo en el nombre.
        for _mid, num in sobrantes:
            self._eliminar_huerfanos_modulo(num)

    def _eliminar_un_modulo(self, mod_id: str, num: int):
        # 1. Bloque <module> en module_meta + identifierref de sus ítems
        pat = re.compile(rf'\s*<module identifier="{mod_id}">.*?</module>',
                         re.DOTALL)
        m = pat.search(self.meta)
        if not m:
            return
        rrefs = re.findall(r'<identifierref>([^<]+)</identifierref>', m.group(0))
        self.meta = pat.sub("", self.meta, count=1)

        # 2. Ítem del módulo en <organizations> (anidado: corte balanceado)
        self._quitar_item_organizations(mod_id)

        # 3. Recursos de cada ítem + archivos físicos
        for rref in rrefs:
            self._eliminar_recurso(rref)

        logger.info(f"  Módulo {num} (placeholder del aula base) eliminado")
        self.spec.issues.append(Issue(Severidad.INFO,
            f"El módulo {num} del aula base no lo usa este curso "
            f"({len(self.spec.modulos)} módulos): se eliminó del paquete.",
            "Limpieza"))

    def _eliminar_encuesta_valoracion(self):
        """'Encuesta de valoración final' (aula base) es un Quiz clásico
        (Quizzes::Quiz). El equipo usa New Quizzes, que el formato IMSCC no
        puede generar, así que esa encuesta queda siempre vacía y hay que
        rehacerla a mano en Canvas — se quita del paquete en vez de dejarla
        como recurso muerto (pedido del usuario)."""
        m = re.search(
            r'<module identifier="([^"]+)">\s*<title>\s*Encuesta de valoraci[óo]n',
            self.meta, re.IGNORECASE)
        if not m:
            return
        mod_id = m.group(1)
        pat = re.compile(rf'\s*<module identifier="{mod_id}">.*?</module>', re.DOTALL)
        mm = pat.search(self.meta)
        if not mm:
            return
        rrefs = re.findall(r'<identifierref>([^<]+)</identifierref>', mm.group(0))
        self.meta = pat.sub("", self.meta, count=1)
        self._quitar_item_organizations(mod_id)
        for rref in rrefs:
            self._eliminar_recurso(rref)
        logger.info("  'Encuesta de valoración final' (Quiz clásico) eliminada")
        self.spec.issues.append(Issue(Severidad.INFO,
            "Se quitó 'Encuesta de valoración final' del aula base: es un "
            "Quiz clásico y el equipo usa New Quizzes (el IMSCC no puede "
            "generarlos) — crearla a mano en Canvas.", "Limpieza"))

    def _eliminar_huerfanos_modulo(self, num: int):
        """Borra recursos del aula base que nombran al módulo `num` y que NO
        están referenciados por ningún ítem (huérfanos: actividad sugerida,
        foros optativos, banners). Solo toca huérfanos, así que los módulos
        vigentes (cuyos recursos sí están en organizations) quedan intactos."""
        marca = re.compile(rf'(?i)m{num}\b|{num}-dot-|m[óo]dulo\s*{num}\b')
        org = re.search(r'<organizations.*?</organizations>',
                        self.manifest, re.S).group(0)
        candidatos = re.findall(
            r'<resource identifier="([^"]+)"[^>]*>.*?</resource>',
            self.manifest, re.DOTALL)
        for rid in candidatos:
            if f'identifierref="{rid}"' in org:
                continue   # aún usado por un ítem → no es huérfano
            mres = re.search(
                rf'<resource identifier="{rid}"[^>]*>.*?</resource>',
                self.manifest, re.DOTALL)
            if mres and any(marca.search(h)
                            for h in re.findall(r'href="([^"]+)"', mres.group(0))):
                self._eliminar_recurso(rid)

        # Archivos sueltos del módulo en web_resources (banners, imágenes de
        # foros/actividades del aula base) que ya no usa ninguna página.
        wr = self.working / "web_resources"
        if wr.is_dir():
            for f in wr.rglob("*"):
                if f.is_file() and marca.search(f.name):
                    f.unlink()

    def _purgar_referencias_rotas(self):
        """Elimina <resource> cuyos archivos href ya no existen (p.ej. la
        dependencia assessment_meta.xml de un quiz cuya carpeta se borró)."""
        def _filtrar(m):
            bloque = m.group(0)
            for h in re.findall(r'href="([^"]+)"', bloque):
                if not h.startswith("http") and not (self.working / h).exists():
                    return ""
            return bloque
        self.manifest = re.sub(r'\s*<resource\b.*?</resource>', _filtrar,
                               self.manifest, flags=re.DOTALL)

    def _quitar_item_organizations(self, item_id: str):
        """Quita <item identifier="item_id">…</item> de organizations contando
        el balance de <item>/</item> (el ítem del módulo anida sub-ítems)."""
        ancla = f'<item identifier="{item_id}">'
        inicio = self.manifest.find(ancla)
        if inicio == -1:
            return
        depth = 0
        fin = inicio
        for mm in re.finditer(r'<item\b[^>]*>|</item>', self.manifest[inicio:]):
            depth += -1 if mm.group(0).startswith("</item") else 1
            if depth == 0:
                fin = inicio + mm.end()
                break
        self.manifest = self.manifest[:inicio] + self.manifest[fin:]

    def _eliminar_recurso(self, rref: str):
        """Elimina <resource identifier="rref">…</resource> del manifest y los
        archivos/carpetas que referencia."""
        pat = re.compile(
            rf'\s*<resource identifier="{rref}"[^>]*>.*?</resource>', re.DOTALL)
        m = pat.search(self.manifest)
        if not m:
            return
        bloque = m.group(0)
        hrefs = set(re.findall(r'<file href="([^"]+)"', bloque))
        mh = re.search(r'<resource[^>]*\bhref="([^"]+)"', bloque)
        if mh:
            hrefs.add(mh.group(1))
        self.manifest = pat.sub("", self.manifest, count=1)
        for href in hrefs:
            f = self.working / href
            if f.exists():
                f.unlink()
        # Los assignments del aula base viven en una carpeta llamada como el rid
        carpeta = self.working / rref
        if carpeta.is_dir():
            shutil.rmtree(carpeta)

    # ------------------------------------------------------------------ #
    def _limpiar_recursos_no_usados(self):
        """El aula base trae en cada módulo TODOS los recursos posibles (Foro de
        apertura, Foro obligatorio, Autoevaluación, Actividad obligatoria). Se
        dejan solo los que la planilla pide para ese módulo y se borran los
        demás (pedido del usuario: 'si la planilla tiene un foro y una actividad,
        maquetar esas dos y borrar las otras')."""
        quiere_apertura = False
        for modulo in self.spec.modulos:
            n = modulo.numero
            quedan = self._recursos_que_pide_modulo(modulo)
            if "Foro de apertura" in quedan:
                quiere_apertura = True
            # Recursos borrables PROPIOS de este módulo (no el Foro de apertura,
            # que es del curso y vive solo en M1: se trata aparte más abajo).
            candidatos = {
                "DiscussionTopic": [f"Foro obligatorio M{n}"],
                "Quizzes::Quiz": [f"Autoevaluación M{n}"],
                "Assignment": [f"Actividad obligatoria M{n}"],
            }
            for content_type, titulos in candidatos.items():
                for titulo in titulos:
                    if titulo in quedan:
                        continue
                    rref = self._rid_en_meta(content_type, re.escape(titulo))
                    if rref:
                        self._eliminar_item_por_rref(rref)
                        logger.info(f"  [M{n}] recurso no pedido eliminado: {titulo}")

        # Foro de apertura (recurso de curso, único): se borra solo si ningún
        # módulo declara un foro de presentación/apertura.
        if not quiere_apertura:
            rref = self._rid_en_meta("DiscussionTopic", re.escape("Foro de apertura"))
            if rref:
                self._eliminar_item_por_rref(rref)
                logger.info("  Foro de apertura (no pedido) eliminado")

    def _avisar_recursos_vacios(self):
        """Tras maquetar, los foros/actividades que QUEDAN pero no recibieron
        contenido (el asesor entregó un enlace de Google Docs en vez de un DOCX,
        o no llegó el archivo) siguen con el placeholder del aula base. Se avisa
        para completarlos a mano, así nada queda incompleto en silencio."""
        for m in re.finditer(
                r'<content_type>(DiscussionTopic|Assignment)</content_type>\s*'
                r'<workflow_state>[^<]*</workflow_state>\s*<title>([^<]*)</title>\s*'
                r'<identifierref>([^<]+)</identifierref>', self.meta):
            _ct, titulo, rid = m.groups()
            largo = self._texto_de_recurso(rid)
            if largo is not None and largo < 300:
                self.spec.issues.append(Issue(Severidad.AVISO,
                    f"El recurso '{titulo.strip()}' quedó con el placeholder del "
                    "aula base (sin contenido). Suele pasar cuando el asesor "
                    "entrega un enlace (Google Docs) en vez de un archivo: "
                    "completar a mano en Canvas.", "Recursos a completar"))

    def _validar_xml_generado(self):
        """Cualquier XML mal formado en el paquete (p.ej. un '&' sin escapar
        en un título) hace fallar la importación en Canvas. Se chequea acá,
        sobre el paquete ya armado, para que aparezca en los avisos de ESTA
        corrida en vez de descubrirse recién al importar."""
        rotos = []
        for xml_path in self.working.rglob("*.xml"):
            try:
                ET.fromstring(xml_path.read_text(encoding="utf-8"))
            except Exception as e:
                rotos.append(f"{xml_path.relative_to(self.working)}: {e}")
        if rotos:
            detalle = " | ".join(rotos[:5])
            if len(rotos) > 5:
                detalle += f" | (+{len(rotos) - 5} más)"
            self.spec.issues.append(Issue(Severidad.BLOQUEANTE,
                f"{len(rotos)} archivo(s) XML mal formado(s) — el paquete NO "
                f"va a importar bien en Canvas: {detalle}", "Validación XML"))

    # Títulos oficiales de los CTA/recuadros estandarizados: se REPITEN a
    # propósito cuando una página trae más de una caja del mismo tipo (p.ej.
    # dos "Una pausa para reflexionar"), no es un duplicado accidental.
    _TITULOS_ESTANDARIZADOS = {
        "una pausa para reflexionar", "no pases de largo",
        "ejemplos que iluminan", "descubri leyendo", "auriculares on",
        "miralo con lupa", "voces que construyen",
        "¿como vengo hasta aca?", "caja de herramientas para usar",
        "laboratorio de ideas",
    }

    def _avisar_contenido_duplicado(self):
        """Un título que se arma como caja (CTA/recuadro) y ADEMÁS queda
        repetido como texto suelto en la misma página suele ser el mismo bug:
        la etiqueta no se sacó del cuerpo al armar el recuadro. Se avisa por
        página para revisar visualmente, sin tener que abrir cada una."""
        carpeta = self.working / "wiki_content"
        if not carpeta.is_dir():
            return
        for html_path in sorted(carpeta.glob("*.html")):
            soup = BeautifulSoup(html_path.read_text(encoding="utf-8"),
                                 "html.parser")
            conteo = {}
            # Los títulos de panel de un acordeón/expander armado desde una
            # tabla (class="dp-panel-heading") repiten a propósito el mismo
            # encabezado de columna en cada fila/grupo — no es un duplicado.
            titulos = [t for t in soup.find_all(["h2", "h3"])
                       if "dp-panel-heading" not in t.get("class", [])]
            for tag in titulos + soup.select(".card-title"):
                t = tag.get_text(" ", strip=True)
                if len(t) >= 15 and normalizar(t) not in self._TITULOS_ESTANDARIZADOS:
                    conteo[t] = conteo.get(t, 0) + 1
            repetidos = [t for t, n in conteo.items() if n > 1]
            if repetidos:
                self.spec.issues.append(Issue(Severidad.AVISO,
                    "Texto de título repetido dentro de la página (puede "
                    "haber quedado duplicado al armar un recuadro): "
                    + "; ".join(f"'{t}'" for t in repetidos[:3]),
                    html_path.stem))

    def _texto_de_recurso(self, rid: str):
        """Largo del texto del archivo de un recurso (topic XML / assignment
        HTML). None si no se ubica."""
        mr = re.search(rf'<resource[^>]*identifier="{rid}"[^>]*>(.*?)</resource>',
                       self.manifest, re.DOTALL)
        if not mr:
            return None
        for f in re.findall(r'href="([^"]+)"', mr.group(1)):
            if f.endswith((".xml", ".html")):
                p = self.working / f
                if p.exists():
                    return len(BeautifulSoup(
                        p.read_text(encoding="utf-8"), "html.parser")
                        .get_text(" ", strip=True))
        return None

    def _recursos_que_pide_modulo(self, modulo) -> set:
        """Conjunto de títulos de recurso del aula base que la planilla pide
        para este módulo, según el tipo de cada ítem."""
        n = modulo.numero
        quedan = set()
        for item in modulo.items:
            if item.detalle.get("plantilla_vacia"):
                continue
            # El asesor marca lo que NO va con "No corresponde" / "no aplica":
            # esos ítems no generan recurso.
            coment = normalizar(item.comentarios_asesor or "")
            estado = normalizar(item.estado_planilla or "")
            if any(s in coment or s in estado for s in
                   ("no corresponde", "no aplica", "no va", "sin actividad")):
                continue
            txt = normalizar(item.titulo + " "
                             + item.detalle.get("item_planilla", "") + " "
                             + (item.comentarios_asesor or ""))
            if item.tipo == TipoItem.FORO:
                if "apertura" in txt or "presentaci" in txt or "bienvenid" in txt:
                    quedan.add("Foro de apertura")
                else:
                    quedan.add(f"Foro obligatorio M{n}")
            elif item.tipo == TipoItem.EVALUACION:
                self._avisar_autoevaluacion_clasica(n, item.titulo)
            elif item.tipo == TipoItem.TAREA:
                if "autoeval" in txt:
                    self._avisar_autoevaluacion_clasica(n, item.titulo)
                else:
                    quedan.add(f"Actividad obligatoria M{n}")
        return quedan

    def _avisar_autoevaluacion_clasica(self, n: int, titulo: str):
        """La planilla pide una autoevaluación, pero el 'Autoevaluación MN'
        del aula base es un Quiz clásico (Quizzes::Quiz) y el equipo usa New
        Quizzes — el IMSCC no puede llevarlos, así que ese recurso siempre
        queda vacío y hay que rehacerlo a mano. Se avisa y NO se agrega a
        `quedan`, así _limpiar_recursos_no_usados lo elimina del paquete
        (pedido del usuario: no dejar quizzes/encuestas clásicos inútiles)."""
        self.spec.issues.append(Issue(Severidad.AVISO,
            f"'{titulo[:60]}' pide una autoevaluación — no se incluye el "
            f"Quiz clásico del aula base (Módulo {n}): el equipo usa New "
            "Quizzes, que el formato IMSCC no puede generar. Crear a mano "
            "en Canvas.", f"Módulo {n}"))

    def _eliminar_item_por_rref(self, rref: str):
        """Quita un ítem (no un módulo entero) de organizations + module_meta y
        borra su recurso/archivos. Los ítems son hojas (sin anidación)."""
        self.manifest = re.sub(
            rf'\s*<item identifier="[^"]+" identifierref="{rref}">.*?</item>',
            "", self.manifest, count=1, flags=re.DOTALL)
        self.meta = re.sub(
            rf'\s*<item identifier="[^"]+">(?:(?!</item>).)*?'
            rf'<identifierref>{rref}</identifierref>(?:(?!</item>).)*?</item>',
            "", self.meta, count=1, flags=re.DOTALL)
        self._eliminar_recurso(rref)

    # ------------------------------------------------------------------ #
    def _rutear_media(self, html: str) -> str:
        html = (html or "").replace("__MEDIA__/", f"{MEDIA_URL}/")
        # Figuras de DISEÑO: van directo a Multimedia cargada/ (como a mano)
        for path in self.figuras_usadas:
            from urllib.parse import quote
            html = html.replace(f"__DISENO__/{path.name}",
                                "$IMS-CC-FILEBASE$/Multimedia%20cargada/"
                                + quote(path.name))
        return html

    def _empaquetar_media(self):
        destino = self.working / MEDIA_SUBDIR
        if self.media:
            destino.mkdir(parents=True, exist_ok=True)
            for nombre, (data, _ctype) in self.media.items():
                (destino / nombre).write_bytes(data)
                self.recursos_nuevos.append(
                    (_gen_id(), f"{MEDIA_SUBDIR}/{nombre}"))
            logger.info(f"  {len(self.media)} imágenes en {MEDIA_SUBDIR}")
        # Figuras de DISEÑO usadas → web_resources/Multimedia cargada/
        if self.figuras_usadas:
            carpeta = self.working / "web_resources" / "Multimedia cargada"
            carpeta.mkdir(parents=True, exist_ok=True)
            for path in self.figuras_usadas:
                shutil.copy2(path, carpeta / path.name)
                self.recursos_nuevos.append(
                    (_gen_id(), f"web_resources/Multimedia cargada/{path.name}"))
            logger.info(f"  {len(self.figuras_usadas)} figuras de DISEÑO empaquetadas")
        # Figuras de DISEÑO que no pude ubicar en ninguna página
        sobrantes = [p for p in getattr(self.spec, "imagenes_diseno", [])
                     if p not in self.figuras_usadas]
        if sobrantes:
            self.spec.issues.append(Issue(Severidad.AVISO,
                f"{len(sobrantes)} figuras de DISEÑO no se ubicaron en las "
                "páginas (sin epígrafe 'Figura N.' que las referencie): "
                + ", ".join(p.name for p in sobrantes[:8])
                + ("…" if len(sobrantes) > 8 else "")))

    def _registrar_recursos(self):
        bloques = "".join(f"""
    <resource identifier="{rid}" type="webcontent" href="{href}">
      <file href="{href}"/>
    </resource>""" for rid, href in self.recursos_nuevos)
        self.manifest = self.manifest.replace(
            "</resources>", bloques + "\n  </resources>")

    def _renumerar_posiciones(self):
        """Reasigna <position> secuencialmente dentro de cada <items> para que
        el orden quede consistente tras las inyecciones."""
        def _renum(m):
            bloque = m.group(0)
            contador = [0]
            def _pos(_):
                contador[0] += 1
                return f"<position>{contador[0]}</position>"
            return re.sub(r"<position>\d+</position>", _pos, bloque)
        self.meta = re.sub(r"<items>.*?</items>", _renum, self.meta,
                           flags=re.DOTALL)

        # Posición DE cada módulo (la que va tras <workflow_state>, antes de
        # <items>): tras clonar un módulo, el clon hereda la posición del
        # template. Se renumeran en orden de documento (1, 2, 3, …).
        contador = [0]
        def _pos_modulo(_):
            contador[0] += 1
            return f"</workflow_state>\n    <position>{contador[0]}</position>"
        self.meta = re.sub(
            r"</workflow_state>\s*<position>\d+</position>",
            _pos_modulo, self.meta, count=0)


def generar_imscc(spec: CourseSpec, media: dict, output_dir: Path) -> Path:
    return GeneradorAula(spec, media, Path(output_dir)).generar()
