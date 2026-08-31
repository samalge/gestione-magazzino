import streamlit as st
import json
import os
import re
import shutil
from datetime import datetime, date

# ============================================================
# CONFIGURAZIONE
# ============================================================

st.set_page_config(
    page_title="Gestione Magazzino",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded"
)

DB_FILE = "stato_magazzino.json"
LOG_FILE = "storico_magazzino.json"
BACKUP_DIR = "backup_magazzino"

# IMPORTANTE:
# Per sicurezza, in produzione è consigliato mettere la password
# nei Secrets di Streamlit:
#
# ADMIN_PASSWORD = "LaTuaPassword"
#
# Il valore qui sotto rimane come fallback per mantenere
# compatibilità con la tua versione precedente.
PASSWORD_FALLBACK = "Samuelmark123#"

SOGLIA_ULTIME_SCORTE = 6
MAX_LOG = 500


# ============================================================
# CSS
# ============================================================

st.markdown(
    """
    <style>

    .main-title {
        font-size: 2.3rem;
        font-weight: 700;
        margin-bottom: 0;
    }

    .subtitle {
        color: #777;
        margin-bottom: 1.5rem;
    }

    .danger-box {
        padding: 15px;
        border-radius: 10px;
        background-color: #f8d7da;
        border-left: 6px solid #dc3545;
        margin-bottom: 10px;
    }

    .warning-box {
        padding: 15px;
        border-radius: 10px;
        background-color: #fff3cd;
        border-left: 6px solid #f0ad4e;
        margin-bottom: 10px;
    }

    .success-box {
        padding: 15px;
        border-radius: 10px;
        background-color: #d1e7dd;
        border-left: 6px solid #198754;
        margin-bottom: 10px;
    }

    .stock-critical {
        color: #dc3545;
        font-size: 1.15rem;
        font-weight: 700;
    }

    .stock-warning {
        color: #d97706;
        font-size: 1.05rem;
        font-weight: 700;
    }

    .stock-ok {
        color: #198754;
        font-weight: 700;
    }

    .small-muted {
        color: #777;
        font-size: 0.85rem;
    }

    </style>
    """,
    unsafe_allow_html=True
)


# ============================================================
# SESSION STATE
# ============================================================

if "autenticato" not in st.session_state:
    st.session_state.autenticato = False

if "conferma_eliminazione" not in st.session_state:
    st.session_state.conferma_eliminazione = False

if "codice_da_eliminare" not in st.session_state:
    st.session_state.codice_da_eliminare = None


# ============================================================
# PASSWORD
# ============================================================

def get_password():
    try:
        if "ADMIN_PASSWORD" in st.secrets:
            return st.secrets["ADMIN_PASSWORD"]
    except Exception:
        pass

    return PASSWORD_FALLBACK


# ============================================================
# DATABASE
# ============================================================

def database_predefinito():
    return {
        "101": {
            "nome": "Pasta Barilla",
            "scorta": 20,
            "soglia_minima": 5
        },
        "102": {
            "nome": "Polpa di Pomodoro",
            "scorta": 50,
            "soglia_minima": 10
        },
        "103": {
            "nome": "Vino Rosso della Casa",
            "scorta": 12,
            "soglia_minima": 3
        }
    }


def carica_magazzino():
    if not os.path.exists(DB_FILE):
        return database_predefinito()

    try:
        with open(DB_FILE, "r", encoding="utf-8") as f:
            dati = json.load(f)

        if not isinstance(dati, dict):
            return {}

        # Normalizzazione dati vecchi
        for codice, info in dati.items():

            if not isinstance(info, dict):
                dati[codice] = {
                    "nome": str(info),
                    "scorta": 0,
                    "soglia_minima": 5
                }
                continue

            info.setdefault("nome", codice)
            info.setdefault("scorta", 0)
            info.setdefault("soglia_minima", 5)

            try:
                info["scorta"] = int(info["scorta"])
            except Exception:
                info["scorta"] = 0

            try:
                info["soglia_minima"] = int(info["soglia_minima"])
            except Exception:
                info["soglia_minima"] = 5

        return dati

    except Exception:
        st.error(
            "⚠️ Impossibile leggere il database del magazzino. "
            "Controlla il file stato_magazzino.json."
        )
        return {}


