#! /usr/bin/env python
# -*- coding: utf-8 -*-


# OpenFisca -- A versatile microsimulation software
# By: OpenFisca Team <contact@openfisca.fr>
#
# Copyright (C) 2011, 2012, 2013, 2014, 2015 OpenFisca Team
# https://github.com/openfisca
#
# This file is part of OpenFisca.
#
# OpenFisca is free software; you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# OpenFisca is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import logging
from pandas import concat, DataFrame


from openfisca_france_data.temporary import TemporaryStore
from openfisca_france_data.input_data_builders.build_openfisca_survey_data.utils import assert_dtype

log = logging.getLogger(__name__)

# Retreives the families
# Creates 'idfam' and 'quifam' variables


def control_04(dataframe, base):
    log.info(u"longueur de la dataframe après opération :".format(len(dataframe.index)))
    log.info(u"contrôle des doublons : il y a {} individus en double".format(any(dataframe.duplicated(cols='noindiv'))))
    log.info(u"contrôle des colonnes : il y a {} colonnes".format(len(dataframe.columns)))
    log.info(u"Il y a {} de familles différentes".format(len(set(dataframe.noifam.values))))
    log.info(u"contrôle: {} noifam are NaN:".format(len(dataframe[dataframe['noifam'].isnull()])))
    log.info(u"{} lignes dans dataframe vs {} lignes dans base".format(len(dataframe.index), len(base.index)))
    assert len(dataframe.index) <= len(base.index), u"dataframe has too many rows compared to base"


def subset_base(base, famille):
    """
    Generates a dataframe containing the values of base that are not already in famille
    """
    return base[~(base.noindiv.isin(famille.noindiv.values))].copy()


