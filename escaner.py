import sys
from google import genai

def escanear_modelos():
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
    print("🔍 Conectando a Google y solicitando lista de modelos activos...")
    import os
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except Exception:
        pass
    gemini_key = os.environ.get("GEMINI_API_KEY", "")
    client = genai.Client(api_key=gemini_key)
    
    try:
        modelos = client.models.list()
        print("\n✅ ¡Conexión exitosa! Estos son los modelos exactos que puedes usar:")
        print("--------------------------------------------------")
        for m in modelos:
            print(f"- {m.name}")
        print("--------------------------------------------------")
    except Exception as e:
        print(f"\n[ERROR] Falló el escaneo: {e}")

if __name__ == "__main__":
    escanear_modelos()
