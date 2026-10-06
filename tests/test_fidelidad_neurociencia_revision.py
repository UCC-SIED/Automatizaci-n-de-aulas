# -*- coding: utf-8 -*-
"""Correcciones de la revisión en Canvas de "Neurociencia Aplicada I".

El equipo maquetó el aula sobre el paquete generado y anotó, ítem por ítem,
lo que hubo que arreglar. Cada test reproduce el markup real que producía el
error, verificado contra la exportación corregida del aula.
"""

import pytest
from bs4 import BeautifulSoup

from maquetador.build.snippets import procesar_contenido, _texto_de_acceso
from maquetador.build.bibliography import construir_bibliografia, _icono_de


class TestEtiquetaDeSeccionDelDocx:
    """El asesor separa su DOCX con rótulos ("Consigna"). En el aula el
    bloque ya se presenta con su ícono y su título, así que ese rótulo queda
    suelto arriba de todo: en el foro de apertura se publicó así."""

    def test_el_rotulo_que_abre_el_contenido_se_va(self):
        html = ("<p><strong>Consigna</strong></p>"
                "<p>Les damos la bienvenida a la asignatura.</p>")
        out = procesar_contenido(html)
        assert "Consigna" not in out
        assert "Les damos la bienvenida" in out

    def test_si_no_abre_el_contenido_se_queda(self):
        """En medio del texto, "Consigna" es contenido: el rótulo solo sobra
        cuando es lo primero."""
        html = ("<p>Antes de empezar, leé con atención.</p>"
                "<p><strong>Consigna</strong></p><p>Elegí un caso.</p>")
        assert "Consigna" in procesar_contenido(html)


class TestNoPasesDeLargoEsImportante:
    """El catálogo trae tres cajas con ese mismo título. La que usa el equipo
    para destacar lo que no hay que saltearse es la de Importante (ámbar, con
    el marcador), no la de Atención (roja, con el triángulo)."""

    def test_la_variante_es_la_de_importante(self):
        html = ("<table><thead><tr><th><p><strong>No pases de largo</strong>"
                "</p></th></tr><tr><th><p>Las emociones no son enemigas de la "
                "razón.</p></th></tr></thead></table>")
        out = procesar_contenido(html)
        assert "dp-callout-color-lg-warning" in out
        assert "fa-bookmark" in out
        assert "dp-callout-color-danger" not in out
        assert "fa-exclamation-triangle" not in out


class TestBitacoraDeAprendizaje:
    """Ficha propia, con barra lateral gruesa y encabezado: no es un
    dp-callout. Sin reconocerla salía de recuadro simple, sin título."""

    def test_arma_la_ficha_con_su_encabezado(self):
        html = ("<table><thead><tr><th><p><strong>Bitácora de aprendizaje"
                "</strong></p></th></tr><tr><th><p>Escribí en qué medida "
                "cambió tu perspectiva.</p></th></tr></thead></table>")
        out = procesar_contenido(html)
        assert "Bitácora de aprendizaje" in out
        assert "fa-diagnoses" in out
        assert "#003366" in out
        assert "Escribí en qué medida" in out
        assert "dp-callout" not in out


class TestNombreDelEnlaceSegunElRecurso:
    """El enlace se publica con lo que el lector va a hacer del otro lado. La
    pista sale de la cita APA, que declara el tipo entre corchetes."""

    @pytest.mark.parametrize("contexto,esperado", [
        ("Lahiperactina. (2024). Dos neuronas [Video]. YouTube.", "Ver video"),
        ("Un episodio del podcast sobre liderazgo", "Escuchar el podcast"),
        ("Te dejo el artículo completo", "Acceso al artículo"),
        ("Revisá el capítulo 2 del manual", "Acceso al documento"),
    ])
    def test_cada_recurso_con_su_texto(self, contexto, esperado):
        assert _texto_de_acceso(contexto) == esperado

    def test_dentro_del_recuadro_de_video(self):
        html = ("<table><thead><tr><th><p><strong>Auriculares on</strong></p>"
                "</th></tr><tr><th>"
                "<p>Lahiperactina. (2024, 31 enero). Dos neuronas a punto de "
                'conectarse [Video]. YouTube. <a href="https://youtu.be/x">'
                "https://youtu.be/x</a></p></th></tr></thead></table>")
        out = procesar_contenido(html)
        assert ">Ver video<" in out
        assert "Acceso al documento" not in out


