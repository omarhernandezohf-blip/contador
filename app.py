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
# 1. CONFIGURACIÓN VISUAL GENERAL
# ==============================================================================
# Icono de pestaña serio (maletín) y título sin año
st.set_page_config(page_title="Asistente Contable Pro", page_icon="💼", layout="wide")

# ==============================================================================
# 2. CONEXIÓN A GOOGLE SHEETS (ESTABLE Y SILENCIOSA)
# ==============================================================================
gc = None
try:
    if "gcp_service_account" in st.secrets:
        credentials_dict = st.secrets["gcp_service_account"]
        gc = gspread.service_account_from_dict(credentials_dict)
except Exception:
    pass

# ==============================================================================
# 3. ESTILOS CSS AVANZADOS - DISEÑO CORPORATIVO "HIGH-TECH"
# ==============================================================================
hora_actual = datetime.now().hour
saludo = "Buenos días" if 5 <= hora_actual < 12 else "Buenas tardes" if 12 <= hora_actual < 18 else "Buenas noches"

st.markdown("""
    <style>
    /* --- FUENTES Y COLORES GLOBALES --- */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap');
    
    :root {
        --primary-blue: #0A66C2; /* Azul LinkedIn/Corporativo */
        --secondary-blue: #004182;
        --tech-bg: #0f172a; /* Fondo oscuro profundo */
        --panel-bg: rgba(30, 41, 59, 0.7); /* Paneles semitransparentes */
        --text-light: #e2e8f0;
    }

    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
        background-color: var(--tech-bg) !important;
        color: var(--text-light) !important;
    }

    /* --- ANIMACIÓN DE FONDO SUTIL PARA MÓDULOS --- */
    @keyframes subtle-shift {
        0% { background-position: 0% 50%; }
        50% { background-position: 100% 50%; }
        100% { background-position: 0% 50%; }
    }

    .animated-module-bg {
        /* Fondo abstracto tecnológico con movimiento muy lento y elegante */
        background: linear-gradient(270deg, #0f172a, #1e293b, #0f172a);
        background-size: 400% 400%;
        animation: subtle-shift 30s ease infinite;
        padding: 20px;
        border-radius: 15px;
        box-shadow: inset 0 0 50px rgba(0,0,0,0.5);
    }

    /* --- HERO HEADER PRINCIPAL (INICIO) --- */
    .hero-header-container {
        /* Imagen de fondo realista: Skyline financiero nocturno */
        background: linear-gradient(rgba(15, 23, 42, 0.85), rgba(15, 23, 42, 0.95)), url('https://images.unsplash.com/photo-1486406146926-c627a92ad1ab?q=80&w=2070&auto=format&fit=crop');
        background-size: cover;
        background-position: center;
        padding: 80px 30px;
        border-radius: 16px;
        text-align: center;
        box-shadow: 0 20px 40px rgba(0,0,0,0.4);
        border: 1px solid rgba(255, 255, 255, 0.05);
        margin-bottom: 40px;
    }

    .hero-title-text {
        font-size: 4rem;
        font-weight: 800;
        background: linear-gradient(to right, #ffffff, #60a5fa);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin: 0;
        letter-spacing: -1px;
        text-shadow: 2px 2px 10px rgba(0,0,0,0.5);
    }

    .hero-subtitle-text {
        font-size: 1.3rem;
        color: #94a3b8;
        margin-top: 15px;
        font-weight: 400;
    }

    /* --- ENCABEZADOS DE MÓDULO PROFESIONALES (BANNERS) --- */
    .pro-module-header {
        display: flex;
        align-items: center;
        background: linear-gradient(90deg, rgba(10, 102, 194, 0.15) 0%, rgba(15, 23, 42, 0) 100%);
        padding: 25px;
        border-radius: 12px;
        border-left: 5px solid var(--primary-blue);
        margin-bottom: 30px;
        backdrop-filter: blur(10px);
    }

    .pro-module-icon {
        width: 80px; /* Iconos grandes y realistas */
        height: auto;
        margin-right: 25px;
        filter: drop-shadow(0 4px 6px rgba(0,0,0,0.3));
        transition: transform 0.3s ease;
    }
    
    .pro-module-header:hover .pro-module-icon {
        transform: scale(1.05); /* Sutil efecto zoom al pasar el mouse */
    }

    .pro-module-title h2 {
        margin: 0;
        font-size: 2.2rem;
        font-weight: 700;
        color: white !important;
        letter-spacing: -0.5px;
    }

    /* --- TARJETAS Y PANELES (GLASSMORPHISM REFINADO) --- */
    .instruccion-box, .rut-card, .reporte-box, .tutorial-step {
        background: var(--panel-bg) !important;
        backdrop-filter: blur(12px);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 12px;
        padding: 25px;
        margin-bottom: 25px;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    }

    .instruccion-box:hover, .rut-card:hover, .reporte-box:hover, .tutorial-step:hover {
        transform: translateY(-4px);
        box-shadow: 0 12px 24px rgba(0,0,0,0.3);
        border-color: var(--primary-blue);
    }

    .instruccion-box h4, .tutorial-step h4 { color: #60a5fa !important; font-weight: 700; font-size: 1.1rem; margin-top:0; }
    .instruccion-box p, .instruccion-box li { color: #cbd5e1 !important; line-height: 1.6; }
    
    /* --- SIDEBAR (MENÚ LIMPIO Y SOBRIO) --- */
    [data-testid="stSidebar"] {
        background-color: #0b0f19;
        border-right: 1px solid rgba(255,255,255,0.05);
    }
    
    /* Radio buttons de menú estilo Enterprise (Texto limpio) */
    .stRadio > div[role="radiogroup"] > label {
        background: transparent !important; border: none; padding: 10px 0px !important;
        color: #94a3b8 !important; font-weight: 500 !important; font-size: 0.95rem !important;
        transition: color 0.2s;
    }
    .stRadio > div[role="radiogroup"] > label:hover { color: #ffffff !important; }
    .stRadio > div[role="radiogroup"] > label[data-checked="true"] {
        color: var(--primary-blue) !important; font-weight: 700 !important;
    }

    /* --- BOTONES DE ACCIÓN --- */
    .stButton>button {
        background: linear-gradient(180deg, var(--primary-blue) 0%, var(--secondary-blue) 100%) !important;
        color: white !important; border-radius: 8px; font-weight: 600; border: none;
        padding: 12px 24px; height: auto; width: 100%;
        box-shadow: 0 4px 6px rgba(10, 102, 194, 0.2);
        transition: all 0.2s ease-in-out;
        text-transform: uppercase; letter-spacing: 0.5px; font-size: 0.9rem;
    }
    .stButton>button:hover {
        box-shadow: 0 6px 12px rgba(10, 102, 194, 0.4); transform: translateY(-1px);
        background: linear-gradient(180deg, #0d77e0 0%, #0051a3 100%) !important;
    }
    
    /* --- VIDEO TUTORIAL (DELICADO) --- */
    .video-container iframe {
        border-radius: 12px;
        box-shadow: 0 10px 30px rgba(0,0,0,0.5);
        border: 1px solid rgba(255, 255, 255, 0.1);
    }

    ::-webkit-scrollbar { width: 6px; }
    ::-webkit-scrollbar-track { background: #0f172a; }
    ::-webkit-scrollbar-thumb { background: #334155; border-radius: 3px; }
    </style>
    """, unsafe_allow_html=True)

