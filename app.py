import streamlit as st
import google.generativeai as genai
from PIL import Image
import pandas as pd
import json
import time

# --- 1. CONFIGURACIÓN VISUAL ---
st.set_page_config(page_title="ContadorIA Bulk", page_icon="⚡", layout="wide")

def local_css():
    st.markdown("""
        <style>
        html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
        .stButton>button {
            background: linear-gradient(90deg, #8B5CF6 0%, #6366F1 100%);
            color: white; border: none; padding: 0.6rem 1.2rem;
            border-radius: 10px; font-weight: 600; width: 100%;
        }
        /* Estilo para la barra de progreso */
        .stProgress > div > div > div > div {
            background-color: #8B5CF6;
        }
        </style>
        """, unsafe_allow_html=True)
local_css()

st.title("⚡ ContadorIA - Procesamiento en Lote")
st.markdown("### Sube hasta 10 facturas y procésalas automáticamente.")
st.markdown("---")

# --- BARRA LATERAL ---
with st.sidebar:
    st.header("⚙️ Configuración")
    api_key_input = st.text_input("🔑 API Key de Google", type="password")
    api_key = api_key_input.strip() if api_key_input else None
    
    if api_key:
        st.success("Sistema Activo")
    
    st.info("💡 Nota: El límite de 10 es para proteger la cuota gratuita de Google.")

# --- FUNCIÓN INTELIGENTE DE AUTO-DETECCIÓN ---
def encontrar_modelo_disponible():
    try:
        modelos = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        preferidos = ['models/gemini-1.5-flash', 'models/gemini-1.5-flash-001', 'models/gemini-1.5-pro']
        
        for pref in preferidos:
            if pref in modelos: return pref
            
        # Fallback a cualquier modelo de visión
        return next((m for m in modelos if 'vision' in m), modelos[0] if modelos else None)
    except:
        return None

# --- LÓGICA PRINCIPAL ---
if not api_key:
    st.warning("👈 Ingresa tu API Key a la izquierda para comenzar.")
else:
    genai.configure(api_key=api_key)
    
    # 1. CARGA MÚLTIPLE (accept_multiple_files=True)
    archivos = st.file_uploader(
        "Arrastra tus facturas aquí (Máx 10)", 
        type=["jpg", "png", "jpeg"], 
        accept_multiple_files=True
    )

    if archivos:
        cantidad = len(archivos)
        
        # Validación del límite
        if cantidad > 10:
            st.error(f"⚠️ Has subido {cantidad} archivos. El límite es 10 por seguridad. Por favor elimina algunos.")
        else:
            st.info(f"📂 {cantidad} facturas listas para procesar.")
            
            # Botón de Acción
            if st.button(f"🚀 Procesar {cantidad} Facturas Ahora"):
                
                nombre_modelo = encontrar_modelo_disponible()
                if not nombre_modelo:
                    st.error("No se encontró un modelo IA disponible.")
                    st.stop()
                
                model = genai.GenerativeModel(nombre_modelo)
                resultados = []
                errores = 0
                
                # BARRA DE PROGRESO
                barra_progreso = st.progress(0)
                status_text = st.empty()
                
                # --- BUCLE DE PROCESAMIENTO ---
                for i, archivo in enumerate(archivos):
                    # Actualizar barra
                    progreso = (i + 1) / cantidad
                    barra_progreso.progress(progreso)
                    status_text.text(f"Analizando factura {i+1} de {cantidad}: {archivo.name}...")
                    
                    try:
                        image = Image.open(archivo)
                        
                        prompt = """
                        Analiza esta factura y extrae datos en JSON puro:
                        {"fecha": "YYYY-MM-DD", "proveedor": "texto", "nit": "texto", "total": numero, "iva": numero}
                        Si falta un dato usa null.
                        """
                        
                        response = model.generate_content([prompt, image])
                        texto_limpio = response.text.replace("```json", "").replace("```", "")
                        datos = json.loads(texto_limpio)
                        
                        # Agregamos el nombre del archivo para identificarlo
                        datos["archivo_origen"] = archivo.name
                        resultados.append(datos)
                        
                        # Pequeña pausa para no saturar la API gratuita
                        time.sleep(1) 
                        
                    except Exception as e:
                        errores += 1
                        resultados.append({
                            "archivo_origen": archivo.name,
                            "proveedor": "ERROR DE LECTURA",
                            "total": 0,
                            "nota_error": str(e)
                        })
                
                status_text.text("¡Procesamiento finalizado!")
                st.balloons()
                
                # --- RESULTADOS CONSOLIDADOS ---
                st.divider()
                st.subheader("📊 Tabla Maestra de Gastos")
                
                if errores > 0:
                    st.warning(f"Hubo {errores} errores al leer archivos. Revisa la tabla.")
                
                # Crear DataFrame con TODOS los datos
                df = pd.DataFrame(resultados)
                
                # Reordenar columnas para que 'archivo_origen' salga primero
                cols = ['archivo_origen'] + [c for c in df.columns if c != 'archivo_origen']
                df = df[cols]
                
                # Editor de datos
                df_editado = st.data_editor(
                    df, 
                    num_rows="dynamic", 
                    use_container_width=True,
                    key="editor_datos"
                )
                
                # Métricas Totales del Lote
                total_lote = df_editado["total"].sum()
                iva_lote = df_editado["iva"].sum()
                
                c1, c2 = st.columns(2)
                c1.metric("💰 Total del Lote", f"${total_lote:,.2f}")
                c2.metric("🧾 IVA Total Recuperable", f"${iva_lote:,.2f}")
                
                # Descarga ÚNICA
                csv = df_editado.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Descargar Reporte Consolidado (Excel/CSV)",
                    data=csv,
                    file_name="reporte_gastos_lote.csv",
                    mime="text/csv",
                    type="primary"
                )