class TestFuenteDeLaFiguraEntreParentesis:
    """Entre paréntesis y en la misma línea, la URL parte el pie de la figura
    al medio. El equipo la manda abajo con un salto de línea y le saca los
    paréntesis y el punto final."""

    def test_el_enlace_baja_a_su_renglon(self):
        html = ('<p><img src="__MEDIA__/fig.png"></p>'
                "<p>Nota. Cuadro creado con ChatGPT (https://chatgpt.com/).</p>")
        out = procesar_contenido(html)
        s = BeautifulSoup(out, "html.parser")
        cap = s.find("figcaption")
        assert cap is not None
        assert cap.find("br") is not None
        assert "(" not in cap.get_text()
        assert cap.get_text(" ", strip=True).startswith("Cuadro creado con ChatGPT")

    def test_una_nota_sin_enlace_queda_igual(self):
        html = ('<p><img src="__MEDIA__/fig.png"></p>'
                "<p>Nota. Elaboración propia.</p>")
        s = BeautifulSoup(procesar_contenido(html), "html.parser")
        assert s.find("figcaption").find("br") is None


class TestRecuadroSinHuecoAlFinal:
    """El asesor cierra la caja con un renglón en blanco. Adentro del
    recuadro no hace falta —la caja ya trae su padding— y deja un hueco raro
    contra el borde."""

    def test_el_parrafo_vacio_final_se_va(self):
        html = ("<table><thead><tr><th><p><strong>Descubrí leyendo</strong>"
                "</p></th></tr><tr><th><p>Revisá el capítulo 2.</p>"
                "<p>&nbsp;</p></th></tr></thead></table>")
        s = BeautifulSoup(procesar_contenido(html), "html.parser")
        cuerpo = s.find(class_="card-body")
        hijos = cuerpo.find_all(recursive=False)
        assert hijos[-1].get_text(strip=True), "el recuadro cierra en vacío"


class TestBibliografiaDeLaPagina:
    """En la página de Bibliografía el h2 es el título del bloque, así que
    "Obligatoria" es un h3. El h4 es del índice del Programa, donde además
    cuelga de un h3 por módulo. Y el bloque cierra con aire, como todos."""

    REFS = ("<p><em>Bibliografía obligatoria</em></p>"
            "<p>Roldán, L. (2025). <em>Neurociencia empresarial</em>. "
            'Autoedición. <a href="https://drive.google.com/x">'
            "https://drive.google.com/x</a></p>")

    def test_la_pagina_usa_h3(self):
        out = construir_bibliografia(self.REFS, nivel="h3")
        assert '<h3 style="text-align: left;">Obligatoria</h3>' in out

    def test_el_programa_sigue_en_h4(self):
        out = construir_bibliografia(self.REFS)
        assert '<h4 style="text-align: left;">Obligatoria</h4>' in out

    def test_cierra_con_aire(self):
        assert construir_bibliografia(self.REFS).rstrip().endswith("<p>&nbsp;</p>")

    @pytest.mark.parametrize("referencia,url,icono", [
        ("Biointeractive. (2016). Mecanismos [Video]. YouTube",
         "https://www.youtube.com/watch?v=1i8", "Icono%20video.svg"),
        ("Un episodio del podcast", "https://open.spotify.com/x",
         "icono%20podcast.svg"),
        ("Roldán, L. (2025). Neurociencia empresarial. Autoedición.",
         "https://drive.google.com/x", "icono%20lectura.svg"),
    ])
    def test_el_icono_dice_de_que_recurso_se_trata(self, referencia, url, icono):
        assert _icono_de(referencia, url).endswith(icono)
