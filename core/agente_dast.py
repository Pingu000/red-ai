"""
Agente DAST principal — Red-AI
LangGraph + Ollama / Anthropic Claude
"""
import os
import operator
import json
import re
import sys
from typing import TypedDict, Annotated, List

from langchain_ollama import ChatOllama
try:
    from langchain_anthropic import ChatAnthropic
    ANTHROPIC_DISPONIBLE = True
except ImportError:
    ANTHROPIC_DISPONIBLE = False

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from core.herramientas import TODAS_LAS_HERRAMIENTAS, MAPA_HERRAMIENTAS
from core.prompts import SYSTEM_PROMPT, PROMPT_ANALISIS, PROMPT_REPORTE

def _urls_visitadas(hallazgos: list) -> list:
    """Extrae URLs ya visitadas con curl desde los hallazgos."""
    urls = []
    for h in hallazgos:
        if "[CURL]" in h or "[HERRAMIENTA_CURL]" in h:
            for token in h.split():
                if token.startswith("http://") or token.startswith("https://"):
                    urls.append(token.rstrip('.,;"'))
    return list(dict.fromkeys(urls))


# ─── Configuración ────────────────────────────────────────────────────────────
OLLAMA_URL = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
MODELO_DEFAULT = "qwen2.5-coder:14b"


def _crear_llm(modelo: str, temperature: float = 0, con_tools: bool = False):
    """Crea el LLM adecuado según el modelo especificado."""
    if modelo.startswith("claude-"):
        if not ANTHROPIC_DISPONIBLE:
            raise ImportError("langchain-anthropic no instalado. Ejecuta: pip install langchain-anthropic")
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY no configurada. Introdúcela en el dashboard.")
        llm = ChatAnthropic(model=modelo, api_key=api_key)
    else:
        llm = ChatOllama(base_url=OLLAMA_URL, model=modelo, temperature=temperature)
    if con_tools:
        return llm.bind_tools(TODAS_LAS_HERRAMIENTAS)
    return llm


# ─── Estado del grafo ─────────────────────────────────────────────────────────
class AgentState(TypedDict):
    objetivo: str
    modelo: str
    hallazgos: Annotated[List[str], operator.add]
    herramientas_usadas: Annotated[List[str], operator.add]
    iteracion: int
    reporte: str
    # Historial completo de mensajes — acumulado con operator.add
    # Esto ES la memoria: cada iteración añade sus mensajes al historial
    messages: Annotated[List, operator.add]
    pensamiento: str


# ─── Parser de emergencia ─────────────────────────────────────────────────────

def _extraer_json_balanceado(texto: str) -> dict | None:
    """Extrae el primer objeto JSON completo (con llaves balanceadas)."""
    depth = 0
    start = None
    for i, ch in enumerate(texto):
        if ch == '{':
            if depth == 0:
                start = i
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0 and start is not None:
                fragment = texto[start:i+1]
                try:
                    return json.loads(fragment)
                except json.JSONDecodeError:
                    start = None
    return None


def _intentar_ejecutar_desde_texto(content: str) -> list | None:
    """
    Intenta parsear un tool-call embebido como JSON en el texto del LLM.
    Retorna [nombre_herramienta, resultado_str] o None.
    """
    datos = _extraer_json_balanceado(content)
    if not datos:
        return None

    nombre = datos.get("name") or datos.get("tool") or datos.get("function")
    argumentos = (
        datos.get("arguments")
        or datos.get("args")
        or datos.get("parameters")
        or {}
    )
    if not nombre or nombre not in MAPA_HERRAMIENTAS:
        return None

    herramienta = MAPA_HERRAMIENTAS[nombre]
    print(f"\n[PARSER] Tool call detectado en texto: {nombre}({argumentos})")
    try:
        resultado = herramienta.invoke(argumentos)
        return [nombre, str(resultado)]
    except Exception as e:
        return [nombre, f"Error ejecutando {nombre}: {e}"]


# ─── Extractor de pensamiento ─────────────────────────────────────────────────

