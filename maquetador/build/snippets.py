# -*- coding: utf-8 -*-
"""Procesador de contenido con los snippets oficiales CidiLabs de la UCC.

Los bloques se replican EXACTAMENTE como en el aula de snippets
(cidiplus-export) y las aulas maquetadas a mano:

  - CTA con barra de título (Lectura, Video, Podcast, Imagen…):
    dp-callout-color-lg-tip + dp-callout-type-title-bar, borde #1b1e31,
    icono SVG de web_resources/Iconos/.
  - Resaltado Profundización (Reflexiona / Para pensar / Para saber más):
    dp-callout-color-warning + ícono lámpara sobre #f4e600, título #757121.
  - Resaltado Atención/Importante: dp-callout-color-danger + triángulo.
  - Resaltado simple (sin título): borde #1b1e31, solo card-body.

Detección sobre el HTML del DOCX: las tablas de UNA columna son recuadros
(la primera fila es la etiqueta del tipo); las tablas multicolumna son
tablas de datos reales y se conservan.

Además convierte los subtítulos en negrita en <h3> (como hace el equipo a
mano: el dp-wrapper los estiliza) y estiliza figuras y sus epígrafes.
"""

import re
import unicodedata

from bs4 import BeautifulSoup, NavigableString
from maquetador.build.componentes_asesor import (construir_flipcards,
                                                   construir_panels, aplicar_cita)

# Acento institucional por aula base. Los snippets se arman con el de posgrado
# y al final se repintan según el tema del curso (ver aplicar_acento_del_tema):
# hasta ahora TODO curso salía con el color de posgrado, también los de
# educación.
ACENTO_POR_TEMA = {"educacion": "#003087", "posgrado": "#1b1e31"}

# Estilo institucional de tabla de datos ("Estándares para Recursos Visuales y
# Datos" + catálogo de snippets). El encabezado NO usa el mismo color que los
# recuadros: educación va #004a80 y posgrado #1b1e31.
CABECERA_TABLA_POR_TEMA = {"educacion": "#004a80", "posgrado": "#1b1e31"}
_TABLA_CLASES = ("ic-Table dp-shadow-b3 ic-Table--striped dp-border-dir-all "
                 "cp-bg-dp-white")
_TABLA_ESTILO = ("width: 100%; border-radius: 10px; border-collapse: separate; "
                 "overflow: hidden; table-layout: fixed;")
_TABLA_BORDE_CELDA = "border-bottom: 1px solid #e2e8f0;"
_TABLA_FILA_PAR, _TABLA_FILA_IMPAR = "#ffffff", "#f4f7fa"
ACCENT = ACENTO_POR_TEMA["posgrado"]
ICONOS_BASE = "$IMS-CC-FILEBASE$/Iconos"
ICONOS = {
    "lectura": "Icono%20recuadro%20lectura.svg",
    "video": "Icono%20recuadro%20video.svg",
    "podcast": "Icono%20recuadro%20Podcast.svg",
    "imagen": "Icono%20recuadro%20imagen.svg",
    "foro": "Icono%20recuadro%20Foro.svg",
    "mural": "icono%20recuadro%20Mural.svg",
    "consigna": "Icono%20recuadro%20consigna.svg",
}


def _norm(t: str) -> str:
    t = unicodedata.normalize("NFKD", t)
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", t.lower()).strip()


# ---------------------------------------------------------------------- #
#  Snippets oficiales
# ---------------------------------------------------------------------- #

def cta_titulo(etiqueta: str, body_html: str, icono: str = "") -> str:
    """CTA con barra de título (Lectura, Video, Podcast…) — markup idéntico
    al de las aulas maquetadas a mano."""
    img = ""
    if icono:
        img = (f'<img role="presentation" src="{ICONOS_BASE}/{icono}" alt="" '
               f'loading="lazy">&nbsp; ')
    return f"""<div class="dp-callout dp-callout-color-lg-tip card dp-callout-position-default dp-callout-type-title-bar" style="border-color: {ACCENT}; border-radius: 5px;">
<div class="card-body">
<p class="card-title dp-heading-ignore" style="text-align: left; background-color: {ACCENT}; color: #ffffff;"><span style="font-size: 10pt;"><em><strong style="border-color: {ACCENT};">{img}</strong></em><strong style="border-color: {ACCENT};">{etiqueta}</strong></span></p>
{body_html}
</div>
</div>"""


def cta_descubri_leyendo(body_html: str) -> str:
    """CTA 'Descubrí leyendo' para una cita/mención del cuerpo del texto que
    trae un link suelto (p.ej. '… (WEF, 2021): https://…'), distinto del CTA
    Lectura (que sale de una tabla o de una frase-invitación explícita como
    'te invito a leer'). Ícono fa-book-reader, markup idéntico al de las
    aulas maquetadas a mano."""
    return f"""<div class="dp-callout card dp-callout-position-default dp-callout-type-title-bar dp-callout-color-lg-tip dp-hover-shadow-b1" style="border-radius: 5px; border-color: {ACCENT};">
<div class="card-body">
<p class="card-title dp-heading-ignore" style="text-align: left; background-color: {ACCENT};"><span style="font-size: 10pt;"><em><strong style="border-color: {ACCENT};"><i class="dp-icon fas fa-book-reader dp-i-size-med" aria-hidden="true"><span class="dp-icon-content" style="display: none;">&nbsp;</span></i>&nbsp; </strong></em><strong style="border-color: {ACCENT};">Descubrí leyendo</strong></span></p>
{body_html}
</div>
</div>"""


# Marcador que deja el asesor donde va un video propio ("VIDEO M2.", "VIDEO 2",
# "VIDEO MÓDULO 1"). A veces es un párrafo suelto y a veces queda pegado al
# final de la invitación.
# Párrafo que es SOLO el nombre de un archivo: el asesor anota al pie de un
# recuadro a qué entregable apunta ("EP - AFI.docx", "AEO 1 - GRyI.docx"). Es
# una nota para maquetación, no contenido del aula.
_PAT_SOLO_ARCHIVO = re.compile(
    r"^[\w\s().,+&'’\-–—]{1,80}\.(docx?|pdf|xlsx?|pptx?)$", re.I)

# "Embeber video: GRyI - V_M1" — el asesor marca dónde va un video PROPIO y
# con qué archivo se corresponde. Es una indicación para maquetación, no
# contenido del aula.
_PAT_EMBEBER_VIDEO = re.compile(
    r"^\s*(?:embeber|incrustar|insertar|subir)\b[^:<]{0,25}?\bvideos?\b\s*[:.\-–—]*\s*",
    re.I)
_PAT_MARCADOR_VIDEO = re.compile(
    r"^\s*videos?\s*(?:m(?:[oó]dulo)?\s*)?\d*\s*[\.:]?\s*$", re.I)
_PAT_MARCADOR_VIDEO_FINAL = re.compile(
    r"\s*\bvideos?\s*(?:m(?:[oó]dulo)?\s*)?\d*\s*\.?\s*(?=</|$)", re.I)


def _sin_marcador_video(html: str) -> str:
    """Saca el marcador de video del final del párrafo, si quedó ahí."""
    return _PAT_MARCADOR_VIDEO_FINAL.sub("", html, count=1)


def bloque_video_studio(body_html: str = "", referencia: str = "") -> str:
    """Bloque de video propio de la UCC (Canvas Studio).

    Los videos de desarrollo / introducción / conceptuales NO son un CTA: no
    mandan a YouTube, se suben a Canvas Studio y se incrustan. Como el id del
    video recién existe cuando alguien lo sube —después de generar el aula— el
    bloque queda armado y vacío, listo para pegar el embed.

    `referencia` es el nombre con el que el asesor identificó el video en el
    DOCX ("GRyI - V_M1"): no se publica, va en el comentario del hueco para
    que quien pegue el embed sepa cuál de los archivos va acá.
    """
    intro = f'{body_html}<p>&nbsp;</p>' if body_html else ""
    cual = f": {referencia}" if referencia else ""
    return f"""<div class="dp-content-block" data-title="Video" data-category="+UCC">
<h2 class="dp-has-icon"><i class="dp-icon fab fa-youtube" aria-hidden="true"><span class="dp-icon-content" style="display: none;">&nbsp;</span></i></h2>
{intro}<div class="dp-embed-wrapper mx-auto d-block" style="text-align: center;"><!-- Pegar aquí el embed de Canvas Studio{cual} --></div>
<p>&nbsp;</p>
</div>"""


def resaltado_profundizacion(titulo: str, body_html: str) -> str:
    """Reflexiona / Para pensar / Para saber más — amarillo con lámpara.

    Token de color `dp-callout-color-warning` (no el `lg-`) y el amarillo
    institucional explícito en la barra lateral, como en "Estilos para
    Llamados a la Acción…" y en las aulas maquetadas a mano.
    """
    return f"""<div class="dp-callout dp-callout-placeholder card dp-callout-position-default dp-callout-type-info dp-callout-color-warning">
<div class="dp-callout-side-emphasis" style="background-color: #f4e600; color: #000000;"><i class="dp-icon fas fa-lightbulb dp-default-icon">​</i></div>
<div class="card-body">
<h3 class="card-title" style="color: #757121;">{titulo}</h3>
{body_html}
</div>
</div>"""


def resaltado_atencion(body_html: str, titulo: str = "No pases de largo") -> str:
    return f"""<div class="dp-callout dp-callout-placeholder card dp-callout-position-default dp-callout-type-info dp-callout-color-danger">
<div class="dp-callout-side-emphasis"><i class="dp-icon dp-default-icon fas fa-exclamation-triangle">​</i></div>
<div class="card-body">
<h3 class="card-title">{titulo}</h3>
{body_html}
</div>
</div>"""


def resaltado_ejemplo(body_html: str, titulo: str = "Ejemplos que iluminan") -> str:
    return f"""<div class="dp-callout dp-callout-placeholder card dp-callout-position-default dp-callout-color-dp-primary dp-callout-type-info">
<div class="dp-callout-side-emphasis"><i class="fas fa-copy dp-default-icon">​</i></div>
<div class="card-body">
<h3 class="card-title">{titulo}</h3>
{body_html}
</div>
</div>"""


def _indentar_cuerpo_laboratorio(body_html: str) -> str:
    """El cuerpo del "Laboratorio de ideas" va sangrado 40px, alineado con el
    título: cada <p> de primer nivel lleva ese padding, y una lista de primer
    nivel se envuelve en un <ul><li style="list-style-type: none;">…</li></ul>
    extra (la convención del equipo para correr los ítems bajo esa sangría sin
    que les salga su propia viñeta duplicada)."""
    soup = BeautifulSoup(body_html, "html.parser")
    for p in soup.find_all("p", recursive=False):
        estilo = p.get("style", "")
        p["style"] = (estilo.rstrip("; ") + "; " if estilo else "") \
            + "padding-left: 40px;"
    for lista in soup.find_all(["ul", "ol"], recursive=False):
        envoltorio = soup.new_tag("ul")
        li = soup.new_tag("li", style="list-style-type: none;")
        lista.wrap(li)
        li.wrap(envoltorio)
    return str(soup)


def resaltado_laboratorio_ideas(body_html: str,
                                titulo: str = "Laboratorio de ideas") -> str:
    """Desafío personal sin entrega — "Lecture Hook" con forma de flecha,
    ícono de matraz. Catálogo UCC, ver docs/referencia-designplus-cidilabs-
    ucc.md."""
    cuerpo = _indentar_cuerpo_laboratorio(body_html)
    return f"""<div class="dp-content-block" style="margin-left: 0 !important; padding-left: 0 !important;" data-title="Lecture Hook" data-category="Interactions">
<div class="dp-column-container container-fluid" style="font-size: 16px; width: 100%; border-radius: 16px; overflow: hidden; padding-left: 0 !important; margin-left: 0 !important;">
<div class="row" style="margin-left: 0; margin-right: 0;">
<div class="col-lg-1 col-md-1 col-sm-2 dp-bg dp-shape-peak-r cp-bg-dp-primary dp-mask-grd-md-h dp-wcag-aa align-items-center justify-content-center" style="padding-right: 0px;">
<p class="text-center dp-heading-ignore"><strong><i class="dp-icon fas fa-flask" style="font-size: 25px;" aria-hidden="true"><span class="dp-icon-content" style="display: none;">&nbsp;</span></i></strong></p>
</div>
<div class="dp-bg dp-shape-tri-cut-l cp-bg-light col-lg-11 col-md-11 col-sm-10 dp-padding-direction-tblr" style="padding-right: 75px; padding-left: 25px; background-color: #f4f6f8;">
<h3 class="dp-ignore-theme" style="padding-left: 40px;"><strong>{titulo}</strong></h3>
{cuerpo}
</div>
</div>
</div>
</div>"""


#  Frase corta dentro de un recuadro simple: el equipo la centra.
_LARGO_FRASE_CORTA = 220


def resaltado_simple(body_html: str) -> str:
    """Recuadro destacado sin título (borde institucional).

    Si el contenido es una frase corta va centrado, como lo maqueta el equipo
    a mano ("si la frase es chica, centrala").
    """
    cuerpo = body_html
    texto = BeautifulSoup(body_html, "html.parser").get_text(" ", strip=True)
    if 0 < len(texto) <= _LARGO_FRASE_CORTA:
        soup = BeautifulSoup(body_html, "html.parser")
        parrafos = soup.find_all("p")
        if parrafos:
            for p in parrafos:
                estilo = (p.get("style") or "").rstrip("; ")
                if "text-align" not in estilo:
                    p["style"] = (estilo + "; " if estilo else "") + "text-align: center;"
                clases = p.get("class") or []
                if "card-text" not in clases:
                    p["class"] = clases + ["card-text"]
            cuerpo = str(soup)
        else:
            cuerpo = (f'<p class="card-text" style="text-align: center;">'
                      f'{body_html}</p>')
    elif texto and not BeautifulSoup(body_html, "html.parser").find("p"):
        # Una cita larga (>220) que llega SIN su <p> (aplicar_comentarios pasa
        # solo el contenido interno del párrafo anclado, "".join(children),
        # no el <p> que lo envolvía) quedaba como texto/<em> suelto, hijo
        # directo de card-body: sin bloque propio, el margen que separa la
        # caja de lo que sigue queda a merced de cómo el navegador arme la
        # caja anónima para ese contenido inline — inconsistente. Se envuelve
        # igual que la frase corta, sin el centrado (no es una frase corta).
        cuerpo = f"<p>{body_html}</p>"
    return f"""<div class="dp-callout dp-callout-color-lg-tip card dp-callout-position-default dp-callout-type-title-bar" style="border-color: {ACCENT}; border-radius: 5px;">
<div class="card-body">
{cuerpo}
</div>
</div>"""


