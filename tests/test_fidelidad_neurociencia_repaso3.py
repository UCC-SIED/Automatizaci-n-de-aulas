# -*- coding: utf-8 -*-
"""Tercera tanda del repaso de "Neurociencia Aplicada I".

Componentes y actividad: lo que el equipo corrigió a mano sobre 2.2, 2.4,
3.1, 3.2 y la actividad obligatoria del módulo 2, verificado contra las
páginas que pasó como correctas.
"""

from bs4 import BeautifulSoup

from maquetador.build.snippets import procesar_contenido, maquetar_actividad
from maquetador.ingest.docx_comments import aplicar_comentarios
from maquetador.build.imscc_builder import GeneradorAula


class TestSubtitulosConLetraComoTabs:
    """"a. Inteligencia emocional" y "b. Capacidad de persuasión" no son dos
    secciones sueltas: son las ramas de la enumeración que el párrafo de
    arriba acaba de anunciar. El asesor las marcó como subtítulo —error
    suyo, corregido en reunión— y van como solapas."""

    HTML = ("<p>Entre ellos, dos que son básicos: a) inteligencia emocional; "
            "y b) capacidad de persuasión.</p>"
            "<h3><strong>a. Inteligencia emocional</strong></h3>"
            "<p>La medida de la inteligencia depende de los parámetros.</p>"
            "<h3><strong>b. Capacidad de persuasión</strong></h3>"
            "<p>¿Alguna vez has propuesto una idea brillante?</p>")

    def test_se_arman_las_solapas(self):
        s = BeautifulSoup(procesar_contenido(self.HTML), "html.parser")
        tabs = s.find(class_="dp-panels-wrapper")
        assert tabs is not None
        assert "dp-tabs-buttons" in tabs.get("class")
        titulos = [h.get_text(" ", strip=True)
                   for h in tabs.find_all(class_="dp-panel-heading")]
        assert titulos == ["a. Inteligencia emocional",
                           "b. Capacidad de persuasión"]

    def test_el_cuerpo_de_cada_rama_entra_en_su_solapa(self):
        s = BeautifulSoup(procesar_contenido(self.HTML), "html.parser")
        paneles = s.find_all(class_="dp-panel-content")
        assert "parámetros" in paneles[0].get_text()
        assert "idea brillante" in paneles[1].get_text()

    def test_la_entrada_queda_afuera(self):
        s = BeautifulSoup(procesar_contenido(self.HTML), "html.parser")
        tabs = s.find(class_="dp-panels-wrapper")
        assert "Entre ellos, dos que son básicos" not in tabs.get_text()

    def test_un_solo_subtitulo_con_letra_no_arma_nada(self):
        html = ("<h3>a. Inteligencia emocional</h3><p>Cuerpo.</p>"
                "<h3>Persuasión e inteligencia emocional</h3><p>Otro.</p>")
        assert "dp-panels-wrapper" not in procesar_contenido(html)


class TestElAireDebajoDelExpander:
    """El componente ya trae su propio margen, así que contra un subtítulo
    o texto el renglón de aire sobra (los lóbulos cerebrales de 1.3.3).
    Contra otra caja hace falta: una pegada a la otra no se distinguen (la
    serie de figuras de 3.5, con el "Descubrí leyendo" justo abajo)."""

    PANELES = ("<h3>a. Frontal</h3><p>Uno.</p>"
               "<h3>b. Parietal</h3><p>Dos.</p>")

    def test_contra_un_subtitulo_el_aire_se_saca(self):
        html = (self.PANELES
                + "<p>&nbsp;</p><h3>La corteza cerebral</h3><p>Sigue.</p>")
        s = BeautifulSoup(procesar_contenido(html), "html.parser")
        sig = s.find(class_="dp-panels-wrapper").find_next_sibling()
        assert sig is not None and sig.name == "h3"

    def test_contra_un_recuadro_el_aire_se_queda(self):
        html = (self.PANELES + "<p>&nbsp;</p>"
                "<table><thead><tr><th><p><strong>Descubrí leyendo</strong>"
                "</p></th></tr><tr><th><p>Revisá el capítulo 2 del libro.</p>"
                "</th></tr></thead></table>")
        s = BeautifulSoup(procesar_contenido(html), "html.parser")
        sig = s.find(class_="dp-panels-wrapper").find_next_sibling()
        assert sig is not None and sig.name == "p"
        assert not sig.get_text().strip()
        assert "dp-callout" in " ".join(
            sig.find_next_sibling().get("class") or [])


class TestElAltEntreElRotuloYElTitulo:
    """En 3.2 el asesor intercala el texto alternativo entre "Figura 1" y el
    título: el epígrafe salía publicado como "Figura 1. texto alternativo:
    El estoicismo regula emociones…"."""

    HTML = ("<p><strong>Figura 1 </strong></p>"
            "<p>texto alternativo: El estoicismo regula emociones con razón.</p>"
            "<p><strong>¿Qué es y qué no es estoicismo?</strong></p>"
            '<p><img src="__MEDIA__/f1.png"></p>')

    def test_el_epigrafe_toma_el_titulo_de_verdad(self):
        out = procesar_contenido(self.HTML)
        assert "Figura 1. ¿Qué es y qué no es estoicismo?" in out
        assert "Figura 1. texto alternativo" not in out

    def test_y_el_alt_llega_a_la_imagen(self):
        s = BeautifulSoup(procesar_contenido(self.HTML), "html.parser")
        img = s.find("img")
        assert img["alt"].startswith("El estoicismo regula emociones")
        assert "texto alternativo" not in s.get_text()


