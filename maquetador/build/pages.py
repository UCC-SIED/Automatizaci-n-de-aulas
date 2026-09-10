# -*- coding: utf-8 -*-
"""Plantillas de páginas Canvas con diseño CidiLabs, parametrizadas.

Reusa las clases dp-wrapper de processors.cidilabs_builder y procesa el
contenido con los snippets oficiales UCC (maquetador.build.snippets),
sin nada hardcodeado de un módulo o curso concreto.
"""

import re
import unicodedata

from processors.cidilabs_builder import (DP_WRAPPER_CLASSES, DP_WRAPPER_ATTRS,
                                         _attrs_str)
from maquetador.build.snippets import (procesar_contenido, limpiar_anclas_vacias,
                                       sanear_lista_objetivos)
from maquetador.build.bibliography import construir_bibliografia


def slugify(titulo: str) -> str:
    """Genera el nombre de archivo wiki al estilo Canvas:
    '1.1. El problema de la corrupción' → '1-dot-1-el-problema-de-la-corrupcion'.
    """
    t = titulo.strip()
    # Numeración "N.M." → "N-dot-M"
    m = re.match(r"^(\d+)\.\s*(\d+)\.?\s*(.*)", t)
    if m:
        t = f"{m.group(1)}-dot-{m.group(2)} {m.group(3)}"
    t = unicodedata.normalize("NFKD", t)
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = re.sub(r"[^a-zA-Z0-9]+", "-", t.lower()).strip("-")
    return t[:150]


def _cabecera(titulo: str, identifier: str) -> str:
    return f"""<html>
<head>
<meta http-equiv="Content-Type" content="text/html; charset=utf-8"/>
<title>{titulo}</title>
<meta name="identifier" content="{identifier}"/>
<meta name="editing_roles" content="teachers"/>
<meta name="workflow_state" content="active"/>
</head>
<body>"""


def _banner(banner_src: str, alt: str = "") -> str:
    if not banner_src:
        return '<div id="" class="dp-banner-image"></div>'
    return (f'<div id="" class="dp-banner-image">'
            f'<img class="dp-full-width" style="height: auto;" '
            f'src="{banner_src}" alt="{alt}" loading="lazy"></div>')


def pagina_intro(titulo: str, intro_html: str, objetivos_html: str,
                 banner_src: str, identifier: str) -> str:
    """Página 'Introducción MN' del módulo."""
    return f"""{_cabecera(titulo, identifier)}
<div id="dp-wrapper" class="{DP_WRAPPER_CLASSES}" {_attrs_str(DP_WRAPPER_ATTRS)}>
<div id="dp-wrapper_1" class="undefined">
{_banner(banner_src, titulo)}
<div class="dp-content-block kl_introduction">
<p class="lead dp-progress-placeholder dp-module-progress-completion dp-padding-direction-all dp-margin-direction-all" style="display: none; padding: 10px; margin: 20px;">Module Item Completion (built in browser, hidden in app)</p>
</div>
<div class="dp-content-block kl_objectives2" style="background-color: #f8f8f8; color: #000000;">
<h2 class="dp-has-icon"><i class="fas fa-book dp-i-border-mid dp-i-size-small" aria-hidden="true"><span class="dp-icon-content" style="display: none;">&nbsp;</span></i> Introducción</h2>
{procesar_contenido(intro_html)}
<ol id="kl_objective_list"></ol>
</div>
<div class="dp-content-block kl_readings2">
<h2 class="dp-has-icon"><i class="fas fa-flag" aria-hidden="true"><span class="dp-icon-content" style="display: none;">&nbsp;</span></i> Objetivos</h2>
{sanear_lista_objetivos(limpiar_anclas_vacias(objetivos_html))}
<p>&nbsp;</p>
</div>
</div>
</div>
</body>
</html>"""


def pagina_contenido(titulo: str, body_html: str, banner_src: str,
                     identifier: str) -> str:
    """Página de contenido (1.1, 1.2, …)."""
    return f"""{_cabecera(titulo, identifier)}
<div id="dp-wrapper" class="{DP_WRAPPER_CLASSES}" {_attrs_str(DP_WRAPPER_ATTRS)}>
{_banner(banner_src, titulo)}
<div class="dp-content-block kl_introduction">
<p class="lead dp-progress-placeholder dp-module-progress-completion dp-padding-direction-all dp-margin-direction-all" style="display: none; padding: 10px; margin: 20px;">Module Item Completion (built in browser, hidden in app)</p>
</div>
<div class="dp-content-block kl_readings2" style="background-color: #ffffff; color: #000000;">
<h2 class="dp-has-icon"><i class="fa-book fas" aria-hidden="true"><span class="dp-icon-content" style="display: none;">&nbsp;</span></i></h2>
{procesar_contenido(body_html)}
<p>&nbsp;</p>
</div>
</div>
</body>
</html>"""


def pagina_bibliografia(titulo: str, body_html: str, banner_src: str,
                        identifier: str) -> str:
    """Página 'Bibliografía MN' con estructura oficial kl_custom_block_0."""
    bib_body = construir_bibliografia(body_html) or procesar_contenido(body_html)
    return f"""{_cabecera(titulo, identifier)}
<div id="dp-wrapper" class="{DP_WRAPPER_CLASSES}" {_attrs_str(DP_WRAPPER_ATTRS)}>
{_banner(banner_src, titulo)}
<div class="dp-content-block kl_introduction">
<p class="lead dp-progress-placeholder dp-module-progress-completion dp-padding-direction-all dp-margin-direction-all" style="display: none; padding: 10px; margin: 20px;">Module Item Completion (built in browser, hidden in app)</p>
</div>
<div class="dp-content-block kl_custom_block_0">
<h2 class="dp-has-icon"><i class="fas fa-bookmark dp-i-border-mid dp-i-size-small" aria-hidden="true"><span class="dp-icon-content" style="display: none;">&nbsp;</span></i></h2>
{bib_body}
</div>
</div>
</body>
</html>"""