def _extraer_pensamiento(content: str) -> str:
    """
    Extrae el texto de razonamiento antes del JSON / tool call.
    Todo lo que no es el bloque JSON se considera pensamiento.
    """
    sin_code = re.sub(r'```[^`]*```', '', content, flags=re.DOTALL)
    depth = 0
    start_json = None
    for i, ch in enumerate(sin_code):
        if ch == '{':
            if depth == 0:
                start_json = i
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0 and start_json is not None:
                sin_code = sin_code[:start_json] + sin_code[i+1:]
                break
    pensamiento = sin_code.strip()
    return pensamiento if len(pensamiento) > 5 else ""


# ─── Nodos del grafo ──────────────────────────────────────────────────────────

def nodo_reconocimiento(state: AgentState) -> dict:
    objetivo = state["objetivo"]
    modelo = state.get("modelo", MODELO_DEFAULT)
    print(f"\n{'='*60}")
    print(f"[RECONOCIMIENTO] Iniciando con modelo: {modelo}")
    print(f"[RECONOCIMIENTO] Objetivo: {objetivo}")
    print('='*60)

    llm = _crear_llm(modelo, temperature=0)
    hallazgos = []
    herramientas_usadas = []

    # Nmap
    print("\n[+] Ejecutando nmap...")
    try:
        nmap_tool = MAPA_HERRAMIENTAS["herramienta_nmap"]
        resultado_nmap = nmap_tool.invoke({"objetivo": objetivo})
        hallazgos.append(f"[NMAP]\n{resultado_nmap}")
        herramientas_usadas.append("herramienta_nmap")
        print(f"[NMAP] Completado ({len(str(resultado_nmap))} chars)")
    except Exception as e:
        hallazgos.append(f"[NMAP] Error: {e}")

    # WhatWeb
    print("\n[+] Ejecutando whatweb...")
    try:
        whatweb_tool = MAPA_HERRAMIENTAS["herramienta_whatweb"]
        resultado_whatweb = whatweb_tool.invoke({"objetivo": objetivo})
        hallazgos.append(f"[WHATWEB]\n{resultado_whatweb}")
        herramientas_usadas.append("herramienta_whatweb")
        print(f"[WHATWEB] Completado ({len(str(resultado_whatweb))} chars)")
    except Exception as e:
        hallazgos.append(f"[WHATWEB] Error: {e}")

    # El primer mensaje del historial es el system prompt + contexto inicial
    mensaje_inicial = SystemMessage(content=SYSTEM_PROMPT)
    contexto_inicial = HumanMessage(content=(
        f"Iniciando auditoría sobre: {objetivo}\n\n"
        f"Reconocimiento inicial completado:\n\n"
        + "\n\n".join(hallazgos)
    ))

    return {
        "hallazgos": hallazgos,
        "herramientas_usadas": herramientas_usadas,
        "iteracion": 0,
        # Inicializamos el historial con el system prompt y el contexto de reconocimiento
        "messages": [mensaje_inicial, contexto_inicial],
        "pensamiento": "",
    }


