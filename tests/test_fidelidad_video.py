# -*- coding: utf-8 -*-
"""Video propio (Canvas Studio) vs CTA a una plataforma externa.

Los videos de desarrollo / introducción / conceptuales son de la UCC: se suben
a Canvas Studio y se incrustan, NO son un llamado a la acción que manda a
YouTube. El generador los trataba a todos como CTA y dejaba el marcador
"VIDEO M2." publicado como texto.

El id del video recién existe cuando alguien lo sube, después de generar el
aula, así que el bloque queda armado y vacío listo para pegar el embed.

Ver docs/auditoria-fidelidad-gestion-calidad-2026-09-10.md
"""

from maquetador.build.snippets import procesar_contenido, bloque_video_studio

PROPIO = ("<p>Antes de profundizar en cada una de estas herramientas, te "
          "proponemos mirar el siguiente video conceptual. VIDEO M2.</p>")
EXTERNO = ('<p>Te invito a ver el video sobre calidad.</p>'
           '<p><a href="https://youtu.be/abc123">https://youtu.be/abc123</a></p>')


class TestVideoPropio:
    def test_arma_el_bloque_de_canvas_studio(self):
        out = procesar_contenido(PROPIO)
        assert 'data-title="Video"' in out
        assert 'data-category="+UCC"' in out

    def test_no_es_un_cta(self):
        assert "Auriculares on" not in procesar_contenido(PROPIO)

    def test_deja_el_hueco_para_el_embed(self):
        out = procesar_contenido(PROPIO)
        assert "dp-embed-wrapper" in out
        assert "Canvas Studio" in out

    def test_el_divisor_queda_en_h2(self):
        """El h2 con ícono es el divisor de sección: no se degrada a h3."""
        out = procesar_contenido(PROPIO)
        assert '<h2 class="dp-has-icon">' in out

    def test_no_publica_el_marcador(self):
        out = procesar_contenido(PROPIO)
        assert "VIDEO M2" not in out
        assert "video conceptual" in out

    def test_el_marcador_suelto_tampoco_se_publica(self):
        out = procesar_contenido("<p>Te invito a ver el video.</p><p>VIDEO 2</p>")
        assert "VIDEO 2" not in out


class TestMarcadorConNombreDeModulo:
    """El asesor también marca el video como "VIDEO MÓDULO 1" (no solo
    "VIDEO 2"/"VIDEO M2."), y a veces lo deja separado de la invitación por un
    párrafo de aire (&nbsp;): igual debe quedar adentro del mismo bloque, sin
    duplicar el hueco del embed ni publicarse como título suelto."""

    CON_AIRE = ("<p>Te invito a ver el siguiente video sobre calidad.</p>"
                "<p>&nbsp;</p><p><strong>VIDEO MÓDULO 1</strong></p>")

    def test_no_publica_el_marcador_con_modulo(self):
        out = procesar_contenido(self.CON_AIRE)
        assert "VIDEO MÓDULO" not in out.upper()

    def test_un_solo_bloque_de_video(self):
        out = procesar_contenido(self.CON_AIRE)
        assert out.count('data-title="Video"') == 1

    def test_suelto_separado_por_aire_no_publica_titulo(self):
        out = procesar_contenido(
            "<p>Te invito a ver el video.</p><p>&nbsp;</p><p>VIDEO MÓDULO 2</p>")
        assert "VIDEO MÓDULO" not in out.upper()
        assert out.count('data-title="Video"') == 1


class TestVideoExterno:
    def test_con_enlace_sigue_siendo_cta(self):
        out = procesar_contenido(EXTERNO)
        assert "Auriculares on" in out

    def test_no_arma_bloque_de_studio(self):
        assert 'data-title="Video"' not in procesar_contenido(EXTERNO)


class TestBloqueSuelto:
    def test_sin_intro_arma_igual_el_bloque(self):
        html = bloque_video_studio()
        assert "dp-embed-wrapper" in html
        assert '<h2 class="dp-has-icon">' in html


