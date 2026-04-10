"""Subset C: Neuroscience bio (neu:) + Neuro-pharmacology chem (phar:).

Bio: Neurotransmitter synthesis, receptors, synaptic signaling, neurodegeneration.
Chem: Psychiatric drugs, neurotransmitters as pure chemistry, reaction types.
Bridge: Shared neurotransmitter molecules (Dopamine, Serotonin, GABA, Norepinephrine).

Designed for Run 013 cross-subset reproducibility test.
Entity prefixes: neu: (biology/neuroscience), phar: (chemistry/neuro-pharmacology).
No overlap with wikidata_phase4_loader.py bio:/chem: namespace.
"""

from __future__ import annotations

from src.data.wikidata_phase4_loader import WD4Data


# ---------------------------------------------------------------------------
# Bio nodes (neu: prefix)
# ---------------------------------------------------------------------------

_NEU_NODES: list[tuple[str, str]] = [
    # --- Neurotransmitter synthesis enzymes ---
    ("neu:TH", "Tyrosine hydroxylase"),
    ("neu:DDC", "DOPA decarboxylase"),
    ("neu:DBH", "Dopamine beta-hydroxylase"),
    ("neu:PNMT", "PNMT"),
    ("neu:TPH1", "Tryptophan hydroxylase 1"),
    ("neu:TPH2", "Tryptophan hydroxylase 2"),
    ("neu:AADC", "Aromatic L-amino acid decarboxylase"),
    ("neu:CHAT", "Choline acetyltransferase"),
    ("neu:GAD1", "Glutamate decarboxylase 1"),
    ("neu:GAD2", "Glutamate decarboxylase 2"),
    ("neu:MAOA", "MAO-A"),
    ("neu:MAOB", "MAO-B"),
    ("neu:ALDH2", "ALDH2"),
    ("neu:COMT", "COMT"),
    # --- Neurotransmitter transporters ---
    ("neu:DAT", "Dopamine transporter"),
    ("neu:NET", "Norepinephrine transporter"),
    ("neu:SERT", "Serotonin transporter"),
    ("neu:VMAT2", "VMAT2"),
    ("neu:VAChT", "Vesicular acetylcholine transporter"),
    ("neu:GAT1", "GABA transporter 1"),
    ("neu:GlyT1", "Glycine transporter 1"),
    # --- Dopamine receptors ---
    ("neu:DRD1", "Dopamine receptor D1"),
    ("neu:DRD2", "Dopamine receptor D2"),
    ("neu:DRD3", "Dopamine receptor D3"),
    ("neu:DRD4", "Dopamine receptor D4"),
    ("neu:DRD5", "Dopamine receptor D5"),
    # --- Serotonin receptors ---
    ("neu:HTR1A", "5-HT1A receptor"),
    ("neu:HTR1B", "5-HT1B receptor"),
    ("neu:HTR2A", "5-HT2A receptor"),
    ("neu:HTR2C", "5-HT2C receptor"),
    ("neu:HTR3A", "5-HT3A receptor"),
    ("neu:HTR4", "5-HT4 receptor"),
    # --- Glutamate receptors ---
    ("neu:GRIN1", "NMDA receptor NR1"),
    ("neu:GRIN2A", "NMDA receptor NR2A"),
    ("neu:GRIN2B", "NMDA receptor NR2B"),
    ("neu:GRIA1", "AMPA receptor GluA1"),
    ("neu:GRIA2", "AMPA receptor GluA2"),
    ("neu:GRM1", "mGluR1"),
    ("neu:GRM5", "mGluR5"),
    # --- GABA receptors ---
    ("neu:GABRA1", "GABA-A receptor alpha1"),
    ("neu:GABRA2", "GABA-A receptor alpha2"),
    ("neu:GABRB2", "GABA-A receptor beta2"),
    ("neu:GABRG2", "GABA-A receptor gamma2"),
    ("neu:GABABR1", "GABA-B receptor 1"),
    # --- Cholinergic receptors ---
    ("neu:CHRM1", "Muscarinic M1 receptor"),
    ("neu:CHRM2", "Muscarinic M2 receptor"),
    ("neu:CHRNA4", "nAChR alpha4"),
    ("neu:CHRNA7", "nAChR alpha7"),
    ("neu:CHRNB2", "nAChR beta2"),
    # --- Adrenergic receptors ---
    ("neu:ADRA1A", "Alpha-1A adrenergic receptor"),
    ("neu:ADRA2A", "Alpha-2A adrenergic receptor"),
    ("neu:ADRB1", "Beta-1 adrenergic receptor"),
    ("neu:ADRB2", "Beta-2 adrenergic receptor"),
    # --- Synaptic machinery ---
    ("neu:SNAP25", "SNAP-25"),
    ("neu:STX1A", "Syntaxin-1A"),
    ("neu:VAMP2", "VAMP2"),
    ("neu:NSF", "NSF"),
    ("neu:SYN1", "Synapsin-1"),
    ("neu:SYN2", "Synapsin-2"),
    ("neu:CAMK2A", "CaMKII alpha"),
    ("neu:CAMK4", "CaMKIV"),
    ("neu:CREB1", "CREB1"),
    ("neu:PPP1R1B", "DARPP-32"),
    # --- Neurotrophins / growth factors ---
    ("neu:BDNF", "BDNF"),
    ("neu:NTRK2", "TrkB"),
    ("neu:NGF", "NGF"),
    ("neu:NTRK1", "TrkA"),
    ("neu:GDNF", "GDNF"),
    ("neu:NTRK3", "TrkC"),
    # --- Neuropeptides ---
    ("neu:NPY", "Neuropeptide Y"),
    ("neu:VIP", "VIP"),
    ("neu:CALCA", "CGRP"),
    ("neu:TAC1", "Substance P"),
    ("neu:PENK", "Enkephalin"),
    ("neu:PDYN", "Dynorphin"),
    # --- Neurodegeneration proteins ---
    ("neu:SNCA", "Alpha-synuclein"),
    ("neu:LRRK2", "LRRK2"),
    ("neu:PARK2", "Parkin"),
    ("neu:PINK1", "PINK1"),
    ("neu:UCHL1", "UCH-L1"),
    ("neu:APP", "APP"),
    ("neu:BACE1", "BACE1"),
    ("neu:PSEN1", "Presenilin-1"),
    ("neu:MAPT", "Tau"),
    ("neu:HTT", "Huntingtin"),
    ("neu:ATXN1", "Ataxin-1"),
    ("neu:SOD1_neu", "SOD1-neu"),
    # --- Signaling cascades ---
    ("neu:PRKACA", "PKA catalytic alpha"),
    ("neu:PRKAR1A", "PKA regulatory Ialpha"),
    ("neu:PDE4D", "PDE4D"),
    ("neu:NRXN1", "Neurexin-1"),
    ("neu:NLGN1", "Neuroligin-1"),
    ("neu:SHANK3", "SHANK3"),
    ("neu:GSK3A", "GSK-3alpha"),
    ("neu:CDK5", "CDK5"),
    # --- Ion channels ---
    ("neu:SCN1A", "Nav1.1"),
    ("neu:SCN2A", "Nav1.2"),
    ("neu:KCNQ2", "Kv7.2"),
    ("neu:KCNQ3", "Kv7.3"),
    ("neu:HCN1", "HCN1"),
    ("neu:HCN2", "HCN2"),
    ("neu:CACNA1C", "Cav1.2"),
    ("neu:KCNA1", "Kv1.1"),
    # --- Structural / glia ---
    ("neu:MAP2", "MAP2"),
    ("neu:TUBB3", "Tubulin beta-3"),
    ("neu:NEFH", "Neurofilament heavy"),
    ("neu:GFAP", "GFAP"),
    ("neu:AQP4", "Aquaporin-4"),
    ("neu:MBP", "Myelin basic protein"),
    ("neu:CX3CR1", "CX3CR1"),
    ("neu:TMEM119", "TMEM119"),
    # --- Neurotransmitter metabolites ---
    ("neu:m_Dopamine", "Dopamine"),
    ("neu:m_Serotonin", "Serotonin"),
    ("neu:m_GABA", "GABA"),
    ("neu:m_Glutamate", "Glutamate"),
    ("neu:m_Norepinephrine", "Norepinephrine"),
    ("neu:m_Acetylcholine", "Acetylcholine"),
    ("neu:m_Glycine", "Glycine"),
    ("neu:m_Adenosine", "Adenosine"),
    ("neu:m_DOPAC", "DOPAC"),
    ("neu:m_HVA", "Homovanillic acid"),
    ("neu:m_5HIAA", "5-HIAA"),
    # --- Genes ---
    ("neu:g_TH", "TH gene"),
    ("neu:g_SNCA", "SNCA gene"),
    ("neu:g_BDNF", "BDNF gene"),
    ("neu:g_DRD2", "DRD2 gene"),
    ("neu:g_HTT", "HTT gene"),
    ("neu:g_MAPT", "MAPT gene"),
    ("neu:g_LRRK2", "LRRK2 gene"),
    ("neu:g_PARK2", "PARK2 gene"),
    ("neu:g_APP", "APP gene"),
    ("neu:g_BACE1", "BACE1 gene"),
    ("neu:g_MAOA", "MAOA gene"),
    ("neu:g_COMT", "COMT gene"),
    # --- Diseases ---
    ("neu:d_Epilepsy", "Epilepsy"),
    ("neu:d_Schizophrenia", "Schizophrenia"),
    ("neu:d_Depression", "Major depression"),
    ("neu:d_BipolarDisorder", "Bipolar disorder"),
    ("neu:d_ALS", "ALS"),
    ("neu:d_Huntington", "Huntington disease"),
    ("neu:d_Narcolepsy", "Narcolepsy"),
    ("neu:d_ADHD", "ADHD"),
    ("neu:d_Autism", "Autism spectrum disorder"),
    # --- Processes ---
    ("neu:p_SynapticTransmission", "Synaptic transmission"),
    ("neu:p_LTP", "Long-term potentiation"),
    ("neu:p_LTD", "Long-term depression"),
    ("neu:p_Neurogenesis", "Neurogenesis"),
    ("neu:p_Myelination", "Myelination"),
    ("neu:p_NeuroinflammationNeuro", "Neuroinflammation"),
    ("neu:p_AxonGrowth", "Axon growth"),
    ("neu:p_Apoptosis_neu", "Neuronal apoptosis"),
]