def nodo_agente_decisor(state: AgentState) -> dict:
    objetivo = state["objetivo"]
    modelo = state.get("modelo", MODELO_DEFAULT)
    hallazgos = state.get("hallazgos", [])
    herramientas_usadas = state.get("herramientas_usadas", [])
    iteracion = state.get("iteracion", 0) + 1
    messages = state.get("messages", [])

    print(f"\n{'─'*60}")
    print(f"[AGENTE] Iteración #{iteracion} | Modelo: {modelo}")
    print(f"[AGENTE] Herramientas usadas: {herramientas_usadas}")
    print(f"[AGENTE] Mensajes en historial: {len(messages)}")

    llm = _crear_llm(modelo, temperature=0.1, con_tools=True)

    # Construir el mensaje de esta iteración con contexto resumido de lo nuevo
    urls_ya_vistas = _urls_visitadas(hallazgos)
    urls_str = "\n  - ".join(urls_ya_vistas) if urls_ya_vistas else "ninguna"

    # Solo los hallazgos recientes (últimos 3) como contexto del turno actual
    # El modelo YA tiene todo el historial anterior en messages[]
    hallazgos_recientes = hallazgos[-3:]
    hallazgos_str = "\n\n".join(h[:600] for h in hallazgos_recientes)

    prompt_turno = PROMPT_ANALISIS.format(
        objetivo=objetivo,
        iteracion=iteracion,
        herramientas_usadas=", ".join(herramientas_usadas) if herramientas_usadas else "ninguna",
        urls_visitadas=urls_str,
        hallazgos=hallazgos_str,
    )

    # Añadir el mensaje del turno actual al historial acumulado
    nuevo_mensaje_usuario = HumanMessage(content=prompt_turno)
    historial_completo = messages + [nuevo_mensaje_usuario]

    print(f"\n[AGENTE] Enviando historial completo al LLM ({len(historial_completo)} mensajes)...")
    respuesta = llm.invoke(historial_completo)
    content = respuesta.content if isinstance(respuesta.content, str) else ""

    # ── Extraer y mostrar pensamiento ───────────────────────────────────────
    pensamiento = _extraer_pensamiento(content)
    if pensamiento:
        print(f"\n\033[93m[💭 RAZONAMIENTO]\033[0m")
        print(f"\033[93m{pensamiento}\033[0m")

    # ── Procesar tool calls nativos ─────────────────────────────────────────
    nuevos_hallazgos = []
    nuevas_herramientas = []
    # Mensajes nuevos de este turno: el mensaje usuario + la respuesta del modelo
    nuevos_messages = [nuevo_mensaje_usuario, respuesta]

    if hasattr(respuesta, "tool_calls") and respuesta.tool_calls:
        for tc in respuesta.tool_calls:
            nombre = tc["name"]
            args = tc["args"]
            print(f"\n\033[94m[🔧 TOOL CALL]\033[0m {nombre}({args})")

            if nombre in MAPA_HERRAMIENTAS:
                try:
                    resultado = MAPA_HERRAMIENTAS[nombre].invoke(args)
                    resultado_str = str(resultado)
                    print(f"\033[92m[✓ RESULTADO]\033[0m {resultado_str[:300]}...")

                    # Añadir el resultado como ToolMessage al historial
                    tool_msg = ToolMessage(
                        content=resultado_str[:3000],  # truncar para no explotar el contexto
                        tool_call_id=tc.get("id", nombre),
                        name=nombre,
                    )
                    nuevos_messages.append(tool_msg)

                    nuevos_hallazgos.append(f"[{nombre.upper()}]\n{resultado_str}")
                    if nombre == "herramienta_curl":
                        url_usada = args.get("url", "")
                        nuevas_herramientas.append(f"herramienta_curl:{url_usada}")
                    else:
                        nuevas_herramientas.append(nombre)
                except Exception as e:
                    err = f"Error en {nombre}: {e}"
                    print(f"\033[91m[✗ ERROR]\033[0m {err}")
                    nuevos_hallazgos.append(f"[{nombre.upper()}] {err}")
                    tool_msg = ToolMessage(
                        content=err,
                        tool_call_id=tc.get("id", nombre),
                        name=nombre,
                    )
                    nuevos_messages.append(tool_msg)
            else:
                print(f"\033[91m[✗]\033[0m Herramienta desconocida: {nombre}")

    elif content:
        resultado_parser = _intentar_ejecutar_desde_texto(content)
        if resultado_parser:
            nombre_tool, resultado_str = resultado_parser
            print(f"\033[92m[✓ PARSER]\033[0m {nombre_tool}: {resultado_str[:300]}...")
            nuevos_hallazgos.append(f"[{nombre_tool.upper()}]\n{resultado_str}")
            nuevas_herramientas.append(nombre_tool)
        elif "AUDITORIA_COMPLETA" in content:
            print("\n\033[92m[✓] AUDITORIA_COMPLETA detectado\033[0m")
            nuevos_hallazgos.append("[DECISIÓN] AUDITORIA_COMPLETA")
        else:
            print(f"\n\033[90m[AGENTE] Respuesta de texto (sin tool call):\033[0m\n{content[:500]}")

    return {
        "hallazgos": nuevos_hallazgos,
        "herramientas_usadas": nuevas_herramientas,
        "iteracion": iteracion,
        # Acumulamos los mensajes nuevos de este turno (usuario + respuesta + tool results)
        "messages": nuevos_messages,
        "pensamiento": pensamiento,
    }


