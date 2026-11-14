"""
Red-AI — Dashboard Streamlit
Streaming en tiempo real vía threading + queue
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import threading
import queue
import time
import sys
import io
import re
import requests

from core.agente_dast import ejecutar_auditoria, OLLAMA_URL, MODELO_DEFAULT

# ─── Configuración de página ──────────────────────────────────────────────────
st.set_page_config(
    page_title="Red-AI | Pentesting Autónomo",
    page_icon="🔴",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Estilos CSS ──────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .main-header { font-size: 2.2rem; font-weight: 800; color: #ff4b4b; margin-bottom: 0; }
    .sub-header  { color: #888; font-size: 0.95rem; margin-top: -10px; margin-bottom: 20px; }
    .node-badge  { display:inline-block; background:#1e3a5f; color:#7ec8e3;
                   padding:3px 10px; border-radius:12px; font-size:0.82rem;
                   margin:2px; font-family:monospace; }
    .tool-badge  { display:inline-block; background:#1a3a1a; color:#7ec87e;
                   padding:3px 10px; border-radius:12px; font-size:0.82rem;
                   margin:2px; font-family:monospace; }
    .hallazgo-card { background:#1a1a2e; border-left:3px solid #ff4b4b;
                     padding:10px 14px; border-radius:6px; margin:6px 0;
                     font-family:monospace; font-size:0.83rem; }
    .pensamiento-card { background:#2a2a1a; border-left:3px solid #ffa500;
                        padding:10px 14px; border-radius:6px; margin:6px 0;
                        font-size:0.88rem; color:#ffd580; }
    .log-line    { font-family:monospace; font-size:0.82rem; color:#aaa;
                   padding:1px 0; }
    .reporte-box { background:#0d1117; border:1px solid #30363d;
                   border-radius:8px; padding:20px; }
    .status-running { color:#ffa500; font-weight:600; }
    .status-done    { color:#4caf50; font-weight:600; }
    .status-error   { color:#f44336; font-weight:600; }
</style>
""", unsafe_allow_html=True)


# ─── Obtener modelos desde Ollama ─────────────────────────────────────────────

def obtener_modelos_ollama() -> list[str]:
    """Consulta la API de Ollama y devuelve lista de modelos disponibles."""
    try:
        resp = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            modelos = [m["name"] for m in data.get("models", [])]
            if modelos:
                return modelos
    except Exception:
        pass
    # Fallback si no hay conexión
    return [MODELO_DEFAULT, "qwen2.5-coder:32b", "qwen2.5-coder:7b"]


# ─── QueueWriter (redirige stdout al queue) ───────────────────────────────────

_ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;]*m|\[[0-9]+m")

class QueueWriter(io.TextIOBase):
    def __init__(self, q: queue.Queue):
        self.q = q

    def write(self, text: str) -> int:
        if text and text.strip():
            clean = _ANSI_ESCAPE.sub("", text)
            # Solo va a "pensamiento" lo que el agente marque explícitamente como razonamiento
            if "💭 RAZONAMIENTO" in clean or "RAZONAMIENTO" in clean:
                self.q.put(("pensamiento_raw", clean))
            else:
                self.q.put(("log", clean))
        return len(text)

    def flush(self):
        pass


# ─── Hilo de ejecución ────────────────────────────────────────────────────────

def ejecutar_agente(objetivo: str, modelo: str, event_queue: queue.Queue):
    old_stdout = sys.stdout
    writer = QueueWriter(event_queue)
    sys.stdout = writer

    try:
        resultado = ejecutar_auditoria(objetivo=objetivo, modelo=modelo)

        # Emitir hallazgos
        for h in resultado.get("hallazgos", []):
            event_queue.put(("hallazgo", h))

        # Emitir herramientas usadas
        event_queue.put(("tools", resultado.get("herramientas_usadas", [])))

        # Emitir reporte
        reporte = resultado.get("reporte", "Sin reporte generado.")
        event_queue.put(("reporte", reporte))

    except Exception as e:
        import traceback
        event_queue.put(("error", f"{e}\n{traceback.format_exc()}"))
    finally:
        sys.stdout = old_stdout
        event_queue.put(("fin", None))


# ─── Inicialización de session_state ─────────────────────────────────────────

defaults = {
    "corriendo": False,
    "logs": [],
        "pensamientos": [],
    "hallazgos": [],
    "tools_usadas": [],
    "reporte": None,
    "error": None,
    "event_queue": None,
    "thread": None,
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v


# ─── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🔴 Red-AI")
    st.markdown("*Agente autónomo de pentesting web*")
    st.divider()

    # Selector de proveedor
    st.markdown("### 🤖 Modelo")
    proveedor = st.radio(
        "Proveedor",
        options=["Ollama (local)", "Claude (API)"],
        horizontal=True,
        disabled=st.session_state.corriendo,
    )

    if proveedor == "Claude (API)":
        # API key: primero variable de entorno, si no input manual
        api_key_env = os.environ.get("ANTHROPIC_API_KEY", "")
        if api_key_env:
            st.success("✅ ANTHROPIC_API_KEY detectada en entorno")
            api_key_input = api_key_env
        else:
            api_key_input = st.text_input(
                "Anthropic API Key",
                type="password",
                placeholder="sk-ant-...",
                help="Obtén tu API key en platform.anthropic.com",
                disabled=st.session_state.corriendo,
            )

        CLAUDE_MODELOS = [
            "claude-sonnet-4-5",
            "claude-haiku-4-5",
            "claude-opus-4-5",
            "claude-sonnet-4-6",
        ]
        modelo_elegido = st.selectbox(
            "Modelo Claude",
            options=CLAUDE_MODELOS,
            index=0,
            help="claude-sonnet-4-5 es el mejor balance calidad/coste",
            disabled=st.session_state.corriendo,
        )
        # Inyectar API key en entorno para que agente_dast la recoja
        if api_key_input:
            os.environ["ANTHROPIC_API_KEY"] = api_key_input

    else:
        api_key_input = ""
        modelos_disponibles = obtener_modelos_ollama()
        idx_default = 0
        for i, m in enumerate(modelos_disponibles):
            if "32b" in m:
                idx_default = i
                break
        modelo_elegido = st.selectbox(
            "Modelo Ollama",
            options=modelos_disponibles,
            index=idx_default,
            help="Modelos disponibles en tu instancia de Ollama",
            disabled=st.session_state.corriendo,
        )

    st.divider()
    st.markdown("### 🎯 Objetivo")
    objetivo = st.text_input(
        "URL o IP del objetivo",
        value="http://testasp.vulnweb.com",
        placeholder="http://ejemplo.com",
        disabled=st.session_state.corriendo,
    )

    st.caption("ℹ️ El agente se detiene automáticamente cuando agota todos los vectores (AUDITORIA_COMPLETA) o tras 50 iteraciones de seguridad.")

    st.divider()

    # Validación antes de lanzar
    _claude_listo = (proveedor == "Ollama (local)") or bool(api_key_input)

    # Botón iniciar / detener
    if not st.session_state.corriendo:
        if proveedor == "Claude (API)" and not api_key_input:
            st.warning("⚠️ Introduce tu Anthropic API key para continuar.")
        if st.button("🚀 Iniciar Auditoría", use_container_width=True, type="primary",
                     disabled=not _claude_listo):
            if objetivo:
                # Reset estado
                st.session_state.logs = []
                st.session_state.pensamientos = []
                st.session_state.hallazgos = []
                st.session_state.tools_usadas = []
                st.session_state.reporte = None
                st.session_state.error = None

                # Crear queue y lanzar hilo
                q = queue.Queue()
                st.session_state.event_queue = q
                st.session_state.corriendo = True

                t = threading.Thread(
                    target=ejecutar_agente,
                    args=(objetivo, modelo_elegido, q),
                    daemon=True,
                )
                t.start()
                st.session_state.thread = t
                st.rerun()
    else:
        st.button("⏳ Auditando...", use_container_width=True, disabled=True)

    st.divider()
    if proveedor == "Ollama (local)":
        st.markdown(f"**Ollama:** `{OLLAMA_URL}`")
    else:
        st.markdown("**Proveedor:** `Anthropic API`")
    st.markdown(f"**Modelo activo:** `{modelo_elegido}`")


# ─── Layout principal ─────────────────────────────────────────────────────────
st.markdown('<p class="main-header">🔴 Red-AI</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-header">Agente Autónomo de Pentesting Web — TFG U-TAD</p>', unsafe_allow_html=True)

# Consumir eventos de la queue
if st.session_state.corriendo and st.session_state.event_queue:
    q = st.session_state.event_queue
    nuevos_logs = []
    nuevos_pensamientos = []
    fin = False

    while not q.empty():
        try:
            evento, dato = q.get_nowait()
        except queue.Empty:
            break

        if evento == "log":
            nuevos_logs.append(dato)
        elif evento == "pensamiento_raw":
            nuevos_pensamientos.append(dato)
        elif evento == "hallazgo":
            st.session_state.hallazgos.append(dato)
        elif evento == "tools":
            st.session_state.tools_usadas = dato
        elif evento == "reporte":
            st.session_state.reporte = dato
        elif evento == "error":
            st.session_state.error = dato
        elif evento == "fin":
            fin = True

    st.session_state.logs.extend(nuevos_logs)
    st.session_state.pensamientos.extend(nuevos_pensamientos)

    if fin:
        st.session_state.corriendo = False


# ─── Tabs de contenido ────────────────────────────────────────────────────────
tab_consola, tab_razonamiento, tab_hallazgos, tab_reporte = st.tabs([
    "📟 Consola", "💭 Razonamiento IA", "🔍 Hallazgos", "📋 Reporte"
])

# — Consola —
with tab_consola:
    if st.session_state.corriendo:
        st.markdown('<span class="status-running">● Auditoría en curso...</span>', unsafe_allow_html=True)
    elif st.session_state.reporte:
        st.markdown('<span class="status-done">✔ Auditoría completada</span>', unsafe_allow_html=True)
    elif st.session_state.error:
        st.markdown('<span class="status-error">✖ Error durante la auditoría</span>', unsafe_allow_html=True)

    # Herramientas usadas
    if st.session_state.tools_usadas:
        st.markdown("**Herramientas ejecutadas:**")
        badges = " ".join(
            f'<span class="tool-badge">✓ {t.replace("herramienta_","")}</span>'
            for t in st.session_state.tools_usadas
        )
        st.markdown(badges, unsafe_allow_html=True)
        st.markdown("")

    # Logs
    if st.session_state.logs:
        log_html = "\n".join(
            f'<div class="log-line">{line}</div>'
            for line in st.session_state.logs[-200:]
        )
        st.markdown(f'<div style="max-height:500px;overflow-y:auto;background:#0d1117;padding:12px;border-radius:6px;border:1px solid #30363d">{log_html}</div>', unsafe_allow_html=True)
    elif st.session_state.corriendo:
        st.info("Esperando salida del agente...")

    if st.session_state.error:
        st.error(f"**Error:**\n```\n{st.session_state.error}\n```")

# — Razonamiento IA —
with tab_razonamiento:
    st.markdown("### 💭 Lo que piensa el modelo")
    st.caption("Texto de razonamiento emitido por el LLM antes de cada tool call")

    if st.session_state.pensamientos:
        for i, p in enumerate(st.session_state.pensamientos):
            if p.strip():
                st.markdown(
                    f'<div class="pensamiento-card">🧠 <b>Paso {i+1}</b><br>{p}</div>',
                    unsafe_allow_html=True,
                )
    elif st.session_state.corriendo:
        st.info("El modelo aún no ha emitido razonamiento...")
    else:
        st.info("Inicia una auditoría para ver el razonamiento del modelo aquí.")

# — Hallazgos —
with tab_hallazgos:
    st.markdown(f"### 🔍 Hallazgos ({len(st.session_state.hallazgos)})")

    if st.session_state.hallazgos:
        for h in st.session_state.hallazgos:
            lineas = h.split("\n")
            titulo = lineas[0] if lineas else "Hallazgo"
            preview = "\n".join(lineas[1:6]) if len(lineas) > 1 else ""
            with st.expander(titulo, expanded=False):
                st.code(h, language="text")
    else:
        st.info("Los hallazgos aparecerán aquí durante la auditoría.")

# — Reporte —
with tab_reporte:
    if st.session_state.reporte:
        st.markdown("### 📋 Reporte Final")
        st.markdown(
            f'<div class="reporte-box">{st.session_state.reporte}</div>',
            unsafe_allow_html=True,
        )
        st.download_button(
            "⬇️ Descargar Reporte (.md)",
            data=st.session_state.reporte,
            file_name="reporte_redai.md",
            mime="text/markdown",
        )
    else:
        st.info("El reporte aparecerá aquí al finalizar la auditoría.")

# ─── Auto-refresh durante ejecución ──────────────────────────────────────────
if st.session_state.corriendo:
    time.sleep(0.3)
    st.rerun()
