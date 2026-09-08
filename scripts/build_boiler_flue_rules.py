"""
build_boiler_flue_rules.py
Costruisce il dataset Knowledge/boiler_flue_compatibility_rules.json
contenente le regole di compatibilità certificate per la fumisteria delle caldaie
a condensazione (pagine 28-82 del Catalogo Puglia Termica 2026).

Regole chiave:
1. Priorità: Fumisteria Compatibile = Principale (Primary), Fumisteria Originale = Backup.
2. Tipologia fumi: Coassiale 60/100 vs Sdoppiato 80/80.
3. Filtri di compatibilità per modello (inclusioni / esclusioni specifiche del catalogo).
"""

import os
import sys
import json

sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RULES_OUT_PATH = os.path.join(BASE_DIR, "Knowledge", "boiler_flue_compatibility_rules.json")
MASTER_PATH = os.path.join(BASE_DIR, "Knowledge", "unified_catalog_master.json")

# Definizione tabellare strutturata delle regole estratte dalle pagine dedicate del catalogo
RULES_DATA = {
    "universal_defangatore": {
        "code": "50405633",
        "name": "DEFANGATORE MAGNETICO KJ",
        "brand": "FERRARI",
        "primary_page": 90,
        "badge_text": "⭐ Defangatore Universale Sotto-Caldaia",
        "measure": "3/4\""
    },
    "brands": {
        "FERROLI": {
            "catalog_flue_page": 32,
            "compatible": [
                {
                    "code": "50346967",
                    "flue_type": "COAXIAL",
                    "diameter": "60/100",
                    "name_catalog": "KIT COASSIALE IN PP/PP CON TERMINALE DI SCARICO BIANCO",
                    "note": "Per tutti i modelli",
                    "inclusions": ["*"],
                    "exclusions": [],
                    "is_starter_kit": True
                },
                {
                    "code": "50347018",
                    "flue_type": "COAXIAL",
                    "diameter": "60/100",
                    "name_catalog": "KIT COASSIALE UNIVERSALE in PP/PP CON TERMINALE DI SCARICO BIANCO",
                    "note": "Per tutti i modelli",
                    "inclusions": ["*"],
                    "exclusions": []
                },
                {
                    "code": "50345946",
                    "flue_type": "COAXIAL",
                    "diameter": "60/100",
                    "name_catalog": "PARTENZA VERTICALE COASSIALE pp/pvc CON PRELIEVO FUMI",
                    "note": "Per tutti i modelli",
                    "inclusions": ["*"],
                    "exclusions": []
                },
                {
                    "code": "50431434",
                    "flue_type": "SPLIT",
                    "diameter": "60/100 - 80/80",
                    "name_catalog": "KIT SDOPPIATO A CIABATTA ECO in pp/PP UNIVERSALE CON PRELIEVO FUMI",
                    "note": "Per tutti i modelli",
                    "inclusions": ["*"],
                    "exclusions": [],
                    "is_starter_kit": True
                },
                {
                    "code": "50431403",
                    "flue_type": "SPLIT",
                    "diameter": "60/100 - 80/80",
                    "name_catalog": "KIT SDOPPIATO A CIABATTA ECO in PP/PP CON PRELIEVO FUMI",
                    "note": "Per tutti i modelli",
                    "inclusions": ["*"],
                    "exclusions": []
                },
                {
                    "code": "50345960",
                    "flue_type": "SPLIT",
                    "diameter": "80/80",
                    "name_catalog": "KIT CONDOTTI SEPARATI IN PP/pvc Senza prelievo fumi",
                    "note": "Esclusi i mod. FBC e Theta",
                    "inclusions": ["*"],
                    "exclusions": ["FBC", "THETA"]
                }
            ],
            "original": [
                {
                    "code": "99130435",
                    "flue_type": "COAXIAL",
                    "diameter": "60/100",
                    "name_catalog": "TERMINALE COASSIALE PP MT1 1KWMA56W",
                    "note": "Per tutti i modelli",
                    "inclusions": ["*"],
                    "exclusions": []
                },
                {
                    "code": "99652876",
                    "flue_type": "COAXIAL",
                    "diameter": "60/100",
                    "name_catalog": "CURVA COASSIALE 90° GIREVOLE 360° CON PASSO 45° 041084X0",
                    "note": "Per Modelli RRT - Alpha - Theta - FBC",
                    "inclusions": ["RRT", "ALPHA", "THETA", "FBC"],
                    "exclusions": []
                },
                {
                    "code": "99652883",
                    "flue_type": "COAXIAL",
                    "diameter": "60/100",
                    "name_catalog": "PARTENZA VERTICALE COASSIALE 041083X0",
                    "note": "Per Modelli Rrt - Alpha - Theta - FBC",
                    "inclusions": ["RRT", "ALPHA", "THETA", "FBC"],
                    "exclusions": []
                },
                {
                    "code": "50017799",
                    "flue_type": "COAXIAL",
                    "diameter": "80/125",
                    "name_catalog": "PARTENZA VERTICALE COASSIALE 041006X0",
                    "note": "Per Modelli Rrt - Alpha - Theta - FBC",
                    "inclusions": ["RRT", "ALPHA", "THETA", "FBC"],
                    "exclusions": []
                },
                {
                    "code": "99213275",
                    "flue_type": "COAXIAL",
                    "diameter": "60/100",
                    "name_catalog": "PARTENZA VERTICALE COASSIALE 041002X0",
                    "note": "Per Hitech RRT 45 H",
                    "inclusions": ["RRT 45", "45 H", "45H"],
                    "exclusions": []
                },
                {
                    "code": "99191627",
                    "flue_type": "COAXIAL",
                    "diameter": "60/100",
                    "name_catalog": "CURVA 90° FLANGIATA COASSIALE 041001X0",
                    "note": "Per modelli Hitech RRT 45 H",
                    "inclusions": ["RRT 45", "45 H", "45H"],
                    "exclusions": []
                },
                {
                    "code": "99652890",
                    "flue_type": "SPLIT",
                    "diameter": "80/80",
                    "name_catalog": "KIT SCARICO TUBI SEPARATI COMPLETO DI PRESE PER ANALISI 041082X0",
                    "note": "Per Modelli Rrt - Alpha - Theta - FBC",
                    "inclusions": ["RRT", "ALPHA", "THETA", "FBC"],
                    "exclusions": []
                },
                {
                    "code": "99248710",
                    "flue_type": "SPLIT",
                    "diameter": "80/80",
                    "name_catalog": "KIT PER TUBI SEPARATI DN 80 041039X0",
                    "note": "Per Bluehelix B S K 100",
                    "inclusions": ["B S K 100", "K 100", "K100"],
                    "exclusions": []
                },
                {
                    "code": "50018901",
                    "flue_type": "ACCESSORY",
                    "diameter": "FUMI",
                    "name_catalog": "KIT VALVOLA CLAPET GAS SCARICO 041106X0",
                    "note": "Per Bluehelix Alpha - Theta - FBC",
                    "inclusions": ["ALPHA", "THETA", "FBC"],
                    "exclusions": []
                }
            ]
        },
        "BAXI": {
            "catalog_flue_page": 37,
            "compatible": [
                {
                    "code": "50225972",
                    "flue_type": "COAXIAL",
                    "diameter": "60/100",
                    "name_catalog": "KIT FUMI COASSIALE IN PP/PVC TIPO BAXI",
                    "note": "Per tutti i modelli",
                    "inclusions": ["*"],
                    "exclusions": [],
                    "is_starter_kit": True
                },
                {
                    "code": "50226115",
                    "flue_type": "SPLIT",
                    "diameter": "80/80",
                    "name_catalog": "KIT SDOPPIATO CON PRELIEVI FUMI TIPO BAXI",
                    "note": "Per tutti i modelli",
                    "inclusions": ["*"],
                    "exclusions": [],
                    "is_starter_kit": True
                },
                {
                    "code": "50346950",
                    "flue_type": "COAXIAL",
                    "diameter": "60/100",
                    "name_catalog": "KIT COASSIALE IN PP/PP CON TERMINALE DI SCARICO BIANCO",
                    "note": "Per tutti i modelli esclusi tutti i mod. Luna",
                    "inclusions": ["*"],
                    "exclusions": ["LUNA"]
                },
                {
                    "code": "50345908",
                    "flue_type": "COAXIAL",
                    "diameter": "60/100",
                    "name_catalog": "PARTENZA VERTICALE COASSIALE in PP/Pvc CON PRELIEVO FUMI",
                    "note": "Per tutti i modelli esclusi tutti i mod. Luna",
                    "inclusions": ["*"],
                    "exclusions": ["LUNA"]
                },
                {
                    "code": "50431373",
                    "flue_type": "SPLIT",
                    "diameter": "60/100 - 80/80",
                    "name_catalog": "KIT SDOPPIATO A CIABATTA ECO in PP/PP CON PRELIEVO FUMI",
                    "note": "Per tutti i modelli esclusi tutti i mod. Luna",
                    "inclusions": ["*"],
                    "exclusions": ["LUNA"]
                },
                {
                    "code": "50431434",
                    "flue_type": "SPLIT",
                    "diameter": "60/100 - 80/80",
                    "name_catalog": "KIT SDOPPIATO A CIABATTA ECO UNIVERSALE in PP/PP CON PRELIEVO FUMI",
                    "note": "Per tutti i modelli esclusi tutti i mod. Luna",
                    "inclusions": ["*"],
                    "exclusions": ["LUNA"]
                },
                {
                    "code": "50345915",
                    "flue_type": "SPLIT",
                    "diameter": "60/100 - 80/80",
                    "name_catalog": "KIT SDOPPIATO A CIABATTA ECO in PP/PP CON PRELIEVO FUMI",
                    "note": "Per tutti i modelli esclusi tutti i mod. Luna",
                    "inclusions": ["*"],
                    "exclusions": ["LUNA"]
                },
                {
                    "code": "50345922",
                    "flue_type": "SPLIT",
                    "diameter": "80/80",
                    "name_catalog": "KIT CONDOTTI SEPARATI IN PP/pvc senza prelievo fumi",
                    "note": "Per tutti i modelli esclusi tutti i mod. Luna",
                    "inclusions": ["*"],
                    "exclusions": ["LUNA"]
                }
            ],
            "original": [
                {
                    "code": "99220846",
                    "flue_type": "COAXIAL",
                    "diameter": "60/100",
                    "name_catalog": "TERMINALE COASSIALE HT IN PP KHG 71405961",
                    "note": "Per tutti i modelli",
                    "inclusions": ["*"],
                    "exclusions": []
                },
                {
                    "code": "99237790",
                    "flue_type": "COAXIAL",
                    "diameter": "60/100",
                    "name_catalog": "CURVA 90° COASSIALE HT IN PP KHG 71405971",
                    "note": "Per tutti i modelli (con adattatore su Luna)",
                    "inclusions": ["*"],
                    "exclusions": []
                },
                {
                    "code": "99556464",
                    "flue_type": "COAXIAL",
                    "diameter": "60/100",
                    "name_catalog": "CURVA COASSIALE 90° RIBASSATA KA00049",
                    "note": "Per Luna Classic - Luna Century - Luna Compact - Nuvola Century",
                    "inclusions": ["LUNA CLASSIC", "LUNA CENTURY", "LUNA COMPACT", "NUVOLA CENTURY", "LUNA", "NUVOLA"],
                    "exclusions": []
                },
                {
                    "code": "99809829",
                    "flue_type": "COAXIAL",
                    "diameter": "60/100",
                    "name_catalog": "PARTENZA VERTICALE COASSIALE A7755079 / ADATTATORE",
                    "note": "Per Luna Classic - Luna Century - Luna Compact - Nuvola Century",
                    "inclusions": ["LUNA CLASSIC", "LUNA CENTURY", "LUNA COMPACT", "NUVOLA CENTURY", "LUNA", "NUVOLA"],
                    "exclusions": []
                },
                {
                    "code": "99237844",
                    "flue_type": "SPLIT",
                    "diameter": "80",
                    "name_catalog": "KIT SCARICO VERTICALE B23 KHG 71411101",
                    "note": "Per tutti i modelli",
                    "inclusions": ["*"],
                    "exclusions": []
                },
                {
                    "code": "99237806",
                    "flue_type": "SPLIT",
                    "diameter": "80/80",
                    "name_catalog": "KIT SCARICO SEPARATO HT IN PP KHG 71405911",
                    "note": "Per tutti i modelli escluso Luna Classic / Century / Compact",
                    "inclusions": ["*"],
                    "exclusions": ["LUNA CLASSIC", "LUNA CENTURY", "LUNA COMPACT", "NUVOLA CENTURY"]
                },
                {
                    "code": "99328481",
                    "flue_type": "SPLIT",
                    "diameter": "80/80",
                    "name_catalog": "KIT SCARICO SEPARATO 7102689",
                    "note": "Per tutti i modelli escluso Luna Classic / Century / Compact",
                    "inclusions": ["*"],
                    "exclusions": ["LUNA CLASSIC", "LUNA CENTURY", "LUNA COMPACT", "NUVOLA CENTURY"]
                },
                {
                    "code": "50442942",
                    "flue_type": "SPLIT",
                    "diameter": "80/80",
                    "name_catalog": "KIT SCARICO SEPARATO KA00048",
                    "note": "Per Luna Prime",
                    "inclusions": ["LUNA PRIME", "PRIME"],
                    "exclusions": []
                }
            ]
        },
        "ARISTON": {
            "catalog_flue_page": 44,
            "compatible": [
                {
                    "code": "50346943",
                    "flue_type": "COAXIAL",
                    "diameter": "60/100",
                    "name_catalog": "KIT COASSIALE IN PP/PP CON TERMINALE DI SCARICO COLORE BIANCO",
                    "note": "Per tutti i modelli",
                    "inclusions": ["*"],
                    "exclusions": [],
                    "is_starter_kit": True
                },
                {
                    "code": "50347018",
                    "flue_type": "COAXIAL",
                    "diameter": "60/100",
                    "name_catalog": "KIT COASSIALE UNIVERSALE in PP/PP CON TERMINALE DI SCARICO COLORE BIANCO",
                    "note": "Per tutti i modelli",
                    "inclusions": ["*"],
                    "exclusions": []
                },
                {
                    "code": "50345847",
                    "flue_type": "COAXIAL",
                    "diameter": "60/100",
                    "name_catalog": "PARTENZA VERTICALE COASSIALE in pp/PVC CON PRELIEVO FUMI",
                    "note": "Per tutti i modelli",
                    "inclusions": ["*"],
                    "exclusions": []
                },
                {
                    "code": "50431434",
                    "flue_type": "SPLIT",
                    "diameter": "60/100 - 80/80",
                    "name_catalog": "KIT SDOPPIATO A CIABATTA ECO UNIVERSALE in PP/PP CON PRELIEVO FUMI",
                    "note": "Per tutti i modelli",
                    "inclusions": ["*"],
                    "exclusions": [],
                    "is_starter_kit": True
                },
                {
                    "code": "50345854",
                    "flue_type": "SPLIT",
                    "diameter": "80/80",
                    "name_catalog": "KIT CONDOTTI SEPARATI IN PP/PVC senza prelievo fumi",
                    "note": "Per tutti i modelli",
                    "inclusions": ["*"],
                    "exclusions": []
                }
            ],
            "original": [
                {
                    "code": "99178994",
                    "flue_type": "COAXIAL",
                    "diameter": "60/100",
                    "name_catalog": "Kit scarico coassiale da 1 mt. orizzontale 3318073",
                    "note": "Per tutti i modelli (Esclusi Alteas One Net, Genus One Net/System)",
                    "inclusions": ["*"],
                    "exclusions": ["ALTEAS", "GENUS ONE NET", "GENUS ONE SYSTEM"]
                },
                {
                    "code": "99616274",
                    "flue_type": "COAXIAL",
                    "diameter": "60/100",
                    "name_catalog": "Kit scarico coassiale 1 mt. orizzontale grigio 3319163",
                    "note": "Per Alteas One Net, Genus One Net / One System",
                    "inclusions": ["ALTEAS", "GENUS ONE NET", "GENUS ONE SYSTEM"],
                    "exclusions": []
                },
                {
                    "code": "99179007",
                    "flue_type": "COAXIAL",
                    "diameter": "60/100",
                    "name_catalog": "Partenza verticale 3318079",
                    "note": "Per tutti i modelli",
                    "inclusions": ["*"],
                    "exclusions": []
                },
                {
                    "code": "99616328",
                    "flue_type": "COAXIAL",
                    "diameter": "60/100",
                    "name_catalog": "Kit scarico coassiale verticale 1mt. bianco 3318074",
                    "note": "Per Clas One, Cares S, Clas B One, HS Premium",
                    "inclusions": ["CLAS ONE", "CARES S", "CLAS B ONE", "HS PREMIUM", "CLAS", "CARES"],
                    "exclusions": []
                },
                {
                    "code": "99616335",
                    "flue_type": "SPLIT",
                    "diameter": "60/100 - 80",
                    "name_catalog": "Kit scarico sdoppiato bianco 3318370",
                    "note": "Per Clas One, Cares S, Clas B One, HS Premium",
                    "inclusions": ["CLAS ONE", "CARES S", "CLAS B ONE", "HS PREMIUM", "CLAS", "CARES"],
                    "exclusions": []
                },
                {
                    "code": "99616298",
                    "flue_type": "SPLIT",
                    "diameter": "60/100 - 80",
                    "name_catalog": "Kit scarico sdoppiato grigio 3319161",
                    "note": "Per Alteas One Net, Genus One Net, Genus One System",
                    "inclusions": ["ALTEAS", "GENUS ONE NET", "GENUS ONE SYSTEM", "GENUS"],
                    "exclusions": []
                },
                {
                    "code": "50058433",
                    "flue_type": "SPLIT",
                    "diameter": "60/100 - 80",
                    "name_catalog": "ADATTATORE PER SISTEMI SDOPPIATI 3319497",
                    "note": "Per Cares Premium Ext - Genius One Net Ext",
                    "inclusions": ["EXT", "CARES PREMIUM EXT", "GENUS ONE NET EXT"],
                    "exclusions": []
                },
                {
                    "code": "99179014",
                    "flue_type": "SPLIT",
                    "diameter": "60/100 - 80",
                    "name_catalog": "Adattatore per sistemi sdoppiati bianco 3318369",
                    "note": "Per tutti i modelli (Esclusi Alteas / Genus)",
                    "inclusions": ["*"],
                    "exclusions": ["ALTEAS", "GENUS"]
                },
                {
                    "code": "99616250",
                    "flue_type": "SPLIT",
                    "diameter": "60/100 - 80",
                    "name_catalog": "Adattatore per sistemi sdoppiati grigio 3319159",
                    "note": "Per Alteas One Net, Genus One Net, Genus One System",
                    "inclusions": ["ALTEAS", "GENUS"],
                    "exclusions": []
                },
                {
                    "code": "99616359",
                    "flue_type": "COAXIAL",
                    "diameter": "80/125",
                    "name_catalog": "Kit scarico coassiale orizzontale 1mt 3318090",
                    "note": "Per Cares S - HS Premium",
                    "inclusions": ["CARES S", "HS PREMIUM", "CARES"],
                    "exclusions": []
                },
                {
                    "code": "99616366",
                    "flue_type": "COAXIAL",
                    "diameter": "80/125",
                    "name_catalog": "Kit scarico coassiale verticale 3318095",
                    "note": "Per Cares S - HS Premium",
                    "inclusions": ["CARES S", "HS PREMIUM", "CARES"],
                    "exclusions": []
                },
                {
                    "code": "99616267",
                    "flue_type": "SPLIT",
                    "diameter": "80 - 50",
                    "name_catalog": "Adattatore vert/orizz per sistema sdoppiato 3319139",
                    "note": "Per Alteas, Genus, Clas One",
                    "inclusions": ["ALTEAS", "GENUS", "CLAS"],
                    "exclusions": []
                }
            ]
        },
        "BERETTA": {
            "catalog_flue_page": 48,
            "compatible": [
                {
                    "code": "50346998",
                    "flue_type": "COAXIAL",
                    "diameter": "60/100",
                    "name_catalog": "KIT COASSIALE IN PP/PP CON TERMINALE DI SCARICO BIANCO",
                    "note": "Per tutti i modelli",
                    "inclusions": ["*"],
                    "exclusions": [],
                    "is_starter_kit": True
                },
                {
                    "code": "50347018",
                    "flue_type": "COAXIAL",
                    "diameter": "60/100",
                    "name_catalog": "KIT COASSIALE UNIVERSALE in PP/PP CON TERMINALE DI SCARICO BIANCO",
                    "note": "Per tutti i modelli",
                    "inclusions": ["*"],
                    "exclusions": []
                },
                {
                    "code": "50346080",
                    "flue_type": "COAXIAL",
                    "diameter": "60/100",
                    "name_catalog": "PARTENZA VERTICALE COASSIALE in PP/PVC CON PRELIEVO FUMI",
                    "note": "Per tutti i modelli",
                    "inclusions": ["*"],
                    "exclusions": []
                },
                {
                    "code": "50431427",
                    "flue_type": "SPLIT",
                    "diameter": "60/100 - 80/80",
                    "name_catalog": "KIT SDOPPIATO A CIABATTA riello in PP/PP CON PRELIEVO FUMI",
                    "note": "Per tutti i modelli",
                    "inclusions": ["*"],
                    "exclusions": [],
                    "is_starter_kit": True
                },
                {
                    "code": "50431434",
                    "flue_type": "SPLIT",
                    "diameter": "60/100 - 80/80",
                    "name_catalog": "KIT SDOPPIATO A CIABATTA ECO UNIVERSALE in PP/PP CON PRELIEVO FUMI",
                    "note": "Per tutti i modelli",
                    "inclusions": ["*"],
                    "exclusions": []
                },
                {
                    "code": "50346165",
                    "flue_type": "SPLIT",
                    "diameter": "80/80",
                    "name_catalog": "KIT CONDOTTI SEPARATI IN PP/PVC RIELLO - BERETTA",
                    "note": "Per modelli Exclusive X - Mynute Evo X - Mynute X Box - Ciao X",
                    "inclusions": ["EXCLUSIVE X", "MYNUTE EVO X", "MYNUTE X BOX", "MYNUTE X", "CIAO X", "EXCLUSIVE", "MYNUTE", "CIAO"],
                    "exclusions": []
                }
            ],
            "original": [
                {
                    "code": "99668167",
                    "flue_type": "COAXIAL",
                    "diameter": "60/100",
                    "name_catalog": "Collettore fumi a parete 20132018",
                    "note": "Per tutti i modelli escluso Exclusive X - Mynute X - Ciao X - Meteo X",
                    "inclusions": ["*"],
                    "exclusions": ["EXCLUSIVE X", "MYNUTE X", "CIAO X", "METEO X"]
                },
                {
                    "code": "99619268",
                    "flue_type": "COAXIAL",
                    "diameter": "60/100",
                    "name_catalog": "Kit terminale orizzontale con curva ribassata 20129175",
                    "note": "Per tutti i modelli esclusi Exclusive, Mynute",
                    "inclusions": ["*"],
                    "exclusions": ["EXCLUSIVE", "MYNUTE"]
                },
                {
                    "code": "99619275",
                    "flue_type": "COAXIAL",
                    "diameter": "60/100",
                    "name_catalog": "Kit adattatore attacco verticale 20129174",
                    "note": "Per Exclusive X - Mynute X - Ciao X - Meteo X",
                    "inclusions": ["EXCLUSIVE X", "MYNUTE X", "CIAO X", "METEO X", "EXCLUSIVE", "MYNUTE", "CIAO"],
                    "exclusions": []
                },
                {
                    "code": "99784508",
                    "flue_type": "SPLIT",
                    "diameter": "80",
                    "name_catalog": "KIT SISTEMA SDOPPIATO BERETTA/RIELLO 20129765",
                    "note": "Per Meteo Green He/He Box - Ciao X - Exclusive X - Mynute X / Box - Meteo X",
                    "inclusions": ["METEO GREEN", "CIAO X", "EXCLUSIVE X", "MYNUTE X", "METEO X", "CIAO", "EXCLUSIVE", "MYNUTE"],
                    "exclusions": []
                },
                {
                    "code": "99619251",
                    "flue_type": "SPLIT",
                    "diameter": "80",
                    "name_catalog": "Kit sistema sdoppiato con ingresso aria 20134830 orientabile",
                    "note": "Per Mynute X - Ciao At Low Nox - Ciao X - Exclusive X - Meteo X",
                    "inclusions": ["MYNUTE X", "CIAO AT", "CIAO X", "EXCLUSIVE X", "METEO X", "MYNUTE", "CIAO", "EXCLUSIVE"],
                    "exclusions": []
                },
                {
                    "code": "99643454",
                    "flue_type": "SPLIT",
                    "diameter": "80",
                    "name_catalog": "Adattatore scarico fumi con presa aria in box 20137527",
                    "note": "Per Ciao Green - Meteo Green He/He Box",
                    "inclusions": ["CIAO GREEN", "METEO GREEN"],
                    "exclusions": []
                },
                {
                    "code": "99654092",
                    "flue_type": "SPLIT",
                    "diameter": "80",
                    "name_catalog": "Sistema sdoppiato 20137501",
                    "note": "Per Ciao Green",
                    "inclusions": ["CIAO GREEN"],
                    "exclusions": []
                },
                {
                    "code": "99654115",
                    "flue_type": "SPLIT",
                    "diameter": "80",
                    "name_catalog": "Sistema sdoppiato 20137523",
                    "note": "Per Exclusive Boiler Green He - Mynute Boiler Green - Meteo Green He Box",
                    "inclusions": ["EXCLUSIVE BOILER", "MYNUTE BOILER", "METEO GREEN"],
                    "exclusions": []
                }
            ]
        },
        "RIELLO": {
            "catalog_flue_page": 54,
            "compatible": [
                {
                    "code": "50346998",
                    "flue_type": "COAXIAL",
                    "diameter": "60/100",
                    "name_catalog": "KIT COASSIALE IN PP/PP CON TERMINALE DI SCARICO BIANCO",
                    "note": "Per tutti i modelli",
                    "inclusions": ["*"],
                    "exclusions": [],
                    "is_starter_kit": True
                },
                {
                    "code": "50347018",
                    "flue_type": "COAXIAL",
                    "diameter": "60/100",
                    "name_catalog": "KIT COASSIALE UNIVERSALE in PP/PP CON TERMINALE DI SCARICO BIANCO",
                    "note": "Per tutti i modelli",
                    "inclusions": ["*"],
                    "exclusions": []
                },
                {
                    "code": "50346080",
                    "flue_type": "COAXIAL",
                    "diameter": "60/100",
                    "name_catalog": "PARTENZA VERTICALE COASSIALE in PP/PVC CON PRELIEVO FUMI",
                    "note": "Per tutti i modelli",
                    "inclusions": ["*"],
                    "exclusions": []
                },
                {
                    "code": "50431427",
                    "flue_type": "SPLIT",
                    "diameter": "60/100 - 80/80",
                    "name_catalog": "KIT SDOPPIATO A CIABATTA ECO in PP/PP CON PRELIEVO FUMI",
                    "note": "Per tutti i modelli",
                    "inclusions": ["*"],
                    "exclusions": [],
                    "is_starter_kit": True
                },
                {
                    "code": "50431434",
                    "flue_type": "SPLIT",
                    "diameter": "60/100 - 80/80",
                    "name_catalog": "KIT SDOPPIATO A CIABATTA ECO UNIVERSALE in PP/PP CON PRELIEVO FUMI",
                    "note": "Per tutti i modelli",
                    "inclusions": ["*"],
                    "exclusions": []
                },
                {
                    "code": "50346165",
                    "flue_type": "SPLIT",
                    "diameter": "80/80",
                    "name_catalog": "KIT SDOP 80/80 PP/PVC RIELLO - BERETTA",
                    "note": "Per tutti i modelli",
                    "inclusions": ["*"],
                    "exclusions": []
                },
                {
                    "code": "50346189",
                    "flue_type": "SPLIT",
                    "diameter": "80/80",
                    "name_catalog": "KIT CONDOTTI SEPARATI IN PP/PVC RIELLO CONDENS/EVO",
                    "note": "Per modelli In Condens Solar / Domus / Insieme",
                    "inclusions": ["IN CONDENS", "SOLAR", "DOMUS", "INSIEME"],
                    "exclusions": []
                }
            ],
            "original": [
                {
                    "code": "99784539",
                    "flue_type": "COAXIAL",
                    "diameter": "60/100",
                    "name_catalog": "COLLETTORE PARETE TELESCOPICO ø60/100",
                    "note": "Per tutti i modelli",
                    "inclusions": ["*"],
                    "exclusions": []
                },
                {
                    "code": "99668167",
                    "flue_type": "COAXIAL",
                    "diameter": "60/100",
                    "name_catalog": "COLLETTORE PARETE 60/100 20132018/RIELLO",
                    "note": "Per tutti i modelli",
                    "inclusions": ["*"],
                    "exclusions": []
                },
                {
                    "code": "99619275",
                    "flue_type": "COAXIAL",
                    "diameter": "60/100",
                    "name_catalog": "KIT ADATT ATTACCO VERTICALE 60/100",
                    "note": "Per tutti i modelli",
                    "inclusions": ["*"],
                    "exclusions": []
                },
                {
                    "code": "50332496",
                    "flue_type": "SPLIT",
                    "diameter": "80/80",
                    "name_catalog": "KIT SISTEMA SDOPP X FAMILY HM",
                    "note": "Per Family HM",
                    "inclusions": ["FAMILY HM", "FAMILY"],
                    "exclusions": []
                },
                {
                    "code": "99784508",
                    "flue_type": "SPLIT",
                    "diameter": "80",
                    "name_catalog": "KIT SISTEMA SDOPPIATO ø80 BERETTA/RIELLO",
                    "note": "Per tutti i modelli",
                    "inclusions": ["*"],
                    "exclusions": []
                },
                {
                    "code": "99619251",
                    "flue_type": "SPLIT",
                    "diameter": "80",
                    "name_catalog": "SIST SDOPPIATO ORIENT 60/100-80+80",
                    "note": "Per tutti i modelli",
                    "inclusions": ["*"],
                    "exclusions": []
                }
            ]
        },
        "BOSCH": {
            "catalog_flue_page": 61,
            "compatible": [
                {
                    "code": "50346202",
                    "flue_type": "COAXIAL",
                    "diameter": "60/100",
                    "name_catalog": "KIT COASSIALE in PP/PVC PER SCARICO FUMI BOSCH",
                    "note": "Per tutti i modelli",
                    "inclusions": ["*"],
                    "exclusions": [],
                    "is_starter_kit": True
                },
                {
                    "code": "50346219",
                    "flue_type": "COAXIAL",
                    "diameter": "60/100",
                    "name_catalog": "PARTENZA VERTICALE COASSIALE in pp/PVC CON PRELIEVO FUMI BOSCH",
                    "note": "Per tutti i modelli",
                    "inclusions": ["*"],
                    "exclusions": []
                },
                {
                    "code": "50431397",
                    "flue_type": "SPLIT",
                    "diameter": "60/100 - 80/80",
                    "name_catalog": "KIT SDOPPIATO A CIABATTA ECO in PP/PVC CON PRELIEVO FUMI BOSCH",
                    "note": "Per tutti i modelli",
                    "inclusions": ["*"],
                    "exclusions": [],
                    "is_starter_kit": True
                }
            ],
            "original": [
                {
                    "code": "99735845",
                    "flue_type": "COAXIAL",
                    "diameter": "60/100",
                    "name_catalog": "Kit fumi 7 738 112 497",
                    "note": "Per tutti i modelli",
                    "inclusions": ["*"],
                    "exclusions": []
                },
                {
                    "code": "99735685",
                    "flue_type": "COAXIAL",
                    "diameter": "60/100",
                    "name_catalog": "Kit fumi telescopico 7 738 112 499",
                    "note": "Per tutti i modelli",
                    "inclusions": ["*"],
                    "exclusions": []
                },
                {
                    "code": "99735722",
                    "flue_type": "COAXIAL",
                    "diameter": "80/125 - 60/100",
                    "name_catalog": "Adattatore verticale 7 738 112 636",
                    "note": "Per tutti i modelli",
                    "inclusions": ["*"],
                    "exclusions": []
                },
                {
                    "code": "99809720",
                    "flue_type": "SPLIT",
                    "diameter": "80-125 a 80-80",
                    "name_catalog": "Adattatore sdoppiato 7 738 113 529",
                    "note": "Per tutti i modelli",
                    "inclusions": ["*"],
                    "exclusions": []
                },
                {
                    "code": "99816063",
                    "flue_type": "COAXIAL",
                    "diameter": "80/125",
                    "name_catalog": "Kit fumi 7 738 112 577",
                    "note": "Per tutti i modelli",
                    "inclusions": ["*"],
                    "exclusions": []
                },
                {
                    "code": "99735692",
                    "flue_type": "COAXIAL",
                    "diameter": "60/100",
                    "name_catalog": "Camino con attacco caldaia verticale 7 738 112 504",
                    "note": "Per tutti i modelli",
                    "inclusions": ["*"],
                    "exclusions": []
                }
            ]
        },
        "IMMERGAS": {
            "catalog_flue_page": 67,
            "compatible": [
                {
                    "code": "50346974",
                    "flue_type": "COAXIAL",
                    "diameter": "60/100",
                    "name_catalog": "KIT COASSIALE IN PP/PP CON TERMINALE DI SCARICO COLORE BIANCO",
                    "note": "Per tutti i modelli",
                    "inclusions": ["*"],
                    "exclusions": [],
                    "is_starter_kit": True
                },
                {
                    "code": "50225934",
                    "flue_type": "COAXIAL",
                    "diameter": "60/100",
                    "name_catalog": "Kit fumi coassiale in PP/PVC",
                    "note": "Per tutti i modelli",
                    "inclusions": ["*"],
                    "exclusions": []
                },
                {
                    "code": "50346042",
                    "flue_type": "COAXIAL",
                    "diameter": "60/100",
                    "name_catalog": "PARTENZA VERTICALE COASSIALE in PP/PVC CON PRELIEVO FUMI",
                    "note": "Per tutti i modelli",
                    "inclusions": ["*"],
                    "exclusions": []
                },
                {
                    "code": "50346066",
                    "flue_type": "SPLIT",
                    "diameter": "80/80",
                    "name_catalog": "KIT CONDOTTI SEPARATI IN PP/PVC IMMERGAS senza prelievo fumi",
                    "note": "Per tutti i modelli",
                    "inclusions": ["*"],
                    "exclusions": [],
                    "is_starter_kit": True
                }
            ],
            "original": [
                {
                    "code": "99505394",
                    "flue_type": "COAXIAL",
                    "diameter": "60/100 - 851 mm",
                    "name_catalog": "Kit fumi orizzontale Short 3.024598",
                    "note": "Per tutti i modelli",
                    "inclusions": ["*"],
                    "exclusions": []
                },
                {
                    "code": "99070977",
                    "flue_type": "COAXIAL",
                    "diameter": "60/100 - 956 mm",
                    "name_catalog": "Kit fumi orizzontale 3.012000",
                    "note": "Per tutti i modelli",
                    "inclusions": ["*"],
                    "exclusions": []
                },
                {
                    "code": "99658403",
                    "flue_type": "COAXIAL",
                    "diameter": "60/100 - 956 mm",
                    "name_catalog": "Kit terminale orizz. orientabile 3.027408",
                    "note": "Per tutti i modelli",
                    "inclusions": ["*"],
                    "exclusions": []
                },
                {
                    "code": "99070991",
                    "flue_type": "COAXIAL",
                    "diameter": "60/100",
                    "name_catalog": "Partenza verticale 3.012086",
                    "note": "Per tutti i modelli",
                    "inclusions": ["*"],
                    "exclusions": []
                },
                {
                    "code": "99663674",
                    "flue_type": "COAXIAL",
                    "diameter": "60/100 - 50 cm",
                    "name_catalog": "Kit tubo prolunga 50 cm",
                    "note": "Per tutti i modelli",
                    "inclusions": ["*"],
                    "exclusions": []
                },
                {
                    "code": "99663681",
                    "flue_type": "COAXIAL",
                    "diameter": "60/100 - 100 cm",
                    "name_catalog": "Kit tubo prolunga 100 cm",
                    "note": "Per tutti i modelli",
                    "inclusions": ["*"],
                    "exclusions": []
                },
                {
                    "code": "99070984",
                    "flue_type": "SPLIT",
                    "diameter": "80/80",
                    "name_catalog": "Kit separatore 3.012002",
                    "note": "Per caldaie < 35 kW",
                    "inclusions": ["*"],
                    "exclusions": []
                },
                {
                    "code": "99131807",
                    "flue_type": "SPLIT",
                    "diameter": "80/80",
                    "name_catalog": "Kit sdoppiato 3.012087",
                    "note": "Per tutti i modelli",
                    "inclusions": ["*"],
                    "exclusions": []
                }
            ]
        },
        "HSD": {
            "catalog_flue_page": 71,
            "compatible": [
                {
                    "code": "50345991",
                    "flue_type": "COAXIAL",
                    "diameter": "60/100",
                    "name_catalog": "KIT COASSIALE in PP/PVC PER SCARICO FUMI",
                    "note": "Per tutti i modelli",
                    "inclusions": ["*"],
                    "exclusions": [],
                    "is_starter_kit": True
                },
                {
                    "code": "50431410",
                    "flue_type": "SPLIT",
                    "diameter": "60/100 - 80/80",
                    "name_catalog": "KIT SDOPPIATO A CIABATTA ECO in PP/PP CON PRELIEVO FUMI",
                    "note": "Per tutti i modelli",
                    "inclusions": ["*"],
                    "exclusions": [],
                    "is_starter_kit": True
                },
                {
                    "code": "50346967",
                    "flue_type": "COAXIAL",
                    "diameter": "60/100",
                    "name_catalog": "KIT COASSIALE IN PP/PP CON TERMINALE DI SCARICO",
                    "note": "Solo per Themis Condens",
                    "inclusions": ["THEMIS CONDENS", "THEMIS"],
                    "exclusions": []
                },
                {
                    "code": "50346004",
                    "flue_type": "COAXIAL",
                    "diameter": "60/100",
                    "name_catalog": "PARTENZA VERTICALE COASSIALE in PP/PVC CON PRELIEVO FUMI",
                    "note": "Per tutti i modelli escluso Themis Condens",
                    "inclusions": ["*"],
                    "exclusions": ["THEMIS CONDENS", "THEMIS"]
                }
            ],
            "original": [
                {
                    "code": "99778194",
                    "flue_type": "COAXIAL",
                    "diameter": "60/100",
                    "name_catalog": "Kit fumi 0010031041",
                    "note": "Per tutti i modelli escluso Themis Condens",
                    "inclusions": ["*"],
                    "exclusions": ["THEMIS CONDENS", "THEMIS"]
                },
                {
                    "code": "99778217",
                    "flue_type": "COAXIAL",
                    "diameter": "60/100",
                    "name_catalog": "Raccordo partenza verticale concentrico 0010031029",
                    "note": "Per tutti i modelli escluso Themis Condens",
                    "inclusions": ["*"],
                    "exclusions": ["THEMIS CONDENS", "THEMIS"]
                },
                {
                    "code": "99778170",
                    "flue_type": "SPLIT",
                    "diameter": "80/80",
                    "name_catalog": "Sdoppiatore 0010024098",
                    "note": "Per tutti i modelli escluso Themis Condens",
                    "inclusions": ["*"],
                    "exclusions": ["THEMIS CONDENS", "THEMIS"]
                }
            ]
        },
        "VAILLANT": {
            "catalog_flue_page": 74,
            "compatible": [
                {
                    "code": "50347001",
                    "flue_type": "COAXIAL",
                    "diameter": "60/100",
                    "name_catalog": "KIT COASSIALE IN PP/PP CON TERMINALE DI SCARICO COLORE BIANCO",
                    "note": "Per tutti i modelli",
                    "inclusions": ["*"],
                    "exclusions": [],
                    "is_starter_kit": True
                },
                {
                    "code": "50347018",
                    "flue_type": "COAXIAL",
                    "diameter": "60/100",
                    "name_catalog": "KIT COASSIALE UNIVERSALE in PP/PP CON TERMINALE DI SCARICO COLORE BIANCO",
                    "note": "Per tutti i modelli",
                    "inclusions": ["*"],
                    "exclusions": []
                },
                {
                    "code": "50346240",
                    "flue_type": "COAXIAL",
                    "diameter": "60/100",
                    "name_catalog": "PARTENZA VERTICALE COASSIALE in PP/PVC CON PRELIEVO FUMI",
                    "note": "Per tutti i modelli",
                    "inclusions": ["*"],
                    "exclusions": []
                },
                {
                    "code": "50431441",
                    "flue_type": "SPLIT",
                    "diameter": "60/100 - 80/80",
                    "name_catalog": "KIT SDOPPIATO A CIABATTA ECO in PP/PP CON PRELIEVO FUMI",
                    "note": "Per tutti i modelli",
                    "inclusions": ["*"],
                    "exclusions": [],
                    "is_starter_kit": True
                }
            ],
            "original": [
                {
                    "code": "99169176",
                    "flue_type": "COAXIAL",
                    "diameter": "60/100",
                    "name_catalog": "Kit scarico fumi con curva 87° 0020219517",
                    "note": "Per tutti i modelli",
                    "inclusions": ["*"],
                    "exclusions": []
                },
                {
                    "code": "99345419",
                    "flue_type": "SPLIT",
                    "diameter": "80/80",
                    "name_catalog": "Kit sdoppiato 0020147470",
                    "note": "Per tutti i modelli",
                    "inclusions": ["*"],
                    "exclusions": []
                }
            ]
        },
        "RINNAI": {
            "catalog_flue_page": 76,
            "compatible": [
                {
                    "code": "50347018",
                    "flue_type": "COAXIAL",
                    "diameter": "60/100",
                    "name_catalog": "KIT COASSIALE UNIVERSALE in PP/PP CON TERMINALE DI SCARICO COLORE BIANCO",
                    "note": "Per tutti i modelli",
                    "inclusions": ["*"],
                    "exclusions": [],
                    "is_starter_kit": True
                },
                {
                    "code": "50431434",
                    "flue_type": "SPLIT",
                    "diameter": "60/100 - 80/80",
                    "name_catalog": "KIT SDOPPIATO in PP/PP A CIABATTA ECO UNIVERSALE CON PRELIEVO FUMI",
                    "note": "Per tutti i modelli",
                    "inclusions": ["*"],
                    "exclusions": [],
                    "is_starter_kit": True
                }
            ],
            "original": [
                {
                    "code": "99736323",
                    "flue_type": "COAXIAL",
                    "diameter": "60/100",
                    "name_catalog": "Kit scarico a parete FOT-KX060-A07",
                    "note": "Per caldaia Zen",
                    "inclusions": ["ZEN"],
                    "exclusions": []
                },
                {
                    "code": "99504427",
                    "flue_type": "COAXIAL",
                    "diameter": "80/125",
                    "name_catalog": "Kit aspirazione/scarico fumi con curva 90° FOT-KS080-007",
                    "note": "Per caldaia Momiji - Zen",
                    "inclusions": ["MOMIJI", "ZEN"],
                    "exclusions": []
                },
                {
                    "code": "99736330",
                    "flue_type": "COAXIAL",
                    "diameter": "60/100 - 80/125",
                    "name_catalog": "Adattatore FOT-HX060-A15",
                    "note": "Per caldaia Zen",
                    "inclusions": ["ZEN"],
                    "exclusions": []
                },
                {
                    "code": "99736347",
                    "flue_type": "SPLIT",
                    "diameter": "80/80",
                    "name_catalog": "Adattatore sistema sdoppiato FOT-KB015",
                    "note": "Per caldaia Zen",
                    "inclusions": ["ZEN"],
                    "exclusions": []
                },
                {
                    "code": "99736354",
                    "flue_type": "SPLIT",
                    "diameter": "80/80 - 60/100",
                    "name_catalog": "Adattatore FOT-KS080-008",
                    "note": "Per caldaia Momiji",
                    "inclusions": ["MOMIJI"],
                    "exclusions": []
                }
            ]
        },
        "FONDITAL": {
            "catalog_flue_page": 78,
            "compatible": [
                {
                    "code": "50346967",
                    "flue_type": "COAXIAL",
                    "diameter": "60/100",
                    "name_catalog": "KIT COASSIALE IN PP/PP CON TERMINALE DI SCARICO COLORE BIANCO",
                    "note": "Per tutti i modelli",
                    "inclusions": ["*"],
                    "exclusions": [],
                    "is_starter_kit": True
                },
                {
                    "code": "50347018",
                    "flue_type": "COAXIAL",
                    "diameter": "60/100",
                    "name_catalog": "KIT COASSIALE UNIVERSALE in PP/PP CON TERMINALE DI SCARICO COLORE BIANCO",
                    "note": "Per tutti i modelli",
                    "inclusions": ["*"],
                    "exclusions": []
                },
                {
                    "code": "50345946",
                    "flue_type": "COAXIAL",
                    "diameter": "60/100",
                    "name_catalog": "PARTENZA VERTICALE COASSIALE in PP/PVC CON PRELIEVO FUMI",
                    "note": "Per tutti i modelli",
                    "inclusions": ["*"],
                    "exclusions": []
                },
                {
                    "code": "50431434",
                    "flue_type": "SPLIT",
                    "diameter": "60/100 - 80/80",
                    "name_catalog": "KIT SDOPPIATO A CIABATTA ECO UNIVERSALE in PP/PP CON PRELIEVO FUMI",
                    "note": "Per tutti i modelli",
                    "inclusions": ["*"],
                    "exclusions": [],
                    "is_starter_kit": True
                },
                {
                    "code": "50431403",
                    "flue_type": "SPLIT",
                    "diameter": "60/100 - 80/80",
                    "name_catalog": "KIT SDOPPIATO A CIABATTA ECO in PP/PP CON PRELIEVO FUMI",
                    "note": "Per tutti i modelli",
                    "inclusions": ["*"],
                    "exclusions": []
                },
                {
                    "code": "50345984",
                    "flue_type": "SPLIT",
                    "diameter": "80/80",
                    "name_catalog": "KIT CONDOTTI SEPARATI IN PP/PVC FONDITAL senza prelievo fumi",
                    "note": "Per tutti i modelli",
                    "inclusions": ["*"],
                    "exclusions": []
                }
            ],
            "original": [
                {
                    "code": "99337124",
                    "flue_type": "COAXIAL",
                    "diameter": "60/100 - 75 cm",
                    "name_catalog": "Kit fumi coassiale 75 cm 0condasp00",
                    "note": "Per tutti i modelli",
                    "inclusions": ["*"],
                    "exclusions": []
                },
                {
                    "code": "99335373",
                    "flue_type": "COAXIAL",
                    "diameter": "60/100",
                    "name_catalog": "Partenza verticale 0KITATCO00",
                    "note": "Per tutti i modelli",
                    "inclusions": ["*"],
                    "exclusions": []
                },
                {
                    "code": "50237401",
                    "flue_type": "SPLIT",
                    "diameter": "80/80",
                    "name_catalog": "Kit sdoppiatore 0KITSDOP08",
                    "note": "Per tutti i modelli",
                    "inclusions": ["*"],
                    "exclusions": []
                }
            ]
        },
        "DAIKIN": {
            "catalog_flue_page": 80,
            "compatible": [],
            "original": [
                {
                    "code": "50033256",
                    "flue_type": "COAXIAL",
                    "diameter": "60/100",
                    "name_catalog": "curva a 90° DN 60/100 c/attacco",
                    "note": "Per D2C",
                    "inclusions": ["D2C", "2DC", "*"],
                    "exclusions": [],
                    "is_starter_kit": True
                },
                {
                    "code": "50033263",
                    "flue_type": "COAXIAL",
                    "diameter": "60/100",
                    "name_catalog": "kit scarico fumi orizzontale",
                    "note": "Per D2C",
                    "inclusions": ["D2C", "2DC", "*"],
                    "exclusions": []
                },
                {
                    "code": "50073740",
                    "flue_type": "SPLIT",
                    "diameter": "80/80",
                    "name_catalog": "ATTACCO FUMI SDOPPIATO",
                    "note": "Per D2C",
                    "inclusions": ["D2C", "2DC", "*"],
                    "exclusions": [],
                    "is_starter_kit": True
                }
            ]
        }
    }
}

def main():
    print(f"Salvataggio regole di compatibilità fumi caldaie in {RULES_OUT_PATH}...")
    with open(RULES_OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(RULES_DATA, f, ensure_ascii=False, indent=2)
    print(f"Completato! Brand configurati: {len(RULES_DATA['brands'])}")

if __name__ == "__main__":
    main()
