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
from maquetador.build.componentes_asesor import construir_flipcards, construir_panels

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


# Marcador que deja el asesor donde va un video propio ("VIDEO M2.", "VIDEO 2").
# A veces es un párrafo suelto y a veces queda pegado al final de la invitación.
_PAT_MARCADOR_VIDEO = re.compile(r"^\s*videos?\s*(?:m\s*)?\d*\s*[\.:]?\s*$", re.I)
_PAT_MARCADOR_VIDEO_FINAL = re.compile(
    r"\s*\bvideos?\s*(?:m\s*)?\d*\s*\.?\s*(?=</|$)", re.I)


def _sin_marcador_video(html: str) -> str:
    """Saca el marcador de video del final del párrafo, si quedó ahí."""
    return _PAT_MARCADOR_VIDEO_FINAL.sub("", html, count=1)


def bloque_video_studio(body_html: str = "") -> str:
    """Bloque de video propio de la UCC (Canvas Studio).

    Los videos de desarrollo / introducción / conceptuales NO son un CTA: no
    mandan a YouTube, se suben a Canvas Studio y se incrustan. Como el id del
    video recién existe cuando alguien lo sube —después de generar el aula— el
    bloque queda armado y vacío, listo para pegar el embed.
    """
    intro = f'{body_html}<p>&nbsp;</p>' if body_html else ""
    return f"""<div class="dp-content-block" data-title="Video" data-category="+UCC">
<h2 class="dp-has-icon"><i class="dp-icon fab fa-youtube" aria-hidden="true"><span class="dp-icon-content" style="display: none;">&nbsp;</span></i></h2>
{intro}<div class="dp-embed-wrapper mx-auto d-block" style="text-align: center;"><!-- Pegar aquí el embed de Canvas Studio --></div>
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


def resaltado_ejemplo(body_html: str, titulo: str = "Ejemplo que iluminan") -> str:
    return f"""<div class="dp-callout dp-callout-placeholder card dp-callout-position-default dp-callout-color-dp-primary dp-callout-type-info">
<div class="dp-callout-side-emphasis"><i class="fas fa-copy dp-default-icon">​</i></div>
<div class="card-body">
<h3 class="card-title">{titulo}</h3>
{body_html}
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
    if "video" in n or "visualizar el video" in nt[:200]:
        return "video", "Auriculares on"
    if "podcast" in n or "audio" in n:
        return "podcast", "Auriculares on"
    if "imagen" in n:
        return "imagen", "Miralo con lupa"
    if "atencion" in n or "importante" in n:
        return "atencion", "No pases de largo"
    if "ejemplo" in n:
        return "ejemplo", "Ejemplo que iluminan"
    return "simple", ""


def _es_instruccion_maquetacion(texto: str) -> bool:
    """Etiquetas que son INDICACIONES de maquetación (cómo formatear), no
    contenido: no van en el aula. P.ej. 'Tabla con resaltado sutil'."""
    n = _norm(texto)
    return n.startswith((
        "tabla con", "tabla de datos", "con resaltado", "resaltado",
        "recuadro con", "cuadro con", "imagen con", "imagen de diseno",
        "recurso tipo", "esquema con", "infografia con", "cita con"))