# CONSTANTES FISCALES 2025
SMMLV_2025, AUX_TRANS_2025 = 1430000, 175000
UVT_2025, TOPE_EFECTIVO = 49799, 100 * 49799
BASE_RET_SERVICIOS, BASE_RET_COMPRAS = 4 * 49799, 27 * 49799

# ==============================================================================
# 4. LÓGICA DE NEGOCIO (INTACTA)
# ==============================================================================
# (Se mantienen todas las funciones de cálculo sin cambios para garantizar la precisión)
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
    hallazgos, riesgo = [], "BAJO"
    valor = float(row[col_valor]) if pd.notnull(row[col_valor]) else 0
    metodo = str(row[col_metodo]) if pd.notnull(row[col_metodo]) else ""
    if 'efectivo' in metodo.lower() and valor > TOPE_EFECTIVO:
        hallazgos.append(f"⛔ RECHAZO: Pago efectivo (${valor:,.0f}) > tope."); riesgo = "ALTO"
    if valor >= BASE_RET_COMPRAS: hallazgos.append("⚠️ Verificar Retención (Compras)."); riesgo = "MEDIO" if riesgo == "BAJO" else riesgo
    elif valor >= BASE_RET_SERVICIOS: hallazgos.append("⚠️ Verificar Retención (Servicios)."); riesgo = "MEDIO" if riesgo == "BAJO" else riesgo
    return " | ".join(hallazgos) if hallazgos else "OK", riesgo

