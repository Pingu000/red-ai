#!/usr/bin/env python3
"""
Test unitario del parser de contingencia — ejecutar sin Ollama.
Verifica que el parser detecta y extrae correctamente los JSON de tool calls
que el LLM devuelve como texto plano en lugar de tool calls nativos.
"""

import json
import re
import sys

# ---- Copiamos la lógica de _extraer_json_balanceado y _intentar_ejecutar_desde_texto ----
# (sin importar el módulo completo para no necesitar langchain/ollama)

MAPA_HERRAMIENTAS_TEST = {
    'herramienta_gobuster': lambda args: f"[mock] gobuster sobre {args.get('objetivo')}",
    'herramienta_nikto':    lambda args: f"[mock] nikto sobre {args.get('objetivo')}",
    'herramienta_nmap':     lambda args: f"[mock] nmap sobre {args.get('objetivo')}",
    'herramienta_curl':     lambda args: f"[mock] curl sobre {args.get('url')}",
}

def _extraer_json_balanceado(texto: str) -> list:
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

def _intentar_ejecutar_desde_texto(texto: str, iteracion: int = 1) -> list:
    texto_limpio = re.sub(r'```(?:json)?\s*', '', texto).strip()
    candidatos = _extraer_json_balanceado(texto_limpio)
    for datos in candidatos:
        nombre = datos.get("name") or datos.get("tool") or datos.get("function")
        args = (
            datos.get("arguments")
            or datos.get("args")
            or datos.get("parameters")
            or {}
        )
        if nombre and nombre in MAPA_HERRAMIENTAS_TEST:
            resultado = MAPA_HERRAMIENTAS_TEST[nombre](args)
            return [f"[{nombre.upper()} - Iter.{iteracion}]\n{resultado}"]
    return []

# ---- Tests ----

CASOS = [
    (
        "Formato 'arguments' (logs reales del LLM)",
        '{"name": "herramienta_gobuster", "arguments": {"objetivo": "http://localhost:3000"}}',
        "herramienta_gobuster"
    ),
    (
        "Formato 'args'",
        '{"name": "herramienta_nikto", "args": {"objetivo": "http://localhost:3000"}}',
        "herramienta_nikto"
    ),
    (
        "Envuelto en bloque markdown ```json",
        '```json\n{"name": "herramienta_nmap", "arguments": {"objetivo": "localhost"}}\n```',
        "herramienta_nmap"
    ),
    (
        "Precedido de texto del LLM",
        '[IA RAZONA]\nVoy a usar gobuster para enumerar directorios.\n{"name": "herramienta_gobuster", "arguments": {"objetivo": "http://localhost:3000"}}',
        "herramienta_gobuster"
    ),
    (
        "Formato 'tool' en lugar de 'name'",
        '{"tool": "herramienta_nikto", "arguments": {"objetivo": "http://localhost:3000"}}',
        "herramienta_nikto"
    ),
    (
        "Razonamiento puro sin tool call — debe devolver vacío",
        "Analizando los hallazgos... La superficie de ataque parece limitada. AUDITORIA_COMPLETA",
        None  # se espera lista vacía
    ),
]

OK = 0
FAIL = 0

print("=" * 55)
print("TEST PARSER DE CONTINGENCIA — Red-AI")
print("=" * 55)

for descripcion, texto, herramienta_esperada in CASOS:
    resultado = _intentar_ejecutar_desde_texto(texto)
    if herramienta_esperada is None:
        paso = len(resultado) == 0
    else:
        paso = len(resultado) > 0 and herramienta_esperada.upper() in resultado[0]

    estado = "✓ OK" if paso else "✗ FAIL"
    print(f"\n[{estado}] {descripcion}")
    if not paso:
        print(f"       Texto: {texto[:80]}...")
        print(f"       Resultado: {resultado}")
        FAIL += 1
    else:
        OK += 1

print("\n" + "=" * 55)
print(f"Resultado: {OK}/{OK+FAIL} tests pasaron")
print("=" * 55)

sys.exit(0 if FAIL == 0 else 1)
