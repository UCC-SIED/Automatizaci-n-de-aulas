# -*- coding: utf-8 -*-
"""Un foro sin DOCX propio, cuya consigna el asesor escribió adentro de la
lectura de otra página (comentario "... directamente en siguiente pág", ver
docx_comments._clasificar): el generador tiene que sacar esa consigna de la
página, cargarla en el foro del aula base Y ubicar el <item> de ese foro
justo después del <item> de la página de la que se sacó — no dejarlo donde
el aula base lo trae por defecto (al final del módulo)."""

from maquetador.build.imscc_builder import GeneradorAula


def _generador_con_manifest(manifest: str):
    g = GeneradorAula.__new__(GeneradorAula)
    g.manifest = manifest
    return g


MANIFEST_BASE = (
    '<manifest><organizations><organization identifier="org_1">'
    '<item identifier="mod1"><title>Módulo 1</title>'
    '<item identifier="i1" identifierref="r1"><title>1.1. Uno</title></item>'
    '<item identifier="i2" identifierref="r2"><title>1.2. Dos</title></item>'
    '<item identifier="i3" identifierref="r3"><title>1.3. Tres</title></item>'
    '<item identifier="ifo" identifierref="rforo">\n'
    '            <title>Foro obligatorio M1</title>\n'
    '          </item>'
    '<item identifier="i4" identifierref="r4"><title>1.4. Cuatro</title></item>'
    '</item></organization></organizations></manifest>')


class TestReordenarItemDespuesDePagina:
    def test_mueve_el_foro_justo_despues_de_la_pagina_indicada(self):
        g = _generador_con_manifest(MANIFEST_BASE)
        g._reordenar_item_despues_de_pagina("rforo", "1.3. Tres")
        orden = [t for t in ("1.1. Uno", "1.2. Dos", "1.3. Tres",
                             "Foro obligatorio M1", "1.4. Cuatro")]
        posiciones = [g.manifest.index(t) for t in orden]
        assert posiciones == sorted(posiciones)

    def test_no_duplica_ni_pierde_items(self):
        g = _generador_con_manifest(MANIFEST_BASE)
        g._reordenar_item_despues_de_pagina("rforo", "1.3. Tres")
        for t in ("1.1. Uno", "1.2. Dos", "1.3. Tres",
                 "Foro obligatorio M1", "1.4. Cuatro"):
            assert g.manifest.count(t) == 1

    def test_sin_rid_no_hace_nada(self):
        g = _generador_con_manifest(MANIFEST_BASE)
        g._reordenar_item_despues_de_pagina("", "1.3. Tres")
        assert g.manifest == MANIFEST_BASE

    def test_pagina_inexistente_no_rompe_nada(self):
        """Si no se encuentra la página (título no coincide), el ítem queda
        donde ya estaba en vez de arriesgar un manifiesto roto."""
        g = _generador_con_manifest(MANIFEST_BASE)
        g._reordenar_item_despues_de_pagina("rforo", "1.9. No existe")
        assert g.manifest == MANIFEST_BASE
