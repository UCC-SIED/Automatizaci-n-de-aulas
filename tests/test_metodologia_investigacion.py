# -*- coding: utf-8 -*-
"""Lo que trajo "Metodología de la Investigación Educativa II" (Ed. Especial).

Materia de educación, asesora Juli, docente Adriana Di Francesco. Los
comentarios de esta asesora escriben pedidos que ya resolvíamos, pero con
otras palabras —y con alguna errata—, así que caían en los avisos y el
maquetado salía crudo. Acá quedan con el texto exacto del DOCX.
"""

from pathlib import Path

import pytest
from bs4 import BeautifulSoup

from maquetador.ingest.docx_comments import _clasificar, aplicar_comentarios
from maquetador.ingest.folder_scanner import _descartable


class TestSangriaEsCita:
    """"Mantener sangría" a secas: ocho comentarios en los tres módulos,
    sobre citas largas de Bourdieu y otros. Caían en "revisar" y la cita
    salía pegada al margen, indistinguible del cuerpo."""

    def test_mantener_sangria(self):
        assert _clasificar("Para maquetación: mantener sangría") == "cita"

    def test_con_coma_en_vez_de_dos_puntos(self):
        """Así lo escribió en el módulo 2."""
        assert _clasificar("Para maquetación, mantener sangría") == "cita"

    def test_cita_con_sangria_y_cita_en_sangria_dan_lo_mismo(self):
        """Las dos formas convivían en el mismo módulo: "con sangría" entraba
        por la señal negativa (que solo evita el recuadro, no sangra) y "en
        sangría" por la de cita. Dos citas vecinas salían desalineadas."""
        assert _clasificar("Para maquetación: mantener cita con sangría") == "cita"
        assert _clasificar("Para maquetación: mantener cita en sangría") == "cita"

    def test_mantener_sangria_y_cursiva_no_arma_un_destacado(self):
        """La frase de apertura del módulo 1. Yo la daba por "destacado" y
        salía adentro de un recuadro centrado; la revisión mostró que no:
        "manteniendo sangría izq y cursiva" no pide destacar nada, describe
        cómo ya se ve el párrafo y pide conservarlo. Va la sangría —la
        cursiva ya viene del DOCX— y ninguna caja."""
        assert _clasificar(
            "Para maquetación: frase de inicio antes de la iintroducción, "
            "manteniendo sangría izq y cursiva") == "cita"

    def test_un_destacado_de_verdad_sigue_siendolo(self):
        """Sin "mantener" de por medio, pedir cursiva sí arma el destacado."""
        assert _clasificar(
            "Para maquetación: esto va en cursiva u otra forma de destacado"
        ) == "destacar_tramo"

    def test_la_cita_queda_sangrada_de_los_dos_lados(self):
        html = ('<p>El modo de pensamiento objetivista rescata las relaciones '
                'objetivas que condicionan las prácticas.</p>')
        soup = BeautifulSoup(html, "html.parser")
        aplicar_comentarios(soup, [{
            "accion": "cita",
            "instruccion": "Para maquetación: mantener sangría",
            "anclado": "El modo de pensamiento objetivista rescata las "
                       "relaciones objetivas que condicionan las prácticas.",
        }])
        estilo = soup.find("p").get("style", "")
        assert "margin-left: 80px" in estilo
        assert "margin-right: 40px" in estilo


class TestErrataDeRecuadro:
    """"Mantener recuedro como se dispone", dos veces en el módulo 2, sobre
    los recuadros de palabras clave. La errata rompía la detección y el
    recuadro del docente salía como texto corrido."""

    def test_recuedro(self):
        assert _clasificar(
            "Para maquetación: mantener recuedro como se dispone"
        ) == "recuadro_simple"

    def test_recudro(self):
        assert _clasificar("Para maquetación: mantener recudro") == "recuadro_simple"

    def test_recuadro_bien_escrito_sigue_andando(self):
        assert _clasificar(
            "Para maquetación: mantener recuadro destacado") == "recuadro_simple"

    def test_recuerdo_no_es_recuadro(self):
        """La tolerancia a la errata no puede llevarse por delante una
        palabra común: "recuerdo" no pide ningún recuadro."""
        assert _clasificar(
            "Para maquetación: según recuerdo esto iba antes") != "recuadro_simple"


