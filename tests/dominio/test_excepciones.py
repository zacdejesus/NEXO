import pytest

from dominio import excepciones

PROPIAS = [excepciones.HerramientaNoEncontrada, excepciones.ArgumentosInvalidos,
           excepciones.LimiteContextoSuperado, excepciones.ErrorPersistencia]


@pytest.mark.parametrize("clase", PROPIAS)
def test_todas_heredan_de_error_agente(clase):
    assert issubclass(clase, excepciones.ErrorAgente)
    assert issubclass(excepciones.ErrorAgente, Exception)
