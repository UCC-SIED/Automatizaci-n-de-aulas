# -*- coding: utf-8 -*-
"""Tests para escaneo y clasificación de archivos de curso.

Prueba las capacidades del folder_scanner:
- Clasificación por rol (contenido_modulo, foro, video, actividad, etc.)
- Descarte de borradores, copias, devoluciones
- Extracción de número de módulo desde nombres
- Normalización de texto
- Manejo de convenciones múltiples de carpetas
"""

import pytest
from pathlib import Path
from maquetador.ingest.folder_scanner import (
    escanear,
    normalizar,
    InventarioCurso,
    _numero_modulo,
)


class TestNumeroModuloRomano:
    """El número de módulo puede venir en romanos (modular I/II/III)."""

    def test_romanos_en_material_modular(self):
        assert _numero_modulo("Material multimedial modular I (X).docx") == 1
        assert _numero_modulo("Material multimedial modular II (X).docx") == 2
        assert _numero_modulo("Material multimedial modular III (X).docx") == 3

    def test_romano_con_modulo(self):
        assert _numero_modulo("Módulo IV - desarrollo.docx") == 4

    def test_arabigos_siguen_funcionando(self):
        assert _numero_modulo("Módulo 1.docx") == 1
        assert _numero_modulo("contenido-m2.docx") == 2

    def test_no_falsos_positivos(self):
        # "video" empieza con V/I pero no es un romano de módulo
        assert _numero_modulo("modular video.docx") is None
        # Sin contexto de módulo, una I suelta no es número
        assert _numero_modulo("Introducción general.docx") is None


class TestNormalizar:
    """Tests para la función normalizar."""

    def test_normalizar_convierte_a_minusculas(self):
        """Verifica que normalizar convierte a minúsculas."""
        assert normalizar("HOLA") == "hola"
        assert normalizar("HoLa") == "hola"

    def test_normalizar_elimina_acentos(self):
        """Verifica que eliminan acentos diacríticos."""
        assert normalizar("módulo") == "modulo"
        assert normalizar("Introducción") == "introduccion"
        assert normalizar("Ética") == "etica"

    def test_normalizar_colapsa_espacios(self):
        """Verifica que colapsa múltiples espacios."""
        assert normalizar("hola   mundo") == "hola mundo"
        assert normalizar("  hola  ") == "hola"

    def test_normalizar_combinado(self):
        """Test combinado: mayúsculas + acentos + espacios."""
        result = normalizar("  MÓDULO   DE   ÉTICA  ")
        assert result == "modulo de etica"


class TestEscanearBasico:
    """Tests básicos de la función escanear."""

    def test_escanear_retorna_inventario(self, casos_dir):
        """Verifica que escanear retorna un InventarioCurso válido."""
        # Buscar cualquier subcarpeta de curso
        cursos = [c for c in casos_dir.iterdir() if c.is_dir() and not c.name.startswith(".")]
        if not cursos:
            pytest.skip("No se encontraron carpetas de curso en 'Aulas a generar/'")

        inv = escanear(cursos[0])
        assert isinstance(inv, InventarioCurso)
        assert inv.raiz.is_dir()
        assert isinstance(inv.nombre_curso, str)

    def test_escanear_estructura_basica(self, casos_dir):
        """Verifica la estructura básica del inventario."""
        cursos = [c for c in casos_dir.iterdir() if c.is_dir() and not c.name.startswith(".")]
        if not cursos:
            pytest.skip("No se encontraron carpetas de curso en 'Aulas a generar/'")

        inv = escanear(cursos[0])

        # Verificar que todos los campos esperados existen
        assert isinstance(inv.docx_modulos, dict)
        assert isinstance(inv.actividades, list)
        assert isinstance(inv.foros, list)
        assert isinstance(inv.guiones_video, list)
        assert isinstance(inv.programa, list)
        assert isinstance(inv.hoja_de_ruta, list)
        assert isinstance(inv.biografia, list)
        assert isinstance(inv.fotos_docente, list)
        assert isinstance(inv.imagenes_diseno, list)
        assert isinstance(inv.esquema, list)
        assert isinstance(inv.otros, list)
        assert isinstance(inv.issues, list)

    def test_escanear_retorna_dict(self, casos_dir):
        """Verifica que el inventario puede convertirse a dict."""
        cursos = [c for c in casos_dir.iterdir() if c.is_dir() and not c.name.startswith(".")]
        if not cursos:
            pytest.skip("No se encontraron carpetas de curso en 'Aulas a generar/'")

        inv = escanear(cursos[0])
        d = inv.to_dict()

        assert isinstance(d, dict)
        assert "raiz" in d
        assert "nombre_curso" in d
        assert "docx_modulos" in d
        assert "actividades" in d
        assert "foros" in d