def _tabla_a_recuadro(tabla) -> str:
    """Convierte una tabla de 1 columna en el snippet que corresponda."""
    filas = tabla.find_all("tr")
    celdas = [c for c in (tr.find(["td", "th"]) for tr in filas) if c is not None]
    if not celdas:
        return ""

    # "Líneas" del recuadro: las celdas (tabla multi-fila) o, si hay una sola
    # celda con varios párrafos, cada <p> (así la 1ª línea = etiqueta/instrucción).
    if len(celdas) == 1:
        ps = [p for p in celdas[0].find_all("p") if p.get_text(strip=True)]
        lineas = ps if len(ps) >= 2 else celdas
    else:
        lineas = celdas

    etiqueta = lineas[0].get_text(" ", strip=True)
    texto_completo = tabla.get_text(" ", strip=True)
    tipo, titulo = _clasificar_recuadro(etiqueta, texto_completo)

    def _html_lineas(ls):
        partes = []
        for el in ls:
            if getattr(el, "name", "") == "p":
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
    body = _html_lineas(lineas[1:] if quitar and len(lineas) > 1 else lineas)
    if not body:
        body = _html_lineas(lineas)

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
# "Figura 4 M3.png", "Tabla 1 M2.jpg", "Esquema.jpg"
_PAT_FIG_FILE = re.compile(
    r"(?:m[_\s]?(\d+)\s*fig(?:ura)?\s*(\d+))|(?:fig(?:ura)?\s*(\d+)\s*m[_\s]?(\d+))"
    r"|(?:tabla\s*(\d+)\s*m[_\s]?(\d+))|(?:m[_\s]?(\d+)\s*tabla\s*(\d+))", re.I)

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
            nueva = BeautifulSoup(
                f'<p style="text-align: center;"><img class="{_FIG_CLASES_ESTATICA}" '
                f'style="width: 700px; height: auto;" '
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
            resto = texto[m.end():].strip(" .:–—-")
            img_html = ""
            if resto:
                img_html += (
                    '<p class="dp-heading-ignore" style="text-align: center;">'
                    f'<span style="font-size: 10pt;"><strong>{texto}</strong>'
                    '</span></p>')
            img_html += (
                f'<p style="text-align: center;"><img class="{_FIG_CLASES_ESTATICA}" '
                f'style="width: 700px; height: auto;" '
                f'src="__DISENO__/{path.name}" alt="{texto[:120]}" '
                f'loading="lazy"></p>')
            p.replace_with(BeautifulSoup(img_html, "html.parser"))
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
    for p in list(soup.find_all("p")):
        if p.parent is None or p.find_parent(class_="dp-callout"):
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
            # párrafo, después de la invitación: entra al mismo bloque para
            # que no quede publicado como texto suelto.
            sig = grupo[-1].find_next_sibling()
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

_H2_TITULO_ACTIVIDAD = ('<h2 class="dp-ignore-theme" '
                        'style="color: {color}; text-align: center;">'
                        "<strong>{titulo}</strong></h2>")


def maquetar_actividad(html: str, tema: str = "") -> str:
    """Da forma al cuerpo de una actividad según el "Modelo de actividad".

    - El primer encabezado es el título de la actividad: va como H2 de título
      (dp-ignore-theme, centrado), no como subtítulo, y sin el prefijo
      "Actividad …:" que duplica el nombre del ítem en Canvas.
    - Los rótulos de sección (Objetivo, Consigna, Pautas de presentación,
      Criterios de evaluación, Anexo) pasan a <h3> y se les saca los dos
      puntos; si el párrafo traía el cuerpo pegado, queda debajo.
    """
    if not html:
        return html
    soup = BeautifulSoup(html, "html.parser")

    primero = soup.find(["h1", "h2", "h3", "h4"])
    if primero is not None and not primero.get("class"):
        texto = primero.get_text(" ", strip=True)
        limpio = _PAT_PREFIJO_ACTIVIDAD.sub("", texto).strip()
        if limpio:
            color = ACENTO_POR_TEMA.get(_norm(tema or ""), ACCENT)
            primero.replace_with(BeautifulSoup(
                _H2_TITULO_ACTIVIDAD.format(color=color, titulo=limpio),
                "html.parser"))

    for p in list(soup.find_all("p")):
        texto = p.get_text(" ", strip=True)
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
_EXPANDER_KW = ("expander", "expandible", "expandibles", "acordeon",
                "desplegable", "desplegables")


_FLIP_KW = ("flip card", "flip cards", "flipcard", "flipcards")


def _tabla_a_flipcards(tabla):
    """Tabla con etiqueta 'Flip cards …' → tarjetas (frente=título en negrita,
    dorso=descripción). Se descarta el párrafo de instrucción inicial."""
    cell = tabla.find(["td", "th"])
    if cell is None:
        return None
    parrafos = [p for p in cell.find_all("p") if p.get_text(strip=True)]
    items, i, n = [], 0, len(parrafos)
    while i < n:
        p = parrafos[i]
        strong = p.find("strong")
        if not strong:        # instrucción inicial o dorso huérfano: se ignora
            i += 1
            continue
        frente = strong.get_text(" ", strip=True).strip(" .:–-")
        strong.extract()
        dorso = [re.sub(r"^[\s.:–-]+", "", "".join(str(x) for x in p.children).strip())]
        j = i + 1
        while j < n and not parrafos[j].find("strong"):   # dorso = párrafos sin negrita
            dorso.append(parrafos[j].get_text(" ", strip=True))
            j += 1
        if frente:
            items.append((frente, " ".join(d for d in dorso if d) or "&nbsp;"))
        i = j
    if len(items) < 2:
        return None
    return construir_flipcards(items)


def _tabla_a_acordeon(tabla):
    """Tabla cuya etiqueta es 'Expander/Expandible/Acordeón' → acordeón
    (dp-panels-wrapper). Cada párrafo con título en negrita abre un panel: el
    <strong> es el encabezado, y el contenido son el resto del párrafo del
    encabezado MÁS los párrafos siguientes hasta el próximo encabezado en
    negrita (igual que _tabla_a_flipcards) — el DOCX trae el cuerpo de cada
    ítem en párrafos aparte, no en el mismo párrafo que el título."""
    cell = tabla.find(["td", "th"])
    if cell is None:
        return None
    parrafos = [p for p in cell.find_all("p") if p.get_text(strip=True)]
    # El primer párrafo es la etiqueta ('Expander'); si la etiqueta y el primer
    # ítem comparten párrafo, igual se procesan los que tienen <strong>.
    grupos, i, n = [], 0, len(parrafos)
    while i < n:
        p = parrafos[i]
        strong = p.find("strong")
        if not strong:
            i += 1
            continue
        heading = strong.get_text(" ", strip=True).strip(" .:–-")
        strong.extract()
        resto = re.sub(r"^[\s.:–-]+", "", "".join(str(x) for x in p.children).strip())
        piezas = [f"<p>{resto}</p>"] if resto else []
        j = i + 1
        while j < n and not parrafos[j].find("strong"):
            piezas.append(str(parrafos[j]))
            j += 1
        if heading:
            grupos.append((heading, "".join(piezas) or "&nbsp;"))
        i = j
    if len(grupos) < 2:        # un acordeón necesita al menos 2 paneles
        return None
    return construir_panels(grupos)


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
        f"<!-- Incrustar aquí el recurso{' — ' + titulo if titulo else ''}: "
        "el diseñador entrega el div -->")
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

