import json
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
import numpy as np
import io
from PIL import Image as PILImage
from pathlib import Path

def normalizar_dataframe(df):
    """
    Normaliza el dataframe renombrando columnas a nombres cortos y calculando estadísticas derivadas.
    
    Args:
        df: DataFrame con datos de equipos desde el JSON
        
    Returns:
        DataFrame normalizado con columnas renombradas y estadísticas calculadas
    """
    # Mapeo de nombres largos a nombres cortos
    column_mapping = {
        'nombre': 'Equipo',
        'url_equipo': 'URL_Equipo',
        'url_estadisticas': 'URL_Stats',
        'jugadores': 'Jugadores',
        'liga': 'Liga',
        'categoria': 'Categoria',
        'informacion_general.puntos_favor': 'PTS_Favor',
        'informacion_general.puntos_contra': 'PTS_Contra',
        'informacion_general.partidos_jugados': 'PJ',
        'informacion_general.partidos_ganados': 'PG',
        'informacion_general.partidos_perdidos': 'PP',
        'informacion_general.diferencia_puntos': 'Diff_PTS',
        'resumen_equipo.total_jugadores': 'Total_Jugadores',
        'resumen_equipo.puntos_totales': 'PTS_Total',
        'resumen_equipo.minutos_totales': 'MIN_Total',
        'resumen_equipo.rebotes_totales': 'REB_Total',
        'resumen_equipo.rebotes_ofensivos_totales': 'OREB_Total',
        'resumen_equipo.rebotes_defensivos_totales': 'DREB_Total',
        'resumen_equipo.asistencias_totales': 'AST_Total',
        'resumen_equipo.valoracion_total': 'VAL_Total',
        'resumen_equipo.fg2a_total': 'FG2A',
        'resumen_equipo.fg2m_total': 'FG2M',
        'resumen_equipo.fga_total': 'FGA',
        'resumen_equipo.fgm_total': 'FGM',
        'resumen_equipo.fg3a_total': 'FG3A',
        'resumen_equipo.fg3m_total': 'FG3M',
        'resumen_equipo.fta_total': 'FTA',
        'resumen_equipo.ftm_total': 'FTM',
        'resumen_equipo.perdidas_totales': 'TO',
        'resumen_equipo.recuperaciones_totales': 'STL',
        'resumen_equipo.promedio_puntos_por_jugador': 'PTS_Avg',
        'resumen_equipo.promedio_minutos_por_jugador': 'MIN_Avg',
        'resumen_equipo.promedio_valoracion_por_jugador': 'VAL_Avg'
    }
    
    # Renombrar columnas
    df = df.rename(columns=column_mapping)
    
    # Calcular porcentajes de tiro
    df['FG%'] = (df['FGM'] / df['FGA'] * 100).round(1)
    df['FG2%'] = (df['FG2M'] / df['FG2A'] * 100).round(1)
    df['FG3%'] = (df['FG3M'] / df['FG3A'] * 100).round(1)
    df['FT%'] = (df['FTM'] / df['FTA'] * 100).round(1)
    df['Win%'] = (df['PG'] / df['PJ'] * 100).round(1)
    
    # Calcular estadísticas por partido
    df['PTS/PJ'] = (df['PTS_Favor'] / df['PJ']).round(1)
    df['REB/PJ'] = (df['REB_Total'] / df['PJ']).round(1)
    df['OREB/PJ'] = (df['OREB_Total'] / df['PJ']).round(1)
    df['DREB/PJ'] = (df['DREB_Total'] / df['PJ']).round(1)
    df['AST/PJ'] = (df['AST_Total'] / df['PJ']).round(1)
    df['TO/PJ'] = (df['TO'] / df['PJ']).round(1)
    df['STL/PJ'] = (df['STL'] / df['PJ']).round(1)
    
    # Porcentajes de rebotes
    df['OREB%'] = ((df['OREB_Total'] / df['REB_Total']) * 100).round(1)
    df['DREB%'] = ((df['DREB_Total'] / df['REB_Total']) * 100).round(1)
    
    return df


def cargar_logos_equipos(df):
    """
    Carga los logos de los equipos y añade las columnas 'logo_path' y 'logo_url' al dataframe.
    
    Args:
        df: DataFrame con columnas 'Equipo' y 'URL_Equipo'
        
    Returns:
        DataFrame con las nuevas columnas logo_path y logo_url añadidas
    """
    import os, re, unicodedata, requests
    from pathlib import Path
    
    # Configuración
    IMAGES_DIR = Path("imagenes")
    IMAGES_DIR.mkdir(exist_ok=True)
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0"})
    
    def safe_filename(name):
        """Convierte nombre de equipo a nombre de archivo seguro"""
        n = unicodedata.normalize("NFKD", name)
        n = "".join(c for c in n if not unicodedata.combining(c))
        return re.sub(r"[^A-Za-z0-9._ -]", "", n).strip().replace(" ", "_") or "equipo"
    
    def extraer_team_id(url):
        """Extrae el ID del equipo de la URL"""
        m = re.search(r"[?&]i=(\d+)", url)
        return m.group(1) if m else None
    
    def obtener_logo(equipo, url_equipo):
        """Descarga el logo del equipo si no existe y retorna la ruta local y URL"""
        fn = IMAGES_DIR / f"{safe_filename(equipo)}.jpg"
        
        # Si ya existe el archivo, retornar ruta local y URL
        if fn.exists(): 
            tid = extraer_team_id(url_equipo)
            logo_url = f"https://imagenes.feb.es/Imagen.aspx?i={tid}&ti=1" if tid else None
            return str(fn), logo_url
        
        # Descargar logo si no existe
        tid = extraer_team_id(url_equipo)
        if not tid: 
            return None, None
            
        logo_url = f"https://imagenes.feb.es/Imagen.aspx?i={tid}&ti=1"
        try:
            r = session.get(logo_url, timeout=15)
            r.raise_for_status()
            fn.write_bytes(r.content)
            return str(fn), logo_url
        except Exception as e:
            print(f"Error descargando logo para {equipo}: {e}")
            return None, None
    
    # Crear una copia del dataframe para no modificar el original
    df_copy = df.copy()
    
    # Añadir columnas de logos
    logos_data = [obtener_logo(row.Equipo, row.URL_Equipo) for _, row in df_copy.iterrows()]
    df_copy["logo_path"], df_copy["logo_url"] = zip(*logos_data)
    
    return df_copy


def calcular_estadisticas_avanzadas(df):
    """
    Calcula estadísticas avanzadas de baloncesto: Ritmo, Offensive Rating y Defensive Rating.
    
    Args:
        df: DataFrame con estadísticas básicas de equipos
        
    Returns:
        DataFrame con las nuevas columnas de estadísticas avanzadas añadidas
    """
    # Crear una copia del dataframe para no modificar el original
    df_copy = df.copy()
    
    # Calcular posesiones utilizando rebotes ofensivos reales
    df_copy['Posesiones'] = (df_copy['FGA'] - df_copy['OREB_Total'] + df_copy['TO'] + 0.4 * df_copy['FTA']).round(1)
    
    # Ritmo (Pace) - Posesiones por partido
    df_copy['Ritmo'] = (df_copy['Posesiones'] / df_copy['PJ']).round(1)
    
    # Offensive Rating - Puntos anotados por cada 100 posesiones
    df_copy['ORtg'] = ((df_copy['PTS_Favor'] / df_copy['Posesiones']) * 100).round(1)
    
    # Defensive Rating - Puntos permitidos por cada 100 posesiones
    df_copy['DRtg'] = ((df_copy['PTS_Contra'] / df_copy['Posesiones']) * 100).round(1)
    
    # Net Rating - Diferencia entre ORtg y DRtg
    df_copy['NetRtg'] = (df_copy['ORtg'] - df_copy['DRtg']).round(1)
    
    # True Shooting Percentage
    df_copy['TS%'] = ((df_copy['PTS_Favor'] / (2 * (df_copy['FGA'] + 0.44 * df_copy['FTA']))) * 100).round(1)
    
    # Ratio Asistencias/Pérdidas
    df_copy['AST/TO'] = (df_copy['AST_Total'] / df_copy['TO']).round(2)
    
    # Efectividad en rebotes ofensivos (% de rebotes ofensivos sobre tiros fallados)
    total_misses = df_copy['FGA'] - df_copy['FGM']
    df_copy['OREB_Rate'] = ((df_copy['OREB_Total'] / total_misses) * 100).round(1)
    
    
    
   
    
    return df_copy




# Función para normalizar estadísticas de jugadores individuales
def normalizar_estadisticas_jugadores(df_jugadores):
    """
    Normaliza las estadísticas de jugadores individuales con nombres cortos y estadísticas calculadas.
    
    Args:
        df_jugadores: DataFrame con estadísticas de jugadores
        
    Returns:
        DataFrame normalizado con estadísticas calculadas
    """
    df = df_jugadores.copy()
    
    # Renombrar columnas principales
    column_mapping = {
        'nombre': 'Jugador',
        'enlace': 'Enlace',
        'fase': 'Fase',
        'partidos': 'PJ',
        'minutos_segundos': 'MIN',
        'puntos': 'PTS',
        'tiros_dos_made': 'FG2M',
        'tiros_dos_attempted': 'FG2A',
        'tiros_tres_made': 'FG3M',
        'tiros_tres_attempted': 'FG3A',
        'tiros_campo_made': 'FGM',
        'tiros_campo_attempted': 'FGA',
        'tiros_libres_made': 'FTM',
        'tiros_libres_attempted': 'FTA',
        'rebotes_defensivos': 'DREB',
        'rebotes_ofensivos': 'OREB',
        'rebotes_totales': 'REB',
        'asistencias': 'AST',
        'perdidas': 'TO',
        'recuperaciones': 'STL',
        'tapones_favor': 'BLK',
        'tapones_contra': 'BLKA',
        'faltas_cometidas': 'PF',
        'faltas_recibidas': 'PFD',
        'valoracion': 'VAL'
    }
    
    # Aplicar renombrado solo a columnas que existen
    existing_mapping = {k: v for k, v in column_mapping.items() if k in df.columns}
    df = df.rename(columns=existing_mapping)
    
    # Extraer ID único del jugador desde el enlace
    df['ID'] = df['Enlace'].str.extract(r'c=(\d+)$')[0]
    
    # Calcular estadísticas básicas por partido
    df['PTS/PJ'] = (df['PTS'] / df['PJ']).round(1)
    df['REB/PJ'] = (df['REB'] / df['PJ']).round(1)
    df['AST/PJ'] = (df['AST'] / df['PJ']).round(1)
    df['TO/PJ'] = (df['TO'] / df['PJ']).round(1)
    df['STL/PJ'] = (df['STL'] / df['PJ']).round(1)
    df['VAL/PJ'] = (df['VAL'] / df['PJ']).round(1)
    df['OREB/PJ'] = (df['OREB'] / df['PJ']).round(1)
    df['FG3A/PJ'] = (df['FG3A'] / df['PJ']).round(1)
    df['FTA/PJ'] = (df['FTA'] / df['PJ']).round(1)  # Añadir tiros libres intentados por partido
    
    # Calcular porcentajes de tiro
    if 'FG2M' in df.columns and 'FG2A' in df.columns:
        df['FG2%'] = ((df['FG2M'] / df['FG2A']) * 100).round(1)
    if 'FG3M' in df.columns and 'FG3A' in df.columns:
        df['FG3%'] = ((df['FG3M'] / df['FG3A']) * 100).round(1)
    if 'FTM' in df.columns and 'FTA' in df.columns:
        df['FT%'] = ((df['FTM'] / df['FTA']) * 100).round(1)
    # FG total
    if 'FGM' in df.columns and 'FGA' in df.columns:
        df['FG%'] = ((df['FGM'] / df['FGA']) * 100).round(1)

    # True Shooting Percentage
    if 'PTS' in df.columns and 'FGA' in df.columns and 'FTA' in df.columns:
        df['TS%'] = ((df['PTS'] / (2 * (df['FGA'] + 0.44 * df['FTA']))) * 100).round(1)
    
    # Usage Percentage - cálculo correcto y simplificado
    if 'FGA' in df.columns and 'FTA' in df.columns and 'TO' in df.columns and 'MIN' in df.columns and 'PJ' in df.columns:
        df['USG%'] = 0.0  # Inicializar columna
        
        for i in df.index:
            pj = df.loc[i, 'PJ']
            if pj > 0:  # Solo calcular si el jugador ha jugado partidos
                # Estadísticas por partido
                fga_pg = df.loc[i, 'FGA'] / pj
                fta_pg = df.loc[i, 'FTA'] / pj
                to_pg = df.loc[i, 'TO'] / pj
                min_pg = df.loc[i, 'MIN'] / 60.0 / pj  # Convertir segundos a minutos por partido
                
                if min_pg > 0:  # Evitar división por cero
                    # Posesiones por partido
                    posesiones_pg = fga_pg + 0.44 * fta_pg + to_pg
                    
                    # USG% = (posesiones por minuto) * 40 minutos * factor de escala
                    usg_rate = (posesiones_pg / min_pg) * 40 * 0.5
                    df.loc[i, 'USG%'] = round(min(usg_rate, 99.9), 1)
                else:
                    df.loc[i, 'USG%'] = 0.0
            else:
                df.loc[i, 'USG%'] = 0.0
    
    return df


