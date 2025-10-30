import streamlit as st
import pandas as pd
import io

# =====================
# 🔐 AUTHENTIFICATION
# =====================

if "login" not in st.session_state:
    st.session_state["login"] = False
if "page" not in st.session_state:
    st.session_state["page"] = "Accueil"

def login(username, password):
    users = {
        "aurore": {"password": "12345", "name": "Aurore Demoulin"},
        "laure.froidefond": {"password": "Laure2019$", "name": "Laure Froidefond"},
        "Bruno": {"password": "Toto1963$", "name": "Toto El Gringo"}
    }
    if username in users and password == users[username]["password"]:
        st.session_state["login"] = True
        st.session_state["username"] = username
        st.session_state["name"] = users[username]["name"]
        st.session_state["page"] = "Accueil"
        st.success(f"Bienvenue {st.session_state['name']} 👋")
        st.rerun()
    else:
        st.error("❌ Identifiants incorrects")

if not st.session_state["login"]:
    st.title("🔑 Connexion espace expert-comptable")
    username_input = st.text_input("Identifiant")
    password_input = st.text_input("Mot de passe", type="password")
    if st.button("Connexion"):
        login(username_input, password_input)
    st.stop()

# =====================
# ⚙️ FONCTIONS UTILES
# =====================

def taux_tva(ht, ttc):
    if ht == 0:
        return 0
    taux = round((ttc / ht - 1) * 100, 1)
    if 5 <= taux <= 6:
        return 5.5
    elif 9 <= taux <= 11:
        return 10
    elif 19 <= taux <= 21:
        return 20
    else:
        return 0

def compte_vente(taux):
    if taux == 5.5:
        return "704000000"
    elif taux == 10:
        return "704100000"
    elif taux == 20:
        return "704200000"
    else:
        return "704500000"

def compte_client(nom):
    # simplification : 4110 + 1ère lettre du client
    lettre = nom.strip().upper()[:1]
    return f"4110{lettre}0000"

# =====================
# 🧾 INTERFACE PRINCIPALE
# =====================

st.title("📘 Génération d'écritures comptables ventes")
uploaded_file = st.file_uploader("📤 Importer le fichier Excel (sans en-têtes)", type=["xlsx"])

if uploaded_file:
    df = pd.read_excel(uploaded_file, header=None)

    # Vérification minimale du format
    if df.shape[1] < 10:
        st.error("⚠️ Le fichier doit contenir au moins 10 colonnes.")
        st.stop()

    # Attribution des colonnes utiles
    df = df.rename(columns={
        2: "Date",
        3: "Facture",
        4: "Client",
        8: "HT",
        9: "TTC"
    })

    # Nettoyage des dates
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce").dt.strftime("%d/%m/%Y")

    # Suppression des lignes vides
    df = df.dropna(subset=["Facture", "Client", "HT", "TTC"])

    ecritures = []
    desequilibres = []

    for _, row in df.iterrows():
        ht, ttc = row["HT"], row["TTC"]
        if ht == 0 and ttc == 0:
            continue

        tva = round(ttc - ht, 2)
        taux = taux_tva(ht, ttc)
        compte_vte = compte_vente(taux)
        compte_cli = compte_client(row["Client"])
        libelle = row["Client"]
        date = row["Date"]
        piece = row["Facture"]

        abs_ht, abs_tva, abs_ttc = abs(ht), abs(tva), abs(ttc)

        if ttc >= 0:
            # ✅ Facture normale
            ecritures.append({
                "Date": date, "Journal": "VT",
                "Numéro de compte": compte_cli, "Numéro de pièce": piece,
                "Libellé": libelle, "Débit": abs_ttc, "Crédit": ""
            })
            ecritures.append({
                "Date": date, "Journal": "VT",
                "Numéro de compte": compte_vte, "Numéro de pièce": piece,
                "Libellé": libelle, "Débit": "", "Crédit": abs_ht
            })
            if abs_tva > 0.01:
                ecritures.append({
                    "Date": date, "Journal": "VT",
                    "Numéro de compte": "445740000", "Numéro de pièce": piece,
                    "Libellé": libelle, "Débit": "", "Crédit": abs_tva
                })
        else:
            # ✅ Avoir
            ecritures.append({
                "Date": date, "Journal": "VT",
                "Numéro de compte": compte_cli, "Numéro de pièce": piece,
                "Libellé": libelle, "Débit": "", "Crédit": abs_ttc
            })
            ecritures.append({
                "Date": date, "Journal": "VT",
                "Numéro de compte": compte_vte, "Numéro de pièce": piece,
                "Libellé": libelle, "Débit": abs_ht, "Crédit": ""
            })
            if abs_tva > 0.01:
                ecritures.append({
                    "Date": date, "Journal": "VT",
                    "Numéro de compte": "445740000", "Numéro de pièce": piece,
                    "Libellé": libelle, "Débit": abs_tva, "Crédit": ""
                })

        if round(abs_ttc - (abs_ht + abs_tva), 2) != 0:
            desequilibres.append(row["Facture"])

    df_ecritures = pd.DataFrame(ecritures, columns=[
        "Date", "Journal", "Numéro de compte", "Numéro de pièce", "Libellé", "Débit", "Crédit"
    ])

    st.success("✅ Écritures générées avec succès")
    st.dataframe(df_ecritures.head(50), use_container_width=True)

    if desequilibres:
        st.warning(f"⚠️ {len(desequilibres)} écritures déséquilibrées : {set(desequilibres)}")

    # Export Excel
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df_ecritures.to_excel(writer, index=False, sheet_name="Ecritures")
    st.download_button(
        "💾 Télécharger le fichier des écritures",
        data=output.getvalue(),
        file_name="ecritures_comptables.xlsx"
    )
