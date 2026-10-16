import uuid
from datetime import datetime

from dominio.excepciones import LimiteContextoSuperado


class Mensaje:
    """Un mensaje de la conversación. Es inmutable de cara al exterior."""

    ROLES_VALIDOS = ("usuario", "asistente", "herramienta")

    def __init__(self, rol, contenido, fecha=None):
        if rol not in self.ROLES_VALIDOS:
            raise ValueError(
                f"Rol no válido: {rol!r}. Roles válidos: {', '.join(self.ROLES_VALIDOS)}"
            )
        if not isinstance(contenido, str):
            raise ValueError("El contenido del mensaje debe ser texto")
        if fecha is None:
            fecha = datetime.now().isoformat()
        else:
            try:
                datetime.fromisoformat(fecha)
            except (TypeError, ValueError) as e:
                raise ValueError(f"Fecha no válida: {fecha!r}") from e
        self._rol = rol
        self._contenido = contenido
        self._fecha = fecha

    @property
    def rol(self):
        return self._rol

    @property
    def contenido(self):
        return self._contenido

    @property
    def fecha(self):
        return self._fecha

    def __str__(self):
        return f"[{self._rol}] {self._contenido}"

    def to_dict(self):
        return {"rol": self._rol, "contenido": self._contenido, "fecha": self._fecha}

    @classmethod
    def from_dict(cls, datos):
        if not isinstance(datos, dict):
            raise ValueError("Mensaje no válido: se esperaba un diccionario")
        for campo in ("rol", "contenido"):
            if campo not in datos:
                raise ValueError(f"Falta el campo '{campo}' en el mensaje")
        return cls(datos["rol"], datos["contenido"], datos.get("fecha"))


class Conversacion:
    """Historial de mensajes con límite de tokens. La lista es privada.

    Reto 6: al superar el 80 % del límite, los mensajes antiguos se sustituyen
    por un único mensaje-resumen y se conservan intactos los más recientes.
    """

    UMBRAL_RESUMEN = 0.8
    MENSAJES_RECIENTES = 4
    PROPORCION_RESUMEN = 0.25  # the summary uses at most 25 % of the limit
    PREFIJO_RESUMEN = "[Resumen"

    def __init__(self, id=None, limite_tokens=500, resumen_automatico=True):
        self.id = id or uuid.uuid4().hex[:8]
        self.__mensajes = []
        self._limite_tokens = limite_tokens
        self._resumen_automatico = resumen_automatico
        self._veces_resumida = 0

    @property
    def veces_resumida(self):
        return self._veces_resumida

    @staticmethod
    def _tokens(mensajes):
        return round(sum(len(m.contenido.split()) for m in mensajes) * 1.3)

    def agregar(self, mensaje):
        candidatos = self.__mensajes + [mensaje]
        resumida = False
        if (self._resumen_automatico
                and self._tokens(candidatos) > self._limite_tokens * self.UMBRAL_RESUMEN):
            compactados = self._compactar(self.__mensajes, mensaje)
            if compactados is not None:
                candidatos = compactados + [mensaje]
                resumida = True
        if self._tokens(candidatos) > self._limite_tokens:
            raise LimiteContextoSuperado(
                f"Se supera el límite de {self._limite_tokens} tokens de la conversación"
            )
        self.__mensajes = candidatos  # only commit once we know it fits
        if resumida:
            self._veces_resumida += 1

    def _compactar(self, mensajes, nuevo):
        """Old messages -> one summary + the most recent ones. Keeps as many recent
        messages as possible (MENSAJES_RECIENTES down to 2) while getting back under
        the 80 % threshold. None if summarizing doesn't save anything."""
        objetivo = self._limite_tokens * self.UMBRAL_RESUMEN
        mejor = None
        for recientes in range(self.MENSAJES_RECIENTES, 1, -1):
            antiguos = mensajes[:-recientes]
            if not antiguos:
                continue
            compactados = [self._resumir(antiguos)] + mensajes[-recientes:]
            if self._tokens(compactados) >= self._tokens(mensajes):
                continue  # the summary would be longer than what it replaces
            mejor = compactados
            if self._tokens(compactados + [nuevo]) <= objetivo:
                break
        return mejor

    def _resumir(self, antiguos):
        temas = []
        for mensaje in antiguos:
            if mensaje.contenido.startswith(self.PREFIJO_RESUMEN):
                temas.append(mensaje.contenido.split("Temas: ", 1)[-1])  # carry the previous summary
            elif mensaje.rol == "usuario":
                temas.append(" ".join(mensaje.contenido.split()[:6]))
        max_palabras = max(5, int(self._limite_tokens * self.PROPORCION_RESUMEN / 1.3))
        palabras = "; ".join(temas).split()[-max_palabras:]  # keep the most recent topics
        return Mensaje("asistente",
                       f"{self.PREFIJO_RESUMEN} de {len(antiguos)} mensajes anteriores] "
                       f"Temas: {' '.join(palabras) or 'sin preguntas del usuario'}")

    def get_mensajes(self):
        return list(self.__mensajes)

    def tokens_estimados(self):
        return self._tokens(self.__mensajes)

    def __len__(self):
        return len(self.__mensajes)

    def to_dict(self):
        return {"id": self.id, "mensajes": [m.to_dict() for m in self.__mensajes]}

    @classmethod
    def from_dict(cls, datos):
        if not isinstance(datos, dict):
            raise ValueError("Conversación no válida: se esperaba un diccionario")
        for campo in ("id", "mensajes"):
            if campo not in datos:
                raise ValueError(f"Falta el campo '{campo}' en la conversación")
        if not isinstance(datos["id"], str) or not datos["id"]:
            raise ValueError("El identificador de la conversación no es válido")
        if not isinstance(datos["mensajes"], list):
            raise ValueError("'mensajes' debe ser una lista")
        conversacion = cls(datos["id"])
        # Se restaura el historial tal cual se guardó (sin aplicar el límite).
        conversacion.__mensajes = [Mensaje.from_dict(m) for m in datos["mensajes"]]
        return conversacion
