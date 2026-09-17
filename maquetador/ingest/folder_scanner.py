# -*- coding: utf-8 -*-
"""Escáner de la carpeta de curso que envía asesoría.

No asume una convención de nombres fija: clasifica cada archivo por su rol
(estructura, contenido modular, actividad, foro, guion de video, diseño…)
usando patrones sobre nombres normalizados y la ubicación relativa.

Convenciones observadas en casos reales (todas soportadas):
  A) "1- Programa…", "4- Desarrollo teórico por módulos", "6- Maquetación"
  B) "Etapa 1" … "Etapa 4"
  C) "a - Etapa 1_ Programa" … "d - Etapa 4_ Maquetación"
"""

import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from maquetador.models import Issue, Severidad


def normalizar(texto: str) -> str:
    """minúsculas + sin acentos + espacios colapsados."""
    t = unicodedata.normalize("NFKD", texto)
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", t.lower()).strip()


# Archivos que son borradores o material descartado: nunca son fuente.
# Los informes de similitud y de uso de IA son control interno de la cátedra
# (Turnitin, declaración GAIDeT): acompañan al material pero no se publican.
_DESCARTAR = re.compile(
    r"(borrador|copia de|elimina(r|da)|despues se borra|devoluci|"
    r"versi[óo]n anterior|^no_|^~\$|[-–—]\s*similitud|"
    r"informe de uso de ia|[-–—]\s*uso de ia)", re.I)

# Imágenes que comparten carpeta con la foto del docente pero NO son un
# retrato: fotogramas y miniaturas de la grabación, capturas de pantalla,
# logos y placeholders de banner.
_NO_ES_RETRATO = re.compile(
    r"(^|[-_\s])(video|videos|frame|fotograma|thumb|thumbnail|miniatura|"
    r"captura|screenshot|pantalla|logo|isologo|banner|portada|caratula|"
    r"slide|placeholder|plantilla)([-_\s]|\d|$)", re.I)


def _PARECE_RETRATO(nombre_normalizado: str) -> bool:
    """¿El nombre del archivo es compatible con una foto de docente?"""
    return not _NO_ES_RETRATO.search(nombre_normalizado)

# Carpeta(s) en la ruta que marcan material no usable
_CARPETAS_DESCARTAR = ("borrador", "borradores", "devoluciones",
                       "version anterior", "versiones anterior")

# Ficha de caso ("Ficha_Caso_Disney", "Modulo 1 - Caso_Starbucks"): es un
# anexo del módulo —el repositorio de casos que pide la planilla—, no el
# desarrollo teórico. Se pide la forma "Ficha_Caso…" o el "Caso_" unido por
# guion bajo (así se nombran las fichas) para no llevarse por delante un
# título común que arranca igual ("Casos de estudio", "Caso práctico
# integrador"), que sí puede ser el desarrollo del módulo.
_PAT_FICHA_CASO = re.compile(r"(?:^|[-_\s])(?:ficha[_\s-]*caso|caso_)", re.I)

_PAT_MODULO_NUM = re.compile(
    r"(?:m[óo]dul[a-z]*[\s_]*(\d+)|(?:^|[-_\s])m[\s_]?(\d+)(?![a-z0-9])|"
    r"\bm(\d+)(?![a-z0-9]))", re.I)

# Romanos SOLO pegados a "módulo"/"modular" (así "Material multimedial modular
# III" → 3, pero "modular video" no toma la v/i como número).
_PAT_MODULO_ROMANO = re.compile(
    r"(?:m[óo]dulo|modular)[\s_]+([ivxl]+)(?![a-z])", re.I)

_ROMANO = {"i": 1, "v": 5, "x": 10, "l": 50}


def _romano_a_int(r: str) -> int:
    total, prev = 0, 0
    for c in reversed(r.lower()):
        v = _ROMANO.get(c, 0)
        total += -v if v < prev else v
        prev = max(prev, v)
    return total


def _numero_modulo(nombre: str) -> Optional[int]:
    m = _PAT_MODULO_NUM.search(nombre)
    if m:
        return int(next(g for g in m.groups() if g))
    mr = _PAT_MODULO_ROMANO.search(nombre)
    if mr:
        n = _romano_a_int(mr.group(1))
        if 1 <= n <= 20:
            return n
    return None


