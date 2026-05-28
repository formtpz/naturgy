import streamlit as st
import pandas as pd
from db import get_connection
from permisos import validar_acceso


def render():
    # =========================
    # Control de acceso
    # =========================
    validar_acceso("Historial")

    usuario = st.session_state.get("usuario")

    perfil = usuario["perfil"]
    puesto = usuario["puesto"].lower()
    cedula_usuario = usuario["cedula"]
    nombre_usuario = usuario["nombre"]

    if perfil not in (1, 3, 4, 5):
        st.error("No tiene permiso para acceder al historial")
        st.stop()

    st.title("📈 Historial de Reportes")

    conn = get_connection()
    
    # ✅ Limpiar transacciones pendientes
    conn.rollback()

    # =========================
    # Filtro de fechas
    # =========================
    col1, col2 = st.columns(2)
    with col1:
        fecha_inicio = st.date_input("Desde")
    with col2:
        fecha_fin = st.date_input("Hasta")

    # =========================
    # Selector de alcance según perfil
    # =========================
    where_extra = ""
    params_base = [fecha_inicio, fecha_fin]

    # -------- OPERARIO CATASTRAL --------
    if perfil in (3, 4) and puesto == "operario catastral":
        where_extra = " AND r.cedula_personal = %s"
        params_base.append(cedula_usuario)

    # -------- SUPERVISOR (perfil 3 sin ser operario) --------
    elif perfil == 3:
        opcion = st.radio(
            "Ver reportes de:",
            ["Propios", "Operadores a cargo"],
            horizontal=True
        )

        if opcion == "Propios":
            where_extra = " AND r.cedula_personal = %s"
            params_base.append(cedula_usuario)
        else:
            where_extra = " AND r.supervisor_nombre = %s"
            params_base.append(nombre_usuario)

    # -------- ADMIN / COORDINADOR --------
    elif perfil == 1:
        opcion = st.radio(
            "Ver reportes:",
            ["Totales", "Propios"],
            horizontal=True
        )

        if opcion == "Propios":
            where_extra = " AND r.cedula_personal = %s"
            params_base.append(cedula_usuario)
        else:
            where_extra = ""

    # =========================
    # REPORTES DE PRODUCCIÓN
    # =========================
    st.subheader("📊 Reportes de Producción")

    query_prod = f"""
    SELECT 
        r.id,
        r.fecha_reporte,
        u.nombre AS persona,
        r.supervisor_nombre AS supervisor,
        pr.nombre AS proceso,
        r.horas,
        r."(0 a 100 mts)",
        r."(101 a 500 mts)",
        r."(501 a 1000 mts)",
        r."(1001 a 5000 mts)",
        r."(5001 a 10000 mts)",
        r."(> 10000 mts)",
        r."AP (km)",
        r."MP (0 a 100 mts)",
        r."MP (101 a 500 mts)",
        r."MP (501 a 1000 mts)",
        r."MP (1001 a 5000 mts)",
        r."MP (5001 a 10000 mts)",
        r."MP (> 10000 mts)",
        r.centro_costos,
        r.observaciones,
        r.estado
    FROM naturgy.reportes r
    JOIN naturgy.usuarios u ON u.usuario = r.cedula_personal
    LEFT JOIN naturgy.procesos pr ON pr.id = r.proceso_id
    WHERE r.tipo_reporte = 'produccion'
      AND r.fecha_reporte BETWEEN %s AND %s
      {where_extra}
    ORDER BY r.fecha_reporte DESC, persona
    """

    df_prod = pd.read_sql(query_prod, conn, params=params_base)
    
    if df_prod.empty:
        st.info("No hay reportes de producción en el período seleccionado")
    else:
        st.dataframe(df_prod, use_container_width=True, hide_index=True)

    st.markdown("---")

    # =========================
    # REPORTES DE EVENTOS
    # =========================
    st.subheader("🗂️ Reportes de Eventos")

    query_eventos = f"""
    SELECT 
        r.id,
        r.fecha_reporte,
        u.nombre AS persona,
        r.supervisor_nombre AS supervisor,
        r.horas,
        te.nombre AS tipo_evento,
        r.centro_costos,
        r.observaciones,
        r.estado
    FROM naturgy.reportes r
    JOIN naturgy.usuarios u ON u.usuario = r.cedula_personal
    LEFT JOIN naturgy.tipos_evento te ON te.id = r.tipo_evento_id
    WHERE r.tipo_reporte = 'evento'
      AND r.fecha_reporte BETWEEN %s AND %s
      {where_extra}
    ORDER BY r.fecha_reporte DESC, persona
    """

    df_eventos = pd.read_sql(query_eventos, conn, params=params_base)
    
    if df_eventos.empty:
        st.info("No hay reportes de eventos en el período seleccionado")
    else:
        st.dataframe(df_eventos, use_container_width=True, hide_index=True)

    st.markdown("---")

    # =========================
    # RESUMEN DIARIO DE HORAS (POR PERSONA)
    # =========================
    st.subheader("⏱️ Resumen Diario de Horas por Persona")

    query_horas = f"""
    SELECT 
        r.fecha_reporte,
        u.nombre AS persona,
        SUM(r.horas) AS total_horas
    FROM naturgy.reportes r
    JOIN naturgy.usuarios u ON u.usuario = r.cedula_personal
    WHERE r.fecha_reporte BETWEEN %s AND %s
      {where_extra}
    GROUP BY r.fecha_reporte, u.nombre
    ORDER BY r.fecha_reporte DESC, persona
    """

    df_horas = pd.read_sql(query_horas, conn, params=params_base)

    if df_horas.empty:
        st.info("No hay datos para el resumen de horas")
    else:
        df_horas["estado"] = df_horas["total_horas"].apply(
            lambda x: "✅ OK" if 8.4 <= float(x) <= 8.6 else "⚠️ Revisar"
        )

        # Métricas rápidas
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total personas", df_horas["persona"].nunique())
        with col2:
            st.metric("Total días", df_horas["fecha_reporte"].nunique())
        with col3:
            dias_revisar = df_horas[df_horas["estado"] == "⚠️ Revisar"]["fecha_reporte"].nunique()
            st.metric("Días a revisar", dias_revisar)

        st.dataframe(df_horas, use_container_width=True, hide_index=True)
