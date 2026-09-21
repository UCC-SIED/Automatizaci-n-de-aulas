# -*- coding: utf-8 -*-
"""Comentarios que no son pedidos de maquetación.

Los DOCX llegan con globos del proceso editorial que ya no corresponden al
pasar a maquetación. Dos grupos grandes repiten algo que YA está escrito en el
cuerpo —el pie de fuente de la figura y el texto alternativo—, que el
generador toma del párrafo, no del globo. Y "Para diseño: …" es un encargo
para el diseñador.

Sobre el curso de prueba esto baja el cajón de "revisar" de 12 a 1.

Ver docs/auditoria-fidelidad-gestion-calidad-2026-09-10.md
"""

import pytest

from maquetador.ingest.docx_comments import _clasificar


class TestComentariosMuertos:
    @pytest.mark.parametrize("texto", [
        "Para maquetación: Nota. Figura elaborada con base en Out of the crisis, "
        "por W. E. Deming, 2000, Penguin.",
        "Nota. Figura elaborada con base en Sistemas de gestión de la calidad.",
        "Para maquetación: Texto alternativo: Diagrama de Ishikawa.",
        "Texto alternativo: Gráfico de barras sobre la frecuencia de reclamos.",
    ])
    def test_los_que_duplican_el_cuerpo_no_son_pedidos(self, texto):
        assert _clasificar(texto) is None

    def test_el_encargo_de_diseno_no_es_de_maquetacion(self):
        assert _clasificar(
            "Para diseño: M1 RI1 --> Genially Pantalla principal con 7 botones") is None


class TestNoSeLlevaPuestoLoQueSiImporta:
    def test_una_instruccion_real_sigue_avisandose(self):
        """El foro 'directamente en siguiente pág' ya no cae en el cajón
        genérico de revisar a mano: se reconoce como su propio pedido
        (sacar el contenido de esta página, ver TestOtraPagina) y de
        cualquier forma sigue sin perderse como si fuera ruido editorial."""
        assert _clasificar("Para maquetación: foro directamente en siguiente pág") \
            == "otra_pagina"
        assert _clasificar("Para maquetación: revisar este párrafo") == "revisar"

    @pytest.mark.parametrize("texto,esperado", [
        ("Para maquetación: subtítulo", "subtitulo"),
        ("Para maquetación: sub-subtítulo", "subsubtitulo"),
        ("Para maquetación: acordeón", "acordeon"),
        ("Para maquetación: TABS vertical", "tabs_vertical"),
        ("Para maquetación: flipcards", "flip_card"),
        ("Para maquetación: tooltip --> Sistema de Gestión", "tooltip"),
    ])
    def test_los_pedidos_de_verdad_no_se_filtran(self, texto, esperado):
        assert _clasificar(texto) == esperado

    def test_no_confunde_una_nota_al_pie_con_notar_algo(self):
        """'notar' no es 'Nota.' — el filtro pide el punto o los dos puntos."""
        assert _clasificar("Para maquetación: notar que va en recuadro") \
            == "recuadro_simple"


class TestOtraPagina:
    """El asesor deja el texto de un componente (el foro) en el DOCX de este
    módulo pero aclara que va en OTRA página: no hay que maquetarlo acá.
    Caso real: 'foro directamente en siguiente pág', anclado sobre una tabla
    de 1 columna cuya primera celda dice apenas 'Foro' — el resto de la
    tabla es la consigna completa del foro."""

    def test_se_reconoce_la_instruccion(self):
        from maquetador.ingest.docx_comments import _clasificar
        assert _clasificar("Para maquetación: foro directamente en "
                            "siguiente pág") == "otra_pagina"
        assert _clasificar("Para maquetación: va en la próxima página") \
            == "otra_pagina"

    def test_se_saca_la_tabla_entera_no_solo_la_celda_del_titulo(self):
        from bs4 import BeautifulSoup
        from maquetador.ingest.docx_comments import aplicar_comentarios
        soup = BeautifulSoup(
            "<div><p>Texto de la página.</p>"
            "<table><tr><th><p><strong>Foro</strong></p></th></tr>"
            "<tr><th><p>Reflexioná sobre el rol de la calidad en tu "
            "ámbito.</p></th></tr></table>"
            "<p>Sigue el resto de la página.</p></div>", "html.parser")
        coment = [{"instruccion": "Para maquetación: foro directamente en "
                                  "siguiente pág",
                   "anclado": "Foro", "accion": "otra_pagina", "autor": ""}]
        aplicar_comentarios(soup, coment)
        out = str(soup)
        assert "<table>" not in out
        assert "Reflexioná sobre el rol" not in out
        assert "Sigue el resto de la página" in out
        assert coment[0].get("_aplicado") is True