# ---------------------------------------------------------------------- #
#  Clasificación de recuadros (tablas de 1 columna del DOCX)
# ---------------------------------------------------------------------- #

def _clasificar_recuadro(etiqueta: str, texto_completo: str) -> tuple:
    """Devuelve (tipo, titulo) para una tabla-recuadro según su etiqueta.

    Busca la palabra clave EN CUALQUIER PARTE de la etiqueta, no solo al
    principio: los asesores no siempre escriben la etiqueta "pelada"
    ("Video"), a veces la envuelven en una frase propia ("Auriculares on
    (Video)", "Una pausa para reflexionar") — con solo `startswith` esas
    cajas caían al recuadro simple, sin ícono ni título."""
    n = _norm(etiqueta)
    nt = _norm(texto_completo)

    if any(k in n for k in ("foro", "debate", "discusion")):
        # Llamado a participar del foro: el título completo va en la barra.
        return "foro", etiqueta
    if "mural" in n:
        return "mural", "Voces que construyen"
    if "recursos" in n or "caja de herramientas" in n:
        return "recursos", "Caja de herramientas para usar"
    if "vengo hasta" in n or "autoevaluacion" in n:
        # CTA oficial de autochequeo: el asesor a veces ya usa el título
        # oficial en la etiqueta ("¿Cómo vengo hasta acá? (Actividad /
        # Autoevaluación)") — se limpia el paréntesis de tipo, que es para
        # nosotros, no para el estudiante.
        return "actividad_check", "¿Cómo vengo hasta acá?"
    if "actividad" in n:
        # Actividad de página (rápida/sugerida): recuadro CTA Actividad.
        # (Las obligatorias/integradoras ya fueron extraídas al assignment.)
        return "actividad_cta", etiqueta

    if any(k in n for k in ("reflexion", "pausa")):
        # El equipo estandariza CUALQUIER etiqueta del docente ("Reflexiona",
        # "Para pensar") al único título oficial del snippet UCC — no hay
        # variantes "Para pensar"/"Para saber más", ver catálogo de snippets.
        return "profundizacion", "Una pausa para reflexionar"
    if "lectura" in n or "te invito a leer" in nt \
            or "invitamos a leer" in nt or "te invito a la lectura" in nt:
        return "lectura", "Descubrí leyendo"
    if "auriculares" in n:
        # "Auriculares on" ES el título oficial del CTA de Video/Podcast: a
        # veces llega pelado y a veces con la aclaración de tipo entre
        # paréntesis ("Auriculares on (Video y Podcast)"). Sin esta rama, el
        # mismo recuadro salía como CTA en el módulo que traía el paréntesis
        # y como recuadro simple en los otros dos.
        es_podcast = ("podcast" in nt or "audio" in nt) and "video" not in nt
        return ("podcast" if es_podcast else "video"), "Auriculares on"
    if "video" in n or "visualizar el video" in nt[:200]:
        return "video", "Auriculares on"
    if "podcast" in n or "audio" in n:
        return "podcast", "Auriculares on"
    if "imagen" in n:
        return "imagen", "Miralo con lupa"
    if "atencion" in n or "importante" in n:
        return "atencion", "No pases de largo"
    if "ejemplo" in n:
        return "ejemplo", "Ejemplos que iluminan"
    if "laboratorio de ideas" in n:
        return "laboratorio_ideas", "Laboratorio de ideas"
    return "simple", ""


# Nombres con los que los asesores piden cada componente desde el propio
# DOCX: los escriben como primera línea de la caja y le dejan encima un
# comentario ("Maquetación").
_EXPANDER_KW = ("expander", "expandible", "expandibles", "acordeon",
                "desplegable", "desplegables")
# "Flips cards" (con la 's' de más) es como lo escribe el asesor de "Gestión
# del Riesgo": sin la variante, la tabla salía como un recuadro con la
# instrucción a la vista.
_FLIP_KW = ("flip card", "flip cards", "flipcard", "flipcards",
            "flips card", "flips cards")
# La orientación viene en la misma línea ("Tabs (uno al lado del otro)",
# "Tabs verticales; al hacer clic…").
_TABS_KW = ("tabs", "solapas", "pestanas", "pestana")


def _es_instruccion_maquetacion(texto: str) -> bool:
    """Etiquetas que son INDICACIONES de maquetación (cómo formatear), no
    contenido: no van en el aula. P.ej. 'Tabla con resaltado sutil'."""
    n = _norm(texto)
    return n.startswith((
        "tabla con", "tabla de datos", "con resaltado", "resaltado",
        "recuadro con", "cuadro con", "imagen con", "imagen de diseno",
        "recurso tipo", "esquema con", "infografia con", "cita con",
    # Nombre pelado del componente como primera línea de la caja: es la
    # convención de varios asesores ("Tabs (uno al lado del otro)",
    # "Expander", "Flips cards (una al lado de la otra)"). Si el componente
    # se pudo armar nunca llegamos acá; si no se pudo, al menos la
    # indicación no queda a la vista del estudiante.
    ) + _TABS_KW + _EXPANDER_KW + _FLIP_KW)


def _filas_propias(tabla) -> list:
    """<tr> de esta tabla, sin los de las tablas anidadas adentro."""
    return [tr for tr in tabla.find_all("tr") if tr.find_parent("table") is tabla]


def _columnas_propias(tabla) -> int:
    """Ancho real de la tabla. Contar todas las celdas de `find_all` mezclaba
    las de las tablas anidadas: una caja de 1 celda que adentro tiene una
    tabla de datos daba "13 columnas" y se maquetaba como tabla de datos, con
    una tabla metida en el <th> de otra."""
    return max((len([c for c in tr.find_all(["td", "th"])
                     if c.find_parent("table") is tabla])
                for tr in _filas_propias(tabla)), default=0)


def _es_envoltorio_de_figura(tabla) -> bool:
    """¿La tabla existe solo para sostener una figura (imagen + epígrafe +
    nota), en vez de ser un recuadro del catálogo? Se reconoce porque su
    primer rótulo es un epígrafe ("Figura 1. …", "Tabla 2. …") y adentro
    hay una imagen de contenido."""
    primera = tabla.find(["td", "th"])
    if primera is None:
        return False
    if not _PAT_CAPTION.match(primera.get_text(" ", strip=True)):
        return False
    return any(_es_figura(img) for img in tabla.find_all("img"))


def _desarmar_tabla(tabla) -> None:
    """Reemplaza la tabla por el contenido de sus celdas, en orden."""
    piezas = []
    for celda in tabla.find_all(["td", "th"]):
        piezas.extend(h for h in celda.children
                      if getattr(h, "name", None) or str(h).strip())
    tabla.replace_with(BeautifulSoup(
        "".join(str(p) for p in piezas), "html.parser"))


def _tabla_a_recuadro(tabla) -> str:
    """Convierte una tabla de 1 columna en el snippet que corresponda."""
    filas = _filas_propias(tabla)
    celdas = [c for c in (tr.find(["td", "th"]) for tr in filas) if c is not None]
    if not celdas:
        return ""

    # "Líneas" del recuadro: las celdas (tabla multi-fila) o, si hay una sola
    # celda con varios bloques, cada bloque (así la 1ª línea =
    # etiqueta/instrucción). Se toman los bloques y no solo los <p>: con
    # `find_all("p")` las listas se perdían enteras y las tablas de datos
    # anidadas quedaban aplastadas en sus párrafos sueltos.
    if len(celdas) == 1:
        bloques = _bloques_de_celda(celdas[0])
        lineas = bloques if len(bloques) >= 2 else celdas
    else:
        lineas = celdas

    etiqueta = lineas[0].get_text(" ", strip=True)
    texto_completo = tabla.get_text(" ", strip=True)
    tipo, titulo = _clasificar_recuadro(etiqueta, texto_completo)

    def _html_lineas(ls):
        partes = []
        for el in ls:
            if getattr(el, "name", "") not in ("td", "th"):
                partes.append(str(el))
                continue
            inner = "".join(str(x) for x in el.children).strip()
            if inner and not inner.lstrip().startswith("<"):
                inner = f"<p>{inner}</p>"
            partes.append(inner)
        return "\n".join(p for p in partes if p)

    # La 1ª línea se quita del cuerpo si es una etiqueta/instrucción reconocida
    # (foro/actividad/lectura/…) o una indicación de maquetación. En tablas
    # multi-fila, además, una 1ª fila corta se asume etiqueta (como antes).
    es_instr = _es_instruccion_maquetacion(etiqueta)
    if len(celdas) == 1:
        quitar = (tipo != "simple") or es_instr
    else:
        # tipo != "simple" = ya reconocimos la etiqueta como un tipo de
        # recuadro (aunque sea larga, p.ej. "¿Cómo vengo hasta acá? (Actividad
        # sugerida)", 44 caracteres) → siempre se saca del cuerpo, si no queda
        # duplicada como texto suelto debajo de la caja ya armada.
        quitar = tipo != "simple" or len(etiqueta) <= 35 or es_instr
    cuerpo = lineas[1:] if quitar and len(lineas) > 1 else lineas
    body = _html_lineas(cuerpo)
    if not body:
        cuerpo = lineas
        body = _html_lineas(cuerpo)

    if tipo == "video" and not _PAT_URL_VIDEO.search(body):
        # Con la marca "Embeber video: <nombre>" el video es propio de la UCC:
        # va al bloque de Canvas Studio, no a un CTA que manda afuera. Decide
        # la marca, no la ausencia de URL: hay CTAs legítimos que invitan a una
        # charla TED sin pegar el link en el mismo párrafo.
        frag = BeautifulSoup(body, "html.parser")
        marca = next((p for p in frag.find_all("p")
                      if _PAT_EMBEBER_VIDEO.match(p.get_text(" ", strip=True))),
                     None)
        if marca is not None:
            referencia = _PAT_EMBEBER_VIDEO.sub(
                "", marca.get_text(" ", strip=True)).strip(" .:–—-")
            marca.decompose()
            return bloque_video_studio(str(frag).strip(), referencia)

    if tipo == "foro":
        return cta_titulo(titulo, body, ICONOS["foro"])
    if tipo == "actividad_check":
        # CTA - Actividad/Autoevaluación del catálogo oficial ("¿Cómo vengo
        # hasta acá?"): mismo estilo title-bar que Lectura/Video, ícono de
        # consigna.
        return cta_titulo(titulo, body, ICONOS["consigna"])
    if tipo == "actividad_cta":
        # CTA - Actividad del catálogo oficial (dp-primary, barra de título)
        return f"""<div class="dp-callout dp-callout-placeholder card dp-callout-position-default dp-callout-color-dp-primary dp-callout-type-title-bar">
<div class="card-body">
<p class="card-title dp-heading-ignore" style="text-align: left;"><span style="font-size: 10pt;"><strong>{titulo}</strong></span></p>
{body}
</div>
</div>"""
    if tipo == "recursos":
        return f"""<div class="dp-callout card dp-callout-position-default dp-callout-type-title-bar dp-callout-color-lg-tip dp-hover-shadow-b1" style="border-radius: 5px; border-color: {ACCENT};">
<div class="card-body">
<p class="card-title dp-heading-ignore" style="text-align: left; background-color: {ACCENT};"><span style="font-size: 10pt;"><em><strong style="border-color: {ACCENT};"><i class="dp-icon fas fa-layer-group dp-i-size-med" aria-hidden="true"><span class="dp-icon-content" style="display: none;">&nbsp;</span></i>&nbsp; </strong></em><strong style="border-color: {ACCENT};">{titulo}</strong></span></p>
{body}
</div>
</div>"""
    if tipo == "profundizacion":
        return resaltado_profundizacion(titulo, body)
    if tipo in ("lectura", "video", "podcast", "imagen", "mural"):
        return cta_titulo(titulo, body, ICONOS.get(tipo, ""))
    if tipo == "atencion":
        return resaltado_atencion(body, titulo)
    if tipo == "ejemplo":
        return resaltado_ejemplo(body, titulo)
    if tipo == "laboratorio_ideas":
        return resaltado_laboratorio_ideas(body, titulo)
    return resaltado_simple(body)


# ---------------------------------------------------------------------- #
#  Figuras de DISEÑO: reemplazan a las imágenes embebidas del DOCX
# ---------------------------------------------------------------------- #

# Separador tras "Figura N" tolerante a cualquier convención del asesor:
# punto, dos puntos, guión/raya (con o sin espacio), o nada (el marcador
# solo, sin descripción en el mismo párrafo). NO alcanza con "no sea letra":
# un espacio tampoco lo es, y agarraría cualquier oración que arranque con
# "Tabla "/"Figura " como palabra suelta ("Tabla de contenidos…").
_PAT_FIG_CAPTION = re.compile(
    r"^(figura|esquema|tabla)\s*(\d+)?\s*(?:[\.:]|[-–—]|$)", re.I)
# Nombres reales observados: "M_1 Fig 4.jpg", "M1 Figura 2.jpg",
# "Figura 4 M3.png", "Tabla 1 M2.jpg", "Esquema.jpg", "M1 - Figura 1.png".
# El separador entre el módulo y el tipo varía por curso (espacio, guion
# bajo, guion medio o una mezcla): con `\s*` a secas, "M1 - Figura 1.png"
# no matcheaba y la figura quedaba sin indexar —silenciosamente, sin aviso.
_SEP_FIG = r"[\s_\-–—]*"
_PAT_FIG_FILE = re.compile(
    rf"(?:m[_\s\-]?(\d+){_SEP_FIG}fig(?:ura)?{_SEP_FIG}(\d+))"
    rf"|(?:fig(?:ura)?{_SEP_FIG}(\d+){_SEP_FIG}m[_\s\-]?(\d+))"
    rf"|(?:tabla{_SEP_FIG}(\d+){_SEP_FIG}m[_\s\-]?(\d+))"
    rf"|(?:m[_\s\-]?(\d+){_SEP_FIG}tabla{_SEP_FIG}(\d+))", re.I)

# "Estándares para Recursos Visuales y Datos": la figura estática lleva otro
# borde que la expandible. La estática es el caso por defecto; el estilo con
# lupa (dp-popup-image) solo cuando el asesor pide poder ampliarla.
_FIG_CLASES_ESTATICA = "dp-max-width dp-image-rounded-10 dp-image-bordered"
_FIG_CLASES_EXPANDIBLE = ("dp-max-width dp-popup-image dp-image-rounded-10 "
                          "dp-image-padded dp-image-bordered dp-image-shadow")


