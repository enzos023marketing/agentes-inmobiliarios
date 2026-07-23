import sys
import os
import time
import random
import requests
import json
import hashlib
import urllib.parse
from datetime import datetime, timezone
from bs4 import BeautifulSoup
from google import genai
import db_client

def espera_humana(min_seg=2.0, max_seg=5.0):
    """Simula los tiempos de reacción de un humano para evitar bloqueos de Google."""
    time.sleep(random.uniform(min_seg, max_seg))

def consultar_gemini_con_reintentos(client, prompt_text, max_intentos=3):
    """Realiza la consulta a la API de Gemini con lógica de reintentos."""
    for intento in range(max_intentos):
        try:
            print(f"[IA] Analizando oportunidad con Gemini (Intento {intento + 1}/{max_intentos})...")
            respuesta = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt_text,
            )
            return respuesta.text
        except Exception as e:
            print(f"[WARN] Servidores de IA saturados o error: {e}")
            if intento < max_intentos - 1:
                espera_humana(6.0, 12.0)
            else:
                return "[ERROR]"

def enviar_a_telegram(prop):
    """Envía notificaciones de captación directa a un chat de Telegram."""
    # Configuración de Telegram (se lee de variables de entorno)
    TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
    
    url_telegram = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    tipo = prop.get("Tipo Propiedad", "Propiedad")
    analisis = prop.get("Análisis IA", "Sin análisis")
    link = prop.get("Link", "")
    telefono = prop.get("Teléfono", "A revisar")
    contacto = prop.get("Dueño/Contacto", "Dueño Directo")
    
    mensaje = (
        f"🏢 *NUEVA CAPTACIÓN DIRECTA ({prop.get('Plataforma', 'Redes').upper()})*\n\n"
        f"📍 *Tipo:* {tipo}\n"
        f"👤 *Contacto:* {contacto}\n"
        f"📞 *Teléfono:* {telefono}\n"
        f"💡 *IA:* {analisis}\n\n"
        f"🔗 [Abrir Publicación]({link})"
    )
    payload = {
        "chat_id": CHAT_ID,
        "text": mensaje,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    }
    try:
        r = requests.post(url_telegram, json=payload, timeout=10)
        if r.status_code == 200:
            print(f"[TELEGRAM] ✅ Notificación enviada correctamente.")
        else:
            print(f"[TELEGRAM] ❌ Falló envío. Código de estado: {r.status_code}")
    except Exception as e:
        print(f"[TELEGRAM] [ERROR] Falló enlace con Telegram: {e}")