def salva_magazzino(inventario, backup=True):
    if backup and os.path.exists(DB_FILE):
        crea_backup(DB_FILE)

    try:
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(
                inventario,
                f,
                indent=4,
                ensure_ascii=False
            )
        return True

    except Exception as e:
        st.error(f"❌ Errore nel salvataggio: {e}")
        return False


def carica_log():
    if not os.path.exists(LOG_FILE):
        return []

    try:
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            dati = json.load(f)

        if isinstance(dati, list):
            return dati

        return []

    except Exception:
        return []


def salva_log(lista_log, backup=True):
    if backup and os.path.exists(LOG_FILE):
        crea_backup(LOG_FILE)

    try:
        with open(LOG_FILE, "w", encoding="utf-8") as f:
            json.dump(
                lista_log[:MAX_LOG],
                f,
                indent=4,
                ensure_ascii=False
            )
        return True

    except Exception as e:
        st.error(f"❌ Errore nel salvataggio dello storico: {e}")
        return False


# ============================================================
# BACKUP
# ============================================================

def crea_backup(file_da_salvare):
    if not os.path.exists(file_da_salvare):
        return None

    try:
        os.makedirs(BACKUP_DIR, exist_ok=True)

        nome_file = os.path.basename(file_da_salvare)
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

        percorso_backup = os.path.join(
            BACKUP_DIR,
            f"{timestamp}_{nome_file}"
        )

        shutil.copy2(
            file_da_salvare,
            percorso_backup
        )

        return percorso_backup

    except Exception:
        return None


# ============================================================
# STORICO
# ============================================================

def aggiungi_evento(
    azione,
    codice,
    nome,
    quantita,
    operatore,
    motivo="",
    scorta_prima=None,
    scorta_dopo=None
):
    logs = carica_log()

    evento = {
        "id": datetime.now().strftime(
            "%Y%m%d%H%M%S%f"
        ),
        "orario": datetime.now().strftime(
            "%d/%m/%Y %H:%M:%S"
        ),
        "azione": azione,
        "codice": str(codice),
        "nome": nome,
        "quantita": quantita,
        "operatore": operatore,
        "motivo": motivo,
        "scorta_prima": scorta_prima,
        "scorta_dopo": scorta_dopo
    }

    logs.insert(0, evento)

    salva_log(
        logs,
        backup=False
    )


# ============================================================
# FUNZIONI MAGAZZINO
# ============================================================

def stato_scorta(scorta, soglia):
    if scorta <= SOGLIA_ULTIME_SCORTE:
        return "critica"

    if scorta <= soglia:
        return "bassa"

    return "ok"


def articoli_critici(inventario):
    return {
        codice: info
        for codice, info in inventario.items()
        if int(info.get("scorta", 0)) <= SOGLIA_ULTIME_SCORTE
    }


def articoli_da_riordinare(inventario):
    return {
        codice: info
        for codice, info in inventario.items()
        if int(info.get("scorta", 0))
        <= int(info.get("soglia_minima", 5))
    }


def pulisci_codice(codice):
    codice = str(codice).strip()
    codice = re.sub(r"\s+", "", codice)
    return codice


def trova_codice_da_selezione(selezione):
    if not selezione:
        return None

    return selezione.split(" - ", 1)[0].strip()


def formatta_operatore(cuoco, cameriere):
    firme = []

    if cuoco.strip():
        firme.append(
            f"Kock: {cuoco.strip()}"
        )

    if cameriere.strip():
        firme.append(
            f"Servering: {cameriere.strip()}"
        )

    if firme:
        return " & ".join(firme)

    return "Non specificato"


