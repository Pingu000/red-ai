"""
Motor principal del agente Red-AI.
Grafo de estados LangGraph que orquesta el proceso autónomo de pentesting.
"""

from typing import TypedDict, List, Annotated
import operator
import json
import re
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import StateGraph, END

from core.herramientas import TODAS_LAS_HERRAMIENTAS, MAPA_HERRAMIENTAS
from core.prompts import SYSTEM_PROMPT, PROMPT_ANALISIS, PROMPT_REPORTE


# ==========================================
# 1. ESTADO GLOBAL DEL AGENTE
# ==========================================
class AgentState(TypedDict):
    objetivo: str
    autorizacion: str
    hallazgos: Annotated[List[str], operator.add]
    mensajes: Annotated[List, operator.add]
    iteracion: int
    max_iteraciones: int
    auditoria_completa: bool
    reporte_final: str


# ==========================================
# 2. CONEXIÓN AL LLM
# ==========================================
llm = ChatOllama(model="qwen2.5-coder:7b", temperature=0.1)
llm_con_herramientas = llm.bind_tools(TODAS_LAS_HERRAMIENTAS)


# ==========================================
# 3. PARSER DE CONTINGENCIA ROBUSTO
# Ejecuta la herramienta cuando el LLM devuelve JSON en texto plano.
# Usa extracción de JSON balanceado en lugar de regex simple,
# para soportar objetos anidados como {"arguments": {"objetivo": "..."}}
# ==========================================
def _extraer_json_balanceado(texto: str) -> list:
    """Extrae todos los objetos JSON válidos de un texto, respetando anidamiento."""
    candidatos = []
    i = 0
    while i < len(texto):
        if texto[i] == '{':
            depth = 0
            j = i
            while j < len(texto):
                if texto[j] == '{':
                    depth += 1
                elif texto[j] == '}':
                    depth -= 1
                    if depth == 0:
                        candidato = texto[i:j+1]
                        try:
                            datos = json.loads(candidato)
                            candidatos.append(datos)
                        except json.JSONDecodeError:
                            pass
                        break
                j += 1
        i += 1
    return candidatos


def _intentar_ejecutar_desde_texto(texto: str, iteracion: int) -> list:
    """
    Busca un JSON de tool call en el texto del LLM y ejecuta la herramienta.
    Soporta los formatos más comunes que devuelven los modelos locales:
      - {"name": "...", "arguments": {...}}
      - {"name": "...", "args": {...}}
      - {"tool": "...", "parameters": {...}}
    """
    # Limpiamos bloques de código markdown si los hay
    texto_limpio = re.sub(r'```(?:json)?\s*', '', texto).strip()

    candidatos = _extraer_json_balanceado(texto_limpio)

    for datos in candidatos:
        # Soportamos múltiples nombres de campo para la herramienta y sus argumentos
        nombre = datos.get("name") or datos.get("tool") or datos.get("function")
        args = (
            datos.get("arguments")
            or datos.get("args")
            or datos.get("parameters")
            or {}
        )

        if nombre and nombre in MAPA_HERRAMIENTAS:
            print(f"\n[IA→TOOL CONTINGENCIA] {nombre} | args: {args}")
            try:
                resultado = MAPA_HERRAMIENTAS[nombre].invoke(args)
                print(f"[✓] {nombre} ejecutado vía contingencia.")
                return [f"[{nombre.upper()} - Iter.{iteracion}]\n{resultado}"]
            except Exception as e:
                print(f"[!] Error ejecutando {nombre}: {e}")
                return [f"[ERROR {nombre.upper()} - Iter.{iteracion}]\n{e}"]

    return []  # No se encontró ninguna tool call ejecutable


# ==========================================
# 4. NODOS DEL GRAFO
# ==========================================

