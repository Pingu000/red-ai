from langchain_core.tools import tool
import subprocess

@tool
def herramienta_nmap(objetivo: str) -> str:
    """
    Útil para realizar un escaneo de puertos sobre una dirección IP o dominio.
    Devuelve la salida en texto plano de nmap indicando puertos abiertos y servicios.
    """
    print(f"\n[🔧 SISTEMA] La IA ha decidido ejecutar Nmap contra: {objetivo}")
    try:
        # Usamos una lista de argumentos (shell=False por defecto) por seguridad.
        # -F hace un escaneo rápido (Fast) para no ralentizar el TFG.
        resultado = subprocess.run(
            ['nmap', '-F', objetivo], 
            capture_output=True, 
            text=True, 
            timeout=60
        )
        return resultado.stdout
    except subprocess.TimeoutExpired:
        return "Error: El escaneo de nmap tardó demasiado (timeout)."
    except Exception as e:
        return f"Error crítico al ejecutar nmap: {e}"