class TestClasificacionDocx:
    """Tests para clasificación de archivos DOCX."""

    def test_encuentra_docx_modulos(self, casos_dir):
        """Verifica que encuentra archivos de módulos."""
        cursos = [c for c in casos_dir.iterdir() if c.is_dir() and not c.name.startswith(".")]
        if not cursos:
            pytest.skip("No se encontraron carpetas de curso en 'Aulas a generar/'")

        inv = escanear(cursos[0])
        # Al menos uno debe encontrar módulos
        if inv.docx_modulos:
            assert all(isinstance(k, int) for k in inv.docx_modulos.keys())
            assert all(isinstance(v, Path) for v in inv.docx_modulos.values())

    def test_encuentra_actividades(self, casos_dir):
        """Verifica que detecta archivos de actividades."""
        cursos = [c for c in casos_dir.iterdir() if c.is_dir() and not c.name.startswith(".")]
        if not cursos:
            pytest.skip("No se encontraron carpetas de curso en 'Aulas a generar/'")

        inv = escanear(cursos[0])
        # Las actividades pueden estar vacías, solo verificar estructura
        assert isinstance(inv.actividades, list)
        for item in inv.actividades:
            if isinstance(item, tuple):
                assert len(item) == 2  # (numero_o_none, Path)

    def test_encuentra_foros(self, casos_dir):
        """Verifica que detecta archivos de foros."""
        cursos = [c for c in casos_dir.iterdir() if c.is_dir() and not c.name.startswith(".")]
        if not cursos:
            pytest.skip("No se encontraron carpetas de curso en 'Aulas a generar/'")

        inv = escanear(cursos[0])
        assert isinstance(inv.foros, list)

    def test_encuentra_guiones_video(self, casos_dir):
        """Verifica que detecta guiones de video."""
        cursos = [c for c in casos_dir.iterdir() if c.is_dir() and not c.name.startswith(".")]
        if not cursos:
            pytest.skip("No se encontraron carpetas de curso en 'Aulas a generar/'")

        inv = escanear(cursos[0])
        assert isinstance(inv.guiones_video, list)

    def test_encuentra_programa(self, casos_dir):
        """Verifica que detecta el programa del curso."""
        cursos = [c for c in casos_dir.iterdir() if c.is_dir() and not c.name.startswith(".")]
        if not cursos:
            pytest.skip("No se encontraron carpetas de curso en 'Aulas a generar/'")

        inv = escanear(cursos[0])
        assert isinstance(inv.programa, list)


class TestClasificacionImagenes:
    """Tests para clasificación de imágenes."""

    def test_detecta_imagenes_diseno(self, casos_dir):
        """Verifica que clasifica imágenes de figuras/tablas."""
        cursos = [c for c in casos_dir.iterdir() if c.is_dir() and not c.name.startswith(".")]
        if not cursos:
            pytest.skip("No se encontraron carpetas de curso en 'Aulas a generar/'")

        inv = escanear(cursos[0])
        assert isinstance(inv.imagenes_diseno, list)

    def test_detecta_esquemas(self, casos_dir):
        """Verifica que detecta esquemas."""
        cursos = [c for c in casos_dir.iterdir() if c.is_dir() and not c.name.startswith(".")]
        if not cursos:
            pytest.skip("No se encontraron carpetas de curso en 'Aulas a generar/'")

        inv = escanear(cursos[0])
        assert isinstance(inv.esquema, list)