# ---------------------------------------------------------------------------
# Bio edges (neu:)
# ---------------------------------------------------------------------------

_NEU_EDGES: list[tuple[str, str, str]] = [
    # Dopamine synthesis
    ("neu:g_TH", "encodes", "neu:TH"),
    ("neu:TH", "catalyzes", "neu:m_Dopamine"),
    ("neu:TH", "produces", "neu:m_Dopamine"),
    ("neu:DDC", "catalyzes", "neu:m_Dopamine"),
    ("neu:DBH", "catalyzes", "neu:m_Dopamine"),
    ("neu:DBH", "produces", "neu:m_Norepinephrine"),
    ("neu:PNMT", "catalyzes", "neu:m_Norepinephrine"),
    ("neu:m_Dopamine", "is_substrate_of", "neu:MAOA"),
    ("neu:MAOA", "catalyzes", "neu:m_Dopamine"),
    ("neu:MAOA", "produces", "neu:m_DOPAC"),
    ("neu:g_MAOA", "encodes", "neu:MAOA"),
    ("neu:COMT", "catalyzes", "neu:m_DOPAC"),
    ("neu:COMT", "produces", "neu:m_HVA"),
    ("neu:g_COMT", "encodes", "neu:COMT"),
    # Serotonin synthesis
    ("neu:TPH1", "produces", "neu:m_Serotonin"),
    ("neu:TPH2", "produces", "neu:m_Serotonin"),
    ("neu:AADC", "catalyzes", "neu:m_Serotonin"),
    ("neu:MAOA", "catalyzes", "neu:m_Serotonin"),
    ("neu:MAOA", "produces", "neu:m_5HIAA"),
    # GABA synthesis
    ("neu:GAD1", "produces", "neu:m_GABA"),
    ("neu:GAD2", "produces", "neu:m_GABA"),
    ("neu:m_Glutamate", "is_substrate_of", "neu:GAD1"),
    # Acetylcholine synthesis
    ("neu:CHAT", "produces", "neu:m_Acetylcholine"),
    # Neurotransmitter transport
    ("neu:DAT", "facilitates", "neu:m_Dopamine"),
    ("neu:NET", "facilitates", "neu:m_Norepinephrine"),
    ("neu:SERT", "facilitates", "neu:m_Serotonin"),
    ("neu:VMAT2", "facilitates", "neu:m_Dopamine"),
    ("neu:VAChT", "facilitates", "neu:m_Acetylcholine"),
    ("neu:GAT1", "facilitates", "neu:m_GABA"),
    ("neu:GlyT1", "facilitates", "neu:m_Glycine"),
    # Dopamine receptor signaling
    ("neu:m_Dopamine", "activates", "neu:DRD1"),
    ("neu:m_Dopamine", "activates", "neu:DRD2"),
    ("neu:m_Dopamine", "activates", "neu:DRD3"),
    ("neu:DRD1", "activates", "neu:PRKACA"),
    ("neu:DRD2", "inhibits", "neu:PRKACA"),
    ("neu:DRD2", "activates", "neu:PPP1R1B"),
    ("neu:PPP1R1B", "inhibits", "neu:CAMK2A"),
    ("neu:PRKACA", "activates", "neu:CREB1"),
    ("neu:PRKACA", "inhibits", "neu:PDE4D"),
    ("neu:PDE4D", "inhibits", "neu:PRKACA"),
    ("neu:PRKAR1A", "inhibits", "neu:PRKACA"),
    # Serotonin receptor signaling
    ("neu:m_Serotonin", "activates", "neu:HTR1A"),
    ("neu:m_Serotonin", "activates", "neu:HTR2A"),
    ("neu:m_Serotonin", "activates", "neu:HTR3A"),
    ("neu:HTR1A", "inhibits", "neu:PRKACA"),
    ("neu:HTR2A", "activates", "neu:CAMK2A"),
    ("neu:HTR2C", "inhibits", "neu:PRKACA"),
    # NMDA / AMPA signaling
    ("neu:m_Glutamate", "activates", "neu:GRIN1"),
    ("neu:m_Glutamate", "activates", "neu:GRIA1"),
    ("neu:m_Glutamate", "activates", "neu:GRM5"),
    ("neu:GRIN1", "activates", "neu:CAMK2A"),
    ("neu:GRIN2B", "activates", "neu:CAMK2A"),
    ("neu:CAMK2A", "activates", "neu:CREB1"),
    ("neu:CAMK4", "activates", "neu:CREB1"),
    ("neu:CAMK2A", "activates", "neu:p_LTP"),
    ("neu:GRM5", "activates", "neu:p_LTD"),
    # GABA signaling
    ("neu:m_GABA", "activates", "neu:GABRA1"),
    ("neu:m_GABA", "activates", "neu:GABRB2"),
    ("neu:m_Glycine", "activates", "neu:GABRA2"),
    ("neu:GABRA1", "inhibits", "neu:p_SynapticTransmission"),
    # Cholinergic signaling
    ("neu:m_Acetylcholine", "activates", "neu:CHRM1"),
    ("neu:m_Acetylcholine", "activates", "neu:CHRNA4"),
    ("neu:m_Acetylcholine", "activates", "neu:CHRNA7"),
    ("neu:CHRM1", "activates", "neu:CAMK2A"),
    ("neu:CHRNA7", "activates", "neu:CAMK2A"),
    # Adrenergic signaling
    ("neu:m_Norepinephrine", "activates", "neu:ADRB1"),
    ("neu:m_Norepinephrine", "activates", "neu:ADRA2A"),
    ("neu:ADRB1", "activates", "neu:PRKACA"),
    ("neu:ADRA2A", "inhibits", "neu:PRKACA"),
    # BDNF signaling
    ("neu:g_BDNF", "encodes", "neu:BDNF"),
    ("neu:BDNF", "activates", "neu:NTRK2"),
    ("neu:NTRK2", "activates", "neu:CAMK2A"),
    ("neu:NTRK2", "activates", "neu:CREB1"),
    ("neu:CREB1", "activates", "neu:BDNF"),
    ("neu:CREB1", "activates", "neu:p_Neurogenesis"),
    ("neu:NGF", "activates", "neu:NTRK1"),
    ("neu:NTRK1", "activates", "neu:CAMK2A"),
    ("neu:GDNF", "activates", "neu:NTRK3"),
    # Neurodegeneration
    ("neu:g_SNCA", "encodes", "neu:SNCA"),
    ("neu:SNCA", "inhibits", "neu:p_SynapticTransmission"),
    ("neu:LRRK2", "inhibits", "neu:PARK2"),
    ("neu:PINK1", "activates", "neu:PARK2"),
    ("neu:g_LRRK2", "encodes", "neu:LRRK2"),
    ("neu:g_PARK2", "encodes", "neu:PARK2"),
    ("neu:PARK2", "activates", "neu:p_Apoptosis_neu"),
    ("neu:UCHL1", "inhibits", "neu:p_Apoptosis_neu"),
    ("neu:g_APP", "encodes", "neu:APP"),
    ("neu:g_BACE1", "encodes", "neu:BACE1"),
    ("neu:BACE1", "catalyzes", "neu:APP"),
    ("neu:PSEN1", "activates", "neu:BACE1"),
    ("neu:MAPT", "inhibits", "neu:p_AxonGrowth"),
    ("neu:CDK5", "activates", "neu:MAPT"),
    ("neu:GSK3A", "activates", "neu:MAPT"),
    ("neu:g_MAPT", "encodes", "neu:MAPT"),
    ("neu:g_HTT", "encodes", "neu:HTT"),
    ("neu:HTT", "inhibits", "neu:p_AxonGrowth"),
    # Synaptic proteins
    ("neu:SNAP25", "facilitates", "neu:p_SynapticTransmission"),
    ("neu:STX1A", "facilitates", "neu:p_SynapticTransmission"),
    ("neu:VAMP2", "facilitates", "neu:p_SynapticTransmission"),
    ("neu:NSF", "activates", "neu:SNAP25"),
    ("neu:SYN1", "facilitates", "neu:p_SynapticTransmission"),
    ("neu:NRXN1", "activates", "neu:p_SynapticTransmission"),
    ("neu:NLGN1", "activates", "neu:p_SynapticTransmission"),
    ("neu:SHANK3", "activates", "neu:p_LTP"),
    # Ion channels
    ("neu:SCN1A", "facilitates", "neu:p_SynapticTransmission"),
    ("neu:CACNA1C", "facilitates", "neu:p_SynapticTransmission"),
    ("neu:KCNQ2", "inhibits", "neu:p_SynapticTransmission"),
    ("neu:KCNQ3", "inhibits", "neu:p_SynapticTransmission"),
    ("neu:HCN1", "facilitates", "neu:p_SynapticTransmission"),
    # Disease associations
    ("neu:SNCA", "associated_with", "neu:d_Depression"),
    ("neu:DRD2", "associated_with", "neu:d_Schizophrenia"),
    ("neu:HTR2A", "associated_with", "neu:d_Schizophrenia"),
    ("neu:SCN1A", "associated_with", "neu:d_Epilepsy"),
    ("neu:KCNQ2", "associated_with", "neu:d_Epilepsy"),
    ("neu:MAPT", "associated_with", "neu:d_ALS"),
    ("neu:HTT", "associated_with", "neu:d_Huntington"),
    ("neu:GRIN2B", "associated_with", "neu:d_Autism"),
    ("neu:DAT", "associated_with", "neu:d_ADHD"),
    # Structural
    ("neu:MBP", "activates", "neu:p_Myelination"),
    ("neu:GFAP", "activates", "neu:p_NeuroinflammationNeuro"),
    ("neu:AQP4", "activates", "neu:p_NeuroinflammationNeuro"),
    ("neu:MAP2", "activates", "neu:p_AxonGrowth"),
    # Neuropeptide actions
    ("neu:NPY", "inhibits", "neu:PRKACA"),
    ("neu:TAC1", "activates", "neu:p_NeuroinflammationNeuro"),
    ("neu:BDNF", "activates", "neu:p_AxonGrowth"),
    ("neu:GDNF", "activates", "neu:p_Neurogenesis"),
    # Adenosine signaling
    ("neu:m_Adenosine", "inhibits", "neu:DRD1"),
    ("neu:m_Adenosine", "inhibits", "neu:p_SynapticTransmission"),
]

