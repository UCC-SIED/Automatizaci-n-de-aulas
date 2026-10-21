# -*- coding: utf-8 -*-
"""Banners del plugin de Figma.

El plugin lee la MISMA planilla que el maquetador y saca un PNG por página
("1.3.1.png") y uno por módulo ("M2.png"). Hasta ahora esos archivos se
subían a Canvas y se asignaban a mano: el paquete salía con 6 páginas con
banner y 24 sin. Con `--banners` viajan adentro del .imscc y cada página
sale con el suyo.
"""

import io
import zipfile

import pytest
from PIL import Image

from maquetador.build.imscc_builder import GeneradorAula, clave_de_banner
from maquetador.models import CourseSpec


def _png():
    buf = io.BytesIO()
    Image.new("RGB", (1100, 221), (27, 30, 49)).save(buf, "PNG")
    return buf.getvalue()


def _zip(tmp_path, nombres):
    z = tmp_path / "banners.zip"
    with zipfile.ZipFile(z, "w") as f:
        for n in nombres:
            f.writestr(n, _png())
    return z


class TestLaClaveSaleDelNombre:
    """El equipo venía subiendo los mismos archivos con seis nombres
    distintos en una sola materia, tres de ellos con el "(2)" que Canvas
    agrega cuando el nombre ya existe. La clave se saca del número."""

    @pytest.mark.parametrize("nombre,clave", [
        ("1.3.1.png", "1.3.1"),              # como lo deja el plugin
        ("1.1.1..png", "1.1.1"),             # con el punto de la numeración
        ("2.3.2.png", "2.3.2"),
        ("1.3. (2).png", "1.3"),             # sufijo de Canvas
        ("1.3.3. Estructura y funciones del cerebro.png", "1.3.3"),
        ("M2.png", "M2"),
        ("M1 (8).png", "M1"),
        ("m3.PNG", "M3"),
        ("banner generico.png", ""),
    ])
    def test_cada_forma_da_la_misma_clave(self, nombre, clave):
        assert clave_de_banner(nombre) == clave


class TestCargaDelZip:
    def _gen(self, tmp_path, origen):
        spec = CourseSpec(nombre="x")
        spec.banners = str(origen)
        return GeneradorAula(spec, {}, tmp_path), spec

    def test_lee_el_zip_y_normaliza_los_nombres(self, tmp_path):
        z = _zip(tmp_path, ["1.1..png", "1.1.1.png", "M2.png"])
        gen, _ = self._gen(tmp_path, z)
        banners = gen._cargar_banners()
        assert sorted(banners) == ["1.1", "1.1.1", "M2"]
        # Se republica con el nombre normalizado, no con el que vino.
        assert banners["1.1"][0] == "1.1.png"

    def test_tambien_acepta_una_carpeta(self, tmp_path):
        carpeta = tmp_path / "sueltos"
        carpeta.mkdir()
        (carpeta / "2.4.png").write_bytes(_png())
        (carpeta / "leeme.txt").write_text("no es un banner")
        gen, _ = self._gen(tmp_path, carpeta)
        assert sorted(gen._cargar_banners()) == ["2.4"]

    def test_dos_archivos_para_la_misma_pagina_avisan(self, tmp_path):
        z = _zip(tmp_path, ["1.3.png", "1.3. (2).png"])
        gen, spec = self._gen(tmp_path, z)
        banners = gen._cargar_banners()
        assert sorted(banners) == ["1.3"]
        assert any("misma numeración" in i.mensaje for i in spec.issues)

    def test_sin_banners_no_hace_nada(self, tmp_path):
        gen, _ = self._gen(tmp_path, "")
        assert gen._cargar_banners() == {}

    def test_una_ruta_que_no_existe_es_bloqueante(self, tmp_path):
        from maquetador.models import Severidad
        gen, spec = self._gen(tmp_path, tmp_path / "no-esta.zip")
        assert gen._cargar_banners() == {}
        assert any(i.severidad == Severidad.BLOQUEANTE for i in spec.issues)


class TestAQuePaginaVaCadaUno:
    @pytest.mark.parametrize("titulo,clave", [
        ("1.3.1. La arquitectura de una neurona", "1.3.1"),
        ("2.4. Claves del neuroliderazgo para el éxito", "2.4"),
        ("3.5. Modelo Integrado (MINE)", "3.5"),
        ("Introducción", ""),
    ])
    def test_la_clave_sale_del_titulo_de_la_pagina(self, titulo, clave):
        assert GeneradorAula._clave_de_titulo(titulo) == clave

    def test_la_url_apunta_a_la_carpeta_del_aula(self, tmp_path):
        spec = CourseSpec(nombre="x")
        spec.banners = str(_zip(tmp_path, ["1.3.1.png"]))
        gen = GeneradorAula(spec, {}, tmp_path)
        gen.banners = gen._cargar_banners()
        url = gen._banner_de("1.3.1")
        assert url == ("$IMS-CC-FILEBASE$/Contenido%20multimedia%20cargado/"
                       "1.3.1.png")
        assert "1.3.1" in gen.banners_usados

    def test_una_pagina_sin_banner_no_rompe(self, tmp_path):
        spec = CourseSpec(nombre="x")
        gen = GeneradorAula(spec, {}, tmp_path)
        assert gen._banner_de("9.9") == ""
