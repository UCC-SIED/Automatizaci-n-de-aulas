# -*- coding: utf-8 -*-
from bs4 import BeautifulSoup
from maquetador.build.componentes_asesor import (
    pares_de_tabla, pares_de_texto, extraer_pares, construir_panels,
    construir_flipcards, construir_popover, aplicar_cita,
)
from maquetador.ingest.docx_comments import aplicar_comentarios
from maquetador.build.snippets import _tabla_a_flipcards


def _soup(html):
    return BeautifulSoup(html, "html.parser")


class TestParesDeTabla:
    def test_celdas_alternadas(self):
        html = ("<table><tr><td><p>Título A</p></td></tr>"
                "<tr><td><p>Contenido A</p></td></tr>"
                "<tr><td><p>Título B</p></td></tr>"
                "<tr><td><p>Contenido B</p></td></tr></table>")
        tabla = _soup(html).find("table")
        pares = pares_de_tabla(tabla)
        assert len(pares) == 2
        assert pares[0][0] == "Título A"
        assert "Contenido A" in pares[0][1]
        assert pares[1][0] == "Título B"

    def test_celda_impar_usa_nbsp(self):
        html = ("<table><tr><td>Solo título</td></tr></table>")
        tabla = _soup(html).find("table")
        # un solo título sin contenido → 0 pares completos
        assert pares_de_tabla(tabla) == []


class TestParesDeTexto:
    def test_nombre_dos_puntos_contenido(self):
        parrafos = _soup(
            "<div><p>Vigor: alto nivel de energía y resistencia.</p>"
            "<p>Dedicación: sentido y entusiasmo en el trabajo.</p></div>"
        ).find_all("p")
        pares = pares_de_texto(parrafos)
        assert len(pares) == 2
        assert pares[0] == ("Vigor", "alto nivel de energía y resistencia.")
        assert pares[1][0] == "Dedicación"

    def test_parrafo_sin_dos_puntos_se_ignora(self):
        parrafos = _soup("<div><p>Un párrafo normal sin estructura.</p></div>").find_all("p")
        assert pares_de_texto(parrafos) == []


class TestExtraerPares:
    def test_menos_de_dos_pares_devuelve_vacio(self):
        el = _soup("<p>Solo: uno</p>").find("p")
        assert extraer_pares(el) == ([], [])

    def test_texto_dos_items(self):
        soup = _soup("<div><p>Primero: uno</p><p>Segundo: dos</p></div>")
        el = soup.find("p")
        pares, consumidos = extraer_pares(el)
        assert len(pares) == 2
        assert len(consumidos) == 2          # ambos párrafos se consumen


class TestConstruirPanels:
    def test_acordeon_estructura_cidilabs(self):
        html = construir_panels([("T1", "<p>C1</p>"), ("T2", "<p>C2</p>")])
        assert "dp-panels-wrapper dp-expander-default" in html
        assert html.count('class="dp-panel-group"') == 2
        assert '<h3 class="dp-panel-heading">T1</h3>' in html
        assert '<div class="dp-panel-content"><p>C1</p></div>' in html

    def test_tabs_variante(self):
        html = construir_panels([("T1", "x"), ("T2", "y")], variante="dp-tabs")
        assert "dp-panels-wrapper dp-tabs" in html


class TestConstruirFlipcards:
    def test_estructura_cidilabs(self):
        html = construir_flipcards([("Frente1", "Dorso1"), ("Frente2", "Dorso2")])
        assert 'class="row justify-content-center"' in html
        assert html.count('class="dp-flip-card"') == 2
        assert '<div class="dp-front-card">' in html
        assert '<div class="dp-back-card">' in html
        assert "<strong>Frente1</strong>" in html
        assert "Dorso1" in html


class TestConstruirPopover:
    def test_trigger_y_content_enlazados(self):
        trigger, content = construir_popover("stakeholders", "Toda parte interesada", 0)
        assert 'class="dp-popover-trigger"' in trigger
        assert 'href="#dpPopup0Content"' in trigger
        assert 'id="dpPopup0"' in trigger
        assert ">stakeholders</a>" in trigger
        assert 'id="dpPopup0Content"' in content
        assert "dp-popover-content dp-popup-content" in content
        assert "Toda parte interesada" in content


class TestAplicarCita:
    def test_agrega_sangria(self):
        el = BeautifulSoup("<p>Una cita textual.</p>", "html.parser").find("p")
        aplicar_cita(el)
        assert "margin-left: 40px" in el.get("style", "")


