# -*- coding: utf-8 -*-
"""Modelo canónico del curso, independiente del formato de origen.

Todo parser (XLSX viejo/nuevo, carpetas, DOCX) produce estas estructuras;
todo generador (.imscc) las consume. Nada fuera de este módulo debe
depender del formato específico en que llegó la información.
"""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional


class TipoItem(str, Enum):
    PAGINA = "pagina"               # página de contenido (sección del DOCX)
    INTRO_MODULO = "intro_modulo"   # texto introductorio + objetivos del módulo
    FORO = "foro"
    VIDEO = "video"
    TAREA = "tarea"
    EVALUACION = "evaluacion"
    ARCHIVO = "archivo"             # PDF u otro adjunto (programa, hoja de ruta)
    IMAGEN = "imagen"               # esquema, fotografía del docente
    OTRO = "otro"


class Severidad(str, Enum):
    INFO = "info"
    AVISO = "aviso"        # se puede generar, pero conviene revisar
    BLOQUEANTE = "bloqueante"  # falta algo imprescindible para este ítem


@dataclass
class Issue:
    """Problema o ambigüedad detectada durante el análisis."""
    severidad: Severidad
    mensaje: str
    contexto: str = ""  # ej. "Módulo 1 > 1.3. Soluciones"

    def to_dict(self):
        return {"severidad": self.severidad.value, "mensaje": self.mensaje,
                "contexto": self.contexto}


@dataclass
class FuenteContenido:
    """De dónde sale el contenido de un ítem: archivo y, si aplica,
    sección segmentada dentro de ese archivo."""
    archivo: Optional[Path] = None
    seccion: Optional[str] = None      # ej. "1.3" dentro del DOCX del módulo
    html: Optional[str] = None         # contenido ya segmentado/renderizado
    confianza: float = 0.0             # 0-1: qué tan seguro fue el matching

    def to_dict(self):
        return {"archivo": str(self.archivo) if self.archivo else None,
                "seccion": self.seccion, "confianza": round(self.confianza, 2),
                "tiene_html": bool(self.html)}


@dataclass
class ItemCurso:
    titulo: str
    tipo: TipoItem
    orden: int = 0
    fuente: FuenteContenido = field(default_factory=FuenteContenido)
    estado_planilla: str = ""          # lo que dice la columna ESTADO del XLSX
    comentarios_asesor: str = ""
    detalle: dict = field(default_factory=dict)  # modalidad, tipo entrega, puntos…
    issues: list = field(default_factory=list)

    def to_dict(self):
        return {"titulo": self.titulo, "tipo": self.tipo.value, "orden": self.orden,
                "fuente": self.fuente.to_dict(), "estado_planilla": self.estado_planilla,
                "comentarios_asesor": self.comentarios_asesor, "detalle": self.detalle,
                "issues": [i.to_dict() for i in self.issues]}


@dataclass
class ModuloCurso:
    numero: int
    titulo: str
    items: list = field(default_factory=list)  # list[ItemCurso]

    def to_dict(self):
        return {"numero": self.numero, "titulo": self.titulo,
                "items": [i.to_dict() for i in self.items]}


@dataclass
class CourseSpec:
    """Especificación canónica de un curso lista para maquetar."""
    nombre: str
    codigo: str = ""                   # ej. EP00356
    carpeta_origen: Optional[Path] = None
    tema: str = ""                     # aula base elegida: educacion | posgrado
    docentes: list = field(default_factory=list)
    items_inicio: list = field(default_factory=list)   # página de inicio, programa…
    modulos: list = field(default_factory=list)        # list[ModuloCurso]
    afi: list = field(default_factory=list)            # actividad final integradora
    issues: list = field(default_factory=list)         # issues globales del curso
    recursos_html: list = field(default_factory=list)  # herramientas .html sueltas

    def todos_los_items(self):
        for it in self.items_inicio:
            yield it
        for m in self.modulos:
            yield from m.items
        yield from self.afi

    def to_dict(self):
        return {"nombre": self.nombre, "codigo": self.codigo,
                "carpeta_origen": str(self.carpeta_origen) if self.carpeta_origen else None,
                "tema": self.tema, "docentes": self.docentes,
                "items_inicio": [i.to_dict() for i in self.items_inicio],
                "modulos": [m.to_dict() for m in self.modulos],
                "afi": [i.to_dict() for i in self.afi],
                "issues": [i.to_dict() for i in self.issues]}