class TestElBloqueDeVideoQuedaAbierto:
    """El equipo a mano NO cierra el bloque "Video" después del video: todo
    el resto de la página (herramientas, reflexión, cierre…) queda adentro
    del mismo <div data-title="Video">, no como un segundo bloque aparte.
    Regresión real: 2.2 armaba el bloque de video bien pero lo cerraba
    justo después, y el resto del contenido de la página (el acordeón de
    Ishikawa/5 porqués/Pareto, "No conformidades", la reflexión y el
    cierre) quedaba afuera, en el content-block genérico de arriba."""

    HTML = (PROPIO +
            '<h3>Comprender los problemas antes de actuar</h3>'
            '<p>Antes de aplicar cualquier herramienta…</p>')

    def test_el_resto_de_la_pagina_queda_adentro_del_bloque_de_video(self):
        from bs4 import BeautifulSoup
        out = procesar_contenido(self.HTML)
        soup = BeautifulSoup(out, "html.parser")
        bloque = soup.find("div", attrs={"data-title": "Video"})
        assert bloque is not None
        assert bloque.find("h3") is not None
        assert "Comprender los problemas" in bloque.get_text()

    def test_un_solo_bloque_de_video_con_todo_adentro(self):
        out = procesar_contenido(self.HTML)
        assert out.count('data-title="Video"') == 1

    def test_video_externo_no_se_ve_afectado(self):
        """El CTA a YouTube/Vimeo (con URL) no arma bloque "Video": no hay
        nada que dejar abierto, el resto de la página sigue como siempre."""
        html = EXTERNO + "<h3>Otro tema</h3><p>Más contenido.</p>"
        out = procesar_contenido(html)
        assert 'data-title="Video"' not in out
        assert "<h3>Otro tema</h3>" in out


class TestSubtitulosDentroDelBloqueDeVideoSiguenEspaciados:
    """El paso 5 de procesar_contenido (espaciador antes de un subtítulo
    suelto) solo miraba subtítulos a nivel de página (hx.parent is soup):
    cualquier <h3>/<h4> que cae DENTRO del bloque "Video" —que queda abierto
    y absorbe el resto de la página, no es un componente aislado— se saltaba
    sin su <p>&nbsp;</p> de arriba. Afecta también a la "Conclusión" del
    módulo, que se agrega al final de la página y cae ahí mismo. Regresión
    real: módulo 1.4 de Gestión de la Calidad, dos subtítulos y la
    Conclusión sin espacio."""

    HTML = (PROPIO +
            '<p>El video plantea la diferencia entre cumplir '
            'especificaciones técnicas y responder a expectativas reales.</p>'
            '<h3>Calidad desde la perspectiva del cliente</h3>'
            '<p>La calidad no se define solo desde lo técnico.</p>'
            '<h3>Conclusión</h3>'
            '<p>La calidad en proyectos no se juega solo al final.</p>')

    def test_el_subtitulo_dentro_del_bloque_de_video_lleva_espaciador(self):
        out = procesar_contenido(self.HTML)
        assert ('<p>\xa0</p><h3>Calidad desde la perspectiva del cliente'
               '</h3>') in out

    def test_la_conclusion_tambien_lleva_espaciador(self):
        out = procesar_contenido(self.HTML)
        assert "<p>\xa0</p><h3>Conclusión</h3>" in out

    def test_un_subtitulo_a_nivel_de_pagina_sigue_funcionando(self):
        """No se rompe el caso de siempre: un h3 que NO está adentro de
        ningún bloque de video también lleva su espaciador."""
        html = "<p>Texto previo.</p><h3>Un título cualquiera</h3><p>Cuerpo.</p>"
        out = procesar_contenido(html)
        assert "<p>\xa0</p><h3>Un título cualquiera</h3>" in out