def indexar_figuras_diseno(archivos: list) -> dict:
    """{(modulo, 'figura'|'tabla', n): Path} a partir de los archivos de DISEÑO."""
    indice = {}
    for path in archivos:
        nombre = _norm(path.stem)
        m = _PAT_FIG_FILE.search(nombre)
        if m:
            g = m.groups()
            if g[0]:   mod, num, tipo = int(g[0]), int(g[1]), "figura"
            elif g[2]: mod, num, tipo = int(g[3]), int(g[2]), "figura"
            elif g[4]: mod, num, tipo = int(g[5]), int(g[4]), "tabla"
            else:      mod, num, tipo = int(g[6]), int(g[7]), "tabla"
            indice.setdefault((mod, tipo, num), path)
        elif "esquema" in nombre:
            indice.setdefault(("esquema",), path)
    return indice


def _figura_diseno_es_expandible(p) -> bool:
    """¿La 'Nota'/'Texto alternativo' que sigue al epígrafe describe una
    figura densa en texto (tipo tabla), o el asesor pidió expandirla? Mismos
    marcadores que _figura_es_expandible, mirando los párrafos siguientes
    (donde suelen ir esa nota y el texto alternativo)."""
    trozos = [p.get_text(" ", strip=True)]
    for vecino in list(p.find_next_siblings())[:3]:
        trozos.append(vecino.get_text(" ", strip=True))
    texto = _norm(" ".join(t for t in trozos if t))
    return any(kw in texto for kw in _FIG_EXPANDIBLE_KW)


# Lo único que sigue a una figura y SÍ es contenido de la página.
_PAT_PIE_DE_FIGURA = re.compile(r"^\s*(nota|fuente)\s*[\.:]", re.I)


def _brief_de_figura(p) -> list:
    """Bloques que hay que borrar porque son el pedido a DISEÑO, no contenido.

    El asesor arma una caja de una sola celda con el epígrafe arriba ("Figura
    4. Toma de decisiones") y abajo describe lo que quiere que dibujen
    ("Imagen, tipo check list" y los cuatro ítems). Cuando esa figura llega
    hecha desde la carpeta Diseño, el texto ya está DENTRO de la imagen: si
    se deja, la página muestra lo mismo dos veces.

    Se exige la caja entera (una celda, sin ninguna imagen adentro) para no
    tocar los párrafos que siguen a una figura suelta en medio del texto, y
    se conservan la Nota y la Fuente, que sí son pie de figura."""
    celda = p.find_parent(["td", "th"])
    if celda is None or celda.find("img"):
        return []
    tabla = celda.find_parent("table")
    if tabla is None or len(tabla.find_all(["td", "th"])) != 1:
        return []
    if p.find_previous_sibling() is not None:   # el epígrafe abre la caja
        return []
    return [b for b in p.find_next_siblings()
            if not _PAT_PIE_DE_FIGURA.match(b.get_text(" ", strip=True))]


def reemplazar_figuras_diseno(html: str, modulo: int, indice: dict,
                              usadas: set) -> str:
    """Donde hay un epígrafe 'Figura N.' con una imagen embebida al lado,
    usa la figura de DISEÑO (mejor calidad) en su lugar. Marca en `usadas`
    los paths aprovechados. La ruta queda como __DISENO__/<nombre> para que
    el empaquetador la resuelva."""
    if not html or not indice:
        return html
    soup = BeautifulSoup(html, "html.parser")

    def _vecino_reemplazable(p):
        """Imagen embebida o tabla de datos junto al epígrafe. Se priorizan los
        vecinos MÁS CERCANOS (el siguiente antes que el anterior, porque el
        epígrafe suele estar arriba de la imagen) y la imagen embebida del
        docente por sobre una tabla."""
        sig = list(p.find_next_siblings())
        prev = list(p.find_previous_siblings())
        cercanos = []
        for i in range(2):
            if i < len(sig):
                cercanos.append(sig[i])
            if i < len(prev):
                cercanos.append(prev[i])

        def _img_embebida(vecino):
            nombre = getattr(vecino, "name", "")
            if nombre in ("p", "div"):
                img = vecino.find("img")
                if img and "__MEDIA__" in (img.get("src") or ""):
                    return img
            elif nombre == "img" and "__MEDIA__" in (vecino.get("src") or ""):
                return vecino
            return None

        for vecino in cercanos:        # 1º: imagen embebida adyacente
            img = _img_embebida(vecino)
            if img is not None:
                return ("img", img)
        for vecino in cercanos:        # 2º: tabla (el docente la hizo, diseño la rehízo)
            if getattr(vecino, "name", "") == "table":
                return ("table", vecino)
        return (None, None)

    for p in soup.find_all("p"):
        texto = p.get_text(" ", strip=True)
        m = _PAT_FIG_CAPTION.match(texto)
        if not m:
            continue
        tipo = m.group(1).lower()
        num = int(m.group(2)) if m.group(2) else None
        if tipo == "esquema":
            path = indice.get(("esquema",))
        elif num is not None:
            path = (indice.get((modulo, "figura" if tipo == "figura" else "tabla", num))
                    or (indice.get((modulo, "tabla", num)) if tipo == "figura" else None))
        else:
            path = None
        if not path:
            continue
        clase, vecino = _vecino_reemplazable(p)
        if clase == "img":
            vecino["src"] = f"__DISENO__/{path.name}"
            usadas.add(path)
        elif clase == "table":
            # Una figura de diseño que reemplaza una TABLA de datos es, por
            # definición, densa en texto (varias filas/columnas resumidas en
            # una sola imagen): siempre necesita poder ampliarse para leerse,
            # lo haya pedido el asesor o no — mismo criterio que
            # _FIG_EXPANDIBLE_KW para las figuras que solo dejan un marcador.
            clase_img = _FIG_CLASES_EXPANDIBLE
            ancho = 700
            nueva = BeautifulSoup(
                f'<p style="text-align: center;"><img class="{clase_img}" '
                f'style="width: {ancho}px; height: auto;" '
                f'src="__DISENO__/{path.name}" alt="{texto[:120]}" '
                f'loading="lazy"></p>', "html.parser")
            vecino.replace_with(nueva)
            usadas.add(path)
        else:
            # Sin imagen ni tabla embebida al lado que reemplazar (el epígrafe
            # es un marcador propio: "Figura N" sola, o "Figura N. — desc" con
            # cualquier separador): se inserta la figura de diseño en el lugar
            # del marcador, conservando el texto del epígrafe como pie de foto
            # cuando el párrafo traía descripción además del número.
            #
            # El epígrafe va ARRIBA de la imagen ("Estándares para Recursos
            # Visuales y Datos" y las aulas a mano); salía invertido.
            expandible = _figura_diseno_es_expandible(p)
            clase_img = _FIG_CLASES_EXPANDIBLE if expandible else _FIG_CLASES_ESTATICA
            # 700px para estática y ampliable por igual (pedido del usuario:
            # "un poquito más grande" el ancho por defecto de 600 se veía
            # chico); lo que las distingue es la clase (borde vs.
            # sombra+zoom), no el tamaño.
            ancho = 700
            brief = _brief_de_figura(p)
            resto = texto[m.end():].strip(" .:–—-")
            img_html = ""
            if resto:
                img_html += (
                    '<p class="dp-heading-ignore" style="text-align: center;">'
                    f'<span style="font-size: 10pt;"><strong>{texto}</strong>'
                    '</span></p>')
            img_html += (
                f'<p style="text-align: center;"><img class="{clase_img}" '
                f'style="width: {ancho}px; height: auto;" '
                f'src="__DISENO__/{path.name}" alt="{texto[:120]}" '
                f'loading="lazy"></p>')
            p.replace_with(BeautifulSoup(img_html, "html.parser"))
            for bloque in brief:
                bloque.decompose()
            usadas.add(path)
    return str(soup)


# ---------------------------------------------------------------------- #
#  Consignas de foro: van al DiscussionTopic, no a la página de contenido
# ---------------------------------------------------------------------- #

_SENALES_CONSIGNA_FORO = (
    "responde en el foro", "responder en el foro", "respondan en el foro",
    "comenta en las respuestas", "comenta las respuestas",
    "participa del foro respondiendo", "no mas de", "en un maximo de",
)


def separar_consignas(html: str) -> tuple:
    """Las CONSIGNAS embebidas en el documento multimedial no van en la
    página de contenido: van dentro del recurso de Canvas (foro/actividad).

    Detecta tablas de 1 columna cuya etiqueta es:
      - "Foro …" con señales de consigna (las invitaciones quedan en la página)
      - "Actividad …" (obligatoria/sugerida/práctica/integradora): siempre
        es consigna → al assignment
      - "Autoevaluación …": consigna de quiz → se extrae y queda para carga
        manual (los QTI no se generan automáticamente)

    Devuelve (html_sin_consignas, [(tipo, titulo, body_html), …]) con
    tipo ∈ {foro, actividad, autoevaluacion}.
    """
    low = (html or "").lower()
    if not html or ("foro" not in low and "actividad" not in low
                    and "autoevaluaci" not in low):
        return html, []
    soup = BeautifulSoup(html, "html.parser")
    consignas = []
    for tabla in soup.find_all("table"):
        max_cols = max((len(tr.find_all(["td", "th"]))
                        for tr in tabla.find_all("tr")), default=0)
        if max_cols != 1:
            continue
        celdas = [tr.find(["td", "th"]) for tr in tabla.find_all("tr")]
        celdas = [c for c in celdas if c is not None]
        if not celdas:
            continue
        etiqueta = celdas[0].get_text(" ", strip=True)
        ne = _norm(etiqueta)
        # El docente a veces antepone la referencia al ícono ("Ícono actividad
        # obligatoria"); se ignora ese prefijo para clasificar la etiqueta.
        ne = re.sub(r"^[ií]con[oa]?\s+", "", ne)
        texto = _norm(tabla.get_text(" ", strip=True))

        if ne.startswith("foro"):
            if not any(s in texto for s in _SENALES_CONSIGNA_FORO):
                continue   # invitación: queda en la página como CTA Foro
            tipo = "foro"
        elif ne.startswith("actividad") and any(
                k in ne for k in ("obligatoria", "integradora", "final")):
            # Solo las actividades CALIFICABLES van al assignment; las
            # rápidas/sugeridas/de ejercitación son parte de la página
            # (quedan como recuadro CTA Actividad).
            tipo = "actividad"
        elif ne.startswith("autoevaluacion") or ne.startswith("auto evaluacion"):
            tipo = "autoevaluacion"
        else:
            continue

        cuerpo = []
        for c in celdas[1:]:
            inner = "".join(str(x) for x in c.children).strip()
            if inner and not inner.lstrip().startswith("<"):
                inner = f"<p>{inner}</p>"
            cuerpo.append(inner)
        if not cuerpo and len(celdas) == 1:
            # todo el bloque vive en una sola celda: el cuerpo es la celda
            # completa sin la primera línea-etiqueta
            cuerpo = ["".join(str(x) for x in celdas[0].children).strip()]
        consignas.append((tipo, etiqueta, "\n".join(cuerpo)))
        tabla.decompose()
    return (str(soup), consignas) if consignas else (html, [])


# ---------------------------------------------------------------------- #
#  Recuadros a nivel párrafo (frases-señal que el equipo maqueta a mano)
# ---------------------------------------------------------------------- #

_CUES_PARRAFO = (
    # (tipo, frases con que ARRANCA el párrafo)
    ("lectura", ("te invito a leer", "te invitamos a leer",
                 "proponemos la lectura", "te propongo la lectura",
                 "propongo la lectura", "sugerimos la lectura",
                 "invitamos a la lectura", "te invito a la lectura")),
    ("video", ("te propongo visualizar", "te invitamos a visualizar",
               "te invito a visualizar", "te invito a ver el video",
               "te invitamos a ver el video", "proponemos visualizar")),
    ("atencion", ("es importante destacar", "es importante señalar",
                  "es importante senalar", "es importante recordar",
                  "es importante tener presente", "importante:")),
    ("imagen", ("les proponemos que observen", "proponemos que observen",
                "te propongo observar", "te invitamos a observar",
                "te invito a observar")),
)

# Invitación a ver un video, en cualquier parte del párrafo (no solo al inicio):
# "ver/mirar/visualizar/observar (el) (siguiente) video".
_PAT_VIDEO_INVIT = re.compile(
    r"\b(?:ver|mirar|mir[aá]|visualiz\w+|observa[rl]?\w*|reproduc\w+)\b\s+"
    r"(?:atentamente\s+)?(?:el|los|un|este|la)?\s*(?:siguientes?\s+)?\bvideos?\b",
    re.I)
# Referencia a un video YA visto (no es una invitación a uno nuevo).
_PAT_VIDEO_REF = re.compile(
    r"^\s*(?:luego de|despu[eé]s de|una vez|tras|habiendo|al\s+terminar|"
    r"a partir de)", re.I)
_PAT_URL_VIDEO = re.compile(r"youtu\.?be|youtube\.com|vimeo\.com", re.I)

# Párrafo que introduce una cita textual: termina en ":" con verbo de decir.
_PAT_INTRO_CITA = re.compile(
    r"\b(dice|dicen|señala|senala|sostiene|afirma|plantea|expresa|define|"
    r"menciona|agrega|explica|describe|resume)\b[^:]{0,80}:$")

# Cita APA al final de un párrafo: "(Autor, 2021)" / "(Instituto…, 2021a)".
_PAT_APA_YEAR_FINAL = re.compile(r"\([^()]*,\s*\d{4}[a-z]?\)\.?\s*$")


def _definiciones_citadas_tras_pregunta(soup):
    """Párrafo que define un término, citado en formato APA, justo debajo de
    un encabezado en forma de pregunta ("¿Qué es…?"): es una cita textual
    aunque no traiga una frase introductoria con verbo de decir (no hay
    "define:" antes, el encabezado ya cumple ese rol). Sangría doble, como
    cualquier otra cita — pedido explícito del usuario, no viene marcado por
    un comentario del asesor."""
    for h in soup.find_all(["h2", "h3", "h4", "h5", "h6"]):
        titulo = h.get_text(" ", strip=True)
        if not titulo.startswith("¿"):
            continue
        p = h.find_next_sibling()
        while p is not None and _es_espaciador(p):
            p = p.find_next_sibling()
        if p is None or getattr(p, "name", None) != "p":
            continue
        texto = p.get_text(" ", strip=True)
        if len(texto) < 150 or not _PAT_APA_YEAR_FINAL.search(texto):
            continue
        aplicar_cita(p)


