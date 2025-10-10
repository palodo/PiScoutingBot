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
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from feb_scrapper import FEBScrapper


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
        
        if not os.path.exists(datos2_path):
            print(f"❌ No se encontró {datos2_path}")
            return False
        
        try:
            with open(datos2_path, 'r', encoding='utf-8') as f:
                datos_2024 = json.load(f)
            
            # Guardar bajo clave "2024"
            self.data["temporadas"]["2024"] = datos_2024
            
            # Actualizar metadata
            if "2024" not in self.data["metadata"]["temporadas_disponibles"]:
                self.data["metadata"]["temporadas_disponibles"].append("2024")
            
            print(f"✅ Datos 2024 migrados exitosamente")
            print(f"   - Categorías: {datos_2024.get('total_categorias', 0)}")
            print(f"   - Grupos: {datos_2024.get('total_grupos', 0)}")
            print(f"   - Equipos: {datos_2024.get('total_equipos', 0)}")
            
            return True
            
        except Exception as e:
            print(f"❌ Error migrando datos 2024: {e}")
            return False
    
    def scrapear_temporada(self, year: str = "2025", pause: float = 1.0):
        """Scrapea datos de una temporada específica."""
        print(f"\n🌐 Iniciando scraping de temporada {year}...")
        
        try:
            scraper = FEBScrapper(season=year, pause=pause)
            
            # Crear archivo temporal para el scraping
            temp_file = f"data/temp_{year}.json"
            
            print(f"   Obteniendo equipos y estadísticas...")
            datos_temporada = scraper.crear_base_datos_completa_feb(nombre_archivo=temp_file)
            
            # Cargar datos del archivo temporal
            with open(temp_file, 'r', encoding='utf-8') as f:
                datos_temporada = json.load(f)
            
            # Guardar en la estructura multi-temporada
            self.data["temporadas"][year] = datos_temporada
            
            # Actualizar metadata
            if year not in self.data["metadata"]["temporadas_disponibles"]:
                self.data["metadata"]["temporadas_disponibles"].append(year)
            
            print(f"✅ Scraping de temporada {year} completado")
            print(f"   - Categorías: {datos_temporada.get('total_categorias', 0)}")
            print(f"   - Grupos: {datos_temporada.get('total_grupos', 0)}")
            print(f"   - Equipos: {datos_temporada.get('total_equipos', 0)}")
            
            # Limpiar archivo temporal
            if os.path.exists(temp_file):
                os.remove(temp_file)
            
            return True
            
        except Exception as e:
            print(f"❌ Error scrapeando temporada {year}: {e}")
            return False
    
    def guardar_database(self):
        """Guarda la base de datos histórica."""
        print(f"\n💾 Guardando base de datos histórica en {self.output_file}...")
        
        try:
            # Actualizar metadata
            self.data["metadata"]["ultima_actualizacion"] = datetime.now().isoformat()
            self.data["metadata"]["temporadas_disponibles"].sort()
            
            # Crear directorio si no existe
            os.makedirs(os.path.dirname(self.output_file), exist_ok=True)
            
            # Guardar JSON
            with open(self.output_file, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
            
            print(f"✅ Base de datos guardada exitosamente")
            print(f"   - Temporadas: {', '.join(self.data['metadata']['temporadas_disponibles'])}")
            print(f"   - Última actualización: {self.data['metadata']['ultima_actualizacion']}")
            
            return True
            
        except Exception as e:
            print(f"❌ Error guardando base de datos: {e}")
            return False
    



def main():
    """Flujo principal automático: migración 2024 + scraping 2025 + guardado."""
    print("=" * 80)
    print("🏀 ACTUALIZACIÓN AUTOMÁTICA BASE DE DATOS MULTI-TEMPORADA FEB")
    print("=" * 80)
    print(f"📅 Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    
    # Inicializar base de datos (siempre desde cero)
    db = MultiSeasonDatabase(output_file="data/datos_historicos.json")
    
    print("\n🔄 PASO 1/3: Migrando datos temporada 2024...")
    print("-" * 80)
    db.migrar_datos2024(datos2_path="data/datos2.json")
    
    print("\n🔄 PASO 2/3: Scrapeando datos temporada 2025...")
    print("-" * 80)
    db.scrapear_temporada(year="2025", pause=1.0)
    
    print("\n💾 PASO 3/3: Guardando base de datos...")
    print("-" * 80)
    db.guardar_database()
    
    # Mostrar resumen final
    print("\n" + "=" * 80)
    print("📊 RESUMEN FINAL")
    print("=" * 80)
    
    for year in sorted(db.data["temporadas"].keys()):
        datos = db.data["temporadas"][year]
        print(f"\n🗓️  Temporada {year}:")
        print(f"   ├─ Categorías: {datos.get('total_categorias', 0)}")
        print(f"   ├─ Grupos: {datos.get('total_grupos', 0)}")
        print(f"   ├─ Equipos: {datos.get('total_equipos', 0)}")
        print(f"   └─ Última actualización: {datos.get('fecha_actualizacion', 'N/A')}")
    
    print("\n" + "=" * 80)
    print("✅ ACTUALIZACIÓN COMPLETADA EXITOSAMENTE")
    print(f"📁 Archivo generado: {db.output_file}")
    print("=" * 80)


if __name__ == "__main__":
    main()
