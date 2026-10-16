import ast
import csv
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from dominio.excepciones import ErrorPersistencia, HerramientaNoEncontrada, LimiteContextoSuperado
from dominio.herramientas import BuscadorFAQ, Calculadora, ConversorMoneda
from dominio.mensaje import Conversacion, Mensaje
from dominio.modelos import ModeloReglas, Respuesta, Modelo
from persistencia.registro_uso import RegistroUso
from persistencia.repositorio_conversaciones import RepositorioConversaciones
from presentacion.chat_consola import ChatConsola
from servicios.agente import Agente

RAIZ = Path(__file__).resolve().parent.parent


def crear_agente(registro=None):
    return Agente(ModeloReglas(), [Calculadora(), ConversorMoneda(), BuscadorFAQ()], registro)


def ejecutar_chat(entradas, agente, repo=None, registro=None):
    cola, salida = iter(entradas), []
    def entrada(_):
        try:
            return next(cola)
        except StopIteration:
            raise EOFError
    ChatConsola(agente, repo, registro, entrada=entrada, salida=salida.append).iniciar()
    return "\n".join(salida)


class TestNivel1(unittest.TestCase):
    def test_herramientas(self):
        self.assertEqual(Calculadora().ejecutar(a=3, b=79.9, operacion="*"), "3 * 79.9 = 239.7")
        self.assertEqual(Calculadora().ejecutar(a=3, b=4, operacion="*"), "3 * 4 = 12")
        self.assertEqual(ConversorMoneda().ejecutar(cantidad=250, origen="USD", destino="EUR"),
                         "250 USD = 230.00 EUR")
        self.assertIn("24-48 h", BuscadorFAQ().ejecutar(pregunta="cuánto tarda el envío?"))
        self.assertEqual(BuscadorFAQ().ejecutar(pregunta="xyz"), "No encontrado")

    def test_ejemplo_del_enunciado(self):
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
            self.assertIn(esperado, texto)

    def test_encapsulacion_y_limite(self):
        c = Conversacion()
        c.agregar(Mensaje("usuario", "hola"))
        c.get_mensajes().clear()
        self.assertEqual(len(c), 1)
        with self.assertRaises(ValueError):
            Mensaje("robot", "x")
        with self.assertRaises(LimiteContextoSuperado):
            c.agregar(Mensaje("usuario", "palabra " * 400))

    def test_herramienta_inexistente(self):
        class Raro(Modelo):
            def responder(self, conversacion, herramientas):
                return Respuesta(herramienta="no_existe")
        agente = Agente(Raro("raro"), [Calculadora()])
        with self.assertRaises(HerramientaNoEncontrada):
            agente.procesar("hola")

    def test_limite_de_tres_iteraciones(self):
        llamadas = []
        class Bucle(Modelo):
            def responder(self, conversacion, herramientas):
                llamadas.append(1)
                return Respuesta(herramienta="calculadora",
                                 argumentos={"a": 1, "b": 1, "operacion": "+"})
        with self.assertRaises(Exception):
            Agente(Bucle("bucle"), [Calculadora()]).procesar("hola")
        self.assertEqual(len(llamadas), 3)

    def test_sin_print_input_ni_isinstance(self):
        for carpeta in ("dominio", "servicios"):
            for ruta in (RAIZ / carpeta).glob("*.py"):
                for nodo in ast.walk(ast.parse(ruta.read_text(encoding="utf-8"))):
                    if isinstance(nodo, ast.Call) and isinstance(nodo.func, ast.Name):
                        self.assertNotIn(nodo.func.id, ("print", "input"), ruta)
        arbol = ast.parse((RAIZ / "servicios" / "agente.py").read_text(encoding="utf-8"))
        nombres = {n.func.id for n in ast.walk(arbol)
                   if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
        self.assertNotIn("isinstance", nombres)


class TestPersistenciaJSON(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = RepositorioConversaciones(Path(self.tmp.name) / "a" / "b")

    def test_guardar_y_cargar_completo(self):
        agente = crear_agente()
        agente.procesar("hola")
        agente.procesar("3 * 4")
        original = agente.conversacion
        self.repo.guardar(original)
        cargada = self.repo.cargar(original.id)
        self.assertIsInstance(cargada, Conversacion)
        self.assertEqual(cargada.id, original.id)
        self.assertEqual(cargada.to_dict(), original.to_dict())
        self.assertEqual([m.rol for m in cargada.get_mensajes()],
                         ["usuario", "asistente", "usuario", "herramienta", "asistente"])
        self.assertEqual(self.repo.listar(), [original.id])

    def test_errores_controlados(self):
        self.assertEqual(self.repo.listar(), [])
        for malo in ("no_existe", "../fuera", "a/b", "..", ""):
            with self.assertRaises(ErrorPersistencia):
                self.repo.cargar(malo)
        self.repo.guardar(Conversacion("ok"))
        carpeta = Path(self.tmp.name) / "a" / "b"
        (carpeta / "roto.json").write_text("{no es json", encoding="utf-8")
        (carpeta / "vacio.json").write_text('{"id": "vacio"}', encoding="utf-8")
        (carpeta / "rol.json").write_text(
            json.dumps({"id": "rol", "mensajes": [{"rol": "x", "contenido": "y"}]}), encoding="utf-8")
        for id_conv in ("roto", "vacio", "rol"):
            with self.assertRaises(ErrorPersistencia):
                self.repo.cargar(id_conv)
        with self.assertRaises(ErrorPersistencia):
            self.repo.guardar(Conversacion("../escape"))

    def test_chat_sobrevive_a_errores_de_carga(self):
        carpeta = Path(self.tmp.name) / "a" / "b"
        carpeta.mkdir(parents=True)
        (carpeta / "roto.json").write_text("{", encoding="utf-8")
        texto = ejecutar_chat(["/cargar roto", "/cargar ../x", "/cargar nada", "/cargar", "hola"],
                              crear_agente(), self.repo)
        self.assertEqual(texto.count("⚠"), 3)
        self.assertIn("Uso: /cargar <id>", texto)
        self.assertIn("NEXO > ¡Hola!", texto)

    def test_comandos_de_memoria(self):
        agente = crear_agente()
        texto = ejecutar_chat(["/lista", "/historial", "hola", "/guardar"], agente, self.repo)
        self.assertIn("No hay conversaciones guardadas.", texto)
        self.assertIn("La conversación está vacía.", texto)
        id_viejo = agente.conversacion.id
        self.assertIn(f"💾 Conversación {id_viejo} guardada", texto)
        texto = ejecutar_chat(["/nueva", "/historial", f"/cargar {id_viejo}", "/historial", "/lista"],
                              agente, self.repo)
        self.assertIn(f"📂 Conversación {id_viejo} cargada (2 mensajes)", texto)
        self.assertIn("[usuario] hola", texto)
        self.assertIn("Tokens estimados: 10", texto)  # 8 palabras * 1.3 = 10.4 -> 10
        self.assertEqual(self.repo.listar(), [id_viejo])


class TestRegistroCSV(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.ruta = Path(self.tmp.name) / "datos" / "uso.csv"

    def test_registro_y_stats(self):
        registro = RegistroUso(self.ruta)
        self.assertEqual(registro.resumen(), {"total": 0, "usos": {}, "fallos": {}})
        agente = crear_agente(registro)
        texto = ejecutar_chat(
            ["3 * 4", "10 / 0", "cuánto son 100 USD en euros", "/stats"],
            agente, registro=registro)
        with open(self.ruta, newline="", encoding="utf-8") as f:
            filas = list(csv.reader(f))
        self.assertEqual(filas[0], ["fecha", "herramienta", "argumentos", "exito", "milisegundos"])
        self.assertEqual([f[1] for f in filas[1:]], ["calculadora", "calculadora", "conversor_moneda"])
        self.assertEqual([f[3] for f in filas[1:]], ["True", "False", "True"])
        self.assertGreaterEqual(float(filas[1][4]), 0)
        self.assertEqual(registro.resumen(), {
            "total": 3,
            "usos": {"calculadora": 2, "conversor_moneda": 1},
            "fallos": {"calculadora": 1, "conversor_moneda": 0}})
        self.assertIn("Ejecuciones de herramientas: 3", texto)
        self.assertIn("calculadora: 2 usos, 1 fallos", texto)
        self.assertIn("No he podido completar la operación", texto)

    def test_cabecera_unica_y_acumulacion(self):
        RegistroUso(self.ruta).registrar("calculadora", {"a": 1}, True, 0.1)
        RegistroUso(self.ruta).registrar("calculadora", {"a": 2}, False, 0.2)
        lineas = self.ruta.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lineas), 3)
        self.assertEqual(sum(l.startswith("fecha,") for l in lineas), 1)

    def test_agente_sin_registro(self):
        agente = crear_agente(None)
        agente.procesar("3 * 79.9")
        self.assertEqual(len(agente.conversacion), 3)


class TestMainEntreEjecuciones(unittest.TestCase):
    def ejecutar(self, cwd, entradas):
        r = subprocess.run([sys.executable, str(RAIZ / "main.py")], input="\n".join(entradas) + "\n",
                           capture_output=True, text=True, cwd=cwd, encoding="utf-8", timeout=30)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout

    def test_guardar_cerrar_abrir_cargar(self):
        with tempfile.TemporaryDirectory() as tmp:
            salida = self.ejecutar(tmp, ["hola", "2 + 2", "/guardar", "/salir"])
            id_conv = salida.split("💾 Conversación ")[1].split()[0]
            self.assertTrue((Path(tmp) / "datos" / "conversaciones" / f"{id_conv}.json").exists())
            salida = self.ejecutar(tmp, ["/lista", f"/cargar {id_conv}", "/historial", "/stats", "/salir"])
            self.assertIn(f"  - {id_conv}", salida)
            self.assertIn("(5 mensajes)", salida)
            self.assertIn("[herramienta] 2 + 2 = 4", salida)
            self.assertIn("calculadora: 1 usos, 0 fallos", salida)


if __name__ == "__main__":
    unittest.main()
