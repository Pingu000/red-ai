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


# ─── RECONOCIMIENTO ───────────────────────────────────────────────────────────

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
def herramienta_wafw00f(objetivo: str) -> str:
    """
    Detecta si el objetivo está protegido por un Web Application Firewall (WAF)
    e identifica su tipo. Úsala antes de lanzar scanners agresivos para adaptar
    la estrategia y evitar bloqueos.
    Args:
        objetivo: URL completa del objetivo (ej: 'http://ejemplo.com')
    """
    print(f"\n[WAFW00F] Detectando WAF en: {objetivo}")
    cmd = ['wafw00f', objetivo]
    return _ejecutar_comando(cmd, timeout=60)


# ─── ENUMERACIÓN / FUZZING ────────────────────────────────────────────────────

@tool
def herramienta_gobuster(objetivo: str, wordlist: str = "/usr/share/wordlists/dirb/common.txt") -> str:
    """
    Enumera DIRECTORIOS ocultos mediante fuerza bruta (sin extensión).
    Úsala para descubrir /admin, /login, /api, /backup, paneles de administración, etc.
    Los directorios web normalmente no tienen extensión.
    Args:
        objetivo: URL base del objetivo (ej: 'http://192.168.1.10')
        wordlist: Ruta a la wordlist. Por defecto usa dirb/common.txt de Kali.
    """
    print(f"\n[GOBUSTER] Enumerando directorios en: {objetivo}")
    cmd = ['gobuster', 'dir', '-u', objetivo, '-w', wordlist, '-t', '20', '--no-color', '-q']
    return _ejecutar_comando(cmd, timeout=180)


@tool
def herramienta_gobuster_archivos(objetivo: str, wordlist: str = "/usr/share/wordlists/dirb/common.txt") -> str:
    """
    Enumera ARCHIVOS con extensión en servidores ASP/IIS, PHP o similares.
    Úsala cuando el servidor sea IIS/ASP.NET o PHP para encontrar Login.asp,
    Search.aspx, config.php, etc. que no aparecen en la búsqueda de directorios.
    Args:
        objetivo: URL base del objetivo (ej: 'http://192.168.1.10')
        wordlist: Ruta a la wordlist. Por defecto usa dirb/common.txt de Kali.
    """
    print(f"\n[GOBUSTER-ARCHIVOS] Buscando archivos .asp/.aspx/.php en: {objetivo}")
    cmd = ['gobuster', 'dir', '-u', objetivo, '-w', wordlist, '-t', '20', '--no-color', '-q', '-x', 'asp,aspx,php,html,txt,bak']
    return _ejecutar_comando(cmd, timeout=180)


@tool
def herramienta_ffuf(
    objetivo: str,
    wordlist: str = "/usr/share/wordlists/dirb/common.txt",
    extensiones: str = "",
    filtro_codigo: str = "404",
) -> str:
    """
    Fuzzer web rápido y flexible. Úsalo para:
    - Enumerar directorios y archivos (más rápido que gobuster)
    - Fuzzear parámetros GET/POST poniendo FUZZ en la URL o datos
    - Descubrir virtual hosts poniendo FUZZ en el header Host
    Args:
        objetivo: URL con la palabra FUZZ donde corresponda
                  (ej: 'http://ejemplo.com/FUZZ' o 'http://ejemplo.com/page.php?id=FUZZ')
        wordlist: Wordlist a usar. Por defecto dirb/common.txt
        extensiones: Extensiones separadas por coma (ej: 'php,asp,html'). Vacío = ninguna.
        filtro_codigo: Código HTTP a filtrar/ignorar (ej: '404'). Por defecto oculta 404.
    """
    print(f"\n[FFUF] Fuzzing: {objetivo}")
    cmd = ['ffuf', '-u', objetivo, '-w', wordlist, '-fc', filtro_codigo, '-c', '-v']
    if extensiones:
        cmd += ['-e', extensiones]
    return _ejecutar_comando(cmd, timeout=180)


# ─── ANÁLISIS DE VULNERABILIDADES ────────────────────────────────────────────

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
def herramienta_nuclei(objetivo: str, templates: str = "cves,exposures,misconfiguration,vulnerabilities") -> str:
    """
    Scanner de vulnerabilidades basado en templates. Detecta CVEs conocidos,
    exposiciones de datos, misconfigs y vulnerabilidades comunes de forma automática.
    Es el scanner más completo y potente disponible. Úsalo siempre en la fase
    de análisis de vulnerabilidades.
    Args:
        objetivo: URL del objetivo (ej: 'http://ejemplo.com')
        templates: Categorías de templates separadas por coma.
                   Opciones: cves, exposures, misconfiguration, vulnerabilities,
                   default-logins, technologies, takeovers, network
    """
    print(f"\n[NUCLEI] Escaneando con templates [{templates}]: {objetivo}")
    # Construir lista de tags -t para cada categoría
    template_flags = []
    for t in templates.split(','):
        template_flags += ['-t', t.strip()]
    cmd = ['nuclei', '-u', objetivo] + template_flags + ['-silent', '-no-color']
    return _ejecutar_comando(cmd, timeout=300)


