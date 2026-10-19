from dominio.excepciones import ErrorAgente, LimiteContextoSuperado
from dominio.modelos import ModeloEco, ModeloReglas


class ChatConsola:
    """Capa de presentación: lee, delega en el agente y muestra."""

    MODELOS = {"eco": ModeloEco, "reglas": ModeloReglas}

    # Recibe el agente y lo opcional; entrada y salida se pueden cambiar en las pruebas.
    def __init__(self, agente, repositorio=None, registro_uso=None,
                 entrada=input, salida=print):
        self._agente = agente
        self._repositorio = repositorio
        self._registro = registro_uso
        self._entrada = entrada
        self._salida = salida
        self._activo = False
        self._comandos = {
            "/herramientas": self._cmd_herramientas,
            "/modelo": self._cmd_modelo,
            "/salir": self._cmd_salir,
            "/historial": self._cmd_historial,
            "/guardar": self._cmd_guardar,
            "/cargar": self._cmd_cargar,
            "/lista": self._cmd_lista,
            "/nueva": self._cmd_nueva,
            "/stats": self._cmd_stats,
        }

    # Bucle del chat: lee, ejecuta un comando o una pregunta y muestra los errores sin cerrarse.
    def iniciar(self):
        self._banner()
        self._activo = True
        while self._activo:
            try:
                texto = self._entrada("tú > ").strip()
            except (EOFError, KeyboardInterrupt):
                self._salida("\n👋 ¡Hasta pronto!")
                break
            if not texto:
                continue
            try:
                if texto.startswith("/"):
                    self._ejecutar_comando(texto)
                else:
                    self._responder(texto)
            except LimiteContextoSuperado:
                self._salida("⚠ La conversación ha superado el límite de contexto. "
                             "Guárdala con /guardar y empieza otra con /nueva.")
            except ErrorAgente as e:
                self._salida(f"⚠ {e}")
            except Exception as e:  # el chat nunca se cierra por un fallo inesperado
                self._salida(f"⚠ Error inesperado: {e}")

    # Muestra el cartel de bienvenida.
    def _banner(self):
        self._salida("╭──────────────────────────────────────╮")
        self._salida("│ 🤖 NEXO · asistente de TechNova      │")
        self._salida("│ Escribe /herramientas o /salir       │")
        self._salida("╰──────────────────────────────────────╯")

    # Envía el texto al agente y muestra las herramientas usadas y la respuesta.
    def _responder(self, texto):
        resumida_antes = self._agente.conversacion.veces_resumida
        respuesta = self._agente.procesar(texto)
        for nombre, argumentos in self._agente.herramientas_usadas:
            args = ", ".join(f"{k}={v!r}" for k, v in argumentos.items())
            self._salida(f"🔧 {nombre}({args})")
        if self._agente.conversacion.veces_resumida > resumida_antes:
            self._salida("🗜 He resumido los mensajes antiguos para no superar el límite de tokens")
        self._salida(f"NEXO > {respuesta}")

    # Separa el comando de su argumento y llama a la función que le toca.
    def _ejecutar_comando(self, texto):
        partes = texto.split(maxsplit=1)
        comando = partes[0].lower()
        argumento = partes[1].strip() if len(partes) > 1 else ""
        manejador = self._comandos.get(comando)
        if manejador is None:
            self._salida(f"Comando desconocido: {comando}")
            return
        manejador(argumento)

    # --- Nivel 1 ---
    # /herramientas: lista las herramientas disponibles.
    def _cmd_herramientas(self, _):
        for linea in self._agente.listar_herramientas():
            self._salida(linea)

    # /modelo eco|reglas: cambia de modelo.
    def _cmd_modelo(self, argumento):
        clase = self.MODELOS.get(argumento.lower())
        if clase is None:
            self._salida("Uso: /modelo eco | /modelo reglas")
            return
        self._agente.cambiar_modelo(clase())
        self._salida(f"✔ Modelo cambiado a {clase.__name__}")

    # /salir: termina el chat.
    def _cmd_salir(self, _):
        self._salida("👋 ¡Hasta pronto!")
        self._activo = False

    # --- Nivel 2 ---
    # /historial: muestra los mensajes y los tokens estimados.
    def _cmd_historial(self, _):
        conversacion = self._agente.conversacion
        mensajes = conversacion.get_mensajes()
        if not mensajes:
            self._salida("La conversación está vacía.")
            return
        for i, mensaje in enumerate(mensajes, 1):
            self._salida(f"{i:>2}. {mensaje}")
        self._salida(f"Mensajes: {len(conversacion)} · "
                     f"Tokens estimados: {conversacion.tokens_estimados()}")

    # Avisa y devuelve False si no hay persistencia.
    def _hay_repositorio(self):
        if self._repositorio is None:
            self._salida("⚠ La persistencia no está disponible.")
            return False
        return True

    # /guardar: guarda la conversación actual.
    def _cmd_guardar(self, _):
        if not self._hay_repositorio():
            return
        conversacion = self._agente.conversacion
        self._repositorio.guardar(conversacion)
        self._salida(f"💾 Conversación {conversacion.id} guardada")

    # /cargar <id>: carga una conversación guardada.
    def _cmd_cargar(self, argumento):
        if not self._hay_repositorio():
            return
        if not argumento:
            self._salida("Uso: /cargar <id>")
            return
        conversacion = self._repositorio.cargar(argumento)
        self._agente.conversacion = conversacion
        self._salida(f"📂 Conversación {conversacion.id} cargada "
                     f"({len(conversacion)} mensajes)")

    # /lista: muestra las conversaciones guardadas.
    def _cmd_lista(self, _):
        if not self._hay_repositorio():
            return
        ids = self._repositorio.listar()
        if not ids:
            self._salida("No hay conversaciones guardadas.")
            return
        self._salida("Conversaciones guardadas:")
        for id_conv in ids:
            self._salida(f"  - {id_conv}")

    # /nueva: empieza una conversación nueva.
    def _cmd_nueva(self, _):
        self._agente.nueva_conversacion()
        self._salida(f"✨ Nueva conversación {self._agente.conversacion.id}")

    # /stats: muestra el resumen del registro de uso.
    def _cmd_stats(self, _):
        if self._registro is None:
            self._salida("⚠ El registro de uso no está disponible.")
            return
        resumen = self._registro.resumen()
        self._salida(f"📊 Ejecuciones de herramientas: {resumen['total']}")
        for herramienta, usos in resumen["usos"].items():
            fallos = resumen["fallos"].get(herramienta, 0)
            self._salida(f"  - {herramienta}: {usos} usos, {fallos} fallos")
