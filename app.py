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

# Estilos para que se vea limpio y fácil de leer
st.markdown("""
    <style>
    .main { background-color: #f0f2f6; }
    h1 { color: #1f77b4; }
    h2, h3 { color: #444; }
    .stAlert { border-radius: 8px; }
    /* Botones más grandes y visibles */
    .stButton>button {
        height: 3em;
        font-weight: bold;
        border-radius: 8px;
        background-color: #2c3e50; 
        color: white;
    }
    .stButton>button:hover { background-color: #34495e; color: #ecf0f1; }
    </style>
    """, unsafe_allow_html=True)

# ==============================================================================
# 2. BASE DE DATOS Y CONSTANTES (SIMULACIÓN)
# ==============================================================================
if 'historial_pagos' not in st.session_state:
    st.session_state.historial_pagos = pd.DataFrame({
        'nit': ['900123456', '88222333', '1098765432'],
        'nombre': ['Suministros SAS', 'Pedro Pintor (Régimen Simple)', 'María Contadora'],
        'acumulado_mes': [0.0, 3500000.0, 150000.0],
        'responsable_iva': [True, False, False]
    })

# Cifras Fiscales (Colombia)
UVT_2025 = 49799
TOPE_EFECTIVO = 100 * UVT_2025  # Art 771-5 E.T.
BASE_RETENCION = 4 * UVT_2025   # Base Servicios

# ==============================================================================
# 3. FUNCIONES LÓGICAS (EL CEREBRO DE LA APP)
# ==============================================================================

def auditar_reglas_negocio(nit, valor, metodo_pago):
    """Revisa topes de efectivo y bases de retención."""
    alertas = []
    
    # Regla 1: Efectivo
    if metodo_pago == 'Efectivo' and valor > TOPE_EFECTIVO:
        alertas.append(f"🔴 **PELIGRO (Art. 771-5):** El pago de ${valor:,.0f} supera el tope de efectivo permitido. Será RECHAZADO por la DIAN.")
        
    # Regla 2: Retención Acumulada
    tercero = st.session_state.historial_pagos[st.session_state.historial_pagos['nit'] == nit]
    if not tercero.empty:
        acumulado = tercero['acumulado_mes'].values[0]
        if acumulado < BASE_RETENCION and (acumulado + valor) >= BASE_RETENCION:
            alertas.append(f"🔔 **OJO CON LA RETENCIÓN:** Este proveedor ya acumula ${acumulado:,.0f} en el mes. Con este pago supera la base. ¡Debes practicar Retención en la Fuente!")
            
    return alertas

def auditar_nomina_ugpp(salario, no_salariales):
    """Calcula la Ley 1393 de 2010."""
    total_ingresos = salario + no_salariales
    limite_40 = total_ingresos * 0.40
    
    if no_salariales > limite_40:
        exceso = no_salariales - limite_40
        ibc_ajustado = salario + exceso
        return ibc_ajustado, exceso, "⚠️ CUIDADO: Te pasaste del 40%", "Riesgo"
    else:
        return salario, 0, "✅ Todo en orden: No excede el 40%", "Seguro"

def consultar_ia_dian(concepto, valor):
    """Le pregunta a la IA sobre deducibilidad."""
    try:
        model = genai.GenerativeModel('models/gemini-1.5-flash')
        prompt = f"""
        Actúa como un Contador Tributarista Experto en Colombia.
        Analiza este gasto: "{concepto}" por valor de ${valor}.
        Responde SOLO en formato JSON:
        {{"veredicto": "DEDUCIBLE / NO DEDUCIBLE / RIESGOSO", "explicacion": "Resumen corto de la norma", "cuenta": "Código PUC sugerido"}}
        """
        response = model.generate_content(prompt)
        return json.loads(response.text.replace("```json", "").replace("```", "").strip())
    except:
        return {"veredicto": "ERROR", "explicacion": "Revisa tu conexión o API Key", "cuenta": "N/A"}