def famille(year = 2006):

    temporary_store = TemporaryStore.create(file_name = "erfs")

    log.info('step_04_famille: construction de la table famille')

    # On suit la méthode décrite dans le Guide ERF_2002_rétropolée page 135
    # TODO: extraire ces valeurs d'un fichier de paramètres de législation
    if year == 2006:
        smic = 1254
    elif year == 2007:
        smic = 1280
    elif year == 2008:
        smic = 1308
    elif year == 2009:
        smic = 1337
    else:
        log.info("smic non défini")

    # TODO check if we can remove acteu forter etc since dealt with in 01_pre_proc

    log.info('Etape 1 : préparation de base')
    log.info('    1.1 : récupération de indivi')
    indivi = temporary_store['indivim_{}'.format(year)]

    indivi['year'] = year
    indivi["noidec"] = indivi["declar1"].str[0:2].copy()  # Not converted to int because some NaN are present
    indivi["agepf"] = (
        (indivi.naim < 7) * (indivi.year - indivi.naia)
        + (indivi.naim >= 7) * (indivi.year - indivi.naia - 1)
        ).astype(object)  # TODO: naia has some NaN but naim do not and then should be an int

    indivi = indivi[~(
        (indivi.lien == 6) & (indivi.agepf < 16) & (indivi.quelfic == "EE")
        )].copy()

    assert_dtype(indivi.year, "int64")
    for series_name in ['agepf', 'noidec']:  # integer with NaN
        assert_dtype(indivi[series_name], "object")

    log.info('    1.2 : récupération des enfants à naître')
    individual_variables = [
        'acteu',
        'actrec',
        'agepf',
        'agepr',
        'cohab',
        'contra',
        'declar1',
        'forter',
        'ident',
        'lien',
        'lpr',
        'mrec',
        'naia',
        'naim',
        'noi',
        'noicon',
        'noidec',
        'noimer',
        'noindiv',
        'noiper',
        'persfip',
        'quelfic',
        'retrai',
        'rga',
        'rstg',
        'sexe',
        'stc',
        'titc',
        'year',
        'ztsai',
        ]
    enfants_a_naitre = temporary_store['enfants_a_naitre_{}'.format(year)][individual_variables].copy()
    enfants_a_naitre.drop_duplicates('noindiv', inplace = True)
    log.info(u""""
    Il y a {} enfants à naitre avant de retirer ceux qui ne sont pas enfants
    de la personne de référence
    """.format(len(enfants_a_naitre.index)))
    enfants_a_naitre = enfants_a_naitre[enfants_a_naitre.lpr == 3].copy()
    enfants_a_naitre = enfants_a_naitre[~(enfants_a_naitre.noindiv.isin(indivi.noindiv.values))].copy()
    log.info(u""""
    Il y a {} enfants à naitre après avoir retiré ceux qui ne sont pas enfants
    de la personne de référence
    """.format(len(enfants_a_naitre.index)))
    # PB with vars "agepf"  "noidec" "year"  NOTE: quels problèmes ? JS
    log.info(u"    1.3 : création de la base complète")
    base = concat([indivi, enfants_a_naitre])
    log.info(u"base contient {} lignes ".format(len(base.index)))
    base['noindiv'] = (100 * base.ident + base['noi']).astype(int)
    base['m15'] = base.agepf < 16
    base['p16m20'] = (base.agepf >= 16) & (base.agepf <= 20)
    base['p21'] = base.agepf >= 21
    base['ztsai'].fillna(0, inplace = True)
    base['smic55'] = base['ztsai'] >= (smic * 12 * 0.55)  # 55% du smic mensuel brut
    base['famille'] = 0
    base['kid'] = False
    for series_name in ['kid', 'm15', 'p16m20', 'p21', 'smic55']:
        assert_dtype(base[series_name], "bool")
    assert_dtype(base.famille, "int")
    # TODO: remove or clean from NA assert_dtype(base.ztsai, "int")

    log.info(u"Etape 2 : On cherche les enfants ayant père et/ou mère")
    personne_de_reference = base[['ident', 'noi']][base.lpr == 1].copy()
    personne_de_reference['noifam'] = (100 * personne_de_reference.ident + personne_de_reference['noi']).astype(int)
    personne_de_reference = personne_de_reference[['ident', 'noifam']].copy()
    log.info(u"length personne_de_reference : {}".format(len(personne_de_reference.index)))
    nof01 = base[(base.lpr.isin([1, 2])) | ((base.lpr == 3) & (base.m15)) |
                 ((base.lpr == 3) & (base.p16m20) & (~base.smic55))].copy()
    log.info('longueur de nof01 avant merge : {}'.format(len(nof01.index)))
    nof01 = nof01.merge(personne_de_reference, on='ident', how='outer')
    nof01['famille'] = 10
    nof01['kid'] = (
        (nof01.lpr == 3) & (nof01.m15)
        ) | (
            (nof01.lpr == 3) & (nof01.p16m20) & ~(nof01.smic55)
            )
    for series_name in ['famille', 'noifam']:
        assert_dtype(nof01[series_name], "int")
    assert_dtype(nof01.kid, "bool")
    famille = nof01.copy()
    del nof01
    control_04(famille, base)

    log.info(u"    2.1 : identification des couples")
    # l'ID est le noi de l'homme

    hcouple = subset_base(base, famille)
    hcouple = hcouple[(hcouple.cohab == 1) & (hcouple.lpr >= 3) & (hcouple.sexe == 1)].copy()
    hcouple['noifam'] = (100 * hcouple.ident + hcouple.noi).astype(int)
    hcouple['famille'] = 21
    for series_name in ['famille', 'noifam']:
        assert_dtype(hcouple[series_name], "int")
    log.info(u"longueur hcouple : ".format(len(hcouple.index)))

    log.info(u"    2.2 : attributing the noifam to the wives")
    fcouple = base[~(base.noindiv.isin(famille.noindiv.values))].copy()
    fcouple = fcouple[(fcouple.cohab == 1) & (fcouple.lpr >= 3) & (fcouple.sexe == 2)].copy()
    # l'identifiant de la famille est celui du conjoint de la personne de référence du ménage
    fcouple['noifam'] = (100 * fcouple.ident + fcouple.noicon).astype(int)
    fcouple['famille'] = 22
    for series_name in ['famille', 'noifam']:
        assert_dtype(fcouple[series_name], "int")
    log.info(u"Il y a {} enfants avec parents en fcouple".format(len(fcouple.index)))

    famcom = fcouple.merge(hcouple, on='noifam', how='outer')
    log.info(u"longueur fancom après fusion : {}".format(len(famcom.index)))
    fcouple = fcouple.merge(famcom)  # TODO : check s'il ne faut pas faire un inner merge sinon présence de doublons
    log.info(u"longueur fcouple après fusion : {}".format(len(fcouple.index)))
    famille = concat([famille, hcouple, fcouple], join='inner')
    control_04(famille, base)

    log.info(u"Etape 3: Récupération des personnes seules")
    log.info(u"    3.1 : personnes seules de catégorie 1")
    seul1 = base[~(base.noindiv.isin(famille.noindiv.values))].copy()
    seul1 = seul1[(seul1.lpr.isin([3, 4])) & ((seul1.p16m20 & seul1.smic55) | seul1.p21) & (seul1.cohab == 1) &
                  (seul1.sexe == 2)].copy()
    if len(seul1.index) > 0:
        seul1['noifam'] = (100 * seul1.ident + seul1.noi).astype(int)
        seul1['famille'] = 31
        for series_name in ['famille', 'noifam']:
            assert_dtype(seul1[series_name], "int")
        famille = concat([famille, seul1])
    control_04(famille, base)

    log.info(u"    3.1 personnes seules de catégorie 2")
    seul2 = base[~(base.noindiv.isin(famille.noindiv.values))].copy()
    seul2 = seul2[(seul2.lpr.isin([3, 4])) & seul2.p16m20 & seul2.smic55 & (seul2.cohab != 1)].copy()
    seul2['noifam'] = (100 * seul2.ident + seul2.noi).astype(int)
    seul2['famille'] = 32
    for series_name in ['famille', 'noifam']:
        assert_dtype(seul2[series_name], "int")
    famille = concat([famille, seul2])
    control_04(famille, base)

    log.info(u"    3.3 personnes seules de catégorie 3")
    seul3 = subset_base(base, famille)
    seul3 = seul3[(seul3.lpr.isin([3, 4])) & seul3.p21 & (seul3.cohab != 1)].copy()
    # TODO: CHECK erreur dans le guide méthodologique ERF 2002 lpr 3,4 au lieu de 3 seulement
    seul3['noifam'] = (100 * seul3.ident + seul3.noi).astype(int)
    seul3['famille'] = 33
    for series_name in ['famille', 'noifam']:
        assert_dtype(seul3[series_name], "int")
    famille = concat([famille, seul3])
    control_04(famille, base)

    log.info(u"    3.4 : personnes seules de catégorie 4")
    seul4 = subset_base(base, famille)
    seul4 = seul4[(seul4.lpr == 4) & seul4.p16m20 & ~(seul4.smic55) & (seul4.noimer.isnull()) &
                  (seul4.persfip == 'vous')].copy()
    if len(seul4.index) > 0:
        seul4['noifam'] = (100 * seul4.ident + seul4.noi).astype(int)
        seul4['famille'] = 34
        famille = concat([famille, seul4])
        for series_name in ['famille', 'noifam']:
            assert_dtype(seul4[series_name], "int")
    control_04(famille, base)

    log.info(u"Etape 4 : traitement des enfants")
    log.info(u"    4.1 : enfant avec mère")
    avec_mere = subset_base(base, famille)
    avec_mere = avec_mere[((avec_mere.lpr == 4) & ((avec_mere.p16m20 == 1) | (avec_mere.m15 == 1)) &
                           (avec_mere.noimer.notnull()))].copy()
    avec_mere['noifam'] = (100 * avec_mere.ident + avec_mere.noimer).astype(int)
    avec_mere['famille'] = 41
    avec_mere['kid'] = True
    for series_name in ['famille', 'noifam']:
        assert_dtype(avec_mere[series_name], "int")
    assert_dtype(avec_mere.kid, "bool")

    # On récupère les mères des enfants
    mereid = DataFrame(avec_mere['noifam'].copy())  # Keep a DataFrame instead of a Series to deal with rename and merge
    # Ces mères peuvent avoir plusieurs enfants, or il faut unicité de l'identifiant
    mereid.rename(columns = {'noifam': 'noindiv'}, inplace = True)
    mereid.drop_duplicates(inplace = True)
    mere = mereid.merge(base)
    mere['noifam'] = (100 * mere.ident + mere.noi).astype(int)
    mere['famille'] = 42
    for series_name in ['famille', 'noifam']:
        assert_dtype(mere[series_name], "int")
    avec_mere = avec_mere[avec_mere.noifam.isin(mereid.noindiv.values)].copy()
    log.info(u"Contrôle de famille après ajout des pères")
    control_04(mere, base)

    famille = famille[~(famille.noindiv.isin(mere.noindiv.values))].copy()
    control_04(famille, base)
    # on retrouve les conjoints des mères
    conj_mereid = mere[['ident', 'noicon', 'noifam']].copy()[mere.noicon.notnull()].copy()
    conj_mereid['noindiv'] = 100 * conj_mereid.ident + conj_mereid.noicon
    assert_dtype(conj_mereid[series_name], "int")
    conj_mereid = conj_mereid[['noindiv', 'noifam']].copy()
    conj_mereid = conj_mereid.merge(base)
    control_04(conj_mereid, base)
    conj_mere = conj_mereid.merge(base)
    conj_mere['famille'] = 43
    for series_name in ['famille', 'noifam']:
        assert_dtype(conj_mereid[series_name], "int")
    famille = famille[~(famille.noindiv.isin(conj_mere.noindiv.values))].copy()
    famille = concat([famille, avec_mere, mere, conj_mere])
    control_04(famille, base)
    del avec_mere, mere, conj_mere, mereid, conj_mereid

    log.info(u"    4.2 : enfants avec père")
    avec_pere = subset_base(base, famille)
    avec_pere = avec_pere[(avec_pere.lpr == 4) &
                          ((avec_pere.p16m20 == 1) | (avec_pere.m15 == 1)) &
                          (avec_pere.noiper.notnull())]
    avec_pere['noifam'] = (100 * avec_pere.ident + avec_pere.noiper).astype(int)
    avec_pere['famille'] = 44
    avec_pere['kid'] = True
    # TODO: hack to deal with the problem of presence of NaN in avec_pere
