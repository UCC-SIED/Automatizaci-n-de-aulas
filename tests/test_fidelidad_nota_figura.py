# -*- coding: utf-8 -*-
"""Pie de fuente de la figura: "Nota. Figura elaborada con base en …".

No es un párrafo más del contenido: en el aula corregida a mano va como
<figcaption> dentro de un <figure>, y la palabra "Nota." se cae. El generador
lo dejaba suelto como texto (5 veces en el curso de prueba; v1 tenía 0
<figure> y v2 tiene 5).

Ver docs/auditoria-fidelidad-gestion-calidad-2026-09-10.md
"""

from bs4 import BeautifulSoup

from maquetador.build.snippets import procesar_contenido

FUENTE = ("Figura elaborada con base en Administración y control de la calidad, "
          "por J. R. Evans &amp; W. M. Lindsay, 2020, Cengage Learning.")
BLOQUE = ('<p class="dp-heading-ignore" style="text-align: center;">'
          '<span style="font-size: 10pt;"><strong>Figura 1. Evolución de la '
          'gestión de calidad</strong></span></p>'
          '<p><strong><img src="__MEDIA__/M_1 fig 1.jpg"></strong></p>'
          '<p class="dp-heading-ignore" style="text-align: center;">'
          f'<span style="font-size: 10pt;"><strong>Nota . {FUENTE}</strong>'
          '</span></p>')


class TestNotaAFigcaption:
    def test_arma_un_figure(self):
        soup = BeautifulSoup(procesar_contenido(BLOQUE), "html.parser")
        assert soup.find("figure") is not None

    def test_la_nota_pasa_a_figcaption(self):
        soup = BeautifulSoup(procesar_contenido(BLOQUE), "html.parser")
        cap = soup.find("figcaption")
        assert cap is not None
        assert "Evans" in cap.get_text()

    def test_le_saca_la_palabra_nota(self):
        out = procesar_contenido(BLOQUE)
        assert "Nota" not in out
        assert "Figura elaborada con base en" in out

    def test_la_fuente_no_queda_suelta_como_parrafo(self):
        soup = BeautifulSoup(procesar_contenido(BLOQUE), "html.parser")
        sueltos = [p for p in soup.find_all("p") if "Evans" in p.get_text()]
        assert sueltos == []

    def test_las_clases_van_en_el_figure_y_la_imagen_queda_limpia(self):
        soup = BeautifulSoup(procesar_contenido(BLOQUE), "html.parser")
        fig = soup.find("figure")
        assert "dp-image-bordered" in " ".join(fig.get("class", []))
        assert "text-align: center" in fig.get("style", "")
        assert not soup.find("img").get("class")

    def test_el_epigrafe_queda_afuera_y_arriba(self):
        out = procesar_contenido(BLOQUE)
        assert out.index("Figura 1. Evolución") < out.index("<figure")

    def test_deja_espaciado_despues(self):
        out = procesar_contenido(BLOQUE)
        assert out.index("</figure>") < out.rindex("<p>")

    def test_sin_nota_no_arma_figure(self):
        simple = '<p><img src="__MEDIA__/x.jpg"></p><p>Un párrafo normal.</p>'
        assert "<figure" not in procesar_contenido(simple)
