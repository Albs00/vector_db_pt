"""
Test suite per ClimaMatchingEngine.
Verifica i requisiti specifici:
1. MPN errato già presente (fall-through, risoluzione BOM corretta da catalogo)
2. MPN vuoto (risoluzione da catalogo)
3. Duplicati UI (multiset check: 9+9 richiede 2x UI distinte o duplicate)
4. Revisione simile (marcatura DA_VERIFICARE_VERSIONE e score penalizzato)
5. Accessorio mancante (marcatura DA VERIFICARE per staffa/accessorio citato nel titolo)
6. Configurazione multisplit non confermata (CONFIGURAZIONE_NON_CONFERMATA e score sotto soglia)
"""

import sys
import unittest
from pathlib import Path

# Assicura import da root
BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))

from src.clima_matching_engine import ClimaMatchingEngine, ExpectedBOM

class TestClimaMatchingEngine(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.engine = ClimaMatchingEngine()

    def test_case_1_mpn_errato_presente(self):
        """
        Caso 1: MPN errato già presente.
        Se l'MPN non è coerente, ignora il match attuale e riesegui l'identificazione
        come se l'MPN fosse vuoto. Proponi i codici corretti con score >= 80%.
        """
        # Titolo richiede Midea Elegance 9000, ma MPN ha codice Xtreme Pro (50131181)
        rif = "MIDEA_ELEGANCE_9_MONO"
        title = "CLIMATIZZATORE MIDEA MONOSPLIT ELEGANCE 9000 BTU INVERTER R32"
        bad_mpn = "50131181+50131105"  # 50131181 è UI XTREME PRO!

        res = self.engine.match_product(1, rif, title, bad_mpn)

        # L'esito deve rilevare la discordanza della serie originale
        self.assertEqual(res.status, "DISCORDANZA")
        self.assertIn("DISCORDANZA MPN ORIGINALE", res.feedback)
        self.assertIn("Midea Elegance", res.feedback)
        # Deve aver risolto a catalogo i codici corretti della Elegance 9000: UI 50131051 + UE 50131099
        self.assertEqual(res.mpn_suggerito, "50131051+50131099")
        self.assertGreaterEqual(res.score_value, 80)
        # Non deve contenere codici di utensileria o non clima
        self.assertTrue(self.engine.validate_code_is_ac(res.mpn_suggerito))

    def test_case_2_mpn_vuoto(self):
        """
        Caso 2: MPN vuoto.
        Ricostruisce la BOM dal titolo ed estrae i codici certificati a catalogo PT.
        """
        rif = "SAM_AVANT_9"
        title = "CONDIZIONATORE SAMSUNG WINDFREE AVANT 9000 BTU MONOSPLIT R32"
        empty_mpn = ""

        res = self.engine.match_product(2, rif, title, empty_mpn)

        self.assertEqual(res.status, "COERENTE")
        self.assertGreaterEqual(res.score_value, 80)
        # Samsung Avant 9000: UI 50367818 + UE 50367788
        self.assertEqual(res.mpn_suggerito, "50367818+50367788")
        self.assertTrue(self.engine.validate_code_is_ac(res.mpn_suggerito))

    def test_case_3_duplicati_ui_multiset(self):
        """
        Caso 3: Duplicati UI (Multiset matching).
        Un dual split 9+9 richiede 2x UI 9k. Se l'MPN originale fornisce solo una UI,
        il multiset check deve fallire (1 != 2) e rieseguire la risoluzione completa con 2 UI.
        """
        rif = "PAN_DUAL_9_9"
        title = "CLIMATIZZATORE PANASONIC DUAL SPLIT ETHEREA 9+9 BIANCO CON CU-2Z50TBE"
        # MPN incompleto: solo 1 UI 50207572 + UE 99675233
        incomplete_mpn = "50207572+99675233"

        # 1. Verifica diretta multiset validator
        bom = self.engine.parse_expected_bom(title, rif)
        self.assertEqual(bom.split_count, 2)
        self.assertEqual(bom.ui_btus, [9000, 9000])

        is_coherent, status, score, reasons, _ = self.engine.validate_existing_mpn(["50207572", "99675233"], bom)
        self.assertFalse(is_coherent)
        self.assertEqual(status, "DISCORDANZA")
        self.assertTrue(any("Quantità UI diversa" in r or "Discordanza taglie multiset" in r for r in reasons))

        # 2. Verifica match_product completo: rigetta match e suggerisce BOM corretta con 2x UI
        res = self.engine.match_product(3, rif, title, incomplete_mpn)
        self.assertEqual(res.status, "DISCORDANZA")
        # Deve suggerire 50207572 DUE VOLTE (multiset) + UE
        self.assertEqual(res.mpn_suggerito, "50207572+50207572+99675233")
        self.assertTrue(self.engine.validate_code_is_ac(res.mpn_suggerito))

    def test_case_4_revisione_simile(self):
        """
        Caso 4: Revisione simile / generazionale diversa.
        Modelli molto simili o revisioni diverse devono essere marcati
        DA_VERIFICARE_VERSIONE e penalizzati nel confidence score.
        HARD GATE: DA_VERIFICARE_VERSIONE blocca sempre l'autocorrezione (mpn_suggerito = "").
        """
        # Titolo richiede esplicitamente Panasonic Etherea XKE (generazione precedente)
        rif = "PAN_ETH_XKE"
        title = "CLIMATIZZATORE PANASONIC MONOSPLIT ETHEREA 9000 BTU BIANCO XKE"
        # MPN a catalogo ha la versione ZKE (50207572 + 50207824)
        mpn_zke = "50207572+50207824"

        res = self.engine.match_product(4, rif, title, mpn_zke)

        self.assertEqual(res.status, "DA_VERIFICARE_VERSIONE")
        self.assertEqual(res.score_value, 85)
        self.assertIn("DA_VERIFICARE_VERSIONE", res.confidence_score)
        self.assertIn("Revisione/Generazione diversa", res.feedback)
        # HARD GATE: Autocorrezione bloccata! mpn_suggerito deve essere vuoto
        self.assertEqual(res.mpn_suggerito, "")
        # Ma i candidati rimangono visibili in componenti_db per revisione operatore
        self.assertIn("50207572", res.componenti_db)
        self.assertIn("50207824", res.componenti_db)

    def test_case_5_accessorio_mancante(self):
        """
        Caso 5: Accessorio mancante.
        Se il titolo richiede 'CON STAFFA', ma i codici MPN contengono solo macchine,
        l'algoritmo deve marcare 'DA VERIFICARE' e penalizzare il confidence score.
        """
        rif = "SAM_AVANT_STAFFE"
        title = "CLIMATIZZATORE SAMSUNG WINDFREE AVANT 9000 BTU MONOSPLIT CON STAFFA"
        mpn_macchine = "50367818+50367788"  # solo UI e UE, manca staffa

        res = self.engine.match_product(5, rif, title, mpn_macchine)

        self.assertEqual(res.status, "DA VERIFICARE")
        self.assertEqual(res.score_value, 90)
        self.assertIn("Staffa indicata nel titolo ma non presente nei codici MPN", res.feedback)
        self.assertEqual(res.mpn_suggerito, "50367818+50367788")

    def test_case_6_configurazione_multisplit_non_confermata(self):
        """
        Caso 6: Configurazione multisplit non confermata.
        Se la configurazione multisplit è incompatibile (es. trial split su unità esterna dual con 2 attacchi)
        oppure l'unità esterna non è confermata a catalogo,
        deve essere marcata CONFIGURAZIONE_NON_CONFERMATA e bloccare sempre l'autocorrezione.
        """
        rif = "PAN_TRIAL_2PORT_UE"
        title = "CLIMATIZZATORE PANASONIC TRIAL SPLIT ETHEREA 9+9+12 BIANCO CON CU-2Z35TBE"
        # MPN include 3 UI ma una UE dual split (99675219 CU-2Z35TBE, solo 2 attacchi!)
        incompatible_mpn = "50207572+50207572+50207909+99675219"

        res = self.engine.match_product(6, rif, title, incompatible_mpn)

        self.assertEqual(res.status, "CONFIGURAZIONE_NON_CONFERMATA")
        self.assertEqual(res.score_value, 75)
        self.assertIn("CONFIGURAZIONE_NON_CONFERMATA", res.confidence_score)
        self.assertIn("Attacchi UE insufficienti", res.feedback)
        # HARD GATE: nessun codice deve essere inventato o suggerito!
        self.assertEqual(res.mpn_suggerito, "")

    def test_multisplit_unspecified_ue_blocks_autocorrect(self):
        """
        Verifica: Non inferire UE da numero porte. Se UE non è specificata/confermata
        a catalogo, l'autocorrezione DEVE essere bloccata.
        """
        rif = "SAM_DUAL_NO_UE"
        title = "CLIMATIZZATORE SAMSUNG DUAL SPLIT WINDFREE AVANT 9+9"
        res = self.engine.match_product(7, rif, title, "")

        self.assertEqual(res.status, "CONFIGURAZIONE_NON_CONFERMATA")
        self.assertEqual(res.mpn_suggerito, "")
        self.assertIn("unità esterna FJM non specificata", res.feedback)

    def test_no_tools_category_contamination(self):
        """
        Verifica di sicurezza: impedire tassativamente l'emissione di codici
        appartenenti a UTENSILI ED ATTREZZATURA (es. 50131112 SET GANASCE).
        """
        with self.assertRaises(ValueError):
            self.engine.validate_code_is_ac("50131112", row_idx="TEST_SECURITY")

    def test_case_8_bosch_climate_3000_3200_equivalence(self):
        """
        Verifica: Bosch Climate 3000i e 3200i appartengono alla medesima famiglia
        commerciale da catalogo PT pagina 583. Un titolo Climate 3000i con codice 3200i
        (es. 50418725 per 12k) deve essere validato come COERENTE (100%).
        """
        rif = "5000M105/4E_12+12"
        title = "Bosch Climatizzatore Dual Split Climate 3000i 12+12 con 5000M 105/4 E Inverter R 32 Wi-Fi Optional Classe A++"
        mpn = "50418725+50418725+50250516"

        res = self.engine.match_product(8, rif, title, mpn)
        self.assertEqual(res.status, "COERENTE")
        self.assertEqual(res.score_value, 100)
        self.assertEqual(res.mpn_suggerito, mpn)

    def test_case_9_bosch_7000i_disambiguation(self):
        """
        Verifica: In 'Climate 7000i ... da 9000 btu', il parser non deve confondere
        il nome serie 7000 con la taglia 7000 BTU, ma isolare 9000 BTU.
        """
        rif = "BOSCH_7000_NERO_9"
        title = "Bosch Climatizzatore Monosplit Climate 7000i da 9000 btu Nero Inverter R-32"
        mpn = "50276707+50276479"

        res = self.engine.match_product(9, rif, title, mpn)
        self.assertEqual(res.status, "COERENTE")
        self.assertEqual(res.score_value, 100)
        self.assertEqual(res.mpn_suggerito, mpn)

if __name__ == "__main__":
    unittest.main()

