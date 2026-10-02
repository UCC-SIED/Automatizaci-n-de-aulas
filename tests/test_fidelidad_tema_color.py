# -*- coding: utf-8 -*-
"""Acento institucional según el aula base.

Educación usa #003087 y posgrado #1b1e31. El generador tenía el de posgrado
hardcodeado en ACCENT, así que TODO curso de educación salía con los CTA y
recuadros del color equivocado.

Ver docs/auditoria-fidelidad-gestion-calidad-2026-09-10.md
"""

import pytest

from maquetador.build.snippets import (ACENTO_POR_TEMA, aplicar_acento_del_tema,
                                       cta_titulo, resaltado_simple)
from maquetador.build.pages import pagina_contenido

EDU, POS = "#003087", "#1b1e31"
TABLA_VIDEO = ("<table><tr><td>Video</td></tr>"
               "<tr><td>Mirá este video conceptual.</td></tr></table>")


class TestAcentoPorTema:
    def test_los_dos_colores_institucionales(self):
        assert ACENTO_POR_TEMA["educacion"] == EDU
        assert ACENTO_POR_TEMA["posgrado"] == POS

    @pytest.mark.parametrize("tema,esperado,otro", [
        ("educacion", EDU, POS),
        ("Educación", EDU, POS),
        ("posgrado", POS, EDU),
    ])
    def test_repinta_los_snippets(self, tema, esperado, otro):
        html = aplicar_acento_del_tema(cta_titulo("Video", "<p>x</p>"), tema)
        assert esperado in html
        assert otro not in html

    def test_sin_tema_queda_el_de_posgrado(self):
        html = aplicar_acento_del_tema(resaltado_simple("<p>x</p>"), "")
        assert POS in html

    def test_solo_toca_atributos_style(self):
        """El color no puede reemplazarse dentro del texto del asesor."""
        html = f'<p>El código de color {POS} es institucional.</p>'
        assert aplicar_acento_del_tema(html, "educacion") == html


class TestLlegaALaPagina:
    def test_educacion_usa_su_color(self):
        html = pagina_contenido("1.1 X", TABLA_VIDEO, "b.png", "id",
                                tema="educacion")
        assert EDU in html and POS not in html

    def test_posgrado_usa_el_suyo(self):
        html = pagina_contenido("1.1 X", TABLA_VIDEO, "b.png", "id",
                                tema="posgrado")
        assert POS in html and EDU not in html
