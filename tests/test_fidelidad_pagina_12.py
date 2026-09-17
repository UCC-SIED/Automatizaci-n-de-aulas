# -*- coding: utf-8 -*-
"""Correcciones de la revisión del aula en Canvas (hasta la página 1.2).

Ver docs/auditoria-fidelidad-gestion-calidad-2026-09-10.md
"""

import pytest
from bs4 import BeautifulSoup

from maquetador.build.snippets import (procesar_contenido,
                                       quitar_encabezado_plantilla)
from maquetador.ingest.folder_scanner import _PARECE_RETRATO, normalizar
from maquetador.ingest.docx_comments import aplicar_comentarios


class TestCaratulaDePlantilla:
    """El DOCX abre con la carátula del formulario: título + tabla de
    metadatos. El foro tiene que empezar en "¡Hola a todos!"."""

    HTML = ('<h3>FORO DE APERTURA</h3>'
            '<table><tr><td>Unidad académica</td><td>Escuela de Posgrado</td></tr>'
            '<tr><td>Carrera</td><td>MAESTRÍA EN DIRECCIÓN</td></tr>'
            '<tr><td>Asignatura</td><td>Gestión de la Calidad</td></tr></table>'
            '<p>¡Hola a todos!</p>')

    def test_saca_la_tabla_de_metadatos(self):
        assert "Unidad académica" not in procesar_contenido(self.HTML)

    def test_saca_el_titulo_repetido(self):
        assert "FORO DE APERTURA" not in procesar_contenido(self.HTML)

    def test_arranca_en_el_contenido(self):
        assert procesar_contenido(self.HTML).strip().startswith("<p>¡Hola")

    def test_no_toca_una_tabla_de_datos_del_medio(self):
        html = ("<p>Un párrafo largo que abre la página con su contenido.</p>"
                "<p>Otro párrafo más de desarrollo del tema.</p>"
                "<table><tr><td>Criterio</td><td>Descripción</td></tr>"
                "<tr><td>Exactitud</td><td>Precisión del cálculo.</td></tr></table>")
        assert "<table" in procesar_contenido(html)

    def test_reconoce_la_variante_nombre_de_la_carrera(self):
        """La AFI usa "Nombre de la carrera"/"Nombre del módulo" en vez de
        "Carrera" a secas: con esos rótulos no reconocidos, la carátula
        nunca se sacaba (solo "Asignatura" hacía match, 1 de 3 — no
        alcanzaba el piso de 2 rótulos)."""
        html = ('<table><tr><th>Nombre de la carrera</th>'
                '<th>Maestría en Dirección Estratégica de Proyectos</th></tr>'
                '<tr><td>Asignatura</td><td>Gestión de la Calidad</td></tr>'
                '<tr><td>Nombre del módulo</td><td>AFI</td></tr></table>'
                '<p>Analizá situaciones reales</p>')
        out = procesar_contenido(html)
        assert "Nombre de la carrera" not in out
        assert "Analizá situaciones reales" in out


class TestTabsConTituloEnNegrita:
    """"TABS horizontal … poner Principio 1 / Principio 2 y el título dentro
    del TAB": la negrita marca SOLO el rótulo, el resto es contenido."""

    HTML = ("<div><p>A continuación se desarrollan los principios.</p>"
            "<p><strong>Principio N.° 1</strong>: Enfoque al cliente</p>"
            "<p>La alineación hacia la satisfacción de necesidades.</p>"
            "<p><strong>Principio N.° 2</strong>: Liderazgo</p>"
            "<p>El liderazgo define el rumbo.</p></div>")

    def _aplicar(self, instruccion):
        soup = BeautifulSoup(self.HTML, "html.parser")
        c = [{"instruccion": instruccion, "anclado": "Principio N.° 1",
              "accion": "tabs", "autor": ""}]
        aplicar_comentarios(soup, c)
        return str(soup), c[0]

    @pytest.mark.parametrize("instruccion", [
        "Para maquetación: TABS horizontal (palabras en negrita)",
        # Sin nombrar la forma: se prueban los modos y gana el que sirve.
        "Para maquetación: TABS horizontal Aclaración: si no entra el título "
        "completo poner Principio 1 / Principio 2 y el título dentro del TAB",
    ])
    def test_arma_las_solapas_pese_a_la_redaccion(self, instruccion):
        out, c = self._aplicar(instruccion)
        assert c.get("_aplicado") is True
        assert out.count('class="dp-panel-group"') == 2

    def test_el_rotulo_es_solo_la_parte_en_negrita(self):
        out, _ = self._aplicar("TABS horizontal (palabras en negrita)")
        assert 'dp-panel-heading">Principio N.° 1</h3>' in out

    def test_el_resto_de_la_linea_queda_de_contenido(self):
        out, _ = self._aplicar("TABS horizontal (palabras en negrita)")
        assert "Enfoque al cliente" in out
        assert 'dp-panel-heading">Principio N.° 1: Enfoque' not in out


