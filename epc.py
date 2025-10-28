import streamlit as st
import pandas as pd
from io import BytesIO

# === Configuration de la page ===
st.set_page_config(page_title="Générateur d'écritures de vente", page_icon="📘", layout="centered")
st.title("📘 Générateur d'écritures comptables de ventes")
st.write("Charge ton fichier Excel contenant les ventes (avec les colonnes C à J selon ton modèle).")

# === Upload du fichier ===
uploaded_file = st.file_uploader("📂 Sélectionne ton fichier Excel", type=["xls", "xlsx"])

if uploaded_file:
    df = pd.read_excel(uploaded_file)

    # === Lecture et renommage des colonnes ===
    try:
        df = df[['C', 'D', 'E', 'I', 'J']]
        df.columns = ['Date', 'Facture', 'Client', 'TTC', 'HT']
    except KeyError:
        st.error("❌ Les colonnes C, D, E, I et J n'ont pas été trouvées dans le fichier.")
        st.stop()

    def taux_tva(ht, ttc):
        if ht == 0:
            return 0
        tva_calc = round((ttc / ht - 1) * 100, 1)
        if abs(tva_calc - 5.5) < 0.2:
            return 5.5
        elif abs(tva_calc - 10) < 0.3:
            return 10
        elif abs(tva_calc - 20) < 0.5:
            return 20
        elif abs(ttc - ht) < 0.01:
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

    def compte_client(nom):
        nom = str(nom).strip().upper()
        lettre = nom[0] if nom and nom[0].isalpha() else "X"
        return f"4110{lettre}0000"

    ecritures = []
    desequilibres = []

    for _, row in df.iterrows():
        ht = float(row['HT'])
        ttc = float(row['TTC'])
        tva = round(ttc - ht, 2)
        taux = taux_tva(ht, ttc)
        compte_vte = compte_vente(taux)
        compte_cli = compte_client(row['Client'])
        libelle = f"Facture {row['Facture']} - {row['Client']}"
        date = row['Date']

        ecritures.append({
            'Date': date,
            'Journal': 'VT',
            'Numéro de compte': compte_cli,
            'Libellé': libelle,
            'Débit': round(ttc, 2),
            'Crédit': ''
        })
        ecritures.append({
            'Date': date,
            'Journal': 'VT',
            'Numéro de compte': compte_vte,
            'Libellé': libelle,
            'Débit': '',
            'Crédit': round(ht, 2)
        })
        if tva > 0:
            ecritures.append({
                'Date': date,
                'Journal': 'VT',
                'Numéro de compte': '445740000',
                'Libellé': libelle,
                'Débit': '',
                'Crédit': round(tva, 2)
            })

        # Contrôle équilibre
        total_debit = round(ttc, 2)
        total_credit = round(ht + tva, 2)
        if abs(total_debit - total_credit) > 0.01:
            desequilibres.append(f"{row['Facture']} ({row['Client']})")

    df_out = pd.DataFrame(ecritures, columns=['Date', 'Journal', 'Numéro de compte', 'Libellé', 'Débit', 'Crédit'])

    # === Affichage d’un résumé ===
    st.success(f"✅ {len(df['Facture'])} factures traitées – {len(df_out)} lignes générées.")
    if desequilibres:
        st.warning(f"⚠️ {len(desequilibres)} écritures déséquilibrées : {', '.join(desequilibres[:5])}")

    # === Export Excel en mémoire ===
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_out.to_excel(writer, index=False)
    output.seek(0)

    st.download_button(
        label="💾 Télécharger le fichier d'écritures",
        data=output,
        file_name="ecritures_ventes.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

else:
    st.info("⬆️ Charge ton fichier Excel pour commencer.")
