import streamlit as st
import pandas as pd
import gspread
import google.generativeai as genai
from PIL import Image
import json
import time
import io
from datetime import datetime, timedelta
import xml.etree.ElementTree as ET

# ==============================================================================
# 1. CONFIGURACIÓN VISUAL (OBLIGATORIO AL PRINCIPIO)
# ==============================================================================
st.set_page_config(page_title="Asistente Contable Pro 2025", page_icon="📊", layout="wide")

# ==============================================================================
# 2. SISTEMA DE LOGIN GOOGLE (CORREGIDO Y SIMPLIFICADO)
# ==============================================================================
try:
    from google_auth_oauthlib.flow import Flow
    from google.oauth2 import id_token
    import google.auth.transport.requests
    import requests
except ImportError:
    st.error("⚠️ Falta instalar librerías. Asegúrate de que 'requirements.txt' tenga: google-auth-oauthlib, google-auth, requests")
    st.stop()

# URL EXACTA DE TU APP (Sin barra al final para evitar errores)
REDIRECT_URI = "https://aicontador.streamlit.app"

def sistema_login():
    # A. Si ya está logueado, permitir acceso inmediato
    if st.session_state.get('logged_in') == True:
        return True

    # B. Configurar la conexión con Google usando los Secrets
    try:
        # Verificamos que existan los secretos básicos
        if "client_id" not in st.secrets or "client_secret" not in st.secrets:
            st.warning("⚠️ Esperando configuración de credenciales en Streamlit Secrets...")
            st.stop()

        client_config = {
            "web": {
                "client_id": st.secrets["client_id"],
                "project_id": st.secrets.get("project_id", "asistentecontable"),
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                "client_secret": st.secrets["client_secret"],
                "redirect_uris": [REDIRECT_URI]
            }
        }
        
        # Permisos solicitados
        scopes = [
            "openid",
            "https://www.googleapis.com/auth/userinfo.email",
            "https://www.googleapis.com/auth/userinfo.profile"
        ]

        flow = Flow.from_client_config(
            client_config,
            scopes=scopes,
            redirect_uri=REDIRECT_URI
        )

    except Exception as e:
        st.error(f"❌ Error técnico en configuración: {e}")
        st.stop()

    # C. Procesar el retorno de Google (Cuando trae el código en la URL)
    if 'code' in st.query_params:
        try:
            code = st.query_params['code']
            flow.fetch_token(code=code)
            credentials = flow.credentials
            
            # Validar token
            request = google.auth.transport.requests.Request()
            id_info = id_token.verify_oauth2_token(
                credentials.id_token, request, st.secrets["client_id"]
            )
            
            # ¡ÉXITO! Guardar sesión
            st.session_state['logged_in'] = True
            st.session_state['username'] = id_info.get('name')
            st.session_state['email'] = id_info.get('email')
            
            # Limpiar URL y recargar página limpia
            st.query_params.clear()
            st.rerun()
            return True
            
        except Exception as e:
            st.error(f"❌ Error al validar ingreso. Intenta de nuevo. Detalles: {e}")
            time.sleep(3)
            st.query_params.clear()
            st.rerun()

    # D. Mostrar el Botón de Login (Si no ha entrado)
    else:
        auth_url, _ = flow.authorization_url(prompt='consent')
        
        # Interfaz de Login (Mantenemos tu estilo profesional)
        st.markdown(f"""
            <div style="display: flex; justify-content: center; align-items: center; height: 80vh; flex-direction: column; background-color: #0e1117;">
                <h1 style="color: #0d6efd; font-size: 3.5rem; font-weight: 800; margin-bottom: 10px;">Asistente Contable Pro</h1>
                <p style="color: #a0a0a0; font-size: 1.2rem; margin-bottom: 40px;">Tu Centro de Comando Financiero Inteligente</p>
                <a href="{auth_url}" target="_self" style="
                    background: linear-gradient(90deg, #4285F4 0%, #357ae8 100%);
                    color: white; padding: 15px 40px; 
                    text-decoration: none; border-radius: 50px; font-weight: bold; 
                    font-family: sans-serif; font-size: 18px; 
                    box-shadow: 0 4px 15px rgba(66, 133, 244, 0.4);">
                    🇬 Iniciar Sesión con Google
                </a>
            </div>
        """, unsafe_allow_html=True)
        return False

