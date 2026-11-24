"""
Lista los modelos de Gemini que tu API key puede usar para generar texto.

Sirve para resolver el error HTTP 404 (modelo inexistente o retirado):
elegí uno de la lista y ponelo en el .env como GEMINI_MODEL=<nombre>.

Uso (desde la carpeta entrega_2/, con la key en el .env):
    python listar_modelos.py                          → lista los modelos
    python listar_modelos.py --probar                 → además prueba el modelo configurado
    python listar_modelos.py --probar gemini-3.5-flash gemini-flash-latest   → prueba esos
"""

import argparse
import json
import sys
import urllib.error
import urllib.request

from ombu.config import SSL_CONTEXT, key_valida
from ombu.llm import modelo_configurado

parser = argparse.ArgumentParser()
parser.add_argument("--probar", nargs="*", metavar="MODELO",
                    help="hace un pedido mínimo a cada modelo (sin nombres: el configurado)")
args = parser.parse_args()

key = key_valida("GEMINI_API_KEY")
if not key:
    sys.exit("No encontré GEMINI_API_KEY en el .env (o tiene el texto de ejemplo).")

url = "https://generativelanguage.googleapis.com/v1beta/models?pageSize=200"
req = urllib.request.Request(url, headers={"x-goog-api-key": key})
try:
    with urllib.request.urlopen(req, context=SSL_CONTEXT, timeout=30) as resp:
        datos = json.loads(resp.read().decode("utf-8"))
except urllib.error.HTTPError as e:
    sys.exit(f"La API respondió HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:500]}")
except urllib.error.URLError as e:
    sys.exit(f"No pude conectarme a la API: {e}")

modelos = [m["name"].removeprefix("models/") for m in datos.get("models", [])
           if "generateContent" in m.get("supportedGenerationMethods", [])]
actual = modelo_configurado("gemini")

print(f"Modelo configurado ahora: {actual} → {'✅ disponible' if actual in modelos else '❌ NO está en la lista'}\n")
print("Modelos disponibles para generar texto (los 'flash' son los rápidos y baratos):")
for nombre in sorted(modelos):
    print(f"  {'→ ' if 'flash' in nombre and 'lite' not in nombre else '  '}{nombre}")
print("\nPara cambiarlo, agregá en el .env:  GEMINI_MODEL=<nombre>")


def probar(modelo: str) -> None:
    """Un pedido mínimo, con el mismo formato que usa ombu/llm.py."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent"
    payload = {
        "systemInstruction": {"parts": [{"text": 'Respondé solo con el JSON {"ok": true}'}]},
        "contents": [{"role": "user", "parts": [{"text": "probando"}]}],
        "generationConfig": {"temperature": 0, "responseMimeType": "application/json"},
    }
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"),
                                 headers={"Content-Type": "application/json", "x-goog-api-key": key})
    try:
        with urllib.request.urlopen(req, context=SSL_CONTEXT, timeout=60) as resp:
            texto = json.loads(resp.read())["candidates"][0]["content"]["parts"][0]["text"]
        print(f"  ✅ {modelo}: respondió {texto.strip()[:60]!r}")
    except urllib.error.HTTPError as e:
        print(f"  ❌ {modelo}: HTTP {e.code} — {e.read().decode('utf-8', 'replace')[:400]}")
    except (urllib.error.URLError, KeyError, IndexError) as e:
        print(f"  ❌ {modelo}: {type(e).__name__}: {e}")


if args.probar is not None:
    print("\nPrueba de generación:")
    for m in args.probar or [actual]:
        probar(m)
