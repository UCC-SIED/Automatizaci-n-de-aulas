# -*- coding: utf-8 -*-
"""Errores detectados al corregir a mano "Gestión del Riesgo y la Incertidumbre".

El equipo maquetó el aula sobre el paquete generado y anotó, ítem por ítem,
todo lo que hubo que arreglar. Cada test de acá reproduce el markup real del
DOCX de esa materia que producía el error.
"""

import pytest
from bs4 import BeautifulSoup

from maquetador.build.snippets import procesar_contenido, SRC_ESPACIADOR
from maquetador.build.bibliography import construir_bibliografia


class TestEpigrafePartidoEnDosParrafos:
    """El asesor escribe el número de la figura en un renglón y su título en
    el siguiente. Son UN epígrafe: publicado partido, el título quedaba como
    texto suelto y el aire de la figura caía entre el título y la imagen en
    vez de arriba de todo el bloque."""

    def _cap(self, html):
        s = BeautifulSoup(procesar_contenido(html), "html.parser")
        return [p.get_text(" ", strip=True)
                for p in s.find_all("p", class_="dp-heading-ignore")]

    def test_une_el_numero_con_su_titulo(self):
        html = ("<p><strong>Figura 1</strong></p>"
                "<p>Riesgo, incertidumbre y complejidad</p>"
                "<p>Conocer estos conceptos permite definir una estrategia.</p>")
        assert self._cap(html) == ["Figura 1. Riesgo, incertidumbre y complejidad"]

    def test_tambien_con_tabla_y_con_el_punto_ya_puesto(self):
        html = ("<p><strong>Tabla 1.</strong></p>"
                "<p>Escalas de probabilidad e impacto por objetivo</p>"
                "<p>Cuerpo.</p>")
        assert self._cap(html) == [
            "Tabla 1. Escalas de probabilidad e impacto por objetivo"]

    def test_el_aire_de_la_figura_va_arriba_del_epigrafe(self):
        html = ("<p>La Figura 1 sintetiza estas diferencias.</p>"
                "<p><strong>Figura 1</strong></p>"
                "<p>Riesgo, incertidumbre y complejidad</p>"
                '<p><img src="__MEDIA__/fig.png"></p>')
        s = BeautifulSoup(procesar_contenido(html), "html.parser")
        bloques = [b for b in s.find_all(["p", "figure"], recursive=False)]
        etiquetas = [("aire" if b.name == "p" and not b.get_text(strip=True)
                      else ("epigrafe" if "dp-heading-ignore" in (b.get("class") or [])
                            else b.name))
                     for b in bloques]
        assert "aire" in etiquetas
        assert etiquetas.index("aire") < etiquetas.index("epigrafe")

    def test_no_se_lleva_un_parrafo_largo_que_no_es_titulo(self):
        html = ("<p><strong>Figura 1</strong></p>"
                "<p>" + "texto que sigue y sigue " * 15 + "</p>")
        assert self._cap(html) == ["Figura 1"]

    def test_no_se_lleva_la_nota_al_pie_de_la_figura(self):
        html = ("<p><strong>Figura 1</strong></p>"
                "<p>Nota. Elaboración propia.</p>")
        assert self._cap(html) == ["Figura 1"]


class TestImagenEspaciadoraDeWord:
    """Word deja imágenes de 1x1 transparentes como espaciador. Publicadas
    quedan como una caja vacía con borde: el foro de apertura de Gestión del
    Riesgo abría con un recuadro vacío sin sentido."""

    def test_se_va_la_imagen_y_su_parrafo(self):
        html = (f'<p><img src="{SRC_ESPACIADOR}"></p>'
                "<h3>¡Bienvenidos y bienvenidas!</h3><p>Este foro es el punto "
                "de partida para conocernos.</p>")
        out = procesar_contenido(html)
        assert "<img" not in out
        assert out.lstrip().startswith("<h3>")

    def test_no_toca_las_imagenes_de_verdad(self):
        html = '<p><img src="__MEDIA__/fig.png"></p><p>Texto.</p>'
        assert "__MEDIA__/fig.png" in procesar_contenido(html)


class TestTitulosOficialesComoEtiqueta:
    """El asesor escribe el título oficial del snippet como etiqueta de la
    caja ("Descubrí leyendo", "No pases de largo") en vez del tipo
    ("Lectura", "Importante"): sin reconocerlos, salían de recuadro simple,
    sin barra de título, ícono ni color."""

    def _caja(self, etiqueta, cuerpo):
        html = (f"<table><thead><tr><th><p><strong>{etiqueta}</strong></p>"
                f"</th></tr><tr><th><p>{cuerpo}</p></th></tr></thead></table>")
        return procesar_contenido(html)

    def test_descubri_leyendo_es_el_cta_de_lectura(self):
        out = self._caja("Descubrí leyendo",
                         "Para profundizar, te sugiero leer a Hillson (2017).")
        assert "Descubrí leyendo" in out
        assert "fa-book-reader" in out
        assert "dp-callout-type-title-bar" in out

    def test_no_pases_de_largo_es_el_recuadro_importante(self):
        """El catálogo tiene tres cajas con ese mismo título; la que usa el
        equipo para destacar lo que no hay que saltearse es la de Importante
        (ámbar, con el marcador), no la de Atención (roja, con el triángulo):
        ese peso es para una advertencia, no para un resumen de ideas clave."""
        out = self._caja("No pases de largo",
                         "La gestión del riesgo no es un acto único.")
        assert "No pases de largo" in out
        assert "dp-callout-color-lg-warning" in out
        assert "fa-bookmark" in out
        assert "dp-callout-color-danger" not in out


