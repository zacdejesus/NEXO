import pytest

from persistencia.registro_uso import RegistroUso


@pytest.fixture
def ruta(tmp_path):
    return tmp_path / "datos" / "uso.csv"


def test_resumen_vacio(ruta):
    assert RegistroUso(ruta).resumen() == {"total": 0, "usos": {}, "fallos": {}}


def test_cabecera_unica_y_acumulacion(ruta):
    RegistroUso(ruta).registrar("calculadora", {"a": 1}, True, 0.1)
    RegistroUso(ruta).registrar("calculadora", {"a": 2}, False, 0.2)
    lineas = ruta.read_text(encoding="utf-8").splitlines()
    assert len(lineas) == 3
    assert sum(linea.startswith("fecha,") for linea in lineas) == 1


def test_resumen_cuenta_usos_y_fallos(ruta):
    registro = RegistroUso(ruta)
    registro.registrar("calculadora", {}, True, 0.1)
    registro.registrar("calculadora", {}, False, 0.1)
    registro.registrar("conversor_moneda", {}, True, 0.1)
    assert registro.resumen() == {
        "total": 3,
        "usos": {"calculadora": 2, "conversor_moneda": 1},
        "fallos": {"calculadora": 1, "conversor_moneda": 0},
    }