# ============================================================
# CARICAMENTO
# ============================================================

inventario = carica_magazzino()


# ============================================================
# HEADER
# ============================================================

st.markdown(
    '<div class="main-title">📦 Gestione Magazzino</div>',
    unsafe_allow_html=True
)

st.markdown(
    '<div class="subtitle">'
    'Controllo scorte, carichi, scarichi e registro storico merci'
    '</div>',
    unsafe_allow_html=True
)


# ============================================================
# SIDEBAR - LOGIN
# ============================================================

st.sidebar.header("🔐 Area Riservata Titolare")

st.markdown(
    """
    <style>
    button[title="Show password"],
    button[title="Hide password"] {
        display: none !important;
    }

    input[type="password"]::-ms-reveal {
        display: none !important;
    }
    </style>
    """,
    unsafe_allow_html=True
)


if not st.session_state.autenticato:

    password_inserita = st.sidebar.text_input(
        "Password titolare:",
        type="password",
        key="pwd_field"
    )

    if st.sidebar.button(
        "🔓 Accedi",
        use_container_width=True
    ):

        if password_inserita == get_password():

            st.session_state.autenticato = True
            st.rerun()

        else:

            st.sidebar.error(
                "❌ Password errata."
            )

else:

    st.sidebar.success(
        "🔓 Accesso titolare autorizzato"
    )

    if st.sidebar.button(
        "🔒 Esci e Blocca",
        type="primary",
        use_container_width=True
    ):

        st.session_state.autenticato = False
        st.session_state.conferma_eliminazione = False
        st.rerun()


# ============================================================
# SIDEBAR - GESTIONE ARTICOLI
# ============================================================

