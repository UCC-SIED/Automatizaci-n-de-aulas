# -*- coding: utf-8 -*-
"""Indicaciones del complemento SiedUCC (Google Docs).

El asesor arma los componentes con el complemento. Cada uno deja en el
DOCX una tabla con el contenido y, debajo, un bloque gris que arranca con
el centinela y sigue con pares "Clave: valor".

Ese bloque resuelve de una vez los tres problemas que veníamos teniendo:
no se publica (antes toda tabla de una columna salía como recuadro, así
que las indicaciones internas llegaban al estudiante), dice QUÉ componente
armar, y la tabla de arriba dice dónde empieza y dónde termina —el tramo
ya no hay que deducirlo del ancla del comentario.
"""

from bs4 import BeautifulSoup

from maquetador.build.snippets import procesar_contenido


def _indicacion(*lineas):
    cuerpo = "".join("<p>%s</p>" % x for x in lineas)
    return ("<table><tbody><tr><td>"
            "<p>SIEDUCC · INDICACIÓN INTERNA (no publicar)</p>"
            + cuerpo + "</td></tr></tbody></table>")


def _tabla_de_pares(*pares):
    filas = "".join("<tr><td><p>%s</p></td></tr>" % x
                    for par in pares for x in par)
    return "<table><tbody>%s</tbody></table>" % filas


class TestLaIndicacionNoSePublica:
    def test_el_bloque_interno_se_saca(self):
        out = procesar_contenido(
            "<p>Contenido de la página.</p>"
            + _indicacion("Componente: recuadro_simple",
                          "· Verificar el destino del enlace."))
        assert "SIEDUCC" not in out
        assert "Verificar el destino del enlace" not in out
        assert "Contenido de la página." in out

    def test_una_tabla_normal_no_se_toca(self):
        """Solo se filtra lo que abre con el centinela."""
        out = procesar_contenido(
            "<table><thead><tr><th><p><strong>Descubrí leyendo</strong></p>"
            "</th></tr><tr><th><p>Revisá el capítulo 2.</p></th></tr>"
            "</thead></table>")
        assert "Revisá el capítulo 2" in out


class TestElComponenteSaleDeLaTablaDeArriba:
    PARES = (("Lóbulo frontal", "Decisiones y planificación."),
             ("Lóbulo parietal", "Interpreta el entorno."))

    def _armar(self, clave):
        return procesar_contenido(
            _tabla_de_pares(*self.PARES) + _indicacion("Componente: " + clave))

    def test_expander(self):
        s = BeautifulSoup(self._armar("expander"), "html.parser")
        panel = s.find(class_="dp-panels-wrapper")
        assert panel is not None
        assert "dp-expander-default" in panel.get("class")
        assert [h.get_text(" ", strip=True)
                for h in s.find_all(class_="dp-panel-heading")] == [
            "Lóbulo frontal", "Lóbulo parietal"]

    def test_acordeon_y_tabs_usan_su_variante(self):
        for clave, variante in [("acordeon", "dp-accordion-default"),
                                ("tabs", "dp-tabs-buttons"),
                                ("tabs_vertical", "dp-tabs-buttons-vertical")]:
            s = BeautifulSoup(self._armar(clave), "html.parser")
            assert variante in s.find(class_="dp-panels-wrapper").get("class")

    def test_flip_card(self):
        s = BeautifulSoup(self._armar("flip_card"), "html.parser")
        assert len(s.find_all(class_="dp-flip-card")) == 2

    def test_sin_tabla_arriba_no_inventa_nada(self):
        out = procesar_contenido("<p>Un párrafo suelto.</p>"
                                 + _indicacion("Componente: expander"))
        assert "dp-panels-wrapper" not in out
        assert "Un párrafo suelto." in out


class TestQuickCheckDelComplemento:
    def test_se_arma_la_grilla(self):
        out = procesar_contenido(
            "<table><tbody><tr><td><p>Quick check</p></td></tr>"
            "<tr><td><p>1. El cerebro consume glucosa. Verdadero</p></td></tr>"
            "<tr><td><p>2. La corteza es blanca. Falso</p></td></tr>"
            "</tbody></table>" + _indicacion("Componente: quick_check"))
        s = BeautifulSoup(out, "html.parser")
        assert "¿Cómo vengo hasta acá?" in out
        assert len(s.find_all(attrs={"data-interactive-id": True})) == 2
        assert "Quick check" not in s.get_text()


class TestNoMaquetar:
    def test_borra_el_bloque_de_arriba(self):
        out = procesar_contenido(
            "<p>Esto se publica.</p>"
            "<table><tbody><tr><td><p>Indicaciones para el tutor.</p></td>"
            "</tr></tbody></table>"
            + _indicacion("Componente: no_maquetar"))
        assert "Indicaciones para el tutor" not in out
        assert "Esto se publica." in out
