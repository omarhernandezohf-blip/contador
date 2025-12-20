import streamlit as st
import pandas as pd
import google.generativeai as genai
from PIL import Image
import json
import time
import io

# ==============================================================================
# 1. CONFIGURACIÓN VISUAL (ESTÉTICA DE OFICINA CONTABLE)
# ==============================================================================
st.set_page_config(page_title="Asistente Contable 2025", page_icon="📈", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #f0f2f6; }
    h1 { color: #1f77b4; }
    h2, h3 { color: #444; }
    .stAlert { border-radius: 8px; }
    .stButton>button {
        height: 3em;
        font-weight: bold;
        border-radius: 8px;
        background-color: #2c3e50; 
        color: white;
    }
    .stButton>button:hover { background-color: #34495e; color: #ecf0f1; }
    /* Estilo para tarjetas de resultados */
    .metric-container {
        background-color: #ffffff;
        padding: 15px;
        border-radius: 10px;
        border-left: 5px solid #1f77b4;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    </style>
    """, unsafe_allow_html=True)

# ==============================================================================
# 2. BASE DE DATOS Y CONSTANTES (SIMULACIÓN 2025)
# ==============================================================================
if 'historial_pagos' not in st.session_state:
    st.session_state.historial_pagos = pd.DataFrame({
        'nit': ['900123456', '88222333', '1098765432'],
        'nombre': ['Suministros SAS', 'Pedro Pintor (Régimen Simple)', 'María Contadora'],
        'acumulado_mes': [0.0, 3500000.0, 150000.0],
        'responsable_iva': [True, False, False]
    })

# Cifras Fiscales (Colombia - Proyección 2025)
SMMLV_2025 = 1430000        # Salario Mínimo Estimado
AUX_TRANS_2025 = 175000     # Auxilio Transporte Estimado
UVT_2025 = 49799
TOPE_EFECTIVO = 100 * UVT_2025
BASE_RETENCION = 4 * UVT_2025

# ==============================================================================
# 3. FUNCIONES LÓGICAS (EL CEREBRO DE LA APP)
# ==============================================================================

# --- A. Lógica Anterior (Auditoría y UGPP) ---
def auditar_reglas_negocio(nit, valor, metodo_pago):
    alertas = []
    if metodo_pago == 'Efectivo' and valor > TOPE_EFECTIVO:
        alertas.append(f"🔴 **PELIGRO (Art. 771-5):** Pago en efectivo de ${valor:,.0f} supera tope individual.")
    tercero = st.session_state.historial_pagos[st.session_state.historial_pagos['nit'] == nit]
    if not tercero.empty:
        acumulado = tercero['acumulado_mes'].values[0]
        if acumulado < BASE_RETENCION and (acumulado + valor) >= BASE_RETENCION:
            alertas.append(f"🔔 **OJO RETENCIÓN:** Acumulado del mes (${acumulado:,.0f}) + este pago supera la base.")
    return alertas

def auditar_nomina_ugpp(salario, no_salariales):
    total_ingresos = salario + no_salariales
    limite_40 = total_ingresos * 0.40
    if no_salariales > limite_40:
        exceso = no_salariales - limite_40
        return salario + exceso, exceso, "⚠️ CUIDADO: Te pasaste del 40%", "Riesgo"
    return salario, 0, "✅ Todo en orden: No excede el 40%", "Seguro"

def consultar_ia_dian(concepto, valor):
    try:
        model = genai.GenerativeModel('models/gemini-1.5-flash')
        prompt = f"""Actúa como Contador Tributarista en Colombia. Analiza: "{concepto}" valor ${valor}. Responde JSON: {{"veredicto": "DEDUCIBLE/RIESGOSO", "explicacion": "breve", "cuenta": "PUC"}}"""
        response = model.generate_content(prompt)
        return json.loads(response.text.replace("```json", "").replace("```", "").strip())
    except:
        return {"veredicto": "ERROR", "explicacion": "Sin conexión IA", "cuenta": "N/A"}

def procesar_factura_ocr(image):
    try:
        model = genai.GenerativeModel('models/gemini-1.5-flash')
        prompt = """Extrae datos factura JSON: {"fecha": "YYYY-MM-DD", "nit": "num", "proveedor": "txt", "concepto": "txt", "base": num, "iva": num, "total": num}"""
        response = model.generate_content([prompt, image])
        return json.loads(response.text.replace("```json", "").replace("```", "").strip())
    except:
        return None

# --- B. NUEVA LÓGICA: CALCULADORA LABORAL COMPLETA ---
def calcular_liquidacion_mensual(salario, tiene_aux_trans, riesgo_arl, es_exonerado_1607):
    """Calcula Seguridad Social (Empresa/Empleado) y Parafiscales"""
    
    # 1. Definición de Bases
    aux_trans = AUX_TRANS_2025 if tiene_aux_trans and salario <= (2 * SMMLV_2025) else 0
    ibc = salario # El auxilio de transporte NO hace parte del IBC para seguridad social
    
    # 2. Deducciones al EMPLEADO
    salud_emp = ibc * 0.04
    pension_emp = ibc * 0.04
    fsp = 0
    if salario >= (4 * SMMLV_2025):
        fsp = ibc * 0.01 # Simplificado (1% solidaridad)

    total_deducciones_emp = salud_emp + pension_emp + fsp
    neto_pagar = salario + aux_trans - total_deducciones_emp

    # 3. Costos de la EMPRESA (Seguridad Social)
    # Ley 1607: Si es persona jurídica y devenga < 10 SMMLV, no paga Salud (8.5%) ni SENA/ICBF
    if es_exonerado_1607 and salario < (10 * SMMLV_2025):
        salud_patrono = 0
        sena = 0
        icbf = 0
    else:
        salud_patrono = ibc * 0.085
        sena = ibc * 0.02
        icbf = ibc * 0.03

    pension_patrono = ibc * 0.12
    caja_comp = ibc * 0.04
    
    # Tabla ARL (Riesgos Laborales)
    tabla_arl = {1: 0.00522, 2: 0.01044, 3: 0.02436, 4: 0.04350, 5: 0.06960}
    arl_valor = ibc * tabla_arl.get(riesgo_arl, 0.00522)

    # 4. Provisiones Prestacionales (Costo oculto mensual)
    # Base prestaciones incluye Aux Transporte
    base_prestaciones = salario + aux_trans
    cesantias = base_prestaciones * 0.0833
    int_cesantias = cesantias * 0.12
    prima = base_prestaciones * 0.0833
    vacaciones = salario * 0.0417 # Vacaciones es solo sobre salario

    total_costo_empresa = (salario + aux_trans + salud_patrono + pension_patrono + 
                           arl_valor + caja_comp + sena + icbf + 
                           cesantias + int_cesantias + prima + vacaciones)

    return {
        "empleado": {
            "salud": salud_emp, "pension": pension_emp, "fsp": fsp, "neto": neto_pagar, "aux_trans": aux_trans
        },
        "empresa": {
            "salud": salud_patrono, "pension": pension_patrono, "arl": arl_valor,
            "parafiscales": caja_comp + sena + icbf,
            "prestaciones": cesantias + int_cesantias + prima + vacaciones,
            "total_costo": total_costo_empresa
        }
    }

# ==============================================================================
# 4. BARRA LATERAL
# ==============================================================================
with st.sidebar:
    st.title("🗂️ Menú Principal")
    st.markdown("---")
    
    menu = st.radio("Herramientas:", 
                    ["📸 Digitalizar Facturas", 
                     "🛡️ Auditoría Fiscal", 
                     "👥 Revisar Nómina (UGPP)",
                     "🧮 Calculadora Laboral"]) # <--- NUEVA OPCIÓN
    
    st.markdown("---")
    with st.expander("🔐 Llave IA"):
        api_key = st.text_input("API Key Google:", type="password")
        if api_key: genai.configure(api_key=api_key)

# ==============================================================================
# 5. PANTALLAS PRINCIPALES
# ==============================================================================

if menu == "📸 Digitalizar Facturas":
    st.header("📸 Digitalización Automática")
    st.info("Sube fotos de facturas. La IA extraerá los datos a Excel.")
    archivos = st.file_uploader("Fotos (JPG/PNG)", type=["jpg", "png"], accept_multiple_files=True)
    if archivos and st.button("🚀 Extraer Datos"):
        if not api_key: st.error("Falta API Key")
        else:
            datos = []
            barra = st.progress(0)
            for i, a in enumerate(archivos):
                barra.progress((i+1)/len(archivos))
                info = procesar_factura_ocr(Image.open(a))
                if info: datos.append(info)
                time.sleep(1)
            st.data_editor(pd.DataFrame(datos))

elif menu == "🛡️ Auditoría Fiscal":
    st.header("🛡️ Auditoría Fiscal")
    t1, t2 = st.tabs(["✅ Reglas", "🧠 IA Consultor"])
    with t1:
        nit = st.selectbox("Tercero", st.session_state.historial_pagos['nit'])
        val = st.number_input("Valor", step=50000)
        met = st.selectbox("Método", ["Transferencia", "Efectivo"])
        if st.button("Validar"):
            err = auditar_reglas_negocio(nit, val, met)
            if not err: st.success("OK")
            else: 
                for e in err: st.error(e)
    with t2:
        q = st.text_input("Duda Gasto:")
        if st.button("Consultar") and api_key:
            st.write(consultar_ia_dian(q, 0))

elif menu == "👥 Revisar Nómina (UGPP)":
    st.header("👮‍♀️ Escudo UGPP (Ley 1393)")
    s = st.number_input("Salario", 1300000.0)
    ns = st.number_input("No Salarial", 0.0)
    if st.button("Calcular 40%"):
        ibc, exc, msg, est = auditar_nomina_ugpp(s, ns)
        if est == "Riesgo": st.error(f"{msg} - Exceso: ${exc:,.0f}")
        else: st.success(msg)

# --- NUEVO MÓDULO: CALCULADORA LABORAL ---
elif menu == "🧮 Calculadora Laboral":
    st.header("🧮 Calculadora de Costos Laborales (Colombia)")
    st.markdown("Calcula el **descuento real** al empleado y el **costo total** para la empresa (Carga prestacional).")

    col_input, col_res = st.columns([1, 1.5])

    with col_input:
        st.subheader("Datos del Contrato")
        salario_base = st.number_input("Salario Básico Mensual ($):", value=float(SMMLV_2025), step=50000.0)
        aux_trans_check = st.checkbox("¿Pagar Auxilio de Transporte?", value=True, help="Obligatorio si gana menos de 2 SMMLV")
        riesgo_arl = st.selectbox("Nivel de Riesgo ARL:", [1, 2, 3, 4, 5], index=0, help="1: Oficinas, 5: Construcción/Alturas")
        exonerado = st.checkbox("¿Exonerado Aportes (Ley 1607)?", value=True, help="Aplica para Personas Jurídicas con empleados < 10 SMMLV. No pagan Salud (8.5%) ni SENA/ICBF.")

        if st.button("💥 CALCULAR NÓMINA"):
            resultados = calcular_liquidacion_mensual(salario_base, aux_trans_check, riesgo_arl, exonerado)
            st.session_state['res_nomina'] = resultados

    with col_res:
        if 'res_nomina' in st.session_state:
            r = st.session_state['res_nomina']
            emp = r['empleado']
            pat = r['empresa']

            # Pestañas para ver los dos lados de la moneda
            tab_emp, tab_pat = st.tabs(["👤 Lado Empleado", "🏢 Lado Empresa"])

            with tab_emp:
                st.markdown("##### 💵 Lo que recibe el empleado")
                c1, c2, c3 = st.columns(3)
                c1.metric("Salario + Aux", f"${(salario_base + emp['aux_trans']):,.0f}")
                c2.metric("Deducción Salud", f"- ${emp['salud']:,.0f}")
                c3.metric("Deducción Pensión", f"- ${emp['pension']:,.0f}")
                
                if emp['fsp'] > 0:
                    st.warning(f"Fondo Solidaridad Pensional: - ${emp['fsp']:,.0f}")

                st.divider()
                st.markdown(f"""
                <div style="background-color: #d4edda; padding: 10px; border-radius: 10px; text-align: center;">
                    <h3 style="color: #155724; margin:0;">Neto a Pagar: ${emp['neto']:,.0f}</h3>
                </div>
                """, unsafe_allow_html=True)

            with tab_pat:
                st.markdown("##### 📉 Costo Real para la Empresa")
                st.caption("Esto es lo que realmente te cuesta tener al empleado cada mes (incluyendo provisiones).")
                
                # Gráfica simple de barras usando st.progress como barra visual
                st.write("**Seguridad Social (Salud, Pensión, ARL):**")
                ss_total = pat['salud'] + pat['pension'] + pat['arl']
                st.text(f"${ss_total:,.0f}")
                
                st.write("**Parafiscales (Caja, SENA, ICBF):**")
                st.text(f"${pat['parafiscales']:,.0f}")
                
                st.write("**Provisiones (Primas, Cesantías, Vacaciones):**")
                st.text(f"${pat['prestaciones']:,.0f}")

                st.divider()
                factor_carga = (pat['total_costo'] / salario_base) * 100 - 100
                st.markdown(f"""
                <div style="background-color: #f8d7da; padding: 10px; border-radius: 10px;">
                    <h3 style="color: #721c24; margin:0;">Costo Total Mensual: ${pat['total_costo']:,.0f}</h3>
                    <small>Factor de Carga Prestacional: +{factor_carga:.1f}% sobre el salario</small>
                </div>
                """, unsafe_allow_html=True)

# Pie de página
st.markdown("---")
st.caption("Suite Contable Pro | Bucaramanga 2025")
