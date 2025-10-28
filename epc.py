# app.py
import streamlit as st
import pandas as pd
import numpy as np
from io import BytesIO
from datetime import datetime

# =====================
# AUTHENTIFICATION
# =====================
if "login" not in st.session_state:
    st.session_state["login"] = False
if "page" not in st.session_state:
    st.session_state["page"] = "Accueil"  # page par défaut

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
        st.experimental_rerun()
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
# HEADER NOM UTILISATEUR
# =====================
st.sidebar.success(f"👤 {st.session_state['name']}")

# =====================
# MENU PRINCIPAL
# =====================
pages = ["Accueil", "GÉNÉRATEUR ÉCRITURES VENTES"]
page = st.sidebar.selectbox("📂 Menu principal", pages)

# Bouton de déconnexion
if st.sidebar.button("🚪 Déconnexion"):
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.experimental_rerun()

# =====================
# ACCUEIL
# =====================
if page == "Accueil":
    st.title("👋 Bienvenue dans l'outil de génération d'écritures de ventes")
    st.markdown(
        """
        Cet outil permet d'importer un fichier Excel de ventes et de générer automatiquement :
        - les écritures comptables (Journal VT) au format Excel,
        - un contrôle d'équilibre par facture,
        - l'arrondi à 2 décimales.
        
        Utilisez le menu à gauche pour accéder au générateur.
        """
    )
    st.stop()

