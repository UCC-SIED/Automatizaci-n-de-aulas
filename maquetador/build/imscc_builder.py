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
import io
import zipfile
from pathlib import Path

from xml.sax.saxutils import escape as xml_escape, unescape as xml_unescape
import xml.etree.ElementTree as ET

import warnings

import mammoth
from bs4 import BeautifulSoup, NavigableString, XMLParsedAsHTMLWarning

# Leemos XML de topics/quizzes con el parser HTML de BeautifulSoup a propósito
# (solo medimos longitud de texto); silenciamos el aviso correspondiente.
warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

from maquetador.models import CourseSpec, TipoItem, Issue, Severidad
from maquetador.build.pages import (slugify, pagina_intro, pagina_contenido,
                                    pagina_bibliografia)
from maquetador.build.snippets import (separar_consignas, procesar_contenido,
                                       separar_foro_de_consultas,
                                       urls_de_notas_al_pie,
                                       enlazar_notas_al_pie,
                                       indexar_figuras_diseno,
                                       reconciliar_figuras_diseno,
                                       referencias_de_figuras,
                                       reemplazar_figuras_diseno,
                                       maquetar_actividad,
                                       nombre_publicado_de_figura,
                                       bloque_video_studio,
                                       embed_de_studio,
                                       media_id_de_studio,
                                       recuadro_actividad_grupal,
                                       enlazar_lecturas_con_bibliografia,
                                       _es_espaciador,
                                       _PAT_ES_GRUPAL,
                                       _quitar_portada_de_actividad,
                                       _secciones_de_actividad_a_h3,
                                       token_de_studio,
                                       contenido_declara_video,
                                       bloque_recurso_incrustado,
                                       _FIG_CLASES_EXPANDIBLE,
                                       _FIG_CLASES_ESTATICA, _FIG_ANCHO_MAX)
from maquetador.build.bibliography import construir_bibliografia, indice_de_obras
from maquetador.build.banners import render as banner_render
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
# Banners del plugin de Figma. Van a su propia carpeta: es la que el equipo
# viene usando a mano en el aula ("Contenido multimedia cargado"), separada de
# "Multimedia cargada", donde van las figuras de contenido.
BANNER_SUBDIR = "web_resources/Contenido multimedia cargado"
BANNER_URL = "$IMS-CC-FILEBASE$/Contenido%20multimedia%20cargado"
_EXT_BANNER = (".png", ".jpg", ".jpeg", ".webp")
# El nombre del archivo dice a qué página va. Lo que llega del plugin es
# "1.3.1.png" o "M2.png", pero lo que el equipo venía subiendo a mano traía
# de todo: "1.1.1..png", "2.3.2.png", "1.3. (2).png" (el sufijo que agrega
# Canvas cuando el nombre ya existe) y "1.3.3. Estructura y funciones del
# cerebro.png". Seis formas para lo mismo en una sola materia, así que la
# clave se saca del número y se ignora el resto.
_PAT_CLAVE_BANNER = re.compile(r"^\s*(?:(m)\s*(\d+)|(\d+(?:\s*\.\s*\d+)*))",
                               re.I)


def clave_de_banner(nombre: str) -> str:
    """Nombre de archivo → clave de página ("1.3.1") o de módulo ("M2")."""
    tallo = Path(nombre).stem
    m = _PAT_CLAVE_BANNER.match(tallo)
    if not m:
        return ""
    if m.group(1):
        return "M" + m.group(2)
    return re.sub(r"\s+", "", m.group(3)).rstrip(".")

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


# --------------------------------------------------------------------- #
#  Ficha del "Equipo docente" de la página de inicio
# --------------------------------------------------------------------- #
# Los dos temas traen la MISMA ficha, pero rellenada distinto: el aula base
# de posgrado deja escrito qué va en cada renglón ("Nombre y Apellido del
# docente contenidista", "Titulación relevante.") y la de educación los
# vació dejando un punto o unos puntos suspensivos. Buscar por ese texto
# —como se hacía— funcionaba solo en posgrado: en educación la ficha salía
# con la foto genérica, el nombre en blanco y sin la biografía.
#
# Por eso ahora se busca por ESTRUCTURA, que es la que comparten: el <h3>
# de la sección, la foto al costado y los renglones de texto al lado.
_PLACEHOLDERS_FICHA = ("nombre y apellido del docente", "titulacion relevante")


def _es_hueco_de_ficha(p) -> bool:
    """¿Este <p> es un renglón de la ficha esperando que lo completen?

    Lo es si no tiene texto propio —solo puntos o puntos suspensivos— o si
    tiene el texto de relleno del aula base de posgrado. NO lo es el <p>
    que únicamente sostiene el iconito de 26px del renglón, ni el <p>
    vacío que hace de espaciador.
    """
    bruto = "".join(p.strings).replace("\xa0", " ")
    if not bruto.strip():
        return False          # el icono solo, o un espaciador
    if not bruto.strip(" .·…\t\r\n"):
        return True           # "." / "..." : el renglón vaciado
    return any(k in normalizar(bruto) for k in _PLACEHOLDERS_FICHA)


def _foto_de_ficha(seccion):
    """La foto de la sección: la única imagen que no es el icono de 26px."""
    for img in seccion.find_all("img"):
        if img.get("width") != "26":
            return img
    return None


def _seccion_de_ficha(soup, titulo: str):
    """(contenedor, foto, [huecos]) de "Profesor autor" o "Tutores".

    El rótulo se compara por su arranque porque para entonces ya puede
    estar en femenino ("Profesora autora"): el ajuste de género corre
    antes que esto.
    """
    clave = normalizar(titulo).split()[0]
    enc = next((h for h in soup.find_all(["h3", "h4"])
                if normalizar(h.get_text(" ", strip=True)).startswith(clave)),
               None)
    if enc is None:
        return None, None, []
    seccion = enc.find_next_sibling("div")
    if seccion is None:
        return None, None, []
    huecos = [p for p in seccion.find_all("p") if _es_hueco_de_ficha(p)]
    return seccion, _foto_de_ficha(seccion), huecos


def _escribir_en_hueco(p, texto: str) -> None:
    """Deja `texto` en el renglón, conservando el iconito que lo acompaña."""
    iconos = [img.extract() for img in p.find_all("img")]
    p.clear()
    for icono in iconos:
        p.append(icono)
    marca = BeautifulSoup(f"<strong>{xml_escape(texto)}</strong>", "html.parser")
    if iconos:
        p.append(NavigableString(" "))
    p.append(marca)


# La planilla a veces nombra la asignatura con la carrera pegada entre
# paréntesis ("Metodología de la investigación II (Lic. en Gestión de la
# Educación Especial)"). Eso es dato de catálogo, no el nombre que va en el
# banner de portada ni en el enlace al programa: en el aula la asignatura se
# llama por su nombre a secas. En posgrado no pasaba porque esas planillas
# ya lo traían limpio.
_PAT_CARRERA_PEGADA = re.compile(
    r"\s*\(\s*(?:lic\.?|licenciatura|mgter\.?|mag[ií]ster|maestr[ií]a|"
    r"esp\.?|especializaci[óo]n|doctorado|dr\.?|tec\.?|tecnicatura|prof\.?|"
    r"profesorado|ciclo|carrera)\b[^)]*\)\s*$", re.I)


def nombre_de_asignatura(nombre: str) -> str:
    """El nombre de la asignatura como va al aula, sin la carrera pegada."""
    return _PAT_CARRERA_PEGADA.sub("", (nombre or "").strip()).strip()


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


# Herramientas colaborativas externas: la planilla las nombra en la columna de
# referencia en lugar de un DOCX ("Actividad sugerida | Padlet"). No hay archivo
# que volcar, pero la actividad existe igual y necesita su lugar en Canvas.
_HERRAMIENTAS_EXTERNAS = ("padlet", "mural", "miro", "jamboard", "wooclap",
                          "mentimeter", "flipgrid", "genially")


_PIDE_INTERVENIR = ("coment", "aporte", "respond", "particip", "intervenc")


def _consigna_es_de_foro(html: str) -> bool:
    """¿Esta consigna es la de un foro, más allá de cómo esté rotulada?

    El asesor rotula la caja "Voces que construyen (Mural colaborativo)" pero
    adentro invita a participar de un foro y a comentar los aportes de los
    colegas. Lo que define el destino es la consigna, no la etiqueta."""
    if not html:
        return False
    texto = normalizar(BeautifulSoup(html, "html.parser").get_text(" ", strip=True))
    return "foro" in texto and any(k in texto for k in _PIDE_INTERVENIR)


def _herramienta_externa(item) -> str:
    """Nombre de la herramienta que la planilla puso como referencia, o ""."""
    ref = normalizar(item.detalle.get("referencia", "") or "")
    if not ref or len(ref) > 40:
        return ""
    for herramienta in _HERRAMIENTAS_EXTERNAS:
        if herramienta in ref:
            return herramienta.capitalize()
    return ""


