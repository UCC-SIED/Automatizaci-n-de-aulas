"""
Procesador de contenido CidiLabs para Canvas LMS.
Transforma HTML plano en bloques CidiLabs con el estilo exacto de las aulas UCC.
Basado en el HTML real del ejemplo ya maquetado.
"""

import re
from bs4 import BeautifulSoup, Tag


# Clases CSS del wrapper CidiLabs: tema de encabezados vigente de la UCC.
#
# Se extrajo de las páginas de referencia del curso Canvas 399 (los HTML de
# "Pautas de Estructura…", "Estilos para Llamados a la Acción…", "Estándares
# para Recursos Visuales…" y "Modelo de actividad"): las cuatro traen este
# mismo string, en este mismo orden.
#
# Ojo si se vuelve a copiar de una página exportada: el editor DesignPLUS deja
# dos artefactos que acá se omiten a propósito —un `&nbsp;` pegado a
# `dp-hdg-b-h6-pill-r` (rompe ese token, porque el navegador solo separa clases
# por espacios ASCII) y `custom-paragraph-padding` repetido.
DP_WRAPPER_CLASSES = (
    "dp-wrapper dp-hdg-i-bg-h2-dp-primary dp-hdg-i-align-h2-tc "
    "dp-hdg-i-cp-brdr-h2-dp-white dp-hdg-b-h3-brdr-b dp-hdg-d-h2-c "
    "dp-hdg-b-h4-brdr-b dp-hdg-brdr-h4-2 dp-hdg-brdr-h5-1 "
    "dp-hdg-i-sz-h2-out dp-hdg-i-brdr-h2-2 dp-hdg-brdr-h2-1 dp-hdg-brdr-h3-2 "
    "dp-hdg-txt-h4-dp-gray dp-hdg-d-h5-table-l "
    "dp-hdg-brdr-h6-1 dp-hdg-d-h6-table-l dp-hdg-cp-brdr-h6-dp-gray "
    "dp-hdg-i-styl-h2-pill dp-hdg-txt-h2-dp-primary dp-hdg-b-h2-brdr-t "
    "dp-hdg-b-h4-bold dp-hdg-b-h3-bold dp-hdg-d-h4-table-l "
    "dp-hdg-b-h5-pill-r custom-paragraph-padding dp-hdg-txt-h6-dp-primary "
    "dp-hdg-bg-h5-dp-gray dp-hdg-txt-h5-dp-primary dp-hdg-bg-h6-dp-white "
    "dp-hdg-b-h6-pill-r"
)

DP_WRAPPER_ATTRS = {
    "data-header-class": "dp-header dp-flat-sections",
    "data-nav-class": "container-fluid dp-link-grid dp-flat-sections dp-fs-1",
    "data-img-url": "https://designtools.ciditools.com/css/images/banner_desert_sky.png",
}


def build_intro_page(intro_html: str, objetivos_html: str, banner_src: str = "",
                     identifier: str = "") -> str:
    """
    Construye la página de Introducción del módulo con estructura CidiLabs.
    Replica exactamente la estructura del ejemplo maquetado.
    """
    banner_img = ""
    if banner_src:
        banner_img = (
            f'<img class="dp-full-width" style="height: auto;" '
            f'src="{banner_src}" alt="Introducción" loading="lazy">'
        )
    
    return f"""<html>
<head>
<meta http-equiv="Content-Type" content="text/html; charset=utf-8"/>
<title>Introducción M1</title>
<meta name="identifier" content="{identifier}"/>
<meta name="editing_roles" content="teachers"/>
<meta name="workflow_state" content="active"/>
</head>
<body>
<div id="dp-wrapper" class="{DP_WRAPPER_CLASSES}" {_attrs_str(DP_WRAPPER_ATTRS)}>
<div id="dp-wrapper_1" class="undefined">
<div id="" class="dp-banner-image">{banner_img}</div>
<div class="dp-content-block kl_introduction">
<p class="lead dp-progress-placeholder dp-module-progress-completion dp-padding-direction-all dp-margin-direction-all" style="display: none; padding: 10px; margin: 20px;">Module Item Completion (built in browser, hidden in app)</p>
</div>
<div class="dp-content-block kl_objectives2" style="background-color: #f8f8f8; color: #000000;">
<h2 class="dp-has-icon"><i class="fas fa-book dp-i-border-mid dp-i-size-small" aria-hidden="true"><span class="dp-icon-content" style="display: none;">&nbsp;</span></i> Introducción</h2>
{intro_html}
<ol id="kl_objective_list"></ol>
</div>
<div class="dp-content-block kl_readings2">
<h2 class="dp-has-icon"><i class="fas fa-flag" aria-hidden="true"><span class="dp-icon-content" style="display: none;">&nbsp;</span></i> Objetivos</h2>
{objetivos_html}
<p>&nbsp;</p>
</div>
</div>
</div>
</body>
</html>"""