def nodo_generador_reporte(state: AgentState) -> dict:
    objetivo = state["objetivo"]
    modelo = state.get("modelo", MODELO_DEFAULT)
    hallazgos = state.get("hallazgos", [])

    print(f"\n{'='*60}")
    print(f"[REPORTE] Generando reporte final con modelo {modelo}...")

    MAX_CHARS_HALLAZGO = 600
    MAX_TOTAL = 5000
    hallazgos_truncados = []
    total = 0
    for h in hallazgos:
        h_corto = h[:MAX_CHARS_HALLAZGO]
        if total + len(h_corto) > MAX_TOTAL:
            break
        hallazgos_truncados.append(h_corto)
        total += len(h_corto)

    hallazgos_str = "\n\n---\n\n".join(hallazgos_truncados)

    llm = _crear_llm(modelo, temperature=0)
    prompt = PROMPT_REPORTE.format(objetivo=objetivo, hallazgos=hallazgos_str)

    try:
        respuesta = llm.invoke([{"role": "user", "content": prompt}])
        reporte = respuesta.content
    except Exception as e:
        print(f"[REPORTE] Error generando reporte: {e}")
        reporte = f"# Reporte de Auditoría — {objetivo}\n\n"
        reporte += "## Hallazgos\n\n"
        for h in hallazgos[:10]:
            reporte += f"- {h[:200]}\n"

    print(f"[REPORTE] Completado ({len(reporte)} chars)")
    return {"reporte": reporte}


# ─── Router ───────────────────────────────────────────────────────────────────

def decidir_siguiente_paso(state: AgentState) -> str:
    hallazgos = state.get("hallazgos", [])
    iteracion = state.get("iteracion", 0)

    for h in hallazgos[-3:]:
        if "AUDITORIA_COMPLETA" in h:
            print(f"\n[ROUTER] AUDITORIA_COMPLETA → generando reporte")
            return "generar_reporte"

    if iteracion >= 50:
        print(f"\n[ROUTER] Soft-cap de seguridad (50 iter) → generando reporte")
        return "generar_reporte"

    print(f"\n[ROUTER] Iteración {iteracion} → continuar")
    return "agente_decisor"


# ─── Construcción del grafo con MemorySaver ───────────────────────────────────

# MemorySaver persiste el estado entre llamadas del mismo thread_id en RAM.
# Permite reanudar una auditoría pausada dentro de la misma sesión.
_memory = MemorySaver()


def construir_grafo():
    builder = StateGraph(AgentState)

    builder.add_node("reconocimiento", nodo_reconocimiento)
    builder.add_node("agente_decisor", nodo_agente_decisor)
    builder.add_node("generar_reporte", nodo_generador_reporte)

    builder.set_entry_point("reconocimiento")
    builder.add_edge("reconocimiento", "agente_decisor")
    builder.add_conditional_edges(
        "agente_decisor",
        decidir_siguiente_paso,
        {
            "agente_decisor": "agente_decisor",
            "generar_reporte": "generar_reporte",
        },
    )
    builder.add_edge("generar_reporte", END)

    # Compilar con checkpointer para memoria persistente entre iteraciones
    return builder.compile(checkpointer=_memory)


def ejecutar_auditoria(objetivo: str, modelo: str = MODELO_DEFAULT) -> dict:
    grafo = construir_grafo()

    # thread_id único por auditoría — permite reanudar si se llama de nuevo con el mismo id
    import hashlib, time
    thread_id = hashlib.md5(f"{objetivo}-{time.time()}".encode()).hexdigest()[:12]
    config = {"configurable": {"thread_id": thread_id}}

    print(f"[MEMORIA] Thread ID de auditoría: {thread_id}")

    estado_inicial = {
        "objetivo": objetivo,
        "modelo": modelo,
        "hallazgos": [],
        "herramientas_usadas": [],
        "iteracion": 0,
        "reporte": "",
        "messages": [],
        "pensamiento": "",
    }
    resultado = grafo.invoke(estado_inicial, config=config)
    return resultado
