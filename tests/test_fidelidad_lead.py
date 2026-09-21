# -*- coding: utf-8 -*-
"""Frase destacada ("lead") vs subtítulo.

Una frase corta y en negrita se convertía en <h3>. Pero si el párrafo anterior
termina en ":", esa frase es lo que ese párrafo estaba introduciendo —
contenido destacado, no un título de sección. En el aula corregida a mano
queda como <p class="lead dp-text-bold"> en negrita.

Caso real: "Esta evolución puede resumirse como un desplazamiento progresivo:"
seguido de "detectar defectos → controlar procesos → asegurar consistencia →
generar valor".

Ver docs/auditoria-fidelidad-gestion-calidad-2026-09-10.md
"""

from maquetador.build.snippets import procesar_contenido

FLECHAS = ("detectar defectos → controlar procesos → asegurar consistencia "
           "→ generar valor")
INTRODUCIDA = (f"<p>Esta evolución puede resumirse como un desplazamiento "
               f"progresivo:</p><p><strong>{FLECHAS}</strong></p>")


class TestFraseDestacada:
    def test_no_se_convierte_en_encabezado(self):
        assert "<h3>detectar" not in procesar_contenido(INTRODUCIDA)

    def test_queda_como_parrafo_con_estilo_lead(self):
        out = procesar_contenido(INTRODUCIDA)
        assert "lead" in out and "dp-text-bold" in out

    def test_sigue_en_negrita(self):
        assert "<strong>" in procesar_contenido(INTRODUCIDA)

    def test_conserva_el_texto(self):
        assert FLECHAS in procesar_contenido(INTRODUCIDA)


class TestEspaciadoDeLaFraseDestacada:
    """Fuera de un panel, la frase destacada corta la lectura como una cita:
    aire corto (shift+enter) arriba Y abajo, igual que un recuadro simple —
    no el aire completo que sí lleva una bajada de panel (esa va pegada a su
    propia explicación, ver TestPreguntaSubtituloDentroDeUnPanel en
    test_fidelidad_pagina_12.py). Confirmado en Canvas."""

    def test_lleva_aire_corto_arriba_y_abajo(self):
        html = (INTRODUCIDA
               + "<p>Este cambio resulta especialmente relevante.</p>")
        out = procesar_contenido(html)
        assert f"<p><br/></p><p class=\"lead dp-text-bold\"><strong>{FLECHAS}</strong></p><p><br/></p>" in out

    def test_una_bajada_dentro_de_un_panel_no_se_ve_afectada(self):
        """El mismo estilo "lead dp-text-bold", pero dentro de un panel,
        sigue sin aire abajo — la distinción es estructural (adentro o
        afuera de dp-panel-content), no por el texto."""
        html = ('<div class="dp-panels-wrapper dp-expander-default">'
                '<div class="dp-panel-group">'
                '<h3 class="dp-panel-heading">Título</h3>'
                '<div class="dp-panel-content">'
                '<p class="lead dp-text-bold">Una etiqueta</p>'
                '<p>Su propia explicación.</p>'
                '</div></div></div>')
        out = procesar_contenido(html)
        assert 'Una etiqueta</p><p>Su propia explicación.' in out


class TestSubtituloDeVerdad:
    def test_sin_dos_puntos_antes_sigue_siendo_h3(self):
        html = ("<p>Un párrafo cualquiera de contenido que cierra normal.</p>"
                "<p><strong>Costos de la calidad</strong></p>")
        assert "<h3>Costos de la calidad</h3>" in procesar_contenido(html)

    def test_el_primer_parrafo_de_la_pagina_sigue_siendo_h3(self):
        html = "<p><strong>Costos de la calidad</strong></p><p>Texto.</p>"
        assert "<h3>Costos de la calidad</h3>" in procesar_contenido(html)
