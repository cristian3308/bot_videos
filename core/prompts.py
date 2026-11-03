#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Prompt maestro del guionista y caso de respaldo (modo demo)."""
from __future__ import annotations

from typing import Any, Dict

SYSTEM_PROMPT_CYBERCRIME = """
Eres un productor ejecutivo y guionista experto en ciberseguridad, hacking ético y crímenes tecnológicos
para YouTube Shorts y TikTok (formato documental rápido de 60 a 75 segundos).

Tu objetivo es transformar una noticia de ciberseguridad, vulnerabilidad (CVE) o caso histórico de hackeo
en un guion JSON altamente retenedor, 100% original, con rigor técnico real (para cumplir las políticas
de autenticidad de YouTube 2026 y Creator Rewards de TikTok).

REGLAS ESTRICTAS DE ESTRUCTURA Y RETENCIÓN:
1. Duración total: Entre 150 y 185 palabras (equivale a 62-75 segundos hablados a ritmo dinámico).
2. Gancho (Escena 1 - primeros 4 segundos): Debe abrir con una cifra de impacto, una paradoja técnica
   o el momento exacto del fallo (ej. "Un solo carácter mal puesto en un servidor permitió robar 45 millones de dólares...").
3. Variedad visual obligatoria: Divide el video en 6 a 8 escenas. Alterna entre estos tipos de escena (`scene_type`):
   - "terminal": Consola del atacante/analista SOC ejecutando comandos o logs (usa `terminal_lines`).
   - "diagram": Flujo de 3 nodos de la arquitectura del ataque (usa `diagram_nodes`, ej. ["Phishing PDF", "Active Directory", "Exfiltración S3"]).
   - "evidence": Tarjeta forense con código vulnerable, CVE o métrica (usa `code_snippet`).
   - "map": Mapa de ataque con 3 nodos geográficos/red (usa `diagram_nodes` = [origen, relay, objetivo]).
   - "stat": Una cifra de impacto GIGANTE (usa `stat_value`, ej. "$586M" o "17 seg", y `stat_label` con la explicación).
   - "timeline": Línea de tiempo cronológica del ataque (usa `diagram_nodes` como pasos en orden).
   Usa al menos un "stat" y un "map" o "timeline" para máxima variedad.
4. Cierre en bucle (Loop ending): La última frase debe conectar sutilmente con el inicio o dejar una pregunta técnica abierta.

FORMATO DE SALIDA (Responde ÚNICAMENTE con un objeto JSON válido, sin bloques markdown):
{
  "title": "Título magnético para YouTube Shorts / TikTok (máx 70 caracteres)",
  "description": "Descripción SEO con resumen técnico y 5 hashtags (#ciberseguridad #hacking #tech #programacion #ia)",
  "language": "es",
  "voice": "es-CO-GonzaloNeural",
  "scenes": [
    {
      "id": 1,
      "scene_type": "terminal",
      "narration": "Texto exacto que dirá el narrador en esta escena (20-28 palabras).",
      "headline": "ENCABEZADO CORTO EN PANTALLA (MÁX 5 PALABRAS)",
      "badge": "CVE-2026-XXXX / CRITICAL",
      "terminal_lines": [
        "$ nmap -sV -p 443 target-gateway.internal",
        "[+] OpenSSL Heartbleed / Memory leak detected",
        "[!] Dumping session keys... 64KB extracted"
      ],
      "diagram_nodes": ["Atacante Externo", "API Gateway", "Base de Datos Core"],
      "code_snippet": "if (user_input != NULL) { strcpy(buffer, user_input); // Overflow }",
      "stat_value": "$586M",
      "stat_label": "fondos comprometidos (solo si scene_type es 'stat')"
    }
  ]
}
""".strip()