# --- ACTIVAR EL PORTERO ---
if not sistema_login():
    st.stop() # Si no se loguea, la app se detiene aquí y no muestra nada más.

# ==============================================================================
# 3. APLICACIÓN PRINCIPAL (INTACTA)
# ==============================================================================

# Conexión a Google Sheets (Manejo de errores silencioso si no hay credenciales de DB)
try:
    if "gcp_service_account" in st.secrets:
        credentials_dict = st.secrets["gcp_service_account"]
        gc = gspread.service_account_from_dict(credentials_dict)
    else:
        gc = None
except:
    gc = None

# --- ESTILOS Y CONSTANTES ---
hora_actual = datetime.now().hour
if 5 <= hora_actual < 12:
    saludo = "Buenos días"
    icono_saludo = "☀️"
elif 12 <= hora_actual < 18:
    saludo = "Buenas tardes"
    icono_saludo = "🌤️"
else:
    saludo = "Buenas noches"
    icono_saludo = "🌙"

st.markdown("""
    <style>
    .stApp { background-color: #0e1117 !important; color: #e0e0e0 !important; }
    h1 { background: -webkit-linear-gradient(45deg, #0d6efd, #00d2ff); -webkit-background-clip: text; -webkit-text-fill-color: transparent; font-weight: 800 !important; }
    .instruccion-box, .rut-card, .reporte-box, .tutorial-step { background: rgba(38, 39, 48, 0.7) !important; backdrop-filter: blur(10px); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 12px; padding: 20px; margin-bottom: 25px; border-left: 4px solid #0d6efd; transition: transform 0.3s ease; }
    .instruccion-box:hover { transform: translateY(-5px); border-color: #0d6efd; } 
    .stButton>button { background: linear-gradient(90deg, #0d6efd 0%, #0056b3 100%) !important; color: white !important; border-radius: 8px; font-weight: 600; border: none; height: 3.5em; width: 100%; transition: all 0.3s ease; box-shadow: 0 4px 6px rgba(0,0,0,0.3); }
    .metric-box-red { background: rgba(62, 18, 22, 0.8) !important; color: #ffaeb6 !important; padding: 15px; border-radius: 10px; text-align: center; border: 1px solid #842029; }
    .metric-box-green { background: rgba(15, 41, 30, 0.8) !important; color: #a3cfbb !important; padding: 15px; border-radius: 10px; text-align: center; border: 1px solid #0f5132; }
    </style>
""", unsafe_allow_html=True)

# Constantes 2025
SMMLV_2025 = 1430000
AUX_TRANS_2025 = 175000
UVT_2025 = 49799
TOPE_EFECTIVO = 100 * UVT_2025
BASE_RET_SERVICIOS = 4 * UVT_2025
BASE_RET_COMPRAS = 27 * UVT_2025

# --- FUNCIONES DE LÓGICA ---
def calcular_dv_colombia(nit_sin_dv):
    try:
        nit_str = str(nit_sin_dv).strip()
        if not nit_str.isdigit(): return "Error"
        primos = [3, 7, 13, 17, 19, 23, 29, 37, 41, 43, 47, 53, 59, 67, 71]
        suma = sum(int(digito) * primos[i] for i, digito in enumerate(reversed(nit_str)) if i < len(primos))
        resto = suma % 11
        return str(resto) if resto <= 1 else str(11 - resto)
    except: return "?"