@dataclass
class InventarioCurso:
    """Resultado del escaneo: cada archivo relevante clasificado por rol."""
    raiz: Path
    nombre_curso: str = ""
    estructura_xlsx: Optional[Path] = None
    docx_modulos: dict = field(default_factory=dict)      # {n: Path} desarrollo teórico
    actividades: list = field(default_factory=list)       # [(n|None, Path)]
    foros: list = field(default_factory=list)             # [(n|None, Path)]
    guiones_video: list = field(default_factory=list)     # [(n|None, Path)]
    programa: list = field(default_factory=list)          # PDF/DOCX del programa
    hoja_de_ruta: list = field(default_factory=list)
    biografia: list = field(default_factory=list)
    fotos_docente: list = field(default_factory=list)
    imagenes_diseno: list = field(default_factory=list)   # figuras/esquemas/tablas
    esquema: list = field(default_factory=list)           # esquema introductorio
    casos: list = field(default_factory=list)             # [(n|None, Path)] fichas de caso
    otros: list = field(default_factory=list)
    issues: list = field(default_factory=list)

    def to_dict(self):
        def _l(x):
            return [str(p) for p in x] if x and not isinstance(x[0], tuple) else \
                   [{"modulo": n, "archivo": str(p)} for n, p in x]
        return {
            "raiz": str(self.raiz), "nombre_curso": self.nombre_curso,
            "estructura_xlsx": str(self.estructura_xlsx) if self.estructura_xlsx else None,
            "docx_modulos": {n: str(p) for n, p in sorted(self.docx_modulos.items())},
            "actividades": _l(self.actividades), "foros": _l(self.foros),
            "guiones_video": _l(self.guiones_video), "programa": _l(self.programa),
            "hoja_de_ruta": _l(self.hoja_de_ruta), "biografia": _l(self.biografia),
            "fotos_docente": _l(self.fotos_docente),
            "imagenes_diseno": _l(self.imagenes_diseno), "esquema": _l(self.esquema),
            "casos": _l(self.casos),
            "issues": [i.to_dict() for i in self.issues],
        }


def _encontrar_raiz(carpeta: Path) -> Path:
    """Los ZIP de Drive suelen envolver todo en 1-2 niveles de carpeta única."""
    raiz = carpeta
    for _ in range(3):
        hijos = [h for h in raiz.iterdir() if not h.name.startswith(".")]
        if len(hijos) == 1 and hijos[0].is_dir():
            raiz = hijos[0]
        else:
            break
    return raiz


def _descartable(path: Path, raiz: Path) -> bool:
    rel = path.relative_to(raiz)
    if _DESCARTAR.search(path.name):
        return True
    for parte in rel.parts[:-1]:
        n = normalizar(parte)
        if any(n.startswith(c) or c in n for c in _CARPETAS_DESCARTAR):
            return True
    return False


