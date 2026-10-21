# -*- coding: utf-8 -*-
"""Lo que dejó la revisión de Metodología II (16-10-2026).

La corrección que más se repitió: el maquetador armaba componentes que la
asesora no había pedido, deduciéndolos del texto. *"Todo esto está bien
interpretado, pero lamentablemente si no me lo pide el asesor no puedo
marcarlo, así que la próxima dejalo texto plano."*

Los componentes salen SOLO cuando hay un pedido explícito: un comentario en
el DOCX, una tabla del asesor, o un marcador escrito en el documento.
"""

import pytest
from bs4 import BeautifulSoup

from maquetador.build.componentes_asesor import aplicar_cita
from maquetador.build.snippets import procesar_contenido
from maquetador.ingest.docx_comments import _clasificar, aplicar_comentarios


class TestNoSeInventanComponentes:
    """Las cuatro frases que armaban un recuadro sin que nadie lo pidiera."""

    @pytest.mark.parametrize("parrafo,componente", [
        # "No pases de largo" sobre un párrafo que arranca así.
        ("Es importante señalar que hay un mundo que nos preexiste, con su "
         "lenguaje, sus normas y un conjunto de instituciones que lo "
         "conforman, en el que los sujetos se vinculan intersubjetivamente.",
         "No pases de largo"),
        # "Descubrí leyendo".
        ("Te invito a leer el texto de Guevara Patiño que aborda el estado "
         "del arte en la investigación según los distintos paradigmas.",
         "Descubrí leyendo"),
        # Bloque de video, sin marcador ni enlace.
        ("Te propongo visualizar el material que acompaña este recorrido "
         "para seguir pensando la propuesta del módulo.",
         "data-title=\"Video\""),
        # "Miralo con lupa".
        ("Te propongo observar la imagen con atención y registrar qué "
         "elementos reconocés antes de seguir leyendo el apartado.",
         "Miralo con lupa"),
    ])
    def test_el_texto_solo_no_alcanza(self, parrafo, componente):
        out = procesar_contenido(f"<p>{parrafo}</p>")
        assert componente not in out
        assert "dp-callout" not in out

    def test_el_texto_sigue_estando(self):
        """No se arma el recuadro, pero el contenido no se pierde."""
        out = procesar_contenido(
            "<p>Es importante señalar que hay un mundo que nos preexiste, "
            "con su lenguaje y sus normas.</p>")
        assert "un mundo que nos preexiste" in out

    def test_con_el_comentario_del_asesor_si_se_arma(self):
        """La contracara: cuando lo pide, sale."""
        from maquetador.ingest.docx_comments import aplicar_comentarios
        soup = BeautifulSoup(
            "<p>Es importante señalar que hay un mundo que nos preexiste.</p>",
            "html.parser")
        aplicar_comentarios(soup, [{
            "accion": "recuadro_simple",
            "instruccion": "Para maquetación: mantener recuadro destacado",
            "anclado": "Es importante señalar que hay un mundo que nos preexiste.",
        }])
        assert "dp-callout" in str(soup)


class TestElVideoSaleConSuMarcador:
    """Apagar la deducción por prosa no puede llevarse por delante el video
    que el asesor sí marca."""

    def test_el_marcador_pegado_al_final(self):
        out = procesar_contenido(
            "<p>Antes de profundizar en cada una de estas herramientas, te "
            "proponemos mirar el siguiente video conceptual. VIDEO M2.</p>")
        assert 'data-title="Video"' in out

    def test_el_marcador_en_su_propio_parrafo(self):
        out = procesar_contenido(
            "<p>Te invitamos a ver el video conceptual del módulo.</p>"
            "<p>VIDEO M1.</p>")
        assert 'data-title="Video"' in out

    def test_el_marcador_no_se_publica(self):
        out = procesar_contenido(
            "<p>Te proponemos mirar el siguiente video. VIDEO M2.</p>")
        assert "VIDEO M2" not in out

    def test_un_enlace_externo_sigue_siendo_cta(self):
        """El enlace a YouTube está escrito en el documento: tampoco es una
        deducción de la prosa."""
        out = procesar_contenido(
            "<p>Te invito a ver el video sobre narrativas transmedia.</p>"
            '<p><a href="https://youtu.be/abc123">https://youtu.be/abc123</a></p>')
        assert "Auriculares on" in out

    def test_sin_marcador_ni_enlace_no_hay_bloque(self):
        out = procesar_contenido(
            "<p>Luego de ver el video, te propongo pensar en tu "
            "institución.</p>")
        assert 'data-title="Video"' not in out