class TestFiguraDeDisenoSinLaPalabraReemplazar:
    """"Original en carpeta diseño" sobre el epígrafe: es el mismo pedido que
    "reemplazar esta figura por la de diseño", que el generador ya hace solo.
    Salía como pendiente en cada corrida."""

    def test_original_en_carpeta_diseno(self):
        assert _clasificar("Para maquetación: original en carpeta diseño",
                           "Figura 4") == "figura_de_diseno"

    def test_necesita_estar_anclado_a_una_figura(self):
        """Sin ancla de figura no se asume: "original" aparece en charla
        interna del equipo sobre cualquier cosa."""
        assert _clasificar("Para maquetación: original en carpeta diseño",
                           "Este párrafo va antes") != "figura_de_diseno"


class TestEnlaceEnElAqui:
    """La asesora deja el link en el comentario y marca el renglón donde va.
    Sin la palabra "descargable" el pedido caía en los avisos y el "aquí" se
    publicaba sin enlazar a nada."""

    URL = ("https://docs.google.com/document/d/"
           "1EVrUUvkHXg5dlaVi-0QGABU6uaCGtPAQZqPLSUnLhtU/edit?usp=sharing")

    def test_se_reconoce_por_el_aqui_del_ancla(self):
        assert _clasificar(
            f"Para maquetación: usaremos doc con acceso abierto para edición "
            f"(este link está en la unidad compartida) {self.URL}",
            "Acceso a la grilla colaborativa: aquí") == "enlace_descargable"

    def test_el_link_va_solo_en_el_aqui(self):
        """No en la frase entera: es la convención del aula."""
        html = '<p>Acceso a la grilla colaborativa: aquí</p>'
        soup = BeautifulSoup(html, "html.parser")
        aplicar_comentarios(soup, [{
            "accion": "enlace_descargable",
            "instruccion": f"Para maquetación: usaremos doc con acceso "
                           f"abierto para edición {self.URL}",
            "anclado": "Acceso a la grilla colaborativa: aquí",
        }])
        a = soup.find("a")
        assert a is not None
        assert a.get_text(strip=True) == "aquí"
        assert a["href"].startswith("https://docs.google.com/document/d/1EVr")
        assert "Acceso a la grilla colaborativa:" in soup.get_text()

    def test_sin_url_no_hace_nada(self):
        assert _clasificar("Para maquetación: el link lo vemos después",
                           "Acceso a la grilla: aquí") != "enlace_descargable"


class TestCopiaDeQueNoEsBorrador:
    """El protocolo de transparencia llegó como "Copia de Protocolo de
    transparencia.xlsx" y el escaneo lo descartaba por el "Copia de",
    mientras las tres actividades lo enlazaban."""

    def _armar(self, tmp_path, nombres):
        for n in nombres:
            (tmp_path / n).write_text("x", encoding="utf-8")
        return tmp_path

    def test_se_conserva_si_el_original_no_esta(self, tmp_path):
        raiz = self._armar(tmp_path, ["Copia de Protocolo de transparencia.xlsx"])
        p = raiz / "Copia de Protocolo de transparencia.xlsx"
        assert _descartable(p, raiz) is False

    def test_se_descarta_si_el_original_esta(self, tmp_path):
        """Ahí sí es el duplicado de borrador que la regla buscaba."""
        raiz = self._armar(tmp_path, ["M1.docx", "Copia de M1.docx"])
        assert _descartable(raiz / "Copia de M1.docx", raiz) is True

    def test_copia_de_un_borrador_sigue_siendo_borrador(self, tmp_path):
        raiz = self._armar(tmp_path, ["Copia de borrador M2.docx"])
        assert _descartable(raiz / "Copia de borrador M2.docx", raiz) is True

    def test_los_otros_descartes_no_cambian(self, tmp_path):
        raiz = self._armar(tmp_path, ["M1 - borrador.docx"])
        assert _descartable(raiz / "M1 - borrador.docx", raiz) is True


