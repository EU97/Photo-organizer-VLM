# app/config.py
import os
from datetime import timedelta

class Settings:
    # URL del contenedor o servidor de Ollama
    OLLAMA_HOST: str = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    
    # Modelo visual a utilizar (ej: qwen2-vl:7b, llava, moondream)
    MODELO_VLM: str = os.getenv("MODELO_VLM", "qwen2-vl:7b")
    
    # Rutas absolutas dentro del contenedor (mapeadas en el docker-compose)
    CARPETA_ORIGEN: str = os.getenv("CARPETA_ORIGEN", "/data/origen")
    CARPETA_DESTINO: str = os.getenv("CARPETA_DESTINO", "/data/destino")
    
    # Parámetros del algoritmo de agrupamiento
    UMBRAL_TIEMPO: timedelta = timedelta(hours=int(os.getenv("UMBRAL_HORAS_CLUSTER", "36")))
    MIN_FOTOS_EVENTO: int = int(os.getenv("MIN_FOTOS_EVENTO", "10"))
    
    # Mapeo de meses para la nomenclatura de carpetas finales
    MESES_ESPANOL: dict = {
        1: "01_Enero", 2: "02_Febrero", 3: "03_Marzo", 4: "04_Abril",
        5: "05_Mayo", 6: "06_Junio", 7: "07_Julio", 8: "08_Agosto",
        9: "09_Septiembre", 10: "10_Octubre", 11: "11_Noviembre", 12: "12_Diciembre"
    }

# Instancia única para importar en el resto de la aplicación (Patrón Singleton)
settings = Settings()