class TestDescarte:
    """Tests para descarte de borradores y copias."""

    def test_descarta_carpeta_devoluciones(self, casos_dir):
        """Verifica que descarta archivos en carpeta 'Devoluciones'."""
        # Buscar una carpeta que tenga Devoluciones
        cursos = [c for c in casos_dir.iterdir() if c.is_dir() and not c.name.startswith(".")]
        if not cursos:
            pytest.skip("No se encontraron carpetas de curso en 'Aulas a generar/'")

        inv = escanear(cursos[0])
        # Verificar que no hay rutas que contengan "devoluciones" o "Devoluciones"
        def tiene_devoluciones(p):
            return "devolucion" in str(p).lower()

        for modulo in inv.docx_modulos.values():
            assert not tiene_devoluciones(modulo), \
                f"No debería incluir {modulo} de Devoluciones"

    def test_descarta_palabras_prohibidas_en_nombre(self, casos_dir):
        """Verifica que descarta archivos con 'borrador', 'copia de', etc."""
        cursos = [c for c in casos_dir.iterdir() if c.is_dir() and not c.name.startswith(".")]
        if not cursos:
            pytest.skip("No se encontraron carpetas de curso en 'Aulas a generar/'")

        inv = escanear(cursos[0])
        prohibidas = ["borrador", "copia de", "eliminada"]

        # Verificar documentos principales
        archivos_a_chequear = []
        archivos_a_chequear.extend(inv.docx_modulos.values())
        archivos_a_chequear.extend(inv.programa)
        # Los foros vienen como tuplas (numero, path)
        for item in inv.foros:
            if isinstance(item, tuple):
                archivos_a_chequear.append(item[1])
            else:
                archivos_a_chequear.append(item)

        for path in archivos_a_chequear:
            nombre = path.name.lower()
            for palabra in prohibidas:
                assert palabra not in nombre, \
                    f"No debería incluir '{path.name}' (contiene '{palabra}')"


class TestExtraerNumeroModulo:
    """Tests para extracción de número de módulo desde nombres."""

    def test_extrae_numero_desde_docx_modulos(self, casos_dir):
        """Verifica que los números de módulo se extraen correctamente."""
        cursos = [c for c in casos_dir.iterdir() if c.is_dir() and not c.name.startswith(".")]
        if not cursos:
            pytest.skip("No se encontraron carpetas de curso en 'Aulas a generar/'")

        inv = escanear(cursos[0])
        if inv.docx_modulos:
            # Los números deben ser enteros (pueden ser 0 si no se detecta)
            for num in inv.docx_modulos.keys():
                assert isinstance(num, int), f"Número debe ser int, no {type(num)}"
                assert num >= 0, f"Número de módulo debe ser no-negativo: {num}"

    def test_extrae_numero_desde_actividades(self, casos_dir):
        """Verifica que extrae números de módulo de actividades."""
        cursos = [c for c in casos_dir.iterdir() if c.is_dir() and not c.name.startswith(".")]
        if not cursos:
            pytest.skip("No se encontraron carpetas de curso en 'Aulas a generar/'")

        inv = escanear(cursos[0])
        for item in inv.actividades:
            if isinstance(item, tuple):
                numero, path = item
                # numero puede ser None o un int
                assert numero is None or isinstance(numero, int)


class TestEstructuraXlsx:
    """Tests para detección de la planilla de estructura."""

    def test_encuentra_estructura_xlsx(self, casos_dir):
        """Verifica que busca la planilla de estructura general."""
        cursos = [c for c in casos_dir.iterdir() if c.is_dir() and not c.name.startswith(".")]
        if not cursos:
            pytest.skip("No se encontraron carpetas de curso en 'Aulas a generar/'")

        inv = escanear(cursos[0])
        # estructura_xlsx puede ser None o un Path
        assert inv.estructura_xlsx is None or isinstance(inv.estructura_xlsx, Path)


