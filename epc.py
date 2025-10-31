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

def login(username, password):
    users = {
        "aurore": {"password": "12345", "name": "Aurore Demoulin"},
        "laure.froidefond": {"password": "Laure2019$", "name": "Laure Froidefond"},
        "Bruno": {"password": "Toto1963$", "name": "Toto El Gringo"},
        "Manana": {"password": "193827", "name": "Manana"}
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

# ============================================================
# 🎯 PAGE PRINCIPALE
# ============================================================
st.set_page_config(page_title="Générateur écritures ventes", page_icon="📘", layout="centered")
st.title("📘 Générateur d'écritures comptables de ventes")
st.caption(f"Connecté en tant que **{st.session_state['name']}**")

if st.button("🔓 Déconnexion"):
    st.session_state["login"] = False
    st.rerun()

st.write("Charge un fichier Excel **sans en-tête** contenant les colonnes C à J.")

uploaded_file = st.file_uploader("📂 Fichier Excel", type=["xls", "xlsx"])

if uploaded_file:
    df = pd.read_excel(uploaded_file, header=None, dtype=str)
    
    try:
        # Colonnes utiles : C, D, E, I, J
        df = df.iloc[:, [2, 3, 4, 8, 9]]
        df.columns = ["Date", "Facture", "Client", "HT", "TTC"]
    except Exception:
        st.error("❌ Fichier non conforme : il doit contenir au moins 10 colonnes.")
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
    
    df["HT"] = df["HT"].apply(clean_amount)
    df["TTC"] = df["TTC"].apply(clean_amount)
    
    # Nettoyage dates
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce").dt.strftime("%d/%m/%Y").fillna("")
    
    # === Fonctions utilitaires ===
    def compte_client(nom):
        nom = str(nom).strip().upper()
        lettre = nom[0] if nom and nom[0].isalpha() else "X"
        return f"4110{lettre}0000"
    
    def taux_tva(ht, ttc):
        if ht == 0:
            return 0
        taux_calc = round((ttc / ht - 1) * 100, 1)
        if abs(taux_calc - 20) < 0.6:
            return 20
        elif abs(taux_calc - 10) < 0.6:
            return 10
        elif abs(taux_calc - 5.5) < 0.4:
            return 5.5
        elif abs(ttc - ht) < 0.02:
            return 0
        else:
            return "multi"
    
    def compte_vente(taux):
        comptes = {
            5.5: "704000000",
            10: "704100000",
            20: "704200000",
            0: "704500000",
            "multi": "704300000"
        }
        return comptes[taux]
    
    # === Génération des écritures ===
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
        date = row["Date"]
        piece = row["Facture"]

        # 🔹 Libellé : "Facture" ou "Avoir" selon le signe
        if ttc >= 0:
            libelle = f"Facture {piece} - {row['Client']}"
        else:
            libelle = f"Avoir {piece} - {row['Client']}"

        # === Facture normale ===
        if ttc >= 0:
            ecritures.append({"Date": date, "Journal": "VT", "Numéro de compte": compte_cli,
                               "Numéro de pièce": piece, "Libellé": libelle, "Débit": round(ttc,2), "Crédit": ""})
            ecritures.append({"Date": date, "Journal": "VT", "Numéro de compte": compte_vte,
                               "Numéro de pièce": piece, "Libellé": libelle, "Débit": "", "Crédit": round(ht,2)})
            if abs(tva) > 0.01:
                ecritures.append({"Date": date, "Journal": "VT", "Numéro de compte": "445740000",
                                   "Numéro de pièce": piece, "Libellé": libelle, "Débit": "", "Crédit": round(tva,2)})
        else:
            # === Avoir / facture négative ===
            ttc_abs, ht_abs, tva_abs = abs(ttc), abs(ht), abs(tva)
            ecritures.append({"Date": date, "Journal": "VT", "Numéro de compte": compte_cli,
                               "Numéro de pièce": piece, "Libellé": libelle, "Débit": "", "Crédit": round(ttc_abs,2)})
            ecritures.append({"Date": date, "Journal": "VT", "Numéro de compte": compte_vte,
                               "Numéro de pièce": piece, "Libellé": libelle, "Débit": round(ht_abs,2), "Crédit": ""})
            if abs(tva) > 0.01:
                ecritures.append({"Date": date, "Journal": "VT", "Numéro de compte": "445740000",
                                   "Numéro de pièce": piece, "Libellé": libelle, "Débit": round(tva_abs,2), "Crédit": ""})
        
        # Vérification équilibre
        if abs(ttc - (ht + tva)) > 0.01:
            desequilibres.append(piece)

    df_out = pd.DataFrame(ecritures, columns=["Date", "Journal", "Numéro de compte", "Numéro de pièce", "Libellé", "Débit", "Crédit"])
    
    # === Résumé ===
    st.success(f"✅ {len(df)} lignes sources → {len(df_out)} écritures générées.")
    if desequilibres:
        st.warning(f"⚠️ Factures déséquilibrées : {', '.join(map(str, desequilibres[:5]))}")
    
    # === Aperçu ===
    st.subheader("Aperçu des premières écritures")
    st.dataframe(df_out.head(10))
    
    # === Totaux de contrôle ===
    total_debit = df_out["Débit"].apply(pd.to_numeric, errors="coerce").sum()
    total_credit = df_out["Crédit"].apply(pd.to_numeric, errors="coerce").sum()
    st.info(f"**Total Débit :** {total_debit:,.2f} € | **Total Crédit :** {total_credit:,.2f} € | **Écart :** {total_debit - total_credit:,.2f} €")
    
    # === Export Excel ===
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