def analizar_gasto_fila(row, col_valor, col_metodo, col_concepto):
    hallazgos = []
    riesgo = "BAJO"
    valor = float(row[col_valor]) if pd.notnull(row[col_valor]) else 0
    metodo = str(row[col_metodo]) if pd.notnull(row[col_metodo]) else ""
    if 'efectivo' in metodo.lower() and valor > TOPE_EFECTIVO:
        hallazgos.append(f"⛔ RECHAZO FISCAL: Pago en efectivo (${valor:,.0f}) supera tope.")
        riesgo = "ALTO"
    if valor >= BASE_RET_SERVICIOS and valor < BASE_RET_COMPRAS:
        hallazgos.append("⚠️ ALERTA: Verificar Retención (Base Servicios).")
        if riesgo == "BAJO": riesgo = "MEDIO"
    elif valor >= BASE_RET_COMPRAS:
        hallazgos.append("⚠️ ALERTA: Verificar Retención (Base Compras).")
        if riesgo == "BAJO": riesgo = "MEDIO"
    return " | ".join(hallazgos) if hallazgos else "OK", riesgo

def calcular_ugpp_fila(row, col_salario, col_no_salarial):
    salario = float(row[col_salario]) if pd.notnull(row[col_salario]) else 0
    no_salarial = float(row[col_no_salarial]) if pd.notnull(row[col_no_salarial]) else 0
    total = salario + no_salarial
    limite = total * 0.40
    if no_salarial > limite:
        exceso = no_salarial - limite
        return salario + exceso, exceso, "RIESGO ALTO", f"Excede límite por ${exceso:,.0f}"
    return salario, 0, "OK", "Cumple norma"

def calcular_costo_empresa_fila(row, col_salario, col_aux, col_arl, col_exo):
    salario = float(row[col_salario])
    tiene_aux = str(row[col_aux]).strip().lower() in ['si', 's', 'true', '1', 'yes']
    nivel_arl = int(row[col_arl]) if pd.notnull(row[col_arl]) else 1
    es_exonerado = str(row[col_exo]).strip().lower() in ['si', 's', 'true', '1', 'yes']
    aux_trans = AUX_TRANS_2025 if tiene_aux else 0
    ibc = salario
    base_prest = salario + aux_trans
    salud = 0 if es_exonerado else ibc * 0.085
    pension = ibc * 0.12
    arl_t = {1:0.00522, 2:0.01044, 3:0.02436, 4:0.0435, 5:0.0696}
    arl_val = ibc * arl_t.get(nivel_arl, 0.00522)
    paraf = ibc * 0.04 
    if not es_exonerado: paraf += ibc * 0.05
    prest = base_prest * 0.2183 
    total = base_prest + salud + pension + arl_val + paraf + prest
    return total, (total - base_prest)

def consultar_ia_gemini(prompt):
    try:
        model = genai.GenerativeModel('models/gemini-1.5-flash')
        response = model.generate_content(prompt)
        return response.text
    except Exception as e: return f"Error de conexión IA: {str(e)}"

def ocr_factura(imagen):
    try:
        model = genai.GenerativeModel('models/gemini-1.5-flash')
        prompt = """Extrae datos JSON estricto: {"fecha": "YYYY-MM-DD", "nit": "num", "proveedor": "txt", "concepto": "txt", "base": num, "iva": num, "total": num}"""
        response = model.generate_content([prompt, imagen])
        return json.loads(response.text.replace("```json", "").replace("```", "").strip())
    except: return None

def parsear_xml_dian(archivo_xml):
    try:
        tree = ET.parse(archivo_xml)
        root = tree.getroot()
        ns = {'cac': 'urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2', 'cbc': 'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2'}
        def get_text(path, root_elem=root):
            elem = root_elem.find(path, ns)
            return elem.text if elem is not None else ""
        data = {'Archivo': archivo_xml.name, 'Prefijo': get_text('.//cbc:ID'), 'Fecha Emision': get_text('.//cbc:IssueDate')}
        emisor = root.find('.//cac:AccountingSupplierParty', ns)
        if emisor:
            data['NIT Emisor'] = get_text('.//cbc:CompanyID', emisor.find('.//cac:PartyTaxScheme', ns))
            data['Emisor'] = get_text('.//cbc:RegistrationName', emisor.find('.//cac:PartyTaxScheme', ns))
        receptor = root.find('.//cac:AccountingCustomerParty', ns)
        if receptor:
            data['NIT Receptor'] = get_text('.//cbc:CompanyID', receptor.find('.//cac:PartyTaxScheme', ns))
            data['Receptor'] = get_text('.//cbc:RegistrationName', receptor.find('.//cac:PartyTaxScheme', ns))
        monetary = root.find('.//cac:LegalMonetaryTotal', ns)
        if monetary:
            data['Total a Pagar'] = float(get_text('cbc:PayableAmount', monetary) or 0)
            data['Base Imponible'] = float(get_text('cbc:LineExtensionAmount', monetary) or 0)
            data['Total Impuestos'] = float(get_text('cbc:TaxInclusiveAmount', monetary) or 0) - data['Base Imponible']
        return data
    except: return {"Archivo": archivo_xml.name, "Error": "Error XML"}

