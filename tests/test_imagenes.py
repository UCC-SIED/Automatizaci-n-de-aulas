# -*- coding: utf-8 -*-
"""Recorte de la foto del docente centrado en el rostro (página de inicio).

La foto va en un círculo (CSS: border-radius: 50% + object-fit: cover): sin
el rostro centrado en el archivo original, el recorte automático del
navegador la deja descentrada o "estirada" (el crop del equipo con Fotor
posicionaba el círculo sobre la cara a mano). Acá se prueba el mismo
resultado automatizado con detección de rostro (OpenCV).
"""

from pathlib import Path

from PIL import Image

from maquetador.build.imagenes import recortar_rostro_circular


class TestSinRostroDetectado:
    """Sin rostro (foto sintética de un solo color): recorte centrado en la
    imagen completa, igual que el object-fit:cover de siempre — no hay
    regresión respecto al comportamiento anterior."""

    def test_recorta_un_cuadrado_centrado_en_la_imagen(self, tmp_path):
        src = tmp_path / "foto.png"
        Image.new("RGB", (400, 300), (100, 150, 200)).save(src)
        dst = tmp_path / "recorte.png"
        # El valor devuelto es el lado NATIVO del recorte: el archivo se
        # guarda siempre al tamaño de publicacion (ver TestTamanoDeSalida).
        assert recortar_rostro_circular(src, dst) == 300

    def test_una_imagen_ya_cuadrada_se_recorta_entera(self, tmp_path):
        src = tmp_path / "foto.png"
        Image.new("RGB", (250, 250), (10, 20, 30)).save(src)
        dst = tmp_path / "recorte.png"
        assert recortar_rostro_circular(src, dst) == 250

    def test_guarda_como_png(self, tmp_path):
        src = tmp_path / "foto.jpg"
        Image.new("RGB", (100, 100), (0, 0, 0)).save(src, "JPEG")
        dst = tmp_path / "recorte.png"
        recortar_rostro_circular(src, dst)
        with Image.open(dst) as out:
            assert out.format == "PNG"


class TestConRostroDetectado:
    """Con un rostro (mockeando la detección: no depende de una foto real ni
    de que el modelo Haar cascade lo encuentre) el recorte queda centrado en
    el rostro, no en la imagen completa."""

    def test_recorte_centrado_en_el_rostro_no_en_la_imagen(
            self, tmp_path, monkeypatch):
        import maquetador.build.imagenes as imagenes_mod
        # Imagen ancha (1000x400): el rostro está pegado al borde derecho.
        src = tmp_path / "foto.png"
        Image.new("RGB", (1000, 400), (100, 100, 100)).save(src)
        monkeypatch.setattr(imagenes_mod, "_detectar_rostro",
                             lambda ruta: (800, 100, 100, 100))
        dst = tmp_path / "recorte.png"
        # Rostro: x=800..900, centro=850. Lado = 100*2 = 200 (clamp a los
        # 400px de alto). Recorte esperado: centrado en x=850, no en x=500
        # (centro de la imagen completa) — y clampeado a no salirse del
        # borde derecho (1000 - 200 = 800).
        assert recortar_rostro_circular(src, dst) == 200

    def test_el_recorte_no_se_sale_del_borde_de_la_imagen(
            self, tmp_path, monkeypatch):
        """Rostro pegado a una esquina: el cuadrado se corre para no salirse
        de la imagen, en vez de recortar fuera de los límites."""
        import maquetador.build.imagenes as imagenes_mod
        src = tmp_path / "foto.png"
        Image.new("RGB", (300, 300), (0, 0, 0)).save(src)
        # Rostro grande, pegado a la esquina superior izquierda: un cuadrado
        # centrado ahí se saldría de la imagen sin el clamp.
        monkeypatch.setattr(imagenes_mod, "_detectar_rostro",
                             lambda ruta: (0, 0, 150, 150))
        dst = tmp_path / "recorte.png"
        # clampeado al tamaño de la imagen
        assert recortar_rostro_circular(src, dst) == 300


class TestTamanoDeSalida:
    """La ficha muestra la foto a 150x150 CSS y se guarda al triple, para
    que se vea nítida en pantallas de alta densidad."""

    def _recorte(self, tmp_path, lado):
        src = tmp_path / "foto.png"
        Image.new("RGB", (lado, lado), (120, 130, 140)).save(src)
        dst = tmp_path / "recorte.png"
        recortar_rostro_circular(src, dst)
        return dst

    def test_una_foto_grande_se_reduce(self, tmp_path):
        """2428x2428 ocupaban 4,2 MB del paquete para mostrarse en un
        círculo de 150 px."""
        with Image.open(self._recorte(tmp_path, 2428)) as out:
            assert out.size == (450, 450)

    def test_una_foto_chica_se_agranda(self, tmp_path):
        """No recupera detalle que la foto no tiene, pero queda mejor que
        dejar que el navegador la estire."""
        with Image.open(self._recorte(tmp_path, 160)) as out:
            assert out.size == (450, 450)

    def test_la_del_tamano_justo_no_se_toca(self, tmp_path):
        with Image.open(self._recorte(tmp_path, 450)) as out:
            assert out.size == (450, 450)

    def test_el_archivo_grande_pesa_mucho_menos(self, tmp_path):
        import io as _io
        src = tmp_path / "grande.png"
        # Ruido, para que el PNG no se comprima a nada y la comparacion
        # tenga sentido.
        import random
        random.seed(0)
        im = Image.new("RGB", (2000, 2000))
        im.putdata([(random.randrange(256), random.randrange(256),
                     random.randrange(256)) for _ in range(2000 * 2000)])
        im.save(src)
        dst = tmp_path / "recorte.png"
        recortar_rostro_circular(src, dst)
        assert dst.stat().st_size < src.stat().st_size / 5
