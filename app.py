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
st.set_page_config(page_title="Asistente Contable Pro", page_icon="💼", layout="wide")

# ==============================================================================
# 2. CONEXIÓN A GOOGLE SHEETS (OPCIONAL/SEGURO)
# ==============================================================================
# Intentamos conectar solo si existen las credenciales en Secrets
gc = None
try:
    if "gcp_service_account" in st.secrets:
        credentials_dict = st.secrets["gcp_service_account"]
        gc = gspread.service_account_from_dict(credentials_dict)
except Exception as e:
    pass # Si falla, la app sigue funcionando sin Sheets

# ==============================================================================
# 3. ESTILOS CSS AVANZADOS - DISEÑO CORPORATIVO "HIGH-TECH"
# ==============================================================================
hora_actual = datetime.now().hour
if 5 <= hora_actual < 12:
    saludo = "Buenos días"
elif 12 <= hora_actual < 18:
    saludo = "Buenas tardes"
else:
    saludo = "Buenas noches"

st.markdown("""
    <style>
    /* --- IMPORTAR FUENTE --- */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;800&display=swap');
    
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
        margin-top: 20px;
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
        width: 70px; /* Iconos grandes y realistas */
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

    .instruccion-box { border-left: 4px solid #3b82f6; }
    .instruccion-box h4, .reporte-box h4, .tutorial-step h4 { color: #60a5fa !important; font-weight: 700; font-size: 1.1rem; margin-top:0; }
    .instruccion-box p, .instruccion-box li, .reporte-box p { color: #cbd5e1 !important; line-height: 1.6; }
    
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
SMMLV_2025 = 1430000
AUX_TRANS_2025 = 175000
UVT_2025 = 49799
TOPE_EFECTIVO = 100 * UVT_2025
BASE_RET_SERVICIOS = 4 * UVT_2025
BASE_RET_COMPRAS = 27 * UVT_2025

# ==============================================================================
# 4. FUNCIONES DE LÓGICA DE NEGOCIO (COMPLETAS)
# ==============================================================================

def calcular_dv_colombia(nit_sin_dv):
    try:
        nit_str = str(nit_sin_dv).strip()
        if not nit_str.isdigit(): return "Error"
        primos = [3, 7, 13, 17, 19, 23, 29, 37, 41, 43, 47, 53, 59, 67, 71]
        suma = 0
        for i, digito in enumerate(reversed(nit_str)):
            if i < len(primos):
                suma += int(digito) * primos[i]
        resto = suma % 11
        return str(resto) if resto <= 1 else str(11 - resto)
    except:
        return "?"

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
    except Exception as e:
        return f"Error de conexión IA: {str(e)}"

def ocr_factura(imagen):
    try:
        model = genai.GenerativeModel('models/gemini-1.5-flash')
        prompt = """Extrae datos JSON estricto: {"fecha": "YYYY-MM-DD", "nit": "num", "proveedor": "txt", "concepto": "txt", "base": num, "iva": num, "total": num}"""
        response = model.generate_content([prompt, imagen])
        return json.loads(response.text.replace("```json", "").replace("```", "").strip())
    except:
        return None

def parsear_xml_dian(archivo_xml):
    try:
        tree = ET.parse(archivo_xml)
        root = tree.getroot()
        ns = {'cac': 'urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2',
              'cbc': 'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2'}
        def get_text(path, root_elem=root):
            elem = root_elem.find(path, ns)
            return elem.text if elem is not None else ""
        
        data = {}
        data['Archivo'] = archivo_xml.name
        data['Prefijo'] = get_text('.//cbc:ID')
        data['Fecha Emision'] = get_text('.//cbc:IssueDate')
        
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
    except:
        return {"Archivo": archivo_xml.name, "Error": "Error XML"}

# ==============================================================================
# 5. INTERFAZ DE USUARIO (SIDEBAR & MENÚ PROFESIONAL)
# ==============================================================================
with st.sidebar:
    # Logo principal (Imagen realista de maletín o edificio abstracto)
    st.image("https://cdn-icons-png.flaticon.com/512/2830/2830303.png", width=80)
    
    st.markdown("### 💼 Suite Financiera")
    st.markdown("---")
    
    # MENÚ LIMPIO SIN EMOJIS (SOLO TEXTO PROFESIONAL)
    opciones_menu = [
        "Inicio / Dashboard",
        "Auditoría Cruce DIAN",
        "Minería de XML (Facturación)",
        "Conciliación Bancaria IA",
        "Auditoría Fiscal de Gastos",
        "Escáner de Nómina (UGPP)",
        "Proyección de Tesorería",
        "Costeo de Nómina Real",
        "Analítica Financiera Inteligente",
        "Narrador Financiero & NIIF",
        "Validador de RUT Oficial",
        "Digitalización OCR"
    ]
    
    # El estilo CSS hace que esto se vea como un menú de software ERP
    menu = st.radio("Módulos Operativos:", opciones_menu)
    
    st.markdown("---")
    with st.expander("🔐 Seguridad y Conexión IA"):
        st.info("Pega aquí tu llave para activar el modo 'Cerebro IA':")
        api_key = st.text_input("API Key Google:", type="password")
        if api_key: genai.configure(api_key=api_key)
    
    st.markdown("<br><center><small style='color: #64748b;'>Enterprise Edition v10.0</small></center>", unsafe_allow_html=True)

# ==============================================================================
# 6. PÁGINAS PRINCIPALES (CON CABECERAS REALISTAS Y FONDOS ANIMADOS)
# ==============================================================================

# ------------------------------------------------------------------------------
# 0. INICIO / DASHBOARD (HERO HEADER)
# ------------------------------------------------------------------------------
if menu == "Inicio / Dashboard":
    # HERO HEADER SOBREPUESTO Y VISIBLE
    st.markdown(f"""
    <div class='hero-header-container'>
        <h1 class='hero-title-text'>ASISTENTE CONTABLE PRO</h1>
        <p class='hero-subtitle-text'>{saludo}. Plataforma de Inteligencia Financiera Corporativa.</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Contenedor para descripción y video
    c1, c2 = st.columns([2, 1])
    
    with c1:
        st.markdown("""
        <div class='instruccion-box' style='border-left: 4px solid #0A66C2; background: rgba(15, 23, 42, 0.8);'>
            <h4 style='color: #fff !important; font-size: 1.3rem;'>🚀 La Evolución de la Contabilidad</h4>
            <p style='font-size: 1.1rem;'>Esta suite Enterprise ha sido diseñada para automatizar lo operativo y dejarte tiempo para lo estratégico. <strong>Precisión algorítmica, velocidad de procesamiento y análisis profundo.</strong></p>
        </div>
        """, unsafe_allow_html=True)
        
        # Resumen de Herramientas
        cc1, cc2 = st.columns(2)
        with cc1:
            st.info("⚖️ **Auditoría Fiscal:** Cruces automáticos DIAN vs Contabilidad.")
            st.info("📧 **Minería XML:** Extracción masiva de datos fiscales.")
        with cc2:
            st.info("🤝 **Conciliación IA:** Matching bancario inteligente.")
            st.info("📈 **Reportes NIIF:** Redacción automática experta.")

    with c2:
        # Video Tutorial (Pequeño y Delicado)
        st.markdown("<div class='video-container' style='text-align: center; margin-top: 10px;'>", unsafe_allow_html=True)
        st.video("https://www.youtube.com/watch?v=dHn3d66Qppw") 
        st.caption("Tutorial: Activación del Motor IA")
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("---")
    
    st.subheader("Protocolo de Activación IA")
    
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("""
        <div class='tutorial-step'>
        <h4>1. Acceso Seguro</h4>
        <p>Entra a Google AI Studio con credenciales corporativas.</p>
        <p><a href='https://aistudio.google.com/app/apikey' target='_blank'>🔗 Portal Oficial</a></p>
        </div>
        """, unsafe_allow_html=True)
    
    with c2:
        st.markdown("""
        <div class='tutorial-step'>
        <h4>2. Generación de Credencial</h4>
        <p>Haz clic en el botón azul <strong>"Get API Key"</strong> y luego en "Create Key".</p>
        </div>
        """, unsafe_allow_html=True)
        
    with c3:
        st.markdown("""
        <div class='tutorial-step'>
        <h4>3. Vinculación al Sistema</h4>
        <p>Copia la llave y pégala en el módulo de seguridad del menú lateral izquierdo.</p>
        </div>
        """, unsafe_allow_html=True)

# ------------------------------------------------------------------------------
# CONTENIDO DE MÓDULOS (CON FONDO ANIMADO SUTIL Y CABECERAS REALISTAS)
# ------------------------------------------------------------------------------
else:
    # Contenedor principal con animación de fondo sutil
    st.markdown('<div class="animated-module-bg">', unsafe_allow_html=True)

    if menu == "Auditoría Cruce DIAN":
        # Cabecera Realista: Edificio Gubernamental Moderno
        st.markdown("""<div class='pro-module-header'><img src='https://cdn-icons-png.flaticon.com/512/921/921591.png' class='pro-module-icon'><div class='pro-module-title'><h2>Auditor de Exógena (Cruce DIAN)</h2></div></div>""", unsafe_allow_html=True)
        
        st.markdown("<div class='instruccion-box'><h4>💡 Consistencia Fiscal</h4><p>Cruce automático entre la información reportada por terceros a la entidad fiscal y los registros contables internos para detectar brechas.</p></div>", unsafe_allow_html=True)
        
        col_dian, col_conta = st.columns(2)
        with col_dian:
            st.subheader("🏛️ 1. Archivo DIAN")
            file_dian = st.file_uploader("Subir 'Reporte Terceros DIAN' (.xlsx)", type=['xlsx'])
        with col_conta:
            st.subheader("📒 2. Contabilidad")
            file_conta = st.file_uploader("Subir Auxiliar por Tercero (.xlsx)", type=['xlsx'])
            
        if file_dian and file_conta:
            df_dian = pd.read_excel(file_dian)
            df_conta = pd.read_excel(file_conta)
            
            st.divider()
            st.subheader("⚙️ Configuración del Mapeo")
            c1, c2, c3, c4 = st.columns(4)
            nit_dian = c1.selectbox("NIT (Archivo DIAN):", df_dian.columns)
            val_dian = c2.selectbox("Valor (Archivo DIAN):", df_dian.columns)
            nit_conta = c3.selectbox("NIT (Tu Contabilidad):", df_conta.columns)
            val_conta = c4.selectbox("Saldo (Tu Contabilidad):", df_conta.columns)
            
            if st.button("▶️ EJECUTAR AUDITORÍA"):
                dian_grouped = df_dian.groupby(nit_dian)[val_dian].sum().reset_index()
                dian_grouped.columns = ['NIT', 'Valor_DIAN']
                
                conta_grouped = df_conta.groupby(nit_conta)[val_conta].sum().reset_index()
                conta_grouped.columns = ['NIT', 'Valor_Conta']
                
                cruce = pd.merge(dian_grouped, conta_grouped, on='NIT', how='outer').fillna(0)
                cruce['Diferencia'] = cruce['Valor_DIAN'] - cruce['Valor_Conta']
                
                diferencias = cruce[abs(cruce['Diferencia']) > 1000]
                
                st.success("Cruce Finalizado.")
                
                m1, m2 = st.columns(2)
                m1.metric("Total Reportado DIAN", f"${cruce['Valor_DIAN'].sum():,.0f}")
                m2.metric("Total Tu Contabilidad", f"${cruce['Valor_Conta'].sum():,.0f}")
                
                if not diferencias.empty:
                    st.error(f"⚠️ Se detectaron {len(diferencias)} inconsistencias materiales.")
                    st.dataframe(diferencias.style.format("{:,.0f}"), use_container_width=True)
                    
                    out = io.BytesIO()
                    with pd.ExcelWriter(out, engine='xlsxwriter') as w:
                        diferencias.to_excel(w, index=False)
                    st.download_button("📥 Descargar Reporte de Diferencias", out.getvalue(), "Auditoria_Exogena.xlsx")
                else:
                    st.balloons()
                    st.success("✅ Conciliación perfecta. No se hallaron diferencias materiales.")

    elif menu == "Minería de XML (Facturación)":
        # Cabecera Realista: Servidor de Datos / Archivos
        st.markdown("""<div class='pro-module-header'><img src='https://cdn-icons-png.flaticon.com/512/2823/2823523.png' class='pro-module-icon'><div class='pro-module-title'><h2>Minería de Datos XML (Facturación)</h2></div></div>""", unsafe_allow_html=True)
        
        st.markdown("<div class='instruccion-box'><h4>💡 Extracción desde la Fuente Legal</h4><p>Procesamiento masivo de archivos XML de facturación electrónica para reconstruir la contabilidad fiscal con exactitud.</p></div>", unsafe_allow_html=True)
        
        archivos_xml = st.file_uploader("Cargar XMLs (Lote)", type=['xml'], accept_multiple_files=True)
        if archivos_xml and st.button("▶️ INICIAR PROCESAMIENTO"):
            st.toast("Procesando lote de archivos...")
            datos_xml = []
            barra = st.progress(0)
            for i, f in enumerate(archivos_xml):
                barra.progress((i+1)/len(archivos_xml))
                datos_xml.append(parsear_xml_dian(f))
            
            df_xml = pd.DataFrame(datos_xml)
            st.success("Extracción completada.")
            st.dataframe(df_xml, use_container_width=True)
            
            out = io.BytesIO()
            with pd.ExcelWriter(out, engine='xlsxwriter') as w: df_xml.to_excel(w, index=False)
            st.download_button("📥 Descargar Reporte Maestro (.xlsx)", out.getvalue(), "Resumen_XML.xlsx")

    elif menu == "Conciliación Bancaria IA":
        # Cabecera Realista: Bóveda Bancaria / Seguridad
        st.markdown("""<div class='pro-module-header'><img src='https://cdn-icons-png.flaticon.com/512/2489/2489756.png' class='pro-module-icon'><div class='pro-module-title'><h2>Conciliación Bancaria Inteligente</h2></div></div>""", unsafe_allow_html=True)
        
        st.markdown("<div class='instruccion-box'><h4>💡 Matching Algorítmico</h4><p>Algoritmo de emparejamiento automático entre extractos bancarios y libros auxiliares basado en importes y ventanas de tiempo.</p></div>", unsafe_allow_html=True)
        
        col_banco, col_libro = st.columns(2)
        with col_banco:
            st.subheader("🏦 Extracto Bancario")
            file_banco = st.file_uploader("Subir Excel Banco", type=['xlsx'])
        with col_libro:
            st.subheader("📒 Libro Auxiliar")
            file_libro = st.file_uploader("Subir Excel Contabilidad", type=['xlsx'])
            
        if file_banco and file_libro:
            df_banco = pd.read_excel(file_banco)
            df_libro = pd.read_excel(file_libro)
            
            st.divider()
            c1, c2, c3, c4 = st.columns(4)
            col_fecha_b = c1.selectbox("Fecha Banco:", df_banco.columns, key="fb")
            col_valor_b = c2.selectbox("Valor Banco:", df_banco.columns, key="vb")
            col_fecha_l = c3.selectbox("Fecha Libro:", df_libro.columns, key="fl")
            col_valor_l = c4.selectbox("Valor Libro:", df_libro.columns, key="vl")
            col_desc_b = st.selectbox("Descripción Banco (Para detalle):", df_banco.columns, key="db")
            
            if st.button("▶️ EJECUTAR CONCILIACIÓN"):
                df_banco['Fecha_Dt'] = pd.to_datetime(df_banco[col_fecha_b])
                df_libro['Fecha_Dt'] = pd.to_datetime(df_libro[col_fecha_l])
                df_banco['Conciliado'] = False; df_libro['Conciliado'] = False
                matches = []
                
                bar = st.progress(0)
                for idx_b, row_b in df_banco.iterrows():
                    bar.progress((idx_b+1)/len(df_banco))
                    vb = row_b[col_valor_b]
                    fb = row_b['Fecha_Dt']
                    # Lógica de coincidencia difusa (ventana de 3 días)
                    cands = df_libro[(df_libro[col_valor_l] == vb) & (~df_libro['Conciliado']) & (df_libro['Fecha_Dt'].between(fb-timedelta(days=3), fb+timedelta(days=3)))]
                    
                    if not cands.empty:
                        df_banco.at[idx_b, 'Conciliado']=True
                        df_libro.at[cands.index[0], 'Conciliado']=True
                        matches.append({"Fecha": row_b[col_fecha_b], "Desc": row_b[col_desc_b], "Valor": vb, "Estado": "✅ OK"})
                
                st.success(f"Proceso finalizado. {len(matches)} partidas conciliadas automáticamente.")
                t1, t2, t3 = st.tabs(["✅ Partidas Cruzadas", "⚠️ Pendientes en Banco", "⚠️ Pendientes en Libros"])
                with t1: st.dataframe(pd.DataFrame(matches), use_container_width=True)
                with t2: st.dataframe(df_banco[~df_banco['Conciliado']], use_container_width=True)
                with t3: st.dataframe(df_libro[~df_libro['Conciliado']], use_container_width=True)

    elif menu == "Auditoría Fiscal de Gastos":
        # Cabecera Realista: Documento con Lupa
        st.markdown("""<div class='pro-module-header'><img src='https://cdn-icons-png.flaticon.com/512/1642/1642346.png' class='pro-module-icon'><div class='pro-module-title'><h2>Auditoría Fiscal Masiva (Art. 771-5)</h2></div></div>""", unsafe_allow_html=True)
        
        ar = st.file_uploader("Cargar Auxiliar de Gastos (.xlsx)", type=['xlsx'])
        if ar:
            df = pd.read_excel(ar)
            c1, c2, c3, c4 = st.columns(4)
            cf = c1.selectbox("Fecha", df.columns)
            ct = c2.selectbox("Tercero", df.columns)
            cv = c3.selectbox("Valor", df.columns)
            cm = c4.selectbox("Método de Pago", ["No disponible"]+list(df.columns))
            cc = st.selectbox("Concepto (Opcional)", df.columns)
            
            if st.button("▶️ ANALIZAR RIESGOS"):
                res = []
                for r in df.to_dict('records'):
                    h, rs = analizar_gasto_fila(r, cv, cm, cc)
                    if rs != "BAJO": # Solo mostramos lo relevante
                        res.append({"Fecha": r[cf], "Tercero": r[ct], "Valor": r[cv], "Riesgo": rs, "Hallazgo": h})
                
                if res:
                    st.warning(f"Se encontraron {len(res)} operaciones con riesgo fiscal.")
                    st.dataframe(pd.DataFrame(res), use_container_width=True)
                else:
                    st.success("No se encontraron riesgos fiscales evidentes.")

    elif menu == "Escáner de Nómina (UGPP)":
        # Cabecera Realista: Calculadora y Gente
        st.markdown("""<div class='pro-module-header'><img src='https://cdn-icons-png.flaticon.com/512/3135/3135817.png' class='pro-module-icon'><div class='pro-module-title'><h2>Escáner de Riesgo UGPP (Ley 1393)</h2></div></div>""", unsafe_allow_html=True)
        
        an = st.file_uploader("Cargar Nómina (.xlsx)", type=['xlsx'])
        if an:
            dn = pd.read_excel(an)
            c1, c2, c3 = st.columns(3)
            cn = c1.selectbox("Empleado", dn.columns)
            cs = c2.selectbox("Salario Básico", dn.columns)
            cns = c3.selectbox("Pagos No Salariales", dn.columns)
            
            if st.button("▶️ ESCANEAR NÓMINA"):
                res = []
                for r in dn.to_dict('records'):
                    ibc, exc, est, msg = calcular_ugpp_fila(r, cs, cns)
                    res.append({"Empleado": r[cn], "IBC Ajustado": ibc, "Exceso": exc, "Estado": est, "Detalle": msg})
                st.dataframe(pd.DataFrame(res), use_container_width=True)

    elif menu == "Proyección de Tesorería":
        # Cabecera Realista: Gráfico ascendente con dinero
        st.markdown("""<div class='pro-module-header'><img src='https://cdn-icons-png.flaticon.com/512/5806/5806289.png' class='pro-module-icon'><div class='pro-module-title'><h2>Radar de Liquidez & Flujo de Caja</h2></div></div>""", unsafe_allow_html=True)
        
        saldo_hoy = st.number_input("💵 Saldo Disponible Hoy ($):", min_value=0.0, format="%.2f")
        c1, c2 = st.columns(2)
        fcxc = c1.file_uploader("Cartera (CxC)", type=['xlsx'])
        fcxp = c2.file_uploader("Proveedores (CxP)", type=['xlsx'])
        
        if fcxc and fcxp:
            dcxc = pd.read_excel(fcxc); dcxp = pd.read_excel(fcxp)
            c1, c2, c3, c4 = st.columns(4)
            cfc = c1.selectbox("Fecha Vencimiento CxC:", dcxc.columns)
            cvc = c2.selectbox("Valor CxC:", dcxc.columns)
            cfp = c3.selectbox("Fecha Vencimiento CxP:", dcxp.columns)
            cvp = c4.selectbox("Valor CxP:", dcxp.columns)
            
            if st.button("▶️ GENERAR PROYECCIÓN"):
                try:
                    dcxc['Fecha'] = pd.to_datetime(dcxc[cfc]); dcxp['Fecha'] = pd.to_datetime(dcxp[cfp])
                    fi = dcxc.groupby('Fecha')[cvc].sum().reset_index(); fe = dcxp.groupby('Fecha')[cvp].sum().reset_index()
                    cal = pd.merge(fi, fe, on='Fecha', how='outer').fillna(0)
                    cal.columns = ['Fecha', 'Ingresos', 'Egresos']; cal = cal.sort_values('Fecha')
                    cal['Saldo Proyectado'] = saldo_hoy + (cal['Ingresos'] - cal['Egresos']).cumsum()
                    
                    st.area_chart(cal.set_index('Fecha')['Saldo Proyectado'])
                    st.dataframe(cal, use_container_width=True)
                    
                    if api_key:
                        with st.spinner("🤖 La IA está analizando tu flujo de caja..."):
                            st.markdown(consultar_ia_gemini(f"Analiza este flujo de caja. Saldo inicial: {saldo_hoy}. Datos: {cal.head(10).to_string()}"))
                except: st.error("Error en formato de fechas.")

    elif menu == "Costeo de Nómina Real":
        # Cabecera Realista: Dinero y Personal
        st.markdown("""<div class='pro-module-header'><img src='https://cdn-icons-png.flaticon.com/512/2328/2328761.png' class='pro-module-icon'><div class='pro-module-title'><h2>Calculadora de Costo Real de Nómina</h2></div></div>""", unsafe_allow_html=True)
        
        ac = st.file_uploader("Cargar Listado Personal (.xlsx)", type=['xlsx'])
        if ac:
            dc = pd.read_excel(ac)
            c1, c2, c3, c4 = st.columns(4)
            cn = c1.selectbox("Nombre", dc.columns)
            cs = c2.selectbox("Salario", dc.columns)
            ca = c3.selectbox("Aux Trans (SI/NO)", dc.columns)
            ce = c4.selectbox("Empresa Exonerada (SI/NO)", dc.columns)
            
            if st.button("▶️ CALCULAR COSTOS"):
                rc = []
                for r in dc.to_dict('records'):
                    c, cr = calcular_costo_empresa_fila(r, cs, ca, None, ce)
                    rc.append({"Empleado": r[cn], "Costo Total Mensual": c})
                st.dataframe(pd.DataFrame(rc), use_container_width=True)

    elif menu == "Analítica Financiera Inteligente":
        # Cabecera Realista: Cerebro digital
        st.markdown("""<div class='pro-module-header'><img src='https://cdn-icons-png.flaticon.com/512/10041/10041467.png' class='pro-module-icon'><div class='pro-module-title'><h2>Inteligencia Financiera (IA)</h2></div></div>""", unsafe_allow_html=True)
        
        fi = st.file_uploader("Cargar Datos Financieros (.xlsx/.csv)", type=['xlsx', 'csv'])
        if fi and api_key:
            df = pd.read_csv(fi) if fi.name.endswith('.csv') else pd.read_excel(fi)
            c1, c2 = st.columns(2)
            cd = c1.selectbox("Columna Descripción", df.columns)
            cv = c2.selectbox("Columna Valor", df.columns)
            
            if st.button("▶️ INICIAR ANÁLISIS IA"):
                res = df.groupby(cd)[cv].sum().sort_values(ascending=False).head(10)
                st.bar_chart(res)
                st.markdown(consultar_ia_gemini(f"Actúa como auditor financiero. Analiza estos saldos: {res.to_string()}"))

    elif menu == "Narrador Financiero & NIIF":
        # Cabecera Realista: Presentación de negocios
        st.markdown("""<div class='pro-module-header'><img src='https://cdn-icons-png.flaticon.com/512/3208/3208727.png' class='pro-module-icon'><div class='pro-module-title'><h2>Narrador Financiero & Notas NIIF</h2></div></div>""", unsafe_allow_html=True)
        
        c1, c2 = st.columns(2)
        f1 = c1.file_uploader("Año Actual", type=['xlsx'])
        f2 = c2.file_uploader("Año Anterior", type=['xlsx'])
        
        if f1 and f2 and api_key:
            d1 = pd.read_excel(f1); d2 = pd.read_excel(f2)
            st.divider()
            c1, c2, c3 = st.columns(3)
            cta = c1.selectbox("Cuenta Contable", d1.columns)
            v1 = c2.selectbox("Valor Año Actual", d1.columns)
            v2 = c3.selectbox("Valor Año Anterior", d2.columns)
            
            if st.button("✨ GENERAR INFORME ESTRATÉGICO"):
                g1 = d1.groupby(cta)[v1].sum().reset_index(name='V_Act')
                g2 = d2.groupby(cta)[v2].sum().reset_index(name='V_Ant')
                
                merged = pd.merge(g1, g2, on=cta, how='inner').fillna(0)
                merged['Variacion'] = merged['V_Act'] - merged['V_Ant']
                top = merged.reindex(merged.Variacion.abs().sort_values(ascending=False).index).head(10)
                
                st.markdown("### 📊 Tablero de Control Gerencial")
                st.bar_chart(top.set_index(cta)['Variacion'])
                
                with st.spinner("🤖 El Consultor IA está redactando el informe..."):
                    prompt = f"""
                    Actúa como un CFO experto. Analiza la siguiente tabla de variaciones contables:
                    {top.to_string()}
                    GENERA:
                    1. Un Informe Gerencial Ejecutivo explicando las causas probables.
                    2. Un borrador de Nota a los Estados Financieros bajo NIIF.
                    """
                    st.markdown(consultar_ia_gemini(prompt))

    elif menu == "Validador de RUT Oficial":
        # Cabecera Realista: Tarjeta ID
        st.markdown("""<div class='pro-module-header'><img src='https://cdn-icons-png.flaticon.com/512/9422/9422888.png' class='pro-module-icon'><div class='pro-module-title'><h2>Validador Oficial de RUT</h2></div></div>""", unsafe_allow_html=True)
        
        nit = st.text_input("Ingrese NIT o Cédula (Sin DV):", max_chars=15)
        if st.button("🔢 VERIFICAR"):
            dv = calcular_dv_colombia(nit)
            st.metric("Dígito de Verificación (DV)", dv)
            st.link_button("🔗 Consulta Estado en Muisca (DIAN)", "https://muisca.dian.gov.co/WebRutMuisca/DefConsultaEstadoRUT.faces")

    elif menu == "Digitalización OCR":
        # Cabecera Realista: Escáner Láser
        st.markdown("""<div class='pro-module-header'><img src='https://cdn-icons-png.flaticon.com/512/3588/3588241.png' class='pro-module-icon'><div class='pro-module-title'><h2>Digitalización Inteligente (OCR)</h2></div></div>""", unsafe_allow_html=True)
        
        af = st.file_uploader("Cargar Imágenes", type=["jpg", "png"], accept_multiple_files=True)
        if af and st.button("🧠 PROCESAR IMÁGENES") and api_key:
            do = []
            bar = st.progress(0)
            for i, f in enumerate(af):
                bar.progress((i+1)/len(af)); info = ocr_factura(Image.open(f))
                if info: do.append(info)
            st.dataframe(pd.DataFrame(do), use_container_width=True)

    # Cierre del contenedor animado
    st.markdown('</div>', unsafe_allow_html=True)

# ==============================================================================
# PIE DE PÁGINA
# ==============================================================================
st.markdown("---")
st.markdown("<center><strong>Asistente Contable Pro</strong> | Enterprise Financial Suite</center>", unsafe_allow_html=True)