#    avec_pere.dropna(subset = ['noifam'], how = 'all', inplace = True)
    assert avec_pere['noifam'].notnull().all(), 'presence of NaN in avec_pere'
    for series_name in ['famille', 'noifam']:
        assert_dtype(avec_pere[series_name], "int")
    assert_dtype(avec_pere.kid, "bool")

    pereid = DataFrame(avec_pere['noifam'])  # Keep a DataFrame instead of a Series to deal with rename and merge
    pereid.rename(columns = {'noifam': 'noindiv'}, inplace = True)
    pereid.drop_duplicates(inplace = True)
    pere = pereid.merge(base)

    pere['noifam'] = (100 * pere.ident + pere.noi).astype(int)
    pere['famille'] = 45
    famille = famille[~(famille.noindiv.isin(pere.noindiv.values))].copy()

    # On récupère les conjoints des pères
    conj_pereid = pere[['ident', 'noicon', 'noifam']].copy()[pere.noicon.notnull()].copy()
    conj_pereid['noindiv'] = (100 * conj_pereid.ident + conj_pereid.noicon).astype(int)
    conj_pereid = conj_pereid[['noindiv', 'noifam']].copy()

    conj_pere = conj_pereid.merge(base)
    control_04(conj_pere, base)
    if len(conj_pere.index) > 0:
        conj_pere['famille'] = 46
    for series_name in ['famille', 'noifam']:
        assert_dtype(conj_pere[series_name], "int")

    famille = famille[~(famille.noindiv.isin(conj_pere.noindiv.values))].copy()
    famille = concat([famille, avec_pere, pere, conj_pere])
    log.info(u"Contrôle de famille après ajout des pères")
    control_04(famille, base)
    del avec_pere, pere, pereid, conj_pere, conj_pereid

    log.info(u"    4.3 : enfants avec déclarant")
    avec_dec = subset_base(base, famille)
    avec_dec = avec_dec[
        (avec_dec.persfip == "pac") &
        (avec_dec.lpr == 4) &
        (
            (avec_dec.p16m20 & ~(avec_dec.smic55)) | (avec_dec.m15 == 1)
            )
        ]
    avec_dec['noifam'] = (100 * avec_dec.ident + avec_dec.noidec.astype('int')).astype('int')
    avec_dec['famille'] = 47
    avec_dec['kid'] = True
    for series_name in ['famille', 'noifam']:
        assert_dtype(avec_dec[series_name], "int")
    assert_dtype(avec_dec.kid, "bool")
    control_04(avec_dec, base)
    # on récupère les déclarants pour leur attribuer une famille propre
    declarant_id = DataFrame(avec_dec['noifam'].copy()).rename(columns={'noifam': 'noindiv'})
    declarant_id.drop_duplicates(inplace = True)
    dec = declarant_id.merge(base)
    dec['noifam'] = (100 * dec.ident + dec.noi).astype(int)
    dec['famille'] = 48
    for series_name in ['famille', 'noifam']:
        assert_dtype(dec[series_name], "int")
    famille = famille[~(famille.noindiv.isin(dec.noindiv.values))].copy()
    famille = concat([famille, avec_dec, dec])
    del dec, declarant_id, avec_dec
    control_04(famille, base)

    log.info(u"Etape 5 : Récupération des enfants fip")
    log.info(u"    5.1 : Création de la df fip")
    individual_variables_fip = [
        'acteu',
        'actrec',
        'agepf',
        'agepr',
        'cohab',
        'contra',
        'declar1',
        'forter',
        'ident',
        'lien',
        'lpr',
        'mrec',
        'naia',
        'naim',
        'noi',
        'noicon',
        'noidec',
        'noimer',
        'noindiv',
        'noiper',
        'persfip',
        'quelfic',
        'retrai',
        'rga',
        'rstg',
        'sexe',
        'stc',
        'titc',
        'year',
        'ztsai',
        ]
    fip = temporary_store['fipDat_{}'.format(year)][individual_variables_fip].copy()
    # Variables auxilaires présentes dans base qu'il faut rajouter aux fip'
    # WARNING les noindiv des fip sont construits sur les ident des déclarants
    # pas d'orvelap possible avec les autres noindiv car on a des noi =99, 98, 97 ,...'
    fip['m15'] = (fip.agepf < 16)
    fip['p16m20'] = ((fip.agepf >= 16) & (fip.agepf <= 20))
    fip['p21'] = (fip.agepf >= 21)
    fip['smic55'] = (fip.ztsai >= smic * 12 * 0.55)
    fip['famille'] = 0
    fip['kid'] = False
    for series_name in ['kid', 'm15', 'p16m20', 'p21', 'smic55']:
        assert_dtype(fip[series_name], "bool")
    for series_name in ['famille']:
        assert_dtype(fip[series_name], "int")

