import streamlit as st
from db import get_connection

def login_usuario(cedula, password):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT usuario as cedula, nombre, perfil, puesto
        FROM naturgy.usuarios
        WHERE usuario = %s
          AND contraseña = %s
          AND estado = 'Activo'
    """, (cedula.strip(), password.strip()))

    user = cur.fetchone()

    if user:
        st.session_state["usuario"] = {
            "cedula": user[0],
            "nombre": user[1],
            "perfil": user[2],
            "puesto": user[3]
        }
        st.rerun()
    
    else:
        st.error("Credenciales incorrectas")