def main():
    # Asegurar codificación UTF-8 en salida estándar
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

    print("=====================================================")
    print("🤖 INICIANDO AGENTE FANTASMA MODULAR Y CLOUD-READY 🤖")
    print("=====================================================\n")

    # 1. Argumentos CLI y Consulta de Paginación en Supabase
    plataforma = sys.argv[1].lower().strip() if len(sys.argv) > 1 else "instagram"
    
    # Lectura del índice inicial de paginación desde Supabase
    indice_inicial = db_client.obtener_ultimo_indice(plataforma)

    print(f"[CONFIG] Plataforma activa para escaneo: {plataforma.upper()}")
    print(f"[CONFIG] Índice inicial cargado de Supabase: {indice_inicial}")

    # 2. Inicializar cliente de Google GenAI
    gemini_key = os.environ.get("GEMINI_API_KEY", "")
    client = genai.Client(api_key=gemini_key)

    # 3. Definir Dorks de búsqueda con filtros anti-autos, anti-alquileres y anti-inmobiliarias
    if plataforma == "instagram":
        dorks = [
            'site:instagram.com "dueño vende" "mar del plata" (departamento OR casa OR depto OR dto) -inmobiliaria -alquiler -alquilo -alquileres -auto -moto -camioneta',
            'site:instagram.com "dueño directo" "mar del plata" (departamento OR casa OR depto OR dto) -inmobiliaria -alquiler -alquilo -auto -moto'
        ]
    elif plataforma == "facebook":
        dorks = [
            'site:facebook.com/marketplace "dueño vende" "mar del plata" (casa OR departamento OR depto) -alquiler -alquilo -auto -camioneta -vehiculo -moto',
            'site:facebook.com "dueño directo" "mar del plata" (venta OR vendo OR vende) -inmobiliaria -alquiler -alquilo -auto -camioneta'
        ]
    else:
        dorks = [
            f'site:{plataforma}.com "dueño directo" "mar del plata" -alquiler -alquilo'
        ]

    # Búsqueda acotada: Se avanzan 10 índices (1 página de Google) por dork por ejecución
    limite_de_bloque = 10
    nuevo_indice = indice_inicial + limite_de_bloque
    
    print(f"\n[EXEC] Iniciando escaneo de bloques en Google Search...")
    print(f"[EXEC] Buscando para {plataforma.upper()} con índice de inicio: {indice_inicial}")

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    anuncios_candidatos = []

    # 4. Motor de peticiones HTTP limpias
    for dork in dorks:
        url = f"https://www.google.com/search?q={urllib.parse.quote_plus(dork)}&start={indice_inicial}"
        print(f"\n[HTTP] Consultando query: {url}")
        
        try:
            response = requests.get(url, headers=headers, timeout=15)
            
            # Control de bloqueo/consensos de Google
            if response.status_code == 429 or "detected unusual traffic" in response.text:
                print(f"[HTTP] [WARN] Bloqueo temporal o Captcha detectado por Google (Código {response.status_code}).")
                continue
            
            if response.status_code != 200:
                print(f"[HTTP] [WARN] Estado de respuesta no exitoso: {response.status_code}")
                continue
                
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extraer enlaces candidatos de la plataforma específica
            for a in soup.find_all('a', href=True):
                link = a['href']
                
                # Desempaquetar redirecciones de Google si existen
                if '/url?q=' in link:
                    link = link.split('/url?q=')[1].split('&')[0]
                
                link = urllib.parse.unquote(link)
                
                # Descartar links internos de Google o inválidos
                if not link.startswith('https://') or 'google.com' in link:
                    continue
                
                # Filtrar rigurosamente que pertenezcan a la plataforma activa
                if plataforma == "instagram" and "instagram.com" not in link:
                    continue
                if plataforma == "facebook" and "facebook.com" not in link:
                    continue
                
                # Extraer título del resultado de búsqueda
                h3 = a.find('h3')
                titulo = h3.get_text(strip=True) if h3 else ""
                
                # Obtener fragmento de texto adyacente (snippet) subiendo en el DOM
                snippet = ""
                parent = a.parent
                for _ in range(4):
                    if not parent:
                        break
                    text = parent.get_text(" ", strip=True)
                    if len(text) > len(titulo) + 30:
                        snippet = text
                        break
                    parent = parent.parent
                
                if not titulo:
                    titulo = snippet[:60] + "..." if snippet else f"Publicación de {plataforma.capitalize()}"
                
                # Control de duplicados en la lista de la tanda actual
                if link not in [an['link'] for an in anuncios_candidatos]:
                    anuncios_candidatos.append({
                        'titulo': titulo,
                        'link': link,
                        'texto': snippet or titulo
                    })
                    
        except Exception as e:
            print(f"[HTTP] [ERROR] Error al escanear la query: {e}")
        
        # Pausa anti-bloqueo entre consultas de dorks
        espera_humana(4.0, 7.0)

    print(f"\n[SYS] Encontrados {len(anuncios_candidatos)} candidatos brutos para {plataforma.upper()}.")

    nuevos_registros_guardados = 0

    # 5. Procesamiento de resultados y Control de Duplicados en Supabase
    for anuncio in anuncios_candidatos:
        link_url = anuncio['link']
        
        # Generar hash y verificar contra Supabase para descartar duplicados antes de insertar o llamar a IA
        if db_client.existe_captacion_por_link(link_url):
            print(f"[DUPLICADO] Omitiendo '{link_url}' (ya registrado en Supabase).")
            continue
            
        print(f"\n[NUEVO] Procesando publicación potencial: {link_url}")
        
        # Armar el prompt optimizado para clasificación con Gemini
        prompt = f"""
        Analiza este posteo de redes sociales para determinar si cumple rigurosamente con los siguientes requisitos:
        1. Es una VENTA (no alquiler, no alquiler temporal).
        2. Es de DUEÑO DIRECTO o VENTA SIN COMISIÓN (si dice que es de una inmobiliaria, broker o gestor de bienes raíces, descártalo).
        3. Es en la ciudad de Mar del Plata, Argentina (especialmente en áreas: Centro, Macrocentro, Parque Luro, Chauvín, Playa Grande, Stella Maris, San José, Paso, Pompeya o Constitución).

        Si cumple con TODO lo anterior, devuelve estrictamente un JSON válido con este formato:
        {{
          "Cumple": true,
          "Tipo Propiedad": "(Casa, Departamento, Duplex, Terreno, etc.)",
          "Teléfono": "(Número de teléfono si se menciona en el texto, o 'A revisar')",
          "Dueño/Contacto": "(Nombre del dueño/contacto si se menciona, o 'Dueño Directo')",
          "Análisis IA": "(Un análisis muy breve explicando por qué es venta directa y sus detalles principales)"
        }}

        Si no cumple con alguno de los requisitos, devuelve estrictamente este JSON:
        {{
          "Cumple": false
        }}

        Datos a analizar:
        TÍTULO: {anuncio['titulo']}
        DESCRIPCIÓN: {anuncio['texto']}
        LINK: {anuncio['link']}
        """
        
        reporte = consultar_gemini_con_reintentos(client, prompt)
        if reporte == "[ERROR]":
            continue
            
        # Extraer y parsear JSON retornado por la IA
        try:
            start = reporte.find('{')
            end = reporte.rfind('}')
            if start != -1 and end != -1:
                datos_json = json.loads(reporte[start:end+1])
                
                # Si cumple con los filtros, se registra y se notifica
                if datos_json.get("Cumple") is True:
                    db_client.guardar_captacion(
                        titulo=anuncio['titulo'],
                        link=link_url,
                        telefono=datos_json.get("Teléfono", "A revisar"),
                        plataforma=plataforma,
                        analisis_ia=datos_json.get("Análisis IA", "Venta Directa de Dueño")
                    )
                    
                    # Adjuntar plataforma y notificar a Telegram
                    datos_json["Link"] = link_url
                    datos_json["Plataforma"] = plataforma
                    enviar_a_telegram(datos_json)
                    nuevos_registros_guardados += 1
                else:
                    # Si no cumple, igualmente lo guardamos como descartado para registrar el hash
                    # y no volver a gastar tokens de Gemini analizando el mismo link la próxima vez.
                    db_client.guardar_captacion(
                        titulo=anuncio['titulo'],
                        link=link_url,
                        telefono="Descartado",
                        plataforma=plataforma,
                        analisis_ia="DESCARTADO: No cumple criterios de venta directa por dueño o zona."
                    )
                    print(f"[IA] Publicación descartada (no cumple filtros). Registrado hash en BD para evitar re-análisis.")
                    
            else:
                print(f"[IA] [WARN] No se localizó estructura JSON válida en el reporte.")
        except Exception as e:
            print(f"[IA] [ERROR] Error al parsear JSON o registrar en BD: {e}")
            
        espera_humana(2.0, 4.0)

    # 6. Actualización del puntero de paginación en Supabase
    db_client.actualizar_indice(plataforma, nuevo_indice)
    print(f"\n=====================================================")
    print(f"✅ CICLO ACUTADO FINALIZADO exitosamente.")
    print(f"📊 Nuevas captaciones agregadas: {nuevos_registros_guardados}")
    print(f"🔑 Paginación actualizada en Supabase para {plataforma.upper()}: {nuevo_indice}")
    print("=====================================================")

if __name__ == "__main__":
    main()