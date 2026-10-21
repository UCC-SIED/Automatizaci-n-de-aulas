# -*- coding: utf-8 -*-
"""Lo que trajo el modelo viejo de asesoría (IA Aplicada I, Virgolini).

Material de abril de 2025: las carpetas se llaman "1. Programa", "4.
Materiales"… en vez de "Etapa N", la bibliografía y la hoja de ruta van
aparte, y la planilla numera las actividades en la misma serie que las
páginas de contenido.
"""

import pytest

from maquetador.ingest.xlsx_parser import (_clasificar_item, _sin_numeracion,
                                           _normalizar_numeracion_titulo)
from maquetador.models import TipoItem


class TestLaActividadNumeradaComoPagina:
    """"1.6. Actividad M1- obligatoria (individual)" venía después de 1.1 a
    1.4 y salía como página: sin buzón de entrega y pidiéndole al DOCX una
    sección que no existe. Era bloqueante."""

    def test_en_la_seccion_de_actividades_es_una_tarea(self):
        assert _clasificar_item(
            "1.6. Actividad M1- obligatoria (individual)",
            "actividades") == TipoItem.TAREA

    @pytest.mark.parametrize("titulo", [
        "2.5. Tarea del módulo",
        "3.7. Trabajo práctico integrador",
    ])
    def test_las_otras_formas_de_nombrarla(self, titulo):
        assert _clasificar_item(titulo, "actividades") == TipoItem.TAREA

    def test_una_pagina_numerada_sigue_siendo_pagina(self):
        assert _clasificar_item(
            "1.2. Conceptos de Big Data y su importancia",
            "contenidos") == TipoItem.PAGINA

    def test_una_pagina_que_habla_de_actividades_no_se_confunde(self):
        """Está en contenidos: es una página aunque la palabra aparezca."""
        assert _clasificar_item(
            "2.3. Actividades económicas y su automatización",
            "contenidos") == TipoItem.PAGINA


class TestElNumeroNoVaEnElTituloDeLaActividad:
    """La numeración es de las páginas. La actividad entra al aula por su
    nombre: en Canvas vive en el buzón, no en el recorrido del módulo."""

    def test_le_saca_el_numero(self):
        assert _sin_numeracion("1.6. Actividad M1- obligatoria (individual)") \
            == "Actividad M1- obligatoria (individual)"

    @pytest.mark.parametrize("entrada,esperado", [
        ("2.5 Tarea del módulo", "Tarea del módulo"),
        ("3.7.- Trabajo práctico", "Trabajo práctico"),
        ("1.1. Actividad", "Actividad"),
    ])
    def test_las_distintas_puntuaciones(self, entrada, esperado):
        assert _sin_numeracion(entrada) == esperado

    def test_un_titulo_sin_numero_no_cambia(self):
        assert _sin_numeracion("Actividad obligatoria (grupal)") \
            == "Actividad obligatoria (grupal)"

    def test_si_el_numero_era_todo_el_titulo_se_conserva(self):
        assert _sin_numeracion("1.6.") == "1.6."

    def test_las_paginas_conservan_su_numeracion(self):
        """La convención de título UCC no cambia para las páginas."""
        assert _normalizar_numeracion_titulo("1.2 Conceptos de Big Data") \
            == "1.2. Conceptos de Big Data"


class TestLaFotoSueltaEnLaRaiz:
    """El modelo viejo dejaba la foto del docente en la raíz de la carpeta,
    junto a la biodata y la planilla, con el nombre que le puso la cámara
    ("DSC06278.jpg"): no la delata ni el nombre ni la carpeta."""

    def _curso(self, tmp_path, *archivos):
        raiz = tmp_path / "Curso"
        (raiz / "Etapa 4 - Maquetación").mkdir(parents=True)
        (raiz / "Etapa 4 - Maquetación"
         / "Estructura general - Para maquetación.xlsx").write_bytes(b"x")
        (raiz / "Etapa 1 - Programa").mkdir()
        for nombre in archivos:
            destino = raiz / nombre
            destino.parent.mkdir(parents=True, exist_ok=True)
            destino.write_bytes(b"x")
        return tmp_path

    def test_la_toma_como_foto_del_docente(self, tmp_path):
        from maquetador.ingest.folder_scanner import escanear
        inv = escanear(self._curso(tmp_path, "DSC06278.jpg"))
        assert [p.name for p in inv.fotos_docente] == ["DSC06278.jpg"]

    def test_avisa_para_que_se_verifique(self, tmp_path):
        """Es la rama menos segura de todas."""
        from maquetador.ingest.folder_scanner import escanear
        inv = escanear(self._curso(tmp_path, "DSC06278.jpg"))
        assert any("DSC06278.jpg" in i.mensaje for i in inv.issues)

    def test_un_logo_en_la_raiz_no_es_la_foto(self, tmp_path):
        from maquetador.ingest.folder_scanner import escanear
        inv = escanear(self._curso(tmp_path, "logo-ucc.png"))
        assert inv.fotos_docente == []

    def test_una_figura_en_la_raiz_tampoco(self, tmp_path):
        from maquetador.ingest.folder_scanner import escanear
        inv = escanear(self._curso(tmp_path, "Figura 2_M1_Pilares.jpg"))
        assert inv.fotos_docente == []

    def test_una_imagen_en_una_subcarpeta_no_entra_por_esta_rama(self, tmp_path):
        from maquetador.ingest.folder_scanner import escanear
        inv = escanear(self._curso(tmp_path, "Diseño/DSC06278.jpg"))
        assert inv.fotos_docente == []


