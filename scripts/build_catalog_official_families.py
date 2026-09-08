import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

# Catalogo Ufficiale Puglia Termica 2026 - Tassonomia Completa di TUTTE le Famiglie / Serie di Climatizzazione
OFFICIAL_CATALOG_FAMILIES = {
    "DAIKIN": [
        {"id": "DAIKIN_PERFERA", "name": "PERFERA ALL SEASONS", "category": "RESIDENZIALE", "type": "PARETE", "pages": [468, 476, 478], "description": "Climatizzatore monosplit/multisplit a parete A+++ con tecnologia Flash Streamer.", "models_prefix": ["FTXM", "RXM"], "keywords": ["PERFERA", "FTXM", "RXM"]},
        {"id": "DAIKIN_SIESTA", "name": "SIESTA GSI", "category": "RESIDENZIALE", "type": "PARETE", "pages": [468], "description": "Serie monosplit Siesta ad alta efficienza energetica A++/A+.", "models_prefix": ["ATXF", "ARXF"], "keywords": ["SIESTA", "ATXF", "ARXF", "GSI"]},
        {"id": "DAIKIN_STYLISH", "name": "STYLISH", "category": "RESIDENZIALE", "type": "PARETE", "pages": [469], "description": "Design ultracompatto in 4 colori (Bianco, Argento, Blackwood, Nero Opaco).", "models_prefix": ["FTXA", "RXA"], "keywords": ["STYLISH", "FTXA", "RXA"]},
        {"id": "DAIKIN_EMURA", "name": "EMURA", "category": "RESIDENZIALE", "type": "PARETE", "pages": [469], "description": "Icona di design curvato a parete (Bianco, Total Silver, Nero opaco).", "models_prefix": ["FTXJ", "RXJ"], "keywords": ["EMURA", "FTXJ", "RXJ"]},
        {"id": "DAIKIN_URURU_SARARA", "name": "URURU SARARA", "category": "RESIDENZIALE", "type": "PARETE", "pages": [469], "description": "Sistema top di gamma con umidificazione, deumidificazione e ricambio aria.", "models_prefix": ["FTXZ", "RXZ"], "keywords": ["URURU SARARA", "FTXZ", "RXZ"]},
        {"id": "DAIKIN_SENSIRA", "name": "SENSIRA", "category": "RESIDENZIALE", "type": "PARETE", "pages": [470], "description": "Serie residenziale entry-level affidabile e silenziosa R32.", "models_prefix": ["FTXF", "RXF", "CTXF"], "keywords": ["SENSIRA", "FTXF", "RXF", "CTXF"]},
        {"id": "DAIKIN_COMFORA", "name": "COMFORA", "category": "RESIDENZIALE", "type": "PARETE", "pages": [470], "description": "Unità compatta con filtro deodorizzante e 3D Airflow.", "models_prefix": ["FTXP", "RXP"], "keywords": ["COMFORA", "FTXP", "RXP"]},
        {"id": "DAIKIN_MULTI_MXF", "name": "MULTI MXF (SIESTA)", "category": "RESIDENZIALE", "type": "MULTI_SPLIT", "pages": [470], "description": "Unità esterne multi split dedicate per linea Siesta (2MXF40, 2MXF50, 3MXF52, 3MXF68).", "models_prefix": ["2MXF", "3MXF", "MXF"], "keywords": ["MXF", "2MXF", "3MXF"]},
        {"id": "DAIKIN_MULTI_MXM", "name": "MULTI SPLIT BLUEVOLUTION MXM", "category": "RESIDENZIALE", "type": "MULTI_SPLIT", "pages": [471], "description": "Unità esterne multi split universali R32 compatibili con tutta la gamma residenziale (2-5 attacchi).", "models_prefix": ["2MXM", "3MXM", "4MXM", "5MXM", "MXM"], "keywords": ["MXM", "2MXM", "3MXM", "4MXM", "5MXM"]},
        {"id": "DAIKIN_MULTI_DHW", "name": "MULTI+ (MULTI DHW)", "category": "RESIDENZIALE", "type": "MULTI_SPLIT", "pages": [471, 475], "description": "Sistema ibrido multi split per climatizzazione e ACS con accumulo.", "models_prefix": ["4MWXM", "5MWXM"], "keywords": ["MULTI+", "DHW", "MWXM", "4MWXM", "5MWXM"]},
        {"id": "DAIKIN_CANALIZZATA_FDXM", "name": "CANALIZZATA ULTRAPIATTA FDXM", "category": "COMMERCIALE_LIGHT", "type": "CANALIZZATO", "pages": [472], "description": "Canalizzata ultrapiatta h 200 mm per controsoffitti ribassati.", "models_prefix": ["FDXM"], "keywords": ["FDXM"]},
        {"id": "DAIKIN_PENSILE_FHA", "name": "PENSILE A SOFFITTO FHA", "category": "COMMERCIALE", "type": "PENSILE_SOFFITTO", "pages": [472, 482], "description": "Unità pensile a soffitto per ambienti commerciali senza controsoffitto.", "models_prefix": ["FHA"], "keywords": ["FHA"]},
        {"id": "DAIKIN_CASSETTA_ROUND_FLOW", "name": "CASSETTA ROUND FLOW FCAG 90x90", "category": "COMMERCIALE", "type": "CASSETTA_90X90", "pages": [473, 477, 479, 481, 484, 487], "description": "Cassetta 360° Round Flow per mandata aria omnidirezionale uniforme.", "models_prefix": ["FCAG"], "keywords": ["FCAG", "ROUND FLOW"]},
        {"id": "DAIKIN_SUPERCASSETTE_FCAHG", "name": "ROUND FLOW SUPERCASSETTE FCAHG", "category": "COMMERCIALE", "type": "CASSETTA_90X90", "pages": [488], "description": "Supercassetta ad altissima efficienza stagionale per il terziario.", "models_prefix": ["FCAHG"], "keywords": ["FCAHG", "SUPERCASSETTE"]},
        {"id": "DAIKIN_CASSETTA_FFA", "name": "CASSETTA 4 VIE FFA 60x60", "category": "COMMERCIALE_LIGHT", "type": "CASSETTA_60X60", "pages": [477, 479], "description": "Cassetta 60x60 standard integrabile a soffitto.", "models_prefix": ["FFA"], "keywords": ["FFA"]},
        {"id": "DAIKIN_PAVIMENTO_FNA", "name": "PAVIMENTO DA INCASSO FNA", "category": "RESIDENZIALE_COMMERCIALE", "type": "CONSOLE_PAVIMENTO", "pages": [476], "description": "Unità da incasso a scomparsa a pavimento.", "models_prefix": ["FNA", "FVXM"], "keywords": ["FNA", "FVXM"]},
        {"id": "DAIKIN_CANALIZZATA_FBA", "name": "CANALIZZATA DC FBA (MEDIA PREVALENZA)", "category": "COMMERCIALE", "type": "CANALIZZATO", "pages": [476, 478, 480, 483, 487], "description": "Canalizzata DC Inverter a media prevalenza.", "models_prefix": ["FBA"], "keywords": ["FBA"]},
        {"id": "DAIKIN_CANALIZZATA_FDA", "name": "CANALIZZATA ALTA PREVALENZA FDA", "category": "COMMERCIALE", "type": "CANALIZZATO", "pages": [483, 486], "description": "Canalizzata ad alta prevalenza per grandi impianti commerciali.", "models_prefix": ["FDA"], "keywords": ["FDA"]},
        {"id": "DAIKIN_PARETE_FAA", "name": "PARETE COMMERCIALE FAA", "category": "COMMERCIALE", "type": "PARETE", "pages": [480, 482], "description": "Split commerciale a parete per motori Sky Air.", "models_prefix": ["FAA"], "keywords": ["FAA"]},
        {"id": "DAIKIN_CASSETTA_PENSILE_FUA", "name": "CASSETTA PENSILE A SOFFITTO FUA", "category": "COMMERCIALE", "type": "CASSETTA_90X90", "pages": [484, 488], "description": "Cassetta pensile 4 vie senza controsoffitto.", "models_prefix": ["FUA"], "keywords": ["FUA"]},
        {"id": "DAIKIN_COLONNA_FVA", "name": "COLONNA COMMERCIALE FVA", "category": "COMMERCIALE", "type": "COLONNA", "pages": [485], "description": "Unità commerciale a colonna per ampie volumetrie.", "models_prefix": ["FVA"], "keywords": ["FVA"]},
        {"id": "DAIKIN_SKY_AIR_ALPHA", "name": "SKY AIR ALPHA (RZAG / RZA)", "category": "COMMERCIALE_UE", "type": "COMMERCIALE_UE", "pages": [478, 486], "description": "Unità esterne commerciali top di gamma A++.", "models_prefix": ["RZAG", "RZA"], "keywords": ["RZAG", "RZA", "ALPHA"]},
        {"id": "DAIKIN_SKY_AIR_ADVANCE", "name": "SKY AIR ADVANCE (RZASG)", "category": "COMMERCIALE_UE", "type": "COMMERCIALE_UE", "pages": [482, 483, 485, 486], "description": "Unità esterne commerciali ad alte prestazioni.", "models_prefix": ["RZASG"], "keywords": ["RZASG", "ADVANCE"]},
        {"id": "DAIKIN_SKY_AIR_ACTIVE", "name": "SKY AIR ACTIVE (AZAS)", "category": "COMMERCIALE_UE", "type": "COMMERCIALE_UE", "pages": [480, 481], "description": "Unità esterne commerciali standard entry.", "models_prefix": ["AZAS"], "keywords": ["AZAS", "ACTIVE"]}
    ],

    "MITSUBISHI": [
        {"id": "MITSU_MSZ_HR", "name": "MSZ-HR SMART INVERTER", "category": "RESIDENZIALE", "type": "PARETE", "pages": [490], "description": "Climatizzatore monosplit e multisplit essenziale, silenzioso ed economico.", "models_prefix": ["MSZ-HR", "MUZ-HR", "HR25", "HR35", "HR42", "HR50"], "keywords": ["MSZ-HR", "MUZ-HR"]},
        {"id": "MITSU_MSZ_AP", "name": "MSZ-AP / MSZ-AP LARGE", "category": "RESIDENZIALE", "type": "PARETE", "pages": [490, 496], "description": "Serie compatta universale ad alta efficienza A+++, inclusa versione Large (60-71).", "models_prefix": ["MSZ-AP", "MUZ-AP"], "keywords": ["MSZ-AP", "MUZ-AP", "AP LARGE"]},
        {"id": "MITSU_MSZ_AY", "name": "MSZ-AY GENERATION", "category": "RESIDENZIALE", "type": "PARETE", "pages": [496], "description": "Finitura opaca vellutata, filtro V-Blocking e Dual Barrier Coating.", "models_prefix": ["MSZ-AY", "MUZ-AY"], "keywords": ["MSZ-AY", "MUZ-AY"]},
        {"id": "MITSU_MSZ_LN", "name": "MSZ-LN KIRIGAMINE STYLE", "category": "RESIDENZIALE", "type": "PARETE", "pages": [491, 496], "description": "Top di gamma con 3D i-See Sensor, Plasma Quad Plus e 4 finiture specchiate.", "models_prefix": ["MSZ-LN", "MUZ-LN"], "keywords": ["MSZ-LN", "MUZ-LN", "KIRIGAMINE STYLE"]},
        {"id": "MITSU_MSZ_EF", "name": "MSZ-EF KIRIGAMINE ZEN", "category": "RESIDENZIALE", "type": "PARETE", "pages": [496], "description": "Design squadrato nei colori Bianco, Nero e Argento.", "models_prefix": ["MSZ-EF", "MUZ-EF"], "keywords": ["MSZ-EF", "MUZ-EF", "KIRIGAMINE ZEN"]},
        {"id": "MITSU_MSZ_BT", "name": "MSZ-BT ENTRY WI-FI", "category": "RESIDENZIALE", "type": "PARETE", "pages": [496], "description": "Residenziale con Wi-Fi MELCloud integrato di serie.", "models_prefix": ["MSZ-BT", "MUZ-BT"], "keywords": ["MSZ-BT", "MUZ-BT"]},
        {"id": "MITSU_SEZ_M", "name": "SEZ-M DA2 CANALIZZATA (BASSA PREVALENZA)", "category": "COMMERCIALE_LIGHT", "type": "CANALIZZATO", "pages": [491, 497, 503], "description": "Canalizzata compatta ribassata (200 mm) per residenziale e hotel.", "models_prefix": ["SEZ-M"], "keywords": ["SEZ-M"]},
        {"id": "MITSU_SLZ_M", "name": "SLZ-M FA2 CASSETTA 60x60", "category": "COMMERCIALE_LIGHT", "type": "CASSETTA_60X60", "pages": [492, 503, 507], "description": "Cassetta 4 vie euro 60x60 con 3D i-See Sensor opzionale.", "models_prefix": ["SLZ-M"], "keywords": ["SLZ-M"]},
        {"id": "MITSU_MFZ_KT", "name": "MFZ-KT VGK PAVIMENTO", "category": "RESIDENZIALE", "type": "CONSOLE_PAVIMENTO", "pages": [492], "description": "Console a pavimento con doppia mandata per riscaldamento ottimale.", "models_prefix": ["MFZ-KT", "SFZ-M"], "keywords": ["MFZ-KT", "SFZ-M"]},
        {"id": "MITSU_MLZ_KP", "name": "MLZ-KP / MLZ-KY CASSETTA 1 VIA", "category": "RESIDENZIALE_COMMERCIALE", "type": "CASSETTA_1VIA", "pages": [497], "description": "Cassetta 1 via per corridoi e ambienti rettangolari.", "models_prefix": ["MLZ-KP", "MLZ-KY"], "keywords": ["MLZ-KP", "MLZ-KY"]},
        {"id": "MITSU_MXZ_HA", "name": "MXZ-HA MULTI SMART", "category": "RESIDENZIALE", "type": "MULTI_SPLIT", "pages": [493], "description": "Multi split entry-level per linea MSZ-HR.", "models_prefix": ["MXZ-2HA", "MXZ-3HA", "MXZ-HA"], "keywords": ["MXZ-HA", "MXZ-2HA", "MXZ-3HA"]},
        {"id": "MITSU_MXZ_VF", "name": "MXZ-VF / MXZ-F MULTI INVERTER", "category": "RESIDENZIALE", "type": "MULTI_SPLIT", "pages": [494, 498], "description": "Gamma multi split completa da 2 a 6 attacchi, anche Hyper Heating (VFHZ).", "models_prefix": ["MXZ-2F", "MXZ-3F", "MXZ-4F", "MXZ-5F", "MXZ-6F", "MXZ-F", "MXZ-VF", "MXZ-2F53VFHZ"], "keywords": ["MXZ-2F", "MXZ-3F", "MXZ-4F", "MXZ-5F", "MXZ-6F", "MXZ-VF", "MXZ-F"]},
        {"id": "MITSU_PUMY", "name": "SMALL Y PUMY-SP MINI VRF", "category": "COMMERCIALE", "type": "MULTI_SPLIT", "pages": [495], "description": "Mini VRF con branch box per grandi ville ed uffici.", "models_prefix": ["PUMY-SP", "PUMY"], "keywords": ["PUMY-SP", "PUMY"]},
        {"id": "MITSU_PKA_M", "name": "PKA-M LAL/KAL PARETE MR SLIM", "category": "COMMERCIALE", "type": "PARETE", "pages": [499, 502, 507], "description": "Parete commerciale Mr Slim ad alta robustezza.", "models_prefix": ["PKA-M"], "keywords": ["PKA-M"]},
        {"id": "MITSU_PEAD_M", "name": "PEAD-M JA2 CANALIZZATA (MEDIA-ALTA PREVALENZA)", "category": "COMMERCIALE", "type": "CANALIZZATO", "pages": [499, 502], "description": "Canalizzata Mr Slim con prevalenza fino a 150 Pa.", "models_prefix": ["PEAD-M"], "keywords": ["PEAD-M"]},
        {"id": "MITSU_PEA_M", "name": "PEA-M LA CANALIZZATA (ALTA PREVALENZA)", "category": "COMMERCIALE", "type": "CANALIZZATO", "pages": [500], "description": "Canalizzata ad alta prevalenza fino a 250 Pa.", "models_prefix": ["PEA-M"], "keywords": ["PEA-M"]},
        {"id": "MITSU_PLA_M", "name": "PLA-M EA2 CASSETTA 90x90", "category": "COMMERCIALE", "type": "CASSETTA_90X90", "pages": [500, 504, 508], "description": "Cassetta 90x90 Mr Slim con flusso d'aria Coanda.", "models_prefix": ["PLA-M", "PLA-RP"], "keywords": ["PLA-M", "PLA-RP"]},
        {"id": "MITSU_PCA_M", "name": "PCA-M KA2 / HA2 PENSILE SOFFITTO", "category": "COMMERCIALE", "type": "PENSILE_SOFFITTO", "pages": [501, 504, 505, 508], "description": "Pensile a soffitto Mr Slim (incluso acciaio inox HA2).", "models_prefix": ["PCA-M"], "keywords": ["PCA-M"]},
        {"id": "MITSU_PSA_M", "name": "PSA-M COLONNA MR SLIM", "category": "COMMERCIALE", "type": "COLONNA", "pages": [501, 505], "description": "Colonna commerciale Mr Slim con display LCD.", "models_prefix": ["PSA-M"], "keywords": ["PSA-M"]},
        {"id": "MITSU_POWER_INVERTER", "name": "POWER INVERTER PUZ-ZM", "category": "COMMERCIALE_UE", "type": "COMMERCIALE_UE", "pages": [502, 503, 505, 506], "description": "Motori commerciali Power Inverter top di gamma.", "models_prefix": ["PUZ-ZM"], "keywords": ["PUZ-ZM", "POWER INVERTER"]},
        {"id": "MITSU_STANDARD_INVERTER", "name": "STANDARD INVERTER PUZ-M / SUZ-M", "category": "COMMERCIALE_UE", "type": "COMMERCIALE_UE", "pages": [499, 501, 506], "description": "Motori commerciali linea Standard Inverter.", "models_prefix": ["PUZ-M", "SUZ-M"], "keywords": ["PUZ-M", "SUZ-M", "STANDARD INVERTER"]}
    ],

    "PANASONIC": [
        {"id": "PANA_BZ", "name": "BZ COMPATTO", "category": "RESIDENZIALE", "type": "PARETE", "pages": [510], "description": "Unità ultracompatta da 779 mm con filtro antipolvere.", "models_prefix": ["CS-BZ", "CU-BZ"], "keywords": ["CS-BZ", "CU-BZ", "BZ"]},
        {"id": "PANA_TZ", "name": "TZ SUPER COMPATTO", "category": "RESIDENZIALE", "type": "PARETE", "pages": [510], "description": "Larghezza 779 mm con nanoe X Generator Mark 1 e Wi-Fi.", "models_prefix": ["CS-TZ", "CU-TZ"], "keywords": ["CS-TZ", "CU-TZ", "TZ"]},
        {"id": "PANA_ETHEREA", "name": "ETHEREA", "category": "RESIDENZIALE", "type": "PARETE", "pages": [511], "description": "Top di gamma con nanoe X Mark 3 (Bianco Opaco e Silver).", "models_prefix": ["CS-Z", "CS-XZ", "CU-Z"], "keywords": ["ETHEREA", "CS-Z", "CS-XZ", "CU-Z"]},
        {"id": "PANA_CONSOLE", "name": "CONSOLE DA PAVIMENTO", "category": "RESIDENZIALE", "type": "CONSOLE_PAVIMENTO", "pages": [512], "description": "Console a pavimento con flusso d'aria bidirezionale nanoe X.", "models_prefix": ["CS-Z25UFEAW", "CS-Z35UFEAW", "CS-Z50UFEAW", "CS-Z25CFEAW"], "keywords": ["CONSOLE", "UFEAW", "CFEAW"]},
        {"id": "PANA_MULTI_Z", "name": "MULTI Z", "category": "RESIDENZIALE", "type": "MULTI_SPLIT", "pages": [513], "description": "Unità esterne multi split Free Multi Z da 2 a 5 attacchi.", "models_prefix": ["CU-2Z", "CU-3Z", "CU-4Z", "CU-5Z"], "keywords": ["MULTI Z", "CU-2Z", "CU-3Z", "CU-4Z", "CU-5Z"]},
        {"id": "PANA_CANALIZZATA_RES", "name": "CANALIZZATA RESIDENZIALE UD3EA / CD3EA", "category": "COMMERCIALE_LIGHT", "type": "CANALIZZATO", "pages": [514], "description": "Canalizzata residenziale a bassa prevalenza compatta.", "models_prefix": ["CS-MZ20UD3EA", "CS-Z25UD3EA", "CS-Z35UD3EA", "CS-Z50UD3EA", "CS-MZ20CD3EA"], "keywords": ["UD3EA", "CD3EA"]},
        {"id": "PANA_CASSETTA_60", "name": "CASSETTA 60x60 RESIDENZIALE UB4EA", "category": "COMMERCIALE_LIGHT", "type": "CASSETTA_60X60", "pages": [514], "description": "Cassetta 4 vie compatta 60x60.", "models_prefix": ["CS-MZ20UB4EA", "CS-Z25UB4EA", "CS-Z35UB4EA", "CS-Z50UB4EA"], "keywords": ["UB4EA"]},
        {"id": "PANA_PACI_STANDARD", "name": "PACI NX STANDARD", "category": "COMMERCIALE", "type": "COMMERCIALE", "pages": [515, 516, 517], "description": "Gamma commerciale Panasonic PACi NX Standard abbinabile a Parete, Canalizzata, Cassetta 60x60/90x90 e Soffitto.", "models_prefix": ["U-100PZ", "U-125PZ", "U-140PZ", "U-36PZ", "U-50PZ", "U-60PZ", "U-71PZ", "S-1014PF3E", "S-3650PF3E", "S-6071PF3E"], "keywords": ["PACI NX STANDARD", "PACI", "PZ3E5", "PF3E", "PU3E", "PT3E", "PK3E"]},
        {"id": "PANA_PACI_ELITE", "name": "PACI NX ELITE", "category": "COMMERCIALE", "type": "COMMERCIALE", "pages": [518, 519, 520], "description": "Gamma commerciale PACi NX Elite ad altissima efficienza.", "models_prefix": ["U-100PZH", "U-125PZH", "U-140PZH", "U-36PZH", "U-50PZH", "U-60PZH", "U-71PZH"], "keywords": ["PACI NX ELITE", "PZH4E5", "PZH4E8"]},
        {"id": "PANA_BIG_PACI", "name": "BIG PACI ALTA PREVALENZA", "category": "COMMERCIALE", "type": "CANALIZZATO", "pages": [521], "description": "Unità commerciale per grandi ambienti con prevalenza fino a 200 Pa.", "models_prefix": ["U-200PZH", "U-250PZH", "S-200PE", "S-250PE"], "keywords": ["BIG PACI", "U-200PZH", "U-250PZH"]}
    ],

    "TOSHIBA": [
        {"id": "TOSH_SEIYA", "name": "SEIYA CLASSIC / SEIYA", "category": "RESIDENZIALE", "type": "PARETE", "pages": [523], "description": "Linea residenziale con batteria Ultra Pure e Magic Coil.", "models_prefix": ["RAS-B10B2KVG", "RAS-B13B2KVG", "RAS-B16B2KVG", "RAS-B07E2KVG", "RAS-B10E2KVG", "RAS-B13E2KVG"], "keywords": ["SEIYA"]},
        {"id": "TOSH_SHORAI_EDGE", "name": "SHORAI EDGE", "category": "RESIDENZIALE", "type": "PARETE", "pages": [523], "description": "Design moderno a linee tese opaco con flusso HADA Care.", "models_prefix": ["RAS-B10G3KVSG", "RAS-B13G3KVSG", "RAS-B16G3KVSG", "RAS-B22G3KVSG", "RAS-B24G3KVSG"], "keywords": ["SHORAI", "SHORAI EDGE"]},
        {"id": "TOSH_DAISEIKAI_10", "name": "DAISEIKAI 10", "category": "RESIDENZIALE", "type": "PARETE", "pages": [524], "description": "Top di gamma assoluto A+++ in raffrescamento e riscaldamento in vero legno di frassino o satinato.", "models_prefix": ["RAS-B10S4KVPG", "RAS-B13S4KVPG", "RAS-B16S4KVPG", "RAS-10S4AVPG", "RAS-13S4AVPG"], "keywords": ["DAISEIKAI", "DAISEIKAI 10"]},
        {"id": "TOSH_HAORI", "name": "HAORI", "category": "RESIDENZIALE", "type": "PARETE", "pages": [524], "description": "Rivestimento personalizzabile in tessuto d'arredo.", "models_prefix": ["RAS-B10N4KVRG", "RAS-B13N4KVRG", "RAS-B16N4KVRG"], "keywords": ["HAORI"]},
        {"id": "TOSH_CONSOLE", "name": "CONSOLE A PAVIMENTO", "category": "RESIDENZIALE", "type": "CONSOLE_PAVIMENTO", "pages": [524], "description": "Console a pavimento con mandata bi-flow ad effetto radiante.", "models_prefix": ["RAS-B10J2FVG", "RAS-B13J2FVG", "RAS-B18J2FVG"], "keywords": ["CONSOLE", "J2FVG"]},
        {"id": "TOSH_MULTI_M", "name": "MULTI SPLIT RAS-M", "category": "RESIDENZIALE", "type": "MULTI_SPLIT", "pages": [525], "description": "Unità esterne multi split Toshiba da 2 a 5 attacchi.", "models_prefix": ["RAS-2M", "RAS-3M", "RAS-4M", "RAS-5M"], "keywords": ["RAS-2M", "RAS-3M", "RAS-4M", "RAS-5M", "2M10", "2M14", "2M18", "3M26", "4M27", "5M34"]},
        {"id": "TOSH_CANALIZZATA_SLIM", "name": "CANALIZZATA RIBASSATA / ULTRAPIATTA", "category": "COMMERCIALE_LIGHT", "type": "CANALIZZATO", "pages": [527, 528], "description": "Canalizzata sottile 210 mm per controsoffitti ribassati.", "models_prefix": ["RAS-M07U2DVG", "RAS-M10U2DVG", "RAS-M13U2DVG", "RAV-HM301SDTY", "RAV-HM401SDTY"], "keywords": ["SDTY", "U2DVG"]},
        {"id": "TOSH_CASSETTA_60", "name": "CASSETTA 4 VIE 60x60", "category": "COMMERCIALE_LIGHT", "type": "CASSETTA_60X60", "pages": [527, 528, 529], "description": "Cassetta compatta 60x60 con alette indipendenti.", "models_prefix": ["RAS-M10U2MUVG", "RAS-M13U2MUVG", "RAV-HM301MUT", "RAV-HM401MUT", "RAV-HM561MUT"], "keywords": ["MUT", "MUTP", "U2MUVG"]},
        {"id": "TOSH_COMMERCIALE_RAV", "name": "COMMERCIALE RAV (DIGITAL / SUPER DIGITAL)", "category": "COMMERCIALE", "type": "COMMERCIALE", "pages": [530, 531, 532, 533, 535, 537, 538], "description": "Gamma commerciale completa: Parete (KRTP), Canalizzata Standard (BTP), Soffitto (CTP), Cassetta 90x90 (UTP), Colonna (FT) e motori Digital e Super Digital.", "models_prefix": ["RAV-GM", "RAV-GV", "RAV-GP", "RAV-HM", "RAV-RM"], "keywords": ["RAV-GM", "RAV-GV", "RAV-GP", "DIGITAL INVERTER", "SUPER DIGITAL", "RAV-HM", "RAV-RM", "BTPE", "KRTP", "UTPE", "FTPE"]}
    ],

    "MIDEA": [
        {"id": "MIDEA_XTREME_PRO", "name": "XTREME PRO WI-FI", "category": "RESIDENZIALE", "type": "PARETE", "pages": [539], "description": "Serie residenziale monosplit con controllo Wi-Fi e ionizzatore.", "models_prefix": ["MSAGAU", "XTREME PRO"], "keywords": ["XTREME PRO", "MSAGAU", "AGAU"]},
        {"id": "MIDEA_FLEXI", "name": "FLEXI / BREEZELESS", "category": "RESIDENZIALE", "type": "PARETE", "pages": [539], "description": "Innovativo deflettore TwinFlap con microfori per diffusione aria senza correnti dirette.", "models_prefix": ["MSAGBU", "MSFAAU", "BREEZELESS", "FLEXI"], "keywords": ["FLEXI", "BREEZELESS", "MSAGBU", "MSFAAU"]},
        {"id": "MIDEA_ALYA", "name": "ALYA", "category": "RESIDENZIALE", "type": "PARETE", "pages": [539], "description": "Serie a parete compatta residenziale Alya 9, 12, 18, 24.", "models_prefix": ["ALYA", "ALYA 9", "ALYA 12", "ALYA 18"], "keywords": ["ALYA"]},
        {"id": "MIDEA_MULTI", "name": "MULTI SPLIT MIDEA", "category": "RESIDENZIALE", "type": "MULTI_SPLIT", "pages": [540, 542, 543, 544, 545], "description": "Unità esterne multi split da 2 a 5 attacchi (M2OH, M2OE, M3OE, M4OE, M5OE).", "models_prefix": ["M2OH", "M2OE", "M3OE", "M4OE", "M5OE"], "keywords": ["M2OH", "M2OE", "M3OE", "M4OE", "M5OE"]},
        {"id": "MIDEA_COMMERCIALE", "name": "COMMERCIALE MIDEA (CANALIZZATO / CASSETTA / CONSOLE / COLONNA / MDV)", "category": "COMMERCIALE", "type": "COMMERCIALE", "pages": [541, 546, 547], "description": "Gamma commerciale con canalizzati MTI, cassette 60x60 MCA4 e 90x90 MCD, console MFA, soffitto MUE, colonna MFM e motori MOD30U / MDV.", "models_prefix": ["MTI", "MCA4", "MCD", "MFA", "MUE", "MFM", "MOD30U", "MDV"], "keywords": ["MTI", "MCA4", "MCD", "MFA", "MUE", "MFM", "MOD30U", "MDV", "COMM CAN", "COMM CASS"]}
    ],

    "HISENSE": [
        {"id": "HIS_EASY_SMART", "name": "EASY SMART", "category": "RESIDENZIALE", "type": "PARETE", "pages": [548], "description": "Climatizzatore monosplit entry con display LED a scomparsa e 4 filtri in 1.", "models_prefix": ["CA25YR", "CA35YR", "CA50XS", "CA70BT", "EASY SMART"], "keywords": ["EASY SMART", "CA25YR", "CA35YR", "CA50XS", "CA70BT"]},
        {"id": "HIS_ENERGY_PRO", "name": "ENERGY PRO X / PLUS", "category": "RESIDENZIALE", "type": "PARETE", "pages": [548], "description": "Top di gamma Hisense in classe A+++/A+++ con sensore intelligente Smart Eye e sterilizzazione TMS.", "models_prefix": ["QE25XV", "QE35XV", "QE50XV", "ENERGY PRO"], "keywords": ["ENERGY PRO", "ENERGY PRO X", "ENERGY PRO PLUS", "QE25XV", "QE35XV"]},
        {"id": "HIS_HI_COMFORT", "name": "HI-COMFORT", "category": "RESIDENZIALE", "type": "PARETE", "pages": [548], "description": "Serie a parete comfort con Wi-Fi integrato ConnectLife.", "models_prefix": ["AS25YR4BW", "AS35MR0BW", "AS50XS1GW", "AS70BT2BW", "HI COMFORT"], "keywords": ["HI COMFORT", "HI-COMFORT", "AS25YR", "AS35MR"]},
        {"id": "HIS_AIR_MASTER", "name": "AIR MASTER / SILENTIUM PRO", "category": "RESIDENZIALE", "type": "PARETE", "pages": [548, 550], "description": "Serie ad altissima silenziosità (16 dB) con ricambio d'aria fresca dall'esterno.", "models_prefix": ["AS25WM", "AS35WM", "AIR MASTER", "SILENTIUM"], "keywords": ["AIR MASTER", "SILENTIUM", "AS25WM", "AS35WM"]},
        {"id": "HIS_MULTI", "name": "MULTI INVERTER HISENSE", "category": "RESIDENZIALE", "type": "MULTI_SPLIT", "pages": [549, 550], "description": "Unità esterne multi split Free Match da 2 a 5 attacchi (2AMW, 3AMW, 4AMW, 5AMW).", "models_prefix": ["2AMW", "3AMW", "4AMW", "5AMW"], "keywords": ["2AMW", "3AMW", "4AMW", "5AMW"]},
        {"id": "HIS_COMMERCIALE", "name": "COMMERCIALE HISENSE (CANALIZZATO / CASSETTA / CONSOLE / COLONNA)", "category": "COMMERCIALE", "type": "COMMERCIALE", "pages": [551, 552], "description": "Gamma commerciale con canalizzati ADT e AUD, cassette Round Flow ACT, console AKT, soffitto-pavimento AVT e colonne AUF con motori AUW e UNI HB.", "models_prefix": ["ADT", "AUD", "ACT", "AKT", "AVT", "AUF", "AUW", "UNI HB"], "keywords": ["ADT", "AUD", "ACT", "AKT", "AVT", "AUF", "AUW", "UNI HB", "COMM CANALIZZ", "ROUND-FLOW"]}
    ],

    "KOSAMI": [
        {"id": "KOS_PEONY", "name": "PEONY", "category": "RESIDENZIALE", "type": "PARETE", "pages": [553], "description": "Serie residenziale monosplit elegante.", "models_prefix": ["PEONY"], "keywords": ["PEONY"]},
        {"id": "KOS_BORA", "name": "BORA BIANCO OPACO", "category": "RESIDENZIALE", "type": "PARETE", "pages": [553], "description": "Serie a parete moderna finitura bianco opaco.", "models_prefix": ["BORA"], "keywords": ["BORA"]},
        {"id": "KOS_VENUS", "name": "VENUS", "category": "RESIDENZIALE", "type": "PARETE", "pages": [554], "description": "Serie monosplit e multisplit Venus con Wi-Fi.", "models_prefix": ["VENUS"], "keywords": ["VENUS"]},
        {"id": "KOS_PAROS", "name": "MULTI SPLIT PAROS", "category": "RESIDENZIALE", "type": "MULTI_SPLIT", "pages": [554], "description": "Unità esterne multi split Paros da 2 a 4 attacchi.", "models_prefix": ["PAROS"], "keywords": ["PAROS"]},
        {"id": "KOS_COMM", "name": "COMMERCIALE KOSAMI (CANALIZZATO / CASSETTA / CONSOLE / COLONNA)", "category": "COMMERCIALE", "type": "COMMERCIALE", "pages": [555], "description": "Gamma commerciale Kosami per grandi impianti.", "models_prefix": ["CAN-CASS", "COMM CAN", "COMM CASS", "COMM COLONNA", "COMM PAVIM"], "keywords": ["CAN-CASS", "COMM CAN", "COMM CASS", "COMM COLONNA", "COMM PAVIM"]}
    ],

    "HAIER": [
        {"id": "HAIER_TIDE", "name": "TIDE R / TIDE GREEN", "category": "RESIDENZIALE", "type": "PARETE", "pages": [556], "description": "Serie monosplit R32 entry-level affidabile ed economica.", "models_prefix": ["HEC", "TIDE"], "keywords": ["TIDE", "HEC"]},
        {"id": "HAIER_GEOS", "name": "GEOS PLUS+", "category": "RESIDENZIALE", "type": "PARETE", "pages": [557], "description": "Monosplit residenziale con tecnologia Inverter Plus e Self-Clean.", "models_prefix": ["AS25TADHRA", "AS35TADHRA", "GEOS"], "keywords": ["GEOS", "GEOS PLUS"]},
        {"id": "HAIER_FLEXIS", "name": "FLEXIS PLUS", "category": "RESIDENZIALE", "type": "PARETE", "pages": [557], "description": "Design elegante in finitura Bianco e Nero Opaco con lampada UV-C Pro e sensore Eco Sensor.", "models_prefix": ["AS25S2SF1FA", "AS35S2SF1FA", "AS50S2SF1FA", "AS71S2SF1FA"], "keywords": ["FLEXIS", "FLEXIS PLUS"]},
        {"id": "HAIER_EXPERT", "name": "EXPERT", "category": "RESIDENZIALE", "type": "PARETE", "pages": [564, 565], "description": "Top di gamma Haier con sterilizzazione UV-C, igienizzazione a 56°C e facilità estrema di smontaggio e pulizia.", "models_prefix": ["AS20XCAHRA", "AS25XCAHRA", "AS35XCAHRA", "AS50XCAHRA", "AS71XCAHRA"], "keywords": ["EXPERT"]},
        {"id": "HAIER_PEARL", "name": "PEARL", "category": "RESIDENZIALE", "type": "PARETE", "pages": [557], "description": "Serie con tecnologia Self-Clean, UV-C Sterilisation e Wi-Fi integrato con hOn.", "models_prefix": ["AS20PBAHRA", "AS25PBAHRA", "AS35PBAHRA", "AS50PBAHRA", "AS71PBAHRA"], "keywords": ["PEARL"]},
        {"id": "HAIER_REVIVE", "name": "REVIVE", "category": "RESIDENZIALE", "type": "PARETE", "pages": [561], "description": "Climatizzatore a parete residenziale smart compatibile con app hOn e controllo vocale.", "models_prefix": ["AS25RHBHRA", "AS35RHBHRA", "AS50RHBHRA", "AS68RHBHRA"], "keywords": ["REVIVE"]},
        {"id": "HAIER_MULTI", "name": "MULTI SPLIT HAIER (2U/3U/4U/5U)", "category": "RESIDENZIALE", "type": "MULTI_SPLIT", "pages": [561, 562, 564], "description": "Unità esterne multi split R32 Super Match collegabili da 2 a 5 unità interne.", "models_prefix": ["2U40", "2U50", "3U55", "3U70", "4U75", "4U85", "5U90", "5U105", "5U125"], "keywords": ["2U40", "2U50", "3U55", "3U70", "4U75", "4U85", "5U90", "5U105", "5U125"]},
        {"id": "HAIER_COMM_MATCH", "name": "COMMERCIALE SUPER MATCH (CANALIZZATO / CASSETTA / CONSOLE / COLONNA)", "category": "COMMERCIALE", "type": "COMMERCIALE", "pages": [558, 559, 560, 563, 565, 566, 567, 568, 569], "description": "Gamma commerciale Haier con Canalizzati (Slim, Media e Alta Prevalenza), Cassette (1 via, 620 e Round Flow 90x90), Console e Colonne Cabinet.", "models_prefix": ["AD25", "AD35", "AD50", "AD71", "AD105", "AD125", "AD140", "ADH125", "AB25", "AB35", "AB50", "AB71", "AB105", "AF25", "AF35", "AC50", "AP71", "AP105", "AP140", "1U25", "1U35", "1U50", "1U71", "1U105", "1U140"], "keywords": ["1U", "SUPER MATCH", "COMM", "CANALIZZ", "CASSETTA", "CONSOLE", "COLONNA"]}
    ],

    "SAMSUNG": [
        {"id": "SAMS_AR35", "name": "AR35", "category": "RESIDENZIALE", "type": "PARETE", "pages": [571], "description": "Monosplit essenziale Samsung classe A++/A+.", "models_prefix": ["AR09TXHQASI", "AR12TXHQASI", "AR18TXHQASI", "AR24TXHQASI"], "keywords": ["AR35"]},
        {"id": "SAMS_WINDFREE_PREMIERE", "name": "WINDFREE PREMIÈRE+", "category": "RESIDENZIALE", "type": "PARETE", "pages": [572, 575], "description": "La massima espressione della tecnologia WindFree a migliaia di microfori con finiture White e Black.", "models_prefix": ["AR70H09", "AR70H12", "AR70H18", "AR70H24"], "keywords": ["WINDFREE PREMIERE", "PREMIERE+"]},
        {"id": "SAMS_WINDFREE_ELITE", "name": "WINDFREE ELITE / BLACK", "category": "RESIDENZIALE", "type": "PARETE", "pages": [571, 575], "description": "Top di gamma con filtro Tri-Care e sensore di movimento MDS.", "models_prefix": ["AR09TXCAAWK", "AR12TXCAAWK"], "keywords": ["WINDFREE ELITE", "WINDFREE BLACK"]},
        {"id": "SAMS_WINDFREE_AVANT", "name": "WINDFREE AVANT", "category": "RESIDENZIALE", "type": "PARETE", "pages": [575], "description": "Raffrescamento senza getti d'aria diretti con filtro antibatterico Tri-Care.", "models_prefix": ["AR09TXEAAWK", "AR12TXEAAWK", "AR18TXEAAWK", "AR24TXEAAWK"], "keywords": ["WINDFREE AVANT"]},
        {"id": "SAMS_WINDFREE_COMFORT", "name": "WINDFREE COMFORT", "category": "RESIDENZIALE", "type": "PARETE", "pages": [575], "description": "La comodità del WindFree con Easy Filter Plus e Wi-Fi.", "models_prefix": ["AR09TXFCAWK", "AR12TXFCAWK", "AR18TXFCAWK", "AR24TXFCAWK"], "keywords": ["WINDFREE COMFORT"]},
        {"id": "SAMS_CEBU", "name": "CEBU WI-FI", "category": "RESIDENZIALE", "type": "PARETE", "pages": [575], "description": "Split a parete tradizionale con AI Auto Comfort e SmartThings.", "models_prefix": ["AR09TXFYAWK", "AR12TXFYAWK", "AR18TXFYAWK", "AR24TXFYAWK"], "keywords": ["CEBU"]},
        {"id": "SAMS_MULTI_FJM", "name": "MULTI SPLIT FJM", "category": "RESIDENZIALE", "type": "MULTI_SPLIT", "pages": [573, 575], "description": "Unità esterne Free Joint Multi (FJM) da 2 a 5 connessioni.", "models_prefix": ["AJ040", "AJ050", "AJ052", "AJ068", "AJ080", "AJ100"], "keywords": ["AJ040", "AJ050", "AJ052", "AJ068", "AJ080", "AJ100", "FJM"]},
        {"id": "SAMS_CAC_COMMERCIALE", "name": "COMMERCIALE CAC (WINDFREE 360° / CASSETTE / CANALIZZATI / COLONNA)", "category": "COMMERCIALE", "type": "COMMERCIALE", "pages": [574, 576, 577, 578, 579, 580], "description": "Gamma commerciale Samsung CAC R32/R410 con la rivoluzionaria Cassetta 360° circolare, Cassette WindFree 1 via, 4 vie mini 60x60 e standard 90x90, canalizzati LSP/MSP e colonne.", "models_prefix": ["AC026", "AC035", "AC052", "AC071", "AC100", "AC120", "AC140", "AC200", "AC250"], "keywords": ["COMM AC", "WINDFREE DELUXE", "CASSETTA 360", "RNNDKG", "RN4DKG", "RN4PKG", "RN1DKG", "MNLDKG", "MNMDKG", "BNPDKH"]}
    ],

    "LG": [
        {"id": "LG_LIBERO", "name": "LIBERO / LIBERO SMART", "category": "RESIDENZIALE", "type": "PARETE", "pages": [582, 585], "description": "Climatizzatore monosplit/multisplit essenziale e silenzioso con Wi-Fi ThinQ integrato.", "models_prefix": ["W09TI", "W12TI", "W18TI", "W24TI", "S09ET", "S12ET", "S18ET", "S24ET"], "keywords": ["LIBERO", "LIBERO SMART"]},
        {"id": "LG_DUALCOOL_DELUXE", "name": "DUALCOOL DELUXE", "category": "RESIDENZIALE", "type": "PARETE", "pages": [582], "description": "Climatizzatore con tecnologia UVnano e purificazione Plasmaster Plus.", "models_prefix": ["H09S1DA", "H12S1DA", "H18S1DA", "H24S1DA"], "keywords": ["DUALCOOL DELUXE"]},
        {"id": "LG_DUALCOOL_PREMIUM", "name": "DUALCOOL PREMIUM AL AIR", "category": "RESIDENZIALE", "type": "PARETE", "pages": [583], "description": "Top di gamma con intelligenza artificiale AI Air e purificazione aria completa.", "models_prefix": ["H09S1PA", "H12S1PA"], "keywords": ["DUALCOOL PREMIUM"]},
        {"id": "LG_ARTCOOL_GALLERY", "name": "ARTCOOL GALLERY PHOTO / LCD", "category": "RESIDENZIALE", "type": "PARETE", "pages": [583, 585], "description": "Iconico quadro d'arredo a parete con cornice personalizzabile con fotografie o display digitale LCD.", "models_prefix": ["A09GA2", "A12GA2"], "keywords": ["ARTCOOL GALLERY"]},
        {"id": "LG_ARTCOOL_MIRROR", "name": "ARTCOOL MIRROR / BLACK", "category": "RESIDENZIALE", "type": "PARETE", "pages": [582, 583], "description": "Elegante superficie in vetro a specchio nero riflettente con ionizzatore UVnano.", "models_prefix": ["AC09BQ", "AC12BQ", "AC18BQ", "AC24BQ", "AA09SB", "AA12SB"], "keywords": ["ARTCOOL MIRROR", "ARTCOOL BLACK"]},
        {"id": "LG_MULTI", "name": "MULTI SPLIT LG R32", "category": "RESIDENZIALE", "type": "MULTI_SPLIT", "pages": [584], "description": "Unità esterne multi split MU2R, MU3R, MU4R, MU5R da 2 a 5 attacchi.", "models_prefix": ["MU2R", "MU3R", "MU4R", "MU5R"], "keywords": ["MU2R", "MU3R", "MU4R", "MU5R"]},
        {"id": "LG_COMMERCIALE", "name": "COMMERCIALE UNIVERSAL (ROUND CASSETTE 360° / CASSETTE / CANALIZZATI / SOFFITTO)", "category": "COMMERCIALE", "type": "COMMERCIALE", "pages": [586, 587, 588, 589, 590, 591, 592], "description": "Gamma commerciale LG con motori Universal Inverter UUA, UUB, UUC, UUD e unità interne Round Cassette 360°, Cassette 4 vie 57x57 e 84x84, Canalizzati bassa e alta prevalenza e Soffitto.", "models_prefix": ["CT09", "CT12", "CT18", "CT24", "UT30", "UT36", "UT42", "UT48", "UT60", "CL09", "CL12", "CL18", "CL24", "UM12", "UM18", "UM24", "UM30", "UM36", "UM42", "UM48", "UB200", "UB250", "UV18", "UV24", "UV30", "UV36", "UV42", "UV48", "UUA1", "UUB1", "UUC1", "UUD1", "UUD3"], "keywords": ["COMM", "UNIVERSAL", "ROUND CASSETTE", "UUA", "UUB", "UUC", "UUD", "UT36", "UT48", "UM12", "UM18", "UM24", "UM36", "UM48"]}
    ],

    "FERROLI": [
        {"id": "FERR_GIADA", "name": "GIADA (MONOSPLIT E MULTI)", "category": "RESIDENZIALE", "type": "PARETE", "pages": [594], "description": "Gamma monosplit e multi split residenziale con ionizzatore a 4 stadi di filtrazione.", "models_prefix": ["GIADA"], "keywords": ["GIADA"]},
        {"id": "FERR_GIADA_C", "name": "GIADA-C (CANALIZZATA E CASSETTA 90X90)", "category": "COMMERCIALE", "type": "COMMERCIALE", "pages": [595], "description": "Gamma commerciale Ferroli con canalizzati media prevalenza e cassette 90x90.", "models_prefix": ["GIADA-C", "DUCT", "CASSETTA 90X90"], "keywords": ["GIADA-C", "DUCT"]},
        {"id": "FERR_AMBRA", "name": "AMBRA", "category": "RESIDENZIALE", "type": "PARETE", "pages": [594], "description": "Serie residenziale monosplit compatta classe A++.", "models_prefix": ["AMBRA"], "keywords": ["AMBRA"]}
    ],

    "BAXI": [
        {"id": "BAXI_ASTRA", "name": "ASTRA", "category": "RESIDENZIALE", "type": "PARETE", "pages": [596], "description": "Serie monosplit residenziale Baxi con ionizzatore antibatterico.", "models_prefix": ["ASTRA", "LSGT", "JSGNW"], "keywords": ["ASTRA", "LSGT25", "LSGT35", "LSGT50", "LSGT70", "JSGNW"]},
        {"id": "BAXI_SIDERA", "name": "SIDERA", "category": "RESIDENZIALE", "type": "PARETE", "pages": [596], "description": "Serie con ionizzatore di serie e design raffinato.", "models_prefix": ["SIDERA"], "keywords": ["SIDERA"]},
        {"id": "BAXI_MULTI", "name": "MULTI SPLIT BAXI", "category": "RESIDENZIALE", "type": "MULTI_SPLIT", "pages": [597, 598], "description": "Unità esterne multi split Baxi da 2 a 5 porte.", "models_prefix": ["LSGT40-2M", "LSGT50-2M", "LSGT60-3M", "LSGT70-3M", "LSGT80-4M", "LSGT100-4M", "LSGT120-5M"], "keywords": ["LSGT", "MULTI", "2M", "3M", "4M", "5M"]},
        {"id": "BAXI_LIGHT_COMM", "name": "LIGHT COMMERCIAL (CANALIZZATA / CASSETTA / CONSOLE)", "category": "COMMERCIALE", "type": "COMMERCIALE", "pages": [597, 599], "description": "Gamma light commercial Baxi comprendente canalizzati, cassette 4 vie e console.", "models_prefix": ["RZ2GT", "RZGT", "RZ2GND", "RZGBK", "LSGBK", "LSGND", "RZ2GNF"], "keywords": ["LIGHTCOMM", "RZ2GT", "RZGT", "RZ2GND", "RZGBK", "RZ2GNF"]}
    ],

    "ARISTON": [
        {"id": "ARIS_KIOS", "name": "KIOS NET", "category": "RESIDENZIALE", "type": "PARETE", "pages": [600], "description": "Top di gamma con Wi-Fi Ariston Clima integrato e sensore 3D.", "models_prefix": ["KIOS", "KIOS NET"], "keywords": ["KIOS", "KIOS NET"]},
        {"id": "ARIS_NEVIS", "name": "NEVIS EVO", "category": "RESIDENZIALE", "type": "PARETE", "pages": [600], "description": "Serie residenziale evoluta classe A+++/A++.", "models_prefix": ["NEVIS", "NEVIS EVO"], "keywords": ["NEVIS", "NEVIS EVO"]},
        {"id": "ARIS_ALYS", "name": "ALYS", "category": "RESIDENZIALE", "type": "PARETE", "pages": [600], "description": "Monosplit residenziale elegante con gas ecologico R32.", "models_prefix": ["ALYS"], "keywords": ["ALYS"]},
        {"id": "ARIS_MULTI", "name": "MULTI SPLIT ARISTON (DUAL C / TRIAL C / QUAD C / PENTA C)", "category": "RESIDENZIALE", "type": "MULTI_SPLIT", "pages": [601, 602], "description": "Unità esterne multi split Dual, Trial, Quad e Penta.", "models_prefix": ["DUAL C", "TRIAL C", "QUAD C", "PENTA C", "C 40 XD0", "C 50 XD0", "C 80 XD0", "110 XD0", "121 XD0"], "keywords": ["DUAL C", "TRIAL C", "QUAD C", "PENTA C", "XD0"]},
        {"id": "ARIS_COMM", "name": "COMMERCIALE ARISTON (DUCT CANALIZZATA / CASSETTA SLIM / CONSOLE / SOFFITTO)", "category": "COMMERCIALE", "type": "COMMERCIALE", "pages": [602, 603], "description": "Gamma commerciale con canalizzati DUC, cassette Slim 90x90, console CON e soffitto CEF con unità esterne MUC.", "models_prefix": ["DUC", "MUC", "CON R32", "CEF R32"], "keywords": ["DUC", "MUC", "CON R32", "CEF R32", "SLIM CASSETTA"]}
    ],

    "BERETTA": [
        {"id": "BER_BREVA", "name": "BREVA / BREVA E", "category": "RESIDENZIALE", "type": "PARETE", "pages": [604], "description": "Gamma monosplit e multi split residenziale Beretta a parete in classe A++/A+.", "models_prefix": ["BREVA", "BREVA E", "BREVA IN", "BREVA EX"], "keywords": ["BREVA", "BREVA E"]}
    ],

    "RIELLO": [
        {"id": "RIEL_AARIA_START", "name": "AARIA START N / AMW ST N", "category": "RESIDENZIALE", "type": "PARETE", "pages": [605], "description": "Climatizzatore monosplit entry affidabile e silenzioso.", "models_prefix": ["AARIA START", "AMW 25 ST", "AMW 35 ST", "AMW 50 ST"], "keywords": ["AARIA START", "AMW 25 ST", "AMW 35 ST", "AMW 50 ST", "ST N"]},
        {"id": "RIEL_ELIXA", "name": "RIELLO ELIXA MONO-REW", "category": "RESIDENZIALE", "type": "PARETE", "pages": [605], "description": "Unità a parete residenziale Riello Elixa.", "models_prefix": ["ELIXA", "REW"], "keywords": ["ELIXA", "REW"]},
        {"id": "RIEL_AARIA_PLUS", "name": "AARIA MONO PLUS (AMW PLUS)", "category": "RESIDENZIALE", "type": "PARETE", "pages": [605], "description": "Serie residenziale monosplit ad alta efficienza e tecnologia 3D Airflow.", "models_prefix": ["AARIA MONO", "AMW PLUS", "25 PLUS I", "35 PLUS I", "50 PLUS I"], "keywords": ["AARIA MONO", "AMW PLUS", "PLUS I"]},
        {"id": "RIEL_AARIA_MULTI", "name": "AARIA MULTI", "category": "RESIDENZIALE", "type": "MULTI_SPLIT", "pages": [608], "description": "Unità esterne multi split Riello da 2 a 5 attacchi.", "models_prefix": ["AARIA MULTI", "AMW PI", "PI R32"], "keywords": ["AARIA MULTI", "250 PI", "355 PI", "370 PI", "480 PI", "5100 PI", "AMW 20 PI", "AMW 25 PI"]},
        {"id": "RIEL_COMM", "name": "COMMERCIALE AARIA MONO PLUS / PRO P", "category": "COMMERCIALE", "type": "COMMERCIALE", "pages": [606, 607], "description": "Gamma commerciale Riello comprendente Canalizzata AMD, Cassetta AMK 60x60, Console AMC, Soffitto AMS e motori Aaria Pro P.", "models_prefix": ["I-AMD", "I-AMK", "I-AMC", "P-AMS", "AARIA PRO P"], "keywords": ["I-AMD", "I-AMK", "I-AMC", "P-AMS", "AARIA PRO P"]}
    ],

    "BOSCH": [
        {"id": "BOSCH_3000I", "name": "CLIMATE 3000i / 3200i", "category": "RESIDENZIALE", "type": "PARETE", "pages": [609], "description": "Climatizzatore monosplit compatto, silenzioso e dai consumi ridotti.", "models_prefix": ["CLIMATE 3000I", "CLIMATE 3200I", "CL3000I"], "keywords": ["CLIMATE 3000I", "CLIMATE 3200I", "CL3000I"]},
        {"id": "BOSCH_4000I", "name": "CLIMATE 4000i", "category": "RESIDENZIALE", "type": "PARETE", "pages": [609], "description": "Monosplit ad alta efficienza e design moderno.", "models_prefix": ["CLIMATE 4000I", "CL4000I"], "keywords": ["CLIMATE 4000I", "CL4000I"]},
        {"id": "BOSCH_6000I", "name": "CLIMATE 6000i", "category": "RESIDENZIALE", "type": "PARETE", "pages": [609], "description": "Serie avanzata con sensore di presenza e controllo umidità.", "models_prefix": ["CLIMATE 6000I", "CL6000I"], "keywords": ["CLIMATE 6000I", "CL6000I"]},
        {"id": "BOSCH_7000I", "name": "CLIMATE 7000i", "category": "RESIDENZIALE", "type": "PARETE", "pages": [609], "description": "Top di gamma a parete con elevatissima classe energetica A+++.", "models_prefix": ["CLIMATE 7000I", "CL7000I"], "keywords": ["CLIMATE 7000I", "CL7000I"]},
        {"id": "BOSCH_COMM_5000I", "name": "CLIMATE 5000 I (CANALIZZATA / CASSETTA)", "category": "COMMERCIALE", "type": "COMMERCIALE", "pages": [610], "description": "Gamma commerciale con canalizzati CL5000i-U, cassette 4 vie CL5000i-4C e motori Climate 5000L.", "models_prefix": ["CL5000I", "CL5000L"], "keywords": ["CANALIZZATA CLIMATE", "CASSETTA CLIMATE", "CL5000I", "CL5000L"]},
        {"id": "BOSCH_MULTI_5000M", "name": "MULTI CLIMATE 5000 M", "category": "RESIDENZIALE", "type": "MULTI_SPLIT", "pages": [611, 612], "description": "Unità esterne multi split da 2 a 5 connessioni.", "models_prefix": ["CL5000M", "CLIMATE 5000M"], "keywords": ["CLIMATE 5000M", "CL5000M", "41/2 E", "53/2 E", "62/3 E", "79/4 E", "82/4 E", "105/4 E", "125/5 E"]}
    ],

    "IMMERGAS": [
        {"id": "IMMER_THOR", "name": "THOR", "category": "RESIDENZIALE", "type": "PARETE", "pages": [613], "description": "Monosplit e multisplit residenziale Immergas a parete classe A++/A+.", "models_prefix": ["THOR"], "keywords": ["THOR"]},
        {"id": "IMMER_GOTHA", "name": "GOTHA", "category": "RESIDENZIALE", "type": "PARETE", "pages": [613], "description": "Serie residenziale monosplit di design con ionizzatore integrato.", "models_prefix": ["GOTHA"], "keywords": ["GOTHA"]},
        {"id": "IMMER_MULTI", "name": "MULTI SPLIT IMMERGAS", "category": "RESIDENZIALE", "type": "MULTI_SPLIT", "pages": [613, 614], "description": "Unità esterne multi split Immergas da 2 a 5 attacchi.", "models_prefix": ["UE MULTI 18", "UE MULTI 21", "UE MULTI 27", "UE MULTI 28", "UE MULTI 36", "UE MULTI 42"], "keywords": ["UE MULTI", "MULTI 2 ATT", "MULTI 3 ATT", "MULTI 4 ATT", "MULTI 5 ATT"]},
        {"id": "IMMER_COMM", "name": "COMMERCIALE IMMERGAS (CANALIZZATO DUCT / CASSETTA / CONSOLE)", "category": "COMMERCIALE", "type": "COMMERCIALE", "pages": [613], "description": "Unità interne ed esterne canalizzate, cassette e console.", "models_prefix": ["UI DUCT", "UI CAS", "UI CONSOLE"], "keywords": ["UI DUCT", "UI CAS", "UI CONSOLE", "CANALIZZABILE DUCT"]}
    ],

    "HSD": [
        {"id": "HSD_VIVAIR_ONE", "name": "VIVAIR ONE", "category": "RESIDENZIALE", "type": "PARETE", "pages": [615], "description": "Climatizzatore a parete residenziale compatto ed essenziale.", "models_prefix": ["SDHL 1-030", "VIVAIR ONE"], "keywords": ["VIVAIR ONE", "SDHL"]},
        {"id": "HSD_VIVAIR_LITE", "name": "VIVAIR LITE", "category": "RESIDENZIALE", "type": "PARETE", "pages": [615], "description": "Serie residenziale monosplit ad alta efficienza energetica.", "models_prefix": ["SDH B1-025S", "SDH B1-035S", "SDH B1-050S", "VIVAIR LITE"], "keywords": ["VIVAIR LITE", "SDH B1"]},
        {"id": "HSD_VIVAIR_TOP", "name": "VIVAIR TOP COMFORT / UNI COMFORT / MAX", "category": "RESIDENZIALE", "type": "PARETE", "pages": [615], "description": "Serie a parete evoluta con ionizzatore e funzioni comfort avanzate.", "models_prefix": ["SDHP1", "TOP COMFORT", "UNI COMFORT"], "keywords": ["TOP COMFORT", "UNI COMFORT", "VIVAIR MAX", "SDHP1"]},
        {"id": "HSD_VIVAIR_MULTI", "name": "VIVAIR MULTI", "category": "RESIDENZIALE", "type": "MULTI_SPLIT", "pages": [616], "description": "Unità esterne ed interne multi split da 2 a 5 attacchi.", "models_prefix": ["SDH1-040", "SDH1-050", "SDH1-070", "SDH1-080", "SDH1-120"], "keywords": ["VIVAIR MULTI", "MNA2O", "MNA3O", "MNA4O", "MNA5O", "SDH1-"]}
    ],

    "VAILLANT": [
        {"id": "VAIL_INTRO", "name": "CLIMAVAIR INTRO", "category": "RESIDENZIALE", "type": "PARETE", "pages": [617], "description": "Monosplit entry-level Vaillant affidabile, silenzioso e classe A++/A+.", "models_prefix": ["VAIL 1-025", "VAIL 1-030", "VAIL 1-035", "CLIMAVAIR INTRO"], "keywords": ["CLIMAVAIR INTRO", "VAIL 1"]},
        {"id": "VAIL_PRO", "name": "CLIMAVAIR PRO / PLUS", "category": "RESIDENZIALE", "type": "PARETE", "pages": [617], "description": "Serie monosplit e multisplit ad alte prestazioni con purificazione aria e Wi-Fi.", "models_prefix": ["VAIB 1-025", "VAIB 1-035", "VAIB 1-050", "VAIB 1-065", "VAIP1"], "keywords": ["CLIMAVAIR PRO", "CLIMAVAIR PLUS", "VAIB 1", "VAIP1"]},
        {"id": "VAIL_EXCLUSIVE", "name": "CLIMAVAIR EXCLUSIVE", "category": "RESIDENZIALE", "type": "PARETE", "pages": [617], "description": "Top di gamma Vaillant con massima efficienza energetica A+++.", "models_prefix": ["VAI 5-025", "VAI 5-035", "5-025WNO", "5-065WNO"], "keywords": ["CLIMAVAIR EXCLUSIVE", "VAI 5"]},
        {"id": "VAIL_MULTI", "name": "CLIMAVAIR MULTI", "category": "RESIDENZIALE", "type": "MULTI_SPLIT", "pages": [618, 619], "description": "Unità esterne multi split Vaillant da 2 a 5 attacchi.", "models_prefix": ["VAM1-040", "VAM1-050", "VAM1-070", "VAM1-080", "VAM1-120", "VAM1"], "keywords": ["CLIMAVAIR MULTI", "VAM1"]}
    ],

    "AERMEC": [
        {"id": "AERM_SFE", "name": "SFE", "category": "RESIDENZIALE", "type": "PARETE", "pages": [620], "description": "Monosplit residenziale a parete con refrigerante ecologico R32.", "models_prefix": ["SFE250", "SFE350", "SFE500", "SFE700"], "keywords": ["SFE", "SFE250", "SFE350", "SFE500", "SFE700"]},
        {"id": "AERM_SPG", "name": "SPG", "category": "RESIDENZIALE", "type": "PARETE", "pages": [620], "description": "Serie monosplit e multisplit a parete ad alta efficienza energetica con controllo Wi-Fi.", "models_prefix": ["SPG250", "SPG350", "SPG500", "SPG700"], "keywords": ["SPG", "SPG250", "SPG350", "SPG500", "SPG700"]},
        {"id": "AERM_CKG", "name": "CKG CONSOLE", "category": "RESIDENZIALE", "type": "CONSOLE_PAVIMENTO", "pages": [620], "description": "Console da pavimento con doppia mandata d'aria.", "models_prefix": ["CKG261", "CKG361", "CKG501"], "keywords": ["CKG", "CKG261", "CKG361", "CKG501"]},
        {"id": "AERM_MPG", "name": "MPG / MGE MULTI SPLIT", "category": "RESIDENZIALE", "type": "MULTI_SPLIT", "pages": [621], "description": "Unità esterne multi split Aermec da 2 a 5 attacchi.", "models_prefix": ["MPG420", "MPG520", "MPG630", "MPG730", "MPG840", "MPG1040", "MPG1250", "MGE420", "MGE520", "MGE630", "MGE830"], "keywords": ["MPG", "MGE", "MPG1040", "MPG1250"]},
        {"id": "AERM_LPG_COMM", "name": "COMMERCIALE LPG (CANALIZZATA LPG D / CASSETTA LPG C / SOFFITTO LPG F)", "category": "COMMERCIALE", "type": "COMMERCIALE", "pages": [622, 623], "description": "Gamma commerciale Aermec con canalizzati LPG D, cassette 60x60 LPG C e pavimento/soffitto LPG F.", "models_prefix": ["LPG350", "LPG500", "LPG700", "LPG1000", "LPG1200", "LPG1400", "LPG1600"], "keywords": ["LPG D", "LPG C", "LPG F", "LPG1000", "LPG1200", "LPG1400", "LPG1600"]},
        {"id": "AERM_SCG", "name": "SCG COLONNA", "category": "COMMERCIALE", "type": "COLONNA", "pages": [623], "description": "Unità commerciale a colonna.", "models_prefix": ["SCG701", "SCG1201", "SCG1401"], "keywords": ["SCG", "SCG701", "SCG1201", "SCG1401"]}
    ],

    "HITACHI": [
        {"id": "HIT_AIRHOME_200", "name": "AIRHOME 200", "category": "RESIDENZIALE", "type": "PARETE", "pages": [], "description": "Climatizzatore essenziale con tecnologia FrostWash autopulente.", "models_prefix": ["RAC-CJ", "RAK-CJ"], "keywords": ["AIRHOME 200", "RAC-CJ", "RAK-CJ"]},
        {"id": "HIT_AIRHOME_400", "name": "AIRHOME 400", "category": "RESIDENZIALE", "type": "PARETE", "pages": [], "description": "Serie intelligente con FrostWash, AQtiv-Ion e Wi-Fi airCloud Home di serie.", "models_prefix": ["RAC-DJ", "RAK-DJ"], "keywords": ["AIRHOME 400", "RAC-DJ", "RAK-DJ"]},
        {"id": "HIT_AIRHOME_600", "name": "AIRHOME 600", "category": "RESIDENZIALE", "type": "PARETE", "pages": [], "description": "Filtrazione ad alta efficienza e sensore di presenza.", "models_prefix": ["RAC-VJ", "RAK-VJ"], "keywords": ["AIRHOME 600", "RAC-VJ", "RAK-VJ"]},
        {"id": "HIT_AIRHOME_800", "name": "AIRHOME 800", "category": "RESIDENZIALE", "type": "PARETE", "pages": [], "description": "Top di gamma Hitachi con design premium e massime prestazioni energetiche.", "models_prefix": ["RAC-XJ", "RAK-XJ"], "keywords": ["AIRHOME 800", "RAC-XJ", "RAK-XJ"]},
        {"id": "HIT_DODAI", "name": "DODAI 2", "category": "RESIDENZIALE", "type": "PARETE", "pages": [], "description": "Monosplit residenziale compatto R32.", "models_prefix": ["RAC-REF", "RAK-REF"], "keywords": ["DODAI", "RAC-REF", "RAK-REF"]},
        {"id": "HIT_MOKAI", "name": "MOKAI", "category": "RESIDENZIALE", "type": "PARETE", "pages": [], "description": "Serie elegante compatta ad alta efficienza A+++.", "models_prefix": ["RAC-PEF", "RAK-PEF"], "keywords": ["MOKAI", "RAC-PEF", "RAK-PEF"]},
        {"id": "HIT_TAKAI", "name": "TAKAI", "category": "RESIDENZIALE", "type": "PARETE", "pages": [], "description": "Top di gamma Takai per riscaldamento fino a -25°C.", "models_prefix": ["RAC-RXF", "RAK-RXF"], "keywords": ["TAKAI", "RAC-RXF", "RAK-RXF"]},
        {"id": "HIT_AKEBONO", "name": "AKEBONO CONSOLE", "category": "RESIDENZIALE", "type": "CONSOLE_PAVIMENTO", "pages": [], "description": "Console a pavimento con tecnologia FrostWash.", "models_prefix": ["RAC-25FXE", "RAF-"], "keywords": ["AKEBONO", "FXE", "RAF-"]},
        {"id": "HIT_MULTIZONE", "name": "MULTIZONE HITACHI", "category": "RESIDENZIALE", "type": "MULTI_SPLIT", "pages": [], "description": "Unità esterne multi split Hitachi RAM fino a 5 connessioni.", "models_prefix": ["RAM-"], "keywords": ["RAM-", "MULTIZONE"]},
        {"id": "HIT_PRIMAIRY", "name": "PRIMAIRY COMMERCIALE (CANALIZZATO / CASSETTA / SOFFITTO)", "category": "COMMERCIALE", "type": "COMMERCIALE", "pages": [], "description": "Gamma commerciale Hitachi Primairy per canalizzati RAD, cassette RCI e soffitto RPC.", "models_prefix": ["PRIMAIRY", "RCI", "RAD", "RPK", "RPC", "RAC-NPE"], "keywords": ["PRIMAIRY", "RCI", "RAD", "RPK", "RPC", "CANAL/CASS E RAC"]}
    ],

    "TCL": [
        {"id": "TCL_BREEZEIN", "name": "BREEZEIN P5", "category": "RESIDENZIALE", "type": "PARETE", "pages": [], "description": "Serie con tecnologia Gentle Breeze a microfori.", "models_prefix": ["ST09P", "ST12P", "ST18P", "ST24P"], "keywords": ["BREEZEIN", "ST09P", "ST12P", "ST18P", "ST24P"]},
        {"id": "TCL_ELITE", "name": "ELITE F2", "category": "RESIDENZIALE", "type": "PARETE", "pages": [], "description": "Serie essenziale ad alta affidabilità.", "models_prefix": ["ST09F", "ST12F", "ST18F", "ST24F"], "keywords": ["ELITE F2", "ST09F", "ST12F", "ST18F", "ST24F"]},
        {"id": "TCL_MULTI", "name": "MULTI SPLIT TCL", "category": "RESIDENZIALE", "type": "MULTI_SPLIT", "pages": [], "description": "Unità esterne multisplit TCL MT da 2 a 5 attacchi.", "models_prefix": ["MT14", "MT18", "MT27", "MT32", "MT42"], "keywords": ["MT14", "MT18", "MT27", "MT32", "MT42", "LCAC MT"]}
    ],

    "HOSHIKO": [
        {"id": "HOSH_IRIS", "name": "IRIS", "category": "RESIDENZIALE", "type": "PARETE", "pages": [], "description": "Monosplit residenziale compatto R32.", "models_prefix": ["IRIS"], "keywords": ["IRIS"]},
        {"id": "HOSH_KOVER", "name": "KOVER", "category": "RESIDENZIALE", "type": "PARETE", "pages": [], "description": "Serie a parete di design moderno.", "models_prefix": ["KOVER"], "keywords": ["KOVER"]},
        {"id": "HOSH_NINFA", "name": "NINFA", "category": "RESIDENZIALE", "type": "PARETE", "pages": [], "description": "Serie residenziale monosplit ad alta potenza.", "models_prefix": ["NINFA"], "keywords": ["NINFA"]},
        {"id": "HOSH_YOS", "name": "YOS", "category": "RESIDENZIALE", "type": "PARETE", "pages": [], "description": "Serie residenziale monosplit e multisplit.", "models_prefix": ["YOS"], "keywords": ["YOS"]}
    ],

    "ACCORRONI": [
        {"id": "ACC_TREDI", "name": "TREDI", "category": "RESIDENZIALE", "type": "PARETE", "pages": [], "description": "Monosplit e multisplit residenziale Accorroni Tredi.", "models_prefix": ["TREDI"], "keywords": ["TREDI"]}
    ],

    "KUKYR": [
        {"id": "KUK_SPRING", "name": "SPRING / SUMMER / SUN", "category": "RESIDENZIALE", "type": "PARETE", "pages": [], "description": "Monosplit a parete Kukyr.", "models_prefix": ["SPRING", "SUMMER", "SUN"], "keywords": ["SPRING", "SUMMER", "SUN"]}
    ],

    "SENZA_UNITA_ESTERNA": [
        {
            "id": "SUE_INNOVA",
            "name": "INNOVA 2.0 (MINI / 12 HP / ELEC / CEILING)",
            "category": "SENZA_UNITA_ESTERNA",
            "type": "SENZA_UNITA_ESTERNA",
            "pages": [624],
            "description": "Il climatizzatore senza unità esterna 100% metallo ultrasottile (profondità solo 16 cm), installabile sia a parete che a soffitto (Ceiling) o con resistenza elettrica integrata (Elec).",
            "models_prefix": ["2.0 MINI", "2.0 ELEC", "2.0 CEILING", "12 HP", "15 HP", "09 HP"],
            "keywords": ["INNOVA", "2.0", "CEILING", "MINI 09 HP"]
        },
        {
            "id": "SUE_KOSAMI",
            "name": "KOSAMI SENZA UNITA ESTERNA",
            "category": "SENZA_UNITA_ESTERNA",
            "type": "SENZA_UNITA_ESTERNA",
            "pages": [624],
            "description": "Monoblocco senza unità esterna da 9000, 12000 e 14000 BTU in pompa di calore.",
            "models_prefix": ["C5MO09", "C5MO12", "C5MO14"],
            "keywords": ["KOSAMI", "C5MO", "MONOBLOCCO P/C"]
        },
        {
            "id": "SUE_ARGO",
            "name": "ARGO APOLLO 12 HP",
            "category": "SENZA_UNITA_ESTERNA",
            "type": "SENZA_UNITA_ESTERNA",
            "pages": [625],
            "description": "Climatizzatore a parete monoblocco senza unità esterna con Wi-Fi di serie.",
            "models_prefix": ["APOLLO 12HP", "APOLLO"],
            "keywords": ["ARGO", "APOLLO", "APOLLO 12HP"]
        },
        {
            "id": "SUE_PANASONIC",
            "name": "PANASONIC RAC SOLO",
            "category": "SENZA_UNITA_ESTERNA",
            "type": "SENZA_UNITA_ESTERNA",
            "pages": [625],
            "description": "Monoblocco senza unità esterna ultrasottile (profondo solo 165 mm) con app Aquarea Home.",
            "models_prefix": ["RAC SOLO", "SOLO"],
            "keywords": ["RAC SOLO", "SOLO"]
        },
        {
            "id": "SUE_AERMEC_POLO",
            "name": "AERMEC POLO",
            "category": "SENZA_UNITA_ESTERNA",
            "type": "SENZA_UNITA_ESTERNA",
            "pages": [625],
            "description": "Climatizzatore monoblocco senza unità esterna in pompa di calore 10.000 BTU.",
            "models_prefix": ["POLO 10K", "POLO"],
            "keywords": ["POLO", "POLO 10K"]
        },
        {
            "id": "SUE_IDEAL_CLIMA",
            "name": "IDEAL CLIMA / AERMEC FK",
            "category": "SENZA_UNITA_ESTERNA",
            "type": "SENZA_UNITA_ESTERNA",
            "pages": [625],
            "description": "Monoblocco compatto senza unità esterna in R32 (FK260, FK360, FK261, FK361).",
            "models_prefix": ["FK260", "FK360", "FK261", "FK361"],
            "keywords": ["FK260", "FK360", "FK261", "FK361"]
        },
        {
            "id": "SUE_OLIMPIA",
            "name": "OLIMPIA SPLENDID UNICO (AIR / EASY / EDGE / EVO / PRO / TOWER / TWIN)",
            "category": "SENZA_UNITA_ESTERNA",
            "type": "SENZA_UNITA_ESTERNA",
            "pages": [626],
            "description": "La gamma di riferimento dei condizionatori senza unità esterna: Unico Air (solo 16 cm), Unico Easy (formato console), Unico Edge, Unico Evo (con resistenza elettrica modulante), Unico Pro e Unico Twin (con split per seconda stanza).",
            "models_prefix": ["UNICO AIR", "UNICO EASY", "UNICO EVO", "UNICO EDGE", "UNICO PRO", "UNICO TWIN", "UNICO TOWER"],
            "keywords": ["UNICO", "UNICO AIR", "UNICO EASY", "UNICO EVO", "UNICO EDGE", "UNICO PRO", "UNICO TWIN"]
        }
    ]
}

def main():
    total_brands = len(OFFICIAL_CATALOG_FAMILIES)
    total_families = sum(len(fams) for fams in OFFICIAL_CATALOG_FAMILIES.values())
    print(f"Salvataggio tassonomia ufficiale catalogo 2026: {total_brands} marchi, {total_families} famiglie/serie censite.")
    with open('Knowledge/catalog_official_families_2026.json', 'w', encoding='utf-8') as f:
        json.dump(OFFICIAL_CATALOG_FAMILIES, f, indent=2, ensure_ascii=False)
    print("Aggiornato con successo Knowledge/catalog_official_families_2026.json")

if __name__ == '__main__':
    main()
