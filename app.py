
import streamlit as st
import json
import os
import re
import shutil
import pandas as pd

from datetime import datetime


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

# Soglia fissa per l'allarme rosso
SOGLIA_ULTIME_SCORTE = 6

# Numero massimo di operazioni conservate nello storico
MAX_LOG = 500

# Password di emergenza/fallback.
# Se hai ADMIN_PASSWORD nei Secrets di Streamlit,
# quella avrà la precedenza.
PASSWORD_FALLBACK = "Samuelmark123#"


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
        color: #777777;
        margin-bottom: 1.5rem;
    }

    /* --------------------------------------------------------
       BOX SCORTE
       -------------------------------------------------------- */

    .stock-critical {
        padding: 15px;
        border-radius: 10px;
        background-color: #ffe5e5;
        border: 2px solid #dc3545;
        color: #111111 !important;
        margin-bottom: 10px;
    }

    .stock-warning {
        padding: 15px;
        border-radius: 10px;
        background-color: #fff0d6;
        border: 2px solid #f0ad4e;
        color: #111111 !important;
        margin-bottom: 10px;
    }

    .stock-ok {
        padding: 15px;
        border-radius: 10px;
        background-color: #e5f6ea;
        border: 2px solid #198754;
        color: #111111 !important;
        margin-bottom: 10px;
    }

    .stock-critical *,
    .stock-warning *,
    .stock-ok * {
        color: #111111 !important;
    }

    /* --------------------------------------------------------
       BOX AVVISI
       -------------------------------------------------------- */

    .danger-box {
        padding: 15px;
        border-radius: 10px;
        background-color: #ffe5e5;
        border-left: 6px solid #dc3545;
        color: #111111 !important;
        margin-bottom: 10px;
    }

    .warning-box {
        padding: 15px;
        border-radius: 10px;
        background-color: #fff0d6;
        border-left: 6px solid #f0ad4e;
        color: #111111 !important;
        margin-bottom: 10px;
    }

    .success-box {
        padding: 15px;
        border-radius: 10px;
        background-color: #e5f6ea;
        border-left: 6px solid #198754;
        color: #111111 !important;
        margin-bottom: 10px;
    }

    .danger-box *,
    .warning-box *,
    .success-box * {
        color: #111111 !important;
    }

    /* --------------------------------------------------------
       PASSWORD
       -------------------------------------------------------- */

    button[title="Show password"],
    button[title="Hide password"] {
        display: none !important;
    }

    input[type="password"]::-ms-reveal {
        display: none !important;
    }

    /* --------------------------------------------------------
       MOBILE
       -------------------------------------------------------- */

    @media (max-width: 768px) {

        .main-title {
            font-size: 1.8rem;
        }

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
            return str(
                st.secrets["ADMIN_PASSWORD"]
            )

    except Exception:
        pass

    return PASSWORD_FALLBACK


# ============================================================
# BACKUP
# ============================================================

def crea_backup(file_da_salvare):

    if not os.path.exists(file_da_salvare):
        return None

    try:

        os.makedirs(
            BACKUP_DIR,
            exist_ok=True
        )

        nome_file = os.path.basename(
            file_da_salvare
        )

        timestamp = datetime.now().strftime(
            "%Y-%m-%d_%H-%M-%S-%f"
        )

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
# DATABASE MAGAZZINO
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


def normalizza_inventario(dati):

    if not isinstance(dati, dict):
        return {}

    risultato = {}

    for codice, info in dati.items():

        codice = str(codice).strip()

        if not codice:
            continue

        if not isinstance(info, dict):

            risultato[codice] = {
                "nome": str(info),
                "scorta": 0,
                "soglia_minima": 5
            }

            continue

        nome = str(
            info.get(
                "nome",
                codigo_se_nome_mancante(codice)
            )
        ).strip()

        try:
            scorta = int(
                float(
                    info.get(
                        "scorta",
                        0
                    )
                )
            )
        except Exception:
            scorta = 0

        try:
            soglia = int(
                float(
                    info.get(
                        "soglia_minima",
                        5
                    )
                )
            )
        except Exception:
            soglia = 5

        scorta = max(
            0,
            scorta
        )

        soglia = max(
            0,
            soglia
        )

        risultato[codice] = {
            "nome": nome if nome else codice,
            "scorta": scorta,
            "soglia_minima": soglia
        }

    return risultato


def codigo_se_nome_mancante(codice):

    return f"Articolo {codice}"


def carica_magazzino():

    if not os.path.exists(DB_FILE):

        return database_predefinito()

    try:

        with open(
            DB_FILE,
            "r",
            encoding="utf-8"
        ) as f:

            dati = json.load(f)

        return normalizza_inventario(
            dati
        )

    except Exception as e:

        st.error(
            "⚠️ Non è stato possibile leggere "
            f"'{DB_FILE}'."
        )

        st.caption(
            f"Dettaglio tecnico: {e}"
        )

        return {}


def salva_magazzino(
    inventario,
    backup=True
):

    try:

        if backup and os.path.exists(DB_FILE):
            crea_backup(DB_FILE)

        with open(
            DB_FILE,
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                inventario,
                f,
                indent=4,
                ensure_ascii=False
            )

        return True

    except Exception as e:

        st.error(
            f"❌ Errore durante il salvataggio: {e}"
        )

        return False


# ============================================================
# DATABASE STORICO
# ============================================================

def carica_log():

    if not os.path.exists(LOG_FILE):
        return []

    try:

        with open(
            LOG_FILE,
            "r",
            encoding="utf-8"
        ) as f:

            dati = json.load(f)

        if isinstance(dati, list):
            return dati

        return []

    except Exception as e:

        st.warning(
            "⚠️ Il registro storico non è leggibile."
        )

        return []


def salva_log(
    lista_log,
    backup=True
):

    try:

        if backup and os.path.exists(LOG_FILE):
            crea_backup(LOG_FILE)

        with open(
            LOG_FILE,
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                lista_log[:MAX_LOG],
                f,
                indent=4,
                ensure_ascii=False
            )

        return True

    except Exception as e:

        st.error(
            f"❌ Errore durante il salvataggio dello storico: {e}"
        )

        return False


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
        "azione": str(azione),
        "codice": str(codice),
        "nome": str(nome),
        "quantita": int(quantita),
        "operatore": str(operatore),
        "motivo": str(motivo),
        "scorta_prima": scorta_prima,
        "scorta_dopo": scorta_dopo
    }

    logs.insert(
        0,
        evento
    )

    salva_log(
        logs,
        backup=False
    )