if st.session_state.autenticato:

    st.sidebar.markdown("---")

    st.sidebar.header("📦 Gestione Articoli")

    tab_aggiungi, tab_modifica = st.sidebar.tabs(
        ["➕ Nuovo", "✏️ Modifica"]
    )

    # ========================================================
    # NUOVO ARTICOLO
    # ========================================================

    with tab_aggiungi:

        nuovo_codice = st.text_input(
            "Codice / Barcode:",
            placeholder="Es. 104",
            key="nuovo_codice"
        )

        nuovo_nome = st.text_input(
            "Nome articolo:",
            placeholder="Es. Mozzarella",
            key="nuovo_nome"
        )

        nuova_soglia = st.number_input(
            "Scorta minima:",
            min_value=0,
            value=5,
            step=1,
            key="nuova_soglia"
        )

        nuova_scorta = st.number_input(
            "Scorta iniziale:",
            min_value=0,
            value=0,
            step=1,
            key="nuova_scorta"
        )

        if st.button(
            "➕ Crea Articolo",
            use_container_width=True
        ):

            codice = pulisci_codice(
                nuovo_codice
            )

            nome = nuovo_nome.strip()

            if not codice:

                st.error(
                    "Inserisci un codice."
                )

            elif not nome:

                st.error(
                    "Inserisci il nome dell'articolo."
                )

            elif codice in inventario:

                st.error(
                    "❌ Questo codice esiste già."
                )

            else:

                crea_backup(DB_FILE)

                inventario[codice] = {
                    "nome": nome,
                    "scorta": int(nuova_scorta),
                    "soglia_minima": int(nuova_soglia)
                }

                salva_magazzino(
                    inventario,
                    backup=False
                )

                aggiungi_evento(
                    "NUOVO ARTICOLO (➕)",
                    codice,
                    nome,
                    int(nuova_scorta),
                    "Titolare",
                    "Nuovo articolo creato",
                    0,
                    int(nuova_scorta)
                )

                st.success(
                    f"✅ {nome} creato."
                )

                st.rerun()

    # ========================================================
    # MODIFICA ARTICOLO
    # ========================================================

    with tab_modifica:

        if inventario:

            elenco_modifica = [
                f"{codice} - {info['nome']}"
                for codice, info in inventario.items()
            ]

            articolo_modifica = st.selectbox(
                "Articolo:",
                elenco_modifica,
                key="articolo_modifica"
            )

            codice_modifica = trova_codice_da_selezione(
                articolo_modifica
            )

            info_modifica = inventario[
                codice_modifica
            ]

            nome_modificato = st.text_input(
                "Nome:",
                value=info_modifica["nome"],
                key="nome_modificato"
            )

            soglia_modificata = st.number_input(
                "Scorta minima:",
                min_value=0,
                value=int(
                    info_modifica.get(
                        "soglia_minima",
                        5
                    )
                ),
                step=1,
                key="soglia_modificata"
            )

            nuovo_codice_modificato = st.text_input(
                "Codice:",
                value=codice_modifica,
                key="codice_modificato"
            )

            if st.button(
                "💾 Salva Modifiche",
                use_container_width=True
            ):

                nuovo_codice_modificato = pulisci_codice(
                    nuovo_codice_modificato
                )

                nome_modificato = nome_modificato.strip()

                if not nuovo_codice_modificato:

                    st.error(
                        "Il codice non può essere vuoto."
                    )

                elif not nome_modificato:

                    st.error(
                        "Il nome non può essere vuoto."
                    )

                elif (
                    nuovo_codice_modificato != codice_modifica
                    and nuovo_codice_modificato in inventario
                ):

                    st.error(
                        "❌ Il nuovo codice esiste già."
                    )

                else:

                    crea_backup(DB_FILE)

                    dati_articolo = inventario.pop(
                        codice_modifica
                    )

                    dati_articolo["nome"] = nome_modificato
                    dati_articolo["soglia_minima"] = int(
                        soglia_modificata
                    )

                    inventario[
                        nuovo_codice_modificato
                    ] = dati_articolo

                    salva_magazzino(
                        inventario,
                        backup=False
                    )

                    aggiungi_evento(
                        "MODIFICA ARTICOLO (✏️)",
                        nuovo_codice_modificato,
                        nome_modificato,
                        0,
                        "Titolare",
                        (
                            f"Modificato articolo "
                            f"{codice_modifica}"
                        ),
                        dati_articolo.get("scorta", 0),
                        dati_articolo.get("scorta", 0)
                    )

                    st.success(
                        "✅ Articolo modificato."
                    )

                    st.rerun()

        else:

            st.sidebar.info(
                "Nessun articolo presente."
            )


# ============================================================
# DASHBOARD
# ============================================================

st.markdown("---")
st.header("📊 Situazione Magazzino")

numero_articoli = len(inventario)

pezzi_totali = sum(
    int(info.get("scorta", 0))
    for info in inventario.values()
)

critici = articoli_critici(
    inventario
)

da_riordinare = articoli_da_riordinare(
    inventario
)

c1, c2, c3, c4 = st.columns(4)

with c1:
    st.metric(
        "📦 Articoli",
        numero_articoli
    )

with c2:
    st.metric(
        "🔢 Pezzi totali",
        pezzi_totali
    )

with c3:
    st.metric(
        "🔴 Ultime 6",
        len(critici)
    )

with c4:
    st.metric(
        "🟠 Da riordinare",
        len(da_riordinare)
    )


# ============================================================
# ALLARMI
# ============================================================

if critici:

    st.markdown(
        """
        <div class="danger-box">
        <strong>🚨 ATTENZIONE — ULTIME SCORTE!</strong><br>
        Ci sono articoli con 6 pezzi o meno in magazzino.
        Controlla subito le scorte.
        </div>
        """,
        unsafe_allow_html=True
    )

    for codice, info in critici.items():

        st.markdown(
            f"""
            <div class="danger-box">
            🔴 <strong>ULTIME SCORTE</strong><br>
            <strong>{info['nome']}</strong>
            — Codice: {codice}
            — Rimasti: <strong>{info['scorta']} pz</strong>
            </div>
            """,
            unsafe_allow_html=True
        )