class TestCarruselEsUnaFila:
    """"Carrusel de imágenes" sobre las tres fotos de "Miralo con lupa"
    (módulo 2). Son fotos que se comparan de un vistazo, así que van lado a
    lado y no en las solapas verticales de la galería —esas se eligieron
    para diagramas con texto, que en miniatura no se leen."""

    HTML = (
        '<p><strong>Figura 1. Miralo con lupa (1)</strong></p>'
        '<p><img src="a.jpg" /></p>'
        '<p><em>Nota</em>. <em>Gente relajándose junto a un mural</em> '
        '[fotografía], por Jens Schwan, 2026, Unsplash.</p>'
        '<p>Texto alternativo: Grupo de jóvenes frente a un mural.</p>'
        '<p><strong>Figura 2. Miralo con lupa (2)</strong></p>'
        '<p><img src="b.jpg" /></p>'
        '<p><em>Nota</em>. <em>Personas formando un círculo</em> '
        '[fotografía], por Dario Valenzuela, 2018, Unsplash.</p>'
        '<p>Texto alternativo: Grupo reunido en círculo al aire libre.</p>'
        '<p><strong>Figura 3. Miralo con lupa (3)</strong></p>'
        '<p><img src="c.jpg" /></p>'
        '<p><em>Nota. </em>Imágenes tomadas de Unsplash.</p>'
        '<p>Texto alternativo: Collage sobre etnografía.</p>'
        '<p><strong>Requisitos y criterios</strong></p>')

    def _armar(self):
        soup = BeautifulSoup(self.HTML, "html.parser")
        aplicar_comentarios(soup, [{
            "accion": "galeria_fila",
            "instruccion": "Para maquetación: carrusel de imágenes",
            "anclado": "Figura 1. Miralo con lupa (1)",
        }])
        return soup

    def test_se_reconoce_el_pedido(self):
        assert _clasificar("Para maquetación: carrusel de imágenes") == "galeria_fila"

    def test_las_tres_quedan_en_una_fila(self):
        soup = self._armar()
        fila = soup.find("div", class_="dp-popup-gallery")
        assert fila is not None
        columnas = fila.find_all("div", class_="col-lg-4")
        assert len(columnas) == 3
        assert all(c.find("img") is not None for c in columnas)

    def test_se_amplian_al_clic(self):
        """Es lo que reemplaza al carrusel: la grilla de DesignPLUS abre la
        foto grande al hacer clic."""
        fila = self._armar().find("div", class_="dp-popup-gallery")
        assert fila["data-title"] == "Image Grid Gallery 3x3"

    def test_el_texto_alternativo_va_al_alt_y_no_al_cuerpo(self):
        soup = self._armar()
        alts = [i.get("alt", "") for i in soup.find_all("img")]
        assert "Grupo de jóvenes frente a un mural." in alts
        assert "Collage sobre etnografía." in alts
        assert "Texto alternativo" not in soup.get_text()

    def test_cada_figura_conserva_su_epigrafe_y_su_nota(self):
        texto = self._armar().get_text(" ", strip=True)
        for n in ("Figura 1. Miralo con lupa (1)",
                  "Figura 2. Miralo con lupa (2)",
                  "Figura 3. Miralo con lupa (3)"):
            assert n in texto
        assert "por Jens Schwan" in texto

    def test_la_nota_no_queda_con_el_punto_separado(self):
        """El pie trae "Nota" en cursiva y el punto afuera: al pasarlo a
        texto plano quedaba "Nota ." con un espacio en medio."""
        assert "Nota ." not in self._armar().get_text()

    def test_no_se_come_lo_que_sigue(self):
        """La serie termina donde deja de haber figuras: el párrafo de
        requisitos tiene que quedar afuera de la fila."""
        soup = self._armar()
        fila = soup.find("div", class_="dp-popup-gallery")
        assert "Requisitos y criterios" not in fila.get_text()
        assert "Requisitos y criterios" in soup.get_text()

    def test_una_figura_sola_no_arma_fila(self):
        """Sin serie no hay nada que agrupar: se avisa y se maqueta como
        figura suelta."""
        soup = BeautifulSoup(
            '<p><strong>Figura 1. Una sola</strong></p>'
            '<p><img src="a.jpg" /></p>', "html.parser")
        comentarios = [{
            "accion": "galeria_fila",
            "instruccion": "Para maquetación: carrusel de imágenes",
            "anclado": "Figura 1. Una sola",
        }]
        aplicar_comentarios(soup, comentarios)
        assert soup.find("div", class_="dp-popup-gallery") is None
        assert comentarios[0]["_aplicado"] is False


