# -*- coding: utf-8 -*-
"""Tests de fidelidad del maquetado, salidos de la auditoría del 2026-09-10.

Cada caso reproduce markup REAL que hoy sale de la segmentación del DOCX y
verifica que el generador lo deja como el aula maquetada a mano
(`pruebas/gestion-de-la-calidad-2026-export (2).imscc`).

Ver docs/auditoria-fidelidad-gestion-calidad-2026-09-10.md
"""

import re

from processors.cidilabs_builder import DP_WRAPPER_CLASSES
from maquetador.build.pages import pagina_intro, pagina_contenido
from maquetador.build.snippets import procesar_contenido, sanear_lista_objetivos


class TestTemaDelWrapper:
    """El #dp-wrapper tiene que traer el tema de encabezados vigente."""

    def test_trae_los_tokens_del_tema_nuevo(self):
        for token in ("custom-paragraph-padding", "dp-hdg-txt-h6-dp-primary",
                      "dp-hdg-bg-h5-dp-gray", "dp-hdg-txt-h5-dp-primary",
                      "dp-hdg-bg-h6-dp-white", "dp-hdg-d-h4-table-l",
                      "dp-hdg-b-h5-pill-r"):
            assert token in DP_WRAPPER_CLASSES, f"falta {token}"

    def test_no_arrastra_tokens_del_tema_viejo(self):
        for token in ("dp-hdg-txt-h5-dp-white", "dp-hdg-bg-h6-dp-gray",
                      "dp-hdg-txt-h6-dp-gray", "dp-hdg-b-h6-bold",
                      "dp-hdg-b-h5-bold", "dp-hdg-b-h5-brdr-b"):
            assert token not in DP_WRAPPER_CLASSES, f"sobra {token}"

    def test_sin_artefactos_del_editor(self):
        """El editor DesignPLUS deja '&nbsp;' pegado a una clase y duplica
        custom-paragraph-padding; el generador no debe copiar eso."""
        assert "&nbsp;" not in DP_WRAPPER_CLASSES
        tokens = DP_WRAPPER_CLASSES.split()
        assert len(tokens) == len(set(tokens)), "hay clases repetidas"

    def test_llega_a_la_pagina_generada(self):
        html = pagina_contenido("1.1. Título", "<p>x</p>", "b.png", "id")
        assert 'id="dp-wrapper"' in html
        assert "custom-paragraph-padding" in html


class TestFiguras:
    """Figura embebida en el DOCX: epígrafe + imagen + 'Texto alternativo:'."""

    # Markup tal cual sale hoy de la página 2.2 del curso de prueba.
    FIGURA = (
        '<p class="dp-heading-ignore" style="text-align: center;">'
        '<span style="font-size: 10pt;"><strong>Figura 2. Ejemplo simplificado'
        ' de diagrama de Ishikawa</strong></span></p>'
        '<p><strong><img src="__MEDIA__/M_2 fig 2.jpg"></strong></p>'
        '<p>Texto alternativo: Diagrama de Ishikawa para identificar las '
        'posibles causas de un problema.</p>'
    )

    def test_el_texto_alternativo_va_al_atributo_alt(self):
        out = procesar_contenido(self.FIGURA)
        assert 'alt="Diagrama de Ishikawa para identificar las posibles ' \
               'causas de un problema"' in out

    def test_el_texto_alternativo_deja_de_verse_en_la_pagina(self):
        out = procesar_contenido(self.FIGURA)
        assert "Texto alternativo:" not in out

    def test_la_figura_queda_centrada_aunque_word_la_envuelva_en_strong(self):
        """El <p> contenedor se centra: hay que subir hasta él, porque el
        padre directo de la imagen es el <strong> que mete Word."""
        out = procesar_contenido(self.FIGURA)
        assert '<p style="text-align: center;"><strong><img' in out

    def test_borde_estatico_por_defecto(self):
        out = procesar_contenido(self.FIGURA)
        assert "dp-image-rounded-10" in out and "dp-image-bordered" in out
        assert "dp-popup-image" not in out
        assert "dp-image-shadow" not in out

    def test_borde_expandible_si_el_asesor_lo_pide(self):
        html = self.FIGURA + "<p>Figura expandible</p>"
        out = procesar_contenido(html)
        assert "dp-popup-image" in out
        assert "dp-image-shadow" in out

    def test_no_toca_los_iconos_de_los_recuadros(self):
        html = ('<div class="dp-callout"><div class="card-body">'
                '<img src="$IMS-CC-FILEBASE$/Iconos/icono%20lectura.svg" alt="">'
                '</div></div>')
        out = procesar_contenido(html)
        assert "dp-image-rounded-10" not in out

    def test_alt_explicito_pisa_al_epigrafe(self):
        """reemplazar_figuras_diseno deja el epígrafe como alt de arranque;
        si el asesor escribió un texto alternativo, ese manda."""
        html = ('<p><img src="__DISENO__/f.jpg" alt="Figura 2. Ejemplo"></p>'
                '<p>Texto alternativo: Descripción accesible real.</p>')
        out = procesar_contenido(html)
        assert 'alt="Descripción accesible real"' in out
        assert "Figura 2. Ejemplo" not in out


