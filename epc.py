import streamlit as st
import pandas as pd
import io

# =====================
# AUTHENTIFICATION
# =====================
if "login" not in st.session_state:
    st.session_state["login"] = False

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
st.title("💼 Générateur d’écritures comptables - Ventes")

uploaded_file = st.file_uploader("Choisir un fichier Excel", type=["xlsx"])

if uploaded_file:
    try:
        df = pd.read_excel(uploaded_file, header=None)
    except Exception as e:
        st.error(f"Erreur lors de la lecture du fichier : {e}")
        st.stop()

    # Supposons que les colonnes soient dans un ordre fixe sans en-têtes
    df.columns = [
        "Date", "Client", "Facture", "HT", "TTC", "TVA"
    ]

    df["Date"] = pd.to_datetime(df["Date"], errors="coerce").dt.strftime("%d/%m/%Y")

    # Création du dataframe d’écritures
    ecritures = []

    for _, row in df.iterrows():
        date = row["Date"]
        client = str(row["Client"])
        facture = str(row["Facture"])
        ht = float(row["HT"])
        ttc = float(row["TTC"])
        tva = float(row["TVA"]) if not pd.isna(row["TVA"]) else 0.0

        # Détermination du taux de TVA
        taux = round((tva / ht) * 100, 1) if ht != 0 else 0
        if abs(taux - 5.5) < 1:
            compte_vente = "704000000"
        elif abs(taux - 10) < 1:
            compte_vente = "704100000"
        elif abs(taux - 20) < 1:
            compte_vente = "704200000"
        else:
            compte_vente = "704500000"

        compte_client = "4110" + client[:1].upper() + "0000"

        # Ligne client (TTC)
        ecritures.append({
            "Date": date,
            "Journal": "VT",
            "Compte": compte_client,
            "Pièce": facture,
            "Libellé": f"Facture {facture} - {client}",
            "Débit": round(ttc, 2) if ttc > 0 else "",
            "Crédit": round(abs(ttc), 2) if ttc < 0 else ""
        })

        # Ligne produit (HT)
        ecritures.append({
            "Date": date,
            "Journal": "VT",
            "Compte": compte_vente,
            "Pièce": facture,
            "Libellé": f"Facture {facture} - {client}",
            "Débit": round(abs(ht), 2) if ht < 0 else "",
            "Crédit": round(ht, 2) if ht > 0 else ""
        })

        # Ligne TVA (si applicable)
        if tva != 0:
            ecritures.append({
                "Date": date,
                "Journal": "VT",
                "Compte": "445740000",
                "Pièce": facture,
                "Libellé": f"Facture {facture} - {client}",
                "Débit": round(abs(tva), 2) if tva < 0 else "",
                "Crédit": round(tva, 2) if tva > 0 else ""
            })

    ecritures_df = pd.DataFrame(ecritures)

    st.subheader("📋 Aperçu des écritures générées")
    st.dataframe(ecritures_df.head(20))

    # Export Excel
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        ecritures_df.to_excel(writer, index=False, sheet_name="Ecritures")

    st.download_button(
        label="⬇️ Télécharger le fichier d'écritures",
        data=output.getvalue(),
        file_name="ecritures_comptables.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
