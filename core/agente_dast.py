"""
Motor principal del agente Red-AI.
Grafo de estados LangGraph que orquesta el proceso autónomo de pentesting.
"""

from typing import TypedDict, List, Annotated
import operator
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
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
# 3. NODOS DEL GRAFO
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

    hallazgos_texto = "\n\n".join(state["hallazgos"]) if state["hallazgos"] else "Sin hallazgos aún."

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

    # Tool Calling nativo (LangChain)
    if hasattr(respuesta, 'tool_calls') and respuesta.tool_calls:
        for tool_call in respuesta.tool_calls:
            nombre_tool = tool_call["name"]
            args = tool_call["args"]
            print(f"\n[IA DECIDE] Ejecutar: {nombre_tool} con args: {args}")
            if nombre_tool in MAPA_HERRAMIENTAS:
                resultado = MAPA_HERRAMIENTAS[nombre_tool].invoke(args)
                nuevos_hallazgos.append(f"[{nombre_tool.upper()} - Iter.{iteracion}]\n{resultado}")
                print(f"[✓] {nombre_tool} completado.")

    # Respuesta en texto
    else:
        texto = respuesta.content if hasattr(respuesta, 'content') else str(respuesta)
        print(f"\n[IA RAZONA]\n{texto}")
        if "AUDITORIA_COMPLETA" in texto:
            print("\n[✓] Auditoría marcada como completa por el agente.")
            auditoria_completa = True
        else:
            nuevos_hallazgos.append(f"[RAZONAMIENTO IA - Iter.{iteracion}]\n{texto}")

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

    hallazgos_texto = "\n\n".join(state["hallazgos"])
    prompt_reporte = PROMPT_REPORTE.format(
        objetivo=state["objetivo"],
        hallazgos=hallazgos_texto
    )

    respuesta = llm.invoke([
        SystemMessage(content="Eres un experto en ciberseguridad redactando reportes técnicos profesionales."),
        HumanMessage(content=prompt_reporte)
    ])

    reporte = respuesta.content if hasattr(respuesta, 'content') else str(respuesta)
    print("[✓] Reporte generado.")
    return {"reporte_final": reporte}


# ==========================================
# 4. ROUTING CONDICIONAL
# ==========================================

def decidir_siguiente_paso(state: AgentState) -> str:
    if state.get("auditoria_completa", False):
        return "generar_reporte"
    if state["iteracion"] >= state["max_iteraciones"]:
        print(f"\n[!] Límite de iteraciones alcanzado. Generando reporte.")
        return "generar_reporte"
    return "agente_decisor"


# ==========================================
# 5. CONSTRUCCIÓN DEL GRAFO
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
