import streamlit as st
import google.generativeai as genai
from PIL import Image
import pandas as pd
import json
import time
import io

# --- 1. CONFIGURACIÓN VISUAL ---
st.set_page_config(page_title="ContadorIA Pro", page_icon="🕵️‍♂️", layout="wide")

def local_css():
    st.markdown("""
        <style>
        html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
        .stButton>button {
            background: linear-gradient(90deg, #2563EB 0%, #1E40AF 100%);
            color: white; border: none; padding: 0.6rem 1.2rem;
            border-radius: 8px; font-weight: 600; width: 100%;
        }
        /* Estilos para semáforo de riesgo */
        .riesgo-alto { color: #dc2626; font-weight: bold; }
        .riesgo-medio { color: #d97706; font-weight: bold; }
        .riesgo-bajo { color: #059669; font-weight: bold; }
        </style>
        """, unsafe_allow_html=True)
local_css()

# --- BARRA LATERAL ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/2830/2830305.png", width=80)
    st.title("ContadorIA Suite")
    st.markdown("---")
    api_key_input = st.text_input("🔑 Tu API Key de Google", type="password")
    api_key = api_key_input.strip() if api_key_input else None
    
    if api_key:
        genai.configure(api_key=api_key)
        st.success("Sistema Conectado")
    else:
        st.warning("Ingresa la Key para activar el cerebro.")

    st.markdown("---")
    st.info("💡 Tip: Para la auditoría masiva, asegúrate de que tu Excel tenga una columna llamada 'Concepto' o 'Detalle'.")

# --- FUNCIONES ---
def encontrar_modelo_disponible():
    try:
        modelos = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        preferidos = ['models/gemini-1.5-flash', 'models/gemini-1.5-pro']
        for pref in preferidos:
            if pref in modelos: return pref
        return modelos[0] if modelos else None
    except:
        return None

def auditar_fila(concepto, valor):
    """Envía un solo gasto a la IA para evaluación rápida"""
    try:
        # Usamos flash por velocidad y economía
        model = genai.GenerativeModel('models/gemini-1.5-flash')
        prompt = f"""
        Actúa como auditor de la DIAN (Colombia). Analiza este gasto:
        Concepto: "{concepto}"
        Valor: ${valor}
        
        Responde SOLO con un objeto JSON (sin markdown):
        {{"riesgo": "Alto/Medio/Bajo", "justificacion": "Explicación corta de 10 palabras", "cuenta_sugerida": "Código PUC"}}
        """
        response = model.generate_content(prompt)
        return json.loads(response.text.replace("```json", "").replace("```", "").strip())
    except:
        return
