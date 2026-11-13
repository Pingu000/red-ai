# Red-AI — Autonomous Web Pentesting Agent

> Agente autónomo de auditoría web ofensiva impulsado por IA local.
> Desarrollado como Trabajo de Fin de Grado en Ingeniería del Software (especialidad Ciberseguridad).

---

## ¿Qué es?

**Red-AI** es un agente DAST (Dynamic Application Security Testing) que combina LLMs locales con herramientas de pentesting reales para realizar auditorías web de forma autónoma. El agente razona sobre el objetivo, selecciona herramientas, analiza resultados y adapta su estrategia en cada iteración — sin intervención humana.

Está pensado para entornos de laboratorio y webs de prueba con permiso explícito. No usar contra sistemas sin autorización.

---

## Stack técnico

- **Orquestación:** [LangGraph](https://github.com/langchain-ai/langgraph)
- **LLM local:** [Ollama](https://ollama.com) (`qwen2.5-coder:14b` / `qwen2.5-coder:32b`)
- **Interfaz:** [Streamlit](https://streamlit.io)
- **OS de ejecución:** Kali Linux
- **Herramientas integradas:** `nmap`, `gobuster`, `sqlmap`, `nikto`, `curl`

---

## Flujo del agente

1. **Reconocimiento** — nmap para detectar puertos y servicios
2. **Enumeración** — gobuster para directorios y archivos (doble pasada: sin extensión + `.asp/.php/.html`)
3. **Exploración** — curl para analizar formularios y endpoints
4. **Explotación** — sqlmap y nikto sobre los vectores encontrados
5. **Reporte** — informe final generado automáticamente por el LLM

El agente mantiene un historial de hallazgos y URLs visitadas para evitar repetir acciones, y se detiene al emitir `AUDITORIA_COMPLETA` o tras 50 iteraciones.

---

## Estructura

```
red-ai/
├── core/
│   ├── agente_dast.py      # Grafo LangGraph principal
│   ├── herramientas.py     # Tools (nmap, gobuster, sqlmap, nikto, curl)
│   └── prompts.py          # System prompt y prompts de análisis
├── frontend/
│   └── app.py              # Dashboard Streamlit con streaming en tiempo real
├── run.py                  # CLI entry point
└── requirements.txt
```

---

## Instalación

```bash
git clone https://github.com/Pingu000/red-ai.git
cd red-ai
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

**Requisitos previos:**
- Kali Linux (o cualquier distro con las herramientas instaladas)
- [Ollama](https://ollama.com) corriendo con un modelo cargado
- `nmap`, `gobuster`, `sqlmap`, `nikto` instalados

---

## Configuración

Por defecto el agente busca Ollama en `http://localhost:11434`. Si lo tienes en otra máquina (p.ej. Windows host desde una VM), configúralo con:

```bash
export OLLAMA_HOST=http://192.168.56.1:11434
```

---

## Uso

**Dashboard (recomendado):**
```bash
source venv/bin/activate
streamlit run frontend/app.py
```

**CLI:**
```bash
python run.py --objetivo http://target.com --modelo qwen2.5-coder:14b
```

---

## Aviso legal

Esta herramienta está diseñada exclusivamente para entornos de laboratorio y auditorías con autorización explícita. El uso contra sistemas sin permiso es ilegal. El autor no se hace responsable del uso que se le dé.

---

## Licencia

MIT
