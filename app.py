import streamlit as st
import pandas as pd
import google.generativeai as genai
from PIL import Image
import json
import time
import io
import os
from datetime import datetime, timedelta
import xml.etree.ElementTree as ET
import sqlite3
import hashlib
import requests

# LIBRERÍAS PARA GOOGLE LOGIN
from google_auth_oauthlib.flow import Flow

# ==============================================================================
# 1. GESTIÓN DE BASE DE DATOS Y SEGURIDAD
# ==============================================================================

def make_hashes(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

def check_hashes(password, hashed_text):
    if make_hashes(password) == hashed_text:
        return hashed_text
    return False

# Inicializar Base de Datos (SQLite Local)
conn = sqlite3.connect('contabilidad_users.db', check_same_thread=False)
c = conn.cursor()

def create_tables():
    c.execute('CREATE TABLE IF NOT EXISTS userstable(username TEXT UNIQUE, password TEXT, role TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS access_logs(username TEXT, login_time TIMESTAMP, action TEXT)')
    # Crear usuario Admin por defecto: Usuario "admin", Clave "admin123"
    try:
        c.execute('INSERT INTO userstable(username, password, role) VALUES (?,?,?)', 
                  ("admin", make_hashes("admin123"), "admin"))
        conn.commit()
    except:
        pass

def add_userdata(username, password):
    try:
        c.execute('INSERT INTO userstable(username,password,role) VALUES (?,?,?)', (username, password, "user"))
        conn.commit()
        return True
    except:
        return False

def login_user(username, password):
    c.execute('SELECT * FROM userstable WHERE username =? AND password = ?', (username, password))
    return c.fetchall()

def add_log(username, action):
    now = datetime.now()
    c.execute('INSERT INTO access_logs(username, login_time, action) VALUES (?,?,?)', (username, now, action))
    conn.commit()

def view_logs():
    c.execute('SELECT * FROM access_logs ORDER BY login_time DESC')
    return c.fetchall()

create_tables()

# ==============================================================================
# 2. CONFIGURACIÓN VISUAL (MODO OSCURO PREMIUM)
# ==============================================================================
st.set_page_config(page_title="Asistente Contable Pro 2025", page_icon="📊", layout="wide")

# Lógica para saludo dinámico
hora_actual = datetime.now().hour
if 5 <= hora_actual < 12:
    saludo, icono_saludo = "Buenos días", "☀️"
elif 12 <= hora_actual < 18:
    saludo, icono_saludo = "Buenas tardes", "🌤️"
else:
    saludo, icono_saludo = "Buenas noches", "🌙"

st.markdown("""
    <style>
    .stApp { background-color: #0e1117 !important; color: #e0e0e0 !important; }
    html, body, [class*="css"] { font-family: 'Inter', 'Segoe UI', Arial, sans-serif; }
    h1 { background: -webkit-linear-gradient(45deg, #0d6efd, #00d2ff); -webkit-background-clip: text; -webkit-text-fill-color: transparent; font-weight: 800 !important; }
    h2, h3 { color: #f0f2f6 !important; font-weight: 700; }
    .instruccion-box, .rut-card, .reporte-box, .tutorial-step {
        background: rgba(38, 39, 48, 0.7) !important; backdrop-filter: blur(10px);
        border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 12px;
        padding: 20px; margin-bottom: 25px; transition: all 0.3s ease;
    }
    .instruccion-box:hover { transform: translateY(-5px); border-color: #0d6efd; }
    .stButton>button {
        background: linear-gradient(90deg, #0d6efd, #0056b3) !important; color: white !important;
        border-radius: 8px; font-weight: 600; border: none; height: 3.5em; width: 100%;
    }
    </style>
    """, unsafe_allow_html=True)

# ==============================================================================
# 3. LÓGICA DE HERRAMIENTAS (INTACTA)
# ==============================================================================
SMMLV_2025, AUX_TRANS_2025, UVT_2025 = 1430000, 175000, 49799
TOPE_EFECTIVO = 100 * UVT_2025

def calcular_dv_colombia(nit):
    try:
        nit = str(nit).strip()
        primos = [3, 7, 13, 17, 19, 23, 29, 37, 41, 43, 47, 53, 59, 67, 71]
        suma = sum(int(d) * p for d, p in zip(reversed(nit), primos))
        resto = suma % 11
        return str(resto) if resto <= 1 else str(11 - resto)
    except: return "?"

def analizar_gasto_fila(row, cv, cm, cc):
    val = float(row[cv]) if pd.notnull(row[cv]) else 0
    met = str(row[cm]).lower()
    h = []
    if 'efectivo' in met and val > TOPE_EFECTIVO: h.append("⛔ RECHAZO 771-5")
    return " | ".join(h) if h else "OK", "ALTO" if h else "BAJO"

def parsear_xml_dian(f):
    try:
        tree = ET.parse(f); root = tree.getroot()
        ns = {'cac': 'urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2', 'cbc': 'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2'}
        return {'Archivo': f.name, 'Emisor': root.find('.//cac:AccountingSupplierParty//cbc:RegistrationName', ns).text, 'Total': float(root.find('.//cbc:PayableAmount', ns).text)}
    except: return {'Archivo': f.name, 'Error': 'XML Inválido'}

# ==============================================================================
# 4. APLICACIÓN PRINCIPAL
# ==============================================================================

def mostrar_aplicacion_principal():
    with st.sidebar:
        st.image("https://cdn-icons-png.flaticon.com/512/9320/9320399.png", width=80)
        st.markdown(f"### 👤 {st.session_state['username']}")
        
        if st.session_state['role'] == 'admin':
            st.markdown("---")
            if st.button("📊 Ver Estadísticas (Admin)"): st.session_state['menu_actual'] = "Admin_Stats"

        menu = st.radio("Herramientas:", [
            "🏠 Inicio", "⚖️ Cruce DIAN", "📧 Lector XML", "🤝 Conciliador Bancario",
            "📂 Auditoría Gastos", "👥 Nómina UGPP", "🔍 Validador RUT", "📸 OCR"
        ])
        
        if st.button("🚪 Cerrar Sesión"):
            st.session_state['logged_in'] = False
            st.rerun()

    if st.session_state.get('menu_actual') == "Admin_Stats":
        st.title("📊 Panel Admin")
        df_logs = pd.DataFrame(view_logs(), columns=['Usuario', 'Fecha', 'Acción'])
        st.metric("Accesos Totales", len(df_logs))
        st.dataframe(df_logs, use_container_width=True)
        if st.button("Volver"): 
            st.session_state['menu_actual'] = "App"
            st.rerun()
        return

    if menu == "🏠 Inicio":
        st.markdown(f"# {icono_saludo} {saludo}, Colega.")
        st.markdown("<div class='instruccion-box'><h4>🚀 Bienvenido</h4><p>Usa el menú lateral para navegar por las herramientas contables.</p></div>", unsafe_allow_html=True)
        
    elif menu == "🔍 Validador RUT":
        st.header("🔍 Validador de RUT")
        nit = st.text_input("Ingrese NIT (Sin DV):")
        if st.button("Calcular"):
            dv = calcular_dv_colombia(nit)
            st.markdown(f"<div class='rut-card'><h3>NIT: {nit}-{dv}</h3></div>", unsafe_allow_html=True)

    elif menu == "📧 Lector XML":
        st.header("📧 Lector XML")
        files = st.file_uploader("Subir XMLs", accept_multiple_files=True, type=['xml'])
        if files and st.button("Procesar"):
            results = [parsear_xml_dian(f) for f in files]
            st.dataframe(pd.DataFrame(results), use_container_width=True)

    # ... (Resto de tus herramientas aquí)

# ==============================================================================
# 5. SISTEMA DE LOGIN REAL (GOOGLE & LOCAL)
# ==============================================================================

# CONFIGURACIÓN GOOGLE AUTH
REDIRECT_URI = "TU_URL_DE_STREAMLIT" # CAMBIAR ESTO POR TU URL REAL (EJM: https://tuapp.streamlit.app)

def main():
    if 'logged_in' not in st.session_state:
        st.session_state['logged_in'] = False
        st.session_state['username'] = ''
        st.session_state['role'] = ''

    if not st.session_state['logged_in']:
        col_a, col_b, col_c = st.columns([1, 2, 1])
        with col_b:
            st.image("https://cdn-icons-png.flaticon.com/512/9320/9320399.png", width=100)
            st.markdown("<h1 style='text-align: center;'>Asistente Contable Pro</h1>", unsafe_allow_html=True)
            
            tab1, tab2 = st.tabs(["🔐 Ingresar", "📝 Registrarse"])
            
            with tab1:
                # --- GOOGLE LOGIN ---
                try:
                    flow = Flow.from_client_secrets_file(
                        "client_secret.json",
                        scopes=['openid', 'https://www.googleapis.com/auth/userinfo.email', 'https://www.googleapis.com/auth/userinfo.profile'],
                        redirect_uri=REDIRECT_URI
                    )
                    
                    if 'code' not in st.query_params:
                        auth_url, _ = flow.authorization_url(prompt='consent')
                        st.link_button("🇬 Iniciar Sesión con Google", auth_url, use_container_width=True)
                    else:
                        code = st.query_params['code']
                        flow.fetch_token(code=code)
                        user_info = requests.get(f'https://www.googleapis.com/oauth2/v1/userinfo?access_token={flow.credentials.token}').json()
                        email = user_info.get('email')
                        if email:
                            add_userdata(email, make_hashes("google_user_pwd"))
                            st.session_state['logged_in'], st.session_state['username'], st.session_state['role'] = True, email, 'user'
                            add_log(email, "Login Google")
                            st.query_params.clear()
                            st.rerun()
                except Exception as e:
                    st.warning("Google Auth no disponible. Configura client_secret.json")

                st.markdown("---")
                u = st.text_input("Usuario")
                p = st.text_input("Contraseña", type="password")
                if st.button("Entrar"):
                    res = login_user(u, make_hashes(p))
                    if res:
                        st.session_state['logged_in'], st.session_state['username'], st.session_state['role'] = True, u, res[0][2]
                        add_log(u, "Login Local")
                        st.rerun()
                    else: st.error("Usuario/Clave incorrectos")

            with tab2:
                nu = st.text_input("Nuevo Usuario")
                np = st.text_input("Nueva Clave", type="password")
                if st.button("Crear Cuenta"):
                    if add_userdata(nu, make_hashes(np)):
                        st.success("Cuenta creada. Ya puedes ingresar.")
                        add_log(nu, "Registro Nuevo")
    else:
        mostrar_aplicacion_principal()

if __name__ == '__main__':
    main()
