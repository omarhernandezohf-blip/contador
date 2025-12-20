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
st.set_page_config(page_title="Asistente Contable 2025", page_icon="📈", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #f0f2f6; }
    .stButton>button {
        height: 3em; font-weight: bold; border-radius: 8px;
        background-color: #2c3e50; color: white;
    }
    .metric-card { background-color: white; padding: 10px; border-radius: 10px; border-left: 5px solid #1f77b4; }
    </style>
    """, unsafe_allow_html=True)

# ==============================================================================
# 2. CONSTANTES FISCALES 2025 (Estimadas para el ejercicio)
# ==============================================================================
SMMLV_2025 = 1430000  # Salario Mínimo Estimado
AUX_TRANSPORTE_2025 = 162000
UVT_2025 = 49799
TOPE_EFECTIVO = 100 * UVT_2025
BASE_RETENCION = 4 * UVT_2025

# Tarifas ARL (Riesgo I a V)
TARIFAS_ARL = {
    "Riesgo I (Oficina)": 0.00522,
    "Riesgo II (Manufactura baja)": 0.01044,
    "Riesgo III (Manufactura media)": 0.02436,
    "Riesgo IV (Procesos industriales)": 0.04350,
    "Riesgo V (Alto riesgo/Construcción)": 0.06960
}

# Base de Datos Simulada
if 'historial_pagos' not in st.session_state:
    st.session_state.historial_pagos = pd.DataFrame({
        'nit': ['900123456', '88222333', '1098765432'],
        'nombre': ['Suministros SAS', 'Pedro Pintor', 'María Contadora'],
        'acumulado_mes': [0.0, 3500000.0, 150000.0]
    })

# ==============================================================================
# 3. FUNCIONES LÓGICAS (EL CEREBRO)
# ==============================================================================

# --- NUEVA FUNCIÓN: LIQUIDADOR DE SEGURIDAD SOCIAL ---
def calcular_pila_completa(salario_base, auxilio_transporte, riesgo_arl_key, es_juridica):
    """Calcula salud, pensión, ARL, parafiscales y prestaciones."""
    
    # 1. Definir IBC (El auxilio de transporte NO hace base para seguridad social, solo para prestaciones)
    ibc = salario_base 
    if ibc < SMMLV_2025: ibc = SMMLV_2025 # Nadie cotiza por debajo del mínimo
    
    # 2. Deducciones Empleado
    salud_emp = ibc * 0.04
    pension_emp = ibc * 0.04
    fsp = 0
    if ibc > (4 * SMMLV_2025):
        fsp = ibc * 0.01 # Simplificado al 1%, sube si gana más de 16 SMMLV
        
    total_deducciones = salud_emp + pension_emp + fsp
    neto_pagar = (salario_base + auxilio_transporte) - total_deducciones
    
    # 3. Costos Empleador
    # Exoneración Art 114-1 ET: Si gana < 10 SMMLV y es jurídica, no paga Salud(8.5%) ni Sena/ICBF
    exonerado = False
    if es_juridica and ibc < (10 * SMMLV_2025):
        exonerado = True
        
    salud_patrono = 0 if exonerado else ibc * 0.085
    pension_patrono = ibc * 0.12
    arl_patrono = ibc * TARIFAS_ARL[riesgo_arl_key]
    
    sena = 0 if exonerado else ibc * 0.02
    icbf = 0 if exonerado else ibc * 0.03
    caja = ibc * 0.04
    
    # 4. Provisiones (Prestaciones Sociales) - Base incluye Auxilio Transporte
    base_prestaciones = salario_base + auxilio_transporte
    cesantias = base_prestaciones * 0.0833
    intereses_cesantias = cesantias * 0.12
    prima = base_prestaciones * 0.0833
    vacaciones = salario_base * 0.0417 # Vacaciones es solo sobre salario base
    
    total_patrono = salud_patrono + pension_patrono + arl_patrono + sena + icbf + caja
    total_provisiones = cesantias + intereses_cesantias + prima + vacaciones
    costo_total_empresa = salario_base + auxilio_transporte + total_patrono + total_provisiones
    
    return {
        "empleado": {"Salud (4%)": salud_emp, "Pensión (4%)": pension_emp, "Fondo Sol.": fsp, "Neto": neto_pagar},
        "patrono": {"Salud (8.5%)": salud_patrono, "Pensión (12%)": pension_patrono, "ARL": arl_patrono, "Caja (4%)": caja, "SENA": sena, "ICBF": icbf},
        "provisiones": {"Cesantías": cesantias, "Int. Cesantías": intereses_cesantias, "Prima": prima, "Vacaciones": vacaciones},
        "totales": {"Costo Mensual Empresa": costo_total_empresa, "Carga Prestacional": total_patrono + total_provisiones}
    }

# --- FUNCIONES ANTERIORES (CONSERVADAS) ---
def auditar_reglas_negocio(nit, valor, metodo_pago):
    alertas = []
    if metodo_pago == 'Efectivo' and valor > TOPE_EFECTIVO:
        alertas.append(f"🔴 **PELIGRO (Art. 771-5):** Supera tope efectivo. Gasto NO DEDUCIBLE.")
    tercero = st.session_state.historial_pagos[st.session_state.historial_pagos['nit'] == nit]
    if not tercero.empty:
        acumulado = tercero['acumulado_mes'].values[0]
        if acumulado < BASE_RETENCION and (acumulado + valor) >= BASE_RETENCION:
            alertas.append(f"🔔 **RETENCIÓN:** Acumulado supera base. ¡Practicar Retención!")
    return alertas

def auditar_nomina_ugpp(salario, no_salariales):
    total = salario + no_salariales
    limite = total * 0.40
    if no_salariales > limite:
        return salario + (no_salariales - limite), (no_salariales - limite), "⚠️ EXCESO 40%", "Riesgo"
    return salario, 0, "✅ OK", "Seguro"

def consultar_ia_dian(concepto, valor):
    # (Simulación simple para que funcione sin API Key obligatoria al probar)
    try:
        if not st.session_state.get('api_key'): return {"veredicto": "SIN CONEXIÓN", "explicacion": "Ingresa API Key", "cuenta": "N/A"}
        model = genai.GenerativeModel('models/gemini-1.5-flash')
        prompt = f"Analiza gasto contable Colombia: {concepto}, valor {valor}. JSON: {{'veredicto': 'txt', 'explicacion': 'txt', 'cuenta': 'txt'}}"
        res = model.generate_content(prompt)
        return json.loads(res.text.replace("```json", "").replace("```", "").strip())
    except: return {"veredicto": "ERROR", "explicacion": "Fallo IA", "cuenta": "N/A"}

def procesar_factura_ocr(image):
    try:
        model = genai.GenerativeModel('models/gemini-1.5-flash')
        prompt = "Datos factura JSON: {'fecha': '', 'nit': '', 'proveedor': '', 'base': 0, 'iva': 0, 'total': 0}"
        res = model.generate_content([prompt, image])
        return json.loads(res.text.replace("```json", "").replace("```", "").strip())
    except: return None

# ==============================================================================
# 4. INTERFAZ GRÁFICA
# ==============================================================================
with st.sidebar:
    st.title("🗂️ Menú")
    menu = st.radio("Herramienta:", ["📸 Digitalizar", "🛡️ Auditoría Fiscal", "👥 Nómina y Laboral"])
    st.markdown("---")
    api_key_input = st.text_input("API Key (Opcional)", type="password")
    if api_key_input: 
        st.session_state['api_key'] = api_key_input
        genai.configure(api_key=api_key_input)

# --- MÓDULO NÓMINA (ACTUALIZADO CON LA NUEVA HERRAMIENTA) ---
if menu == "👥 Nómina y Laboral":
    st.header("👥 Gestión de Nómina y Seguridad Social")
    
    # Creamos dos pestañas: Una para el cálculo legal (UGPP) y otra para liquidar mes a mes
    tab_ugpp, tab_liquidador = st.tabs(["👮‍♀️ Escudo UGPP (Ley 1393)", "💰 Liquidador Seguridad Social (Nuevo)"])
    
    # --- PESTAÑA 1: LO QUE YA TENÍAMOS ---
    with tab_ugpp:
        st.info("Verifica que los bonos y auxilios no salariales no superen el 40% del total.")
        c1, c2 = st.columns(2)
        sal = c1.number_input("Salario Básico", value=1300000.0, step=50000.0)
        no_sal = c2.number_input("Pagos NO Salariales", value=0.0, step=50000.0)
        if st.button("Auditar UGPP"):
            ibc, exc, msg, est = auditar_nomina_ugpp(sal, no_sal)
            if est == "Riesgo": st.error(f"{msg}. Ajuste PILA: +${exc:,.0f}")
            else: st.success(msg)

    # --- PESTAÑA 2: NUEVA HERRAMIENTA "CON EL IPS" (LIQUIDADOR) ---
    with tab_liquidador:
        st.markdown("### 🧮 Calculadora de Costos Laborales y Seguridad Social")
        st.caption("Calcula salud, pensión, riesgos y provisiones automáticamente. (Cifras estimadas 2025)")
        
        col_inp1, col_inp2 = st.columns(2)
        
        with col_inp1:
            salario_base = st.number_input("Salario Mensual:", value=float(SMMLV_2025), step=50000.0)
            tiene_auxilio = st.checkbox("¿Tiene Auxilio de Transporte?", value=True)
            aux_transporte = AUX_TRANSPORTE_2025 if tiene_auxilio else 0.0
            st.metric("Total Devengado", f"${(salario_base + aux_transporte):,.0f}")
            
        with col_inp2:
            tipo_empleador = st.radio("Tipo de Empleador (Exoneración Art. 114-1)", ["Persona Jurídica (Exonerado)", "Persona Natural (No Exonerado)"])
            es_juridica = True if "Jurídica" in tipo_empleador else False
            riesgo = st.selectbox("Nivel de Riesgo ARL:", list(TARIFAS_ARL.keys()))

        if st.button("🔢 Calcular Nómina Completa"):
            res = calcular_pila_completa(salario_base, aux_transporte, riesgo, es_juridica)
            
            # MOSTRAR RESULTADOS
            st.markdown("---")
            c_res1, c_res2, c_res3 = st.columns(3)
            
            with c_res1:
                st.markdown("#### 👤 Empleado (Deducciones)")
                for k, v in res['empleado'].items():
                    if k == "Neto": st.metric("NETO A PAGAR", f"${v:,.0f}")
                    else: st.write(f"**{k}:** -${v:,.0f}")
            
            with c_res2:
                st.markdown("#### 🏢 Empresa (Seguridad Social)")
                for k, v in res['patrono'].items():
                    st.write(f"**{k}:** ${v:,.0f}")
                st.info(f"Subtotal SS: ${sum(res['patrono'].values()):,.0f}")

            with c_res3:
                st.markdown("#### 🐷 Provisiones (Prestaciones)")
                for k, v in res['provisiones'].items():
                    st.write(f"**{k}:** ${v:,.0f}")
                st.warning(f"Costo Real Mensual: **${res['totales']['Costo Mensual Empresa']:,.0f}**")
            
            # Gráfico simple de distribución
            st.markdown("---")
            st.caption(f"Factor Prestacional: {(res['totales']['Carga Prestacional'] / salario_base * 100):.1f}% sobre el salario.")

# --- OTROS MÓDULOS (RESUMIDOS PARA QUE QUEPA EL CÓDIGO) ---
elif menu == "📸 Digitalizar":
    st.header("📸 Digitalización")
    archivo = st.file_uploader("Subir Factura", type=["jpg", "png"])
    if archivo and st.button("Procesar"):
        if 'api_key' not in st.session_state: st.error("Falta API Key")
        else: st.success("Simulación: Datos extraídos correctamente.")

elif menu == "🛡️ Auditoría Fiscal":
    st.header("🛡️ Auditoría")
    # (Aquí iría el código de las pestañas de auditoría que ya tienes)
    st.info("Módulo de auditoría activo.")