# --- MENÚ LATERAL Y NAVEGACIÓN ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/9320/9320399.png", width=80)
    
    if 'username' in st.session_state:
        st.write(f"👤 **{st.session_state['username']}**")
        if st.button("Cerrar Sesión"):
            st.session_state.clear()
            st.rerun()
            
    st.markdown("### 🏢 Panel de Control")
    st.markdown("---")
    
    opciones_menu = [
        "🏠 Inicio / Quiénes Somos",
        "⚖️ Cruce DIAN vs Contabilidad",
        "📧 Lector XML (Facturación)",
        "🤝 Conciliador Bancario (IA)",
        "📂 Auditoría Masiva de Gastos",
        "👥 Escáner de Nómina (UGPP)",
        "💰 Tesorería & Flujo de Caja",
        "💰 Calculadora Costos (Masiva)",
        "📊 Analítica Financiera",
        "📈 Reportes Gerenciales & Notas NIIF (IA)", # MÓDULO NUEVO INCLUIDO
        "🔍 Validador de RUT (Real)",
        "📸 Digitalización (OCR)"
    ]
    
    menu = st.radio("Herramientas Profesionales:", opciones_menu)
    
    st.markdown("---")
    with st.expander("🔐 Configuración & Seguridad"):
        st.info("Pega aquí tu llave para activar el modo 'Cerebro IA':")
        api_key = st.text_input("API Key Google:", type="password")
        if api_key: genai.configure(api_key=api_key)
    
    st.markdown("<br><center><small>v6.0 | Build 2025</small></center>", unsafe_allow_html=True)

# --- DESARROLLO DE PÁGINAS ---

# 0. INICIO
if menu == "🏠 Inicio / Quiénes Somos":
    st.markdown(f"# {icono_saludo} {saludo}, {st.session_state.get('username', 'Colega')}.")
    st.markdown("### Bienvenido a tu Centro de Comando Contable Inteligente.")
    col_intro1, col_intro2 = st.columns([1.5, 1])
    with col_intro1:
        st.markdown("""
        <div class='instruccion-box' style='border-left: 4px solid #00d2ff;'>
            <h4>🚀 La Nueva Era Contable</h4>
            <p>Olvídate de la "carpintería". Esta suite ha sido diseñada para automatizar lo operativo y dejarte tiempo para lo estratégico.</p>
        </div>
        """, unsafe_allow_html=True)
        st.markdown("### 🛠️ Herramientas de Alto Impacto:")
        c_tool1, c_tool2 = st.columns(2)
        with c_tool1:
            st.info("⚖️ **Cruce DIAN:** Compara Exógena vs Contabilidad.")
            st.info("📧 **XML Miner:** Minería de datos de facturación.")
        with c_tool2:
            st.info("🤝 **Bank Match:** Conciliación Bancaria IA.")
            st.info("📈 **Notas NIIF:** Redacción automática.")
    with col_intro2:
        st.markdown("""
        <div class='reporte-box'>
            <h4>💡 Workflow Recomendado</h4>
            <ol>
                <li>Descarga auxiliares de tu ERP.</li>
                <li>Descarga el reporte de la DIAN.</li>
                <li>Usa el "Cruce DIAN" para auditar.</li>
                <li>Genera tus Notas NIIF con IA.</li>
            </ol>
        </div>
        """, unsafe_allow_html=True)

