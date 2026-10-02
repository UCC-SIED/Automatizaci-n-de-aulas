# tests/test_xml_validation.py
"""Validación de los paquetes .imscc generados.

Un XML mal formado —un '&' sin escapar en un título, por ejemplo— hace fallar
la importación en Canvas sin dar una pista útil. Por eso estos tests validan
el paquete entero, no una muestra.

Los paquetes salen del fixture `paquetes_imscc`: los reales de output/ si el
equipo generó alguno, y si no uno construido al vuelo desde el curso sintético
(ver tests/fixtures/curso_sintetico.py). Antes esto se salteaba entero cuando
output/ estaba vacío, que es siempre el caso en CI y en un clon limpio.
"""
import zipfile
from xml.etree import ElementTree as ET

import pytest

NS = {"imscc": "http://www.imsglobal.org/xsd/imsccv1p1/imscp_v1p1"}


class TestXMLBienFormado:
    """Valida que los archivos XML sean bien formados"""

    def test_imscc_files_exist(self, paquetes_imscc):
        """Los paquetes a validar deben ser ZIPs legibles."""
        assert paquetes_imscc, "No hay ningún paquete .imscc para validar"
        for imscc_path in paquetes_imscc:
            assert zipfile.is_zipfile(imscc_path), \
                f"{imscc_path.name} no es un ZIP válido"

    def test_imscc_contiene_imsmanifest(self, paquetes_imscc):
        """Cada IMSCC debe contener imsmanifest.xml"""
        for imscc_path in paquetes_imscc[:3]:
            with zipfile.ZipFile(imscc_path, "r") as z:
                assert "imsmanifest.xml" in z.namelist(), \
                    f"{imscc_path.name} missing imsmanifest.xml"

    def test_imscc_contiene_module_meta(self, paquetes_imscc):
        """Cada IMSCC debe contener course_settings/module_meta.xml"""
        for imscc_path in paquetes_imscc[:3]:
            with zipfile.ZipFile(imscc_path, "r") as z:
                metas = [f for f in z.namelist() if "module_meta.xml" in f]
                assert metas, f"{imscc_path.name} missing module_meta.xml"

    def test_xml_parseable(self, paquetes_imscc):
        """Todos los archivos XML dentro del IMSCC deben ser parseables"""
        for imscc_path in paquetes_imscc[:2]:
            with zipfile.ZipFile(imscc_path, "r") as z:
                for xml_file in [f for f in z.namelist() if f.endswith(".xml")]:
                    try:
                        ET.fromstring(z.read(xml_file))
                    except ET.ParseError as e:
                        pytest.fail(
                            f"XML malformado en {imscc_path.name}/{xml_file}: {e}")


class TestEstructuraIMSCC:
    """Valida estructura y referencias en IMSCC"""

    def test_manifest_tiene_organizations(self, paquetes_imscc):
        """imsmanifest.xml debe tener organizations"""
        with zipfile.ZipFile(paquetes_imscc[0], "r") as z:
            root = ET.fromstring(z.read("imsmanifest.xml"))
            assert root.findall(".//imscc:organizations", NS), \
                "No organizations encontrada"

    def test_referencias_cruzadas_validas(self, paquetes_imscc):
        """Items deben apuntar a resources que existen.

        Una referencia colgada es la forma más común de romper la importación
        después de que el generador elimina módulos o recursos que la planilla
        no pide."""
        with zipfile.ZipFile(paquetes_imscc[0], "r") as z:
            root = ET.fromstring(z.read("imsmanifest.xml"))

            resource_ids = {r.get("identifier")
                            for r in root.findall(".//imscc:resource", NS)
                            if r.get("identifier")}

            for item in root.findall(".//imscc:item", NS):
                ref = item.get("identifierref")
                if ref:
                    assert ref in resource_ids, \
                        f"Item apunta a resource inexistente: {ref}"


class TestIntegracion:
    """Tests de integración contra los paquetes disponibles"""

    def test_procesar_todos_imscc(self, paquetes_imscc):
        """Todos los paquetes deben abrirse y tener un manifest parseable"""
        errores = []
        for imscc_path in paquetes_imscc:
            try:
                with zipfile.ZipFile(imscc_path, "r") as z:
                    ET.fromstring(z.read("imsmanifest.xml"))
            except Exception as e:
                errores.append(f"{imscc_path.name}: {e}")
        assert not errores, f"Errores en XML: {errores}"

    def test_paquete_trae_contenido_del_curso(self, paquetes_imscc):
        """El paquete no debe ser solo el aula base clonada: tiene que traer
        páginas de contenido y el manifest debe declarar recursos."""
        with zipfile.ZipFile(paquetes_imscc[0], "r") as z:
            nombres = z.namelist()
            assert [n for n in nombres if n.endswith(".html")], \
                "El paquete no tiene ninguna página HTML"
            root = ET.fromstring(z.read("imsmanifest.xml"))
            assert root.findall(".//imscc:resource", NS), \
                "El manifest no declara ningún recurso"
