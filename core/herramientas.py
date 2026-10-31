"""
Herramientas de Kali Linux disponibles para el agente Red-AI.
Cada función está decorada con @tool para que el LLM pueda invocarlas autónomamente.
"""

from langchain_core.tools import tool
import subprocess


def _ejecutar_comando(comando: list, timeout: int = 120) -> str:
    """Ejecutor base seguro. Nunca usa shell=True."""
    try:
        resultado = subprocess.run(
            comando,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        salida = resultado.stdout
        if resultado.stderr and not salida:
            salida = resultado.stderr
        return salida if salida else "El comando no produjo salida."
    except subprocess.TimeoutExpired:
        return f"Timeout: el comando tardó más de {timeout}s."
    except FileNotFoundError:
        return f"Error: '{comando[0]}' no está instalado en este sistema."
    except Exception as e:
        return f"Error inesperado: {e}"


@tool
def herramienta_nmap(objetivo: str, opciones: str = "-sV -sC -T4 --top-ports 1000") -> str:
    """
    Realiza un escaneo de puertos y detección de servicios con Nmap.
    Úsala al inicio de cualquier auditoría para mapear la superficie de ataque.
    Args:
        objetivo: IP, dominio o rango (ej: '192.168.1.1' o 'ejemplo.com')
        opciones: Flags de nmap. Por defecto detecta servicios y versiones.
    """
    print(f"\n[NMAP] Escaneando: {objetivo}")
    cmd = ['nmap'] + opciones.split() + [objetivo]
    return _ejecutar_comando(cmd, timeout=120)


@tool
def herramienta_whatweb(objetivo: str) -> str:
    """
    Identifica tecnologías web: CMS, frameworks, servidores, librerías JS, etc.
    Úsala sobre URLs completas para conocer el stack tecnológico del objetivo.
    Args:
        objetivo: URL completa (ej: 'http://192.168.1.10' o 'https://ejemplo.com')
    """
    print(f"\n[WHATWEB] Identificando tecnologías en: {objetivo}")
    cmd = ['whatweb', '--color=never', '-v', objetivo]
    return _ejecutar_comando(cmd, timeout=60)


@tool
def herramienta_gobuster(objetivo: str, wordlist: str = "/usr/share/wordlists/dirb/common.txt") -> str:
    """
    Enumera directorios y archivos ocultos mediante fuerza bruta de rutas.
    Úsala para descubrir paneles de admin, backups, APIs no documentadas, etc.
    Args:
        objetivo: URL base del objetivo (ej: 'http://192.168.1.10')
        wordlist: Ruta a la wordlist. Por defecto usa dirb/common.txt de Kali.
    """
    print(f"\n[GOBUSTER] Enumerando directorios en: {objetivo}")
    cmd = ['gobuster', 'dir', '-u', objetivo, '-w', wordlist, '-t', '20', '--no-color', '-q']
    return _ejecutar_comando(cmd, timeout=180)


@tool
def herramienta_nikto(objetivo: str) -> str:
    """
    Analiza el servidor web en busca de vulnerabilidades conocidas, configuraciones
    inseguras, archivos peligrosos y cabeceras de seguridad ausentes.
    Args:
        objetivo: URL o IP del servidor web (ej: 'http://192.168.1.10')
    """
    print(f"\n[NIKTO] Analizando vulnerabilidades en: {objetivo}")
    cmd = ['nikto', '-h', objetivo, '-nointeractive']
    return _ejecutar_comando(cmd, timeout=180)


@tool
def herramienta_curl(url: str, metodo: str = "GET", headers: str = "", datos: str = "") -> str:
    """
    Realiza peticiones HTTP personalizadas para validar vulnerabilidades manualmente.
    Úsala para probar endpoints específicos, inyecciones simples o verificar respuestas.
    Args:
        url: URL completa incluyendo parámetros si los hay
        metodo: GET, POST, PUT, DELETE, etc.
        headers: Cabeceras adicionales en formato 'Nombre: Valor' (separadas por '|')
        datos: Cuerpo de la petición para POST/PUT (ej: 'user=admin&pass=test')
    """
    print(f"\n[CURL] {metodo} -> {url}")
    cmd = ['curl', '-s', '-i', '-X', metodo, '--max-time', '30']
    if headers:
        for header in headers.split('|'):
            cmd += ['-H', header.strip()]
    if datos:
        cmd += ['-d', datos]
    cmd.append(url)
    return _ejecutar_comando(cmd, timeout=35)


@tool
def herramienta_sqlmap(url: str, parametro: str = "", opciones_extra: str = "--level=1 --risk=1 --batch") -> str:
    """
    Detecta y analiza vulnerabilidades de inyección SQL de forma automatizada.
    IMPORTANTE: Solo usar con autorización explícita documentada.
    Args:
        url: URL del endpoint a analizar (ej: 'http://objetivo.com/page.php?id=1')
        parametro: Parámetro específico a testear (ej: 'id'). Vacío = todos.
        opciones_extra: Flags adicionales de sqlmap.
    """
    print(f"\n[SQLMAP] Analizando inyección SQL en: {url}")
    cmd = ['sqlmap', '-u', url] + opciones_extra.split()
    if parametro:
        cmd += ['-p', parametro]
    return _ejecutar_comando(cmd, timeout=300)


# Registro global de herramientas
TODAS_LAS_HERRAMIENTAS = [
    herramienta_nmap,
    herramienta_whatweb,
    herramienta_gobuster,
    herramienta_nikto,
    herramienta_curl,
    herramienta_sqlmap,
]

MAPA_HERRAMIENTAS = {t.name: t for t in TODAS_LAS_HERRAMIENTAS}