# 1. CRUCE DIAN
elif menu == "⚖️ Cruce DIAN vs Contabilidad":
    st.header("⚖️ Auditor de Exógena (Cruce DIAN)")
    col_dian, col_conta = st.columns(2)
    with col_dian:
        file_dian = st.file_uploader("Subir 'Reporte Terceros DIAN' (.xlsx)", type=['xlsx'])
    with col_conta:
        file_conta = st.file_uploader("Subir Auxiliar por Tercero (.xlsx)", type=['xlsx'])
    if file_dian and file_conta:
        df_dian = pd.read_excel(file_dian)
        df_conta = pd.read_excel(file_conta)
        st.write("---")
        st.subheader("⚙️ Mapeo de Columnas")
        c1, c2, c3, c4 = st.columns(4)
        nit_dian = c1.selectbox("NIT (DIAN):", df_dian.columns)
        val_dian = c2.selectbox("Valor (DIAN):", df_dian.columns)
        nit_conta = c3.selectbox("NIT (Contabilidad):", df_conta.columns)
        val_conta = c4.selectbox("Saldo (Contabilidad):", df_conta.columns)
        if st.button("🔎 EJECUTAR CRUCE"):
            dian_grouped = df_dian.groupby(nit_dian)[val_dian].sum().reset_index()
            dian_grouped.columns = ['NIT', 'Valor_DIAN']
            conta_grouped = df_conta.groupby(nit_conta)[val_conta].sum().reset_index()
            conta_grouped.columns = ['NIT', 'Valor_Conta']
            cruce = pd.merge(dian_grouped, conta_grouped, on='NIT', how='outer').fillna(0)
            cruce['Diferencia'] = cruce['Valor_DIAN'] - cruce['Valor_Conta']
            diferencias = cruce[abs(cruce['Diferencia']) > 1000]
            if not diferencias.empty:
                st.error(f"⚠️ Se encontraron {len(diferencias)} diferencias.")
                st.dataframe(diferencias)
                out = io.BytesIO()
                with pd.ExcelWriter(out, engine='xlsxwriter') as w:
                    diferencias.to_excel(w, index=False)
                st.download_button("📥 Descargar Reporte", out.getvalue(), "Diferencias.xlsx")
            else:
                st.success("✅ Todo cuadra perfectamente.")

# 2. LECTOR XML
elif menu == "📧 Lector XML (Facturación)":
    st.header("📧 Minería de Datos XML")
    archivos_xml = st.file_uploader("Arrastra XMLs", type=['xml'], accept_multiple_files=True)
    if archivos_xml and st.button("🚀 INICIAR EXTRACCIÓN"):
        datos_xml = []
        barra = st.progress(0)
        for i, f in enumerate(archivos_xml):
            barra.progress((i+1)/len(archivos_xml))
            datos_xml.append(parsear_xml_dian(f))
        st.dataframe(pd.DataFrame(datos_xml))

# 3. CONCILIADOR BANCARIO
elif menu == "🤝 Conciliador Bancario (IA)":
    st.header("🤝 Conciliación Bancaria")
    c1, c2 = st.columns(2)
    fb = c1.file_uploader("Extracto Banco", type=['xlsx'])
    fl = c2.file_uploader("Libros Auxiliares", type=['xlsx'])
    if fb and fl:
        db = pd.read_excel(fb); dl = pd.read_excel(fl)
        c1, c2, c3, c4 = st.columns(4)
        cfb = c1.selectbox("Fecha Banco", db.columns); cvb = c2.selectbox("Valor Banco", db.columns)
        cfl = c3.selectbox("Fecha Libro", dl.columns); cvl = c4.selectbox("Valor Libro", dl.columns)
        col_desc_b = st.selectbox("Descripción Banco:", db.columns)
        if st.button("🔄 CONCILIAR"):
            db['Fecha_Dt'] = pd.to_datetime(db[cfb]); dl['Fecha_Dt'] = pd.to_datetime(dl[cfl])
            db['Conciliado'] = False; dl['Conciliado'] = False
            matches = []
            bar = st.progress(0)
            for idx_b, row_b in db.iterrows():
                bar.progress((idx_b+1)/len(db))
                vb = row_b[cvb]; fb = row_b['Fecha_Dt']
                cands = dl[(dl[cvl] == vb) & (~dl['Conciliado']) & (dl['Fecha_Dt'].between(fb-timedelta(days=3), fb+timedelta(days=3)))]
                if not cands.empty:
                    db.at[idx_b, 'Conciliado']=True; dl.at[cands.index[0], 'Conciliado']=True
                    matches.append({"Fecha": row_b[cfb], "Desc": row_b[col_desc_b], "Valor": vb, "Estado": "✅ OK"})
            st.success(f"Conciliados: {len(matches)} partidas.")
            st.dataframe(pd.DataFrame(matches))

