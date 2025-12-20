import streamlit as st
import pandas as pd
import google.generativeai as genai
from PIL import Image
import json
import time
import io

# ==============================================================================
# 1. CONFIGURACIÓN VISUAL
# ==============================================================================
st.set_page_config(page_title="Suite Contable IA 2025", page_icon="📊", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #f4f6f9; }
    h1, h2 { color: #0f2c4a; } 
    .stButton>button {
        height: 3em;
        background-color: #0d6efd; 
        color: white; 
        border-radius: 8px;
        font-weight: bold;
    }
    .stButton>button:hover { background-color: #0b5ed7; }
    .metric-card {
        background-color: white;
        padding: 15px;
        border-radius: 10px;
        border-left: 5px solid #0d6efd;
        box-shadow: 0 2px 5px rgba(0,0,0,0.1);
    }
    </style>
    """, unsafe_allow_html=True)

# ==============================================================================
# 2. BASE DE DATOS Y CONSTANTES
# ==============================================================================
if 'historial_pagos' not in st.session_state:
    st.session_state.historial_pagos = pd.DataFrame({
        'nit': ['900123456', '88222333', '1098765432'],
        'nombre': ['Suministros SAS', 'Pedro Pintor (Régimen Simple)', 'María Contadora'],
        'acumulado_mes': [0.0, 3500000.0, 150000.0],
        'responsable_iva': [True, False, False]
    })

# Cifras Fiscales 2025 (Estimadas)
SMMLV_2025 = 1430000
AUX_TRANS_2025 = 175000
UVT_2025 = 49799
TOPE_EFECTIVO = 100 * UVT_2025
BASE_RETENCION = 4 * UVT_2025

# ==============================================================================
# 3. LÓGICA & CEREBRO (IA + REGLAS)
# ==============================================================================

# --- A. Lógica de Reglas (Auditoría Puntual) ---
def auditar_reglas_negocio(nit, valor, metodo_pago):
    alertas = []
    if metodo_pago == 'Efectivo' and valor > TOPE_EFECTIVO:
        alertas.append(f"🔴 **PELIGRO (Art. 771-5):** Pago en efectivo supera el tope fiscal.")
    tercero = st.session_state.historial_pagos[st.session_state.historial_pagos['nit'] == nit]
    if not tercero.empty:
        acumulado = tercero['acumulado_mes'].values[0]
        if acumulado < BASE_RETENCION and (acumulado + valor) >= BASE_RETENCION:
            alertas.append(f"🔔 **RETENCIÓN:** Acumulado mensual supera base ({BASE_RETENCION:,.0f}).")
    return alertas

def auditar_nomina_ugpp(salario, no_salariales):
    total = salario + no_salariales
    limite = total * 0.40
    if no_salariales > limite:
        return salario + (no_salariales - limite), (no_salariales - limite), "⚠️ Excede 40%", "Riesgo"
    return salario, 0, "✅ OK", "Seguro"

def calcular_liquidacion_mensual(salario, aux_trans, riesgo, exonerado):
    base_prest = salario + (AUX_TRANS_2025 if aux_trans else 0)
    ibc = salario
    
    # Empleado
    ded_salud = ibc * 0.04
    ded_pen = ibc * 0.04
    fsp = ibc * 0.01 if salario >= (4*SMMLV_2025) else 0
    neto = base_prest - (ded_salud + ded_pen + fsp)
    
    # Empresa
    salud_pat = 0 if exonerado else ibc * 0.085
    sena_icbf = 0 if exonerado else ibc * 0.05
    pen_pat = ibc * 0.12
    caja = ibc * 0.04
    tabla_arl = {1:0.00522, 2:0.01044, 3:0.02436, 4:0.0435, 5:0.0696}
    arl = ibc * tabla_arl.get(riesgo, 0.00522)
    prestaciones = base_prest * 0.2183 # Cesantias+Int+Prima+Vac
    
    costo_total = base_prest + salud_pat + sena_icbf + pen_pat + caja + arl + prestaciones
    
    return {"empleado": {"neto": neto, "deducciones": ded_salud+ded_pen+fsp}, 
            "empresa": {"total": costo_total, "carga": costo_total-base_prest}}

# --- B. Lógica de IA (Gemini) ---
def consultar_ia_general(prompt_texto):
    try:
        model = genai.GenerativeModel('models/gemini-1.5-flash')
        response = model.generate_content(prompt_texto)
        return response.text
    except:
        return "Error de conexión con la IA."

def procesar_ocr(imagen):
    try:
        model = genai.GenerativeModel('models/gemini-1.5-flash')
        prompt = 'Extrae datos JSON: {"fecha":"YYYY-MM-DD", "nit":"num", "proveedor":"txt", "base":num, "iva":num, "total":num}'
        res = model.generate_content([prompt, imagen])
        return json.loads(res.text.replace("```json","").replace("```","").strip())
    except:
        return None

# ==============================================================================
# 4. INTERFAZ (SIDEBAR)
# ==============================================================================
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/9320/9320399.png", width=70)
    st.title("Suite Contable")
    
    menu = st.radio("Herramientas:", 
        ["📊 Analítica de Archivos (Nuevo)", 
         "📸 OCR Facturas", 
         "🛡️ Auditoría Puntual", 
         "👥 Nómina & UGPP",
         "🧮 Costos Laborales"])
    
    st.divider()
    with st.expander("🔑 Configuración IA"):
        api_key = st.text_input("API Key Google:", type="password")
        if api_key: genai.configure(api_key=api_key)

# ==============================================================================
# 5. MÓDULOS
# ==============================================================================

# --- MÓDULO NUEVO: ANALÍTICA DE ARCHIVOS (SIIGO/ALEGRA) ---
if menu == "📊 Analítica de Archivos (Nuevo)":
    st.header("📊 Inteligencia de Negocios para Contadores")
    st.info("""
    **Instrucciones:**
    1. Descarga un auxiliar de gastos o movimiento contable de tu software (Excel/CSV).
    2. Súbelo aquí.
    3. La IA analizará tendencias, riesgos tributarios y anomalías.
    """)
    
    uploaded_file = st.file_uploader("Cargar Archivo del Software (.xlsx, .csv)", type=['xlsx', 'csv'])
    
    if uploaded_file:
        try:
            # 1. Cargar Data
            if uploaded_file.name.endswith('.csv'):
                df = pd.read_csv(uploaded_file)
            else:
                df = pd.read_excel(uploaded_file)
            
            st.write("### 1. Vista Previa de Datos")
            st.dataframe(df.head(5))
            
            # 2. Mapeo de Columnas (Para que funcione con cualquier software)
            st.write("### 2. Configuración de Columnas")
            col1, col2, col3 = st.columns(3)
            col_detalle = col1.selectbox("Columna Concepto/Detalle:", df.columns)
            col_valor = col2.selectbox("Columna Valor/Saldo:", df.columns)
            col_fecha = col3.selectbox("Columna Fecha:", df.columns)
            
            # 3. Dashboard Automático
            st.write("### 3. Análisis Preliminar")
            
            # Agrupación por concepto
            gastos_por_concepto = df.groupby(col_detalle)[col_valor].sum().sort_values(ascending=False).head(10)
            
            c_dash1, c_dash2 = st.columns(2)
            with c_dash1:
                st.subheader("Top 10 Conceptos (Gasto/Ingreso)")
                st.bar_chart(gastos_por_concepto)
            
            with c_dash2:
                total_movimiento = df[col_valor].sum()
                st.metric("Total Movimiento Analizado", f"${total_movimiento:,.0f}")
                st.caption("Validar si coincide con el total del auxiliar.")

            # 4. Auditoría IA Profunda
            st.divider()
            st.subheader("🧠 Dictamen de Inteligencia Artificial")
            
            if st.button("🤖 Generar Informe de Auditoría"):
                if not api_key:
                    st.error("Necesitas la API Key para el análisis inteligente.")
                else:
                    with st.spinner("La IA está analizando los patrones contables..."):
                        # Preparamos un resumen para no saturar la IA con miles de filas
                        resumen_texto = gastos_por_concepto.to_string()
                        
                        prompt_analisis = f"""
                        Actúa como Auditor Fiscal Experto en Colombia.
                        Te doy un resumen de los movimientos contables de una empresa (Top 10 conceptos por valor):
                        
                        {resumen_texto}
                        
                        Por favor genera un informe corto que incluya:
                        1. Análisis de la estructura de gastos/ingresos.
                        2. Banderas rojas o riesgos tributarios evidentes según norma colombiana (ej: gastos no deducibles por concepto).
                        3. Recomendaciones para el cierre contable.
                        
                        Usa formato profesional con viñetas.
                        """
                        
                        analisis = consultar_ia_general(prompt_analisis)
                        st.markdown(analisis)
                        
        except Exception as e:
            st.error(f"Error leyendo el archivo: {e}")

# --- MÓDULO OCR ---
elif menu == "📸 OCR Facturas":
    st.header("📸 Digitalización")
    files = st.file_uploader("Fotos Facturas", type=["jpg","png"], accept_multiple_files=True)
    if files and st.button("Procesar") and api_key:
        res = []
        bar = st.progress(0)
        for i, f in enumerate(files):
            bar.progress((i+1)/len(files))
            d = procesar_ocr(Image.open(f))
            if d: res.append(d)
        st.data_editor(pd.DataFrame(res))

# --- MÓDULO AUDITORÍA PUNTUAL ---
elif menu == "🛡️ Auditoría Puntual":
    st.header("🛡️ Auditoría Rápida")
    t1, t2 = st.tabs(["Reglas", "Consulta IA"])
    with t1:
        nit = st.selectbox("Tercero", st.session_state.historial_pagos['nit'])
        val = st.number_input("Valor", step=50000)
        met = st.selectbox("Método", ["Transferencia", "Efectivo"])
        if st.button("Validar"):
            err = auditar_reglas_negocio(nit, val, met)
            if not err: st.success("Limpio")
            else: 
                for e in err: st.error(e)
    with t2:
        q = st.text_input("Duda Gasto:")
        if st.button("Consultar") and api_key:
            prompt = f"Como auditor CO, es deducible: {q}?"
            st.write(consultar_ia_general(prompt))

# --- MÓDULO UGPP ---
elif menu == "👥 Nómina & UGPP":
    st.header("👮‍♀️ Escudo UGPP")
    s = st.number_input("Salario", 1300000.0)
    ns = st.number_input("No Salarial", 0.0)
    if st.button("Calcular 40%"):
        ibc, exc, msg, est = auditar_nomina_ugpp(s, ns)
        if est == "Riesgo": st.error(f"{msg} - Ajuste PILA: ${exc:,.0f}")
        else: st.success(msg)

# --- MÓDULO COSTOS LABORALES ---
elif menu == "🧮 Costos Laborales":
    st.header("🧮 Calculadora Costo Empresa")
    c1, c2 = st.columns(2)
    with c1:
        sb = st.number_input("Básico", value=float(SMMLV_2025))
        at = st.checkbox("Aux Trans", True)
        rl = st.selectbox("Riesgo ARL", [1,2,3,4,5])
        exo = st.checkbox("Exonerado (Ley 1607)", True)
    with c2:
        if st.button("Calcular"):
            r = calcular_liquidacion_mensual(sb, at, rl, exo)
            st.metric("Neto Empleado", f"${r['empleado']['neto']:,.0f}")
            st.metric("Costo Total Empresa", f"${r['empresa']['total']:,.0f}")
            st.warning(f"Carga Prestacional: ${r['empresa']['carga']:,.0f}")

st.markdown("---")
st.caption("Suite Contable Pro v4.0 | Bucaramanga 2025")
