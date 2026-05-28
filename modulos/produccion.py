import streamlit as st
from datetime import date
from db import get_connection
from permisos import validar_acceso


def render():

    # =========================
    # Control de acceso
    # =========================
    validar_acceso("Reportes Producción")

    usuario = st.session_state.get("usuario")

    perfil = usuario["perfil"]
    puesto = usuario["puesto"]
    cedula_usuario = usuario["cedula"]

    if perfil not in (1, 3, 4, 5):
        st.error("No tiene permiso para acceder a Producción")
        st.stop()

    st.title("📊 Reporte de Producción")

    conn = get_connection()
    cur = conn.cursor()

    # =========================
    # Cargar procesos
    # =========================
    cur.execute("""
        SELECT id, nombre
        FROM naturgy.procesos
        WHERE id <> 0
        ORDER BY id
    """)
    procesos = cur.fetchall()
    procesos_dict = {nombre: pid for pid, nombre in procesos}

    # =========================
    # Obtener supervisor real
    # =========================
    cur.execute("""
        SELECT supervisor
        FROM naturgy.usuarios
        WHERE usuario = %s
    """, (cedula_usuario,))
    row_sup = cur.fetchone()
    supervisor_nombre = row_sup[0] if row_sup else None

    # =========================
    # PROCESO
    # =========================
    proceso_nombre = st.selectbox(
        "Proceso",
        procesos_dict.keys()
    )
    proceso_id = procesos_dict[proceso_nombre]

    # Determinar qué campos mostrar según el proceso
    es_control_calidad = (proceso_id == 1)
    es_recaptura_red = (proceso_id == 2)

    # =========================
    # FORMULARIO
    # =========================
    with st.form("form_reporte_produccion"):

        fecha_reporte = st.date_input(
            "Fecha",
            value=date.today()
        )

        horas = st.number_input(
            "Horas laboradas en formato decimal (X min = X/60, ejemplo: para reportar 40 min = 40/60 = 0.67 h, se reportan 0.67 h. Nota: la jornada diaria debe sumar 8.5 h)",
            min_value=0.0,
            max_value=12.5,
            step=0.5
        )

        st.markdown("---")

        # =========================
        # CAMPOS SEGÚN PROCESO
        # =========================
        if es_control_calidad:
            st.subheader("📏 Cantidad de Planos por Rango (CC)")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                rango_0_100 = st.number_input("(0 a 100 mts)", min_value=0, step=1, value=0)
                rango_1001_5000 = st.number_input("(1001 a 5000 mts)", min_value=0, step=1, value=0)
            
            with col2:
                rango_101_500 = st.number_input("(101 a 500 mts)", min_value=0, step=1, value=0)
                rango_5001_10000 = st.number_input("(5001 a 10000 mts)", min_value=0, step=1, value=0)
            
            with col3:
                rango_501_1000 = st.number_input("(501 a 1000 mts)", min_value=0, step=1, value=0)
                rango_mas_10000 = st.number_input("(> 10000 mts)", min_value=0, step=1, value=0)
            
            # Inicializar campos de Recaptura en 0
            ap_km = 0.0
            mp_0_100 = 0.0
            mp_101_500 = 0.0
            mp_501_1000 = 0.0
            mp_1001_5000 = 0.0
            mp_5001_10000 = 0.0
            mp_mas_10000 = 0.0

        elif es_recaptura_red:
            st.subheader("📏 Cantidad de Metros/KM por Rango (Recaptura de Red)")
            
            ap_km = st.number_input("AP (km)", min_value=0.0, step=0.01, format="%.2f")
            
            st.markdown("#### MP (Metros de Parque)")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                mp_0_100 = st.number_input("MP (0 a 100 mts)", min_value=0.0, step=0.01, format="%.2f")
                mp_1001_5000 = st.number_input("MP (1001 a 5000 mts)", min_value=0.0, step=0.01, format="%.2f")
            
            with col2:
                mp_101_500 = st.number_input("MP (101 a 500 mts)", min_value=0.0, step=0.01, format="%.2f")
                mp_5001_10000 = st.number_input("MP (5001 a 10000 mts)", min_value=0.0, step=0.01, format="%.2f")
            
            with col3:
                mp_501_1000 = st.number_input("MP (501 a 1000 mts)", min_value=0.0, step=0.01, format="%.2f")
                mp_mas_10000 = st.number_input("MP (> 10000 mts)", min_value=0.0, step=0.01, format="%.2f")
            
            # Inicializar campos de CC en 0
            rango_0_100 = 0
            rango_101_500 = 0
            rango_501_1000 = 0
            rango_1001_5000 = 0
            rango_5001_10000 = 0
            rango_mas_10000 = 0

        else:
            # Otros procesos: inicializar todo en 0
            st.info("ℹ️ Este proceso no requiere campos adicionales de medición")
            
            rango_0_100 = 0
            rango_101_500 = 0
            rango_501_1000 = 0
            rango_1001_5000 = 0
            rango_5001_10000 = 0
            rango_mas_10000 = 0
            ap_km = 0.0
            mp_0_100 = 0.0
            mp_101_500 = 0.0
            mp_501_1000 = 0.0
            mp_1001_5000 = 0.0
            mp_5001_10000 = 0.0
            mp_mas_10000 = 0.0

        st.markdown("---")

        # =========================
        # CENTRO DE COSTOS
        # =========================
        centro_costos = st.selectbox(
            "Centro de Costos",
            options=["NOA", "BAN"]
        )

        # =========================
        # OBSERVACIONES
        # =========================
        observaciones = st.text_area("Observaciones", max_chars=240)

        # =========================
        # ESTADO (por debajo)
        # =========================
        estado = "N/A"

        submit = st.form_submit_button("Guardar reporte")

    # =========================
    # GUARDAR REPORTE
    # =========================
    if submit:

        semana = fecha_reporte.isocalendar()[1]
        año = fecha_reporte.year

        try:
            cur.execute("""
                INSERT INTO naturgy.reportes (
                    tipo_reporte,
                    cedula_personal,
                    cedula_quien_reporta,
                    supervisor_nombre,
                    fecha_reporte,
                    semana,
                    "año",
                    horas,
                    proceso_id,
                    "(0 a 100 mts)",
                    "(101 a 500 mts)",
                    "(501 a 1000 mts)",
                    "(1001 a 5000 mts)",
                    "(5001 a 10000 mts)",
                    "(> 10000 mts)",
                    "AP (km)",
                    "MP (0 a 100 mts)",
                    "MP (101 a 500 mts)",
                    "MP (501 a 1000 mts)",
                    "MP (1001 a 5000 mts)",
                    "MP (5001 a 10000 mts)",
                    "MP (> 10000 mts)",
                    centro_costos,
                    observaciones,
                    estado,
                    perfil,
                    puesto
                )
                VALUES (
                    'produccion',
                    %s, %s, %s, %s, %s, %s,
                    %s, %s,
                    %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s
                )
            """, (
                cedula_usuario,
                cedula_usuario,
                supervisor_nombre,
                fecha_reporte,
                semana,
                año,
                horas,
                proceso_id,
                rango_0_100,
                rango_101_500,
                rango_501_1000,
                rango_1001_5000,
                rango_5001_10000,
                rango_mas_10000,
                ap_km,
                mp_0_100,
                mp_101_500,
                mp_501_1000,
                mp_1001_5000,
                mp_5001_10000,
                mp_mas_10000,
                centro_costos,
                observaciones,
                estado,
                perfil,
                puesto
            ))

            conn.commit()
            st.success("✅ Reporte guardado correctamente")

        except Exception as e:
            conn.rollback()
            st.error("❌ Error al guardar el reporte")
            st.exception(e)
        finally:
            cur.close()
            conn.close()
