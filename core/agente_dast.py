from typing import TypedDict, List, Dict
import requests
from bs4 import BeautifulSoup
from langchain_ollama import OllamaLLM
from langgraph.graph import StateGraph, END 

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
# 1.5 CONEXIÓN AL LLM LOCAL (El "Cerebro")
# ==========================================
# Asegúrate de que el nombre del modelo coincida exactamente con el que tienes en Ollama
llm = OllamaLLM(model="qwen2.5-coder:7b", temperature=0.1)
# Temperature 0.1 hace que la IA sea analítica y determinista, no creativa.

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
# 3. NODO ANALIZADOR (Fase 2: Razonamiento IA)
# ==========================================
def nodo_analizador(state: AgentState) -> AgentState:
    print("\n[+] Fase 2: IA Analizando Superficie de Ataque...")
    endpoints = state.get("endpoints_descubiertos", [])
    
    if not endpoints:
        print("[-] No hay endpoints para analizar.")
        return {"parametros_encontrados": []}

    # Aquí construimos el Prompt que le pasamos al LLM
    prompt = f"""
    Actúa como el motor de análisis de una herramienta DAST.
    Tu objetivo es analizar la siguiente lista de rutas (endpoints) extraídas de una aplicación web:
    {endpoints}
    
    Identifica cuáles de estos endpoints son susceptibles de recibir entrada del usuario (por ejemplo, rutas de login, búsqueda, perfiles, o aquellas con parámetros como '?id=').
    Devuelve estrictamente un análisis técnico breve de los vectores de entrada más críticos.
    """
    
    print("[*] Consultando al modelo en Ollama...")
    try:
        respuesta_ia = llm.invoke(prompt)
        print("\n--- RAZONAMIENTO DE LA IA ---")
        print(respuesta_ia)
        print("-----------------------------\n")
    except Exception as e:
        print(f"[-] Error de conexión con Ollama: {e}")
        print("    (¿Está el servidor de Ollama corriendo?)")

    # Por ahora simulamos la extracción estructurada hasta que apliquemos parseo JSON
    parametros_simulados = [{"endpoint": "/login", "param": "username"}]
    
    return {"parametros_encontrados": parametros_simulados, "intentos_actuales": 0}

# (Mantén todos los imports, el AgentState, la conexión a OllamaLLM y las funciones nodo_crawler y nodo_analizador que ya tienes)

from langgraph.graph import StateGraph, END # AÑADE ESTE IMPORT ARRIBA DEL TODO

# ... (Aquí va tu código anterior de los nodos) ...

# ==========================================
# 4. ORQUESTACIÓN (El Flujo Autónomo)
# ==========================================
# Creamos el grafo pasándole nuestra estructura de memoria
workflow = StateGraph(AgentState)

# Añadimos los "órganos" de nuestro agente al grafo
workflow.add_node("crawler", nodo_crawler)
workflow.add_node("analizador", nodo_analizador)

# Definimos cómo fluye la información de forma autónoma
workflow.set_entry_point("crawler")
workflow.add_edge("crawler", "analizador")
workflow.add_edge("analizador", END) # Por ahora termina aquí, luego añadiremos el validador/explotador

# Compilamos el agente en una aplicación ejecutable
agente_app = workflow.compile()

# ==========================================
# EJECUCIÓN DEL AGENTE COMPLETO
# ==========================================
if __name__ == "__main__":
    # Estado inicial real
    estado_inicial: AgentState = {
        "url_objetivo": "http://example.com", # Usamos example.com para esta prueba de flujo
        "endpoints_descubiertos": [],
        "parametros_encontrados": [],
        "vulnerabilidades_confirmadas": [],
        "intentos_actuales": 0
    }
    
    print("=== INICIANDO AGENTE DAST AUTÓNOMO ===")
    
    # app.stream ejecuta los nodos en orden automáticamente, pasándose el estado de uno a otro
    for output in agente_app.stream(estado_inicial):
        # LangGraph devuelve el estado modificado después de cada nodo
        # Podemos imprimir en qué nodo estamos para depurar
        for key, value in output.items():
            print(f"\n[Sistema] Nodo completado: {key}")
            
    print("\n=== FLUJO AUTÓNOMO FINALIZADO ===")
