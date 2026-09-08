import json
import sys
sys.stdout.reconfigure(encoding='utf-8')
from test_classifier_on_master import detect_catalog_family

def main():
    with open('Knowledge/climatizzatori_compatibilita_master.json', 'r', encoding='utf-8') as f:
        master = json.load(f)

    print("Daikin items in commercial fallback:")
    for code, ui in master['unita_interne'].items():
        if ui['brand'] == 'DAIKIN':
            fam, _, _ = detect_catalog_family(ui['brand'], ui['nome'], ui.get('codice_mfg', ''), ui.get('pagina_catalogo'))
            if 'DAIKIN SERIE COMMERCIALE' in fam:
                print(f"  [{code}] P.{ui.get('pagina_catalogo')}: {ui['nome']}")

if __name__ == '__main__':
    main()
