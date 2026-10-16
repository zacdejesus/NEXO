import pytest

from dominio.mensaje import Conversacion, Mensaje
from dominio.modelos import ModeloEco, ModeloReglas


def _conversacion(*mensajes):
    conversacion = Conversacion()
    for rol, contenido in mensajes:
        conversacion.agregar(Mensaje(rol, contenido))
    return conversacion


def test_eco():
    assert ModeloEco().responder(_conversacion(("usuario", "hola")), []).texto == "Has dicho: hola"


@pytest.mark.parametrize("texto, herramienta, argumentos", [
    ("3 * 4", "calculadora", {"a": 3, "b": 4, "operacion": "*"}),
    ("7 x 6", "calculadora", {"a": 7, "b": 6, "operacion": "*"}),
    ("cuánto son 250 USD en euros", "conversor_moneda", {"cantidad": 250, "origen": "USD", "destino": "EUR"}),
    ("cómo puedo pagar?", "buscador_faq", {"pregunta": "cómo puedo pagar?"}),
])
def test_reglas_piden_la_herramienta(texto, herramienta, argumentos):
    respuesta = ModeloReglas().responder(_conversacion(("usuario", texto)), [])
    assert respuesta.es_llamada_herramienta()
    assert (respuesta.herramienta, respuesta.argumentos) == (herramienta, argumentos)


def test_reglas_saludo_y_desconocido():
    assert ModeloReglas().responder(_conversacion(("usuario", "hola")), []).texto.startswith("¡Hola!")
    assert "reformularlo" in ModeloReglas().responder(_conversacion(("usuario", "zzz")), []).texto


# --- Reto 4: encadenar herramientas -----------------------------------------

def test_pide_segunda_herramienta_tras_la_primera():
    conversacion = _conversacion(
        ("usuario", "convierte 100 USD a euros y multiplícalo por 3"),
        ("herramienta", "100 USD = 92.00 EUR"),
    )
    respuesta = ModeloReglas().responder(conversacion, [])
    assert respuesta.herramienta == "calculadora"
    assert respuesta.argumentos == {"a": 92, "b": 3, "operacion": "*"}


@pytest.mark.parametrize("verbo, operacion", [
    ("multiplícalo por 2", "*"), ("divídelo entre 2", "/"), ("súmale 2", "+"), ("réstale 2", "-"),
])
def test_verbos_encadenados(verbo, operacion):
    conversacion = _conversacion(("usuario", f"3 * 4 y {verbo}"), ("herramienta", "3 * 4 = 12"))
    assert ModeloReglas().responder(conversacion, []).argumentos == {"a": 12, "b": 2, "operacion": operacion}


def test_tras_dos_resultados_responde_con_ambos():
    conversacion = _conversacion(
        ("usuario", "convierte 100 USD a euros y multiplícalo por 3"),
        ("herramienta", "100 USD = 92.00 EUR"),
        ("herramienta", "92 * 3 = 276"),
    )
    respuesta = ModeloReglas().responder(conversacion, [])
    assert not respuesta.es_llamada_herramienta()
    assert respuesta.texto == "Primero, 100 USD = 92.00 EUR; después, 92 * 3 = 276. ¿Necesitas algo más?"


def test_no_encadena_si_el_primer_paso_falla():
    conversacion = _conversacion(("usuario", "5 / 0 y multiplícalo por 3"),
                                 ("herramienta", "Error: No se puede dividir entre 0"))
    respuesta = ModeloReglas().responder(conversacion, [])
    assert not respuesta.es_llamada_herramienta()
    assert "No he podido" in respuesta.texto


def test_sin_segunda_operacion_no_encadena():
    conversacion = _conversacion(("usuario", "cuánto son 100 USD en euros"),
                                 ("herramienta", "100 USD = 92.00 EUR"))
    assert ModeloReglas().responder(conversacion, []).texto == "100 USD = 92.00 EUR."
