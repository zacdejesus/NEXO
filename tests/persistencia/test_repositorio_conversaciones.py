import json

import pytest

from dominio.excepciones import ErrorPersistencia
from dominio.mensaje import Conversacion
from persistencia.repositorio_conversaciones import RepositorioConversaciones
from tests.ayudantes import crear_agente


@pytest.fixture
def carpeta(tmp_path):
    return tmp_path / "a" / "b"


@pytest.fixture
def repo(carpeta):
    return RepositorioConversaciones(carpeta)


def test_guardar_y_cargar_completo(repo):
    agente = crear_agente()
    agente.procesar("hola")
    agente.procesar("3 * 4")
    original = agente.conversacion
    repo.guardar(original)
    cargada = repo.cargar(original.id)
    assert isinstance(cargada, Conversacion)
    assert cargada.id == original.id
    assert cargada.to_dict() == original.to_dict()
    assert [m.rol for m in cargada.get_mensajes()] == ["usuario", "asistente", "usuario", "herramienta", "asistente"]
    assert repo.listar() == [original.id]


@pytest.mark.parametrize("malo", ["no_existe", "../fuera", "a/b", "..", ""])
def test_ids_invalidos_o_inexistentes(repo, malo):
    with pytest.raises(ErrorPersistencia):
        repo.cargar(malo)


def test_archivos_corruptos(repo, carpeta):
    assert repo.listar() == []
    repo.guardar(Conversacion("ok"))
    (carpeta / "roto.json").write_text("{no es json", encoding="utf-8")
    (carpeta / "vacio.json").write_text('{"id": "vacio"}', encoding="utf-8")
    (carpeta / "rol.json").write_text(
        json.dumps({"id": "rol", "mensajes": [{"rol": "x", "contenido": "y"}]}), encoding="utf-8")
    for id_conv in ("roto", "vacio", "rol"):
        with pytest.raises(ErrorPersistencia):
            repo.cargar(id_conv)


def test_no_se_puede_guardar_fuera_de_la_carpeta(repo):
    with pytest.raises(ErrorPersistencia):
        repo.guardar(Conversacion("../escape"))
