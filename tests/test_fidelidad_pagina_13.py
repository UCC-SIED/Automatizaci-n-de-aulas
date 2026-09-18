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
    Evans y Lindsay, en el medio). Al estar encerrado entre dos referencias
    de texto corrido (sin abrir/cerrar sección), el aire que le corresponde
    es el corto, no el párrafo entero — ver _encerrado_entre_texto."""

    def test_el_cta_de_cita_con_link_lleva_espaciado_arriba_y_abajo(self):
        html = ("<p>Deming, W. E. (2000). Out of the crisis. Penguin Random "
                "House.</p>"
                "<p>Evans, J. R., Lindsay, W. M. (2020). Administración y "
                "control de la calidad. Cengage Learning. "
                "https://ebooks7-24.com/?il=10765</p>"
                "<p>Garvin, D. A. (1988). Managing quality. Free Press</p>")
        out = procesar_contenido(html)
        assert "Descubrí leyendo" in out
        assert "<br/>" in out or "<br>" in out


class TestCitaDeDefinicionTrasPregunta:
    """La definición de SGC, citada en formato APA narrativo ("(Instituto
    Argentino de Normalización y Certificación, 2015a)"), va justo debajo del
    encabezado pregunta "¿Qué es un sistema de gestión de calidad?" y no
    tenía NINGÚN estilo: quedaba como párrafo corrido en vez de cita con
    sangría doble. No hay comentario del asesor que la marque como cita (se
    verificó contra el DOCX real) — el pedido es explícito del usuario, así
    que se detecta por el patrón encabezado-pregunta + cita APA al final."""

    def test_definicion_citada_lleva_sangria_doble(self):
        html = ("<h4>¿Qué es un sistema de gestión de calidad?</h4>"
                "<p>Un Sistema de Gestión de la Calidad (SGC) es un conjunto "
                "de políticas, procesos, procedimientos de trabajo y recursos "
                "interrelacionados que una organización establece para "
                "asegurar que sus productos o servicios cumplen con los "
                "requisitos definidos y promueven la mejora continua. "
                "(Instituto Argentino de Normalización y Certificación, "
                "2015a)</p>"
                "<p>En otras palabras, un sistema de gestión de calidad "
                "tiene por propósito organizar.</p>")
        out = procesar_contenido(html)
        assert "margin-left: 40px; margin-right: 40px;" in out

    def test_no_marca_un_parrafo_corto_tras_la_pregunta(self):
        """Sin cita APA de verdad al final (o muy corto), no es una
        definición citada: no hay que sangrar cualquier párrafo que siga a
        un encabezado-pregunta."""
        html = ("<h4>¿Cómo se vincula un sistema de gestión de calidad a la "
                "gestión de proyectos?</h4>"
                "<p>Desde la perspectiva de gestión de proyectos, un SGC no "
                "es solo un marco documental.</p>")
        out = procesar_contenido(html)
        assert "margin-left: 40px" not in out


class TestSubSubtituloDentroDeUnPanel:
    """'Gestión ambiental' y 'Seguridad y salud ocupacional' (ISO 14001/45001)
    abren cada panel del acordeón como un párrafo TODO en negrita: quedaban
    sin ningún estilo (ni h3 —no correspondía, competía con el propio título
    del panel— ni el 'lead' que sí lleva cualquier otro subtítulo en negrita
    del catálogo). El pedido del usuario es exactamente ese: más grande y en
    negrita, pero sin asumir la categoría de heading."""

    def test_parrafo_en_negrita_al_abrir_un_panel_es_lead(self):
        html = ('<div class="dp-panels-wrapper dp-accordion-default">'
                '<div class="dp-panel-group">'
                '<h3 class="dp-panel-heading">ISO 14001</h3>'
                '<div class="dp-panel-content">'
                '<p><strong>Gestión ambiental</strong></p>'
                '<p>La norma ISO 14001 establece los requisitos para un '
                'sistema de gestión ambiental.</p>'
                '</div></div></div>')
        out = procesar_contenido(html)
        assert '<p class="lead dp-text-bold"><strong>Gestión ambiental' in out
        assert "<h3>Gestión ambiental</h3>" not in out


class TestEspaciadoDeRecuadroTrasUnaLista:
    """'Ejemplos que iluminan' (ISO 9001, aplicación logística) quedaba SIN
    aire arriba cuando lo precedía una <ul> en vez de un <p>: _aire_corto_
    antes solo sabía colgar el <br> del final de un <p>, y con cualquier otro
    vecino (una lista) simplemente no hacía nada — ni corto ni entero."""

    def test_recuadro_encerrado_tras_una_lista_lleva_aire_corto_arriba(self):
        html = ("<ul><li>Planificar objetivos y metas</li>"
                "<li>Asegurar la satisfacción del cliente</li></ul>"
                '<div class="dp-callout dp-callout-placeholder card '
                'dp-callout-position-default dp-callout-color-dp-primary '
                'dp-callout-type-info">'
                '<div class="dp-callout-side-emphasis"></div>'
                '<div class="card-body">'
                '<h3 class="card-title">Ejemplos que iluminan</h3>'
                '<p>En un proyecto logístico, aplicar ISO 9001 implica '
                'definir indicadores.</p>'
                '</div></div>'
                '<p>La norma ISO 9001:2015 se estructura bajo el modelo de '
                'alto nivel.</p>')
        out = procesar_contenido(html)
        assert "</ul><p><br/></p><div" in out
        assert "Ejemplos que iluminan" in out


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

    def test_el_cuerpo_queda_sangrado_como_el_titulo(self):
        """Regresión real (módulo 2.1): el texto y la lista del cuerpo salían
        pegados al borde, sin la sangría de 40px que sí lleva el <h3> del
        título — quedaban desalineados con él."""
        out = resaltado_laboratorio_ideas(
            "<p>¡Momento de ensayar!</p>"
            "<ul><li>¿Qué problemas?</li><li>¿Cómo se gestionaban?</li></ul>"
            "<p>No se busca una respuesta correcta.</p>")
        assert '<p style="padding-left: 40px;">¡Momento de ensayar!</p>' in out
        assert ('<p style="padding-left: 40px;">No se busca una respuesta '
                'correcta.</p>') in out

    def test_la_lista_va_doblemente_anidada_sin_vinieta_extra(self):
        """La convención del equipo: <ul><li style="list-style-type: none;">
        envuelve la lista real, para correrla bajo la sangría sin agregarle
        su propia viñeta."""
        out = resaltado_laboratorio_ideas(
            "<p>Intro.</p><ul><li>Uno</li><li>Dos</li></ul>")
        assert ('<ul><li style="list-style-type: none;"><ul><li>Uno</li>'
                '<li>Dos</li></ul></li></ul>') in out

    def test_conserva_un_style_previo_de_los_parrafos(self):
        out = resaltado_laboratorio_ideas(
            '<p style="text-align: center;">Centrado.</p>')
        assert 'style="text-align: center; padding-left: 40px;"' in out


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