def _detectar_cue(texto_norm: str) -> str:
    for tipo, frases in _CUES_PARRAFO:
        if texto_norm.startswith(frases):
            return tipo
    return ""


def _absorber_siguientes(p) -> list:
    """Tras un párrafo-cue, los 1-2 párrafos siguientes cortos con el link o
    la referencia bibliográfica forman parte del mismo recuadro."""
    extras = []
    sig = p.find_next_sibling()
    while sig is not None and len(extras) < 2 and getattr(sig, "name", "") == "p":
        texto = sig.get_text(" ", strip=True)
        tiene_link = sig.find("a") is not None
        es_corto = len(texto) <= 220
        if (tiene_link and es_corto) or (es_corto and sig.find(["em", "i"])):
            extras.append(sig)
            sig = sig.find_next_sibling()
        else:
            break
    return extras


def _procesar_cues_parrafo(soup):
    # Bloques de video que YA venían armados de la tabla ("Embeber video: …"):
    # sus párrafos no se vuelven a mirar, si no el bloque salía duplicado y
    # anidado dentro de sí mismo. Se toman ahora y no con find_parent adentro
    # del bucle porque los bloques que arma ESTE paso se quedan abiertos y
    # absorben el resto de la página a propósito (ver más abajo): lo que cae
    # ahí adentro sí debe seguir procesándose.
    ya_armados = soup.find_all("div", attrs={"data-title": "Video"})
    for p in list(soup.find_all("p")):
        if p.parent is None or p.find_parent(class_="dp-callout"):
            continue
        if any(any(a is bloque for a in p.parents) for bloque in ya_armados):
            continue
        # El asesor pidió explícitamente NO encuadrar este párrafo.
        if p.get("data-keep-plain"):
            continue
        texto = p.get_text(" ", strip=True)
        if not texto or len(texto) > 700:
            continue
        tipo = _detectar_cue(_norm(texto))
        if not tipo and _PAT_VIDEO_INVIT.search(texto):
            # Invitación a ver un video aunque no arranque con la frase-cue.
            # Si es una referencia a un video ya visto ("luego de ver el
            # video, ¿…?") y no trae enlace, no es un recuadro de video.
            tiene_url = bool(_PAT_URL_VIDEO.search(texto)) or any(
                _PAT_URL_VIDEO.search(s.get_text(" ", strip=True))
                for s in _absorber_siguientes(p))
            if tiene_url or not _PAT_VIDEO_REF.match(texto):
                tipo = "video"
        if not tipo:
            continue
        grupo = [p] + _absorber_siguientes(p)
        if tipo == "video":
            # El marcador donde va el video ("VIDEO 2") suele ir en su propio
            # párrafo, después de la invitación —a veces separado por un
            # párrafo de aire (&nbsp;)— y entra al mismo bloque para que no
            # quede publicado como texto suelto.
            sig = grupo[-1].find_next_sibling()
            while sig is not None and _es_espaciador(sig):
                sig = sig.find_next_sibling()
            if sig is not None and getattr(sig, "name", "") == "p" \
                    and _PAT_MARCADOR_VIDEO.match(sig.get_text(" ", strip=True)):
                grupo.append(sig)
        body = "\n".join(str(x) for x in grupo)
        if tipo == "lectura":
            nuevo = cta_titulo("Descubrí leyendo", body, ICONOS["lectura"])
        elif tipo == "video":
            # Con enlace a YouTube/Vimeo es un CTA que manda afuera; sin
            # enlace es un video propio de la UCC (Canvas Studio).
            if _PAT_URL_VIDEO.search(body):
                nuevo = cta_titulo("Auriculares on", body, ICONOS["video"])
            else:
                # El marcador que el asesor deja donde va el video ("VIDEO M2.")
                # no es contenido: no se publica, ni como párrafo suelto ni
                # pegado al final de la invitación.
                nuevo = bloque_video_studio("\n".join(
                    _sin_marcador_video(str(x)) for x in grupo
                    if not _PAT_MARCADOR_VIDEO.match(x.get_text(" ", strip=True))))
                fragmento = BeautifulSoup(nuevo, "html.parser")
                bloque_video = fragmento.find(
                    "div", attrs={"data-title": "Video"})
                p.replace_with(fragmento)
                # El bloque "Video" NO se cierra después del video: el
                # equipo a mano lo deja abierto y ahí adentro sigue el
                # resto de la página completa (herramientas, reflexión,
                # cierre…) — se mueve todo lo que sigue adentro, así no
                # queda como un segundo bloque separado.
                sig = bloque_video.find_next_sibling()
                while sig is not None:
                    proximo = sig.find_next_sibling()
                    bloque_video.append(sig.extract())
                    sig = proximo
                for x in grupo[1:]:
                    x.decompose()
                continue
        elif tipo == "imagen":
            nuevo = cta_titulo("Miralo con lupa", body, ICONOS["imagen"])
        else:
            nuevo = resaltado_atencion(body)
        p.replace_with(BeautifulSoup(nuevo, "html.parser"))
        for x in grupo[1:]:
            x.decompose()

    # Citas textuales: párrafo introductorio con verbo de decir terminado
    # en ":", seguido de un párrafo largo (la cita) → recuadro simple.
    for p in list(soup.find_all("p")):
        if p.parent is None or p.find_parent(class_="dp-callout"):
            continue
        texto = p.get_text(" ", strip=True)
        if not texto.endswith(":") or len(texto) > 250:
            continue
        if not _PAT_INTRO_CITA.search(_norm(texto)):
            continue
        cita = p.find_next_sibling()
        if cita is None or getattr(cita, "name", "") != "p":
            continue
        texto_cita = cita.get_text(" ", strip=True)
        if len(texto_cita) < 250:
            continue
        body = str(p) + "\n" + str(cita)
        p.replace_with(BeautifulSoup(resaltado_simple(body), "html.parser"))
        cita.decompose()


def _procesar_citas_con_link(soup):
    """Párrafo con una mención/cita + un link suelto (autolinkeado, texto del
    link = la URL) → recuadro 'Descubrí leyendo', reemplazando la URL cruda
    por 'Acceso al documento'. Corre DESPUÉS de _autolink_urls.

    No toca: epígrafes/notas de figura (_NO_H3: ya llevan su propia
    atribución, p.ej. una imagen hecha con IA — no son una invitación a leer
    algo aparte) ni párrafos que YA son solo el link (esos quedan con el
    estilo de bibliografía más liviano, ver más abajo en procesar_contenido)."""
    for p in list(soup.find_all("p")):
        if p.parent is None or p.find_parent(class_="dp-callout"):
            continue
        if p.get("data-keep-plain"):
            continue
        texto = p.get_text(" ", strip=True)
        if not texto or _NO_H3.match(texto):
            continue
        link = next((a for a in p.find_all("a")
                     if a.get("href", "").startswith("http")
                     and a.get_text(strip=True) == a.get("href", "")), None)
        if link is None:
            continue
        hijos = [x for x in p.children
                 if getattr(x, "name", None) or str(x).strip()]
        if len(hijos) == 1:
            continue   # el párrafo ya es solo el link: no es este caso
        link.extract()   # saca el link (a cualquier nivel de anidamiento);
                          # lo que queda en p es la intro tal cual
        intro = "".join(str(x) for x in p.children).strip()
        link.string = "Acceso al documento"
        body = (f"<p><span>{intro}</span></p>" if intro else "") + f"<p>{link}</p>"
        p.replace_with(BeautifulSoup(cta_descubri_leyendo(body), "html.parser"))


# ---------------------------------------------------------------------- #
#  Procesador principal
# ---------------------------------------------------------------------- #

_PAT_CAPTION = re.compile(r"^(figura|tabla|esquema)\s*\d*\s*(?:[\.:]|[-–—]|$)", re.I)
_NO_H3 = re.compile(r"^(figura|tabla|esquema|nota\s*[\.:]|fuente\s*[\.:])", re.I)
_PAT_URL = re.compile(r"(https?://[^\s<>\"')\]]+)")


def _autolink_urls(soup):
    """Convierte URLs en texto plano en <a> (el equipo linkea toda URL)."""
    from bs4 import NavigableString
    for nodo in list(soup.find_all(string=True)):
        if not isinstance(nodo, NavigableString):
            continue
        if nodo.find_parent("a") or nodo.find_parent(["script", "style"]):
            continue
        texto = str(nodo)
        if "http" not in texto or not _PAT_URL.search(texto):
            continue
        partes = _PAT_URL.split(texto)
        nuevos = []
        for parte in partes:
            if _PAT_URL.fullmatch(parte):
                url = parte.rstrip(".,;")
                resto = parte[len(url):]
                a = soup.new_tag("a", href=url)
                a.string = url
                nuevos.append(a)
                if resto:
                    nuevos.append(NavigableString(resto))
            elif parte:
                nuevos.append(NavigableString(parte))
        for nuevo in reversed(nuevos):
            nodo.insert_after(nuevo)
        nodo.extract()


def limpiar_anclas_vacias(html: str) -> str:
    """Quita las anclas internas de Word/Google Docs (<a id="_heading=…"></a>
    o <a name="_xxx"></a>): marcadores de navegación sin href ni texto que
    mammoth arrastra. Son ruido invisible; el equipo las borra a mano."""
    if not html:
        return html
    soup = BeautifulSoup(html, "html.parser")
    for a in soup.find_all("a"):
        if not a.get("href") and not a.get_text(strip=True) and not a.find("img"):
            a.unwrap() if a.contents else a.decompose()
    return str(soup)


# Rótulos de sección del "Modelo de actividad": el asesor los escribe como
# "Objetivo:" al principio de un párrafo y son encabezados, no texto corrido.
_SECCIONES_ACTIVIDAD = ("objetivo", "objetivos", "consigna", "consignas",
                        "pautas de presentacion", "criterios de evaluacion",
                        "criterio de evaluacion", "anexo")

# "Actividad final integradora: Analizá situaciones reales" → el prefijo repite
# el nombre del ítem que Canvas ya muestra en el módulo.
_PAT_PREFIJO_ACTIVIDAD = re.compile(
    r"^\s*actividad\s*(?:final\s*integradora|obligatoria|sugerida|optativa)?"
    r"\s*(?:m\s*\d+)?\s*[:\-–—]\s*", re.I)

# "Actividad obligatoria 1" a secas (sin ":" ni nada después): no queda un
# título propio al sacarle el prefijo, así que no aporta nada — Canvas ya
# muestra ese mismo nombre en el banner de la Assignment.
_PAT_TITULO_GENERICO_ACTIVIDAD = re.compile(
    r"^\s*actividad\s*(?:final\s*integradora|obligatoria|sugerida|optativa)?"
    r"\s*(?:m\s*\d+)?\s*\d*\s*[:\-–—]?\s*$", re.I)

_H2_TITULO_ACTIVIDAD = ('<h2 class="dp-ignore-theme" '
                        'style="color: {color}; text-align: center;">'
                        "<strong>{titulo}</strong></h2>")

# Rótulo dentro de la narrativa del caso que se destaca en línea (subrayado y
# negrita), sin cortar el párrafo en un encabezado aparte: no abre una
# sección nueva, es énfasis dentro del relato.
_PAT_ROTULO_EN_LINEA = re.compile(
    r"^(situaci[oó]n de incertidumbre)\s*:\s*", re.I)

# Disclaimer de uso de IA del "Modelo de actividad": va en recuadro simple,
# no como texto corrido.
_PAT_DISCLAIMER_IA = re.compile(r"aporte de la ia", re.I)

# Pregunta numerada de la consigna ("1. ¿Considera que…?"): el asesor a
# veces le da estilo de título de Word adentro del propio documento (para
# organizarse), pero es un ítem de una lista de preguntas, no un encabezado
# de caso — no debe convertirse en <h4> junto con los sub-encabezados
# reales del relato ("Contexto del proyecto", "Actores involucrados"…).
_PAT_PREGUNTA_NUMERADA = re.compile(r"^\d+[.)]\s")


def _limpiar_encabezado(h) -> None:
    """Un encabezado nativo del DOCX puede traer subrayado directo del autor
    (redundante: el tema ya subraya los encabezados por CSS, queda doble) y
    los dos puntos finales de la frase original — ninguno de los dos
    corresponde en un <h3>/<h4> del catálogo. Solo toca el último nodo de
    texto (no h.clear()+h.string): así no se pierde formato interno legítimo
    (p.ej. un <strong>/<em> a mitad del encabezado)."""
    for u in h.find_all("u"):
        u.unwrap()
    ultimo = None
    for nodo in h.descendants:
        if isinstance(nodo, NavigableString):
            ultimo = nodo
    if ultimo is not None:
        limpio = re.sub(r"[:\s]+$", "", str(ultimo))
        if limpio != str(ultimo):
            ultimo.replace_with(limpio)


