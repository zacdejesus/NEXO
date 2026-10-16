import csv

from dominio.mensaje import Conversacion
from persistencia.registro_uso import RegistroUso
from persistencia.repositorio_conversaciones import RepositorioConversaciones
from tests.ayudantes import crear_agente, ejecutar_chat


def test_ejemplo_del_enunciado():
    texto = ejecutar_chat(
        ["hola", "si compro 3 * 79.9 cuánto pago?", "cuánto son 250 USD en euros",
         "cuánto tarda el envío?", "/modelo eco", "hola", "/salir"],
        crear_agente())
    for esperado in ["¡Hola! Soy NEXO", "🔧 calculadora(a=3, b=79.9, operacion='*')",
                     "El resultado es 3 * 79.9 = 239.7. ¿Necesitas algo más?",
                     "🔧 conversor_moneda(cantidad=250, origen='USD', destino='EUR')",
                     "NEXO > 250 USD = 230.00 EUR.", "🔧 buscador_faq(",
                     "Según nuestra información: Los envíos tardan 24-48 h",
                     "✔ Modelo cambiado a ModeloEco", "NEXO > Has dicho: hola"]:
        assert esperado in texto


def test_chat_sobrevive_a_errores_de_carga(tmp_path):
    carpeta = tmp_path / "a" / "b"
    carpeta.mkdir(parents=True)
    (carpeta / "roto.json").write_text("{", encoding="utf-8")
    texto = ejecutar_chat(["/cargar roto", "/cargar ../x", "/cargar nada", "/cargar", "hola"],
                          crear_agente(), RepositorioConversaciones(carpeta))
    assert texto.count("⚠") == 3
    assert "Uso: /cargar <id>" in texto
    assert "NEXO > ¡Hola!" in texto


def test_comandos_de_memoria(tmp_path):
    repo = RepositorioConversaciones(tmp_path / "conversaciones")
    agente = crear_agente()
    texto = ejecutar_chat(["/lista", "/historial", "hola", "/guardar"], agente, repo)
    assert "No hay conversaciones guardadas." in texto
    assert "La conversación está vacía." in texto
    id_viejo = agente.conversacion.id
    assert f"💾 Conversación {id_viejo} guardada" in texto
    texto = ejecutar_chat(["/nueva", "/historial", f"/cargar {id_viejo}", "/historial", "/lista"], agente, repo)
    assert f"📂 Conversación {id_viejo} cargada (2 mensajes)" in texto
    assert "[usuario] hola" in texto
    assert "Tokens estimados: 10" in texto  # 8 words * 1.3 = 10.4 -> 10
    assert repo.listar() == [id_viejo]


def test_registro_y_stats(tmp_path):
    ruta = tmp_path / "datos" / "uso.csv"
    registro = RegistroUso(ruta)
    texto = ejecutar_chat(["3 * 4", "10 / 0", "cuánto son 100 USD en euros", "/stats"],
                          crear_agente(registro), registro=registro)
    with open(ruta, newline="", encoding="utf-8") as fichero:
        filas = list(csv.reader(fichero))
    assert filas[0] == ["fecha", "herramienta", "argumentos", "exito", "milisegundos"]
    assert [f[1] for f in filas[1:]] == ["calculadora", "calculadora", "conversor_moneda"]
    assert [f[3] for f in filas[1:]] == ["True", "False", "True"]
    assert float(filas[1][4]) >= 0
    assert "Ejecuciones de herramientas: 3" in texto
    assert "calculadora: 2 usos, 1 fallos" in texto
    assert "No he podido completar la operación" in texto


def test_encadenado_muestra_las_dos_llamadas():
    texto = ejecutar_chat(["convierte 100 USD a euros y multiplícalo por 3"], crear_agente())
    assert "🔧 conversor_moneda(cantidad=100, origen='USD', destino='EUR')" in texto
    assert "🔧 calculadora(a=92, b=3, operacion='*')" in texto
    assert "NEXO > Primero, 100 USD = 92.00 EUR; después, 92 * 3 = 276." in texto


def test_avisa_cuando_resume():
    agente = crear_agente()
    agente.conversacion = Conversacion(limite_tokens=60)
    texto = ejecutar_chat(["cuánto es 3 * 4"] * 6, agente)
    assert "🗜 He resumido los mensajes antiguos" in texto
    assert "⚠" not in texto
