"""
Script automático para generar base de datos histórica multi-temporada de FEB.

Ejecución automática semanal:
- Migra datos2.json (2024) a estructura con clave de año
- Scrappea nueva temporada (2025)
- Combina ambas temporadas en un JSON unificado
- Sobrescribe el archivo cada vez (sin interacción del usuario)

Uso:
    python multi_season_scraper.py

Estructura resultado (data/datos_historicos.json):
{
    "temporadas": {
        "2024": { datos completos temporada 2024 },
        "2025": { datos completos temporada 2025 }
    },
    "metadata": {
        "ultima_actualizacion": "2025-10-10T...",
        "temporadas_disponibles": ["2024", "2025"]
    }
}
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from feb_scrapper import FEBScrapper

# Configurar codificación UTF-8 para Windows
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')


class MultiSeasonDatabase:
    """Gestiona base de datos histórica multi-temporada de FEB."""
    
    def __init__(self, output_file: str = "data/datos_historicos.json"):
        self.output_file = output_file
        self.data = {
            "temporadas": {},
            "metadata": {
                "ultima_actualizacion": None,
                "temporadas_disponibles": []
            }
        }
    

    
    def migrar_datos2024(self, datos2_path: str = "data/datos2.json"):
        """Migra datos2.json a la estructura multi-temporada bajo clave 2024."""
        print(f"\n🔄 Migrando datos de temporada 2024 desde {datos2_path}...")
        print(f"   📍 Verificando si existe el archivo...")
        
        if not os.path.exists(datos2_path):
            print(f"❌ No se encontró {datos2_path}")
            print(f"   📁 Archivos disponibles en data/:")
            try:
                for file in os.listdir("data/"):
                    print(f"      - {file}")
            except:
                print("      No se pudo listar el directorio data/")
            return False
        
        print(f"   ✅ Archivo encontrado, procediendo a cargar...")
        
        try:
            print(f"   📖 Abriendo archivo JSON...")
            with open(datos2_path, 'r', encoding='utf-8') as f:
                print(f"   🔄 Parseando contenido JSON...")
                datos_2024 = json.load(f)
            
            print(f"   💾 Guardando datos en estructura multi-temporada...")
            # Guardar bajo clave "2024"
            self.data["temporadas"]["2024"] = datos_2024
            
            print(f"   🔧 Actualizando metadata...")
            # Actualizar metadata
            if "2024" not in self.data["metadata"]["temporadas_disponibles"]:
                self.data["metadata"]["temporadas_disponibles"].append("2024")
            
            print(f"✅ Datos 2024 migrados exitosamente")
            print(f"   - Categorías: {datos_2024.get('total_categorias', 0)}")
            print(f"   - Grupos: {datos_2024.get('total_grupos', 0)}")
            print(f"   - Equipos: {datos_2024.get('total_equipos', 0)}")
            print(f"   - Tamaño en memoria: ~{len(str(datos_2024))} caracteres")
            
            return True
            
        except Exception as e:
            print(f"❌ Error migrando datos 2024: {e}")
            print(f"   🔍 Tipo de error: {type(e).__name__}")
            return False
    
    def scrapear_temporada(self, year: str = "2025", pause: float = 1.0):
        """Scrapea datos de una temporada específica."""
        print(f"\n🌐 Iniciando scraping de temporada {year}...")
        print(f"   ⏱️  Pausa entre peticiones: {pause}s")
        
        try:
            print(f"   🔧 Creando instancia de FEBScrapper...")
            scraper = FEBScrapper(season=year, pause=pause)
            print(f"   ✅ FEBScrapper creado exitosamente")
            
            # Crear archivo temporal para el scraping
            temp_file = f"data/temp_{year}.json"
            print(f"   📁 Archivo temporal: {temp_file}")
            
            print(f"   🚀 INICIANDO SCRAPING - Esto puede tomar varios minutos...")
            print(f"   📡 Obteniendo equipos y estadísticas de FEB...")
            print(f"   ⚠️  NO INTERRUMPIR - El proceso está funcionando aunque parezca lento...")
            
            # Agregar callback de progreso si existe
            datos_temporada = scraper.crear_base_datos_completa_feb(nombre_archivo=temp_file)
            
            print(f"   ✅ Scraping completado, cargando archivo temporal...")
            # Cargar datos del archivo temporal
            with open(temp_file, 'r', encoding='utf-8') as f:
                print(f"   📖 Parseando JSON del archivo temporal...")
                datos_temporada = json.load(f)
            
            print(f"   💾 Guardando en estructura multi-temporada...")
            # Guardar en la estructura multi-temporada
            self.data["temporadas"][year] = datos_temporada
            
            print(f"   🔧 Actualizando metadata...")
            # Actualizar metadata
            if year not in self.data["metadata"]["temporadas_disponibles"]:
                self.data["metadata"]["temporadas_disponibles"].append(year)
            
            print(f"✅ Scraping de temporada {year} completado")
            print(f"   - Categorías: {datos_temporada.get('total_categorias', 0)}")
            print(f"   - Grupos: {datos_temporada.get('total_grupos', 0)}")
            print(f"   - Equipos: {datos_temporada.get('total_equipos', 0)}")
            print(f"   - Tamaño en memoria: ~{len(str(datos_temporada))} caracteres")
            
            print(f"   🧹 Limpiando archivo temporal...")
            # Limpiar archivo temporal
            if os.path.exists(temp_file):
                os.remove(temp_file)
                print(f"   ✅ Archivo temporal eliminado")
            
            return True
            
        except Exception as e:
            print(f"❌ Error scrapeando temporada {year}: {e}")
            print(f"   🔍 Tipo de error: {type(e).__name__}")
            print(f"   📍 Ubicación del error: línea {e.__traceback__.tb_lineno if e.__traceback__ else 'desconocida'}")
            return False
    
    def guardar_database(self):
        """Guarda la base de datos histórica."""
        print(f"\n💾 Guardando base de datos histórica en {self.output_file}...")
        
        try:
            print(f"   🕒 Actualizando timestamp...")
            # Actualizar metadata
            self.data["metadata"]["ultima_actualizacion"] = datetime.now().isoformat()
            self.data["metadata"]["temporadas_disponibles"].sort()
            
            print(f"   📁 Verificando/creando directorio...")
            # Crear directorio si no existe
            os.makedirs(os.path.dirname(self.output_file), exist_ok=True)
            
            print(f"   💾 Escribiendo archivo JSON...")
            # Guardar JSON
            with open(self.output_file, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
            
            print(f"   📊 Calculando estadísticas finales...")
            file_size = os.path.getsize(self.output_file)
            
            print(f"✅ Base de datos guardada exitosamente")
            print(f"   - Temporadas: {', '.join(self.data['metadata']['temporadas_disponibles'])}")
            print(f"   - Última actualización: {self.data['metadata']['ultima_actualizacion']}")
            print(f"   - Tamaño del archivo: {file_size / 1024 / 1024:.2f} MB")
            
            return True
            
        except Exception as e:
            print(f"❌ Error guardando base de datos: {e}")
            print(f"   🔍 Tipo de error: {type(e).__name__}")
            return False
    



def main():
    """Flujo principal automático: migración 2024 + scraping 2025 + guardado."""
    print("=" * 80)
    print("🏀 ACTUALIZACIÓN AUTOMÁTICA BASE DE DATOS MULTI-TEMPORADA FEB")
    print("=" * 80)
    print(f"📅 Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🖥️  Sistema: {os.name}")
    print(f"📂 Directorio actual: {os.getcwd()}")
    print("=" * 80)
    
    print(f"\n🔧 Inicializando base de datos...")
    # Inicializar base de datos (siempre desde cero)
    db = MultiSeasonDatabase(output_file="data/datos_historicos.json")
    print(f"   ✅ Base de datos inicializada")
    
    print("\n" + "=" * 80)
    print("🔄 PASO 1/3: Migrando datos temporada 2024...")
    print("=" * 80)
    start_time = datetime.now()
    resultado_migracion = db.migrar_datos2024(datos2_path="data/datos2.json")
    end_time = datetime.now()
    print(f"⏱️  Tiempo migración: {(end_time - start_time).total_seconds():.2f} segundos")
    
    if not resultado_migracion:
        print("❌ Falló la migración de datos 2024, pero continuando con scraping 2025...")
    
    print("\n" + "=" * 80)
    print("🔄 PASO 2/3: Scrapeando datos temporada 2025...")
    print("=" * 80)
    print("⚠️  ATENCIÓN: Este paso puede tomar 10-30 minutos dependiendo de la conexión")
    print("⚠️  El script NO está congelado, está haciendo peticiones HTTP a FEB")
    print("⚠️  Si ves este mensaje, el proceso está funcionando correctamente")
    print("-" * 80)
    
    start_time = datetime.now()
    resultado_scraping = db.scrapear_temporada(year="2025", pause=1.0)
    end_time = datetime.now()
    print(f"⏱️  Tiempo scraping: {(end_time - start_time).total_seconds():.2f} segundos")
    
    if not resultado_scraping:
        print("❌ Falló el scraping de temporada 2025")
        return False
    
    print("\n" + "=" * 80)
    print("💾 PASO 3/3: Guardando base de datos...")
    print("=" * 80)
    start_time = datetime.now()
    resultado_guardado = db.guardar_database()
    end_time = datetime.now()
    print(f"⏱️  Tiempo guardado: {(end_time - start_time).total_seconds():.2f} segundos")
    
    if not resultado_guardado:
        print("❌ Falló el guardado de la base de datos")
        return False
    
    # Mostrar resumen final
    print("\n" + "=" * 80)
    print("📊 RESUMEN FINAL")
    print("=" * 80)
    
    total_equipos = 0
    total_categorias = 0
    total_grupos = 0
    
    for year in sorted(db.data["temporadas"].keys()):
        datos = db.data["temporadas"][year]
        equipos = datos.get('total_equipos', 0)
        categorias = datos.get('total_categorias', 0)
        grupos = datos.get('total_grupos', 0)
        
        total_equipos += equipos
        total_categorias += categorias
        total_grupos += grupos
        
        print(f"\n🗓️  Temporada {year}:")
        print(f"   ├─ Categorías: {categorias}")
        print(f"   ├─ Grupos: {grupos}")
        print(f"   ├─ Equipos: {equipos}")
        print(f"   └─ Última actualización: {datos.get('fecha_actualizacion', 'N/A')}")
    
    print(f"\n📈 TOTALES ACUMULADOS:")
    print(f"   ├─ Temporadas: {len(db.data['temporadas'])}")
    print(f"   ├─ Categorías totales: {total_categorias}")
    print(f"   ├─ Grupos totales: {total_grupos}")
    print(f"   └─ Equipos totales: {total_equipos}")
    
    print("\n" + "=" * 80)
    print("✅ ACTUALIZACIÓN COMPLETADA EXITOSAMENTE")
    print(f"📁 Archivo generado: {db.output_file}")
    print(f"📅 Hora finalización: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    
    return True


if __name__ == "__main__":
    main()