if da_riordinare:

    solo_warning = {
        codice: info
        for codice, info in da_riordinare.items()
        if codice not in critici
    }

    if solo_warning:

        st.markdown(
            """
            <div class="warning-box">
            <strong>🟠 ARTICOLI DA RIORDINARE</strong><br>
            Alcuni prodotti hanno raggiunto la soglia minima.
            </div>
            """,
            unsafe_allow_html=True
        )


# ============================================================
# SCARICO RAPIDO
# ============================================================

st.markdown("---")
st.header("🛒 Scarico Rapido")
st.caption(
    "Registrazione delle merci prelevate dalla cucina o dalla sala."
)


col_personale, col_prodotto, col_quantita = st.columns(
    [1.2, 1.8, 1]
)


with col_personale:

    nome_cuoco = st.text_input(
        "👨‍🍳 Kock",
        placeholder="Nome cuoco"
    )

    nome_cameriere = st.text_input(
        "🤵 Servering",
        placeholder="Nome cameriere"
    )


with col_prodotto:

    elenco_prodotti = [
        f"{codice} - {info['nome']}"
        for codice, info in inventario.items()
    ]

    if elenco_prodotti:

        prodotto_selezionato = st.selectbox(
            "📦 Prodotto:",
            elenco_prodotti,
            key="prodotto_scarico"
        )

    else:

        prodotto_selezionato = None

        st.info(
            "Nessun prodotto disponibile."
        )

    codice_manuale = st.text_input(
        "Oppure codice manuale:",
        placeholder="Es. 101",
        key="manual_code_input"
    )


with col_quantita:

    quantita_prelievo = st.number_input(
        "Quantità:",
        min_value=1,
        value=1,
        step=1,
        key="qta_scarico"
    )


motivo_out = st.text_input(
    "📝 Note / Motivazione:",
    placeholder=(
        "Es. Servizio pranzo, cena, scaduto, rotto..."
    )
)


if st.button(
    "➖ CONFERMA SCARICO",
    type="primary",
    use_container_width=True
):

    codice_prelievo = None

    if codice_manuale.strip():

        codice_prelievo = pulisci_codice(
            codice_manuale
        )

    elif prodotto_selezionato:

        codice_prelievo = trova_codice_da_selezione(
            prodotto_selezionato
        )

    if not codice_prelievo:

        st.error(
            "❌ Seleziona un prodotto o inserisci un codice."
        )

    elif codice_prelievo not in inventario:

        st.error(
            f"❌ Codice {codice_prelievo} non trovato."
        )

    else:

        info = inventario[
            codice_prelievo
        ]

        scorta_prima = int(
            info.get("scorta", 0)
        )

        quantita = int(
            quantita_prelievo
        )

        if quantita > scorta_prima:

            st.error(
                f"❌ Scorte insufficienti. "
                f"Disponibili: {scorta_prima} pz."
            )

        else:

            scorta_dopo = (
                scorta_prima - quantita
            )

            crea_backup(DB_FILE)

            inventario[
                codice_prelievo
            ]["scorta"] = scorta_dopo

            salva_magazzino(
                inventario,
                backup=False
            )

            operatore = formatta_operatore(
                nome_cuoco,
                nome_cameriere
            )

            aggiungi_evento(
                "SCARICO (➖)",
                codice_prelievo,
                info["nome"],
                quantita,
                operatore,
                motivo_out.strip(),
                scorta_prima,
                scorta_dopo
            )

            st.success(
                f"✅ Prelevati {quantita} pz di "
                f"{info['nome']}."
            )

            if scorta_dopo <= SOGLIA_ULTIME_SCORTE:

                st.error(
                    f"🚨 ATTENZIONE: rimangono soltanto "
                    f"{scorta_dopo} pz di {info['nome']}!"
                )

            elif scorta_dopo <= int(
                info.get("soglia_minima", 5)
            ):

                st.warning(
                    f"⚠️ {info['nome']} è sotto la soglia "
                    f"minima: {scorta_dopo} pz."
                )

            st.rerun()