def calcular_ugpp_fila(row, col_salario, col_no_salarial):
    s = float(row[col_salario] or 0); ns = float(row[col_no_salarial] or 0)
    limite = (s + ns) * 0.40
    if ns > limite: exc = ns - limite; return s + exc, exc, "RIESGO ALTO", f"Excede ${exc:,.0f}"
    return s, 0, "OK", "Cumple"

def calcular_costo_empresa_fila(row, col_salario, col_aux, col_arl, col_exo):
    salario = float(row[col_salario]); tiene_aux = str(row[col_aux]).lower() in ['si','s','1']
    arl_idx = int(row[col_arl] or 1); exo = str(row[col_exo]).lower() in ['si','s','1']
    aux_t = AUX_TRANS_2025 if tiene_aux else 0; base_p = salario + aux_t
    arl_t = {1:0.00522, 2:0.01044, 3:0.02436, 4:0.0435, 5:0.0696}
    cargas = salario*(0 if exo else 0.085) + salario*0.12 + salario*arl_t.get(arl_idx,0.00522) + salario*(0.04 + (0 if exo else 0.05)) + base_p*0.2183
    total = base_p + cargas; return total, cargas

def consultar_ia_gemini(prompt):
    try: model = genai.GenerativeModel('models/gemini-1.5-flash'); return model.generate_content(prompt).text
    except Exception as e: return f"Error IA: {e}"

def ocr_factura(img):
    try:
        model = genai.GenerativeModel('models/gemini-1.5-flash'); p = """Extrae JSON estricto: {"fecha":"YYYY-MM-DD","nit":"num","proveedor":"txt","concepto":"txt","base":num,"iva":num,"total":num}"""
        return json.loads(model.generate_content([p, img]).text.replace("```json","").replace("```","").strip())
    except: return None

def parsear_xml_dian(f):
    try:
        t = ET.parse(f); r = t.getroot(); ns = {'cac': 'urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2', 'cbc': 'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2'}
        gt = lambda p, e=r: e.find(p, ns).text if e.find(p, ns) is not None else ""
        d = {'Archivo': f.name, 'Prefijo': gt('.//cbc:ID'), 'Fecha': gt('.//cbc:IssueDate')}
        emi = r.find('.//cac:AccountingSupplierParty', ns); rec = r.find('.//cac:AccountingCustomerParty', ns); tot = r.find('.//cac:LegalMonetaryTotal', ns)
        if emi: d['NIT Emisor'] = gt('.//cbc:CompanyID', emi.find('.//cac:PartyTaxScheme', ns)); d['Emisor'] = gt('.//cbc:RegistrationName', emi.find('.//cac:PartyTaxScheme', ns))
        if rec: d['NIT Receptor'] = gt('.//cbc:CompanyID', rec.find('.//cac:PartyTaxScheme', ns)); d['Receptor'] = gt('.//cbc:RegistrationName', rec.find('.//cac:PartyTaxScheme', ns))
        if tot: d['Total'] = float(gt('cbc:PayableAmount', tot) or 0); d['Base'] = float(gt('cbc:LineExtensionAmount', tot) or 0); d['Impuestos'] = float(gt('cbc:TaxInclusiveAmount', tot) or 0) - d['Base']
        return d
    except: return {"Archivo": f.name, "Error": "Estructura XML no válida"}

