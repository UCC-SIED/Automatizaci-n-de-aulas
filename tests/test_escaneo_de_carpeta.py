# -*- coding: utf-8 -*-
"""Lo que rompe el escaneo antes de poder mirar el contenido.

Dos bloqueantes reales, los dos de "Medios, tecnologías digitales y
lenguajes en educación": una carpeta cuyo nombre termina en espacio y una
planilla que no se llama como se tiene que llamar.
"""

import os

import pytest

from maquetador.ingest.folder_scanner import (_encontrar_raiz, _ruta_accesible,
                                              escanear)


solo_windows = pytest.mark.skipif(
    os.name != "nt", reason="el recorte de espacios finales es de Windows")


class TestCarpetaConEspacioAlFinal:
    """Windows recorta el espacio final al resolver la ruta, así que la
    carpeta existe y se lista desde afuera, pero `is_dir()` dice que no. El
    ZIP llegó con "…lenguajes en educación " y el escaneo veía una carpeta
    vacía: ni planilla ni módulos, todo bloqueante."""

    @pytest.fixture
    def arbol(self, tmp_path):
        # El árbol hay que crearlo con el prefijo \\?\, porque si no Windows
        # le recorta el espacio final también al crearlo y la prueba no
        # reproduce nada.
        curso = tmp_path / "Curso de prueba "      # ← el espacio del problema
        prefijo = "\\\\?\\" if os.name == "nt" else ""
        try:
            os.mkdir(prefijo + str(curso))
            # Dos etapas, como cualquier curso real: con una sola, el
            # desenvoltorio de carpetas-envase bajaría un nivel de más.
            os.mkdir(prefijo + str(curso / "Etapa 1 - Programa"))
            os.mkdir(prefijo + str(curso / "Etapa 4 - Maquetación"))
            with open(prefijo + str(curso / "Etapa 4 - Maquetación"
                                    / "Estructura general - Para maquetación.xlsx"),
                      "wb") as f:
                f.write(b"x")
        except OSError:
            pytest.skip("el sistema de archivos no acepta el espacio final")
        return tmp_path, curso

    @solo_windows
    def test_sin_el_arreglo_la_carpeta_parece_no_existir(self, arbol):
        """La comprobación que fallaba, para dejar claro qué se está
        esquivando."""
        _tmp, curso = arbol
        assert curso.is_dir() is False

    def test_se_encuentra_la_raiz_igual(self, arbol):
        tmp, curso = arbol
        raiz = _encontrar_raiz(tmp)
        assert raiz.name.strip() == "Curso de prueba"
        assert any(h.name.startswith("Etapa 4") for h in raiz.iterdir())

    def test_la_ruta_queda_usable(self, arbol):
        _tmp, curso = arbol
        usable = _ruta_accesible(curso)
        assert usable.is_dir()
        assert list(usable.rglob("*.xlsx"))

    def test_una_carpeta_normal_no_se_toca(self, tmp_path):
        normal = tmp_path / "Curso normal"
        normal.mkdir()
        assert _ruta_accesible(normal) == normal


class TestNombreDeLaPlanilla:
    """El nombre canónico es "Estructura general - Para maquetación", pero
    el asesor de esta materia la guardó como "Para maquetación (1210124_…)".
    Sin planilla no hay estructura: es bloqueante."""

    def _curso(self, tmp_path, nombre_planilla, etapa="Etapa 4 - Maquetación"):
        curso = tmp_path / "Curso"
        (curso / etapa).mkdir(parents=True)
        (curso / etapa / nombre_planilla).write_bytes(b"x")
        return tmp_path

    def test_el_nombre_canonico(self, tmp_path):
        raiz = self._curso(
            tmp_path, "Estructura general - Para maquetación (1200137).xlsx")
        assert escanear(raiz).estructura_xlsx is not None

    def test_sin_la_palabra_estructura_pero_en_la_etapa_4(self, tmp_path):
        raiz = self._curso(
            tmp_path, "Para maquetación (1210124_Medios_tecnologías).xlsx")
        inv = escanear(raiz)
        assert inv.estructura_xlsx is not None
        assert inv.estructura_xlsx.name.startswith("Para maquetación")

    def test_con_el_guion_bajo_de_esta_catedra(self, tmp_path):
        """Esa carpeta se llama "Etapa 4_ Maquetación", con guion bajo."""
        raiz = self._curso(tmp_path, "Para maquetación (1210124).xlsx",
                           etapa="Etapa 4_ Maquetación")
        assert escanear(raiz).estructura_xlsx is not None

    def test_un_xlsx_cualquiera_no_es_la_planilla(self, tmp_path):
        raiz = self._curso(tmp_path, "Cronograma de la asignatura.xlsx")
        assert escanear(raiz).estructura_xlsx is None

    def test_un_xlsx_de_otra_etapa_tampoco(self, tmp_path):
        raiz = self._curso(tmp_path, "Notas para maquetación.xlsx",
                           etapa="Etapa 2 - Materiales")
        assert escanear(raiz).estructura_xlsx is None