def maquetar_actividad(html: str, tema: str = "", color_titulo: str = "") -> str:
    """Da forma al cuerpo de una actividad según el "Modelo de actividad".

    - El primer encabezado es el título de la actividad: va como H2 de título
      (dp-ignore-theme, centrado), no como subtítulo, y sin el prefijo
      "Actividad …:" que duplica el nombre del ítem en Canvas. Si no queda
      texto propio al sacarle el prefijo (era solo "Actividad obligatoria 1"),
      se saca directamente: el banner de la Assignment ya lo muestra.
    - Los "Título N" nativos de Word que trae el caso planteado (más
      profundos que el título de la actividad) bajan un nivel: quedan <h4>,
      no <h3>, para no competir con los rótulos de sección de abajo.
    - Los rótulos de sección (Objetivo, Consigna, Pautas de presentación,
      Criterios de evaluación, Anexo) pasan a <h3> y se les saca los dos
      puntos; si el párrafo traía el cuerpo pegado, queda debajo.
    - Un rótulo dentro del relato ("Situación de incertidumbre:") se destaca
      en línea (negrita + subrayado), sin volverse un encabezado propio.
    - El disclaimer de uso de IA va en recuadro simple.

    `color_titulo`: color del título del caso, si hay que igualarlo al de un
    texto fijo que YA trae el placeholder del aula base (p.ej. el banner
    "¡Llegaste al final!" de la AFI, que es azul #003087 siempre, sin
    importar el tema del curso). Sin esto, el color sale del tema.
    """
    if not html:
        return html
    soup = BeautifulSoup(html, "html.parser")

    # El DOCX a veces trae el rótulo genérico ("Actividad obligatoria 1", sin
    # nombre de caso) COMO SU PROPIO encabezado: no aporta nada (el banner
    # de la Assignment ya lo muestra), se decompone y ahí termina — no se
    # sigue buscando otro encabezado para promover a "título de la
    # actividad": el que sigue ("Proyecto: …") es un subtítulo del caso
    # como cualquier otro, no el título. procesar_contenido ya corrió con
    # bajar_h1_h2=False para esta actividad: llega con su nivel h1/h2
    # nativo intacto, así que el bucle de más abajo lo baja a <h3> igual que
    # cualquier otro encabezado de Word que no sea "primero" — no hace
    # falta tratarlo como caso especial acá.
    primero = soup.find(["h1", "h2", "h3", "h4"])
    if primero is not None and not primero.get("class"):
        texto = primero.get_text(" ", strip=True)
        if _PAT_TITULO_GENERICO_ACTIVIDAD.match(texto):
            primero.decompose()
        else:
            limpio = _PAT_PREFIJO_ACTIVIDAD.sub("", texto).strip()
            if limpio:
                color = color_titulo or ACENTO_POR_TEMA.get(_norm(tema or ""), ACCENT)
                primero.replace_with(BeautifulSoup(
                    _H2_TITULO_ACTIVIDAD.format(color=color, titulo=limpio),
                    "html.parser"))

    # Los <h3> que ya traía el DOCX (estilo "Título 3" de Word, el caso
    # planteado) bajan a <h4>: van antes del bucle de rótulos de sección, así
    # los <h3> que ESE bucle arma después (Objetivo/Consigna/…) no se tocan.
    # Un rótulo de sección que YA llegó como encabezado nativo en vez de
    # <p> ("Pautas de presentación:" es "Título 2" en este DOCX, y el bucle
    # de p→h3 de más abajo lo tocaría si viniera como <p>) se deja: tiene
    # que terminar en el mismo nivel que sus hermanos armados desde <p>.
    for h3 in list(soup.find_all("h3")):
        texto_h3 = h3.get_text(" ", strip=True)
        texto_sin_dp = re.sub(r"[:\s]+$", "", texto_h3)
        if _norm(texto_sin_dp) in _SECCIONES_ACTIVIDAD:
            # Rótulo de sección ya nativo (no pasa por el bucle de <p> de más
            # abajo, que es el que le saca los dos puntos a los que arrancan
            # como párrafo): se los saca acá también.
            h3.string = texto_sin_dp
            continue
        if _PAT_PREGUNTA_NUMERADA.match(texto_h3):
            # Una consigna numerada ("1. ¿Considera que…?") a veces llega
            # con estilo de título de Word (para organizarse en el propio
            # documento), pero es un ítem de la lista de preguntas de la
            # consigna, no un encabezado de caso: baja a párrafo común, no
            # a <h4> como los sub-encabezados reales del relato. El aire
            # que procesar_contenido le puso adelante (paso 5, cuando
            # todavía era un <h3> "suelto") ya no corresponde: una lista de
            # preguntas va corrida, sin separador entre cada una.
            previo = h3.previous_sibling
            while isinstance(previo, NavigableString) and not previo.strip():
                previo = previo.previous_sibling
            if _es_espaciador(previo):
                previo.decompose()
            h3.name = "p"
            continue
        _limpiar_encabezado(h3)
        h3.name = "h4"

    # Encabezados h1/h2 nativos del DOCX que no son el título de la
    # actividad (el "primero", ya resuelto arriba: decompuesto, o reemplazado
    # por el <h2 class="dp-ignore-theme"> de la plantilla propia — por eso se
    # excluye cualquiera CON clase) bajan a <h3>. Va después del bucle de
    # arriba, para que uno recién bajado a <h3> no vuelva a bajar a <h4>.
    for h in list(soup.find_all(["h1", "h2"])):
        if h.get("class"):
            continue
        _limpiar_encabezado(h)
        h.name = "h3"

    for p in list(soup.find_all("p")):
        texto = p.get_text(" ", strip=True)
        if _PAT_DISCLAIMER_IA.search(_norm(texto)):
            fragmento = BeautifulSoup(
                resaltado_simple("".join(str(x) for x in p.children)),
                "html.parser")
            nuevo = fragmento.find("div", class_="dp-callout")
            p.replace_with(nuevo)
            # Aviso de cierre: aire de párrafo completo arriba y abajo (no
            # el corto que llevaría cualquier otro recuadro simple), para
            # que se note como un aparte, no como parte del flujo del caso.
            _aire_antes(nuevo, soup)
            _aire_despues(nuevo, soup)
            continue
        m_rotulo = _PAT_ROTULO_EN_LINEA.match(texto)
        if m_rotulo:
            resto = texto[m_rotulo.end():]
            p.clear()
            p.append(BeautifulSoup(
                f"<u><strong>{m_rotulo.group(1)}:</strong></u> {resto}",
                "html.parser"))
            continue
        m = re.match(r"^([^:]{3,40}):\s*(.*)$", texto, re.S)
        if not m or _norm(m.group(1)) not in _SECCIONES_ACTIVIDAD:
            continue
        h3 = soup.new_tag("h3")
        h3.string = m.group(1).strip()
        resto = m.group(2).strip()
        p.replace_with(h3)
        if resto:
            nuevo = soup.new_tag("p")
            nuevo.string = resto
            h3.insert_after(nuevo)

    # Los rótulos de sección llevan aire arriba, tanto si vinieron de un
    # <p> "Consigna: …" como si ya eran un encabezado nativo del DOCX
    # ("Pautas de presentación").
    for h3 in soup.find_all("h3"):
        if _norm(h3.get_text(" ", strip=True)) in _SECCIONES_ACTIVIDAD:
            _aire_antes(h3, soup)

    return str(soup)


def sanear_lista_objetivos(html: str) -> str:
    """Devuelve todos los ítems de una lista a <li>.

    Si en el DOCX un objetivo quedó con estilo de título (o el asesor lo puso
    en negrita y Word lo volcó como encabezado), mammoth lo emite como
    <h3>/<h4> suelto DENTRO del <ul> y Canvas lo muestra como una titulación
    en medio de las viñetas. Todos los objetivos son ítems de la misma lista:
    cualquier encabezado hijo directo de un <ul>/<ol> se degrada a <li>.
    """
    if not html:
        return html
    soup = BeautifulSoup(html, "html.parser")
    for lista in soup.find_all(["ul", "ol"]):
        for hijo in lista.find_all(["h1", "h2", "h3", "h4", "h5", "h6"],
                                   recursive=False):
            hijo.name = "li"
            hijo.attrs = {}
            for fuerte in hijo.find_all(["strong", "b"]):
                fuerte.unwrap()
    return str(soup)


# Genially tiene dos dominios: el corto (genial.ly/…) y el de las vistas
# publicadas (view.genially.com/…), que es el que aparece en las aulas.
_PAT_GENIALLY_URL = re.compile(
    r"https?://(?:[\w-]+\.)*genial(?:\.ly|ly\.com)/[^\s\"'<>]+", re.I)
# Bloques de primer nivel que puede haber dentro de la celda de un recuadro.
_BLOQUES_CELDA = ("p", "ul", "ol", "table", "blockquote", "figure", "div",
                  "h1", "h2", "h3", "h4", "h5", "h6", "pre", "img")


def _bloques_de_celda(cell) -> list:
    """Bloques hijos directos de la celda, en orden de documento.

    No sirve `find_all("p")`: el asesor escribe el cuerpo de cada ítem como
    lista (<ul>) o hasta como tabla de datos anidada, y al recorrer solo los
    párrafos esos bloques se perdían — el panel quedaba con el título y el
    cuerpo vacío."""
    bloques = []
    for hijo in cell.children:
        nombre = getattr(hijo, "name", None)
        if nombre not in _BLOQUES_CELDA:
            continue
        if nombre == "p" and not hijo.get_text(strip=True) and not hijo.find("img"):
            continue
        bloques.append(hijo)
    return bloques


def _titulo_negrita(bloque):
    """<strong> con texto que abre un párrafo-ítem, o None."""
    if getattr(bloque, "name", None) != "p":
        return None
    strong = bloque.find("strong")
    if strong is None or not strong.get_text(strip=True):
        return None
    return strong


# Nombre del componente al principio de la línea de instrucción, con su
# paréntesis aclaratorio si lo trae ("Flips cards (una al lado de la otra)").
_PAT_NOMBRE_COMPONENTE = re.compile(
    r"^\s*(?:flips?\s*cards?|expanders?|expandibles?|acorde(?:on|ón)e?s?|"
    r"desplegables?|tabs?|solapas?|pesta(?:n|ñ)as?)\b"
    r"(?:\s*\([^)]*\))?[\s:;.,–—-]*", re.I)


def _titulo_tras_instruccion(cell) -> str:
    """Lo que el asesor escribió DESPUÉS del nombre del componente en la línea
    de instrucción ("Expander Cuatro preguntas para decidir…"): es el título
    del bloque, no parte de la indicación, y se perdía junto con la línea.

    Se exige que arranque en mayúscula: así "Tabs verticales; al hacer clic en
    cada zona…" se reconoce como lo que es, el resto de la indicación."""
    bloques = _bloques_de_celda(cell)
    if not bloques or _titulo_negrita(bloques[0]) is not None:
        return ""
    texto = bloques[0].get_text(" ", strip=True)
    resto = _PAT_NOMBRE_COMPONENTE.sub("", texto, count=1).strip()
    if resto == texto or len(resto) <= 3 or not resto[:1].isupper():
        return ""
    return resto


def _indices_de_epigrafe(bloques) -> set:
    """Índices de los bloques en negrita que NO abren un panel: el epígrafe de
    una figura o tabla ("Tabla 2") y, según APA, su línea de título justo
    debajo. Van en negrita como los títulos de panel, pero son el rótulo de
    una tabla que el asesor metió adentro del expander."""
    cuerpo = set()
    for i, b in enumerate(bloques):
        strong = _titulo_negrita(b)
        if strong is None or not _PAT_CAPTION.match(
                strong.get_text(" ", strip=True)):
            continue
        cuerpo.add(i)
        if i + 1 < len(bloques) and _titulo_negrita(bloques[i + 1]) is not None:
            cuerpo.add(i + 1)
    return cuerpo


def _grupos_por_titulo_en_negrita(cell) -> list:
    """[(título, html)] de una celda donde cada ítem abre con su título en
    negrita y sigue con el cuerpo (resto del párrafo, listas, tablas) hasta el
    próximo título en negrita. Es la convención con la que los asesores
    escriben expanders, tabs y flip cards dentro de una sola celda."""
    bloques = _bloques_de_celda(cell)
    epigrafes = _indices_de_epigrafe(bloques)

    def _abre_panel(k):
        return k not in epigrafes and _titulo_negrita(bloques[k]) is not None

    grupos, i, n = [], 0, len(bloques)
    while i < n:
        if not _abre_panel(i):     # instrucción inicial o cuerpo huérfano
            i += 1
            continue
        strong = _titulo_negrita(bloques[i])
        titulo = strong.get_text(" ", strip=True).strip(" .:–-")
        strong.extract()
        resto = re.sub(r"^[\s.:–-]+", "",
                       "".join(str(x) for x in bloques[i].children).strip())
        # Word deja un <strong> vacío tras el punto ("<strong> </strong>"):
        # tiene marcado pero no texto, así que no es cuerpo.
        piezas = ([f"<p>{resto}</p>"]
                  if BeautifulSoup(resto, "html.parser").get_text(strip=True)
                  else [])
        j = i + 1
        while j < n and not _abre_panel(j):
            piezas.append(str(bloques[j]))
            j += 1
        if titulo:
            grupos.append((titulo, "".join(piezas) or "&nbsp;"))
        i = j
    return grupos


def _tabla_a_flipcards(tabla):
    """Tabla con etiqueta 'Flip cards …' → tarjetas (frente=título en negrita,
    dorso=descripción). Se descarta el párrafo de instrucción inicial."""
    cell = tabla.find(["td", "th"])
    if cell is None:
        return None
    items = [(t, BeautifulSoup(c, "html.parser").get_text(" ", strip=True) or "&nbsp;")
             for t, c in _grupos_por_titulo_en_negrita(cell)]
    if len(items) < 2:
        return None
    return construir_flipcards(items)


def _tabla_a_acordeon(tabla, variante: str = "dp-expander-default"):
    """Tabla cuya etiqueta es 'Expander/Expandible/Acordeón' (o 'Tabs') →
    paneles CidiLabs. Cada párrafo con título en negrita abre un panel: el
    <strong> es el encabezado, y el contenido es el resto de ese párrafo MÁS
    los bloques siguientes hasta el próximo encabezado en negrita — el DOCX
    trae el cuerpo de cada ítem en párrafos y listas aparte, no en el mismo
    párrafo que el título."""
    cell = tabla.find(["td", "th"])
    if cell is None:
        return None
    titulo = _titulo_tras_instruccion(cell)
    grupos = _grupos_por_titulo_en_negrita(cell)
    if len(grupos) < 2:        # un acordeón necesita al menos 2 paneles
        return None
    encabezado = (f'<p class="lead dp-text-bold">{titulo}</p>\n'
                  if titulo else "")
    return encabezado + construir_panels(grupos, variante)


def _grupos_de_tabla_de_datos(datos) -> list:
    """[(solapa, html)] a partir de una tabla de datos: la 1ª fila son los
    encabezados y cada fila siguiente es una solapa rotulada con su primera
    celda. Es la otra forma en que el asesor entrega unas tabs: escribe la
    tabla y arriba anota 'Tabs verticales; al hacer clic en cada zona…'."""
    filas = _filas_propias(datos)
    if len(filas) < 3:          # encabezados + al menos dos solapas
        return []
    encabezados = [c.get_text(" ", strip=True)
                   for c in filas[0].find_all(["td", "th"])]
    grupos = []
    for fila in filas[1:]:
        celdas = fila.find_all(["td", "th"])
        rotulo = celdas[0].get_text(" ", strip=True) if celdas else ""
        if not rotulo:
            continue
        piezas = []
        for i, celda in enumerate(celdas[1:], start=1):
            cuerpo = BeautifulSoup("".join(str(x) for x in celda.children),
                                   "html.parser")
            if not cuerpo.get_text(strip=True):
                continue
            titulo = encabezados[i] if i < len(encabezados) else ""
            # El encabezado de la columna va PEGADO al texto, no como párrafo
            # en negrita aparte: suelto lo agarra el paso de subtítulos y una
            # columna queda con estilo de subtítulo y la otra no.
            primero = cuerpo.find("p")
            if titulo and primero is not None:
                rotulo_html = BeautifulSoup(
                    f"<strong>{titulo}.</strong> ", "html.parser")
                primero.insert(0, rotulo_html)
            elif titulo:
                cuerpo = BeautifulSoup(
                    f"<p><strong>{titulo}.</strong> {cuerpo}</p>", "html.parser")
            piezas.append(str(cuerpo))
        grupos.append((rotulo, "".join(p for p in piezas if p) or "&nbsp;"))
    return grupos if len(grupos) >= 2 else []


