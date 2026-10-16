import pytest

from dominio.excepciones import ArgumentosInvalidos
from dominio.herramientas import BuscadorFAQ, Calculadora, ConversorMoneda, Herramienta


def test_heredan_de_herramienta():
    for herramienta in (Calculadora(), ConversorMoneda(), BuscadorFAQ()):
        assert isinstance(herramienta, Herramienta)


def test_calculadora():
    assert Calculadora().ejecutar(a=3, b=79.9, operacion="*") == "3 * 79.9 = 239.7"
    assert Calculadora().ejecutar(a=3, b=4, operacion="*") == "3 * 4 = 12"
    assert Calculadora().ejecutar(a=10, b=4, operacion="/") == "10 / 4 = 2.5"


@pytest.mark.parametrize("argumentos", [
    {"a": 1, "b": 0, "operacion": "/"},
    {"a": 1, "b": 2, "operacion": "%"},
    {"a": "x", "b": 2, "operacion": "+"},
])
def test_calculadora_errores(argumentos):
    with pytest.raises(ArgumentosInvalidos):
        Calculadora().ejecutar(**argumentos)


def test_conversor():
    assert ConversorMoneda().ejecutar(cantidad=250, origen="USD", destino="EUR") == "250 USD = 230.00 EUR"
    with pytest.raises(ArgumentosInvalidos):
        ConversorMoneda().ejecutar(cantidad=1, origen="BTC", destino="EUR")


@pytest.mark.parametrize("pregunta, esperado", [
    ("cuánto tarda el envío?", "24-48 h"),
    ("cómo puedo pagar?", "Bizum"),
    ("aceptáis devoluciones?", "30 días"),
])
def test_buscador_faq(pregunta, esperado):
    assert esperado in BuscadorFAQ().ejecutar(pregunta=pregunta)


def test_buscador_faq_sin_resultado():
    assert BuscadorFAQ().ejecutar(pregunta="xyz") == "No encontrado"