# ============================================================
# RICERCA INVENTARIO
# ============================================================

st.markdown("---")
st.header("📦 Scorte Attuali")

ricerca = st.text_input(
    "🔎 Cerca articolo per nome o codice:",
    placeholder="Es. mozzarella oppure 101"
)

inventario_visualizzato = {}

for codice, info in inventario.items():

    testo_ricerca = (
        f"{codice} {info['nome']}"
    ).lower()

    if (
        not ricerca.strip()
        or ricerca.lower().strip() in testo_ricerca
    ):

        inventario_visualizzato[
            codice
        ] = info


if not inventario_visualizzato:

    st.info(
        "Nessun articolo trovato."
    )

else:

    # --------------------------------------------------------
    # ORDINE: prima quelli critici
    # --------------------------------------------------------

    inventario_visualizzato = dict(
        sorted(
            inventario_visualizzato.items(),
            key=lambda item: (
                item[1].get("scorta", 0),
                item[1].get("nome", "")
            )
        )
    )

    for codice, info in inventario_visualizzato.items():

        scorta = int(
            info.get("scorta", 0)
        )

        soglia = int(
            info.get("soglia_minima", 5)
        )

        stato = stato_scorta(
            scorta,
            soglia
        )

        col_info, col_azioni = st.columns(
            [3, 1]
        )

        with col_info:

            if stato == "critica":

                st.markdown(
                    f"""
                    <div class="danger-box">
                    🔴 <strong>ULTIME 6 SCORTE!</strong><br>
                    <strong>{info['nome']}</strong><br>
                    Codice: {codice}<br>
                    Rimasti:
                    <span class="stock-critical">
                    {scorta} pz
                    </span>
                    </div>
                    """,
                    unsafe_allow_html=True
                )

            elif stato == "bassa":

                st.markdown(
                    f"""
                    <div class="warning-box">
                    🟠 <strong>DA RIORDINARE</strong><br>
                    <strong>{info['nome']}</strong><br>
                    Codice: {codice}<br>
                    Rimasti:
                    <span class="stock-warning">
                    {scorta} pz
                    </span>
                    — Soglia minima: {soglia}
                    </div>
                    """,
                    unsafe_allow_html=True
                )

            else:

                st.markdown(
                    f"""
                    <div class="success-box">
                    🟢 <strong>{info['nome']}</strong><br>
                    Codice: {codice}<br>
                    Rimasti:
                    <span class="stock-ok">
                    {scorta} pz
                    </span>
                    — Soglia minima: {soglia}
                    </div>
                    """,
                    unsafe_allow_html=True
                )

        with col_azioni:

            st.write("")

            if st.button(
                "➖ 1 pezzo",
                key=f"scarico_rapido_{codice}",
                use_container_width=True
            ):

                if scorta > 0:

                    crea_backup(DB_FILE)

                    inventario[codice]["scorta"] -= 1

                    nuova_scorta = inventario[
                        codice
                    ]["scorta"]

                    salva_magazzino(
                        inventario,
                        backup=False
                    )

                    aggiungi_evento(
                        "SCARICO RAPIDO (➖)",
                        codice,
                        info["nome"],
                        1,
                        "Operazione rapida",
                        "Scarico rapido 1 pezzo",
                        scorta,
                        nuova_scorta
                    )

                    st.rerun()

                else:

                    st.error(
                        "Scorta già a zero."
                    )


# ============================================================
# STORICO
# ============================================================

st.markdown("---")
st.header("📜 Registro Storico Merci")

logs = carica_log()

if not logs:

    st.info(
        "Nessuna operazione registrata."
    )

