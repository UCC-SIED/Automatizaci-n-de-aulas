# -*- coding: utf-8 -*-
"""La foto del docente cuando llega con pocos píxeles.

La ficha de la página de inicio la muestra en un círculo de 150x150 CSS y
las pantallas de hoy son de alta densidad, así que el navegador pide varias
veces esos píxeles. Si la foto viene chica, estirarla la deja borrosa — que
es como se vio la de Evelin Pineda, subida a mano porque la carpeta del
curso no traía ninguna.

Ahora el maquetador la lleva siempre al tamaño de publicación: reduce la
que viene grande (y de paso saca megabytes del paquete) y agranda con
enfoque la que viene chica. Detalle que la foto no tiene no se inventa, así
que además se avisa para pedir una mejor.
"""

from pathlib import Path

import pytest
from PIL import Image

from maquetador.build.imagenes import LADO_FICHA
from maquetador.build.imscc_builder import GeneradorAula
from maquetador.models import CourseSpec


def _generador(tmp_path):
    spec = CourseSpec(nombre="Materia")
    spec.tema = "educacion"
    g = GeneradorAula(spec, {}, tmp_path)
    g.working = tmp_path
    return g


class TestElAvisoDeFotoChica:
    def test_avisa_cuando_el_recorte_queda_chico(self, tmp_path):
        g = _generador(tmp_path)
        g._avisar_si_la_foto_es_chica(180, Path("Foto docente.jpg"))
        assert any("180x180" in i.mensaje for i in g.spec.issues)
        assert any("menos nítida" in i.mensaje for i in g.spec.issues)

    def test_dice_que_la_agrando_igual(self, tmp_path):
        """No es un error: el paquete sale bien, pero conviene una mejor."""
        g = _generador(tmp_path)
        g._avisar_si_la_foto_es_chica(150, Path("f.jpg"))
        assert any("agrandé y la enfoqué" in i.mensaje for i in g.spec.issues)

    def test_no_avisa_con_una_foto_grande(self, tmp_path):
        g = _generador(tmp_path)
        g._avisar_si_la_foto_es_chica(2428, Path("ADRIANA.jpg"))
        assert g.spec.issues == []

    def test_el_limite_es_el_tamano_de_publicacion(self, tmp_path):
        g = _generador(tmp_path)
        g._avisar_si_la_foto_es_chica(LADO_FICHA, Path("f.jpg"))
        assert g.spec.issues == []

    def test_nombra_el_archivo_original(self, tmp_path):
        g = _generador(tmp_path)
        g._avisar_si_la_foto_es_chica(100, Path("EVELIN PINEDA.jpg"))
        assert any("EVELIN PINEDA.jpg" in i.mensaje for i in g.spec.issues)

    def test_sin_dato_no_avisa(self, tmp_path):
        """Si el recorte fallo y se uso la foto original, no hay medida."""
        g = _generador(tmp_path)
        g._avisar_si_la_foto_es_chica(0, Path("f.jpg"))
        assert g.spec.issues == []


class TestLaFotoQueSePublica:
    """Lo que termina en el paquete, para el caso real de las dos materias."""

    def _publicar(self, tmp_path, lado_foto, rostro=None, monkeypatch=None):
        from maquetador.build.imagenes import recortar_rostro_circular
        src = tmp_path / "foto.png"
        Image.new("RGB", (lado_foto, lado_foto), (90, 110, 130)).save(src)
        dst = tmp_path / "circular.png"
        nativo = recortar_rostro_circular(src, dst)
        with Image.open(dst) as im:
            return nativo, im.size

    def test_la_foto_grande_de_adriana_se_reduce(self, tmp_path):
        """6000x4000 dejaban un recorte de 2428 y un PNG de 4,2 MB en el
        paquete, para mostrarse en un círculo de 150 px."""
        nativo, tamano = self._publicar(tmp_path, 2428)
        assert nativo == 2428
        assert tamano == (LADO_FICHA, LADO_FICHA)

    def test_la_foto_chica_se_agranda_al_mismo_tamano(self, tmp_path):
        nativo, tamano = self._publicar(tmp_path, 160)
        assert nativo == 160
        assert tamano == (LADO_FICHA, LADO_FICHA)

    @pytest.mark.parametrize("lado", [120, 300, 450, 900, 3000])
    def test_siempre_sale_al_tamano_de_publicacion(self, tmp_path, lado):
        _nativo, tamano = self._publicar(tmp_path, lado)
        assert tamano == (LADO_FICHA, LADO_FICHA)