# 4. AUDITORIA GASTOS
elif menu == "📂 Auditoría Masiva de Gastos":
    st.header("📂 Auditoría Fiscal")
    ar = st.file_uploader("Auxiliar Gastos", type=['xlsx'])
    if ar:
        df = pd.read_excel(ar)
        c1, c2, c3, c4 = st.columns(4)
        cf = c1.selectbox("Fecha", df.columns); cv = c2.selectbox("Valor", df.columns)
        cm = c3.selectbox("Método Pago", df.columns); cc = c4.selectbox("Concepto", df.columns)
        if st.button("AUDITAR"):
            res = []
            for r in df.to_dict('records'):
                h, rs = analizar_gasto_fila(r, cv, cm, cc)
                res.append({"Fila": r[cf], "Hallazgo": h, "Riesgo": rs})
            st.dataframe(pd.DataFrame(res))

# 5. ESCANER UGPP
elif menu == "👥 Escáner de Nómina (UGPP)":
    st.header("👥 Escáner UGPP")
    an = st.file_uploader("Nómina", type=['xlsx'])
    if an:
        dn = pd.read_excel(an)
        c1, c2, c3 = st.columns(3)
        cn = c1.selectbox("Empleado", dn.columns); cs = c2.selectbox("Salario", dn.columns); cns = c3.selectbox("No Salarial", dn.columns)
        if st.button("ESCANEAR"):
            res = []
            for r in dn.to_dict('records'):
                ibc, exc, est, msg = calcular_ugpp_fila(r, cs, cns)
                res.append({"Empleado": r[cn], "Exceso": exc, "Estado": est})
            st.dataframe(pd.DataFrame(res))

# 6. TESORERIA
elif menu == "💰 Tesorería & Flujo de Caja":
    st.header("💰 Tesorería")
    saldo_hoy = st.number_input("Saldo Hoy:", min_value=0.0)
    c1, c2 = st.columns(2)
    fcxc = c1.file_uploader("Cartera", type=['xlsx']); fcxp = c2.file_uploader("Proveedores", type=['xlsx'])
    if fcxc and fcxp:
        dcxc = pd.read_excel(fcxc); dcxp = pd.read_excel(fcxp)
        c1, c2, c3, c4 = st.columns(4)
        cfc = c1.selectbox("F. Venc CxC", dcxc.columns); cvc = c2.selectbox("Vlr CxC", dcxc.columns)
        cfp = c3.selectbox("F. Venc CxP", dcxp.columns); cvp = c4.selectbox("Vlr CxP", dcxp.columns)
        if st.button("PROYECTAR"):
            try:
                dcxc['F'] = pd.to_datetime(dcxc[cfc]); dcxp['F'] = pd.to_datetime(dcxp[cfp])
                fi = dcxc.groupby('F')[cvc].sum().reset_index(); fe = dcxp.groupby('F')[cvp].sum().reset_index()
                cal = pd.merge(fi, fe, on='F', how='outer').fillna(0)
                cal.columns = ['Fecha', 'Ing', 'Egr']; cal = cal.sort_values('Fecha')
                cal['Saldo'] = saldo_hoy + (cal['Ing'] - cal['Egr']).cumsum()
                st.area_chart(cal.set_index('Fecha')['Saldo'])
                st.dataframe(cal)
            except: st.error("Error en fechas")

