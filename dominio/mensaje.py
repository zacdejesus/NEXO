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
    """Historial de mensajes con límite de tokens. La lista es privada."""

    def __init__(self, id=None, limite_tokens=500):
        self.id = id or uuid.uuid4().hex[:8]
        self.__mensajes = []
        self._limite_tokens = limite_tokens

    def _palabras(self):
        return sum(len(m.contenido.split()) for m in self.__mensajes)

    def agregar(self, mensaje):
        palabras = self._palabras() + len(mensaje.contenido.split())
        if round(palabras * 1.3) > self._limite_tokens:
            raise LimiteContextoSuperado(
                f"Se supera el límite de {self._limite_tokens} tokens de la conversación"
            )
        self.__mensajes.append(mensaje)

    def get_mensajes(self):
        return list(self.__mensajes)

    def tokens_estimados(self):
        return round(self._palabras() * 1.3)

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