class TestLinkCrudoDentroDeUnRecuadro:
    """La URL pelada al final de la oración no le dice nada a nadie: el
    equipo la renombra siempre y la baja a su propio renglón."""

    def _caja(self, cuerpo):
        html = ("<table><thead><tr><th><p><strong>Descubrí leyendo</strong>"
                f"</p></th></tr><tr><th>{cuerpo}</th></tr></thead></table>")
        return procesar_contenido(html)

    def test_la_url_pasa_a_ser_acceso_al_documento(self):
        out = self._caja(
            "<p>Si no podés acceder al libro, esta reseña de acceso libre "
            'sintetiza sus ideas: <a href="https://pmworldjournal.com/x">'
            "https://pmworldjournal.com/x</a></p>")
        assert "Acceso al documento" in out
        assert ">https://pmworldjournal.com/x<" not in out
        s = BeautifulSoup(out, "html.parser")
        enlace = s.find("a", href="https://pmworldjournal.com/x")
        assert enlace.parent.name == "p"
        assert enlace.parent.get_text(strip=True) == "Acceso al documento"

    def test_si_el_texto_habla_de_un_articulo_dice_articulo(self):
        out = self._caja('<p>Te dejo el artículo completo: '
                         '<a href="https://x.org/a">https://x.org/a</a></p>')
        assert "Acceso al artículo" in out


class TestBajadaDeRecuadro:
    """El renglón en negrita con el que abre un recuadro es su bajada: va más
    grande, pero NO como encabezado (el recuadro ya tiene el suyo)."""

    def test_el_titulo_del_ejemplo_va_en_lead_18pt(self):
        html = ("<table><thead><tr><th><p><strong>Ejemplos que iluminan"
                "</strong></p></th></tr><tr><th>"
                "<p><strong>Un mismo riesgo, tres decisiones distintas</strong></p>"
                "<p>Supongamos que existe un riesgo idéntico en tres proyectos."
                "</p></th></tr></thead></table>")
        s = BeautifulSoup(procesar_contenido(html), "html.parser")
        bajada = s.find("p", class_="lead")
        assert bajada is not None
        assert bajada.get_text(strip=True) == \
            "Un mismo riesgo, tres decisiones distintas"
        assert "font-size: 18pt" in str(bajada)
        assert not s.find_all(["h4", "h5"])

    def test_un_recuadro_de_un_solo_parrafo_no_tiene_bajada(self):
        html = ("<table><thead><tr><th><p><strong>Ejemplos que iluminan"
                "</strong></p></th></tr><tr><th>"
                "<p><strong>Todo el cuerpo va en negrita.</strong></p>"
                "</th></tr></thead></table>")
        s = BeautifulSoup(procesar_contenido(html), "html.parser")
        assert s.find("p", class_="lead") is None


class TestSubitemsAnidados:
    """Word no anida: el asesor escribe el ítem que abre con ":" y debajo,
    al mismo nivel, su desglose. Sin anidarlos se pierde que cuelgan de él."""

    HTML = ("<ul><li>En primer lugar, guía al equipo por cada categoría.</li>"
            "<li>En segundo lugar, permite asignar cada riesgo al área más "
            "competente para su gestión:</li>"
            "<li>Técnicos: especialistas del proceso o del producto.</li>"
            "<li>De gestión: dirección del proyecto.</li>"
            "<li>Contractuales: Área legal.</li></ul>")

    def test_los_subitems_quedan_adentro_del_que_los_abre(self):
        s = BeautifulSoup(procesar_contenido(self.HTML), "html.parser")
        raiz = s.find("ul")
        items = raiz.find_all("li", recursive=False)
        assert len(items) == 2
        anidados = items[1].find("ul").find_all("li")
        assert [li.get_text(" ", strip=True) for li in anidados] == [
            "Técnicos: especialistas del proceso o del producto.",
            "De gestión: dirección del proyecto.",
            "Contractuales: Área legal."]

    def test_una_lista_normal_no_se_toca(self):
        html = ("<ul><li>Ventas</li><li>Resultado operativo</li>"
                "<li>EBITDA</li></ul>")
        s = BeautifulSoup(procesar_contenido(html), "html.parser")
        assert len(s.find("ul").find_all("li", recursive=False)) == 3
        assert s.find("li").find("ul") is None