# ---------------------------------------------------------------------------
# Chem nodes (phar: prefix)
# ---------------------------------------------------------------------------

_PHAR_NODES: list[tuple[str, str]] = [
    # --- SSRIs ---
    ("phar:Fluoxetine", "Fluoxetine"),
    ("phar:Sertraline", "Sertraline"),
    ("phar:Paroxetine", "Paroxetine"),
    ("phar:Citalopram", "Citalopram"),
    ("phar:Escitalopram", "Escitalopram"),
    ("phar:Fluvoxamine", "Fluvoxamine"),
    # --- SNRIs ---
    ("phar:Venlafaxine", "Venlafaxine"),
    ("phar:Duloxetine", "Duloxetine"),
    ("phar:Desvenlafaxine", "Desvenlafaxine"),
    ("phar:Milnacipran", "Milnacipran"),
    # --- TCAs ---
    ("phar:Amitriptyline", "Amitriptyline"),
    ("phar:Nortriptyline", "Nortriptyline"),
    ("phar:Imipramine", "Imipramine"),
    ("phar:Clomipramine", "Clomipramine"),
    ("phar:Desipramine", "Desipramine"),
    # --- MAOIs ---
    ("phar:Phenelzine", "Phenelzine"),
    ("phar:Tranylcypromine", "Tranylcypromine"),
    ("phar:Selegiline", "Selegiline"),
    ("phar:Moclobemide", "Moclobemide"),
    # --- Antipsychotics (typical) ---
    ("phar:Haloperidol", "Haloperidol"),
    ("phar:Chlorpromazine", "Chlorpromazine"),
    ("phar:Fluphenazine", "Fluphenazine"),
    ("phar:Thioridazine", "Thioridazine"),
    ("phar:Perphenazine", "Perphenazine"),
    # --- Antipsychotics (atypical) ---
    ("phar:Clozapine", "Clozapine"),
    ("phar:Risperidone", "Risperidone"),
    ("phar:Olanzapine", "Olanzapine"),
    ("phar:Quetiapine", "Quetiapine"),
    ("phar:Ziprasidone", "Ziprasidone"),
    ("phar:Aripiprazole", "Aripiprazole"),
    ("phar:Amisulpride", "Amisulpride"),
    # --- Benzodiazepines ---
    ("phar:Diazepam", "Diazepam"),
    ("phar:Lorazepam", "Lorazepam"),
    ("phar:Alprazolam", "Alprazolam"),
    ("phar:Clonazepam", "Clonazepam"),
    ("phar:Midazolam", "Midazolam"),
    ("phar:Nitrazepam", "Nitrazepam"),
    # --- Anticonvulsants ---
    ("phar:ValproicAcid", "Valproic acid"),
    ("phar:Phenytoin", "Phenytoin"),
    ("phar:Carbamazepine", "Carbamazepine"),
    ("phar:Lamotrigine", "Lamotrigine"),
    ("phar:Levetiracetam", "Levetiracetam"),
    ("phar:Topiramate", "Topiramate"),
    ("phar:Gabapentin", "Gabapentin"),
    ("phar:Pregabalin", "Pregabalin"),
    # --- Anti-Parkinson ---
    ("phar:Levodopa", "Levodopa"),
    ("phar:Carbidopa", "Carbidopa"),
    ("phar:Pramipexole", "Pramipexole"),
    ("phar:Ropinirole", "Ropinirole"),
    ("phar:Rasagiline", "Rasagiline"),
    ("phar:Amantadine", "Amantadine"),
    # --- Anti-Alzheimer ---
    ("phar:Donepezil", "Donepezil"),
    ("phar:Rivastigmine", "Rivastigmine"),
    ("phar:Galantamine", "Galantamine"),
    ("phar:Memantine", "Memantine"),
    ("phar:Tacrine", "Tacrine"),
    # --- CNS stimulants ---
    ("phar:Methylphenidate", "Methylphenidate"),
    ("phar:Amphetamine", "Amphetamine"),
    ("phar:Modafinil", "Modafinil"),
    ("phar:Atomoxetine", "Atomoxetine"),
    ("phar:Lisdexamfetamine", "Lisdexamfetamine"),
    # --- Neurotransmitters as pure chemicals ---
    ("phar:Dopamine", "Dopamine"),
    ("phar:Serotonin", "Serotonin"),
    ("phar:GABA_chem", "GABA"),
    ("phar:Glutamate_chem", "Glutamate"),
    ("phar:Norepinephrine", "Norepinephrine"),
    ("phar:Glycine_chem", "Glycine"),
    ("phar:Adenosine_chem", "Adenosine"),
    ("phar:Acetylcholine_chem", "Acetylcholine"),
    # --- Precursors ---
    ("phar:Tyrosine_phar", "L-Tyrosine"),
    ("phar:Tryptophan_phar", "L-Tryptophan"),
    ("phar:Glutamine_phar", "L-Glutamine"),
    ("phar:Choline_phar", "Choline"),
    # --- Chemical reactions (phar) ---
    ("phar:r_Hydroxylation", "Hydroxylation reaction"),
    ("phar:r_Methylation", "Methylation reaction"),
    ("phar:r_Oxidation_phar", "Oxidation reaction"),
    ("phar:r_Deamination", "Deamination reaction"),
    ("phar:r_Glucuronidation", "Glucuronidation reaction"),
    ("phar:r_Decarboxylation_phar", "Decarboxylation reaction"),
    # --- Functional groups (phar) ---
    ("phar:fg_Catechol", "Catechol group"),
    ("phar:fg_Indole", "Indole group"),
    ("phar:fg_Phenethylamine", "Phenethylamine scaffold"),
    ("phar:fg_Benzodiazepine", "Benzodiazepine scaffold"),
    ("phar:fg_Piperidine", "Piperidine ring"),
    ("phar:fg_Phenothiazine", "Phenothiazine scaffold"),
    ("phar:fg_Butyrophenone", "Butyrophenone scaffold"),
]

