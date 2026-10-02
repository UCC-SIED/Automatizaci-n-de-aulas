# -*- coding: utf-8 -*-
"""Tests para Task 6: F4 UI — template edit_plan.html y route GET /plan/<plan_id>/edit."""

import json
import pytest
from pathlib import Path
from maquetador.web.app import app


@pytest.fixture
def client():
    """Cliente de prueba para Flask."""
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


@pytest.fixture
def plan_test_json(tmp_path):
    """Crea un plan de prueba en la carpeta temporal."""
    planes_dir = tmp_path / "planes"
    planes_dir.mkdir(parents=True, exist_ok=True)

    plan_data = {
        "nombre": "Curso Test",
        "codigo": "TEST001",
        "tema": "educacion",
        "curso_id": "curso-test",
        "docentes": [],
        "items_inicio": [],
        "modulos": [
            {
                "numero": 1,
                "titulo": "Módulo 1",
                "items": [
                    {
                        "titulo": "1.1. Introducción",
                        "tipo": "pagina",
                        "orden": 1,
                        "fuente": {
                            "archivo": "modulo1.docx",
                            "seccion": "1.1",
                            "confianza": 0.95,
                            "tiene_html": False
                        },
                        "estado_planilla": "Obligatorio",
                        "comentarios_asesor": "",
                        "detalle": {},
                        "issues": []
                    },
                    {
                        "titulo": "1.2. Contenido",
                        "tipo": "video",
                        "orden": 2,
                        "fuente": {
                            "archivo": "modulo1.docx",
                            "seccion": "1.2",
                            "confianza": 0.90,
                            "tiene_html": False
                        },
                        "estado_planilla": "Obligatorio",
                        "comentarios_asesor": "",
                        "detalle": {},
                        "issues": []
                    }
                ]
            }
        ],
        "afi": [],
        "issues": []
    }

    plan_path = planes_dir / "plan_TEST001.json"
    with open(plan_path, "w", encoding="utf-8") as f:
        json.dump(plan_data, f, indent=2, ensure_ascii=False)

    return str(plan_path), "plan_TEST001", plan_data


class TestEditPlanTemplate:
    """Tests para el template edit_plan.html."""

    def test_template_edit_plan_existe(self):
        """Verificar que el template edit_plan.html existe."""
        template_path = (Path(__file__).parent.parent /
                        "maquetador/web/templates/edit_plan.html")
        assert template_path.exists(), "Template edit_plan.html no encontrado"

    def test_template_contiene_formulario_principal(self):
        """Verificar que el template contiene un formulario con id form-edit-plan."""
        template_path = (Path(__file__).parent.parent /
                        "maquetador/web/templates/edit_plan.html")
        with open(template_path, "r", encoding="utf-8") as f:
            contenido = f.read()

        assert 'id="form-edit-plan"' in contenido, \
            "Template debe contener formulario con id 'form-edit-plan'"
        assert 'method="post"' in contenido, "Formulario debe usar POST"

    def test_template_contiene_elementos_formulario(self):
        """Verificar que el template contiene elementos de formulario esperados."""
        template_path = (Path(__file__).parent.parent /
                        "maquetador/web/templates/edit_plan.html")
        with open(template_path, "r", encoding="utf-8") as f:
            contenido = f.read()

        # Elementos esperados
        elementos = [
            'id="nombre"',          # Campo nombre
            'id="codigo"',          # Campo código
            'id="tema"',            # Selector tema
            'class="item-titulo"',  # Campo título de item
            'class="item-tipo"',    # Selector tipo de item
            'class="item-archivo"', # Campo archivo
            'id="btn-guardar"',     # Botón guardar
        ]

        for elemento in elementos:
            assert elemento in contenido, \
                f"Template debe contener elemento: {elemento}"