class TestEnlaceDescargable:
    """El asesor a veces deja el link real de un documento en el comentario
    mismo (sin más texto que la URL y 'debe ser descargable'): el texto
    anclado en el cuerpo pasa a ser el link a ese documento. Caso real: el
    "protocolo de transparencia" de una actividad obligatoria, anclado sobre
    esas palabras dentro del párrafo, con la URL de Google Drive en el
    comentario."""

    def test_se_reconoce_la_instruccion(self):
        from maquetador.ingest.docx_comments import _clasificar
        assert _clasificar(
            "https://docs.google.com/spreadsheets/d/abc123/edit "
            "debe ser descargable") == "enlace_descargable"

    def test_el_texto_anclado_se_vuelve_link(self):
        from bs4 import BeautifulSoup
        from maquetador.ingest.docx_comments import aplicar_comentarios
        soup = BeautifulSoup(
            "<div><p>En el caso de utilizar IA, deberá adjuntar el "
            "protocolo de transparencia completo.</p></div>", "html.parser")
        coment = [{
            "instruccion": "https://docs.google.com/spreadsheets/d/abc123/"
                          "edit debe ser descargable",
            "anclado": "protocolo de transparencia",
            "accion": "enlace_descargable", "autor": "",
        }]
        aplicar_comentarios(soup, coment)
        out = str(soup)
        a = soup.find("a")
        assert a is not None
        assert a["href"] == "https://docs.google.com/spreadsheets/d/abc123/edit"
        assert a.get_text(strip=True) == "protocolo de transparencia"
        assert "deberá adjuntar el" in out
        assert "completo." in out
        assert coment[0].get("_aplicado") is True


class TestGeniallyConRespuestaDelDisenador:
    """"Para diseño: … Genially …" no es un pedido de maquetación (se
    excluye en _clasificar), pero si el diseñador YA respondió el comentario
    con el div/iframe armado (word/commentsExtended.xml liga la respuesta al
    comentario original por w14:paraId, ver _respuestas_por_cid), ese embed
    real reemplaza el brief completo —desde el ancla hasta donde el propio
    comentario marca el final— en vez de quedar publicado como texto."""

    def test_liga_la_respuesta_por_paraid(self):
        from maquetador.ingest.docx_comments import _respuestas_por_cid
        import xml.etree.ElementTree as ET
        W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
        W14 = "{http://schemas.microsoft.com/office/word/2010/wordml}"
        W15 = "{http://schemas.microsoft.com/office/word/2012/wordml}"
        comments_xml = f"""<w:comments xmlns:w="{W[1:-1]}" xmlns:w14="{W14[1:-1]}">
<w:comment w:id="1" w:author="Julieta">
<w:p w14:paraId="AAA"><w:r><w:t>Para diseño: Genially</w:t></w:r></w:p>
</w:comment>
<w:comment w:id="2" w:author="Lucas">
<w:p w14:paraId="BBB"><w:r><w:t>&lt;iframe src="https://view.genially.com/xyz"&gt;&lt;/iframe&gt;</w:t></w:r></w:p>
</w:comment>
</w:comments>"""
        ext_xml = f"""<w15:commentsEx xmlns:w15="{W15[1:-1]}">
<w15:commentEx w15:paraId="BBB" w15:paraIdParent="AAA"/>
</w15:commentsEx>"""
        croot = ET.fromstring(comments_xml)
        respuestas = _respuestas_por_cid(croot, ext_xml.encode("utf-8"))
        assert "1" in respuestas
        assert "view.genially.com" in respuestas["1"][0]

    def test_reemplaza_el_brief_por_el_embed_real(self):
        from bs4 import BeautifulSoup
        from maquetador.ingest.docx_comments import aplicar_comentarios
        soup = BeautifulSoup(
            "<div><p>Texto previo de la página.</p>"
            "<p>a) Implementación de una línea de envasado.</p>"
            "<p>Descripción general del proyecto: una empresa decide "
            "ejecutar un proyecto de envasado automatizado.</p>"
            "<p>b) Alcance del proyecto: fin del brief.</p>"
            "<h3>Siguiente sección</h3></div>", "html.parser")
        coment = [{
            "instruccion": "Para diseño: M1 RI1 --> Genially Pantalla "
                          "principal con 7 botones con popup",
            "anclado": "a) Implementación de una línea de envasado. "
                      "Descripción general del proyecto: una empresa "
                      "decide ejecutar un proyecto de envasado "
                      "automatizado. b) Alcance del proyecto: fin del "
                      "brief.",
            "accion": "genially_listo", "autor": "",
            "_html_genially": '<iframe src="https://view.genially.com/xyz">'
                              '</iframe>',
        }]
        aplicar_comentarios(soup, coment)
        out = str(soup)
        assert "Implementación de una línea de envasado" not in out
        assert "fin del brief" not in out
        assert "https://view.genially.com/xyz" in out
        assert "dp-embed-wrapper" in out
        assert "Texto previo de la página" in out
        assert "<h3>Siguiente sección</h3>" in out
        assert coment[0].get("_aplicado") is True