# ---------------------------------------------------------------------------
# Chem edges (phar:)
# ---------------------------------------------------------------------------

_PHAR_EDGES: list[tuple[str, str, str]] = [
    # SSRI mechanism
    ("phar:Fluoxetine", "inhibits", "phar:r_Oxidation_phar"),
    ("phar:Sertraline", "inhibits", "phar:r_Oxidation_phar"),
    ("phar:Paroxetine", "inhibits", "phar:r_Methylation"),
    ("phar:Citalopram", "inhibits", "phar:r_Oxidation_phar"),
    ("phar:Escitalopram", "inhibits", "phar:r_Oxidation_phar"),
    ("phar:Fluvoxamine", "inhibits", "phar:r_Oxidation_phar"),
    # SNRI mechanism
    ("phar:Venlafaxine", "inhibits", "phar:r_Hydroxylation"),
    ("phar:Duloxetine", "inhibits", "phar:r_Hydroxylation"),
    ("phar:Desvenlafaxine", "inhibits", "phar:r_Hydroxylation"),
    # TCA mechanism
    ("phar:Amitriptyline", "inhibits", "phar:r_Methylation"),
    ("phar:Nortriptyline", "inhibits", "phar:r_Methylation"),
    ("phar:Imipramine", "inhibits", "phar:r_Methylation"),
    ("phar:Clomipramine", "inhibits", "phar:r_Oxidation_phar"),
    # MAOI mechanism
    ("phar:Phenelzine", "inhibits", "phar:r_Deamination"),
    ("phar:Tranylcypromine", "inhibits", "phar:r_Deamination"),
    ("phar:Selegiline", "inhibits", "phar:r_Deamination"),
    ("phar:Moclobemide", "inhibits", "phar:r_Deamination"),
    # Antipsychotic chemistry
    ("phar:Haloperidol", "contains", "phar:fg_Butyrophenone"),
    ("phar:Chlorpromazine", "contains", "phar:fg_Phenothiazine"),
    ("phar:Fluphenazine", "contains", "phar:fg_Phenothiazine"),
    ("phar:Thioridazine", "contains", "phar:fg_Phenothiazine"),
    ("phar:Risperidone", "contains", "phar:fg_Piperidine"),
    ("phar:Olanzapine", "inhibits", "phar:r_Hydroxylation"),
    ("phar:Quetiapine", "inhibits", "phar:r_Glucuronidation"),
    ("phar:Clozapine", "inhibits", "phar:r_Hydroxylation"),
    ("phar:Aripiprazole", "inhibits", "phar:r_Deamination"),
    # Benzodiazepine chemistry
    ("phar:Diazepam", "contains", "phar:fg_Benzodiazepine"),
    ("phar:Lorazepam", "contains", "phar:fg_Benzodiazepine"),
    ("phar:Alprazolam", "contains", "phar:fg_Benzodiazepine"),
    ("phar:Clonazepam", "contains", "phar:fg_Benzodiazepine"),
    ("phar:Midazolam", "contains", "phar:fg_Benzodiazepine"),
    ("phar:Diazepam", "undergoes", "phar:r_Glucuronidation"),
    ("phar:Lorazepam", "undergoes", "phar:r_Glucuronidation"),
    # Anticonvulsant chemistry
    ("phar:ValproicAcid", "inhibits", "phar:r_Deamination"),
    ("phar:Phenytoin", "inhibits", "phar:r_Hydroxylation"),
    ("phar:Carbamazepine", "undergoes", "phar:r_Hydroxylation"),
    ("phar:Lamotrigine", "undergoes", "phar:r_Glucuronidation"),
    ("phar:Topiramate", "inhibits", "phar:r_Glucuronidation"),
    # Anti-Parkinson chemistry
    ("phar:Levodopa", "undergoes", "phar:r_Decarboxylation_phar"),
    ("phar:Levodopa", "is_precursor_of", "phar:Dopamine"),
    ("phar:Carbidopa", "inhibits", "phar:r_Decarboxylation_phar"),
    ("phar:Rasagiline", "inhibits", "phar:r_Deamination"),
    ("phar:Amantadine", "inhibits", "phar:r_Methylation"),
    # Anti-Alzheimer chemistry
    ("phar:Donepezil", "inhibits", "phar:r_Hydroxylation"),
    ("phar:Rivastigmine", "inhibits", "phar:r_Glucuronidation"),
    ("phar:Galantamine", "inhibits", "phar:r_Hydroxylation"),
    ("phar:Memantine", "inhibits", "phar:r_Deamination"),
    ("phar:Tacrine", "inhibits", "phar:r_Hydroxylation"),
    # Neurotransmitter chemistry
    ("phar:Dopamine", "contains", "phar:fg_Catechol"),
    ("phar:Dopamine", "undergoes", "phar:r_Hydroxylation"),
    ("phar:Dopamine", "undergoes", "phar:r_Methylation"),
    ("phar:Serotonin", "contains", "phar:fg_Indole"),
    ("phar:Serotonin", "undergoes", "phar:r_Deamination"),
    ("phar:Norepinephrine", "contains", "phar:fg_Catechol"),
    ("phar:Norepinephrine", "undergoes", "phar:r_Methylation"),
    ("phar:Norepinephrine", "undergoes", "phar:r_Hydroxylation"),
    ("phar:GABA_chem", "undergoes", "phar:r_Deamination"),
    ("phar:Glutamate_chem", "undergoes", "phar:r_Decarboxylation_phar"),
    ("phar:Glutamate_chem", "is_precursor_of", "phar:GABA_chem"),
    ("phar:Glycine_chem", "undergoes", "phar:r_Deamination"),
    ("phar:Adenosine_chem", "undergoes", "phar:r_Deamination"),
    ("phar:Acetylcholine_chem", "undergoes", "phar:r_Glucuronidation"),
    ("phar:Dopamine", "contains", "phar:fg_Phenethylamine"),
    ("phar:Serotonin", "contains", "phar:fg_Phenethylamine"),
    ("phar:Norepinephrine", "contains", "phar:fg_Phenethylamine"),
    # Precursor chemistry
    ("phar:Tyrosine_phar", "is_precursor_of", "phar:Dopamine"),
    ("phar:Tyrosine_phar", "undergoes", "phar:r_Hydroxylation"),
    ("phar:Tryptophan_phar", "is_precursor_of", "phar:Serotonin"),
    ("phar:Tryptophan_phar", "contains", "phar:fg_Indole"),
    ("phar:Glutamine_phar", "is_precursor_of", "phar:Glutamate_chem"),
    ("phar:Choline_phar", "is_precursor_of", "phar:Acetylcholine_chem"),
    # Stimulant chemistry
    ("phar:Methylphenidate", "inhibits", "phar:r_Deamination"),
    ("phar:Amphetamine", "contains", "phar:fg_Phenethylamine"),
    ("phar:Amphetamine", "inhibits", "phar:r_Deamination"),
    ("phar:Atomoxetine", "inhibits", "phar:r_Hydroxylation"),
    # Functional group reactions
    ("phar:r_Hydroxylation", "produces", "phar:fg_Catechol"),
    ("phar:r_Deamination", "produces", "phar:fg_Phenethylamine"),
    ("phar:r_Methylation", "produces", "phar:fg_Piperidine"),
]

