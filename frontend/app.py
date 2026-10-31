import streamlit as st
import sys
import os

# Añadimos la raíz del proyecto al path para poder importar nuestro motor 'core'
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from core.agente_dast import agente_app, AgentState

# ==========================================
# CONFIGURACIÓN DE LA PÁGINA
# ==========================================
st.set_page_config(
    page_title="Red-AI | Agente DAST",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==========================================
# PANEL LATERAL (Sidebar)
# ==========================================
with st.sidebar:
    st.image("https://upload.wikimedia.org/wikipedia/commons/thumb/c/c3/Python-logo-notext.svg/1200px-Python-logo-notext.svg.png", width=50)
    st.title("Red-AI Config")
    st.markdown("---")
    
    st.subheader("Objetivo")
    target_url = st.text_input("Target URL", value="http://example.com")
    
    st.subheader("Motor LLM")
    modelo_seleccionado = st.selectbox("Seleccionar Cerebro", ["Qwen 2.5 Coder (7B) local"])
    
    st.markdown("---")
    # Botón principal para iniciar la acción
    iniciar = st.button("🚀 Iniciar Auditoría Autónoma", type="primary", use_container_width=True)

# ==========================================
# ÁREA PRINCIPAL (Dashboard)
# ==========================================
st.title("🎯 Red-AI: Autonomous Web Pentesting")
st.markdown("Interfaz de orquestación agéntica para Trabajo de Fin de Grado.")

# Contenedores vacíos que iremos llenando dinámicamente
consola_placeholder = st.empty()

if iniciar:
    st.markdown("### 📡 Monólogo Interno del Agente")
    # Creamos un área de texto con estilo de terminal negra
    caja_terminal = st.empty()
    texto_consola = f"[+] Inicializando agente contra objetivo: {target_url}\n"
    caja_terminal.code(texto_consola, language="bash")
    
    # Preparamos el estado inicial de LangGraph
    estado_inicial: AgentState = {
        "url_objetivo": target_url,
        "endpoints_descubiertos": [],
        "parametros_encontrados": [],
        "vulnerabilidades_confirmadas": [],
        "intentos_actuales": 0
    }
    
    with st.spinner("Agente ejecutando flujo de estados..."):
        try:
            # Ejecutamos nuestro grafo de LangGraph en vivo
            for output in agente_app.stream(estado_inicial):
                for nodo, estado_modificado in output.items():
                    texto_consola += f"\n[Sistema] ➔ Nodo completado: {nodo.upper()}\n"
                    
                    # Mostrar resultados según el nodo
                    if nodo == "crawler":
                        enlaces = estado_modificado.get('endpoints_descubiertos', [])
                        texto_consola += f"    [*] Enlaces inyectados/descubiertos: {len(enlaces)}\n"
                    elif nodo == "analizador":
                        texto_consola += f"    [*] Análisis de IA completado. Vectores evaluados.\n"
                    
                    # Actualizamos la consola en vivo en la pantalla
                    caja_terminal.code(texto_consola, language="bash")
                    
            st.success("✅ Flujo autónomo finalizado con éxito.")
            
        except Exception as e:
            st.error(f"Error crítico en el motor: {e}")