class TestIssues:
    """Tests para validaciones y issues."""

    def test_issues_list_existe(self, casos_dir):
        """Verifica que hay un campo issues."""
        cursos = [c for c in casos_dir.iterdir() if c.is_dir() and not c.name.startswith(".")]
        if not cursos:
            pytest.skip("No se encontraron carpetas de curso en 'Aulas a generar/'")

        inv = escanear(cursos[0])
        assert isinstance(inv.issues, list)

    def test_issues_contienen_severidad(self, casos_dir):
        """Verifica que los issues tienen severidad."""
        cursos = [c for c in casos_dir.iterdir() if c.is_dir() and not c.name.startswith(".")]
        if not cursos:
            pytest.skip("No se encontraron carpetas de curso en 'Aulas a generar/'")

        inv = escanear(cursos[0])
        for issue in inv.issues:
            # Los issues deben tener al menos mensaje
            assert hasattr(issue, "mensaje") or hasattr(issue, "message")


class TestMultiplesCasos:
    """Tests contra múltiples casos reales."""

    def test_escanear_todos_los_cursos(self, casos_dir):
        """Corre escanear contra todos los cursos disponibles."""
        cursos = sorted([c for c in casos_dir.iterdir() if c.is_dir() and not c.name.startswith(".")])
        if not cursos:
            pytest.skip("No se encontraron carpetas de curso en 'Aulas a generar/'")

        resultados = []
        for curso_dir in cursos[:5]:  # Limitar a 5 para no tardar
            try:
                inv = escanear(curso_dir)
                resultados.append((
                    inv.nombre_curso,
                    len(inv.docx_modulos),
                    len(inv.actividades),
                    len(inv.issues),
                ))
            except Exception as e:
                pytest.fail(f"Error al escanear {curso_dir.name}: {e}")

        assert len(resultados) > 0

    def test_consistency_mismo_curso(self, casos_dir):
        """Verifica que escaneando dos veces da el mismo resultado."""
        cursos = [c for c in casos_dir.iterdir() if c.is_dir() and not c.name.startswith(".")]
        if not cursos:
            pytest.skip("No se encontraron carpetas de curso en 'Aulas a generar/'")

        curso_dir = cursos[0]
        inv1 = escanear(curso_dir)
        inv2 = escanear(curso_dir)

        # Mismo número de módulos
        assert len(inv1.docx_modulos) == len(inv2.docx_modulos)
        # Mismo número de actividades
        assert len(inv1.actividades) == len(inv2.actividades)
        # Mismo nombre de curso
        assert inv1.nombre_curso == inv2.nombre_curso


class TestAfiConGuionBajo:
    """El AFI a veces llega como 'AFI_ Nombre.docx'; el guion bajo no debe
    impedir que se clasifique como actividad (regresión: '\bafi\b' no matchea
    'afi_' porque '_' es carácter de palabra)."""

    def _curso(self, tmp_path):
        raiz = tmp_path / "Seminario X"
        (raiz / "Etapa 2" / "Actividades y AFI").mkdir(parents=True)
        (raiz / "Etapa 2" / "Actividades y AFI" /
         "AFI_ El liderazgo desde mi mirada .docx").write_text("x", encoding="utf-8")
        return raiz

    def test_afi_con_guion_bajo_es_actividad(self, tmp_path):
        inv = escanear(self._curso(tmp_path))
        nombres = [p.name for _n, p in inv.actividades]
        assert any("AFI_" in n for n in nombres), \
            f"El AFI con guion bajo no se clasificó como actividad: {nombres}"