def crear_rankings_jugadores(df_jugadores):
    """
    Crea rankings de los mejores jugadores en diferentes categorías estadísticas por partido jugado.
    Utiliza las columnas /PJ ya calculadas en el DataFrame.
    Incluye ID y Enlace para poder acceder al sistema de caché de fotos.
    
    Args:
        df_jugadores: DataFrame con estadísticas normalizadas de jugadores
        
    Returns:
        dict: Diccionario con rankings por categoría (por partido)
    """
    rankings = {}
    
    # Columnas comunes para todos los rankings (incluir ID y Enlace para el sistema de caché)
    columnas_base = ['Jugador', 'ID', 'Enlace', 'PJ', 'foto_path']
    
    # Top 7 en Puntos por partido
    rankings['Puntos'] = df_jugadores.nlargest(7, 'PTS/PJ')[columnas_base + ['PTS/PJ']].copy()
    
    # Top 7 en Valoración por partido
    rankings['Valoracion'] = df_jugadores.nlargest(7, 'VAL/PJ')[columnas_base + ['VAL/PJ']].copy()
    
    # Top 7 en Rebotes por partido
    rankings['Rebotes'] = df_jugadores.nlargest(7, 'REB/PJ')[columnas_base + ['REB/PJ']].copy()
    
    # Top 7 en Rebotes ofensivos por partido
    rankings['Rebotes_Ofensivos'] = df_jugadores.nlargest(7, 'OREB/PJ')[columnas_base + ['OREB/PJ']].copy()
    
    # Top 7 en Robos por partido
    rankings['Robos'] = df_jugadores.nlargest(7, 'STL/PJ')[columnas_base + ['STL/PJ']].copy()
    
    # Top 7 en Tiros de 3 por partido (con su FG3%)
    rankings['Triples_Intentados'] = df_jugadores.nlargest(7, 'FG3A/PJ')[columnas_base + ['FG3A/PJ', 'FG3%']].copy()
    
    # Top 7 en Porcentaje de Uso (USG%)
    if 'USG%' in df_jugadores.columns:
        rankings['Uso'] = df_jugadores.nlargest(7, 'USG%')[columnas_base + ['USG%']].copy()
    
    # Top 7 en Asistencias por partido
    rankings['Asistencias'] = df_jugadores.nlargest(7, 'AST/PJ')[columnas_base + ['AST/PJ']].copy()
    
    # Top 7 en Porcentaje de Tiros Libres (FT%)
    # Filtrar jugadores que han tirado al menos 1 tiro libre por partido para evitar porcentajes engañosos
    df_ft_filter = df_jugadores[df_jugadores['FTA/PJ'] >= 1.0].copy()
    if not df_ft_filter.empty:
        rankings['Tiros_Libres'] = df_ft_filter.nlargest(7, 'FT%')[columnas_base + ['FT%', 'FTA/PJ']].copy()
    else:
        # Si nadie cumple el criterio, usar todos los jugadores
        rankings['Tiros_Libres'] = df_jugadores.nlargest(7, 'FT%')[columnas_base + ['FT%', 'FTA/PJ']].copy()
    
    # Top 7 en True Shooting Percentage (TS%) - Estadística avanzada
    # Filtrar jugadores con al menos 5 puntos por partido para mayor relevancia
    df_ts_filter = df_jugadores[df_jugadores['PTS/PJ'] >= 5.0].copy()
    if not df_ts_filter.empty:
        rankings['True_Shooting'] = df_ts_filter.nlargest(7, 'TS%')[columnas_base + ['TS%', 'PTS/PJ']].copy()
    else:
        # Si nadie cumple el criterio, usar todos los jugadores
        rankings['True_Shooting'] = df_jugadores.nlargest(7, 'TS%')[columnas_base + ['TS%', 'PTS/PJ']].copy()
    
    return rankings


def descargar_fotos_jugadores(df_jugadores, equipo_actual):
    """
    Procesa fotos para jugadores usando el sistema de caché centralizado.
    Ya no descarga fotos, solo retorna las rutas del caché en data/player_photos_cache/
    Si la foto no está en caché, retorna la ruta del caché donde DEBERÍA estar,
    para que get_player_photo_buffer() la descargue bajo demanda.
    
    Args:
        df_jugadores: DataFrame con estadísticas de jugadores normalizadas
        equipo_actual: Nombre del equipo (ya no se usa, mantenido por compatibilidad)
        
    Returns:
        DataFrame con columna 'foto_path' actualizada con rutas del caché
    """
    import os, re
    from pathlib import Path

    # Usar caché centralizado
    CACHE_DIR = Path('data') / 'player_photos_cache'
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    
    # Placeholder por si no existe foto
    placeholder_path = Path('data') / 'player_whitebg.jpg'

    # Procesar cada jugador
    out_paths = []
    for _, row in df_jugadores.iterrows():
        # Intentar obtener el ID directamente si ya está en el DataFrame
        player_code = row.get('ID', None)
        
        # Si no hay ID, extraer del enlace
        if not player_code or pd.isna(player_code):
            enlace = row.get('Enlace', '') or ''
            if 'c=' in enlace:
                m = re.search(r'c=(\d+)', enlace)
                if m:
                    player_code = m.group(1)
        
        # Si tenemos código, usar ruta del caché (exista o no el archivo)
        # Si no existe, get_player_photo_buffer() lo descargará bajo demanda
        if player_code:
            cached_photo_path = CACHE_DIR / f"{player_code}.jpg"
            out_paths.append(str(cached_photo_path))
        else:
            # Si no hay código, usar placeholder
            if placeholder_path.exists():
                out_paths.append(str(placeholder_path))
            else:
                out_paths.append("")  # Ruta vacía si no hay nada disponible
    
    # Añadir o actualizar columna al dataframe
    df_resultado = df_jugadores.copy()
    df_resultado['foto_path'] = out_paths
    
    return df_resultado



# Función específica para recalcular USG% correctamente
def calcular_usg_correcto(df):
    """
    Calcula USG% usando la fórmula que probamos manualmente
    """
    df_copy = df.copy()
    df_copy['USG%'] = 0.0
    
    for i in df_copy.index:
        pj = df_copy.loc[i, 'PJ']
        if pj > 0:
            fga = df_copy.loc[i, 'FGA']
            fta = df_copy.loc[i, 'FTA'] 
            to = df_copy.loc[i, 'TO']
            minutos = df_copy.loc[i, 'MIN']
            
            # Calcular por partido
            fga_pg = fga / pj
            fta_pg = fta / pj
            to_pg = to / pj
            min_pg = minutos / 60 / pj  # Convertir segundos a minutos por partido
            
            if min_pg > 0:
                # Posesiones por partido
                posesiones_pg = fga_pg + 0.44 * fta_pg + to_pg
                
                # USG% = (posesiones por minuto) * 40 min * factor de escala
                usg_rate = (posesiones_pg / min_pg) * 40 * 0.5
                df_copy.loc[i, 'USG%'] = round(min(usg_rate, 99.9), 1)
    
    return df_copy


