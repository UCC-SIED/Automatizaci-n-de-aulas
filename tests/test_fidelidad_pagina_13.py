# -*- coding: utf-8 -*-
"""Correcciones de la revisión del aula en Canvas: página 1.3/1.4 y
bibliografía, módulos 1 y 2."""

from maquetador.build.snippets import (procesar_contenido, resaltado_ejemplo,
                                       resaltado_laboratorio_ideas)


class TestTituloDeEjemplos:
    """El catálogo UCC dice 'Ejemplos que iluminan' (plural): el código tenía
    el título hardcodeado en singular ('Ejemplo que iluminan'), un typo que
    quedaba publicado tal cual en el aula."""

    def test_resaltado_ejemplo_usa_el_titulo_del_catalogo(self):
        assert "Ejemplos que iluminan" in resaltado_ejemplo("<p>cuerpo</p>")
        assert "Ejemplo que iluminan<" not in resaltado_ejemplo("<p>cuerpo</p>")

    def test_no_se_avisa_como_titulo_duplicado_por_paginas(self):
        """_TITULOS_ESTANDARIZADOS tenía la forma vieja en singular: con el
        título ya corregido a plural, dos 'Ejemplos que iluminan' en la misma
        página (título de catálogo reutilizado a propósito) no debe salir
        como aviso de 'título repetido' — quedó con el singular viejo y ya no
        matcheaba tras corregir resaltado_ejemplo()."""
        from maquetador.build.imscc_builder import GeneradorAula
        from maquetador.ingest.folder_scanner import normalizar
        assert normalizar("Ejemplos que iluminan") \
            in GeneradorAula._TITULOS_ESTANDARIZADOS

    def test_recuadro_de_tabla_tipo_ejemplo_usa_el_titulo_del_catalogo(self):
        html = ("<table><tr><td>Ejemplo</td></tr>"
                "<tr><td>Un caso real de aplicación.</td></tr></table>")
        out = procesar_contenido(html)
        assert "Ejemplos que iluminan" in out


class TestEncabezadoVacio:
    """Word a veces deja un 'Título 3' vacío, solo con el ancla/bookmark que
    mammoth vuelca como <h3><a id="…"></a></h3>: sin texto, se ve como un
    salto de línea/aire raro en medio del contenido (pasó justo después de un
    recuadro 'Ejemplos que iluminan', en la página 1.3)."""

    def test_encabezado_solo_con_ancla_se_elimina(self):
        html = ('<p>Texto previo.</p>'
                '<h3><a id="_heading=h.abc123"></a></h3>'
                '<h3><a id="_heading=h.def456"></a>Título real</h3>'
                '<p>Texto posterior.</p>')
        out = procesar_contenido(html)
        assert "<h3></h3>" not in out
        assert "<h3>Título real</h3>" in out

    def test_no_toca_un_encabezado_con_imagen_y_sin_texto(self):
        """Un <h3> sin texto pero con una imagen adentro no es un vacío de
        Word: no hay que borrarlo."""
        html = '<h3><img src="x.png"></h3>'
        out = procesar_contenido(html)
        assert "<img" in out


class TestEspaciadoDelCTADeBibliografia:
    """'Descubrí leyendo' (cita + link suelto → CTA, _procesar_citas_con_link)
    se arma DESPUÉS del paso que airea los recuadros: sin un segundo pasaje de
    espaciado, el CTA quedaba pegado a las referencias de bibliografía que lo
    rodean, arriba y abajo (regresión real: 'Deming, W. E. (2000)…' y
    'Garvin, D. A. (1988)…', pegadas al CTA armado desde la referencia de
    Evans y Lindsay, en el medio)."""

    def test_el_cta_de_cita_con_link_lleva_parrafo_arriba_y_abajo(self):
        html = ("<p>Deming, W. E. (2000). Out of the crisis. Penguin Random "
                "House.</p>"
                "<p>Evans, J. R., Lindsay, W. M. (2020). Administración y "
                "control de la calidad. Cengage Learning. "
                "https://ebooks7-24.com/?il=10765</p>"
                "<p>Garvin, D. A. (1988). Managing quality. Free Press</p>")
        out = procesar_contenido(html)
        assert "Descubrí leyendo" in out
        assert out.count("<p>\xa0</p>") >= 2


class TestLaboratorioDeIdeas:
    """'Laboratorio de ideas' (tabla de 1 columna, catálogo UCC — desafío
    personal sin entrega, "Lecture Hook") no tenía mapeo en _clasificar_
    recuadro(): caía al recuadro simple sin título, y encima el título de la
    tabla ("Laboratorio de ideas") se descartaba del todo al armar el
    recuadro, sin dejar ni rastro (regresión real: módulo 2, '¡Momento de
    ensayar!')."""

    def test_tabla_con_etiqueta_arma_el_lecture_hook(self):
        html = ("<table><tr><td>Laboratorio de ideas</td></tr>"
                "<tr><td>¡Momento de ensayar! Pensá en un proyecto que "
                "conozcas.</td></tr></table>")
        out = procesar_contenido(html)
        assert "Lecture Hook" in out
        assert "<strong>Laboratorio de ideas</strong>" in out
        assert "Momento de ensayar" in out

    def test_lleva_parrafo_de_espaciado_arriba_y_abajo(self):
        html = ("<p>Texto previo.</p>"
                "<table><tr><td>Laboratorio de ideas</td></tr>"
                "<tr><td>¡Momento de ensayar!</td></tr></table>"
                "<p>Texto posterior.</p>")
        out = procesar_contenido(html)
        assert out.count("<p>\xa0</p>") >= 2

    def test_resaltado_laboratorio_ideas_usa_el_titulo_del_catalogo(self):
        assert "<strong>Laboratorio de ideas</strong>" in \
            resaltado_laboratorio_ideas("<p>cuerpo</p>")


class TestEspaciadoDeFiguraQueEsTabla:
    """Una "figura" a veces es en realidad una tabla de datos (el epígrafe
    dice "Figura N." pero el contenido es una tabla, no una imagen, p.ej.
    una síntesis comparativa): _espaciar_figuras solo miraba <figure>/<img>,
    así que esta tabla no llevaba el aire de párrafo que sí lleva cualquier
    otra figura (regresión real: módulo 2, "Figura 5. Síntesis de
    enfoques")."""

    HTML = ("<table><thead><tr><th><p>Enfoque</p></th>"
            "<th><p>Descripción</p></th></tr></thead>"
            "<tr><td><p>Lean</p></td><td><p>Eliminar desperdicios</p></td></tr>"
            "</table>")

    def test_lleva_espaciado_arriba_y_abajo(self):
        html = ("<p>Texto previo.</p>"
                "<p><strong>Figura 5. Síntesis de enfoques</strong></p>"
                f"{self.HTML}"
                "<p>Texto posterior.</p>")
        out = procesar_contenido(html)
        assert out.count("<p>\xa0</p>") >= 2

    def test_no_airea_una_tabla_de_datos_sin_epigrafe(self):
        """Una tabla de datos normal, SIN "Figura N."/"Tabla N." encima, no
        se toca: solo se airean las que tienen ese epígrafe."""
        html = f"<p>Texto previo.</p>{self.HTML}<p>Texto posterior.</p>"
        out = procesar_contenido(html)
        assert out.count("<p>\xa0</p>") == 0