class TestCableado:
    """Acordeón y expander son variantes DISTINTAS de DesignPLUS: el acordeón
    es dp-accordion-default. Hasta la auditoría del 2026-09-10 ambos salían
    como dp-expander-default y estos tests fijaban ese error."""

    def test_acordeon_desde_texto_se_arma(self):
        soup = BeautifulSoup(
            "<div><p>Autoevaluación: la persona valora su propio desempeño.</p>"
            "<p>Evaluación por objetivos: mide el grado de cumplimiento.</p></div>",
            "html.parser")
        comentarios = [{
            "instruccion": "Maquetación: acordeón",
            "anclado": "Autoevaluación: la persona valora su propio desempeño.",
            "accion": "acordeon", "autor": "",
        }]
        aplicar_comentarios(soup, comentarios)
        assert "dp-panels-wrapper dp-accordion-default" in str(soup)
        assert comentarios[0].get("_aplicado") is True

    def test_acordeon_desde_tabla_se_arma(self):
        soup = BeautifulSoup(
            "<div><p>Acordeón:</p>"
            "<table><tr><td><p>Título A</p></td></tr>"
            "<tr><td><p>Contenido de A</p></td></tr>"
            "<tr><td><p>Título B</p></td></tr>"
            "<tr><td><p>Contenido de B</p></td></tr></table></div>",
            "html.parser")
        comentarios = [{
            "instruccion": "Maquetación: acordeón",
            "anclado": "Acordeón:",
            "accion": "acordeon", "autor": "",
        }]
        aplicar_comentarios(soup, comentarios)
        assert "dp-panels-wrapper dp-accordion-default" in str(soup)
        assert str(soup).count('class="dp-panel-group"') == 2
        assert comentarios[0].get("_aplicado") is True
        # la tabla original NO debe quedar duplicada
        assert soup.find("table") is None

    def test_sin_estructura_no_se_aplica(self):
        soup = BeautifulSoup("<div><p>Un párrafo cualquiera.</p></div>", "html.parser")
        comentarios = [{
            "instruccion": "Maquetación: acordeón",
            "anclado": "Un párrafo cualquiera.",
            "accion": "acordeon", "autor": "",
        }]
        aplicar_comentarios(soup, comentarios)
        # No hay ≥2 pares → no se arma → queda como aviso (no _aplicado)
        assert "dp-panels-wrapper" not in str(soup)
        assert comentarios[0].get("_aplicado") is not True

    def test_cita_sangra(self):
        soup = BeautifulSoup("<div><p>La GT es una iniciativa estratégica.</p></div>", "html.parser")
        comentarios = [{
            "instruccion": "Maquetación: es una cita",
            "anclado": "La GT es una iniciativa estratégica.",
            "accion": "cita", "autor": "",
        }]
        aplicar_comentarios(soup, comentarios)
        assert "margin-left: 40px" in str(soup)
        assert comentarios[0].get("_aplicado") is True

    def test_tooltip_preserva_parrafo(self):
        soup = BeautifulSoup("<div><p>Definición de stakeholders en proyectos ágiles.</p></div>", "html.parser")
        comentarios = [{"instruccion": "al hacer clic aparezca: parte interesada",
                        "anclado": "stakeholders", "accion": "tooltip", "autor": ""}]
        aplicar_comentarios(soup, comentarios)
        p = soup.find("p")
        assert p is not None                          # el <p> sobrevive
        assert "dp-popover-trigger" in str(p)         # el trigger queda DENTRO del <p>
        assert comentarios[0].get("_aplicado") is True

    def test_tooltip_palabra_ausente_no_aplica(self):
        soup = BeautifulSoup("<div><p>Texto sin la palabra clave.</p></div>", "html.parser")
        comentarios = [{"instruccion": "al hacer clic aparezca: X",
                        "anclado": "inexistenteylargo", "accion": "tooltip", "autor": ""}]
        aplicar_comentarios(soup, comentarios)
        assert "dp-popover-trigger" not in str(soup)
        assert comentarios[0].get("_aplicado") is not True


class TestFlipcardViejoAlineado:
    def test_usa_clases_cidilabs_reales(self):
        html = ("<table><tr><td>"
                "<p><strong>Frente A</strong> dorso A largo</p>"
                "<p><strong>Frente B</strong> dorso B largo</p>"
                "</td></tr></table>")
        tabla = BeautifulSoup(html, "html.parser").find("table")
        out = _tabla_a_flipcards(tabla)
        assert out is not None
        assert "dp-front-card" in out          # clase CidiLabs real
        assert "dp-flip-card-front" not in out  # ya NO la clase vieja


class TestParesDeTablaGrilla:
    """Tabla-grilla de N columnas: fila de títulos + fila de descripciones. Cada
    título debe emparejarse con la descripción de ABAJO (por columna), no con el
    título de al lado (regresión: pares cruzados '1. IDENTIFICACIÓN'/'2. PROPÓSITO')."""

    def test_grilla_titulos_arriba_descripciones_abajo(self):
        html = (
            "<table>"
            "<tr><td><p>1. Identificación</p></td><td><p>2. Propósito</p></td></tr>"
            "<tr><td><p>Nombre del puesto, área o negocio y fecha de descripcion del rol completo.</p></td>"
            "<td><p>Define en forma resumida para qué existe el puesto dentro de la organización y qué valor aporta.</p></td></tr>"
            "<tr><td><p>3. Organización</p></td><td><p>4. Magnitudes</p></td></tr>"
            "<tr><td><p>Estructura organizativa completa a la que pertenece el puesto dentro del organigrama.</p></td>"
            "<td><p>Medida cuantificable financiera o no sobre la que el puesto tiene impacto directo y relevante.</p></td></tr>"
            "</table>")
        tabla = _soup(html).find("table")
        pares = pares_de_tabla(tabla)
        titulos = [t for t, _ in pares]
        # Ningún par debe tener dos títulos numerados enfrentados
        for titulo, cuerpo in pares:
            assert not cuerpo.strip().lstrip("<p>").strip()[:2].rstrip(".").isdigit() \
                or "puesto" in cuerpo.lower() or "existe" in cuerpo.lower() \
                or "estructura" in cuerpo.lower() or "medida" in cuerpo.lower(), \
                f"Par cruzado título/título: {titulo!r} -> {cuerpo!r}"
        # El frente '1. Identificación' debe llevar SU descripción, no '2. Propósito'
        d = dict(pares)
        assert "1. Identificación" in d
        assert "Nombre del puesto" in d["1. Identificación"]
        assert "2. Propósito" in d
        assert "existe el puesto" in d["2. Propósito"]
