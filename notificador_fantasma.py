import pandas as pd
import time
import random
import webbrowser
import pyautogui
import pyperclip
import os

def espera_humana(min_seg, max_seg):
    time.sleep(random.uniform(min_seg, max_seg))

def main():
    print("=====================================================")
    print("📱 INICIANDO NOTIFICADOR FANTASMA (ANTI-BAN V1.0) 📱")
    print("=====================================================\n")
    
    archivo_excel = "contactos_captacion.xlsx"
    
    if not os.path.exists(archivo_excel):
        print("[ERROR] No se encontró el archivo Excel base.")
        return
        
    df = pd.read_excel(archivo_excel)
    
    # 1. Crear columna de control si no existe
    if "Notificado" not in df.columns:
        df["Notificado"] = "NO"
        print("[SYS] Columna de memoria 'Notificado' agregada al Excel.")
        
    # 2. Filtrar propiedades pendientes
    pendientes = df[df["Notificado"] == "NO"]
    
    if pendientes.empty:
        print("[SYS] 💤 No hay propiedades nuevas pendientes de notificación.")
        return
        
    # 3. Limitar a un máximo de 3 envíos por tanda (Comportamiento Humano)
    a_enviar = pendientes.head(3)
    print(f"[SYS] Se encontraron {len(pendientes)} propiedades sin notificar. Procesando {len(a_enviar)} por seguridad...")
    
    # 4. Abrir WhatsApp Web en el grupo específico
    ID_GRUPO = "EjqSN0gbMN38YK6mCqMLt1"
    print("[SYS] Abriendo centro de comando en WhatsApp Web...")
    webbrowser.open(f"https://web.whatsapp.com/accept?code={ID_GRUPO}")
    
    # Pausa larga para asegurar que WhatsApp Web cargue el chat por completo
    print("[SYS] Esperando 25 segundos para la sincronización web (NO TOQUES EL MOUSE)...")
    espera_humana(20.0, 25.0)
    
    # 5. Envío por Goteo
    indices_actualizados = []
    
    for index, row in a_enviar.iterrows():
        tipo = row.get("Tipo Propiedad", "Propiedad")
        analisis = row.get("Análisis IA", "Sin análisis")
        link = row.get("Link", "")
        
        mensaje = f"🏢 *{tipo}*\n💡 {analisis}\n🔗 {link}"
        
        print(f"[SYS] Tipeando mensaje para fila {index}...")
        # Copiar al portapapeles (permite enviar emojis perfectamente)
        pyperclip.copy(mensaje)
        
        # Simular Pegar y Enviar
        pyautogui.hotkey('ctrl', 'v')
        espera_humana(1.5, 3.0) # Pausa antes de enviar
        pyautogui.press('enter')
        
        indices_actualizados.append(index)
        
        # Pausa humana larga entre envíos para no activar filtros anti-spam
        if len(a_enviar) > 1 and index != a_enviar.index[-1]:
            pausa = random.uniform(15.0, 25.0)
            print(f"[SYS] ⏳ Pausa táctica de {int(pausa)} segundos para simular lectura humana...")
            time.sleep(pausa)
            
    # 6. Actualizar Excel
    for idx in indices_actualizados:
        df.at[idx, "Notificado"] = "SÍ"
        
    df.to_excel(archivo_excel, index=False, engine='openpyxl')
    print("\n[SYS] ✅ Tanda de mensajes enviada y Excel actualizado exitosamente.")

if __name__ == "__main__":
    main()