# ============================================================
# FUNZIONI UTILI
# ============================================================

def pulisci_codice(codice):

    codice = str(codice).strip()

    codice = re.sub(
        r"\s+",
        "",
        codice
    )

    return codice


def trova_codice_da_selezione(selezione):

    if not selezione:
        return None

    return str(
        selezione
    ).split(
        " - ",
        1
    )[0].strip()


def formatta_operatore(
    cuoco,
    cameriere
):

    firme = []

    if str(cuoco).strip():

        firme.append(
            f"Kock: {str(cuoco).strip()}"
        )

    if str(cameriere).strip():

        firme.append(
            f"Servering: {str(cameriere).strip()}"
        )

    if firme:
        return " & ".join(firme)

    return "Non specificato"


def stato_scorta(
    scorta,
    soglia
):

    if scorta <= SOGLIA_ULTIME_SCORTE:
        return "critica"

    if scorta <= soglia:
        return "bassa"

    return "ok"


def get_critici(inventario):

    return {
        codice: info
        for codice, info in inventario.items()
        if int(info.get("scorta", 0))
        <= SOGLIA_ULTIME_SCORTE
    }


def get_da_riordinare(inventario):

    return {
        codice: info
        for codice, info in inventario.items()
        if int(info.get("scorta", 0))
        <= int(
            info.get(
                "soglia_minima",
                5
            )
        )
    }


# ============================================================
# CARICAMENTO DATI
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
# SIDEBAR - ACCESSO TITOLARE
# ============================================================