# ---------------------------------------------------------------------------
# Bridge edges (neu: ↔ phar:)
# ---------------------------------------------------------------------------

_BRIDGE_C_SPARSE: list[tuple[str, str, str]] = [
    # Shared neurotransmitter molecules (bio metabolite = chem compound)
    ("neu:m_Dopamine", "same_entity_as", "phar:Dopamine"),
    ("neu:m_Serotonin", "same_entity_as", "phar:Serotonin"),
    ("neu:m_GABA", "same_entity_as", "phar:GABA_chem"),
    ("neu:m_Norepinephrine", "same_entity_as", "phar:Norepinephrine"),
    ("neu:m_Glutamate", "same_entity_as", "phar:Glutamate_chem"),
    ("neu:m_Adenosine", "same_entity_as", "phar:Adenosine_chem"),
    # Drug-receptor bridges (phar drug → neu receptor)
    ("phar:Haloperidol", "inhibits", "neu:DRD2"),
    ("phar:Fluoxetine", "inhibits", "neu:SERT"),
    ("phar:Memantine", "inhibits", "neu:GRIN1"),
    ("phar:Diazepam", "activates", "neu:GABRA1"),
    ("phar:Donepezil", "inhibits", "neu:MAOA"),
    ("phar:Levodopa", "activates", "neu:TH"),
]