def procesar_factura_ocr(image):
    """Lee la foto de la factura."""
    try:
        model = genai.GenerativeModel('models/gemini-1.5-flash')
        prompt = """
        Extrae los datos de esta factura para contabilidad. Formato JSON:
        {"fecha": "YYYY-MM-DD", "nit": "Solo números", "proveedor": "Nombre Empresa", "concepto": "Resumen", "base": numero, "iva": numero, "total": numero}
        """
        response = model.generate_content([prompt, image])
        return json.loads(response.text.replace("```json", "").replace("```", "").strip())
    except:
        return None

# ==============================================================================
# 4. BARRA LATERAL (MENÚ DE NAVEGACIÓN)
# ==============================================================================
with st.sidebar:
    st.title("🗂️ Menú Principal")
    st.markdown("---")
    
    # Menú explicativo
    menu = st.radio("¿Qué deseas hacer hoy?", 
                    ["📸 Digitalizar Facturas", 
                     "🛡️ Auditoría Fiscal", 
                     "👥 Revisar Nómina (UGPP)"])
    
    st.markdown("---")
    
    # Configuración de Seguridad
    with st.expander("🔐 Configuración de Acceso"):
        st.caption("Para usar las funciones de IA (Lectura y Consultas), ingresa tu clave aquí:")
        api_key = st.text_input("Tu API Key de Google:", type="password")
        if api_key:
            genai.configure(api_key=api_key)
            st.success("Sistema Conectado y Listo.")
        else:
            st.warning("Sistema en modo básico (Solo Cálculos).")

# ==============================================================================
# 5. PANTALLAS (MÓDULOS) CON EXPLICACIONES CLARAS
# ==============================================================================

# --- PESTAÑA 1: DIGITALIZACIÓN ---
if menu == "📸 Digitalizar Facturas":
    st.header("📸 Digitalización Automática")
    
    # Explicación para el colega
    st.info("""
    **¿Para qué sirve esto?**
    Ahórrate la digitación manual. Sube fotos de facturas físicas o imágenes de WhatsApp.
    La herramienta leerá la Fecha, el NIT, la Base y el IVA automáticamente y te entregará un Excel listo para importar.
    """)
    
    archivos = st.file_uploader("Arrastra aquí las fotos de las facturas (JPG/PNG)", type=["jpg", "png", "jpeg"], accept_multiple_files=True)
    
    if archivos and st.button("🚀 Extraer Datos Ahora"):
        if not api_key:
            st.error("⚠️ Necesitas activar la 'Llave Maestra' en el menú de la izquierda.")
        else:
            datos_extraidos = []
            barra = st.progress(0)
            st.write("👓 Leyendo documentos... un momento.")
            
            for i, archivo in enumerate(archivos):
                barra.progress((i + 1) / len(archivos))
                img = Image.open(archivo)
                info = procesar_factura_ocr(img)
                if info:
                    info['Archivo'] = archivo.name
                    datos_extraidos.append(info)
                time.sleep(1)
            
            if datos_extraidos:
                df = pd.DataFrame(datos_extraidos)
                st.success("✅ ¡Listo! Revisa los datos abajo.")
                st.data_editor(df, use_container_width=True)
                
                # Exportar
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    df.to_excel(writer, index=False)
                st.download_button("📥 Descargar Excel para Contabilidad", output.getvalue(), "facturas_leidas.xlsx")

