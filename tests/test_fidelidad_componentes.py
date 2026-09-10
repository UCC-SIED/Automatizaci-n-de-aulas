# -*- coding: utf-8 -*-
"""Componentes colapsables pedidos por comentario del asesor.

Casos salidos de la auditoría del 2026-09-10: en el curso de prueba la
automatización generó UN solo panel en 13 páginas, aunque la asesora había
pedido tabs, expander y acordeón en varias.

Ver docs/auditoria-fidelidad-gestion-calidad-2026-09-10.md
"""

import re

from bs4 import BeautifulSoup

from maquetador.ingest.docx_comments import _clasificar, _VARIANTE_PANEL, \
    aplicar_comentarios
from maquetador.build.componentes_asesor import (construir_panels,
                                                 pares_de_secciones,
                                                 extraer_pares)


class TestVariantesDePanel:
    """Cada tipo de panel tiene SU clase de DesignPLUS."""

    def test_acordeon_y_expander_no_son_la_misma_variante(self):
        assert _VARIANTE_PANEL["acordeon"] == "dp-accordion-default"
        assert _VARIANTE_PANEL["expander"] == "dp-expander-default"

    def test_tabs_usa_la_clase_que_existe(self):
        assert _VARIANTE_PANEL["tabs"] == "dp-tabs-buttons"
        assert _VARIANTE_PANEL["tabs_vertical"] == "dp-tabs-buttons-vertical"

    def test_clasifica_la_orientacion_de_las_tabs(self):
        assert _clasificar("Para maquetación: TABS vertical") == "tabs_vertical"
        assert _clasificar("Para maquetación: tabs") == "tabs"
        assert _clasificar("Maquetación: solapas horizontales") == "tabs"

    def test_colores_de_panel_del_catalogo_ucc(self):
        html = construir_panels([("A", "<p>a</p>"), ("B", "<p>b</p>")],
                                "dp-accordion-default")
        assert "dp-panel-color-dp-primary" in html
        assert "dp-panel-active-color-dp-secondary" in html
        assert "dp-panel-hover-color-dp-secondary" in html


class TestPanelDesdeSubtitulos:
    """'expander (títulos subrayados)': el asesor no arma tabla, subraya los
    subtítulos y escribe el contenido corrido."""

    HTML = ("<div>"
            "<p>Antes de aplicar cualquier herramienta conviene reconocer algo.</p>"
            "<p>Por ejemplo, si un proyecto presenta retrasos en la entrega.</p>"
            "<p><u>El diagrama de Ishikawa: explorar posibles causas</u></p>"
            "<p>Una de las herramientas más utilizadas para analizar problemas.</p>"
            "<p>Su principal objetivo es identificar y organizar las causas.</p>"
            "<p><u>La técnica de los 5 porqués: buscar la causa raíz</u></p>"
            "<p>Mientras que Ishikawa ayuda a explorar diversas posibilidades.</p>"
            "<p><u>El diagrama de Pareto: priorizar esfuerzos</u></p>"
            "<p>Una vez identificados distintos problemas o causas posibles.</p>"
            "</div>")

    def _aplicar(self):
        soup = BeautifulSoup(self.HTML, "html.parser")
        coment = [{"instruccion": "Para maquetación: expander (títulos subrayados)",
                   "anclado": "Antes de aplicar cualquier herramienta conviene",
                   "accion": "expander", "autor": ""}]
        aplicar_comentarios(soup, coment)
        return str(soup), coment[0]

    def test_arma_un_panel_por_subtitulo_subrayado(self):
        out, coment = self._aplicar()
        assert coment.get("_aplicado") is True
        assert out.count('class="dp-panel-group"') == 3

    def test_los_titulos_son_los_subtitulos_completos(self):
        out, _ = self._aplicar()
        titulos = re.findall(r'dp-panel-heading">([^<]+)', out)
        assert titulos == ["El diagrama de Ishikawa: explorar posibles causas",
                           "La técnica de los 5 porqués: buscar la causa raíz",
                           "El diagrama de Pareto: priorizar esfuerzos"]

    def test_cada_panel_se_lleva_sus_parrafos(self):
        out, _ = self._aplicar()
        cuerpos = re.findall(r'dp-panel-content">(.*?)</div>', out, re.S)
        assert cuerpos[0].count("<p>") == 2
        assert cuerpos[1].count("<p>") == 1

    def test_la_introduccion_queda_fuera_del_panel(self):
        """Lo anterior al primer subtítulo no es parte de ningún panel."""
        out, _ = self._aplicar()
        antes = out.split('<div class="dp-panels-wrapper')[0]
        assert "Antes de aplicar cualquier herramienta" in antes
        assert "Por ejemplo, si un proyecto presenta retrasos" in antes

    def test_no_parte_el_subtitulo_por_los_dos_puntos(self):
        """El extractor 'Nombre: contenido' cortaba el título en el ':' y
        perdía los párrafos de la sección — por eso salían paneles basura."""
        out, _ = self._aplicar()
        assert "El diagrama de Ishikawa: explorar posibles causas" in out
        assert 'dp-panel-heading">El diagrama de Ishikawa</h3>' not in out


class TestNoRompeLoQueYaAndaba:
    def test_sigue_armando_desde_nombre_contenido(self):
        soup = BeautifulSoup(
            "<div><p>Autoevaluación: la persona valora su desempeño.</p>"
            "<p>Evaluación por objetivos: mide el cumplimiento.</p></div>",
            "html.parser")
        pares, _ = extraer_pares(soup.find("p"), "Maquetación: acordeón")
        assert len(pares) == 2
        assert pares[0][0] == "Autoevaluación"

    def test_sin_subtitulos_no_inventa_secciones(self):
        soup = BeautifulSoup("<div><p>Un párrafo suelto.</p>"
                             "<p>Otro párrafo suelto.</p></div>", "html.parser")
        pares, _ = pares_de_secciones(soup.find("p"))
        assert pares == []

    def test_un_solo_subtitulo_no_alcanza_para_un_panel(self):
        soup = BeautifulSoup("<div><p><u>Único título</u></p>"
                             "<p>Su contenido.</p></div>", "html.parser")
        pares, _ = pares_de_secciones(soup.find("p"))
        assert pares == []