class TestListaDeObjetivos:
    """Un objetivo con estilo de título no puede romper la lista."""

    LISTA = ('<ul><li>Comprender…</li><li>Analizar…</li>'
             '<h3>Distinguir los procesos de planificación…</h3>'
             '<li>Interpretar…</li></ul>')

    def test_el_encabezado_suelto_vuelve_a_ser_item(self):
        out = sanear_lista_objetivos(self.LISTA)
        assert "<h3>" not in out
        assert out.count("<li>") == 4

    def test_conserva_el_texto_del_objetivo(self):
        out = sanear_lista_objetivos(self.LISTA)
        assert "Distinguir los procesos de planificación…" in out

    def test_no_toca_los_encabezados_fuera_de_la_lista(self):
        html = "<h3>Objetivos</h3><ul><li>uno</li></ul>"
        out = sanear_lista_objetivos(html)
        assert "<h3>Objetivos</h3>" in out

    def test_se_aplica_al_construir_la_pagina_de_intro(self):
        html = pagina_intro("Introducción M1", "<p>i</p>", self.LISTA,
                            "b.png", "id")
        bloque = re.search(r"<ul>.*?</ul>", html, re.S).group(0)
        assert "<h3>" not in bloque
        assert bloque.count("<li>") == 4


class TestRecuadroDebajoDeLosObjetivos:
    """Los objetivos no son solo la lista: el asesor deja debajo el recuadro
    que invita al video del módulo. Ese bloque no pasaba por
    procesar_contenido y la caja se publicaba como una <table> cruda, con
    bordes de Word y sin ícono. Regresión real: Gestión del Riesgo, los tres
    módulos."""

    OBJETIVOS = (
        "<p>Al finalizar este módulo serás capaz de:</p>"
        "<ul><li>Diferenciar riesgo, incertidumbre y complejidad.</li></ul>"
        "<table><thead><tr><th><p><strong>Auriculares <em>on</em></strong></p>"
        "</th></tr><tr><th><p>Antes de empezar, te propongo visualizar un "
        "video introductorio.</p></th></tr></thead></table>")

    def _pagina(self):
        return pagina_intro("Introducción M1", "<p>i</p>", self.OBJETIVOS,
                            "b.png", "id")

    def test_la_caja_se_maqueta(self):
        html = self._pagina()
        assert "<table>" not in html
        assert "dp-callout" in html

    def test_auriculares_on_es_el_cta_de_video(self):
        """En un módulo el asesor escribe "Auriculares on (Video y Podcast)" y
        en los otros dos solo "Auriculares on": salía CTA en uno y recuadro
        simple en los demás."""
        html = self._pagina()
        assert "Auriculares on" in html
        assert "Icono%20recuadro%20video.svg" in html

    def test_los_objetivos_siguen_siendo_una_lista(self):
        assert "<li>Diferenciar riesgo, incertidumbre y complejidad.</li>" \
            in self._pagina()


class TestIndiceDeFigurasDeDiseno:
    """El separador entre el módulo y el tipo de figura cambia por curso
    ("M_1 fig 2.jpg", "M1 Figura 2.jpg", "M1 - Figura 1.png"). Regresión
    real (Creación de Valor en la Economía de la Experiencia): con el guion
    medio, "M1 - Figura 1.png" no se indexaba y la Figura 1 de CADA módulo
    quedaba afuera del aula, sin ningún aviso."""

    def _indice(self, nombres):
        from pathlib import Path
        from maquetador.build.snippets import indexar_figuras_diseno
        return indexar_figuras_diseno([Path(n) for n in nombres])

    def test_guion_medio_entre_modulo_y_figura(self):
        indice = self._indice(["M1 - Figura 1.png", "M2 - Figura 1.png",
                               "M3 - Figura 1.png"])
        assert indice[(1, "figura", 1)].name == "M1 - Figura 1.png"
        assert indice[(2, "figura", 1)].name == "M2 - Figura 1.png"
        assert indice[(3, "figura", 1)].name == "M3 - Figura 1.png"

    def test_las_convenciones_de_siempre_siguen_andando(self):
        indice = self._indice(["M_1 fig 2.jpg", "M1 Figura 3.jpg",
                               "Figura 4 M3.png", "Tabla 1 M2.jpg",
                               "M_Esquema.jpg"])
        assert indice[(1, "figura", 2)].name == "M_1 fig 2.jpg"
        assert indice[(1, "figura", 3)].name == "M1 Figura 3.jpg"
        assert indice[(3, "figura", 4)].name == "Figura 4 M3.png"
        assert indice[(2, "tabla", 1)].name == "Tabla 1 M2.jpg"
        assert indice[("esquema",)].name == "M_Esquema.jpg"