class TestElBloqueDeVideoEsUnBloqueAparteEnLaPagina:
    """El bloque "Video" no va ANIDADO dentro del content-block de lectura
    (kl_readings2) de la página: el equipo a mano cierra ese div y abre uno
    nuevo, propio, para el video — hermano al mismo nivel, no metido
    adentro. procesar_contenido no puede devolver eso solo (su salida
    entera queda embebida en UN content-block por la plantilla de la
    página): pagina_contenido tiene que separarlo."""

    HTML = (PROPIO +
            '<h3>Comprender los problemas antes de actuar</h3>'
            '<p>Antes de aplicar cualquier herramienta…</p>')

    def test_video_es_hermano_de_kl_readings2_no_esta_adentro(self):
        from bs4 import BeautifulSoup
        from maquetador.build.pages import pagina_contenido
        out = pagina_contenido("1.4. Título", self.HTML, "b.png", "id")
        soup = BeautifulSoup(out, "html.parser")
        wrapper = soup.find("div", id="dp-wrapper")
        hijos_directos = wrapper.find_all("div", recursive=False)
        clases = [h.get("class") for h in hijos_directos]
        assert ["dp-content-block", "kl_readings2"] in clases
        video = soup.find("div", attrs={"data-title": "Video"})
        assert video is not None
        assert video in hijos_directos
        assert video.find_parent(class_="kl_readings2") is None

    def test_el_contenido_previo_al_video_queda_en_kl_readings2(self):
        from bs4 import BeautifulSoup
        from maquetador.build.pages import pagina_contenido
        html = "<h3>Antes del video</h3><p>Contenido previo.</p>" + self.HTML
        out = pagina_contenido("1.4. Título", html, "b.png", "id")
        soup = BeautifulSoup(out, "html.parser")
        readings = soup.find("div", class_="kl_readings2")
        video = soup.find("div", attrs={"data-title": "Video"})
        assert "Antes del video" in readings.get_text()
        assert "Comprender los problemas" in video.get_text()
        assert "Antes del video" not in video.get_text()
        assert "Comprender los problemas" not in readings.get_text()

    def test_el_bloque_de_video_termina_con_el_mismo_aire_que_kl_readings2(self):
        """kl_readings2 SIEMPRE cierra con un <p>&nbsp;</p> antes del borde
        del content-block (lo pone pagina_contenido); ese mismo spacer le
        faltaba al bloque de video cuando absorbe el resto de la página —
        terminaba pegado al borde. Regresión real: módulo 2.2 de Gestión de
        la Calidad, el último párrafo de la página quedaba sin aire debajo."""
        from bs4 import BeautifulSoup
        from maquetador.build.pages import pagina_contenido
        out = pagina_contenido("2.2. Título", self.HTML, "b.png", "id")
        soup = BeautifulSoup(out, "html.parser")
        video = soup.find("div", attrs={"data-title": "Video"})
        ultimo = video.find_all(recursive=False)[-1]
        assert ultimo.name == "p"
        assert ultimo.get_text(strip=True) in ("", "\xa0")

    def test_no_duplica_el_aire_si_ya_termina_en_espaciador(self):
        from bs4 import BeautifulSoup
        from maquetador.build.pages import pagina_contenido
        html = self.HTML + "<p>&nbsp;</p>"
        out = pagina_contenido("2.2. Título", html, "b.png", "id")
        soup = BeautifulSoup(out, "html.parser")
        video = soup.find("div", attrs={"data-title": "Video"})
        hijos = video.find_all(recursive=False)
        assert not (hijos[-1].get_text(strip=True) in ("", "\xa0")
                   and hijos[-2].get_text(strip=True) in ("", "\xa0"))

    def test_sin_video_no_hay_bloque_aparte(self):
        from bs4 import BeautifulSoup
        from maquetador.build.pages import pagina_contenido
        out = pagina_contenido("1.1. Título", "<p>Contenido común.</p>",
                               "b.png", "id")
        soup = BeautifulSoup(out, "html.parser")
        assert soup.find("div", attrs={"data-title": "Video"}) is None


