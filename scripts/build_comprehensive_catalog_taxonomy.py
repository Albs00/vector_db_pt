"""
BUILD COMPREHENSIVE CATALOG TAXONOMY 2026
Mappa in modo esaustivo e definitivo TUTTE le famiglie commerciali ufficiali
del catalogo Puglia Termica 2026 (Pagine 468 - 626) per tutti i 26 marchi.
"""

import json
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

# Definizione esaustiva e rigorosa delle famiglie per brand
TAXONOMY = {
    # -------------------------------------------------------------
    # DAIKIN (Pagine 468 - 489)
    # -------------------------------------------------------------
    "DAIKIN": [
        {
            "id": "DAIKIN_PERFERA",
            "name": "PERFERA ALL SEASONS",
            "category": "RESIDENZIALE",
            "type": "PARETE",
            "pages": [468, 476, 478],
            "description": "Climatizzatore monosplit/multisplit a parete A+++ con tecnologia Flash Streamer.",
            "models_prefix": ["FTXM", "RXM"],
            "keywords": ["PERFERA", "FTXM", "RXM"]
        },
        {
            "id": "DAIKIN_SIESTA",
            "name": "SIESTA GSI",
            "category": "RESIDENZIALE",
            "type": "PARETE",
            "pages": [468],
            "description": "Serie monosplit Siesta ad alta efficienza energetica A++/A+.",
            "models_prefix": ["ATXF", "ARXF"],
            "keywords": ["SIESTA", "ATXF", "ARXF", "GSI"]
        },
        {
            "id": "DAIKIN_COMFORA",
            "name": "COMFORA",
            "category": "RESIDENZIALE",
            "type": "PARETE",
            "pages": [468],
            "description": "Unità a parete compatta e silenziosa A++/A++.",
            "models_prefix": ["FTXP", "RXP"],
            "keywords": ["COMFORA", "FTXP", "RXP"]
        },
        {
            "id": "DAIKIN_STYLISH",
            "name": "STYLISH",
            "category": "RESIDENZIALE",
            "type": "PARETE",
            "pages": [469],
            "description": "Design ultracompatto in 4 colori (Bianco, Argento, Blackwood, Nero Opaco).",
            "models_prefix": ["FTXA", "RXA"],
            "keywords": ["STYLISH", "FTXA", "RXA"]
        },
        {
            "id": "DAIKIN_EMURA",
            "name": "EMURA 3",
            "category": "RESIDENZIALE",
            "type": "PARETE",
            "pages": [469],
            "description": "Icona di design curvato Daikin, vincitore premi internazionali di design.",
            "models_prefix": ["FTXJ", "RXJ"],
            "keywords": ["EMURA", "FTXJ", "RXJ"]
        },
        {
            "id": "DAIKIN_URURU_SARARA",
            "name": "URURU SARARA",
            "category": "RESIDENZIALE",
            "type": "PARETE",
            "pages": [468],
            "description": "Sistema completo con umidificazione, deumidificazione e ventilazione.",
            "models_prefix": ["FTXZ", "RXZ"],
            "keywords": ["URURU", "SARARA", "FTXZ", "RXZ"]
        },
        {
            "id": "DAIKIN_SENSIRA",
            "name": "SENSIRA",
            "category": "RESIDENZIALE",
            "type": "PARETE",
            "pages": [470],
            "description": "Serie residenziale essenziale e affidabile ad alta efficienza A++.",
            "models_prefix": ["FTXF", "RXF"],
            "keywords": ["SENSIRA", "FTXF", "RXF"]
        },
        {
            "id": "DAIKIN_MULTI_MXM",
            "name": "MULTI SPLIT MXM-A8 / A9",
            "category": "RESIDENZIALE",
            "type": "MULTI_SPLIT",
            "pages": [470, 471],
            "description": "Unità esterne multi-split Bluevolution da 2 a 5 attacchi (2MXM, 3MXM, 4MXM, 5MXM).",
            "models_prefix": ["2MXM", "3MXM", "4MXM", "5MXM"],
            "keywords": ["2MXM", "3MXM", "4MXM", "5MXM", "MULTI MXM"]
        },
        {
            "id": "DAIKIN_FDXM",
            "name": "FDXM CANALIZZATA RIBASSATA",
            "category": "RESIDENZIALE",
            "type": "CANALIZZATO",
            "pages": [472, 476, 478],
            "description": "Unità interna canalizzabile ultracompatta (altezza 200 mm) per controsoffitti stretti.",
            "models_prefix": ["FDXM"],
            "keywords": ["FDXM"]
        },
        {
            "id": "DAIKIN_FFA",
            "name": "FFA CASSETTA 60x60 FULL FLAT",
            "category": "RESIDENZIALE",
            "type": "CASSETTA_60X60",
            "pages": [473, 477, 479],
            "description": "Cassetta 60x60 completamente piatta a filo controsoffitto.",
            "models_prefix": ["FFA"],
            "keywords": ["FFA", "FFA25", "FFA35", "FFA50", "FFA60"]
        },
        {
            "id": "DAIKIN_FCAG",
            "name": "FCAG ROUND FLOW CASSETTA 90x90",
            "category": "COMMERCIALE",
            "type": "CASSETTA_90X90",
            "pages": [474, 477, 479, 481, 488],
            "description": "Cassetta 90x90 con mandata a 360° Round Flow per distribuzione uniforme.",
            "models_prefix": ["FCAG", "FCAHG"],
            "keywords": ["FCAG", "FCAHG", "ROUND FLOW"]
        },
        {
            "id": "DAIKIN_FVXM",
            "name": "FVXM CONSOLE A PAVIMENTO",
            "category": "RESIDENZIALE",
            "type": "CONSOLE_PAVIMENTO",
            "pages": [472],
            "description": "Console a pavimento con doppio flusso e riscaldamento radiante pavimento.",
            "models_prefix": ["FVXM"],
            "keywords": ["FVXM", "CONSOLE FVXM"]
        },
        {
            "id": "DAIKIN_FNA",
            "name": "FNA INCASSO A PAVIMENTO",
            "category": "RESIDENZIALE",
            "type": "CONSOLE_PAVIMENTO",
            "pages": [473, 476],
            "description": "Unità ad incasso a parete o a pavimento per totale scomparsa.",
            "models_prefix": ["FNA"],
            "keywords": ["FNA", "INCASSO FNA"]
        },
        {
            "id": "DAIKIN_FBA",
            "name": "FBA CANALIZZATA MEDIA PREVALENZA",
            "category": "COMMERCIALE",
            "type": "CANALIZZATO",
            "pages": [480, 483, 487],
            "description": "Canalizzata commerciale a media prevalenza regolabile con pompa scarico condensa inclusa.",
            "models_prefix": ["FBA"],
            "keywords": ["FBA", "FBA35", "FBA50", "FBA60", "FBA71", "FBA100", "FBA125", "FBA140"]
        },
        {
            "id": "DAIKIN_FDA",
            "name": "FDA CANALIZZATA ALTA PREVALENZA",
            "category": "COMMERCIALE",
            "type": "CANALIZZATO",
            "pages": [483],
            "description": "Unità canalizzata ad altissima prevalenza fino a 200 Pa per grandi canalizzazioni.",
            "models_prefix": ["FDA"],
            "keywords": ["FDA", "FDA125"]
        },
        {
            "id": "DAIKIN_FAA",
            "name": "FAA PARETE COMMERCIALE",
            "category": "COMMERCIALE",
            "type": "PARETE",
            "pages": [480, 482],
            "description": "Unità a parete commerciale Sky Air per ambienti di grandi dimensioni.",
            "models_prefix": ["FAA"],
            "keywords": ["FAA", "FAA71", "FAA100"]
        },
        {
            "id": "DAIKIN_FUA",
            "name": "FUA CASSETTA PENSILE 4 VIE",
            "category": "COMMERCIALE",
            "type": "CASSETTA_PENSILE",
            "pages": [484],
            "description": "Cassetta pensile 4 vie senza necessità di controsoffitto.",
            "models_prefix": ["FUA"],
            "keywords": ["FUA", "FUA71", "FUA100", "FUA125"]
        },
        {
            "id": "DAIKIN_FVA",
            "name": "FVA COLONNA SKY AIR",
            "category": "COMMERCIALE",
            "type": "COLONNA",
            "pages": [485],
            "description": "Unità a colonna per sale ricevimento, negozi e open space con altezze elevate.",
            "models_prefix": ["FVA"],
            "keywords": ["FVA", "FVA71", "FVA100", "FVA125", "FVA140"]
        },
        {
            "id": "DAIKIN_MINISKY",
            "name": "MINI SKY MONOSPLIT ALPHA",
            "category": "COMMERCIALE",
            "type": "COMMERCIALE_UE",
            "pages": [476, 478],
            "description": "Unità esterne monosplit commerciali R32 compatte serie Alpha (RZAG35-60).",
            "models_prefix": ["RZAG35", "RZAG50", "RZAG60"],
            "keywords": ["MINISKY", "MINI SKY", "RZAG35", "RZAG50", "RZAG60"]
        },
        {
            "id": "DAIKIN_SKY_ACTIVE",
            "name": "SKY AIR ACTIVE R32",
            "category": "COMMERCIALE",
            "type": "COMMERCIALE_UE",
            "pages": [480, 481],
            "description": "Linea commerciale Sky Air Active entry-level ad alta efficienza (AZAS).",
            "models_prefix": ["AZAS"],
            "keywords": ["AZAS", "SKY ACTIVE", "SKY AIR ACTIVE"]
        },
        {
            "id": "DAIKIN_SKY_ADVANCE",
            "name": "SKY AIR ADVANCE R32",
            "category": "COMMERCIALE",
            "type": "COMMERCIALE_UE",
            "pages": [482, 483, 484, 485, 486],
            "description": "Linea commerciale Sky Air Advance per applicazioni terziarie e retail (RZASG, RZA).",
            "models_prefix": ["RZASG", "RZA200", "RZA250"],
            "keywords": ["RZASG", "RZA200", "RZA250", "SKY ADVANCE"]
        },
        {
            "id": "DAIKIN_SKY_ALPHA",
            "name": "SKY AIR ALPHA R32",
            "category": "COMMERCIALE",
            "type": "COMMERCIALE_UE",
            "pages": [486, 487, 488],
            "description": "Linea commerciale top di gamma Sky Air Alpha a massima efficienza energetica (RZAG71-140).",
            "models_prefix": ["RZAG71", "RZAG100", "RZAG125", "RZAG140"],
            "keywords": ["RZAG71", "RZAG100", "RZAG125", "RZAG140", "SKY ALPHA"]
        }
    ],

    # -------------------------------------------------------------
    # MITSUBISHI ELECTRIC (Pagine 490 - 509)
    # -------------------------------------------------------------
    "MITSUBISHI": [
        {
            "id": "MITSU_MSZ_HR",
            "name": "MSZ-HR SMART INVERTER",
            "category": "RESIDENZIALE",
            "type": "PARETE",
            "pages": [490],
            "description": "Climatizzatore monosplit e multisplit essenziale, silenzioso ed economico.",
            "models_prefix": ["MSZ-HR", "MUZ-HR", "HR25", "HR35", "HR42", "HR50"],
            "keywords": ["MSZ-HR", "MUZ-HR", "SMART INVERTER"]
        },
        {
            "id": "MITSU_MSZ_AP",
            "name": "MSZ-AP / MSZ-AP LARGE",
            "category": "RESIDENZIALE",
            "type": "PARETE",
            "pages": [490, 496],
            "description": "Serie compatta universale ad alta efficienza A+++, inclusa versione Large (60-71).",
            "models_prefix": ["MSZ-AP", "MUZ-AP"],
            "keywords": ["MSZ-AP", "MUZ-AP", "AP LARGE"]
        },
        {
            "id": "MITSU_MSZ_AY",
            "name": "MSZ-AY GENERATION",
            "category": "RESIDENZIALE",
            "type": "PARETE",
            "pages": [496],
            "description": "Finitura opaca vellutata, filtro V-Blocking e Dual Barrier Coating.",
            "models_prefix": ["MSZ-AY", "MUZ-AY"],
            "keywords": ["MSZ-AY", "MUZ-AY"]
        },
        {
            "id": "MITSU_MSZ_EF",
            "name": "MSZ-EF KIRIGAMINE ZEN",
            "category": "RESIDENZIALE",
            "type": "PARETE",
            "pages": [491, 496],
            "description": "Design elegante minimalista in 3 colorazioni: Bianco, Nero Lucido, Silver.",
            "models_prefix": ["MSZ-EF", "MUZ-EF"],
            "keywords": ["MSZ-EF", "MUZ-EF", "ZEN", "KIRIGAMINE ZEN"]
        },
        {
            "id": "MITSU_MSZ_LN",
            "name": "MSZ-LN KIRIGAMINE STYLE",
            "category": "RESIDENZIALE",
            "type": "PARETE",
            "pages": [492, 496],
            "description": "Top di gamma di design lussuoso in 4 colori con 3D i-See Sensor e Plasma Quad Plus.",
            "models_prefix": ["MSZ-LN", "MUZ-LN"],
            "keywords": ["MSZ-LN", "MUZ-LN", "KIRIGAMINE STYLE"]
        },
        {
            "id": "MITSU_MSZ_BT",
            "name": "MSZ-BT ESSENTIAL",
            "category": "RESIDENZIALE",
            "type": "PARETE",
            "pages": [496],
            "description": "Unità compatta residenziale con Wi-Fi integrato di serie e silenziosità record.",
            "models_prefix": ["MSZ-BT"],
            "keywords": ["MSZ-BT"]
        },
        {
            "id": "MITSU_MULTI_MXZ_HA",
            "name": "MXZ-HA MULTI SMART",
            "category": "RESIDENZIALE",
            "type": "MULTI_SPLIT",
            "pages": [493],
            "description": "Unità esterne multi-split serie Smart da 2 e 3 attacchi.",
            "models_prefix": ["MXZ-2HA", "MXZ-3HA"],
            "keywords": ["MXZ-2HA", "MXZ-3HA", "MULTI SMART"]
        },
        {
            "id": "MITSU_MULTI_MXZ_F",
            "name": "MXZ-F MULTI SPLIT INVERTER",
            "category": "RESIDENZIALE",
            "type": "MULTI_SPLIT",
            "pages": [494, 498],
            "description": "Unità esterne multi-split universali da 2 a 6 attacchi (MXZ-2F, 3F, 4F, 5F, 6F).",
            "models_prefix": ["MXZ-2F", "MXZ-3F", "MXZ-4F", "MXZ-5F", "MXZ-6F"],
            "keywords": ["MXZ-2F", "MXZ-3F", "MXZ-4F", "MXZ-5F", "MXZ-6F", "MXZ MULTI"]
        },
        {
            "id": "MITSU_SMALL_Y",
            "name": "PUMY-SP SMALL Y VRF MULTISPLIT",
            "category": "RESIDENZIALE",
            "type": "MULTI_SPLIT",
            "pages": [495],
            "description": "Sistemi VRF mini residenziali/commerciali Small Y con Branch Box.",
            "models_prefix": ["PUMY-SP", "PUMY-P"],
            "keywords": ["PUMY-SP", "PUMY", "SMALL Y"]
        },
        {
            "id": "MITSU_MLZ_KP",
            "name": "MLZ-KP / MLZ-KY CASSETTA 1 VIA",
            "category": "RESIDENZIALE",
            "type": "CASSETTA_1VIA",
            "pages": [497],
            "description": "Cassetta monovia ultracompatta specifica per controsoffitti stretti.",
            "models_prefix": ["MLZ-KP", "MLZ-KY"],
            "keywords": ["MLZ-KP", "MLZ-KY", "CASSETTA 1 VIA"]
        },
        {
            "id": "MITSU_MFZ_KT",
            "name": "MFZ-KT CONSOLE A PAVIMENTO",
            "category": "RESIDENZIALE",
            "type": "CONSOLE_PAVIMENTO",
            "pages": [497],
            "description": "Console a pavimento con tre deflettori per climatizzazione invernale ed estiva perfetta.",
            "models_prefix": ["MFZ-KT", "MFZ-KJ"],
            "keywords": ["MFZ-KT", "MFZ-KJ", "CONSOLE MFZ"]
        },
        {
            "id": "MITSU_SEZ_M",
            "name": "SEZ-M CANALIZZATA RIBASSATA",
            "category": "RESIDENZIALE",
            "type": "CANALIZZATO",
            "pages": [497],
            "description": "Unità interna canalizzabile ultracompatta da 200 mm per appartamenti e uffici.",
            "models_prefix": ["SEZ-M"],
            "keywords": ["SEZ-M", "SEZ-M25", "SEZ-M35", "SEZ-M50", "SEZ-M60", "SEZ-M71"]
        },
        {
            "id": "MITSU_SLZ_M",
            "name": "SLZ-M CASSETTA 60x60 4 VIE",
            "category": "COMMERCIALE",
            "type": "CASSETTA_60X60",
            "pages": [497, 500, 507],
            "description": "Cassetta 60x60 a 4 vie con 3D i-See Sensor opzionale e presa aria esterna.",
            "models_prefix": ["SLZ-M"],
            "keywords": ["SLZ-M", "SLZ-M25", "SLZ-M35", "SLZ-M50", "SLZ-M60"]
        },
        {
            "id": "MITSU_PEAD_M",
            "name": "PEAD-M CANALIZZATA MEDIA PREVALENZA",
            "category": "COMMERCIALE",
            "type": "CANALIZZATO",
            "pages": [499, 503, 507],
            "description": "Canalizzata commerciale Mr. Slim a media pressione fino a 150 Pa.",
            "models_prefix": ["PEAD-M"],
            "keywords": ["PEAD-M", "PEAD-M35", "PEAD-M50", "PEAD-M60", "PEAD-M71", "PEAD-M100", "PEAD-M125", "PEAD-M140"]
        },
        {
            "id": "MITSU_PEA_M",
            "name": "PEA-M CANALIZZATA ALTA PREVALENZA",
            "category": "COMMERCIALE",
            "type": "CANALIZZATO",
            "pages": [503],
            "description": "Canalizzata commerciale Mr. Slim ad alta prevalenza fino a 200 Pa.",
            "models_prefix": ["PEA-M"],
            "keywords": ["PEA-M", "PEA-M200", "PEA-M250"]
        },
        {
            "id": "MITSU_PKA_M",
            "name": "PKA-M PARETE COMMERCIALE",
            "category": "COMMERCIALE",
            "type": "PARETE",
            "pages": [499, 502, 507],
            "description": "Unità a parete commerciale Mr. Slim per uffici e negozi.",
            "models_prefix": ["PKA-M"],
            "keywords": ["PKA-M", "PKA-M35", "PKA-M50", "PKA-M60", "PKA-M71", "PKA-M100"]
        },
        {
            "id": "MITSU_PLA_M",
            "name": "PLA-M EA2 CASSETTA 90x90",
            "category": "COMMERCIALE",
            "type": "CASSETTA_90X90",
            "pages": [500, 504, 508],
            "description": "Cassetta 90x90 Mr. Slim a 4 vie con 3D i-See Sensor e flusso orizzontale Coanda.",
            "models_prefix": ["PLA-M", "PLA-RP"],
            "keywords": ["PLA-M", "PLA-M35", "PLA-M50", "PLA-M60", "PLA-M71", "PLA-M100", "PLA-M125", "PLA-M140"]
        },
        {
            "id": "MITSU_PCA_M",
            "name": "PCA-M KA2 / HA2 PENSILE SOFFITTO",
            "category": "COMMERCIALE",
            "type": "PENSILE_SOFFITTO",
            "pages": [501, 504, 505, 508],
            "description": "Pensile a soffitto Mr. Slim, disponibile anche in versione acciaio inox per cucine (HA2).",
            "models_prefix": ["PCA-M"],
            "keywords": ["PCA-M", "PCA-M50", "PCA-M60", "PCA-M71", "PCA-M100", "PCA-M125", "PCA-M140"]
        },
        {
            "id": "MITSU_PSA_M",
            "name": "PSA-M COLONNA MR SLIM",
            "category": "COMMERCIALE",
            "type": "COLONNA",
            "pages": [501, 505],
            "description": "Unità a colonna Mr. Slim a pavimento per locali commerciali e saloni.",
            "models_prefix": ["PSA-M"],
            "keywords": ["PSA-M", "PSA-M71", "PSA-M100", "PSA-M125", "PSA-M140"]
        },
        {
            "id": "MITSU_PUZ_ZM",
            "name": "POWER INVERTER PUZ-ZM",
            "category": "COMMERCIALE",
            "type": "COMMERCIALE_UE",
            "pages": [502, 503, 505, 506],
            "description": "Unità esterne commerciali top di gamma Power Inverter a lunghissime tubazioni.",
            "models_prefix": ["PUZ-ZM"],
            "keywords": ["PUZ-ZM", "POWER INVERTER"]
        },
        {
            "id": "MITSU_PUZ_M",
            "name": "STANDARD INVERTER PUZ-M / SUZ-M",
            "category": "COMMERCIALE",
            "type": "COMMERCIALE_UE",
            "pages": [499, 501, 506],
            "description": "Unità esterne commerciali Standard Inverter per applicazioni commerciali standard.",
            "models_prefix": ["PUZ-M", "SUZ-M"],
            "keywords": ["PUZ-M", "SUZ-M", "STANDARD INVERTER"]
        }
    ],

    # -------------------------------------------------------------
    # PANASONIC (Pagine 510 - 522)
    # -------------------------------------------------------------
    "PANASONIC": [
        {
            "id": "PANA_BZ",
            "name": "BZ COMPATTO",
            "category": "RESIDENZIALE",
            "type": "PARETE",
            "pages": [510],
            "description": "Unità a parete supercompatta da 779 mm con filtro PM2,5.",
            "models_prefix": ["CS-BZ", "CU-BZ"],
            "keywords": ["CS-BZ", "CU-BZ", "BZ"]
        },
        {
            "id": "PANA_TZ",
            "name": "TZ SUPER COMPATTO",
            "category": "RESIDENZIALE",
            "type": "PARETE",
            "pages": [510],
            "description": "Unità ultra-compatta con tecnologia nanoe X Generator Mark 1 integrata e Wi-Fi.",
            "models_prefix": ["CS-TZ", "CU-TZ"],
            "keywords": ["CS-TZ", "CU-TZ", "TZ"]
        },
        {
            "id": "PANA_ETHEREA",
            "name": "ETHEREA",
            "category": "RESIDENZIALE",
            "type": "PARETE",
            "pages": [511],
            "description": "Icona di design Panasonic con nanoe X Generator Mark 3 e classe A+++/A+++.",
            "models_prefix": ["CS-Z", "CS-XZ", "CU-Z"],
            "keywords": ["ETHEREA", "CS-Z", "CS-XZ", "CU-Z"]
        },
        {
            "id": "PANA_CONSOLE",
            "name": "CONSOLE DA PAVIMENTO",
            "category": "RESIDENZIALE",
            "type": "CONSOLE_PAVIMENTO",
            "pages": [512],
            "description": "Console a pavimento con nanoe X e doppio flusso d'aria.",
            "models_prefix": ["CS-Z25UFEAW", "CS-Z35UFEAW", "CS-Z50UFEAW", "CS-Z25CFEAW"],
            "keywords": ["CS-Z25UFEAW", "CONSOLE CS-Z", "CONSOLE PANASONIC"]
        },
        {
            "id": "PANA_MULTI_Z",
            "name": "MULTI Z",
            "category": "RESIDENZIALE",
            "type": "MULTI_SPLIT",
            "pages": [513, 514],
            "description": "Unità esterne multi-split Free Multi R32 da 2 a 5 attacchi.",
            "models_prefix": ["CU-2Z", "CU-3Z", "CU-4Z", "CU-5Z"],
            "keywords": ["CU-2Z", "CU-3Z", "CU-4Z", "CU-5Z", "MULTI Z"]
        },
        {
            "id": "PANA_CANALIZZATA_UD3",
            "name": "CANALIZZATA RESIDENZIALE UD3EA / CD3EA",
            "category": "RESIDENZIALE",
            "type": "CANALIZZATO",
            "pages": [514],
            "description": "Canalizzata ribassata slim per abitazioni e piccoli uffici.",
            "models_prefix": ["CS-MZ20UD3EA", "CS-Z25UD3EA", "CS-Z35UD3EA", "CS-Z50UD3EA", "CS-Z60UD3EA"],
            "keywords": ["UD3EA", "CD3EA", "CANALIZZATA RESIDENZIALE"]
        },
        {
            "id": "PANA_CASSETTA_UB4",
            "name": "CASSETTA 60x60 RESIDENZIALE UB4EA",
            "category": "RESIDENZIALE",
            "type": "CASSETTA_60X60",
            "pages": [514],
            "description": "Cassetta 60x60 4 vie per sistemi residenziali e multi.",
            "models_prefix": ["CS-MZ20UB4EA", "CS-Z25UB4EA", "CS-Z35UB4EA", "CS-Z50UB4EA", "CS-Z60UB4EA"],
            "keywords": ["UB4EA", "CASSETTA 60X60 UB4"]
        },
        {
            "id": "PANA_PACI_STANDARD",
            "name": "PACI NX STANDARD",
            "category": "COMMERCIALE",
            "type": "COMMERCIALE",
            "pages": [515, 516, 517],
            "description": "Gamma commerciale PACi NX Standard con canalizzate, cassette 90x90 e pensili a soffitto.",
            "models_prefix": ["U-100PZ", "U-125PZ", "U-140PZ", "U-36PZ", "U-50PZ", "U-60PZ", "U-71PZ"],
            "keywords": ["PACI NX STANDARD", "U-100PZ", "U-125PZ", "U-140PZ"]
        },
        {
            "id": "PANA_PACI_ELITE",
            "name": "PACI NX ELITE",
            "category": "COMMERCIALE",
            "type": "COMMERCIALE",
            "pages": [518, 519, 520],
            "description": "Gamma commerciale PACi NX Elite ad altissima efficienza stagionale A+++.",
            "models_prefix": ["U-100PZH", "U-125PZH", "U-140PZH", "U-36PZH", "U-50PZH", "U-60PZH", "U-71PZH"],
            "keywords": ["PACI NX ELITE", "U-100PZH", "U-125PZH", "U-140PZH"]
        },
        {
            "id": "PANA_BIG_PACI",
            "name": "BIG PACI ALTA PREVALENZA",
            "category": "COMMERCIALE",
            "type": "CANALIZZATO",
            "pages": [521],
            "description": "Unità commerciali di grande potenza 20-25 kW canalizzate ad altissima pressione.",
            "models_prefix": ["U-200PZH", "U-250PZH", "S-200PE", "S-250PE"],
            "keywords": ["BIG PACI", "U-200PZH", "U-250PZH"]
        }
    ],

    # -------------------------------------------------------------
    # TOSHIBA (Pagine 523 - 538)
    # -------------------------------------------------------------
    "TOSHIBA": [
        {
            "id": "TOSH_SEIYA",
            "name": "SEIYA CLASSIC / SEIYA",
            "category": "RESIDENZIALE",
            "type": "PARETE",
            "pages": [523],
            "description": "Climatizzatore a parete residenziale essenziale e silenzioso A++/A+.",
            "models_prefix": ["RAS-B10B2KVG", "RAS-B13B2KVG", "RAS-B16B2KVG", "RAS-B07E2KVG", "RAS-B10E2KVG"],
            "keywords": ["SEIYA", "RAS-B10B2KVG", "RAS-B13B2KVG", "RAS-B16B2KVG"]
        },
        {
            "id": "TOSH_SHORAI_EDGE",
            "name": "SHORAI EDGE",
            "category": "RESIDENZIALE",
            "type": "PARETE",
            "pages": [523],
            "description": "Design a linee rette con finitura opaca, filtro Ultra Pure e tecnologia Hada Care.",
            "models_prefix": ["RAS-B10G3KVSG", "RAS-B13G3KVSG", "RAS-B16G3KVSG", "RAS-B22G3KVSG", "RAS-B24G3KVSG"],
            "keywords": ["SHORAI", "SHORAI EDGE", "G3KVSG"]
        },
        {
            "id": "TOSH_DAISEIKAI_10",
            "name": "DAISEIKAI 10",
            "category": "RESIDENZIALE",
            "type": "PARETE",
            "pages": [524],
            "description": "Nuova ammiraglia Toshiba con materiali naturali/legno, ionizzatore al plasma e A+++.",
            "models_prefix": ["RAS-B10S4KVPG", "RAS-B13S4KVPG", "RAS-B16S4KVPG", "RAS-10S4AVPG", "RAS-13S4AVPG"],
            "keywords": ["DAISEIKAI", "DAISEIKAI 10", "S4KVPG", "S4AVPG"]
        },
        {
            "id": "TOSH_HAORI",
            "name": "HAORI",
            "category": "RESIDENZIALE",
            "type": "PARETE",
            "pages": [524, 526],
            "description": "Esclusivo climatizzatore a parete con rivestimento in tessuto personalizzabile.",
            "models_prefix": ["RAS-B10N4KVRG", "RAS-B13N4KVRG", "RAS-B16N4KVRG"],
            "keywords": ["HAORI", "N4KVRG"]
        },
        {
            "id": "TOSH_CONSOLE",
            "name": "CONSOLE A PAVIMENTO",
            "category": "RESIDENZIALE",
            "type": "CONSOLE_PAVIMENTO",
            "pages": [524],
            "description": "Console a pavimento con diffusione bi-flow e funzione riscaldamento radiante a pavimento.",
            "models_prefix": ["RAS-B10J2FVG", "RAS-B13J2FVG", "RAS-B18J2FVG"],
            "keywords": ["RAS-B10J2FVG", "J2FVG", "CONSOLE TOSHIBA"]
        },
        {
            "id": "TOSH_MULTI_RAS",
            "name": "MULTI SPLIT RAS-M",
            "category": "RESIDENZIALE",
            "type": "MULTI_SPLIT",
            "pages": [525],
            "description": "Unità esterne multi-split R32 da 2 a 5 attacchi (2M10, 2M14, 2M18, 3M26, 4M27, 5M34).",
            "models_prefix": ["RAS-2M", "RAS-3M", "RAS-4M", "RAS-5M"],
            "keywords": ["RAS-2M", "RAS-3M", "RAS-4M", "RAS-5M", "MULTI RAS"]
        },
        {
            "id": "TOSH_CANALIZZATA_M",
            "name": "CANALIZZATA RIBASSATA / ULTRAPIATTA",
            "category": "RESIDENZIALE",
            "type": "CANALIZZATO",
            "pages": [527, 528],
            "description": "Canalizzata ribassata da 210 mm per controsoffitti residenziali.",
            "models_prefix": ["RAS-M07U2DVG", "RAS-M10U2DVG", "RAS-M13U2DVG", "RAS-M16U2DVG", "RAV-HM301SDTY"],
            "keywords": ["U2DVG", "SDTY", "CANALIZZATA RIBASSATA"]
        },
        {
            "id": "TOSH_CASSETTA_60",
            "name": "CASSETTA 4 VIE 60x60",
            "category": "RESIDENZIALE",
            "type": "CASSETTA_60X60",
            "pages": [527, 528, 529],
            "description": "Cassetta 60x60 compatta a 4 vie con mandata orientabile indipendente.",
            "models_prefix": ["RAS-M10U2MUVG", "RAS-M13U2MUVG", "RAS-M16U2MUVG", "RAV-HM301MUT", "RAV-HM401MUT", "RAV-HM561MUT"],
            "keywords": ["U2MUVG", "MUTP", "MUT", "CASSETTA 60X60 TOSHIBA"]
        },
        {
            "id": "TOSH_COMMERCIALE_RAV",
            "name": "COMMERCIALE RAV (DIGITAL / SUPER DIGITAL / BIG)",
            "category": "COMMERCIALE",
            "type": "COMMERCIALE",
            "pages": [528, 529, 530, 531, 532, 533, 534, 535, 536, 537, 538],
            "description": "Gamma commerciale RAV con Digital Inverter, Digital Classic, Super Digital e Big Digital Inverter.",
            "models_prefix": ["RAV-GM", "RAV-GV", "RAV-GP", "RAV-HM", "RAV-RM"],
            "keywords": ["RAV-GM", "RAV-GV", "RAV-GP", "RAV-HM", "RAV-RM", "DIGITAL INVERTER", "SUPER DIGITAL"]
        }
    ],

    # -------------------------------------------------------------
    # MIDEA (Pagine 539 - 547)
    # -------------------------------------------------------------
    "MIDEA": [
        {
            "id": "MIDEA_ALYA",
            "name": "ALYA",
            "category": "RESIDENZIALE",
            "type": "PARETE",
            "pages": [539],
            "description": "Serie residenziale monosplit Alya con Wi-Fi di serie e triplo filtro.",
            "models_prefix": ["ALYA", "MSAFB"],
            "keywords": ["ALYA", "MSAFB"]
        },
        {
            "id": "MIDEA_BREEZELESS",
            "name": "BREEZELESS / BREEZELESS E",
            "category": "RESIDENZIALE",
            "type": "PARETE",
            "pages": [539, 541],
            "description": "Esclusiva tecnologia con microfori TwinFlap per comfort assoluto senza getti diretti.",
            "models_prefix": ["MSFAAU", "CB1"],
            "keywords": ["BREEZELESS", "MSFAAU", "CB1"]
        },
        {
            "id": "MIDEA_ALL_EASY_PRO",
            "name": "ALL EASY PRO",
            "category": "RESIDENZIALE",
            "type": "PARETE",
            "pages": [539],
            "description": "Climatizzatore progettato per installazione e manutenzione velocissima in 1 minuto.",
            "models_prefix": ["AE PRO", "MSXAU"],
            "keywords": ["ALL EASY PRO", "AE PRO", "MSXAU"]
        },
        {
            "id": "MIDEA_MULTI_SPLIT",
            "name": "MULTI SPLIT M2O / M3O / M4O / M5O",
            "category": "RESIDENZIALE",
            "type": "MULTI_SPLIT",
            "pages": [540, 542, 543, 544, 545],
            "description": "Unità esterne multi-split da 2 a 5 attacchi serie M2O, M3O, M4O, M5O.",
            "models_prefix": ["M2O", "M3O", "M4O", "M5O"],
            "keywords": ["M2O", "M3O", "M4O", "M5O", "M2OE", "M3OA", "M4OE", "M5OE"]
        },
        {
            "id": "MIDEA_COMMERCIALE",
            "name": "COMMERCIALE MIDEA (CANALIZZATO / CASSETTA / CONSOLE / COLONNA)",
            "category": "COMMERCIALE",
            "type": "COMMERCIALE",
            "pages": [541, 546, 547],
            "description": "Gamma commerciale con canalizzati MTI/MTJ, cassette MCA/MCD, pavimento-soffitto MUE e colonne MFM.",
            "models_prefix": ["MTI", "MTJ", "MCA", "MCD", "MUE", "MFM", "MOD"],
            "keywords": ["MTI", "MTJ", "MCA", "MCD", "MUE", "MFM", "MOD", "COMMERCIALE MIDEA"]
        }
    ],

    # -------------------------------------------------------------
    # HISENSE (Pagine 548 - 552)
    # -------------------------------------------------------------
    "HISENSE": [
        {
            "id": "HIS_AIR_MASTER",
            "name": "AIR MASTER",
            "category": "RESIDENZIALE",
            "type": "PARETE",
            "pages": [548, 550],
            "description": "Serie residenziale ad alta efficienza energetica A+++ con intelligenza artificiale TMS.",
            "models_prefix": ["AS25WM", "AS35WM", "AS50FM"],
            "keywords": ["AIR MASTER", "AS25WM", "AS35WM", "AS50FM"]
        },
        {
            "id": "HIS_ENERGY_PRO",
            "name": "ENERGY PRO PLUS / ENERGY PRO X",
            "category": "RESIDENZIALE",
            "type": "PARETE",
            "pages": [548, 550],
            "description": "Sensore intelligente di presenza, flusso 4D, purificazione Hi-Nano e A+++.",
            "models_prefix": ["QE25", "QE35", "QE50", "ENERGY PRO"],
            "keywords": ["ENERGY PRO", "ENERGY PRO PLUS", "ENERGY PRO X"]
        },
        {
            "id": "HIS_COMFORT",
            "name": "COMFORT / EASY SMART",
            "category": "RESIDENZIALE",
            "type": "PARETE",
            "pages": [548],
            "description": "Climatizzatore monosplit entry-level con display LED a scomparsa e Wi-Fi.",
            "models_prefix": ["DJ25", "DJ35", "CA25", "CA35"],
            "keywords": ["COMFORT", "EASY SMART"]
        },
        {
            "id": "HIS_MULTI_SPLIT",
            "name": "MULTI SPLIT 2AMW / 3AMW / 4AMW / 5AMW",
            "category": "RESIDENZIALE",
            "type": "MULTI_SPLIT",
            "pages": [549, 550],
            "description": "Unità esterne multi-split R32 da 2 a 5 attacchi.",
            "models_prefix": ["2AMW", "3AMW", "4AMW", "5AMW"],
            "keywords": ["2AMW", "3AMW", "4AMW", "5AMW", "MULTI HISENSE"]
        },
        {
            "id": "HIS_COMMERCIALE",
            "name": "COMMERCIALE HISENSE (TURBO / CASSETTA / CANALIZZATO / COLONNA)",
            "category": "COMMERCIALE",
            "type": "COMMERCIALE",
            "pages": [549, 551, 552],
            "description": "Gamma commerciale Turbo con cassette Round-Flow AUC, canalizzati ADT/AUD, soffitto AUV e colonna AUF.",
            "models_prefix": ["AUW", "AUC", "AUD", "ADT", "AUV", "AUF"],
            "keywords": ["AUW", "AUC", "AUD", "ADT", "AUV", "AUF", "COMMERCIALE HISENSE", "TURBO 105"]
        }
    ],

    # -------------------------------------------------------------
    # KOSAMI (Pagine 553 - 555, 624)
    # -------------------------------------------------------------
    "KOSAMI": [
        {
            "id": "KOS_BORA",
            "name": "BORA",
            "category": "RESIDENZIALE",
            "type": "PARETE",
            "pages": [553],
            "description": "Serie residenziale monosplit compatta ed efficiente.",
            "models_prefix": ["BORA"],
            "keywords": ["BORA", "UE BORA", "UI BORA"]
        },
        {
            "id": "KOS_VENUS",
            "name": "VENUS / WINTER",
            "category": "RESIDENZIALE",
            "type": "PARETE",
            "pages": [553, 554],
            "description": "Climatizzatore monosplit e multisplit ad alte prestazioni termiche anche a basse temperature esterne.",
            "models_prefix": ["VENUS", "WINTER"],
            "keywords": ["VENUS", "WINTER"]
        },
        {
            "id": "KOS_PAROS",
            "name": "PAROS MULTI SPLIT",
            "category": "RESIDENZIALE",
            "type": "MULTI_SPLIT",
            "pages": [554],
            "description": "Unità esterne multi-split Paros da 2 a 5 attacchi.",
            "models_prefix": ["PAROS"],
            "keywords": ["PAROS", "MULTI PAROS"]
        },
        {
            "id": "KOS_COMMERCIALE",
            "name": "COMMERCIALE KOSAMI (CANALIZZATO / CASSETTA)",
            "category": "COMMERCIALE",
            "type": "COMMERCIALE",
            "pages": [555],
            "description": "Unità commerciali canalizzate e cassette 4 vie da 24.000 a 60.000 BTU.",
            "models_prefix": ["UEKOCOMM", "UIKOCOMM", "CAN-CASS"],
            "keywords": ["UE COMM CAN-CASS", "UI COMM CAN-CASS", "UEKOCOMM"]
        },
        {
            "id": "KOS_SENZA_UNITA_ESTERNA",
            "name": "KOSAMI SENZA UNITA ESTERNA MONOBLOCCO",
            "category": "SENZA_UNITA_ESTERNA",
            "type": "SENZA_UNITA_ESTERNA",
            "pages": [624],
            "description": "Monoblocco verticale e orizzontale a parete/soffitto senza unità esterna.",
            "models_prefix": ["C5MO", "MONOBLOCCO P/C"],
            "keywords": ["C5MO09", "C5MO12", "C5MO14", "MONOBLOCCO P/C"]
        }
    ],

    # -------------------------------------------------------------
    # HAIER (Pagine 556 - 570)
    # -------------------------------------------------------------
    "HAIER": [
        {
            "id": "HAIER_TIDE_R",
            "name": "HEC TIDE R",
            "category": "RESIDENZIALE",
            "type": "PARETE",
            "pages": [556],
            "description": "Serie residenziale entry-level HEC Tide R affidabile ed economica.",
            "models_prefix": ["HEC25", "HEC35", "HEC50", "TIDE R"],
            "keywords": ["HEC TIDE", "TIDE R", "HEC25", "HEC35", "HEC50"]
        },
        {
            "id": "HAIER_REVIVE",
            "name": "REVIVE",
            "category": "RESIDENZIALE",
            "type": "PARETE",
            "pages": [556, 561],
            "description": "Serie residenziale compatta ad alta efficienza A++ con funzione Self-Clean.",
            "models_prefix": ["AS25TH", "AS35TH", "AS50TH", "REVIVE"],
            "keywords": ["REVIVE", "AS25TH", "AS35TH", "AS50TH"]
        },
        {
            "id": "HAIER_GEOS_PLUS",
            "name": "GEOS PLUS+",
            "category": "RESIDENZIALE",
            "type": "PARETE",
            "pages": [556, 561],
            "description": "Climatizzatore monosplit e multisplit best-seller con controllo Wi-Fi hOn.",
            "models_prefix": ["AS25RH", "AS35RH", "AS50RH", "GEOS"],
            "keywords": ["GEOS", "GEOS PLUS", "GEOS PL"]
        },
        {
            "id": "HAIER_PEARL",
            "name": "PEARL / PEARL PREMIUM",
            "category": "RESIDENZIALE",
            "type": "PARETE",
            "pages": [557],
            "description": "Design bianco perla opaco con tecnologia UV-C Pro Sterilization e Coanda Plus.",
            "models_prefix": ["AS25PB", "AS35PB", "AS50PB", "PEARL"],
            "keywords": ["PEARL", "AS25PB", "AS35PB", "AS50PB"]
        },
        {
            "id": "HAIER_EXPERT",
            "name": "EXPERT (WHITE / BLACK)",
            "category": "RESIDENZIALE",
            "type": "PARETE",
            "pages": [557, 564],
            "description": "Top di gamma Haier con lampada UV-C Pro, UVC Sterilization e igienizzazione a 56°C.",
            "models_prefix": ["AS25XCA", "AS35XCA", "AS50XCA", "AS71XCA", "EXPERT"],
            "keywords": ["EXPERT", "AS25XCA", "AS35XCA", "AS50XCA", "AS71XCA"]
        },
        {
            "id": "HAIER_FLEXIS_PLUS",
            "name": "FLEXIS PLUS (WHITE / MATT BLACK / SILVER)",
            "category": "RESIDENZIALE",
            "type": "PARETE",
            "pages": [557],
            "description": "Design squadrato di lusso con finitura opaca, Eco Sensor e sterilizzazione UV-C.",
            "models_prefix": ["AS25S2SF", "AS35S2SF", "AS50S2SF", "FLEXIS"],
            "keywords": ["FLEXIS", "FLEXIS PLUS", "AS25S2SF", "AS35S2SF"]
        },
        {
            "id": "HAIER_SUPER_MATCH_1U",
            "name": "SUPER MATCH 1U MONOSPLIT",
            "category": "RESIDENZIALE",
            "type": "COMMERCIALE_UE",
            "pages": [557, 560],
            "description": "Unità esterne monosplit universali Super Match 1U25, 1U35, 1U42, 1U50, 1U71.",
            "models_prefix": ["1U25", "1U35", "1U42", "1U50", "1U71"],
            "keywords": ["1U25", "1U35", "1U42", "1U50", "1U71", "SUPER MATCH 1U"]
        },
        {
            "id": "HAIER_MULTI_SPLIT",
            "name": "MULTI SPLIT 2U / 3U / 4U / 5U",
            "category": "RESIDENZIALE",
            "type": "MULTI_SPLIT",
            "pages": [561, 562, 564],
            "description": "Unità esterne multi-split universali da 2 a 5 attacchi (2U40, 2U50, 3U55, 3U70, 4U75, 4U85, 5U90, 5U105, 5U125).",
            "models_prefix": ["2U40", "2U50", "3U55", "3U70", "4U75", "4U85", "5U90", "5U105", "5U125"],
            "keywords": ["2U40", "2U50", "3U55", "3U70", "4U75", "4U85", "5U90", "5U105", "5U125", "MULTI HAIER"]
        },
        {
            "id": "HAIER_COMMERCIALE_SUPER_MATCH",
            "name": "COMMERCIALE SUPER MATCH (CANALIZZATO / CASSETTA / CONSOLE / COLONNA)",
            "category": "COMMERCIALE",
            "type": "COMMERCIALE",
            "pages": [558, 559, 560, 563, 565, 566, 567, 568, 569],
            "description": "Gamma commerciale con canalizzati ribassati e media/alta prevalenza AD/ADH, cassette AB/ABH, console AF, e colonne AP.",
            "models_prefix": ["ADH", "ABH", "AB", "AF", "AP", "1U105", "1U125", "1U140", "1UH200", "1UH250"],
            "keywords": ["ADH", "ABH", "AB105", "AB125", "AF50", "AP105", "AP140", "1U105", "1U125", "1U140", "1UH200", "1UH250", "COMMERCIALE SUPER MATCH"]
        }
    ],

    # -------------------------------------------------------------
    # SAMSUNG (Pagine 571 - 581)
    # -------------------------------------------------------------
    "SAMSUNG": [
        {
            "id": "SAMSUNG_AR35",
            "name": "AR35 (MALDIVES EVOLUTION)",
            "category": "RESIDENZIALE",
            "type": "PARETE",
            "pages": [571],
            "description": "Serie residenziale monosplit AR35 essenziale, economica e affidabile A++/A+.",
            "models_prefix": ["AR09TXHQASI", "AR12TXHQASI", "AR18TXHQASI", "AR24TXHQASI", "AR35"],
            "keywords": ["AR35", "TXHQASI"]
        },
        {
            "id": "SAMSUNG_WINDFREE_PREMIERE",
            "name": "WINDFREE PREMIÈRE+",
            "category": "RESIDENZIALE",
            "type": "PARETE",
            "pages": [572, 575],
            "description": "Top di gamma assoluto WindFree con intelligenza artificiale avanzata, 21.000 microfori e classe A+++.",
            "models_prefix": ["AR70H09", "AR70H12", "AR70H18", "AR70H24", "AR70H"],
            "keywords": ["PREMIERE", "PREMIÈRE", "AR70H"]
        },
        {
            "id": "SAMSUNG_WINDFREE_ELITE",
            "name": "WINDFREE ELITE / BLACK",
            "category": "RESIDENZIALE",
            "type": "PARETE",
            "pages": [571, 575],
            "description": "Serie WindFree ad altissima efficienza A+++ con sensore di movimento (MDS) e filtro Tri-Care.",
            "models_prefix": ["AR09TXCAAWK", "AR12TXCAAWK", "TXCAAWK"],
            "keywords": ["WINDFREE ELITE", "TXCAAWK"]
        },
        {
            "id": "SAMSUNG_WINDFREE_AVANT",
            "name": "WINDFREE AVANT",
            "category": "RESIDENZIALE",
            "type": "PARETE",
            "pages": [575],
            "description": "Serie WindFree a parete con filtro antibatterico Tri-Care e controllo vocale Bixby/Google/Alexa.",
            "models_prefix": ["AR09TXEAAWK", "AR12TXEAAWK", "AR18TXEAAWK", "AR24TXEAAWK", "TXEAAWK"],
            "keywords": ["WINDFREE AVANT", "TXEAAWK", "AVANT"]
        },
        {
            "id": "SAMSUNG_WINDFREE_COMFORT",
            "name": "WINDFREE COMFORT",
            "category": "RESIDENZIALE",
            "type": "PARETE",
            "pages": [575],
            "description": "La gamma WindFree con il miglior rapporto qualità-prezzo e connettività SmartThings.",
            "models_prefix": ["AR09TXFCAWK", "AR12TXFCAWK", "AR18TXFCAWK", "AR24TXFCAWK", "TXFCAWK"],
            "keywords": ["WINDFREE COMFORT", "TXFCAWK", "COMFORT"]
        },
        {
            "id": "SAMSUNG_CEBU",
            "name": "CEBU WI-FI",
            "category": "RESIDENZIALE",
            "type": "PARETE",
            "pages": [575],
            "description": "Climatizzatore tradizionale senza tecnologia WindFree ma con Wi-Fi SmartThings di serie.",
            "models_prefix": ["AR09TXFYAWK", "AR12TXFYAWK", "AR18TXFYAWK", "AR24TXFYAWK", "TXFYAWK"],
            "keywords": ["CEBU", "TXFYAWK"]
        },
        {
            "id": "SAMSUNG_MULTI_FJM",
            "name": "MULTI SPLIT FJM",
            "category": "RESIDENZIALE",
            "type": "MULTI_SPLIT",
            "pages": [573, 575],
            "description": "Unità esterne Free Joint Multi (FJM) R32 da 2 a 5 attacchi (AJ040, AJ050, AJ052, AJ068, AJ080, AJ100).",
            "models_prefix": ["AJ040", "AJ050", "AJ052", "AJ068", "AJ080", "AJ100"],
            "keywords": ["AJ040", "AJ050", "AJ052", "AJ068", "AJ080", "AJ100", "MULTI FJM"]
        },
        {
            "id": "SAMSUNG_COMMERCIALE_CAC",
            "name": "COMMERCIALE CAC (WINDFREE 360° / CASSETTE / CANALIZZATI / COLONNA)",
            "category": "COMMERCIALE",
            "type": "COMMERCIALE",
            "pages": [574, 576, 577, 578, 579, 580],
            "description": "Gamma commerciale CAC con WindFree 360° circolare, cassette 4 vie/1 via WindFree, canalizzati LSP/MSP/HSP e colonna.",
            "models_prefix": ["AC026", "AC035", "AC052", "AC071", "AC090", "AC100", "AC120", "AC140", "AC200", "AC250"],
            "keywords": ["AC026", "AC035", "AC052", "AC071", "AC090", "AC100", "AC120", "AC140", "AC200", "AC250", "COMMERCIALE CAC", "WINDFREE 360"]
        }
    ],

    # -------------------------------------------------------------
    # LG (Pagine 582 - 593)
    # -------------------------------------------------------------
    "LG": [
        {
            "id": "LG_DUALCOOL_DELUXE",
            "name": "DUALCOOL DELUXE AI AIR",
            "category": "RESIDENZIALE",
            "type": "PARETE",
            "pages": [582],
            "description": "Nuova linea DUALCOOL Deluxe con intelligenza artificiale AI Air, purificatore d'aria e classe A+++.",
            "models_prefix": ["H09S1DA", "H12S1DA", "H18S1DA", "H24S1DA"],
            "keywords": ["DUALCOOL DELUXE", "H09S1DA", "H12S1DA", "H18S1DA", "H24S1DA"]
        },
        {
            "id": "LG_ARTCOOL_GALLERY",
            "name": "ARTCOOL GALLERY PHOTO / LCD",
            "category": "RESIDENZIALE",
            "type": "PARETE",
            "pages": [583],
            "description": "Icona mondiale di design quadrato a quadro d'autore o con display LCD full-color personalizzabile.",
            "models_prefix": ["A09GA2", "A12GA2", "ARTCOOL GALLERY"],
            "keywords": ["ARTCOOL GALLERY", "A09GA2", "A12GA2"]
        },
        {
            "id": "LG_ARTCOOL_MIRROR",
            "name": "ARTCOOL MIRROR / BLACK",
            "category": "RESIDENZIALE",
            "type": "PARETE",
            "pages": [583],
            "description": "Design a specchio nero riflettente con tecnologia Plasmaster Ionizer Plus e Wi-Fi ThinQ.",
            "models_prefix": ["AC09BK", "AC12BK", "AC18BK", "AC24BK"],
            "keywords": ["ARTCOOL MIRROR", "ARTCOOL BLACK", "AC09BK", "AC12BK"]
        },
        {
            "id": "LG_LIBERO",
            "name": "LIBERO / LIBERO SMART",
            "category": "RESIDENZIALE",
            "type": "PARETE",
            "pages": [582],
            "description": "Serie residenziale Libero Smart con compressore Dual Inverter garantito 10 anni e Wi-Fi integrato.",
            "models_prefix": ["S09ET", "S12ET", "S18ET", "S24ET", "LIBERO"],
            "keywords": ["LIBERO", "LIBERO SMART", "S09ET", "S12ET", "S18ET"]
        },
        {
            "id": "LG_MULTI_SPLIT",
            "name": "MULTI SPLIT MU2R / MU3R / MU4R / MU5R",
            "category": "RESIDENZIALE",
            "type": "MULTI_SPLIT",
            "pages": [584, 586],
            "description": "Unità esterne multi-split R32 da 2 a 5 attacchi (MU2R15, MU2R17, MU3R19, MU3R21, MU4R25, MU4R27, MU5R30, MU5R40).",
            "models_prefix": ["MU2R", "MU3R", "MU4R", "MU5R"],
            "keywords": ["MU2R", "MU3R", "MU4R", "MU5R", "MULTI LG"]
        },
        {
            "id": "LG_COMMERCIALE_UNIVERSAL",
            "name": "COMMERCIALE UNIVERSAL (ROUND CASSETTE 360° / CASSETTE / CANALIZZATI / SOFFITTO)",
            "category": "COMMERCIALE",
            "type": "COMMERCIALE",
            "pages": [585, 586, 587, 588, 589, 590, 591, 592],
            "description": "Gamma commerciale Universal Inverter con Round Cassette 360°, cassette 57x57 e 84x84 (UT/CT), canalizzati UM/CM, soffitto UV e unità esterne UU/UUA/UUB/UUD.",
            "models_prefix": ["UUA", "UUB", "UUD", "UU", "UT", "CT", "UM", "CM", "UV"],
            "keywords": ["UUA", "UUB", "UUD", "UU200", "UU250", "UT30", "UT36", "UT42", "UM12", "UM18", "UM24", "UM42", "COMMERCIALE LG"]
        }
    ],

    # -------------------------------------------------------------
    # FERROLI (Pagine 594 - 595)
    # -------------------------------------------------------------
    "FERROLI": [
        {
            "id": "FERROLI_GIADA",
            "name": "GIADA S",
            "category": "RESIDENZIALE",
            "type": "PARETE",
            "pages": [594],
            "description": "Climatizzatore monosplit e multisplit a parete con gas R32 e Wi-Fi integrato.",
            "models_prefix": ["GIADA S", "GIADA"],
            "keywords": ["GIADA S", "GIADA", "UE GIADA", "UI GIADA"]
        },
        {
            "id": "FERROLI_AMBRA",
            "name": "AMBRA S",
            "category": "RESIDENZIALE",
            "type": "PARETE",
            "pages": [594],
            "description": "Serie residenziale monosplit Ambra S ad alta efficienza A++.",
            "models_prefix": ["AMBRA S", "AMBRA"],
            "keywords": ["AMBRA S", "AMBRA"]
        },
        {
            "id": "FERROLI_MULTI_GIADA",
            "name": "MULTI SPLIT GIADA",
            "category": "RESIDENZIALE",
            "type": "MULTI_SPLIT",
            "pages": [594],
            "description": "Unità esterne multi-split Giada da 2 a 5 attacchi.",
            "models_prefix": ["GIADA M", "MULTI GIADA"],
            "keywords": ["MULTI GIADA", "GIADA M"]
        },
        {
            "id": "FERROLI_GIADA_C",
            "name": "GIADA-C COMMERCIALE (CASSETTA / CANALIZZATO / SOFFITTO)",
            "category": "COMMERCIALE",
            "type": "COMMERCIALE",
            "pages": [595],
            "description": "Linea commerciale Giada-C con cassette 4 vie 60x60 e 84x84, canalizzati e pensili soffitto.",
            "models_prefix": ["GIADA-C"],
            "keywords": ["GIADA-C", "GIADA C"]
        }
    ],

    # -------------------------------------------------------------
    # BAXI (Pagine 596 - 599)
    # -------------------------------------------------------------
    "BAXI": [
        {
            "id": "BAXI_ASTRA",
            "name": "ASTRA",
            "category": "RESIDENZIALE",
            "type": "PARETE",
            "pages": [596],
            "description": "Serie residenziale monosplit Astra con modulo Wi-Fi opzionale Air Connect.",
            "models_prefix": ["LSGT25-S", "LSGT35-S", "LSGT50-S", "LSGT70-S", "ASTRA"],
            "keywords": ["ASTRA", "LSGT25-S", "LSGT35-S", "LSGT50-S", "LSGT70-S"]
        },
        {
            "id": "BAXI_SIDERA",
            "name": "SIDERA",
            "category": "RESIDENZIALE",
            "type": "PARETE",
            "pages": [596],
            "description": "Serie residenziale di fascia superiore Sidera ad altissima silenziosità ed efficienza.",
            "models_prefix": ["SIDERA", "JSG"],
            "keywords": ["SIDERA"]
        },
        {
            "id": "BAXI_MULTI_LSGT",
            "name": "MULTI SPLIT DUAL / TRIAL / QUADRI LSGT",
            "category": "RESIDENZIALE",
            "type": "MULTI_SPLIT",
            "pages": [597, 598],
            "description": "Unità esterne multi-split Baxi da 2 a 4 attacchi (LSGT40-2M, LSGT50-2M, LSGT60-3M, LSGT80-4M).",
            "models_prefix": ["LSGT40", "LSGT50", "LSGT60", "LSGT80", "LSGT100"],
            "keywords": ["LSGT40", "LSGT50", "LSGT60", "LSGT80", "LSGT100", "MULTI BAXI"]
        },
        {
            "id": "BAXI_LIGHT_COMMERCIAL",
            "name": "LIGHT COMMERCIAL RZ2GT (CASSETTA / CANALIZZATO / SOFFITTO)",
            "category": "COMMERCIALE",
            "type": "COMMERCIALE",
            "pages": [597, 599],
            "description": "Gamma commerciale con unità esterne RZ2GT e unità interne cassette 4 vie, canalizzati e pavimento-soffitto.",
            "models_prefix": ["RZ2GT", "RZGBK", "LSGBK"],
            "keywords": ["RZ2GT", "RZGBK", "LSGBK", "LIGHTCOMM"]
        }
    ],

    # -------------------------------------------------------------
    # ARISTON (Pagine 600 - 603)
    # -------------------------------------------------------------
    "ARISTON": [
        {
            "id": "ARISTON_ALYS",
            "name": "ALYS R32",
            "category": "RESIDENZIALE",
            "type": "PARETE",
            "pages": [600],
            "description": "Climatizzatore monosplit Alys con connettività Wi-Fi Ariston Clima e classe A++.",
            "models_prefix": ["ALYS 25", "ALYS 35", "ALYS 50"],
            "keywords": ["ALYS", "ALYS 25", "ALYS 35", "ALYS 50"]
        },
        {
            "id": "ARISTON_KYDOS",
            "name": "KYDOS R32",
            "category": "RESIDENZIALE",
            "type": "PARETE",
            "pages": [600],
            "description": "Serie monosplit Kydos ad alta efficienza A+++/A++.",
            "models_prefix": ["KYDOS"],
            "keywords": ["KYDOS"]
        },
        {
            "id": "ARISTON_PRIOS",
            "name": "PRIOS R32",
            "category": "RESIDENZIALE",
            "type": "PARETE",
            "pages": [600],
            "description": "Serie residenziale compatta Prios con filtro odori e funzione Memory.",
            "models_prefix": ["PRIOS"],
            "keywords": ["PRIOS"]
        },
        {
            "id": "ARISTON_MULTI",
            "name": "MULTI SPLIT DUAL / TRIAL / QUADRI / PENTA R32",
            "category": "RESIDENZIALE",
            "type": "MULTI_SPLIT",
            "pages": [601, 602],
            "description": "Unità esterne multi-split Ariston da 2 a 5 attacchi (DUAL, TRIAL, QUAD, PENTA).",
            "models_prefix": ["DUAL 40", "DUAL 50", "TRIAL 70", "QUAD 80", "PENTA 110"],
            "keywords": ["DUAL 40", "DUAL 50", "TRIAL 70", "QUAD 80", "PENTA 110", "MULTI ARISTON"]
        },
        {
            "id": "ARISTON_COMMERCIALE_MUC",
            "name": "COMMERCIALE MUC (CASSETTA / CANALIZZATO / SOFFITTO / CONSOLE)",
            "category": "COMMERCIALE",
            "type": "COMMERCIALE",
            "pages": [602, 603],
            "description": "Gamma commerciale con unità esterne MUC e unità interne cassette KAS, canalizzati KCA, console CON e soffitto CEF.",
            "models_prefix": ["MUC", "KAS", "KCA", "CON", "CEF"],
            "keywords": ["MUC R32", "KAS R32", "KCA R32", "CON R32", "CEF R32"]
        }
    ],

    # -------------------------------------------------------------
    # BERETTA (Pagina 604)
    # -------------------------------------------------------------
    "BERETTA": [
        {
            "id": "BERETTA_BREVA",
            "name": "BREVA / BREVA E",
            "category": "RESIDENZIALE",
            "type": "PARETE",
            "pages": [604],
            "description": "Climatizzatore monosplit e multisplit Breva ad alta efficienza A++.",
            "models_prefix": ["BREVA EX", "BREVA"],
            "keywords": ["BREVA EX", "BREVA", "BREVA E"]
        },
        {
            "id": "BERETTA_MULTI_BREVA",
            "name": "MULTI SPLIT BREVA R32",
            "category": "RESIDENZIALE",
            "type": "MULTI_SPLIT",
            "pages": [604],
            "description": "Unità esterne multi-split Breva da 2 e 3 attacchi.",
            "models_prefix": ["BREVA MULTI"],
            "keywords": ["BREVA MULTI", "MULTI BREVA"]
        }
    ],

    # -------------------------------------------------------------
    # RIELLO (Pagine 605 - 608)
    # -------------------------------------------------------------
    "RIELLO": [
        {
            "id": "RIELLO_AARIA_START",
            "name": "AARIA START N / AMW ST N",
            "category": "RESIDENZIALE",
            "type": "PARETE",
            "pages": [605],
            "description": "Serie residenziale monosplit compatta ed essenziale A++/A+.",
            "models_prefix": ["AARIA START", "AMW 25 ST", "AMW 35 ST", "AMW 50 ST"],
            "keywords": ["AARIA START", "AMW 25 ST", "AMW 35 ST", "AMW 50 ST"]
        },
        {
            "id": "RIELLO_AARIA_MONO_PLUS",
            "name": "AARIA MONO PLUS (AMW PLUS)",
            "category": "RESIDENZIALE",
            "type": "PARETE",
            "pages": [605],
            "description": "Climatizzatore monosplit ad elevate prestazioni stagionali A+++/A++.",
            "models_prefix": ["AARIA MONO", "AMW PLUS", "25 PLUS I", "35 PLUS I", "50 PLUS I"],
            "keywords": ["AARIA MONO", "AMW PLUS", "25 PLUS I", "35 PLUS I", "50 PLUS I"]
        },
        {
            "id": "RIELLO_ELIXA",
            "name": "RIELLO ELIXA MONO-REW",
            "category": "RESIDENZIALE",
            "type": "PARETE",
            "pages": [605],
            "description": "Serie monosplit Elixa a parete per climatizzazione residenziale.",
            "models_prefix": ["ELIXA", "REW"],
            "keywords": ["ELIXA", "REW"]
        },
        {
            "id": "RIELLO_AARIA_MULTI",
            "name": "AARIA MULTI",
            "category": "RESIDENZIALE",
            "type": "MULTI_SPLIT",
            "pages": [608],
            "description": "Unità esterne multi-split Riello da 2 a 5 attacchi (250 PI, 355 PI, 370 PI, 480 PI, 5100 PI).",
            "models_prefix": ["AARIA MULTI", "AMW PI", "PI R32"],
            "keywords": ["AARIA MULTI", "250 PI", "355 PI", "370 PI", "480 PI", "5100 PI"]
        },
        {
            "id": "RIELLO_COMMERCIALE_AARIA",
            "name": "COMMERCIALE AARIA MONO PLUS / PRO P (CANALIZZATO / CASSETTA / SOFFITTO / PAVIMENTO)",
            "category": "COMMERCIALE",
            "type": "COMMERCIALE",
            "pages": [606, 607],
            "description": "Gamma commerciale con cassette 4 vie AMK, canalizzati AMD, pavimento AMC e pensili soffitto AMS.",
            "models_prefix": ["I-AMD", "I-AMK", "I-AMC", "P-AMS", "AMK", "AMD", "AMC", "AMS"],
            "keywords": ["AMK", "AMD", "AMC", "AMS", "AARIA AMK", "AARIA AMD", "AARIA AMC", "AARIA AMS"]
        }
    ],

    # -------------------------------------------------------------
    # BOSCH (Pagine 609 - 612)
    # -------------------------------------------------------------
    "BOSCH": [
        {
            "id": "BOSCH_CLIMATE_3000I",
            "name": "CLIMATE 3000i",
            "category": "RESIDENZIALE",
            "type": "PARETE",
            "pages": [609],
            "description": "Climatizzatore monosplit residenziale facile da usare, compatto e silenzioso A++/A+.",
            "models_prefix": ["CLIMATE 3000i", "CL3000i"],
            "keywords": ["CLIMATE 3000i", "CL3000i", "3000i 26", "3000i 35", "3000i 53"]
        },
        {
            "id": "BOSCH_CLIMATE_5000I",
            "name": "CLIMATE 5000i",
            "category": "RESIDENZIALE",
            "type": "PARETE",
            "pages": [609],
            "description": "Serie residenziale con ionizzatore d'aria, tecnologia di bio-filtraggio e connettività HomeCom Easy.",
            "models_prefix": ["CLIMATE 5000i", "CL5000i"],
            "keywords": ["CLIMATE 5000i", "CL5000i"]
        },
        {
            "id": "BOSCH_CLIMATE_6000I",
            "name": "CLIMATE 6000i",
            "category": "RESIDENZIALE",
            "type": "PARETE",
            "pages": [609],
            "description": "Top di gamma Bosch con sensore di presenza intelligente e classe A+++.",
            "models_prefix": ["CLIMATE 6000i", "CL6000i"],
            "keywords": ["CLIMATE 6000i", "CL6000i"]
        },
        {
            "id": "BOSCH_MULTI_5000M",
            "name": "MULTI SPLIT CLIMATE 5000M",
            "category": "RESIDENZIALE",
            "type": "MULTI_SPLIT",
            "pages": [611, 612],
            "description": "Unità esterne multi-split da 2 a 5 attacchi (41/2 E, 53/2 E, 62/3 E, 79/3 E, 82/4 E, 105/4 E, 125/5 E).",
            "models_prefix": ["CLIMATE 5000M", "CL5000M"],
            "keywords": ["CLIMATE 5000M", "CL5000M", "5000M 41", "5000M 53", "5000M 62", "5000M 79"]
        },
        {
            "id": "BOSCH_COMMERCIALE_5000",
            "name": "COMMERCIALE CLIMATE 5000 (CASSETTA / CANALIZZATO / SOFFITTO)",
            "category": "COMMERCIALE",
            "type": "COMMERCIALE",
            "pages": [610],
            "description": "Gamma commerciale con cassette 4 vie 4C/4CC, canalizzati compatti e pavimento-soffitto.",
            "models_prefix": ["CL5000i-P 4C", "CL5000i-P 4CC", "CL5000i-U", "CL5000i-D"],
            "keywords": ["CL5000i-P", "CL5000i-U", "CL5000i-D", "CASSETTA CL5000i"]
        }
    ],

    # -------------------------------------------------------------
    # IMMERGAS (Pagine 613 - 614)
    # -------------------------------------------------------------
    "IMMERGAS": [
        {
            "id": "IMMER_CLIMA",
            "name": "IMMERCLIMA (MONO & MULTI)",
            "category": "RESIDENZIALE",
            "type": "PARETE",
            "pages": [613, 614],
            "description": "Climatizzatori a parete Immergas monosplit e multisplit con gas R32.",
            "models_prefix": ["IMMERCLIMA", "UI CAS", "UI DUCT", "UI SP"],
            "keywords": ["IMMERCLIMA", "UI CAS", "UI DUCT", "UI SP"]
        }
    ],

    # -------------------------------------------------------------
    # HSD / HERMANN SAUNIER DUVAL (Pagine 615 - 616)
    # -------------------------------------------------------------
    "HSD": [
        {
            "id": "HSD_VIVAIR_LITE",
            "name": "VIVAIR LITE",
            "category": "RESIDENZIALE",
            "type": "PARETE",
            "pages": [615],
            "description": "Climatizzatore monosplit Hermann Saunier Duval compatto, pratico ed economico.",
            "models_prefix": ["VIVAIR LITE", "B1-025S", "B1-035S", "B1-050S"],
            "keywords": ["VIVAIR LITE", "B1-025S", "B1-035S", "B1-050S"]
        },
        {
            "id": "HSD_VIVAIR_TOP",
            "name": "VIVAIR TOP",
            "category": "RESIDENZIALE",
            "type": "PARETE",
            "pages": [615],
            "description": "Serie residenziale di punta VivAir Top ad altissima efficienza e silenziosità.",
            "models_prefix": ["VIVAIR TOP", "SDH19"],
            "keywords": ["VIVAIR TOP", "SDH19"]
        },
        {
            "id": "HSD_MULTI_VIVAIR",
            "name": "MULTI SPLIT VIVAIR",
            "category": "RESIDENZIALE",
            "type": "MULTI_SPLIT",
            "pages": [616],
            "description": "Unità esterne multi-split VivAir da 2 a 4 attacchi con unità interne a parete e cassette.",
            "models_prefix": ["VIVAIR MULTI", "1-040 MNA2O", "1-050 MNA2O", "1-070 MNA3O", "1-080 MNA4O"],
            "keywords": ["VIVAIR MULTI", "1-040 MNA", "1-050 MNA", "1-070 MNA", "1-080 MNA"]
        }
    ],

    # -------------------------------------------------------------
    # VAILLANT (Pagine 617 - 619)
    # -------------------------------------------------------------
    "VAILLANT": [
        {
            "id": "VAIL_INTRO",
            "name": "CLIMAVAIR INTRO",
            "category": "RESIDENZIALE",
            "type": "PARETE",
            "pages": [617],
            "description": "Linea monosplit residenziale entry-level climaVAIR Intro affidabile ed essenziale A++/A+.",
            "models_prefix": ["VAIL 1-025", "VAIL 1-030", "VAIL 1-035", "CLIMAVAIR INTRO"],
            "keywords": ["CLIMAVAIR INTRO", "VAIL 1-025", "VAIL 1-030", "VAIL 1-035"]
        },
        {
            "id": "VAIL_PLUS",
            "name": "CLIMAVAIR PRO / PLUS",
            "category": "RESIDENZIALE",
            "type": "PARETE",
            "pages": [617],
            "description": "Climatizzatore monosplit climaVAIR Plus con display integrato e connettività smart.",
            "models_prefix": ["VAIB 1-025", "VAIB 1-035", "VAIB 1-050", "VAIB 1-065"],
            "keywords": ["VAIB 1-025", "VAIB 1-035", "VAIB 1-050", "VAIB 1-065"]
        },
        {
            "id": "VAIL_EXCLUSIVE",
            "name": "CLIMAVAIR EXCLUSIVE",
            "category": "RESIDENZIALE",
            "type": "PARETE",
            "pages": [617],
            "description": "Top di gamma Vaillant climaVAIR Exclusive con sensore di temperatura integrato nel telecomando e A+++.",
            "models_prefix": ["VAI 5-025", "VAI 5-035", "5-025WNO", "5-065WNO"],
            "keywords": ["CLIMAVAIR EXCLUSIVE", "5-025WNO", "5-035WNO", "5-065WNO", "VAI 5"]
        },
        {
            "id": "VAIL_MULTI",
            "name": "MULTI SPLIT CLIMAVAIR MULTI (VAM1)",
            "category": "RESIDENZIALE",
            "type": "MULTI_SPLIT",
            "pages": [618, 619],
            "description": "Unità esterne multi-split climaVAIR da 2 a 4 attacchi (VAM1-040, VAM1-050, VAM1-070, VAM1-080).",
            "models_prefix": ["VAM1-040", "VAM1-050", "VAM1-070", "VAM1-080"],
            "keywords": ["VAM1-040", "VAM1-050", "VAM1-070", "VAM1-080", "CLIMAVAIR MULTI"]
        }
    ],

    # -------------------------------------------------------------
    # AERMEC (Pagine 620 - 623, 625)
    # -------------------------------------------------------------
    "AERMEC": [
        {
            "id": "AERMEC_SLG_SPG",
            "name": "SLG / SPG A PARETE",
            "category": "RESIDENZIALE",
            "type": "PARETE",
            "pages": [620],
            "description": "Climatizzatore residenziale a parete monosplit e multisplit R32 con Wi-Fi di serie.",
            "models_prefix": ["SLG", "SPG"],
            "keywords": ["SLG", "SPG", "UE SLG", "UI SLG"]
        },
        {
            "id": "AERMEC_CKG",
            "name": "CKG CONSOLE A PAVIMENTO",
            "category": "RESIDENZIALE",
            "type": "CONSOLE_PAVIMENTO",
            "pages": [620],
            "description": "Console a pavimento compatta con doppia mandata d'aria e display frontale.",
            "models_prefix": ["CKG261", "CKG361", "CKG501"],
            "keywords": ["CKG261", "CKG361", "CKG501", "CONSOLE CKG"]
        },
        {
            "id": "AERMEC_MULTI_MPG",
            "name": "MULTI SPLIT MPG",
            "category": "RESIDENZIALE",
            "type": "MULTI_SPLIT",
            "pages": [621],
            "description": "Unità esterne multi-split MPG da 2 a 5 attacchi (MPG 410, MPG 520, MPG 720, MPG 830, MPG 1040, MPG 1250).",
            "models_prefix": ["MPG 410", "MPG 520", "MPG 720", "MPG 830", "MPG 1040", "MPG 1250"],
            "keywords": ["MPG 410", "MPG 520", "MPG 720", "MPG 830", "MPG 1040", "MPG 1250", "MULTI MPG"]
        },
        {
            "id": "AERMEC_COMMERCIALE_LPG",
            "name": "COMMERCIALE LPG (CANALIZZATO MEDIA/ALTA PREVALENZA)",
            "category": "COMMERCIALE",
            "type": "CANALIZZATO",
            "pages": [622],
            "description": "Gamma commerciale canalizzata ad alta efficienza da 3,5 a 16 kW.",
            "models_prefix": ["LPG 1000", "LPG 1200", "LPG 1400", "LPG1000D", "LPG1200D"],
            "keywords": ["LPG 1000", "LPG 1200", "LPG 1400", "LPG1000D", "LPG1200D"]
        },
        {
            "id": "AERMEC_COMMERCIALE_SCG",
            "name": "COMMERCIALE SCG (CASSETTA 4 VIE / SOFFITTO)",
            "category": "COMMERCIALE",
            "type": "CASSETTA_90X90",
            "pages": [623],
            "description": "Unità commerciali a cassetta 4 vie e pavimento-soffitto SCG.",
            "models_prefix": ["SCG 701", "SCG1001", "SCG1201"],
            "keywords": ["SCG 701", "SCG1001", "SCG1201", "SCG1201T"]
        },
        {
            "id": "AERMEC_POLO",
            "name": "POLO SENZA UNITA ESTERNA",
            "category": "SENZA_UNITA_ESTERNA",
            "type": "SENZA_UNITA_ESTERNA",
            "pages": [625],
            "description": "Condizionatore monoblocco a parete senza unità motocondensante esterna.",
            "models_prefix": ["POLO 10K", "POLO"],
            "keywords": ["POLO 10K", "POLO"]
        }
    ],

    # -------------------------------------------------------------
    # SENZA UNITÀ ESTERNA (Pagine 624 - 626)
    # -------------------------------------------------------------
    "SENZA_UNITA_ESTERNA": [
        {
            "id": "SUE_INNOVA",
            "name": "INNOVA 2.0 (MINI / 12 HP / ELEC / CEILING)",
            "category": "SENZA_UNITA_ESTERNA",
            "type": "SENZA_UNITA_ESTERNA",
            "pages": [624],
            "description": "La gamma di climatizzatori monoblocco senza unità esterna più sottile e silenziosa al mondo.",
            "models_prefix": ["2.0 MINI", "2.0 ELEC", "2.0 CEILING", "12 HP", "10 HP"],
            "keywords": ["INNOVA", "2.0 MINI", "2.0 ELEC", "2.0 CEILING", "ORIZ 2.0", "VERT 2.0"]
        },
        {
            "id": "SUE_ARGO_APOLLO",
            "name": "ARGO APOLLO 12 HP",
            "category": "SENZA_UNITA_ESTERNA",
            "type": "SENZA_UNITA_ESTERNA",
            "pages": [625],
            "description": "Climatizzatore a parete monoblocco con pompa di calore e Wi-Fi integrato senza motore esterno.",
            "models_prefix": ["APOLLO 12HP", "APOLLO"],
            "keywords": ["APOLLO 12HP", "APOLLO", "ARGO APOLLO"]
        },
        {
            "id": "SUE_PANASONIC_SOLO",
            "name": "PANASONIC RAC SOLO",
            "category": "SENZA_UNITA_ESTERNA",
            "type": "SENZA_UNITA_ESTERNA",
            "pages": [625],
            "description": "Climatizzatore monoblocco a finestra / parete senza unità esterna.",
            "models_prefix": ["RAC SOLO", "SOLO"],
            "keywords": ["RAC SOLO", "PANASONIC SOLO"]
        },
        {
            "id": "SUE_IDEAL_CLIMA",
            "name": "IDEAL CLIMA / AERMEC FK",
            "category": "SENZA_UNITA_ESTERNA",
            "type": "SENZA_UNITA_ESTERNA",
            "pages": [625],
            "description": "Monoblocco senza unità esterna FK260 e FK360 ad espansione diretta con refrigerante ecologico R32.",
            "models_prefix": ["FK260", "FK360", "FK261", "FK361"],
            "keywords": ["FK260", "FK360", "FK261", "FK361", "IDEAL CLIMA"]
        },
        {
            "id": "SUE_OLIMPIA_UNICO",
            "name": "OLIMPIA SPLENDID UNICO (AIR / EASY / EDGE / EVO / PRO / TOWER / TWIN)",
            "category": "SENZA_UNITA_ESTERNA",
            "type": "SENZA_UNITA_ESTERNA",
            "pages": [626],
            "description": "Tutta la celebre gamma UNICO di Olimpia Splendid: Unico Air, Unico Easy, Unico Edge, Unico Evo, Unico Pro, Unico Tower e Unico Twin.",
            "models_prefix": ["UNICO AIR", "UNICO EASY", "UNICO EVO", "UNICO EDGE", "UNICO PRO", "UNICO TWIN", "UNICO TOWER"],
            "keywords": ["UNICO AIR", "UNICO EASY", "UNICO EVO", "UNICO EDGE", "UNICO PRO", "UNICO TWIN", "UNICO TOWER", "OLIMPIA UNICO"]
        }
    ],

    # -------------------------------------------------------------
    # ALTRI MARCHI PRESENTI A LISTINO / ERP
    # -------------------------------------------------------------
    "HITACHI": [
        {
            "id": "HIT_AIRHOME",
            "name": "AIRHOME 400 / 600",
            "category": "RESIDENZIALE",
            "type": "PARETE",
            "pages": [],
            "description": "Serie residenziale AirHome con tecnologia FrostWash, purificazione AQtiv-Ion e Wi-Fi airCloud Go.",
            "models_prefix": ["RAK-DJ", "RAD-DJ", "RAC-DJ"],
            "keywords": ["AIRHOME", "RAD-DJ", "RAK-DJ"]
        },
        {
            "id": "HIT_PERFORMANCE",
            "name": "PERFORMANCE RAK-RPE",
            "category": "RESIDENZIALE",
            "type": "PARETE",
            "pages": [],
            "description": "Serie ad alta efficienza A+++ con purificazione aria e filtrazione avanzata.",
            "models_prefix": ["RAK-RPE", "RAK-RPD", "RAC-RPE"],
            "keywords": ["PERFORM", "RAK-RPE", "RAK-RPD"]
        },
        {
            "id": "HIT_LIGHT_COMMERCIAL",
            "name": "LIGHT COMMERCIAL (RAK / RAI / RAD)",
            "category": "COMMERCIALE",
            "type": "COMMERCIALE",
            "pages": [],
            "description": "Gamma Light Commercial con cassette RAI, canalizzati RAD e parete RAK.",
            "models_prefix": ["RAI-VJ", "RAI-60PPD", "RAK-60PPD", "RAK-70PPD", "RAC-25NPE", "RAC-35NPE", "RAC-50NPE"],
            "keywords": ["LIGHTCOMM", "RAI-VJ", "RAI-60PPD", "RAK-60PPD", "RAK-70PPD", "RAC-25NPE", "RAC-35NPE", "RAC-50NPE"]
        },
        {
            "id": "HIT_UTOPIA_PRIME",
            "name": "UTOPIA PRIME / IVX PRIME",
            "category": "COMMERCIALE",
            "type": "COMMERCIALE",
            "pages": [],
            "description": "Sistemi commerciali ad espansione diretta Utopia Prime e IVX Prime R32.",
            "models_prefix": ["RPIH", "RPI-", "RAS-4H", "RAS-5H", "RAS-6H"],
            "keywords": ["UTOPIA PRIME", "IVX PRIME", "RPIH", "RPI-", "RAS-4H"]
        }
    ],

    "TCL": [
        {
            "id": "TCL_BREEZEIN",
            "name": "BREEZEIN P5",
            "category": "RESIDENZIALE",
            "type": "PARETE",
            "pages": [],
            "description": "Serie residenziale BreezeIN con flusso d'aria delicato e Wi-Fi di serie.",
            "models_prefix": ["ST09P", "ST12P", "ST18P", "ST24P"],
            "keywords": ["BREEZEIN", "ST09P", "ST12P"]
        },
        {
            "id": "TCL_ELITE",
            "name": "ELITE F2",
            "category": "RESIDENZIALE",
            "type": "PARETE",
            "pages": [],
            "description": "Climatizzatore monosplit Elite con gas R32.",
            "models_prefix": ["ST09F", "ST12F", "ST18F", "ST24F"],
            "keywords": ["ELITE F2", "ST09F", "ST12F"]
        },
        {
            "id": "TCL_MULTI",
            "name": "MULTI SPLIT TCL",
            "category": "RESIDENZIALE",
            "type": "MULTI_SPLIT",
            "pages": [],
            "description": "Unità esterne multi-split TCL da 2 a 4 attacchi.",
            "models_prefix": ["MT14", "MT18", "MT27", "MT32"],
            "keywords": ["MT14", "MT18", "MT27", "MT32"]
        }
    ],

    "HOSHIKO": [
        {
            "id": "HOSHIKO_MONO",
            "name": "HOSHIKO MONOSPLIT R32",
            "category": "RESIDENZIALE",
            "type": "PARETE",
            "pages": [],
            "description": "Climatizzatore monosplit ad alta efficienza energetica.",
            "models_prefix": ["HK", "HOSHIKO"],
            "keywords": ["HOSHIKO", "HK"]
        }
    ],

    "ACCORRONI": [
        {
            "id": "ACCORRONI_BOOSTER",
            "name": "BOOSTER HR",
            "category": "COMMERCIALE",
            "type": "COMMERCIALE",
            "pages": [82, 131],
            "description": "Unità commerciali e pompe di calore Booster HR.",
            "models_prefix": ["BOOSTER HR", "7601", "7603"],
            "keywords": ["BOOSTER HR", "76010500", "76030500"]
        }
    ],

    "KUKYR": [
        {
            "id": "KUKYR_SPLIT",
            "name": "KUKYR SPLIT R32",
            "category": "RESIDENZIALE",
            "type": "PARETE",
            "pages": [],
            "description": "Climatizzatori a parete Kukyr.",
            "models_prefix": ["KUKYR"],
            "keywords": ["KUKYR"]
        }
    ]
}

def main():
    print(f"Salvataggio Tassonomia Ufficiale Famiglie Catalogo 2026...")
    total_fams = sum(len(fams) for fams in TAXONOMY.values())
    print(f"Marchi censiti: {len(TAXONOMY)}")
    print(f"Famiglie totali strutturate: {total_fams}")

    out_path = "Knowledge/catalog_official_families_2026.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(TAXONOMY, f, indent=2, ensure_ascii=False)
    
    print(f"File salvato con successo in: {out_path}")

if __name__ == "__main__":
    main()
