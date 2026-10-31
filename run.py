#!/usr/bin/env python3
"""
Punto de entrada principal de Red-AI.
Uso: python3 run.py [--objetivo URL] [--max-iter N]
"""

import argparse
import sys
from core.agente_dast import agente_app, AgentState

def main():
    parser = argparse.ArgumentParser(description="Red-AI — Agente Autónomo de Pentesting Web")
    parser.add_argument(
        "--objetivo",
        default="http://localhost:3000",
        help="URL objetivo de la auditoría (default: http://localhost:3000)"
    )
    parser.add_argument(
        "--max-iter",
        type=int,
        default=5,
        help="Máximo de iteraciones autónomas (default: 5)"
    )
    args = parser.parse_args()

    estado_inicial: AgentState = {
        "objetivo": args.objetivo,
        "autorizacion": "TFG-UTAD-2026",
        "hallazgos": [],
        "mensajes": [],
        "iteracion": 0,
        "max_iteraciones": args.max_iter,
        "auditoria_completa": False,
        "reporte_final": "",
    }

    print("=" * 60)
    print("   RED-AI — Agente Autónomo de Pentesting Web")
    print(f"   Objetivo:    {estado_inicial['objetivo']}")
    print(f"   Max iter:    {estado_inicial['max_iteraciones']}")
    print("=" * 60)

    estado_final = None
    try:
        for output in agente_app.stream(estado_inicial):
            for nodo, estado in output.items():
                print(f"\n[Sistema] ✓ Nodo completado: {nodo.upper()}")
            estado_final = output
    except KeyboardInterrupt:
        print("\n\n[!] Ejecución interrumpida por el usuario.")
        sys.exit(0)

    # Mostrar y guardar el reporte
    if estado_final:
        ultimo = list(estado_final.values())[-1]
        reporte = ultimo.get("reporte_final", "")
        if reporte:
            print("\n" + "=" * 60)
            print("REPORTE FINAL")
            print("=" * 60)
            print(reporte)

            # Guardamos el reporte en un archivo
            objetivo_limpio = args.objetivo.replace("http://", "").replace("https://", "").replace("/", "_").replace(":", "-")
            nombre_archivo = f"reporte_{objetivo_limpio}.md"
            with open(nombre_archivo, "w") as f:
                f.write(reporte)
            print(f"\n[✓] Reporte guardado en: {nombre_archivo}")
        else:
            print("\n[!] No se generó reporte.")

if __name__ == "__main__":
    main()