@tool
def herramienta_dalfox(url: str, parametro: str = "") -> str:
    """
    Scanner especializado en Cross-Site Scripting (XSS). Detecta XSS reflejado,
    almacenado y DOM-based con alta precisión. Úsalo en URLs con parámetros
    de entrada cuando nikto/nuclei sugieran posible XSS.
    Args:
        url: URL completa con parámetros (ej: 'http://ejemplo.com/search.php?q=test')
        parametro: Parámetro específico a analizar (ej: 'q'). Vacío = todos.
    """
    print(f"\n[DALFOX] Escaneando XSS en: {url}")
    cmd = ['dalfox', 'url', url, '--no-color', '--silence']
    if parametro:
        cmd += ['-p', parametro]
    return _ejecutar_comando(cmd, timeout=120)


@tool
def herramienta_commix(url: str, datos: str = "", parametro: str = "") -> str:
    """
    Detecta y explota vulnerabilidades de Command Injection (inyección de comandos OS).
    Úsalo cuando encuentres formularios o parámetros que interactúen con el sistema
    operativo del servidor (ping, resolve, convert, etc.).
    Args:
        url: URL del endpoint vulnerable (ej: 'http://ejemplo.com/ping.php?host=test')
        datos: Datos POST si es un formulario (ej: 'host=test&submit=Go')
        parametro: Parámetro específico a testear. Vacío = todos.
    """
    print(f"\n[COMMIX] Probando command injection en: {url}")
    cmd = ['commix', '--url', url, '--batch', '--no-color']
    if datos:
        cmd += ['--data', datos]
    if parametro:
        cmd += ['-p', parametro]
    return _ejecutar_comando(cmd, timeout=180)


# ─── EXPLOTACIÓN ──────────────────────────────────────────────────────────────

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


@tool
def herramienta_hydra(
    objetivo: str,
    servicio: str = "http-post-form",
    usuario: str = "admin",
    wordlist_pass: str = "/usr/share/wordlists/rockyou.txt",
    parametros_form: str = "",
) -> str:
    """
    Herramienta de fuerza bruta para autenticación. Úsala cuando encuentres
    paneles de login para intentar credenciales débiles o por defecto.
    Args:
        objetivo: IP o dominio del objetivo (ej: '192.168.1.10' o 'ejemplo.com')
        servicio: Protocolo/servicio (ej: 'http-post-form', 'http-get', 'ftp', 'ssh')
        usuario: Usuario a probar. Usa 'admin' por defecto.
        wordlist_pass: Ruta a wordlist de contraseñas. Por defecto rockyou.txt.
        parametros_form: Para http-post-form: '/ruta/login:usuario=^USER^&pass=^PASS^:F=mensaje_error_login'
    """
    print(f"\n[HYDRA] Fuerza bruta {servicio} en: {objetivo}")
    if servicio == "http-post-form" and parametros_form:
        cmd = ['hydra', '-l', usuario, '-P', wordlist_pass, objetivo,
               'http-post-form', parametros_form, '-V', '-f', '-t', '4']
    else:
        cmd = ['hydra', '-l', usuario, '-P', wordlist_pass, '-t', '4',
               '-f', '-V', f'{objetivo}', servicio]
    return _ejecutar_comando(cmd, timeout=300)


@tool
def herramienta_searchsploit(consulta: str) -> str:
    """
    Busca exploits conocidos en la base de datos local de Exploit-DB (ExploitDB).
    Úsala cuando identifiques versiones concretas de software, CMS o servicios
    para saber si existen exploits públicos disponibles.
    Args:
        consulta: Términos de búsqueda (ej: 'Apache 2.4.49', 'WordPress 5.8', 'vsftpd 2.3.4')
    """
    print(f"\n[SEARCHSPLOIT] Buscando exploits para: {consulta}")
    cmd = ['searchsploit', '--color', consulta]
    return _ejecutar_comando(cmd, timeout=30)


# ─── REGISTRO GLOBAL ─────────────────────────────────────────────────────────

TODAS_LAS_HERRAMIENTAS = [
    # Reconocimiento
    herramienta_nmap,
    herramienta_whatweb,
    herramienta_wafw00f,
    # Enumeración / Fuzzing
    herramienta_gobuster,
    herramienta_gobuster_archivos,
    herramienta_ffuf,
    # Análisis de vulnerabilidades
    herramienta_nikto,
    herramienta_nuclei,
    herramienta_dalfox,
    herramienta_commix,
    # Explotación
    herramienta_curl,
    herramienta_sqlmap,
    herramienta_hydra,
    herramienta_searchsploit,
]

MAPA_HERRAMIENTAS = {t.name: t for t in TODAS_LAS_HERRAMIENTAS}