class TestRecuadroDuplicado:
    def test_el_recuadro_dentro_de_otro_queda_uno_solo(self):
        html = ('<div class="dp-callout dp-callout-color-lg-tip card">'
                '<div class="card-body">'
                '<div class="dp-callout dp-callout-color-lg-tip card">'
                '<div class="card-body"><p>La misma frase.</p></div></div>'
                "</div></div>")
        out = procesar_contenido(html)
        assert out.count("dp-callout dp-callout-color-lg-tip") == 1


class TestEspaciadoDeRecuadros:
    def test_el_recuadro_con_titulo_lleva_parrafo_entero_si_no_esta_encerrado(self):
        """Un recuadro con título que ABRE o CIERRA una sección (acá, pegado
        a un h3) lleva el aire de párrafo entero — no está "encerrado entre
        texto", así que no aplica el espaciado corto."""
        html = ("<h3>Un tema</h3>"
                "<table><tr><td>Reflexiona</td></tr>"
                "<tr><td>¿Qué pensás de esto?</td></tr></table>"
                "<p>Texto posterior.</p>")
        out = procesar_contenido(html)
        assert out.count("<p>\xa0</p>") >= 1

    def test_el_recuadro_con_titulo_encerrado_entre_texto_lleva_espaciado_corto(self):
        """Un recuadro con título que interrumpe un tramo de texto corrido
        (párrafo antes Y después, sin abrir/cerrar sección) se ve exagerado
        con el párrafo entero: lleva el mismo aire corto que el simple."""
        html = ("<p>Texto previo.</p>"
                "<table><tr><td>Reflexiona</td></tr>"
                "<tr><td>¿Qué pensás de esto?</td></tr></table>"
                "<p>Texto posterior.</p>")
        out = procesar_contenido(html)
        assert out.count("<p>\xa0</p>") == 0
        assert "<br/>" in out or "<br>" in out

    def test_el_recuadro_simple_lleva_espaciado_corto(self):
        """'los recuadros simples llevan un espaciado menor… shift enter'."""
        html = ("<p>Texto previo que introduce.</p>"
                "<blockquote><p>Una frase corta destacada.</p></blockquote>"
                "<p>Sigue el texto.</p>")
        out = procesar_contenido(html)
        assert "<br/>" in out or "<br>" in out
        assert "<p>\xa0</p>" not in out


class TestBiodata:
    """La planilla nombra el archivo "Biodata" y el escáner solo reconocía
    "biografía"/"CV": la titulación del docente salía "sin fuente" aunque el
    archivo estuviera en la carpeta."""

    def test_biodata_se_clasifica_como_biografia(self, tmp_path):
        from maquetador.ingest.folder_scanner import escanear
        etapa = tmp_path / "Etapa 4_ Maquetación"
        etapa.mkdir(parents=True)
        (etapa / "Biodata.docx").write_bytes(b"x")
        inv = escanear(tmp_path)
        assert [f.name for f in inv.biografia] == ["Biodata.docx"]

    def test_sigue_reconociendo_las_otras_formas(self, tmp_path):
        from maquetador.ingest.folder_scanner import escanear
        etapa = tmp_path / "Etapa 4_ Maquetación"
        etapa.mkdir(parents=True)
        (etapa / "Biografía del docente.docx").write_bytes(b"x")
        inv = escanear(tmp_path)
        assert len(inv.biografia) == 1

    def test_la_heuristica_de_retrato_sigue_andando(self):
        assert _PARECE_RETRATO(normalizar("EMILIANO MARINO 2"))
        assert not _PARECE_RETRATO(normalizar("video-01"))


class TestEspaciadoDeH4:
    """"h4 los 2 primeros... le faltó un párrafo de espacio arriba".

    El espaciador de subtítulos solo cubría <h3>; el sub-subtítulo
    (docx_comments lo marca como <h4>) quedaba pegado al párrafo anterior.
    """

    def test_el_h4_lleva_aire_arriba(self):
        from maquetador.build.snippets import procesar_contenido
        html = ("<p>Texto previo que cierra un párrafo normal.</p>"
                "<h4>Sub-subtítulo suelto</h4>"
                "<p>Contenido que sigue.</p>")
        out = procesar_contenido(html)
        assert out.index("<p>\xa0</p>") < out.index("<h4>")

    def test_no_duplica_el_aire_si_ya_estaba(self):
        from maquetador.build.snippets import procesar_contenido
        html = ("<p>Texto previo.</p><p>&nbsp;</p>"
                "<h4>Sub-subtítulo</h4><p>Contenido.</p>")
        out = procesar_contenido(html)
        assert out.count("<p>\xa0</p>") == 1

    def test_el_h4_de_un_panel_no_se_toca(self):
        """dp-panel-heading tiene clase: el filtro "sin clase" lo excluye."""
        from maquetador.build.snippets import procesar_contenido
        html = ('<div class="dp-panels-wrapper dp-expander-default">'
                '<div class="dp-panel-group">'
                '<h4 class="dp-panel-heading">Título</h4>'
                '<div class="dp-panel-content"><p>x</p></div></div></div>')
        out = procesar_contenido(html)
        assert '<h4 class="dp-panel-heading">Título</h4>' in out