# 7. CALCULADORA COSTOS
elif menu == "💰 Calculadora Costos (Masiva)":
    st.header("💰 Costeo Nómina")
    ac = st.file_uploader("Lista Personal", type=['xlsx'])
    if ac:
        dc = pd.read_excel(ac)
        c1, c2, c3 = st.columns(3)
        cn = c1.selectbox("Nombre", dc.columns); cs = c2.selectbox("Salario", dc.columns); ca = c3.selectbox("Aux Trans (Si/No)", dc.columns)
        if st.button("CALCULAR"):
            rc = []
            for r in dc.to_dict('records'):
                c, cr = calcular_costo_empresa_fila(r, cs, ca, None, "No")
                rc.append({"Empleado": r[cn], "Costo Total": c})
            st.dataframe(pd.DataFrame(rc))

# 8. ANALITICA
elif menu == "📊 Analítica Financiera":
    st.header("📊 Analítica IA")
    fi = st.file_uploader("Datos", type=['xlsx'])
    if fi and api_key:
        df = pd.read_excel(fi)
        cd = st.selectbox("Descripción", df.columns); cv = st.selectbox("Valor", df.columns)
        if st.button("ANALIZAR"):
            res = df.groupby(cd)[cv].sum().sort_values(ascending=False).head(10)
            st.bar_chart(res)
            st.markdown(consultar_ia_gemini(f"Analiza: {res.to_string()}"))

# 9. NARRADOR FINANCIERO (NUEVO)
elif menu == "📈 Reportes Gerenciales & Notas NIIF (IA)":
    st.header("📈 Narrador Financiero & NIIF")
    st.markdown("""<div class='instruccion-box' style='border-left: 4px solid #ad00ff;'><h4>💡 Financial Storytelling</h4><p>Sube los balances comparativos y la IA redactará el informe.</p></div>""", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    f1 = c1.file_uploader("Año Actual 2025", type=['xlsx'])
    f2 = c2.file_uploader("Año Anterior 2024", type=['xlsx'])
    if f1 and f2:
        df_act = pd.read_excel(f1); df_ant = pd.read_excel(f2)
        st.subheader("Configuración")
        c1, c2, c3 = st.columns(3)
        col_cuenta = c1.selectbox("Columna Cuenta:", df_act.columns)
        col_v1 = c2.selectbox("Valor 2025:", df_act.columns)
        col_v2 = c3.selectbox("Valor 2024:", df_ant.columns)
        if st.button("✨ GENERAR INFORME") and api_key:
            d1 = df_act.groupby(col_cuenta)[col_v1].sum().reset_index()
            d2 = df_ant.groupby(col_cuenta)[col_v2].sum().reset_index()
            merged = pd.merge(d1, d2, on=col_cuenta).fillna(0)
            merged['Var'] = merged[col_v1] - merged[col_v2]
            top = merged.reindex(merged.Var.abs().sort_values(ascending=False).index).head(10)
            st.markdown("### 📊 Tablero Gerencial")
            st.bar_chart(top.set_index(col_cuenta)['Var'])
            with st.spinner("🤖 Redactando informe..."):
                prompt = f"Actúa como Contador experto. Analiza estas variaciones y redacta Informe Gerencial y Notas NIIF: {top.to_string()}"
                st.markdown(consultar_ia_gemini(prompt))

# 10. VALIDADOR RUT
elif menu == "🔍 Validador de RUT (Real)":
    st.header("🔍 Validador RUT")
    nit = st.text_input("NIT:")
    if st.button("CALCULAR"): st.success(f"DV: {calcular_dv_colombia(nit)}")

# 11. OCR
elif menu == "📸 Digitalización (OCR)":
    st.header("📸 OCR Facturas")
    af = st.file_uploader("Imagen", type=["jpg", "png"])
    if af and st.button("PROCESAR") and api_key:
        st.write(ocr_factura(Image.open(af)))

st.markdown("---")
st.markdown("<center><strong>Asistente Contable Pro</strong> | Desarrollado para Contadores 4.0 | Bucaramanga, Colombia</center>", unsafe_allow_html=True)