# # base <- rbind(base,fip)
# # table(base$quelfic)

# # enfant_fip <- base[(!base$noindiv %in% famille$noindiv),]
# # enfant_fip <- subset(enfant_fip, (quelfic=="FIP") & (( (agepf %in% c(19,20)) & !smic55 ) | (naia==year & rga=='6')) )  # TODO check year ou year-1 !
# # enfant_fip <- within(enfant_fip,{
# #                      noifam=100*ident+noidec
# #                      famille=50
# #                      kid=TRUE})
# # #                     ident=NA}) # TODO : je ne sais pas quoi mettre un NA fausse les manips suivantes
# # famille <- rbind(famille,enfant_fip)
# #
# # # TODO: En 2006 on peut faire ce qui suit car tous les parents fip sont déjà dans une famille
# # parent_fip <- famille[famille$noindiv %in% enfant_fip$noifam,]
# # any(enfant_fip$noifam %in% parent_fip$noindiv)
# # parent_fip <- within(parent_fip,{
# #                      noifam <- noindiv
# #                      famille <- 51
# #                      kid <- FALSE})
# # famille[famille$noindiv %in% enfant_fip$noifam,] <- parent_fip
# # # TODO quid du conjoint ?

    log.info(u"    5.2 : extension de base avec les fip")
    base_ = concat([base, fip])
    enfant_fip = subset_base(base_, famille)
    enfant_fip = enfant_fip[
        (enfant_fip.quelfic == "FIP") & (
            (enfant_fip.agepf.isin([19, 20]) & ~(enfant_fip.smic55)) |
            ((enfant_fip.naia == enfant_fip.year - 1) & (enfant_fip.rga.astype('int') == 6))
            )
        ].copy()
    enfant_fip['noifam'] = (100 * enfant_fip.ident + enfant_fip.noidec).astype(int)
    enfant_fip['famille'] = 50
    enfant_fip['kid'] = True
    enfant_fip['ident'] = None  # TODO: should we really do this ?
    assert_dtype(enfant_fip.kid, "bool")
    for series_name in ['famille', 'noifam']:
        assert_dtype(enfant_fip[series_name], "int")
    control_04(enfant_fip, base)
    famille = concat([famille, enfant_fip])
    base = concat([base, enfant_fip])
    parent_fip = famille[famille.noindiv.isin(enfant_fip.noifam.values)].copy()
    assert (enfant_fip.noifam.isin(parent_fip.noindiv.values)).any(), \
        "{} doublons entre enfant_fip et parent fip !".format((enfant_fip.noifam.isin(parent_fip.noindiv.values)).sum())
    parent_fip['noifam'] = parent_fip['noindiv'].values.copy()
    parent_fip['famille'] = 51
    parent_fip['kid'] = False
    log.info(u"Contrôle de parent_fip")
    control_04(parent_fip, base)
    control_04(famille, base)
    famille = famille.merge(parent_fip, how='outer')
    # duplicated_individuals = famille.noindiv.duplicated()
    # TODO: How to prevent failing in the next assert and avoiding droppping duplicates ?
    # assert not duplicated_individuals.any(), "{} duplicated individuals in famille".format(
    # duplicated_individuals.sum())
    famille = famille.drop_duplicates(subset = 'noindiv', take_last = True)
    control_04(famille, base)
    del enfant_fip, fip, parent_fip

