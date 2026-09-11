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


class TestSubtituloDeVerdad:
    def test_sin_dos_puntos_antes_sigue_siendo_h3(self):
        html = ("<p>Un párrafo cualquiera de contenido que cierra normal.</p>"
                "<p><strong>Costos de la calidad</strong></p>")
        assert "<h3>Costos de la calidad</h3>" in procesar_contenido(html)

    def test_el_primer_parrafo_de_la_pagina_sigue_siendo_h3(self):
        html = "<p><strong>Costos de la calidad</strong></p><p>Texto.</p>"
        assert "<h3>Costos de la calidad</h3>" in procesar_contenido(html)