class TestRecuadroConMarcaDeEmbebido:
    """El asesor de Gestión del Riesgo entrega el video del módulo como
    recuadro "Auriculares on" y adentro escribe «Embeber video: GRyI - V_M1».
    Ese video es propio (el .mp4 está en la carpeta), así que va al bloque de
    Canvas Studio, no a un CTA que manda afuera. La marca es la que decide: en
    Creación de Valor hay CTAs legítimos —"Te sugiero ver… la siguiente charla
    TED"— que tampoco traen la URL en el mismo párrafo y deben seguir siendo
    CTA."""

    CAJA = ('<table><thead><tr><th><p><strong>Auriculares <em>on</em> (Video y '
            'Podcast)</strong></p></th></tr>'
            '<tr><th><p>Antes de empezar con el recorrido, te propongo '
            'visualizar un video introductorio.</p>'
            '<p>Embeber video: <a href="https://docs.google.com/document/d/1fi">'
            'GRyI - V_M1</a></p></th></tr></thead></table>')

    SIN_MARCA = ('<table><thead><tr><th><p><strong>Auriculares on</strong></p>'
                 '</th></tr><tr><th><p>Te sugiero ver la siguiente charla TED '
                 'en la que Joe Pine presenta el marco conceptual.</p>'
                 '</th></tr></thead></table>')

    def test_arma_el_bloque_de_canvas_studio(self):
        out = procesar_contenido(self.CAJA)
        assert 'data-title="Video"' in out
        assert "Auriculares on" not in out

    def test_la_indicacion_de_embeber_no_se_publica(self):
        out = procesar_contenido(self.CAJA)
        assert "Embeber video" not in out
        assert "docs.google.com" not in out

    def test_el_nombre_del_video_queda_como_comentario(self):
        """No se publica, pero le dice a quien pegue el embed cuál de los
        archivos de la carpeta va en este hueco."""
        out = procesar_contenido(self.CAJA)
        assert "<!-- Pegar aquí el embed de Canvas Studio: GRyI - V_M1 -->" in out

    def test_la_invitacion_se_conserva(self):
        assert "te propongo visualizar un video introductorio." \
            in procesar_contenido(self.CAJA)

    def test_el_bloque_no_sale_duplicado(self):
        """La invitación es además un "cue" de video: el paso de párrafos
        volvía a encuadrarla y el bloque salía anidado dentro de sí mismo."""
        assert procesar_contenido(self.CAJA).count('data-title="Video"') == 1

    def test_sin_la_marca_sigue_siendo_un_cta(self):
        out = procesar_contenido(self.SIN_MARCA)
        assert "Auriculares on" in out
        assert 'data-title="Video"' not in out


class TestVideoEnLaPaginaDeIntroduccion:
    """El recuadro del video va debajo de los objetivos, en "Introducción MN":
    el bloque de Studio tiene que salir como content-block hermano, igual que
    en las páginas de contenido."""

    OBJETIVOS = ("<p>Al finalizar este módulo serás capaz de:</p>"
                 "<ul><li>Diferenciar riesgo e incertidumbre.</li></ul>"
                 + TestRecuadroConMarcaDeEmbebido.CAJA)

    def test_el_video_es_hermano_del_bloque_de_objetivos(self):
        from bs4 import BeautifulSoup
        from maquetador.build.pages import pagina_intro
        out = pagina_intro("Introducción M1", "<p>i</p>", self.OBJETIVOS,
                           "b.png", "id")
        soup = BeautifulSoup(out, "html.parser")
        video = soup.find("div", attrs={"data-title": "Video"})
        assert video is not None
        assert video.find_parent(class_="kl_readings2") is None

    def test_los_objetivos_no_se_van_con_el_video(self):
        from maquetador.build.pages import pagina_intro
        from bs4 import BeautifulSoup
        out = pagina_intro("Introducción M1", "<p>i</p>", self.OBJETIVOS,
                           "b.png", "id")
        soup = BeautifulSoup(out, "html.parser")
        objetivos = soup.find("div", class_="kl_readings2")
        assert "Diferenciar riesgo e incertidumbre." in objetivos.get_text()
