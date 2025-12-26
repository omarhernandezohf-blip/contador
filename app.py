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
# 1. CONFIGURACIÓN VISUAL
# ==============================================================================
st.set_page_config(page_title="Asistente Contable Pro", page_icon="💼", layout="wide")

# ==============================================================================
# 2. CONEXIÓN A GOOGLE SHEETS (OPCIONAL)
# ==============================================================================
gc = None
try:
    if "gcp_service_account" in st.secrets:
        credentials_dict = st.secrets["gcp_service_account"]
        gc = gspread.service_account_from_dict(credentials_dict)
except Exception:
    pass

# ==============================================================================
# 3. LÓGICA DE CLIMA Y HORARIO (AUTO-DETECT)
# ==============================================================================
hora_actual = datetime.now().hour

if 6 <= hora_actual < 18:
    # MODO DÍA
    saludo = "Buenos días"
    icono_clima = "☀️"
    video_fondo = "https://joy.videvo.net/videvo_files/video/free/2013-08/large_watermarked/hd0992_preview.mp4" # Ciudad de día
    overlay_color = "linear-gradient(to right, rgba(255,255,255,0.85), rgba(200,220,255,0.7))"
    texto_hero = "#0f172a"
    sombra_hero = "none"
else:
    # MODO NOCHE
    saludo = "Buenas noches"
    icono_clima = "🌙"
    video_fondo = "https://joy.videvo.net/videvo_files/video/free/2015-09/large_watermarked/Network_Connection_Background_Blue_5966_preview.mp4" # Tech noche
    overlay_color = "linear-gradient(to bottom, rgba(15, 23, 42, 0.5), rgba(15, 23, 42, 0.95))"
    texto_hero = "#ffffff"
    sombra_hero = "0 4px 15px rgba(0,0,0,0.8)"

