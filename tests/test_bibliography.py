# -*- coding: utf-8 -*-
"""Bibliografía (kl_custom_block_0 / consolidada del programa).

Ver docs/auditoria-fidelidad-gestion-calidad-2026-09-10.md
"""

from maquetador.build.bibliography import construir_bibliografia


class TestFilaSinLinkNoQuedaApelmazada:
    """Una referencia CON link tiene 3 renglones (texto, link, aire); una
    SIN link solo tenía 2 (texto, aire) — un renglón menos que sus vecinas,
    lo que la dejaba visualmente apelmazada contra la siguiente referencia.
    Pedido explícito del usuario: que las referencias sin link tengan el
    mismo aire que las que sí tienen link."""

    def test_referencia_sin_link_tiene_el_mismo_numero_de_renglones(self):
        html = ("<p>Con link. (2020). https://ejemplo.com/a</p>"
                "<p>Sin link. (1986). Un libro sin URL.</p>")
        out = construir_bibliografia(html)
        filas = out.split('<div class="row">')[1:]
        assert len(filas) == 2
        renglones_con_link, renglones_sin_link = (
            f.count('<p class="text-break"') for f in filas)
        assert renglones_con_link == renglones_sin_link == 3

    def test_no_cambia_el_contenido_de_la_referencia_con_link(self):
        html = "<p>Con link. (2020). https://ejemplo.com/a</p>"
        out = construir_bibliografia(html)
        assert 'href="https://ejemplo.com/a"' in out
