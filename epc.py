import streamlit as st
import pandas as pd
from io import BytesIO

st.set_page_config(page_title="Générateur écritures ventes", page_icon="📘", layout="centered")
st.title("📘 Générateur d'écritures de ventes (TVA sur encaissements)")
st.write("Charge un fichier Excel sans en-tête (colonnes C à J).")

uploaded_file = st.file_uploader("📂 Fichier Excel", type=["xls", "xlsx"])

if uploaded_file:
    # Lecture brute sans en-tête
    df = pd.read_excel(uploaded_file, header=None, dtype=str)

    try:
        df = df.iloc[:, [2, 3, 4, 8, 9]]  # C, D, E, I, J
        df.columns = ["Date", "Facture", "Client", "TTC", "HT"]
    except Exception:
        st.error("❌ Fichier non conforme : il doit contenir au moins 10 colonnes.")
        st.stop()

    # Nettoyage des montants
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

    # Nettoyage et formatage des dates
    df["Date"] = (
        pd.to_datetime(df["Date"], errors="coerce")
        .dt.strftime("%d/%m/%Y")
        .fillna("")
    )

    # === Fonctions auxiliaires ===
    def compte_client(nom):
        nom = str(nom).strip().upper()
        lettre = nom[0] if nom and nom[0].isalpha() else "X"
        return f"4110{lettre}0000"

    def determiner_taux(ht, ttc):
        """Retourne le taux de TVA (5.5, 10, 20, 0 ou 'multi')."""
        if ht == 0:
            return 0
        taux_calcule = round((ttc / ht - 1) * 100, 1)
        if 5 <= taux_calcule <= 6:
            return 5.5
        elif 9 <= taux_calcule <= 11:
            return 10
        elif 19 <= taux_calcule <= 21:
            return 20
        elif abs(ttc - ht) < 0.02:
            return 0
        else:
            return "multi"

    def compte_vente(taux):
        mapping = {
            5.5: "704000000",
            10: "704100000",
            20: "704200000",
            0: "704500000",
            "multi": "704300000"
        }
        return mapping.get(taux, "704300000")

    # === Génération des écritures ===
    ecritures = []
    desequilibres = []

    for _, row in df.iterrows():
        ht, ttc = round(row["HT"], 2), round(row["TTC"], 2)
        if ht == 0 and ttc == 0:
            continue

        tva = round(ttc - ht, 2)
        taux = determiner_taux(ht, ttc)
        cpt_vente = compte_vente(taux)
        cpt_client = compte_client(row["Client"])
        libelle = f"Facture {row['Facture']} - {row['Client']}"
        date = row["Date"]

        # Ligne Client (Débit TTC)
        ecritures.append({
            "Date": date, "Journal": "VT",
            "Numéro de compte": cpt_client, "Libellé": libelle,
            "Débit": ttc, "Crédit": ""
        })

        # Ligne Vente (Crédit HT)
        ecritures.append({
            "Date": date, "Journal": "VT",
            "Numéro de compte": cpt_vente, "Libellé": libelle,
            "Débit": "", "Crédit": ht
        })

        # Ligne TVA (Crédit TVA, si différente de 0)
        if abs(tva) > 0.01:
            ecritures.append({
                "Date": date, "Journal": "VT",
                "Numéro de compte": "445740000", "Libellé": libelle,
                "Débit": "", "Crédit": tva
            })

        # Contrôle d'équilibre
        if abs((ttc) - (ht + tva)) > 0.01:
            desequilibres.append(row["Facture"])

    df_out = pd.DataFrame(ecritures, columns=["Date", "Journal", "Numéro de compte", "Libellé", "Débit", "Crédit"])

    # === Résumé ===
    st.success(f"✅ {len(df)} lignes source – {len(df_out)} écritures générées.")
    if desequilibres:
        st.warning(f"⚠️ {len(desequilibres)} factures déséquilibrées : {', '.join(map(str, desequilibres[:10]))}")

    # === Aperçu ===
    st.subheader("Aperçu des premières écritures")
    st.dataframe(df_out.head(10))

    # === Export ===
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df_out.to_excel(writer, index=False)
    output.seek(0)

    st.download_button(
        "💾 Télécharger les écritures",
        data=output,
        file_name="ecritures_ventes.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

else:
    st.info("⬆️ Charge ton fichier Excel pour commencer.")
