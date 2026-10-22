# -*- coding: utf-8 -*-
"""Las "ventanas emergentes" numeradas (IA Aplicada I - Salud, Virgolini).

La asesora marca el par con dos globos: "Maquetación: ventana emergente 1"
sobre el bloque de párrafos que tiene que emerger y "Maquetación: enlazar a
ventana emergente 1" sobre la palabra que lo abre, más arriba en el texto.
Se juntan por el número.

Hasta ahora los dos caían en "revisar" y el bloque salía como párrafos
sueltos, con el término repetido: una vez en la mención y otra como título
del bloque.

El markup sale de `Snippets - ventanas emergentes.html`, el HTML de
referencia de DesignPLUS que pasó el usuario (22-10-2026).
"""


from bs4 import BeautifulSoup

from maquetador.build.componentes_asesor import (construir_popover,
                                                 construir_tooltip)
from maquetador.ingest.docx_comments import _clasificar, aplicar_comentarios


def _comentario(instruccion, anclado):
    return {"instruccion": instruccion, "anclado": anclado,
            "accion": _clasificar(instruccion, anclado), "_orden": 0}


MENCION = ("<p>Siguieron apareciendo tecnologías emergentes: "
           "Computación en la nube y en el borde, Gemelos Digitales "
           "y varias más.</p>")
BLOQUES = ("<p>Computación en la nube y en el borde</p>"
           "<p>La computación en la nube ofrece almacenamiento y cálculo "
           "bajo demanda a través de internet.</p>"
           "<p>Madurez: alta. Cada institución define dónde se alojan los "
           "datos.</p>"
           "<p>Gemelos Digitales</p>"
           "<p>Un gemelo digital es una réplica virtual que se actualiza "
           "con datos reales.</p>"
           "<p>Madurez: baja-media. Están más cerca de usarse que los de "
           "pacientes.</p>")
CIERRE = ("<p>Estas tecnologías se apoyan en lo que el sistema de salud ya "
          "viene incorporando.</p>")

PARES = [
    ("Maquetación: enlazar a ventana emergente 1",
     "Computación en la nube y en el borde"),
    ("Maquetación: ventana emergente 1",
     "Computación en la nube y en el borde"),
    ("Maquetación: enlazar a ventana emergente 2", "Gemelos Digitales"),
    ("Maquetación: ventana emergente 2", "Gemelos Digitales"),
]


def _armar(html=MENCION + BLOQUES + CIERRE, pares=PARES):
    soup = BeautifulSoup(html, "html.parser")
    comentarios = [_comentario(i, a) for i, a in pares]
    aplicar_comentarios(soup, comentarios)
    return soup, comentarios


class TestElClasificador:
    def test_el_globo_del_contenido(self):
        assert _clasificar("Maquetación: ventana emergente 1", "Blockchain") \
            == "ventana_emergente"

    def test_el_globo_del_disparador(self):
        assert _clasificar("Maquetación: enlazar a ventana emergente 1",
                           "Blockchain") == "enlazar_ventana_emergente"

    def test_no_se_confunde_con_el_tooltip(self):
        """"Emerger" también dispara la regla del globo chico, y esto es la
        ficha grande."""
        assert _clasificar("para maquetación: tooltip", "DUA") == "tooltip"


class TestElParSeArma:
    def test_los_dos_globos_quedan_aplicados(self):
        _, comentarios = _armar()
        assert all(c.get("_aplicado") for c in comentarios)

    def test_la_palabra_mencionada_abre_la_ventana(self):
        soup, _ = _armar()
        a = soup.find("a", class_="dp-popover-trigger")
        assert a.get_text(strip=True) == "Computación en la nube y en el borde"
        assert a["href"] == "#dpPopup0Content"
        assert a["aria-describedby"] == "dpPopup0Content"

    def test_el_disparador_queda_dentro_del_parrafo_que_lo_menciona(self):
        soup, _ = _armar()
        p = soup.find("a", class_="dp-popover-trigger").find_parent("p")
        assert "Siguieron apareciendo" in p.get_text()
        assert "y varias más" in p.get_text()

    def test_el_bloque_se_va_del_flujo(self):
        """Si no, el contenido queda dos veces en la página."""
        soup, _ = _armar()
        sueltos = [p.get_text(" ", strip=True) for p in soup.find_all("p")
                   if not p.find_parent("div", class_="dp-popover-content")]
        assert not any("réplica virtual" in t for t in sueltos)

    def test_el_bloque_emerge_entero(self):
        soup, _ = _armar()
        ficha = soup.find("div", id="dpPopup0Content")
        texto = ficha.get_text(" ", strip=True)
        assert "almacenamiento y cálculo" in texto
        assert "Madurez: alta" in texto

    def test_el_ultimo_bloque_no_se_lleva_el_texto_que_sigue(self):
        """El bloque del medio lo corta el término siguiente; el último no
        tiene quién lo corte, y se aprende del rótulo ("Madurez:")."""
        soup, _ = _armar()
        ficha = soup.find("div", id="dpPopup1Content")
        assert "Madurez: baja-media" in ficha.get_text()
        assert "sistema de salud ya viene incorporando" not in ficha.get_text()

    def test_el_parrafo_de_cierre_sigue_en_la_pagina(self):
        soup, _ = _armar()
        assert "sistema de salud ya viene incorporando" in soup.get_text()

    def test_cada_ventana_tiene_su_numero(self):
        soup, _ = _armar()
        assert [a["id"] for a in soup.find_all("a", class_="dp-popover-trigger")] \
            == ["dpPopup0", "dpPopup1"]
        assert [d["id"] for d in soup.find_all("div", class_="dp-popover-content")] \
            == ["dpPopup0Content", "dpPopup1Content"]

    def test_las_fichas_quedan_en_el_orden_del_texto(self):
        """Las dos cuelgan del mismo párrafo: la segunda va detrás de la
        primera, no delante."""
        soup, _ = _armar()
        orden = [d["id"] for d in soup.find_all("div",
                                                class_="dp-popover-content")]
        assert orden == ["dpPopup0Content", "dpPopup1Content"]


