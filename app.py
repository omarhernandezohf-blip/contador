import streamlit as st
import pandas as pd
import google.generativeai as genai
from PIL import Image
import json
import time
import io
from datetime import datetime, timedelta
import xml.etree.ElementTree as ET

# ==============================================================================
# 1. CONFIGURACIÓN VISUAL PROFESIONAL
# ==============================================================================
st.set_page_config(page_title="Asistente Contable Pro 2025", page_icon="📊", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    h1 { color: #0d6efd; font-weight: 800; }
    h2, h3 { color: #343a40; }
    .stButton>button {
        background-color: #0d6efd; color: white; border-radius: 8px; 
        font-weight: bold; width: 100%; height: 3.5em; border: none;
    }
    .stButton>button:hover { background-color: #0b5ed7; box-shadow: 0 4px 8px rgba(0,0,0,0.2); }
    .reporte-box {
        background-color: #ffffff; padding: 20px; border-radius: 10px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1); border-left: 6px solid #0d6efd;
    }
    .rut-card {
        background-color: #ffffff; padding: 20px; border-radius: 10px;
        border-left: 5px solid #1565c0; color: #343a40;
        box-shadow: 0 2px 5px rgba(0,0,0,0.1);
    }
    /* Estilos Tesorería */
    .metric-box-red { background-color: #f8d7da; padding: 10px; border-radius: 5px; color: #721c24; text-align: center; }
    .metric-box-green { background-color: #d1e7dd; padding: 10px; border-radius: 5px; color: #0f5132; text-align: center; }
    
    /* VISIBILIDAD DE TEXTO (Instrucciones) */
    .instruccion-box {
        background-color: #e2e3e5; 
        color: #212529 !important; 
        padding: 15px; border-radius: 8px; margin-bottom: 20px; border-left: 5px solid #343a40;
    }
    .instruccion-box h4 { color: #000000 !important; margin-top: 0; font-weight: bold; }
    .instruccion-box p, .instruccion-box li { color: #212529 !important; }
    </style>
    """, unsafe_allow_html=True)

# ==============================================================================
# 2. CONSTANTES FISCALES 2025
# ==============================================================================
SMMLV_2025 = 1430000
AUX_TRANS_2025 = 175000
UVT_2025 = 49799
TOPE_EFECTIVO = 100 * UVT_2025
BASE_RET_SERVICIOS = 4 * UVT_2025
BASE_RET_COMPRAS = 27 * UVT_2025

# ==============================================================================
# 3. LÓGICA DE NEGOCIO (EL MOTOR CONTABLE)
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
# 4. BARRA LATERAL
# ==============================================================================
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/9320/9320399.png", width=80)
    st.title("Suite Contable IA")
    st.markdown("---")
    
    menu = st.radio("Herramientas:", 
                    ["🤝 Conciliador Bancario (IA)", # <-- NUEVA HERRAMIENTA
                     "📧 Lector XML (Facturación)", 
                     "💰 Tesorería & Flujo de Caja", 
                     "🔍 Validador de RUT (Real)",  
                     "📂 Auditoría Masiva de Gastos", 
                     "👥 Escáner de Nómina (UGPP)", 
                     "💰 Calculadora Costos (Masiva)",
                     "📸 Digitalización (OCR)",
                     "📊 Analítica Financiera"])
    
    st.markdown("---")
    with st.expander("🔑 Configuración IA"):
        st.info("Activar Inteligencia Artificial:")
        api_key = st.text_input("API Key:", type="password")
        if api_key: genai.configure(api_key=api_key)

# ==============================================================================
# 5. PESTAÑAS Y FUNCIONALIDADES
# ==============================================================================

# ------------------------------------------------------------------------------
# MÓDULO NUEVO: CONCILIADOR BANCARIO
# ------------------------------------------------------------------------------
if menu == "🤝 Conciliador Bancario (IA)":
    st.header("🤝 Conciliador Bancario Automático")
    
    st.markdown("""
    <div class='instruccion-box'>
        <h4>💡 ¿Cómo funciona el Match Automático?</h4>
        <p>Cruza los movimientos del Banco contra tu Contabilidad para detectar diferencias en segundos.</p>
        <p><strong>Pasos:</strong></p>
        <ol>
            <li>Sube el <strong>Extracto Bancario</strong> (Excel).</li>
            <li>Sube el <strong>Libro Auxiliar de Bancos</strong> de tu software (Excel).</li>
            <li>El sistema buscará coincidencias exactas por <strong>Valor</strong> y <strong>Fecha Cercana</strong> (Margen de 3 días).</li>
        </ol>
    </div>
    """, unsafe_allow_html=True)
    
    col_banco, col_libro = st.columns(2)
    
    with col_banco:
        st.subheader("🏦 1. Extracto Bancario")
        file_banco = st.file_uploader("Subir Extracto (.xlsx)", type=['xlsx'])
        
    with col_libro:
        st.subheader("📒 2. Auxiliar Contable")
        file_libro = st.file_uploader("Subir Auxiliar (.xlsx)", type=['xlsx'])
        
    if file_banco and file_libro:
        df_banco = pd.read_excel(file_banco)
        df_libro = pd.read_excel(file_libro)
        
        st.write("---")
        st.subheader("⚙️ Mapeo de Columnas")
        c1, c2, c3, c4 = st.columns(4)
        col_fecha_b = c1.selectbox("Fecha Banco:", df_banco.columns, key="fb")
        col_valor_b = c2.selectbox("Valor/Importe Banco:", df_banco.columns, key="vb")
        col_fecha_l = c3.selectbox("Fecha Contabilidad:", df_libro.columns, key="fl")
        col_valor_l = c4.selectbox("Valor/Saldo Contabilidad:", df_libro.columns, key="vl")
        
        col_desc_b = st.selectbox("Descripción Banco (Para detalle):", df_banco.columns, key="db")
        
        if st.button("🔄 EJECUTAR CONCILIACIÓN"):
            # Procesamiento
            df_banco['Fecha_Dt'] = pd.to_datetime(df_banco[col_fecha_b])
            df_libro['Fecha_Dt'] = pd.to_datetime(df_libro[col_fecha_l])
            
            # Crear columnas de match
            df_banco['Conciliado'] = False
            df_libro['Conciliado'] = False
            df_banco['Match_ID'] = None
            
            matches = []
            
            # Algoritmo de Cruce
            st.write("🔍 Buscando coincidencias...")
            bar_prog = st.progress(0)
            total_items = len(df_banco)
            
            for idx_b, row_b in df_banco.iterrows():
                bar_prog.progress((idx_b + 1) / total_items)
                valor_b = row_b[col_valor_b]
                fecha_b = row_b['Fecha_Dt']
                
                # Buscar en libro: Mismo valor Y fecha dentro de +/- 3 días
                candidatos = df_libro[
                    (df_libro[col_valor_l] == valor_b) & 
                    (df_libro['Conciliado'] == False) &
                    (df_libro['Fecha_Dt'] >= (fecha_b - timedelta(days=3))) &
                    (df_libro['Fecha_Dt'] <= (fecha_b + timedelta(days=3)))
                ]
                
                if not candidatos.empty:
                    # Encontramos match! (Tomamos el primero por simplicidad)
                    idx_l = candidatos.index[0]
                    df_banco.at[idx_b, 'Conciliado'] = True
                    df_libro.at[idx_l, 'Conciliado'] = True
                    matches.append({
                        "Fecha Banco": row_b[col_fecha_b],
                        "Descripción": row_b[col_desc_b],
                        "Valor": valor_b,
                        "Estado": "✅ CRUZADO"
                    })
            
            # Separar Partidas Conciliatorias
            pendientes_banco = df_banco[df_banco['Conciliado'] == False]
            pendientes_libro = df_libro[df_libro['Conciliado'] == False]
            
            # --- RESULTADOS ---
            st.success(f"Proceso Terminado. Se cruzaron {len(matches)} partidas automáticamente.")
            
            tab1, tab2, tab3 = st.tabs(["✅ Cruzados", "⚠️ Pendientes en Banco", "⚠️ Pendientes en Libros"])
            
            with tab1:
                st.dataframe(pd.DataFrame(matches))
            
            with tab2:
                st.warning("Estas partidas están en el BANCO pero NO en Contabilidad (Posibles Notas Débito/Crédito faltantes):")
                st.dataframe(pendientes_banco[[col_fecha_b, col_desc_b, col_valor_b]])
            
            with tab3:
                st.warning("Estas partidas están en CONTABILIDAD pero NO en el Banco (Posibles Cheques no cobrados):")
                st.dataframe(pendientes_libro[[col_fecha_l, col_valor_l]])
                
            # Descarga Informe
            output_concil = io.BytesIO()
            with pd.ExcelWriter(output_concil, engine='xlsxwriter') as writer:
                pd.DataFrame(matches).to_excel(writer, sheet_name='Cruzados', index=False)
                pendientes_banco.to_excel(writer, sheet_name='Pendientes_Banco', index=False)
                pendientes_libro.to_excel(writer, sheet_name='Pendientes_Libro', index=False)
                
            st.download_button("📥 Descargar Informe de Conciliación", output_concil.getvalue(), "Conciliacion_Bancaria.xlsx")


# ------------------------------------------------------------------------------
# MÓDULO: LECTOR XML
# ------------------------------------------------------------------------------
elif menu == "📧 Lector XML (Facturación)":
    st.header("📧 Extractor Masivo XML")
    st.markdown("""<div class='instruccion-box'><h4>💡 ¿Para qué sirve?</h4><p>Extrae datos de Facturación Electrónica (XML) a Excel en segundos.</p></div>""", unsafe_allow_html=True)
    archivos_xml = st.file_uploader("Arrastra XMLs (Máx 5GB)", type=['xml'], accept_multiple_files=True)
    if archivos_xml and st.button("🚀 PROCESAR"):
        datos_xml = []
        bar = st.progress(0)
        for i, f in enumerate(archivos_xml):
            bar.progress((i+1)/len(archivos_xml))
            datos_xml.append(parsear_xml_dian(f))
        df_xml = pd.DataFrame(datos_xml)
        st.dataframe(df_xml)
        out = io.BytesIO()
        with pd.ExcelWriter(out, engine='xlsxwriter') as w: df_xml.to_excel(w, index=False)
        st.download_button("📥 Descargar Excel", out.getvalue(), "Resumen_XML.xlsx")

# ------------------------------------------------------------------------------
# MÓDULO: TESORERÍA
# ------------------------------------------------------------------------------
elif menu == "💰 Tesorería & Flujo de Caja":
    st.header("💰 Radar de Liquidez")
    st.markdown("""<div class='instruccion-box'><h4>💡 ¿Para qué sirve?</h4><p>Proyecta tu flujo de caja cruzando CxC vs CxP.</p></div>""", unsafe_allow_html=True)
    saldo_hoy = st.number_input("💵 Saldo Hoy:", min_value=0.0, format="%.2f")
    c1, c2 = st.columns(2)
    fcxc = c1.file_uploader("CxC (.xlsx)", type=['xlsx'])
    fcxp = c2.file_uploader("CxP (.xlsx)", type=['xlsx'])
    if fcxc and fcxp:
        dcxc = pd.read_excel(fcxc); dcxp = pd.read_excel(fcxp)
        c1, c2, c3, c4 = st.columns(4)
        cfc = c1.selectbox("Fecha CxC:", dcxc.columns); cvc = c2.selectbox("Valor CxC:", dcxc.columns)
        cfp = c3.selectbox("Fecha CxP:", dcxp.columns); cvp = c4.selectbox("Valor CxP:", dcxp.columns)
        if st.button("PROYECTAR"):
            try:
                dcxc['Fecha'] = pd.to_datetime(dcxc[cfc]); dcxp['Fecha'] = pd.to_datetime(dcxp[cfp])
                fi = dcxc.groupby('Fecha')[cvc].sum().reset_index(); fe = dcxp.groupby('Fecha')[cvp].sum().reset_index()
                cal = pd.merge(fi, fe, on='Fecha', how='outer').fillna(0)
                cal.columns = ['Fecha', 'Ing', 'Egr']; cal = cal.sort_values('Fecha')
                cal['Saldo'] = saldo_hoy + (cal['Ing'] - cal['Egr']).cumsum()
                st.line_chart(cal.set_index('Fecha')['Saldo'])
                st.dataframe(cal)
            except: st.error("Error en fechas")

# ------------------------------------------------------------------------------
# MÓDULO: VALIDADOR DE RUT
# ------------------------------------------------------------------------------
elif menu == "🔍 Validador de RUT (Real)":
    st.header("🔍 Validación de RUT")
    st.markdown("""<div class='instruccion-box'><h4>💡 Herramienta Profesional</h4><p>Calcula el DV Real y te lleva a la DIAN para verificar estado.</p></div>""", unsafe_allow_html=True)
    nit = st.text_input("NIT (Sin DV):", max_chars=15)
    if st.button("CALCULAR") and nit:
        dv = calcular_dv_colombia(nit)
        st.markdown(f"<div class='rut-card'><h2>NIT: {nit}-{dv}</h2></div>", unsafe_allow_html=True)
        st.link_button("🔗 Verificar en DIAN", "https://muisca.dian.gov.co/WebRutMuisca/DefConsultaEstadoRUT.faces")

# ------------------------------------------------------------------------------
# MÓDULO: AUDITORÍA GASTOS
# ------------------------------------------------------------------------------
elif menu == "📂 Auditoría Masiva de Gastos":
    st.header("📂 Auditoría Fiscal")
    st.markdown("""<div class='instruccion-box'><h4>💡 ¿Para qué sirve?</h4><p>Detecta errores 771-5 y retenciones en tu auxiliar.</p></div>""", unsafe_allow_html=True)
    ar = st.file_uploader("Auxiliar (.xlsx)", type=['xlsx'])
    if ar:
        df = pd.read_excel(ar)
        c1, c2, c3, c4 = st.columns(4)
        cf, ct, cc, cv = c1.selectbox("F", df.columns), c2.selectbox("T", df.columns), c3.selectbox("C", df.columns), c4.selectbox("V", df.columns)
        cm = st.selectbox("M", ["No"]+list(df.columns))
        if st.button("AUDITAR"):
            res = []
            for r in df.to_dict('records'):
                met = r[cm] if cm != "No" else "Efectivo"
                h, rs = analizar_gasto_fila(r, cv, cf, cc)
                v = float(r[cv]) if pd.notnull(r[cv]) else 0
                txt, rv = [], "BAJO"
                if "efectivo" in str(met).lower() and v > TOPE_EFECTIVO: txt.append("RECHAZO 771-5"); rv="ALTO"
                if v >= BASE_RET_SERVICIOS: txt.append("Verif. Retención"); rv="MEDIO" if rv=="BAJO" else rv
                res.append({"Fila": r[cf], "Val": v, "Riesgo": rv, "Nota": " ".join(txt)})
            st.dataframe(pd.DataFrame(res))

# ------------------------------------------------------------------------------
# MÓDULO: UGPP
# ------------------------------------------------------------------------------
elif menu == "👥 Escáner de Nómina (UGPP)":
    st.header("👥 Escáner UGPP")
    st.markdown("""<div class='instruccion-box'><h4>💡 ¿Para qué sirve?</h4><p>Detecta excesos del 40% en pagos no salariales (Ley 1393).</p></div>""", unsafe_allow_html=True)
    an = st.file_uploader("Nómina (.xlsx)", type=['xlsx'])
    if an:
        dn = pd.read_excel(an)
        c1, c2, c3 = st.columns(3)
        cn, cs, cns = c1.selectbox("N", dn.columns), c2.selectbox("S", dn.columns), c3.selectbox("NS", dn.columns)
        if st.button("AUDITAR"):
            res = []
            for r in dn.to_dict('records'):
                ibc, exc, est, msg = calcular_ugpp_fila(r, cs, cns)
                res.append({"Emp": r[cn], "Exc": exc, "Est": est})
            st.dataframe(pd.DataFrame(res))

# ------------------------------------------------------------------------------
# MÓDULO: COSTOS
# ------------------------------------------------------------------------------
elif menu == "💰 Calculadora Costos (Masiva)":
    st.header("💰 Costos Nómina")
    st.markdown("""<div class='instruccion-box'><h4>💡 ¿Para qué sirve?</h4><p>Calcula costo real empresa (Prestaciones + Seg. Social).</p></div>""", unsafe_allow_html=True)
    ac = st.file_uploader("Personal (.xlsx)", type=['xlsx'])
    if ac:
        dc = pd.read_excel(ac)
        c1, c2, c3, c4 = st.columns(4)
        cn, cs, ca, car = c1.selectbox("N", dc.columns), c2.selectbox("S", dc.columns), c3.selectbox("Au", dc.columns), c4.selectbox("ARL", dc.columns)
        ce = st.selectbox("Exo", dc.columns)
        if st.button("CALCULAR"):
            rc = []
            for r in dc.to_dict('records'):
                c, cr = calcular_costo_empresa_fila(r, cs, ca, car, ce)
                rc.append({"Emp": r[cn], "Tot": c})
            st.dataframe(pd.DataFrame(rc))

# ------------------------------------------------------------------------------
# MÓDULO: OCR
# ------------------------------------------------------------------------------
elif menu == "📸 Digitalización (OCR)":
    st.header("📸 OCR Facturas")
    st.markdown("""<div class='instruccion-box'><h4>💡 ¿Para qué sirve?</h4><p>Extrae datos de fotos de facturas a Excel.</p></div>""", unsafe_allow_html=True)
    af = st.file_uploader("Fotos", type=["jpg", "png"], accept_multiple_files=True)
    if af and st.button("PROCESAR") and api_key:
        do = []
        bar = st.progress(0)
        for i, f in enumerate(af):
            bar.progress((i+1)/len(af)); info = ocr_factura(Image.open(f))
            if info: do.append(info)
        st.dataframe(pd.DataFrame(do))

# ------------------------------------------------------------------------------
# MÓDULO: ANALÍTICA
# ------------------------------------------------------------------------------
elif menu == "📊 Analítica Financiera":
    st.header("📊 Analítica IA")
    st.markdown("""<div class='instruccion-box'><h4>💡 ¿Para qué sirve?</h4><p>Diagnóstico financiero automático con IA.</p></div>""", unsafe_allow_html=True)
    fi = st.file_uploader("Financieros", type=['xlsx', 'csv'])
    if fi and api_key:
        df = pd.read_csv(fi) if fi.name.endswith('.csv') else pd.read_excel(fi)
        cd, cv = st.selectbox("Desc", df.columns), st.selectbox("Val", df.columns)
        if st.button("ANALIZAR"):
            res = df.groupby(cd)[cv].sum().sort_values(ascending=False).head(10)
            st.bar_chart(res)
            st.markdown(consultar_ia_gemini(f"Analiza: {res.to_string()}"))

# ==============================================================================
# PIE DE PÁGINA
# ==============================================================================
st.markdown("---")
st.markdown("<center>Desarrollado para Contadores 4.0 | Bucaramanga, Colombia</center>", unsafe_allow_html=True)
