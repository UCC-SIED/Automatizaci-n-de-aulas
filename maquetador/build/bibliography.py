# -*- coding: utf-8 -*-
"""Constructor de la página de Bibliografía con la estructura oficial UCC.

El aula base usa el bloque kl_custom_block_0:
  <h4>Obligatoria</h4>
  <div class="dp-columns-container container-fluid">
    <div class="row">  (una por referencia)
      <div class="col-md-1 col-xs-2"> icono lectura (link si hay URL) </div>
      <div class="col-md-11 col-xs-10"> texto + URL + &nbsp; </div>
    </div>
  </div>
  <h4>Sugerida y referente</h4>
  ...

Este módulo toma el HTML crudo de la sección "referencias" del DOCX (lista
de <p>, con subtítulos del docente que varían: "Obligatoria"/"Complementaria"
/"Referente y sugerida"/"Bibliografía obligatoria"…) y lo reescribe con esa
estructura exacta.
"""

import re
import unicodedata

from bs4 import BeautifulSoup

ICONO_LECTURA = "$IMS-CC-FILEBASE$/Iconos/icono%20lectura.svg"
_PAT_URL = re.compile(r"(https?://[^\s<>\"')\]]+)")
# APA: año entre paréntesis p.ej. (2021) / (2022a,) / (2019, 15 de marzo)
_PAT_APA_YEAR = re.compile(r"\(\d{4}")


def _norm(t: str) -> str:
    t = unicodedata.normalize("NFKD", t)
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", t.lower()).strip()


def _es_header_obligatoria(t: str) -> bool:
    n = _norm(t)
    return n in ("obligatoria", "bibliografia obligatoria",
                 "bibliografia", "lecturas obligatorias")


def _es_header_sugerida(t: str) -> bool:
    n = _norm(t)
    return any(k in n for k in ("sugerida", "referente", "complementaria",
                                "ampliatoria", "opcional")) and len(n) < 45


def _fila_referencia(ref_html: str, url: str) -> str:
    """Construye un <div class="row"> con icono + texto (+ URL separada)."""
    if url:
        icono = (f'<a class="inline_disabled dp-ext-ignore" href="{url}" '
                 f'target="_blank"><img role="presentation" '
                 f'src="{ICONO_LECTURA}" alt="" loading="lazy"></a>')
        link_p = (f'<p class="text-break" style="margin: 0; padding: 0;">'
                  f'<a class="inline_disabled dp-ext-ignore" href="{url}" '
                  f'target="_blank">{url}</a></p>')
    else:
        icono = (f'<img role="presentation" src="{ICONO_LECTURA}" alt="" '
                 f'loading="lazy">')
        # Sin URL, la fila queda dos líneas más corta que sus vecinas con
        # link (texto + link + aire, contra solo texto + aire): sin este
        # renglón de aire de más en su lugar, las referencias sin link
        # quedan apelmazadas contra la siguiente.
        link_p = '<p class="text-break" style="margin: 0; padding: 0;">&nbsp;</p>'
    return f"""<div class="row">
<div class="col-md-1 col-xs-2">{icono}</div>
<div class="col-md-11 col-xs-10">
<p class="text-break" style="margin: 0; padding: 0;">{ref_html}</p>
{link_p}
<p class="text-break" style="margin: 0; padding: 0;">&nbsp;</p>
</div>
</div>"""


def _separar_url(p) -> tuple:
    """Devuelve (html_referencia_sin_url, url). La URL puede venir como <a>
    o como texto plano al final de la cita."""
    # 1) ¿hay un <a href="http...">?
    a = p.find("a", href=_PAT_URL)
    if a:
        url = a["href"].rstrip(".,;")
        contenido_link = "".join(str(x) for x in a.children).strip()
        a.extract()
        ref = "".join(str(x) for x in p.children).strip()
        if not ref and contenido_link:
            # Word aplicó el hipervínculo a la cita ENTERA (autor, título y
            # todo), no solo a la URL al final: el texto de la cita vive
            # dentro del propio <a>, que acabamos de extraer completo. Se
            # recupera de ahí, quitando la URL que queda repetida al final
            # como texto plano.
            ref = contenido_link
            m = _PAT_URL.search(ref)
            if m and m.group(1).rstrip(".,;") == url:
                ref = ref[:m.start()].strip()
        ref = re.sub(r"\s+(disponible en|recuperado de)\s*:?\s*$", "",
                     ref, flags=re.I).strip(" .,:;–-")
        return ref, url
    # 2) URL en texto plano
    texto = "".join(str(x) for x in p.children)
    m = _PAT_URL.search(texto)
    if m:
        url = m.group(1).rstrip(".,;")
        ref = texto.replace(m.group(0), "").strip()
        ref = re.sub(r"\s+(disponible en|recuperado de)\s*:?\s*$", "",
                     ref, flags=re.I).strip(" .,:;–-")
        return ref, url
    return "".join(str(x) for x in p.children).strip(), ""


def _bloque_columnas(refs: list) -> str:
    filas = "\n".join(_fila_referencia(ref, url) for ref, url in refs)
    return (f'<div class="dp-columns-container container-fluid">\n'
            f'{filas}\n</div>')


def construir_bibliografia(refs_html: str) -> str:
    """HTML crudo de referencias → cuerpo del kl_custom_block con la
    estructura oficial. Devuelve '' si no hay referencias reconocibles."""
    if not refs_html:
        return ""
    soup = BeautifulSoup(refs_html, "html.parser")
    # Solo <p>: las citas APA vienen como párrafos. Los <li> son anotaciones
    # o listas de Word que no deben interpretarse como referencias.
    parrafos = [p for p in soup.find_all("p")
                if p.get_text(strip=True)]
    if not parrafos:
        return ""

    obligatoria, sugerida = [], []
    actual = obligatoria
    hubo_header = False   # ¿el DOCX clasifica (Obligatoria/Sugerida)?
    for p in parrafos:
        texto = p.get_text(" ", strip=True)
        if _es_header_sugerida(texto):
            actual = sugerida
            hubo_header = True
            continue
        if _es_header_obligatoria(texto):
            actual = obligatoria
            hubo_header = True
            continue
        # Línea suelta que es solo una URL (continuación de la cita anterior)
        if _PAT_URL.fullmatch(texto) and actual and not actual[-1][1]:
            ref, _ = actual[-1]
            actual[-1] = (ref, texto.rstrip(".,;"))
            continue
        # Filtro mínimo: debe tener año APA (2021) o URL para ser referencia.
        # Párrafos descriptivos/anotaciones no tienen ninguno de los dos.
        if not _PAT_APA_YEAR.search(texto) and not _PAT_URL.search(texto):
            continue
        ref, url = _separar_url(p)
        if ref or url:
            actual.append((ref, url))

    if not obligatoria and not sugerida:
        return ""

    # Si el DOCX no clasifica (no trae headers), no inventar "Obligatoria":
    # se listan las referencias directas (como hace el equipo a mano).
    if not hubo_header:
        return _bloque_columnas(obligatoria)

    partes = []
    if obligatoria:
        partes.append('<h4 style="text-align: left;">Obligatoria</h4>')
        partes.append(_bloque_columnas(obligatoria))
    if sugerida:
        partes.append('<h4 style="text-align: left;">Sugerida y referente</h4>')
        partes.append(_bloque_columnas(sugerida))
    return "\n".join(partes)
