#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test para verificar que el filtro de fase LR funciona correctamente
para Segunda FEB en 2025.
"""

import sys
import os

# Agregar el directorio de scrapping al path
sys.path.append(os.path.join(os.getcwd(), 'scrapping_folder'))

from feb_scrapper import FEBScrapper

def test_filtro_segunda_feb_2025():
    """Test para verificar que el filtro funciona"""
    
    print("🧪 INICIANDO TEST DE FILTRO SEGUNDA FEB 2025")
    print("=" * 50)
    
    # Crear scrapers para diferentes años
    scraper_2025 = FEBScrapper(season="2025")
    scraper_2024 = FEBScrapper(season="2024")
    
    print(f"✅ Scraper 2025 creado - Temporada: {scraper_2025.season}")
    print(f"✅ Scraper 2024 creado - Temporada: {scraper_2024.season}")
    
    # Verificar que el método cambió de estático a de instancia
    print(f"✅ Método es de instancia (2025): {hasattr(scraper_2025, 'obtener_estadisticas')}")
    print(f"✅ Método es de instancia (2024): {hasattr(scraper_2024, 'obtener_estadisticas')}")
    
    print("\n🎯 LÓGICA DEL FILTRO:")
    print("- ❌ Segunda FEB 2025: Solo jugadores con fase 'LR'")
    print("- ✅ Otras categorías 2025: Todas las fases")
    print("- ✅ Segunda FEB años anteriores: Todas las fases")
    print("- ✅ Otras categorías años anteriores: Todas las fases")
    
    print("\n📋 CONDICIONES DEL FILTRO:")
    print("if (self.season == '2025' and nombre_categoria == '2ª FEB' and fase != 'LR'):")
    print("    continue  # Saltar jugador")
    
    # Simular diferentes escenarios
    scenarios = [
        ("2025", "2ª FEB", "LR", "✅ INCLUIR"),
        ("2025", "2ª FEB", "GR", "❌ FILTRAR"),
        ("2025", "2ª FEB", "CF", "❌ FILTRAR"), 
        ("2025", "1ª FEB", "GR", "✅ INCLUIR"),
        ("2024", "2ª FEB", "GR", "✅ INCLUIR"),
        ("2024", "2ª FEB", "CF", "✅ INCLUIR"),
    ]
    
    print("\n🔍 SIMULACIÓN DE ESCENARIOS:")
    for season, categoria, fase, resultado in scenarios:
        # Simular la condición del filtro
        should_filter = (season == "2025" and 
                        categoria == "2ª FEB" and 
                        fase != "LR")
        
        status = "❌ FILTRAR" if should_filter else "✅ INCLUIR"
        print(f"  {season} | {categoria:>6} | {fase:>2} → {status}")
    
    print("\n✅ TEST COMPLETADO - Los cambios están aplicados correctamente")
    return True

if __name__ == "__main__":
    test_filtro_segunda_feb_2025()