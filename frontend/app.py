"""
Interfaz gráfica de Red-AI — Streamlit
Panel de control con streaming en tiempo real del agente.
"""

import streamlit as st
import sys
import os
import queue
import threading
import time
from io import StringIO

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.agente_dast import AgentState, construir_grafo
from core.agente_dast import MODELO, OLLAMA_URL

st.set_page_config(
    page_title="Red-AI | Autonomous Pentesting",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .stApp { background-color: #0d1117; color: #c9d1d9; }
    .stTextInput > div > div > input {
        background-color: #161b22; color: #58a6ff;
        border: 1px solid #30363d; font-family: 'Courier New', monospace;
    }
    .stButton > button {
        background-color: #238636; color: white;
        border: none; font-weight: bold; width: 100%;
    }
    .stButton > button:hover { background-color: #2ea043; }
    .terminal-box {
        background-color: #0d1117; border: 1px solid #30363d;
        border-radius: 6px; padding: 16px;
        font-family: 'Courier New', monospace; font-size: 12px;
        color: #58a6ff; white-space: pre-wrap;
        height: 520px; overflow-y: auto;
    }
    .hallazgo-card {
        background-color: #161b22; border-left: 3px solid #f85149;
        padding: 10px 14px; margin: 8px 0;
        border-radius: 0 4px 4px 0;
        font-family: 'Courier New', monospace; font-size: 12px;
    }
    .tool-badge {
        display: inline-block; background-color: #1f6feb;
        color: white; border-radius: 4px; padding: 2px 8px;
        font-size: 11px; font-family: monospace; margin: 2px;
    }
    .tool-badge-done {
        display: inline-block; background-color: #238636;
        color: white; border-radius: 4px; padding: 2px 8px;
        font-size: 11px; font-family: monospace; margin: 2px;
    }
    .iter-header {
        color: #f0883e; font-family: monospace;
        font-size: 13px; font-weight: bold;
    }
    h1, h2, h3 { color: #58a6ff !important; }
    .stAlert { background-color: #161b22; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# SIDEBAR
# ==========================================
with st.sidebar:
    st.markdown("## 🎯 Red-AI")
    st.markdown("*Agente autónomo de pentesting web*")
    st.markdown("---")
    st.markdown("### Configuración de Misión")

    objetivo = st.text_input("URL / IP Objetivo", value="http://localhost:3000")
    autorizacion = st.text_input("Referencia de Autorización", value="TFG-UTAD-2026")
    max_iter = st.slider("Máximo de iteraciones", min_value=2, max_value=10, value=5)

    st.markdown("---")
    st.markdown(f"**Modelo:** `{MODELO}`")
    st.markdown(f"**Ollama:** `{OLLAMA_URL}`")
    st.markdown("---")
    st.markdown("### Herramientas habilitadas")
    col1, col2 = st.columns(2)
    with col1:
        st.checkbox("Nmap", value=True)
        st.checkbox("WhatWeb", value=True)
        st.checkbox("Gobuster", value=True)
    with col2:
        st.checkbox("Nikto", value=True)
        st.checkbox("Curl", value=True)
        st.checkbox("SQLmap", value=False)

    st.markdown("---")
    iniciar = st.button("🚀 INICIAR AUDITORÍA", type="primary")
    st.markdown("<small style='color:#8b949e'>Red-AI v0.3 — TFG U-TAD 2026<br>Solo para entornos autorizados</small>", unsafe_allow_html=True)

# ==========================================
# ÁREA PRINCIPAL
# ==========================================
st.markdown("# 🎯 Red-AI — Autonomous Pentesting Agent")

if not iniciar:
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("<div style='background:#161b22;padding:20px;border-radius:8px;border:1px solid #30363d'><h3>🔍 Reconocimiento</h3><p style='color:#8b949e;font-size:13px'>Nmap + WhatWeb automáticos al inicio</p></div>", unsafe_allow_html=True)
    with col2:
        st.markdown("<div style='background:#161b22;padding:20px;border-radius:8px;border:1px solid #30363d'><h3>🤖 Decisión Autónoma</h3><p style='color:#8b949e;font-size:13px'>El LLM decide qué herramienta usar en cada iteración</p></div>", unsafe_allow_html=True)
    with col3:
        st.markdown("<div style='background:#161b22;padding:20px;border-radius:8px;border:1px solid #30363d'><h3>📄 Reporte Final</h3><p style='color:#8b949e;font-size:13px'>Reporte técnico en markdown descargable</p></div>", unsafe_allow_html=True)
    st.info("⬅️ Configura el objetivo y pulsa INICIAR AUDITORÍA")

else:
    st.markdown(f"### 🔴 Auditoría en curso — `{objetivo}`")

    # Layout principal: consola | hallazgos
    col_consola, col_hallazgos = st.columns([3, 2])

    with col_consola:
        st.markdown("#### 📡 Consola del Agente")
        consola_placeholder = st.empty()

    with col_hallazgos:
        st.markdown("#### 🔎 Hallazgos & Herramientas")
        tools_placeholder = st.empty()
        hallazgos_placeholder = st.empty()

    reporte_placeholder = st.empty()

    # Cola de eventos para comunicar el hilo del agente con Streamlit
    event_queue = queue.Queue()

    # Redirigimos stdout para capturar los prints del agente en tiempo real
    class QueueWriter:
        def __init__(self, q):
            self.q = q
        def write(self, msg):
            if msg.strip():
                self.q.put(("log", msg.rstrip()))
        def flush(self):
            pass

    def ejecutar_agente(q):
        """Hilo secundario: corre el agente y emite eventos a la cola."""
        old_stdout = sys.stdout
        sys.stdout = QueueWriter(q)
        try:
            estado_inicial: AgentState = {
                "objetivo": objetivo,
                "autorizacion": autorizacion,
                "hallazgos": [],
                "mensajes": [],
                "iteracion": 0,
                "max_iteraciones": max_iter,
                "auditoria_completa": False,
                "reporte_final": "",
                "herramientas_usadas": [],
            }

            agente = construir_grafo()
            for output in agente.stream(estado_inicial):
                for nodo_nombre, estado_nodo in output.items():
                    q.put(("nodo", nodo_nombre))

                    nuevos = estado_nodo.get("hallazgos", [])
                    for h in nuevos:
                        q.put(("hallazgo", h))

                    tools = estado_nodo.get("herramientas_usadas", [])
                    if tools:
                        q.put(("tools", tools))

                    reporte = estado_nodo.get("reporte_final", "")
                    if reporte:
                        q.put(("reporte", reporte))

        except Exception as e:
            q.put(("error", str(e)))
        finally:
            sys.stdout = old_stdout
            q.put(("fin", None))

    # Lanzamos el agente en hilo separado
    hilo = threading.Thread(target=ejecutar_agente, args=(event_queue,), daemon=True)
    hilo.start()

    # Estado local del frontend
    lineas_consola = [f"[+] Misión iniciada: {objetivo}", f"[+] Modelo: {MODELO}", ""]
    hallazgos_acumulados = []
    herramientas_usadas = []
    reporte_final = ""
    terminado = False

    # Loop de actualización — polling de la cola de eventos
    while not terminado:
        # Vaciamos la cola en cada tick
        eventos_este_tick = []
        try:
            while True:
                eventos_este_tick.append(event_queue.get_nowait())
        except queue.Empty:
            pass

        for tipo, dato in eventos_este_tick:
            if tipo == "log":
                lineas_consola.append(dato)
            elif tipo == "nodo":
                lineas_consola.append(f"\n✓ [{dato.upper()}] completado\n")
            elif tipo == "hallazgo":
                hallazgos_acumulados.append(dato)
                titulo = dato.split("\n")[0]
                lineas_consola.append(f"  → {titulo}")
            elif tipo == "tools":
                herramientas_usadas = dato
            elif tipo == "reporte":
                reporte_final = dato
                lineas_consola.append("\n✓ [REPORTE] generado")
            elif tipo == "error":
                lineas_consola.append(f"\n❌ ERROR: {dato}")
                terminado = True
            elif tipo == "fin":
                terminado = True

        # Limitamos la consola a las últimas 120 líneas para no saturar el DOM
        lineas_mostrar = lineas_consola[-120:]
        texto_consola = "\n".join(lineas_mostrar)

        # Actualizamos consola
        consola_placeholder.markdown(
            f'<div class="terminal-box">{texto_consola}</div>',
            unsafe_allow_html=True
        )

        # Actualizamos herramientas usadas
        if herramientas_usadas:
            badges = "".join([
                f'<span class="tool-badge-done">✓ {t.replace("herramienta_","")}</span>'
                for t in herramientas_usadas
            ])
            tools_placeholder.markdown(
                f'<div style="margin-bottom:8px">{badges}</div>',
                unsafe_allow_html=True
            )

        # Actualizamos hallazgos
        if hallazgos_acumulados:
            html_hallazgos = ""
            for h in hallazgos_acumulados[-8:]:  # últimos 8
                titulo = h.split("\n")[0]
                preview = h.split("\n")[1][:80] if len(h.split("\n")) > 1 else ""
                html_hallazgos += f'<div class="hallazgo-card">► <b>{titulo}</b><br><small style="color:#8b949e">{preview}</small></div>'
            hallazgos_placeholder.markdown(html_hallazgos, unsafe_allow_html=True)

        time.sleep(0.3)  # tick cada 300ms

    # Resultado final
    if reporte_final:
        reporte_placeholder.markdown("---")
        reporte_placeholder.markdown("## 📄 Reporte Final de Auditoría")
        reporte_placeholder.markdown(reporte_final)
        st.download_button(
            label="⬇️ Descargar Reporte (.md)",
            data=reporte_final,
            file_name=f"reporte_{objetivo.replace('http://','').replace('/','_').replace(':','-')}.md",
            mime="text/markdown"
        )
        st.success("✅ Auditoría autónoma finalizada.")
    else:
        st.warning("⚠️ La auditoría terminó sin generar reporte.")