class TestAnchoDeColumnaSegunCuantasHaya:
    def test_dos_figuras_van_a_la_mitad(self):
        from maquetador.build.snippets import fila_de_figuras
        html = fila_de_figuras([("1", "Una", '<img src="a.jpg"/>', ""),
                                ("2", "Otra", '<img src="b.jpg"/>', "")])
        assert html.count('class="col-lg-6"') == 2

    def test_cuatro_van_a_un_cuarto(self):
        from maquetador.build.snippets import fila_de_figuras
        figs = [(str(i), f"F{i}", f'<img src="{i}.jpg"/>', "") for i in range(1, 5)]
        assert fila_de_figuras(figs).count('class="col-lg-3"') == 4

    def test_sin_figuras_no_devuelve_nada(self):
        from maquetador.build.snippets import fila_de_figuras
        assert fila_de_figuras([]) == ""


class TestLaReferenciaDeLaPlanillaNoSiempreEsUnArchivo:
    """La columna "referencia" trae tres cosas distintas y antes se las
    trataba a todas como nombre de archivo."""

    def test_un_nombre_de_archivo_si_sirve(self):
        from maquetador.ingest.reconciler import _referencia_nombra_archivo
        assert _referencia_nombra_archivo(
            "Actividad obligatoria 1 (Metodología de la Investigación II- "
            "Adriana Di Francesco).docx") is True
        assert _referencia_nombra_archivo(
            "Foro (Metodología de la Investigación II- "
            "Adriana Di Francesco).docx") is True

    @pytest.mark.parametrize("ref", [
        "En la lectura",
        "Final del 1.2 pág. 9",
        "En 2.1, pag 4",
        "en 1.3, p. 14",
        "3.2.1, p. 8",
    ])
    def test_un_lugar_de_la_lectura_no_sirve(self, ref):
        """Dice DÓNDE escribió el docente la consigna, no en qué archivo."""
        from maquetador.ingest.reconciler import _referencia_nombra_archivo
        assert _referencia_nombra_archivo(ref) is False

    def test_una_url_de_drive_no_sirve(self):
        from maquetador.ingest.reconciler import _referencia_nombra_archivo
        assert _referencia_nombra_archivo(
            "https://docs.google.com/document/d/19KBfK4uxK2w3-iO6KD42zEcCViyP9lLv/edit"
        ) is False

    def test_vacia_no_sirve(self):
        from maquetador.ingest.reconciler import _referencia_nombra_archivo
        assert _referencia_nombra_archivo("") is False
        assert _referencia_nombra_archivo("   ") is False


