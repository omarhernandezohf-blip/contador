import streamlit as st
import pandas as pd
import google.generativeai as genai
from PIL import Image
import json
import time
import io

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
    .riesgo-alto { color: #dc3545; font-weight: bold; }
    .riesgo-medio { color: #ffc107; font-weight: bold; }
    .ok { color: #198754; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

# ==============================================================================
# 2. CONSTANTES FISCALES 2025 (Parametrización)
# ==============================================================================
# Estos valores se usan para los cálculos automáticos
SMMLV_2025 = 1430000
AUX_TRANS_2025 = 175000
UVT_2025 = 49799
TOPE_EFECTIVO = 100 * UVT_2025  # Art 771-5 E.T.
BASE_RET_SERVICIOS = 4 * UVT_2025
BASE_RET_COMPRAS = 27 * UVT_2025

# ==============================================================================
# 3. LÓGICA DE NEGOCIO (EL MOTOR CONTABLE)
# ==============================================================================

def analizar_gasto_fila(row, col_valor, col_metodo, col_concepto):
    """Analiza una sola fila del Excel de gastos aplicando reglas tributarias."""
    hallazgos = []
    riesgo = "BAJO"
    valor = float(row[col_valor]) if pd.notnull(row[col_valor]) else 0
    metodo = str(row[col_metodo]) if pd.notnull(row[col_metodo]) else ""
    
    # Regla 1: Bancarización (Art 771-5)
    if 'efectivo' in metodo.lower() and valor > TOPE_EFECTIVO:
        hallazgos.append(f"⛔ RECHAZO FISCAL: Pago en efectivo (${valor:,.0f}) supera tope individual.")
        riesgo = "ALTO"
    
    # Regla 2: Retenciones (Simplificada para masivos)
    # Nota: Para ser exactos necesitaríamos el histórico, pero esto alerta operaciones grandes únicas.
    if valor >= BASE_RET_SERVICIOS and valor < BASE_RET_COMPRAS:
        hallazgos.append("⚠️ ALERTA: Verificar si se practicó Retención (Base Servicios superada).")
        if riesgo == "BAJO": riesgo = "MEDIO"
    elif valor >= BASE_RET_COMPRAS:
        hallazgos.append("⚠️ ALERTA: Verificar Retención (Base Compras superada).")
        if riesgo == "BAJO": riesgo = "MEDIO"

    return " | ".join(hallazgos) if hallazgos else "OK", riesgo

def calcular_ugpp_fila(row, col_salario, col_no_salarial):
    """Calcula la regla del 40% (Ley 1393) fila por fila."""
    salario = float(row[col_salario]) if pd.notnull(row[col_salario]) else 0
    no_salarial = float(row[col_no_salarial]) if pd.notnull(row[col_no_salarial]) else 0
    
    total_ingresos = salario + no_salarial
    limite_40 = total_ingresos * 0.40
    
    if no_salarial > limite_40:
        exceso = no_salarial - limite_40
        ibc_ajustado = salario + exceso
        return ibc_ajustado, exceso, "RIESGO ALTO", f"Excede límite por ${exceso:,.0f}"
    else:
        return salario, 0, "OK", "Cumple norma"

def calcular_costo_empresa_fila(row, col_salario, col_aux, col_arl, col_exo):
    """Calcula el costo total empresa fila por fila."""
    salario = float(row[col_salario])
    tiene_aux = str(row[col_aux]).strip().lower() in ['si', 's', 'true', '1', 'yes']
    nivel_arl = int(row[col_arl]) if pd.notnull(row[col_arl]) else 1
    es_exonerado = str(row[col_exo]).strip().lower() in ['si', 's', 'true', '1', 'yes']
    
    # Bases
    aux_trans = AUX_TRANS_2025 if tiene_aux else 0
    ibc = salario
    base_prestaciones = salario + aux_trans
    
    # Aportes Patrono
    salud = 0 if es_exonerado else ibc * 0.085
    pension = ibc * 0.12
    arl_tabla = {1:0.00522, 2:0.01044, 3:0.02436, 4:0.0435, 5:0.0696}
    arl_val = ibc * arl_tabla.get(nivel_arl, 0.00522)
    parafiscales = ibc * 0.04 # Caja (SENA/ICBF exonerados generalmente si salud lo está)
    if not es_exonerado: parafiscales += ibc * 0.05
    
    # Provisiones
    prestaciones = base_prestaciones * 0.2183 # Cesantías+Int+Prima+Vac
    
    total_costo = base_prestaciones + salud + pension + arl_val + parafiscales + prestaciones
    return total_costo, (total_costo - base_prestaciones)

# --- FUNCIONES IA ---
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
        prompt = """
        Extrae los datos contables de esta imagen en formato JSON estricto:
        {"fecha": "YYYY-MM-DD", "nit": "sin digito", "proveedor": "texto", "concepto": "texto", "base": numero, "iva": numero, "total": numero}
        """
        response = model.generate_content([prompt, imagen])
        return json.loads(response.text.replace("```json", "").replace("```", "").strip())
    except:
        return None

# ==============================================================================
# 4. BARRA LATERAL (CONFIGURACIÓN)
# ==============================================================================
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/9320/9320399.png", width=80)
    st.title("Suite Contable IA")
    st.markdown("---")
    
    menu = st.radio("Selecciona Herramienta:", 
                    ["📂 Auditoría Masiva de Gastos", 
                     "👥 Escáner de Nómina (UGPP)", 
                     "💰 Calculadora Costos (Masiva)",
                     "📸 Digitalización (OCR)",
                     "📊 Analítica Financiera"])
    
    st.markdown("---")
    with st.expander("🔑 Activar Inteligencia Artificial"):
        st.info("Pega tu API Key de Google aquí para habilitar las funciones de razonamiento y lectura de facturas.")
        api_key = st.text_input("API Key:", type="password")
        if api_key: genai.configure(api_key=api_key)

# ==============================================================================
# 5. PESTAÑAS Y FUNCIONALIDADES
# ==============================================================================

# ------------------------------------------------------------------------------
# MÓDULO 1: AUDITORÍA MASIVA DE GASTOS
# ------------------------------------------------------------------------------
if menu == "📂 Auditoría Masiva de Gastos":
    st.header("📂 Auditoría Fiscal Masiva")
    
    # Explicación Colega
    st.info("""
    **¿Para qué sirve esta pestaña?**
    Colega, no revises el auxiliar línea por línea.
    1. Descarga el auxiliar de gastos de tu software (Siigo, Alegra, etc.) en Excel.
    2. Súbelo aquí.
    3. El sistema buscará errores de **Bancarización, Topes y Retenciones** en segundos.
    4. Además, la IA analizará los conceptos para advertirte de gastos "raros" o no deducibles.
    """)
    
    archivo = st.file_uploader("Cargar Auxiliar (.xlsx)", type=['xlsx'])
    
    if archivo:
        df = pd.read_excel(archivo)
        st.write("### 1. Mapeo de Columnas")
        st.caption("Ayúdame a entender tu archivo. Selecciona qué columna corresponde a cada dato:")
        
        c1, c2, c3, c4 = st.columns(4)
        col_fecha = c1.selectbox("Fecha:", df.columns)
        col_tercero = c2.selectbox("Nombre Tercero:", df.columns)
        col_concepto = c3.selectbox("Concepto/Detalle:", df.columns)
        col_valor = c4.selectbox("Valor Gasto:", df.columns)
        col_metodo = st.selectbox("Forma de Pago (Opcional - Si no tienes, asume Efectivo):", ["No disponible"] + list(df.columns))
        
        if st.button("🔍 INICIAR AUDITORÍA AUTOMÁTICA"):
            # 1. Auditoría Matemática (Python - Rápida)
            st.write("🔄 Ejecutando validaciones matemáticas...")
            barra = st.progress(0)
            
            resultados = []
            for idx, row in df.iterrows():
                barra.progress((idx + 1) / len(df))
                
                # Definir método de pago
                metodo_val = row[col_metodo] if col_metodo != "No disponible" else "Efectivo"
                
                hallazgo, nivel_riesgo = analizar_gasto_fila(row, col_valor, col_fecha, col_concepto) # Usando lógica interna
                
                # Usamos la lógica local re-escrita aquí para tener acceso a variables locales del loop
                hallazgo_texto = []
                riesgo_val = "BAJO"
                val = float(row[col_valor]) if pd.notnull(row[col_valor]) else 0
                
                # Regla Topes Efectivo
                if "efectivo" in str(metodo_val).lower() and val > TOPE_EFECTIVO:
                    hallazgo_texto.append("RECHAZO 771-5 (Efectivo)")
                    riesgo_val = "ALTO"
                
                # Regla Base Retención
                if val >= BASE_RET_SERVICIOS:
                    hallazgo_texto.append("Revisar Retención")
                    if riesgo_val == "BAJO": riesgo_val = "MEDIO"
                
                resultados.append({
                    "Fila Excel": idx + 2,
                    "Fecha": row[col_fecha],
                    "Tercero": row[col_tercero],
                    "Concepto": row[col_concepto],
                    "Valor": val,
                    "Dictamen IA": " Pendiente", # Se llena si se activa
                    "Hallazgos": " | ".join(hallazgo_texto) if hallazgo_texto else "OK",
                    "Nivel Riesgo": riesgo_val
                })
            
            df_res = pd.DataFrame(resultados)
            
            # 2. Auditoría Cualitativa (IA - Opcional)
            if api_key:
                st.write("🧠 La IA está analizando los conceptos sospechosos...")
                # Agrupamos para no saturar: Tomamos los conceptos de mayor valor
                conceptos_top = df.groupby(col_concepto)[col_valor].sum().sort_values(ascending=False).head(10)
                resumen_conceptos = conceptos_top.to_string()
                
                prompt = f"""
                Analiza estos conceptos de gasto de una empresa en Colombia.
                Indica cuáles podrían ser NO DEDUCIBLES o RIESGOSOS (ej: gastos personales, suntuarios, sin relación de causalidad).
                
                Datos:
                {resumen_conceptos}
                """
                analisis_ia = consultar_ia_gemini(prompt)
                st.info("### 🧠 Opinión del Auditor IA sobre tus Gastos:")
                st.markdown(analisis_ia)
            
            # Mostrar tabla
            st.write("### 📋 Resultados Detallados")
            
            def color_riesgo(val):
                color = '#ffcccc' if 'ALTO' in str(val) else ('#fff3cd' if 'MEDIO' in str(val) else '#d1e7dd')
                return f'background-color: {color}'
            
            st.dataframe(df_res.style.applymap(color_riesgo, subset=['Nivel Riesgo']), use_container_width=True)
            
            # Descarga
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df_res.to_excel(writer, index=False)
            st.download_button("📥 Descargar Papel de Trabajo", output.getvalue(), "Auditoria_Gastos.xlsx")

# ------------------------------------------------------------------------------
# MÓDULO 2: ESCÁNER DE NÓMINA (UGPP)
# ------------------------------------------------------------------------------
elif menu == "👥 Escáner de Nómina (UGPP)":
    st.header("👥 Escáner Masivo Anti-UGPP")
    
    st.info("""
    **¿Cómo funciona?**
    La UGPP nos fiscaliza masivamente, nosotros debemos auditarnos masivamente también.
    1. Sube un Excel con la lista de tus empleados.
    2. Debe tener columnas: Nombre, Salario Básico, Total Pagos NO Salariales (Bonos, Rodamientos, etc).
    3. El sistema aplicará la **Ley 1393 (Regla del 40%)** a cada uno y te dirá cuánto debes ajustar en la PILA.
    """)
    
    archivo_nom = st.file_uploader("Cargar Nómina (.xlsx)", type=['xlsx'])
    
    if archivo_nom:
        df_nom = pd.read_excel(archivo_nom)
        st.write("### Mapeo de Columnas")
        c1, c2, c3 = st.columns(3)
        col_nom = c1.selectbox("Nombre Empleado:", df_nom.columns)
        col_sal = c2.selectbox("Salario Básico:", df_nom.columns)
        col_nosal = c3.selectbox("Total NO Salarial:", df_nom.columns)
        
        if st.button("👮‍♀️ AUDITAR NÓMINA COMPLETA"):
            resultados_ugpp = []
            riesgo_total = 0
            
            for idx, row in df_nom.iterrows():
                ibc_real, exceso, estado, msg = calcular_ugpp_fila(row, col_sal, col_nosal)
                
                if estado == "RIESGO ALTO":
                    riesgo_total += exceso
                
                resultados_ugpp.append({
                    "Empleado": row[col_nom],
                    "Salario": row[col_sal],
                    "No Salarial": row[col_nosal],
                    "Estado": estado,
                    "Exceso a Reportar": exceso,
                    "IBC Correcto PILA": ibc_real
                })
            
            df_ugpp = pd.DataFrame(resultados_ugpp)
            
            # Métricas Globales
            m1, m2 = st.columns(2)
            m1.metric("Empleados Analizados", len(df_ugpp))
            m2.metric("Riesgo Total de Omisión (Base)", f"${riesgo_total:,.0f}", delta_color="inverse")
            
            if riesgo_total > 0:
                st.error(f"🚨 ATENCIÓN: Tienes una omisión de base de cotización de ${riesgo_total:,.0f}. Si la UGPP te visita, pagarás esto + sanciones e intereses.")
            else:
                st.success("✅ ¡Felicitaciones! Tu nómina está blindada contra la UGPP.")
            
            st.dataframe(df_ugpp)

# ------------------------------------------------------------------------------
# MÓDULO 3: CALCULADORA COSTOS (MASIVA)
# ------------------------------------------------------------------------------
elif menu == "💰 Calculadora Costos (Masiva)":
    st.header("💰 Presupuesto de Nómina Real")
    
    st.info("""
    **Calcula el costo real de TODA tu empresa.**
    Sube un Excel con tu planta de personal. El sistema calculará automáticamente:
    * Seguridad Social (Patrono)
    * Parafiscales
    * Provisiones (Cesantías, Primas, Vacaciones)
    * Costo Total Mensual
    """)
    
    archivo_costos = st.file_uploader("Cargar Planta Personal (.xlsx)", type=['xlsx'])
    
    if archivo_costos:
        df_costos = pd.read_excel(archivo_costos)
        st.write("### Configuración")
        
        c1, c2, c3, c4 = st.columns(4)
        col_nom_c = c1.selectbox("Empleado:", df_costos.columns)
        col_sal_c = c2.selectbox("Salario:", df_costos.columns)
        col_aux_c = c3.selectbox("¿Tiene Aux Trans? (Columna SI/NO):", df_costos.columns)
        col_arl_c = c4.selectbox("Nivel Riesgo ARL (1-5):", df_costos.columns)
        col_exo_c = st.selectbox("¿Empresa Exonerada? (Columna SI/NO):", df_costos.columns, help="Columna que diga SI o NO para cada empleado")
        
        if st.button("🧮 CALCULAR COSTO TOTAL EMPRESA"):
            res_costos = []
            total_nomina = 0
            
            for idx, row in df_costos.iterrows():
                costo, carga = calcular_costo_empresa_fila(row, col_sal_c, col_aux_c, col_arl_c, col_exo_c)
                total_nomina += costo
                res_costos.append({
                    "Empleado": row[col_nom_c],
                    "Salario Básico": row[col_sal_c],
                    "Carga Prestacional (Oculta)": carga,
                    "Costo Total Mensual": costo
                })
            
            df_fin = pd.DataFrame(res_costos)
            
            st.markdown(f"""
            <div class='reporte-box'>
                <h2 style='text-align: center;'>Costo Total Mensual de la Nómina</h2>
                <h1 style='text-align: center; color: #0d6efd;'>${total_nomina:,.0f}</h1>
                <p style='text-align: center;'>Esto es lo que debes tener en el banco cada mes para no descapitalizarte.</p>
            </div>
            """, unsafe_allow_html=True)
            
            st.write("### Desglose por Empleado")
            st.dataframe(df_fin)
            
            # Exportar
            out_cost = io.BytesIO()
            with pd.ExcelWriter(out_cost, engine='xlsxwriter') as w:
                df_fin.to_excel(w, index=False)
            st.download_button("📥 Descargar Presupuesto", out_cost.getvalue(), "Costo_Nomina_Total.xlsx")

# ------------------------------------------------------------------------------
# MÓDULO 4: DIGITALIZACIÓN (OCR)
# ------------------------------------------------------------------------------
elif menu == "📸 Digitalización (OCR)":
    st.header("📸 De Papel a Excel")
    st.info("Sube fotos de facturas físicas. La IA extraerá los datos y te permitirá descargar un Excel masivo.")
    
    archivos = st.file_uploader("Cargar Fotos", type=["jpg", "png", "jpeg"], accept_multiple_files=True)
    
    if archivos and st.button("🚀 PROCESAR IMÁGENES") and api_key:
        datos_ocr = []
        barra_ocr = st.progress(0)
        
        for i, img_file in enumerate(archivos):
            barra_ocr.progress((i+1)/len(archivos))
            info = ocr_factura(Image.open(img_file))
            if info:
                info['Archivo Origen'] = img_file.name
                datos_ocr.append(info)
        
        if datos_ocr:
            df_ocr = pd.DataFrame(datos_ocr)
            st.success("Lectura completada.")
            st.data_editor(df_ocr)
            
            out_ocr = io.BytesIO()
            with pd.ExcelWriter(out_ocr, engine='xlsxwriter') as w:
                df_ocr.to_excel(w, index=False)
            st.download_button("📥 Descargar Excel", out_ocr.getvalue(), "Facturas_Leidas.xlsx")

# ------------------------------------------------------------------------------
# MÓDULO 5: ANALÍTICA FINANCIERA
# ------------------------------------------------------------------------------
elif menu == "📊 Analítica Financiera":
    st.header("📊 Tablero de Control Inteligente")
    st.info("Sube tu Balance de Comprobación o Libro Diario. La IA te dará un diagnóstico de la salud financiera.")
    
    archivo_fin = st.file_uploader("Cargar Datos Financieros (.csv / .xlsx)", type=['csv', 'xlsx'])
    
    if archivo_fin and api_key:
        if archivo_fin.name.endswith('.csv'): df_fin = pd.read_csv(archivo_fin)
        else: df_fin = pd.read_excel(archivo_fin)
        
        st.write("Vista Previa:", df_fin.head())
        col_desc = st.selectbox("Columna Descripción:", df_fin.columns)
        col_val_fin = st.selectbox("Columna Valor:", df_fin.columns)
        
        if st.button("🤖 ANALIZAR CON IA"):
            # Resumimos datos para la IA
            resumen = df_fin.groupby(col_desc)[col_val_fin].sum().sort_values(ascending=False).head(15)
            st.bar_chart(resumen)
            
            prompt_fin = f"""
            Actúa como Asesor Financiero. Analiza estos movimientos contables principales de mi cliente:
            {resumen.to_string()}
            
            Dame 3 conclusiones financieras y 2 alertas tributarias si ves algo raro.
            """
            
            with st.spinner("La IA está pensando..."):
                analisis = consultar_ia_gemini(prompt_fin)
                st.markdown("### 🧠 Diagnóstico Financiero:")
                st.markdown(analisis)

# ==============================================================================
# PIE DE PÁGINA
# ==============================================================================
st.markdown("---")
st.markdown("<center>Desarrollado para Contadores 4.0 | Bucaramanga, Colombia</center>", unsafe_allow_html=True)