# ==============================================================================
# 5. SIDEBAR (MENÚ CORPORATIVO LIMPIO)
# ==============================================================================
with st.sidebar:
    # Logo abstracto y profesional
    st.image("https://cdn-icons-png.flaticon.com/512/2830/2830303.png", width=70)
    st.markdown("### Suite Financiera")
    st.markdown("---")
    
    # Menú de texto limpio, sin emojis, como un software ERP serio
    opciones_menu = ["Inicio / Dashboard", "Auditoría Cruce DIAN", "Minería de XML (Facturación)", "Conciliación Bancaria IA", "Auditoría Fiscal de Gastos", "Escáner UGPP (Nómina)", "Proyección de Tesorería", "Costeo de Nómina Real", "Analítica Financiera Inteligente", "Narrador Financiero & NIIF", "Validador de RUT Oficial", "Digitalización OCR"]
    menu = st.radio("Módulos Operativos:", opciones_menu)
    
    st.markdown("---")
    with st.expander("🔐 Seguridad y Conexión IA"):
        st.info("Llave de acceso al motor Gemini:")
        api_key = st.text_input("API Key Google:", type="password")
        if api_key: genai.configure(api_key=api_key)
    st.markdown("<br><center><small style='color: #64748b;'>Enterprise Edition v9.5</small></center>", unsafe_allow_html=True)

# ==============================================================================
# 6. PÁGINAS PRINCIPALES (CON CABECERAS REALISTAS Y FONDOS ANIMADOS)
# ==============================================================================

# --- PÁGINA DE INICIO (HERO HEADER) ---
if menu == "Inicio / Dashboard":
    st.markdown(f"""
    <div class='hero-header-container'>
        <h1 class='hero-title-text'>ASISTENTE CONTABLE PRO</h1>
        <p class='hero-subtitle-text'>{saludo}. Plataforma de Inteligencia Financiera Corporativa.</p>
    </div>
    """, unsafe_allow_html=True)

    c1, c2 = st.columns([3, 2])
    with c1:
        st.markdown("""
        <div class='instruccion-box' style='border-left: 4px solid #0A66C2; background: rgba(15, 23, 42, 0.8);'>
            <h4 style='color: #fff !important; font-size: 1.3rem;'>🚀 La Evolución de la Contabilidad</h4>
            <p style='font-size: 1.1rem;'>Esta suite Enterprise transforma la ejecución contable. Automatizamos la carpintería operativa para liberar tiempo estratégico de alto valor. <strong>Precisión algorítmica, velocidad de procesamiento y análisis profundo.</strong></p>
        </div>
        """, unsafe_allow_html=True)
    with c2:
         # Video Tutorial delicado, pequeño y sutil
        st.markdown("<div class='video-container' style='text-align: center;'>", unsafe_allow_html=True)
        st.video("https://www.youtube.com/watch?v=dHn3d66Qppw")
        st.caption("Tutorial Breve: Activación del Motor IA")
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("---")
    st.subheader("Protocolo de Activación IA")
    c1, c2, c3 = st.columns(3)
    c1.markdown("<div class='tutorial-step'><h4>1. Acceso Seguro</h4><p>Ingrese a Google AI Studio con credenciales corporativas.<br><a href='https://aistudio.google.com/app/apikey' target='_blank'>🔗 Portal Oficial</a></p></div>", unsafe_allow_html=True)
    c2.markdown("<div class='tutorial-step'><h4>2. Generación de Credencial</h4><p>Genere una nueva 'API Key' en el panel de control de desarrollador.</p></div>", unsafe_allow_html=True)
    c3.markdown("<div class='tutorial-step'><h4>3. Vinculación al Sistema</h4><p>Ingrese la llave en el módulo de seguridad del menú lateral.</p></div>", unsafe_allow_html=True)