def nodo_reconocimiento(state: AgentState) -> dict:
    """Fase 1: Reconocimiento inicial obligatorio con nmap y whatweb."""
    print(f"\n{'='*50}")
    print(f"[FASE 1] RECONOCIMIENTO -> {state['objetivo']}")
    print(f"{'='*50}")

    objetivo = state["objetivo"]
    host = objetivo.replace("http://", "").replace("https://", "").split("/")[0]
    hallazgos_reconocimiento = []

    print("[*] Ejecutando Nmap...")
    resultado_nmap = MAPA_HERRAMIENTAS["herramienta_nmap"].invoke({"objetivo": host})
    hallazgos_reconocimiento.append(f"[NMAP - {host}]\n{resultado_nmap}")

    print("[*] Ejecutando WhatWeb...")
    resultado_whatweb = MAPA_HERRAMIENTAS["herramienta_whatweb"].invoke({"objetivo": objetivo})
    hallazgos_reconocimiento.append(f"[WHATWEB - {objetivo}]\n{resultado_whatweb}")

    print(f"[✓] Reconocimiento completado.")
    return {"hallazgos": hallazgos_reconocimiento, "iteracion": 0}


def nodo_agente_decisor(state: AgentState) -> dict:
    """Fase 2: El LLM analiza hallazgos y decide la siguiente acción autónomamente."""
    iteracion = state["iteracion"] + 1
    print(f"\n{'='*50}")
    print(f"[FASE 2] DECISIÓN AUTÓNOMA — Iteración {iteracion}/{state['max_iteraciones']}")
    print(f"{'='*50}")

    # Limitamos el contexto: solo los últimos 3 hallazgos para no saturar el modelo
    hallazgos_recientes = state["hallazgos"][-3:] if len(state["hallazgos"]) > 3 else state["hallazgos"]
    hallazgos_texto = "\n\n".join(hallazgos_recientes) if hallazgos_recientes else "Sin hallazgos aún."

    # Truncamos si sigue siendo demasiado largo
    if len(hallazgos_texto) > 4000:
        hallazgos_texto = hallazgos_texto[:4000] + "\n...[truncado para caber en contexto]"

    prompt_usuario = PROMPT_ANALISIS.format(
        objetivo=state["objetivo"],
        iteracion=iteracion,
        hallazgos=hallazgos_texto
    )

    mensajes = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=prompt_usuario)
    ]

    print("[*] Consultando al LLM...")
    respuesta = llm_con_herramientas.invoke(mensajes)

    nuevos_hallazgos = []
    auditoria_completa = False

    # VÍA 1: Tool Calling nativo de LangChain (lo que queremos idealmente)
    if hasattr(respuesta, 'tool_calls') and respuesta.tool_calls:
        for tool_call in respuesta.tool_calls:
            nombre_tool = tool_call["name"]
            args = tool_call["args"]
            print(f"\n[IA→TOOL NATIVO] {nombre_tool} | args: {args}")
            if nombre_tool in MAPA_HERRAMIENTAS:
                resultado = MAPA_HERRAMIENTAS[nombre_tool].invoke(args)
                nuevos_hallazgos.append(f"[{nombre_tool.upper()} - Iter.{iteracion}]\n{resultado}")
                print(f"[✓] {nombre_tool} ejecutado vía tool calling nativo.")

    # VÍA 2: El LLM devuelve texto — puede ser JSON de tool call o razonamiento puro
    else:
        texto = respuesta.content if hasattr(respuesta, 'content') else str(respuesta)
        print(f"\n[IA RESPONDE (primeros 300 chars)]\n{texto[:300]}")

        # Intento de parsear y ejecutar si el texto contiene un JSON de tool call
        hallazgos_tool = _intentar_ejecutar_desde_texto(texto, iteracion)

        if hallazgos_tool:
            nuevos_hallazgos.extend(hallazgos_tool)
        elif "AUDITORIA_COMPLETA" in texto:
            print("\n[✓] Auditoría marcada como completa por el agente.")
            auditoria_completa = True
        else:
            # Razonamiento puro — lo guardamos y continuamos (no paramos)
            print("[*] El LLM razonó sin usar herramientas. Guardando y continuando.")
            nuevos_hallazgos.append(f"[RAZONAMIENTO IA - Iter.{iteracion}]\n{texto[:500]}")

    return {
        "hallazgos": nuevos_hallazgos,
        "iteracion": iteracion,
        "auditoria_completa": auditoria_completa,
        "mensajes": [respuesta],
    }