_BRIDGE_C_MEDIUM: list[tuple[str, str, str]] = list(_BRIDGE_C_SPARSE) + [
    # More neurotransmitter bridges
    ("neu:m_Acetylcholine", "same_entity_as", "phar:Acetylcholine_chem"),
    ("neu:m_Glycine", "same_entity_as", "phar:Glycine_chem"),
    # More drug-receptor bridges
    ("phar:Risperidone", "inhibits", "neu:HTR2A"),
    ("phar:Clozapine", "inhibits", "neu:HTR2A"),
    ("phar:Aripiprazole", "activates", "neu:DRD2"),
    ("phar:Sertraline", "inhibits", "neu:SERT"),
    ("phar:Paroxetine", "inhibits", "neu:SERT"),
    ("phar:Venlafaxine", "inhibits", "neu:NET"),
    ("phar:Duloxetine", "inhibits", "neu:NET"),
    ("phar:Selegiline", "inhibits", "neu:MAOB"),
    ("phar:Rasagiline", "inhibits", "neu:MAOB"),
    ("phar:Phenelzine", "inhibits", "neu:MAOA"),
    ("phar:Moclobemide", "inhibits", "neu:MAOA"),
    ("phar:Pramipexole", "activates", "neu:DRD3"),
    ("phar:Ropinirole", "activates", "neu:DRD3"),
    ("phar:Carbidopa", "inhibits", "neu:DDC"),
    ("phar:Galantamine", "activates", "neu:CHRNA4"),
    ("phar:Lorazepam", "activates", "neu:GABRB2"),
    ("phar:Pregabalin", "inhibits", "neu:CACNA1C"),
    ("phar:Gabapentin", "inhibits", "neu:CACNA1C"),
]