class TestElEsquemaVaComoImagen:
    """Si la carpeta trae también el DOCX con el que armaron el esquema, la
    imagen tiene que ir primero: el generador avisaba que no la encontraba
    aunque estuviera al lado."""

    def test_la_imagen_gana_al_docx(self, tmp_path):
        from maquetador.ingest.folder_scanner import escanear
        from maquetador.ingest.reconciler import reconciliar
        from maquetador.models import CourseSpec, ItemCurso, TipoItem
        raiz = tmp_path / "Curso"
        (raiz / "Etapa 4 - Maquetación").mkdir(parents=True)
        (raiz / "Etapa 4 - Maquetación"
         / "Estructura general - Para maquetación.xlsx").write_bytes(b"x")
        (raiz / "Etapa 1 - Programa").mkdir()
        (raiz / "Esquema conceptual- Virgolini.docx").write_bytes(b"x")
        (raiz / "Esquema Inteligencia Artificial.jpg").write_bytes(b"x")
        inv = escanear(tmp_path)
        spec = CourseSpec(nombre="Materia")
        spec.items_inicio = [ItemCurso(
            titulo="Esquema introductorio a la asignatura",
            tipo=TipoItem.IMAGEN, orden=1)]
        reconciliar(spec, inv)
        assert spec.items_inicio[0].fuente.archivo.suffix == ".jpg"


class TestLosBloquesDeCodigo:
    """El módulo 2 trae ejemplos de Python. Word los manda como un párrafo
    por línea —con la sangría adentro del texto, que es lo que los salva—
    así que publicados tal cual quedaban párrafos sueltos, sin sangría ni
    saltos, imposibles de leer y de copiar."""

    CODIGO = ("<p># Creación de un diccionario</p>"
              "<p>estudiante = {</p>"
              '<p>    "nombre": "Juan",</p>'
              '<p>    "edad": 21,</p>'
              "<p>}</p>")

    def _procesar(self, html):
        from maquetador.build.snippets import procesar_contenido
        return procesar_contenido(html)

    def test_se_juntan_en_un_solo_bloque(self):
        out = self._procesar(self.CODIGO)
        assert out.count("<pre") == 1

    def test_conserva_la_sangria(self):
        out = self._procesar(self.CODIGO)
        assert '    "nombre": "Juan",' in out

    def test_conserva_los_saltos_de_linea(self):
        out = self._procesar(self.CODIGO)
        assert "estudiante = {\n" in out

    def test_va_en_monoespaciada(self):
        assert "monospace" in self._procesar(self.CODIGO)

    def test_no_se_lleva_la_prosa_de_alrededor(self):
        out = self._procesar(
            "<p>Un diccionario en Python es una colección de elementos.</p>"
            + self.CODIGO +
            "<p>Con Pandas se pueden cargar datos desde archivos CSV.</p>")
        assert "<p>Un diccionario en Python" in out
        assert "<p>Con Pandas se pueden cargar" in out

    @pytest.mark.parametrize("html", [
        # Una enumeración sangrada no es código.
        "<p>   El primer punto del análisis.</p>"
        "<p>   El segundo punto del análisis.</p>",
        # Una sola línea tampoco, aunque parezca.
        "<p># Un comentario suelto en el texto</p>",
    ])
    def test_lo_que_no_es_codigo_queda_como_esta(self, html):
        assert "<pre" not in self._procesar(html)

    def test_escapa_lo_que_mete_adentro(self):
        out = self._procesar(
            "<p>if x &lt; 3:</p><p>    print(&quot;hola&quot;)</p>")
        assert "&lt;" in out and "<pre" in out
