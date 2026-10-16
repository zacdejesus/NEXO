import time

from dominio.excepciones import (
    ArgumentosInvalidos,
    ErrorAgente,
    HerramientaNoEncontrada,
)
from dominio.mensaje import Conversacion, Mensaje


class Agente:
    """Bucle del agente: usuario -> modelo -> herramienta -> modelo -> respuesta."""

    MAX_ITERACIONES = 3

    def __init__(self, modelo, herramientas, registro_uso=None):
        self.modelo = modelo
        self._herramientas = {h.nombre: h for h in herramientas}
        self._registro = registro_uso
        self.conversacion = Conversacion()
        self._llamadas = []

    @property
    def herramientas_usadas(self):
        """Llamadas (nombre, argumentos) hechas en el último turno."""
        return list(self._llamadas)

    def procesar(self, texto_usuario) -> str:
        self.conversacion.agregar(Mensaje("usuario", texto_usuario))
        self._llamadas = []
        herramientas = list(self._herramientas.values())

        for _ in range(self.MAX_ITERACIONES):
            respuesta = self.modelo.responder(self.conversacion, herramientas)
            if not respuesta.es_llamada_herramienta():
                texto = respuesta.texto or ""
                self.conversacion.agregar(Mensaje("asistente", texto))
                return texto

            resultado = self._ejecutar_herramienta(respuesta.herramienta, respuesta.argumentos)
            self.conversacion.agregar(Mensaje("herramienta", resultado))

        raise ErrorAgente(
            f"El modelo no llegó a una respuesta final en {self.MAX_ITERACIONES} iteraciones"
        )

    def _ejecutar_herramienta(self, nombre, argumentos):
        herramienta = self._herramientas.get(nombre)
        if herramienta is None:
            raise HerramientaNoEncontrada(f"La herramienta '{nombre}' no existe")
        self._llamadas.append((nombre, dict(argumentos)))

        exito = True
        inicio = time.perf_counter()
        try:
            resultado = herramienta.ejecutar(**argumentos)
        except ArgumentosInvalidos as e:
            exito = False
            resultado = f"Error: {e}"
        except Exception:
            self._registrar(nombre, argumentos, False, inicio)
            raise
        self._registrar(nombre, argumentos, exito, inicio)
        return resultado

    def _registrar(self, nombre, argumentos, exito, inicio):
        if self._registro is not None:
            milisegundos = (time.perf_counter() - inicio) * 1000
            self._registro.registrar(nombre, argumentos, exito, milisegundos)

    def listar_herramientas(self) -> list[str]:
        return [str(h) for h in self._herramientas.values()]

    def cambiar_modelo(self, modelo):
        self.modelo = modelo

    def nueva_conversacion(self):
        self.conversacion = Conversacion()
        self._llamadas = []