class TestDeDondeSaleElTituloDeLaPagina:
    """La planilla y la lectura no siempre coinciden. Cuando la docente
    reescribió el encabezado gana la lectura; cuando la diferencia es solo
    de puntuación o mayúsculas gana la planilla, para no mover el título de
    páginas ya entregadas sin ninguna ganancia."""

    def _item(self, titulo):
        from maquetador.models import ItemCurso, TipoItem
        return ItemCurso(tipo=TipoItem.PAGINA, titulo=titulo, orden=1)

    def test_gana_la_lectura_cuando_el_titulo_cambio(self):
        from maquetador.ingest.reconciler import _elegir_titulo_de_pagina
        it = self._item("3.2.2. Observación y observación participativa: "
                        "condiciones y particularidades")
        _elegir_titulo_de_pagina(
            it, "3.2.2. La observación como medio de representar la realidad")
        assert it.titulo == ("3.2.2. La observación como medio de representar "
                            "la realidad")

    def test_la_numeracion_sigue_siendo_la_de_la_planilla(self):
        """Es la que ordena el aula: si la lectura numeró distinto, manda
        la planilla."""
        from maquetador.ingest.reconciler import _elegir_titulo_de_pagina
        it = self._item("3.2.3. Entrevistas: principales aspectos")
        _elegir_titulo_de_pagina(
            it, "3.3. La entrevista abierta como práctica")
        assert it.titulo.startswith("3.2.3. ")
        assert "La entrevista abierta como práctica" in it.titulo

    @pytest.mark.parametrize("planilla,lectura", [
        # Solo sobra el punto final en la planilla.
        ("1.1. La ruptura epistemológica y la cuestión de los paradigmas "
         "en el siglo XX.",
         "1.1. La ruptura epistemológica y la cuestión de los paradigmas "
         "en el siglo XX"),
        # Solo cambia una mayúscula.
        ("2.1. Criterios y principios epistemológicos de la Investigación "
         "cualitativa.",
         "2.1. Criterios y principios epistemológicos de la investigación "
         "cualitativa"),
    ])
    def test_una_diferencia_cosmetica_no_cambia_nada(self, planilla, lectura):
        from maquetador.ingest.reconciler import _elegir_titulo_de_pagina
        it = self._item(planilla)
        _elegir_titulo_de_pagina(it, lectura)
        assert it.titulo == planilla

    def test_sin_titulo_en_la_lectura_no_toca_nada(self):
        from maquetador.ingest.reconciler import _elegir_titulo_de_pagina
        it = self._item("3.2.4. Encuestas")
        _elegir_titulo_de_pagina(it, "")
        assert it.titulo == "3.2.4. Encuestas"

    def test_queda_registrado_que_se_cambio(self):
        """Para que la asesora lo pueda revisar."""
        from maquetador.ingest.reconciler import _elegir_titulo_de_pagina
        it = self._item("3.2.5. Grupos de discusión: aspectos para el guión")
        _elegir_titulo_de_pagina(
            it, "3.2.5. Grupos de discusión. Formación de los grupos.")
        assert it.detalle["titulo_planilla_original"].startswith(
            "Grupos de discusión: aspectos")
        assert any("Título tomado de la lectura" in i.mensaje for i in it.issues)


class TestElTextoAlternativoNuncaSePublica:
    """Es una instrucción de maquetación: va al atributo alt y el renglón
    desaparece. Tres formas de escribirlo se estaban publicando."""

    def _procesar(self, html):
        from maquetador.build.snippets import _alt_parrafo_a_atributo
        soup = BeautifulSoup(html, "html.parser")
        _alt_parrafo_a_atributo(soup)
        return soup

    def test_en_el_mismo_parrafo_que_la_imagen(self):
        """Así lo escribió la docente en la Figura 2 de 3.2.4: la imagen y
        el rótulo en un solo renglón de Word. Borrar el párrafo entero se
        habría llevado la imagen."""
        soup = self._procesar(
            '<p><img src="a.jpg"/>Texto alternativo: Tipos de encuestas.</p>')
        img = soup.find("img")
        assert img is not None, "la imagen no puede desaparecer"
        assert img["alt"] == "Tipos de encuestas"
        assert "Texto alternativo" not in soup.get_text()

    def test_separado_de_la_imagen_por_la_nota(self):
        """El orden real: imagen, "Nota. …" y después el alt."""
        soup = self._procesar(
            '<p><img src="a.jpg"/></p>'
            '<p><em>Nota</em>. Figura creada con Gemini AI.</p>'
            '<p>Texto alternativo: Mural simbólico con rostros humanos.</p>')
        assert soup.find("img")["alt"] == "Mural simbólico con rostros humanos"
        assert "Texto alternativo" not in soup.get_text()

    def test_dentro_de_un_recuadro(self):
        """La Figura 3 de 1.2 vive adentro de la caja "¿Qué vemos?". Antes
        se descartaba toda imagen dentro de un dp-callout y quedaba sin alt
        y con el rótulo publicado."""
        soup = self._procesar(
            '<div class="dp-callout card">'
            '<div class="card-body">'
            '<p><img src="a.jpg"/></p>'
            '<p>Texto alternativo: Mural simbólico interconectado.</p>'
            '</div></div>')
        assert soup.find("img")["alt"] == "Mural simbólico interconectado"
        assert "Texto alternativo" not in soup.get_text()

    def test_el_icono_del_recuadro_no_es_una_figura(self):
        """Lo que la exclusión protegía de verdad: el icono del costado no
        tiene que quedarse con el alt de la figura."""
        from maquetador.build.snippets import _es_figura
        soup = BeautifulSoup(
            '<div class="dp-callout-side-emphasis">'
            '<img src="/Iconos/info.png"/></div>', "html.parser")
        assert _es_figura(soup.find("img")) is False

    def test_una_tabla_lleva_aria_label(self):
        soup = self._procesar(
            '<table><tr><td>dato</td></tr></table>'
            '<p>Texto alternativo: Comparación de paradigmas.</p>')
        assert soup.find("table")["aria-label"] == "Comparación de paradigmas"