else:

    col_filtro1, col_filtro2, col_filtro3 = st.columns(3)

    with col_filtro1:

        filtro_azione = st.selectbox(
            "Tipo operazione:",
            [
                "Tutte",
                "CARICO",
                "SCARICO",
                "ELIMINATO",
                "NUOVO ARTICOLO",
                "MODIFICA ARTICOLO"
            ]
        )

    with col_filtro2:

        filtro_ricerca_log = st.text_input(
            "🔎 Cerca nello storico:",
            placeholder="Nome, codice, operatore..."
        )

    with col_filtro3:

        numero_righe = st.selectbox(
            "Visualizza:",
            [20, 50, 100, 250, 500],
            index=0
        )

    logs_filtrati = []

    for evento in logs:

        azione = str(
            evento.get("azione", "")
        )

        testo_evento = " ".join(
            [
                str(evento.get("codice", "")),
                str(evento.get("nome", "")),
                str(evento.get("operatore", "")),
                str(evento.get("motivo", ""))
            ]
        ).lower()

        if filtro_azione != "Tutte":

            if filtro_azione not in azione:

                continue

        if (
            filtro_ricerca_log.strip()
            and filtro_ricerca_log.lower().strip()
            not in testo_evento
        ):

            continue

        logs_filtrati.append(
            evento
        )

    logs_filtrati = logs_filtrati[
        :numero_righe
    ]

    if not logs_filtrati:

        st.info(
            "Nessun movimento corrisponde ai filtri."
        )

    else:

        dati_storico = []

        for evento in logs_filtrati:

            dati_storico.append(
                {
                    "Data/Ora": evento.get(
                        "orario",
                        ""
                    ),
                    "Operazione": evento.get(
                        "azione",
                        ""
                    ),
                    "Codice": evento.get(
                        "codice",
                        ""
                    ),
                    "Articolo": evento.get(
                        "nome",
                        ""
                    ),
                    "Quantità": evento.get(
                        "quantita",
                        0
                    ),
                    "Operatore": evento.get(
                        "operatore",
                        ""
                    ),
                    "Motivo": evento.get(
                        "motivo",
                        ""
                    ),
                    "Scorta prima": evento.get(
                        "scorta_prima",
                        ""
                    ),
                    "Scorta dopo": evento.get(
                        "scorta_dopo",
                        ""
                    )
                }
            )

        df_log = st.dataframe(
            dati_storico,
            use_container_width=True,
            hide_index=True,
            height=500
        )


# ============================================================
# ESPORTAZIONE STORICO
# ============================================================

if logs:

    st.markdown("---")
    st.subheader("📤 Esporta dati")

    dati_export = []

    for evento in logs:

        dati_export.append(
            {
                "Data/Ora": evento.get(
                    "orario",
                    ""
                ),
                "Operazione": evento.get(
                    "azione",
                    ""
                ),
                "Codice": evento.get(
                    "codice",
                    ""
                ),
                "Articolo": evento.get(
                    "nome",
                    ""
                ),
                "Quantità": evento.get(
                    "quantita",
                    0
                ),
                "Operatore": evento.get(
                    "operatore",
                    ""
                ),
                "Motivo": evento.get(
                    "motivo",
                    ""
                ),
                "Scorta prima": evento.get(
                    "scorta_prima",
                    ""
                ),
                "Scorta dopo": evento.get(
                    "scorta_dopo",
                    ""
                )
            }
        )

    df_export = pd.DataFrame(
        dati_export
    )

    csv = df_export.to_csv(
        index=False
    ).encode(
        "utf-8-sig"
    )

    st.download_button(
        "📥 Scarica storico CSV",
        data=csv,
        file_name=(
            "storico_magazzino_"
            f"{datetime.now().strftime('%Y-%m-%d')}.csv"
        ),
        mime="text/csv",
        use_container_width=True
    )


# ============================================================
# AREA TITOLARE - DOWNLOAD DATABASE
# ============================================================