# =====================
# GÉNÉRATEUR ÉCRITURES VENTES
# =====================
elif page == "GÉNÉRATEUR ÉCRITURES VENTES":
    st.header("🧾 Générateur d'écritures de ventes (Journal VT)")

    st.markdown("""
    **Règles attendues du fichier d'entrée (prise en charge automatique)** :
    - Colonne C → Date
    - Colonne D → Numéro de facture
    - Colonne E → Nom du client
    - Colonne I → Montant TTC
    - Colonne J → Montant HT

    L'import tente d'abord de lire des colonnes nommées (Date/Facture/Client/TTC/HT), 
    sinon il prend les colonnes par position (C=idx2, D=idx3, E=idx4, I=idx8, J=idx9).
    """)

    uploaded = st.file_uploader("Sélectionnez votre fichier Excel (xlsx)", type=["xlsx"])
    if not uploaded:
        st.info("Importez un fichier Excel contenant les ventes (colonnes C,D,E,I,J ou colonnes nommées).")
        st.stop()

    try:
        df_raw = pd.read_excel(uploaded, header=0)
    except Exception as e:
        st.error(f"Erreur lors de la lecture du fichier : {e}")
        st.stop()

    st.success(f"Fichier chargé ({df_raw.shape[0]} lignes, {df_raw.shape[1]} colonnes)")
    st.write("Aperçu (premières lignes) :")
    st.dataframe(df_raw.head())

    # === EXTRACTION DES COLONNES ATTENDUES ===
    expected_names = {"Date", "Facture", "Client", "TTC", "HT"}
    use_by_name = expected_names.issubset(set(df_raw.columns.astype(str)))
    if use_by_name:
        df = pd.DataFrame({
            "Date": pd.to_datetime(df_raw["Date"], errors="coerce"),
            "Facture": df_raw["Facture"].astype(str).fillna("").str.strip(),
            "Client": df_raw["Client"].astype(str).fillna("").str.strip(),
            "TTC": pd.to_numeric(df_raw["TTC"], errors="coerce").fillna(0),
            "HT": pd.to_numeric(df_raw["HT"], errors="coerce").fillna(0),
        })
    else:
        # Tentative par position : C=2, D=3, E=4, I=8, J=9 (0-index)
        if df_raw.shape[1] >= 10:
            df = pd.DataFrame({
                "Date": pd.to_datetime(df_raw.iloc[:, 2], errors="coerce"),
                "Facture": df_raw.iloc[:, 3].astype(str).fillna("").str.strip(),
                "Client": df_raw.iloc[:, 4].astype(str).fillna("").str.strip(),
                "TTC": pd.to_numeric(df_raw.iloc[:, 8], errors="coerce").fillna(0),
                "HT": pd.to_numeric(df_raw.iloc[:, 9], errors="coerce").fillna(0),
            })
            st.info("Colonnes extraites par position (C,D,E,I,J).")
        else:
            st.error("Le fichier ne contient pas assez de colonnes et ne possède pas les noms attendus (Date,Facture,Client,TTC,HT). Vérifiez le format.")
            st.stop()

    # Aperçu des colonnes extraites
    st.subheader("Colonnes utilisées")
    st.dataframe(df.head())

    # Paramètres utilisateur
    st.markdown("### Paramètres de génération")
    journal_code = st.text_input("Code Journal", value="VT")
    compte_tva_enc = st.text_input("Compte TVA (sur encaissements)", value="445740000")
    comptes_vente_input = st.text_input("Comptes ventes (5.5,10,20,multi,auto)", value="704000000,704100000,704200000,704300000,704500000")
    comptes_list = [c.strip() for c in comptes_vente_input.split(",")]
    # mapping: 5.5->index0, 10->1, 20->2, multi->3, auto->4
    if len(comptes_list) < 5:
        st.warning("Les comptes ventes doivent être au format '704000000,704100000,704200000,704300000,704500000' (5 éléments). Valeurs par défaut utilisées si manquant.")
        compt_5_5, compt_10, compt_20, compt_multi, compt_auto = "704000000","704100000","704200000","704300000","704500000"
    else:
        compt_5_5, compt_10, compt_20, compt_multi, compt_auto = comptes_list[:5]

    # Bouton génération
    if st.button("Générer les écritures"):
        # === FONCTIONS UTILES ===
        def taux_tva(ht, ttc):
            # si ht == 0 on considère taux 0 pour éviter division par 0
            if ht == 0:
                if abs(ttc) < 1e-8:
                    return 0
                else:
                    return "multi"
            # calc taux en pourcentage arrondi raisonnablement
            tva_calc = (ttc / ht - 1) * 100
            tva_rounded = round(tva_calc, 1)
            # tolérances
            if abs(tva_rounded - 5.5) < 0.25:
                return 5.5
            elif abs(tva_rounded - 10) < 0.35:
                return 10
            elif abs(tva_rounded - 20) < 0.6:
                return 20
            elif abs(ttc - ht) < 0.01:
                return 0
            else:
                return "multi"

        def compte_vente(taux):
            if taux == 5.5:
                return compt_5_5
            elif taux == 10:
                return compt_10
            elif taux == 20:
                return compt_20
            elif taux == 0:
                return compt_auto
            else:
                return compt_multi

        def compte_client(nom):
            nom = str(nom).strip().upper()
            lettre = "X"
            if nom and nom[0].isalpha():
                lettre = nom[0]
            return f"4110{lettre}0000"

        # Construction des écritures
        ecritures = []
        erreurs = []
        # We'll keep a mapping facture -> (total_debit, total_credit)
        bilan_par_facture = {}

        for idx, row in df.iterrows():
            date = row["Date"]
            # si date NaT, on peut mettre vide ou aujourd'hui ; on garde tel quel
            facture = str(row["Facture"]).strip()
            client = str(row["Client"]).strip()
            ttc = float(row["TTC"]) if not pd.isna(row["TTC"]) else 0.0
            ht = float(row["HT"]) if not pd.isna(row["HT"]) else 0.0
            tva = round(ttc - ht, 2)

            taux = taux_tva(ht, ttc)
            compte_vte = compte_vente(taux)
            compte_cli = compte_client(client)
            libelle = f"Facture {facture} - {client}"

            # Arrondis à 2 décimales
            ttc_r = round(ttc, 2)
            ht_r = round(ht, 2)
            tva_r = round(tva, 2)

            # Ligne client (débit TTC)
            ecritures.append({
                "Date": date,
                "Journal": journal_code,
                "Numéro de compte": compte_cli,
                "Libellé": libelle,
                "Débit": ttc_r,
                "Crédit": 0.0
            })

            # Ligne vente (crédit HT)
            ecritures.append({
                "Date": date,
                "Journal": journal_code,
                "Numéro de compte": compte_vte,
                "Libellé": libelle,
                "Débit": 0.0,
                "Crédit": ht_r
            })

            # Ligne TVA si positive
            if tva_r > 0.0:
                ecritures.append({
                    "Date": date,
                    "Journal": journal_code,
                    "Numéro de compte": compte_tva_enc,
                    "Libellé": libelle,
                    "Débit": 0.0,
                    "Crédit": tva_r
                })

            # Mise à jour bilan par facture
            prev = bilan_par_facture.get(facture, {"debit": 0.0, "credit": 0.0})
            prev["debit"] += ttc_r
            prev["credit"] += ht_r + (tva_r if tva_r > 0 else 0.0)
            bilan_par_facture[facture] = prev

        # Vérification d'équilibre par facture
        des_equilibres = []
        for fact, sums in bilan_par_facture.items():
            debit = round(sums["debit"], 2)
            credit = round(sums["credit"], 2)
            diff = round(debit - credit, 2)
            if abs(diff) > 0.01:  # tolérance centime
                des_equilibres.append({
                    "Facture": fact,
                    "Total Débit": debit,
                    "Total Crédit": credit,
                    "Diff (Débit - Crédit)": diff
                })

        # DataFrame export
        df_out = pd.DataFrame(ecritures, columns=["Date", "Journal", "Numéro de compte", "Libellé", "Débit", "Crédit"])

        # Formatage : arrondir (déjà arrondi) et forcer types numériques
        df_out["Débit"] = pd.to_numeric(df_out["Débit"], errors="coerce").fillna(0).round(2)
        df_out["Crédit"] = pd.to_numeric(df_out["Crédit"], errors="coerce").fillna(0).round(2)

        # Préparer le fichier Excel en mémoire
        buffer = BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            # Feuille principale : écritures
            # Pour l'affichage Excel, laisser les dates converties proprement
            df_export = df_out.copy()
            # si 'Date' est datetime64, ExcelWriter gérera la conversion
            df_export.to_excel(writer, index=False, sheet_name="Ecritures_Ventes")

            # Feuille contrôle d'équilibre
            df_balance = pd.DataFrame(list(bilan_par_facture.items()), columns=["Facture", "Sums"])
            # transform sums
            df_balance["Total Débit"] = df_balance["Sums"].apply(lambda x: round(x["debit"], 2))
            df_balance["Total Crédit"] = df_balance["Sums"].apply(lambda x: round(x["credit"], 2))
            df_balance["Diff (Débit - Crédit)"] = (df_balance["Total Débit"] - df_balance["Total Crédit"]).round(2)
            df_balance = df_balance[["Facture", "Total Débit", "Total Crédit", "Diff (Débit - Crédit)"]]
            df_balance.to_excel(writer, index=False, sheet_name="Controle_Equilibre")

            # Feuille anomalies uniquement si des déséquilibres
            if des_equilibres:
                df_des = pd.DataFrame(des_equilibres)
                df_des.to_excel(writer, index=False, sheet_name="Deséquilibres")
        buffer.seek(0)

        # Affichage résultat dans l'app
        st.success("✅ Génération terminée.")
        st.subheader("Aperçu des écritures générées")
        st.dataframe(df_out.head(50))

        # Afficher le tableau d'équilibre
        st.subheader("Contrôle d'équilibre par facture")
        st.dataframe(df_balance.style.format({
            "Total Débit": "{:,.2f}",
            "Total Crédit": "{:,.2f}",
            "Diff (Débit - Crédit)": "{:,.2f}"
        }))

        # Si déséquilibres, afficher en évidence
        if des_equilibres:
            st.error(f"{len(des_equilibres)} facture(s) déséquilibrée(s) détectée(s) — vérifier les montants HT/TTC.")
            st.dataframe(pd.DataFrame(des_equilibres).style.format({
                "Total Débit": "{:,.2f}",
                "Total Crédit": "{:,.2f}",
                "Diff (Débit - Crédit)": "{:,.2f}"
            }))
        else:
            st.success("Tous les soldes par facture sont équilibrés (tolérance ±0.01 €).")

        # Téléchargement
        now_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        download_name = f"ecritures_ventes_{now_str}.xlsx"
        st.download_button(
            label="📥 Télécharger le fichier d'écritures (Excel)",
            data=buffer,
            file_name=download_name,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

        # Afficher résumé rapide
        total_debit = df_out["Débit"].sum()
        total_credit = df_out["Crédit"].sum()
        st.info(f"Total Débit (fichier généré) : {total_debit:,.2f} € — Total Crédit : {total_credit:,.2f} €")

        st.balloons()