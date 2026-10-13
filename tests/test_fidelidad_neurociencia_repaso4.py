# -*- coding: utf-8 -*-
"""Cuarta tanda del repaso de "Neurociencia Aplicada I" (3.3, 3.4 y 3.5)."""

from pathlib import Path

from bs4 import BeautifulSoup

from maquetador.build.snippets import (procesar_contenido, quick_check,
                                       reemplazar_figuras_diseno)
from maquetador.ingest.docx_comments import aplicar_comentarios


class TestElRecuadroSimpleTomaTodoElTramo:
    """El asesor marca varios párrafos y pide un resaltado simple. Se
    encuadraba solo el primero: en 3.3 el recuadro se quedaba con la
    pregunta de apertura y las tres del diario salían sueltas debajo."""

    HTML = ("<p>¿Cómo podemos llevar a cabo el diario en la empresa?</p>"
            "<p>Al final del día, responder por escrito a tres preguntas:</p>"
            "<p>1. ¿Qué decisiones tomé hoy y bajo qué criterio?</p>"
            "<p>2. ¿Dónde reaccioné más de lo que pensé?</p>"
            "<p>3. ¿Qué dependía de mí y qué no?</p>"
            "<p>Esta práctica tiene un efecto doble.</p>")

    ANCLA = ("¿Cómo podemos llevar a cabo el diario en la empresa?Al final "
             "del día, responder por escrito a tres preguntas:1. ¿Qué "
             "decisiones tomé hoy y bajo qué criterio?2. ¿Dónde reaccioné "
             "más de lo que pensé?3. ¿Qué dependía de mí y qué no?")

    def _aplicar(self):
        s = BeautifulSoup(self.HTML, "html.parser")
        aplicar_comentarios(s, [{
            "accion": "recuadro_simple",
            "instruccion": "para maquetación: resaltado de contenido simple",
            "anclado": self.ANCLA}])
        return s

    def test_las_preguntas_entran_a_la_caja(self):
        caja = self._aplicar().find(class_="dp-callout")
        assert caja is not None
        texto = caja.get_text(" ", strip=True)
        assert "¿Qué decisiones tomé hoy" in texto
        assert "¿Qué dependía de mí y qué no?" in texto

    def test_lo_que_viene_despues_queda_afuera(self):
        s = self._aplicar()
        caja = s.find(class_="dp-callout")
        assert "Esta práctica tiene un efecto doble" not in caja.get_text()
        assert "Esta práctica tiene un efecto doble" in s.get_text()


class TestSubtituloNumeradoVaUnNivelAbajo:
    """"1. El diario estoico de Marco Aurelio" cuelga de "Rutinas simples,
    impacto profundo": no es otro subtítulo de sección."""

    def test_el_numerado_baja_a_h4(self):
        html = ("<p><strong>Rutinas simples, impacto profundo</strong></p>"
                "<p>Cuerpo de la sección.</p>"
                "<h3><strong>1. El diario estoico de Marco Aurelio</strong></h3>"
                "<p>Cuerpo.</p>"
                "<p><strong>4. Microhábitos sostenibles</strong></p>"
                "<p>Cuerpo.</p>")
        s = BeautifulSoup(procesar_contenido(html), "html.parser")
        niveles = [(h.name, h.get_text(" ", strip=True))
                   for h in s.find_all(["h3", "h4"]) if not h.get("class")]
        assert niveles == [
            ("h3", "Rutinas simples, impacto profundo"),
            ("h4", "1. El diario estoico de Marco Aurelio"),
            ("h4", "4. Microhábitos sostenibles"),
        ]

    def test_en_una_actividad_no_se_toca(self):
        """Ahí una consigna numerada no es un encabezado, y de eso se
        encarga maquetar_actividad."""
        out = procesar_contenido("<h3>1. ¿Considera que el riesgo es alto?</h3>",
                                 bajar_h1_h2=False)
        assert "<h4>" not in out


class TestElEncabezadoDelQuickCheck:
    """Salía con un título de otro componente y sin la bajada: el
    estudiante no sabía qué se esperaba que hiciera."""

    def test_el_titulo_y_la_bajada_del_aula(self):
        out = quick_check([("Una.", "Verdadero"), ("Dos.", "Falso")])
        assert "¿Cómo vengo hasta acá?" in out
        assert "¿Cómo venís con las lecturas?" in out
        assert "Compruebe su comprensión" not in out

    def test_el_titulo_no_se_vuelve_un_encabezado_de_la_pagina(self):
        s = BeautifulSoup(procesar_contenido(
            quick_check([("Una.", "Verdadero"), ("Dos.", "Falso")])),
            "html.parser")
        assert s.find(["h2", "h3"]) is None


class TestLaFiguraDeDisenoSiempreSeAmplia:
    """En 3.5 el modelo MINE resume cinco niveles en una pirámide con
    texto: sin poder ampliarla no se lee."""

    HTML = ("<p><strong>Figura 2</strong></p>"
            "<p><strong>Modelo Integrado de Neuroliderazgo Estoico (MINE)"
            "</strong></p>"
            '<p><img src="__MEDIA__/m3_img_1.png"></p>'
            "<p><em>Nota</em>. Figura creada con Claude.</p>")

    def _salida(self):
        return reemplazar_figuras_diseno(
            self.HTML, 3, {(3, "figura", 2): Path("M_3 fig 2.jpg")}, set())

    def test_la_imagen_del_asesor_no_queda_ademas_de_la_de_diseno(self):
        """El párrafo que lleva la imagen se tomaba por un renglón en
        blanco: la figura de diseño se insertaba aparte y quedaban las dos
        publicadas, una debajo de la otra."""
        out = self._salida()
        assert "__DISENO__/M_3 fig 2.jpg" in out
        assert "m3_img_1.png" not in out

    def test_queda_ampliable(self):
        assert "dp-popup-image" in self._salida()

    def test_el_epigrafe_se_une_con_su_titulo(self):
        out = procesar_contenido(self._salida())
        assert ("Figura 2. Modelo Integrado de Neuroliderazgo Estoico (MINE)"
                in out)