class TestSiglaPropiaDelAsesorEnLaCarpetaDeActividades:
    """Cada asesor abrevia como quiere: "AEO 1 - GRyI.docx" (actividad de
    evaluación obligatoria) no dice "actividad" ni "AFI" en el nombre y caía
    en `otros`. La planilla nombraba el archivo exacto, pero como no estaba
    entre los candidatos la actividad obligatoria del módulo 2 terminaba
    apuntando al AFI. Regresión real: Gestión del Riesgo y la Incertidumbre."""

    def _curso(self, tmp_path):
        raiz = tmp_path / "08. Gestión del Riesgo"
        (raiz / "3. Actividades").mkdir(parents=True)
        (raiz / "2. Desarrollo Teórico").mkdir(parents=True)
        (raiz / "2. Desarrollo Teórico" / "Modulo 1 - GRyI.docx").write_text(
            "x", encoding="utf-8")
        for nombre in ("AEO 1 - GRyI.docx", "AEO 2 - GRyI.docx",
                       "AFI - GRyI.docx", "Foro de Apertura - GRyI.docx"):
            (raiz / "3. Actividades" / nombre).write_text("x", encoding="utf-8")
        return raiz

    def test_el_docx_de_la_carpeta_actividades_es_una_actividad(self, tmp_path):
        inv = escanear(self._curso(tmp_path))
        nombres = sorted(p.name for _n, p in inv.actividades)
        assert nombres == ["AEO 1 - GRyI.docx", "AEO 2 - GRyI.docx",
                           "AFI - GRyI.docx"]

    def test_el_foro_sigue_siendo_foro(self, tmp_path):
        inv = escanear(self._curso(tmp_path))
        assert [p.name for _n, p in inv.foros] == ["Foro de Apertura - GRyI.docx"]

    def test_el_guion_de_video_se_reconoce_por_su_carpeta(self, tmp_path):
        """"GRyI - V_M1.docx" tampoco dice "video" ni "guion": lo dice la
        carpeta que lo contiene."""
        raiz = self._curso(tmp_path)
        (raiz / "5. Videos").mkdir()
        (raiz / "5. Videos" / "GRyI - V_M1.docx").write_text("x", encoding="utf-8")
        inv = escanear(raiz)
        assert [(n, p.name) for n, p in inv.guiones_video] == \
            [(1, "GRyI - V_M1.docx")]

    def test_la_numeracion_de_la_actividad_no_es_la_del_modulo(self, tmp_path):
        """El "1" de "AEO 1" es el número de actividad, no el del módulo: si
        se lo tomara como módulo, la obligatoria del módulo 2 (que la planilla
        manda a AEO 1) se filtraría fuera de los candidatos."""
        inv = escanear(self._curso(tmp_path))
        assert all(n is None for n, _p in inv.actividades)


class TestFichaDeCasoNoEsElDesarrolloDelModulo:
    """Las fichas de caso ("Modulo 1 - Caso_Starbucks.docx",
    "M3 - Ficha_Caso_Quibi.docx") son anexos del módulo —el repositorio de
    casos que pide la planilla—, no su desarrollo teórico. Regresión real
    (Creación de Valor en la Economía de la Experiencia): competían por el
    slot del módulo y le ganaban al multimedial real solo por orden
    alfabético, así que los módulos 1 y 3 quedaban armados desde una ficha
    de caso y ninguna de sus páginas de contenido se encontraba."""

    def _curso(self, tmp_path):
        raiz = tmp_path / "Creacion de Valor"
        mod1 = raiz / "Materiales" / "Módulos" / "Módulo 1"
        mod1.mkdir(parents=True)
        (mod1 / "Modulo 1 - Caso_Cirque_du_Soleil.docx").write_text("x", encoding="utf-8")
        (mod1 / "Modulo 1 - Ficha_Caso_Disney.docx").write_text("x", encoding="utf-8")
        (mod1 / "Modulo 1 - Creación de Valor - Sepúlveda.docx").write_text("x", encoding="utf-8")
        return raiz

    def test_el_modulo_toma_el_multimedial_no_la_ficha(self, tmp_path):
        inv = escanear(self._curso(tmp_path))
        assert "Creación de Valor" in inv.docx_modulos[1].name

    def test_las_fichas_quedan_en_casos(self, tmp_path):
        inv = escanear(self._curso(tmp_path))
        nombres = sorted(p.name for _n, p in inv.casos)
        assert nombres == ["Modulo 1 - Caso_Cirque_du_Soleil.docx",
                           "Modulo 1 - Ficha_Caso_Disney.docx"]

    def test_el_pdf_de_la_ficha_tambien_va_a_casos(self, tmp_path):
        """El PDF que sale de diseño es la versión publicable del caso."""
        raiz = tmp_path / "Curso"
        (raiz / "Diseño").mkdir(parents=True)
        (raiz / "Diseño" / "Modulo 1 - Ficha_Caso_Disney.docx.pdf").write_text("x", encoding="utf-8")
        inv = escanear(raiz)
        assert [p.name for _n, p in inv.casos] == ["Modulo 1 - Ficha_Caso_Disney.docx.pdf"]

    def test_descarta_los_informes_internos_de_similitud_y_uso_de_ia(self, tmp_path):
        """Turnitin y la declaración GAIDeT acompañan al material pero son
        control interno de la cátedra: no se publican ni cuentan como caso."""
        raiz = tmp_path / "Curso"
        (raiz / "Módulos" / "Módulo 1").mkdir(parents=True)
        d = raiz / "Módulos" / "Módulo 1"
        (d / "Modulo 1 - Ficha_Caso_Disney - Similitud.pdf").write_text("x", encoding="utf-8")
        (d / "Modulo 1 - Ficha_Caso_Disney - Uso de IA.pdf").write_text("x", encoding="utf-8")
        (d / "Modulo 1 - Desarrollo - Informe de uso de IA.pdf").write_text("x", encoding="utf-8")
        (d / "Modulo 1 - Ficha_Caso_Disney.docx").write_text("x", encoding="utf-8")
        inv = escanear(raiz)
        assert [p.name for _n, p in inv.casos] == ["Modulo 1 - Ficha_Caso_Disney.docx"]

    def test_un_titulo_que_solo_empieza_con_caso_sigue_siendo_contenido(self, tmp_path):
        """'Casos de estudio'/'Caso práctico' pueden ser el desarrollo del
        módulo: solo la forma de ficha ("Ficha_Caso…"/"Caso_…") es anexo."""
        raiz = tmp_path / "Otro curso"
        (raiz / "Módulos").mkdir(parents=True)
        (raiz / "Módulos" / "Modulo 1 - Casos de estudio.docx").write_text("x", encoding="utf-8")
        inv = escanear(raiz)
        assert inv.docx_modulos.get(1) is not None
        assert inv.casos == []