if st.session_state.autenticato:

    st.markdown("---")
    st.header("🔐 Strumenti Titolare")

    col_db, col_log, col_backup = st.columns(3)

    with col_db:

        if os.path.exists(DB_FILE):

            with open(
                DB_FILE,
                "rb"
            ) as f:

                st.download_button(
                    "📥 Scarica Database",
                    data=f,
                    file_name="stato_magazzino_backup.json",
                    mime="application/json",
                    use_container_width=True
                )

    with col_log:

        if os.path.exists(LOG_FILE):

            with open(
                LOG_FILE,
                "rb"
            ) as f:

                st.download_button(
                    "📥 Scarica Registro",
                    data=f,
                    file_name="storico_magazzino_backup.json",
                    mime="application/json",
                    use_container_width=True
                )

    with col_backup:

        if os.path.exists(BACKUP_DIR):

            try:

                numero_backup = len(
                    [
                        file
                        for file in os.listdir(
                            BACKUP_DIR
                        )
                        if file.endswith(".json")
                    ]
                )

            except Exception:

                numero_backup = 0

        else:

            numero_backup = 0

        st.metric(
            "💾 Backup disponibili",
            numero_backup
        )


# ============================================================
# ELIMINAZIONE ARTICOLO - AREA TITOLARE
# ============================================================

if st.session_state.autenticato:

    st.markdown("---")
    st.header("🗑️ Eliminazione Articolo")

    if inventario:

        elenco_elimina = [
            f"{codice} - {info['nome']}"
            for codice, info in inventario.items()
        ]

        prodotto_da_eliminare = st.selectbox(
            "Seleziona articolo:",
            elenco_elimina,
            key="elimina_articolo"
        )

        codice_el = trova_codice_da_selezione(
            prodotto_da_eliminare
        )

        info_el = inventario[
            codice_el
        ]

        st.warning(
            f"Stai per eliminare: "
            f"**{info_el['nome']}** "
            f"(codice {codice_el})"
        )

        if not st.session_state.conferma_eliminazione:

            if st.button(
                "🗑️ Elimina Definitivamente",
                type="primary",
                use_container_width=True
            ):

                st.session_state.codice_da_eliminare = codice_el
                st.session_state.conferma_eliminazione = True
                st.rerun()

        else:

            codice_conferma = (
                st.session_state.codice_da_eliminare
            )

            if (
                codice_conferma
                and codice_conferma in inventario
            ):

                nome_conferma = inventario[
                    codice_conferma
                ]["nome"]

                st.error(
                    f"⚠️ CONFERMA FINALE: eliminare "
                    f"**{nome_conferma}**?"
                )

                col_no, col_si = st.columns(2)

                with col_no:

                    if st.button(
                        "❌ Annulla",
                        use_container_width=True
                    ):

                        st.session_state.conferma_eliminazione = False
                        st.session_state.codice_da_eliminare = None
                        st.rerun()

                with col_si:

                    if st.button(
                        "✅ SÌ, ELIMINA",
                        type="primary",
                        use_container_width=True
                    ):

                        codice_finale = (
                            st.session_state.codice_da_eliminare
                        )

                        info_finale = inventario[
                            codice_finale
                        ]

                        scorta_finale = int(
                            info_finale.get(
                                "scorta",
                                0
                            )
                        )

                        crea_backup(DB_FILE)

                        del inventario[
                            codice_finale
                        ]

                        salva_magazzino(
                            inventario,
                            backup=False
                        )

                        aggiungi_evento(
                            "ELIMINATO (❌)",
                            codice_finale,
                            info_finale["nome"],
                            0,
                            "Titolare",
                            "Rimosso completamente dal catalogo",
                            scorta_finale,
                            0
                        )

                        st.session_state.conferma_eliminazione = False
                        st.session_state.codice_da_eliminare = None

                        st.success(
                            f"✅ {info_finale['nome']} "
                            f"eliminato definitivamente."
                        )

                        st.rerun()

    else:

        st.info(
            "Nessun articolo da eliminare."
        )


# ============================================================
# FOOTER
# ============================================================

st.markdown("---")

st.caption(
    "📦 Gestione Magazzino • "
    f"{datetime.now().strftime('%d/%m/%Y %H:%M')}"
)
