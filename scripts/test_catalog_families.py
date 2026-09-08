import json
import sys
from collections import Counter, defaultdict

sys.stdout.reconfigure(encoding='utf-8')

CATALOG_FAMILIES_DEF = {
    "DAIKIN": [
        {"name": "PERFERA ALL SEASONS", "type": "PARETE", "pages": [468, 476, 478], "keys": ["PERFERA", "FTXM", "RXM"]},
        {"name": "SIESTA GSI", "type": "PARETE", "pages": [468], "keys": ["SIESTA", "ATXF", "ARXF", "GSI"]},
        {"name": "STYLISH", "type": "PARETE", "pages": [469], "keys": ["STYLISH", "FTXA", "RXA"]},
        {"name": "EMURA", "type": "PARETE", "pages": [469], "keys": ["EMURA", "FTXJ", "RXJ"]},
        {"name": "SENSIRA", "type": "PARETE", "pages": [470], "keys": ["SENSIRA", "FTXF", "RXF", "CTXF"]},
        {"name": "COMFORA", "type": "PARETE", "pages": [470], "keys": ["COMFORA", "FTXP", "RXP"]},
        {"name": "MULTI MXF", "type": "MULTI_SPLIT", "pages": [470], "keys": ["MXF", "2MXF", "3MXF"]},
        {"name": "MULTI SPLIT MXM", "type": "MULTI_SPLIT", "pages": [471], "keys": ["MXM", "2MXM", "3MXM", "4MXM", "5MXM"]},
        {"name": "MULTI+ ACS / DHW", "type": "MULTI_SPLIT", "pages": [471, 475], "keys": ["MULTI+", "DHW", "MWXM", "4MWXM", "5MWXM"]},
        {"name": "CANALIZZATA ULTRAPIATTA FDXM", "type": "CANALIZZATO", "pages": [472], "keys": ["FDXM"]},
        {"name": "PENSILE A SOFFITTO FHA", "type": "PENSILE_SOFFITTO", "pages": [472, 482], "keys": ["FHA"]},
        {"name": "CASSETTA ROUND FLOW FCAG 90x90", "type": "CASSETTA_90X90", "pages": [473, 477, 479, 481, 484, 487], "keys": ["FCAG", "ROUND FLOW"]},
        {"name": "ROUND FLOW SUPERCASSETTE FCAHG", "type": "CASSETTA_90X90", "pages": [488], "keys": ["FCAHG", "SUPERCASSETTE"]},
        {"name": "CASSETTA 4 VIE FFA 60x60", "type": "CASSETTA_60X60", "pages": [477, 479], "keys": ["FFA"]},
        {"name": "PAVIMENTO DA INCASSO FNA", "type": "CONSOLE_PAVIMENTO", "pages": [476], "keys": ["FNA"]},
        {"name": "CANALIZZATA DC FBA (MEDIA PREVALENZA)", "type": "CANALIZZATO", "pages": [476, 478, 480, 483, 487], "keys": ["FBA"]},
        {"name": "CANALIZZATA FDA (ALTA PREVALENZA)", "type": "CANALIZZATO", "pages": [483, 486], "keys": ["FDA"]},
        {"name": "PARETE COMMERCIALE FAA", "type": "PARETE", "pages": [480, 482], "keys": ["FAA"]},
        {"name": "CASSETTA PENSILE A SOFFITTO FUA", "type": "CASSETTA_90X90", "pages": [484, 488], "keys": ["FUA"]},
        {"name": "COLONNA COMMERCIALE FVA", "type": "COLONNA", "pages": [485], "keys": ["FVA"]},
        {"name": "SKY AIR ALPHA", "type": "COMMERCIALE_UE", "pages": [478, 486], "keys": ["RZAG", "RZA", "ALPHA"]},
        {"name": "SKY AIR ADVANCE", "type": "COMMERCIALE_UE", "pages": [482, 483, 485, 486], "keys": ["RZASG", "ADVANCE"]},
        {"name": "SKY AIR ACTIVE", "type": "COMMERCIALE_UE", "pages": [480, 481], "keys": ["AZAS", "ACTIVE"]}
    ],
    "MITSUBISHI": [
        {"name": "MSZ-HR SMART", "type": "PARETE", "pages": [490], "keys": ["MSZ-HR", "HR25", "HR35", "HR42", "HR50", "MUZ-HR"]},
        {"name": "MSZ-AP / MSZ-AP LARGE", "type": "PARETE", "pages": [490, 496], "keys": ["MSZ-AP", "AP LARGE", "AP15", "AP20", "AP25", "AP35", "AP42", "AP50", "AP60", "AP71", "MUZ-AP"]},
        {"name": "MSZ-AY GENERATION", "type": "PARETE", "pages": [496], "keys": ["MSZ-AY", "AY15", "AY20", "AY25", "AY35", "AY42", "AY50", "MUZ-AY"]},
        {"name": "MSZ-LN KIRIGAMINE STYLE", "type": "PARETE", "pages": [491, 496], "keys": ["MSZ-LN", "KIRIGAMINE STYLE", "LN25", "LN35", "LN50", "LN60", "MUZ-LN"]},
        {"name": "MSZ-EF KIRIGAMINE ZEN", "type": "PARETE", "pages": [496], "keys": ["MSZ-EF", "KIRIGAMINE ZEN", "EF18", "EF22", "EF25", "EF35", "EF42", "EF50", "MUZ-EF"]},
        {"name": "MSZ-BT ENTRY WI-FI", "type": "PARETE", "pages": [496], "keys": ["MSZ-BT", "BT20", "BT25", "BT35", "BT50", "MUZ-BT"]},
        {"name": "SEZ-M DA2 CANALIZZATA (BASSA PREVALENZA)", "type": "CANALIZZATO", "pages": [491, 497, 503], "keys": ["SEZ-M", "SEZ-M25", "SEZ-M35", "SEZ-M50", "SEZ-M60", "SEZ-M71"]},
        {"name": "SLZ-M FA2 CASSETTA 60x60", "type": "CASSETTA_60X60", "pages": [492, 503, 507], "keys": ["SLZ-M", "SLZ-M25", "SLZ-M35", "SLZ-M50", "SLZ-M60"]},
        {"name": "MFZ-KT VGK PAVIMENTO", "type": "CONSOLE_PAVIMENTO", "pages": [492], "keys": ["MFZ-KT", "MFZ-KT25", "MFZ-KT35", "MFZ-KT50", "MFZ-KT60"]},
        {"name": "MLZ-KP / MLZ-KY CASSETTA 1 VIA", "type": "CASSETTA_1VIA", "pages": [497], "keys": ["MLZ-KP", "MLZ-KY", "MLZ-KP25", "MLZ-KP35", "MLZ-KP50"]},
        {"name": "MXZ-HA MULTI SMART", "type": "MULTI_SPLIT", "pages": [493], "keys": ["MXZ-HA", "MXZ-2HA", "MXZ-3HA"]},
        {"name": "MXZ-VF / MXZ-F MULTI INVERTER", "type": "MULTI_SPLIT", "pages": [494, 498], "keys": ["MXZ-2F", "MXZ-3F", "MXZ-4F", "MXZ-5F", "MXZ-6F", "MXZ-2D", "MXZ-3D", "MXZ-4E", "MXZ-5E", "MXZ-F", "MXZ-VF", "MXZ-2F53VFHZ"]},
        {"name": "SMALL Y PUMY-SP MINI VRF", "type": "MULTI_SPLIT", "pages": [495], "keys": ["PUMY-SP", "PUMY"]},
        {"name": "PKA-M LAL/KAL PARETE COMMERCIALE", "type": "PARETE", "pages": [499, 502, 507], "keys": ["PKA-M", "PKA-M35", "PKA-M50", "PKA-M60", "PKA-M71", "PKA-M100"]},
        {"name": "PEAD-M JA2 CANALIZZATA (MEDIA-ALTA PREVALENZA)", "type": "CANALIZZATO", "pages": [499, 502], "keys": ["PEAD-M", "PEAD-M35", "PEAD-M50", "PEAD-M60", "PEAD-M71", "PEAD-M100", "PEAD-M125", "PEAD-M140"]},
        {"name": "PEA-M LA CANALIZZATA (ALTA PREVALENZA)", "type": "CANALIZZATO", "pages": [500], "keys": ["PEA-M", "PEA-M200", "PEA-M250"]},
        {"name": "PLA-M EA2 CASSETTA 90x90", "type": "CASSETTA_90X90", "pages": [500, 504, 508], "keys": ["PLA-M", "PLA-M35", "PLA-M50", "PLA-M60", "PLA-M71", "PLA-M100", "PLA-M125", "PLA-M140"]},
        {"name": "PCA-M KA2 / HA2 PENSILE SOFFITTO", "type": "PENSILE_SOFFITTO", "pages": [501, 504, 505, 508], "keys": ["PCA-M", "PCA-M50", "PCA-M60", "PCA-M71", "PCA-M100", "PCA-M125", "PCA-M140"]},
        {"name": "PSA-M COLONNA MR SLIM", "type": "COLONNA", "pages": [501, 505], "keys": ["PSA-M", "PSA-M71", "PSA-M100", "PSA-M125", "PSA-M140"]},
        {"name": "POWER INVERTER PUZ-ZM", "type": "COMMERCIALE_UE", "pages": [502, 503, 505, 506], "keys": ["PUZ-ZM", "POWER INVERTER"]},
        {"name": "STANDARD INVERTER PUZ-M / SUZ-M", "type": "COMMERCIALE_UE", "pages": [499, 501, 506], "keys": ["PUZ-M", "SUZ-M", "STANDARD INVERTER"]}
    ],
    "PANASONIC": [
        {"name": "BZ COMPATTO", "type": "PARETE", "pages": [510], "keys": ["BZ", "CS-BZ", "CU-BZ"]},
        {"name": "TZ SUPER COMPATTO", "type": "PARETE", "pages": [510], "keys": ["TZ", "CS-TZ", "CU-TZ"]},
        {"name": "ETHEREA", "type": "PARETE", "pages": [511], "keys": ["ETHEREA", "CS-Z", "CS-XZ", "CU-Z"]},
        {"name": "YKEA PARETE ALTA EFFICIENZA", "type": "PARETE", "pages": [511], "keys": ["YKEA", "CS-E", "CU-E"]},
        {"name": "CONSOLE DA PAVIMENTO", "type": "CONSOLE_PAVIMENTO", "pages": [512], "keys": ["CONSOLE", "CS-Z25UFEAW", "CS-Z35UFEAW", "CS-Z50UFEAW", "CS-Z25CFEAW", "UBEA", "CBEA"]},
        {"name": "MULTI Z", "type": "MULTI_SPLIT", "pages": [513], "keys": ["MULTI Z", "CU-2Z", "CU-3Z", "CU-4Z", "CU-5Z"]},
        {"name": "CANALIZZATA RESIDENZIALE", "type": "CANALIZZATO", "pages": [514], "keys": ["CS-MZ20UD3EA", "CS-Z25UD3EA", "CS-Z35UD3EA", "CS-Z50UD3EA", "CS-Z60UD3EA", "UD3EA", "CD3EA", "MZ20CD3EA"]},
        {"name": "CASSETTA 60x60 RESIDENZIALE", "type": "CASSETTA_60X60", "pages": [514], "keys": ["CS-MZ20UB4EA", "CS-Z25UB4EA", "CS-Z35UB4EA", "CS-Z50UB4EA", "CS-Z60UB4EA", "UB4EA"]},
        {"name": "PACI NX STANDARD", "type": "COMMERCIALE", "pages": [515, 516, 517], "keys": ["PACI NX STANDARD", "PACI", "U-100PZ", "U-125PZ", "U-140PZ", "U-36PZ", "U-50PZ", "U-60PZ", "U-71PZ", "PZ3E5", "PF3E", "PU3E", "PT3E", "PK3E"]},
        {"name": "PACI NX ELITE", "type": "COMMERCIALE", "pages": [518, 519, 520], "keys": ["PACI NX ELITE", "U-100PZH", "U-125PZH", "U-140PZH", "U-36PZH", "U-50PZH", "U-60PZH", "U-71PZH", "PZH4E5", "PZH4E8"]},
        {"name": "BIG PACI ALTA PREVALENZA", "type": "CANALIZZATO", "pages": [521], "keys": ["BIG PACI", "U-200PZH", "U-250PZH", "S-200PE", "S-250PE"]}
    ],
    "TOSHIBA": [
        {"name": "SEIYA CLASSIC / SEIYA", "type": "PARETE", "pages": [523], "keys": ["SEIYA", "RAS-B10B2KVG", "RAS-B13B2KVG", "RAS-B16B2KVG", "RAS-B07E2KVG", "RAS-B10E2KVG", "RAS-B13E2KVG"]},
        {"name": "SHORAI EDGE", "type": "PARETE", "pages": [523], "keys": ["SHORAI", "SHORAI EDGE", "RAS-B10G3KVSG", "RAS-B13G3KVSG", "RAS-B16G3KVSG", "RAS-B22G3KVSG", "RAS-B24G3KVSG"]},
        {"name": "DAISEIKAI 10", "type": "PARETE", "pages": [524], "keys": ["DAISEIKAI", "RAS-B10S4KVPG", "RAS-B13S4KVPG", "RAS-B16S4KVPG", "RAS-10S4AVPG", "RAS-13S4AVPG", "RAS-16S4AVPG", "RAS-18S4AVPG"]},
        {"name": "HAORI", "type": "PARETE", "pages": [524], "keys": ["HAORI", "RAS-B10N4KVRG", "RAS-B13N4KVRG", "RAS-B16N4KVRG", "RAS10J2AVSGE1", "RAS13J2AVSGE1", "RAS16J2AVSGE1"]},
        {"name": "CONSOLE", "type": "CONSOLE_PAVIMENTO", "pages": [524], "keys": ["CONSOLE", "RAS-B10J2FVG", "RAS-B13J2FVG", "RAS-B18J2FVG"]},
        {"name": "MULTI SPLIT RAS-M", "type": "MULTI_SPLIT", "pages": [525], "keys": ["RAS-2M", "RAS-3M", "RAS-4M", "RAS-5M", "2M10", "2M14", "2M18", "3M26", "4M27", "5M34"]},
        {"name": "CANALIZZATA RIBASSATA / ULTRAPIATTA", "type": "CANALIZZATO", "pages": [527, 528], "keys": ["RAS-M07U2DVG", "RAS-M10U2DVG", "RAS-M13U2DVG", "RAS-M16U2DVG", "RASM07U2DVGE", "RASM10U2DVGE", "RASM13U2DVGE", "RASM16U2DVGE", "RAV-HM301SDTY", "RAV-HM401SDTY", "RAV-HM561SDTY"]},
        {"name": "CASSETTA 4 VIE 60x60", "type": "CASSETTA_60X60", "pages": [527, 528, 529], "keys": ["RAS-M10U2MUVG", "RAS-M13U2MUVG", "RAV-HM301MUT", "RAV-HM401MUT", "RAV-HM561MUT", "RAVHM301MUTP", "RAVHM401MUTP", "RAVHM561MUTP"]},
        {"name": "PARETE COMMERCIALE RAV", "type": "PARETE", "pages": [530, 533, 535], "keys": ["RAV-HM301KRTP", "RAV-HM401KRTP", "RAV-HM561KRTP", "RAV-HM801KRTP"]},
        {"name": "CANALIZZATA STANDARD RAV", "type": "CANALIZZATO", "pages": [530, 533, 535], "keys": ["RAV-HM561BTP", "RAV-HM801BTP", "RAV-HM1101BTP", "RAV-HM1401BTP", "RAV-HM1601BTP", "RAVRM2241", "RAVRM2801", "RAV-RM"]},
        {"name": "SOFFITTO RAV", "type": "PENSILE_SOFFITTO", "pages": [531, 536], "keys": ["RAV-HM401CTP", "RAV-HM561CTP", "RAV-HM801CTP", "RAV-HM1101CTP", "RAV-HM1401CTP", "RAV-HM1601CTP"]},
        {"name": "CASSETTA 90x90 STANDARD / SMART RAV", "type": "CASSETTA_90X90", "pages": [531, 534, 537], "keys": ["RAV-HM561UTP", "RAV-HM801UTP", "RAV-HM1101UTP", "RAV-HM1401UTP", "RAV-HM1601UTP", "RAVHM1101UTE", "RAVHM1401UTE"]},
        {"name": "COLONNA RAV", "type": "COLONNA", "pages": [532, 538], "keys": ["RAV-HM561FT", "RAV-HM801FT", "RAV-HM1101FT", "RAV-HM1401FT", "RAV-HM1601FT", "RAVHM1101FTE", "RAVHM1401FTE", "RAVHM1601FTE"]},
        {"name": "DIGITAL INVERTER RAV-GM", "type": "COMMERCIALE_UE", "pages": [528, 529, 530, 531, 532], "keys": ["RAV-GM", "DIGITAL INVERTER", "RAV-GM301", "RAV-GM401", "RAV-GM561", "RAV-GM801", "RAV-GM1101", "RAV-GM1401"]},
        {"name": "DIGITAL CLASSIC RAV-GV", "type": "COMMERCIALE_UE", "pages": [533, 534], "keys": ["RAV-GV", "DIGITAL CLASSIC", "RAVGV1101", "RAV-GV1101", "RAVGV1401", "RAV-GV1401"]},
        {"name": "SUPER DIGITAL INVERTER RAV-GP", "type": "COMMERCIALE_UE", "pages": [535, 536, 537, 538], "keys": ["RAV-GP", "SUPER DIGITAL", "RAV-GP1101", "RAV-GP1401", "RAV-GP1601"]},
        {"name": "BIG DIGITAL INVERTER", "type": "COMMERCIALE_UE", "pages": [530], "keys": ["RAV-GM224", "RAV-GM280", "BIG DIGITAL"]}
    ],
    "MIDEA": [
        {"name": "XTREME PRO WI-FI", "type": "PARETE", "pages": [539], "keys": ["XTREME PRO", "MSAGAU", "AGAU"]},
        {"name": "FLEXI / BREEZELESS", "type": "PARETE", "pages": [539], "keys": ["FLEXI", "BREEZELESS", "MSAGBU", "MSFAAU"]},
        {"name": "ALYA", "type": "PARETE", "pages": [539], "keys": ["ALYA", "ALYA 9", "ALYA 12", "ALYA 18", "ALYA 24"]},
        {"name": "MULTI SPLIT MIDEA", "type": "MULTI_SPLIT", "pages": [540, 542, 543, 544, 545], "keys": ["M2OH", "M2OE", "M3OE", "M4OE", "M5OE"]},
        {"name": "CANALIZZATA MIDEA", "type": "CANALIZZATO", "pages": [541, 546], "keys": ["CANALIZZAT", "MTI", "MTIU"]},
        {"name": "CONSOLE MIDEA", "type": "CONSOLE_PAVIMENTO", "pages": [541, 547], "keys": ["CONSOLE", "MFA", "MFAU"]},
        {"name": "CASSETTA COMPATTA 60x60", "type": "CASSETTA_60X60", "pages": [541], "keys": ["MCA4", "MCA4U"]},
        {"name": "CASSETTA SUPER SLIM 90x90", "type": "CASSETTA_90X90", "pages": [546], "keys": ["MCD", "MCDU"]},
        {"name": "PAVIMENTO / SOFFITTO MIDEA", "type": "PENSILE_SOFFITTO", "pages": [547], "keys": ["MUE", "MUEU"]},
        {"name": "COLONNA MIDEA", "type": "COLONNA", "pages": [547], "keys": ["MFM", "MFMU"]},
        {"name": "COMMERCIALE MDV / VRF", "type": "COMMERCIALE_UE", "pages": [], "keys": ["MDV", "MDV-V"]}
    ],
    "HISENSE": [
        {"name": "EASY SMART", "type": "PARETE", "pages": [548], "keys": ["EASY SMART", "CA25YR", "CA35YR", "CA50XS", "CA70BT"]},
        {"name": "ENERGY PRO X / PLUS", "type": "PARETE", "pages": [548], "keys": ["ENERGY PRO", "ENERGY PRO X", "QE25XV", "QE35XV", "QE50XV"]},
        {"name": "HI-COMFORT", "type": "PARETE", "pages": [548], "keys": ["HI COMFORT", "HI-COMFORT", "AS25YR4BW", "AS35MR0BW", "AS50XS1GW", "AS70BT2BW"]},
        {"name": "AIR MASTER / SILENTIUM PRO", "type": "PARETE", "pages": [548, 550], "keys": ["AIR MASTER", "SILENTIUM", "AS25WM", "AS35WM"]},
        {"name": "UNI HB COMMERCIALE", "type": "COMMERCIALE_UE", "pages": [548], "keys": ["UNI HB", "AS25XU", "AS35XU", "AS50XU"]},
        {"name": "MULTI INVERTER HISENSE", "type": "MULTI_SPLIT", "pages": [549, 550], "keys": ["2AMW", "3AMW", "4AMW", "5AMW"]},
        {"name": "CANALIZZATA HISENSE", "type": "CANALIZZATO", "pages": [551], "keys": ["CANALIZZAT", "ADT"]},
        {"name": "CASSETTA ROUND-FLOW 90x90 & 60x60", "type": "CASSETTA_90X90", "pages": [551], "keys": ["CASSETTA", "ACT", "ROUND-FLOW"]},
        {"name": "CONSOLE HISENSE", "type": "CONSOLE_PAVIMENTO", "pages": [551], "keys": ["CONSOLE", "AKT"]},
        {"name": "SOFFITTO-PAVIMENTO HISENSE", "type": "PENSILE_SOFFITTO", "pages": [552], "keys": ["SOFFITTO-PAVIMENTO", "AVT"]},
        {"name": "COLONNA HISENSE", "type": "COLONNA", "pages": [552], "keys": ["COLONNA", "AUF", "AUW"]}
    ],
    "KOSAMI": [
        {"name": "PEONY", "type": "PARETE", "pages": [553], "keys": ["PEONY"]},
        {"name": "BORA BIANCO OPACO", "type": "PARETE", "pages": [553], "keys": ["BORA"]},
        {"name": "VENUS", "type": "PARETE", "pages": [554], "keys": ["VENUS"]},
        {"name": "MULTI SPLIT PAROS", "type": "MULTI_SPLIT", "pages": [554], "keys": ["PAROS"]},
        {"name": "COMMERCIALE CANALIZZATO / CASSETTA / CONSOLE", "type": "COMMERCIALE", "pages": [555], "keys": ["CAN-CASS", "COMM CAN"]},
        {"name": "SENZA UNITA ESTERNA KOSAMI", "type": "SENZA_UNITA_ESTERNA", "pages": [624], "keys": ["MONOBLOCCO"]}
    ],
    "HAIER": [
        {"name": "TIDE R / TIDE GREEN", "type": "PARETE", "pages": [556], "keys": ["TIDE", "HEC", "HEC25", "HEC35", "HEC50"]},
        {"name": "GEOS PLUS+", "type": "PARETE", "pages": [557], "keys": ["GEOS", "GEOS PLUS", "AS25TADHRA", "AS35TADHRA", "AS50TDDHRA"]},
        {"name": "FLEXIS PLUS", "type": "PARETE", "pages": [557], "keys": ["FLEXIS", "FLEXIS PLUS", "AS25S2SF1FA", "AS35S2SF1FA", "AS50S2SF1FA", "AS71S2SF1FA"]},
        {"name": "EXPERT", "type": "PARETE", "pages": [564, 565], "keys": ["EXPERT", "AS20XCAHRA", "AS25XCAHRA", "AS35XCAHRA", "AS50XCAHRA", "AS71XCAHRA"]},
        {"name": "PEARL", "type": "PARETE", "pages": [557], "keys": ["PEARL", "AS20PBAHRA", "AS25PBAHRA", "AS35PBAHRA", "AS50PBAHRA", "AS71PBAHRA"]},
        {"name": "REVIVE", "type": "PARETE", "pages": [561], "keys": ["REVIVE", "AS25RHBHRA", "AS35RHBHRA", "AS50RHBHRA", "AS68RHBHRA"]},
        {"name": "MONOSPLIT UE 1U SUPER MATCH", "type": "COMMERCIALE_UE", "pages": [557, 558, 560, 565, 569], "keys": ["1U25", "1U35", "1U42", "1U50", "1U71", "1U105", "1U125", "1U140", "1UH200"]},
        {"name": "MULTI SPLIT HAIER (2U/3U/4U/5U)", "type": "MULTI_SPLIT", "pages": [561, 562, 564], "keys": ["2U40", "2U50", "3U55", "3U70", "4U75", "4U85", "5U90", "5U105", "5U125"]},
        {"name": "CANALIZZATA SLIM BP 30 Pa", "type": "CANALIZZATO", "pages": [558], "keys": ["SLIM BP", "AD25S2SS1FA", "AD35S2SS1FA", "AD50S2SS1FA", "AD71S2SS1FA"]},
        {"name": "CANALIZZATA MP 150 Pa", "type": "CANALIZZATO", "pages": [558, 565], "keys": ["CANALIZZATA MP", "AD50S2SM1FA", "AD71S2SM1FA", "AD105S2SM1FA", "AD125S2SM1FA", "AD140S2SM1FA"]},
        {"name": "CANALIZZATA ALTA PREVALENZA", "type": "CANALIZZATO", "pages": [566], "keys": ["CANALIZZ A/P", "ADH125", "ADH140", "ADH160"]},
        {"name": "CASSETTA A 1 VIA HAIER", "type": "CASSETTA_1VIA", "pages": [559, 567], "keys": ["CASSETTA A 1 VIA", "AB25S2SC1FA", "AB35S2SC1FA"]},
        {"name": "CASSETTA 620 62x62", "type": "CASSETTA_60X60", "pages": [563], "keys": ["CASSETTA 620", "AB25S2SC2FA", "AB35S2SC2FA", "AB50S2SC2FA", "AB60S2SC2FA"]},
        {"name": "CASSETTA ROUND FLOW 90x90", "type": "CASSETTA_90X90", "pages": [566, 567], "keys": ["CASSETTA ROUND FLOW", "AB71S2SR1FA", "AB105S2SR1FA", "AB125S2SR1FA", "AB140S2SR1FA"]},
        {"name": "CONSOLE HAIER", "type": "CONSOLE_PAVIMENTO", "pages": [559, 563], "keys": ["CONSOLE", "AF25S2SD1FA", "AF35S2SD1FA", "AF50S2SD1FA"]},
        {"name": "SOFFITTO / PAVIMENTO HAIER", "type": "PENSILE_SOFFITTO", "pages": [560, 568], "keys": ["SOFFITTO PAVIMENTO", "AC50S2SG1FA", "AC71S2SG1FA", "AC105S2SG1FA", "AC125S2SG1FA", "AC140S2SG1FA"]},
        {"name": "COLONNA DI ZUN / CABINET", "type": "COLONNA", "pages": [560, 568, 569], "keys": ["COLONNA", "ZUN", "AP71DFMHRA", "AP105S2SK1FA", "AP140S2SK1FA", "AP105S2SE1FA"]}
    ],
    "SAMSUNG": [
        {"name": "AR35", "type": "PARETE", "pages": [571], "keys": ["AR35", "AR09TXHQASI", "AR12TXHQASI", "AR18TXHQASI", "AR24TXHQASI"]},
        {"name": "WINDFREE PREMIÈRE+", "type": "PARETE", "pages": [572, 575], "keys": ["WINDFREE PREMIERE", "PREMIERE+", "AR70H09", "AR70H12", "AR70H18", "AR70H24"]},
        {"name": "WINDFREE ELITE / BLACK", "type": "PARETE", "pages": [571, 575], "keys": ["WINDFREE ELITE", "WINDFREE BLACK", "AR09TXCAAWK", "AR12TXCAAWK"]},
        {"name": "WINDFREE AVANT", "type": "PARETE", "pages": [575], "keys": ["WINDFREE AVANT", "AR09TXEAAWK", "AR12TXEAAWK", "AR18TXEAAWK", "AR24TXEAAWK"]},
        {"name": "WINDFREE COMFORT", "type": "PARETE", "pages": [575], "keys": ["WINDFREE COMFORT", "AR09TXFCAWK", "AR12TXFCAWK", "AR18TXFCAWK", "AR24TXFCAWK"]},
        {"name": "CEBU WI-FI", "type": "PARETE", "pages": [575], "keys": ["CEBU", "AR09TXFYAWK", "AR12TXFYAWK", "AR18TXFYAWK", "AR24TXFYAWK"]},
        {"name": "MULTI SPLIT FJM", "type": "MULTI_SPLIT", "pages": [573, 575], "keys": ["AJ040", "AJ050", "AJ068", "AJ080", "AJ100", "FJM"]},
        {"name": "COMMERCIALE CAC INVERTER AC", "type": "COMMERCIALE_UE", "pages": [576, 577, 578, 579, 580], "keys": ["AC026RXADKG", "AC035RXADKG", "AC052RXADKG", "AC071RXADKG", "AC052BXAPKG", "AC071BXAPKG", "AC100", "AC120", "AC140", "AC200", "AC250", "UE COMM AC"]},
        {"name": "PARETE WINDFREE DELUXE COMMERCIALE", "type": "PARETE", "pages": [576], "keys": ["WINDFREE DELUXE", "AC026RNNDKG", "AC035RNNDKG"]},
        {"name": "CANALIZZATA BASSA PREVALENZA (LSP)", "type": "CANALIZZATO", "pages": [574, 576], "keys": ["CANALIZZATA", "LSP", "AC026MNLDKG", "AC035MNLDKG"]},
        {"name": "CANALIZZATA MEDIA PREVALENZA (MSP)", "type": "CANALIZZATO", "pages": [577], "keys": ["CANALIZZATA", "MSP", "AC052MNMDKG", "AC071MNMDKG", "AC100MNMDKG", "AC120MNMDKG", "AC140MNMDKG"]},
        {"name": "MINI CASSETTA 4 VIE WINDFREE 60x60", "type": "CASSETTA_60X60", "pages": [574, 577], "keys": ["CASSETTA 4 VIE MINI", "CASSETTA 60X60", "AC026RNNDKG", "AC035RNNDKG", "AC052RNNDKG", "AC060RNNDKG"]},
        {"name": "CASSETTA 4 VIE WINDFREE 90x90", "type": "CASSETTA_90X90", "pages": [578], "keys": ["CASSETTA 4 VIE WINDFREE 90", "AC071RN4DKG", "AC100RN4DKG", "AC120RN4DKG", "AC140RN4DKG"]},
        {"name": "CASSETTA 360° CIRCOLARE", "type": "CASSETTA_90X90", "pages": [578], "keys": ["CASSETTA 360", "AC071RN4PKG", "AC100RN4PKG", "AC120RN4PKG", "AC140RN4PKG"]},
        {"name": "CASSETTA 1 VIA SLIM WINDFREE", "type": "CASSETTA_1VIA", "pages": [579], "keys": ["CASSETTA 1 VIA", "AC026RN1DKG", "AC035RN1DKG"]},
        {"name": "SOFFITTO / PAVIMENTO SAMSUNG", "type": "PENSILE_SOFFITTO", "pages": [579], "keys": ["SOFFITTO/PAVIMENTO", "AC052RNCDKG", "AC071RNCDKG", "AC100RNCDKG"]},
        {"name": "COLONNA SAMSUNG", "type": "COLONNA", "pages": [580], "keys": ["COLONNA", "AC100BNPDKH", "AC140BNPDKH"]}
    ],
    "LG": [
        {"name": "LIBERO", "type": "PARETE", "pages": [582], "keys": ["LIBERO", "W09TI", "W12TI", "W18TI", "W24TI"]},
        {"name": "DUALCOOL LIBERO SMART", "type": "PARETE", "pages": [582, 585], "keys": ["LIBERO SMART", "S09ET", "S12ET", "S18ET", "S24ET"]},
        {"name": "DUALCOOL DELUXE", "type": "PARETE", "pages": [582], "keys": ["DUALCOOL DELUXE", "H09S1DA", "H12S1DA", "H18S1DA", "H24S1DA"]},
        {"name": "DUALCOOL PREMIUM AL AIR", "type": "PARETE", "pages": [583], "keys": ["DUALCOOL PREMIUM", "H09S1PA", "H12S1PA"]},
        {"name": "ARTCOOL GALLERY PHOTO / LCD", "type": "PARETE", "pages": [583, 585], "keys": ["ARTCOOL GALLERY", "A09GA2", "A12GA2"]},
        {"name": "ARTCOOL MIRROR / BLACK", "type": "PARETE", "pages": [582, 583], "keys": ["ARTCOOL MIRROR", "AC09BQ", "AC12BQ", "AC18BQ", "AC24BQ", "ARTCOOL BLACK", "AA09SB", "AA12SB"]},
        {"name": "MULTI SPLIT LG R32", "type": "MULTI_SPLIT", "pages": [584], "keys": ["MU2R", "MU3R", "MU4R", "MU5R"]},
        {"name": "CASSETTA 4 VIE 57x57 (60x60)", "type": "CASSETTA_60X60", "pages": [586, 588, 590], "keys": ["CASSETTA 57X57", "CASSETTA 60X60", "CT09F", "CT12F", "CT18F", "CT24F"]},
        {"name": "CASSETTA 4 VIE 84x84 (90x90)", "type": "CASSETTA_90X90", "pages": [586, 588, 590], "keys": ["CASSETTA 84X84", "UT30F", "UT36F", "UT42F", "UT48F", "UT60F"]},
        {"name": "ROUND CASSETTE STANDARD 360°", "type": "CASSETTA_90X90", "pages": [591], "keys": ["ROUND CASSETTE", "UT36F.NY0", "UT48F.NY0", "UT60F.NY0"]},
        {"name": "CANALIZZATA BASSA PREVALENZA LG", "type": "CANALIZZATO", "pages": [587, 589], "keys": ["CANALIZZATA", "CL09F", "CL12F", "CL18F", "CL24F"]},
        {"name": "CANALIZZATA ALTA PREVALENZA LG", "type": "CANALIZZATO", "pages": [591, 592], "keys": ["CANALIZZATA A/P", "UM12FH", "UM18FH", "UM24FH", "UM30FH", "UM36FH", "UM42FH", "UM48FH", "UB200", "UB250"]},
        {"name": "SOFFITTO / PAVIMENTO LG", "type": "PENSILE_SOFFITTO", "pages": [588, 590], "keys": ["SOFFITTO", "UV18F", "UV24F", "UV30F", "UV36F", "UV42F", "UV48F", "UV60F"]},
        {"name": "COMMERCIALE UNIVERSAL INVERTER", "type": "COMMERCIALE_UE", "pages": [587, 588, 589, 590, 591, 592], "keys": ["UUA1", "UUB1", "UUC1", "UUD1", "UUD3", "UU48W", "UU49W", "UU200", "UU250"]}
    ],
    "FERROLI": [
        {"name": "GIADA", "type": "PARETE", "pages": [594], "keys": ["GIADA", "GIADA 9", "GIADA 12", "GIADA 18", "GIADA 24"]},
        {"name": "GIADA MULTI SPLIT", "type": "MULTI_SPLIT", "pages": [594], "keys": ["GIADA MULTI", "GIADA 14-2", "GIADA 18-2", "GIADA 21-3", "GIADA 27-4", "GIADA 36-4"]},
        {"name": "GIADA-C DUCT (CANALIZZATA)", "type": "CANALIZZATO", "pages": [595], "keys": ["GIADA-C DUCT", "DUCT"]},
        {"name": "GIADA-C CASSETTA 90X90", "type": "CASSETTA_90X90", "pages": [595], "keys": ["GIADA-C CASSETTA", "CASSETTA 90X90"]},
        {"name": "AMBRA", "type": "PARETE", "pages": [594], "keys": ["AMBRA"]}
    ],
    "BAXI": [
        {"name": "ASTRA", "type": "PARETE", "pages": [596], "keys": ["ASTRA", "LSGT25-S", "LSGT35-S", "LSGT50-S", "LSGT70-S", "JSGNW25", "JSGNW35", "JSGNW50", "JSGNW70"]},
        {"name": "SIDERA", "type": "PARETE", "pages": [596], "keys": ["SIDERA"]},
        {"name": "MULTI SPLIT BAXI", "type": "MULTI_SPLIT", "pages": [597, 598], "keys": ["LSGT40-2M", "LSGT50-2M", "LSGT60-3M", "LSGT70-3M", "LSGT80-4M", "LSGT100-4M", "LSGT120-5M"]},
        {"name": "LIGHT COMMERCIAL CANALIZZATA", "type": "CANALIZZATO", "pages": [597, 599], "keys": ["RZ2GT", "RZGT", "RZ2GND", "LIGHTCOMM CANALIZZ"]},
        {"name": "LIGHT COMMERCIAL CASSETTA 60x60 / 90x90", "type": "CASSETTA_60X60", "pages": [597, 599], "keys": ["RZGBK", "LSGBK", "LIGHTCOMM CASS"]},
        {"name": "LIGHT COMMERCIAL CONSOLE", "type": "CONSOLE_PAVIMENTO", "pages": [599], "keys": ["CONSOLE"]}
    ],
    "ARISTON": [
        {"name": "KIOS NET", "type": "PARETE", "pages": [600], "keys": ["KIOS", "KIOS NET"]},
        {"name": "NEVIS EVO", "type": "PARETE", "pages": [600], "keys": ["NEVIS", "NEVIS EVO"]},
        {"name": "ALYS", "type": "PARETE", "pages": [600], "keys": ["ALYS", "ALYS 25", "ALYS 35", "ALYS 50"]},
        {"name": "MULTI SPLIT DUAL / TRIAL / QUAD / PENTA", "type": "MULTI_SPLIT", "pages": [601, 602], "keys": ["DUAL C", "TRIAL C", "QUAD C", "PENTA C", "C 40 XD0", "C 50 XD0", "C 80 XD0", "110 XD0", "121 XD0"]},
        {"name": "CONSOLE ARISTON", "type": "CONSOLE_PAVIMENTO", "pages": [602], "keys": ["CONSOLE", "CON R32"]},
        {"name": "SOFFITTO ARISTON", "type": "PENSILE_SOFFITTO", "pages": [602], "keys": ["SOFFITTO", "CEF R32"]},
        {"name": "DUCT CANALIZZATA ARISTON", "type": "CANALIZZATO", "pages": [603], "keys": ["DUCT", "MUC R32"]},
        {"name": "SLIM CASSETTA 90x90 ARISTON", "type": "CASSETTA_90X90", "pages": [603], "keys": ["SLIM CASSETTA", "CASSETTA 90X90"]}
    ],
    "BERETTA": [
        {"name": "BREVA / BREVA E", "type": "PARETE", "pages": [604], "keys": ["BREVA", "BREVA E", "BREVA IN", "BREVA EX"]}
    ],
    "RIELLO": [
        {"name": "AARIA START N / AMW ST N", "type": "PARETE", "pages": [605], "keys": ["AARIA START", "AMW 25 ST", "AMW 35 ST"]},
        {"name": "RIELLO ELIXA MONO-REW", "type": "PARETE", "pages": [605], "keys": ["ELIXA", "REW"]},
        {"name": "AARIA MONO PLUS (AMW PLUS)", "type": "PARETE", "pages": [605], "keys": ["AARIA MONO", "AMW PLUS", "25 PLUS I", "35 PLUS I", "50 PLUS I"]},
        {"name": "AARIA MULTI", "type": "MULTI_SPLIT", "pages": [608], "keys": ["AARIA MULTI", "250 PI", "355 PI", "370 PI", "480 PI", "5100 PI", "AMW 20 PI"]},
        {"name": "AARIA PRO P COMMERCIALE", "type": "COMMERCIALE_UE", "pages": [606, 607], "keys": ["AARIA PRO P", "1070 MI", "1100 MI", "1125 MI", "1125 TI", "1140 TI"]},
        {"name": "CANALIZZATA AARIA MONO PLUS I-AMD", "type": "CANALIZZATO", "pages": [606], "keys": ["I-AMD", "AMD"]},
        {"name": "CASSETTA AARIA MONO PLUS I-AMK 60x60", "type": "CASSETTA_60X60", "pages": [606], "keys": ["I-AMK", "AMK"]},
        {"name": "CONSOLE AARIA MONO PLUS I-AMC", "type": "CONSOLE_PAVIMENTO", "pages": [607], "keys": ["I-AMC", "AMC"]},
        {"name": "PAVIMENTO/SOFFITTO AARIA PRO P-AMS P", "type": "PENSILE_SOFFITTO", "pages": [607], "keys": ["P-AMS", "AMS"]}
    ],
    "BOSCH": [
        {"name": "CLIMATE 3000i / 3200i", "type": "PARETE", "pages": [609], "keys": ["CLIMATE 3000I", "CLIMATE 3200I", "CL3000I"]},
        {"name": "CLIMATE 4000i", "type": "PARETE", "pages": [609], "keys": ["CLIMATE 4000I", "CL4000I"]},
        {"name": "CLIMATE 7000i", "type": "PARETE", "pages": [609], "keys": ["CLIMATE 7000I", "CL7000I"]},
        {"name": "CANALIZZATA CLIMATE 5000 I", "type": "CANALIZZATO", "pages": [610], "keys": ["CANALIZZATA CLIMATE", "CL5000I-U"]},
        {"name": "CASSETTA CLIMATE 5000 I", "type": "CASSETTA_60X60", "pages": [610], "keys": ["CASSETTA CLIMATE", "CL5000I-4C", "CL5000I-P"]},
        {"name": "CLIMATE 5000L COMMERCIALE", "type": "COMMERCIALE_UE", "pages": [610], "keys": ["CLIMATE 5000L", "CL5000L"]},
        {"name": "MULTI CLIMATE 5000 M", "type": "MULTI_SPLIT", "pages": [611, 612], "keys": ["CLIMATE 5000M", "CL5000M", "41/2 E", "53/2 E", "62/3 E", "79/4 E", "82/4 E", "105/4 E", "125/5 E"]}
    ],
    "IMMERGAS": [
        {"name": "THOR", "type": "PARETE", "pages": [613], "keys": ["THOR", "THOR 9", "THOR 12"]},
        {"name": "GOTHA", "type": "PARETE", "pages": [613], "keys": ["GOTHA", "GOTHA 9", "GOTHA 12"]},
        {"name": "MULTI SPLIT IMMERGAS", "type": "MULTI_SPLIT", "pages": [613, 614], "keys": ["UE MULTI 18", "UE MULTI 21", "UE MULTI 27", "UE MULTI 28", "UE MULTI 36", "UE MULTI 42", "UE MULTI 2 ATT 18", "UE MULTI 3 ATT", "UE MULTI 4 ATT", "UE MULTI 5 ATT"]},
        {"name": "CASSETTA IMMERGAS", "type": "CASSETTA_60X60", "pages": [613], "keys": ["CASSETTA", "UI CAS"]},
        {"name": "CANALIZZATO DUCT IMMERGAS", "type": "CANALIZZATO", "pages": [613], "keys": ["CANALIZZATO", "UI DUCT"]}
    ],
    "HSD": [
        {"name": "VIVAIR ONE", "type": "PARETE", "pages": [615], "keys": ["VIVAIR ONE", "SDHL 1-030"]},
        {"name": "VIVAIR LITE", "type": "PARETE", "pages": [615], "keys": ["VIVAIR LITE", "SDH B1-025S", "SDH B1-035S", "SDH B1-050S"]},
        {"name": "VIVAIR MAX", "type": "PARETE", "pages": [615], "keys": ["VIVAIR MAX", "SDHP1"]},
        {"name": "VIVAIR MULTI", "type": "MULTI_SPLIT", "pages": [616], "keys": ["VIVAIR MULTI", "SDH1-040", "SDH1-050", "SDH1-070", "SDH1-080", "SDH1-120", "MNA2O", "MNA3O", "MNA4O", "MNA5O"]}
    ],
    "VAILLANT": [
        {"name": "CLIMAVAIR INTRO", "type": "PARETE", "pages": [617], "keys": ["CLIMAVAIR INTRO", "VAIL 1-025", "VAIL 1-030", "VAIL 1-035"]},
        {"name": "CLIMAVAIR PRO / PLUS", "type": "PARETE", "pages": [617], "keys": ["CLIMAVAIR PRO", "CLIMAVAIR PLUS", "VAIB 1-025", "VAIB 1-035", "VAIB 1-050", "VAIB 1-065", "VAIP1"]},
        {"name": "CLIMAVAIR EXCLUSIVE", "type": "PARETE", "pages": [617], "keys": ["CLIMAVAIR EXCLUSIVE", "VAI 5-025", "VAI 5-035", "5-025WNO", "5-065WNO"]},
        {"name": "CLIMAVAIR MULTI", "type": "MULTI_SPLIT", "pages": [618, 619], "keys": ["CLIMAVAIR MULTI", "VAM1-040", "VAM1-050", "VAM1-070", "VAM1-080", "VAM1-120", "VAM1"]}
    ],
    "AERMEC": [
        {"name": "SFE", "type": "PARETE", "pages": [620], "keys": ["SFE", "SFE250", "SFE350", "SFE500", "SFE700"]},
        {"name": "SPG", "type": "PARETE", "pages": [620], "keys": ["SPG", "SPG250", "SPG350", "SPG500", "SPG700"]},
        {"name": "CKG CONSOLE", "type": "CONSOLE_PAVIMENTO", "pages": [620], "keys": ["CKG", "CKG261", "CKG361", "CKG501"]},
        {"name": "MPG MULTI SPLIT", "type": "MULTI_SPLIT", "pages": [621], "keys": ["MPG", "MPG420", "MPG520", "MPG630", "MPG730", "MPG840", "MPG1040", "MPG1250"]},
        {"name": "LPG COMMERCIALE (CANALIZZATA / CASSETTA / SOFFITTO)", "type": "COMMERCIALE", "pages": [622, 623], "keys": ["LPG", "LPG350", "LPG500", "LPG700", "LPG1000", "LPG1200", "LPG1400", "LPG1600"]},
        {"name": "SCG COLONNA", "type": "COLONNA", "pages": [623], "keys": ["SCG", "SCG701", "SCG1201", "SCG1401"]},
        {"name": "PORTATILE AERMEC", "type": "PORTATILE", "pages": [], "keys": ["PORTATILE", "PSL"]}
    ],
    "HITACHI": [
        {"name": "AIRHOME 200", "type": "PARETE", "pages": [], "keys": ["AIRHOME 200", "RAC-CJ", "RAK-CJ"]},
        {"name": "AIRHOME 400", "type": "PARETE", "pages": [], "keys": ["AIRHOME 400", "RAC-DJ", "RAK-DJ"]},
        {"name": "AIRHOME 600", "type": "PARETE", "pages": [], "keys": ["AIRHOME 600", "RAC-VJ", "RAK-VJ"]},
        {"name": "DODAI 2", "type": "PARETE", "pages": [], "keys": ["DODAI", "RAC-REF", "RAK-REF"]},
        {"name": "MOKAI", "type": "PARETE", "pages": [], "keys": ["MOKAI", "RAC-PEF", "RAK-PEF"]},
        {"name": "TAKAI", "type": "PARETE", "pages": [], "keys": ["TAKAI", "RAC-RXF", "RAK-RXF"]},
        {"name": "MULTIZONE HITACHI", "type": "MULTI_SPLIT", "pages": [], "keys": ["RAM-", "MULTIZONE"]},
        {"name": "PRIMAIRY COMMERCIALE", "type": "COMMERCIALE", "pages": [], "keys": ["PRIMAIRY", "RCI", "RAD", "RPK", "RPC"]}
    ],
    "TCL": [
        {"name": "BREEZEIN P5", "type": "PARETE", "pages": [], "keys": ["BREEZEIN", "ST09P", "ST12P", "ST18P", "ST24P"]},
        {"name": "ELITE F2", "type": "PARETE", "pages": [], "keys": ["ELITE F2", "ST09F", "ST12F", "ST18F", "ST24F"]},
        {"name": "OCARINA", "type": "PARETE", "pages": [], "keys": ["OCARINA"]}
    ],
    "HOSHIKO": [
        {"name": "IRIS", "type": "PARETE", "pages": [], "keys": ["IRIS"]},
        {"name": "KOVER", "type": "PARETE", "pages": [], "keys": ["KOVER"]}
    ],
    "ACCORRONI": [
        {"name": "TREDI", "type": "PARETE", "pages": [], "keys": ["TREDI"]}
    ],
    "SENZA UNITA ESTERNA": [
        {"name": "INNOVA 2.0 VERTICALE / ORIZZONTALE", "type": "SENZA_UNITA_ESTERNA", "pages": [624], "keys": ["INNOVA", "2.0", "MINI 09 HP", "12 HP", "15 HP", "CEILING"]},
        {"name": "KOSAMI SENZA UNITA ESTERNA", "type": "SENZA_UNITA_ESTERNA", "pages": [624], "keys": ["KOSAMI", "C5MO", "12000", "14000"]},
        {"name": "ARGO APOLLO 12 HP", "type": "SENZA_UNITA_ESTERNA", "pages": [625], "keys": ["ARGO", "APOLLO", "APOLLO 12HP"]},
        {"name": "PANASONIC RAC SOLO", "type": "SENZA_UNITA_ESTERNA", "pages": [625], "keys": ["RAC SOLO", "SOLO"]},
        {"name": "AERMEC POLO", "type": "SENZA_UNITA_ESTERNA", "pages": [625], "keys": ["POLO", "POLO 10K"]},
        {"name": "IDEAL CLIMA FK / AERMEC FK", "type": "SENZA_UNITA_ESTERNA", "pages": [625], "keys": ["IDEAL CLIMA", "FK260", "FK360", "FK261", "FK361"]},
        {"name": "OLIMPIA SPLENDID UNICO (AIR / EASY / EDGE / EVO / PRO / TWIN)", "type": "SENZA_UNITA_ESTERNA", "pages": [626], "keys": ["UNICO", "UNICO AIR", "UNICO EASY", "UNICO EDGE", "UNICO EVO", "UNICO PRO", "UNICO TOWER", "UNICO TWIN"]}
    ]
}

