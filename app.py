import streamlit as st
import pandas as pd
import google.generativeai as genai
from PIL import Image
import json
import time
import io
from datetime import datetime, timedelta
import xml.etree.ElementTree as ET # Nueva librería para leer XML

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
    
    /* --- CORRECCIÓN DE VISIBILIDAD DE TEXTO --- */
    .instruccion-box {
        background-color: #e2e3e5; 
        color: #212529 !important; /* Texto oscuro forzado */
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
    """Calcula el DV según el algoritmo oficial de la DIAN (Módulo 11). Matemática Real."""
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

# --- NUEVA FUNCIÓN: PARSER DE XML DIAN (UBL 2.1) ---
def parsear_xml_dian(archivo_xml):
    """Extrae datos clave de Facturación Electrónica Colombia"""
    try:
        tree = ET.parse(archivo_xml)
        root = tree.getroot()
        
        # Namespaces comunes en DIAN
        ns = {
            'cac': 'urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2',
            'cbc': 'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2'
        }
        
        # Función auxiliar para buscar con seguridad
        def get_text(path, root_elem=root):
            elem = root_elem.find(path, ns)
            return elem.text if elem is not None else ""

        # Extracción de Datos
        data = {}
        data['Archivo'] = archivo_xml.name
        data['Prefijo'] = get_text('.//cbc:ID')
        data['Fecha Emision'] = get_text('.//cbc:IssueDate')
        
        # Emisor
        emisor = root.find('.//cac:AccountingSupplierParty', ns)
        if emisor:
            data['NIT Emisor'] = get_text('.//cbc:CompanyID', emisor.find('.//cac:PartyTaxScheme', ns))
            data['Emisor'] = get_text('.//cbc:RegistrationName', emisor.find('.//cac:PartyTaxScheme', ns))
            
        # Receptor
        receptor = root.find('.//cac:AccountingCustomerParty', ns)
        if receptor:
            data['NIT Receptor'] = get_text('.//cbc:CompanyID', receptor.find('.//cac:PartyTaxScheme', ns))
            data['Receptor'] = get_text('.//cbc:RegistrationName', receptor.find('.//cac:PartyTaxScheme', ns))

        # Totales
        monetary = root.find('.//cac:LegalMonetaryTotal', ns)
        if monetary:
            data['Total a Pagar'] = float(get_text('cbc:PayableAmount', monetary) or 0)
            data['Base Imponible'] = float(get_text('cbc:LineExtensionAmount', monetary) or 0)
            data['Total Impuestos'] = float(get_text('cbc:TaxInclusiveAmount', monetary) or 0) - data['Base Imponible']

        return data
    except Exception as e:
        return {"Archivo": archivo_xml.name, "Error": "No es un XML Válido o Estructura Desconocida"}

# ==============================================================================
# 4. BARRA LATERAL
# ==============================================================================
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/9320/9320399.png", width=80)
    st.title("Suite Contable IA")
    st.markdown("---")
    
    menu = st.radio("Herramientas:", 
                    ["📧 Lector XML (Facturación)", # <-- NUEVA HERRAMIENTA
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
# MÓDULO NUEVO: LECTOR MASIVO XML
# ------------------------------------------------------------------------------
if menu == "📧 Lector XML (Facturación)":
    st.header("📧 Extractor Masivo de Facturas Electrónicas (XML)")
    
    st.markdown("""
    <div class='instruccion-box'>
        <h4>💡 ¿Para qué sirve esta herramienta?</h4>
        <p>Los contadores perdemos horas digitando facturas mirando el PDF, pero la <strong>verdad legal</strong> está en el XML. Esta herramienta:</p>
        <ol>
            <li>Recibe cientos de archivos <strong>.XML</strong> (Facturas de Venta o Compra).</li>
            <li>Extrae automáticamente: NITs, Fechas, Bases, IVAs y Totales.</li>
            <li>Genera un <strong>Excel plano</strong> listo para importar a tu software contable.</li>
        </ol>
    </div>
    """, unsafe_allow_html=True)
    
    archivos_xml = st.file_uploader("Arrastra tus archivos XML aquí (Máx 5GB)", type=['xml'], accept_multiple_files=True)
    
    if archivos_xml and st.button("🚀 PROCESAR XMLs"):
        datos_xml = []
        barra_xml = st.progress(0)
        
        for i, archivo in enumerate(archivos_xml):
            barra_xml.progress((i+1)/len(archivos_xml))
            # Procesar
            info = parsear_xml_dian(archivo)
            datos_xml.append(info)
            
        if datos_xml:
            df_xml = pd.DataFrame(datos_xml)
            
            # Reordenar columnas para que se vea ordenado
            cols_orden = ['Fecha Emision', 'Prefijo', 'NIT Emisor', 'Emisor', 'NIT Receptor', 'Base Imponible', 'Total Impuestos', 'Total a Pagar', 'Archivo']
            # Filtramos solo las que existen en el df
            cols_finales = [c for c in cols_orden if c in df_xml.columns]
            df_xml = df_xml[cols_finales]
            
            st.success(f"✅ Se procesaron {len(archivos_xml)} facturas exitosamente.")
            st.dataframe(df_xml)
            
            # Descarga
            out_xml = io.BytesIO()
            with pd.ExcelWriter(out_xml, engine='xlsxwriter') as writer:
                df_xml.to_excel(writer, index=False)
                
            st.download_button("📥 Descargar Resumen en Excel", out_xml.getvalue(), "Resumen_Facturacion_XML.xlsx")

# ------------------------------------------------------------------------------
# MÓDULO: TESORERÍA & FLUJO DE CAJA
# ------------------------------------------------------------------------------
elif menu == "💰 Tesorería & Flujo de Caja":
    st.header("💰 Radar de Liquidez y Flujo de Caja 360°")
    
    st.markdown("""
    <div class='instruccion-box'>
        <h4>💡 ¿Para qué sirve esta herramienta?</h4>
        <p>Esta herramienta evita que la empresa se quede sin efectivo (liquidez). Cruza lo que tienes que pagar (Proveedores) vs. lo que vas a cobrar (Clientes) y te muestra en qué fecha exacta podrías quedarte en rojo.</p>
    </div>
    """, unsafe_allow_html=True)
    
    saldo_hoy = st.number_input("💵 Saldo Disponible en Bancos HOY ($):", min_value=0.0, step=100000.0, format="%.2f")
    col_up1, col_up2 = st.columns(2)
    with col_up1:
        st.subheader("📥 Cuentas por Cobrar (Cartera)")
        file_cxc = st.file_uploader("Subir Excel CxC", type=['xlsx'])
    with col_up2:
        st.subheader("📤 Cuentas por Pagar (Proveedores)")
        file_cxp = st.file_uploader("Subir Excel CxP", type=['xlsx'])
        
    if file_cxc and file_cxp:
        df_cxc = pd.read_excel(file_cxc)
        df_cxp = pd.read_excel(file_cxp)
        st.write("---")
        st.subheader("⚙️ Configuración de Columnas")
        c1, c2, c3, c4 = st.columns(4)
        col_fecha_cxc = c1.selectbox("Fecha Vencimiento (CxC):", df_cxc.columns, key="f_cxc")
        col_valor_cxc = c2.selectbox("Valor a Cobrar:", df_cxc.columns, key="v_cxc")
        col_fecha_cxp = c3.selectbox("Fecha Vencimiento (CxP):", df_cxp.columns, key="f_cxp")
        col_valor_cxp = c4.selectbox("Valor a Pagar:", df_cxp.columns, key="v_cxp")
        
        if st.button("🚀 PROYECTAR FLUJO DE CAJA"):
            try:
                df_cxc['Fecha'] = pd.to_datetime(df_cxc[col_fecha_cxc])
                df_cxp['Fecha'] = pd.to_datetime(df_cxp[col_fecha_cxp])
                flujo_ingresos = df_cxc.groupby('Fecha')[col_valor_cxc].sum().reset_index()
                flujo_egresos = df_cxp.groupby('Fecha')[col_valor_cxp].sum().reset_index()
                calendario = pd.merge(flujo_ingresos, flujo_egresos, on='Fecha', how='outer').fillna(0)
                calendario.columns = ['Fecha', 'Ingresos', 'Egresos']
                calendario = calendario.sort_values('Fecha')
                calendario['Flujo Neto'] = calendario['Ingresos'] - calendario['Egresos']
                calendario['Saldo Proyectado'] = saldo_hoy + calendario['Flujo Neto'].cumsum()
                
                st.subheader("📈 Proyección de Liquidez (Próximos 30 días)")
                st.line_chart(calendario.set_index('Fecha')['Saldo Proyectado'])
                
                minimo_saldo = calendario['Saldo Proyectado'].min()
                fecha_quiebre = calendario[calendario['Saldo Proyectado'] < 0]['Fecha'].min()
                
                m1, m2, m3 = st.columns(3)
                m1.metric("Ingresos Proyectados", f"${calendario['Ingresos'].sum():,.0f}")
                m2.metric("Egresos Proyectados", f"${calendario['Egresos'].sum():,.0f}")
                if minimo_saldo < 0:
                    m3.markdown(f"<div class='metric-box-red'>🚨 DÉFICIT DETECTADO<br>Fecha Crítica: {fecha_quiebre.date()}</div>", unsafe_allow_html=True)
                else:
                    m3.markdown(f"<div class='metric-box-green'>✅ FLUJO SALUDABLE<br>No hay quiebre proyectado</div>", unsafe_allow_html=True)
                
                with st.expander("Ver Detalle Diario"):
                    st.dataframe(calendario.style.format({"Ingresos": "${:,.0f}", "Egresos": "${:,.0f}", "Saldo Proyectado": "${:,.0f}"}))
                
                if api_key:
                    st.write("---")
                    st.subheader("🧠 Estrategia de Tesorería (IA)")
                    resumen_flujo = calendario.head(15).to_string()
                    prompt_tesoreria = f"""Actúa como Gerente Financiero. Analiza flujo. Saldo Ini: ${saldo_hoy:,.0f}. Datos: {resumen_flujo}. ¿Riesgos? Sugerencias."""
                    with st.spinner("Analizando..."):
                        st.markdown(consultar_ia_gemini(prompt_tesoreria))
            except Exception as e:
                st.error(f"Error: {e}")

# ------------------------------------------------------------------------------
# MÓDULO: VALIDADOR DE RUT (CORREGIDO - DATOS REALES)
# ------------------------------------------------------------------------------
elif menu == "🔍 Validador de RUT (Real)":
    st.header("🔍 Validación de RUT y DV")
    
    st.markdown("""
    <div class='instruccion-box'>
        <h4>💡 Herramienta Profesional</h4>
        <p><strong>1. Cálculo Matemático (Exacto):</strong> Obtenemos el Dígito de Verificación (DV) usando el algoritmo oficial de la DIAN (Módulo 11).</p>
        <p><strong>2. Verificación de Estado (Oficial):</strong> Para confirmar si el RUT está "Activo" o "Suspendido", facilitamos el acceso directo a la base de datos pública del MUISCA.</p>
    </div>
    """, unsafe_allow_html=True)

    col_input, col_btn = st.columns([3, 1])
    nit_busqueda = col_input.text_input("Ingrese NIT o Cédula (Sin DV):", max_chars=15)
    
    if col_btn.button("🔢 CALCULAR DV") and nit_busqueda:
        dv_calculado = calcular_dv_colombia(nit_busqueda)
        st.subheader("📋 Resultado del Cálculo")
        st.markdown(f"""
        <div class='rut-card'>
            <h2 style='color: #0d6efd; margin:0;'>NIT: {nit_busqueda} - {dv_calculado}</h2>
            <p style='color: #333;'>El Dígito de Verificación correcto es: <strong>{dv_calculado}</strong></p>
        </div>
        """, unsafe_allow_html=True)
        st.markdown("---")
        st.write("### 🌍 Verificación Oficial en la DIAN")
        st.link_button("🔗 Consultar Estado en la DIAN (Sitio Oficial)", "https://muisca.dian.gov.co/WebRutMuisca/DefConsultaEstadoRUT.faces")

# ------------------------------------------------------------------------------
# MÓDULO: AUDITORÍA MASIVA DE GASTOS
# ------------------------------------------------------------------------------
elif menu == "📂 Auditoría Masiva de Gastos":
    st.header("📂 Auditoría Fiscal Masiva")
    
    st.markdown("""
    <div class='instruccion-box'>
        <h4>💡 ¿Para qué sirve esta herramienta?</h4>
        <p>Es un auditor robot que revisa miles de filas en segundos. Detecta errores tributarios graves.</p>
    </div>
    """, unsafe_allow_html=True)

    archivo = st.file_uploader("Cargar Auxiliar (.xlsx) - Soporta hasta 5GB", type=['xlsx'])
    if archivo:
        df = pd.read_excel(archivo)
        c1, c2, c3, c4 = st.columns(4)
        col_fecha = c1.selectbox("Fecha:", df.columns)
        col_tercero = c2.selectbox("Tercero:", df.columns)
        col_concepto = c3.selectbox("Concepto:", df.columns)
        col_valor = c4.selectbox("Valor:", df.columns)
        col_metodo = st.selectbox("Método:", ["No disponible"] + list(df.columns))
        
        if st.button("🔍 AUDITAR"):
            res = []
            bar = st.progress(0)
            for i, r in enumerate(df.to_dict('records')):
                bar.progress((i+1)/len(df))
                met = r[col_metodo] if col_metodo != "No disponible" else "Efectivo"
                hallazgo, riesgo = analizar_gasto_fila(r, col_valor, col_fecha, col_concepto)
                val = float(r[col_valor]) if pd.notnull(r[col_valor]) else 0
                txt, r_val = [], "BAJO"
                if "efectivo" in str(met).lower() and val > TOPE_EFECTIVO:
                    txt.append("RECHAZO 771-5"); r_val = "ALTO"
                if val >= BASE_RET_SERVICIOS:
                    txt.append("Verificar Retención"); r_val = "MEDIO" if r_val == "BAJO" else r_val
                res.append({"Fila": i+2, "Valor": val, "Riesgo": r_val, "Nota": " | ".join(txt) if txt else "OK"})
            
            df_r = pd.DataFrame(res)
            def color(v): return f'background-color: {"#ffcccc" if "ALTO" in str(v) else "#d1e7dd"}'
            st.dataframe(df_r.style.applymap(color, subset=['Riesgo']))

# ------------------------------------------------------------------------------
# MÓDULO: ESCÁNER UGPP
# ------------------------------------------------------------------------------
elif menu == "👥 Escáner de Nómina (UGPP)":
    st.header("👥 Escáner Anti-UGPP")
    
    st.markdown("""
    <div class='instruccion-box'>
        <h4>💡 ¿Para qué sirve esta herramienta?</h4>
        <p>La UGPP fiscaliza agresivamente los pagos <strong>"No Salariales"</strong>. La Ley 1393 dice que estos no pueden superar el 40% del total ganado.</p>
    </div>
    """, unsafe_allow_html=True)

    archivo_nom = st.file_uploader("Cargar Nómina (.xlsx) - Soporta hasta 5GB", type=['xlsx'])
    if archivo_nom:
        df_n = pd.read_excel(archivo_nom)
        c1, c2, c3 = st.columns(3)
        cn = c1.selectbox("Nombre:", df_n.columns)
        cs = c2.selectbox("Salario:", df_n.columns)
        cns = c3.selectbox("No Salarial:", df_n.columns)
        if st.button("AUDITAR"):
            res = []
            for r in df_n.to_dict('records'):
                ibc, exc, est, msg = calcular_ugpp_fila(r, cs, cns)
                res.append({"Empleado": r[cn], "Exceso": exc, "Estado": est})
            st.dataframe(pd.DataFrame(res))

# ------------------------------------------------------------------------------
# MÓDULO: CALCULADORA COSTOS
# ------------------------------------------------------------------------------
elif menu == "💰 Calculadora Costos (Masiva)":
    st.header("💰 Costos de Nómina")
    
    st.markdown("""
    <div class='instruccion-box'>
        <h4>💡 ¿Para qué sirve esta herramienta?</h4>
        <p>Calcula el <strong>COSTO REAL</strong> para la empresa incluyendo: Seguridad Social del Empleador, Parafiscales y Prestaciones Sociales.</p>
    </div>
    """, unsafe_allow_html=True)

    ac = st.file_uploader("Cargar Personal (.xlsx) - Soporta hasta 5GB", type=['xlsx'])
    if ac:
        dc = pd.read_excel(ac)
        c1, c2, c3, c4 = st.columns(4)
        cn = c1.selectbox("Empleado:", dc.columns)
        cs = c2.selectbox("Salario:", dc.columns)
        ca = c3.selectbox("Aux Trans (SI/NO):", dc.columns)
        carl = c4.selectbox("ARL (1-5):", dc.columns)
        cex = st.selectbox("Exonerado (SI/NO):", dc.columns)
        if st.button("CALCULAR"):
            rc = []
            for r in dc.to_dict('records'):
                c, car = calcular_costo_empresa_fila(r, cs, ca, carl, cex)
                rc.append({"Empleado": r[cn], "Costo Total": c})
            st.dataframe(pd.DataFrame(rc))

# ------------------------------------------------------------------------------
# MÓDULO: OCR FACTURAS
# ------------------------------------------------------------------------------
elif menu == "📸 Digitalización (OCR)":
    st.header("📸 OCR Facturas")
    
    st.markdown("""
    <div class='instruccion-box'>
        <h4>💡 ¿Para qué sirve esta herramienta?</h4>
        <p>Sube una foto (JPG/PNG) de una factura física y la IA extraerá los datos (Fecha, NIT, Totales) a Excel.</p>
    </div>
    """, unsafe_allow_html=True)

    af = st.file_uploader("Fotos - Soporta hasta 5GB", type=["jpg", "png"], accept_multiple_files=True)
    if af and st.button("PROCESAR") and api_key:
        do = []
        bar = st.progress(0)
        for i, f in enumerate(af):
            bar.progress((i+1)/len(af))
            info = ocr_factura(Image.open(f))
            if info: do.append(info)
        st.data_editor(pd.DataFrame(do))

# ------------------------------------------------------------------------------
# MÓDULO: ANALÍTICA
# ------------------------------------------------------------------------------
elif menu == "📊 Analítica Financiera":
    st.header("📊 Analítica IA")
    
    st.markdown("""
    <div class='instruccion-box'>
        <h4>💡 ¿Para qué sirve esta herramienta?</h4>
        <p>Sube un Balance de Comprobación y la IA analizará los movimientos para darte un resumen ejecutivo.</p>
    </div>
    """, unsafe_allow_html=True)

    fi = st.file_uploader("Datos Financieros - Soporta hasta 5GB", type=['xlsx', 'csv'])
    if fi and api_key:
        dfi = pd.read_csv(fi) if fi.name.endswith('.csv') else pd.read_excel(fi)
        cd = st.selectbox("Descripción:", dfi.columns)
        cv = st.selectbox("Valor:", dfi.columns)
        if st.button("ANALIZAR"):
            res = dfi.groupby(cd)[cv].sum().sort_values(ascending=False).head(10)
            st.bar_chart(res)
            st.markdown(consultar_ia_gemini(f"Analiza saldos: {res.to_string()}"))

# ==============================================================================
# PIE DE PÁGINA
# ==============================================================================
st.markdown("---")
st.markdown("<center>Desarrollado para Contadores 4.0 | Bucaramanga, Colombia</center>", unsafe_allow_html=True)