# # message('Etape 6 : non attribué')
# # non_attribue1 <- base[(!base$noindiv %in% famille$noindiv),]
# # non_attribue1 <- subset(non_attribue1,
# #                         (quelfic!="FIP") & (m15 | (p16m20&(lien %in% c(1,2,3,4) & agepr>=35)))
# #                         )
# # # On rattache les moins de 15 ans avec la PR (on a déjà éliminé les enfants en nourrice)
# # non_attribue1 <- merge(pr,non_attribue1)
# # non_attribue1 <- within(non_attribue1,{
# #   famille <- ifelse(m15,61,62)
# #     kid <- TRUE })
# #
# # rm(pr)
# # famille <- rbind(famille,non_attribue1)
# # dup <- duplicated(famille$noindiv)
# # table(dup)
# # rm(non_attribue1)
# # table(famille$famille, useNA="ifany")
# #
# # non_attribue2 <- base[(!base$noindiv %in% famille$noindiv) & (base$quelfic!="FIP"),]
# # non_attribue2 <- within(non_attribue2,{
# #   noifam <- 100*ident+noi # l'identifiant est celui du jeune */
# #     kid<-FALSE
# #     famille<-63})
# #
# # famille <- rbind(famille,non_attribue2)

    log.info(u"Etape 6 : gestion des non attribués")
    log.info(u"    6.1 : non attribués type 1")
    non_attribue1 = subset_base(base, famille)
    non_attribue1 = non_attribue1[
        ~(non_attribue1.quelfic != 'FIP') & (
            non_attribue1.m15 | (
                non_attribue1.p16m20 & (non_attribue1.lien.isin(range(1, 5))) & (non_attribue1.agepr >= 35)
                )
            )
        ].copy()
    # On rattache les moins de 15 ans avec la PR (on a déjà éliminé les enfants en nourrice)
    non_attribue1 = non_attribue1.merge(personne_de_reference)
    control_04(non_attribue1, base)
    non_attribue1['famille'] = 61 * non_attribue1.m15 + 62 * ~(non_attribue1.m15)
    non_attribue1['kid'] = True
    assert_dtype(non_attribue1.kid, "bool")
    assert_dtype(non_attribue1.famille, "int")
    famille = concat([famille, non_attribue1])
    control_04(famille, base)
    del personne_de_reference, non_attribue1

    log.info(u"    6.2 : non attribué type 2")
    non_attribue2 = base[(~(base.noindiv.isin(famille.noindiv.values)) & (base.quelfic != "FIP"))].copy()
    non_attribue2['noifam'] = (100 * non_attribue2.ident + non_attribue2.noi).astype(int)
    non_attribue2['kid'] = False
    non_attribue2['famille'] = 63
    assert_dtype(non_attribue2.kid, "bool")
    for series_name in ['famille', 'noifam']:
        assert_dtype(non_attribue2[series_name], "int")
    famille = concat([famille, non_attribue2], join='inner')
    control_04(famille, base)
    del non_attribue2

    # Sauvegarde de la table famille
    log.info(u"Etape 7 : Sauvegarde de la table famille")
    log.info(u"    7.1 : Mise en forme finale")