class TestFlipCardConIgual:
    """El asesor separa frente y dorso con "=" ("Zenón = Disciplina estoica
    y coherencia."). Sin reconocerlo, los cuatro filósofos de 3.2 quedaban
    como cuatro renglones sueltos."""

    HTML = ("<p>Zenón = Disciplina estoica y coherencia.</p>"
            "<p>Séneca = Gestionar el poder y el tiempo personal.</p>"
            "<p>Epicteto = Focalizarse y conseguir control emocional.</p>"
            "<p>Marco Aurelio = Capacidad de reflexión y servicio.</p>"
            "<p>Este aporte resulta profundamente actual: en un entorno de "
            "reacción constante, el líder sufre menos.</p>")

    def _aplicar(self):
        s = BeautifulSoup(self.HTML, "html.parser")
        aplicar_comentarios(s, [{
            "accion": "flip_card",
            "instruccion": "para maquetación: flip card",
            "anclado": "Zenón = Disciplina estoica y coherencia."}])
        return str(s)

    def test_se_arman_las_cuatro_tarjetas(self):
        s = BeautifulSoup(self._aplicar(), "html.parser")
        frentes = [c.find(class_="dp-front-card").get_text(" ", strip=True)
                   for c in s.find_all(class_="dp-flip-card")]
        assert frentes == ["Zenón", "Séneca", "Epicteto", "Marco Aurelio"]

    def test_el_parrafo_de_cierre_no_entra_ni_desaparece(self):
        """Tiene dos puntos de puntuación normal, no es un par: se colaba
        como quinta tarjeta y después se borraba de la página."""
        out = self._aplicar()
        assert "Este aporte resulta profundamente actual" in out
        s = BeautifulSoup(out, "html.parser")
        assert len(s.find_all(class_="dp-flip-card")) == 4


class TestElTituloDeLaActividad:
    """La portada del DOCX se saca, pero el título del caso se queda: va en
    el h2 del bloque, con el ícono de tareas y en el azul institucional."""

    CUERPO = ("<h3>Actividad Obligatoria 1: Diagnóstico de Neuroliderazgo en "
              "una Organización Real</h3><p>Contextualización del caso.</p>")

    def test_le_saca_el_prefijo_con_numero_pelado(self):
        out = maquetar_actividad(self.CUERPO, "posgrado")
        assert "Diagnóstico de Neuroliderazgo en una Organización Real" in out
        assert "Actividad Obligatoria 1" not in out

    def test_el_titulo_entra_en_el_h2_del_icono(self):
        html = ('<div data-title="Actividad">'
                '<h2 class="dp-has-icon"><i class="dp-icon fas fa-tasks"></i>'
                "</h2>"
                '<h2 class="dp-ignore-theme" style="color: #003087; '
                'text-align: center;"><strong>Diagnóstico</strong></h2>'
                "<p>Cuerpo.</p></div>")
        s = BeautifulSoup(GeneradorAula._titulo_dentro_del_encabezado(html),
                          "html.parser")
        assert s.find("h2", class_="dp-ignore-theme") is None
        h2 = s.find("h2", class_="dp-has-icon")
        assert "Diagnóstico" in h2.get_text()
        assert h2.find("i", class_="fa-tasks") is not None
        assert "#003087" in h2["style"]

    def test_si_el_aula_base_ya_trae_texto_no_se_toca(self):
        html = ('<div data-title="Actividad">'
                '<h2 class="dp-has-icon">¡Llegaste al final!</h2>'
                '<h2 class="dp-ignore-theme"><strong>Caso</strong></h2></div>')
        out = GeneradorAula._titulo_dentro_del_encabezado(html)
        assert "dp-ignore-theme" in out


class TestLaOracionDestacadaVaEnLead:
    """"Calificación mínima para aprobar la actividad: 70/100 (equivalente a
    7)." es una oración en negrita al pie de la actividad: salía de <h4>."""

    def test_queda_como_parrafo_destacado(self):
        html = ("<p><strong>Calificación mínima para aprobar la actividad: "
                "70/100 (equivalente a 7).</strong></p>")
        s = BeautifulSoup(procesar_contenido(html), "html.parser")
        assert s.find(["h3", "h4"]) is None
        p = s.find("p")
        assert "lead" in (p.get("class") or [])
        assert p.find("strong") is not None

    def test_un_subtitulo_corto_en_negrita_sigue_siendo_h3(self):
        out = procesar_contenido("<p><strong>Mucho más que emociones</strong></p>")
        assert "<h3>" in out
