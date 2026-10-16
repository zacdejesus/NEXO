from dominio.herramientas import Calculadora, ConversorMoneda, BuscadorFAQ
from dominio.modelos import ModeloReglas
from servicios.agente import Agente
from persistencia.repositorio_conversaciones import RepositorioConversaciones
from persistencia.registro_uso import RegistroUso
from presentacion.chat_consola import ChatConsola

if __name__ == "__main__":
    herramientas = [Calculadora(), ConversorMoneda(), BuscadorFAQ()]
    registro = RegistroUso("datos/uso.csv")
    agente = Agente(ModeloReglas(), herramientas, registro)
    ChatConsola(agente, RepositorioConversaciones(), registro).iniciar()
