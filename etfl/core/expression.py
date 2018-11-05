# -*- coding: utf-8 -*-
"""
.. module:: ETFL
   :platform: Unix, Windows
   :synopsis: Thermodynamics-based Flux Analysis

.. moduleauthor:: ETFL team

ME-related Reaction subclasses and methods definition


"""
from cobra import Reaction, Metabolite
from .rna import tRNA

from collections import defaultdict

def build_trna_charging(model, aa_dict,
                        atp='atp_c',
                        amp='amp_c',
                        ppi='ppi_c',
                        h2o='h2o_c',
                        h='h_c'):
    trna_dict = dict()
    for letter, aa_id in aa_dict.items():
        aa = model.metabolites.get_by_id(aa_id)

        rxn_id = 'trna_ch_{}'.format(aa.id)

        # charged_trna = Metabolite(name = 'Charged tRNA-{}'.format(aa.name),
        #                           id = 'trna_charged_{}'.format(aa.id),
        #                           compartment = aa.compartment)
        # uncharged_trna = Metabolite(name = 'Uncharged tRNA-{}'.format(aa.name),
        #                           id = 'trna_uncharged_{}'.format(aa.id),
        #                           compartment = aa.compartment)
        charging_rxn = Reaction(name='tRNA Charging of {}'.format(aa.name),
                                id= rxn_id)

        charged_trna = tRNA(aminoacid_id=aa.id,
                            charged = True,
                            name = aa.name)

        uncharged_trna = tRNA(aminoacid_id=aa.id,
                            charged = False,
                            name = aa.name)

        model.add_reactions([charging_rxn])

        # Trick in case two amino acids are linked to the same reaction. Example:
        # Cysteine and selenocysteine
        the_rxn = model.reactions.get_by_id(rxn_id)
        mets = {
                aa:-1,
                # uncharged_trna:-1,
                atp:-1,
                h2o:-2,
                # charged_trna:1,
                amp:1,
                ppi:1,
                h:2,
                }

        the_rxn.add_metabolites(mets)

        trna_dict[aa_id] = (charged_trna,uncharged_trna, charging_rxn)
    return trna_dict

def make_stoich_from_aa_sequence(sequence, aa_dict, trna_dict,
                                 gtp, gdp, pi, h2o, h):
    stoich = defaultdict(int)

    for letter in sequence:
        met_id = aa_dict[letter]
        charged_trna, uncharged_trna, _ = trna_dict[met_id]
        # stoich[met]-=1
        stoich[charged_trna] -= 1
        stoich[uncharged_trna] += 1
    stoich[gtp] = -2 * len(sequence)
    stoich[h2o] = -2 * len(sequence)
    stoich[gdp] = 2 * len(sequence)
    stoich[h] = 2 * len(sequence)
    stoich[pi] = 2 * len(sequence)
    return stoich

def make_stoich_from_nt_sequence(sequence, nt_dict, ppi):
    stoich = defaultdict(int)
    for letter in sequence:
        met_id = nt_dict[letter]
        stoich[met_id]-=1
    stoich[ppi] = len(sequence)
    return stoich

def degrade_peptide(peptide, aa_dict, h2o):
    sequence = peptide.peptide

    stoich = defaultdict(int)

    for letter in sequence:
        met_id = aa_dict[letter]
        stoich[met_id]+=1
    stoich[h2o] = -1 * len(sequence)

    return stoich

def degrade_mrna(mrna, nt_dict, h2o, h):
    sequence = mrna.rna

    stoich = defaultdict(int)

    for letter in sequence:
        met_id = nt_dict[letter]
        stoich[met_id]+=1
    stoich[h2o] = -1 * len(sequence)
    stoich[h] = 1 * len(sequence)

    return stoich