# -*- coding: utf-8 -*-
"""Convenciones que trajo "El Pricing y el Abordaje Estratégico de los Mercados".

La carpeta y la planilla de esta materia traían tres cosas que el generador
no leía: la foto del docente nombrada por lo que es, la consigna del foro
encabezada con "Texto:" a secas, y material de cursada que viaja en la
carpeta sin una fila que lo ubique.
"""

import pytest

from maquetador.ingest.folder_scanner import escanear
from maquetador.ingest.xlsx_parser import _texto_inline, FilaPlanilla
from maquetador.build.imscc_builder import GeneradorAula


class TestFotoDelDocentePorElNombre:
    """La foto vive en la etapa del programa, junto al DOCX y a una imagen
    conceptual. Ninguna de las carpetas que el escáner reconocía la cubría,
    así que el ítem salía "sin fuente" aunque el archivo dijera qué es."""

    def _curso(self, tmp_path, nombre):
        from PIL import Image
        raiz = tmp_path / "Pricing"
        etapa = raiz / "Etapa 1_ Programa, hoja de ruta y bibliografía"
        etapa.mkdir(parents=True)
        (raiz / "Etapa 2_ Materiales multimediales y actividades").mkdir()
        Image.new("RGB", (400, 400)).save(etapa / nombre)
        return raiz

    @pytest.mark.parametrize("nombre", [
        "Fotografía del profesor.jpg",
        "Foto docente.jpg",
        "fotografia_de_la_profesora.png",
    ])
    def test_el_nombre_alcanza_sin_mirar_la_carpeta(self, tmp_path, nombre):
        inv = escanear(self._curso(tmp_path, nombre))
        assert [p.name for p in inv.fotos_docente] == [nombre]

    def test_una_imagen_cualquiera_de_esa_carpeta_no_es_la_foto(self, tmp_path):
        inv = escanear(self._curso(tmp_path, "Conceptualización.jpg"))
        assert inv.fotos_docente == []


class TestConsignaEncabezadaConTexto:
    """Parte de asesoría encabeza la consigna con "Texto:" a secas, no con
    "Texto del foro:". Sin reconocerlo, el foro del módulo salía vacío aunque
    su texto estuviera en la misma fila de la planilla."""

    def _fila(self, modalidad):
        return FilaPlanilla(bloque="", item="Foro", modalidad=modalidad)

    def test_texto_a_secas(self):
        cuerpo = _texto_inline(self._fila(
            "Texto: \nForo de Consultas - Actividad Obligatoria Grupal\n"
            "Estimados Maestrandos, les damos la bienvenida."))
        assert cuerpo.startswith("Foro de Consultas")
        assert "Estimados Maestrandos" in cuerpo

    def test_las_formas_de_siempre_siguen_andando(self):
        assert _texto_inline(self._fila("Texto del foro: Bienvenidos.")) \
            == "Bienvenidos."

    def test_una_celda_cualquiera_no_es_una_consigna(self):
        assert _texto_inline(self._fila("👥 GRUPAL")) == ""


class TestMaterialSueltoDeLaCarpeta:
    """Los casos que el docente usa en las actividades viajan en la carpeta
    sin una fila que los ubique. No se pueden colocar solos, pero tampoco se
    tiran: se publican en los archivos del aula para enlazarlos a mano."""

    def test_los_papeles_del_proceso_no_se_publican(self):
        pat = GeneradorAula._NO_PUBLICABLE
        for nombre in ("Plantilla Material multimedial modular M1.docx",
                       "Cronograma (Horacio D_Esposito).xlsx",
                       "Protocolo de transparencia (1).xlsx",
                       "GAIDET.docx",
                       "001. 1323-22.RR MAESTRIA EN GESTIÓN.pdf",
                       "EJEMPLO - El_Árbol_de_Problemas.png"):
            assert pat.search(nombre), nombre

    def test_el_material_de_cursada_si(self):
        pat = GeneradorAula._NO_PUBLICABLE
        for nombre in ("Llao Llao_ Setting a Pricing Strategy.pdf",
                       "Pricing at Netflix.pdf",
                       "Detalle páginas Nagle.xlsx",
                       "Conceptualización.JPG"):
            assert not pat.search(nombre), nombre

    def test_el_pptx_queda_afuera(self):
        """Cuando aparece es el archivo fuente de algo que ya se publica
        hecho (el esquema, las placas del video)."""
        assert ".pptx" not in GeneradorAula._EXT_PUBLICABLES
        assert ".pdf" in GeneradorAula._EXT_PUBLICABLES