def _tabla_a_tabs(tabla):
    """Tabla cuya etiqueta es 'Tabs …' → solapas. La orientación la dice el
    propio asesor en la etiqueta ('Tabs verticales; …')."""
    cell = tabla.find(["td", "th"])
    if cell is None:
        return None
    ps = cell.find_all("p")
    etiqueta = _norm(ps[0].get_text(" ", strip=True)) if ps else ""
    variante = ("dp-tabs-buttons-vertical" if "vertical" in etiqueta
                else "dp-tabs-buttons")
    por_negrita = _tabla_a_acordeon(tabla, variante)
    if por_negrita:
        return por_negrita
    # Sin títulos en negrita: el contenido de las solapas viene como tabla.
    internas = [t for t in cell.find_all("table") if _columnas_propias(t) > 1]
    if len(internas) != 1:
        return None
    grupos = _grupos_de_tabla_de_datos(internas[0])
    return construir_panels(grupos, variante) if grupos else None


def bloque_recurso_incrustado(iframe_html: str = "", titulo: str = "") -> str:
    """Contenedor responsivo 16:9 para un recurso incrustado (Genially y demás).

    Es el mismo molde que usan las aulas a mano: el alto se resuelve con el
    padding-bottom del 56.25% y el iframe se estira adentro, así el recurso no
    rompe el ancho en pantalla chica.

    Sin `iframe_html` queda vacío a propósito: el pedido de Genially es un
    encargo para el diseñador, que después entrega el div para incrustar. El
    hueco marca dónde va.
    """
    interior = iframe_html or (
        f"<!-- Incrustar aquí el {titulo} -->" if titulo else
        "<!-- Incrustar aquí el recurso: el diseñador entrega el div -->")
    return ('<div style="width: 100%;" title="contenido insertado">\n'
            '<div style="position: relative; padding-bottom: 56.25%; '
            'padding-top: 0; height: 0;">\n'
            f'<div class="dp-embed-wrapper">{interior}</div>\n</div>\n</div>')


def _procesar_genially(soup):
    """Genially: si ya hay URL se incrusta; si no, queda el hueco para el div
    que entrega el diseñador. La descripción del recurso es el encargo para
    diseño y NO se copia a la página."""
    for p in list(soup.find_all(["p", "li"])):
        if p.parent is None:
            continue
        texto = p.get_text(" ", strip=True)
        if "genial" not in texto.lower():
            continue
        m = _PAT_GENIALLY_URL.search(str(p))
        if m:
            url = m.group(0).rstrip(".,;)")
            iframe = (
                '<iframe style="position: absolute; top: 0; left: 0; '
                'width: 100%; height: 100%;" title="Recurso interactivo" '
                f'src="{url}" width="1200" height="675" frameborder="0" '
                'scrolling="yes" allowfullscreen="allowfullscreen" '
                'loading="lazy"></iframe>')
            p.replace_with(BeautifulSoup(bloque_recurso_incrustado(iframe),
                                         "html.parser"))
        elif re.search(r"genial\.?ly", texto, re.I):
            p.replace_with(BeautifulSoup(
                bloque_recurso_incrustado(titulo="Genially"), "html.parser"))


# ---------------------------------------------------------------------- #
#  Figuras: estilo, centrado y texto alternativo
# ---------------------------------------------------------------------- #

# El asesor escribe el texto alternativo como un párrafo suelto debajo de la
# imagen ("Texto alternativo: Diagrama de Ishikawa…"). El estándar de la UCC
# pide que viva en el atributo alt de la figura, no como texto visible.
_PAT_ALT_PARRAFO = re.compile(
    r"^texto\s*(?:alternativo|alt)\s*[:\.]\s*(.+)$", re.I | re.S)

# Marcadores con los que el asesor pide que la figura se pueda ampliar, o que
# describen una figura densa en texto (tipo tabla): en ambos casos hace falta
# poder ampliarla para leerla, la haya pedido el asesor o no.
_FIG_EXPANDIBLE_KW = ("expandible", "expandida", "ampliable",
                      "clic para ampliar", "click para ampliar",
                      "resumen", "sintesis", "comparativo", "comparacion")


def _es_espaciador(el) -> bool:
    """¿Es un <p> de aire (&nbsp; y nada más)?"""
    return (getattr(el, "name", None) == "p"
            and el.get_text(strip=True) in ("", "\xa0")
            and not el.find("img"))


def _aire_antes(el, soup):
    previo = el.previous_sibling
    while isinstance(previo, NavigableString) and not previo.strip():
        previo = previo.previous_sibling
    if previo is not None and not _es_espaciador(previo):
        el.insert_before(BeautifulSoup("<p>&nbsp;</p>", "html.parser"))


def _aire_despues(el, soup):
    sig = el.next_sibling
    while isinstance(sig, NavigableString) and not sig.strip():
        sig = sig.next_sibling
    if sig is not None and not _es_espaciador(sig):
        el.insert_after(BeautifulSoup("<p>&nbsp;</p>", "html.parser"))


def _espaciar_figuras(soup):
    """Un párrafo de aire arriba y abajo de cada figura, con su epígrafe.

    El equipo separa SIEMPRE la figura del texto que la rodea. El aire de
    arriba va antes del epígrafe, no entre el epígrafe y la imagen.
    """
    bloques = list(soup.find_all("figure"))
    for p in soup.find_all("p"):
        img = p.find("img")
        if img is not None and _es_figura(img) and p.find_parent("figure") is None:
            bloques.append(p)
    # Una "figura" a veces es en realidad una tabla de datos (el epígrafe
    # dice "Figura N." pero el contenido es una tabla, no una imagen): recibe
    # el mismo aire, siempre que tenga encima el epígrafe que la identifica
    # como tal — así no se airean tablas de datos sueltas sin esa marca.
    for tabla in soup.find_all("table"):
        contenedor = tabla.find_parent(class_="dp-table-scroll") or tabla
        if contenedor.parent is None or contenedor in bloques:
            continue
        previo = contenedor.previous_sibling
        while isinstance(previo, NavigableString) and not previo.strip():
            previo = previo.previous_sibling
        if previo is not None and getattr(previo, "name", None) == "p" \
                and _PAT_CAPTION.match(previo.get_text(" ", strip=True)):
            bloques.append(contenedor)
    for bloque in bloques:
        if bloque.parent is None:
            continue
        _aire_despues(bloque, soup)
        # El epígrafe ("Figura N. …") es parte del bloque: el aire va antes.
        inicio = bloque
        previo = bloque.previous_sibling
        while isinstance(previo, NavigableString) and not previo.strip():
            previo = previo.previous_sibling
        if previo is not None and getattr(previo, "name", None) == "p" \
                and _PAT_CAPTION.match(previo.get_text(" ", strip=True)):
            inicio = previo
        _aire_antes(inicio, soup)


def _es_recuadro_simple(caja) -> bool:
    """Recuadro sin título ni barra lateral: el 'resaltado simple'."""
    return (caja.find(class_="card-title") is None
            and caja.find(class_="dp-callout-side-emphasis") is None)


def _aire_corto_antes(el):
    """Espaciado chico: un párrafo propio con un solo <br> adentro, más
    corto que el <p>&nbsp;</p> de aire entero.

    Antes este "shift+enter" se colgaba como <br> suelto al FINAL del
    párrafo anterior (el atajo real que usa el equipo al escribir a mano en
    el editor de Canvas). Verificado en Canvas: ese <br> final, pegado justo
    antes de un elemento de bloque (el <div> del recuadro), no siempre se
    renderiza como espacio visible — el navegador no le arma una línea con
    altura porque no hay contenido después. Un <br> como ÚNICO contenido de
    su propio <p> sí tiene garantizada esa línea (es el contenido entero de
    un bloque real, no la cola de otro).
    """
    previo = el.previous_sibling
    while isinstance(previo, NavigableString) and not previo.strip():
        previo = previo.previous_sibling
    if previo is not None and not _es_espaciador(previo):
        el.insert_before(BeautifulSoup("<p><br></p>", "html.parser"))


def _aire_corto_despues(el):
    """Espaciado chico DESPUÉS: la mitad "después" de _aire_corto_antes."""
    sig = el.next_sibling
    while isinstance(sig, NavigableString) and not sig.strip():
        sig = sig.next_sibling
    if sig is not None and not _es_espaciador(sig):
        el.insert_after(BeautifulSoup("<p><br></p>", "html.parser"))


def _vecino_real(el, atras: bool):
    """Vecino no-vacío (salteando texto en blanco y párrafos de aire) hacia
    atrás o hacia adelante."""
    vecino = el.previous_sibling if atras else el.next_sibling
    while isinstance(vecino, NavigableString) and not vecino.strip():
        vecino = vecino.previous_sibling if atras else vecino.next_sibling
    while vecino is not None and _es_espaciador(vecino):
        vecino = vecino.previous_sibling if atras else vecino.next_sibling
    return vecino


def _encerrado_entre_texto(caja) -> bool:
    """¿El recuadro interrumpe un tramo de texto corrido —un párrafo/lista
    ANTES y otro DESPUÉS, sin que abra ni cierre una sección (encabezado) ni
    esté pegado a otro componente armado? Ahí el párrafo entero de aire se ve
    exagerado: lleva el mismo espaciado corto que el recuadro simple.
    """
    def _es_texto(vecino):
        return vecino is not None and getattr(vecino, "name", None) in ("p", "ul", "ol")
    return _es_texto(_vecino_real(caja, atras=True)) \
        and _es_texto(_vecino_real(caja, atras=False))


def _espaciar_recuadros(soup):
    """Aire alrededor de los recuadros.

    El recuadro con título (Profundización, Atención, Ejemplos…) se separa con
    un párrafo entero — salvo que quede encerrado entre texto corrido (ver
    _encerrado_entre_texto), donde ese aire se ve exagerado y lleva el mismo
    espaciado corto que el recuadro simple. El simple SIEMPRE lleva el
    espaciado menor —el shift+enter del equipo—, para que no quede tan
    despegado del texto que lo rodea.
    """
    for caja in soup.find_all("div", class_="dp-callout"):
        if caja.parent is None or caja.find_parent(class_="dp-callout"):
            continue
        if _es_recuadro_simple(caja):
            _aire_corto_antes(caja)
            _aire_corto_despues(caja)
        elif _encerrado_entre_texto(caja):
            _aire_corto_antes(caja)
            _aire_corto_despues(caja)
        else:
            _aire_antes(caja, soup)
            _aire_despues(caja, soup)

    # "Laboratorio de ideas" no es un dp-callout (es un dp-content-block, el
    # mismo molde que el "Lecture Hook"), pero siempre lleva título: le
    # corresponde el mismo aire de párrafo entero que a un recuadro con
    # título, no el espaciado corto del simple.
    for caja in soup.find_all("div", attrs={"data-title": "Lecture Hook"}):
        if caja.parent is None:
            continue
        _aire_antes(caja, soup)
        _aire_despues(caja, soup)


def _agrandar_intro_subrayada_de_panel(soup):
    """El primer párrafo de un panel, si está TODO subrayado, es la bajada
    del título (p.ej. "La calidad como responsabilidad de toda la
    organización" abriendo el panel "Calidad Total"): letra un poco más
    grande y en negrita, igual que cualquier otra bajada del catálogo
    (subtítulo dentro de un recuadro, pregunta organizadora dentro de un
    panel) — sigue siendo párrafo, no un título de sección."""
    for contenido in soup.find_all("div", class_="dp-panel-content"):
        p = contenido.find("p", recursive=False)
        if p is None:
            continue
        texto = p.get_text(" ", strip=True)
        us = p.find_all("u")
        if not texto or not us:
            continue
        if _norm(" ".join(u.get_text(" ", strip=True) for u in us)) != _norm(texto):
            continue
        clases = p.get("class") or []
        for clase in ("lead", "dp-text-bold"):
            if clase not in clases:
                clases = clases + [clase]
        p["class"] = clases


def _desheadear_dentro_de_panel(soup):
    """Un <hN> nativo de Word (estilo "Subtitle") que queda DENTRO del cuerpo
    de un panel —no es el título que lo abre, sino una pregunta o subtítulo
    que organiza esa sección del contenido ("¿Cuándo conviene utilizar
    Ishikawa?")— no debe competir con la jerarquía de encabezados de la
    página: pasa a párrafo destacado (negrita, letra un poco más grande),
    igual que las bajadas de panel y los subtítulos dentro de un recuadro.

    Solo se demota el <hN> que NO abre el panel (`_es_encabezado_de_seccion`
    con modo="subrayado" ya lo excluyó de abrir uno nuevo; acá se limpia el
    que quedó, verbatim, adentro del <div class="dp-panel-content">)."""
    for contenido in soup.find_all("div", class_="dp-panel-content"):
        for h in contenido.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]):
            p = soup.new_tag("p")
            p["class"] = ["lead", "dp-text-bold"]
            for hijo in list(h.children):
                p.append(hijo.extract())
            h.replace_with(p)


def _espaciar_destacados(soup):
    """Aire arriba de la frase destacada (estilo lead), no abajo.

    Es una bajada/etiqueta —nombra lo que sigue ("¿Cuándo conviene utilizar
    Ishikawa?", "Enfoque al cliente")—, no un párrafo suelto: separarla del
    texto que la precede tiene sentido, pero separarla de SU PROPIA
    explicación (que va justo debajo) se ve como un corte en el medio de la
    misma idea. Verificado en Canvas."""
    for p in soup.find_all("p", class_="lead"):
        if p.parent is None or "dp-text-bold" not in (p.get("class") or []):
            continue
        _aire_antes(p, soup)


def _introducido_por_dos_puntos(p) -> bool:
    """¿El párrafo anterior termina en ':' y por lo tanto lo está presentando?

    Sirve para no confundir una frase destacada con un subtítulo: "Esta
    evolución puede resumirse como un desplazamiento progresivo:" seguido de
    "detectar defectos → controlar procesos → …" en negrita es contenido, no
    un título de sección.
    """
    anterior = p.find_previous_sibling()
    while anterior is not None and getattr(anterior, "name", None) not in (
            "p", "li", "h1", "h2", "h3", "h4", "h5", "h6", "ul", "ol", "table"):
        anterior = anterior.find_previous_sibling()
    if anterior is None or getattr(anterior, "name", None) not in ("p", "li"):
        return False
    return anterior.get_text(" ", strip=True).endswith(":")


