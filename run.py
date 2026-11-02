#!/usr/bin/env python3
"""
Punto de entrada CLI de Red-AI.
Uso: python3 run.py --objetivo URL [--modelo NOMBRE]
"""
import argparse
import sys
from core.agente_dast import ejecutar_auditoria, MODELO_DEFAULT

def main():
    parser = argparse.ArgumentParser(description="Red-AI — Agente Autónomo de Pentesting Web")
    parser.add_argument(
        "--objetivo",
        default="http://localhost:3000",
        help="URL objetivo de la auditoría (default: http://localhost:3000)"
    )
    parser.add_argument(
        "--modelo",
        default=MODELO_DEFAULT,
        help=f"Modelo Ollama a usar (default: {MODELO_DEFAULT})"
    )
    args = parser.parse_args()

    print("=" * 60)
    print("   RED-AI — Agente Autónomo de Pentesting Web")
    print(f"   Objetivo: {args.objetivo}")
    print(f"   Modelo:   {args.modelo}")
    print("   Iteraciones: sin límite (para en AUDITORIA_COMPLETA)")
    print("=" * 60)

    try:
        resultado = ejecutar_auditoria(objetivo=args.objetivo, modelo=args.modelo)
    except KeyboardInterrupt:
        print("\n\n[!] Ejecución interrumpida por el usuario.")
        sys.exit(0)

    reporte = resultado.get("reporte", "")
    if reporte:
        print("\n" + "=" * 60)
        print("REPORTE FINAL")
        print("=" * 60)
        print(reporte)

        objetivo_limpio = (
            args.objetivo.replace("http://","").replace("https://","")
            .replace("/","_").replace(":","_")
        )
        nombre = f"reporte_{objetivo_limpio}.md"
        with open(nombre, "w") as f:
            f.write(reporte)
        print(f"\n[✓] Reporte guardado en: {nombre}")
    else:
        print("\n[!] No se generó reporte.")

if __name__ == "__main__":
    main()