def classify_family(brand: str, name: str, page: int = None):
    b = brand.upper()
    n = name.upper()
    
    # 1. Match against brand families
    families = CATALOG_FAMILIES_DEF.get(b, [])
    
    # Check page-aware match first
    if page:
        for fam in families:
            if page in fam["pages"]:
                # Check keys
                if any(k in n for k in fam["keys"]):
                    return fam["name"], fam["type"]
                
    # Fallback to key matching for the brand
    for fam in families:
        if any(k in n for k in fam["keys"]):
            return fam["name"], fam["type"]
            
    # Check Senza Unita Esterna
    if any(k in n for k in ["SENZA UNITA ESTERNA", "S/UE", "MONOBLOCCO", "UNICO", "APOLLO", "FK26", "FK36"]):
        for fam in CATALOG_FAMILIES_DEF.get("SENZA UNITA ESTERNA", []):
            if any(k in n for k in fam["keys"]):
                return fam["name"], fam["type"]
                
    return "ALTRE SERIE", "PARETE"

def test_classification():
    with open('Knowledge/unified_catalog_master.json', 'r', encoding='utf-8') as f:
        items = json.load(f)

    ac_items = [it for it in items if any(k in (it.get('category_path') or '').upper() for k in ['RESIDENZIALI', 'COMMERCIALI', 'SENZA UNIT'])]
    
    matched = 0
    unmatched = 0
    family_counter = Counter()

    for it in ac_items:
        brand = it.get('brand', '')
        name = it.get('name', '')
        page = it.get('primary_page')
        fam_name, fam_type = classify_family(brand, name, page)
        family_counter[(brand, fam_name)] += 1
        if fam_name != "ALTRE SERIE":
            matched += 1
        else:
            unmatched += 1

    print(f"Total AC Items Tested: {len(ac_items)}")
    print(f"Matched to Official Catalog Families: {matched} ({matched/len(ac_items)*100:.1f}%)")
    print(f"Unmatched: {unmatched}")
    
    print("\nTop 50 Brand-Family breakdown:")
    for (b, f_name), count in family_counter.most_common(50):
        print(f"  [{b:15s}] {f_name:45s}: {count:4d} items")

if __name__ == '__main__':
    test_classification()