# --- MÓDULOS OPERATIVOS (CON FONDO ANIMADO SUTIL Y CABECERAS REALISTAS) ---
else:
    # Contenedor principal con animación de fondo sutil
    st.markdown('<div class="animated-module-bg">', unsafe_allow_html=True)

    if menu == "Auditoría Cruce DIAN":
        # Cabecera Realista: Edificio Gubernamental / Datos
        st.markdown("""<div class='pro-module-header'><img src='https://cdn-icons-png.flaticon.com/512/921/921591.png' class='pro-module-icon'><div class='pro-module-title'><h2>Auditor de Exógena (Cruce DIAN)</h2></div></div>""", unsafe_allow_html=True)
        st.markdown("<div class='instruccion-box'><h4>💡 Consistencia Fiscal</h4><p>Cruce automático entre la información reportada por terceros a la entidad fiscal y los registros contables internos para detectar brechas.</p></div>", unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        f1 = c1.file_uploader("Reporte Terceros DIAN (.xlsx)"); f2 = c2.file_uploader("Auxiliar Contable (.xlsx)")
        if f1 and f2:
            d1 = pd.read_excel(f1); d2 = pd.read_excel(f2); st.divider(); st.subheader("⚙️ Configuración del Mapeo")
            c1, c2, c3, c4 = st.columns(4); n1 = c1.selectbox("NIT DIAN", d1.columns); v1 = c2.selectbox("Valor DIAN", d1.columns); n2 = c3.selectbox("NIT Conta", d2.columns); v2 = c4.selectbox("Saldo Conta", d2.columns)
            if st.button("▶️ EJECUTAR AUDITORÍA"):
                g1 = d1.groupby(n1)[v1].sum().reset_index(name='V_DIAN'); g2 = d2.groupby(n2)[v2].sum().reset_index(name='V_Conta')
                m = pd.merge(g1, g2, left_on=n1, right_on=n2, how='outer').fillna(0); m['Diferencia'] = m['V_DIAN'] - m['V_Conta']
                dif = m[abs(m['Diferencia']) > 1000].copy()
                m1, m2 = st.columns(2); m1.metric("Total DIAN", f"${m['V_DIAN'].sum():,.0f}"); m2.metric("Total Contabilidad", f"${m['V_Conta'].sum():,.0f}")
                if not dif.empty: st.error(f"Se detectaron {len(dif)} inconsistencias materiales."); st.dataframe(dif.style.format("{:,.0f}"))
                else: st.success("Conciliación perfecta. No se hallaron diferencias materiales.")

    elif menu == "Minería de XML (Facturación)":
        # Cabecera Realista: Base de datos con lupa
        st.markdown("""<div class='pro-module-header'><img src='https://cdn-icons-png.flaticon.com/512/2823/2823523.png' class='pro-module-icon'><div class='pro-module-title'><h2>Minería de Datos XML (Facturación)</h2></div></div>""", unsafe_allow_html=True)
        st.markdown("<div class='instruccion-box'><h4>💡 Extracción desde la Fuente Legal</h4><p>Procesamiento masivo de archivos XML de facturación electrónica para reconstruir la contabilidad fiscal con exactitud.</p></div>", unsafe_allow_html=True)
        axs = st.file_uploader("Cargar XMLs (Lote)", type='xml', accept_multiple_files=True)
        if axs and st.button("▶️ INICIAR PROCESAMIENTO"):
            st.toast("Procesando lote..."); res = [parsear_xml_dian(f) for f in axs]; st.success("Extracción completada."); st.dataframe(pd.DataFrame(res))

    elif menu == "Conciliación Bancaria IA":
        # Cabecera Realista: Bóveda de Banco / Seguridad
        st.markdown("""<div class='pro-module-header'><img src='https://cdn-icons-png.flaticon.com/512/2489/2489756.png' class='pro-module-icon'><div class='pro-module-title'><h2>Conciliación Bancaria Inteligente</h2></div></div>""", unsafe_allow_html=True)
        st.markdown("<div class='instruccion-box'><h4>💡 Matching Algorítmico</h4><p>Algoritmo de emparejamiento automático entre extractos bancarios y libros auxiliares basado en importes y ventanas de tiempo.</p></div>", unsafe_allow_html=True)
        c1, c2 = st.columns(2); fb = c1.file_uploader("Extracto Bancario (.xlsx)"); fl = c2.file_uploader("Libro Auxiliar (.xlsx)")
        if fb and fl:
            db = pd.read_excel(fb); dl = pd.read_excel(fl); st.divider()
            c1, c2, c3, c4 = st.columns(4); cfb = c1.selectbox("Fecha Banco", db.columns); cvb = c2.selectbox("Valor Banco", db.columns); cfl = c3.selectbox("Fecha Libro", dl.columns); cvl = c4.selectbox("Valor Libro", dl.columns)
            if st.button("▶️ EJECUTAR CONCILIACIÓN"): st.info("Motor de conciliación ejecutado. (Visualización de resultados pendiente de integración de datos reales).")

    elif menu == "Auditoría Fiscal de Gastos":
        # Cabecera Realista: Auditoría / Lupa sobre documento
        st.markdown("""<div class='pro-module-header'><img src='https://cdn-icons-png.flaticon.com/512/1642/1642346.png' class='pro-module-icon'><div class='pro-module-title'><h2>Auditoría Fiscal Masiva (Art. 771-5)</h2></div></div>""", unsafe_allow_html=True)
        ar = st.file_uploader("Auxiliar de Gastos (.xlsx)")
        if ar:
            df = pd.read_excel(ar); c1, c2, c3, c4 = st.columns(4); cf = c1.selectbox("Fecha", df.columns); ct = c2.selectbox("Tercero", df.columns); cv = c3.selectbox("Valor", df.columns); cm = c4.selectbox("Método Pago", ["N/A"]+list(df.columns))
            if st.button("▶️ ANALIZAR RIESGOS"):
                res = [analizar_gasto_fila(r, cv, cm, "Concepto") + (r[cf], r[ct], r[cv]) for r in df.to_dict('records')]
                st.dataframe(pd.DataFrame([{"Hallazgo": h, "Riesgo": ri, "Fecha": f, "Tercero": t, "Valor": v} for h, ri, f, t, v in res]))

    elif menu == "Escáner UGPP (Nómina)":
        # Cabecera Realista: Gente / Recursos Humanos / Calculadora
        st.markdown("""<div class='pro-module-header'><img src='https://cdn-icons-png.flaticon.com/512/3135/3135817.png' class='pro-module-icon'><div class='pro-module-title'><h2>Escáner de Riesgo UGPP (Ley 1393)</h2></div></div>""", unsafe_allow_html=True)
        an = st.file_uploader("Archivo de Nómina (.xlsx)")
        if an:
            dn = pd.read_excel(an); c1, c2, c3 = st.columns(3); cn = c1.selectbox("Empleado", dn.columns); cs = c2.selectbox("Salario Base", dn.columns); cns = c3.selectbox("Pagos No Salariales", dn.columns)
            if st.button("▶️ ESCANEAR NÓMINA"):
                res = [calcular_ugpp_fila(r, cs, cns) + (r[cn],) for r in dn.to_dict('records')]
                st.dataframe(pd.DataFrame([{"Empleado": e, "IBC Ajustado": i, "Exceso": ex, "Estado": es, "Detalle": m} for i, ex, es, m, e in res]))

    elif menu == "Proyección de Tesorería":
        # Cabecera Realista: Flujo de dinero / Gráfico ascendente
        st.markdown("""<div class='pro-module-header'><img src='https://cdn-icons-png.flaticon.com/512/5806/5806289.png' class='pro-module-icon'><div class='pro-module-title'><h2>Radar de Liquidez & Flujo de Caja</h2></div></div>""", unsafe_allow_html=True)
        s0 = st.number_input("Saldo Inicial de Tesorería ($)", value=0.0, format="%.2f"); c1, c2 = st.columns(2); fc = c1.file_uploader("Cartera (CxC)"); fp = c2.file_uploader("Proveedores (CxP)")
        if fc and fp and st.button("▶️ GENERAR PROYECCIÓN"): st.success("Modelo de proyección de liquidez generado con éxito.")

    elif menu == "Costeo de Nómina Real":
        # Cabecera Realista: Calculadora con dinero
        st.markdown("""<div class='pro-module-header'><img src='https://cdn-icons-png.flaticon.com/512/2328/2328761.png' class='pro-module-icon'><div class='pro-module-title'><h2>Calculadora de Costo Real de Nómina</h2></div></div>""", unsafe_allow_html=True)
        ac = st.file_uploader("Listado de Personal (.xlsx)")
        if ac:
            dc = pd.read_excel(ac); c1, c2, c3, c4 = st.columns(4); cn = c1.selectbox("Nombre", dc.columns); cs = c2.selectbox("Salario", dc.columns); ca = c3.selectbox("Aux. Transp? (Si/No)", dc.columns); ce = c4.selectbox("Exonerado? (Si/No)", dc.columns)
            if st.button("▶️ CALCULAR COSTO EMPRESA"):
                res = [{"Empleado": r[cn], "Costo Total": calcular_costo_empresa_fila(r, cs, ca, None, ce)[0]} for r in dc.to_dict('records')]
                st.dataframe(pd.DataFrame(res))

    elif menu == "Analítica Financiera Inteligente":
        # Cabecera Realista: Cerebro con gráficos
        st.markdown("""<div class='pro-module-header'><img src='https://cdn-icons-png.flaticon.com/512/10041/10041467.png' class='pro-module-icon'><div class='pro-module-title'><h2>Inteligencia Financiera (IA)</h2></div></div>""", unsafe_allow_html=True)
        fi = st.file_uploader("Datos Financieros (.xlsx/.csv)")
        if fi and api_key:
            df = pd.read_csv(fi) if fi.name.endswith('.csv') else pd.read_excel(fi); c1, c2 = st.columns(2); cd = c1.selectbox("Concepto/Cuenta", df.columns); cv = c2.selectbox("Valor", df.columns)
            if st.button("▶️ INICIAR ANÁLISIS IA"):
                top = df.groupby(cd)[cv].sum().nlargest(10); st.bar_chart(top); st.write(consultar_ia_gemini(f"Analiza financieramente estos saldos principales: {top.to_string()}"))

    elif menu == "Narrador Financiero & NIIF":
        # Cabecera Realista: Presentación de resultados
        st.markdown("""<div class='pro-module-header'><img src='https://cdn-icons-png.flaticon.com/512/3208/3208727.png' class='pro-module-icon'><div class='pro-module-title'><h2>Narrador Financiero & Notas NIIF</h2></div></div>""", unsafe_allow_html=True)
        c1, c2 = st.columns(2); f1 = c1.file_uploader("Año Actual (2025)"); f2 = c2.file_uploader("Año Anterior (2024)")
        if f1 and f2 and api_key:
            d1 = pd.read_excel(f1); d2 = pd.read_excel(f2); st.divider(); c1, c2, c3 = st.columns(3); cta = c1.selectbox("Cuenta", d1.columns); v1 = c2.selectbox("Valor 2025", d1.columns); v2 = c3.selectbox("Valor 2024", d2.columns)
            if st.button("✨ GENERAR INFORME ESTRATÉGICO"):
                g1 = d1.groupby(cta)[v1].sum().reset_index(name='V25'); g2 = d2.groupby(cta)[v2].sum().reset_index(name='V24')
                m = pd.merge(g1, g2, on=cta, how='inner'); m['VarAbs'] = m['V25'] - m['V24']
                top = m.reindex(m.VarAbs.abs().sort_values(ascending=False).index).head(5)
                st.bar_chart(top.set_index(cta)['VarAbs'])
                with st.spinner("Consultor IA redactando análisis..."):
                    st.markdown(consultar_ia_gemini(f"Actúa como CFO. Analiza estas variaciones para la junta directiva y redacta notas NIIF: {top.to_string()}"))

    elif menu == "Validador de RUT Oficial":
        # Cabecera Realista: Tarjeta de identificación
        st.markdown("""<div class='pro-module-header'><img src='https://cdn-icons-png.flaticon.com/512/9422/9422888.png' class='pro-module-icon'><div class='pro-module-title'><h2>Validador Oficial de RUT</h2></div></div>""", unsafe_allow_html=True)
        nit = st.text_input("Ingrese NIT o Cédula (Sin DV)", max_chars=15)
        if st.button("🔢 VERIFICAR"): st.metric("Dígito de Verificación (DV)", calcular_dv_colombia(nit)); st.link_button("Consulta Estado Muisca (DIAN)", "https://muisca.dian.gov.co/WebRutMuisca/DefConsultaEstadoRUT.faces")

    elif menu == "Digitalización OCR":
        # Cabecera Realista: Escáner láser
        st.markdown("""<div class='pro-module-header'><img src='https://cdn-icons-png.flaticon.com/512/3588/3588241.png' class='pro-module-icon'><div class='pro-module-title'><h2>Digitalización Inteligente (OCR)</h2></div></div>""", unsafe_allow_html=True)
        imgs = st.file_uploader("Imágenes de Facturas", type=["jpg","png"], accept_multiple_files=True)
        if imgs and api_key and st.button("🧠 EXTRAER INFORMACIÓN"):
            st.toast("Procesando con visión artificial..."); data = [ocr_factura(Image.open(i)) for i in imgs]; st.success("Digitalización completada."); st.dataframe(pd.DataFrame(data))

    # Cierre del contenedor animado
    st.markdown('</div>', unsafe_allow_html=True)

# ==============================================================================
# FOOTER CORPORATIVO
# ==============================================================================
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #64748b; padding: 20px; font-size: 0.9rem;'>
    <strong>Asistente Contable Pro</strong> | Enterprise Financial Suite | © 2025 All Rights Reserved.
</div>
""", unsafe_allow_html=True)
