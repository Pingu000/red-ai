from typing import TypedDict, List, Dict
import requests
from bs4 import BeautifulSoup
from langchain_ollama import ChatOllama
from langgraph.graph import StateGraph, END
from core.herramientas import herramienta_nmap
import json

# ==========================================
# 1. EL ESTADO (La "Memoria" de la IA)
# ==========================================
class AgentState(TypedDict):
    url_objetivo: str
    endpoints_descubiertos: List[str]
    parametros_encontrados: List[Dict[str, str]]
    vulnerabilidades_confirmadas: List[str]
    intentos_actuales: int

# ==========================================
# 1.5 CONEXIÓN AL LLM LOCAL CON HERRAMIENTAS
# ==========================================
# Cambiamos a ChatOllama porque es la clase que soporta el emparejamiento de funciones (Tool Calling)
llm = ChatOllama(model="qwen2.5-coder:7b", temperature=0.1)

# Vinculamos las herramientas de Kali al cerebro de la IA para que sepa que puede usarlas
herramientas_disponibles = [herramienta_nmap]
llm_con_herramientas = llm.bind_tools(herramientas_disponibles)

# ==========================================
# 2. NODO CRAWLER (Fase 1: Descubrimiento)
# ==========================================
def nodo_crawler(state: AgentState) -> AgentState:
    print(f"\n[+] Fase 1: Iniciando Crawler en {state['url_objetivo']}")
    url = state["url_objetivo"]
    enlaces_encontrados = []
    
    try:
        respuesta = requests.get(url, timeout=10)
        respuesta.raise_for_status()
        soup = BeautifulSoup(respuesta.text, 'html.parser')
        
        for etiqueta_a in soup.find_all('a'):
            href = etiqueta_a.get('href')
            if href and href not in enlaces_encontrados:
                enlaces_encontrados.append(href)
                
        print(f"[*] Crawler finalizado: {len(enlaces_encontrados)} enlaces descubiertos.")
    except Exception as e:
        print(f"[-] Error en Crawler: {e}")
        
    # SIMULACIÓN PARA TESTEAR EL GRAFO: 
    # Forzamos que el crawler devuelva estos enlaces para que la IA tenga trabajo
    enlaces_simulados = ["/index.html", "/api/users?id=1", "/login.php"]
    print(f"[*] (Simulación) Inyectando {len(enlaces_simulados)} enlaces al estado...")
    
    return {"endpoints_descubiertos": enlaces_simulados}

# ==========================================
# 3. NODO ANALIZADOR (Fase 2: Razonamiento y Tool Calling)
# ==========================================
def nodo_analizador(state: AgentState) -> AgentState:
    print("\n[+] Fase 2: IA Analizando y decidiendo uso de herramientas...")
    url = state["url_objetivo"]
    endpoints = state.get("endpoints_descubiertos", [])
    
    if not endpoints:
        print("[-] No hay endpoints para analizar.")
        return {"parametros_encontrados": []}

    # Extraemos el dominio limpio para que las herramientas de red lo entiendan correctamente
    dominio = url.replace("http://", "").replace("https://", "").split("/")[0]
    
    prompt = f"""
    Eres un agente DAST autónomo. Se te ha asignado auditar el objetivo: {dominio}.
    Has descubierto los siguientes endpoints: {endpoints}
    
    Como primer paso estratégico, utiliza la herramienta 'herramienta_nmap' para descubrir qué puertos están abiertos en el dominio objetivo.
    """
    
    print("[*] Consultando al modelo en Ollama para orquestación...")
    try:
        # Invocamos al modelo que tiene la capacidad de usar herramientas
        respuesta_ia = llm_con_herramientas.invoke(prompt)
        
        # Verificamos si la IA ha decidido invocar una herramienta emitiendo un JSON de ejecución
        # 1. Intento nativo de LangChain (cuando el modelo usa la API interna correctamente)
        if hasattr(respuesta_ia, 'tool_calls') and respuesta_ia.tool_calls:
            for tool_call in respuesta_ia.tool_calls:
                if tool_call["name"] == "herramienta_nmap":
                    objetivo_decidido = tool_call["args"].get("objetivo", dominio)
                    print(f"[*] La IA ha decidido ejecutar Nmap sobre: {objetivo_decidido}")
                    
                    resultado_terminal = herramienta_nmap.invoke({"objetivo": objetivo_decidido})
                    print("\n--- RESULTADO DE LA TERMINAL (NMAP) ---")
                    print(resultado_terminal)
                    print("---------------------------------------\n")
                    
        # 2. Parseo de Contingencia (cuando el modelo devuelve el JSON como texto plano)
        else:
            texto_ia = respuesta_ia.content.strip()
            ejecutado = False
            
            try:
                # Si el texto parece un JSON, intentamos interpretarlo
                if texto_ia.startswith("{") and texto_ia.endswith("}"):
                    datos = json.loads(texto_ia)
                    if datos.get("name") == "herramienta_nmap":
                        objetivo_decidido = datos.get("arguments", {}).get("objetivo", dominio)
                        print(f"[*] (Contingencia) La IA ha decidido ejecutar Nmap sobre: {objetivo_decidido}")
                        
                        resultado_terminal = herramienta_nmap.invoke({"objetivo": objetivo_decidido})
                        print("\n--- RESULTADO DE LA TERMINAL (NMAP) ---")
                        print(resultado_terminal)
                        print("---------------------------------------\n")
                        ejecutado = True
            except json.JSONDecodeError:
                pass # No es un JSON válido, seguimos adelante
                
            # Si no se ejecutó por ninguna de las dos vías, mostramos el razonamiento
            if not ejecutado:
                print("[*] La IA analizó el contexto pero no creyó necesario usar herramientas en este paso.")
                print(f"Razonamiento: {texto_ia}")
            
    except Exception as e:
        print(f"[-] Error de conexión con Ollama o ejecución de herramienta: {e}")

    # Mantenemos los parámetros simulados por ahora para que el grafo de estado no se rompa
    parametros_simulados = [{"endpoint": "/login", "param": "username"}]
    
    return {"parametros_encontrados": parametros_simulados, "intentos_actuales": 0}

# ==========================================
# 4. ORQUESTACIÓN (El Flujo Autónomo)
# ==========================================
workflow = StateGraph(AgentState)

workflow.add_node("crawler", nodo_crawler)
workflow.add_node("analizador", nodo_analizador)

workflow.set_entry_point("crawler")
workflow.add_edge("crawler", "analizador")
workflow.add_edge("analizador", END) 

agente_app = workflow.compile()

# ==========================================
# EJECUCIÓN DEL AGENTE COMPLETO
# ==========================================
if __name__ == "__main__":
    estado_inicial: AgentState = {
        "url_objetivo": "http://example.com",
        "endpoints_descubiertos": [],
        "parametros_encontrados": [],
        "vulnerabilidades_confirmadas": [],
        "intentos_actuales": 0
    }
    
    print("=== INICIANDO AGENTE DAST AUTÓNOMO CON TOOL CALLING ===")
    
    for output in agente_app.stream(estado_inicial):
        for key, value in output.items():
            print(f"\n[Sistema] Nodo completado: {key}")
            
    print("\n=== FLUJO AUTÓNOMO FINALIZADO ===")
