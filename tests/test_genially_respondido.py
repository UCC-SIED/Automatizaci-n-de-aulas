# -*- coding: utf-8 -*-
"""El Genially ya entregado manda sobre lo que diga el brief del asesor.

Regresión real (Selección y Optimización de Inversiones): el globo decía
"Diseño: imagen interactiva con los pasos… En el medio, antes del H hay un
recuadro para reflexión", el diseñador respondió con el iframe ya armado y el
asesor lo aprobó ("¡Me encanta!"). Como la palabra "recuadro" del brief hacía
que el comentario se clasificara como recuadro_simple, la rama que usa la
respuesta del diseñador no se ejecutaba: el Genially entregado no se publicaba
nunca y la página salía con el pedido al diseñador como si fuera contenido.
"""

import zipfile
from xml.sax.saxutils import escape

from maquetador.ingest.docx_comments import extraer_comentarios

_NS = ('xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
       'xmlns:w14="http://schemas.microsoft.com/office/word/2010/wordml" '
       'xmlns:w15="http://schemas.microsoft.com/office/word/2012/wordml"')

IFRAME = ('<div style="width: 100%;"><iframe title="Etapas del proceso" '
          'src="https://view.genially.com/68f0aaaa1111cccc22223333" '
          'width="100%" height="675"></iframe></div>')


def _docx(tmp_path, brief, respuestas, nombre="m1.docx"):
    """DOCX mínimo con un comentario anclado y sus respuestas."""
    comentarios = [(0, brief, "w14p000")]
    comentarios += [(i + 1, texto, f"w14p{i + 1:03d}")
                    for i, texto in enumerate(respuestas)]
    cuerpo_comments = "".join(
        f'<w:comment w:id="{cid}" w:author="Asesoría">'
        f'<w:p w14:paraId="{pid}"><w:r><w:t>{escape(texto)}</w:t></w:r></w:p>'
        f'</w:comment>' for cid, texto, pid in comentarios)
    extendido = "".join(
        f'<w15:commentEx w15:paraId="{pid}" w15:paraIdParent="w14p000"/>'
        for _cid, _t, pid in comentarios[1:])
    documento = (
        f'<w:document {_NS}><w:body>'
        '<w:p><w:commentRangeStart w:id="0"/><w:r><w:t>Etapas del proceso de '
        'selección de inversiones: A, B, C … H.</w:t></w:r>'
        '<w:commentRangeEnd w:id="0"/></w:p>'
        '</w:body></w:document>')
    path = tmp_path / nombre
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("word/document.xml", documento)
        z.writestr("word/comments.xml",
                   f'<w:comments {_NS}>{cuerpo_comments}</w:comments>')
        z.writestr("word/commentsExtended.xml",
                   f'<w15:commentsEx {_NS}>{extendido}</w15:commentsEx>')
    return path


BRIEF = ("Diseño: imagen interactiva con los pasos. La idea sería que estén "
         "todos los pasos que tienen las letras A,B,C ....H) y al hacer clic "
         "toda la información que está debajo. En el medio, antes del H hay "
         "un recuadro para reflexión.")


class TestLaRespuestaDelDisenadorManda:
    def test_el_brief_con_la_palabra_recuadro_no_tapa_el_genially(self, tmp_path):
        cs = extraer_comentarios(_docx(tmp_path, BRIEF,
                                       [IFRAME, "¡Me encanta! Gracias."]))
        assert [c["accion"] for c in cs] == ["genially_listo"]
        assert "genially.com" in cs[0]["_html_genially"]

    def test_sin_respuesta_util_sigue_valiendo_lo_que_dice_el_globo(self, tmp_path):
        cs = extraer_comentarios(_docx(tmp_path, BRIEF, ["¡Me encanta!"]))
        assert [c["accion"] for c in cs] == ["recuadro_simple"]

    def test_un_brief_sin_accion_propia_tambien_usa_la_respuesta(self, tmp_path):
        cs = extraer_comentarios(_docx(
            tmp_path, "Diseño: imagen interactiva con el título Factores",
            [IFRAME]))
        assert [c["accion"] for c in cs] == ["genially_listo"]