def _leer(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _escribir(path: Path, texto: str):
    path.write_text(texto, encoding="utf-8")


def _extraer_identifier(html: str) -> str:
    m = re.search(r'<meta name="identifier" content="([^"]+)"', html)
    return m.group(1) if m else _gen_id()


_PAT_ACT_OBLIGATORIA = re.compile(r"actividad-obligatoria-m(\d+)", re.I)
_PAT_ACT_SUGERIDA = re.compile(r"actividad-sugerida-m(\d+)", re.I)


def _banner_de_actividad(nombre_archivo: str) -> tuple:
    """(clave, texto) del banner de una actividad, por su nombre de archivo."""
    m = _PAT_ACT_OBLIGATORIA.search(nombre_archivo)
    if m:
        return (f"actividad-obligatoria-m{m.group(1)}",
                f"Actividad obligatoria del módulo {m.group(1)}")
    m = _PAT_ACT_SUGERIDA.search(nombre_archivo)
    if m:
        return (f"actividad-sugerida-m{m.group(1)}",
                f"Actividad sugerida del módulo {m.group(1)}")
    if "final-integradora" in nombre_archivo.lower():
        return ("actividad-final-integradora", "Actividad final integradora")
    return ("", "")


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


def _titulacion_de_planilla(item) -> list:
    """Renglones de titulación que el asesor escribió en la columna LINK.

    Esa columna a veces trae un enlace (Drive, Canvas Studio) y a veces el
    texto mismo. Solo se toma cuando es texto: un enlace no es una
    biografía, y publicarlo dejaría una URL suelta en la ficha del docente.
    """
    texto = (item.detalle or {}).get("referencia", "").strip()
    if not texto or re.match(r"https?://", texto, re.I) or len(texto) < 25:
        return []
    return [r.strip() for r in texto.splitlines() if r.strip()]


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
        self.modulo_por_slug = {}          # {slug de la página: nº de módulo}
        self.rid_por_archivo = {}          # {nombre del DOCX: rid del assignment}
        self.indice_diseno = indexar_figuras_diseno(
            getattr(spec, "imagenes_diseno", []))
        self._conciliar_figuras_mal_rotuladas()
        self.figuras_usadas = set()        # paths de DISEÑO aprovechados
        self.adjuntos_usados = set()       # archivos del curso enlazados
        self.rid_sugerida = {}             # {módulo: rid del buzón sugerido}
        self.videos_puestos = set()        # claves de --video ya incrustadas
        self.banners = {}                  # clave de pagina -> (nombre, bytes)
        self.banners_usados = set()
        self.paginas_sin_banner = []       # [(clave, titulo)]
        self.banners_generados = {}        # nombre.png -> bytes
        self._aviso_sin_plantilla = False

    def _conciliar_figuras_mal_rotuladas(self):
        """Rescata las figuras de DISEÑO nombradas con el módulo equivocado."""
        if not self.indice_diseno:
            return
        referencias = {}
        for modulo in self.spec.modulos:
            refs = set()
            for item in modulo.items:
                if item.fuente.html:
                    refs |= referencias_de_figuras(item.fuente.html)
            referencias[modulo.numero] = refs
        for mod, tipo, num, mod_nombre, path in reconciliar_figuras_diseno(
                self.indice_diseno, referencias):
            self.spec.issues.append(Issue(
                Severidad.AVISO,
                f"El archivo de DISEÑO '{path.name}' dice módulo {mod_nombre}, "
                f"pero la {tipo} {num} la pide el módulo {mod}: la uso ahí. "
                f"Conviene renombrarlo en la carpeta de Diseño.",
                f"Módulo {mod}"))

    # ------------------------------------------------------------------ #
    def generar(self) -> Path:
        spec = self.spec
        base = TEMAS.get(spec.tema)
        if not base or not base.is_dir():
            raise ValueError(f"No existe el aula base para el tema '{spec.tema}'")

        # El nombre del archivo conserva los acentos y los espacios: con los
        # acentos convertidos en guiones bajos ("Medios_tecnolog_as_…") el
        # paquete no se distinguía del ZIP del material que manda el asesor,
        # y se subió el equivocado a Canvas (19-10-2026, "Unsupported content
        # package"). Solo se sacan los caracteres que Windows no acepta en un
        # nombre de archivo.
        # Y abre con "Aula - ": sin eso queda igual al ZIP del material
        # salvo por la extensión, que en el explorador de Windows ni se ve.
        nombre_corto = (spec.codigo
                        or "Aula - " + re.sub(
                            r'[<>:"/\\|?*]+', " ",
                            nombre_de_asignatura(spec.nombre))[:60]
                        ).strip(" ._") or "Aula"
        self.working = self.output_dir / f"working_{nombre_corto}"
        if self.working.exists():
            _rmtree_longpath(self.working)
        _copytree_longpath(base, self.working)
        logger.info(f"Aula base '{spec.tema}' clonada en {self.working}")

        self.manifest = _leer(self.working / "imsmanifest.xml")
        self.meta = _leer(self.working / "course_settings" / "module_meta.xml")

        # Las obras que manda a leer un recuadro 'Descubri leyendo' estan
        # en la bibliografia del modulo, con su enlace: el recuadro solo
        # trae el titulo. Se indexan antes de armar las paginas.
        self.obras_citadas = {}
        for modulo in spec.modulos:
            refs = getattr(modulo, 'extras', {}).get('referencias', '')
            for titulo, url in indice_de_obras(refs).items():
                self.obras_citadas.setdefault(titulo, url)
        self.banners = self._cargar_banners()
        self._titulo_curso()
        self._asegurar_modulos()
        for modulo in spec.modulos:
            self._procesar_modulo(modulo)
        self._eliminar_modulos_sobrantes()
        self._limpiar_recursos_no_usados()
        self._inyectar_afi()
        # Después de la AFI: el foro de consultas se engancha ahí, y
        # borrando antes se lo llevaba puesto.
        self._eliminar_foros_sueltos()
        self._resolver_enlaces_de_actividad()
        self._avisar_recursos_vacios()
        self._avisar_figuras_de_diseno_sin_usar()
        self._avisar_protocolo_de_transparencia()
        self._personalizar_inicio()
        self._construir_syllabus()
        self._empaquetar_media()
        self._empaquetar_banners()
        self._publicar_material_suelto()
        self._unificar_tema_wrapper()
        self._registrar_recursos()
        self._renumerar_posiciones()
        # Con todos los archivos válidos ya en su sitio, cualquier <resource>
        # que apunte a un archivo inexistente es basura (módulos eliminados o
        # referencias colgadas que el aula base ya traía): se elimina.
        self._purgar_referencias_rotas()
        self._incrustar_videos_de_studio()

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
    def _video_de_planilla(self, items, ctx) -> str:
        """Hueco del video del módulo, según lo que declara la planilla.

        Cuando el DOCX no marca dónde va el video ("Embeber video: …"), la
        planilla sí lo dice: una fila de tipo VIDEO con el enlace de Canvas
        Studio en la columna LINK. Sin mirarla, el módulo salía sin ningún
        bloque de video y no quedaba ni el lugar para pegarlo.

        El embed NO se arma: el enlace de la planilla es el de edición del
        medio y su token no sirve como id del reproductor (ver
        `token_de_studio`). Queda el hueco con el enlace en el comentario,
        que es como se venía entregando."""
        if any(contenido_declara_video(i.fuente.html) for i in items):
            return ""      # el DOCX ya dice dónde va: no se duplica el bloque
        for item in items:
            if item.tipo != TipoItem.VIDEO:
                continue
            url = (item.detalle or {}).get("referencia", "")
            # Si la planilla ya trae el id del medio (o el embed entero
            # pegado), el video se incrusta aca mismo y no queda hueco.
            media_id = media_id_de_studio(url)
            if media_id:
                return bloque_video_studio(
                    referencia=url, embed=embed_de_studio(media_id, item.titulo))
            if token_de_studio(url)[0]:
                self.spec.issues.append(Issue(Severidad.AVISO,
                    f"El video de este módulo ya está en Canvas Studio ({url}), "
                    "pero el embed se pega a mano: quedó el hueco en la página "
                    "de Introducción, debajo de los Objetivos.", ctx))
                return bloque_video_studio(referencia=url)
            # Sin enlace todavía (la fila está "Pendiente", el video se graba
            # o se sube después): el hueco va igual. Que el video no esté
            # subido no cambia dónde va, y sin el bloque nadie se acuerda de
            # ubicarlo cuando llega.
            self.spec.issues.append(Issue(Severidad.AVISO,
                f"'{item.titulo[:60]}': la planilla lo declara pero todavía no "
                "tiene el enlace de Canvas Studio. Dejé el hueco en la página "
                "de Introducción, debajo de los Objetivos.", ctx))
            return bloque_video_studio(referencia=item.titulo)
        return ""

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
                # El plugin nombra el banner del módulo "M1.png": si vino,
                # va ese; si no, el del aula base.
                banner_src=self._banner_de(
                    f"M{n}", modulo.titulo or f"Módulo {n}",
                    rotulo=f"Módulo {n}") or _extraer_banner(viejo),
                identifier=_extraer_identifier(viejo),
                tema=self.spec.tema,
                video_html=self._video_de_planilla(modulo.items, ctx))
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
            self._inyectar_consigna_foro(
                n, foros_emb, ctx,
                obligatorio=any("obligatori" in normalizar(t)
                                for t, _ in foros_emb))
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
                # Las figuras de DISEÑO se reemplazan recorriendo los ítems
                # de la planilla, y la conclusión no es un ítem: se anexa
                # después. Sin pasarla por acá, la figura que el docente
                # puso en el cierre se quedaba con la versión embebida —o
                # sin ninguna imagen, como la Figura 3 del módulo 3 de
                # Metodología II, que llegó con el epígrafe solo.
                if self.indice_diseno:
                    conclusion = reemplazar_figuras_diseno(
                        conclusion, n, self.indice_diseno, self.figuras_usadas)
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
                banner_src=self._banner_de(f"bibliografia-m{n}",
                                           f"Bibliografía M{n}")
                           or _extraer_banner(viejo),
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
            # Cada página lleva SU banner, el que el plugin armó con el
            # título de esa página. Sin banners se cae al del placeholder
            # del aula base, que es el que se venía entregando.
            clave = self._clave_de_titulo(item.titulo)
            propio = self._banner_de(clave, item.titulo) if clave else ""
            if self.banners and not propio:
                self.paginas_sin_banner.append((clave, item.titulo[:40]))
            html = pagina_contenido(
                titulo=item.titulo,
                body_html=self._rutear_media(item.fuente.html),
                banner_src=propio or banner, identifier=page_id,
                tema=self.spec.tema)
            html = enlazar_lecturas_con_bibliografia(html, self.obras_citadas)
            _escribir(self.working / href, html)
            self.modulo_por_slug[slug] = n
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
    def _completar_ficha_docente(self, html: str, nombre: str, bio: str,
                                 url_foto: str) -> tuple:
        """Completa el popup "Equipo docente" por la estructura de la ficha.

        Sirve para los dos temas: posgrado deja el texto de relleno escrito
        ("Nombre y Apellido del docente contenidista") y educación lo vació
        dejando un punto, así que buscar por ese texto solo funcionaba en
        uno. Acá se ubican las secciones por su <h3>, la foto por ser la
        única imagen que no es el iconito, y los renglones por estar
        vacíos. Lo que ya quedó lleno no se toca.

        El tutor de la Sección 1 sale, por defecto, con los datos del
        docente autor: es la convención del equipo cuando la carpeta no
        trae tutores (acá el Biodata solo trae al profesor autor).
        """
        if not (nombre or bio or url_foto):
            return html, []
        soup = BeautifulSoup(html, "html.parser")
        cambios = []
        for titulo, estilo_foto, alt_foto in (
                ("Profesor autor",
                 "border-radius: 50%; object-fit: cover; "
                 "width: 150px; height: 150px;",
                 "Fotografía del docente"),
                ("Tutores",
                 "height: auto; width: 100px;",
                 "Fotografía del tutor")):
            _seccion, img, huecos = _seccion_de_ficha(soup, titulo)
            if img is not None and url_foto \
                    and not img.get("alt", "").startswith("Fotograf"):
                img["src"] = url_foto
                img["style"] = estilo_foto
                img["alt"] = f"{alt_foto} {nombre}".strip() if nombre else alt_foto
                img.attrs.pop("role", None)
                if titulo == "Tutores":
                    # La del tutor va con el borde institucional, no en
                    # círculo (así la maqueta el equipo a mano).
                    img["class"] = ["dp-image-rounded-10", "dp-image-bordered"]
                cambios.append(f"foto ({titulo.lower()})")
            # Primer renglón el nombre, segundo la titulación/biografía.
            # El tutor lleva SOLO el nombre, como en el aula base de
            # posgrado —que para el tutor trae un único renglón—: su
            # biografía no la tenemos, y repetir ahí la del docente autor
            # son seiscientos caracteres de investigación duplicados.
            valores = (nombre,) if titulo == "Tutores" else (nombre, bio)
            for hueco, texto in zip(huecos, valores):
                if texto:
                    _escribir_en_hueco(hueco, texto)
            # Los renglones que sobran son relleno del aula base ("...") y
            # no se publican: el equipo los completa al asignar el tutor.
            for sobrante in huecos[len(valores):]:
                sobrante.decompose()
            if huecos and (nombre or bio):
                cambios.append(f"datos ({titulo.lower()})")
        return (str(soup), cambios) if cambios else (html, [])

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
        asignatura = nombre_de_asignatura(self.spec.nombre)
        if asignatura:
            propio = self._banner_de("portada", asignatura)
            if propio:
                html = self._poner_banner(html, propio, asignatura)
                cambios.append("banner de portada")
            else:
                html, nb = re.subn(r'alt="Nombre de la asignatura[^"]*"',
                                   f'alt="{xml_escape(asignatura)}"', html)
                if nb:
                    cambios.append("alt del banner")

        # --- foto del docente ---
        url_foto = ""      # la guarda el bloque de abajo, para la ficha
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
                self._avisar_si_la_foto_es_chica(recorte, foto)
            except Exception as e:
                logger.warning(f"  No pude recortar la foto del docente "
                               f"centrada en el rostro ({e}): uso la original.")
                shutil.copy2(foto, self.working / "web_resources"
                            / "Multimedia cargada" / foto.name)
            destino_rel = f"web_resources/Multimedia cargada/{nombre_final}"
            self.recursos_nuevos.append((_gen_id(), destino_rel))
            url = url_foto = "$IMS-CC-FILEBASE$/Multimedia%20cargada/" \
                + quote(nombre_final)
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
        # Dos fuentes: un DOCX de biografía, o —cuando no hay archivo— el
        # texto que el asesor escribe directo en la columna LINK de la
        # planilla, con un renglón por ítem (Selección y Optimización de
        # Inversiones). Sin la segunda, la titulación salía vacía y había que
        # completarla a mano aunque estuviera escrita en la planilla.
        renglones = []
        if bio_item and bio_item.fuente.archivo \
                and bio_item.fuente.archivo.suffix.lower() == ".docx":
            try:
                from docx import Document
                doc = Document(str(bio_item.fuente.archivo))
                parrafos = [p.text.strip() for p in doc.paragraphs
                            if p.text.strip()
                            and not normalizar(p.text).startswith("biograf")]
                # El DOCX abre con el nombre del docente en una línea propia
                # y en mayúsculas. Arriba, en la ficha, ya está: sin sacarlo
                # la titulación empieza repitiéndolo. No se compara con el
                # nombre de la ficha porque no coinciden —la bio suele traer
                # un apellido más ("Luis ROLDÁN González de las Cuevas"
                # contra "Luis Gonzalez de las Cuevas")—: una línea corta y
                # toda en mayúsculas al principio de una biografía es el
                # nombre, no hay otra cosa que pueda ser.
                if parrafos and len(parrafos[0]) <= 70 \
                        and parrafos[0] == parrafos[0].upper() \
                        and any(c.isalpha() for c in parrafos[0]):
                    parrafos = parrafos[1:]
                renglones = [" ".join(parrafos)]
            except Exception:
                renglones = []
        elif bio_item:
            renglones = _titulacion_de_planilla(bio_item)
        bio = ""
        if renglones:
            if nombre and normalizar(renglones[0]).startswith(normalizar(nombre)):
                # El asesor suele abrir con el nombre del docente, que ya está
                # arriba en la ficha: sin sacarlo saldría dos veces.
                renglones[0] = renglones[0][len(nombre):].lstrip(" .,:;-–")
            renglones = [r.replace("\\", "").strip() for r in renglones if r.strip()]
            bio = " ".join(renglones)
        if bio:
            marcado = "<br>".join(xml_escape(r) for r in renglones)
            html, n = re.subn(r"(>)\s*Titulación relevante\.?\s*(<)",
                              lambda m: m.group(1) + marcado + m.group(2),
                              html, count=1)
            if n:
                cambios.append("titulación/biografía")
            # Género del rótulo "Profesor/a autor/a". Los DOS temas traen el
            # masculino en el aula base —el comentario de antes decía lo
            # contrario y por eso el ajuste no corría nunca—, así que lo que
            # hace falta es el camino inverso: pasarlo a femenino cuando la
            # biografía lo dice. Adriana Di Francesco ("Dra. en Educación…
            # Licenciada… Profesora… Directora") salía como "Profesor autor".
            genero = _genero_texto(bio + " " + nombre)
            if genero == "f":
                html, ng = re.subn(r">\s*Profesor autor\s*<",
                                   ">Profesora autora<", html, count=1)
            elif genero == "m":
                html, ng = re.subn(r">\s*Profesora autora\s*<",
                                   ">Profesor autor<", html, count=1)
            else:
                ng = 0
            if ng:
                cambios.append(f"género docente ({genero})")

        # --- la ficha, por estructura ---
        # Lo de arriba completa la ficha buscando el texto de relleno del
        # aula base de posgrado. El aula base de educación no lo trae —dejó
        # los renglones con un punto— y la ficha salía con la foto genérica,
        # sin nombre y sin biografía. Esta pasada la completa por su forma,
        # que las dos comparten, y no toca lo que ya haya quedado lleno.
        html, nuevos = self._completar_ficha_docente(html, nombre, bio, url_foto)
        cambios.extend(nuevos)

        # --- video de bienvenida (Canvas Studio) ---
        # El bloque "Te damos la bienvenida" del aula base queda con su
        # párrafo vacío: el embed se pega a mano. Si la planilla trae el
        # enlace del video ya subido, se avisa cuál va.
        video_item = next((i for k, i in items.items()
                           if "video" in k and "introduc" in k), None)
        url_video = (video_item.detalle or {}).get("referencia", "") \
            if video_item else ""
        media_id = (self.spec.videos_studio or {}).get("inicio")             or media_id_de_studio(url_video)
        if media_id:
            # El bloque del aula base trae un <p> vacío donde va el video.
            # En las aulas maquetadas el iframe va centrado en ese párrafo.
            titulo = video_item.titulo if video_item else "Video de bienvenida"
            embed = (f'<p style="text-align: center;">'
                     f'{embed_de_studio(media_id, titulo)}</p>\n')
            html, nv = self._llenar_bloque(html, "Te damos la bienvenida",
                                           embed)
            if nv:
                cambios.append("video de bienvenida")
                self.videos_puestos.add("inicio")
            else:
                self.spec.issues.append(Issue(Severidad.AVISO,
                    "No encontré el bloque 'Te damos la bienvenida' para "
                    f"poner el video ({media_id}).", "Página de inicio"))
        elif token_de_studio(url_video)[0]:
            self.spec.issues.append(Issue(Severidad.AVISO,
                f"El video de bienvenida ya está en Canvas Studio "
                f"({url_video}): pegar su embed en el bloque 'Te damos la "
                "bienvenida' de la página de inicio.", "Página de inicio"))

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
            pendiente = ("" if "video de bienvenida" in cambios
                         else " El video de bienvenida se carga a mano en "
                              "Canvas Studio.")
            self.spec.issues.append(Issue(Severidad.INFO,
                "Página de inicio personalizada ("
                + ", ".join(cambios) + ")." + pendiente, "Página de inicio"))

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
            asignatura = nombre_de_asignatura(self.spec.nombre)
            etiqueta = f"Programa {asignatura}" if asignatura else "Programa"
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

        # --- Bloque "Transparencia del documento" ---
        # Va pegado abajo del bloque que enlaza el programa en PDF, y una
        # sola vez: el docente repite la misma declaración en los tres DOCX.
        transparencia = self._bloque_transparencia()
        if transparencia:
            nuevo = self._reemplazar_bloque_div(
                html, "kl_custom_block_1",
                self._bloque_div(html, "kl_custom_block_1") + transparencia)
            if nuevo != html:
                html = nuevo
                cambios.append("transparencia del documento")

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
            # El esquema de la asignatura es un mapa conceptual lleno de
            # texto chico, asi que va al ancho maximo. Pero NO expandible:
            # ya ocupa todo el ancho, y la lupa lo abre en un visor mas
            # chico que la propia pagina — se ve PEOR al hacer clic. Lo
            # marco la revision de Metodologia II ("cuando se abre se hace
            # mas chica… le cambie el estilo para que no se expanda").
            '<p style="text-align: center;">'
            f'<img class="{_FIG_CLASES_ESTATICA}" '
            f'style="width: {_FIG_ANCHO_MAX}px; height: auto;" '
            f'src="{url}" width="{_FIG_ANCHO_MAX}" '
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

    def _llenar_bloque(self, html: str, titulo: str, cuerpo: str) -> tuple:
        """Mete `cuerpo` DENTRO del bloque, antes de su aire de cierre.

        A diferencia de _reemplazar_bloque_por_data_title, que cambia el
        bloque entero, acá el <h2> con su ícono se conserva: lo único que
        cambia es lo que cuelga abajo."""
        ancla = re.search(rf'<div[^>]*\bdata-title="{re.escape(titulo)}"[^>]*>',
                          html)
        if not ancla:
            return html, False
        depth = 0
        for mm in re.finditer(r'<div\b[^>]*>|</div>', html[ancla.start():]):
            depth += -1 if mm.group(0).startswith("</div") else 1
            if depth == 0:
                corte = ancla.start() + mm.start()
                # El bloque cierra con un <p>&nbsp;</p> de aire: el contenido
                # va ANTES, para que el aire siga siendo lo último.
                aire = re.search(r"(?:<p>(?:&nbsp;|\s)*</p>\s*)+$",
                                 html[:corte])
                if aire:
                    corte = aire.start()
                return html[:corte] + cuerpo + html[corte:], True
        return html, False

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

    def _bloque_div(self, html: str, clase: str) -> str:
        """El <div class="…clase…">…</div> tal como está, o ''."""
        marca = "\x00BLOQUE\x00"
        recortado = self._reemplazar_bloque_div(html, clase, marca)
        if marca not in recortado:
            return ""
        i = recortado.index(marca)
        return html[i:len(html) - (len(recortado) - i - len(marca))]

    def _bloque_transparencia(self) -> str:
        """Bloque 'Transparencia del documento' del Programa.

        El docente declara arriba de cada DOCX modular que usó una
        herramienta de IA para el estilo. Es la misma declaración en los tres
        módulos y no es contenido de ninguno: se publica una vez sola, en el
        Programa, debajo del PDF."""
        for modulo in self.spec.modulos:
            cuerpo = getattr(modulo, "extras", {}).get("transparencia", "")
            if not cuerpo:
                continue
            notas = urls_de_notas_al_pie(
                getattr(modulo, "extras", {}).get("referencias", ""))
            cuerpo = enlazar_notas_al_pie(cuerpo, notas)
            return (
                '\n<div class="dp-content-block" '
                'data-title="Transparencia del documento" data-category="+UCC">\n'
                '<h2 class="dp-has-icon"><i class="dp-icon fas fa-robot" '
                'aria-hidden="true"><span class="dp-icon-content" '
                'style="display: none;">&nbsp;</span></i> Transparencia del '
                'documento</h2>\n' + cuerpo + "\n</div>")
        return ""

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
        if es_actividad:
            # La portada del DOCX (carrera, asignatura, docente, título de la
            # actividad, tabla de metadatos) no va: Canvas ya muestra el
            # nombre y la fecha. Y cada rótulo de sección va como h3.
            _quitar_portada_de_actividad(soup, self.spec.nombre)
            _secciones_de_actividad_a_h3(soup)
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
        salida = procesar_contenido(self._rutear_media(html), self.spec.tema,
                                    bajar_h1_h2=not es_actividad)
        if es_actividad and _PAT_ES_GRUPAL.search(soup.get_text(" ", strip=True)):
            # Instructivo de grupos: no está en el DOCX (no es contenido de la
            # asignatura) y el equipo lo pega al pie de toda entrega grupal.
            salida += "\n" + recuadro_actividad_grupal()
            self.spec.issues.append(Issue(Severidad.AVISO,
                f"'{path.stem[:50]}' se entrega en grupo: le agregué el "
                "recuadro 'Actividad Grupal' al pie. Si es individual, "
                "borralo en Canvas.", "Actividades"))
        return salida

    # La ficha muestra la foto a 150x150 CSS. Las pantallas de hoy son de
    # alta densidad, asi que el navegador pide el doble de pixeles reales:
    # por debajo de eso la agranda y se ve borrosa, que es como salio la
    # foto que se subio a mano en Medios.
    _LADO_MINIMO_FOTO = 300

    def _avisar_si_la_foto_es_chica(self, recorte: Path, original: Path) -> None:
        """La foto del docente se ve borrosa si llega con pocos píxeles.

        Se mide DESPUÉS del recorte: lo que importa no es el tamaño del
        archivo original sino cuánto queda de la cara. Una foto de cuerpo
        entero de 4000px puede dejar un recorte de 200.
        """
        try:
            from PIL import Image
            with Image.open(recorte) as im:
                lado = min(im.size)
        except Exception:                                   # pragma: no cover
            return
        if lado >= self._LADO_MINIMO_FOTO:
            return
        self.spec.issues.append(Issue(Severidad.AVISO,
            f"La foto del docente queda en {lado}x{lado} px después de "
            f"recortarla al rostro y la ficha la muestra a 150x150: en una "
            f"pantalla de alta densidad se va a ver borrosa. Pedir una foto "
            f"más grande (el rostro tiene que ocupar al menos "
            f"{self._LADO_MINIMO_FOTO} px) — la original es "
            f"'{original.name}'.", "Página de inicio"))

    def _avisar_protocolo_de_transparencia(self) -> None:
        """¿Las actividades salieron sin el recuadro del uso de IA?

        El equipo lo pone en TODAS las entregas, con el protocolo de
        transparencia enlazado. Cuando el asesor lo escribió solo en el
        programa —como en Medios— las actividades salen sin él, y
        agregarlo por nuestra cuenta seria inventar contenido. Se avisa
        para que se decida.
        """
        carpetas = [self.working / rid for rid in self.assignments_escritos]
        archivos = [a for carpeta in carpetas if carpeta.is_dir()
                    for a in carpeta.glob("*.html")]
        if not archivos:
            return
        if any("aporte de la ia" in normalizar(_leer(a)) for a in archivos):
            return
        self.spec.issues.append(Issue(Severidad.AVISO,
            "Ninguna actividad trae el recuadro del uso de IA con el "
            "protocolo de transparencia: el asesor no lo escribió en los "
            "DOCX de actividad. Si corresponde, agregarlo a mano en Canvas.",
            "Actividades"))

    def _rubrica_de(self, clave: str):
        """La imagen de la rúbrica que le corresponde a esta actividad.

        Llegan en la carpeta de Diseño nombradas por la actividad
        ("Actividad obligatoria 1 rubrica_evaluacion.jpg", "AFI
        rubrica_evaluacion.jpg"). No son figuras del módulo —no tienen
        epígrafe "Figura N"— así que el reemplazo de figuras no las ubicaba
        y quedaban avisadas como sobrantes, sin llegar nunca al estudiante.
        """
        if not clave:
            return None
        m_num = re.search(r"m(\d+)$", clave)
        es_afi = "integradora" in clave
        for path in getattr(self.spec, "imagenes_diseno", []):
            if path in self.figuras_usadas:
                continue
            nombre = normalizar(path.stem)
            if "rubrica" not in nombre and "rúbrica" not in path.stem.lower():
                continue
            if es_afi and ("afi" in nombre.split() or "integradora" in nombre):
                return path
            if m_num and "obligatoria" in clave and "obligatoria" in nombre \
                    and re.search(rf"\b{m_num.group(1)}\b", nombre):
                return path
            if m_num and "sugerida" in clave and "sugerida" in nombre \
                    and re.search(rf"\b{m_num.group(1)}\b", nombre):
                return path
        return None

    def _agregar_rubrica(self, html: str, clave: str, rotulo: str) -> str:
        """Pega la rúbrica al pie de la actividad, dentro de su bloque."""
        rubrica = self._rubrica_de(clave)
        if rubrica is None:
            return html
        soup = BeautifulSoup(html, "html.parser")
        bloque = soup.find("div", attrs={"data-title": "Actividad"}) \
            or soup.find("div", class_="content-block")
        if bloque is None:
            return html
        nombre = nombre_publicado_de_figura(rubrica)
        self.figuras_usadas.add(rubrica)
        alt = f"Rúbrica de evaluación — {rotulo}" if rotulo else "Rúbrica de evaluación"
        bloque.append(BeautifulSoup(
            '<h3>Rúbrica de evaluación</h3>'
            '<p style="text-align: center;">'
            f'<img class="{_FIG_CLASES_EXPANDIBLE}" '
            f'style="width: {_FIG_ANCHO_MAX}px; height: auto;" '
            f'src="__DISENO__/{nombre}" alt="{xml_escape(alt)}" '
            'loading="lazy"></p>', "html.parser"))
        return self._rutear_media(str(soup))

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

    @staticmethod
    def _color_del_placeholder(html_previo: str) -> str:
        """Color del primer texto con estilo propio que YA trae el
        placeholder del aula base para este assignment (p.ej. el banner fijo
        "¡Llegaste al final!" de la AFI). Devuelve "" si no hay ninguno."""
        m = re.search(r'style="color:\s*(#[0-9a-fA-F]{3,6})[;"]', html_previo)
        return m.group(1) if m else ""

    _PAT_PARRAFO_VACIO_FINAL = re.compile(
        r"(?:<p>(?:&nbsp;|\s*)</p>\s*)+$")

    @classmethod
    def _sacar_un_espacio_final(cls, html_previo: str) -> str:
        """Si el placeholder termina en dos o más párrafos vacíos seguidos
        (el aula base de la AFI trae <hr><p>&nbsp;</p><p>&nbsp;</p> antes del
        título del caso, un aire doble), saca uno solo: el resto de las
        páginas de actividad usan un único párrafo vacío de separación."""
        m = cls._PAT_PARRAFO_VACIO_FINAL.search(html_previo)
        if m is None:
            return html_previo
        vacios = re.findall(r"<p>(?:&nbsp;|\s*)</p>", m.group(0))
        if len(vacios) < 2:
            return html_previo
        return html_previo[:m.start()] + "".join(vacios[1:])

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
        def _reemplazo(m):
            # Si el placeholder del aula base ya trae un texto fijo con color
            # propio (el banner "¡Llegaste al final!" de la AFI, azul #003087
            # sin importar el tema del curso), el título del caso se pinta
            # igual — es el mismo bloque, no puede quedar de otro color.
            color = self._color_del_placeholder(m.group(2))
            previo = self._sacar_un_espacio_final(m.group(2))
            return (m.group(1) + previo + "\n"
                   + maquetar_actividad(body_html, self.spec.tema, color)
                   + "\n" + m.group(3))
        html = pat.sub(_reemplazo, html, count=1)
        html = self._titulo_dentro_del_encabezado(html)
        # El banner de la actividad lo nombra el propio archivo del aula
        # base ("actividad-obligatoria-m2.html"): de ahí salen el texto y la
        # clave, así cada actividad tiene el suyo.
        clave, rotulo_banner = _banner_de_actividad(archivos[0].stem)
        if clave:
            html = self._poner_banner(
                html, self._banner_de(clave, rotulo_banner), rotulo_banner)
        html = self._agregar_rubrica(html, clave, rotulo_banner)
        _escribir(archivos[0], html)
        self.assignments_escritos.add(rid)
        return True

    @staticmethod
    def _titulo_dentro_del_encabezado(html: str) -> str:
        """El título del caso va DENTRO del h2 con el ícono del aula base.

        El bloque "Actividad" abre con un <h2> que solo trae el ícono de
        tareas, y el título salía debajo, en un h2 propio: dos encabezados,
        el ícono suelto arriba y el título sin él. El equipo los publica
        como uno solo."""
        soup = BeautifulSoup(html, "html.parser")
        bloque = soup.find(attrs={"data-title": "Actividad"})
        if bloque is None:
            return html
        encabezado = bloque.find("h2", class_="dp-has-icon")
        titulo = bloque.find("h2", class_="dp-ignore-theme")
        if encabezado is None or titulo is None:
            return html
        if encabezado.get_text(strip=True):
            return html       # el aula base ya trae su propio texto
        color = ""
        for parte in (titulo.get("style") or "").split(";"):
            if "color" in parte:
                color = parte.split(":")[-1].strip()
        encabezado["style"] = f"text-align: center; color: {color}" \
            if color else "text-align: center;"
        for hijo in list(titulo.children):
            encabezado.append(hijo.extract())
        titulo.decompose()
        # El aula base deja su renglón de aire y el cuerpo trae el suyo: al
        # juntar los dos encabezados quedaban dos seguidos.
        sig = encabezado.find_next_sibling()
        while sig is not None and _es_espaciador(sig):
            siguiente = sig.find_next_sibling()
            if not _es_espaciador(siguiente):
                break
            sig.decompose()
            sig = siguiente
        return str(soup)

    def _rid_actividad(self, n: int, etiqueta: str) -> tuple:
        """Elige el assignment del aula base según la etiqueta de la consigna."""
        ne = normalizar(etiqueta)
        if "integradora" in ne or "final" in ne:
            return self._rid_en_meta(
                "Assignment", r"[^<]*[Aa]ctividad final[^<]*"), "Actividad final integradora"
        if "sugerida" in ne or "optativa" in ne:
            # La no calificable se llama "Actividad MN" (así la nombra el
            # equipo en Canvas); también se acepta como la escribía antes.
            rid = self._rid_en_meta(
                "Assignment", rf"[^<]*[Aa]ctividad (?:sugerida |optativa )?M{n}[^<]*")
            if rid:
                return rid, f"Actividad M{n}"
        return self._rid_obligatoria(n), f"Actividad obligatoria M{n}"

    def _consigna_de_mural(self, modulo) -> str:
        """Consigna del recuadro de mural colaborativo del módulo, si lo hay.

        Cuando la actividad del módulo se resuelve en una herramienta externa,
        la consigna no llega como DOCX: el asesor la escribe en el recuadro
        "Voces que construyen (Mural colaborativo)" del propio multimedial.
        """
        fuentes = [getattr(i.fuente, "html", "") or "" for i in modulo.items]
        # El recuadro suele ir al final del multimedial, después de la última
        # sección numerada: ahí ya no pertenece a ningún ítem de la planilla,
        # queda en el bloque de cierre del módulo.
        fuentes += list(getattr(modulo, "extras", {}).values())
        for html in fuentes:
            if not html or ("mural" not in normalizar(html)
                            and "voces que" not in normalizar(html)):
                continue
            soup = BeautifulSoup(html, "html.parser")
            for tabla in soup.find_all("table"):
                celdas = tabla.find_all(["td", "th"])
                if not celdas:
                    continue
                etiqueta = normalizar(celdas[0].get_text(" ", strip=True))
                if "mural" not in etiqueta and "voces que construyen" not in etiqueta:
                    continue
                cuerpo = "".join(
                    "".join(str(x) for x in c.children) for c in celdas[1:])
                if cuerpo.strip():
                    return cuerpo
        return ""

    def _inyectar_actividad_con_herramienta(self, modulo, item, herramienta: str,
                                            ctx: str):
        """Actividad que se resuelve en una herramienta externa (Padlet, Mural,
        Miro…): la planilla nombra la herramienta en vez de un DOCX, así que no
        hay archivo que volcar. Se arma igual el assignment, con la consigna
        que el asesor dejó en el multimedial y el contenedor listo para pegar
        el embebido."""
        n = modulo.numero
        consigna = self._consigna_de_mural(modulo)
        # La etiqueta del recuadro dice "Mural colaborativo", pero manda lo que
        # pide la consigna: cuando invita a participar de un FORO y a comentar
        # los aportes de los demás, es un foro y va al espacio del foro del
        # módulo, no a un buzón de entrega. Pasó en Gestión del Riesgo: el
        # "Voces que construyen" del módulo 1 salía de actividad sugerida.
        if _consigna_es_de_foro(consigna):
            self._inyectar_consigna_foro(
                n, [(item.titulo, consigna)], ctx)
            return
        rid = self._clonar_actividad_sugerida(n)
        if not rid:
            item.issues.append(Issue(Severidad.AVISO,
                f"La actividad del módulo {n} se resuelve en {herramienta} y no "
                "pude clonar un assignment para ella: crearla a mano en Canvas.",
                item.titulo))
            return
        cuerpo = (consigna + bloque_recurso_incrustado(titulo=herramienta)).strip()
        if self._escribir_assignment(rid, self._rutear_media(cuerpo), ctx):
            item.issues.append(Issue(Severidad.INFO,
                f"'{item.titulo[:50]}' se resuelve en {herramienta}: creé el "
                f"assignment 'Actividad M{n}' (Completo/Incompleto, no "
                f"cuenta para la nota final) con el hueco para pegar el "
                f"{herramienta}. La consigna sigue además en el multimedial.",
                item.titulo))
            logger.info(f"  [M{n}] Actividad sugerida (nueva) ← {herramienta}")

    def _inyectar_consigna_sugerida(self, modulo, extra: dict, ctx: str):
        """La consigna que el asesor marcó como "de la actividad sugerida".

        Vive dentro de la lectura (el recuadro "¿Cómo vengo hasta acá?" de
        Metodología II) y el asesor pide además un buzón de entrega. Se
        vuelca en la ranura 'Actividad sugerida M{n}' que el aula base ya
        trae —sin calificar, no cuenta para la nota— y en la lectura queda
        el llamado a la acción, que _resolver_enlaces_de_actividad enlaza a
        este mismo buzón.
        """
        n = modulo.numero
        rid = self._rid_de_actividad("sugerida", n) \
            or self._clonar_actividad_sugerida(n)
        if not rid:
            self.spec.issues.append(Issue(Severidad.AVISO,
                f"El asesor marcó una consigna como actividad sugerida del "
                f"módulo {n}, pero no encontré ni pude crear ese buzón: "
                "crearlo a mano en Canvas (Completo/Incompleto, no cuenta "
                "para la nota final).", ctx))
            return
        if rid in self.assignments_escritos:
            self.spec.issues.append(Issue(Severidad.AVISO,
                f"El buzón de la actividad sugerida del módulo {n} ya tenía "
                "contenido: esta consigna quedó sin volcar. Revisar.", ctx))
            return
        cuerpo = procesar_contenido(self._rutear_media(extra["html"]),
                                    self.spec.tema)
        self.rid_sugerida[n] = rid
        if self._escribir_assignment(rid, cuerpo, ctx):
            self.spec.issues.append(Issue(Severidad.INFO,
                f"Consigna sugerida del módulo {n} cargada en 'Actividad "
                f"sugerida M{n}' (con buzón de entrega, sin calificar). En la "
                "lectura quedó el llamado a la acción enlazado al buzón.",
                ctx))
            logger.info(f"  [M{n}] Actividad sugerida ← consigna de la lectura")
            self._reorders_pendientes.append(
                (rid, extra.get("pagina_titulo", "")))

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
                # El aula base rotula todos los foros de módulo como "Foro
                # obligatorio MN". Lo que decide es la FILA de la planilla,
                # no el cuerpo de la consigna: un foro de consultas habla de
                # la actividad obligatoria sin ser él mismo calificable.
                if destino != "Foro de apertura":
                    self._ajustar_nombre_de_foro(rid, n, item)
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
            if extra.get("destino") == "sugerida":
                self._inyectar_consigna_sugerida(modulo, extra, ctx)
                continue
            rid = self._rid_en_meta("DiscussionTopic",
                                    rf"[^<]*[Ff]oro[^<]*M{n}[^<]*")
            if not rid or rid in self.topics_escritos:
                continue
            cuerpo = procesar_contenido(self._rutear_media(html), self.spec.tema)
            if self._escribir_topic(rid, cuerpo, ctx):
                self._ajustar_nombre_de_foro(rid, n)
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
                if item.tipo == TipoItem.TAREA and not archivo:
                    herramienta = _herramienta_externa(item)
                    if herramienta:
                        self._inyectar_actividad_con_herramienta(
                            modulo, item, herramienta, ctx)
                continue
            if item.tipo in (TipoItem.FORO, TipoItem.TAREA) \
                    and item.fuente.confianza < 0.6:
                item.issues.append(Issue(Severidad.AVISO,
                    f"Match de baja confianza ({item.fuente.confianza:.0%}) con "
                    f"'{archivo.name}': no lo cargué automáticamente; revisar.",
                    item.titulo))
                continue
            # El MISMO DOCX referenciado desde dos módulos es una sola
            # actividad, no dos. La planilla de Gestión del Riesgo apunta la
            # entrega preparatoria ("EP - AFI.docx") desde el módulo 2 y
            # desde el 3, y salían dos buzones con idéntica consigna.
            if item.tipo == TipoItem.TAREA \
                    and archivo.name in self.rid_por_archivo:
                item.issues.append(Issue(Severidad.INFO,
                    f"'{archivo.name}' ya se cargó como actividad en otro "
                    "módulo: este ítem apunta a la misma y no se duplica.",
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
                    if destino != "Foro de apertura":
                        self._ajustar_nombre_de_foro(rid, n, item)
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
                        # setdefault: el mismo DOCX puede alimentar la sugerida
                        # de varios módulos (la entrega preparatoria va de M2 a
                        # M3). El enlace tiene que llevar al primer buzón, no
                        # al último que se clonó.
                        self.rid_por_archivo.setdefault(archivo.name, rid_sug)
                        item.issues.append(Issue(Severidad.INFO,
                            f"Contenido de '{archivo.name}' cargado en un "
                            f"assignment nuevo 'Actividad M{n}' "
                            "(Completo/Incompleto, no cuenta para la nota "
                            "final). Verificar en Canvas.", item.titulo))
                        logger.info(f"  [M{n}] Actividad sugerida (nueva) ← {archivo.name}")
                    continue
                rid = self._rid_obligatoria(n)
                if not rid or rid in self.assignments_escritos:
                    continue
                html = self._docx_a_html(archivo, f"act_m{n}", es_actividad=True)
                if self._escribir_assignment(rid, html, ctx):
                    assignment_escrito = True
                    self.rid_por_archivo.setdefault(archivo.name, rid)
                    item.issues.append(Issue(Severidad.INFO,
                        f"Contenido de '{archivo.name}' cargado en la "
                        f"Actividad obligatoria M{n}.", item.titulo))
                    logger.info(f"  [M{n}] Actividad obligatoria ← {archivo.name}")

    # Material que viaja en la carpeta del curso sin una fila en la planilla:
    # los casos que el docente usa en las actividades, planillas de apoyo,
    # una imagen conceptual. No se pueden ubicar solos (nadie dice dónde van)
    # pero tampoco se tiran: se publican en los archivos del aula para que el
    # equipo los enlace desde donde corresponda.
    # El .pptx queda afuera a propósito: cuando aparece es el archivo fuente
    # de algo que ya se publica hecho (el esquema, las placas del video).
    _EXT_PUBLICABLES = {".pdf", ".xlsx", ".xls", ".docx",
                        ".jpg", ".jpeg", ".png", ".gif", ".webp"}
    # Las etapas de producción (guiones, grabación) son material interno: sus
    # PPT y PDF no son para el estudiante.
    _ETAPAS_INTERNAS = ("guion", "grabaci", "maquetaci", "etapa 3", "etapa 4")
    # Papeles del proceso editorial que viajan en la misma carpeta y NO son
    # material de cursada: plantillas vacías, el cronograma interno, el plan
    # de estudios de la carrera, las declaraciones de uso de IA.
    _NO_PUBLICABLE = re.compile(
        r"plantilla|cronograma|protocolo|gaidet|plan de estudio|"
        r"\brr\b|uso de ia|similitud|resoluci[oó]n|^ejemplo\b|[-–—]\s*ejemplo",
        re.I)

    def _publicar_material_suelto(self):
        """Sube a 'Recursos/' el material de la carpeta que nadie referenció."""
        from urllib.parse import quote
        raiz = self.spec.carpeta_origen
        sueltos = []
        for path in getattr(self.spec, "material_suelto", []) or []:
            if path.suffix.lower() not in self._EXT_PUBLICABLES \
                    or self._NO_PUBLICABLE.search(path.name):
                continue
            try:
                relativa = normalizar(str(path.parent.relative_to(raiz)))
            except (ValueError, TypeError):
                continue
            if relativa in (".", "") or any(e in relativa
                                            for e in self._ETAPAS_INTERNAS):
                continue      # la raíz guarda papeles administrativos
            sueltos.append(path)
        if not sueltos:
            return
        destino = self.working / "web_resources" / "Recursos"
        destino.mkdir(parents=True, exist_ok=True)
        for path in sueltos:
            shutil.copy2(path, destino / path.name)
            self.recursos_nuevos.append(
                (_gen_id(), f"web_resources/Recursos/{path.name}"))
        self.spec.issues.append(Issue(Severidad.AVISO,
            "Material de la carpeta que la planilla no ubica: lo publiqué en "
            "los archivos del aula (Recursos/) para enlazarlo desde donde "
            "corresponda — " + ", ".join(p.name for p in sueltos) + ".",
            "Archivos del aula"))

    def _copiar_html_completo(self, origen: Path, destino: Path) -> None:
        """Copia la herramienta y, si es un fragmento, la completa.

        El asesor exporta el .html sin el esqueleto: arranca en <title> y
        cierra en </script>, sin doctype, sin <html> y sin declarar el
        charset. Pegado dentro de la página del aula no se nota, pero el
        iframe lo sirve como documento propio: el navegador entra en modo
        quirks y, sin charset, los acentos salen rotos."""
        texto = origen.read_text(encoding="utf-8", errors="replace")
        cabeza = texto.lstrip()[:400].lower()
        if cabeza.startswith("<!doctype") or cabeza.startswith("<html"):
            shutil.copy2(origen, destino)
            return
        titulo = ""
        m = re.search(r"<title>(.*?)</title>", texto, re.S | re.I)
        if m:
            titulo = m.group(1).strip()
            texto = texto[:m.start()] + texto[m.end():]
        destino.write_text(
            '<!DOCTYPE html>\n<html lang="es">\n<head>\n'
            '<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, '
            'initial-scale=1">\n'
            f"<title>{titulo or origen.stem}</title>\n"
            f"</head>\n<body>\n{texto.strip()}\n</body>\n</html>\n",
            encoding="utf-8")
        self.spec.issues.append(Issue(Severidad.INFO,
            f"'{origen.name}' venía sin el esqueleto HTML (sin doctype ni "
            "charset): se lo agregué al publicarlo, si no el iframe lo abre "
            "en modo quirks y con los acentos rotos.", "AFI"))

    def _herramienta_html_incrustada(self) -> str:
        """Publica la herramienta HTML de la AFI y devuelve su bloque embebido.

        El asesor entrega la actividad como un .html autónomo (con su CSS y
        su JS adentro). Va a los archivos del aula, en la carpeta "Recursos",
        y se incrusta en la página de la AFI apuntando a ese archivo: es el
        "instrumento de aplicación" que la consigna manda usar, así que tiene
        que estar a la vista y además quedar accesible por su cuenta."""
        from urllib.parse import quote
        recursos = list(getattr(self.spec, "recursos_html", []) or [])
        if not recursos:
            return ""
        bloques = []
        for path in recursos:
            destino_rel = f"web_resources/Recursos/{path.name}"
            (self.working / "web_resources" / "Recursos").mkdir(
                parents=True, exist_ok=True)
            self._copiar_html_completo(path, self.working / destino_rel)
            self.recursos_nuevos.append((_gen_id(), destino_rel))
            # $IMS-CC-FILEBASE$ lo reescribe Canvas al importar. Si en el
            # iframe no llega a resolverse, se pasa el link del archivo ya
            # subido con --afi-url y el paquete sale apuntando ahí.
            url = (getattr(self.spec, "afi_url", "")
                   or "$IMS-CC-FILEBASE$/Recursos/" + quote(path.name))
            # Alto fijo y sin envoltorio de proporción: la herramienta es una
            # página con su propio layout, no un video. Con el envoltorio de
            # 56,25% y position:absolute quedaba aplastada contra el borde y
            # no se veía nada.
            titulo = xml_escape(path.stem.replace("_", " "))
            iframe = (f'<p><iframe src="{url}" width="100%" height="950px" '
                      'style="border: medium none currentcolor;" '
                      'frameborder="0" scrolling="yes" '
                      'allowfullscreen="allowfullscreen" '
                      f'title="{titulo}" loading="lazy"></iframe></p>')
            bloques.append("<p>&nbsp;</p>\n" + iframe + "\n<p>&nbsp;</p>")
            self.spec.issues.append(Issue(Severidad.INFO,
                f"'{path.name}' se publicó en los archivos del aula "
                f"(Recursos/) y quedó incrustado en la Actividad final "
                "integradora.", "AFI"))
        return "\n".join(bloques)

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
        html, titulo_foro, cuerpo_foro = separar_foro_de_consultas(html)
        if cuerpo_foro:
            self._inyectar_foro_de_consultas_afi(titulo_foro, cuerpo_foro)
        html += self._herramienta_html_incrustada()
        if self._escribir_assignment(rid, html, "AFI"):
            self.rid_por_archivo[item.fuente.archivo.name] = rid
            item.issues.append(Issue(Severidad.INFO,
                f"Contenido de '{item.fuente.archivo.name}' cargado en la "
                "Actividad final integradora.", item.titulo))
            logger.info(f"  [AFI] ← {item.fuente.archivo.name}")

    # ------------------------------------------------------------------ #
    def _topic_del_aula_base(self, pat_titulo: str):
        """(recurso_id, ruta_xml) del DiscussionTopic cuyo título matchea, o
        (None, None). El título va como fragmento de regex."""
        pat_item = re.compile(
            r"<item identifier=\"[^\"]+\">\s*"
            r"<content_type>DiscussionTopic</content_type>\s*"
            r"<workflow_state>active</workflow_state>\s*"
            rf"<title>{pat_titulo}</title>\s*"
            r"<identifierref>([^<]+)</identifierref>", re.DOTALL)
        m = pat_item.search(self.meta)
        if not m:
            return None, None
        recurso_id = m.group(1)
        pat_res = re.compile(
            rf'<resource[^>]*identifier="{recurso_id}"[^>]*>.*?'
            r'<file href="([^"]+\.xml)"', re.DOTALL)
        mr = pat_res.search(self.manifest)
        if not mr:
            return recurso_id, None
        topic_path = self.working / mr.group(1)
        return recurso_id, (topic_path if topic_path.exists() else None)

    def _topic_suelto(self, patron_titulo: str):
        """(recurso_id, ruta_xml) de un DiscussionTopic que el aula base trae
        armado pero NO enganchado a ningún módulo.

        El foro de consultas de la AFI viene así en el aula base de posgrado:
        el topic y su diseño existen, pero no figuran en module_meta, así que
        buscarlo por module_meta no lo encuentra nunca."""
        pat = re.compile(patron_titulo)
        for m in re.finditer(r'<resource[^>]*identifier="([^"]+)"[^>]*'
                             r'type="imsdt_xmlv1p1"[^>]*>.*?'
                             r'<file href="([^"]+\.xml)"', self.manifest,
                             re.DOTALL):
            ruta = self.working / m.group(2)
            if not ruta.exists():
                continue
            mt = re.search(r"<title>([^<]*)</title>", _leer(ruta))
            if mt and pat.search(mt.group(1)):
                return m.group(1), ruta
        return None, None

    def _enganchar_item_en_modulo(self, modulo_titulo: str, rref: str,
                                  titulo: str, content_type: str) -> bool:
        """Agrega un ítem al final del módulo indicado, en module_meta y en
        organizations. Devuelve False si no encontró el módulo."""
        pat_mod = re.compile(
            rf'<module identifier="([^"]+)">\s*<title>{modulo_titulo}</title>'
            r'.*?<items>(.*?)</items>', re.DOTALL)
        m = pat_mod.search(self.meta)
        if not m:
            return False
        posicion = len(re.findall(r"<item identifier=", m.group(2))) + 1
        item_id = _gen_id()
        nuevo = (f'\n      <item identifier="{item_id}">\n'
                 f'        <content_type>{content_type}</content_type>\n'
                 f'        <workflow_state>active</workflow_state>\n'
                 f'        <title>{xml_escape(titulo)}</title>\n'
                 f'        <identifierref>{rref}</identifierref>\n'
                 f'        <position>{posicion}</position>\n'
                 f'        <new_tab>false</new_tab>\n'
                 f'        <indent>0</indent>\n'
                 f'        <link_settings_json>null</link_settings_json>\n'
                 f'      </item>')
        # Se inserta ANTES del blanco que cierra <items>, para no heredar su
        # sangría y dejar el ítem desalineado con sus hermanos.
        fin = m.end(2)
        while fin > m.start(2) and self.meta[fin - 1] in " \t\r\n":
            fin -= 1
        self.meta = self.meta[:fin] + nuevo + self.meta[fin:]
        cierre = self._cierre_del_item_org(m.group(1))
        if cierre is not None:
            while cierre > 0 and self.manifest[cierre - 1] in " \t\r\n":
                cierre -= 1
            org_item = (f'\n          <item identifier="{item_id}" '
                        f'identifierref="{rref}">\n'
                        f'            <title>{xml_escape(titulo)}</title>\n'
                        f'          </item>\n        ')
            self.manifest = (self.manifest[:cierre] + org_item
                             + self.manifest[cierre:])
        return True

    def _cierre_del_item_org(self, identificador: str):
        """Posición del </item> que cierra ese <item> de organizations.

        Los ítems de módulo ANIDAN a sus páginas, así que no alcanza con
        buscar el primer </item>: hay que contar aperturas y cierres."""
        m = re.search(rf'<item identifier="{identificador}"[^>]*>',
                      self.manifest)
        if not m:
            return None
        nivel, pos = 1, m.end()
        for t in re.finditer(r"<item\b[^>]*?(/?)>|</item>",
                             self.manifest[m.end():]):
            if t.group(0).startswith("</"):
                nivel -= 1
                if nivel == 0:
                    return m.end() + t.start()
            elif not t.group(1):
                nivel += 1
        return None

    # ------------------------------------------------------------------ #
    def _inyectar_foro_de_consultas_afi(self, titulo: str, cuerpo: str):
        """La consigna del foro de consultas que el asesor dejó al final del
        DOCX de la AFI va al foro que ya trae el aula base, no al pie de la
        consigna de la actividad."""
        recurso_id, topic_path = self._topic_del_aula_base(
            r"[^<]*[Ff]oro[^<]*consultas?[^<]*")
        enganchar = False
        if topic_path is None:
            recurso_id, topic_path = self._topic_suelto(
                r"[Ff]oro\s+de\s+consultas?")
            enganchar = topic_path is not None
        if topic_path is None:
            self.spec.issues.append(Issue(Severidad.AVISO,
                f"Saqué la consigna de '{titulo[:60]}' del final de la AFI, "
                "pero no encontré el foro de consultas en el aula base: queda "
                "para carga manual.", "AFI"))
            return
        topic_xml = _leer(topic_path)
        mt = re.search(r'<text texttype="text/html">(.*?)</text>',
                       topic_xml, re.DOTALL)
        base_body = xml_unescape(mt.group(1)) if mt else ""
        nuevo = self._cuerpo_topic_con_diseno(base_body, procesar_contenido(
            cuerpo, self.spec.tema))
        if nuevo is None:
            return
        topic_xml = re.sub(
            r'(<text texttype="text/html">).*?(</text>)',
            lambda mm: mm.group(1) + xml_escape(nuevo) + mm.group(2),
            topic_xml, count=1, flags=re.DOTALL)
        _escribir(topic_path, topic_xml)
        self.topics_escritos.add(recurso_id)
        logger.info(f"  [AFI] Consigna del foro de consultas inyectada en "
                    f"{topic_path.name}")
        titulo_base = re.search(r"<title>([^<]*)</title>", topic_xml)
        if enganchar and not self._enganchar_item_en_modulo(
                r"Actividad final integradora", recurso_id,
                titulo_base.group(1) if titulo_base else titulo,
                "DiscussionTopic"):
            self.spec.issues.append(Issue(Severidad.AVISO,
                "Cargué la consigna en el foro de consultas, pero no encontré "
                "el módulo 'Actividad final integradora' para engancharlo: "
                "agregarlo a mano al módulo en Canvas.", "AFI"))
            return
        self.spec.issues.append(Issue(Severidad.INFO,
            f"'{titulo[:60]}' se quitó del final de la AFI y se cargó en el "
            "foro de consultas del aula base"
            + (", que se enganchó al módulo de la AFI." if enganchar else "."),
            "AFI"))

    # ------------------------------------------------------------------ #
    def _inyectar_consigna_foro(self, n: int, consignas: list, ctx: str,
                                obligatorio: bool = False):
        """Escribe la consigna extraída del DOCX dentro del DiscussionTopic
        'Foro (obligatorio) MN' del aula base.

        `obligatorio` distingue el foro calificable del de participación: el
        aula base los trae todos rotulados "Foro obligatorio MN", y el de
        participación se publica con el nombre corto que usa el equipo."""
        recurso_id, topic_path = self._topic_del_aula_base(
            rf"[^<]*[Ff]oro[^<]*M{n}[^<]*")
        if recurso_id is None:
            self.spec.issues.append(Issue(Severidad.AVISO,
                f"Extraje la consigna del foro del módulo {n} del contenido, "
                f"pero no encontré el foro 'Foro … M{n}' en el aula base para "
                "volcarla. Queda para carga manual.", ctx))
            return
        if topic_path is None:
            self.spec.issues.append(Issue(Severidad.AVISO,
                f"No encontré el recurso XML del foro del módulo {n}.", ctx))
            return

        # Volcar la consigna conservando el diseño del aula base
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
        if not obligatorio:
            self._renombrar_recurso(recurso_id, topic_path,
                                    self._nombre_de_foro(n))
        logger.info(f"  [M{n}] Consigna del foro inyectada en {topic_path.name}")
        self.spec.issues.append(Issue(Severidad.INFO,
            f"La consigna '{titulo[:60]}' se quitó de la página de contenido "
            f"y se cargó en el foro del módulo {n}.", ctx))

    def _nombre_de_foro(self, n: int) -> str:
        """Cómo se llama el foro de participación del módulo en cada aula.

        El aula base los trae todos como "Foro obligatorio MN", pero ese
        nombre es solo del calificable: en posgrado el de participación es
        "Foro MN" y en educación "Foro sugerido MN"."""
        return (f"Foro sugerido M{n}" if normalizar(self.spec.tema) == "educacion"
                else f"Foro M{n}")

    def _ajustar_nombre_de_foro(self, rid: str, n: int, item=None) -> None:
        """El foro del módulo se llama "sugerido" salvo que sea obligatorio.

        El aula base los trae todos como "Foro obligatorio MN" porque es el
        único que incluye, pero ese nombre es el del calificable. De la
        revisión de Metodología II: "el foro lo pusiste en un foro
        obligatorio, no corresponde, a menos que diga explícitamente que sea
        obligatorio; si no sería, en educación, foro sugerido M1".

        Lo decide la FILA de la planilla, no el cuerpo de la consigna: un
        foro de consultas habla de la actividad obligatoria sin ser él mismo
        calificable.
        """
        if not rid:
            return
        rotulo = ""
        if item is not None:
            rotulo = normalizar(item.detalle.get("item_planilla", "") + " "
                                + item.titulo + " "
                                + (item.estado_planilla or ""))
        nombre = (f"Foro obligatorio M{n}" if "obligatori" in rotulo
                  else self._nombre_de_foro(n))
        if "obligatori" not in rotulo:
            self._renombrar_recurso(rid, None, nombre)
        self._poner_banner_de_foro(rid, nombre)

    def _poner_banner_de_foro(self, rid: str, nombre: str) -> None:
        """El foro también lleva su banner dibujado.

        El aula base trae uno genérico para todos, así que los tres foros
        de un curso salían con el mismo. Lleva el nombre con que queda el
        foro en Canvas ("Foro sugerido M2"), que es lo que se lee arriba
        de la página.
        """
        clave = normalizar(nombre).replace(" ", "-")
        url = self._banner_de(clave, nombre)
        if not url:
            return
        mr = re.search(rf'<resource[^>]*identifier="{rid}"[^>]*>.*?'
                       r'<file href="([^"]+\.xml)"', self.manifest, re.DOTALL)
        if not mr:
            return
        ruta = self.working / mr.group(1)
        if not ruta.exists():
            return
        xml = _leer(ruta)
        mt = re.search(r'<text texttype="text/html">(.*?)</text>', xml, re.DOTALL)
        if not mt:
            return
        cuerpo = xml_unescape(mt.group(1))
        nuevo = self._poner_banner(cuerpo, url, nombre)
        if nuevo == cuerpo:
            return
        _escribir(ruta, re.sub(
            r'(<text texttype="text/html">).*?(</text>)',
            lambda m: m.group(1) + xml_escape(nuevo) + m.group(2),
            xml, count=1, flags=re.DOTALL))

    def _renombrar_recurso(self, rref: str, ruta_xml, nuevo: str):
        """Cambia el título de un recurso en sus cuatro lugares: el <item> de
        module_meta, el de organizations, el XML del topic y el de su meta."""
        escapado = xml_escape(nuevo)
        self.meta = re.sub(
            rf'(<item identifier="[^"]+">(?:(?!</item>).)*?<title>)[^<]*'
            rf'(</title>(?:(?!</item>).)*?<identifierref>{rref}</identifierref>)',
            lambda m: m.group(1) + escapado + m.group(2), self.meta,
            count=1, flags=re.DOTALL)
        self.manifest = re.sub(
            rf'(<item identifier="[^"]+" identifierref="{rref}">\s*<title>)[^<]*',
            lambda m: m.group(1) + escapado, self.manifest, count=1)
        # El topic y su "topicMeta" (la dependencia del recurso) llevan cada
        # uno su propio <title>: con renombrar solo uno, Canvas seguía
        # mostrando el viejo.
        m_dep = re.search(rf'<resource[^>]*identifier="{rref}"[^>]*>.*?'
                          r'<dependency identifierref="([^"]+)"',
                          self.manifest, re.DOTALL)
        archivos = [ruta_xml, self.working / f"{rref}.xml"]
        if m_dep:
            archivos.append(self.working / f"{m_dep.group(1)}.xml")
        for archivo in archivos:
            if archivo is not None and archivo.exists():
                _escribir(archivo, re.sub(r"(<title>)[^<]*(</title>)",
                                          lambda m: m.group(1) + escapado
                                          + m.group(2), _leer(archivo), count=1))

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

    def _rid_obligatoria(self, n: int) -> str:
        """El assignment calificable del módulo, nombrándolo explícitamente.

        Desde que la actividad no calificable se agrega ARRIBA de la
        obligatoria, un patrón genérico ("Actividad … MN") se queda con la
        de más arriba: la consigna calificable no se cargaba y el buzón
        obligatorio quedaba con el placeholder del aula base."""
        return (self._rid_en_meta(
                    "Assignment", rf"[^<]*[Aa]ctividad obligatoria[^<]*M{n}[^<]*")
                or self._rid_en_meta(
                    "Assignment", rf"[^<]*[Aa]ctividad[^<]*M{n}[^<]*"))

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
        rid_base = self._rid_obligatoria(n)
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
                        f"<title>Actividad M{n}</title>", xml, count=1)
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
                                 f"<title>Actividad M{n}</title>",
                                 nuevo_meta_item, count=1)
        # La entrega no calificable prepara la obligatoria: va ARRIBA de ella,
        # como la ubica el equipo en Canvas.
        self.meta = self.meta.replace(
            bloque_meta_item, nuevo_meta_item + "\n      " + bloque_meta_item, 1)

        nuevo_org_item = m_org_item.group(0).replace(
            f'identifier="{item_id_base}" identifierref="{rid_base}"',
            f'identifier="{nuevo_item_id}" identifierref="{nuevo_rid}"', 1)
        nuevo_org_item = re.sub(r"<title>[^<]*</title>",
                                f"<title>Actividad M{n}</title>",
                                nuevo_org_item, count=1)
        self.manifest = self.manifest.replace(
            m_org_item.group(0), nuevo_org_item + "\n            " + m_org_item.group(0), 1)
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
        """Saca la 'Encuesta de valoración final' del aula base.

        YA NO SE USA: el aula se entrega CON la encuesta. Se la quitaba por
        ser un Quiz clásico (el equipo usa New Quizzes), pero en el aula
        funciona y el equipo la quiere en el paquete. Queda el método por si
        hiciera falta volver a sacarla en algún curso."""
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

    def _resolver_enlaces_de_actividad(self):
        """Completa los <a data-actividad="…"> que dejó el pedido "enlazar
        actividad" del asesor.

        Se hace al final y no al maquetar cada página: el destino puede ser la
        actividad de OTRO módulo (la entrega preparatoria usa un solo buzón
        para los módulos 2 y 3) y los assignments clonados recién existen
        cuando todos los módulos pasaron."""
        for archivo in sorted((self.working / "wiki_content").glob("*.html")):
            html = _leer(archivo)
            if "data-actividad=" not in html:
                continue
            modulo = self.modulo_por_slug.get(archivo.stem)

            def _href(m, modulo=modulo, archivo=archivo):
                nombre = m.group(2) or ""
                clase, _, mod_pedido = m.group(1).partition(":")
                n = int(mod_pedido) if mod_pedido else modulo
                # Si el asesor nombró el módulo ("el buzón debe ser el mismo
                # que se abrió en el módulo 2"), manda eso. Si no, manda el
                # DOCX que anotó al pie del recuadro, que es el dato exacto.
                rid = self._rid_de_actividad(clase, n) if mod_pedido else ""
                if not rid:
                    rid = self.rid_por_archivo.get(nombre, "")
                if not rid and n:
                    rid = self._rid_de_actividad(clase, n)
                if not rid:
                    self.spec.issues.append(Issue(Severidad.AVISO,
                        f"El asesor pidió enlazar la actividad {clase} "
                        f"({nombre or 'módulo ' + str(n or '?')}) en "
                        f"'{archivo.stem}', pero no encontré ese recurso: "
                        "enlazarlo a mano en Canvas.", "Enlaces a actividades"))
                    return ' class="dp-course-link"'
                return (' class="dp-course-link" href='
                        f'"$CANVAS_OBJECT_REFERENCE$/assignments/{rid}"')

            nuevo = re.sub(
                r' class="dp-course-link" data-actividad="([^"]+)"'
                r'(?: data-actividad-archivo="([^"]+)")?',
                _href, html)
            if nuevo != html:
                _escribir(archivo, nuevo)

    def _rid_de_actividad(self, clase: str, n: int) -> str:
        """rid del assignment 'Actividad <clase> M<n>' del paquete ya armado."""
        # El buzón sugerido no siempre se llama "Actividad sugerida M{n}":
        # cuando hay que clonarlo queda como "Actividad M{n}", y buscarlo
        # por título fallaba —el llamado a la acción de la lectura salía sin
        # enlazar—. El que se usó de verdad queda anotado.
        if clase == "sugerida" and self.rid_sugerida.get(n):
            return self.rid_sugerida[n]
        return self._rid_en_meta(
            "Assignment", rf"[^<]*[Aa]ctividad {clase}[^<]*M{n}\b[^<]*")

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
        dependencias = set(re.findall(r'<dependency identifierref="([^"]+)"',
                                      bloque))
        self.manifest = pat.sub("", self.manifest, count=1)
        # Las dependencias del recurso (el "topicMeta" de un foro, por
        # ejemplo) se van con él, si no las usa nadie más. Sin esto
        # quedaban en el manifiesto apuntando a un recurso que ya no
        # existe: cinco por curso, que Canvas importaba igual.
        for dep in dependencias:
            if f'identifierref="{dep}"' in self.manifest:
                continue        # otro recurso todavía la usa
            self._eliminar_recurso(dep)
        for href in hrefs:
            f = self.working / href
            if f.exists():
                f.unlink()
        # Los assignments del aula base viven en una carpeta llamada como el rid
        carpeta = self.working / rref
        if carpeta.is_dir():
            shutil.rmtree(carpeta)

    # ------------------------------------------------------------------ #
    # Recursos que Canvas lista como ítems del curso y que, si no están en
    # ningún módulo, son sobras del aula base. Los LTI y los webcontent NO
    # entran: las herramientas externas y los archivos (imágenes, banners)
    # viven fuera de los módulos a propósito.
    _TIPOS_BORRABLES_SUELTOS = ("imsdt_xmlv1p1",          # foros
                                "imsqti_xmlv1p2/imscc_xmlv1p1/assessment")

    def _eliminar_foros_sueltos(self):
        """Foros y cuestionarios que no están en ningún módulo.

        Las dos aulas base traen los foros DUPLICADOS —"Foro sugerido M1"
        aparece dos veces, "Foro obligatorio M2" otras dos— y solo una
        copia de cada uno está puesta en un módulo. Las demás viajan en el
        manifiesto igual, así que Canvas las importa y quedan sueltas en
        "Foros de discusión": quince por curso, que el equipo despues borra
        a mano. Es lo que anotó la revisión como "actualizar aula base con
        respecto a los foros que traen".

        Lo mismo con los cuestionarios: el aula base arrastra un "Test -
        Canva - Encuesta" que quedó del armado y viaja en cada curso. La
        encuesta de valoración final, que sí está puesta en un módulo, no
        se toca.

        Se va solo lo que NO está en ningún módulo y no escribimos nosotros.
        """
        sueltos = []
        for m in re.finditer(r'<resource identifier="([^"]+)"[^>]*'
                             r'type="([^"]+)"', self.manifest):
            rid, tipo = m.group(1), m.group(2)
            if tipo not in self._TIPOS_BORRABLES_SUELTOS:
                continue
            if rid in self.meta or rid in self.topics_escritos                     or rid in self.assignments_escritos:
                continue
            sueltos.append(rid)
        for rid in sueltos:
            # Las dependencias (el "topicMeta" de un foro) se van con él:
            # lo resuelve _eliminar_recurso.
            self._eliminar_recurso(rid)
        if sueltos:
            logger.info(f"  {len(sueltos)} recursos sueltos del aula base "
                        "eliminados (no estaban en ningún módulo)")

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
                    # Un recurso que la planilla no pide pero que YA se llenó
                    # no es sobrante: la consigna llegó desde el contenido del
                    # multimedial, no desde una fila. En Gestión del Riesgo el
                    # foro del módulo 1 se cargaba y se borraba a continuación.
                    if rref and rref not in self.topics_escritos \
                            and rref not in self.assignments_escritos:
                        self._eliminar_item_por_rref(rref)
                        logger.info(f"  [M{n}] recurso no pedido eliminado: {titulo}")

        # Foro de apertura (recurso de curso, único): se borra solo si ningún
        # módulo declara un foro de presentación/apertura.
        if not quiere_apertura:
            rref = self._rid_en_meta("DiscussionTopic", re.escape("Foro de apertura"))
            if rref:
                self._eliminar_item_por_rref(rref)
                logger.info("  Foro de apertura (no pedido) eliminado")

    def _avisar_figuras_de_diseno_sin_usar(self):
        """Diseño mandó una figura y en el aula no quedó ubicada.

        Pasa cuando el epígrafe del DOCX no coincide con el nombre del
        archivo (la figura dice "Figura 4" y el archivo es "M_2 fig 3") o
        cuando el asesor no dejó el epígrafe. Sin este aviso la figura se
        pierde en silencio: el aula sale con la imagen del asesor, o sin
        nada, y nadie se entera hasta la revisión en Canvas."""
        for clave, path in sorted(self.indice_diseno.items(), key=lambda x: str(x[0])):
            if path in self.figuras_usadas:
                continue
            modulo = clave[0] if isinstance(clave, tuple) and clave else "?"
            que = " ".join(str(x) for x in clave[1:]) if isinstance(clave, tuple) else clave
            self.spec.issues.append(Issue(Severidad.AVISO,
                f"La figura de diseño '{Path(path).name}' ({que}) no quedó "
                "ubicada en ninguna página: revisá que el epígrafe del DOCX "
                "coincida con el número del archivo.", f"Módulo {modulo}"))

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

    # ------------------------------------------------------------------ #
    _PAT_HUECO_VIDEO = re.compile(
        r"<!--\s*Pegar aqu[ií] el embed de Canvas Studio([^>]*?)-->")

    def _clave_de_pagina(self, titulo: str) -> str:
        """La clave con la que se nombra esta pagina al pasar un video."""
        m = re.match(r"\s*((?:\d+\.)+)", titulo or "")
        if m:
            return m.group(1).rstrip(".")
        return "inicio"

    def _incrustar_videos_de_studio(self):
        """Reemplaza los huecos de video por el embed real.

        El id de Studio no existe cuando se arma el aula —la coleccion se
        comparte al cerrar la maquetacion— asi que el paquete sale con el
        hueco comentado. Cuando los ids llegan, se vuelven a pasar (en la
        columna de enlace de la planilla o con --video) y el mismo paquete
        sale ya con los videos puestos, sin pegarlos a mano uno por uno."""
        pedidos = dict(self.spec.videos_studio or {})
        if not pedidos:
            return
        usados = set(self.videos_puestos)
        for archivo in sorted((self.working / "wiki_content").glob("*.html")):
            html = _leer(archivo)
            if not self._PAT_HUECO_VIDEO.search(html):
                continue
            m = re.search(r"<title>(.*?)</title>", html, re.S)
            titulo = re.sub(r"<[^>]+>", "", m.group(1)).strip() if m else ""
            clave = self._clave_de_pagina(titulo)
            # Un id se usa UNA vez: "inicio" es la clave de toda página sin
            # número, así que el video de bienvenida se repetía en las tres
            # introducciones de módulo, que lo que llevan es su propio hueco.
            if clave in self.videos_puestos:
                continue
            media_id = pedidos.get(clave)
            if not media_id:
                continue
            html = self._PAT_HUECO_VIDEO.sub(
                lambda mm: embed_de_studio(media_id, titulo), html, count=1)
            _escribir(archivo, html)
            usados.add(clave)
            self.videos_puestos.add(clave)
            logger.info(f"Video de Studio incrustado en '{titulo}' ({media_id})")
        for clave in pedidos:
            if clave not in usados:
                self.spec.issues.append(Issue(Severidad.AVISO,
                    f"Me pasaste el video '{clave}' pero no encontre el hueco "
                    "de video en esa pagina: revisa el numero.", "videos"))

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
                elif "sugerida" in txt or "opcional" in txt:
                    # La sugerida se arma clonando: no ocupa el slot de la
                    # obligatoria del aula base. Si el módulo NO pide una
                    # obligatoria (en Gestión del Riesgo, el módulo 1 solo
                    # tiene una sugerida en Padlet), ese slot se queda vacío y
                    # hay que borrarlo, no dejarlo con el placeholder.
                    quedan.add(f"Actividad M{n}")
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
    @staticmethod
    def _nombre_publicado_de_adjunto(path) -> str:
        """El nombre con que se publica el adjunto.

        Sin el "Copia de " que le deja Drive: es ruido del proceso y el
        estudiante lo ve en el enlace ("Copia de Protocolo de
        transparencia.xlsx").
        """
        return re.sub(r"^\s*copia\s+de\s+", "", path.name, flags=re.I)

    def _adjuntar_archivos_del_curso(self, html: str) -> str:
        """Los enlaces a Drive cuyo archivo está en la carpeta del curso
        pasan a apuntar al archivo del paquete.

        El protocolo de transparencia de Metodología II llegó así: las tres
        actividades lo enlazaban a la unidad compartida y el asesor aclaró
        "el archivo debe ser descargable". Enlazando el de Drive la descarga
        depende de los permisos de la unidad y de que nadie mueva la
        carpeta; adentro del paquete, no.

        Solo se reemplaza cuando el archivo está de verdad: un documento
        colaborativo de Google —la grilla del módulo 3, que los estudiantes
        editan— no tiene archivo local y sigue siendo un link a Drive.
        """
        from urllib.parse import quote
        adjuntos = getattr(self.spec, "adjuntos", [])
        if not adjuntos or not html or "http" not in html:
            return html
        soup = BeautifulSoup(html, "html.parser")
        cambio = False
        for a in soup.find_all("a", href=True):
            if not a["href"].lower().startswith("http"):
                continue
            texto = normalizar(a.get_text(" ", strip=True))
            # Un texto corto ("acá", "aquí", "link") no alcanza para decidir
            # a qué archivo se refiere.
            if len(texto) < 8:
                continue
            destino = next((p for p in adjuntos
                            if texto in normalizar(p.stem)), None)
            if destino is None:
                continue
            publicado = self._nombre_publicado_de_adjunto(destino)
            a["href"] = ("$IMS-CC-FILEBASE$/Multimedia%20cargada/"
                         + quote(publicado)
                         + "?canvas_=1&canvas_qs_wrap=1")
            a["class"] = "instructure_file_link instructure_scribd_file"
            a["title"] = publicado
            a["target"] = "_blank"
            self.adjuntos_usados.add(destino)
            cambio = True
        return str(soup) if cambio else html

    def _rutear_media(self, html: str) -> str:
        html = self._adjuntar_archivos_del_curso(html)
        html = (html or "").replace("__MEDIA__/", f"{MEDIA_URL}/")
        # Figuras de DISEÑO: van directo a Multimedia cargada/ (como a mano)
        for path in self.figuras_usadas:
            from urllib.parse import quote
            nombre = nombre_publicado_de_figura(path)
            html = html.replace(f"__DISENO__/{nombre}",
                                "$IMS-CC-FILEBASE$/Multimedia%20cargada/"
                                + quote(nombre))
        return html

    def _cargar_banners(self) -> dict:
        """{clave de página: (nombre a publicar, bytes)} desde el ZIP del
        plugin de Figma, o desde una carpeta con los PNG sueltos."""
        origen = getattr(self.spec, "banners", "")
        if not origen:
            return {}
        origen = Path(origen)
        if not origen.exists():
            self.spec.issues.append(Issue(Severidad.BLOQUEANTE,
                f"No existe el archivo de banners: {origen}", "Banners"))
            return {}
        crudos = []           # [(nombre, bytes)]
        if origen.is_dir():
            for f in sorted(origen.iterdir()):
                if f.suffix.lower() in _EXT_BANNER:
                    crudos.append((f.name, f.read_bytes()))
        else:
            with zipfile.ZipFile(origen) as z:
                for info in z.infolist():
                    nombre = Path(info.filename).name
                    if info.is_dir() or not nombre \
                            or Path(nombre).suffix.lower() not in _EXT_BANNER:
                        continue
                    crudos.append((nombre, z.read(info)))
        banners, repetidos = {}, []
        for nombre, datos in crudos:
            clave = clave_de_banner(nombre)
            if not clave:
                continue
            if clave in banners:
                repetidos.append(nombre)
                continue
            # Se republica con el nombre normalizado: los que subía el equipo
            # a mano venían con "(2)" y con el título pegado, y después nadie
            # sabía cuál correspondía a cuál.
            banners[clave] = (clave + Path(nombre).suffix.lower(), datos)
        if repetidos:
            self.spec.issues.append(Issue(Severidad.AVISO,
                f"{len(repetidos)} banner(s) con la misma numeración que otro: "
                + ", ".join(repetidos[:5]) + ". Usé el primero de cada uno.",
                "Banners"))
        logger.info(f"  {len(banners)} banners leídos de {origen.name}")
        return banners

    _PAT_BANNER_IMG = re.compile(
        r'(<div[^>]*class="dp-banner-image"[^>]*>\s*<img\b)([^>]*?)(/?>)',
        re.I | re.S)

    def _poner_banner(self, html: str, url: str, alt: str) -> str:
        """Cambia el banner del placeholder del aula base por el nuestro."""
        if not url:
            return html
        def _cambiar(m):
            atrib = m.group(2)
            atrib = re.sub(r'\ssrc="[^"]*"', "", atrib)
            atrib = re.sub(r'\salt="[^"]*"', "", atrib)
            return (f'{m.group(1)} src="{url}" alt="{xml_escape(alt)}"'
                    f'{atrib}{m.group(3)}')
        return self._PAT_BANNER_IMG.sub(_cambiar, html, count=1)

    def _banner_de(self, clave: str, titulo: str = "", rotulo: str = "") -> str:
        """URL del banner de esa página, generándolo si hace falta.

        Primero manda lo que venga por --banners (el ZIP del plugin de
        Figma o una carpeta): así se puede pisar cualquiera a mano. Si no
        vino, se dibuja con la plantilla del tema, que es el render del
        diseño oficial sin su capa de texto."""
        from urllib.parse import quote
        entrada = self.banners.get(clave)
        if entrada:
            self.banners_usados.add(clave)
            return f"{BANNER_URL}/{quote(entrada[0])}"
        if not titulo:
            return ""
        nombre = f"{clave}.png"
        if nombre not in self.banners_generados:
            try:
                img = banner_render(titulo, rotulo=rotulo, tema=self.spec.tema)
            except FileNotFoundError as e:
                if not self._aviso_sin_plantilla:
                    self.spec.issues.append(Issue(Severidad.AVISO, str(e),
                                                  "Banners"))
                    self._aviso_sin_plantilla = True
                return ""
            buf = io.BytesIO()
            img.save(buf, "PNG", optimize=True)
            self.banners_generados[nombre] = buf.getvalue()
        return f"{BANNER_URL}/{quote(nombre)}"

    @staticmethod
    def _clave_de_titulo(titulo: str) -> str:
        """"1.3.1. La arquitectura de una neurona" → "1.3.1"."""
        m = re.match(r"\s*(\d+(?:\.\d+)*)", titulo or "")
        return m.group(1).rstrip(".") if m else ""

    def _empaquetar_banners(self):
        if not self.banners and not self.banners_generados:
            return
        carpeta = self.working / BANNER_SUBDIR
        carpeta.mkdir(parents=True, exist_ok=True)
        puestos = 0
        for clave, (nombre, datos) in sorted(self.banners.items()):
            if clave not in self.banners_usados:
                continue
            (carpeta / nombre).write_bytes(datos)
            self.recursos_nuevos.append((_gen_id(), f"{BANNER_SUBDIR}/{nombre}"))
            puestos += 1
        for nombre, datos in sorted(self.banners_generados.items()):
            (carpeta / nombre).write_bytes(datos)
            self.recursos_nuevos.append((_gen_id(), f"{BANNER_SUBDIR}/{nombre}"))
            puestos += 1
        logger.info(f"  {puestos} banners empaquetados en {BANNER_SUBDIR}")
        sobrantes = sorted(set(self.banners) - self.banners_usados)
        if sobrantes:
            self.spec.issues.append(Issue(Severidad.AVISO,
                f"{len(sobrantes)} banner(s) sin página a la que ir: "
                + ", ".join(sobrantes[:8]) + ". Revisá que la numeración "
                "coincida con la de la planilla.", "Banners"))
        faltan = [t for c, t in self.paginas_sin_banner]
        if faltan:
            self.spec.issues.append(Issue(Severidad.AVISO,
                f"{len(faltan)} página(s) quedaron sin banner: "
                + ", ".join(faltan[:6]) + ".", "Banners"))

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
                # Se publica con extensión real aunque el archivo de Diseño
                # no la traiga: si no, Canvas lo sirve como descarga en vez
                # de mostrarlo como imagen.
                nombre = nombre_publicado_de_figura(path)
                shutil.copy2(path, carpeta / nombre)
                self.recursos_nuevos.append(
                    (_gen_id(), f"web_resources/Multimedia cargada/{nombre}"))
            logger.info(f"  {len(self.figuras_usadas)} figuras de DISEÑO empaquetadas")
        # Archivos del curso que alguna actividad enlaza (el protocolo de
        # transparencia): se adjuntan para que la descarga no dependa de los
        # permisos de la unidad compartida de Drive.
        if self.adjuntos_usados:
            carpeta = self.working / "web_resources" / "Multimedia cargada"
            carpeta.mkdir(parents=True, exist_ok=True)
            for path in sorted(self.adjuntos_usados):
                publicado = self._nombre_publicado_de_adjunto(path)
                shutil.copy2(path, carpeta / publicado)
                self.recursos_nuevos.append(
                    (_gen_id(), f"web_resources/Multimedia cargada/{publicado}"))
            logger.info(f"  {len(self.adjuntos_usados)} archivos del curso adjuntados")
        # Repositorio de casos: las fichas se suben como archivos del curso
        # (la planilla las pide como repositorio, no como página propia), y
        # el equipo las enlaza desde donde corresponda.
        casos = list(getattr(self.spec, "casos", []) or [])
        if casos:
            carpeta = self.working / "web_resources" / "Multimedia cargada"
            carpeta.mkdir(parents=True, exist_ok=True)
            for path in casos:
                shutil.copy2(path, carpeta / path.name)
                self.recursos_nuevos.append(
                    (_gen_id(), f"web_resources/Multimedia cargada/{path.name}"))
            self.spec.issues.append(Issue(Severidad.INFO,
                f"{len(casos)} fichas del repositorio de casos subidas a "
                "'Multimedia cargada': " + ", ".join(p.name for p in casos)
                + ". Quedan como archivos del curso, para enlazarlas desde "
                "donde corresponda."))

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
