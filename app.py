import streamlit as st
import json
import os
from datetime import datetime

st.set_page_config(page_title="Lagerhantering", layout="wide")
st.title("📦 Lagerhantering & Historik")

DB_FILE = "stato_magazzino.json"
LOG_FILE = "historik_magazzino.json"

# Carica Inventario
def carica_magazzino():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r") as f:
                return json.load(f)
        except:
            return {}
    return {
        "101": {"nome": "Pasta Barilla", "scorta": 20, "soglia_minima": 5},
        "102": {"nome": "Krossade tomater", "scorta": 50, "soglia_minima": 10},
        "103": {"nome": "Husets rödvin", "scorta": 12, "soglia_minima": 3}
    }

def salva_magazzino(inventario):
    with open(DB_FILE, "w") as f:
        json.dump(inventario, f)

# Carica Registro Storico
def carica_log():
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, "r") as f:
                return json.load(f)
        except:
            return []
    return []

def salva_log(lista_log):
    with open(LOG_FILE, "w") as f:
        json.dump(lista_log, f)

def aggiungi_evento(azione, codice, nome, quantita, operatore, motivo=""):
    logs = carica_log()
    nuovo_evento = {
        "tid": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "azione": azione, # "INPUT" o "OUTPUT"
        "kod": codice,
        "namn": nome,
        "antal": quantita,
        "personal": operatore,
        "orsak": motivo
    }
    logs.insert(0, nuovo_evento) # Mette l'ultimo evento in cima
    salva_log(logs[:100]) # Tiene in memoria solo gli ultimi 100 movimenti

inventario = carica_magazzino()

# SIDOPANEL: LEVERANS (INPUT)
st.sidebar.header("🚚 Leverans (Lägg till varor)")
operatore_in = st.sidebar.selectbox("Vem registrerar?", ["Kock 1", "Kock 2", "Chef", "Annan"], key="op_in")
nuovo_codice = st.sidebar.text_input("Produktkod / Streckkod:", placeholder="t.ex. 104 eller skanna")
nuovo_nome = st.sidebar.text_input("Produktnamn:", placeholder="t.ex. Mozzarella")
quantita_carico = st.sidebar.number_input("Antal att lägga till:", min_value=1, value=10)
soglia_allerta = st.sidebar.number_input("Minsta varningsnivå:", min_value=1, value=5)

if st.sidebar.button("Registrera i lager"):
    if not nuovo_codice or not nuovo_nome:
        st.sidebar.error("Ange både produktkod och produktnamn!")
    else:
        if nuovo_codice in inventario:
            inventario[nuovo_codice]["scorta"] += quantita_carico
            nome_p = inventario[nuovo_codice]["nome"]
        else:
            inventario[nuovo_codice] = {"nome": nuovo_nome, "scorta": quantita_carico, "soglia_minima": soglia_allerta}
            nome_p = nuovo_nome
        
        salva_magazzino(inventario)
        aggiungi_evento("LEVERANS (➕)", nuovo_codice, nome_p, quantita_carico, operatore_in, "Inkommande varor")
        st.sidebar.success(f"Registrerat! {quantita_carico} st tillagda.")
        st.rerun()

# CENTRALPANEL: UTTAG (OUTPUT)
st.header("🛒 Snabbuttag (Minska lager)")

# Integrazione Scanner Fotocamera del telefono (Nativa)
codice_scannato = st.text_input("📷 KLICKA HÄR FÖR ATT SKANNA MED TELEFONEN:", key="scan_input", placeholder="Placera markören här och använd kameran")

col_user, col_quantita, col_motivo = st.columns(3)
with col_user:
    operatore_out = st.selectbox("Vem tar ut varan?", ["Kock 1", "Kock 2", "Servering", "Chef"], key="op_out")
with col_quantita:
    quantita_prelievo = st.number_input("Antal att ta ut:", min_value=1, value=1, key="qta")
with col_motivo:
    motivo_out = st.text_input("Anledning (valfritt):", placeholder="t.ex. Matsal, Trasig, Utgången")

if st.button("🔄 Bekräfta uttag", use_container_width=True):
    codice_prelievo = codice_scannato.strip()
    if codice_prelievo in inventario:
        if inventario[codice_prelievo]["scorta"] >= quantita_prelievo:
            inventario[codice_prelievo]["scorta"] -= quantita_prelievo
            salva_magazzino(inventario)
            aggiungi_evento("UTTAG (➖)", codice_prelievo, inventario[codice_prelievo]["nome"], quantita_prelievo, operatore_out, motivo_out)
            st.success(f"Tog ut {quantita_prelievo} st!")
            st.rerun()
        else:
            st.error(f"Otillräckligt lager! Endast {inventario[codice_prelievo]['scorta']} st kvar.")
    else:
        st.error("Produktkoden hittades inte i databasen!")

# LAGERSTATUS I REALTID
st.header("📊 Lagerstatus")
for codice, info in list(inventario.items()):
    col_info, col_azioni = st.columns(2)
    scorta_attuale = info["scorta"]
    soglia = info["soglia_minima"]
    
    with col_info:
        if scorta_attuale <= soglia:
            st.markdown(f"🚨 [<span style='color: #FFD166; font-size: 24px; font-weight: bold;'>{codice}</span>] **{info['nome']}** | Lager: <span style='color: #F72585; font-weight: bold;'>{scorta_attuale} st</span> (Varning!)", unsafe_allow_html=True)
        else:
            st.markdown(f"📦 [<span style='color: #FFD166; font-size: 24px; font-weight: bold;'>{codice}</span>] **{info['nome']}** | Lager: **{scorta_attuale} st**", unsafe_allow_html=True)
            
    with col_azioni:
        if st.button("Snabbradering (1 st)", key=f"del_{codice}"):
            if inventario[codice]["scorta"] > 0:
                inventario[codice]["scorta"] -= 1
                salva_magazzino(inventario)
                aggiungi_evento("SNARENSNING (🗑️)", codice, inventario[codice]["nome"], 1, "Chef/Kock", "Manuellt borttagen")
                st.rerun()
    st.markdown("<hr style='margin: 8px 0; border: 0.5px solid #333;'>", unsafe_allow_html=True)

# REGISTRO STORICO DELLE ATTIVITÀ (HISTORIK)
st.header("📜 Senaste aktiviteterna (Tracerbarhet)")
lista_attivita = carica_log()

if lista_attivita:
    for ev in lista_attivita:
        st.text(f"⏱️ {ev['tid']} | {ev['azione']} | Kod: {ev['kod']} - {ev['namn']} | Antal: {ev['antal']} st | Av: {ev['personal']} | Obs: {ev['orsak']}")
else:
    st.write("Inga aktiviteter registrerade ännu.")