class TestLaFiguraDeDisenoLlegaATodasPartes:
    def test_tambien_a_la_que_esta_en_la_fila(self):
        """La fila deja el epígrafe en el <figcaption>, así que el barrido
        por párrafos no la veía y las tres fotos de DISEÑO del módulo 2
        quedaban sin usar."""
        from maquetador.build.snippets import reemplazar_figuras_diseno
        indice = {(2, "figura", 1): Path("M_2 fig 1 (original).jpg")}
        html = ('<div class="dp-content-block dp-popup-gallery">'
                '<div class="row"><div class="col-lg-4">'
                '<figure><img src="embebida.jpg" style="height: 200px;"/>'
                '<figcaption><strong>Figura 1. Miralo con lupa (1)</strong>'
                '</figcaption></figure></div></div></div>')
        usadas = set()
        salida = reemplazar_figuras_diseno(html, 2, indice, usadas)
        assert "__DISENO__/M_2 fig 1 (original).jpg" in salida
        assert len(usadas) == 1

    def test_la_grilla_conserva_su_recorte(self):
        """Solo cambia el src: el alto y el object-fit son de la grilla."""
        from maquetador.build.snippets import reemplazar_figuras_diseno
        indice = {(2, "figura", 1): Path("M_2 fig 1.jpg")}
        html = ('<div class="dp-popup-gallery"><div class="col-lg-4">'
                '<figure><img src="e.jpg" style="height: 200px; '
                'object-fit: cover;"/>'
                '<figcaption><strong>Figura 1. Una foto</strong>'
                '</figcaption></figure></div></div>')
        salida = reemplazar_figuras_diseno(html, 2, indice, set())
        assert "height: 200px" in salida and "object-fit: cover" in salida


class TestElProtocoloDeTransparenciaSeAdjunta:
    """Las tres actividades lo enlazan a Drive con la aclaración "el archivo
    debe ser descargable". El archivo está en la carpeta, así que se adjunta
    al paquete: la descarga no depende de los permisos de la unidad."""

    URL = ("https://docs.google.com/spreadsheets/d/"
           "1VoFjbXU2hFNrMWeffjlTqyM2dyYyVomS/edit?usp=drive_link")
    PARRAFO = (
        "Se recomienda que el aporte de la IA no exceda el 30 % del trabajo, "
        "que su uso esté correctamente citado y que no se utilice para "
        "elaborar reflexiones personales, fundamentaciones y/o conclusiones. "
        "En el caso de utilizarla para la realización de la actividad, deberá "
        "completar y entregar completo el protocolo de transparencia.")

    def test_el_ancla_se_encuentra_en_un_parrafo_largo(self):
        """Son tres palabras al final de un párrafo de 325 caracteres, el
        único lugar del DOCX donde se lo nombra. El límite de longitud lo
        descartaba y el pedido fallaba en silencio."""
        from maquetador.ingest.docx_comments import _buscar_elemento
        soup = BeautifulSoup(f"<p>{self.PARRAFO}</p>", "html.parser")
        assert _buscar_elemento(soup, "protocolo de transparencia") is not None

    def test_un_candidato_mejor_le_sigue_ganando(self):
        """El último recurso no puede pisar a un subtítulo con ese texto."""
        from maquetador.ingest.docx_comments import _buscar_elemento
        soup = BeautifulSoup(
            f"<p>{self.PARRAFO}</p><h3>Protocolo de transparencia</h3>",
            "html.parser")
        el = _buscar_elemento(soup, "protocolo de transparencia")
        assert el.name == "h3"

    def test_solo_la_frase_queda_enlazada(self):
        from maquetador.ingest.docx_comments import aplicar_comentarios
        soup = BeautifulSoup(f"<p>{self.PARRAFO}</p>", "html.parser")
        aplicar_comentarios(soup, [{
            "accion": "enlace_descargable",
            "instruccion": f"Para maquetación: {self.URL} archivo debe ser "
                           "descargable",
            "anclado": "protocolo de transparencia",
        }])
        a = soup.find("a")
        assert a is not None
        assert a.get_text(strip=True) == "protocolo de transparencia"
        assert "Se recomienda que el aporte" in soup.get_text()

    def test_se_publica_sin_el_copia_de_de_drive(self):
        """El estudiante ve el nombre del archivo en el enlace."""
        from maquetador.build.imscc_builder import GeneradorAula
        nombre = GeneradorAula._nombre_publicado_de_adjunto(
            Path("Copia de Protocolo de transparencia.xlsx"))
        assert nombre == "Protocolo de transparencia.xlsx"

    def test_un_nombre_sin_copia_de_no_se_toca(self):
        from maquetador.build.imscc_builder import GeneradorAula
        nombre = GeneradorAula._nombre_publicado_de_adjunto(
            Path("Protocolo de transparencia.xlsx"))
        assert nombre == "Protocolo de transparencia.xlsx"


