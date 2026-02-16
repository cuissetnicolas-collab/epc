import streamlit as st
import pandas as pd
from io import BytesIO

# ============================================================
# 🔐 AUTHENTIFICATION
# ============================================================

if "login" not in st.session_state:
    st.session_state["login"] = False
if "page" not in st.session_state:
    st.session_state["page"] = "Accueil"

USERS = {
    "aurore": {"password": "12345", "name": "Aurore Demoulin"},
    "laure.froidefond": {"password": "Laure2019$", "name": "Laure Froidefond"},
    "Bruno": {"password": "Toto1963$", "name": "Toto El Gringo"},
    "Manana": {"password": "193827", "name": "Manana"}
}

def login(username, password):
    if username in USERS and password == USERS[username]["password"]:
        st.session_state["login"] = True
        st.session_state["username"] = username
        st.session_state["name"] = USERS[username]["name"]
        st.session_state["page"] = "Accueil"
        st.success(f"Bienvenue {st.session_state['name']} 👋")
        st.stop()
    else:
        st.error("❌ Identifiants incorrects")

if not st.session_state["login"]:
    st.title("🔑 Connexion espace expert-comptable")
    username_input = st.text_input("Identifiant")
    password_input = st.text_input("Mot de passe", type="password")
    if st.button("Connexion"):
        login(username_input, password_input)
    st.stop()

# ============================================================
# 🎯 PAGE PRINCIPALE
# ============================================================

st.set_page_config(page_title="Générateur écritures ventes", page_icon="📘", layout="centered")
st.title("📘 Générateur d'écritures comptables de ventes")
st.caption(f"Connecté en tant que **{st.session_state['name']}**")

if st.button("🔓 Déconnexion"):
    st.session_state["login"] = False
    st.stop()

st.write(
    "Charge un fichier Excel avec les colonnes : "
    "`N° Facture`, `Date`, `Nom Facture`, `Total HT`, `Taux de tva`, `Total TTC`"
)
uploaded_file = st.file_uploader("📂 Fichier Excel", type=["xls", "xlsx"])

if uploaded_file:
    df = pd.read_excel(uploaded_file, dtype=str)

    # Vérification des colonnes nécessaires
    expected_cols = ["N° Facture", "Date", "Nom Facture", "Total HT", "Taux de tva", "Total TTC"]
    if not all(col in df.columns for col in expected_cols):
        st.error(f"❌ Fichier non conforme : il doit contenir les colonnes {expected_cols}")
        st.stop()

    # Nettoyage montants
    def clean_amount(x):
        if pd.isna(x):
            return 0.0
        x = str(x).replace(",", ".").replace("€", "").replace(" ", "").strip()
        try:
            return float(x)
        except ValueError:
            return 0.0

    df["Total HT"] = df["Total HT"].apply(clean_amount)
    df["Total TTC"] = df["Total TTC"].apply(clean_amount)
    df["Taux de tva"] = df["Taux de tva"].apply(clean_amount)
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce").dt.strftime("%d/%m/%Y").fillna("")

    # --- Regroupement par facture ---
    df_grouped = df.groupby(["N° Facture", "Date", "Nom Facture"], as_index=False).agg({
        "Total HT": "sum",
        "Total TTC": "sum",
        "Taux de tva": "first"  # On prend le premier taux pour la facture (ou tu peux gérer multi-TVA plus tard)
    })

    # Fonctions utilitaires
    def compte_client(nom):
        nom = str(nom).strip().upper()
        lettre = nom[0] if nom and nom[0].isalpha() else "X"
        return f"4110{lettre}0000"

    def compte_vente(taux):
        comptes = {5.5: "704000000", 10: "704100000", 20: "704200000", 0: "704500000", "multi": "704300000"}
        return comptes.get(taux, "704300000")

    # === Génération des écritures par facture ===
    ecritures = []
    desequilibres = []

    for _, row in df_grouped.iterrows():
        ht, ttc, tva_rate = row["Total HT"], row["Total TTC"], row["Taux de tva"]
        if ht == 0 and ttc == 0:
            continue
        tva = round(ttc - ht, 2)
        compte_vte = compte_vente(tva_rate)
        compte_cli = compte_client(row["Nom Facture"])
        date = row["Date"]
        piece = row["N° Facture"]
        libelle = f"{'Facture' if ttc >=0 else 'Avoir'} {piece} - {row['Nom Facture']}"

        if ttc >= 0:
            ecritures.append({"Date": date, "Journal": "VT", "Numéro de compte": compte_cli,
                              "Numéro de pièce": piece, "Libellé": libelle, "Débit": round(ttc,2), "Crédit": ""})
            ecritures.append({"Date": date, "Journal": "VT", "Numéro de compte": compte_vte,
                              "Numéro de pièce": piece, "Libellé": libelle, "Débit": "", "Crédit": round(ht,2)})
            if abs(tva) > 0.01:
                ecritures.append({"Date": date, "Journal": "VT", "Numéro de compte": "445740000",
                                  "Numéro de pièce": piece, "Libellé": libelle, "Débit": "", "Crédit": round(tva,2)})
        else:
            ttc_abs, ht_abs, tva_abs = abs(ttc), abs(ht), abs(tva)
            ecritures.append({"Date": date, "Journal": "VT", "Numéro de compte": compte_cli,
                              "Numéro de pièce": piece, "Libellé": libelle, "Débit": "", "Crédit": round(ttc_abs,2)})
            ecritures.append({"Date": date, "Journal": "VT", "Numéro de compte": compte_vte,
                              "Numéro de pièce": piece, "Libellé": libelle, "Débit": round(ht_abs,2), "Crédit": ""})
            if abs(tva) > 0.01:
                ecritures.append({"Date": date, "Journal": "VT", "Numéro de compte": "445740000",
                                  "Numéro de pièce": piece, "Libellé": libelle, "Débit": round(tva_abs,2), "Crédit": ""})

        if abs(ttc - (ht + tva)) > 0.01:
            desequilibres.append(piece)

    df_out = pd.DataFrame(ecritures, columns=["Date", "Journal", "Numéro de compte",
                                              "Numéro de pièce", "Libellé", "Débit", "Crédit"])

    # === Résumé ===
    st.success(f"✅ {len(df_grouped)} factures → {len(df_out)} écritures générées.")
    if desequilibres:
        st.warning(f"⚠️ Factures déséquilibrées : {', '.join(map(str, desequilibres[:5]))}")

    st.subheader("Aperçu des premières écritures")
    st.dataframe(df_out.head(10))

    # Totaux
    total_debit = df_out["Débit"].apply(pd.to_numeric, errors="coerce").sum()
    total_credit = df_out["Crédit"].apply(pd.to_numeric, errors="coerce").sum()
    st.info(f"**Total Débit :** {total_debit:,.2f} € | **Total Crédit :** {total_credit:,.2f} € | **Écart :** {total_debit - total_credit:,.2f} €")

    # Export Excel
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl", date_format="DD/MM/YYYY") as writer:
        df_out.to_excel(writer, index=False, sheet_name="Écritures")
    output.seek(0)

    st.download_button(
        "💾 Télécharger les écritures générées",
        data=output,
        file_name="ecritures_ventes.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

else:
    st.info("⬆️ Charge ton fichier Excel pour commencer.")