def build_content_page(body_html: str, title: str = "", banner_src: str = "",
                       identifier: str = "") -> str:
    """
    Construye una página de contenido (1.1, 1.2, etc.) con estructura CidiLabs.
    Transforma los bloques de reflexión en callouts amarillos.
    """
    # Procesar callouts de reflexión y bloques especiales
    processed_html = _process_content_blocks(body_html)
    
    banner_img = ""
    if banner_src:
        banner_img = (
            f'<img class="dp-full-width" style="height: auto;" '
            f'src="{banner_src}" alt="{title}" loading="lazy">'
        )
    
    return f"""<html>
<head>
<meta http-equiv="Content-Type" content="text/html; charset=utf-8"/>
<title>{title}</title>
<meta name="identifier" content="{identifier}"/>
<meta name="editing_roles" content="teachers"/>
<meta name="workflow_state" content="active"/>
</head>
<body>
<div id="dp-wrapper" class="{DP_WRAPPER_CLASSES}" {_attrs_str(DP_WRAPPER_ATTRS)}>
<div id="" class="dp-banner-image">{banner_img}</div>
<div class="dp-content-block kl_introduction">
<p class="lead dp-progress-placeholder dp-module-progress-completion dp-padding-direction-all dp-margin-direction-all" style="display: none; padding: 10px; margin: 20px;">Module Item Completion (built in browser, hidden in app)</p>
</div>
<div class="dp-content-block kl_readings2" style="background-color: #ffffff; color: #000000;">
<h2 class="dp-has-icon"><i class="fa-book fas" aria-hidden="true"><span class="dp-icon-content" style="display: none;">&nbsp;</span></i></h2>
{processed_html}
</div>
</div>
</body>
</html>"""


def _process_content_blocks(html: str) -> str:
    """
    Transforma bloques especiales del contenido:
    - Tablas con "Reflexiona" / "Para reflexionar" -> callout amarillo CidiLabs
    - Tablas con "Te invito a leer" -> callout de lectura
    - Figuras con <img> + nota -> bloque centrado con estilo
    """
    soup = BeautifulSoup(html, "html.parser")
    
    # 1. Transformar tablas de reflexión en callouts
    for table in soup.find_all("table"):
        text = table.get_text().strip()
        
        if _is_reflection_block(text):
            callout = _build_callout(soup, table, "reflexion")
            if callout:
                table.replace_with(callout)
        elif _is_reading_block(text):
            callout = _build_callout(soup, table, "lectura")
            if callout:
                table.replace_with(callout)
    
    # 2. Estilizar imágenes de figuras
    for img in soup.find_all("img"):
        img["class"] = img.get("class", [])
        if "dp-popup-image" not in img.get("class", []):
            img["class"] = "dp-popup-image dp-image-rounded-10 dp-image-padded dp-image-bordered dp-image-shadow"
            img["style"] = "width: 700px; height: auto;"
            # Centrar el padre
            parent = img.parent
            if parent and parent.name == "p":
                parent["style"] = "text-align: center;"
    
    # 3. Estilizar captions de figuras (párrafos con "Figura N." o "Nota.")
    for p in soup.find_all("p"):
        text = p.get_text().strip()
        if re.match(r'^(Figura \d+\.)', text):
            p["class"] = "dp-heading-ignore"
            p["style"] = "text-align: center;"
            # Envolver en <strong><span style="font-size: 10pt;">
            inner = f'<span style="font-size: 10pt;"><strong>{text}</strong></span>'
            p.clear()
            p.append(BeautifulSoup(inner, "html.parser"))
        elif text.startswith("Nota."):
            p["class"] = "dp-heading-ignore"
            p["style"] = "text-align: center;"
            inner = f'<strong><span style="font-size: 10pt;">{text}</span></strong>'
            p.clear()
            p.append(BeautifulSoup(inner, "html.parser"))
    
    return str(soup)