class TestLaActividadSugeridaConBuzon:
    """"¿Cómo vengo hasta acá?" (módulos 1 y 3). La planilla la anota como
    tarea con carga de archivo y los comentarios aclaran que es sugerida y
    que hay que abrir buzón de entrega. La consigna vive dentro de la
    lectura: se va al buzón y arriba queda el llamado a la acción."""

    INSTRUCCION_M1 = (
        "Para maquetación: esto queda como consigna de la actividad "
        "sugerida. A continuación dejo el llamado a la acción: Antes de "
        "finalizar con el módulo, se propone una actividad que luego será "
        "retomada en otras instancias, entendiendo que toda investigación "
        "involucra un proceso, un camino espiralado. Link")

    INSTRUCCION_M3 = (
        "Para maquetación: Lo marcado en este comentario queda como llamado "
        "a la acción y agregar el link. Desde el punto 1 en adelante forma "
        "parte de la consigna")

    def test_se_reconoce_la_consigna_de_la_sugerida(self):
        assert _clasificar(self.INSTRUCCION_M1) == "consigna_de_sugerida"

    def test_se_reconoce_el_corte_por_punto(self):
        assert _clasificar(self.INSTRUCCION_M3) == "consigna_desde_el_punto"

    def test_la_consigna_sale_de_la_lectura_y_queda_el_cta(self):
        html = ('<table><tr><th><p><strong>¿Cómo vengo hasta acá?</strong></p>'
                '<p>Definí el tema a investigar y los actores involucrados.</p>'
                '</th></tr></table>'
                '<p>Conclusión del módulo.</p>')
        soup = BeautifulSoup(html, "html.parser")
        comentarios = [{
            "accion": "consigna_de_sugerida",
            "instruccion": self.INSTRUCCION_M1,
            "anclado": "¿Cómo vengo hasta acá?",
        }]
        aplicar_comentarios(soup, comentarios)
        assert "Definí el tema" in comentarios[0]["_contenido_extraido"]
        assert comentarios[0]["_destino_extraido"] == "sugerida"
        assert "Definí el tema" not in soup.get_text()
        # El llamado a la acción que escribió la asesora, con su enlace.
        assert "camino espiralado" in soup.get_text()
        a = soup.find("a", class_="dp-course-link")
        assert a is not None and a["data-actividad"] == "sugerida"

    def test_la_palabra_link_no_se_publica(self):
        """La asesora cierra la frase con "Link" para marcar dónde va el
        enlace: es una indicación, no parte del texto."""
        soup = BeautifulSoup(
            '<table><tr><th><p><strong>¿Cómo vengo hasta acá?</strong></p>'
            '<p>Consigna.</p></th></tr></table>', "html.parser")
        aplicar_comentarios(soup, [{
            "accion": "consigna_de_sugerida",
            "instruccion": self.INSTRUCCION_M1,
            "anclado": "¿Cómo vengo hasta acá?",
        }])
        assert soup.get_text().rstrip().endswith("Acceder a la actividad")
        assert "espiralado. Link" not in soup.get_text()

    def test_el_corte_deja_la_invitacion_y_se_lleva_los_puntos(self):
        html = ('<table><thead>'
                '<tr><th><p><strong>¿Cómo vengo hasta acá?</strong></p></th></tr>'
                '<tr><th>'
                '<p><strong>¿Cómo leemos los datos estadísticos?</strong></p>'
                '<p>Te propongo un ejercicio de lectura.</p>'
                '<p>1. Leé la introducción del artículo sugerido.</p>'
                '<p>Ospino, W. G. (2024). Elementos de la gestión directiva.</p>'
                '<p>2. Ahora elegí una tabla de tu escuela.</p>'
                '</th></tr></thead></table>')
        soup = BeautifulSoup(html, "html.parser")
        comentarios = [{
            "accion": "consigna_desde_el_punto",
            "instruccion": self.INSTRUCCION_M3,
            "anclado": "¿Cómo leemos los datos estadísticos?",
        }]
        aplicar_comentarios(soup, comentarios)
        consigna = comentarios[0]["_contenido_extraido"]
        # Los dos puntos y, con ellos, la referencia del artículo que hay
        # que leer: viaja con el punto al que pertenece.
        assert "1. Leé la introducción" in consigna
        assert "Ospino, W. G." in consigna
        assert "2. Ahora elegí una tabla" in consigna
        # Arriba queda la invitación, con el enlace al buzón.
        texto = soup.get_text(" ", strip=True)
        assert "Te propongo un ejercicio de lectura" in texto
        assert "Ahora elegí una tabla" not in texto
        assert soup.find("a", class_="dp-course-link") is not None

    def test_sin_puntos_numerados_no_corta_nada(self):
        """Mejor avisar que partir la caja en un lugar inventado."""
        soup = BeautifulSoup(
            '<table><tr><th><p>Una invitación sin puntos.</p></th></tr></table>',
            "html.parser")
        comentarios = [{
            "accion": "consigna_desde_el_punto",
            "instruccion": self.INSTRUCCION_M3,
            "anclado": "Una invitación sin puntos.",
        }]
        aplicar_comentarios(soup, comentarios)
        assert comentarios[0]["_aplicado"] is False
        assert "Una invitación sin puntos" in soup.get_text()

    def test_el_pedido_de_buzon_se_cumple_con_el_mismo_buzon(self):
        """La asesora pide el buzón en un globo aparte, anclado al párrafo
        que aclara que la actividad no es obligatoria. Avisarlo mandaba a
        revisar a mano algo que el otro comentario ya resolvió."""
        assert _clasificar(
            "Para maquetación: agregar buzón de entrega") == "buzon_de_entrega"
        soup = BeautifulSoup(
            '<table><tr><th><p><strong>¿Cómo vengo hasta acá?</strong></p>'
            '<p>Consigna.</p></th></tr></table>'
            '<p>La actividad no es obligatoria; sin embargo, se habilitará '
            'un espacio para subirla.</p>', "html.parser")
        comentarios = [
            {"accion": "consigna_de_sugerida",
             "instruccion": self.INSTRUCCION_M1,
             "anclado": "¿Cómo vengo hasta acá?"},
            {"accion": "buzon_de_entrega",
             "instruccion": "Para maquetación: agregar buzón de entrega",
             "anclado": "La actividad no es obligatoria; sin embargo, se "
                        "habilitará un espacio para subirla."},
        ]
        aplicar_comentarios(soup, comentarios)
        assert comentarios[1]["_aplicado"] is True

    def test_sin_buzon_abierto_el_pedido_sigue_pendiente(self):
        soup = BeautifulSoup(
            '<p>La actividad no es obligatoria; sin embargo, se habilitará '
            'un espacio para subirla.</p>', "html.parser")
        comentarios = [{
            "accion": "buzon_de_entrega",
            "instruccion": "Para maquetación: agregar buzón de entrega",
            "anclado": "La actividad no es obligatoria; sin embargo, se "
                       "habilitará un espacio para subirla.",
        }]
        aplicar_comentarios(soup, comentarios)
        assert not comentarios[0].get("_aplicado")
