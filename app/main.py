import os
import shutil
import json
from datetime import datetime, timedelta
from fastapi import FastAPI, BackgroundTasks, HTTPException
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS
from geopy.geocoders import Nominatim
from app.config import settings

app = FastAPI(title="Cognitive Photo Organizer Service", version="1.0")

#Variables de entorno
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
MODELO_VLM = os.getenv("MODELO_VLM", "qwen2-vl:7b")
CARPETA_ORIGEN = os.getenv("CARPETA_ORIGEN", "/data/origen")
CARPETA_DESTINO = os.getenv("CARPETA_DESTINO", "/data/destino")

UMBRAL_TIEMPO = timedelta(hours=36)
MIN_FOTOS_EVENTO = 10

geolocator = Nominatim(user_agent="organizador_fotos_container")
client = ollama.Client(host=OLLAMA_HOST)

def obtener_metadata(ruta_archivo):
    fecha = datetime.fromtimestamp(os.path.getmtime(ruta_archivo))
    lat, lon = None, None
    try:
        with Image.open(ruta_archivo) as img:
            exif = img._getexif()
            if exif:
                gps_data = {}
                for tag, value in exif.items():
                    decoded = TAGS.get(tag, tag)
                    if decoded == 'DateTimeOriginal':
                        fecha = datetime.strptime(value, '%Y:%m:%d %H:%M:%S')
                    if decoded == 'GPSInfo':
                        for g_tag in value:
                            g_decoded = GPSTAGS.get(g_tag, g_tag)
                            gps_data[g_decoded] = value[g_tag]
                
                if 'GPSLatitude' in gps_data and 'GPSLongitude' in gps_data:
                    def to_degrees(val):
                        return float(val[0]) + (float(val[1]) / 60.0) + (float(val[2]) / 3600.0)
                    lat = to_degrees(gps_data['GPSLatitude'])
                    lon = to_degrees(gps_data['GPSLongitude'])
                    if gps_data.get('GPSLatitudeRef') == 'S': lat = -lat
                    if gps_data.get('GPSLongitudeRef') == 'W': lon = -lon
    except Exception:
        pass
    return fecha, lat, lon

def obtener_nombre_lugar(lat, lon):
    if not lat or not lon: return None
    try:
        location = geolocator.reverse((lat, lon), timeout=5, language="es")
        if location:
            addr = location.raw.get('address', {})
            return f"{addr.get('city') or addr.get('town') or addr.get('village')}_{addr.get('country')}"
    except Exception:
        pass
    return None

def analizar_con_vlm(ruta_imagen):
    prompt = (
        "Analyze this image. You must respond ONLY with a valid JSON object. "
        "Do not include markdown formatting like ```json. Just raw JSON.\n"
        "Format: {\"tipo\": \"foto_real\"|\"meme\"|\"captura_pantalla\", "
        "\"contexto_evento\": \"graduacion\"|\"boda\"|\"laboratorio\"|\"viaje\"|\"vida_cotidiana\"}"
    )
    try:
        response = client.generate(model=MODELO_VLM, prompt=prompt, images=[ruta_imagen])
        data = json.loads(response['response'].strip())
        return data.get('tipo', 'foto_real'), data.get('contexto_evento', 'vida_cotidiana')
    except Exception:
        return 'foto_real', 'vida_cotidiana'

def ejecutar_pipeline_organizacion():
    if not os.path.exists(CARPETA_ORIGEN):
        return
    
    archivos = []
    for raiz, _, f_lista in os.walk(CARPETA_ORIGEN):
        for f in f_lista:
            if f.lower().endswith(('.jpg', '.jpeg', '.png')):
                ruta = os.path.join(raiz, f)
                fecha, lat, lon = obtener_metadata(ruta)
                archivos.append({'ruta': ruta, 'fecha': fecha, 'lat': lat, 'lon': lon, 'nombre': f})
                
    if not archivos: return

    archivos.sort(key=lambda x: x['fecha'])
    
    # Clustering temporal
    clusters = []
    cluster_actual = [archivos[0]]
    for foto in archivos[1:]:
        if foto['fecha'] - cluster_actual[-1]['fecha'] <= UMBRAL_TIEMPO:
            cluster_actual.append(foto)
        else:
            clusters.append(cluster_actual)
            cluster_actual = [foto]
    clusters.append(cluster_actual)

    meses = {1: "01_Enero", 2: "02_Febrero", 3: "03_Marzo", 4: "04_Abril", 5: "05_Mayo", 6: "06_Junio", 
             7: "07_Julio", 8: "08_Agosto", 9: "09_Septiembre", 10: "10_Octubre", 11: "11_Noviembre", 12: "12_Diciembre"}

    for idx, cluster in enumerate(clusters):
        fecha_base = cluster[0]['fecha']
        año = str(fecha_base.year)
        mes = meses[fecha_base.month]
        
        ubicacion_viaje = None
        for f in cluster:
            if f['lat'] and f['lon']:
                ubicacion_viaje = obtener_nombre_lugar(f['lat'], f['lon'])
                if ubicacion_viaje: break
        
        es_evento = len(cluster) >= MIN_FOTOS_EVENTO
        
        for foto in cluster:
            tipo_visual, contexto = analizar_con_vlm(foto['ruta'])
            
            if tipo_visual in ['meme', 'captura_pantalla']:
                ruta_final = os.path.join(CARPETA_DESTINO, año, mes, f"Descartes_{tipo_visual}")
            else:
                if es_evento:
                    tag_final = f"{contexto}_{ubicacion_viaje}" if ubicacion_viaje else f"Evento_{contexto}"
                    ruta_final = os.path.join(CARPETA_DESTINO, año, mes, f"{fecha_base.strftime('%Y-%m-%d')}_{tag_final}")
                else:
                    ruta_final = os.path.join(CARPETA_DESTINO, año, mes, f"Dia_{foto['fecha'].strftime('%d')}")
            
            os.makedirs(ruta_final, exist_ok=True)
            shutil.move(foto['ruta'], os.path.join(ruta_final, foto['nombre']))

@app.get("/status")
def status():
    return {"status": "online", "vlm_configured": MODELO_VLM, "ollama_host": OLLAMA_HOST}

@app.post("/start-organization")
def start_organization(background_tasks: BackgroundTasks):
    # Se ejecuta en segundo plano para no congelar la respuesta HTTP
    background_tasks.add_task(ejecutar_pipeline_organizacion)
    return {"message": "Proceso de organización cognitivo iniciado en segundo plano."}