# ---------------------------------------------------------------------------
# Public loader
# ---------------------------------------------------------------------------

def load_subset_c_data() -> WD4Data:
    """Load Subset C: Neuroscience (neu:) + Neuro-pharmacology (phar:).

    Returns:
        WD4Data with sparse and medium bridge configurations.
    """
    bio_nodes = [{"id": nid, "label": label, "qid": ""} for nid, label in _NEU_NODES]
    bio_edges = [{"source": s, "relation": r, "target": t} for s, r, t in _NEU_EDGES]
    chem_nodes = [{"id": nid, "label": label, "qid": ""} for nid, label in _PHAR_NODES]
    chem_edges = [{"source": s, "relation": r, "target": t} for s, r, t in _PHAR_EDGES]
    bridge_sparse = [{"source": s, "relation": r, "target": t}
                     for s, r, t in _BRIDGE_C_SPARSE]
    bridge_medium = [{"source": s, "relation": r, "target": t}
                     for s, r, t in _BRIDGE_C_MEDIUM]

    return WD4Data(
        bio_nodes=bio_nodes,
        bio_edges=bio_edges,
        chem_nodes=chem_nodes,
        chem_edges=chem_edges,
        bridge_edges_sparse=bridge_sparse,
        bridge_edges_medium=bridge_medium,
        source="subset_c",
    )
