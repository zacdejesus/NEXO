"""Project-wide rules from the assignment (they span several layers)."""
import ast

from tests.ayudantes import RAIZ


def _llamadas(ruta):
    arbol = ast.parse(ruta.read_text(encoding="utf-8"))
    return {n.func.id for n in ast.walk(arbol) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}


def test_sin_print_ni_input_en_dominio_y_servicios():
    for carpeta in ("dominio", "servicios"):
        for ruta in (RAIZ / carpeta).glob("*.py"):
            assert not _llamadas(ruta) & {"print", "input"}, ruta


def test_agente_sin_isinstance():
    assert "isinstance" not in _llamadas(RAIZ / "servicios" / "agente.py")