class TestCuandoElBloqueEstaEnUnaCajaDeWord:
    """En el módulo 1 cada tecnología está adentro de una tabla de Word.

    Mammoth la convierte en <table>, y la tabla "menciona" el término igual
    que el párrafo que lo introduce: el disparador se enganchaba ahí —
    adentro del propio bloque— en vez de en la mención.
    """

    CAJA = ("<p>Las principales son: Computación en la nube y en el borde, "
            "Gemelos digitales y varias más.</p>"
            "<table><tbody><tr><td>"
            "<p>Computación en la nube y en el borde</p>"
            "<p>La computación en la nube ofrece almacenamiento bajo "
            "demanda.</p>"
            "</td></tr></tbody></table>"
            "<p>Estas tecnologías se apoyan en la historia clínica "
            "electrónica.</p>")

    PARES = [("Maquetación: enlazar a ventana emergente 1",
              "Computación en la nube y en el borde"),
             ("Maquetación: ventana emergente 1",
              "Computación en la nube y en el borde")]

    def test_el_disparador_va_en_la_mencion_no_en_la_caja(self):
        soup, _ = _armar(html=self.CAJA, pares=self.PARES)
        p = soup.find("a", class_="dp-popover-trigger").find_parent("p")
        assert "Las principales son" in p.get_text()

    def test_la_caja_entera_se_va_de_la_pagina(self):
        """Sacando solo los párrafos quedaba el recuadro vacío."""
        soup, _ = _armar(html=self.CAJA, pares=self.PARES)
        assert not soup.find("table")

    def test_lo_que_emerge_son_los_parrafos_de_la_caja(self):
        soup, _ = _armar(html=self.CAJA, pares=self.PARES)
        ficha = soup.find("div", class_="dp-popover-content")
        assert "almacenamiento bajo demanda" in ficha.get_text()
        assert ficha.find("table") is None

    def test_la_definicion_no_queda_dos_veces(self):
        soup, _ = _armar(html=self.CAJA, pares=self.PARES)
        assert str(soup).count("almacenamiento bajo demanda") == 1


class TestLosCasosQueNoSeArman:
    def test_un_contenido_sin_su_disparador_queda_como_estaba(self):
        soup, comentarios = _armar(pares=[PARES[1]])
        assert not soup.find("div", class_="dp-popover-content")
        assert not comentarios[0].get("_aplicado")

    def test_un_disparador_sin_su_contenido_tampoco(self):
        soup, comentarios = _armar(pares=[PARES[0]])
        assert not soup.find("a", class_="dp-popover-trigger")
        assert not comentarios[0].get("_aplicado")

    def test_si_la_palabra_no_aparece_en_el_texto_no_se_inventa(self):
        soup, _ = _armar(html=BLOQUES + CIERRE)
        assert not soup.find("a", class_="dp-popover-trigger")


class TestElMarkupDeReferencia:
    """Contra `Snippets - ventanas emergentes.html`."""

    def test_el_popover_es_la_ficha_clara(self):
        _, content = construir_popover("palabra", "Contenido", 1)
        assert 'class="dp-popover-content dp-popup-content"' in content
        assert "background: #f7f7f7" in content
        assert "border: 1px solid #A9A9A9" in content
        assert "color: #26323d" in content
        assert "width: 600px" in content

    def test_el_contenido_en_bloques_no_se_vuelve_a_envolver(self):
        _, content = construir_popover(
            "palabra", "<p>Uno</p><p>Dos</p>", 1, envolver=False)
        assert "<p>Uno</p><p>Dos</p>" in content
        assert "<p><p>" not in content

    def test_el_tooltip_es_el_globo_gris_oscuro(self):
        """El globo chico SÍ va gris oscuro con texto blanco: es el
        componente oficial. Estuvo un día con la superficie del popover."""
        out = construir_tooltip("DUA", "Diseño Universal", 0)
        assert "background-color: #545454" in out
        assert "color: #ffffff" in out
        assert 'class="dp-tooltip-content dp-popup-content"' in out
