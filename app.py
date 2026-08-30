import streamlit as st
import json
import os

st.set_page_config(page_title="Lagerhantering", layout="wide")
st.title("📦 Lagerhantering & Skafferi")

DB_FILE = "stato_magazzino.json"

def carica_magazzino():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r") as f:
                return json.load(f)
        except:
            return {}
    # Standardprodukter som exempel (du kan ändra dem direkt i appen)
    return {
        "101": {"nome": "Pasta Barilla", "scorta": 20, "soglia_minima": 5},
        "102": {"nome": "Krossade tomater", "scorta": 50, "soglia_minima": 10},
        "103": {"nome": "Husets rödvin", "scorta": 12, "soglia_minima": 3}
    }

def salva_magazzino(inventario):
    with open(DB_FILE, "w") as f:
        json.dump(inventario, f)

inventario = carica_magazzino()

# SIDOPANEL: REGISTRERA LEVERANS (Inkommande varor)
st.sidebar.header("🚚 Leverans (Lägg till varor)")
nuovo_codice = st.sidebar.text_input("Produktkod / Streckkod:", placeholder="t.ex. 104 eller skanna")
nuovo_nome = st.sidebar.text_input("Produktnamn:", placeholder="t.ex. Mozzarella")
quantita_carico = st.sidebar.number_input("Antal att lägga till:", min_value=1, value=10)
soglia_allerta = st.sidebar.number_input("Minsta varningsnivå:", min_value=1, value=5)

if st.sidebar.button("Registrera i lager"):
    if not nuovo_codice or not nuevo_nome:
        st.sidebar.error("Ange både produktkod och produktnamn!")
    else:
        if nuovo_codice in inventario:
            inventario[nuovo_codice]["scorta"] += quantita_carico
        else:
            inventario[nuovo_codice] = {"nome": nuevo_nome, "scorta": quantita_carico, "soglia_minima": soglia_allerta}
        salva_magazzino(inventario)
        st.sidebar.success(f"Registrerat! {quantita_carico} st av {nuevo_nome} tillagda.")
        st.sidebar.button("Rensa") # Hjälper att nollställa fältet vid behov
        st.rerun()


# CENTRALPANEL: UTTAG FRÅN LAGER (Minska lagret)
st.header("🛒 Snabbuttag (Minska lager)")
col_scan, col_quantita = st.columns(2)

with col_scan:
    codice_prelievo = st.text_input("Skanna streckkod eller skriv produktkod:", key="scan", placeholder="Placera markören här")
with col_quantita:
    quantita_prelievo = st.number_input("Antal att ta ut:", min_value=1, value=1, key="qta")

if st.button("🔄 Bekräfta uttag", use_container_width=True):
    if codice_prelievo in inventario:
        if inventario[codice_prelievo]["scorta"] >= quantita_prelievo:
            inventario[codice_prelievo]["scorta"] -= quantita_prelievo
            salva_magazzino(inventario)
            st.success(f"Tog ut {quantita_prelievo} st av **{inventario[codice_prelievo]['nome']}**!")
            st.rerun()
        else:
            st.error(f"Otillräckligt lager! Du har bara {inventario[codice_prelievo]['scorta']} st kvar.")
    else:
        st.error("Produktkoden hittades inte i databasen!")


# LAGERSTATUS I REALTID
st.header("📊 Lagerstatus i realtid")

for codice, info in list(inventario.items()):
    col_info, col_azioni = st.columns(2)
    scorta_attuale = info["scorta"]
    soglia = info["soglia_minima"]
    
    with col_info:
        if scorta_attuale <= soglia:
            # Röd varning om produkten håller på att ta slut
            st.error(f"🚨 **[{codice}] {info['nome']}** | Lager: **{scorta_attuale}** st (Under minsta nivå på {soglia} st!)")
        else:
            st.info(f"📦 **[{codice}] {info['nome']}** | Lager: **{scorta_attuale}** st")
            
    with col_azioni:
        # Snabbknapp för att ta bort 1 st (t.ex. om en produkt blivit gammal)
        if st.button("Ta bort 1 st", key=f"del_{codice}"):
            if inventario[codice]["scorta"] > 0:
                inventario[codice]["scorta"] -= 1
                salva_magazzino(inventario)
                st.rerun()
    st.markdown("<hr style='margin: 5px 0; border: 0.5px solid #333;'>", unsafe_allow_html=True)
