import streamlit as st
import pandas as pd
import json
import pydeck as pdk
from db import get_connection
from permisos import validar_acceso


def render():
    # =========================
    # Control de acceso
    # =========================
    validar_acceso("Dashboards")

    usuario = st.session_state["usuario"]
    if usuario["perfil"] not in (1,5):
        st.error("⛔ Acceso exclusivo para Administrador / Coordinador / Supervisor")
        st.stop()

    st.title("📊 Dashboards")
    conn = get_connection()

    # =====================================================
    # A) RESUMEN DE PERSONAL ACTIVO
    # =====================================================
    st.subheader("👥 Personal activo")

    df_personal = pd.read_sql("""
        SELECT puesto, COUNT(*) AS cantidad
        FROM personal
        WHERE estado = 'activo'
        GROUP BY puesto
        ORDER BY puesto
    """, conn)

    total_personal = df_personal["cantidad"].sum()

    df_personal_resumen = pd.concat(
        [
            pd.DataFrame([{"puesto": "TOTAL", "cantidad": total_personal}]),
            df_personal
        ],
        ignore_index=True
    )

    st.dataframe(df_personal_resumen, use_container_width=True)
    st.divider()

    # =====================================================
    # FILTRO GLOBAL DE FECHAS (INFORMATIVO)
    # =====================================================
    st.subheader("📅 Filtro de fechas")

    col1, col2 = st.columns(2)
    with col1:
        fecha_inicio = st.date_input("Desde")
    with col2:
        fecha_fin = st.date_input("Hasta")

    st.divider()

    # =====================================================
    # MAPA – ESTADO POR BLOQUES (ASIGNACIONES)
    # =====================================================
    st.subheader("🗺️ Estado por bloques")

    df_regiones = pd.read_sql("""
        SELECT DISTINCT region
        FROM asignaciones
        WHERE region IS NOT NULL
        ORDER BY region
    """, conn)

    lista_regiones = ["Todas"] + df_regiones["region"].tolist()

    col1, col2, col3 = st.columns(3)
    with col1:
        st.date_input("Desde (mapa)", value=fecha_inicio, key="map_ini", disabled=True)
    with col2:
        st.date_input("Hasta (mapa)", value=fecha_fin, key="map_fin", disabled=True)
    with col3:
        region_seleccionada = st.selectbox("Región", lista_regiones)

    where_region = ""
    params = []

    if region_seleccionada != "Todas":
        where_region = " WHERE a.region = %s"
        params.append(region_seleccionada)

    df_asig = pd.read_sql(f"""
        SELECT
            a.region,
            a.asignacion,
            a.bloque,
            a.estado_actual,
            a.proceso_actual,
            COALESCE(p.nombre_completo, '—') AS operador
        FROM asignaciones a
        LEFT JOIN personal p
            ON p.cedula = a.operador_actual
        {where_region}
    """, conn, params=params)

    info_por_bloque = {
        (row["region"], row["asignacion"], int(row["bloque"])): {
            "estado": str(row["estado_actual"]).lower().strip(),
            "estado_raw": row["estado_actual"],
            "proceso": row["proceso_actual"],
            "operador": row["operador"]
        }
        for _, row in df_asig.iterrows()
    }

    with open("italia.geojson", "r", encoding="utf-8") as f:
        geojson = json.load(f)

    for feature in geojson["features"]:
        region_geo = str(feature["properties"]["region"]).strip()
        asignacion_geo = str(feature["properties"]["Asignacion"]).strip()
        bloque_geo = int(feature["properties"]["BLOQUE"])

        key = (region_geo, asignacion_geo, bloque_geo)

        if key in info_por_bloque:
            info = info_por_bloque[key]
            estado = info["estado"]

            if estado == "finalizado" or estado == "aprobado":
                color = [52, 152, 219, 180] 
            elif estado == "asignado":
                color = [241, 196, 15, 180]  
            elif estado == "pendiente":
                color = [200, 200, 200, 180]
            elif estado == "proceso":
                color = [46, 204, 113, 180]
            elif estado.startswith("rechazado"):
                color = [255, 0, 0, 180]
            else:
                color = [241, 196, 15, 180]

            feature["properties"]["color"] = color
            feature["properties"]["operador"] = info["operador"]
            feature["properties"]["estado_actual"] = info["estado_raw"]
            feature["properties"]["proceso_actual"] = info["proceso"]
        else:
            feature["properties"]["color"] = [220, 220, 220, 140]
            feature["properties"]["operador"] = "—"
            feature["properties"]["estado_actual"] = "—"
            feature["properties"]["proceso_actual"] = "—"

    layer = pdk.Layer(
        "GeoJsonLayer",
        data=geojson,
        filled=True,
        get_fill_color="properties.color",
        stroked=True,
        get_line_color=[60, 60, 60, 255],
        line_width_min_pixels=1,
        pickable=True,
        auto_highlight=True,
    )

    deck = pdk.Deck(
        layers=[layer],
        initial_view_state=pdk.ViewState(
            latitude=44.2,
            longitude=9.44,
            zoom=6.5
        ),
        map_style=None,
        views=[pdk.View(type="MapView", controller=True)],
        tooltip={
            "html": """
            <b>Región:</b> {region}<br/>
            <b>Asignación:</b> {Asignacion}<br/>
            <b>Bloque:</b> {BLOQUE}<br/>
            <b>Operador:</b> {operador}<br/>
            <b>Estado:</b> {estado_actual}<br/>
            <b>Proceso:</b> {proceso_actual}
            """,
            "style": {"backgroundColor": "#333", "color": "white"}
        }
    )

    st.pydeck_chart(deck, use_container_width=True)

    # =====================================================
    # TABLA – ESTADO ACTUAL
    # =====================================================
    st.subheader("📋 Estado actual por bloque")

    if df_asig.empty:
        st.info("No hay asignaciones para los filtros seleccionados.")
    else:
        st.dataframe(
            df_asig[
                ["region", "asignacion", "bloque",
                 "operador", "estado_actual", "proceso_actual"]
            ],
            use_container_width=True,
            hide_index=True
        )
