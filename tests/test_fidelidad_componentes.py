# -*- coding: utf-8 -*-
"""Componentes colapsables pedidos por comentario del asesor.

Casos salidos de la auditoría del 2026-09-10: en el curso de prueba la
automatización generó UN solo panel en 13 páginas, aunque la asesora había
pedido tabs, expander y acordeón en varias.

Ver docs/auditoria-fidelidad-gestion-calidad-2026-09-10.md
"""

import re

import pytest

from bs4 import BeautifulSoup

from maquetador.ingest.docx_comments import _clasificar, _VARIANTE_PANEL, \
    aplicar_comentarios
from maquetador.build.componentes_asesor import (construir_panels,
                                                 pares_de_secciones,
                                                 extraer_pares)
from maquetador.build.snippets import maquetar_actividad


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


class TestMaquetadoDeActividad:
    """El "Modelo de actividad": título propio y rótulos de sección.

    En la AFI del curso de prueba el título salía como <h3> arrastrando el
    prefijo "Actividad final integradora: ", que repite el nombre que Canvas
    ya muestra en el módulo, y "Objetivo:" quedaba como párrafo.
    """

    CUERPO = ('<h3>Actividad final integradora: Analizá situaciones reales</h3>'
              '<p>Objetivo: </p>'
              '<p>Interpretar la situación planteada e integrar los conceptos.</p>'
              '<p>Consigna: Elaborá un informe técnico.</p>')

    def test_el_titulo_va_en_el_h2_de_titulo(self):
        out = maquetar_actividad(self.CUERPO)
        assert 'class="dp-ignore-theme"' in out
        assert "color: #003087" in out
        assert "text-align: center" in out

    def test_le_saca_el_prefijo_que_duplica_el_nombre_del_item(self):
        out = maquetar_actividad(self.CUERPO)
        assert "<strong>Analizá situaciones reales</strong>" in out
        assert "Actividad final integradora:" not in out

    def test_los_rotulos_de_seccion_son_encabezados(self):
        out = maquetar_actividad(self.CUERPO)
        assert "<h3>Objetivo</h3>" in out
        assert "<h3>Consigna</h3>" in out
        assert "<p>Objetivo: </p>" not in out

    def test_el_cuerpo_pegado_al_rotulo_queda_debajo(self):
        out = maquetar_actividad(self.CUERPO)
        assert "<h3>Consigna</h3><p>Elaborá un informe técnico.</p>" in out

    def test_no_toca_un_parrafo_que_no_es_rotulo(self):
        out = maquetar_actividad("<p>Nutri Pet S.A.: una empresa del rubro.</p>")
        assert "<h3>" not in out


class TestJerarquiaDeSubtitulos:
    """Textos tomados de los comentarios reales del curso de prueba.

    La política de jerarquía de la UCC: H2 título de página, H3 subtítulo,
    H4 sub-subtítulo. "sub-subtítulo" contiene la palabra "subtítulo", así que
    todos caían en H3.
    """

    def test_subtitulo_es_h3(self):
        assert _clasificar("Para maquetación: subtítulo") == "subtitulo"

    @pytest.mark.parametrize("texto", [
        "Para maquetación: sub-subtítulo",
        "Para maquetación: subsubtítulo",
        "Para maquetación: sub subtitulo",
    ])
    def test_sub_subtitulo_es_h4(self, texto):
        assert _clasificar(texto) == "subsubtitulo"

    def test_aplica_el_nivel_correcto(self):
        soup = BeautifulSoup("<div><p>¿Qué es un indicador?</p></div>",
                             "html.parser")
        coment = [{"instruccion": "Para maquetación: sub-subtítulo",
                   "anclado": "¿Qué es un indicador?",
                   "accion": "subsubtitulo", "autor": ""}]
        aplicar_comentarios(soup, coment)
        assert "<h4>¿Qué es un indicador?</h4>" in str(soup)

    def test_el_subtitulo_sigue_siendo_h3(self):
        soup = BeautifulSoup("<div><p>Costos de la calidad</p></div>",
                             "html.parser")
        coment = [{"instruccion": "Para maquetación: subtítulo",
                   "anclado": "Costos de la calidad",
                   "accion": "subtitulo", "autor": ""}]
        aplicar_comentarios(soup, coment)
        assert "<h3>Costos de la calidad</h3>" in str(soup)


class TestMarcadorDeCierre:
    """'fin del expander' marca dónde termina, no pide armar otro."""

    @pytest.mark.parametrize("texto", [
        "Para maquetación: fin del expander",
        "Para maquetación: fin de la tabla",
        "fin del acordeón",
    ])
    def test_no_dispara_un_componente(self, texto):
        assert _clasificar(texto) is None

    def test_el_expander_de_verdad_sigue_disparando(self):
        assert _clasificar("Para maquetación: expander") == "expander"


class TestPedidoRepetido:
    """Un mismo pedido anclado en varios lugares es UN componente.

    El asesor marca con el mismo globo cada tramo que va adentro: "TABS
    vertical ISO 14001 ISO 45001" aparece 3 veces en el DOCX del curso de
    prueba y "flipcards" una vez por tarjeta. El generador intentaba armar uno
    por globo.
    """

    HTML = ("<div>"
            "<p><u>ISO 14001</u></p><p>Gestión ambiental de la organización.</p>"
            "<p><u>ISO 45001</u></p><p>Seguridad y salud en el trabajo.</p>"
            "<p><u>ISO 50001</u></p><p>Gestión de la energía.</p>"
            "</div>")
    INSTR = "Para maquetación: TABS vertical ISO 14001 ISO 45001"

    def _aplicar(self):
        soup = BeautifulSoup(self.HTML, "html.parser")
        coments = [{"instruccion": self.INSTR, "anclado": a,
                    "accion": "tabs_vertical", "autor": ""}
                   for a in ("ISO 14001", "Gestión ambiental de la organización.",
                             "Seguridad y salud en el trabajo.")]
        aplicar_comentarios(soup, coments)
        return str(soup), coments

    def test_arma_un_solo_componente(self):
        out, _ = self._aplicar()
        assert out.count("dp-panels-wrapper") == 1

    def test_con_todos_los_paneles(self):
        out, _ = self._aplicar()
        assert out.count('class="dp-panel-group"') == 3

    def test_saldar_todo_el_grupo(self):
        """Los globos repetidos quedan resueltos, no pendientes de aviso."""
        _, coments = self._aplicar()
        assert all(c.get("_aplicado") for c in coments)

    def test_pedidos_distintos_siguen_siendo_componentes_distintos(self):
        """La deduplicación agrupa por pedido: dos pedidos distintos, en dos
        tramos distintos, siguen dando dos componentes."""
        soup = BeautifulSoup(
            "<div>"
            "<p><u>ISO 14001</u></p><p>Gestión ambiental.</p>"
            "<p><u>ISO 45001</u></p><p>Seguridad y salud.</p>"
            "<h2>Otra sección</h2>"
            "<p><u>Planificar</u></p><p>Definir el alcance.</p>"
            "<p><u>Verificar</u></p><p>Medir los resultados.</p>"
            "</div>", "html.parser")
        coments = [
            {"instruccion": "Para maquetación: TABS vertical",
             "anclado": "ISO 14001", "accion": "tabs_vertical", "autor": ""},
            {"instruccion": "Para maquetación: acordeón",
             "anclado": "Planificar", "accion": "acordeon", "autor": ""},
        ]
        aplicar_comentarios(soup, coments)
        out = str(soup)
        assert out.count("dp-panels-wrapper") == 2
        assert "dp-tabs-buttons-vertical" in out
        assert "dp-accordion-default" in out
