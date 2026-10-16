import pytest

from dominio.excepciones import LimiteContextoSuperado
from dominio.mensaje import Conversacion, Mensaje


# --- Mensaje ---------------------------------------------------------------

def test_rol_invalido():
    with pytest.raises(ValueError):
        Mensaje("robot", "x")


def test_str_y_dict():
    mensaje = Mensaje("usuario", "Hola", fecha="2026-10-20T10:15:00")
    assert str(mensaje) == "[usuario] Hola"
    assert mensaje.to_dict() == {"rol": "usuario", "contenido": "Hola", "fecha": "2026-10-20T10:15:00"}
    assert Mensaje.from_dict(mensaje.to_dict()).to_dict() == mensaje.to_dict()


# --- Conversacion: encapsulación y límite ----------------------------------

def test_get_mensajes_devuelve_copia():
    conversacion = Conversacion()
    conversacion.agregar(Mensaje("usuario", "hola"))
    conversacion.get_mensajes().clear()
    assert len(conversacion) == 1


def test_lista_privada():
    with pytest.raises(AttributeError):
        Conversacion().__mensajes


def test_limite_de_tokens():
    conversacion = Conversacion()
    conversacion.agregar(Mensaje("usuario", "hola"))
    with pytest.raises(LimiteContextoSuperado):
        conversacion.agregar(Mensaje("usuario", "palabra " * 400))
    assert len(conversacion) == 1  # the message that doesn't fit is not added


def test_ida_y_vuelta_dict():
    conversacion = Conversacion()
    conversacion.agregar(Mensaje("usuario", "hola"))
    conversacion.agregar(Mensaje("asistente", "¡Hola!"))
    assert Conversacion.from_dict(conversacion.to_dict()).to_dict() == conversacion.to_dict()


# --- Reto 6: resumen automático al superar el 80 % --------------------------

def _llenar(conversacion, veces, inicio=0, palabras=10):
    for i in range(inicio, inicio + veces):
        conversacion.agregar(Mensaje("usuario" if i % 2 == 0 else "asistente",
                                     f"pregunta{i} " + "relleno " * (palabras - 1)))


def test_resume_al_superar_el_80_por_ciento():
    conversacion = Conversacion(limite_tokens=100)  # 80 % = 80 tokens ≈ 61 palabras
    _llenar(conversacion, 6)                         # 60 palabras = 78 tokens: aún no
    assert conversacion.veces_resumida == 0
    _llenar(conversacion, 1, inicio=6)               # 70 palabras = 91 tokens: resume
    mensajes = conversacion.get_mensajes()
    assert conversacion.veces_resumida == 1
    assert mensajes[0].rol == "asistente"
    assert mensajes[0].contenido.startswith("[Resumen de ")
    assert mensajes[-1].contenido.startswith("pregunta6")  # the new message is kept
    assert len(mensajes) < 7
    assert conversacion.tokens_estimados() <= 100 * Conversacion.UMBRAL_RESUMEN


def test_resumen_conserva_los_temas_del_usuario():
    conversacion = Conversacion(limite_tokens=100)
    _llenar(conversacion, 7)
    resumen = conversacion.get_mensajes()[0].contenido
    assert "pregunta0" in resumen and "pregunta2" in resumen
    assert "pregunta1" not in resumen  # assistant messages are not topics


def test_resumen_encadenado_arrastra_el_anterior():
    conversacion = Conversacion(limite_tokens=100)
    _llenar(conversacion, 12)
    resumen = conversacion.get_mensajes()[0].contenido
    assert conversacion.veces_resumida >= 2
    assert resumen.count("[Resumen") == 1          # summaries are merged, not nested
    assert "pregunta4" in resumen and "pregunta8" in resumen  # topics carried from earlier summaries
    assert "pregunta0" not in resumen              # the oldest topics fall off (bounded size)


def test_sin_resumen_automatico_lanza_el_limite():
    conversacion = Conversacion(limite_tokens=100, resumen_automatico=False)
    _llenar(conversacion, 7)  # 91 tokens: under the hard limit
    with pytest.raises(LimiteContextoSuperado):
        _llenar(conversacion, 1, inicio=7)
    assert conversacion.veces_resumida == 0


def test_un_mensaje_enorme_sigue_lanzando_el_limite():
    conversacion = Conversacion(limite_tokens=100)
    _llenar(conversacion, 5)
    antes = conversacion.to_dict()
    with pytest.raises(LimiteContextoSuperado):
        conversacion.agregar(Mensaje("usuario", "x " * 90))
    assert conversacion.to_dict() == antes  # nothing changed on failure
