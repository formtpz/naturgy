import streamlit as st
import pandas as pd
from db import get_connection
from permisos import validar_acceso
from datetime import date

def render():
    # =========================
    # Control de acceso
    # =========================
    validar_acceso("RRHH")

    usuario = st.session_state.get("usuario")
    if usuario["perfil"] != 1:
        st.error("⛔ Acceso restringido al módulo de RRHH")
        st.stop()

    st.title("👥 RRHH – Gestión de Personal")

    # =========================
    # Mensajes post-acción
    # =========================
    if st.session_state.get("rrhh_success"):
        st.success(st.session_state["rrhh_success"])
        del st.session_state["rrhh_success"]

    if st.session_state.get("rrhh_error"):
        st.error(st.session_state["rrhh_error"])
        del st.session_state["rrhh_error"]

    conn = get_connection()
    cur = conn.cursor()

    # =========================
    # Supervisores disponibles
    # =========================
    df_supervisores = pd.read_sql("""
        SELECT nombre_completo
        FROM personal
        WHERE estado = 'activo'
          AND puesto <> 'Operario Catastral'
        ORDER BY nombre_completo
    """, conn)

    lista_supervisores = [""] + df_supervisores["nombre_completo"].tolist()

    modo = st.radio(
        "Seleccione una acción",
        ["Personal Existente", "Crear Nuevo Personal"],
        horizontal=True
    )

    # =====================================================
    # MODO: PERSONAL EXISTENTE
    # =====================================================
    if modo == "Personal Existente":

        df_personal = pd.read_sql("""
            SELECT
                p.id,
                p.cedula,
                p.nombre_completo,
                p.contraseña,
                p.puesto,
                p.perfil,
                p.horario,
                p.estado,
                p.supervisor,
                p.fecha_vinculacion,
                p.fecha_desvinculacion,

                d.nombre_completo_signos,
                d.correo_interno,
                d.correo_externo,
                d.telefono,
                d.nota_gis
            FROM personal p
            LEFT JOIN personal_datos d
                ON d.personal_id = p.id
            ORDER BY p.nombre_completo
        """, conn)

        empleado = st.selectbox(
            "Empleado",
            df_personal["nombre_completo"]
        )

        row = df_personal[df_personal["nombre_completo"] == empleado].iloc[0]

        idx_sup = (
            lista_supervisores.index(row["supervisor"])
            if row["supervisor"] in lista_supervisores
            else 0
        )

        with st.form("editar_personal"):
            st.subheader("📌 Datos personales")

            cedula = st.text_input("Cédula", row["cedula"])
            nombre = st.text_input("Nombre completo", row["nombre_completo"])
            password = st.text_input("Contraseña", row["contraseña"])
            puesto = st.text_input("Puesto", row["puesto"])

            perfil = st.number_input(
                "Perfil (1=Admin, 2=RRHH, 3=Operario, 4=Operario Calidad, 5=Supervisor)",
                min_value=1,
                max_value=5,
                value=int(row["perfil"])
            )

            horario = st.text_input("Horario", row["horario"])
            estado = st.selectbox(
                "Estado",
                ["activo", "inactivo"],
                index=0 if row["estado"] == "activo" else 1
            )

            supervisor = st.selectbox(
                "Supervisor",
                lista_supervisores,
                index=idx_sup
            )

            fecha_desv = st.date_input(
                "Fecha de desvinculación",
                value=row["fecha_desvinculacion"]
                if pd.notnull(row["fecha_desvinculacion"])
                else None
            )

            st.divider()
            st.subheader("🧾 Datos complementarios")

            nombre_signos = st.text_input(
                "Nombre completo (con signos)",
                value=row["nombre_completo_signos"] or ""
            )

            correo_int = st.text_input(
                "Correo interno",
                value=row["correo_interno"] or ""
            )

            correo_ext = st.text_input(
                "Correo externo",
                value=row["correo_externo"] or ""
            )

            telefono = st.text_input(
                "Teléfono",
                value=row["telefono"] or ""
            )

            nota_gis = st.number_input(
                "Nota GIS",
                min_value=0,
                max_value=100,
                value=int(row["nota_gis"]) if row["nota_gis"] is not None else 0
            )

            guardar = st.form_submit_button("💾 Guardar cambios")

        if guardar:
            try:
                cur.execute("""
                    UPDATE personal SET
                        cedula = %s,
                        nombre_completo = %s,
                        contraseña = %s,
                        puesto = %s,
                        perfil = %s,
                        horario = %s,
                        estado = %s,
                        supervisor = %s,
                        fecha_desvinculacion = %s
                    WHERE id = %s
                """, (
                    cedula,
                    nombre,
                    password,
                    puesto,
                    int(perfil),
                    horario,
                    estado,
                    supervisor if supervisor else None,
                    fecha_desv,
                    int(row["id"])
                ))

                cur.execute("""
                    INSERT INTO personal_datos (
                        personal_id,
                        nombre_completo_signos,
                        correo_interno,
                        correo_externo,
                        telefono,
                        nota_gis
                    )
                    VALUES (%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (personal_id)
                    DO UPDATE SET
                        nombre_completo_signos = EXCLUDED.nombre_completo_signos,
                        correo_interno = EXCLUDED.correo_interno,
                        correo_externo = EXCLUDED.correo_externo,
                        telefono = EXCLUDED.telefono,
                        nota_gis = EXCLUDED.nota_gis,
                        fecha_actualizacion = CURRENT_TIMESTAMP
                """, (
                    int(row["id"]),
                    nombre_signos,
                    correo_int,
                    correo_ext,
                    telefono,
                    nota_gis
                ))

                conn.commit()
                st.session_state["rrhh_success"] = "✅ Personal actualizado correctamente"
                st.rerun()

            except Exception as e:
                conn.rollback()
                st.session_state["rrhh_error"] = f"❌ Error al guardar cambios: {e}"
                st.rerun()

    # =====================================================
    # MODO: CREAR NUEVO PERSONAL
    # =====================================================
    else:
        st.subheader("➕ Crear nuevo personal")

        with st.form("nuevo_personal"):
            cedula = st.text_input("Cédula")
            nombre = st.text_input("Nombre completo")
            password = st.text_input("Contraseña", type="password")
            puesto = st.text_input("Puesto")

            perfil = st.number_input(
                "Perfil (1=Admin, 2=RRHH, 3=Operativo)",
                min_value=1,
                max_value=3
            )

            horario = st.text_input("Horario")
            estado = st.selectbox("Estado", ["activo", "inactivo"])
            supervisor = st.selectbox("Supervisor", lista_supervisores)
            fecha_vinc = st.date_input("Fecha de vinculación", value=date.today())

            st.divider()
            st.subheader("🧾 Datos complementarios")

            nombre_signos = st.text_input("Nombre completo (con signos)")
            correo_int = st.text_input("Correo interno")
            correo_ext = st.text_input("Correo externo")
            telefono = st.text_input("Teléfono")
            nota_gis = st.number_input("Nota GIS", min_value=0, max_value=100)

            crear = st.form_submit_button("Crear personal")

        if crear:
            try:
                cur.execute("""
                    INSERT INTO personal (
                        cedula, nombre_completo, contraseña,
                        puesto, perfil, horario,
                        estado, supervisor, fecha_vinculacion
                    )
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    RETURNING id
                """, (
                    cedula,
                    nombre,
                    password,
                    puesto,
                    int(perfil),
                    horario,
                    estado,
                    supervisor if supervisor else None,
                    fecha_vinc
                ))

                personal_id = cur.fetchone()[0]

                cur.execute("""
                    INSERT INTO personal_datos (
                        personal_id,
                        nombre_completo_signos,
                        correo_interno,
                        correo_externo,
                        telefono,
                        nota_gis
                    )
                    VALUES (%s,%s,%s,%s,%s,%s)
                """, (
                    personal_id,
                    nombre_signos,
                    correo_int,
                    correo_ext,
                    telefono,
                    nota_gis
                ))

                conn.commit()
                st.session_state["rrhh_success"] = "✅ Personal creado correctamente"
                st.rerun()

            except Exception as e:
                conn.rollback()
                st.session_state["rrhh_error"] = f"❌ Error al crear personal: {e}"
                st.rerun()
    # =====================================================
    # LISTADO GENERAL DE PERSONAL (SOLO LECTURA)
    # =====================================================
    st.divider()
    st.subheader("📋 Listado general de personal")

    df_listado = pd.read_sql("""
        SELECT
            nombre_completo,
            cedula,
            puesto
        FROM personal
        ORDER BY nombre_completo
    """, conn)

    if df_listado.empty:
        st.info("No hay personal registrado")
    else:
        st.dataframe(
            df_listado,
            use_container_width=True,
            hide_index=True
        )
