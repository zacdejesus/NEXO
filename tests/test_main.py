import subprocess
import sys
from pathlib import Path

from tests.ayudantes import RAIZ


def _ejecutar(cwd, entradas):
    resultado = subprocess.run([sys.executable, str(RAIZ / "main.py")], input="\n".join(entradas) + "\n",
                               capture_output=True, text=True, cwd=cwd, encoding="utf-8", timeout=30)
    assert resultado.returncode == 0, resultado.stderr
    return resultado.stdout


def test_guardar_cerrar_abrir_cargar(tmp_path):
    salida = _ejecutar(tmp_path, ["hola", "2 + 2", "/guardar", "/salir"])
    id_conv = salida.split("💾 Conversación ")[1].split()[0]
    assert (Path(tmp_path) / "datos" / "conversaciones" / f"{id_conv}.json").exists()
    salida = _ejecutar(tmp_path, ["/lista", f"/cargar {id_conv}", "/historial", "/stats", "/salir"])
    assert f"  - {id_conv}" in salida
    assert "(5 mensajes)" in salida
    assert "[herramienta] 2 + 2 = 4" in salida
    assert "calculadora: 1 usos, 0 fallos" in salida
