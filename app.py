import streamlit as st
import json
import os
from datetime import datetime
import streamlit.components.v1 as components

st.set_page_config(page_title="Gestione Magazzino", layout="wide")
st.title("📦 Magazzino & Registro Storico Merci")

DB_FILE = "stato_magazzino.json"
LOG_FILE = "storico_magazzino.json"

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
        "102": {"nome": "Polpa di Pomodoro", "scorta": 50, "soglia_minima": 10},
        "103": {"nome": "Vino Rosso della Casa", "scorta": 12, "soglia_minima": 3}
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
        "orario": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "azione": azione,
        "codice": codice,
        "nome": nome,
        "quantita": quantita,
        "operatore": operatore,
        "motivo": motivo
    }
    logs.insert(0, nuovo_evento)
    salva_log(logs[:100])

inventario = carica_magazzino()

# BARRA LATERALE: CARICO MERCI
st.sidebar.header("🚚 Carico Merci (Arrivo Fornitori)")
operatore_in = st.sidebar.selectbox("Chi registra il carico?", ["Cuoco 1", "Cuoco 2", "Titolare", "Altro"], key="op_in")

elenco_carico_tendina = [f"{codice} - {info['nome']}" for codice, info in inventario.items()]
elenco_carico_tendina.insert(0, "➕ NUOVO PRODOTTO (Inserisci a mano...)")

prodotto_carico_scelto = st.sidebar.selectbox("Seleziona prodotto da aggiungere:", elenco_carico_tendina)

if prodotto_carico_scelto == "➕ NUOVO PRODOTTO (Inserisci a mano...)":
    nuovo_codice = st.sidebar.text_input("Codice Prodotto / Codice a Barre:", placeholder="es. 104")
    nuovo_nome = st.sidebar.text_input("Nome Prodotto:", placeholder="es. Mozzarella")
    soglia_allerta = st.sidebar.number_input("Scorta minima di allerta:", min_value=1, value=5)
else:
    codice_esistente = prodotto_carico_scelto.split(" - ")[0]
    st.sidebar.info(f"Stai caricando: **{inventario[codice_esistente]['nome']}**")

quantita_carico = st.sidebar.number_input("Quantità da aggiungere:", min_value=1, value=10)

if st.sidebar.button("Registra ed Entra in Magazzino"):
    if prodotto_carico_scelto == "➕ NUOVO PRODOTTO (Inserisci a mano...)":
        nuovo_codice = nuovo_codice.strip()
        if not nuovo_codice or not nuovo_nome:
            st.sidebar.error("Inserisci sia il codice che il nome per il nuovo prodotto!")
        else:
            if nuovo_codice in inventario:
                st.sidebar.error("Questo codice esiste già nel magazzino!")
            else:
                inventario[nuovo_codice] = {"nome": nuovo_nome, "scorta": quantita_carico, "soglia_minima": soglia_allerta}
                salva_magazzino(inventario)
                aggiungi_evento("CARICO (➕)", nuovo_codice, nuovo_nome, quantita_carico, operatore_in, "Nuovo prodotto inserito a mano")
                st.sidebar.success(f"Prodotto creato: {nuovo_nome}!")
                st.rerun()
    else:
        codice_esistente = prodotto_carico_scelto.split(" - ")[0]
        inventario[codice_esistente]["scorta"] += quantita_carico
        salva_magazzino(inventario)
        aggiungi_evento("CARICO (➕)", codice_esistente, inventario[codice_esistente]['nome'], quantita_carico, operatore_in, "Rifornimento scorte")
        st.sidebar.success(f"Aggiunti {quantita_carico} pz.")
        st.rerun()

# RIMOZIONE DEFINITIVA DAL CATALOGO
st.sidebar.markdown("<hr style='margin: 15px 0;'>", unsafe_allow_html=True)
st.sidebar.header("🗑️ Elimina Articolo")
elenco_elimina = [f"{codice} - {info['nome']}" for codice, info in inventario.items()]
if elenco_elimina:
    prodotto_da_eliminare = st.sidebar.selectbox("Seleziona prodotto da cancellare:", elenco_elimina, key="el_sel")
    if st.sidebar.button("🗑️ Elimina Definitivamente dal Magazzino", type="primary"):
        cod_el = prodotto_da_eliminare.split(" - ")[0]
        nome_el = inventario[cod_el]["nome"]
        del inventario[cod_el]
        salva_magazzino(inventario)
        aggiungi_evento("ELIMINATO (❌)", cod_el, nome_el, 0, "Titolare", "Rimosso completamente dal catalogo")
        st.sidebar.success(f"Rimosso {nome_el} dal magazzino!")
        st.rerun()


# PANNELLO CENTRALE: SCARICO RAPIDO
st.header("🛒 Scarico Rapido (Uscita merci per la cucina)")
elenco_prodotti_tendina = [f"{codice} - {info['nome']}" for codice, info in inventario.items()]