# Marcadores con los que el asesor pide que la figura se pueda ampliar.
_FIG_EXPANDIBLE_KW = ("expandible", "expandida", "ampliable",
                      "clic para ampliar", "click para ampliar")


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
    contenedor = img.find_parent("p") or img.parent
    trozos = [img.get("alt", "")]
    if contenedor is not None:
        for vecino in list(contenedor.find_next_siblings())[:2]:
            trozos.append(vecino.get_text(" ", strip=True))
        for vecino in list(contenedor.find_previous_siblings())[:2]:
            trozos.append(vecino.get_text(" ", strip=True))
    texto = _norm(" ".join(t for t in trozos if t))
    return any(kw in texto for kw in _FIG_EXPANDIBLE_KW)


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
    if encabezado.find_parent("thead") is None:
        thead = BeautifulSoup("<thead></thead>", "html.parser").thead
        encabezado.insert_before(thead)
        thead.append(encabezado.extract())
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


def procesar_contenido(html: str, tema: str = "") -> str:
    if not html:
        return html
    soup = BeautifulSoup(html, "html.parser")

    # 0. Anclas internas de Word/Google Docs (ruido de la conversión).
    for a in soup.find_all("a"):
        if not a.get("href") and not a.get_text(strip=True) and not a.find("img"):
            a.unwrap() if a.contents else a.decompose()

    # 0.5 Genially: incrustar (URL) o marcar para incrustar (descripción).
    _procesar_genially(soup)

    # 1. Tablas → acordeón ('Expander'), recuadro (1 columna) o tabla de datos
    for tabla in soup.find_all("table"):
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
        max_cols = max((len(tr.find_all(["td", "th"]))
                        for tr in tabla.find_all("tr")), default=0)
        if max_cols == 1:
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

    # 1.6 Párrafos con frases-señal → recuadros (Lectura / Video / Atención)
    _procesar_cues_parrafo(soup)

    # 1.7 Encabezados reales de Word (estilo "Título 1"/"Título 2") dentro
    # del cuerpo → <h3>. El título de la página en Canvas ya cumple el rol
    # de encabezado principal; cualquier subtítulo numerado interno es
    # siempre h3, tanto si el asesor lo marcó en negrita (ver paso 2) como
    # si usó el estilo de título de Word (mammoth lo vuelca tal cual a
    # <h1>/<h2>, sin bajarlo de nivel).
    for h in soup.find_all(["h1", "h2"]):
        # El h2 con ícono no es un encabezado del contenido: es el divisor de
        # sección que arma el propio generador (bloque de video, por ejemplo).
        if "dp-has-icon" in (h.get("class") or []):
            continue
        for strong in h.find_all(["strong", "b"]):
            strong.unwrap()
        h.name = "h3"

    # 2. Subtítulos en negrita → <h3> (el dp-wrapper los estiliza). Solo
    # texto SUELTO del flujo principal — no el cuerpo de un componente que
    # otro paso ya armó (recuadro/acordeón/flip-card): ahí "en negrita y
    # corto" puede ser contenido legítimo (p.ej. el placeholder de Genially),
    # no un subtítulo, y convertirlo duplicaba el título del recuadro.
    for p in soup.find_all("p"):
        if p.find_parent(class_=("dp-callout", "dp-panels-wrapper",
                                  "dp-flip-card-deck")):
            continue
        strongs = p.find_all("strong")
        if not strongs:
            continue
        texto = p.get_text(" ", strip=True)
        texto_strong = " ".join(s.get_text(" ", strip=True) for s in strongs)
        if (texto and texto == texto_strong and 10 <= len(texto) <= 90
                and not texto.endswith(":") and not _NO_H3.match(texto)
                and not p.find("img")):
            if _introducido_por_dos_puntos(p):
                # El párrafo anterior termina en ":": esto es lo que estaba
                # introduciendo, no un subtítulo nuevo. Queda como párrafo
                # destacado (estilo lead, en negrita), que es como lo maqueta
                # el equipo a mano.
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
    # el bloque vacío, nunca se publica como texto.
    for p in list(soup.find_all("p")):
        if not _PAT_MARCADOR_VIDEO.match(p.get_text(" ", strip=True)):
            continue
        previo = p.find_previous_sibling()
        ya_hay_bloque = (previo is not None
                         and getattr(previo, "get", None) is not None
                         and previo.get("data-title") == "Video")
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
            img["class"] = (_FIG_CLASES_EXPANDIBLE if _figura_es_expandible(img)
                            else _FIG_CLASES_ESTATICA)
            if not img.get("style"):
                img["style"] = "width: 700px; height: auto;"
        # Centrar el párrafo contenedor aunque Word haya envuelto la imagen en
        # <strong>/<span>: hay que subir hasta el <p>, no mirar el padre directo.
        contenedor = img.find_parent("p")
        if contenedor is not None:
            contenedor["style"] = "text-align: center;"

    # Con las figuras ya estiladas: el pie de fuente pasa a <figcaption> y las
    # clases se mudan al <figure> (la imagen queda limpia, como a mano).
    _nota_a_figcaption(soup)
    _espaciar_figuras(soup)

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

    # 4. Epígrafes (Figura N. / Nota.) → centrados, tamaño 10pt
    for p in soup.find_all("p"):
        texto = p.get_text(" ", strip=True)
        if _PAT_CAPTION.match(texto) or re.match(r"^nota\s*[\.:]", texto, re.I):
            p["class"] = "dp-heading-ignore"
            p["style"] = "text-align: center;"
            inner = f'<span style="font-size: 10pt;"><strong>{texto}</strong></span>'
            p.clear()
            p.append(BeautifulSoup(inner, "html.parser"))

    # 5. Espaciador antes de subtítulos sueltos (h3 sin clase — de los pasos
    # 1.7 y 2, no los card-title/dp-panel-heading de componentes): el equipo
    # SIEMPRE separa un subtítulo del párrafo anterior con <p>&nbsp;</p>,
    # salvo que sea el primer elemento de la página.
    for h3 in soup.find_all("h3", class_=lambda c: not c):
        if h3.parent is not soup:
            continue
        anterior = h3.previous_sibling
        while isinstance(anterior, NavigableString) and not anterior.strip():
            anterior = anterior.previous_sibling
        if anterior is None:
            continue
        ya_espaciado = (getattr(anterior, "name", None) == "p"
                        and anterior.get_text(strip=True) in ("", "\xa0")
                        and not anterior.find("img"))
        if not ya_espaciado:
            h3.insert_before(BeautifulSoup("<p>&nbsp;</p>", "html.parser"))

    return aplicar_acento_del_tema(str(soup), tema)