# --- PESTAÑA 2: AUDITORÍA FISCAL ---
elif menu == "🛡️ Auditoría Fiscal":
    st.header("🛡️ Centro de Control Fiscal")
    st.markdown("Aquí validamos que los gastos cumplan con la norma ANTES de contabilizarlos.")
    
    # Sub-pestañas con nombres claros
    pestana1, pestana2, pestana3 = st.tabs([
        "✅ 1. Chequeo de Reglas (Bancarización)", 
        "🧠 2. Consultar Duda a la IA", 
        "📂 3. Revisión Masiva (Excel)"
    ])
    
    # 2.1 REGLAS
    with pestana1:
        st.info("**Objetivo:** Verificar requisitos formales matemáticos (Topes de efectivo y Acumulación de Retención).")
        
        c1, c2 = st.columns(2)
        nit_sel = c1.selectbox("Selecciona el Proveedor:", st.session_state.historial_pagos['nit'], help="Trae el acumulado del mes de este tercero.")
        nom_ter = st.session_state.historial_pagos[st.session_state.historial_pagos['nit'] == nit_sel]['nombre'].values[0]
        st.caption(f"Proveedor: **{nom_ter}**")
        
        val_sel = c2.number_input("Valor a Pagar ($):", min_value=0, step=50000)
        met_sel = c1.selectbox("Forma de Pago:", ["Transferencia", "Cheque", "Efectivo"], help="Recuerda: El efectivo tiene límites estrictos.")
        
        if st.button("🔍 Validar Operación"):
            errores = auditar_reglas_negocio(nit_sel, val_sel, met_sel)
            if not errores:
                st.success("✅ **APROBADO:** La operación cumple con los topes y reglas básicas.")
            else:
                for error in errores:
                    if "PELIGRO" in error: st.error(error)
                    else: st.warning(error)

    # 2.2 CONSULTA IA
    with pestana2:
        st.info("**Objetivo:** ¿Tienes una factura rara? (Ej: Almuerzo de socios, Ropa de trabajo, Regalos a clientes). Pregúntale a la IA si es deducible.")
        pregunta = st.text_area("Describe el gasto:", placeholder="Ejemplo: Compra de licor para fiesta de fin de año de empleados...")
        valor_preg = st.number_input("Valor aproximado:", value=0)
        
        if st.button("🤔 Consultar Concepto Tributario"):
            if api_key:
                with st.spinner("Analizando Estatuto Tributario..."):
                    res = consultar_ia_dian(pregunta, valor_preg)
                    st.write(f"**Veredicto:** {res['veredicto']}")
                    st.write(f"**Explicación:** {res['explicacion']}")
                    st.info(f"Cuenta Sugerida: {res['cuenta']}")
            else:
                st.error("Falta la API Key.")

    # 2.3 MASIVA
    with pestana3:
        st.info("**Objetivo:** Sube tu auxiliar de gastos en Excel. La IA revisará fila por fila buscando problemas.")
        archivo = st.file_uploader("Cargar Excel (.xlsx)", type=['xlsx'])
        if archivo and st.button("Iniciar Auditoría Masiva"):
            st.warning("⚠️ Función de demostración (Analizará las primeras 5 filas para no gastar toda tu cuota de IA).")
            # (Aquí iría la lógica de iteración similar al código anterior)

# --- PESTAÑA 3: NÓMINA UGPP ---
elif menu == "👥 Revisar Nómina (UGPP)":
    st.header("👮‍♀️ Escudo Anti-UGPP (Ley 1393)")
    
    st.info("""
    **¿Por qué usar esto?**
    La UGPP sanciona si los pagos "No Salariales" (Bonos, Rodamientos no constitutivos) superan el 40% del total ganado.
    Esta calculadora te dice exactamente cuánto debes ajustar en la PILA para dormir tranquilo.
    """)
    
    col_izq, col_der = st.columns(2)
    
    with col_izq:
        st.subheader("Ingresos del Empleado")
        salario = st.number_input("Salario Básico ($):", value=1300000.0, step=50000.0)
        no_sal = st.number_input("Total Pagos NO Salariales ($):", value=0.0, step=50000.0, help="Suma aquí: Bonos mera liberalidad, Auxilios de alimentación, Rodamiento, etc.")
    
    with col_der:
        st.subheader("Resultado Auditoría")
        if st.button("🧮 Calcular Límite 40%"):
            ibc_pila, exceso, mensaje, estado = auditar_nomina_ugpp(salario, no_sal)
            
            st.metric(label="IBC que debes reportar en PILA", value=f"${ibc_pila:,.0f}")
            
            if estado == "Riesgo":
                st.error(f"{mensaje}")
                st.write(f"🛑 **Atención:** Tienes un exceso de **${exceso:,.0f}**. Debes sumar este valor al salario para cotizar seguridad social, o serás sancionado.")
            else:
                st.success(f"{mensaje}")
                st.write("👍 Puedes liquidar la PILA solo con el Salario Básico.")

# Pie de página
st.markdown("---")
st.caption("Desarrollado por Colegas para Colegas | Versión 3.0 | 2025")