#    TODO: nettoyer les champs qui ne servent plus à rien
#    famille['idec'] = famille['declar1'].str[3:11]
#    famille['idec'].apply(lambda x: str(x)+'-')
#    famille['idec'] += famille['declar1'].str[0:2]
    famille['chef'] = (famille['noifam'] == (100 * famille.ident + famille.noi))
    assert_dtype(famille.chef, "bool")

    famille.reset_index(inplace = True)
    control_04(famille, base)

    log.info(u"    7.2 : création de la colonne rang")

    famille['rang'] = famille.kid.astype('int')
    while any(famille[(famille.rang != 0)].duplicated(subset = ['rang', 'noifam'])):
        famille["rang"][famille.rang != 0] += famille[famille.rang != 0].copy().duplicated(
            cols = ["rang", 'noifam']).values
        log.info(u"nb de rangs différents : {}".format(len(set(famille.rang.values))))

    log.info(u"    7.3 : création de la colonne quifam et troncature")
    log.info(u"value_counts chef : \n {}".format(famille['chef'].value_counts()))
    log.info(u"value_counts kid :' \n {}".format(famille['kid'].value_counts()))

    famille['quifam'] = -1
    # famille['quifam'] = famille['quifam'].where(famille['chef'].values, 0)
    # ATTENTTION : ^ stands for XOR
    famille.quifam = (0 +
        ((~famille['chef']) & (~famille['kid'])).astype(int) +
        famille.kid * famille.rang
        ).astype('int')

    # TODO: Test a groupby to improve the following this (should be placed )
    #    assert famille['chef'].sum() == len(famille.noifam.unique()), \
    #      'The number of family chiefs {} is different from the number of families {}'.format(
    #          famille['chef'].sum(),
    #          len(famille.idfam.unique())
    #          )

    #    famille['noifam'] = famille['noifam'].astype('int')
    log.info(u"value_counts quifam : \n {}".format(famille['quifam'].value_counts()))
    famille = famille[['noindiv', 'quifam', 'noifam']].copy()
    famille.rename(columns = {'noifam': 'idfam'}, inplace = True)
    log.info(u"Vérifications sur famille")
    # TODO: we drop duplicates if any
    log.info(u"There are {} duplicates of quifam inside famille, we drop them".format(
        famille.duplicated(subset = ['idfam', 'quifam']).sum())
        )
    famille.drop_duplicates(subset = ['idfam', 'quifam'], inplace = True)
    # assert not(famille.duplicated(cols=['idfam', 'quifam']).any()), \
    #   'There are {} duplicates of quifam inside famille'.format(
    #       famille.duplicated(cols=['idfam', 'quifam']).sum())

    temporary_store["famc_{}".format(year)] = famille
    del indivi, enfants_a_naitre

if __name__ == '__main__':
    import sys
    logging.basicConfig(level = logging.INFO, stream = sys.stdout)
    famille()
    log.info(u"étape 04 famille terminée")