col_inputs, col_scanner = st.columns([2, 1])

with col_inputs:
    operatore_out = st.selectbox("Chi preleva la merce?", ["Cuoco 1", "Cuoco 2", "Sala / Camerieri", "Titolare"], key="op_out")
    if elenco_prodotti_tendina:
        prodotto_selezionato = st.selectbox("Seleziona manualmente dal menu:", elenco_prodotti_tendina)
    else:
        st.write("Nessun prodotto in magazzino.")
    
    quantita_prelievo = st.number_input("Quantità da prelevare:", min_value=1, value=1, key="qta")
    motivo_out = st.text_input("Note / Motivazione (opzionale):", placeholder="es. Servizio pranzo, Scaduto, Rotto")
    codice_rilevato = st.text_input("Codice Rilevato (Compilato dallo scanner):", key="manual_code_input")

with col_scanner:
    st.subheader("📸 Lettore Smartphone")
    
    # Componente HTML/JS che attiva lo scanner SOLO se premuto sul telefono
    scanner_html = """
    <script src="https://unpkg.com"></script>
    <div id="reader" style="width:100%; max-width:300px; border:1px solid #333; background:#111;"></div>
    <script>
        function onScanSuccess(decodedText, decodedResult) {
            const inputField = window.parent.document.querySelector('input[aria-label="Codice Rilevato (Compilato dallo scanner):"]');
            if(inputField) {
                inputField.value = decodedText;
                inputField.dispatchEvent(new Event('input', { bubbles: true }));
            } else {
                alert("Codice scansionato: " + decodedText + ". Digitalo nel campo apposito.");
            }
        }
        let html5QrcodeScanner = new Html5QrcodeScanner("reader", { fps: 10, qrbox: 250 });
        html5QrcodeScanner.render(onScanSuccess);
    </script>
    """
    components.html(scanner_html, height=320)

if st.button("🔄 Conferma Operazione", use_container_width=True):
    codice_prelievo = None
    
    if codice_rilevato.strip():
        codice_prelievo = codice_rilevato.strip()
    elif elenco_prodotti_tendina:
        codice_prelievo = prodotto_selezionato.split(" - ")[0]
        
    if codice_prelievo and codice_prelievo in inventario:
        if inventario[codice_prelievo]["scorta"] >= quantita_prelievo:
            inventario[codice_prelievo]["scorta"] -= quantita_prelievo
            salva_magazzino(inventario)
            aggiungi_evento("SCARICO (➖)", codice_prelievo, inventario[codice_prelievo]["nome"], quantita_prelievo, operatore_out, motivo_out)
            st.success(f"Prelevati {quantita_prelievo} pz di {inventario[codice_prelievo]['nome']}!")
            st.rerun()
        else:
            st.error(f"Scorte insufficienti! Ci sono solo {inventario[codice_prelievo]['scorta']} pz in magazzino.")
    else:
        st.error("Codice prodotto non trovato nel database o magazzino vuoto!")

# INVENTARIO IN TEMPO REALE
st.header("📊 Scorte Attuali in Dispensa")
for codice, info in list(inventario.items()):
    col_info, col_azioni = st.columns(2)
    scorta_attuale = info["scorta"]
    soglia = info["soglia_minima"]
    
    with col_info:
        if scorta_attuale <= soglia:
            st.markdown(f"🚨 [<span style='color: #FFD166; font-size: 24px; font-weight: bold;'>{codice}</span>] **{info['nome']}** | In Magazzino: <span style='color: #F72585; font-weight: bold;'>{scorta_attuale} pz</span> (Sotto la soglia!)", unsafe_allow_html=True)
        else:
            st.markdown(f"📦 [<span style='color: #FFD166; font-size: 24px; font-weight: bold;'>{codice}</span>] **{info['nome']}** | In Magazzino: **{scorta_attuale} pz**", unsafe_allow_html=True)
            
    with col_azioni:
        if st.button("Elimina rapido (1 pz)", key=f"del_{codice}"):
            if inventario[codice]["scorta"] > 0:
                inventario[codice]["scorta"] -= 1
                salva_magazzino(inventario)
                aggiungi_evento("CANCELLAZIONE (🗑️)", codice, inventario[codice]["nome"], 1, "Titolare", "Eliminato a mano")
                st.rerun()
    st.markdown("<hr style='margin: 8px 0; border: 0.5px solid #333;'>", unsafe_allow_html=True)

# REGISTRO STORICO
st.header("📜 Registro Ultimi Movimenti (Tracciabilità)")
lista_attivita = carica_log()

if lista_attivita:
    for ev in lista_attivita:
        st.text(f"⏱️ {ev['orario']} | {ev['azione']} | Cod: {ev['codice']} - {ev['nome']} | Qnt: {ev['quantita']} pz | Da: {ev['operatore']} | Note: {ev['motivo']}")
else:
    st.write("Nessun movimento registrato finora.")
