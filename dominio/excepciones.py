class ErrorAgente(Exception):
    """Excepción base de NEXO."""


class HerramientaNoEncontrada(ErrorAgente):
    """El modelo ha pedido una herramienta que el agente no tiene."""


class ArgumentosInvalidos(ErrorAgente):
    """Los argumentos recibidos por una herramienta no son válidos."""


class LimiteContextoSuperado(ErrorAgente):
    """La conversación supera el límite de tokens permitido."""


class ErrorPersistencia(ErrorAgente):
    """Fallo al guardar o leer datos en disco (JSON/CSV)."""