class TestBibliografiaConLosRotulosDelDocx:
    """El DOCX trae "Bibliografía obligatoria" y "Bibliografía sugerida y
    complementaria" como subtítulos. El segmentador los tomaba por el
    arranque de otra sección y los descartaba: las dos listas salían pegadas
    en un solo bloque sin clasificar, en todo el curso."""

    REFS = ("<p><em>Bibliografía obligatoria</em></p>"
            "<p>Project Management Institute. (2025). <em>Guía del PMBOK</em> "
            '(8a ed.). PMI. <a href="https://idp.pmi.org/">https://idp.pmi.org/</a></p>'
            "<p><em>Bibliografía sugerida y complementaria</em></p>"
            "<p>Hillson, D. (2017). <em>Managing risk attitude</em>. Routledge.</p>")

    def test_separa_obligatoria_de_sugerida(self):
        out = construir_bibliografia(self.REFS)
        assert '<h4 style="text-align: left;">Obligatoria</h4>' in out
        assert '<h4 style="text-align: left;">Sugerida y complementaria</h4>' in out
        assert out.index("PMBOK") < out.index("Sugerida y complementaria")
        assert out.index("Sugerida y complementaria") < out.index("Hillson")

    def test_la_nota_al_pie_no_es_una_referencia(self):
        """La transparencia deja "<ol><li id=footnote-0>https://gemini…" al
        final de las referencias: salía publicada como una cita más."""
        refs = self.REFS + ('<ol><li id="footnote-0"><p> https://gemini.google.com/ '
                            '<a href="#footnote-ref-0">↑</a></p></li></ol>')
        out = construir_bibliografia(refs)
        assert "gemini.google.com" not in out


class TestNotasAlPieConUrl:
    """La llamada "[1]" no lleva a ningún lado en el aula (cada sección es
    una página): cuando la nota es solo una URL, esa URL pasa a ser el
    enlace de la palabra que la llamaba."""

    def test_enlaza_la_palabra_y_borra_la_llamada(self):
        from maquetador.build.snippets import (urls_de_notas_al_pie,
                                               enlazar_notas_al_pie)
        notas = urls_de_notas_al_pie(
            '<ol><li id="footnote-0"><p> https://gemini.google.com/ '
            '<a href="#footnote-ref-0">↑</a></p></li></ol>')
        assert notas == {"footnote-0": "https://gemini.google.com/"}
        out = enlazar_notas_al_pie(
            "<p>se perfeccionó con el apoyo de Gemini<sup><sup>"
            '<a href="#footnote-0" id="footnote-ref-0">[1]</a></sup></sup>, '
            "herramienta de IA generativa.</p>", notas)
        s = BeautifulSoup(out, "html.parser")
        enlace = s.find("a")
        assert enlace["href"] == "https://gemini.google.com/"
        assert enlace.get_text(strip=True) == "Gemini"
        assert "[1]" not in out

    def test_sin_url_conocida_la_llamada_se_borra(self):
        from maquetador.build.snippets import enlazar_notas_al_pie
        out = enlazar_notas_al_pie(
            '<p>Texto<sup><a href="#footnote-9" id="footnote-ref-9">[3]</a>'
            "</sup> y sigue.</p>", {})
        assert "[3]" not in out and "footnote" not in out


class TestNombresYOrdenDeLosItemsDelModulo:
    """Cómo se llaman y dónde van los ítems que el generador agrega al aula
    base, según cómo los deja el equipo en Canvas (capturas del aula de
    Gestión del Riesgo ya maquetada)."""

    def _generador(self, tema="posgrado"):
        from maquetador.models import CourseSpec
        from maquetador.build.imscc_builder import GeneradorAula
        from pathlib import Path
        return GeneradorAula(CourseSpec(nombre="X", tema=tema), {}, Path("."))

    def test_el_foro_de_participacion_de_posgrado_es_foro_mn(self):
        """El aula base rotula TODOS los foros de módulo como "Foro obligatorio
        MN", pero ese nombre es solo del calificable."""
        assert self._generador()._nombre_de_foro(2) == "Foro M2"

    def test_en_educacion_es_foro_sugerido_mn(self):
        assert self._generador("educacion")._nombre_de_foro(2) == "Foro sugerido M2"

    def test_la_consigna_calificable_no_va_al_buzon_no_calificable(self):
        """La actividad no calificable se agrega ARRIBA de la obligatoria: con
        un patrón genérico, la consigna calificable se volcaba en la primera
        que encontrara, que pasó a ser la no calificable."""
        g = self._generador()
        g.meta = (
            '<item identifier="a"><content_type>Assignment</content_type>'
            "<workflow_state>active</workflow_state><title>Actividad M2</title>"
            "<identifierref>rid-no-calificable</identifierref></item>"
            '<item identifier="b"><content_type>Assignment</content_type>'
            "<workflow_state>active</workflow_state>"
            "<title>Actividad obligatoria M2</title>"
            "<identifierref>rid-obligatoria</identifierref></item>")
        assert g._rid_obligatoria(2) == "rid-obligatoria"
        assert g._rid_actividad(2, "Actividad obligatoria") == (
            "rid-obligatoria", "Actividad obligatoria M2")
        assert g._rid_actividad(2, "Actividad sugerida") == (
            "rid-no-calificable", "Actividad M2")
