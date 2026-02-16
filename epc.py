import streamlit as st
import pandas as pd
from io import BytesIO

# ============================================================
# 🔐 AUTHENTIFICATION
# ============================================================

if "login" not in st.session_state:
    st.session_state["login"] = False

def login(username, password):
    users = {
        "aurore": {"password": "12345", "name": "Aurore Demoulin"},
        "laure.froidefond": {"password": "Laure2019$", "name": "Laure Froidefond"},
        "Bruno": {"password": "Toto1963$", "name": "Toto El Gringo"},
        "Manana": {"password": "193827", "name": "Manana"},
    }

    if username in users and password == users[username]["password"]:
        st.session_state["login"] = True
        st.session_state["name"] = users[username]["name"]
        st.rerun()
    else:
        st.error("❌ Identifiants incorrects")

if not st.session_state["login"]:
    st.title("🔑 Connexion espace expert-comptable")
    u = st.text_input("Identifiant")
    p = st.text_input("Mot de passe", type="password")
    if st.button("Connexion"):
        login(u, p)
    st.stop()

# ============================================================
# 🎯 PAGE PRINCIPALE
# ============================================================

st.set_page_config(page_title="Générateur écritures ventes", page_icon="📘")
st.title("📘 Générateur d'écritures comptables de ventes")
st.caption(f"Connecté en tant que **{st.session_state['name']}**")

if st.button("🔓 Déconnexion"):
    st.session_state["login"] = False
    st.rerun()

uploaded_file = st.file_uploader("📂 Charge le fichier export ventes", type=["xlsx", "xls"])

# ============================================================
# 🛠 FONCTIONS COMPTABLES
# ============================================================

def compte_client(nom):
    nom = str(nom).strip().upper()
    lettre = nom[0] if nom and nom[0].isalpha() else "X"
    return f"4110{lettre}0000"

def compte_vente(taux):
    comptes = {
        5.5: "704000000",
        10.0: "704100000",
        20.0: "704200000",
        0.0: "704500000",
    }
    return comptes.get(float(taux), "704300000")

# ============================================================
# 🚀 TRAITEMENT
# ============================================================

if uploaded_file:

    df = pd.read_excel(uploaded_file)
    df.columns = df.columns.str.strip()

    df = df.rename(columns={
        "N° Facture": "Facture",
        "Nom Facture": "Client",
        "Taux de tva": "Taux TVA",
        "Total HT": "HT_TOTAL",
        "Total TTC": "TTC",
        "Total HT d'origine sur quantité unitaire": "HT_LIGNE"
    })

    # Nettoyage
    df["HT_TOTAL"] = pd.to_numeric(df["HT_TOTAL"], errors="coerce").fillna(0)
    df["TTC"] = pd.to_numeric(df["TTC"], errors="coerce").fillna(0)
    df["HT_LIGNE"] = pd.to_numeric(df["HT_LIGNE"], errors="coerce").fillna(0)
    df["Taux TVA"] = pd.to_numeric(df["Taux TVA"], errors="coerce").fillna(0)
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce").dt.strftime("%d/%m/%Y")

    ecritures = []
    multi_taux_factures = []
    desequilibres = []

    grouped = df.groupby("Facture")

    for facture, data in grouped:

        date = data["Date"].iloc[0]
        client = data["Client"].iloc[0]
        piece = facture
        compte_cli = compte_client(client)

        total_ttc = data["TTC"].max()
        total_ht_facture = data["HT_TOTAL"].max()
        nb_taux = data["Taux TVA"].nunique()

        # =====================================================
        # ✅ MONO TAUX
        # =====================================================
        if nb_taux == 1:

            taux = data["Taux TVA"].iloc[0]
            total_tva = round(total_ttc - total_ht_facture, 2)
            compte_vte = compte_vente(taux)

            ecritures.append({
                "Date": date,
                "Journal": "VT",
                "Numéro de compte": compte_cli,
                "Numéro de pièce": piece,
                "Libellé": f"Facture {piece} - {client}",
                "Débit": round(total_ttc,2),
                "Crédit": ""
            })

            ecritures.append({
                "Date": date,
                "Journal": "VT",
                "Numéro de compte": compte_vte,
                "Numéro de pièce": piece,
                "Libellé": f"Facture {piece} - {client}",
                "Débit": "",
                "Crédit": round(total_ht_facture,2)
            })

            if abs(total_tva) > 0.01:
                ecritures.append({
                    "Date": date,
                    "Journal": "VT",
                    "Numéro de compte": "445740000",
                    "Numéro de pièce": piece,
                    "Libellé": f"Facture {piece} - {client}",
                    "Débit": "",
                    "Crédit": round(total_tva,2)
                })

        # =====================================================
        # ⚠️ MULTI TAUX
        # =====================================================
        else:

            multi_taux_factures.append(facture)

            ecritures.append({
                "Date": date,
                "Journal": "VT",
                "Numéro de compte": compte_cli,
                "Numéro de pièce": piece,
                "Libellé": f"Facture {piece} - {client}",
                "Débit": round(total_ttc,2),
                "Crédit": ""
            })

            taux_group = data.groupby("Taux TVA")

            total_ht_multi = 0
            total_tva_multi = 0

            for taux, lignes in taux_group:

                ht_part = lignes["HT_LIGNE"].sum()
                tva_part = round(ht_part * taux / 100, 2)

                total_ht_multi += ht_part
                total_tva_multi += tva_part

                compte_vte = compte_vente(taux)

                ecritures.append({
                    "Date": date,
                    "Journal": "VT",
                    "Numéro de compte": compte_vte,
                    "Numéro de pièce": piece,
                    "Libellé": f"Facture {piece} - {client}",
                    "Débit": "",
                    "Crédit": round(ht_part,2)
                })

                ecritures.append({
                    "Date": date,
                    "Journal": "VT",
                    "Numéro de compte": "445740000",
                    "Numéro de pièce": piece,
                    "Libellé": f"Facture {piece} - {client}",
                    "Débit": "",
                    "Crédit": round(tva_part,2)
                })

            if abs(total_ttc - (total_ht_multi + total_tva_multi)) > 0.02:
                desequilibres.append(facture)

    df_out = pd.DataFrame(ecritures)

    # =====================================================
    # 📊 AFFICHAGE
    # =====================================================

    st.success(f"✅ {len(grouped)} factures traitées")

    if multi_taux_factures:
        st.warning(f"⚠️ {len(multi_taux_factures)} factures multi-taux détectées")
        st.write(multi_taux_factures)

    if desequilibres:
        st.error("❌ Factures déséquilibrées")
        st.write(desequilibres)

    total_debit = pd.to_numeric(df_out["Débit"], errors="coerce").sum()
    total_credit = pd.to_numeric(df_out["Crédit"], errors="coerce").sum()

    st.info(f"Total Débit : {total_debit:.2f} € | Total Crédit : {total_credit:.2f} € | Écart : {(total_debit-total_credit):.2f} €")

    st.dataframe(df_out.head(20))

    # Export Excel
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df_out.to_excel(writer, index=False, sheet_name="Écritures")

    output.seek(0)

    st.download_button(
        "💾 Télécharger les écritures",
        data=output,
        file_name="ecritures_ventes.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

else:
    st.info("⬆️ Charge ton fichier pour commencer.")