def escanear(carpeta: Path) -> InventarioCurso:
    raiz = _encontrar_raiz(Path(carpeta))
    # Nombre del curso: nombre de la carpeta raíz sin el prefijo de orden
    # ("16. Agile Project Management" → "Agile Project Management").
    nombre = re.sub(r"^\s*\d+\s*[-._)]\s*", "", raiz.name.strip()).strip()
    inv = InventarioCurso(raiz=raiz, nombre_curso=nombre or raiz.name.strip())

    for path in sorted(raiz.rglob("*")):
        if not path.is_file():
            continue
        if _descartable(path, raiz):
            continue

        nombre = normalizar(path.name)
        carpeta_padre = normalizar(str(path.parent.relative_to(raiz)))
        ext = path.suffix.lower()
        num = _numero_modulo(path.name)

        # --- Planilla de estructura (la lleva la etapa de maquetación) ---
        if ext == ".xlsx" and "estructura" in nombre and "maquetaci" in nombre:
            if inv.estructura_xlsx:
                inv.issues.append(Issue(Severidad.AVISO,
                    f"Hay más de una planilla de estructura; uso '{inv.estructura_xlsx.name}' "
                    f"y descarto '{path.name}'. Verificar cuál es la vigente."))
            else:
                inv.estructura_xlsx = path
            continue

        if ext == ".xlsx" and "cronograma" in nombre:
            inv.otros.append(path)
            continue

        # --- DOCX ---
        if ext == ".docx":
            if "foro" in nombre:
                inv.foros.append((num, path))
            elif _PAT_FICHA_CASO.search(nombre):
                # Anexo del módulo (repositorio de casos), no su desarrollo
                # teórico: si compite por el slot del módulo le gana al
                # multimedial real solo por orden alfabético.
                inv.casos.append((num, path))
            elif "actividad" in nombre or re.search(r"(?<![a-z])afi(?![a-z])", nombre):
                # "afi" como palabra aislada. Se usa lookaround de LETRAS (no \b)
                # porque '_' es carácter de palabra y \bafi\b no matchea "AFI_…"
                # (nombre real: "AFI_ El liderazgo desde mi mirada.docx").
                inv.actividades.append((num, path))
            elif "video" in nombre or "guion" in nombre or "audiovisual" in nombre \
                    or ("grabaci" in carpeta_padre and "biograf" not in nombre):
                inv.guiones_video.append((num, path))
            elif "biograf" in nombre or "biodata" in nombre \
                    or "curriculum" in nombre \
                    or re.search(r"\bcv\b", nombre) \
                    or "presentacion" in nombre and "foro" not in nombre:
                # "biodata" es como lo nombra la planilla en varios cursos y
                # quedaba sin clasificar: la titulación del docente salía
                # "sin fuente" aunque el archivo estuviera en la carpeta.
                inv.biografia.append(path)
            elif "hoja de ruta" in nombre or "hoja_de_ruta" in nombre:
                inv.hoja_de_ruta.append(path)
            elif "programa" in nombre:
                inv.programa.append(path)
            elif "esquema" in nombre:
                inv.esquema.append(path)
            elif "plantilla" in nombre:
                # Las plantillas vacías que reparte asesoría no son contenido.
                inv.otros.append(path)
            elif ("modulo" in nombre or "multimedial" in nombre or num is not None) \
                    and ("multimedial" in carpeta_padre or "modulo" in carpeta_padre
                         or "desarrollo" in carpeta_padre or "multimedial" in nombre
                         or "modulo" in nombre):
                if num is None:
                    num = _numero_modulo(carpeta_padre) or 0
                if num in inv.docx_modulos:
                    # Ante conflicto, gana el "material multimedial modular" (el
                    # desarrollo teórico canónico) sobre guías/organizadores/
                    # anexos que solo mencionan "módulo N".
                    actual = inv.docx_modulos[num]
                    nuevo_es_mm = "material multimedial" in nombre
                    actual_es_mm = "material multimedial" in normalizar(actual.name)
                    if nuevo_es_mm and not actual_es_mm:
                        inv.otros.append(actual)
                        inv.docx_modulos[num] = path
                    elif not nuevo_es_mm and actual_es_mm:
                        inv.otros.append(path)
                    else:
                        inv.issues.append(Issue(Severidad.AVISO,
                            f"Más de un DOCX para el módulo {num}: ya tenía "
                            f"'{actual.name}', apareció '{path.name}'. "
                            "Verificar cuál es la versión final.", f"Módulo {num}"))
                else:
                    inv.docx_modulos[num] = path
            else:
                inv.otros.append(path)
            continue

        # --- PDFs ---
        if ext == ".pdf":
            if "programa" in nombre and "10a" not in nombre:
                inv.programa.append(path)
            elif "hoja de ruta" in nombre:
                inv.hoja_de_ruta.append(path)
            elif _PAT_FICHA_CASO.search(nombre):
                # El PDF de la ficha (el que sale de diseño) es la versión
                # publicable del repositorio de casos.
                inv.casos.append((num, path))
            else:
                inv.otros.append(path)
            continue

        # --- Imágenes ---
        if ext in (".jpg", ".jpeg", ".png", ".gif", ".webp"):
            if re.search(r"(figura|fig\b|fig\s|tabla|m_?\d)", nombre):
                inv.imagenes_diseno.append(path)
            elif "esquema" in nombre:
                inv.esquema.append(path)
            elif "diseno" in carpeta_padre or "diseño" in carpeta_padre:
                inv.imagenes_diseno.append(path)
            elif "grabaci" in carpeta_padre or "maquetaci" in carpeta_padre \
                    or "etapa 3" in carpeta_padre or "etapa 4" in carpeta_padre \
                    or ("foto" in carpeta_padre and "docente" in carpeta_padre):
                # La foto del docente viene con el material de grabación, en
                # la etapa de maquetación, o en una carpeta dedicada "Foto (y
                # CV) docente". En esas carpetas conviven con capturas y
                # miniaturas de video: si el nombre delata que no es un
                # retrato, no puede terminar de foto del docente (ya pasó:
                # "video-01.jpg" salió publicado como la foto del profesor).
                if _PARECE_RETRATO(nombre):
                    inv.fotos_docente.append(path)
                else:
                    inv.otros.append(path)
            else:
                inv.otros.append(path)
            continue

        inv.otros.append(path)

    # --- Validaciones globales ---
    if not inv.estructura_xlsx:
        inv.issues.append(Issue(Severidad.BLOQUEANTE,
            "No se encontró la planilla 'Estructura general - Para maquetación'. "
            "Sin ella no se puede armar la estructura del aula automáticamente."))
    if not inv.docx_modulos:
        inv.issues.append(Issue(Severidad.BLOQUEANTE,
            "No se encontró ningún DOCX de desarrollo teórico/material multimedial de módulos."))
    return inv
