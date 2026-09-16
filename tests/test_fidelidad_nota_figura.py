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


class TestNotaSueltaSinFigura:
    """Una 'Nota:' que NO tiene una figura al lado es contenido normal del
    cuerpo de la página (un comentario/aclaración del docente), no el pie de
    una figura: va en negrita, sin centrar ni encuadrar. Antes caía en el
    mismo tratamiento de epígrafe centrado que 'Nota. Figura elaborada…',
    aunque no hubiera ninguna figura cerca — quedaba centrada como si fuera
    el pie de una imagen inexistente."""

    HTML = ('<p>Contenido previo sobre las normas ISO 14001 y 45001.</p>'
            '<p>Nota: Las normas o estándares integrables son más diversas '
            'que lo mencionado. ISO 14001 e ISO 45001 son los estándares '
            'más comunes pero no los únicos.</p>')

    def test_queda_en_negrita(self):
        out = procesar_contenido(self.HTML)
        assert "<strong>Nota: Las normas" in out

    def test_no_queda_centrada_ni_como_epigrafe(self):
        out = procesar_contenido(self.HTML)
        idx = out.index("Las normas")
        entorno = out[max(0, idx - 200):idx]
        assert "text-align: center" not in entorno
        assert "dp-heading-ignore" not in entorno

    def test_no_queda_en_un_recuadro(self):
        out = procesar_contenido(self.HTML)
        assert "dp-callout" not in out

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


class TestCentradoYEspaciado:
    """Revisión del aula en Canvas: "la figura le faltó centrar la imagen, y
    todas las imágenes llevan un espacio de párrafo tanto arriba como abajo"."""

    CON_TEXTO = ('<p>Texto anterior.</p>'
                 '<p class="dp-heading-ignore" style="text-align: center;">'
                 '<span style="font-size: 10pt;"><strong>Figura 1. Evolución'
                 '</strong></span></p>'
                 '<p><strong><img src="__MEDIA__/M_1 fig 1.jpg"></strong></p>'
                 '<p>Texto siguiente.</p>')

    def test_la_caja_de_la_figura_se_centra(self):
        """text-align solo alinea lo de adentro: la caja necesita mx-auto."""
        out = procesar_contenido(BLOQUE)
        soup = BeautifulSoup(out, "html.parser")
        clases = " ".join(soup.find("figure").get("class", []))
        assert "mx-auto" in clases and "d-block" in clases

    def test_aire_arriba_del_epigrafe_y_abajo_de_la_figura(self):
        soup = BeautifulSoup(procesar_contenido(self.CON_TEXTO), "html.parser")
        hijos = [c for c in soup.children if getattr(c, "name", None)]
        textos = [c.get_text(strip=True) for c in hijos]
        # …Texto anterior · aire · epígrafe · imagen · aire · Texto siguiente
        assert textos[0].startswith("Texto anterior")
        assert textos[1] in ("", "\xa0")
        assert "Figura 1" in textos[2]
        assert textos[-2] in ("", "\xa0")
        assert textos[-1].startswith("Texto siguiente")

    def test_el_aire_va_antes_del_epigrafe_no_entre_epigrafe_e_imagen(self):
        out = procesar_contenido(self.CON_TEXTO)
        assert out.index("<p> </p>") < out.index("Figura 1")

    def test_no_duplica_el_aire_si_ya_estaba(self):
        html = ("<p>Antes.</p><p>&nbsp;</p>"
                '<p><img src="__MEDIA__/x.jpg"></p>'
                "<p>&nbsp;</p><p>Después.</p>")
        out = procesar_contenido(html)
        assert out.count("<p> </p>") == 2