class TestLaCitaDeWordEsUnaCita:
    """El estilo "Cita" de Word llegaba como <blockquote> y se publicaba
    encuadrado. Es una cita: va sangrada y sin caja."""

    FRASE = ("Esta actitud metodológica lleva necesariamente a sustituir la "
             "relación ingenua entre el individuo y la sociedad. (p. 18)")

    def test_queda_sangrada(self):
        out = procesar_contenido(f"<blockquote><p>{self.FRASE}</p></blockquote>")
        assert "margin-left: 80px" in out

    def test_no_queda_encuadrada(self):
        out = procesar_contenido(f"<blockquote><p>{self.FRASE}</p></blockquote>")
        assert "dp-callout" not in out

    def test_no_se_pierde_el_blockquote_sin_parrafos(self):
        out = procesar_contenido(f"<blockquote>{self.FRASE}</blockquote>")
        assert "sustituir la relación ingenua" in out
        assert "<blockquote" not in out


class TestLaSangriaDeLaCita:
    """Seis veces en la misma revisión: "le falta aumentar la sangría una
    vez más"."""

    def test_ochenta_a_la_izquierda(self):
        p = BeautifulSoup("<p>Una cita textual larga.</p>", "html.parser").p
        aplicar_cita(p)
        assert "margin-left: 80px" in p["style"]

    def test_cuarenta_a_la_derecha(self):
        """El margen derecho queda: sin él la cita se lee como un párrafo
        corrido con un margen cualquiera."""
        p = BeautifulSoup("<p>Una cita textual larga.</p>", "html.parser").p
        aplicar_cita(p)
        assert "margin-right: 40px" in p["style"]

    def test_respeta_el_estilo_que_ya_tenia(self):
        p = BeautifulSoup('<p style="text-align: justify;">Cita.</p>',
                          "html.parser").p
        aplicar_cita(p)
        assert "text-align: justify" in p["style"]
        assert "margin-left: 80px" in p["style"]


class TestLaRubricaLlegaASuActividad:
    """Las rúbricas vienen en la carpeta de Diseño nombradas por la
    actividad ("Actividad obligatoria 1 rubrica_evaluacion.jpg"). No son
    figuras del módulo —no tienen epígrafe "Figura N"— así que el reemplazo
    de figuras no las ubicaba: quedaban avisadas como sobrantes y no
    llegaban nunca al estudiante."""

    def _generador(self, imagenes):
        from pathlib import Path
        from maquetador.build.imscc_builder import GeneradorAula
        from maquetador.models import CourseSpec
        spec = CourseSpec(nombre="Materia")
        spec.imagenes_diseno = [Path(n) for n in imagenes]
        spec.tema = "educacion"
        g = GeneradorAula(spec, {}, Path("."))
        return g

    @pytest.mark.parametrize("clave,esperado", [
        ("actividad-obligatoria-m1", "Actividad obligatoria 1 rubrica_evaluacion.jpg"),
        ("actividad-obligatoria-m2", "Actividad obligatoria 2 rubrica_evaluacion.jpg"),
        ("actividad-final-integradora", "AFI rubrica_evaluacion.jpg"),
    ])
    def test_cada_rubrica_con_su_actividad(self, clave, esperado):
        g = self._generador([
            "Actividad obligatoria 1 rubrica_evaluacion.jpg",
            "Actividad obligatoria 2 rubrica_evaluacion.jpg",
            "AFI rubrica_evaluacion.jpg",
            "M1_fig 1.jpg",
        ])
        assert g._rubrica_de(clave).name == esperado

    def test_una_figura_comun_no_es_una_rubrica(self):
        g = self._generador(["M1_fig 1.jpg", "esquema.jpg"])
        assert g._rubrica_de("actividad-obligatoria-m1") is None

    def test_sin_clave_no_busca_nada(self):
        g = self._generador(["AFI rubrica_evaluacion.jpg"])
        assert g._rubrica_de("") is None

    def test_se_pega_al_pie_de_la_actividad(self):
        g = self._generador(["AFI rubrica_evaluacion.jpg"])
        html = ('<div class="dp-content-block content-block" '
                'data-title="Actividad"><h3>Consigna</h3><p>Hacé esto.</p>'
                "</div>")
        salida = g._agregar_rubrica(html, "actividad-final-integradora",
                                    "Actividad final integradora")
        assert "Rúbrica de evaluación" in salida
        assert "AFI%20rubrica_evaluacion.jpg" in salida or \
               "AFI rubrica_evaluacion.jpg" in salida
        # Adentro del bloque de la actividad, no suelta al final.
        assert salida.rstrip().endswith("</div>")

    def test_no_se_repite_si_ya_se_uso(self):
        from pathlib import Path
        g = self._generador(["AFI rubrica_evaluacion.jpg"])
        g.figuras_usadas.add(Path("AFI rubrica_evaluacion.jpg"))
        assert g._rubrica_de("actividad-final-integradora") is None