def _es_figura(img) -> bool:
    """Imagen de contenido: no un icono de recuadro ni un SVG decorativo."""
    src = img.get("src", "")
    if "/Iconos/" in src or src.endswith(".svg"):
        return False
    if img.find_parent(class_="card-title") or img.find_parent(class_="dp-callout"):
        return False
    return True


def _figura_vecina(p):
    """Figura más cercana al párrafo: primero hacia arriba (el 'Texto
    alternativo' suele ir debajo de la imagen), después hacia abajo.

    Devuelve la imagen, o la tabla cuando la "figura" es una tabla de datos
    (hay epígrafes 'Figura N.' que refieren a una tabla, no a una imagen).
    """
    for buscar in (p.find_previous_siblings, p.find_next_siblings):
        for vecino in list(buscar())[:3]:
            if getattr(vecino, "name", None) == "img":
                if _es_figura(vecino):
                    return vecino
            elif getattr(vecino, "find", None) is not None:
                img = vecino.find("img")
                if img is not None and _es_figura(img):
                    return img
                tabla = (vecino if getattr(vecino, "name", None) == "table"
                         else vecino.find("table"))
                if tabla is not None:
                    return tabla
    return None


# "Nota. Figura elaborada con base en …": el pie de fuente de la figura. No es
# un párrafo del contenido: va como <figcaption> dentro del <figure>, y la
# palabra "Nota." se cae (el equipo la saca al maquetar).
_PAT_NOTA_FIGURA = re.compile(r"^nota\s*[\.:]\s*(.+)$", re.I | re.S)


def _nota_suelta_en_negrita(soup):
    """Una 'Nota:' que no es el pie de una figura (_nota_a_figcaption ya se
    llevó esas) es contenido válido tal cual está, en el cuerpo de la
    página — solo en negrita, sin centrar ni encuadrar: pedido explícito del
    usuario ("está bien que esté dentro del contenido")."""
    for p in soup.find_all("p"):
        if p.find_parent(class_=("dp-callout", "dp-panels-wrapper")):
            continue
        if p.find("strong") or p.find("img"):
            continue
        texto = p.get_text(" ", strip=True)
        if not _PAT_NOTA_FIGURA.match(texto):
            continue
        strong = soup.new_tag("strong")
        for hijo in list(p.children):
            strong.append(hijo)
        p.append(strong)


def _nota_a_figcaption(soup):
    """Imagen + 'Nota. …' → <figure> con <figcaption>.

    El pie de fuente queda pegado a la figura en vez de suelto como un párrafo
    más del texto, y la figura pasa a ser un <figure> de verdad.
    """
    for p in list(soup.find_all("p")):
        texto = p.get_text(" ", strip=True)
        m = _PAT_NOTA_FIGURA.match(texto)
        if not m:
            continue
        img = _figura_vecina(p)
        if img is None:
            continue

        contenedor = img.find_parent("p") or img
        fig = soup.new_tag("figure")
        # bs4 devuelve la clase como lista o como string según cómo se haya
        # seteado; se normaliza a lista antes de sumarle nada.
        clases = img.get("class") or []
        if isinstance(clases, str):
            clases = clases.split()
        # mx-auto d-block centra la CAJA de la figura. Sin eso queda pegada a
        # la izquierda por más text-align que tenga: el text-align solo alinea
        # lo de adentro, no el <figure>, que es un bloque de ancho fijo.
        fig["class"] = (["mx-auto", "d-block"]
                        + (clases or _FIG_CLASES_ESTATICA.split()))
        fig["style"] = "width: 700px; height: auto; text-align: center;"

        cap = soup.new_tag("figcaption")
        interior = BeautifulSoup(
            f'<span style="font-size: 10pt;"><strong>{m.group(1).strip()}</strong>'
            "</span>", "html.parser")
        cap.append(interior)

        contenedor.insert_before(fig)
        fig.append(img.extract())
        img["class"] = ""
        fig.append(cap)
        if contenedor is not img and not contenedor.get_text(strip=True)                 and not contenedor.find("img"):
            contenedor.decompose()
        p.decompose()
        fig.insert_after(BeautifulSoup("<p>&nbsp;</p>", "html.parser"))


def _alt_parrafo_a_atributo(soup):
    """Mueve los párrafos 'Texto alternativo: …' al alt de la figura vecina.

    Pisa el alt que hubiera: `reemplazar_figuras_diseno` deja el epígrafe como
    alt de arranque, pero si el asesor escribió un texto alternativo explícito
    ese manda. El párrafo se elimina siempre que haya figura a la que pegarlo:
    es una instrucción de maquetación, no contenido de la página.
    """
    for p in list(soup.find_all("p")):
        m = _PAT_ALT_PARRAFO.match(p.get_text(" ", strip=True))
        if not m:
            continue
        alt = " ".join(m.group(1).split()).strip(" .;")
        figura = _figura_vecina(p) if alt else None
        if figura is None:
            continue
        if figura.name == "table":
            # Una tabla no lleva alt: el equivalente accesible es aria-label.
            figura["aria-label"] = alt
        else:
            figura["alt"] = alt
        p.decompose()


def _figura_es_expandible(img) -> bool:
    """Solo si el asesor lo pidió explícitamente cerca de la figura."""
    if img.has_attr("data-ampliable"):
        # El pedido vino por comentario del DOCX clavado sobre la imagen
        # ("incluir pop up para ampliar"), no por el texto que la rodea:
        # aplicar_comentarios dejó la marca acá.
        del img["data-ampliable"]
        return True
    contenedor = img.find_parent("p") or img.parent
    trozos = [img.get("alt", "")]
    if contenedor is not None:
        for vecino in list(contenedor.find_next_siblings())[:2]:
            trozos.append(vecino.get_text(" ", strip=True))
        for vecino in list(contenedor.find_previous_siblings())[:2]:
            trozos.append(vecino.get_text(" ", strip=True))
    texto = _norm(" ".join(t for t in trozos if t))
    return any(kw in texto for kw in _FIG_EXPANDIBLE_KW)


# Rótulos de la tabla de portada que traen las plantillas de los asesores.
_ROTULOS_PLANTILLA = ("unidad academica", "carrera", "nombre de la carrera",
                      "asignatura", "docente", "modalidad", "ciclo lectivo",
                      "ano lectivo", "nombre del modulo")


def quitar_encabezado_plantilla(soup) -> bool:
    """Saca la portada de la plantilla del DOCX del arranque del contenido.

    Los asesores escriben sobre una plantilla que abre con el título del ítem
    y una tabla de metadatos (Unidad académica / Carrera / Asignatura). Eso es
    la carátula del formulario, no contenido: el foro tiene que empezar en
    "¡Hola a todos!". Solo se mira el ARRANQUE, para no borrar una tabla de
    datos que esté más abajo.
    """
    primeros = [e for e in soup.find_all(True, recursive=False)][:4]
    tabla = next((e for e in primeros
                  if e.name == "table" or (e.name == "div" and e.find("table"))),
                 None)
    if tabla is None:
        return False
    real = tabla if tabla.name == "table" else tabla.find("table")
    rotulos = [_norm(c.get_text(" ", strip=True))
               for f in real.find_all("tr") for c in f.find_all(["td", "th"])[:1]]
    if not rotulos or sum(r in _ROTULOS_PLANTILLA for r in rotulos) < 2:
        return False

    # El título que la precede repite el nombre del ítem: también sobra.
    previo = tabla.find_previous_sibling()
    if previo is not None and previo.name in ("h1", "h2", "h3", "h4", "p") \
            and len(previo.get_text(" ", strip=True)) <= 60:
        previo.decompose()
    tabla.decompose()
    return True


def estilar_tabla_datos(tabla, tema: str = "") -> None:
    """Tabla de datos del DOCX → estilo institucional UCC.

    Venía como una tabla pelada con `border="1"`: sin barra de encabezado, sin
    filas alternadas y sin contenedor, así que en pantalla chica rompía el
    ancho de la página.
    """
    cabecera = CABECERA_TABLA_POR_TEMA.get(_norm(tema or ""),
                                           CABECERA_TABLA_POR_TEMA["posgrado"])
    tabla["class"] = _TABLA_CLASES
    tabla["style"] = _TABLA_ESTILO
    if tabla.has_attr("border"):
        del tabla["border"]

    filas = tabla.find_all("tr")
    if not filas:
        return

    # La primera fila es el encabezado: si el DOCX no trajo <thead>, se arma.
    encabezado = filas[0]
    thead = encabezado.find_parent("thead")
    if thead is None:
        thead = BeautifulSoup("<thead></thead>", "html.parser").thead
        encabezado.insert_before(thead)
        thead.append(encabezado.extract())
    else:
        # Mammoth a veces mete TODAS las filas en el <thead>: solo la primera
        # es encabezado, el resto es cuerpo (si no, se pintan como títulos).
        cuerpo = tabla.find("tbody")
        for fila in thead.find_all("tr")[1:]:
            if cuerpo is None:
                cuerpo = BeautifulSoup("<tbody></tbody>", "html.parser").tbody
                thead.insert_after(cuerpo)
            for celda in fila.find_all("th"):
                celda.name = "td"
            cuerpo.append(fila.extract())
    encabezado["style"] = (f"background-color: {cabecera}; color: #ffffff; "
                           "height: 60px;")
    for celda in encabezado.find_all(["td", "th"]):
        celda.name = "th"
        celda["scope"] = "col"
        celda["class"] = "align-middle text-center"
        celda["style"] = "text-align: left; padding: 12px 16px;"

    for i, fila in enumerate(filas[1:]):
        fila["style"] = ("background-color: "
                         + (_TABLA_FILA_PAR if i % 2 == 0 else _TABLA_FILA_IMPAR)
                         + ";")
        for celda in fila.find_all(["td", "th"]):
            celda["class"] = "align-middle text-center"
            celda["style"] = f"padding: 12px 16px; {_TABLA_BORDE_CELDA}"

    # Contenedor con scroll horizontal: en el celular la tabla no rompe la caja.
    if tabla.find_parent(class_="dp-table-scroll") is None:
        cont = BeautifulSoup('<div class="dp-table-scroll"></div>',
                             "html.parser").div
        tabla.wrap(cont)


_PAT_ATRIB_ESTILO = re.compile(r'style="([^"]*)"')


def aplicar_acento_del_tema(html: str, tema: str) -> str:
    """Repinta los snippets con el color institucional del aula base.

    Educación usa #003087 y posgrado #1b1e31. Solo se toca el color dentro de
    atributos style=, para no reemplazar nada del texto del asesor.
    """
    acento = ACENTO_POR_TEMA.get(_norm(tema or ""))
    if not acento or acento == ACCENT or not html:
        return html
    return _PAT_ATRIB_ESTILO.sub(
        lambda m: 'style="' + m.group(1).replace(ACCENT, acento) + '"', html)