class TestTablaQueSoloEnvuelveLaFigura:
    """El docente a veces mete la figura en una tabla de 1 columna sin
    bordes, junto con su epígrafe y su nota. Eso NO es un recuadro: al
    encuadrarla, la imagen queda adentro de un dp-callout y _es_figura la
    descarta — la figura se publicaba sin ancho, sin borde y sin poder
    ampliarse. Caso real: la Figura 1 del módulo 1 de Creación de Valor."""

    HTML = ('<table>'
            '<tr><td><p>Figura 1. La progresión del valor económico</p></td></tr>'
            '<tr><td><p><img src="__MEDIA__/M_1 fig 1.jpg"></p></td></tr>'
            '<tr><td><p>Nota. Figura creada con ChatGPT.</p></td></tr>'
            '</table>')

    def test_no_queda_encuadrada_como_recuadro(self):
        out = procesar_contenido(self.HTML)
        assert "dp-callout" not in out

    def test_la_figura_conserva_su_estilo(self):
        out = procesar_contenido(self.HTML)
        assert "dp-image-bordered" in out
        assert "width: 600px" in out

    def test_un_recuadro_de_verdad_con_imagen_sigue_encuadrado(self):
        """Una caja del catálogo que además trae una imagen adentro sigue
        siendo caja: lo que la distingue es el rótulo, no la imagen."""
        html = ('<table>'
                '<tr><td><p>Ejemplos que iluminan</p></td></tr>'
                '<tr><td><p>Un caso con su gráfico.</p>'
                '<p><img src="__MEDIA__/x.jpg"></p></td></tr></table>')
        assert "dp-callout" in procesar_contenido(html)


class TestFiguraAmpliablePorComentario:
    """El asesor clava el globo SOBRE la imagen ("incluir pop up para
    ampliar"): aplicar_comentarios marca la figura y procesar_contenido le
    pone el estilo con lupa en vez del estático."""

    def test_la_marca_vuelve_la_figura_expandible(self):
        from bs4 import BeautifulSoup
        from maquetador.ingest.docx_comments import aplicar_comentarios
        html = ('<div><p>Figura 1. Un esquema</p>'
                '<p><img src="__MEDIA__/M_1 fig 1.jpg"></p>'
                '<p>Nota. Figura creada con ChatGPT.</p></div>')
        soup = BeautifulSoup(html, "html.parser")
        aplicar_comentarios(soup, [{
            "instruccion": "Para maquetación, incluir pop up para ampliar.",
            "anclado": "Nota. Figura creada con ChatGPT.",
            "accion": "figura_expandible", "autor": ""}])
        out = procesar_contenido(str(soup))
        assert "dp-popup-image" in out
        assert "data-ampliable" not in out   # la marca no se publica


class TestFiguraDeDisenoDesdeMarcador:
    """Cuando el asesor deja solo el marcador ("Figura 5. …") sin imagen
    embebida al lado, se inserta la figura de diseño en su lugar."""

    HTML = ('<p>La cláusula 4 a la 10 contiene los requisitos.</p>'
            '<p>Figura 5. Cláusulas del sistema de gestión de la calidad</p>'
            '<p>Texto alternativo: Breve resumen de las cláusulas de ISO 9001.</p>')

    def _generar(self):
        from pathlib import Path
        from maquetador.build.snippets import reemplazar_figuras_diseno
        return reemplazar_figuras_diseno(
            self.HTML, 1, {(1, "figura", 5): Path("M_1 fig 5.jpg")}, set())

    def test_inserta_la_figura_de_diseno(self):
        out = self._generar()
        assert "M_1 fig 5.jpg" in out

    def test_el_epigrafe_va_ARRIBA_de_la_imagen(self):
        """Salía invertido: primero la imagen y el epígrafe debajo."""
        out = self._generar()
        assert out.index("Cláusulas del sistema") < out.index("<img")

    def test_es_expandible_por_el_texto_alternativo_resumen(self):
        """'Breve resumen de las cláusulas…' describe una figura densa en
        texto (tipo tabla, difícil de leer en miniatura): se puede ampliar
        con clic (sombreada), aunque el asesor no lo haya pedido con la
        palabra 'expandible'. Pedido explícito del usuario ('Figura 5')."""
        out = self._generar()
        assert "dp-image-bordered" in out
        assert "dp-popup-image" in out
        assert "dp-image-shadow" in out
        assert "width: 700px" in out

    def test_sin_palabra_clave_de_densidad_queda_estatica_en_600(self):
        """Una figura común (sin 'resumen'/'síntesis'/'expandible' en el
        epígrafe ni en el texto alternativo) no se vuelve expandible: solo
        las figuras densas en texto lo piden."""
        from pathlib import Path
        from maquetador.build.snippets import reemplazar_figuras_diseno
        html = ('<p>Figura 1. Evolución de la gestión de calidad</p>'
                '<p>Texto alternativo: Línea de tiempo de la evolución '
                'histórica.</p>')
        out = reemplazar_figuras_diseno(
            html, 1, {(1, "figura", 1): Path("M_1 fig 1.jpg")}, set())
        assert "dp-popup-image" not in out
        assert "width: 600px" in out