def _is_reflection_block(text: str) -> bool:
    lower = text.lower()
    return any(kw in lower for kw in ["reflexion", "reflexión", "para reflexionar"])


def _is_reading_block(text: str) -> bool:
    lower = text.lower()
    return any(kw in lower for kw in ["te invito a leer", "lectura recomendada"])


def _build_callout(soup, table, callout_type: str):
    """Construye un callout CidiLabs a partir de una tabla."""
    text = table.get_text().strip()
    
    if callout_type == "reflexion":
        # Separar título del cuerpo
        lines = text.split("\n")
        title_text = "Para reflexionar"
        body_lines = []
        found_title = False
        for line in lines:
            line = line.strip()
            if not line:
                continue
            if not found_title and any(kw in line.lower() for kw in ["reflexion", "reflexión", "para reflexionar"]):
                # El título puede ser "Reflexiona" o "Para reflexionar"  
                title_text = line if len(line) < 30 else "Para reflexionar"
                found_title = True
                # Si hay más texto en la misma línea después del título
                remaining = line
                for kw in ["Reflexiona", "Reflexión", "Para reflexionar"]:
                    remaining = remaining.replace(kw, "").strip()
                if remaining:
                    body_lines.append(remaining)
            else:
                body_lines.append(line)
        
        body_text = " ".join(body_lines).strip()
        
        callout_html = f"""<div class="dp-callout dp-callout-placeholder card dp-callout-position-default dp-callout-type-info dp-callout-color-warning">
<div class="dp-callout-side-emphasis" style="background-color: #f4e600; color: #000000;"><i class="dp-icon fas fa-lightbulb dp-default-icon">\u200b</i></div>
<div class="card-body">
<h3 class="card-title" style="color: #757121;">{title_text}</h3>
<p>{body_text}</p>
</div>
</div>"""
        return BeautifulSoup(callout_html, "html.parser")
    
    elif callout_type == "lectura":
        lines = text.split("\n")
        body_lines = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            if "te invito a leer" in line.lower():
                continue
            body_lines.append(line)
        
        body_text = " ".join(body_lines).strip()
        
        callout_html = f"""<div class="dp-callout dp-callout-placeholder card dp-callout-position-default dp-callout-type-info dp-callout-color-info">
<div class="dp-callout-side-emphasis" style="background-color: #0770A3; color: #ffffff;"><i class="dp-icon fas fa-book-open dp-default-icon">\u200b</i></div>
<div class="card-body">
<h3 class="card-title" style="color: #0770A3;">Te invito a leer</h3>
<p>{body_text}</p>
</div>
</div>"""
        return BeautifulSoup(callout_html, "html.parser")
    
    return None


def _attrs_str(attrs: dict) -> str:
    """Convierte un dict de atributos a string HTML."""
    return " ".join(f'{k}="{v}"' for k, v in attrs.items())