class TestElPopoverNoSaleVacio:
    """Esta cátedra nombra el componente al pedirlo ("para maquetación:
    popover: <url>"). Ese marcador no estaba en la lista, así que el
    contenido salía vacío y se publicaba un popover que al hacer clic no
    mostraba nada: peor que no ponerlo."""

    def _contenido(self, instruccion):
        from maquetador.ingest.docx_comments import _texto_tooltip
        return _texto_tooltip(instruccion)

    def test_con_dos_puntos(self):
        assert self._contenido(
            "para maquetación: popover: https://ejemplo.org/informe"
        ) == "https://ejemplo.org/informe"

    def test_sin_dos_puntos(self):
        assert self._contenido(
            "para maquetación popover https://es.wikipedia.org/wiki/Orbis"
        ) == "https://es.wikipedia.org/wiki/Orbis"

    def test_los_marcadores_de_siempre_siguen_andando(self):
        assert self._contenido(
            "Maquetación: que emerja: la gestión por objetivos"
        ) == "la gestión por objetivos"

    def test_sin_contenido_no_devuelve_nada(self):
        """"popover Diseño Universal de Aprendizaje" nombra el término pero
        no dice qué mostrar: queda como pedido pendiente."""
        from maquetador.ingest.docx_comments import aplicar_comentarios
        soup = BeautifulSoup(
            "<p>Tanto los MyTIC como los lenguajes interrogan la lógica "
            "escolar en sus fundamentos.</p>", "html.parser")
        comentarios = [{
            "accion": "tooltip",
            "instruccion": "para maquetación: popover",
            "anclado": "Tanto los MyTIC como los lenguajes interrogan la "
                       "lógica escolar en sus fundamentos.",
        }]
        aplicar_comentarios(soup, comentarios)
        assert "dp-tooltip-container" not in str(soup)
        assert not comentarios[0].get("_aplicado")

    def test_una_url_queda_enlazada_adentro(self):
        from maquetador.build.componentes_asesor import construir_tooltip
        html = construir_tooltip("Digital News Report",
                                 "https://ejemplo.org/informe", 0)
        assert 'href="https://ejemplo.org/informe"' in html
        assert 'target="_blank"' in html

    def test_un_texto_normal_no_se_enlaza(self):
        from maquetador.build.componentes_asesor import construir_tooltip
        html = construir_tooltip("DUA", "Diseño Universal de Aprendizaje", 0)
        assert "<a class=\"inline_disabled" not in html
        assert "Diseño Universal de Aprendizaje" in html


class TestElMarcadorDeVideoNuncaSePublica:
    """"Incrustar video aquí" es una indicación para maquetación. Solo la
    sacaba la rama del video propio (Canvas Studio): un foro que tuviera
    además un enlace externo salía con el marcador escrito en el aula,
    como el foro de apertura de Medios."""

    def test_con_enlace_externo_tampoco_se_publica(self):
        out = procesar_contenido(
            "<p>Les propongo observar una campaña institucional de UNICEF "
            "sobre identidad digital.</p>"
            "<p>incrustar video aquí.</p>"
            '<p><a href="https://youtu.be/abc">https://youtu.be/abc</a></p>')
        assert "incrustar video" not in out.lower()
        assert "Auriculares on" in out
        assert "campaña institucional de UNICEF" in out

    def test_el_video_propio_sigue_limpiando_su_marcador(self):
        out = procesar_contenido(
            "<p>Te proponemos mirar el siguiente video conceptual.</p>"
            "<p>VIDEO M1.</p>")
        assert "VIDEO M1" not in out
        assert 'data-title="Video"' in out

    def test_un_parrafo_que_habla_de_incrustar_no_es_un_marcador(self):
        """El marcador es corto y esta solo; una frase sobre el tema no."""
        from maquetador.build.snippets import _es_marcador_de_video
        soup = BeautifulSoup(
            "<p>Incrustar videos en una clase virtual exige pensar el "
            "formato, la duración y el momento en que se presentan.</p>",
            "html.parser")
        assert _es_marcador_de_video(soup.p) is False