class TestEditPlanRoute:
    """Tests para la ruta GET /plan/<plan_id>/edit."""

    def test_route_edit_plan_existe(self, client, monkeypatch, plan_test_json):
        """Verificar que la ruta GET /plan/<plan_id>/edit está registrada."""
        plan_path, plan_id, plan_data = plan_test_json

        # Parchear OUTPUT_DIR para usar el directorio temporal
        import maquetador.web.app
        original_output_dir = maquetador.web.app.OUTPUT_DIR
        temp_output_dir = Path(plan_path).parent.parent
        monkeypatch.setattr(maquetador.web.app, "OUTPUT_DIR", temp_output_dir)

        try:
            response = client.get(f"/plan/{plan_id}/edit")
            assert response.status_code == 200, \
                f"GET /plan/{plan_id}/edit debe retornar 200, obtuvo {response.status_code}"
        finally:
            monkeypatch.setattr(maquetador.web.app, "OUTPUT_DIR", original_output_dir)

    def test_route_edit_plan_retorna_html(self, client, monkeypatch, plan_test_json):
        """Verificar que la ruta retorna HTML con el formulario."""
        plan_path, plan_id, plan_data = plan_test_json

        import maquetador.web.app
        original_output_dir = maquetador.web.app.OUTPUT_DIR
        temp_output_dir = Path(plan_path).parent.parent
        monkeypatch.setattr(maquetador.web.app, "OUTPUT_DIR", temp_output_dir)

        try:
            response = client.get(f"/plan/{plan_id}/edit")
            assert response.status_code == 200
            data = response.get_data(as_text=True)

            # Verificar que contiene elementos del plan
            assert plan_data["nombre"] in data, \
                "HTML debe contener el nombre del plan"
            assert plan_data["codigo"] in data, \
                "HTML debe contener el código del plan"
            assert 'id="form-edit-plan"' in data, \
                "HTML debe contener el formulario de edición"
        finally:
            monkeypatch.setattr(maquetador.web.app, "OUTPUT_DIR", original_output_dir)

    def test_route_edit_plan_plan_no_encontrado(self, client, monkeypatch):
        """Verificar que se redirige si el plan no existe."""
        import maquetador.web.app
        original_output_dir = maquetador.web.app.OUTPUT_DIR
        temp_output_dir = Path("/tmp/test_nonexistent")
        monkeypatch.setattr(maquetador.web.app, "OUTPUT_DIR", temp_output_dir)

        try:
            response = client.get("/plan/plan_NOEXISTE/edit", follow_redirects=True)
            # Debe redirigir a index
            assert response.status_code == 200
            data = response.get_data(as_text=True)
            assert "Plan no encontrado" in data or "index" in response.request.path
        finally:
            monkeypatch.setattr(maquetador.web.app, "OUTPUT_DIR", original_output_dir)


class TestEditPlanFormElements:
    """Tests para elementos del formulario en edit_plan.html."""

    def test_formulario_tiene_campos_datos_generales(self):
        """Verificar que el formulario tiene campos para datos generales."""
        template_path = (Path(__file__).parent.parent /
                        "maquetador/web/templates/edit_plan.html")
        with open(template_path, "r", encoding="utf-8") as f:
            contenido = f.read()

        campos = ["nombre", "codigo", "tema"]
        for campo in campos:
            assert f'name="{campo}"' in contenido, \
                f"Formulario debe tener campo '{campo}'"

    def test_formulario_tiene_selector_tema(self):
        """Verificar que el selector de tema tiene opciones correctas."""
        template_path = (Path(__file__).parent.parent /
                        "maquetador/web/templates/edit_plan.html")
        with open(template_path, "r", encoding="utf-8") as f:
            contenido = f.read()

        assert 'value="educacion"' in contenido, \
            "Selector tema debe tener opción 'educacion'"
        assert 'value="posgrado"' in contenido, \
            "Selector tema debe tener opción 'posgrado'"

    def test_formulario_tiene_campos_items(self):
        """Verificar que el formulario tiene campos para ítems."""
        template_path = (Path(__file__).parent.parent /
                        "maquetador/web/templates/edit_plan.html")
        with open(template_path, "r", encoding="utf-8") as f:
            contenido = f.read()

        campos_item = ["item-titulo", "item-tipo", "item-archivo", "item-seccion"]
        for campo in campos_item:
            assert f'class="{campo}"' in contenido, \
                f"Formulario debe tener campo de item '{campo}'"

    def test_formulario_tiene_boton_guardar(self):
        """Verificar que el formulario tiene botón de envío."""
        template_path = (Path(__file__).parent.parent /
                        "maquetador/web/templates/edit_plan.html")
        with open(template_path, "r", encoding="utf-8") as f:
            contenido = f.read()

        assert 'type="submit"' in contenido, \
            "Formulario debe tener botón submit"
        assert 'id="btn-guardar"' in contenido, \
            "Botón submit debe tener id 'btn-guardar'"

    def test_formulario_tiene_javascript(self):
        """El formulario debe tener su JavaScript cableado.

        El script vive en un archivo aparte (static/js/edit_plan.js), no
        embebido en el template: se verifica que el template lo cargue y
        que el archivo traiga el manejo de eventos y el POST."""
        raiz = Path(__file__).parent.parent
        template = (raiz / "maquetador/web/templates/edit_plan.html").read_text(
            encoding="utf-8")

        assert "<script" in template, "Template debe contener bloque <script>"
        assert "js/edit_plan.js" in template, \
            "Template debe cargar static/js/edit_plan.js"

        script = (raiz / "maquetador/web/static/js/edit_plan.js").read_text(
            encoding="utf-8")

        assert "addEventListener" in script, "Script debe usar addEventListener"
        assert "fetch" in script, "Script debe usar fetch para POST"