def generar_pdf(JSON_PATH, liga, grupo, equipo):
    # 1) Cargar JSON
    with open(JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    # 2) Navegar por las claves EXACTAS
    nodo_categoria = data["categorias"][liga]
    nodo_grupo = nodo_categoria["grupos"][grupo]
    equipos = nodo_grupo["equipos"]


    df_all = pd.json_normalize(equipos, sep=".")
    df_grupo = normalizar_dataframe(df_all)



    # Aplicar funciones de procesamiento al dataframe de grupo
    df_grupo = cargar_logos_equipos(df_grupo)
    df_grupo = calcular_estadisticas_avanzadas(df_grupo)

    # Extraer estadísticas individuales de los jugadores del equipo seleccionado
    equipo_data = df_grupo[df_grupo['Equipo'] == equipo].iloc[0]
    jugadores_raw = equipo_data['Jugadores']

    # Convertir lista de jugadores a DataFrame
    df_jugadores = pd.json_normalize(jugadores_raw)

    
    # Aplicar normalización a las estadísticas de jugadores
    df_jugadores_norm = normalizar_estadisticas_jugadores(df_jugadores)

    # Descargar fotos de jugadores
    df_jugadores_norm = descargar_fotos_jugadores(df_jugadores_norm, equipo)

    # Filtrar jugadores según porcentaje de partidos jugados
    # Obtener el total de partidos del equipo
    partidos_equipo = equipo_data['PJ']
    umbral_partidos = partidos_equipo * 0.25  # 25% de los partidos
    #
    # Dividir jugadores en principales y apoyo
    df_principales = df_jugadores_norm[df_jugadores_norm['PJ'] > umbral_partidos].copy()
    df_apoyo = df_jugadores_norm[df_jugadores_norm['PJ'] <= umbral_partidos].copy()

    # Crear rankings de jugadores (solo jugadores principales)
    rankings = crear_rankings_jugadores(df_principales)


    # Recalcular estadísticas con USG% corregido
    #print("Recalculando estadísticas con USG% corregido...")
    df_jugadores_norm = normalizar_estadisticas_jugadores(df_jugadores)

    # Recrear df_principales y df_apoyo con los nuevos cálculos
    df_principales = df_jugadores_norm[df_jugadores_norm['PJ'] > umbral_partidos].copy()
    df_apoyo = df_jugadores_norm[df_jugadores_norm['PJ'] <= umbral_partidos].copy()

    
    
    # Aplicar la nueva función
    
    df_jugadores_norm_corrigido = calcular_usg_correcto(df_jugadores_norm)

    # Verificar los resultados
    
    principales_corregidos = df_jugadores_norm_corrigido[df_jugadores_norm_corrigido['PJ'] > umbral_partidos]
    #print(principales_corregidos[['Jugador', 'USG%', 'FGA', 'FTA', 'TO', 'PJ']].head(10))

    # Actualizar los DataFrames principales con USG% corregido
    df_jugadores_norm = df_jugadores_norm_corrigido.copy()
    df_principales = df_jugadores_norm[df_jugadores_norm['PJ'] > umbral_partidos].copy()
    df_apoyo = df_jugadores_norm[df_jugadores_norm['PJ'] <= umbral_partidos].copy()

    df_jugadores_norm = descargar_fotos_jugadores(df_jugadores_norm, equipo)

    # Paso 2: Recrear DataFrames principales
    df_principales = df_jugadores_norm[df_jugadores_norm['PJ'] > umbral_partidos].copy()
    df_apoyo = df_jugadores_norm[df_jugadores_norm['PJ'] <= umbral_partidos].copy()

    rankings = crear_rankings_jugadores(df_principales)


    def crear_rankings_equipos(df_equipos):
        """
        Crea rankings de estadísticas de equipos.
        
        Args:
            df_equipos: DataFrame con estadísticas de todos los equipos del grupo
            
        Returns:
            dict: Diccionario con rankings de equipos por categoría
        """
        rankings = {}
        
        # Solo procesar si hay más de un equipo
        if len(df_equipos) <= 1:
            return rankings
            
        # Anotación (Puntos por partido)
        rankings['Puntos_Equipo'] = df_equipos.sort_values('PTS/PJ', ascending=False).reset_index(drop=True)
        
        # Triples por partido con porcentaje
        rankings['Triples_Equipo'] = df_equipos.sort_values('FG3A', ascending=False).reset_index(drop=True)
        
        # Rebotes por partido
        rankings['Rebotes_Equipo'] = df_equipos.sort_values('REB/PJ', ascending=False).reset_index(drop=True)
        
        # Asistencias por partido
        rankings['Asistencias_Equipo'] = df_equipos.sort_values('AST/PJ', ascending=False).reset_index(drop=True)
        
        # Pérdidas por partido (ascendente porque menos es mejor)
        rankings['Perdidas_Equipo'] = df_equipos.sort_values('TO/PJ', ascending=True).reset_index(drop=True)
        
        # Porcentaje de victorias
        rankings['Victorias_Equipo'] = df_equipos.sort_values('Win%', ascending=False).reset_index(drop=True)
        
        # Porcentaje de tiros de campo
        rankings['FG_Percentage_Equipo'] = df_equipos.sort_values('FG%', ascending=False).reset_index(drop=True)
        
        # Porcentaje de triples
        rankings['FG3_Percentage_Equipo'] = df_equipos.sort_values('FG3%', ascending=False).reset_index(drop=True)
        
        # Porcentaje de tiros libres
        rankings['FT_Percentage_Equipo'] = df_equipos.sort_values('FT%', ascending=False).reset_index(drop=True)
        
        # Rebotes ofensivos por partido
        rankings['Rebotes_Ofensivos_Equipo'] = df_equipos.sort_values('OREB/PJ', ascending=False).reset_index(drop=True)
        
        # Robos por partido
        rankings['Robos_Equipo'] = df_equipos.sort_values('STL/PJ', ascending=False).reset_index(drop=True)
        
        # Defensive Rating (menor es mejor)
        if 'DefRtg' in df_equipos.columns:
            rankings['Defensa_Equipo'] = df_equipos.sort_values('DefRtg', ascending=True).reset_index(drop=True)
        
        # Offensive Rating (mayor es mejor)
        if 'OffRtg' in df_equipos.columns:
            rankings['Ataque_Equipo'] = df_equipos.sort_values('OffRtg', ascending=False).reset_index(drop=True)
            
        return rankings

    def crear_pagina_rankings_equipos(story, rankings_equipos, df_equipos, equipo_seleccionado, styles):
        """
        Crea una página de rankings de equipos en formato compacto
        """
        from reportlab.lib.units import inch, cm
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
        from reportlab.platypus import Paragraph, Spacer, Table, TableStyle, PageBreak, Image
        from reportlab.lib.styles import ParagraphStyle
        from pathlib import Path
        import os
        
        # Solo crear la página si hay rankings de equipos y más de un equipo
        if not rankings_equipos or len(df_equipos) <= 1:
            return
            
        # Añadir salto de página
        story.append(PageBreak())
        
        # Título principal
        titulo_style = ParagraphStyle(
            'TituloEquipos',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#2d3748'),
            alignment=TA_CENTER,
            spaceAfter=20,
            fontName='Helvetica-Bold',
        )
        
        titulo = Paragraph("RANKINGS DE EQUIPOS", titulo_style)
        story.append(titulo)
        
        # Línea decorativa
        linea_style = ParagraphStyle(
            'LineaDecorativa',
            parent=styles['Normal'],
            fontSize=12,
            textColor=colors.HexColor('#e2e8f0'),
            alignment=TA_CENTER,
            spaceAfter=15,
        )
        linea = Paragraph("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", linea_style)
        story.append(linea)

        def crear_ranking_equipo_compacto(titulo, categoria, df_ranking, stat_col, format_func=None, ascending=True, ancho_personalizado=None):
            """Crea un ranking de equipos compacto con formato uniforme"""
            
            # Configuración de colores por categoría
            colores = {
                'Puntos': '#e53e3e',
                'Triples': '#d69e2e',
                'Rebotes': '#3182ce',
                'Asistencias': '#38a169',
                'Pérdidas': '#805ad5',
                'Victorias': '#dd6b20',
                'Tiro de Campo': '#319795',
                'Defensa': '#c53030',
                'Ataque': '#2b6cb0'
            }
            
            color = colores.get(categoria, '#4a5568')
            
            # Usar ancho personalizado si se proporciona, sino ancho estándar
            if ancho_personalizado:
                tabla_width = ancho_personalizado
                col_widths_fila = [0.2*inch, ancho_personalizado-1.0*inch, 0.6*inch]  # Más margen a la derecha
                max_chars = int(((ancho_personalizado/inch) - 1.0) * 8)  # Ajustar caracteres
            else:
                col_widths_fila = [0.2*inch, 1.0*inch, 0.5*inch]
                tabla_width = 1.8*inch
                max_chars = 12
            
            # Crear datos de la tabla con estilo uniforme
            data = [
                [Paragraph(f"<b>{titulo}</b>", ParagraphStyle('header', fontSize=9, textColor=colors.HexColor(color), alignment=TA_CENTER))]
            ]
            
            # Obtener posición del equipo seleccionado
            posicion_equipo = None
            for i, (_, equipo_row) in enumerate(df_ranking.iterrows()):
                if equipo_row['Equipo'] == equipo_seleccionado:
                    posicion_equipo = i + 1
                    break
            
            # Mostrar top 3 + contexto del equipo seleccionado
            equipos_mostrar = []
            
            # Top 3 siempre
            for i, (_, equipo_row) in enumerate(df_ranking.head(3).iterrows()):
                if format_func:
                    valor = format_func(equipo_row)
                else:
                    valor = f"{equipo_row[stat_col]:.1f}"
                    
                destacar = equipo_row['Equipo'] == equipo_seleccionado
                equipos_mostrar.append((i+1, equipo_row['Equipo'], valor, destacar))
            
            # Si el equipo no está en top 3, mostrar contexto alrededor del equipo
            if posicion_equipo and posicion_equipo > 3:
                # Añadir puntos suspensivos si hay salto
                if posicion_equipo > 4:
                    equipos_mostrar.append(('dots', '...', '', False))
                
                # Calcular rango de equipos a mostrar (2 antes, el equipo, 2 después)
                inicio = max(0, posicion_equipo - 3)  # 2 antes del equipo seleccionado
                fin = min(len(df_ranking), posicion_equipo + 2)  # equipo + 2 después
                
                for i in range(inicio, fin):
                    equipo_row = df_ranking.iloc[i]
                    if format_func:
                        valor = format_func(equipo_row)
                    else:
                        valor = f"{equipo_row[stat_col]:.1f}"
                    
                    destacar = equipo_row['Equipo'] == equipo_seleccionado
                    equipos_mostrar.append((i+1, equipo_row['Equipo'], valor, destacar))
            
            # Añadir filas de equipos con tamaños más pequeños
            for pos, nombre, valor, destacar in equipos_mostrar:
                # Manejar puntos suspensivos de manera especial
                if pos == 'dots':
                    fila = Table([
                        [Paragraph("", ParagraphStyle('empty', fontSize=6, alignment=TA_CENTER)),
                         Paragraph("...", ParagraphStyle('dots', fontSize=8, alignment=TA_CENTER, textColor=colors.HexColor('#999999'))),
                         Paragraph("", ParagraphStyle('empty', fontSize=6, alignment=TA_CENTER))]
                    ], colWidths=col_widths_fila)
                    
                    fila.setStyle(TableStyle([
                        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                        ('LEFTPADDING', (0, 0), (-1, -1), 1),
                        ('RIGHTPADDING', (0, 0), (-1, -1), 1),
                        ('TOPPADDING', (0, 0), (-1, -1), 0.5),
                        ('BOTTOMPADDING', (0, 0), (-1, -1), 0.5),
                        ('BACKGROUND', (0, 0), (-1, -1), colors.white),
                    ]))
                    
                    data.append([fila])
                    continue
                
                if destacar:
                    nombre_style = ParagraphStyle('destacar', fontSize=6, fontName='Helvetica-Bold', 
                                                textColor=colors.HexColor(color), alignment=TA_LEFT)
                    pos_style = ParagraphStyle('pos_destacar', fontSize=6, fontName='Helvetica-Bold', 
                                             textColor=colors.HexColor(color), alignment=TA_CENTER)
                    val_style = ParagraphStyle('val_destacar', fontSize=6, fontName='Helvetica-Bold', 
                                             textColor=colors.HexColor(color), alignment=TA_RIGHT)
                else:
                    nombre_style = ParagraphStyle('normal', fontSize=6, alignment=TA_LEFT)
                    pos_style = ParagraphStyle('pos_normal', fontSize=6, alignment=TA_CENTER)
                    val_style = ParagraphStyle('val_normal', fontSize=6, alignment=TA_RIGHT)
                
                fila = Table([
                    [Paragraph(f"{pos}°", pos_style),
                     Paragraph(nombre[:max_chars] + ("..." if len(nombre) > max_chars else ""), nombre_style),
                     Paragraph(valor, val_style)]
                ], colWidths=col_widths_fila)
                
                bg_color = colors.HexColor('#fff2e6') if destacar else (colors.HexColor('#f8f9fa') if pos % 2 == 0 else colors.white)
                
                fila.setStyle(TableStyle([
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ('LEFTPADDING', (0, 0), (-1, -1), 1),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 1),
                    ('TOPPADDING', (0, 0), (-1, -1), 0.5),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 0.5),
                    ('BACKGROUND', (0, 0), (-1, -1), bg_color),
                ]))
                
                data.append([fila])
            
            # Crear tabla del ranking con ancho ajustable
            tabla = Table(data, colWidths=[tabla_width])
            tabla.setStyle(TableStyle([
                ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('LEFTPADDING', (0, 0), (-1, -1), 2),
                ('RIGHTPADDING', (0, 0), (-1, -1), 2),
                ('TOPPADDING', (0, 0), (-1, -1), 2),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
            ]))
            
            return tabla

        # Crear rankings compactos
        rankings_tablas = []
        
        if 'Puntos_Equipo' in rankings_equipos:
            rankings_tablas.append(crear_ranking_equipo_compacto(
                "🏀 ANOTACIÓN", "Puntos", rankings_equipos['Puntos_Equipo'], 'PTS/PJ'
            ))
        
        if 'Rebotes_Equipo' in rankings_equipos:
            rankings_tablas.append(crear_ranking_equipo_compacto(
                "💪 REBOTES", "Rebotes", rankings_equipos['Rebotes_Equipo'], 'REB/PJ'
            ))
        
        if 'Asistencias_Equipo' in rankings_equipos:
            rankings_tablas.append(crear_ranking_equipo_compacto(
                "🤝 ASISTENCIAS", "Asistencias", rankings_equipos['Asistencias_Equipo'], 'AST/PJ'
            ))
        
        if 'Perdidas_Equipo' in rankings_equipos:
            rankings_tablas.append(crear_ranking_equipo_compacto(
                "⚠️ PÉRDIDAS", "Pérdidas", rankings_equipos['Perdidas_Equipo'], 'TO/PJ'
            ))
        
        if 'FG_Percentage_Equipo' in rankings_equipos:
            def format_percentage(row):
                return f"{row['FG%']:.1f}%"
            
            rankings_tablas.append(crear_ranking_equipo_compacto(
                "🎯 TIRO DE CAMPO", "Tiro de Campo", rankings_equipos['FG_Percentage_Equipo'], 'FG%', format_percentage
            ))
        
        if 'FT_Percentage_Equipo' in rankings_equipos:
            def format_percentage_ft(row):
                return f"{row['FT%']:.1f}%"
            
            rankings_tablas.append(crear_ranking_equipo_compacto(
                "🎯 % LIBRES", "Tiro de Campo", rankings_equipos['FT_Percentage_Equipo'], 'FT%', format_percentage_ft
            ))
        
        if 'Rebotes_Ofensivos_Equipo' in rankings_equipos:
            rankings_tablas.append(crear_ranking_equipo_compacto(
                "🚀 REB. OFENS.", "Rebotes", rankings_equipos['Rebotes_Ofensivos_Equipo'], 'OREB/PJ'
            ))
        
        if 'Robos_Equipo' in rankings_equipos:
            rankings_tablas.append(crear_ranking_equipo_compacto(
                "🛡️ ROBOS", "Pérdidas", rankings_equipos['Robos_Equipo'], 'STL/PJ'
            ))
        
        if 'Victorias_Equipo' in rankings_equipos:
            def format_wins(row):
                return f"{row['Win%']:.1f}%"
            
            rankings_tablas.append(crear_ranking_equipo_compacto(
                "🏆 % VICTORIAS", "Victorias", rankings_equipos['Victorias_Equipo'], 'Win%', format_wins
            ))
        
        # Añadir triples en la misma fila que victorias

        if 'Triples_Equipo' in rankings_equipos:
            def format_triples(row):
                intentos = row['FG3A'] / row['PJ']
                porcentaje = row['FG3%']
                return f"{intentos:.1f}({porcentaje:.0f}%)"  # Sin espacio y porcentaje sin decimal para ser más compacto
            
            rankings_tablas.append(crear_ranking_equipo_compacto(
                "🎯 TRIPLES", "Triples", rankings_equipos['Triples_Equipo'], 'FG3A', format_triples, False, 2.4*inch
            ))
        
        # Organizar en grid 4 columnas normal (sin separar triples)
        filas_rankings = []
        for i in range(0, len(rankings_tablas), 4):
            fila = rankings_tablas[i:i+4]
            # Completar fila si es necesario
            while len(fila) < 4:
                fila.append(Spacer(1, 1))
            filas_rankings.append(fila)
        
        # Crear tabla principal con anchos uniformes
        if filas_rankings:
            tabla_principal = Table(filas_rankings, colWidths=[1.9*inch, 1.9*inch, 1.9*inch, 1.9*inch])
            tabla_principal.setStyle(TableStyle([
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('LEFTPADDING', (0, 0), (-1, -1), 3),
                ('RIGHTPADDING', (0, 0), (-1, -1), 3),
                ('TOPPADDING', (0, 0), (-1, -1), 3),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ]))
            
            tabla_principal.hAlign = 'CENTER'
            story.append(tabla_principal)

    def crear_pagina_rankings(story, rankings, styles):
        """
        Crea una página de rankings con diseño moderno y minimalista
        """
        from reportlab.lib.units import inch, cm
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
        from reportlab.platypus import Paragraph, Spacer, Table, TableStyle, PageBreak, Image
        from reportlab.lib.styles import ParagraphStyle
        from pathlib import Path
        import os
        
        # Añadir salto de página
        story.append(PageBreak())
        
        # 🏀 TÍTULO PRINCIPAL ELEGANTE
        titulo_style = ParagraphStyle(
            'TituloElegante',
            parent=styles['Heading1'],
            fontSize=26,
            textColor=colors.HexColor('#2d3748'),
            alignment=TA_CENTER,
            spaceAfter=25,
            fontName='Helvetica-Bold',
        )
        
        titulo = Paragraph("RANKINGS DE JUGADORES", titulo_style)
        story.append(titulo)
        
        # Línea decorativa
        linea_style = ParagraphStyle(
            'LineaDecorativa',
            parent=styles['Normal'],
            fontSize=16,
            textColor=colors.HexColor('#e2e8f0'),
            alignment=TA_CENTER,
            spaceAfter=20,
        )
        linea = Paragraph("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", linea_style)
        story.append(linea)
        
        def crear_ranking_card(categoria, df_ranking):
            """Crea una tarjeta moderna para cada categoría"""
            
            # 🏷️ Configuración de categorías
            config_categorias = {
                'Puntos': {'titulo': 'ANOTACIÓN', 'emoji': '🏀', 'color': '#e53e3e'},
                'Valoracion': {'titulo': 'VALORACIÓN', 'emoji': '⭐', 'color': '#38a169'},
                'Rebotes': {'titulo': 'REBOTES', 'emoji': '💪', 'color': '#3182ce'},
                'Triples_Intentados': {'titulo': 'TRIPLES TIRADOS POR PARTIDO (%T3)', 'emoji': '🎯', 'color': '#d69e2e'},
                'Robos': {'titulo': 'ROBOS', 'emoji': '🛡️', 'color': '#805ad5'},
                'Uso': {'titulo': 'PROTAGONISMO', 'emoji': '👑', 'color': '#dd6b20'},
                'Rebotes_Ofensivos': {'titulo': 'REB. OFENSIVO', 'emoji': '🚀', 'color': '#319795'}
            }
            
            config = config_categorias.get(categoria, {'titulo': categoria, 'emoji': '📊', 'color': '#4a5568'})
            
            # Estilo del título de la categoría
            titulo_cat_style = ParagraphStyle(
                'TituloCategoria',
                parent=styles['Normal'],
                fontSize=14,
                textColor=colors.HexColor(config['color']),
                alignment=TA_CENTER,
                fontName='Helvetica-Bold',
                spaceAfter=8,
            )
            
            # Crear contenido de la tarjeta
            card_data = []
            
            # Header con emoji y título
            header = Paragraph(f"{config['emoji']} {config['titulo']}", titulo_cat_style)
            card_data.append([header])
            
            # Top 7 jugadores con diseño limpio
            for i, (_, jugador) in enumerate(df_ranking.head(7).iterrows()):
                nombre = jugador['Jugador'].split(',')[0] if ',' in jugador['Jugador'] else jugador['Jugador']
                foto_path = jugador.get('foto_path', '')
                
                # Foto del jugador
                if foto_path and os.path.exists(foto_path):
                    try:
                        img = Image(foto_path, width=0.4*inch, height=0.4*inch)
                    except:
                        img = Paragraph("👤", ParagraphStyle('', fontSize=12, alignment=TA_CENTER))
                else:
                    img = Paragraph("👤", ParagraphStyle('', fontSize=12, alignment=TA_CENTER))
                
                # Obtener valor estadístico
                valor = 0.0
                if categoria == 'Puntos':
                    valor = jugador['PTS/PJ']
                elif categoria == 'Valoracion':
                    valor = jugador['VAL/PJ']
                elif categoria == 'Rebotes':
                    valor = jugador['REB/PJ']
                elif categoria == 'Robos':
                    valor = jugador['STL/PJ']
                elif categoria == 'Triples_Intentados':
                    valor = jugador['FG3A/PJ']
                elif categoria == 'Rebotes_Ofensivos':
                    valor = jugador['OREB/PJ']
                elif categoria == 'Uso':
                    valor = jugador['USG%']
                
                # Estilo para la posición
                pos_style = ParagraphStyle(
                    'Posicion',
                    parent=styles['Normal'],
                    fontSize=11,
                    textColor=colors.HexColor('#4a5568'),
                    alignment=TA_CENTER,
                    fontName='Helvetica-Bold',
                )
                
                # Estilo para el nombre
                nombre_style = ParagraphStyle(
                    'NombreJugador',
                    parent=styles['Normal'],
                    fontSize=9,
                    textColor=colors.HexColor('#2d3748'),
                    alignment=TA_LEFT,
                    fontName='Helvetica',
                )
                
                # Estilo para el valor
                valor_style = ParagraphStyle(
                    'ValorStat',
                    parent=styles['Normal'],
                    fontSize=10,
                    textColor=colors.HexColor(config['color']),
                    alignment=TA_RIGHT,
                    fontName='Helvetica-Bold',
                )
                
                # Formatear valor según categoría
                if categoria == 'Triples_Intentados':
                    porcentaje = jugador['FG3%'] if 'FG3%' in jugador and jugador['FG3%'] > 0 else 0
                    valor_texto = f"{valor:.1f} ({porcentaje:.1f}%)"
                else:
                    valor_texto = f"{valor:.1f}"
                
                # Crear fila del jugador
                fila_jugador = Table([
                    [Paragraph(f"{i+1}°", pos_style), img, Paragraph(nombre, nombre_style), Paragraph(valor_texto, valor_style)]
                ], colWidths=[0.3*inch, 0.5*inch, 1.4*inch, 0.8*inch])
                
                fila_jugador.setStyle(TableStyle([
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ('ALIGN', (0, 0), (0, -1), 'CENTER'),
                    ('ALIGN', (1, 0), (1, -1), 'CENTER'),
                    ('ALIGN', (2, 0), (2, -1), 'LEFT'),
                    ('ALIGN', (3, 0), (3, -1), 'RIGHT'),
                    ('LEFTPADDING', (0, 0), (-1, -1), 3),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 3),
                    ('TOPPADDING', (0, 0), (-1, -1), 2),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
                    ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f7fafc') if i % 2 == 0 else colors.white),
                ]))
                
                card_data.append([fila_jugador])
            
            # Crear tabla principal de la tarjeta
            card_table = Table(card_data, colWidths=[3.2*inch])
            card_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.white),
                ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#e2e8f0')),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('LEFTPADDING', (0, 0), (-1, -1), 8),
                ('RIGHTPADDING', (0, 0), (-1, -1), 8),
                ('TOPPADDING', (0, 0), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ]))
            
            return card_table
        
        # Organizar rankings en grid 2x3
        orden_rankings = ['Puntos', 'Valoracion', 'Rebotes', 'Triples_Intentados']
        if 'Uso' in rankings:
            orden_rankings.extend(['Uso', 'Robos'])
        else:
            orden_rankings.extend(['Robos', 'Rebotes_Ofensivos'])
        
        # Crear filas de tarjetas (2 por fila)
        filas_cards = []
        fila_actual = []
        
        for categoria in orden_rankings:
            if categoria in rankings and not rankings[categoria].empty:
                card = crear_ranking_card(categoria, rankings[categoria])
                fila_actual.append(card)
                
                # Si completamos una fila
                if len(fila_actual) == 2:
                    filas_cards.append(fila_actual)
                    fila_actual = []
        
        # Añadir última fila si no está completa
        if fila_actual:
            # Rellenar con espacio vacío si es necesario
            while len(fila_actual) < 2:
                espacio_vacio = Table([[""]], colWidths=[3.2*inch])
                fila_actual.append(espacio_vacio)
            filas_cards.append(fila_actual)
        
        # Control de errores
        if not filas_cards:
            mensaje_error_style = ParagraphStyle(
                'MensajeError',
                parent=styles['Normal'],
                fontSize=16,
                textColor=colors.HexColor('#e53e3e'),
                alignment=TA_CENTER,
                fontName='Helvetica-Bold',
            )
            mensaje = Paragraph("⚠️  No hay datos disponibles para mostrar rankings", mensaje_error_style)
            story.append(mensaje)
            return
        
        # Crear tabla principal con todas las tarjetas
        tabla_principal = Table(filas_cards, colWidths=[3.4*inch, 3.4*inch])
        tabla_principal.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('LEFTPADDING', (0, 0), (-1, -1), 10),
            ('RIGHTPADDING', (0, 0), (-1, -1), 10),
            ('TOPPADDING', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ]))
        
        tabla_principal.hAlign = 'CENTER'
        story.append(tabla_principal)
        
        # Añadir explicaciones si es necesario
        if 'Uso' in rankings and not rankings['Uso'].empty:
            story.append(Spacer(1, 10))
            explicacion_style = ParagraphStyle(
                'Explicacion',
                parent=styles['Normal'],
                fontSize=8,
                textColor=colors.HexColor('#718096'),
                alignment=TA_CENTER,
                fontName='Helvetica',
            )
            explicacion_uso = Paragraph("* Protagonismo = % USG (Porcentaje de posesiones del equipo utilizadas)", explicacion_style)
            story.append(explicacion_uso)
        
        if 'Triples_Intentados' in rankings and not rankings['Triples_Intentados'].empty:
            if 'Uso' not in rankings or rankings['Uso'].empty:
                story.append(Spacer(1, 10))
                explicacion_style = ParagraphStyle(
                    'Explicacion',
                    parent=styles['Normal'],
                    fontSize=8,
                    textColor=colors.HexColor('#718096'),
                    alignment=TA_CENTER,
                    fontName='Helvetica',
                )
            explicacion_triples = Paragraph("", explicacion_style)
            story.append(explicacion_triples)


    def generar_pdf_informe(equipo_data, df_jugadores_norm, df_principales, df_apoyo, rankings, df_grupo=None, rankings_equipos=None, filename=None):
        """
        Genera un PDF completo del informe del equipo con diseño atractivo.
        
        Args:
            equipo_data: Serie con datos del equipo
            df_jugadores_norm: DataFrame con jugadores normalizados
            df_principales: DataFrame con jugadores principales
            df_apoyo: DataFrame con jugadores de apoyo
            rankings: Diccionario con rankings de jugadores
            df_grupo: DataFrame con todos los equipos del grupo
            rankings_equipos: Diccionario con rankings de equipos
            output_path: Ruta donde guardar el PDF
        """
        from reportlab.lib.pagesizes import A4
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle, PageBreak, BaseDocTemplate, Frame, PageTemplate
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch, cm
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
        from pathlib import Path
        import os
        
        # Crear carpeta reportes si no existe
        reportes_dir = Path("reportes")
        reportes_dir.mkdir(exist_ok=True)
        
        # Generar nombre del archivo automáticamente si no se proporciona
        if filename is None:
            nombre_limpio = equipo_data['Equipo'].replace(' ', '_').replace('/', '_')
            filename = f"informe_{nombre_limpio}.pdf"
        
        # Ajustar la ruta del archivo
        output_path = reportes_dir / filename
        
        # Función para dibujar pie de página con PI_circulo
        def footer_todas_paginas(canvas, doc):
            # Pie de página con PI_circulo.png en todas las páginas (más pequeño)
            if os.path.exists('PI_circulo.png'):
                try:
                    canvas.drawImage('PI_circulo.png', 
                                A4[0]/2 - 30, 20,  # Centrado horizontalmente, abajo
                                width=60, height=60, 
                                preserveAspectRatio=True, 
                                mask='auto')
                except:
                    pass
        
        # Crear documento con template personalizado
        doc = BaseDocTemplate(str(output_path), pagesize=A4)
        
        # Definir frame principal (sin margen superior para subir el logo)
        frame = Frame(0.75*inch, 0.75*inch, A4[0] - 1.5*inch, A4[1] - 1.25*inch, 
                    leftPadding=0, bottomPadding=0, rightPadding=0, topPadding=0*inch)
        
        # Crear template de página con pie de página
        template = PageTemplate(id='normal', frames=frame, onPage=footer_todas_paginas)
        doc.addPageTemplates([template])
        
        # Estilos
        styles = getSampleStyleSheet()
        
        # Estilo personalizado para título principal (más compacto)
        titulo_style = ParagraphStyle(
            'TituloEquipo',
            parent=styles['Heading1'],
            fontSize=28,  # Reducido de 36 a 28
            textColor=colors.HexColor('#1a365d'),
            alignment=TA_CENTER,
            spaceAfter=20,  # Reducido de 30 a 20
            fontName='Helvetica-Bold',
            leading=32  # Reducido de 44 a 32
        )

        # Estilo específico para el título de la comparativa (más compacto)
        titulo_comparativa_style = ParagraphStyle(
            'TituloComparativa',
            parent=titulo_style,
            fontSize=24,     # Reducido para ser más compacto
            leading=28,      # Reducido para menos espacio
            spaceAfter=10,   # Reducido de 18 a 10
            fontName='Helvetica-Bold'
        )
        
        # Estilo para subtítulos
        subtitulo_style = ParagraphStyle(
            'Subtitulo',
            parent=styles['Heading2'],
            fontSize=18,
            textColor=colors.HexColor('#2d3748'),
            alignment=TA_CENTER,
            spaceAfter=20,
            fontName='Helvetica-Bold',
        )
        
        # Estilo para números grandes (más pequeños)
        numero_grande_style = ParagraphStyle(
            'NumeroGrande',
            parent=styles['Normal'],
            fontSize=36,
            textColor=colors.HexColor('#2b6cb0'),
            alignment=TA_CENTER,
            spaceAfter=5,
            fontName='Helvetica-Bold',
        )
        
        # Estilo para etiquetas de números (más pequeñas)
        etiqueta_style = ParagraphStyle(
            'Etiqueta',
            parent=styles['Normal'],
            fontSize=12,
            textColor=colors.HexColor('#4a5568'),
            alignment=TA_CENTER,
            spaceAfter=12,
            fontName='Helvetica'
        )
        
        story = []
        
        # === PÁGINA 1: PORTADA DEL EQUIPO ===
        
        # PI_pie.png muy grande solo en la primera página (sin margen superior)
        if os.path.exists('PI_pie.png'):
            try:
                pi_pie_grande = Image('PI_pie.png', width=6*inch, height=3*inch, kind='proportional')
                pi_pie_grande.hAlign = 'CENTER'
                story.append(pi_pie_grande)
                story.append(Spacer(1, 0.1*inch))  # Margen mínimo
            except:
                pass
        
        # Título del equipo con truncamiento automático para nombres largos
        nombre_equipo = equipo_data['Equipo']
        nombre_titulo = nombre_equipo  # Variable separada para el título
        # Truncar nombres muy largos para evitar que se vayan a la siguiente página
        if len(nombre_titulo) > 35:  # Si el nombre es muy largo
            nombre_titulo = nombre_titulo[:32] + "..."
        
        story.append(Paragraph(nombre_titulo, titulo_style))
        story.append(Spacer(1, 0.4*inch))  # Reducido aún más el espacio después del título
        
        # Logo del equipo (si existe) - más pequeño para ahorrar espacio
        logo_path = equipo_data.get('logo_path')
        if logo_path and os.path.exists(logo_path):
            try:
                logo = Image(logo_path, width=2.5*inch, height=2.5*inch, kind='proportional')  # Reducido de 4 a 2.5 pulgadas
                logo.hAlign = 'CENTER'
                story.append(logo)
            except:
                story.append(Paragraph("🏀", ParagraphStyle('Emoji', fontSize=48, alignment=TA_CENTER, spaceAfter=15)))  # Reducido tamaño del emoji
        else:
            story.append(Paragraph("🏀", ParagraphStyle('Emoji', fontSize=48, alignment=TA_CENTER, spaceAfter=15)))  # Reducido tamaño del emoji
        
        story.append(Spacer(1, 0.4*inch))  # Reducido espacio después del logo
        
        # === CUADRADOS SEPARADOS EN LA MISMA LÍNEA ===
        
        # Determinar color del porcentaje
        win_percentage = equipo_data['Win%']
        if win_percentage < 50:
            bg_color = colors.HexColor('#ffebee')    # Rojo claro
            border_color = colors.HexColor('#f44336') # Rojo
        else:
            bg_color = colors.HexColor('#e8f5e8')     # Verde claro
            border_color = colors.HexColor('#4caf50') # Verde
        
        # Crear 3 tablas individuales para tener separación real
        
        # Estilo mejorado para números en las cajas
        numero_caja_style = ParagraphStyle(
            'NumeroCaja',
            parent=styles['Normal'],
            fontSize=42,
            textColor=colors.HexColor('#1565c0'),  # Azul más profundo
            alignment=TA_CENTER,
            spaceAfter=5,
            fontName='Helvetica-Bold',
        )
        
        # Estilo mejorado para etiquetas en las cajas
        etiqueta_caja_style = ParagraphStyle(
            'EtiquetaCaja',
            parent=styles['Normal'],
            fontSize=11,
            textColor=colors.HexColor('#37474f'),  # Gris más elegante
            alignment=TA_CENTER,
            spaceAfter=8,
            fontName='Helvetica-Bold',
            leading=13,
        )
        
        # Cuadrado 1: Partidos Jugados (azul elegante)
        cuadro1_data = [
            [Paragraph(str(equipo_data['PJ']), numero_caja_style)],
            [Paragraph("PARTIDOS<br/>JUGADOS", etiqueta_caja_style)]
        ]
        cuadro1 = Table(cuadro1_data, colWidths=[1.7*inch], rowHeights=[0.9*inch, 0.6*inch])
        cuadro1.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#e8f4fd')),  # Azul más suave
            ('BOX', (0, 0), (-1, -1), 3, colors.HexColor('#1976d2')),     # Borde más grueso
            ('TOPPADDING', (0, 0), (-1, -1), 15),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 15),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ]))
        
        # Cuadrado 2: Partidos Ganados (azul también, pero diferente tono)
        cuadro2_data = [
            [Paragraph(str(equipo_data['PG']), numero_caja_style)],
            [Paragraph("PARTIDOS<br/>GANADOS", etiqueta_caja_style)]
        ]
        cuadro2 = Table(cuadro2_data, colWidths=[1.7*inch], rowHeights=[0.9*inch, 0.6*inch])
        cuadro2.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#e1f5fe')),  # Azul cyan suave
            ('BOX', (0, 0), (-1, -1), 3, colors.HexColor('#0288d1')),     # Azul cyan más oscuro
            ('TOPPADDING', (0, 0), (-1, -1), 15),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 15),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ]))
        
        # Cuadrado 3: Porcentaje (condicional con estilo mejorado)
        # Estilo de número condicional según el porcentaje
        if win_percentage < 50:
            numero_porcentaje_style = ParagraphStyle(
                'NumeroPorcentajeRojo',
                parent=styles['Normal'],
                fontSize=42,
                textColor=colors.HexColor('#c62828'),  # Rojo más elegante
                alignment=TA_CENTER,
                spaceAfter=5,
                fontName='Helvetica-Bold',
            )
            bg_color = colors.HexColor('#ffebee')
            border_color = colors.HexColor('#e53935')
        else:
            numero_porcentaje_style = ParagraphStyle(
                'NumeroPorcentajeVerde',
                parent=styles['Normal'],
                fontSize=42,
                textColor=colors.HexColor('#2e7d32'),  # Verde más elegante
                alignment=TA_CENTER,
                spaceAfter=5,
                fontName='Helvetica-Bold',
            )
            bg_color = colors.HexColor('#e8f5e8')
            border_color = colors.HexColor('#43a047')
        
        cuadro3_data = [
            [Paragraph(f"{win_percentage}%", numero_porcentaje_style)],
            [Paragraph("% DE<br/>VICTORIA", etiqueta_caja_style)]
        ]
        cuadro3 = Table(cuadro3_data, colWidths=[2.0*inch], rowHeights=[0.9*inch, 0.6*inch])  # Aumentado a 2.0 pulgadas
        cuadro3.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('BACKGROUND', (0, 0), (0, -1), bg_color),
            ('BOX', (0, 0), (-1, -1), 3, border_color),  # Borde condicional
            ('TOPPADDING', (0, 0), (-1, -1), 15),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 15),
            ('LEFTPADDING', (0, 0), (-1, -1), 12),
            ('RIGHTPADDING', (0, 0), (-1, -1), 12),
        ]))
        
        # Crear tabla contenedora para colocar los 3 cuadrados con separación
        contenedor_data = [[cuadro1, cuadro2, cuadro3]]
        tabla_contenedora = Table(contenedor_data, colWidths=[2*inch, 2*inch, 2.3*inch])  # Más ancho para la tercera columna
        tabla_contenedora.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0.2*inch),  # Separación entre cuadros
            ('RIGHTPADDING', (0, 0), (-1, -1), 0.2*inch),
        ]))
        
        tabla_contenedora.hAlign = 'CENTER'
        story.append(tabla_contenedora)
        
        # Salto de página para continuar con más contenido
        story.append(PageBreak())
        
        # === PÁGINA 2: RESUMEN GENERAL DEL EQUIPO ===
        
        # Título de la segunda página
        story.append(Paragraph("RESUMEN GENERAL", titulo_style))
        story.append(Spacer(1, 0.3*inch))
        
        # Crear estilos para las estadísticas (más compactos)
        estadistica_numero_style = ParagraphStyle(
            'EstadisticaNumero',
            parent=styles['Normal'],
            fontSize=20,  # Más pequeño
            textColor=colors.HexColor('#1565c0'),
            alignment=TA_CENTER,
            spaceAfter=2,
            fontName='Helvetica-Bold',
        )
        
        estadistica_label_style = ParagraphStyle(
            'EstadisticaLabel',
            parent=styles['Normal'],
            fontSize=8,  # Más pequeño
            textColor=colors.HexColor('#37474f'),
            alignment=TA_CENTER,
            spaceAfter=3,
            fontName='Helvetica-Bold',
            leading=9,
        )
        
        # Calcular todas las estadísticas por partido
        pts_por_partido = round(equipo_data['PTS_Favor'] / equipo_data['PJ'], 1)
        fg3_por_partido = round(equipo_data['FG3A'] / equipo_data['PJ'], 1)
        fg3_aciertos = round(equipo_data['FG3M'] / equipo_data['PJ'], 1)
        ast_por_partido = round(equipo_data['AST_Total'] / equipo_data['PJ'], 1)
        reb_por_partido = round(equipo_data['REB_Total'] / equipo_data['PJ'], 1)
        oreb_por_partido = round(equipo_data['OREB_Total'] / equipo_data['PJ'], 1)
        dreb_por_partido = round(equipo_data['DREB_Total'] / equipo_data['PJ'], 1)
        stl_por_partido = round(equipo_data['STL'] / equipo_data['PJ'], 1)
        fg_porcentaje = round(equipo_data.get('FG%', 0), 1)
        fg2_pct = round(equipo_data.get('FG2%', 0), 1)
        fg3_pct = round(equipo_data.get('FG3%', 0), 1)
        ft_pct = round(equipo_data.get('FT%', 0), 1)
        
        # Función para crear caja estadística con diseño uniforme
        def crear_caja_estadistica(valor, etiqueta, ancho=1.1):
            data = [
                [Paragraph(str(valor), estadistica_numero_style)],
                [Paragraph(etiqueta, estadistica_label_style)]
            ]
            tabla = Table(data, colWidths=[ancho*inch], rowHeights=[0.5*inch, 0.4*inch])
            tabla.setStyle(TableStyle([
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#e8f4fd')),  # Azul claro uniforme
                ('BOX', (0, 0), (-1, -1), 1.5, colors.HexColor('#1976d2')),   # Borde azul uniforme
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('LEFTPADDING', (0, 0), (-1, -1), 4),
                ('RIGHTPADDING', (0, 0), (-1, -1), 4),
            ]))
            return tabla
        
        # === SECCIÓN 1: ESTADÍSTICAS OFENSIVAS ===
        story.append(Paragraph("ESTADÍSTICAS OFENSIVAS", subtitulo_style))
        story.append(Spacer(1, 0.2*inch))
        
        # Estadísticas ofensivas en una fila
        ofensivas = [
            crear_caja_estadistica(pts_por_partido, "PUNTOS<br/>POR PARTIDO"),
            crear_caja_estadistica(ast_por_partido, "ASISTENCIAS<br/>POR PARTIDO"),
            crear_caja_estadistica(fg3_aciertos, "TRIPLES ANOTADOS<br/>POR PARTIDO"),
            crear_caja_estadistica(fg3_por_partido, "TRIPLES INTENTADOS<br/>POR PARTIDO")
        ]
        
        tabla_ofensivas = Table([ofensivas], colWidths=[1.5*inch]*4)
        tabla_ofensivas.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0.05*inch),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0.05*inch),
        ]))
        tabla_ofensivas.hAlign = 'CENTER'
        story.append(tabla_ofensivas)
        story.append(Spacer(1, 0.3*inch))
        
        # === SECCIÓN 2: ESTADÍSTICAS DEFENSIVAS ===
        story.append(Paragraph("ESTADÍSTICAS DEFENSIVAS", subtitulo_style))
        story.append(Spacer(1, 0.2*inch))
        
        # Estadísticas defensivas en una fila
        defensivas = [
            crear_caja_estadistica(reb_por_partido, "REBOTES TOTALES<br/>POR PARTIDO"),
            crear_caja_estadistica(oreb_por_partido, "REBOTES OFENSIVOS<br/>POR PARTIDO"),
            crear_caja_estadistica(dreb_por_partido, "REBOTES DEFENSIVOS<br/>POR PARTIDO"),
            crear_caja_estadistica(stl_por_partido, "ROBOS<br/>POR PARTIDO")
        ]
        
        tabla_defensivas = Table([defensivas], colWidths=[1.5*inch]*4)
        tabla_defensivas.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0.05*inch),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0.05*inch),
        ]))
        tabla_defensivas.hAlign = 'CENTER'
        story.append(tabla_defensivas)
        story.append(Spacer(1, 0.3*inch))
        
        # === SECCIÓN 3: PORCENTAJES DE ACIERTO ===
        story.append(Paragraph("PORCENTAJES DE ACIERTO", subtitulo_style))
        story.append(Spacer(1, 0.2*inch))
        
        # Porcentajes en una fila
        porcentajes = [
            crear_caja_estadistica(f"{fg_porcentaje}%", "% TIROS<br/>DE CAMPO"),
            crear_caja_estadistica(f"{fg2_pct}%", "% TIROS<br/>DE 2"),
            crear_caja_estadistica(f"{fg3_pct}%", "% TIROS<br/>DE 3"),
            crear_caja_estadistica(f"{ft_pct}%", "% TIROS<br/>LIBRES")
        ]
        
        tabla_porcentajes = Table([porcentajes], colWidths=[1.5*inch]*4)
        tabla_porcentajes.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0.05*inch),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0.05*inch),
        ]))
        tabla_porcentajes.hAlign = 'CENTER'
        story.append(tabla_porcentajes)
        
        # ============== TERCERA PÁGINA: COMPARATIVA ==============
        story.append(PageBreak())
        
        # Título de la tercera página (más corto y compacto)
        titulo_comparativa = Paragraph("COMPARATIVA", titulo_comparativa_style)
        story.append(titulo_comparativa)
        story.append(Spacer(1, 12))  # Reducido de 25 a 12
        
        # Calcular rankings y posiciones para nuestro equipo
        df_grupo_sorted_ortg = df_grupo.sort_values('ORtg', ascending=False).reset_index(drop=True)
        df_grupo_sorted_drtg = df_grupo.sort_values('DRtg', ascending=True).reset_index(drop=True)  # Menor es mejor en DRtg
        df_grupo_sorted_ritmo = df_grupo.sort_values('Ritmo', ascending=False).reset_index(drop=True)
        
        # Encontrar posiciones de nuestro equipo con verificación de seguridad
        try:
            mask_ortg = df_grupo_sorted_ortg['Equipo'] == nombre_equipo
            if mask_ortg.any():
                pos_ortg = df_grupo_sorted_ortg[mask_ortg].index[0] + 1
            else:
                print(f"Advertencia: Equipo '{nombre_equipo}' no encontrado en ranking ORtg")
                pos_ortg = len(df_grupo_sorted_ortg)  # Posición por defecto
        except (IndexError, KeyError):
            pos_ortg = len(df_grupo_sorted_ortg)
            
        try:
            mask_drtg = df_grupo_sorted_drtg['Equipo'] == nombre_equipo
            if mask_drtg.any():
                pos_drtg = df_grupo_sorted_drtg[mask_drtg].index[0] + 1
            else:
                print(f"Advertencia: Equipo '{nombre_equipo}' no encontrado en ranking DRtg")
                pos_drtg = len(df_grupo_sorted_drtg)
        except (IndexError, KeyError):
            pos_drtg = len(df_grupo_sorted_drtg)
            
        try:
            mask_ritmo = df_grupo_sorted_ritmo['Equipo'] == nombre_equipo
            if mask_ritmo.any():
                pos_ritmo = df_grupo_sorted_ritmo[mask_ritmo].index[0] + 1
            else:
                print(f"Advertencia: Equipo '{nombre_equipo}' no encontrado en ranking Ritmo")
                pos_ritmo = len(df_grupo_sorted_ritmo)
        except (IndexError, KeyError):
            pos_ritmo = len(df_grupo_sorted_ritmo)
        
        # Obtener valores de nuestro equipo directamente de equipo_data
        nuestro_ortg = equipo_data['ORtg']
        nuestro_drtg = equipo_data['DRtg'] 
        nuestro_ritmo = equipo_data['Ritmo']
        
        # Función para crear caja de comparativa con altura uniforme
        def crear_caja_comparativa(titulo, valor, posicion, total_equipos, es_mejor_mayor=True):
            # Determinar color según posición
            if posicion <= total_equipos // 3:
                color_fondo = colors.HexColor("#e8f5e8")  # Verde claro para top 1/3
                color_borde = colors.HexColor("#4caf50")
            elif posicion <= 2 * total_equipos // 3:
                color_fondo = colors.HexColor("#fff3e0")  # Naranja claro para middle 1/3
                color_borde = colors.HexColor("#ff9800")
            else:
                color_fondo = colors.HexColor("#ffebee")  # Rojo claro para bottom 1/3
                color_borde = colors.HexColor("#f44336")
            
            posicion_text = f"{posicion}º de {total_equipos}"
            
            # Estilos con altura fija (más compactos)
            titulo_style = ParagraphStyle('', fontSize=8, alignment=1, textColor=colors.black, 
                                        fontName='Helvetica-Bold', leading=9)  # Más pequeño
            valor_style = ParagraphStyle('', fontSize=18, alignment=1, textColor=colors.black, 
                                        fontName='Helvetica-Bold', leading=20)  # Más pequeño
            pos_style = ParagraphStyle('', fontSize=7, alignment=1, textColor=colors.HexColor('#666666'), 
                                    leading=8)  # Más pequeño
            
            data = [
                [Paragraph(titulo, titulo_style)],
                [Paragraph(f"{valor:.1f}", valor_style)],
                [Paragraph(posicion_text, pos_style)]
            ]
            
            # Altura más compacta para todas las cajas
            tabla = Table(data, colWidths=[1.3*inch], rowHeights=[0.3*inch, 0.5*inch, 0.25*inch])  # Reducidas todas las alturas
            tabla.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), color_fondo),
                ('ROUNDEDCORNERS', [6, 6, 6, 6]),  # Bordes redondeados
                ('BOX', (0, 0), (-1, -1), 2, color_borde),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('LEFTPADDING', (0, 0), (-1, -1), 6),  # Reducido
                ('RIGHTPADDING', (0, 0), (-1, -1), 6),  # Reducido
                ('TOPPADDING', (0, 0), (-1, -1), 4),   # Reducido
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ]))
            return tabla
        
        # Crear tabla con las tres métricas comparativas con más separación
        total_equipos = len(df_grupo)
        
        # Crear cajas individuales
        caja_ortg = crear_caja_comparativa("OFFENSIVE RATING", nuestro_ortg, pos_ortg, total_equipos, True)
        caja_drtg = crear_caja_comparativa("DEFENSIVE RATING", nuestro_drtg, pos_drtg, total_equipos, False)
        caja_ritmo = crear_caja_comparativa("RITMO", nuestro_ritmo, pos_ritmo, total_equipos, True)
        
        # Crear separadores más pequeños
        separador_amplio = Table([[""]], colWidths=[1.0*inch])  # Reducido de 1.2 a 1.0
        separador_amplio.setStyle(TableStyle([(('BACKGROUND', (0, 0), (-1, -1), colors.white))]))
        
        datos_comparativa = [
            [caja_ortg, separador_amplio, caja_drtg, separador_amplio, caja_ritmo]
        ]
        
        # Tabla con columnas ajustadas al nuevo tamaño
        tabla_comparativa = Table(datos_comparativa, colWidths=[1.3*inch, 1.0*inch, 1.3*inch, 1.0*inch, 1.3*inch])
        tabla_comparativa.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ]))
        tabla_comparativa.hAlign = 'CENTER'
        story.append(tabla_comparativa)
        
        # Añadir explicaciones con asteriscos
        story.append(Spacer(1, 8))  # Reducido de 12 a 8
        
        # Estilo para las explicaciones (más compacto)
        explicacion_style = ParagraphStyle(
            'ExplicacionStyle',
            fontSize=6,  # Reducido de 7 a 6
            textColor=colors.HexColor('#666666'),
            alignment=1,  # Centrado
            fontName='Helvetica',
            leading=7,  # Reducido de 8 a 7
            spaceAfter=1  # Reducido de 2 a 1
        )
        
        # Crear las explicaciones centradas
        explicaciones = [
            "* OFFENSIVE RATING: Puntos anotados por cada 100 posesiones",
            "* DEFENSIVE RATING: Puntos permitidos por cada 100 posesiones", 
            "* RITMO: Número promedio de posesiones por partido"
        ]
        
        for explicacion in explicaciones:
            story.append(Paragraph(explicacion, explicacion_style))
        
        story.append(Spacer(1, 10))  # Reducido de 18 a 10
        
        # Función para crear ranking con cajas alargadas y efecto redondeado
        def crear_ranking_premium(titulo, df_sorted, columna, nombre_equipo, color_principal, color_secundario):
            
            # Función para acortar nombres largos (más generosa con el espacio extra)
            def acortar_nombre(nombre, max_chars=22):
                if len(nombre) <= max_chars:
                    return nombre
                # Buscar palabras para acortar inteligentemente
                palabras = nombre.split()
                if len(palabras) > 1:
                    # Si hay múltiples palabras, usar iniciales excepto la última
                    iniciales = [p[0] + '.' for p in palabras[:-1]]
                    resultado = ' '.join(iniciales + [palabras[-1]])
                    if len(resultado) <= max_chars:
                        return resultado
                    else:
                        return resultado[:max_chars-2] + '..'
                else:
                    # Si es una sola palabra larga, truncar
                    return nombre[:max_chars-2] + '..'
            
            # Crear la tabla con los datos (más alargada)
            datos_ranking = []
            
            # Header con mejor estilo
            header_style = ParagraphStyle(
                'HeaderElegante',
                fontSize=11,
                textColor=colors.white,
                alignment=1,
                fontName='Helvetica-Bold',
                leading=14,
                spaceAfter=2
            )
            
            datos_ranking.append([Paragraph(titulo, header_style), ""])
            
            # Añadir filas de equipos
            for i, (_, row) in enumerate(df_sorted.iterrows()):
                equipo_nombre = row['Equipo']
                valor = row[columna]
                
                # Acortar nombre con más espacio disponible
                nombre_mostrar = acortar_nombre(equipo_nombre, 24)
                
                # Determinar si es nuestro equipo
                es_nuestro = equipo_nombre == nombre_equipo
                
                # Formatear número de forma más legible
                if valor == int(valor):
                    valor_texto = f"{int(valor)}"  # Sin decimales si es entero
                else:
                    valor_texto = f"{valor:.1f}"   # Con un decimal si es necesario
                
                # Estilos con números más prominentes y legibles
                if es_nuestro:
                    nombre_style = ParagraphStyle('', fontSize=10, textColor=colors.HexColor('#2c5530'), 
                                                alignment=0, fontName='Helvetica-Bold', leading=13)
                    valor_style = ParagraphStyle('', fontSize=11, textColor=colors.HexColor('#2c5530'), 
                                            alignment=2, fontName='Helvetica-Bold', leading=13)
                else:
                    nombre_style = ParagraphStyle('', fontSize=9.5, textColor=colors.HexColor('#2c3e50'), 
                                                alignment=0, leading=12)
                    valor_style = ParagraphStyle('', fontSize=10.5, textColor=colors.HexColor('#2c3e50'), 
                                            alignment=2, fontName='Helvetica-Bold', leading=12)
                
                datos_ranking.append([
                    Paragraph(nombre_mostrar, nombre_style),
                    Paragraph(valor_texto, valor_style)
                ])
            
            # Crear la tabla principal con cajas más anchas para mejor presentación
            tabla = Table(datos_ranking, colWidths=[1.6*inch, 0.7*inch], rowHeights=None, splitByRow=True)
            
            # Estilos premium con bordes redondeados IGUALES a las cajas superiores
            estilos = [
                # Header elegante con bordes redondeados
                ('BACKGROUND', (0, 0), (-1, 0), color_principal),
                ('SPAN', (0, 0), (1, 0)),  # Unir celdas del header
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                ('VALIGN', (0, 0), (-1, 0), 'MIDDLE'),
                ('TOPPADDING', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
                ('ROUNDEDCORNERS', [6, 6, 0, 0]),  # Solo esquinas superiores redondeadas
                
                # Contenido con espaciado optimizado
                ('ALIGN', (0, 1), (0, -1), 'LEFT'),
                ('ALIGN', (1, 1), (1, -1), 'RIGHT'),
                ('VALIGN', (0, 1), (-1, -1), 'MIDDLE'),
                ('LEFTPADDING', (0, 1), (-1, -1), 10),
                ('RIGHTPADDING', (0, 1), (-1, -1), 10),
                ('TOPPADDING', (0, 1), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 1), (-1, -1), 4),
                
                # Bordes redondeados IGUALES a las cajas superiores
                ('ROUNDEDCORNERS', [6, 6, 6, 6]),  # Mismos bordes redondeados que arriba
                ('BOX', (0, 0), (-1, -1), 2, color_principal),
                ('LINEBELOW', (0, 0), (-1, 0), 2, colors.white),
            ]
            
            # Colores y efectos para cada fila
            for i, (_, row) in enumerate(df_sorted.iterrows(), 1):
                equipo_nombre = row['Equipo']
                
                if equipo_nombre == nombre_equipo:
                    # Nuestro equipo - destacado elegante
                    estilos.extend([
                        ('BACKGROUND', (0, i), (-1, i), colors.HexColor('#e8f5e8')),  # Verde muy suave
                        ('LINEABOVE', (0, i), (-1, i), 2, colors.HexColor('#4caf50')),
                        ('LINEBELOW', (0, i), (-1, i), 2, colors.HexColor('#4caf50')),
                        ('LEFTPADDING', (0, i), (-1, i), 15),  # Extra padding para destacar
                        ('RIGHTPADDING', (0, i), (-1, i), 15),
                    ])
                else:
                    # Alternar colores suaves para mejor lectura
                    if i % 2 == 0:
                        estilos.append(('BACKGROUND', (0, i), (-1, i), colors.HexColor('#fbfcfd')))
                    else:
                        estilos.append(('BACKGROUND', (0, i), (-1, i), colors.white))
                        
                    # Líneas separadoras muy suaves
                    estilos.append(('LINEBELOW', (0, i), (-1, i), 0.3, colors.HexColor('#f1f3f4')))
            
            tabla.setStyle(TableStyle(estilos))
            
            # Crear contenedor más ancho para mejor presentación
            contenedor_data = [[tabla]]
            contenedor = Table(contenedor_data, colWidths=[2.3*inch])  # Más ancho para mejor legibilidad
            contenedor.setStyle(TableStyle([
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('LEFTPADDING', (0, 0), (-1, -1), 4),
                ('RIGHTPADDING', (0, 0), (-1, -1), 4),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                # Bordes redondeados IGUALES a las cajas superiores
                ('ROUNDEDCORNERS', [6, 6, 6, 6]),  # Mismos bordes que las cajas superiores
                ('BOX', (0, 0), (-1, -1), 2, colors.HexColor('#bdc3c7')),
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#fafbfc')),
            ]))
            
            return contenedor
        
        # Crear los tres rankings con diseño premium y colores modernos
        ranking_ortg = crear_ranking_premium(
            "🎯 OFFENSIVE RATING", 
            df_grupo_sorted_ortg, 'ORtg', nombre_equipo,
            colors.HexColor('#00b894'),  # Verde moderno
            colors.HexColor('#55efc4')   # Verde claro
        )
        
        ranking_drtg = crear_ranking_premium(
            "🛡️ DEFENSIVE RATING", 
            df_grupo_sorted_drtg, 'DRtg', nombre_equipo,
            colors.HexColor('#e17055'),  # Rojo coral
            colors.HexColor('#fab1a0')   # Rosa claro
        )
        
        ranking_ritmo = crear_ranking_premium(
            "⚡ RITMO", 
            df_grupo_sorted_ritmo, 'Ritmo', nombre_equipo,
            colors.HexColor('#0984e3'),  # Azul moderno
            colors.HexColor('#74b9ff')   # Azul claro
        )
        
        # Crear layout con rankings más anchos
        separador = Table([[""],], colWidths=[0.4*inch])  # Espaciador ajustado para rankings más anchos
        separador.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, -1), colors.white)]))
        
        # Colocar rankings más anchos para mejor legibilidad
        tabla_rankings = Table([[ranking_ortg, separador, ranking_drtg, separador, ranking_ritmo]], 
                            colWidths=[2.3*inch, 0.4*inch, 2.3*inch, 0.4*inch, 2.3*inch])
        tabla_rankings.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ]))
        
        tabla_rankings.hAlign = 'CENTER'
        story.append(tabla_rankings)

        # ============== PÁGINA: RANKINGS DE EQUIPOS ==============
        # Crear página de rankings de equipos
        crear_pagina_rankings_equipos(story, rankings_equipos, df_grupo, equipo_data['Equipo'], styles)

        # ============== NUEVA PÁGINA: GRÁFICO OFFENSIVE VS DEFENSIVE RATING ==============
        def nombres_similares(nombre1, nombre2):
            """
            Compara dos nombres de equipos de manera más robusta,
            ignorando diferencias menores como espacios extra o caracteres especiales.
            """
            def normalizar_nombre(nombre):
                import re
                # Convertir a mayúsculas y eliminar espacios extra y caracteres especiales
                return re.sub(r'[^A-Z0-9]', '', str(nombre).upper().strip())
            
            return normalizar_nombre(nombre1) == normalizar_nombre(nombre2)
        
        def crear_grafico_ratings(df_equipos, equipo_seleccionado):
            """Crea un gráfico scatter con fotos de equipos mostrando ORtg vs DRtg"""
            from pathlib import Path
            # Configurar matplotlib
            plt.style.use('default')
            fig, ax = plt.subplots(figsize=(10, 8))
            
            # Configurar colores y estilo
            ax.set_facecolor('#f8f9fa')
            fig.patch.set_facecolor('white')
            
            # Obtener datos de rating
            x_data = df_equipos['DRtg'].values  # Defensive Rating (será invertido en el eje)
            y_data = df_equipos['ORtg'].values  # Offensive Rating
            
            # Invertir el eje X para que menor DRtg esté a la derecha (mejor defensa)
            ax.invert_xaxis()
            
            # Configurar límites con margen
            x_margin = (x_data.max() - x_data.min()) * 0.1
            y_margin = (y_data.max() - y_data.min()) * 0.1
            ax.set_xlim(x_data.max() + x_margin, x_data.min() - x_margin)
            ax.set_ylim(y_data.min() - y_margin, y_data.max() + y_margin)
            
            # Añadir líneas de referencia (promedios)
            avg_ortg = y_data.mean()
            avg_drtg = x_data.mean()
            ax.axhline(y=avg_ortg, color='gray', linestyle='--', alpha=0.5, linewidth=1)
            ax.axvline(x=avg_drtg, color='gray', linestyle='--', alpha=0.5, linewidth=1)
            
            # Añadir cuadrantes con etiquetas
            ax.text(x_data.min() + x_margin, y_data.max() - y_margin*0.5, 'ELITE\n(Buen ataque y defensa)', 
                   ha='left', va='top', fontsize=10, alpha=0.7, 
                   bbox=dict(boxstyle="round,pad=0.3", facecolor='lightgreen', alpha=0.3))
            
            ax.text(x_data.max() - x_margin, y_data.max() - y_margin*0.5, 'OFENSIVO\n(Buen ataque, mala defensa)', 
                   ha='right', va='top', fontsize=10, alpha=0.7,
                   bbox=dict(boxstyle="round,pad=0.3", facecolor='orange', alpha=0.3))
            
            ax.text(x_data.min() + x_margin, y_data.min() + y_margin*0.5, 'DEFENSIVO\n(Mal ataque, buena defensa)', 
                   ha='left', va='bottom', fontsize=10, alpha=0.7,
                   bbox=dict(boxstyle="round,pad=0.3", facecolor='lightblue', alpha=0.3))
            
            ax.text(x_data.max() - x_margin, y_data.min() + y_margin*0.5, 'NECESITA MEJORAR\n(Mal ataque y defensa)', 
                   ha='right', va='bottom', fontsize=10, alpha=0.7,
                   bbox=dict(boxstyle="round,pad=0.3", facecolor='lightcoral', alpha=0.3))
            
            # Colocar fotos de equipos
            for _, row in df_equipos.iterrows():
                nombre_equipo = row['Equipo']
                x_pos = row['DRtg']
                y_pos = row['ORtg']
                
                # Obtener la ruta del logo desde la columna logo_path del dataframe
                imagen_path = None
                if 'logo_path' in row and pd.notna(row['logo_path']) and row['logo_path']:
                    logo_path = Path(row['logo_path'])
                    if logo_path.exists():
                        imagen_path = logo_path
                
                if imagen_path:
                    try:
                        # Cargar y redimensionar imagen
                        img = mpimg.imread(imagen_path)
                        # Corregir el espejo invirtiendo horizontalmente
                        img = np.fliplr(img)
                        
                        # Crear un zoom box para la imagen
                        zoom = 0.08  # Tamaño de la imagen
                        if nombres_similares(nombre_equipo, equipo_seleccionado):
                            zoom = 0.12  # Imagen más grande para el equipo seleccionado
                            # Añadir borde dorado al equipo seleccionado
                            circle = plt.Circle((x_pos, y_pos), radius=zoom*30, fill=False, 
                                              color='gold', linewidth=3)
                            ax.add_patch(circle)
                        
                        # Calcular extensión de la imagen
                        x_extent = zoom * (x_data.max() - x_data.min())
                        y_extent = zoom * (y_data.max() - y_data.min())
                        
                        extent = [x_pos - x_extent/2, x_pos + x_extent/2, 
                                 y_pos - y_extent/2, y_pos + y_extent/2]
                        
                        ax.imshow(img, extent=extent, aspect='auto', zorder=10)
                        
                    except Exception as e:
                        # Si hay error cargando la imagen, usar punto coloreado
                        color = 'red' if nombres_similares(nombre_equipo, equipo_seleccionado) else 'blue'
                        ax.scatter(x_pos, y_pos, s=100, c=color, alpha=0.7, zorder=10)
                        ax.text(x_pos, y_pos-1, nombre_equipo[:8], ha='center', va='top', 
                               fontsize=6, weight='bold')
                else:
                    # Si no hay imagen, usar punto coloreado
                    color = 'red' if nombres_similares(nombre_equipo, equipo_seleccionado) else 'blue'
                    ax.scatter(x_pos, y_pos, s=100, c=color, alpha=0.7, zorder=10)
                    ax.text(x_pos, y_pos-1, nombre_equipo[:8], ha='center', va='top', 
                           fontsize=6, weight='bold')
            
            # Configurar etiquetas y título
            ax.set_xlabel('Defensive Rating (invertido - mejor hacia la derecha)', fontsize=12, weight='bold')
            ax.set_ylabel('Offensive Rating (mejor hacia arriba)', fontsize=12, weight='bold')
            ax.set_title('ANÁLISIS OFENSIVO vs DEFENSIVO POR EQUIPO', fontsize=16, weight='bold', pad=20)
            
            # Añadir grid sutil
            ax.grid(True, alpha=0.3, linestyle='-', linewidth=0.5)
            
            # Ajustar diseño
            plt.tight_layout()
            
            # Guardar en memoria como imagen
            img_buffer = io.BytesIO()
            plt.savefig(img_buffer, format='png', dpi=150, bbox_inches='tight', 
                       facecolor='white', edgecolor='none')
            img_buffer.seek(0)
            plt.close()  # Cerrar para liberar memoria
            
            return img_buffer

        # Crear y añadir el gráfico
        story.append(PageBreak())
        
        # Título de la página
        titulo_grafico_style = ParagraphStyle(
            'TituloGrafico',
            parent=styles['Heading1'],
            fontSize=28,
            spaceAfter=20,
            alignment=TA_CENTER,
            textColor=colors.HexColor('#2c3e50'),
            fontName='Helvetica-Bold'
        )
        
        titulo_grafico = Paragraph("POSICIONAMIENTO COMPETITIVO", titulo_grafico_style)
        story.append(titulo_grafico)
        story.append(Spacer(1, 20))
        
        # Crear el gráfico
        grafico_buffer = crear_grafico_ratings(df_grupo, nombre_equipo)
        
        # Convertir buffer a Image para ReportLab
        imagen_grafico = Image(grafico_buffer, width=7.5*inch, height=6*inch)
        imagen_grafico.hAlign = 'CENTER'
        story.append(imagen_grafico)
        
        # Añadir explicación
        explicacion_style = ParagraphStyle(
            'Explicacion',
            parent=styles['Normal'],
            fontSize=10,
            spaceAfter=10,
            alignment=TA_CENTER,
            textColor=colors.HexColor('#555555')
        )
        
        explicacion = Paragraph(
            "Este gráfico muestra la posición de cada equipo según su rendimiento ofensivo (eje vertical) y defensivo (eje horizontal invertido).<br/>"
            "Los equipos en la esquina superior derecha tienen el mejor balance ofensivo-defensivo.", 
            explicacion_style
        )
        story.append(Spacer(1, 15))
        story.append(explicacion)

        # ============== CUARTA PÁGINA Y SIGUIENTES: ESTADÍSTICAS INDIVIDUALES ==============
        story.append(PageBreak())
        
        # Usar solo jugadores principales para la página de estadísticas individuales
        df_jugadores_principales = df_principales.copy()
        df_jugadores_principales['MIN/PJ'] = df_jugadores_principales['MIN'] / df_jugadores_principales['PJ'] / 60  # Convertir a minutos por partido
        
        # Función para crear tarjeta de jugador con foto y estadísticas (más compacta)
        def crear_tarjeta_jugador(jugador_data):
            nombre = jugador_data['Jugador']
            foto_path = jugador_data['foto_path']
            partidos_jugados = int(jugador_data['PJ'])  # Obtener partidos jugados
            
            # Calcular estadísticas por partido
            min_por_partido_segundos = jugador_data['MIN/PJ'] * 60  # Convertir de vuelta a segundos
            minutos = int(min_por_partido_segundos // 60)
            segundos = int(min_por_partido_segundos % 60)
            min_formato = f"{minutos}:{segundos:02d}"  # Formato MM:SS
            
            pts_por_partido = round(jugador_data['PTS/PJ'], 1)
            fg2_pct = round(jugador_data['FG2%'], 1) if not pd.isna(jugador_data['FG2%']) else 0.0
            fg3_pct = round(jugador_data['FG3%'], 1) if not pd.isna(jugador_data['FG3%']) else 0.0
            ast_por_partido = round(jugador_data['AST/PJ'], 1)
            fg3a_por_partido = round(jugador_data['FG3A/PJ'], 1)
            
            # Estilos para la tarjeta (más compactos)
            partidos_style = ParagraphStyle(
                'PartidosJugador',
                fontSize=6,  # Muy pequeño
                textColor=colors.HexColor('#666666'),
                alignment=2,  # Alineado a la derecha
                fontName='Helvetica',
                leading=7,
                spaceAfter=2
            )
            
            nombre_style = ParagraphStyle(
                'NombreJugador',
                fontSize=9,  # Más pequeño
                textColor=colors.HexColor('#1a365d'),
                alignment=1,  # Centrado
                fontName='Helvetica-Bold',
                leading=10,
                spaceAfter=3
            )
            
            estadistica_jugador_style = ParagraphStyle(
                'EstadisticaJugador',
                fontSize=7,  # Más pequeño
                textColor=colors.HexColor('#2d3748'),
                alignment=1,  # Centrado
                fontName='Helvetica',
                leading=8,
                spaceAfter=1
            )
            
            numero_jugador_style = ParagraphStyle(
                'NumeroJugador',
                fontSize=10,  # Más pequeño
                textColor=colors.HexColor('#2b6cb0'),
                alignment=1,  # Centrado
                fontName='Helvetica-Bold',
                leading=11,
                spaceAfter=1
            )
            
            # Crear datos de la tarjeta
            datos_tarjeta = []
            
            # Fila 1: Foto del jugador (más pequeña)
            if foto_path and os.path.exists(foto_path):
                try:
                    foto_jugador = Image(foto_path, width=1.1*inch, height=1.1*inch, kind='proportional')
                    datos_tarjeta.append([foto_jugador])
                except:
                    datos_tarjeta.append([Paragraph("📷", ParagraphStyle('', fontSize=20, alignment=1))])
            else:
                datos_tarjeta.append([Paragraph("👤", ParagraphStyle('', fontSize=20, alignment=1))])
            
            # Fila 2: Partidos jugados (en pequeño)
            datos_tarjeta.append([Paragraph(f"({partidos_jugados} partidos)", partidos_style)])
            
            # Fila 3: Nombre del jugador
            datos_tarjeta.append([Paragraph(nombre, nombre_style)])
            
            # Fila 4: Minutos por partido (formato MM:SS)
            datos_tarjeta.append([Paragraph(f"{min_formato}", numero_jugador_style)])
            datos_tarjeta.append([Paragraph("MIN PP", estadistica_jugador_style)])
            
            # Fila 5: Puntos por partido
            datos_tarjeta.append([Paragraph(f"{pts_por_partido}", numero_jugador_style)])
            datos_tarjeta.append([Paragraph("PTS PP", estadistica_jugador_style)])
            
            # Fila 6: % Tiros de 2
            datos_tarjeta.append([Paragraph(f"{fg2_pct}%", numero_jugador_style)])
            datos_tarjeta.append([Paragraph("% T2", estadistica_jugador_style)])
            
            # Fila 7: % Tiros de 3 y Triples intentados COMBINADOS en una sola celda
            t3_combinado = f"{fg3_pct}% / {fg3a_por_partido}"
            datos_tarjeta.append([Paragraph(t3_combinado, numero_jugador_style)])
            datos_tarjeta.append([Paragraph("% T3 / T3 INT PP", estadistica_jugador_style)])
            
            # Fila 8: Asistencias por partido
            datos_tarjeta.append([Paragraph(f"{ast_por_partido}", numero_jugador_style)])
            datos_tarjeta.append([Paragraph("AST PP", estadistica_jugador_style)])
            
            # Fila 9: Porcentaje de Uso
            usg_pct = jugador_data.get('USG%', 0.0)
            datos_tarjeta.append([Paragraph(f"{usg_pct}%", numero_jugador_style)])
            datos_tarjeta.append([Paragraph("USG%", estadistica_jugador_style)])
            
            # Crear tabla de la tarjeta (más compacta para caber 6 jugadores por página)
            tabla_jugador = Table(datos_tarjeta, colWidths=[2.3*inch], rowHeights=[0.9*inch, 0.15*inch, 0.22*inch, 0.18*inch, 0.16*inch, 0.18*inch, 0.16*inch, 0.18*inch, 0.16*inch, 0.18*inch, 0.16*inch, 0.18*inch, 0.16*inch, 0.18*inch, 0.16*inch])
            
            tabla_jugador.setStyle(TableStyle([
                # Fondo y bordes
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8f9fa')),
                ('ROUNDEDCORNERS', [6, 6, 6, 6]),
                ('BOX', (0, 0), (-1, -1), 2, colors.HexColor('#1976d2')),
                
                # Alineación
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                
                # Padding uniforme (más compacto)
                ('LEFTPADDING', (0, 0), (-1, -1), 4),
                ('RIGHTPADDING', (0, 0), (-1, -1), 4),
                ('TOPPADDING', (0, 0), (-1, -1), 2),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
                
                # Destacar el nombre del jugador
                ('BACKGROUND', (0, 2), (-1, 2), colors.HexColor('#e3f2fd')),
                
                # Separar secciones con líneas sutiles
                ('LINEBELOW', (0, 2), (-1, 2), 1, colors.HexColor('#bbdefb')),
                ('LINEBELOW', (0, 4), (-1, 4), 0.5, colors.HexColor('#e0e0e0')),
                ('LINEBELOW', (0, 6), (-1, 6), 0.5, colors.HexColor('#e0e0e0')),
                ('LINEBELOW', (0, 8), (-1, 8), 0.5, colors.HexColor('#e0e0e0')),
                ('LINEBELOW', (0, 10), (-1, 10), 0.5, colors.HexColor('#e0e0e0')),
                ('LINEBELOW', (0, 12), (-1, 12), 0.5, colors.HexColor('#e0e0e0')),
            ]))
            
            return tabla_jugador
        
        # Crear tarjetas solo para jugadores principales
        tarjetas_jugadores = []
        for _, jugador in df_jugadores_principales.iterrows():
            tarjeta = crear_tarjeta_jugador(jugador)
            tarjetas_jugadores.append(tarjeta)
        
        # Calcular cuántas páginas se necesitan (6 jugadores por página)
        jugadores_por_pagina = 6
        total_jugadores = len(tarjetas_jugadores)
        paginas_necesarias = (total_jugadores + jugadores_por_pagina - 1) // jugadores_por_pagina
        
        # Procesar cada página de estadísticas individuales
        for pagina_num in range(paginas_necesarias):
            # Añadir título solo en la primera página
            if pagina_num == 0:
                titulo_individuales = Paragraph("ESTADÍSTICAS INDIVIDUALES", titulo_style)
                story.append(titulo_individuales)
            else:
                # Para páginas adicionales, añadir título con continuación
                titulo_continuacion = Paragraph("ESTADÍSTICAS INDIVIDUALES (cont.)", titulo_style)
                story.append(titulo_continuacion)
            
            # Añadir más espacio después del título para evitar solapamiento
            story.append(Spacer(1, 0.4*inch))
            
            # Obtener jugadores para esta página
            inicio_jugador = pagina_num * jugadores_por_pagina
            fin_jugador = min(inicio_jugador + jugadores_por_pagina, total_jugadores)
            jugadores_pagina = tarjetas_jugadores[inicio_jugador:fin_jugador]
            
            # Organizar tarjetas en filas de 3 jugadores
            filas_tarjetas = []
            for i in range(0, len(jugadores_pagina), 3):
                fila = jugadores_pagina[i:i+3]
                
                # Rellenar con espacios vacíos si la fila no está completa
                while len(fila) < 3:
                    espacio_vacio = Table([[""]], colWidths=[2.3*inch])
                    espacio_vacio.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, -1), colors.white)]))
                    fila.append(espacio_vacio)
                
                filas_tarjetas.append(fila)
            
            # Crear tabla principal con todas las tarjetas (3 por fila, más compactas)
            for fila in filas_tarjetas:
                tabla_fila = Table([fila], colWidths=[2.4*inch, 2.4*inch, 2.4*inch])
                tabla_fila.setStyle(TableStyle([
                    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('LEFTPADDING', (0, 0), (-1, -1), 0.05*inch),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 0.05*inch),
                    ('TOPPADDING', (0, 0), (-1, -1), 0.05*inch),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 0.05*inch),
                ]))
                tabla_fila.hAlign = 'CENTER'
                story.append(tabla_fila)
                story.append(Spacer(1, 0.2*inch))  # Espacio entre filas de tarjetas
            
            # Añadir salto de página si no es la última página
            if pagina_num < paginas_necesarias - 1:
                story.append(PageBreak())

        # ============== PÁGINA FINAL: RANKINGS INDIVIDUALES ==============
        # Crear página de rankings de jugadores
        crear_pagina_rankings(story, rankings, styles)
        
        # Construir PDF
        doc.build(story)
        #print(f"PDF generado: {output_path}")
        
        return output_path
    
    # Crear rankings de equipos
    rankings_equipos = crear_rankings_equipos(df_grupo)
    
    pdf_path = generar_pdf_informe(
        equipo_data=equipo_data,
        df_jugadores_norm=df_jugadores_norm,
        df_principales=df_principales,
        df_apoyo=df_apoyo,
        rankings=rankings,
        df_grupo=df_grupo,
        rankings_equipos=rankings_equipos
    )

    return pdf_path

def main():
    from pathlib import Path

    # ---------------- CONFIGURACIÓN (ajusta estos tres valores) ----------------
    JSON_PATH = Path("data") / "datos2.json"   # Ruta al JSON
    liga   = "3ª FEB"                                  # p.ej.: "EBA", "2ª FEB", "1ª FEB"
    grupo  = "Liga Regular \"E-B\""                     # p.ej.: 'Liga Regular "A-A"'
    equipo = "C.B. JORGE JUAN TÁRTAROS GONZALO CASTELLÓ"                           # nombre EXACTO del equipo tal como aparece en el JSON
    # ---------------------------------------------------------------------------

    #print(f"Ruta del JSON: {JSON_PATH.absolute()}")
    a= generar_pdf(JSON_PATH, liga, grupo, equipo)
    print(a)

if __name__ == "__main__":
    main()