class TestLoQueVieneAntesDeLaPrimeraSeccion:
    """El docente abre el módulo con una frase antes del rótulo
    "Introducción". Como todavía no hay sección abierta, ese tramo se
    descartaba y la frase no llegaba nunca al aula: "te olvidaste de eso,
    está clara la indicación" (revisión de Metodología II)."""

    def test_la_frase_de_apertura_se_conserva(self):
        from maquetador.extract.segmenter import _huerfano
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(
            "<table><tr><td>Carrera</td></tr></table>"
            "<p>Investigar y producir conocimientos con otras y otros es un "
            "gran desafío de la gestión educativa.</p>", "html.parser")
        acumulado = [e for e in soup.find_all(recursive=False)]
        # Antes de abrir la primera seccion: lo acumulado se arrastra.
        huerfano = _huerfano(None, acumulado)
        assert len(huerfano) == 1
        assert "Investigar y producir" in huerfano[0].get_text()

    def test_la_tabla_de_metadatos_no_se_arrastra(self):
        from maquetador.extract.segmenter import _huerfano
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(
            "<table><tr><td>Nombre de la carrera</td></tr></table>",
            "html.parser")
        assert _huerfano(None, [e for e in soup.find_all(recursive=False)]) == []

    def test_dentro_de_una_seccion_no_arrastra_nada(self):
        """Una vez abierta la primera seccion, lo acumulado es el cuerpo de
        ESA seccion y lo guarda el flujo normal."""
        from maquetador.extract.segmenter import _huerfano
        from bs4 import BeautifulSoup
        soup = BeautifulSoup("<p>Cuerpo de la seccion.</p>", "html.parser")
        acumulado = [e for e in soup.find_all(recursive=False)]
        assert _huerfano("1.1", acumulado) == []


class TestMantenerSangriaNoEsDestacar:
    """"Manteniendo sangría izq y cursiva" describe cómo ya se ve el
    párrafo y pide conservarlo: no pide un recuadro."""

    def test_no_arma_recuadro(self):
        from maquetador.ingest.docx_comments import aplicar_comentarios
        frase = ("Investigar y producir conocimientos con otras y otros es "
                 "un gran desafío de la gestión educativa.")
        soup = BeautifulSoup(f"<p><em>{frase}</em></p>", "html.parser")
        aplicar_comentarios(soup, [{
            "accion": "cita",
            "instruccion": "Para maquetación: frase de inicio antes de la "
                           "introducción, manteniendo sangría izq y cursiva",
            "anclado": frase,
        }])
        assert "dp-callout" not in str(soup)
        assert "margin-left: 80px" in str(soup)
        assert soup.find("em") is not None       # la cursiva del DOCX queda


class TestLaNotaAlPie:
    """"Esto es una nota al pie de los dos párrafos anteriores, que son una
    extracción de ese texto": la referencia de la que salió el texto de
    arriba. Va en cuerpo chico, donde está, y no como un párrafo más."""

    FRASE = ('*"Lo importante es contar una historia: aproximaciones al '
             'estudio de prácticas de alfabetización audiovisual en '
             'escenarios escolares" (Pineda, 2024).')

    def test_se_reconoce_el_pedido(self):
        assert _clasificar(
            "para maquetación, esto es una nota al pie de los dos párrafos "
            "anteriores, que son una extracción de ese texto") == "nota_al_pie"

    def test_queda_en_cuerpo_chico(self):
        from maquetador.ingest.docx_comments import aplicar_comentarios
        soup = BeautifulSoup(f"<p>{self.FRASE}</p>", "html.parser")
        comentarios = [{
            "accion": "nota_al_pie",
            "instruccion": "para maquetación, esto es una nota al pie",
            "anclado": self.FRASE,
        }]
        aplicar_comentarios(soup, comentarios)
        assert "font-size: 10pt" in str(soup)
        assert "Lo importante es contar una historia" in soup.get_text()
        assert comentarios[0]["_aplicado"] is True

    def test_no_se_vuelve_un_encabezado(self):
        """Lleva dp-heading-ignore: empieza con un asterisco y comillas, y
        sin eso las heuristicas de encabezado podrian levantarlo."""
        from maquetador.ingest.docx_comments import aplicar_comentarios
        soup = BeautifulSoup(f"<p>{self.FRASE}</p>", "html.parser")
        aplicar_comentarios(soup, [{
            "accion": "nota_al_pie",
            "instruccion": "para maquetación, esto es una nota al pie",
            "anclado": self.FRASE,
        }])
        assert "dp-heading-ignore" in str(soup)