# ==============================================================================
# 4. ESTILOS CSS (DISEÑO CORPORATIVO)
# ==============================================================================
st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;700;900&display=swap');
    
    :root {{
        --primary-blue: #0A66C2;
        --tech-bg: #0f172a;
        --panel-bg: rgba(30, 41, 59, 0.7);
        --text-light: #e2e8f0;
    }}

    .stApp {{
        background-color: var(--tech-bg) !important;
        font-family: 'Inter', sans-serif;
    }}

    /* HERO HEADER CON VIDEO */
    .hero-container {{
        position: relative;
        width: 100%;
        height: 420px;
        border-radius: 20px;
        overflow: hidden;
        box-shadow: 0 20px 50px rgba(0,0,0,0.5);
        margin-bottom: 30px;
        border: 1px solid rgba(255,255,255,0.1);
    }}

    .hero-video {{
        position: absolute;
        top: 50%;
        left: 50%;
        min-width: 100%;
        min-height: 100%;
        width: auto;
        height: auto;
        z-index: 0;
        transform: translateX(-50%) translateY(-50%);
        object-fit: cover;
    }}

    .hero-overlay {{
        position: absolute;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background: {overlay_color};
        z-index: 1;
        backdrop-filter: blur(2px);
    }}

    .hero-content {{
        position: relative;
        z-index: 2;
        height: 100%;
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: center;
        text-align: center;
        padding: 20px;
    }}

    .hero-title {{
        font-size: 3.8rem;
        font-weight: 900;
        color: {texto_hero};
        text-transform: uppercase;
        letter-spacing: -1px;
        margin-bottom: 10px;
        text-shadow: {sombra_hero};
    }}

    .hero-weather-badge {{
        background: rgba(255,255,255,0.2);
        backdrop-filter: blur(10px);
        padding: 8px 20px;
        border-radius: 50px;
        border: 1px solid rgba(255,255,255,0.3);
        color: {texto_hero};
        font-weight: 600;
        font-size: 1.1rem;
        display: flex;
        align-items: center;
        gap: 10px;
        margin-bottom: 20px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
    }}

    /* VIDEO TUTORIAL PEQUEÑO */
    .tutorial-video-wrapper {{
        max-width: 500px;
        margin: 0 auto;
        border-radius: 12px;
        overflow: hidden;
        box-shadow: 0 10px 30px rgba(0,0,0,0.5);
        border: 1px solid rgba(255,255,255,0.1);
    }}

    /* CABECERAS DE MÓDULO REALISTAS */
    .pro-module-header {{
        display: flex;
        align-items: center;
        background: linear-gradient(90deg, rgba(10, 102, 194, 0.2) 0%, transparent 100%);
        padding: 20px;
        border-radius: 12px;
        border-left: 5px solid var(--primary-blue);
        margin-bottom: 25px;
    }}
    
    .pro-module-icon {{
        width: 70px;
        margin-right: 20px;
        filter: drop-shadow(0 4px 4px rgba(0,0,0,0.3));
    }}

    .pro-module-title h2 {{
        margin: 0;
        font-size: 2.2rem;
        font-weight: 700;
        color: #e2e8f0;
    }}

    /* TARJETAS DE INFORMACIÓN */
    .instruccion-box, .tutorial-step, .detail-box {{
        background: rgba(30, 41, 59, 0.6) !important;
        backdrop-filter: blur(12px);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 20px;
        transition: transform 0.2s;
    }}
    .instruccion-box:hover {{ transform: translateY(-3px); border-color: var(--primary-blue); }}
    .instruccion-box h4 {{ color: #60a5fa !important; margin-top: 0; }}
    .instruccion-box p {{ color: #cbd5e1 !important; }}

    /* SIDEBAR */
    [data-testid="stSidebar"] {{ background-color: #0b0f19; border-right: 1px solid rgba(255,255,255,0.05); }}
    .stRadio > div[role="radiogroup"] > label {{ color: #94a3b8 !important; padding: 10px !important; }}
    .stRadio > div[role="radiogroup"] > label[data-checked="true"] {{ color: #60a5fa !important; font-weight: 700 !important; }}
    
    /* BOTONES */
    .stButton>button {{
        background: linear-gradient(135deg, #0A66C2 0%, #004182 100%) !important;
        color: white !important; border-radius: 8px; font-weight: 600; border: none;
        padding: 12px 24px; width: 100%;
        box-shadow: 0 4px 10px rgba(10, 102, 194, 0.3);
    }}
    </style>
    """, unsafe_allow_html=True)

# CONSTANTES
SMMLV_2025, AUX_TRANS_2025 = 1430000, 175000
UVT_2025, TOPE_EFECTIVO = 49799, 100 * 49799
BASE_RET_SERVICIOS, BASE_RET_COMPRAS = 4 * 49799, 27 * 49799

# ==============================================================================
# 5. FUNCIONES LÓGICAS (TODO EL CÓDIGO ORIGINAL INTACTO)
# ==============================================================================

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
    if valor >= BASE_RET_COMPRAS: hallazgos.append("⚠️ Verificar Retención (Compras)."); riesgo = "MEDIO" if riesgo == "BAJO" else riesgo
    elif valor >= BASE_RET_SERVICIOS: hallazgos.append("⚠️ Verificar Retención (Servicios)."); riesgo = "MEDIO" if riesgo == "BAJO" else riesgo
    return " | ".join(hallazgos) if hallazgos else "OK", riesgo

def calcular_ugpp_fila(row, col_salario, col_no_salarial):
    s = float(row[col_salario] or 0); ns = float(row[col_no_salarial] or 0)
    limite = (s + ns) * 0.40
    if ns > limite: exc = ns - limite; return s + exc, exc, "RIESGO ALTO", f"Excede límite por ${exc:,.0f}"
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
    except: return {"Archivo": f.name, "Error": "XML Inválido"}

# ==============================================================================
# 6. SIDEBAR
# ==============================================================================
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/2830/2830303.png", width=70)
    st.markdown("### 💼 Suite Financiera")
    st.markdown("---")
    opciones_menu = ["Inicio / Dashboard", "Auditoría Cruce DIAN", "Minería de XML (Facturación)", "Conciliación Bancaria IA", "Auditoría Fiscal de Gastos", "Escáner de Nómina (UGPP)", "Proyección de Tesorería", "Costeo de Nómina Real", "Analítica Financiera Inteligente", "Narrador Financiero & NIIF", "Validador de RUT Oficial", "Digitalización OCR"]
    menu = st.radio("Módulos Operativos:", opciones_menu)
    st.markdown("---")
    with st.expander("🔐 Seguridad y Conexión IA"):
        api_key = st.text_input("API Key Google:", type="password")
        if api_key: genai.configure(api_key=api_key)
    st.markdown("<br><center><small style='color: #64748b;'>Enterprise Edition</small></center>", unsafe_allow_html=True)

# ==============================================================================
# 7. DESARROLLO DE PÁGINAS
# ==============================================================================

if menu == "Inicio / Dashboard":
    # HERO HEADER CON VIDEO REAL (HTML PURO)
    st.markdown(f"""
    <div class="hero-container">
        <video autoplay muted loop class="hero-video">
            <source src="{video_fondo}" type="video/mp4">
        </video>
        <div class="hero-overlay"></div>
        <div class="hero-content">
            <div class="hero-weather-badge">{icono_clima} {saludo} | Estado Actual</div>
            <h1 class="hero-title">ASISTENTE CONTABLE PRO</h1>
            <p style="color: #e2e8f0; font-size: 1.2rem; margin-top: 10px;">Tu Centro de Comando Financiero con Inteligencia Artificial.</p>
        </div>
    </div>
    """, unsafe_allow_html=True)

    c1, c2 = st.columns([1.2, 1])
    with c1:
        st.markdown("""
        <div class='instruccion-box' style='border-left: 4px solid #0A66C2;'>
            <h4>🚀 Potencia tu Contabilidad</h4>
            <p>Bienvenido a la suite contable más avanzada. Olvida la operatividad manual. Aquí, la Inteligencia Artificial trabaja para ti analizando datos, detectando riesgos y redactando informes en segundos.</p>
        </div>
        """, unsafe_allow_html=True)
    
    with c2:
        # VIDEO TUTORIAL PEQUEÑO, SUTIL Y CENTRADO
        st.markdown("""
        <div style="text-align: center;">
            <p style="color: #94a3b8; font-size: 0.9rem; margin-bottom: 5px;">Tutorial: Activación del Motor IA</p>
            <div class='tutorial-video-wrapper'>
                <iframe width="100%" height="200" src="https://www.youtube.com/embed/dHn3d66Qppw?rel=0&modestbranding=1" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>
            </div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")
    st.subheader("Pasos de Activación")
    c1, c2, c3 = st.columns(3)
    c1.markdown("<div class='tutorial-step'><h4>1. Acceso</h4><p>Ingresa a <a href='https://aistudio.google.com/app/apikey' target='_blank'>Google AI Studio</a>.</p></div>", unsafe_allow_html=True)
    c2.markdown("<div class='tutorial-step'><h4>2. Llave</h4><p>Crea tu API Key gratuita.</p></div>", unsafe_allow_html=True)
    c3.markdown("<div class='tutorial-step'><h4>3. Conexión</h4><p>Pégala en el menú lateral.</p></div>", unsafe_allow_html=True)

# --- MÓDULOS OPERATIVOS (CON IMÁGENES REALISTAS Y LÓGICA COMPLETA) ---

elif menu == "Auditoría Cruce DIAN":
    st.markdown("""<div class='pro-module-header'><img src='https://cdn-icons-png.flaticon.com/512/921/921591.png' class='pro-module-icon'><div class='pro-module-title'><h2>Auditor de Exógena (Cruce DIAN)</h2></div></div>""", unsafe_allow_html=True)
    st.markdown("<div class='instruccion-box'><h4>💡 Explicación del Módulo</h4><p>Esta herramienta compara el <strong>Reporte de Información Exógena (DIAN)</strong> reportado por terceros contra tu <strong>Contabilidad Interna</strong>. Detecta discrepancias en ingresos y costos para evitar sanciones por inexactitud antes de presentar la declaración de renta.</p></div>", unsafe_allow_html=True)
    c1, c2 = st.columns(2); f1 = c1.file_uploader("Reporte DIAN (.xlsx)"); f2 = c2.file_uploader("Auxiliar Contable (.xlsx)")
    if f1 and f2:
        d1 = pd.read_excel(f1); d2 = pd.read_excel(f2); st.divider(); c1, c2, c3, c4 = st.columns(4); n1 = c1.selectbox("NIT DIAN", d1.columns); v1 = c2.selectbox("Valor DIAN", d1.columns); n2 = c3.selectbox("NIT Conta", d2.columns); v2 = c4.selectbox("Valor Conta", d2.columns)
        if st.button("▶️ EJECUTAR CRUCE"):
            g1 = d1.groupby(n1)[v1].sum().reset_index(name='V1'); g2 = d2.groupby(n2)[v2].sum().reset_index(name='V2')
            m = pd.merge(g1, g2, left_on=n1, right_on=n2, how='outer').fillna(0); m['Dif'] = m['V1'] - m['V2']
            dif = m[abs(m['Dif']) > 1000]; st.dataframe(dif.style.format("{:,.0f}")) if not dif.empty else st.success("Sin diferencias materiales.")

elif menu == "Minería de XML (Facturación)":
    st.markdown("""<div class='pro-module-header'><img src='https://cdn-icons-png.flaticon.com/512/2823/2823523.png' class='pro-module-icon'><div class='pro-module-title'><h2>Minería de Datos XML</h2></div></div>""", unsafe_allow_html=True)
    st.markdown("<div class='instruccion-box'><h4>💡 Explicación del Módulo</h4><p>Extrae la información legal directamente de los archivos <strong>XML de Facturación Electrónica</strong>. A diferencia del PDF, el XML contiene los metadatos exactos de impuestos, fechas de validación y CUFE, permitiendo reconstruir contabilidades o auditar el IVA.</p></div>", unsafe_allow_html=True)
    axs = st.file_uploader("Cargar XMLs", type='xml', accept_multiple_files=True)
    if axs and st.button("▶️ PROCESAR"):
        res = [parsear_xml_dian(f) for f in axs]; st.dataframe(pd.DataFrame(res))

elif menu == "Conciliación Bancaria IA":
    st.markdown("""<div class='pro-module-header'><img src='https://cdn-icons-png.flaticon.com/512/2489/2489756.png' class='pro-module-icon'><div class='pro-module-title'><h2>Conciliación Bancaria IA</h2></div></div>""", unsafe_allow_html=True)
    st.markdown("<div class='instruccion-box'><h4>💡 Explicación del Módulo</h4><p>Utiliza un algoritmo de coincidencia inteligente para cruzar el <strong>Extracto Bancario</strong> con el <strong>Libro Auxiliar</strong>. Busca partidas por valor exacto dentro de una ventana de tiempo flexible (±3 días) para automatizar el 90% del trabajo operativo.</p></div>", unsafe_allow_html=True)
    c1, c2 = st.columns(2); fb = c1.file_uploader("Extracto"); fl = c2.file_uploader("Libro")
    if fb and fl:
        db = pd.read_excel(fb); dl = pd.read_excel(fl); c1, c2, c3, c4 = st.columns(4); cfb = c1.selectbox("F. Banco", db.columns); cvb = c2.selectbox("V. Banco", db.columns); cfl = c3.selectbox("F. Libro", dl.columns); cvl = c4.selectbox("V. Libro", dl.columns)
        col_desc = st.selectbox("Descripción (Opcional)", db.columns)
        if st.button("▶️ CONCILIAR"): 
            db['F'] = pd.to_datetime(db[cfb]); dl['F'] = pd.to_datetime(dl[cfl]); matches=[]
            for i, r in db.iterrows():
                c = dl[(dl[cvl] == r[cvb]) & (dl['F'].between(r['F']-timedelta(days=3), r['F']+timedelta(days=3)))]
                if not c.empty: matches.append(r.to_dict())
            st.success(f"Conciliados: {len(matches)} movimientos."); st.dataframe(pd.DataFrame(matches))

elif menu == "Auditoría Fiscal de Gastos":
    st.markdown("""<div class='pro-module-header'><img src='https://cdn-icons-png.flaticon.com/512/1642/1642346.png' class='pro-module-icon'><div class='pro-module-title'><h2>Auditoría Fiscal (Art. 771-5)</h2></div></div>""", unsafe_allow_html=True)
    st.markdown("<div class='instruccion-box'><h4>💡 Explicación del Módulo</h4><p>Analiza masivamente tu auxiliar de gastos para asegurar la deducibilidad en Renta. Verifica el cumplimiento de la <strong>Bancarización</strong> (pagos en efectivo prohibidos sobre topes) y alerta sobre posibles omisiones en <strong>Retención en la Fuente</strong>.</p></div>", unsafe_allow_html=True)
    ar = st.file_uploader("Auxiliar Gastos (.xlsx)")
    if ar:
        df = pd.read_excel(ar); c1, c2, c3, c4 = st.columns(4); cf = c1.selectbox("Fecha", df.columns); ct = c2.selectbox("Tercero", df.columns); cv = c3.selectbox("Valor", df.columns); cm = c4.selectbox("Método", ["N/A"]+list(df.columns))
        if st.button("▶️ AUDITAR"):
            res = [analizar_gasto_fila(r, cv, cm, "C") for r in df.to_dict('records')]; st.dataframe(pd.DataFrame(res))

elif menu == "Escáner de Nómina (UGPP)":
    st.markdown("""<div class='pro-module-header'><img src='https://cdn-icons-png.flaticon.com/512/3135/3135817.png' class='pro-module-icon'><div class='pro-module-title'><h2>Escáner UGPP (Ley 1393)</h2></div></div>""", unsafe_allow_html=True)
    st.markdown("<div class='instruccion-box'><h4>💡 Explicación del Módulo</h4><p>Protege a la empresa de sanciones de la UGPP. Verifica empleado por empleado que los <strong>pagos no salariales</strong> no excedan el 40% del total de la remuneración, calculando automáticamente el IBC ajustado si hay exceso.</p></div>", unsafe_allow_html=True)
    an = st.file_uploader("Nómina (.xlsx)")
    if an:
        dn = pd.read_excel(an); c1, c2, c3 = st.columns(3); cn = c1.selectbox("Emp", dn.columns); cs = c2.selectbox("Sal", dn.columns); cns = c3.selectbox("NoSal", dn.columns)
        if st.button("▶️ ESCANEAR"):
            res = [calcular_ugpp_fila(r, cs, cns) + (r[cn],) for r in dn.to_dict('records')]; st.dataframe(pd.DataFrame(res))

elif menu == "Proyección de Tesorería":
    st.markdown("""<div class='pro-module-header'><img src='https://cdn-icons-png.flaticon.com/512/5806/5806289.png' class='pro-module-icon'><div class='pro-module-title'><h2>Radar de Liquidez</h2></div></div>""", unsafe_allow_html=True)
    st.markdown("<div class='instruccion-box'><h4>💡 Explicación del Módulo</h4><p>Herramienta de planeación financiera. Cruza los vencimientos de tu <strong>Cartera (CxC)</strong> contra tus <strong>Proveedores (CxP)</strong> para proyectar el saldo de caja futuro y alertar sobre posibles déficits de liquidez.</p></div>", unsafe_allow_html=True)
    s0 = st.number_input("Saldo Hoy"); c1, c2 = st.columns(2); fc = c1.file_uploader("CxC"); fp = c2.file_uploader("CxP")
    if fc and fp:
        dc = pd.read_excel(fc); dp = pd.read_excel(fp); c1, c2, c3, c4 = st.columns(4); fc_f = c1.selectbox("F. CxC", dc.columns); fc_v = c2.selectbox("V. CxC", dc.columns); fp_f = c3.selectbox("F. CxP", dp.columns); fp_v = c4.selectbox("V. CxP", dp.columns)
        if st.button("▶️ PROYECTAR"): 
            dc['F'] = pd.to_datetime(dc[fc_f]); dp['F'] = pd.to_datetime(dp[fp_f])
            i = dc.groupby('F')[fc_v].sum().reset_index(); e = dp.groupby('F')[fp_v].sum().reset_index()
            m = pd.merge(i, e, on='F', how='outer').fillna(0); m = m.sort_values('F')
            m['Saldo'] = s0 + (m[fc_v] - m[fp_v]).cumsum()
            st.area_chart(m.set_index('F')['Saldo'])

elif menu == "Costeo de Nómina Real":
    st.markdown("""<div class='pro-module-header'><img src='https://cdn-icons-png.flaticon.com/512/2328/2328761.png' class='pro-module-icon'><div class='pro-module-title'><h2>Costeo de Nómina Real</h2></div></div>""", unsafe_allow_html=True)
    st.markdown("<div class='instruccion-box'><h4>💡 Explicación del Módulo</h4><p>Calcula el <strong>costo real</strong> de un empleado incluyendo carga prestacional (Primas, Cesantías), seguridad social y parafiscales. Permite simular escenarios con o sin exoneración de la Ley 1607.</p></div>", unsafe_allow_html=True)
    ac = st.file_uploader("Personal (.xlsx)")
    if ac:
        dc = pd.read_excel(ac); c1, c2, c3 = st.columns(3); cn = c1.selectbox("Nom", dc.columns); cs = c2.selectbox("Sal", dc.columns); ca = c3.selectbox("Aux", dc.columns)
        if st.button("▶️ CALCULAR"):
            res = [{"Emp": r[cn], "Costo": calcular_costo_empresa_fila(r, cs, ca, None, "No")[0]} for r in dc.to_dict('records')]; st.dataframe(pd.DataFrame(res))

elif menu == "Analítica Financiera Inteligente":
    st.markdown("""<div class='pro-module-header'><img src='https://cdn-icons-png.flaticon.com/512/10041/10041467.png' class='pro-module-icon'><div class='pro-module-title'><h2>Analítica Financiera (IA)</h2></div></div>""", unsafe_allow_html=True)
    st.markdown("<div class='instruccion-box'><h4>💡 Explicación del Módulo</h4><p>Convierte datos planos en insights. La IA analiza tus balances para detectar tendencias, variaciones atípicas y patrones de gasto, actuando como un <strong>analista financiero virtual</strong>.</p></div>", unsafe_allow_html=True)
    fi = st.file_uploader("Datos (.xlsx)")
    if fi and api_key:
        df = pd.read_excel(fi); c1, c2 = st.columns(2); cd = c1.selectbox("Desc", df.columns); cv = c2.selectbox("Vlr", df.columns)
        if st.button("▶️ ANALIZAR"):
            res = df.groupby(cd)[cv].sum().nlargest(10); st.bar_chart(res); st.markdown(consultar_ia_gemini(f"Analiza: {res.to_string()}"))

elif menu == "Narrador Financiero & NIIF":
    st.markdown("""<div class='pro-module-header'><img src='https://cdn-icons-png.flaticon.com/512/3208/3208727.png' class='pro-module-icon'><div class='pro-module-title'><h2>Narrador Financiero & NIIF</h2></div></div>""", unsafe_allow_html=True)
    st.markdown("<div class='instruccion-box'><h4>💡 Explicación del Módulo</h4><p>El fin de los reportes aburridos. Sube dos periodos contables y la IA redactará automáticamente un <strong>Informe Gerencial Ejecutivo</strong> y las <strong>Notas a los Estados Financieros</strong> bajo norma NIIF.</p></div>", unsafe_allow_html=True)
    c1, c2 = st.columns(2); f1 = c1.file_uploader("Año Actual"); f2 = c2.file_uploader("Año Anterior")
    if f1 and f2 and api_key:
        d1 = pd.read_excel(f1); d2 = pd.read_excel(f2); st.divider(); c1, c2, c3 = st.columns(3); cta = c1.selectbox("Cta", d1.columns); v1 = c2.selectbox("V25", d1.columns); v2 = c3.selectbox("V24", d2.columns)
        if st.button("✨ GENERAR INFORME"):
            g1 = d1.groupby(cta)[v1].sum().reset_index(name='V1'); g2 = d2.groupby(cta)[v2].sum().reset_index(name='V2')
            m = pd.merge(g1, g2, on=cta).fillna(0); m['Var'] = m['V1'] - m['V2']; top = m.reindex(m.Var.abs().sort_values(ascending=False).index).head(5)
            st.bar_chart(top.set_index(cta)['Var']); st.markdown(consultar_ia_gemini(f"Redacta informe gerencial de: {top.to_string()}"))

elif menu == "Validador de RUT Oficial":
    st.markdown("""<div class='pro-module-header'><img src='https://cdn-icons-png.flaticon.com/512/9422/9422888.png' class='pro-module-icon'><div class='pro-module-title'><h2>Validador de RUT</h2></div></div>""", unsafe_allow_html=True)
    st.markdown("<div class='instruccion-box'><h4>💡 Explicación del Módulo</h4><p>Herramienta de verificación de integridad. Aplica el algoritmo oficial <strong>Módulo 11</strong> para calcular el Dígito de Verificación (DV) de cualquier NIT, asegurando que tus terceros estén creados correctamente.</p></div>", unsafe_allow_html=True)
    nit = st.text_input("NIT")
    if st.button("🔢 CALCULAR"): st.metric("DV", calcular_dv_colombia(nit))

elif menu == "Digitalización OCR":
    st.markdown("""<div class='pro-module-header'><img src='https://cdn-icons-png.flaticon.com/512/3588/3588241.png' class='pro-module-icon'><div class='pro-module-title'><h2>Digitalización OCR</h2></div></div>""", unsafe_allow_html=True)
    st.markdown("<div class='instruccion-box'><h4>💡 Explicación del Módulo</h4><p>Transforma papel en datos. Sube fotos de facturas físicas y la IA extraerá <strong>NIT, Fecha, Proveedor y Valores</strong>, estructurándolos en una tabla lista para Excel. Ideal para legalización de gastos de viaje.</p></div>", unsafe_allow_html=True)
    img = st.file_uploader("Imagen")
    if img and api_key and st.button("🧠 LEER"): st.write(ocr_factura(Image.open(img)))

# ==============================================================================
# PIE DE PÁGINA
# ==============================================================================
st.markdown("---")
st.markdown("<center><strong>Asistente Contable Pro</strong> | Enterprise Financial Suite</center>", unsafe_allow_html=True)