def procesar_contenido(html: str, tema: str = "", bajar_h1_h2: bool = True) -> str:
    """`bajar_h1_h2=False` (actividades): maquetar_actividad necesita el
    nivel NATIVO h1/h2 vs h3 del DOCX para distinguir el título del caso
    ("Proyecto: …", Heading 2) de sus sub-encabezados ("Contexto del
    proyecto", Heading 3) — bajarlos acá los aplana a los dos al mismo
    <h3> y esa distinción se pierde antes de que maquetar_actividad pueda
    usarla."""
    if not html:
        return html
    soup = BeautifulSoup(html, "html.parser")

    # 0. Anclas internas de Word/Google Docs (ruido de la conversión).
    for a in soup.find_all("a"):
        if not a.get("href") and not a.get_text(strip=True) and not a.find("img"):
            a.unwrap() if a.contents else a.decompose()

    # 0.2 Encabezados vacíos: un "Título 3" de Word que solo queda como
    #     marcador de posición (sin texto, apenas el ancla que el paso
    #     anterior ya sacó) se convierte en un <h3></h3> hueco que se ve como
    #     un salto de línea/aire raro en medio del contenido.
    for h in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]):
        if not h.get_text(strip=True) and not h.find("img"):
            h.decompose()

    # 0.3 Marcado vacío de Word: al escribir "<strong>Título</strong>.<strong>
    #     </strong>Texto" queda un resaltado que solo contiene un espacio. No
    #     se ve, pero ensucia el HTML y aparece al principio del cuerpo de
    #     cada panel de un expander/tabs.
    for inline in soup.find_all(["strong", "b", "em", "i", "u"]):
        if not inline.get_text(strip=True) and not inline.find("img"):
            inline.unwrap()

    # 0.35 Nombre de archivo suelto ("EP - AFI.docx"): el asesor anota al pie
    #      del recuadro a qué entregable apunta el enlace. Es una nota para
    #      maquetación y se estaba publicando en la página del estudiante.
    for p in list(soup.find_all(["p", "li"])):
        if p.find("img") is not None \
                or not _PAT_SOLO_ARCHIVO.match(p.get_text(" ", strip=True)):
            continue
        # Un archivo que SÍ se publica va enlazado al archivo subido al aula:
        # ese no se toca. El del asesor apunta al Drive de asesoría.
        if any("IMS-CC-FILEBASE" in (a.get("href") or "") for a in p.find_all("a")):
            continue
        p.decompose()

    # 0.4 Carátula de la plantilla del DOCX (título + tabla de metadatos): es
    #     el formulario, no el contenido.
    quitar_encabezado_plantilla(soup)

    # 0.5 Genially: incrustar (URL) o marcar para incrustar (descripción).
    _procesar_genially(soup)

    # 1.0 Las tablas de datos anidadas (el asesor mete una tabla adentro de un
    #     expander o de una caja) se estilan ANTES: en cuanto se reemplaza la
    #     tabla contenedora, las de adentro quedan fuera del árbol y cualquier
    #     cambio posterior ya no llega a la salida.
    for interna in soup.find_all("table"):
        if interna.find_parent("table") is not None \
                and _columnas_propias(interna) > 1:
            estilar_tabla_datos(interna, tema)

    # 1. Tablas → acordeón ('Expander'), tabs, recuadro (1 col) o tabla de datos
    for tabla in soup.find_all("table"):
        if tabla.find_parent("table") is not None:
            continue                     # ya se resolvió con su contenedora
        primer = tabla.find(["td", "th"])
        etiqueta = _norm(primer.get_text(" ", strip=True)) if primer else ""
        if etiqueta.startswith(_FLIP_KW):
            flip = _tabla_a_flipcards(tabla)
            if flip:
                tabla.replace_with(BeautifulSoup(flip, "html.parser"))
                continue
        if etiqueta.startswith(_EXPANDER_KW):
            acordeon = _tabla_a_acordeon(tabla)
            if acordeon:
                tabla.replace_with(BeautifulSoup(acordeon, "html.parser"))
                continue
        if etiqueta.startswith(_TABS_KW):
            tabs = _tabla_a_tabs(tabla)
            if tabs:
                tabla.replace_with(BeautifulSoup(tabs, "html.parser"))
                continue
        if _columnas_propias(tabla) == 1:
            if _es_envoltorio_de_figura(tabla):
                # Tabla sin bordes que solo sostiene la figura con su
                # epígrafe y su nota: no es un recuadro. Encuadrarla mete la
                # imagen adentro de un dp-callout, y ahí _es_figura la
                # descarta: la figura se queda sin ancho, sin borde y sin
                # poder ampliarse. Se desarma y el contenido sigue el
                # camino normal de las figuras.
                _desarmar_tabla(tabla)
                continue
            nuevo = _tabla_a_recuadro(tabla)
            if nuevo:
                tabla.replace_with(BeautifulSoup(nuevo, "html.parser"))
        else:
            estilar_tabla_datos(tabla, tema)

    # 1.5 Citas (estilo Quote de Word) → resaltado simple.
    #     Si el comentario del asesor ya pidió recuadro sobre el párrafo de
    #     adentro, la cita YA quedó encuadrada: volver a envolverla dejaba un
    #     recuadro dentro de otro (se veía como el recuadro "puesto doble").
    for bq in soup.find_all("blockquote"):
        if bq.find(class_="dp-callout"):
            bq.unwrap()
            continue
        inner = "".join(str(x) for x in bq.children).strip()
        if inner:
            bq.replace_with(BeautifulSoup(resaltado_simple(inner), "html.parser"))

    # 1.55 Definición citada (APA) justo debajo de un encabezado-pregunta
    #      ("¿Qué es…?"): cita textual con sangría doble, sin caja.
    _definiciones_citadas_tras_pregunta(soup)

    # 1.6 Párrafos con frases-señal → recuadros (Lectura / Video / Atención)
    _procesar_cues_parrafo(soup)

    # 1.65 El mismo texto encuadrado dos veces. Pasa cuando llega por dos
    #      caminos (una cita del DOCX y un comentario que pide resaltarlo, por
    #      ejemplo) y cada uno arma su recuadro. Queda uno solo, esté el
    #      segundo al lado o metido adentro del primero.
    for caja in list(soup.find_all("div", class_="dp-callout")):
        if caja.parent is None:
            continue
        texto = caja.get_text(" ", strip=True)

        # Anidado: el de adentro dice lo mismo → se queda el de adentro, que
        # es el que tiene el estilo que pidió el comentario.
        dentro = caja.find("div", class_="dp-callout")
        if dentro is not None and dentro.get_text(" ", strip=True) == texto:
            caja.replace_with(dentro.extract())
            continue

        # Al lado.
        sig = caja.find_next_sibling()
        while sig is not None and _es_espaciador(sig):
            sig = sig.find_next_sibling()
        if sig is not None and "dp-callout" in (sig.get("class") or []) \
                and sig.get_text(" ", strip=True) == texto:
            sig.decompose()


    # 1.7 Encabezados reales de Word (estilo "Título 1"/"Título 2") dentro
    # del cuerpo → <h3>. El título de la página en Canvas ya cumple el rol
    # de encabezado principal; cualquier subtítulo numerado interno es
    # siempre h3, tanto si el asesor lo marcó en negrita (ver paso 2) como
    # si usó el estilo de título de Word (mammoth lo vuelca tal cual a
    # <h1>/<h2>, sin bajarlo de nivel). Las actividades (bajar_h1_h2=False)
    # se saltan este paso: maquetar_actividad hace su propio manejo de
    # niveles, más fino, y necesita el h1/h2 nativo para eso.
    for h in soup.find_all(["h1", "h2"]) if bajar_h1_h2 else []:
        # El h2 con ícono no es un encabezado del contenido: es el divisor de
        # sección que arma el propio generador (bloque de video, por ejemplo).
        if "dp-has-icon" in (h.get("class") or []):
            continue
        for strong in h.find_all(["strong", "b"]):
            strong.unwrap()
        h.name = "h3"

    # 2. Subtítulos en negrita → <h3> (el dp-wrapper los estiliza). Solo
    # texto SUELTO del flujo principal — no el cuerpo de un componente que
    # otro paso ya armó (recuadro/flip-card): ahí "en negrita y corto" puede
    # ser contenido legítimo (p.ej. el placeholder de Genially), no un
    # subtítulo, y convertirlo duplicaba el título del recuadro.
    # Dentro de un acordeón/tabs (dp-panels-wrapper) el mismo patrón SÍ es un
    # sub-subtítulo real (p.ej. "Gestión ambiental" abriendo el panel de ISO
    # 14001), pero nunca se promueve a <h3>: compite con el propio título del
    # panel (dp-panel-heading). Ahí queda "lead" + negrita, más grande pero
    # sin asumir la categoría de encabezado — como el resto del catálogo.
    for p in soup.find_all("p"):
        en_panel = p.find_parent(class_="dp-panels-wrapper") is not None
        if p.find_parent(class_=("dp-callout", "dp-flip-card-deck",
                                  "dp-front-card", "dp-back-card")):
            continue
        if p.find_parent(["td", "th"]):
            # Una celda de tabla en negrita es un encabezado de columna, no
            # un subtítulo de la página (pasaba con "Tipo de inconveniente",
            # que terminaba de <h3>/<h4> adentro de la propia celda).
            continue
        strongs = p.find_all("strong")
        if not strongs:
            continue
        texto = p.get_text(" ", strip=True)
        texto_strong = " ".join(s.get_text(" ", strip=True) for s in strongs)
        if (texto and texto == texto_strong and 10 <= len(texto) <= 90
                and not texto.endswith(":") and not _NO_H3.match(texto)
                and not p.find("img")):
            if en_panel or _introducido_por_dos_puntos(p):
                # El párrafo anterior termina en ":" (esto es lo que estaba
                # introduciendo, no un subtítulo nuevo) o el párrafo vive
                # dentro de un panel (nunca se promueve a heading ahí): queda
                # como párrafo destacado (estilo lead, en negrita), que es
                # como lo maqueta el equipo a mano.
                p["class"] = (p.get("class") or []) + ["lead", "dp-text-bold"]
                continue
            h3 = soup.new_tag("h3")
            h3.string = texto
            p.replace_with(h3)

    # 3. Imágenes de contenido → estilo figura CidiLabs
    #    (los iconos SVG de los recuadros NO son figuras)
    #    Primero el texto alternativo que el asesor dejó como párrafo suelto:
    #    va al atributo alt, así la figura queda accesible y el texto deja de
    #    verse como contenido de la página.
    _alt_parrafo_a_atributo(soup)

    # Marcador de video suelto ("VIDEO 2") que no quedó pegado a ninguna
    # invitación: señala que ahí va un video de Canvas Studio. Se convierte en
    # el bloque vacío, nunca se publica como texto. Si en la página YA hay un
    # bloque de video más arriba (en cualquier parte, no solo el hermano
    # inmediato) es un segundo marcador del mismo video que quedó duplicado
    # por error en el DOCX — se saca, no se arma un segundo hueco vacío.
    for p in list(soup.find_all("p")):
        if not _PAT_MARCADOR_VIDEO.match(p.get_text(" ", strip=True)):
            continue
        ya_hay_bloque = p.find_previous(attrs={"data-title": "Video"}) is not None
        if ya_hay_bloque:
            p.decompose()
        else:
            p.replace_with(BeautifulSoup(bloque_video_studio(), "html.parser"))

    for img in soup.find_all("img"):
        if not _es_figura(img):
            continue
        clases = img.get("class", [])
        ya_estilada = any(c == "dp-popup-image" or c.startswith("dp-image-")
                          for c in clases)
        if not ya_estilada:
            expandible = _figura_es_expandible(img)
            img["class"] = (_FIG_CLASES_EXPANDIBLE if expandible
                            else _FIG_CLASES_ESTATICA)
            if not img.get("style"):
                # 700px para estática y ampliable por igual (ver la misma
                # nota en reemplazar_figuras_diseno).
                img["style"] = "width: 700px; height: auto;"
        # Centrar el párrafo contenedor aunque Word haya envuelto la imagen en
        # <strong>/<span>: hay que subir hasta el <p>, no mirar el padre directo.
        contenedor = img.find_parent("p")
        if contenedor is not None:
            contenedor["style"] = "text-align: center;"

    # Con las figuras ya estiladas: el pie de fuente pasa a <figcaption> y las
    # clases se mudan al <figure> (la imagen queda limpia, como a mano).
    _nota_a_figcaption(soup)
    _nota_suelta_en_negrita(soup)
    _espaciar_figuras(soup)
    _espaciar_recuadros(soup)
    _agrandar_intro_subrayada_de_panel(soup)
    _desheadear_dentro_de_panel(soup)
    _espaciar_destacados(soup)

    # 3.5 Enlaces: URLs sueltas → <a>; todo enlace externo con el estilo
    #     institucional (inline_disabled dp-ext-ignore, target _blank)
    _autolink_urls(soup)
    for a in soup.find_all("a"):
        href = a.get("href", "")
        if href.startswith("http"):
            a["class"] = "inline_disabled dp-ext-ignore"
            a["target"] = "_blank"
    # Párrafos que son solo un link largo → estilo de bibliografía
    for p in soup.find_all("p"):
        hijos = [x for x in p.children
                 if getattr(x, "name", None) or str(x).strip()]
        if len(hijos) == 1 and getattr(hijos[0], "name", "") == "a" \
                and len(hijos[0].get_text(strip=True)) > 40:
            p["class"] = "text-break"
            p["style"] = "margin: 0; padding: 0;"

    # 3.6 Cita/mención + link suelto (no epígrafe, no párrafo-solo-link) →
    #     CTA 'Descubrí leyendo' con 'Acceso al documento' en vez de la URL.
    _procesar_citas_con_link(soup)
    # Este recuadro se arma DESPUÉS del paso 3 (_espaciar_recuadros): sin este
    # segundo pasaje se quedaba sin el aire de párrafo completo que llevan
    # todos los recuadros con título (pasaba en Bibliografía, con el "Descubrí
    # leyendo" pegado a las referencias antes y después).
    _espaciar_recuadros(soup)

    # 4. Epígrafes (Figura N.) → centrados, tamaño 10pt. Una "Nota:" que NO
    # es el pie de una figura (esas ya se consumieron en _nota_a_figcaption,
    # que las decompone) es contenido normal, no un epígrafe — ya la dejó
    # en negrita _nota_suelta_en_negrita más arriba; centrarla y encajarla
    # como epígrafe encima de eso duplicaba el estilo y la descuadraba.
    for p in soup.find_all("p"):
        texto = p.get_text(" ", strip=True)
        if _PAT_CAPTION.match(texto):
            p["class"] = "dp-heading-ignore"
            p["style"] = "text-align: center;"
            inner = f'<span style="font-size: 10pt;"><strong>{texto}</strong></span>'
            p.clear()
            p.append(BeautifulSoup(inner, "html.parser"))

    # 5. Espaciador antes de subtítulos sueltos (h3/h4 sin clase — de los
    # pasos 1.7 y 2, o el sub-subtítulo que arma docx_comments; no los
    # card-title/dp-panel-heading de componentes): el equipo SIEMPRE separa
    # un subtítulo del párrafo anterior con <p>&nbsp;</p>, salvo que sea el
    # primer elemento de la página. Alcanza también al h4: el sub-subtítulo
    # se marca igual que el subtítulo, solo cambia el nivel de encabezado.
    # El bloque "Video" (cuando queda abierto, ver separar_bloque_de_video)
    # no es un componente aislado: es el resto del FLUJO de la página que
    # cayó adentro por quedar después del marcador de video. Un subtítulo
    # que aterriza ahí (p.ej. "Conclusión", o cualquier encabezado que
    # siga al video) tiene que espaciarse igual que uno a nivel de página.
    _bloque_video = soup.find("div", attrs={"data-title": "Video"}, recursive=False)
    for hx in soup.find_all(["h3", "h4"], class_=lambda c: not c):
        if hx.parent is not soup and hx.parent is not _bloque_video:
            continue
        anterior = hx.previous_sibling
        while isinstance(anterior, NavigableString) and not anterior.strip():
            anterior = anterior.previous_sibling
        if anterior is None:
            continue
        ya_espaciado = (getattr(anterior, "name", None) == "p"
                        and anterior.get_text(strip=True) in ("", "\xa0")
                        and not anterior.find("img"))
        if not ya_espaciado:
            hx.insert_before(BeautifulSoup("<p>&nbsp;</p>", "html.parser"))

    return aplicar_acento_del_tema(str(soup), tema)


def separar_bloque_de_video(html: str) -> tuple:
    """El bloque "Video" (bloque_video_studio, cuando queda abierto y
    absorbe el resto de la página — ver _procesar_cues_parrafo) NO va
    anidado dentro del content-block de lectura de la página: el equipo a
    mano cierra ese div y abre uno NUEVO y propio para el video, como
    hermano al mismo nivel, no metido adentro. procesar_contenido no puede
    devolver eso directamente (su salida entera queda embebida dentro de UN
    solo content-block en la plantilla de la página) — se lo separa acá.

    Devuelve (resto_del_contenido, bloque_de_video_o_cadena_vacia).
    """
    soup = BeautifulSoup(html, "html.parser")
    bloque = soup.find("div", attrs={"data-title": "Video"}, recursive=False)
    if bloque is None:
        return html, ""
    # El molde de la página SIEMPRE cierra con un <p>&nbsp;</p> de aire antes
    # del borde del content-block — pero ese trailing spacer va después de
    # {resto}, no del bloque de video. Si el video absorbió el resto de la
    # página (ver _procesar_cues_parrafo), lo último que queda adentro es el
    # cierre del CONTENIDO, no el del molde: sin este spacer, la página
    # terminaba pegada al borde del bloque en vez de con el mismo aire que
    # cualquier otra.
    ultimo = bloque.find_all(recursive=False)[-1] if bloque.find_all(recursive=False) else None
    if not (ultimo is not None and _es_espaciador(ultimo)):
        bloque.append(BeautifulSoup("<p>&nbsp;</p>", "html.parser"))
    bloque_html = str(bloque.extract())
    return str(soup), bloque_html