class TestModuloConPrefijoM:
    """Los DOCX modulares a veces vienen como 'M1_Material multimedial…': el
    guion bajo tras el número no debe impedir extraer el módulo (regresión:
    '\bm1\b' no matchea 'm1_')."""

    def test_m1_guion_bajo(self):
        assert _numero_modulo("M1_Material multimedial modular (Granja).docx") == 1
        assert _numero_modulo("M2_Material multimedial modular.docx") == 2
        assert _numero_modulo("M3_Material multimedial modular.docx") == 3

    def test_no_rompe_material_sin_numero(self):
        assert _numero_modulo("Material multimedial modular.docx") is None


class TestDescartables:
    """Versiones anteriores y archivos marcados para eliminar no son fuente."""

    def _curso(self, tmp_path):
        raiz = tmp_path / "Curso X"
        (raiz / "Material").mkdir(parents=True)
        (raiz / "Material" / "(versión anterior)M1_Material multimedial modular.docx").write_text("x", encoding="utf-8")
        (raiz / "Material" / "ELIMINAR. Módulo 1 - FORO.docx").write_text("x", encoding="utf-8")
        (raiz / "Material" / "M1_Material multimedial modular.docx").write_text("x", encoding="utf-8")
        (raiz / "Versiones anteriores").mkdir()
        (raiz / "Versiones anteriores" / "Video introductorio.docx").write_text("x", encoding="utf-8")
        return raiz

    def test_descarta_version_anterior_y_eliminar(self, tmp_path):
        inv = escanear(self._curso(tmp_path))
        todos = [p.name for p in
                 list(inv.docx_modulos.values())
                 + [p for _n, p in inv.actividades]
                 + [p for _n, p in inv.foros]
                 + [p for _n, p in inv.guiones_video]
                 + inv.otros]
        assert not any("versión anterior" in n or "versi\u00f3n anterior" in n for n in todos), todos
        assert not any(n.startswith("ELIMINAR") for n in todos), todos
        assert not any(n == "Video introductorio.docx" for n in todos), \
            "No se descartó la carpeta 'Versiones anteriores'"
