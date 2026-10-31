"""
Interfaz gráfica de Red-AI — Streamlit
Panel de control para lanzar y monitorizar auditorías autónomas.
"""

import streamlit as st
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.agente_dast import agente_app, AgentState

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
        background-color: #161b22;
        color: #58a6ff;
        border: 1px solid #30363d;
        font-family: 'Courier New', monospace;
    }
    .stButton > button {
        background-color: #238636;
        color: white;
        border: none;
        font-weight: bold;
        width: 100%;
    }
    .stButton > button:hover { background-color: #2ea043; }
    .terminal-box {
        background-color: #0d1117;
        border: 1px solid #30363d;
        border-radius: 6px;
        padding: 16px;
        font-family: 'Courier New', monospace;
        font-size: 13px;
        color: #58a6ff;
        white-space: pre-wrap;
        max-height: 500px;
        overflow-y: auto;
    }
    .hallazgo-card {
        background-color: #161b22;
        border-left: 3px solid #f85149;
        padding: 10px 14px;
        margin: 8px 0;
        border-radius: 0 4px 4px 0;
        font-family: 'Courier New', monospace;
        font-size: 12px;
    }
    h1, h2, h3 { color: #58a6ff !important; }
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
    modelo = st.selectbox("Modelo LLM", ["qwen2.5-coder:7b", "llama3.1:8b", "mistral:7b"])

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
    st.markdown("<small style='color:#8b949e'>Red-AI v0.2 — TFG U-TAD 2026<br>Solo para entornos autorizados</small>", unsafe_allow_html=True)

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
    st.markdown(f"*Autorización: `{autorizacion}` | Modelo: `{modelo}` | Máx. iteraciones: `{max_iter}`*")

    col_consola, col_hallazgos = st.columns([3, 2])
    with col_consola:
        st.markdown("#### 📡 Consola del Agente")
        consola_placeholder = st.empty()
    with col_hallazgos:
        st.markdown("#### 🔎 Hallazgos")
        hallazgos_placeholder = st.empty()

    reporte_placeholder = st.empty()

    estado_inicial: AgentState = {
        "objetivo": objetivo,
        "autorizacion": autorizacion,
        "hallazgos": [],
        "mensajes": [],
        "iteracion": 0,
        "max_iteraciones": max_iter,
        "auditoria_completa": False,
        "reporte_final": "",
    }

    texto_consola = f"[+] Misión iniciada\n[+] Objetivo: {objetivo}\n[+] Autorización: {autorizacion}\n\n"
    hallazgos_acumulados = []

    try:
        for output in agente_app.stream(estado_inicial):
            for nodo_nombre, estado_nodo in output.items():
                texto_consola += f"\n[✓] Nodo completado: {nodo_nombre.upper()}\n"

                nuevos = estado_nodo.get("hallazgos", [])
                if nuevos:
                    hallazgos_acumulados.extend(nuevos)
                    for h in nuevos:
                        titulo = h.split("\n")[0] if "\n" in h else h[:60]
                        texto_consola += f"    → {titulo}\n"

                reporte = estado_nodo.get("reporte_final", "")
                if reporte:
                    texto_consola += "\n[✓] REPORTE GENERADO\n"

                consola_placeholder.markdown(
                    f'<div class="terminal-box">{texto_consola}</div>',
                    unsafe_allow_html=True
                )

                if hallazgos_acumulados:
                    html_hallazgos = ""
                    for h in hallazgos_acumulados:
                        titulo = h.split("\n")[0]
                        html_hallazgos += f'<div class="hallazgo-card">► {titulo}</div>'
                    hallazgos_placeholder.markdown(html_hallazgos, unsafe_allow_html=True)

                if reporte:
                    reporte_placeholder.markdown("---")
                    reporte_placeholder.markdown("## 📄 Reporte Final")
                    reporte_placeholder.markdown(reporte)
                    st.download_button(
                        label="⬇️ Descargar Reporte (.md)",
                        data=reporte,
                        file_name=f"reporte_{objetivo.replace('http://','').replace('/','_')}.md",
                        mime="text/markdown"
                    )

        st.success("✅ Auditoría autónoma finalizada.")

    except Exception as e:
        st.error(f"❌ Error crítico en el motor: {e}")
        st.exception(e)