def nodo_generador_reporte(state: AgentState) -> dict:
    """Fase final: Genera el reporte técnico en markdown."""
    print(f"\n{'='*50}")
    print("[FASE FINAL] GENERANDO REPORTE")
    print(f"{'='*50}")

    # Resumen muy compacto de hallazgos para no saturar el contexto del LLM de 7B
    resumen_hallazgos = []
    for h in state["hallazgos"]:
        # Solo las primeras 600 chars de cada hallazgo
        resumen_hallazgos.append(h[:600] + ("..." if len(h) > 600 else ""))

    hallazgos_texto = "\n\n---\n\n".join(resumen_hallazgos)

    # Tope total: 5000 chars para dejar margen al LLM
    if len(hallazgos_texto) > 5000:
        hallazgos_texto = hallazgos_texto[:5000] + "\n\n...[hallazgos adicionales truncados]"

    prompt_reporte = PROMPT_REPORTE.format(
        objetivo=state["objetivo"],
        hallazgos=hallazgos_texto
    )

    try:
        respuesta = llm.invoke([
            SystemMessage(content="Eres un experto en ciberseguridad. Genera un reporte técnico conciso en markdown. Máximo 500 palabras."),
            HumanMessage(content=prompt_reporte)
        ])
        reporte = respuesta.content if hasattr(respuesta, 'content') else str(respuesta)
    except Exception as e:
        # Si falla la generación LLM, construimos un reporte básico estructurado con los hallazgos
        print(f"[!] Error al generar reporte con LLM: {e}")
        print("[*] Generando reporte de emergencia...")
        reporte = f"# Reporte Red-AI — {state['objetivo']}\n\n"
        reporte += f"**Auditoría completada en {state['iteracion']} iteraciones.**\n\n"
        reporte += "## Hallazgos recopilados\n\n"
        for h in state["hallazgos"]:
            lineas = h.split("\n")
            titulo = lineas[0] if lineas else "Hallazgo"
            reporte += f"### {titulo}\n```\n{h[:500]}\n```\n\n"

    print("[✓] Reporte generado.")
    return {"reporte_final": reporte}


# ==========================================
# 5. ROUTING CONDICIONAL
# ==========================================

def decidir_siguiente_paso(state: AgentState) -> str:
    if state.get("auditoria_completa", False):
        return "generar_reporte"
    if state["iteracion"] >= state["max_iteraciones"]:
        print(f"\n[!] Límite de {state['max_iteraciones']} iteraciones alcanzado.")
        return "generar_reporte"
    return "agente_decisor"


# ==========================================
# 6. CONSTRUCCIÓN DEL GRAFO
# ==========================================

def construir_grafo():
    workflow = StateGraph(AgentState)
    workflow.add_node("reconocimiento", nodo_reconocimiento)
    workflow.add_node("agente_decisor", nodo_agente_decisor)
    workflow.add_node("generar_reporte", nodo_generador_reporte)

    workflow.set_entry_point("reconocimiento")
    workflow.add_edge("reconocimiento", "agente_decisor")
    workflow.add_conditional_edges(
        "agente_decisor",
        decidir_siguiente_paso,
        {
            "agente_decisor": "agente_decisor",
            "generar_reporte": "generar_reporte"
        }
    )
    workflow.add_edge("generar_reporte", END)
    return workflow.compile()


agente_app = construir_grafo()


# ==========================================
# EJECUCIÓN DIRECTA
# ==========================================
if __name__ == "__main__":
    estado_inicial: AgentState = {
        "objetivo": "http://localhost:3000",
        "autorizacion": "TFG-UTAD-2026",
        "hallazgos": [],
        "mensajes": [],
        "iteracion": 0,
        "max_iteraciones": 5,
        "auditoria_completa": False,
        "reporte_final": "",
    }

    print("=" * 60)
    print("   RED-AI — Agente Autónomo de Pentesting Web")
    print(f"   Objetivo: {estado_inicial['objetivo']}")
    print("=" * 60)

    estado_final = None
    for output in agente_app.stream(estado_inicial):
        for nodo, estado in output.items():
            print(f"\n[Sistema] ✓ Nodo: {nodo.upper()}")
        estado_final = output

    if estado_final:
        ultimo = list(estado_final.values())[-1]
        reporte = ultimo.get("reporte_final", "")
        if reporte:
            print("\n" + "=" * 60)
            print(reporte)
