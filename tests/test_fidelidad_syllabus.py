# -*- coding: utf-8 -*-
"""El esquema de la asignatura en la página 'Programa'.

La planilla lo pide como ítem de inicio ("Esquema introductorio a la
asignatura", con el nombre del archivo al lado) y el equipo lo maqueta en el
syllabus, debajo del índice de contenidos, como bloque "Visión General".
La automatización no lo colocaba: el archivo ni siquiera llegaba al paquete.

Ver docs/auditoria-fidelidad-gestion-calidad-2026-09-10.md
"""

import shutil

import pytest

from maquetador.build.imscc_builder import GeneradorAula
from maquetador.models import (CourseSpec, ItemCurso, FuenteContenido,
                               ModuloCurso, TipoItem, Severidad)


def _generador(tmp_path, nombre_archivo=None):
    """GeneradorAula mínimo con un ítem de esquema en la planilla."""
    g = GeneradorAula.__new__(GeneradorAula)
    g.spec = CourseSpec(nombre="Gestión de la Calidad")
    g.working = tmp_path / "working"
    g.working.mkdir()
    g.recursos_nuevos = []

    archivo = None
    if nombre_archivo:
        archivo = tmp_path / nombre_archivo
        archivo.write_bytes(b"imagen")
    g.spec.items_inicio = [ItemCurso(
        titulo="Esquema introdutorio a la asignatura",
        tipo=TipoItem.IMAGEN,
        fuente=FuenteContenido(archivo=archivo))]
    return g


class TestBloqueEsquema:
    def test_arma_el_bloque_vision_general(self, tmp_path):
        html = _generador(tmp_path, "M_Esquema.jpg")._bloque_esquema()
        assert 'data-title="Esquema del módulo"' in html
        assert "fa-network-wired" in html
        assert "Visión General</h2>" in html

    def test_la_imagen_va_centrada_y_con_borde_estatico(self, tmp_path):
        html = _generador(tmp_path, "M_Esquema.jpg")._bloque_esquema()
        assert '<p style="text-align: center;">' in html
        assert "dp-image-rounded-10" in html and "dp-image-bordered" in html
        assert "dp-popup-image" not in html

    def test_la_imagen_tiene_width_600_para_no_quedar_estirada(self, tmp_path):
        html = _generador(tmp_path, "M_Esquema.jpg")._bloque_esquema()
        assert "width: 600px; height: auto;" in html

    def test_tiene_texto_alternativo(self, tmp_path):
        html = _generador(tmp_path, "M_Esquema.jpg")._bloque_esquema()
        assert 'alt="Esquema de la asignatura"' in html

    def test_copia_el_archivo_y_lo_registra_como_recurso(self, tmp_path):
        g = _generador(tmp_path, "M_Esquema.jpg")
        g._bloque_esquema()
        destino = g.working / "web_resources" / "Multimedia cargada" / "M_Esquema.jpg"
        assert destino.exists()
        assert any(r.endswith("M_Esquema.jpg") for _, r in g.recursos_nuevos)

    def test_avisa_si_la_planilla_lo_pide_pero_no_hay_imagen(self, tmp_path):
        g = _generador(tmp_path, nombre_archivo=None)
        assert g._bloque_esquema() == ""
        assert any(i.severidad == Severidad.AVISO and "esquema" in i.mensaje.lower()
                   for i in g.spec.issues)

    def test_ignora_un_archivo_que_no_es_imagen(self, tmp_path):
        """En la carpeta conviven 'M_Esquema.jpg' y el .pptx original."""
        g = _generador(tmp_path, "Esquema Gestión de la Calidad.pptx")
        assert g._bloque_esquema() == ""

    def test_sin_esquema_en_la_planilla_no_agrega_nada_ni_avisa(self, tmp_path):
        g = _generador(tmp_path, "M_Esquema.jpg")
        g.spec.items_inicio = []
        assert g._bloque_esquema() == ""
        assert g.spec.issues == []


class TestIndiceDeContenidosAcordeon:
    """El acordeón 'Contenido' del programa (Bloque 2 de _construir_syllabus)
    debe traer las TRES clases de color (normal/activo/hover), igual que
    cualquier otro acordeón del curso: si le falta dp-panel-hover-color-*
    el tema pinta el hover con un color por defecto que queda invertido
    respecto al resto de los desplegables del aula."""

    def test_el_wrapper_trae_las_tres_clases_de_color(self, tmp_path):
        g = GeneradorAula.__new__(GeneradorAula)
        g.spec = CourseSpec(nombre="Gestión de la Calidad")
        g.working = tmp_path / "working"
        (g.working / "course_settings").mkdir(parents=True)
        g.recursos_nuevos = []
        g.paginas_por_modulo = {1: [("pid1", "1.1. Página uno")]}
        modulo = ModuloCurso(numero=1, titulo="Introducción")
        g.spec.modulos = [modulo]
        g.spec.items_inicio = []
        syl_path = g.working / "course_settings" / "syllabus.html"
        syl_path.write_text(
            '<div class="dp-content-block kl_custom_block_1">x</div>'
            '<div class="dp-content-block kl_custom_block_2">x</div>'
            '<div class="dp-content-block kl_custom_block_3">x</div>',
            encoding="utf-8")
        g._construir_syllabus()
        html = syl_path.read_text(encoding="utf-8")
        assert "dp-panel-color-dp-primary" in html
        assert "dp-panel-active-color-dp-secondary" in html
        assert "dp-panel-hover-color-dp-secondary" in html


class TestBibliografiaConsolidada:
    def _generador(self, tmp_path):
        g = GeneradorAula.__new__(GeneradorAula)
        g.spec = CourseSpec(nombre="Gestión de la Calidad")
        g.working = tmp_path / "working"
        g.working.mkdir()
        g.recursos_nuevos = []
        g.figuras_usadas = []
        modulo = ModuloCurso(numero=1, titulo="Introducción")
        modulo.extras = {"referencias":
            "<p>Autor, A. (2020). Un libro. Obligatoria</p>"
            "<p>Obligatoria</p>"
            "<p>Autor, A. (2020). Un libro cualquiera. https://ejemplo.com</p>"}
        g.spec.modulos = [modulo]
        return g

    def test_hay_aire_entre_el_titulo_de_modulo_y_obligatoria(self, tmp_path):
        g = self._generador(tmp_path)
        html = g._construir_bibliografia_consolidada("")
        assert "<strong><span" in html
        # el <p>&nbsp;</p> de aire va justo antes del cuerpo con "Obligatoria"
        idx_spacer = html.index("<p>&nbsp;</p>")
        idx_obligatoria = html.index("Obligatoria</h4>")
        assert idx_spacer < idx_obligatoria