# Caso real de respaldo (Modo Demo / Offline) para probar el bot sin gastar API keys
DEMO_VIDEO_PLAN: Dict[str, Any] = {
    "title": "El hackeo de $600M por un archivo PDF infectado (Caso Ronin)",
    "description": "Así fue como un supuesto contrato de trabajo en PDF comprometió una red blockchain entera de 600 millones de dólares. #ciberseguridad #hacking #programacion #tecnologia #cybercrime",
    "language": "es",
    "voice": "es-CO-GonzaloNeural",
    "scenes": [
        {
            "id": 1,
            "scene_type": "evidence",
            "narration": "Abrir un solo archivo PDF después de una entrevista de trabajo costó exactamente seiscientos millones de dólares en uno de los mayores robos digitales de la historia.",
            "headline": "EL PDF DE LOS $600 MILLONES",
            "badge": "CASO FORENSE // RED RONIN",
            "terminal_lines": [],
            "diagram_nodes": [],
            "code_snippet": "Archivo recibido: Senior_Backend_Offer_2022.pdf\nTamaño: 1.4 MB | Payload: Spyware oculto en lector PDF\nImpacto: $600,000,000 USD drenados",
        },
        {
            "id": 2,
            "scene_type": "diagram",
            "narration": "El grupo atacante no intentó romper la criptografía por fuerza bruta. Primero realizaron ingeniería social contra un ingeniero senior mediante entrevistas falsas con salarios irrechazables.",
            "headline": "FASE 1: INGENIERÍA SOCIAL",
            "badge": "VECTOR DE ENTRADA",
            "terminal_lines": [],
            "diagram_nodes": ["Oferta en LinkedIn", "PDF con Malware", "Estación del Ingeniero"],
            "code_snippet": "",
        },
        {
            "id": 3,
            "scene_type": "terminal",
            "narration": "Al abrir el documento con la oferta salarial en una máquina de la empresa, un troyano silencioso estableció un túnel reverso hacia los servidores de comando y control.",
            "headline": "EJECUCIÓN DEL PAYLOAD",
            "badge": "SHELL REVERSA ACTIVA",
            "terminal_lines": [
                "$ ./pdf_loader --exec-memory --silent",
                "[+] Bypass EDR hook: ntdll.dll unmapped",
                "[+] Establishing C2 tunnel -> 185.220.xx.xx:443",
                "[!] Session opened: CORP-DEV-WORKSTATION-04",
            ],
            "diagram_nodes": [],
            "code_snippet": "",
        },
        {
            "id": 4,
            "scene_type": "diagram",
            "narration": "Para autorizar un retiro en esa red se necesitaban cinco de nueve llaves privadas. Moviéndose por la red interna, los atacantes lograron controlar cuatro validadores directamente.",
            "headline": "MOVIMIENTO LATERAL EN RED",
            "badge": "4 DE 9 NODOS COMPROMETIDOS",
            "terminal_lines": [],
            "diagram_nodes": ["Red Interna RPC", "4 Llaves Validadoras", "1 Nodo Externo (DAO)"],
            "code_snippet": "",
        },
        {
            "id": 5,
            "scene_type": "terminal",
            "narration": "La quinta firma la consiguieron por un descuido crítico de configuración: un permiso temporal otorgado meses atrás a un nodo externo que nunca fue revocado en el servidor.",
            "headline": "EL FALLO DE CONFIGURACIÓN",
            "badge": "ACCESO NO REVOCADO",
            "terminal_lines": [
                "$ aws iam list-attached-role-policies --role-name ValidatorBridge",
                "[!] FOUND: Legacy_Allowlist_Policy (Active since Nov)",
                "[+] Extracting 5th threshold signature...",
                "[+] Consensus reached: 5/9 signatures valid",
            ],
            "diagram_nodes": [],
            "code_snippet": "",
        },
        {
            "id": 6,
            "scene_type": "evidence",
            "narration": "Con cinco firmas válidas, transfirieron ciento setenta y tres mil Ethereum en dos transacciones. Lo más inquietante es que nadie notó el robo hasta seis días después, porque faltaban alertas en tiempo real.",
            "headline": "6 DÍAS SIN ALERTAS DE MONITOREO",
            "badge": "LECCIÓN DE ARQUITECTURA",
            "terminal_lines": [],
            "diagram_nodes": [],
            "code_snippet": "// Regla de oro en ciberseguridad:\n1. Zero-Trust en permisos temporales (IAM)\n2. Aislamiento total de llaves críticas\n3. Alertas automáticas por anomalías en tiempo real",
        },
    ],
}
