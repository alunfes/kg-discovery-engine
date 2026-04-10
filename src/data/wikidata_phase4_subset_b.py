"""Subset B: Immunology bio (imm:) + Natural products chem (nat:).

Bio: Immune cell signaling, cytokines, innate/adaptive immunity, eicosanoid enzymes.
Chem: Flavonoids, terpenoids, alkaloids, isothiocyanates, natural eicosanoids.
Bridge: Shared eicosanoid metabolites (Arachidonic acid, PGE2, LTB4) and
        drug-like inhibition of immune enzymes by natural compounds.

Designed for Run 013 cross-subset reproducibility test.
Entity prefixes: imm: (biology/immunology), nat: (chemistry/natural products).
No overlap with wikidata_phase4_loader.py bio:/chem: namespace.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from src.data.wikidata_phase4_loader import WD4Data


# ---------------------------------------------------------------------------
# Bio nodes (imm: prefix)
# ---------------------------------------------------------------------------

_IMM_NODES: list[tuple[str, str]] = [
    # --- Immune surface markers ---
    ("imm:CD4", "CD4"),
    ("imm:CD8A", "CD8A"),
    ("imm:CD19", "CD19"),
    ("imm:CD20", "MS4A1"),
    ("imm:CD25", "IL-2 receptor alpha"),
    ("imm:CD28", "CD28"),
    ("imm:CD56", "NCAM1"),
    ("imm:CD80", "B7-1"),
    ("imm:CD86", "B7-2"),
    ("imm:PDCD1", "PD-1"),
    ("imm:CD274", "PD-L1"),
    ("imm:CTLA4", "CTLA-4"),
    ("imm:HAVCR2", "TIM-3"),
    ("imm:LAG3", "LAG-3"),
    ("imm:TIGIT", "TIGIT"),
    ("imm:CD40", "CD40"),
    ("imm:CD40LG", "CD40L"),
    ("imm:HLA_DRA", "HLA-DR alpha"),
    ("imm:FCGR3A", "FcgammaRIII"),
    ("imm:FCER1A", "FcepsilonRI alpha"),
    # --- Cytokines ---
    ("imm:IL1B", "IL-1beta"),
    ("imm:IL2", "IL-2"),
    ("imm:IL4", "IL-4"),
    ("imm:IL5", "IL-5"),
    ("imm:IL8", "IL-8"),
    ("imm:IL10", "IL-10"),
    ("imm:IL12A", "IL-12A"),
    ("imm:IL13", "IL-13"),
    ("imm:IL17A", "IL-17A"),
    ("imm:IL21", "IL-21"),
    ("imm:IL23A", "IL-23A"),
    ("imm:IL25", "IL-25"),
    ("imm:IL33", "IL-33"),
    ("imm:IL18", "IL-18"),
    ("imm:IL36A", "IL-36A"),
    ("imm:IFNA1", "IFN-alpha"),
    ("imm:IFNB1", "IFN-beta"),
    ("imm:TGFB1", "TGF-beta1"),
    ("imm:TNFA", "TNF-alpha-imm"),
    # --- Cytokine receptors ---
    ("imm:IL1R1", "IL-1 receptor"),
    ("imm:IL2RA", "IL-2 receptor alpha"),
    ("imm:IL4R", "IL-4 receptor"),
    ("imm:IL6R", "IL-6 receptor"),
    ("imm:IL10RA", "IL-10 receptor alpha"),
    ("imm:IL12RB1", "IL-12 receptor beta1"),
    ("imm:IL17RA", "IL-17 receptor A"),
    ("imm:TNFR1", "TNFR1"),
    ("imm:IFNAR1", "IFN-alpha receptor 1"),
    ("imm:IFNGR1", "IFN-gamma receptor 1"),
    # --- TLR / innate immunity ---
    ("imm:TLR2", "TLR2"),
    ("imm:TLR4", "TLR4"),
    ("imm:TLR7", "TLR7"),
    ("imm:TLR9", "TLR9"),
    ("imm:MYD88", "MyD88"),
    ("imm:TRIF", "TRIF"),
    ("imm:IRAK1", "IRAK1"),
    ("imm:IRAK4", "IRAK4"),
    ("imm:TRAF6", "TRAF6"),
    ("imm:TAK1", "TAK1"),
    ("imm:TANK", "TANK"),
    # --- STING / cGAS pathway ---
    ("imm:TMEM173", "STING"),
    ("imm:MB21D1", "cGAS"),
    ("imm:TBK1", "TBK1"),
    ("imm:IKBKE", "IKKepsilon"),
    # --- NLRP3 inflammasome ---
    ("imm:NLRP3", "NLRP3"),
    ("imm:PYCARD", "ASC"),
    ("imm:CASP1", "Caspase-1"),
    # --- NF-kB (non-canonical) ---
    ("imm:NFKB2", "NF-kB p100/p52"),
    ("imm:RELB", "RelB"),
    ("imm:CSNK2A1", "CK2 alpha"),
    # --- IRF factors ---
    ("imm:IRF3", "IRF3"),
    ("imm:IRF7", "IRF7"),
    ("imm:IRF5", "IRF5"),
    ("imm:IRF1", "IRF1"),
    # --- T cell signaling ---
    ("imm:LCK", "Lck"),
    ("imm:ZAP70", "ZAP-70"),
    ("imm:LAT", "LAT"),
    ("imm:LCP2", "SLP-76"),
    ("imm:ITK", "ITK"),
    ("imm:NFATC1", "NFAT1"),
    ("imm:NFATC2", "NFAT2"),
    ("imm:NFATC3", "NFAT3"),
    # --- B cell signaling ---
    ("imm:BTK", "BTK"),
    ("imm:BLNK", "BLNK"),
    ("imm:SYK", "SYK"),
    ("imm:CR2", "CD21"),
    ("imm:IGHM", "IgM"),
    # --- Eicosanoid enzymes ---
    ("imm:PTGS1", "COX-1"),
    ("imm:PTGS2", "COX-2"),
    ("imm:ALOX5", "5-LOX"),
    ("imm:ALOX12", "12-LOX"),
    ("imm:ALOX15", "15-LOX"),
    ("imm:PTGES", "PGES"),
    ("imm:TBXAS1", "TXA synthase"),
    ("imm:PLA2G4A", "cPLA2 alpha"),
    # --- Transcription factors ---
    ("imm:TBX21", "T-bet"),
    ("imm:GATA3", "GATA3"),
    ("imm:RORC", "RORgamma-t"),
    ("imm:FOXP3", "FOXP3"),
    ("imm:BCL6", "BCL6"),
    ("imm:BATF", "BATF"),
    ("imm:PRDM1", "BLIMP1"),
    ("imm:IRF4", "IRF4"),
    # --- Chemokines / adhesion ---
    ("imm:CXCL8", "CXCL8"),
    ("imm:CXCL10", "CXCL10"),
    ("imm:CXCL12", "CXCL12"),
    ("imm:CCL2", "MCP-1"),
    ("imm:CCL5", "RANTES"),
    ("imm:VCAM1", "VCAM-1"),
    ("imm:ICAM1", "ICAM-1"),
    ("imm:SELP", "P-selectin"),
    # --- Complement ---
    ("imm:C1QA", "C1q alpha"),
    ("imm:C1QB", "C1q beta"),
    ("imm:C3", "Complement C3"),
    ("imm:C4A", "Complement C4A"),
    ("imm:C5", "Complement C5"),
    ("imm:C5AR1", "C5a receptor"),
    ("imm:C3AR1", "C3a receptor"),
    ("imm:CFB", "Factor B"),
    # --- JAK-STAT (immune) ---
    ("imm:JAK1", "JAK1-imm"),
    ("imm:JAK3", "JAK3"),
    ("imm:STAT1", "STAT1-imm"),
    ("imm:STAT2", "STAT2"),
    ("imm:STAT4", "STAT4"),
    ("imm:STAT6", "STAT6"),
    # --- Immune metabolites ---
    ("imm:m_AA", "Arachidonic acid"),
    ("imm:m_PGE2", "Prostaglandin E2"),
    ("imm:m_LTB4", "Leukotriene B4"),
    ("imm:m_ROS", "Reactive oxygen species"),
    ("imm:m_PGI2", "Prostacyclin"),
    ("imm:m_TXA2", "Thromboxane A2"),
    ("imm:m_5HETE", "5-HETE"),
    ("imm:m_IP3", "Inositol triphosphate"),
    ("imm:m_DAG", "Diacylglycerol"),
    ("imm:m_cAMP", "cAMP-imm"),
    # --- Antimicrobial / danger signals ---
    ("imm:HMGB1", "HMGB1"),
    ("imm:S100A8", "S100A8"),
    ("imm:S100A9", "S100A9"),
    ("imm:DEFB1", "Defensin beta 1"),
    ("imm:PGLYRP1", "PGLYRP1"),
    # --- Regulatory proteins ---
    ("imm:SOCS1", "SOCS1"),
    ("imm:SOCS3", "SOCS3"),
    ("imm:A20", "TNFAIP3"),
    ("imm:SHIP1", "INPP5D"),
    ("imm:SHP1", "PTPN6"),
    # --- Genes ---
    ("imm:g_PTGS2", "PTGS2 gene"),
    ("imm:g_ALOX5", "ALOX5 gene"),
    ("imm:g_NLRP3", "NLRP3 gene"),
    ("imm:g_IRF3", "IRF3 gene"),
    ("imm:g_IL1B", "IL1B gene"),
    ("imm:g_STAT1", "STAT1 gene"),
    ("imm:g_PTGES", "PTGES gene"),
    ("imm:g_TLR4", "TLR4 gene"),
    ("imm:g_IL6", "IL6 gene"),
    ("imm:g_FOXP3", "FOXP3 gene"),
    ("imm:g_PLA2G4A", "PLA2G4A gene"),
    ("imm:g_TBXAS1", "TBXAS1 gene"),
    # --- Diseases ---
    ("imm:d_Asthma", "Asthma"),
    ("imm:d_MultipleSclerosis", "Multiple sclerosis"),
    ("imm:d_SysLupus", "Systemic lupus"),
    ("imm:d_Type1DM", "Type 1 diabetes"),
    ("imm:d_Allergy", "Allergy"),
    ("imm:d_Sepsis", "Sepsis"),
    ("imm:d_Psoriasis", "Psoriasis"),
    ("imm:d_CrohnsDisease", "Crohns disease"),
    ("imm:d_RA", "Rheumatoid arthritis"),
    ("imm:d_Anaphylaxis", "Anaphylaxis"),
    # --- Processes ---
    ("imm:p_Phagocytosis", "Phagocytosis"),
    ("imm:p_RespiratoryBurst", "Respiratory burst"),
    ("imm:p_AntigenPresentation", "Antigen presentation"),
    ("imm:p_TCellActivation", "T cell activation"),
    ("imm:p_BCellMaturation", "B cell maturation"),
    ("imm:p_Inflammasome", "Inflammasome activation"),
    ("imm:p_NETosis", "NETosis"),
    ("imm:p_CytokineStorm", "Cytokine storm"),
    ("imm:p_ClassSwitching", "Antibody class switching"),
    ("imm:p_Opsonization", "Opsonization"),
    ("imm:p_Complement_activation", "Complement activation"),
]

# ---------------------------------------------------------------------------
# Bio edges (imm:)
# ---------------------------------------------------------------------------

_IMM_EDGES: list[tuple[str, str, str]] = [
    # TLR signaling
    ("imm:TLR4", "activates", "imm:MYD88"),
    ("imm:TLR2", "activates", "imm:MYD88"),
    ("imm:TLR9", "activates", "imm:MYD88"),
    ("imm:TLR7", "activates", "imm:MYD88"),
    ("imm:TLR4", "activates", "imm:TRIF"),
    ("imm:MYD88", "activates", "imm:IRAK1"),
    ("imm:MYD88", "activates", "imm:IRAK4"),
    ("imm:IRAK4", "activates", "imm:IRAK1"),
    ("imm:IRAK1", "activates", "imm:TRAF6"),
    ("imm:IRAK4", "activates", "imm:TRAF6"),
    ("imm:TRAF6", "activates", "imm:TAK1"),
    ("imm:TAK1", "activates", "imm:TANK"),
    # STING pathway
    ("imm:MB21D1", "activates", "imm:TMEM173"),
    ("imm:TMEM173", "activates", "imm:TBK1"),
    ("imm:TBK1", "activates", "imm:IRF3"),
    ("imm:TBK1", "activates", "imm:IRF7"),
    ("imm:IKBKE", "activates", "imm:IRF3"),
    ("imm:IRF3", "activates", "imm:IFNB1"),
    ("imm:IRF7", "activates", "imm:IFNA1"),
    ("imm:IRF5", "activates", "imm:IL1B"),
    ("imm:IRF1", "activates", "imm:CXCL10"),
    # NLRP3 inflammasome
    ("imm:NLRP3", "activates", "imm:PYCARD"),
    ("imm:PYCARD", "activates", "imm:CASP1"),
    ("imm:CASP1", "activates", "imm:IL1B"),
    ("imm:CASP1", "activates", "imm:IL18"),
    ("imm:g_NLRP3", "encodes", "imm:NLRP3"),
    ("imm:TRAF6", "activates", "imm:NLRP3"),
    # NF-kB (non-canonical)
    ("imm:TRAF6", "activates", "imm:NFKB2"),
    ("imm:NFKB2", "activates", "imm:RELB"),
    ("imm:RELB", "activates", "imm:p_CytokineStorm"),
    ("imm:CSNK2A1", "activates", "imm:NFKB2"),
    # Eicosanoid synthesis
    ("imm:g_PLA2G4A", "encodes", "imm:PLA2G4A"),
    ("imm:PLA2G4A", "catalyzes", "imm:m_AA"),
    ("imm:g_PTGS2", "encodes", "imm:PTGS2"),
    ("imm:PTGS2", "catalyzes", "imm:m_AA"),
    ("imm:PTGS2", "produces", "imm:m_PGE2"),
    ("imm:PTGS1", "catalyzes", "imm:m_AA"),
    ("imm:PTGS1", "produces", "imm:m_TXA2"),
    ("imm:g_PTGES", "encodes", "imm:PTGES"),
    ("imm:PTGES", "catalyzes", "imm:m_PGE2"),
    ("imm:g_ALOX5", "encodes", "imm:ALOX5"),
    ("imm:ALOX5", "catalyzes", "imm:m_AA"),
    ("imm:ALOX5", "produces", "imm:m_LTB4"),
    ("imm:ALOX5", "produces", "imm:m_5HETE"),
    ("imm:ALOX12", "catalyzes", "imm:m_AA"),
    ("imm:ALOX15", "catalyzes", "imm:m_AA"),
    ("imm:g_TBXAS1", "encodes", "imm:TBXAS1"),
    ("imm:TBXAS1", "produces", "imm:m_TXA2"),
    ("imm:m_AA", "undergoes", "imm:p_Inflammasome"),
    # T cell signaling
    ("imm:CD28", "activates", "imm:LCK"),
    ("imm:LCK", "activates", "imm:ZAP70"),
    ("imm:ZAP70", "activates", "imm:LAT"),
    ("imm:LAT", "activates", "imm:LCP2"),
    ("imm:LCP2", "activates", "imm:ITK"),
    ("imm:ITK", "activates", "imm:NFATC1"),
    ("imm:NFATC1", "activates", "imm:p_TCellActivation"),
    ("imm:NFATC2", "activates", "imm:p_TCellActivation"),
    ("imm:NFATC3", "activates", "imm:IL2"),
    ("imm:CTLA4", "inhibits", "imm:LCK"),
    ("imm:PDCD1", "inhibits", "imm:ZAP70"),
    # B cell signaling
    ("imm:BTK", "activates", "imm:BLNK"),
    ("imm:SYK", "activates", "imm:BTK"),
    ("imm:BLNK", "activates", "imm:p_BCellMaturation"),
    ("imm:CR2", "activates", "imm:SYK"),
    # JAK-STAT (immune)
    ("imm:IFNB1", "activates", "imm:IFNAR1"),
    ("imm:IFNAR1", "activates", "imm:JAK1"),
    ("imm:JAK1", "activates", "imm:STAT1"),
    ("imm:JAK1", "activates", "imm:STAT2"),
    ("imm:JAK3", "activates", "imm:STAT4"),
    ("imm:JAK3", "activates", "imm:STAT6"),
    ("imm:g_STAT1", "encodes", "imm:STAT1"),
    ("imm:STAT1", "activates", "imm:IRF1"),
    ("imm:STAT4", "activates", "imm:TBX21"),
    ("imm:STAT6", "activates", "imm:GATA3"),
    # Immune cell regulation
    ("imm:FOXP3", "inhibits", "imm:p_TCellActivation"),
    ("imm:TBX21", "activates", "imm:IFNA1"),
    ("imm:GATA3", "activates", "imm:IL4"),
    ("imm:GATA3", "activates", "imm:IL13"),
    ("imm:RORC", "activates", "imm:IL17A"),
    ("imm:RORC", "activates", "imm:IL21"),
    ("imm:BCL6", "activates", "imm:p_ClassSwitching"),
    ("imm:PRDM1", "inhibits", "imm:BCL6"),
    ("imm:IRF4", "activates", "imm:PRDM1"),
    ("imm:BATF", "activates", "imm:IRF4"),
    ("imm:g_FOXP3", "encodes", "imm:FOXP3"),
    # Complement cascade
    ("imm:C1QA", "activates", "imm:C4A"),
    ("imm:C4A", "activates", "imm:C3"),
    ("imm:C3", "activates", "imm:C5"),
    ("imm:C5", "activates", "imm:C5AR1"),
    ("imm:C3", "activates", "imm:C3AR1"),
    ("imm:CFB", "activates", "imm:C3"),
    ("imm:p_Complement_activation", "activates", "imm:p_Opsonization"),
    # Feedback / regulation
    ("imm:SOCS1", "inhibits", "imm:JAK1"),
    ("imm:SOCS3", "inhibits", "imm:JAK1"),
    ("imm:A20", "inhibits", "imm:TRAF6"),
    ("imm:SHIP1", "inhibits", "imm:BTK"),
    ("imm:SHP1", "inhibits", "imm:LCK"),
    # Cytokine downstream effects
    ("imm:IL1B", "activates", "imm:d_Sepsis"),
    ("imm:IL17A", "activates", "imm:d_Psoriasis"),
    ("imm:IL13", "activates", "imm:d_Asthma"),
    ("imm:IL4", "activates", "imm:d_Allergy"),
    ("imm:IL33", "activates", "imm:d_Asthma"),
    ("imm:IL21", "activates", "imm:d_SysLupus"),
    ("imm:TGFB1", "activates", "imm:d_MultipleSclerosis"),
    ("imm:IFNA1", "activates", "imm:d_SysLupus"),
    # Chemokine signaling
    ("imm:CXCL8", "activates", "imm:p_NETosis"),
    ("imm:CCL2", "activates", "imm:p_Phagocytosis"),
    ("imm:CXCL12", "activates", "imm:p_TCellActivation"),
    ("imm:VCAM1", "activates", "imm:p_Opsonization"),
    ("imm:ICAM1", "activates", "imm:p_AntigenPresentation"),
    # Danger signal responses
    ("imm:HMGB1", "activates", "imm:TLR4"),
    ("imm:S100A8", "activates", "imm:TLR4"),
    ("imm:S100A9", "activates", "imm:NLRP3"),
    # ROS production
    ("imm:p_RespiratoryBurst", "produces", "imm:m_ROS"),
    ("imm:m_ROS", "activates", "imm:NLRP3"),
    # IP3/DAG signaling
    ("imm:m_IP3", "activates", "imm:NFATC1"),
    ("imm:m_DAG", "activates", "imm:LCK"),
    ("imm:m_cAMP", "inhibits", "imm:NFATC1"),
    # Gene encoding
    ("imm:g_IRF3", "encodes", "imm:IRF3"),
    ("imm:g_IL1B", "encodes", "imm:IL1B"),
    ("imm:g_TLR4", "encodes", "imm:TLR4"),
    ("imm:g_IL6", "encodes", "imm:IL33"),
]

# ---------------------------------------------------------------------------
# Chem nodes (nat: prefix)
# ---------------------------------------------------------------------------

_NAT_NODES: list[tuple[str, str]] = [
    # --- Flavonoids ---
    ("nat:Kaempferol", "Kaempferol"),
    ("nat:Luteolin", "Luteolin"),
    ("nat:Apigenin", "Apigenin"),
    ("nat:Fisetin", "Fisetin"),
    ("nat:Myricetin", "Myricetin"),
    ("nat:Naringenin", "Naringenin"),
    ("nat:Hesperidin", "Hesperidin"),
    ("nat:Rutin", "Rutin"),
    ("nat:Genistein", "Genistein"),
    ("nat:Daidzein", "Daidzein"),
    ("nat:Chrysin", "Chrysin"),
    ("nat:Baicalein", "Baicalein"),
    ("nat:Wogonin", "Wogonin"),
    ("nat:Nobiletin", "Nobiletin"),
    # --- Stilbenes ---
    ("nat:Pterostilbene", "Pterostilbene"),
    ("nat:Piceatannol", "Piceatannol"),
    ("nat:Pinosylvin", "Pinosylvin"),
    ("nat:Oxyresveratrol", "Oxyresveratrol"),
    # --- Catechins ---
    ("nat:Epicatechin", "Epicatechin"),
    ("nat:EpicatechinGallate", "Epicatechin gallate"),
    ("nat:Epigallocatechin", "Epigallocatechin"),
    ("nat:Theaflavin", "Theaflavin"),
    ("nat:ProcyanidinB2", "Procyanidin B2"),
    # --- Xanthones ---
    ("nat:Mangostin", "Alpha-mangostin"),
    ("nat:Xanthone", "Xanthone"),
    ("nat:GambogicAcid", "Gambogic acid"),
    ("nat:Mangiferin", "Mangiferin"),
    # --- Coumarins ---
    ("nat:Umbelliferone", "Umbelliferone"),
    ("nat:Scopoletin", "Scopoletin"),
    ("nat:Bergapten", "Bergapten"),
    ("nat:Psoralen", "Psoralen"),
    ("nat:Aesculetin", "Aesculetin"),
    # --- Monoterpenes ---
    ("nat:Limonene", "D-Limonene"),
    ("nat:Menthol", "L-Menthol"),
    ("nat:Camphor", "Camphor"),
    ("nat:AlphaPinene", "Alpha-pinene"),
    ("nat:Geraniol", "Geraniol"),
    ("nat:Linalool", "Linalool"),
    ("nat:Carvacrol", "Carvacrol"),
    ("nat:Thymol", "Thymol"),
    # --- Sesquiterpenes ---
    ("nat:Artemisinin", "Artemisinin"),
    ("nat:Parthenolide", "Parthenolide"),
    ("nat:Helenalin", "Helenalin"),
    ("nat:Farnesol", "Farnesol"),
    ("nat:Nerolidol", "Nerolidol"),
    # --- Diterpenes ---
    ("nat:TanshinoneIIA", "Tanshinone IIA"),
    ("nat:Andrographolide", "Andrographolide"),
    ("nat:GinkgolideB", "Ginkgolide B"),
    ("nat:Forskolin", "Forskolin"),
    ("nat:Carnosol", "Carnosol"),
    # --- Triterpenes / saponins ---
    ("nat:UrsoliciAcid", "Ursolic acid"),
    ("nat:BetulinicAcid", "Betulinic acid"),
    ("nat:OleanolicAcid", "Oleanolic acid"),
    ("nat:GinsenosideRg1", "Ginsenoside Rg1"),
    ("nat:GinsenosideRb1", "Ginsenoside Rb1"),
    ("nat:Astragaloside", "Astragaloside IV"),
    ("nat:Escin", "Escin"),
    # --- Alkaloids ---
    ("nat:Berberine", "Berberine"),
    ("nat:Piperine", "Piperine"),
    ("nat:Capsaicin", "Capsaicin"),
    ("nat:Gingerol", "6-Gingerol"),
    ("nat:Harmine", "Harmine"),
    ("nat:Colchicine", "Colchicine"),
    ("nat:Theophylline", "Theophylline"),
    ("nat:Theobromine", "Theobromine"),
    ("nat:Nicotine", "Nicotine"),
    ("nat:Vinpocetine", "Vinpocetine"),
    ("nat:Emetine", "Emetine"),
    # --- Isothiocyanates / glucosinolates ---
    ("nat:Allicin", "Allicin"),
    ("nat:Sulforaphane", "Sulforaphane"),
    ("nat:Indole3Carbinol", "Indole-3-carbinol"),
    ("nat:DIM", "3,3'-Diindolylmethane"),
    ("nat:PEITC", "Phenethyl isothiocyanate"),
    # --- Cannabinoids ---
    ("nat:CBD", "Cannabidiol"),
    ("nat:Anandamide", "Anandamide"),
    # --- Eicosanoids (shared bridge metabolites) ---
    ("nat:ArachidonicAcid", "Arachidonic acid"),
    ("nat:PGE2", "Prostaglandin E2"),
    ("nat:LTB4", "Leukotriene B4"),
    ("nat:Prostacyclin", "Prostacyclin"),
    ("nat:TXA2_nat", "Thromboxane A2"),
    # --- Other bioactives ---
    ("nat:Shikonin", "Shikonin"),
    ("nat:Honokiol", "Honokiol"),
    ("nat:Magnolol", "Magnolol"),
    ("nat:Celastrol", "Celastrol"),
    ("nat:Triptolide", "Triptolide"),
    ("nat:Silibinin", "Silibinin"),
    ("nat:CinnamicAcid", "Cinnamic acid"),
    ("nat:Resveratrol_nat", "Resveratrol"),
    ("nat:Quercetin_nat", "Quercetin"),
    # --- Precursors / biosynthetic intermediates ---
    ("nat:Phenylalanine_nat", "L-Phenylalanine"),
    ("nat:Tyrosine_nat", "L-Tyrosine"),
    ("nat:Tryptophan_nat", "L-Tryptophan"),
    ("nat:Mevalonate", "Mevalonic acid"),
    ("nat:GerPP", "Geranyl pyrophosphate"),
    ("nat:FarPP", "Farnesyl pyrophosphate"),
    # --- Chemical reactions (nat) ---
    ("nat:r_Cyclization", "Cyclization reaction"),
    ("nat:r_Glycosylation", "Glycosylation reaction"),
    ("nat:r_Prenylation", "Prenylation reaction"),
    ("nat:r_HydroxylationNat", "Hydroxylation reaction"),
    ("nat:r_OxidationNat", "Oxidation reaction"),
    ("nat:r_Decarboxylation_nat", "Decarboxylation"),
    # --- Functional groups (nat) ---
    ("nat:fg_Phenolic", "Phenolic group"),
    ("nat:fg_Flavone", "Flavone scaffold"),
    ("nat:fg_Terpenoid", "Terpenoid scaffold"),
    ("nat:fg_Catechol_nat", "Catechol group"),
    ("nat:fg_Lactone", "Lactone group"),
    ("nat:fg_Isothiocyanate", "Isothiocyanate group"),
    ("nat:fg_Alkaloid", "Alkaloid scaffold"),
    # --- COX/LOX inhibitors (from nat domain perspective) ---
    ("nat:Zileuton_nat", "Zileuton analog"),
    ("nat:Celecoxib_nat", "Celecoxib analog"),
]

# ---------------------------------------------------------------------------
# Chem edges (nat:)
# ---------------------------------------------------------------------------

_NAT_EDGES: list[tuple[str, str, str]] = [
    # Flavonoid chemistry
    ("nat:Kaempferol", "inhibits", "nat:r_OxidationNat"),
    ("nat:Luteolin", "inhibits", "nat:r_OxidationNat"),
    ("nat:Apigenin", "inhibits", "nat:r_HydroxylationNat"),
    ("nat:Fisetin", "inhibits", "nat:r_OxidationNat"),
    ("nat:Myricetin", "inhibits", "nat:r_OxidationNat"),
    ("nat:Baicalein", "inhibits", "nat:r_Cyclization"),
    ("nat:Chrysin", "inhibits", "nat:r_HydroxylationNat"),
    ("nat:Genistein", "inhibits", "nat:r_Prenylation"),
    ("nat:Daidzein", "inhibits", "nat:r_Prenylation"),
    ("nat:Naringenin", "undergoes", "nat:r_Glycosylation"),
    ("nat:Hesperidin", "undergoes", "nat:r_Glycosylation"),
    ("nat:Rutin", "undergoes", "nat:r_Glycosylation"),
    ("nat:Kaempferol", "contains", "nat:fg_Flavone"),
    ("nat:Luteolin", "contains", "nat:fg_Flavone"),
    ("nat:Apigenin", "contains", "nat:fg_Flavone"),
    ("nat:Fisetin", "contains", "nat:fg_Phenolic"),
    ("nat:Genistein", "contains", "nat:fg_Phenolic"),
    # Stilbene chemistry
    ("nat:Pterostilbene", "inhibits", "nat:r_OxidationNat"),
    ("nat:Piceatannol", "inhibits", "nat:r_OxidationNat"),
    ("nat:Pinosylvin", "contains", "nat:fg_Phenolic"),
    ("nat:Oxyresveratrol", "inhibits", "nat:r_HydroxylationNat"),
    # Catechin chemistry
    ("nat:Epicatechin", "contains", "nat:fg_Catechol_nat"),
    ("nat:EpicatechinGallate", "contains", "nat:fg_Catechol_nat"),
    ("nat:Epigallocatechin", "contains", "nat:fg_Catechol_nat"),
    ("nat:Theaflavin", "undergoes", "nat:r_OxidationNat"),
    ("nat:ProcyanidinB2", "undergoes", "nat:r_Cyclization"),
    # Terpenoid biosynthesis
    ("nat:Mevalonate", "undergoes", "nat:r_Decarboxylation_nat"),
    ("nat:Mevalonate", "is_precursor_of", "nat:GerPP"),
    ("nat:GerPP", "is_precursor_of", "nat:FarPP"),
    ("nat:FarPP", "is_precursor_of", "nat:Farnesol"),
    ("nat:FarPP", "is_precursor_of", "nat:Artemisinin"),
    ("nat:FarPP", "is_precursor_of", "nat:UrsoliciAcid"),
    ("nat:Artemisinin", "contains", "nat:fg_Lactone"),
    ("nat:Parthenolide", "contains", "nat:fg_Lactone"),
    ("nat:TanshinoneIIA", "inhibits", "nat:r_OxidationNat"),
    ("nat:Andrographolide", "inhibits", "nat:r_HydroxylationNat"),
    ("nat:GinkgolideB", "inhibits", "nat:r_Cyclization"),
    ("nat:Forskolin", "activates", "nat:r_Cyclization"),
    ("nat:Carnosol", "inhibits", "nat:r_OxidationNat"),
    ("nat:Limonene", "undergoes", "nat:r_HydroxylationNat"),
    ("nat:Menthol", "contains", "nat:fg_Terpenoid"),
    ("nat:AlphaPinene", "undergoes", "nat:r_Cyclization"),
    ("nat:Geraniol", "is_precursor_of", "nat:Linalool"),
    ("nat:Carvacrol", "inhibits", "nat:r_OxidationNat"),
    ("nat:Thymol", "inhibits", "nat:r_OxidationNat"),
    # Triterpene chemistry
    ("nat:UrsoliciAcid", "contains", "nat:fg_Terpenoid"),
    ("nat:BetulinicAcid", "contains", "nat:fg_Terpenoid"),
    ("nat:OleanolicAcid", "contains", "nat:fg_Terpenoid"),
    ("nat:GinsenosideRg1", "undergoes", "nat:r_Glycosylation"),
    ("nat:GinsenosideRb1", "undergoes", "nat:r_Glycosylation"),
    ("nat:Astragaloside", "undergoes", "nat:r_Glycosylation"),
    # Alkaloid chemistry
    ("nat:Berberine", "contains", "nat:fg_Alkaloid"),
    ("nat:Piperine", "contains", "nat:fg_Alkaloid"),
    ("nat:Capsaicin", "contains", "nat:fg_Phenolic"),
    ("nat:Gingerol", "contains", "nat:fg_Phenolic"),
    ("nat:Harmine", "contains", "nat:fg_Alkaloid"),
    ("nat:Colchicine", "inhibits", "nat:r_Cyclization"),
    ("nat:Vinpocetine", "inhibits", "nat:r_Cyclization"),
    ("nat:Theophylline", "inhibits", "nat:r_HydroxylationNat"),
    ("nat:Theobromine", "inhibits", "nat:r_OxidationNat"),
    # Isothiocyanate chemistry
    ("nat:Allicin", "contains", "nat:fg_Isothiocyanate"),
    ("nat:Sulforaphane", "contains", "nat:fg_Isothiocyanate"),
    ("nat:Indole3Carbinol", "undergoes", "nat:r_Cyclization"),
    ("nat:DIM", "undergoes", "nat:r_Cyclization"),
    ("nat:PEITC", "contains", "nat:fg_Isothiocyanate"),
    # Eicosanoid (natural chemistry)
    ("nat:ArachidonicAcid", "undergoes", "nat:r_OxidationNat"),
    ("nat:ArachidonicAcid", "undergoes", "nat:r_Cyclization"),
    ("nat:ArachidonicAcid", "is_precursor_of", "nat:PGE2"),
    ("nat:ArachidonicAcid", "is_precursor_of", "nat:LTB4"),
    ("nat:ArachidonicAcid", "is_precursor_of", "nat:Prostacyclin"),
    ("nat:ArachidonicAcid", "is_precursor_of", "nat:TXA2_nat"),
    ("nat:PGE2", "undergoes", "nat:r_OxidationNat"),
    ("nat:LTB4", "undergoes", "nat:r_HydroxylationNat"),
    # Phenolic acid chemistry
    ("nat:CinnamicAcid", "contains", "nat:fg_Phenolic"),
    ("nat:Phenylalanine_nat", "is_precursor_of", "nat:CinnamicAcid"),
    ("nat:Phenylalanine_nat", "is_precursor_of", "nat:Tyrosine_nat"),
    ("nat:Tyrosine_nat", "is_precursor_of", "nat:CinnamicAcid"),
    ("nat:Tryptophan_nat", "is_precursor_of", "nat:Harmine"),
    ("nat:Resveratrol_nat", "inhibits", "nat:r_OxidationNat"),
    ("nat:Quercetin_nat", "inhibits", "nat:r_OxidationNat"),
    # Functional group reactions
    ("nat:r_HydroxylationNat", "produces", "nat:fg_Phenolic"),
    ("nat:r_Cyclization", "produces", "nat:fg_Lactone"),
    ("nat:r_Glycosylation", "produces", "nat:fg_Flavone"),
    ("nat:r_OxidationNat", "produces", "nat:fg_Catechol_nat"),
    # Bioactive other
    ("nat:Shikonin", "contains", "nat:fg_Phenolic"),
    ("nat:Honokiol", "inhibits", "nat:r_OxidationNat"),
    ("nat:Magnolol", "inhibits", "nat:r_OxidationNat"),
    ("nat:Celastrol", "inhibits", "nat:r_HydroxylationNat"),
    ("nat:Triptolide", "inhibits", "nat:r_Cyclization"),
    ("nat:Silibinin", "inhibits", "nat:r_OxidationNat"),
]

# ---------------------------------------------------------------------------
# Bridge edges (imm: ↔ nat:)
# ---------------------------------------------------------------------------

_BRIDGE_B_SPARSE: list[tuple[str, str, str]] = [
    # Shared eicosanoid metabolites (same molecule in bio and chem)
    ("imm:m_AA", "same_entity_as", "nat:ArachidonicAcid"),
    ("imm:m_PGE2", "same_entity_as", "nat:PGE2"),
    ("imm:m_LTB4", "same_entity_as", "nat:LTB4"),
    ("imm:m_PGI2", "same_entity_as", "nat:Prostacyclin"),
    ("imm:m_TXA2", "same_entity_as", "nat:TXA2_nat"),
    # Natural compound enzyme inhibitors (nat → imm bridge)
    ("nat:Berberine", "inhibits", "imm:NLRP3"),
    ("nat:Baicalein", "inhibits", "imm:ALOX5"),
    ("nat:Celastrol", "inhibits", "imm:PTGS2"),
    ("nat:Parthenolide", "inhibits", "imm:NFKB2"),
    ("nat:Andrographolide", "inhibits", "imm:STAT1"),
    ("nat:Capsaicin", "activates", "imm:TLR4"),
    ("nat:Sulforaphane", "activates", "imm:IRF3"),
]

_BRIDGE_B_MEDIUM: list[tuple[str, str, str]] = list(_BRIDGE_B_SPARSE) + [
    # More enzyme inhibitor bridges
    ("nat:Luteolin", "inhibits", "imm:PTGS2"),
    ("nat:Kaempferol", "inhibits", "imm:PTGS2"),
    ("nat:Apigenin", "inhibits", "imm:PTGS1"),
    ("nat:Quercetin_nat", "inhibits", "imm:ALOX5"),
    ("nat:Resveratrol_nat", "inhibits", "imm:PTGS2"),
    ("nat:Genistein", "inhibits", "imm:TBK1"),
    ("nat:Triptolide", "inhibits", "imm:TBK1"),
    ("nat:TanshinoneIIA", "inhibits", "imm:STAT4"),
    ("nat:GinkgolideB", "inhibits", "imm:NFATC1"),
    ("nat:Emetine", "inhibits", "imm:IRF7"),
    # Natural T-cell modulators
    ("nat:CBD", "inhibits", "imm:NFATC1"),
    ("nat:Andrographolide", "activates", "imm:FOXP3"),
    # Cytokine-level modulation
    ("nat:Forskolin", "inhibits", "imm:IL1B"),
    ("nat:Daidzein", "inhibits", "imm:TNFA"),
    # Metal bridges
    ("nat:Artemisinin", "inhibits", "imm:NLRP3"),
    ("nat:Colchicine", "inhibits", "imm:CASP1"),
    ("nat:Honokiol", "inhibits", "imm:STAT6"),
    ("nat:Magnolol", "inhibits", "imm:JAK3"),
]


# ---------------------------------------------------------------------------
# Public loader
# ---------------------------------------------------------------------------

def load_subset_b_data() -> WD4Data:
    """Load Subset B: Immunology (imm:) + Natural products (nat:).

    Returns:
        WD4Data with sparse and medium bridge configurations.
    """
    bio_nodes = [{"id": nid, "label": label, "qid": ""} for nid, label in _IMM_NODES]
    bio_edges = [{"source": s, "relation": r, "target": t} for s, r, t in _IMM_EDGES]
    chem_nodes = [{"id": nid, "label": label, "qid": ""} for nid, label in _NAT_NODES]
    chem_edges = [{"source": s, "relation": r, "target": t} for s, r, t in _NAT_EDGES]
    bridge_sparse = [{"source": s, "relation": r, "target": t}
                     for s, r, t in _BRIDGE_B_SPARSE]
    bridge_medium = [{"source": s, "relation": r, "target": t}
                     for s, r, t in _BRIDGE_B_MEDIUM]

    return WD4Data(
        bio_nodes=bio_nodes,
        bio_edges=bio_edges,
        chem_nodes=chem_nodes,
        chem_edges=chem_edges,
        bridge_edges_sparse=bridge_sparse,
        bridge_edges_medium=bridge_medium,
        source="subset_b",
    )