st.sidebar.header(
    "🔐 Area Riservata Titolare"
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
        st.session_state.codice_da_eliminare = None

        st.rerun()


# ============================================================
# SIDEBAR - GESTIONE ARTICOLI
# ============================================================

if st.session_state.autenticato:

    st.sidebar.markdown("---")

    st.sidebar.header(
        "📦 Gestione Articoli"
    )

    tab_nuovo, tab_modifica = st.sidebar.tabs(
        [
            "➕ Nuovo",
            "✏️ Modifica"
        ]
    )

    # ========================================================
    # NUOVO ARTICOLO
    # ========================================================

    with tab_nuovo:

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

                scorta_iniziale = int(
                    nuova_scorta
                )

                soglia_iniziale = int(
                    nuova_soglia
                )

                inventario[codice] = {
                    "nome": nome,
                    "scorta": scorta_iniziale,
                    "soglia_minima": soglia_iniziale
                }

                if salva_magazzino(
                    inventario
                ):

                    aggiungi_evento(
                        "NUOVO ARTICOLO (➕)",
                        codice,
                        nome,
                        scorta_iniziale,
                        "Titolare",
                        "Nuovo articolo creato",
                        0,
                        scorta_iniziale
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
                for codice, info
                in inventario.items()
            ]

            articolo_modifica = st.selectbox(
                "Articolo:",
                elenco_modifica,
                key="articolo_modifica"
            )

            codice_modifica = (
                trova_codice_da_selezione(
                    articolo_modifica
                )
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

                nuovo_codice_modificato = (
                    pulisci_codice(
                        nuovo_codice_modificato
                    )
                )

                nome_modificato = (
                    nome_modificato.strip()
                )

                if not nuovo_codice_modificato:

                    st.error(
                        "Il codice non può essere vuoto."
                    )

                elif not nome_modificato:

                    st.error(
                        "Il nome non può essere vuoto."
                    )

                elif (
                    nuovo_codice_modificato
                    != codice_modifica
                    and nuovo_codice_modificato
                    in inventario
                ):

                    st.error(
                        "❌ Il nuovo codice esiste già."
                    )

                else:

                    scorta_attuale = int(
                        info_modifica.get(
                            "scorta",
                            0
                        )
                    )

                    inventario.pop(
                        codice_modifica
                    )

                    inventario[
                        nuovo_codice_modificato
                    ] = {
                        "nome": nome_modificato,
                        "scorta": scorta_attuale,
                        "soglia_minima": int(
                            soglia_modificata
                        )
                    }

                    if salva_magazzino(
                        inventario
                    ):

                        aggiungi_evento(
                            "MODIFICA ARTICOLO (✏️)",
                            nuovo_codice_modificato,
                            nome_modificato,
                            0,
                            "Titolare",
                            (
                                f"Modifica da codice "
                                f"{codice_modifica}"
                            ),
                            scorta_attuale,
                            scorta_attuale
                        )

                        st.success(
                            "✅ Articolo modificato."
                        )

                        st.rerun()

        else:

            st.info(
                "Nessun articolo presente."
            )


# ============================================================
# DASHBOARD
# ============================================================

st.markdown("---")

st.header(
    "📊 Situazione Magazzino"
)

numero_articoli = len(
    inventario
)

pezzi_totali = sum(
    int(
        info.get(
            "scorta",
            0
        )
    )
    for info in inventario.values()
)

critici = get_critici(
    inventario
)

da_riordinare = get_da_riordinare(
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
# ALLARME ULTIME 6
# ============================================================

if critici:

    st.markdown(
        f"""
        <div class="danger-box">
        <strong>🚨 ATTENZIONE — ULTIME SCORTE!</strong><br>
        Ci sono <strong>{len(critici)}</strong>
        articoli con {SOGLIA_ULTIME_SCORTE} pezzi
        o meno.
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
            — Codice: {codice}<br>
            Rimasti:
            <strong>{info['scorta']} pz</strong>
            </div>
            """,
            unsafe_allow_html=True
        )


# ============================================================
# AVVISO DA RIORDINARE
# ============================================================

solo_warning = {
    codice: info
    for codice, info
    in da_riordinare.items()
    if codice not in critici
}

if solo_warning:

    st.markdown(
        f"""
        <div class="warning-box">
        <strong>🟠 ARTICOLI DA RIORDINARE</strong><br>
        Ci sono <strong>{len(solo_warning)}</strong>
        articoli che hanno raggiunto la soglia minima.
        </div>
        """,
        unsafe_allow_html=True
    )


# ============================================================
# SCARICO RAPIDO
# ============================================================

st.markdown("---")

st.header(
    "🛒 Scarico Rapido"
)

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
        for codice, info
        in inventario.items()
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
        "Es. Servizio pranzo, cena, "
        "scaduto, rotto..."
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

        codice_prelievo = (
            trova_codice_da_selezione(
                prodotto_selezionato
            )
        )

    if not codice_prelievo:

        st.error(
            "❌ Seleziona un prodotto "
            "o inserisci un codice."
        )

    elif codice_prelievo not in inventario:

        st.error(
            f"❌ Codice {codice_prelievo} "
            "non trovato."
        )

    else:

        info = inventario[
            codice_prelievo
        ]

        scorta_prima = int(
            info.get(
                "scorta",
                0
            )
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

            inventario[
                codice_prelievo
            ]["scorta"] = scorta_dopo

            if salva_magazzino(
                inventario
            ):

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
                    f"✅ Prelevati {quantita} pz "
                    f"di {info['nome']}."
                )

                if scorta_dopo <= SOGLIA_ULTIME_SCORTE:

                    st.error(
                        f"🚨 ATTENZIONE: rimangono "
                        f"soltanto {scorta_dopo} pz "
                        f"di {info['nome']}!"
                    )

                elif scorta_dopo <= int(
                    info.get(
                        "soglia_minima",
                        5
                    )
                ):

                    st.warning(
                        f"⚠️ {info['nome']} è "
                        f"sotto la soglia minima: "
                        f"{scorta_dopo} pz."
                    )

                st.rerun()


# ============================================================
# INVENTARIO ATTUALE
# ============================================================

st.markdown("---")

st.header(
    "📦 Scorte Attuali"
)

ricerca = st.text_input(
    "🔎 Cerca articolo per nome o codice:",
    placeholder="Es. mozzarella oppure 101",
    key="ricerca_scorte"
)

inventario_visualizzato = {}

for codice, info in inventario.items():

    testo_ricerca = (
        f"{codice} {info['nome']}"
    ).lower()

    if (
        not ricerca.strip()
        or ricerca.lower().strip()
        in testo_ricerca
    ):

        inventario_visualizzato[
            codice
        ] = info


if not inventario_visualizzato:

    st.info(
        "Nessun articolo trovato."
    )

else:

    # Prima i prodotti con meno pezzi
    inventario_visualizzato = dict(
        sorted(
            inventario_visualizzato.items(),
            key=lambda item: (
                int(
                    item[1].get(
                        "scorta",
                        0
                    )
                ),
                str(
                    item[1].get(
                        "nome",
                        ""
                    )
                ).lower()
            )
        )
    )

    for codice, info in inventario_visualizzato.items():

        scorta = int(
            info.get(
                "scorta",
                0
            )
        )

        soglia = int(
            info.get(
                "soglia_minima",
                5
            )
        )

        stato = stato_scorta(
            scorta,
            soglia
        )

        col_info, col_azioni = st.columns(
            [3, 1]
        )

        # ----------------------------------------------------
        # ARTICOLO
        # ----------------------------------------------------

        with col_info:

            if stato == "critica":

                st.markdown(
                    f"""
                    <div class="stock-critical">
                    🔴 <strong>ULTIME 6 SCORTE!</strong><br><br>
                    <strong>{info['nome']}</strong><br>
                    Codice: {codice}<br>
                    Rimasti:
                    <strong>{scorta} pz</strong>
                    </div>
                    """,
                    unsafe_allow_html=True
                )

            elif stato == "bassa":

                st.markdown(
                    f"""
                    <div class="stock-warning">
                    🟠 <strong>DA RIORDINARE</strong><br><br>
                    <strong>{info['nome']}</strong><br>
                    Codice: {codice}<br>
                    Rimasti:
                    <strong>{scorta} pz</strong><br>
                    Soglia minima:
                    <strong>{soglia} pz</strong>
                    </div>
                    """,
                    unsafe_allow_html=True
                )

            else:

                st.markdown(
                    f"""
                    <div class="stock-ok">
                    🟢 <strong>DISPONIBILE</strong><br><br>
                    <strong>{info['nome']}</strong><br>
                    Codice: {codice}<br>
                    Rimasti:
                    <strong>{scorta} pz</strong><br>
                    Soglia minima:
                    <strong>{soglia} pz</strong>
                    </div>
                    """,
                    unsafe_allow_html=True
                )

        # ----------------------------------------------------
        # AZIONE RAPIDA
        # ----------------------------------------------------

        with col_azioni:

            st.write("")

            if st.button(
                "➖ 1 pezzo",
                key=f"scarico_rapido_{codice}",
                use_container_width=True
            ):

                if scorta <= 0:

                    st.error(
                        "Scorta già a zero."
                    )

                else:

                    nuova_scorta = (
                        scorta - 1
                    )

                    inventario[
                        codice
                    ]["scorta"] = nuova_scorta

                    if salva_magazzino(
                        inventario
                    ):

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


# ============================================================
# STORICO
# ============================================================

st.markdown("---")

st.header(
    "📜 Registro Storico Merci"
)

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
            ],
            key="filtro_azione"
        )

    with col_filtro2:

        filtro_ricerca_log = st.text_input(
            "🔎 Cerca nello storico:",
            placeholder="Nome, codice, operatore...",
            key="filtro_ricerca_log"
        )

    with col_filtro3:

        numero_righe = st.selectbox(
            "Visualizza:",
            [
                20,
                50,
                100,
                250,
                500
            ],
            index=0,
            key="numero_righe"
        )

    logs_filtrati = []

    for evento in logs:

        azione = str(
            evento.get(
                "azione",
                ""
            )
        )

        testo_evento = " ".join(
            [
                str(
                    evento.get(
                        "codice",
                        ""
                    )
                ),
                str(
                    evento.get(
                        "nome",
                        ""
                    )
                ),
                str(
                    evento.get(
                        "operatore",
                        ""
                    )
                ),
                str(
                    evento.get(
                        "motivo",
                        ""
                    )
                )
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
        :int(numero_righe)
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

        df_log = pd.DataFrame(
            dati_storico
        )

        st.dataframe(
            df_log,
            use_container_width=True,
            hide_index=True,
            height=500
        )


# ============================================================
# ESPORTAZIONE CSV
# ============================================================

if logs:

    st.markdown("---")

    st.subheader(
        "📤 Esporta Storico"
    )

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
# STRUMENTI TITOLARE
# ============================================================

if st.session_state.autenticato:

    st.markdown("---")

    st.header(
        "🔐 Strumenti Titolare"
    )

    col_db, col_log, col_backup = st.columns(3)

    # --------------------------------------------------------
    # DOWNLOAD DATABASE
    # --------------------------------------------------------

    with col_db:

        if os.path.exists(DB_FILE):

            try:

                with open(
                    DB_FILE,
                    "rb"
                ) as f:

                    dati_db_download = f.read()

                st.download_button(
                    "📥 Scarica Database",
                    data=dati_db_download,
                    file_name="stato_magazzino_backup.json",
                    mime="application/json",
                    use_container_width=True
                )

            except Exception:

                st.error(
                    "Impossibile scaricare il database."
                )

    # --------------------------------------------------------
    # DOWNLOAD STORICO
    # --------------------------------------------------------

    with col_log:

        if os.path.exists(LOG_FILE):

            try:

                with open(
                    LOG_FILE,
                    "rb"
                ) as f:

                    dati_log_download = f.read()

                st.download_button(
                    "📥 Scarica Registro",
                    data=dati_log_download,
                    file_name="storico_magazzino_backup.json",
                    mime="application/json",
                    use_container_width=True
                )

            except Exception:

                st.error(
                    "Impossibile scaricare lo storico."
                )

    # --------------------------------------------------------
    # BACKUP
    # --------------------------------------------------------

    with col_backup:

        if os.path.exists(
            BACKUP_DIR
        ):

            try:

                numero_backup = len(
                    [
                        file
                        for file
                        in os.listdir(
                            BACKUP_DIR
                        )
                        if file.endswith(
                            ".json"
                        )
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
# ELIMINAZIONE ARTICOLO
# ============================================================

if st.session_state.autenticato:

    st.markdown("---")

    st.header(
        "🗑️ Eliminazione Articolo"
    )

    if inventario:

        elenco_elimina = [
            f"{codice} - {info['nome']}"
            for codice, info
            in inventario.items()
        ]

        prodotto_da_eliminare = st.selectbox(
            "Seleziona articolo:",
            elenco_elimina,
            key="elimina_articolo"
        )

        codice_el = trova_codice_da_selezione(
            prodotto_da_eliminare
        )

        if (
            codice_el
            and codice_el in inventario
        ):

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

                    st.session_state.codice_da_eliminare = (
                        codice_el
                    )

                    st.session_state.conferma_eliminazione = (
                        True
                    )

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
                        f"⚠️ CONFERMA FINALE: "
                        f"eliminare **{nome_conferma}**?"
                    )

                    col_no, col_si = st.columns(2)

                    with col_no:

                        if st.button(
                            "❌ Annulla",
                            use_container_width=True
                        ):

                            st.session_state.conferma_eliminazione = (
                                False
                            )

                            st.session_state.codice_da_eliminare = (
                                None
                            )

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

                            nome_finale = (
                                info_finale["nome"]
                            )

                            del inventario[
                                codice_finale
                            ]

                            if salva_magazzino(
                                inventario
                            ):

                                aggiungi_evento(
                                    "ELIMINATO (❌)",
                                    codice_finale,
                                    nome_finale,
                                    0,
                                    "Titolare",
                                    "Rimosso completamente dal catalogo",
                                    scorta_finale,
                                    0
                                )

                                st.session_state.conferma_eliminazione = (
                                    False
                                )

                                st.session_state.codice_da_eliminare = (
                                    None
                                )

                                st.success(
                                    f"✅ {nome_finale} "
                                    "eliminato definitivamente."
                                )

                                st.rerun()

    else:

        st.info(
            "Nessun articolo da eliminare."
        )


# ============================================================
# INFORMAZIONI FINALI
# ============================================================

st.markdown("---")

st.caption(
    "📦 Gestione Magazzino • "
    f"Aggiornato il {datetime.now().strftime('%d/%m/%Y %H:%M')}"
)
