import streamlit as st
import pandas as pd
import os
from datetime import datetime

# =====================
# AUTHENTIFICATION
# =====================
if "login" not in st.session_state:
    st.session_state["login"] = False

def login(username, password):
    users = {
        "aurore": {"password": "12345", "name": "Aurore Demoulin"},
        "laure.froidefond": {"password": "Laure2019$", "name": "Laure Froidefond"},
        "Bruno": {"password": "Toto1963$", "name": "Toto El Gringo"},
    }
    if username in users and password == users[username]["password"]:
        st.session_state["login"] = True
        st.session_state["username"] = username
        st.session_state["name"] = users[username]["name"]
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
# APPLICATION PRINCIPALE
# =====================

st.title("📘 Générateur d'écritures de vente")
st.write("Importe un fichier Excel sans en-tête pour générer automatiquement les écritures comptables de ventes.")

uploaded_file = st.file_uploader("📂 Importer le fichier Excel des ventes", type=["xlsx"])

if uploaded_file:
    try:
        # Lecture sans en-tête
        df = pd.read_excel(uploaded_file, header=None)
        df = df.iloc[:, [2, 3, 4, 8, 9]]  # colonnes C, D, E, I, J
        df.columns = ["Date", "Facture", "Client", "TTC", "HT"]

        ecritures = []
        for _, row in df.iterrows():
            date = pd.to_datetime(str(row["Date"]), errors='coerce')
            if pd.isna(date):
                continue
            date_str = date.strftime("%d/%m/%Y")

            facture = str(row["Facture"])
            client = str(row["Client"]).strip().upper()
            montant_ttc = float(row["TTC"])
            montant_ht = float(row["HT"])
            montant_tva = round(montant_ttc - montant_ht, 2)

            # Détermination du taux de TVA
            if abs(montant_tva) < 0.01:
                compte_vente = "704500000"  # autoliquidation
            else:
                taux = round((montant_tva / montant_ht) * 100, 1)
                if abs(taux - 5.5) < 0.5:
                    compte_vente = "704000000"
                elif abs(taux - 10) < 0.5:
                    compte_vente = "704100000"
                elif abs(taux - 20) < 1:
                    compte_vente = "704200000"
                else:
                    compte_vente = "704300000"

            compte_client = f"4110{client[0]}0000" if client else "411000000"

            # Écritures
            ecritures.append({
                "Date": date_str,
                "Journal": "VT",
                "Numéro de pièce": facture,
                "Numéro de compte": compte_client,
                "Libellé": client,
                "Débit": round(montant_ttc, 2),
                "Crédit": ""
            })
            ecritures.append({
                "Date": date_str,
                "Journal": "VT",
                "Numéro de pièce": facture,
                "Numéro de compte": compte_vente,
                "Libellé": client,
                "Débit": "",
                "Crédit": round(montant_ht, 2)
            })
            if montant_tva > 0:
                ecritures.append({
                    "Date": date_str,
                    "Journal": "VT",
                    "Numéro de pièce": facture,
                    "Numéro de compte": "445740000",
                    "Libellé": client,
                    "Débit": "",
                    "Crédit": round(montant_tva, 2)
                })

        df_ecritures = pd.DataFrame(ecritures)

        # Sauvegarde fichier Excel de sortie
        output_filename = f"ecritures_ventes_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        df_ecritures.to_excel(output_filename, index=False)

        st.success("✅ Écritures générées avec succès !")
        st.download_button("📥 Télécharger le fichier Excel", data=open(output_filename, "rb"), file_name=output_filename)

        st.dataframe(df_ecritures.head(10))

    except Exception as e:
        st.error(f"❌ Erreur lors du traitement du fichier : {e}")
