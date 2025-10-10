"""
FEBScrapper: Clase que reproduce la lógica del notebook `feb.ipynb`.

Funciones principales:
 - Obtener equipos por grupos (Liga Regular) para una liga/categoría.
 - Obtener estadísticas detalladas por equipo y jugador.
 - Normalizar estadísticas a formato numérico y unificar por jugador.
 - Generar ficheros JSON: por liga(s) y completos para todas las categorías FEB.

Nota: Esta clase usa peticiones HTTP a baloncestoenvivo.feb.es y respeta pequeñas pausas
para no sobrecargar el servidor.
"""

from __future__ import annotations

from bs4 import BeautifulSoup
import requests
import pandas as pd
import json
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple


class FEBScrapper:
    """Scraper de FEB que replica las funciones del notebook.

    Args:
        season: Temporada (año) a consultar, por defecto "2024".
        pause: Pausa (segundos) entre peticiones para no sobrecargar el servidor.
        session: Sesión de requests opcional (se crea una si no se pasa).
    """

    BASE_RESULTS_URL = "https://baloncestoenvivo.feb.es/resultados/ligaeba/{code}/{season}"

    CATEGORY_URLS = {
        "1ª FEB": 1,
        "2ª FEB": 2,
        "3ª FEB": 3,
    }

    def __init__(self, season: str = "2024", pause: float = 1.0, session: Optional[requests.Session] = None):
        self.season = str(season)
        self.pause = float(pause)
        self.session = session or requests.Session()

    # =============================
    # Utilidades de parsing/HTML
    # =============================
    @staticmethod
    def extract_form_fields(soup: BeautifulSoup) -> Dict[str, str]:
        return {
            "__VIEWSTATE": soup.find(id="__VIEWSTATE")["value"] if soup.find(id="__VIEWSTATE") else "",
            "__VIEWSTATEGENERATOR": soup.find(id="__VIEWSTATEGENERATOR")["value"] if soup.find(id="__VIEWSTATEGENERATOR") else "",
            "__EVENTVALIDATION": soup.find(id="__EVENTVALIDATION")["value"] if soup.find(id="__EVENTVALIDATION") else "",
        }

    @staticmethod
    def obtener_equipos_from_soup(soup: BeautifulSoup) -> List[Tuple[str, str, int, int, int]]:
        equipos: List[Tuple[str, str, int, int, int]] = []
        rows = soup.select('#_ctl0_MainContentPlaceHolderMaster_clasificacionDataGrid tr')
        for fila in rows[1:]:  # saltar cabecera
            enlace = fila.find('a')
            celda = fila.find_all('td')
            if enlace and len(celda) >= 7:
                try:
                    nombre = enlace.text.strip()
                    url_equipo = enlace['href']
                    puntos_favor = int(celda[5].text.strip())
                    puntos_en_contra = int(celda[6].text.strip())
                    partidos_jugados = int(celda[2].text.strip())
                    partidos_ganados = int(celda[3].text.strip())
                    partidos_perdidos = int(celda[4].text.strip())
                    equipos.append((nombre, url_equipo, puntos_favor, puntos_en_contra, partidos_jugados, partidos_ganados, partidos_perdidos))
                except Exception:
                    # Saltar filas inesperadas
                    continue
        return equipos

    # =============================
    # Navegación por grupos/ligas
    # =============================
    def _results_url(self, category_code: int) -> str:
        return self.BASE_RESULTS_URL.format(code=category_code, season=self.season)

    def _get_grupos_options(self, results_url: str, only_liga_regular: bool = True) -> Dict[str, str]:
        """Devuelve mapping value->label del select de grupos.

        Si only_liga_regular=True, filtra por opciones que contengan "Liga Regular".
        """
        response = self.session.get(results_url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        select = soup.find("select", {"id": "_ctl0_MainContentPlaceHolderMaster_gruposDropDownList"})
        if not select:
            return {}
        options = select.find_all("option")

        if only_liga_regular:
            return {opt.get("value", ""): opt.text.strip() for opt in options if "Liga Regular" in opt.text}
        else:
            return {opt.get("value", ""): opt.text.strip() for opt in options}

    def get_equipos_dataframe_for_category(self, category: str, only_liga_regular: bool = True) -> pd.DataFrame:
        """Obtiene DataFrame de equipos para una categoría (1ª FEB, 2ª FEB, EBA)."""
        if category not in self.CATEGORY_URLS:
            raise ValueError(f"Categoría no soportada: {category}")

        url = self._results_url(self.CATEGORY_URLS[category])
        grupos = self._get_grupos_options(url, only_liga_regular=only_liga_regular)

        todos_los_equipos: List[Dict] = []
        for value, label in grupos.items():
            # Refrescar VIEWSTATE
            page_response = self.session.get(url)
            page_response.raise_for_status()
            soup = BeautifulSoup(page_response.text, "html.parser")
            form_data = self.extract_form_fields(soup)

            # Preparar POST
            form_data.update({
                "__EVENTTARGET": "_ctl0$MainContentPlaceHolderMaster$gruposDropDownList",
                "__EVENTARGUMENT": "",
                "_ctl0:MainContentPlaceHolderMaster:gruposDropDownList": value,
            })

            # POST y parseo
            post_response = self.session.post(url, data=form_data)
            post_response.raise_for_status()
            post_soup = BeautifulSoup(post_response.text, "html.parser")
            equipos = self.obtener_equipos_from_soup(post_soup)

            for eq in equipos:
                todos_los_equipos.append({
                    "categoria": category,
                    "grupo": label,
                    "equipo": eq[0],
                    "url": eq[1],
                    "p_favor": eq[2],
                    "p_contra": eq[3],
                    "jugados": eq[4],
                    "ganados": eq[5],
                    "perdidos": eq[6],
                })

            time.sleep(self.pause)

        return pd.DataFrame(todos_los_equipos)

    def obtener_todos_los_equipos_feb(self) -> pd.DataFrame:
        """Obtiene todos los equipos de 1ª FEB, 2ª FEB y 3ª FEB (Liga Regular)."""
        dfs = []
        for categoria in ["1ª FEB", "2ª FEB", "3ª FEB"]:
            print(f"Procesando categoría: {categoria}")
            df_cat = self.get_equipos_dataframe_for_category(categoria, only_liga_regular=True)
            dfs.append(df_cat)
        if dfs:
            return pd.concat(dfs, ignore_index=True)
        return pd.DataFrame(columns=["categoria", "grupo", "equipo", "url", "p_favor", "p_contra", "jugados", "ganados", "perdidos"])

    # =============================
    # Estadísticas de equipo/jugador
    # =============================
    @staticmethod
    def obtener_enlace_stats(url_equipo: str) -> str:
        codigo_equipo = url_equipo.split("i=")[-1]
        return f"https://baloncestoenvivo.feb.es/estadisticasacumuladas/{codigo_equipo}"

    @staticmethod
    def obtener_estadisticas(url: str) -> pd.DataFrame:
        """Obtiene DataFrame de estadísticas por jugador (texto original de la web)."""
        response = requests.get(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        jugadores_data: List[List[Optional[str]]] = []
        rows = soup.find_all("tr")[2:]  # omitir cabecera
        for row in rows:
            cols = row.find_all("td")
            if len(cols) > 0:
                nombre_jugador = cols[0].get_text(strip=True)
                enlace_jugador = cols[0].find("a")["href"] if cols[0].find("a") else None
                fase = cols[1].get_text(strip=True)
                partidos = cols[2].get_text(strip=True)
                minutos = cols[3].get_text(strip=True)
                puntos = cols[4].get_text(strip=True)
                tiros_dos = cols[5].get_text(strip=False).split()[0]
                tiros_tres = cols[6].get_text(strip=False).split()[0]
                tiros_campo = cols[7].get_text(strip=False).split()[0]
                tiros_libres = cols[8].get_text(strip=False).split()[0]
                rebotes_ofensivos = cols[9].get_text(strip=True)
                rebotes_defensivos = cols[10].get_text(strip=True)
                rebotes_totales = cols[11].get_text(strip=True)
                asistencias = cols[12].get_text(strip=True)
                recuperaciones = cols[13].get_text(strip=True)
                perdidas = cols[14].get_text(strip=True)
                tapones_favor = cols[15].get_text(strip=True)
                tapones_contra = cols[16].get_text(strip=True)
                mates = cols[17].get_text(strip=True)
                faltas_cometidas = cols[18].get_text(strip=True)
                faltas_recibidas = cols[19].get_text(strip=True)
                valoracion = cols[20].get_text(strip=True)

                jugadores_data.append([
                    nombre_jugador,
                    enlace_jugador,
                    fase,
                    partidos,
                    minutos,
                    puntos,
                    tiros_dos,
                    tiros_tres,
                    tiros_campo,
                    tiros_libres,
                    rebotes_ofensivos,
                    rebotes_defensivos,
                    rebotes_totales,
                    asistencias,
                    recuperaciones,
                    perdidas,
                    tapones_favor,
                    tapones_contra,
                    mates,
                    faltas_cometidas,
                    faltas_recibidas,
                    valoracion,
                ])

        df = pd.DataFrame(
            jugadores_data,
            columns=[
                "Jugador",
                "Enlace",
                "Fase",
                "Partidos",
                "Minutos",
                "Puntos",
                "T2",
                "T3",
                "TC",
                "TL",
                "RO",
                "RD",
                "RT",
                "AS",
                "BR",
                "BP",
                "TapF",
                "TapC",
                "MT",
                "FC",
                "FR",
                "Valoración",
            ],
        )
        # Eliminar última fila si es resumen
        if len(df) > 0:
            df = df.iloc[:-1]
        return df

    # =============================
    # Normalización/Unificación de DataFrames
    # =============================
    @staticmethod
    def _convertir_a_entero(valor) -> int:
        try:
            if pd.isna(valor) or valor == '' or valor is None:
                return 0
            return int(str(valor).strip())
        except (ValueError, TypeError):
            return 0

    @staticmethod
    def _convertir_minutos_a_segundos(minutos_str) -> int:
        try:
            if pd.isna(minutos_str) or minutos_str == '' or minutos_str is None:
                return 0
            if ':' in str(minutos_str):
                partes = str(minutos_str).split(':')
                return int(partes[0]) * 60 + int(partes[1])
            else:
                return int(minutos_str)
        except (ValueError, TypeError):
            return 0

    @staticmethod
    def _dividir_estadistica(stat_str) -> Tuple[int, int]:
        try:
            if pd.isna(stat_str) or stat_str == '' or stat_str is None:
                return 0, 0
            if '/' in str(stat_str):
                partes = str(stat_str).split('/')
                return int(partes[0]), int(partes[1])
            else:
                return int(stat_str), 0
        except (ValueError, TypeError):
            return 0, 0

    def crear_dataframe_numerico(self, df_original: pd.DataFrame) -> pd.DataFrame:
        """Convierte el DataFrame de texto en numérico, expandiendo columnas compuestas."""
        df_numerico = pd.DataFrame()

        # Copiar columnas base
        df_numerico['Jugador'] = df_original['Jugador']
        df_numerico['Enlace'] = df_original['Enlace']
        df_numerico['Fase'] = df_original['Fase']

        # Partidos
        df_numerico['Partidos'] = df_original['Partidos'].apply(self._convertir_a_entero)

        # Minutos a segundos
        df_numerico['Minutos_segundos'] = df_original['Minutos'].apply(self._convertir_minutos_a_segundos)

        # Puntos
        df_numerico['Puntos'] = df_original['Puntos'].apply(self._convertir_a_entero)

        # Dividir T2/T3/TC/TL
        df_numerico[['T2M', 'T2A']] = df_original['T2'].apply(lambda x: pd.Series(self._dividir_estadistica(x)))
        df_numerico[['T3M', 'T3A']] = df_original['T3'].apply(lambda x: pd.Series(self._dividir_estadistica(x)))
        df_numerico[['TCM', 'TCA']] = df_original['TC'].apply(lambda x: pd.Series(self._dividir_estadistica(x)))
        df_numerico[['TLM', 'TLA']] = df_original['TL'].apply(lambda x: pd.Series(self._dividir_estadistica(x)))

        # Resto
        columnas_numericas = ['RO', 'RD', 'RT', 'AS', 'BR', 'BP', 'TapF', 'TapC', 'MT', 'FC', 'FR', 'Valoración']
        for col in columnas_numericas:
            df_numerico[col] = df_original[col].apply(self._convertir_a_entero)

        return df_numerico

    def unificar_jugadores_numericos(self, df_numerico: pd.DataFrame) -> pd.DataFrame:
        """Unifica jugadores que aparecen en múltiples fases sumando estadísticas numéricas."""
        df_trabajo = df_numerico.copy()

        # Propagar nombre/enlace si hay filas vacías
        for i in range(len(df_trabajo)):
            if pd.isna(df_trabajo.iloc[i]['Jugador']) or df_trabajo.iloc[i]['Jugador'] == '':
                if i > 0:
                    df_trabajo.iloc[i, df_trabajo.columns.get_loc('Jugador')] = df_trabajo.iloc[i - 1]['Jugador']
                    df_trabajo.iloc[i, df_trabajo.columns.get_loc('Enlace')] = df_trabajo.iloc[i - 1]['Enlace']

        jugadores_agrupados: List[pd.Series] = []
        jugadores_unicos = df_trabajo.groupby(['Jugador', 'Enlace'])

        columnas_numericas = [
            'Partidos', 'Minutos_segundos', 'Puntos', 'T2M', 'T2A', 'T3M', 'T3A',
            'TCM', 'TCA', 'TLM', 'TLA', 'RO', 'RD', 'RT', 'AS', 'BR', 'BP', 'TapF', 'TapC', 'MT', 'FC', 'FR', 'Valoración'
        ]

        for (nombre, enlace), grupo in jugadores_unicos:
            if len(grupo) == 1:
                jugadores_agrupados.append(grupo.iloc[0].copy())
            else:
                fases = grupo['Fase'].tolist()
                fase_unificada = '+'.join(sorted(set(fases)))
                fila_unificada = {
                    'Jugador': nombre,
                    'Enlace': enlace,
                    'Fase': fase_unificada,
                }
                for col in columnas_numericas:
                    fila_unificada[col] = grupo[col].sum()
                jugadores_agrupados.append(pd.Series(fila_unificada))

        df_unificado = pd.DataFrame(jugadores_agrupados).reset_index(drop=True)
        return df_unificado

    # =============================
    # Resúmenes y exportación JSON
    # =============================
    @staticmethod
    def _convertir_numero(valor) -> float:
        try:
            if valor and str(valor).strip() and str(valor) != '-':
                return float(str(valor).replace(',', '.'))
            return 0.0
        except Exception:
            return 0.0

    def calcular_resumen_equipo(self, jugadores: List[Dict]) -> Dict:
        if not jugadores:
            return {}

        resumen = {
            "total_jugadores": len(jugadores),
            "puntos_totales": sum(self._convertir_numero(j.get("puntos", 0)) for j in jugadores),
            "minutos_totales": sum(self._convertir_numero(j.get("minutos_segundos", 0)) / 60 for j in jugadores),
            "rebotes_totales": sum(self._convertir_numero(j.get("rebotes_totales", 0)) for j in jugadores),
            "rebotes_ofensivos_totales": sum(self._convertir_numero(j.get("rebotes_ofensivos", 0)) for j in jugadores),
            "rebotes_defensivos_totales": sum(self._convertir_numero(j.get("rebotes_defensivos", 0)) for j in jugadores),
            "asistencias_totales": sum(self._convertir_numero(j.get("asistencias", 0)) for j in jugadores),
            "valoracion_total": sum(self._convertir_numero(j.get("valoracion", 0)) for j in jugadores),
            "fg2a_total": sum(self._convertir_numero(j.get("tiros_dos_attempted", 0)) for j in jugadores),
            "fg2m_total": sum(self._convertir_numero(j.get("tiros_dos_made", 0)) for j in jugadores),
            "fga_total": sum(self._convertir_numero(j.get("tiros_campo_attempted", 0)) for j in jugadores),
            "fgm_total": sum(self._convertir_numero(j.get("tiros_campo_made", 0)) for j in jugadores),
            "fg3a_total": sum(self._convertir_numero(j.get("tiros_tres_attempted", 0)) for j in jugadores),
            "fg3m_total": sum(self._convertir_numero(j.get("tiros_tres_made", 0)) for j in jugadores),
            "fta_total": sum(self._convertir_numero(j.get("tiros_libres_attempted", 0)) for j in jugadores),
            "ftm_total": sum(self._convertir_numero(j.get("tiros_libres_made", 0)) for j in jugadores),
            "perdidas_totales": sum(self._convertir_numero(j.get("perdidas", 0)) for j in jugadores),
            "recuperaciones_totales": sum(self._convertir_numero(j.get("recuperaciones", 0)) for j in jugadores),


        }

        if resumen["total_jugadores"] > 0:
            resumen["promedio_puntos_por_jugador"] = resumen["puntos_totales"] / resumen["total_jugadores"]
            resumen["promedio_minutos_por_jugador"] = resumen["minutos_totales"] / resumen["total_jugadores"]
            resumen["promedio_valoracion_por_jugador"] = resumen["valoracion_total"] / resumen["total_jugadores"]
        return resumen

    def _equipo_json_from_row(self, row_equipo: pd.Series, nombre_liga: Optional[str], nombre_categoria: Optional[str]) -> Dict:
        nombre = row_equipo['equipo']
        url_equipo = row_equipo['url']
        puntos_favor = int(row_equipo['p_favor'])
        puntos_contra = int(row_equipo['p_contra'])
        partidos_jugados = int(row_equipo['jugados'])
        partidos_ganados = int(row_equipo['ganados'])
        partidos_perdidos = int(row_equipo['perdidos'])

        # Estadísticas
        url_stats = self.obtener_enlace_stats(url_equipo)
        df_stats_texto = self.obtener_estadisticas(url_stats)
        df_stats_num = self.crear_dataframe_numerico(df_stats_texto)
        df_stats_final = self.unificar_jugadores_numericos(df_stats_num)

        jugadores: List[Dict] = []
        if not df_stats_final.empty:
            for _, r in df_stats_final.iterrows():
                jugadores.append({
                    "nombre": r["Jugador"],
                    "enlace": r["Enlace"],
                    "fase": r["Fase"],
                    "partidos": int(r["Partidos"]),
                    "minutos_segundos": int(r["Minutos_segundos"]),
                    "puntos": int(r["Puntos"]),
                    "tiros_dos_made": int(r["T2M"]),
                    "tiros_dos_attempted": int(r["T2A"]),
                    "tiros_tres_made": int(r["T3M"]),
                    "tiros_tres_attempted": int(r["T3A"]),
                    "tiros_campo_made": int(r["TCM"]),
                    "tiros_campo_attempted": int(r["TCA"]),
                    "tiros_libres_made": int(r["TLM"]),
                    "tiros_libres_attempted": int(r["TLA"]),
                    "rebotes_ofensivos": int(r["RO"]),
                    "rebotes_defensivos": int(r["RD"]),
                    "rebotes_totales": int(r["RT"]),
                    "asistencias": int(r["AS"]),
                    "recuperaciones": int(r["BR"]),
                    "perdidas": int(r["BP"]),
                    "tapones_favor": int(r["TapF"]),
                    "tapones_contra": int(r["TapC"]),
                    "mates": int(r["MT"]),
                    "faltas_cometidas": int(r["FC"]),
                    "faltas_recibidas": int(r["FR"]),
                    "valoracion": int(r["Valoración"]),
                })

        equipo_data: Dict = {
            "nombre": nombre,
            "url_equipo": url_equipo,
            "url_estadisticas": url_stats,
            "informacion_general": {
                "puntos_favor": puntos_favor,
                "puntos_contra": puntos_contra,
                "partidos_jugados": partidos_jugados,
                "partidos_ganados": partidos_ganados,
                "partidos_perdidos": partidos_perdidos,
                "diferencia_puntos": puntos_favor - puntos_contra,
            },
            "jugadores": jugadores,
            "resumen_equipo": self.calcular_resumen_equipo(jugadores),
        }
        if nombre_liga is not None:
            equipo_data["liga"] = nombre_liga
        if nombre_categoria is not None:
            equipo_data["categoria"] = nombre_categoria
        return equipo_data

    def crear_base_datos_json_por_ligas(self, df: pd.DataFrame, nombre_archivo: str = "estadisticas_feb_por_ligas.json") -> Dict:
        """Genera JSON agrupando por 'grupo' (lugar de liga) a partir del DataFrame de equipos."""
        base_datos: Dict = {
            "fecha_actualizacion": datetime.now().isoformat(),
            "total_ligas": int(df['grupo'].nunique()) if not df.empty else 0,
            "total_equipos": int(len(df)),
            "ligas": {},
        }

        grupos = df.groupby('grupo') if not df.empty else []
        for nombre_liga, equipos_liga in grupos:
            base_datos["ligas"][nombre_liga] = {
                "nombre": nombre_liga,
                "total_equipos": int(len(equipos_liga)),
                "equipos": [],
            }

            for _, row in equipos_liga.iterrows():
                try:
                    equipo_data = self._equipo_json_from_row(row, nombre_liga=nombre_liga, nombre_categoria=None)
                    base_datos["ligas"][nombre_liga]["equipos"].append(equipo_data)
                    time.sleep(self.pause)
                except Exception as e:
                    print(f"    Error procesando {row.get('equipo')}: {e}")
                    continue

        with open(nombre_archivo, 'w', encoding='utf-8') as f:
            json.dump(base_datos, f, indent=2, ensure_ascii=False)

        return base_datos

    def crear_base_datos_completa_feb(self, nombre_archivo: str = "estadisticas_feb_completas.json") -> Dict:
        """Genera JSON completo organizado por categoría y grupo para 1ª FEB, 2ª FEB y EBA."""
        df_completo = self.obtener_todos_los_equipos_feb()

        base_datos: Dict = {
            "fecha_actualizacion": datetime.now().isoformat(),
            "total_categorias": int(df_completo['categoria'].nunique()) if not df_completo.empty else 0,
            "total_grupos": int(df_completo['grupo'].nunique()) if not df_completo.empty else 0,
            "total_equipos": int(len(df_completo)),
            "categorias": {},
        }

        if df_completo.empty:
            with open(nombre_archivo, 'w', encoding='utf-8') as f:
                json.dump(base_datos, f, indent=2, ensure_ascii=False)
            return base_datos

        por_categoria = df_completo.groupby('categoria')
        for nombre_categoria, equipos_categoria in por_categoria:
            base_datos["categorias"][nombre_categoria] = {
                "nombre": nombre_categoria,
                "total_grupos": int(equipos_categoria['grupo'].nunique()),
                "total_equipos": int(len(equipos_categoria)),
                "grupos": {},
            }

            por_grupo = equipos_categoria.groupby('grupo')
            for nombre_grupo, equipos_grupo in por_grupo:
                base_datos["categorias"][nombre_categoria]["grupos"][nombre_grupo] = {
                    "nombre": nombre_grupo,
                    "categoria": nombre_categoria,
                    "total_equipos": int(len(equipos_grupo)),
                    "equipos": [],
                }

                for _, row in equipos_grupo.iterrows():
                    try:
                        equipo_data = self._equipo_json_from_row(
                            row, nombre_liga=nombre_grupo, nombre_categoria=nombre_categoria
                        )
                        base_datos["categorias"][nombre_categoria]["grupos"][nombre_grupo]["equipos"].append(equipo_data)
                        time.sleep(self.pause)
                    except Exception as e:
                        print(f"      Error procesando {row.get('equipo')}: {e}")
                        continue

        with open(nombre_archivo, 'w', encoding='utf-8') as f:
            json.dump(base_datos, f, indent=2, ensure_ascii=False)

        return base_datos


def _demo():
    """Ejecución de ejemplo similar al notebook.

    - Genera JSON por ligas para EBA (Liga Regular).
    - Genera JSON completo para 1ª FEB, 2ª FEB y EBA.
    """
    scraper = FEBScrapper(season="2025", pause=1.0)

    # Por ligas: EBA (Liga Regular)
    #print("Obteniendo equipos EBA (Liga Regular)...")
    #df_eba = scraper.get_equipos_dataframe_for_category("EBA", only_liga_regular=True)
    #print(f"Equipos EBA: {len(df_eba)}")
    #scraper.crear_base_datos_json_por_ligas(df_eba, nombre_archivo="estadisticas_feb_por_ligas.json")

    # Completa: 1ª FEB, 2ª FEB y EBA (Liga Regular)
    print("\nCreando base de datos completa FEB...")
    scraper.crear_base_datos_completa_feb(nombre_archivo="2025.json")


if __name__ == "__main__":
    _demo()
