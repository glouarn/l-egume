from scipy import *
import time
import IOtable
import IOxls
import ShootMorpho as sh
import RootDistrib as rtd
import RootMorpho2 as rt
try:
    from riri5 import RIRI5 as riri #import de la version develop si module soil3ds est installe
except:
    import RIRI5 as riri

try:
    from soil3ds import soil_moduleN as solN #import de la version develop si module soil3ds est installe
except:
    import soil_moduleN3 as solN #soil_moduleN2_bis as solN #! renommer car dans nouvelle version Lpy, mot module est reserve et fait planter!


#daily loop
# decoupe daily_growth_loop initial en 4 fonctions pour donner acces au calcul du sol depuis l'exterieur

def daily_growth_loop(ParamP, invar, outvar, res_trans, meteo_j, nbplantes, surfsolref, ls_ftswStress, ls_NNIStress, lsApex, lsApexAll, opt_stressW=1, opt_stressN=1):
    """ daily potential growth loop (computes epsi, DM production / allocation / Ndemand) """

    # calcul de ls_epsi
    invar['parap'] = array(list(map(sum, invar['PARaPlante'])))
    invar['parip'] = array(list(map(sum, invar['PARiPlante'])))
    # qatot= sum(res_trans[-1][:][:])*3600.*24/1000000. + sum(invar['parip'])#(MJ.day-1) #approximatif! a reprendre avec un vrai bilan radiatif
    # print sum(res_trans[-1][:][:]), sum(res_trans[-1][:][:])*3600.*24/1000000., sum(res_trans[-1][:][:])*3600.*24/1000000.  +   sum(invar['parip'])
    # ls_epsi = invar['parip']/qatot.tolist() #a reprendre : approximatif slmt! -> changera un peu avec un vrai bilan radiatif
    # transmi_sol = 1-sum(ls_epsi)
    # epsi = 1-transmi_sol #a reprendre pour differencier cible et vois #
    transmi_sol = sum(res_trans[-1][:][:]) / (meteo_j['I0'] * surfsolref)  # bon
    epsi = 1. - transmi_sol  # bon
    ls_epsi = epsi * invar['parip'] / (sum(invar['parip']) + 10e-15)

    graineC, graineN = sh.reserves_graine(invar, ParamP)

    # calcul de Biomasse tot
    stressHRUE = array(ls_ftswStress['WaterTreshRUE'])
    stressNRUE = array(ls_NNIStress['NTreshRUE'])
    if opt_stressW==0:
        stressHRUE = 1.
    if opt_stressN==0:
        stressNRUE = 1.

    stressFIX = 1 - array(invar['Ndfa']) * array(
        riri.get_lsparami(ParamP, 'NODcost'))  # coeff 0.15 = 15% reduction RUE a 100% fixation -> a passer en paarmetre
    invar['RUEactu'] = array(riri.get_lsparami(ParamP, 'RUE')) * stressHRUE * stressNRUE * stressFIX
    invar['PARaPlanteU'] = array(ls_epsi) * 0.95 * meteo_j[
        'I0'] * 3600. * 24 / 1000000. * surfsolref  # facteur 0.95 pour reflectance / PARa used for calculation
    dM = invar['PARaPlanteU'] * invar['RUEactu'] + graineC
    # dM2 = array(dpar) * array(get_lsparami(ParamP, 'RUE'))

    # allocation
    froot = sh.rootalloc(riri.get_lsparami(ParamP, 'alloc_root'), invar['MS_aer_cumul'])  # fraction aux racines
    for nump in range(nbplantes):
        if invar['germination'][nump] < 2:  # tout aux racines avant apparition de la premiere feuille
            froot[nump] = 0.99

    invar['remob'] = sh.Cremob(array(IOxls.dic2vec(nbplantes, invar['DemCp'])), invar['R_DemandC_Shoot'],
                               invar['MS_pivot'])  # vraiment marginal
    rac_fine = dM * froot * array(
        riri.get_lsparami(ParamP, 'frac_rac_fine'))  # * rtd.filtre_ratio(invar['R_DemandC_Shoot'])
    pivot = dM * froot * (1 - array(riri.get_lsparami(ParamP, 'frac_rac_fine'))) - invar['remob']
    aer = dM - rac_fine - pivot + invar['remob']
    ffeuil = array(IOxls.dic2vec(nbplantes, invar['DemCp_lf'])) / (
                array(IOxls.dic2vec(nbplantes, invar['DemCp'])) + 10e-12)  # fraction aux feuilles
    feuil = aer * ffeuil
    tige = aer * (1 - ffeuil)

    invar['Mtot'].append(dM.tolist())
    invar['Mrac_fine'].append(rac_fine.tolist())  # matrice des delta MSrac fine par date
    invar['Mpivot'].append(pivot.tolist())  # matrice des delta MSpivot par date
    invar['Maerien'].append(aer.tolist())  # matrice des delta MSaerien par date
    invar['Mfeuil'].append(feuil.tolist())  # matrice des delta MSfeuil par date
    invar['MS_pivot'] = list(map(sum, IOtable.t_list(invar['Mpivot'])))  # vecteur des MSpivot cumule au temps t
    invar['MS_aerien'] = list(map(sum, IOtable.t_list(invar['Maerien'])))  # vecteur des MSaerien cumule au temps t
    invar['MS_feuil'] = list(map(sum, IOtable.t_list(invar['Mfeuil'])))  # vecteur des MSfeuil cumule au temps t
    invar['MS_aer_cumul'] += aer
    invar['MS_tot'] = list(map(sum, IOtable.t_list(invar['Mtot'])))
    invar['MS_rac_fine'] = list(map(sum, IOtable.t_list(invar['Mrac_fine'])))  # vecteur des MSraines_fines cumule au temps t
    invar['DiampivMax'] = sqrt(invar['MS_pivot'] * array(riri.get_lsparami(ParamP, 'DPivot2_coeff')))
    # invar['RLTot'] = array(map(sum, IOtable.t_list(invar['Mrac_fine']))) * array(riri.get_lsparami(ParamP, 'SRL')) #somme de toutes les racinesfines produites par plante
    invar['NBsh'], invar['NBI'] = sh.calcNB_NI(lsApex, nbplantes, seuilcountTige=0.25, seuilNItige=0.25)
    nbsh_2, nb1_2 = sh.calcNB_NI(lsApexAll, nbplantes, seuilcountTige=0.25,
                                 seuilNItige=0.25)  # recalcul sur tous les axes pour eviter bug des arret de tiges
    for nump in range(nbplantes):
        if nb1_2[nump] > invar['NBI'][nump]:
            invar['NBI'][nump] = nb1_2[nump]

    invar['L_Sp'] = array(invar['MS_feuil']) / (array(invar['MS_aerien']) - array(invar['MS_feuil']) + 10e-12)

    # print("MS AERIEN",invar['MS_aerien'],invar['MS_aer_cumul'])
    # print invar['Mtot']

    ls_demandeN = array(invar[
                            'DemandN_Tot']) * 0.001 + 1e-15  # en kg N.plant-1 #[1e-12]*nbplantes #sera a renseigner -> la, force a zero - devra utiliser invar['DemandN_Tot'] qui est mis a jour + loin #en kg N
    Npc_aer = array(invar['Naerien']) / (
                aer + array(invar['MS_aerien'])) * 100.  # Npc avec accroissement de biomasse pour calculer la demande
    Npc_piv = array(invar['Npivot']) / (pivot + array(invar['MS_pivot'])) * 100.
    Npc_rac_fine = array(invar['Nrac_fine']) / (rac_fine + array(invar['MS_rac_fine'])) * 100.

    invar['NreservPiv'] = array(invar['Npivot']) * (Npc_piv - array(riri.get_lsparami(ParamP, 'NminPiv'))) / Npc_piv
    invar['NreservPiv'][invar['NreservPiv'] < 0.] = 0.  # verifier que depasse pas zero!!

    ls_demandeN_aer = solN.demandeNdefaut2(MSp=array(invar['MS_aerien']), dMSp=aer, Npc=Npc_aer, surfsolref=surfsolref,
                                           a=array(riri.get_lsparami(ParamP, 'ADIL')),
                                           b1=array(riri.get_lsparami(ParamP, 'BDILi')), b2=array(
            riri.get_lsparami(ParamP, 'BDIL'))) * 0.001 + 1e-15  # en kg N.plant-1
    ls_demandN_piv = solN.demandeNroot(array(invar['MS_pivot']), pivot, Npc_piv, surfsolref,
                                       array(riri.get_lsparami(ParamP, 'NoptPiv'))) * 0.001 + 1e-15  # en kg N.plant-1
    ls_demandN_rac_fine = solN.demandeNroot(array(invar['MS_rac_fine']), rac_fine, Npc_rac_fine, surfsolref, array(
        riri.get_lsparami(ParamP, 'NoptFR'))) * 0.001 + 1e-15  # en kg N.plant-1

    ls_demandeN_bis = ls_demandeN_aer + ls_demandN_piv + ls_demandN_rac_fine
    fracNaer = ls_demandeN_aer / ls_demandeN_bis
    fracNpiv = ls_demandN_piv / ls_demandeN_bis
    fracNrac_fine = ls_demandN_rac_fine / ls_demandeN_bis

    invar['DemandN_TotAer'] = ls_demandeN_aer

    # print invar['Maerien']#invar['MS_aerien']
    # print aer

    # ajout des bilan C plante pour sorties / m2
    outvar['BilanC_PARa'].append(sum(invar['PARaPlanteU']) / surfsolref)
    outvar['BilanC_RUE'].append(sum(dM) / sum(invar['PARaPlanteU']))
    outvar['BilanCdMStot'].append(sum(dM) / surfsolref)
    outvar['BilanCdMrac_fine'].append(sum(rac_fine) / surfsolref)
    outvar['BilanCdMpivot'].append(sum(pivot) / surfsolref)
    outvar['BilanCdMaer'].append(sum(aer) / surfsolref)
    outvar['BilanCdMSenFeuil'].append(sum(invar['dMSenFeuil']) / surfsolref)
    outvar['BilanCdMSenTige'].append(sum(invar['dMSenTige']) / surfsolref)



    #test des 3 autres fonctions en interne au sein d'une fonction globale
    temps = [aer, rac_fine, pivot, graineN, fracNaer, fracNpiv, fracNrac_fine] #variable temporaires pour passer entre fonctions (passer ds invar?)

    return invar, outvar, ls_epsi, ls_demandeN_bis, temps



def step_bilanWN_sol(S, par_SN, lims_sol, surfsolref, stateEV, Uval, b_, meteo_j,  mng_j, ParamP, invar, ls_epsi, ls_systrac, ls_demandeN_bis, opt_residu):
    """ daily step for soil W and N balance from meteo, management and lsystem inputs"""

    # testRL = updateRootDistrib(invar['RLTot'][0], ls_systrac[0], lims_sol)
    # ls_roots = rtd.build_ls_roots_mult(invar['RLTot'], ls_systrac, lims_sol) #ancien calcul base sur SRL fixe
    ls_roots = rtd.build_ls_roots_mult(array(invar['RLTotNet']) * 100. + 10e-15, ls_systrac,
                                       lims_sol)  # !*100 pour passer en cm et tester absoption d'azote (normalement m) #a passer apres calcul de longuer de racine!

    # preparation des entrees eau
    Rain = meteo_j['Precip']
    Irrig = mng_j['Irrig']  # ['irrig_Rh1N']#R1N = sol_nu

    # preparation des entrees azote
    mapN_Rain = 1. * S.m_1[0, :, :] * Rain * par_SN['concrr']  # Nmin de la pluie
    mapN_Irrig = 1. * S.m_1[0, :, :] * Irrig * par_SN['concrr']  # Nmin de l'eau d'irrigation
    mapN_fertNO3 = 1. * S.m_1[0, :, :] * mng_j['FertNO3'] * S.m_vox_surf[0, :, :] / 10000.  # kg N par voxel
    mapN_fertNH4 = 1. * S.m_1[0, :, :] * mng_j['FertNH4'] * S.m_vox_surf[0, :, :] / 10000.  # kg N par voxel

    S.updateTsol(meteo_j['Tsol'])  # (meteo_j['TmoyDay'])#(meteo_j['Tsol'])# #Tsol forcee comme dans STICS (Tsol lue!!)

    #############
    # step  sol
    #############
    treshEffRoots_ = 10e10  # valeur pour forcer a prendre densite effective
    ls_transp, evapo_tot, Drainage, stateEV, ls_m_transpi, m_evap, ls_ftsw = S.stepWBmc(meteo_j['Et0'] * surfsolref,
                                                                                        ls_roots, ls_epsi,
                                                                                        Rain * surfsolref,
                                                                                        Irrig * surfsolref, stateEV,
                                                                                        par_SN['ZESX'], leafAlbedo=0.15,
                                                                                        U=Uval, b=b_, FTSWThreshold=0.4,
                                                                                        treshEffRoots=treshEffRoots_,
                                                                                        opt=1)
    S.stepNB(par_SN)
    if opt_residu == 1:  # s'ily a des residus
        S.stepResidueMin(par_SN)
        S.stepMicrobioMin(par_SN)
    S.stepNitrif(par_SN)
    ActUpNtot, ls_Act_Nuptake_plt, ls_DQ_N, idmin = S.stepNuptakePlt(par_SN, ParamP, ls_roots, ls_m_transpi,
                                                                     ls_demandeN_bis)
    S.stepNINFILT(mapN_Rain, mapN_Irrig, mapN_fertNO3, mapN_fertNH4, Drainage, opt=1)

    temps_sol = [evapo_tot, Drainage, ls_m_transpi, m_evap, ActUpNtot, ls_DQ_N, idmin] #other output variables

    return [S,  stateEV, ls_ftsw, ls_transp, ls_Act_Nuptake_plt, temps_sol]
    #lims_sol et surfsolref pourrait pas etre fournie via S.?
    #pourquoi b_ et Uval trainent la? (paramtres sol??)
    #return more output variables?? -> OK temps_sol
    #move to soil module?




def Update_stress_loop(ParamP, invar, invar_sc, temps, DOY, nbplantes, surfsolref, ls_epsi, ls_ftsw, ls_transp, ls_Act_Nuptake_plt, ls_demandeN_bis, ls_ftswStress, lsOrgans, lsApex, start_time, cutNB, deltaI_I0, nbI_I0, I_I0profilLfPlant, I_I0profilPetPlant, I_I0profilInPlant, NlClasses, NaClasses, NlinClasses, outvar):
    """ Update daily N uptake/fixation from soil WN balance and plant demands / prepares stress variables for next step / write output variables   """

    aer, rac_fine, pivot, graineN, fracNaer, fracNpiv, fracNrac_fine = temps# temps[0], temps[1],temps[2], temps[3],temps[4], temps[5],temps[6] #unpacks variables temporaires passes entre fonction -> a repasser dans invar!!!

    # water
    invar['transpi'] = ls_transp
    invar['cumtranspi'] += array(ls_transp)

    # Uptake N et allocation
    invar['Nuptake_sol'] = array(list(map(sum, ls_Act_Nuptake_plt))) * 1000 + graineN  # g N.plant-1 #test ls_demandeN_bis*1000.#
    try:
        NremobC = invar['remob'] * invar['Npc_piv'] / 100.  # remobilise N pivot qui part avec le C
        invar['Naerien'] += invar['Nuptake_sol'] * fracNaer + NremobC  # uptake N va dans partie aeriennes au prorata des demandes
        invar['Npivot'] += invar['Nuptake_sol'] * fracNpiv - NremobC
    except:  # 1er step
        NremobC = 0.
        invar['Naerien'] += invar['Nuptake_sol'] * fracNaer + NremobC
        invar['Npivot'] += invar['Nuptake_sol'] * fracNpiv
        print('rem')

    invar['Nrac_fine'] += invar['Nuptake_sol'] * fracNrac_fine

    # Fixation et allocation
    maxFix = sh.Ndfa_max(invar['TT'], riri.get_lsparami(ParamP, 'DurDevFix')) * array(
        riri.get_lsparami(ParamP, 'MaxFix')) / 1000. * aer  # * invar['dTT']
    stressHFix = array(ls_ftswStress['WaterTreshFix']) * maxFix  # effet hydrique
    invar['Qfix'] = sh.ActualFix(ls_demandeN_bis * 1000., invar['Nuptake_sol'], stressHFix)  # g N.plant-1
    invar['Ndfa'] = invar['Qfix'] / (invar['Qfix'] + invar['Nuptake_sol'] + 1e-15)

    delta_besoinN_aerien = invar['DemandN_TotAer'] * 1000. - invar['Qfix'] * fracNaer - invar[
        'Nuptake_sol'] * fracNaer - NremobC  # besoin N are sont ils couverts? g N.plant-1
    NremobN = minimum(delta_besoinN_aerien, invar['NreservPiv'])  # si pas couvert remobilisation N du pivot directement
    NremobN[NremobN < 0.] = 0.  # verifie que pas de negatif

    # print 'Npivot', invar['Npivot'][0:2]
    # print 'NreservPiv', invar['NreservPiv'][0:2]
    # print 'delta_besoinN', delta_besoinN_aerien[0:2]
    # print 'NremobN', NremobN[0:2]

    invar['Naerien'] += invar['Qfix'] * fracNaer + NremobN
    invar['Npivot'] += invar['Qfix'] * fracNpiv - NremobN
    invar['NreservPiv'] -= NremobN
    invar['Nrac_fine'] += invar['Qfix'] * fracNrac_fine  # total : vivantes et mortes

    # effet feedback N pas fait (priorite) -> necessaire???
    # mise a jour Npc et calcul NNI

    invar['Npc_aer'] = array(invar['Naerien']) / (aer + array(invar['MS_aerien'])) * 100.  # %
    invar['Npc_piv'] = array(invar['Npivot']) / (pivot + array(invar['MS_pivot'])) * 100.  # %
    invar['Npc_rac_fine'] = array(invar['Nrac_fine']) / (rac_fine + array(invar['MS_rac_fine'])) * 100.  # %

    # print 'Npc_piv', invar['Npc_piv'][0:2]

    critN_inst = solN.critN(sum(aer + array(invar['MS_aerien'])) / (surfsolref * 100.))  # azote critique couvert
    invar['NNI'] = invar['Npc_aer'] / critN_inst


    # update des indices de stress hydrique par plante pour step suivant
    p1, p2, p3, p4, p5, p6, p7, p8, p9 = [], [], [], [], [], [], [], [], []  # liste de parametres
    for nump in range(nbplantes):
        p1.append(ParamP[nump]['WaterTreshExpSurf'])
        p2.append(ParamP[nump]['WaterTreshDevII'])
        p3.append(ParamP[nump]['WaterTreshDevI'])
        p4.append(ParamP[nump]['WaterTreshFix'])
        p5.append(ParamP[nump]['WaterTreshRUE'])
        p6.append(ParamP[nump]['NTreshRUE'])
        p7.append(ParamP[nump]['NTreshExpSurf'])
        p8.append(ParamP[nump]['NTreshDev'])
        p9.append(ParamP[nump]['NTreshDevII'])

    ls_ftswStress = {}
    ls_ftswStress['WaterTreshExpSurf'] = list(map(sh.FTSW_resp, ls_ftsw, p1))
    ls_ftswStress['WaterTreshDevII'] = list(map(sh.FTSW_resp, ls_ftsw, p2))
    ls_ftswStress['WaterTreshDevI'] = list(map(sh.FTSW_resp, ls_ftsw, p3))
    ls_ftswStress['WaterTreshFix'] = list(map(sh.FTSW_resp, ls_ftsw, p4))
    ls_ftswStress['WaterTreshRUE'] = list(map(sh.FTSW_resp, ls_ftsw, p5))

    # update des indices de stress N par plante pour step suivant
    ls_NNIStress = {}
    ls_NNIStress['NTreshRUE'] = list(map(sh.NNI_resp, invar['NNI'], p6))
    ls_NNIStress['NTreshExpSurf'] = list(map(sh.NNI_resp, invar['NNI'], p7))
    ls_NNIStress['NTreshDev'] = list(map(sh.NNI_resp, invar['NNI'], p8))
    ls_NNIStress['NTreshDevII'] = list(map(sh.NNI_resp, invar['NNI'], p9))

    # print invar['TT'], Ndfa_max(invar['TT'], riri.get_lsparami(ParamP, 'DurDevFix')), maxFix, stressHFix
    # print invar['TT'], ls_demandeN_bis, invar['Nuptake_sol'], stressHFix
    # print sum(mapN_Rain), sum(mapN_Irrig), sum(mapN_fertNO3), sum(mapN_fertNH4), meteo_j['Tsol']
    # print ls_demandeN_bis, ls_demandeN, Npc_temp, array(map(sum, ls_Act_Nuptake_plt)), invar['Naerien'] #pour convertir en g N
    # print invar['Npc_bis']
    # print ls_demandeN_bis[0], ls_demandeN
    # print solN.critN(sum(aer+array(invar['MS_aerien']))#, invar['Npc_bis']

    # calcul offre/demandeC
    tab = IOtable.conv_dataframe(IOtable.t_list(lsOrgans))
    # OffCp = calcOffreC (tab, 'plt')#pas utilise??!
    # invar['DemCp'] = calcDemandeC(tab, 'plt')#attention, pour que calcul soit bon, faut le STEPS  suivant mis a jour!-> a faire en StartEach
    # invar['L_Sp'] = sh.calcLeafStemRatio(ParamP, tab, lsAxes)

    # calcul surf par tige/axe
    invar_sc['plt']['Surf'], invar_sc['plt']['SurfVerte'], invar_sc['sh']['Surf'], invar_sc['sh']['SurfVerte'], \
    invar_sc['ax']['Surf'], invar_sc['ax']['SurfVerte'], invar_sc['plt']['PARaF'], invar_sc['sh']['PARaF'], \
    invar_sc['ax']['PARaF'], invar_sc['ax']['AgePiv'], invar_sc['ax']['MaxPARaF'] = sh.calcSurfLightScales(ParamP,
                                                                                                           IOtable.conv_dataframe(
                                                                                                               IOtable.t_list(
                                                                                                                   lsOrgans)))
    # calcul de fraction de PARa par pivot
    invar_sc['ax']['fPARaPiv'] = rt.calc_daxfPARaPiv(nbplantes, invar_sc['ax']['AgePiv'], invar_sc['plt']['PARaF'],
                                                     invar_sc['ax']['PARaF'])
    # calcul demande par pivot
    invar_sc['ax']['DemCRac'], invar_sc['ax']['NRac'] = rt.calc_DemandC_roots(ParamP, invar_sc['ax']['AgePiv'],
                                                                              invar['dTTsol'],
                                                                              invar_sc['ax']['QDCmoyRac'])

    # calcul biomasse, diametres pivots indivs, QDC des racines, increment de longueur et SRL
    daxPiv = rt.distrib_dM_ax(invar_sc['ax']['fPARaPiv'], pivot, Frac_piv_sem=riri.get_lsparami(ParamP, 'Frac_piv_sem'),
                              Frac_piv_loc=riri.get_lsparami(ParamP,
                                                             'Frac_piv_loc'))  # rt.distrib_dM_ax(invar_sc['ax']['fPARaPiv'], pivot)
    invar_sc['ax']['MaxPiv'] = IOxls.add_dic(daxPiv, invar_sc['ax']['MaxPiv'])
    invar_sc['ax']['DiampivMax'] = rt.calc_DiamPiv(ParamP, invar_sc['ax']['MaxPiv'])
    invar_sc['ax']['OfrCRac'] = rt.distrib_dM_ax(invar_sc['ax']['fPARaPiv'], rac_fine,
                                                 Frac_piv_sem=riri.get_lsparami(ParamP, 'Frac_piv_sem'),
                                                 Frac_piv_loc=riri.get_lsparami(ParamP, 'Frac_piv_loc'))
    invar_sc['ax']['QDCRac'] = rt.calc_QDC_roots(invar_sc['ax']['OfrCRac'], invar_sc['ax']['DemCRac'])
    invar_sc['ax']['QDCmoyRac'] = rt.calc_QDCmoy_roots(invar_sc['ax']['QDCRac'], invar_sc['ax']['QDCmoyRac'],
                                                       invar_sc['ax']['AgePiv'], invar['dTTsol'])
    invar_sc['ax']['StressHmoyRac'] = rt.calc_StressHmoy_roots(invar_sc['ax']['StressHRac'],
                                                               invar_sc['ax']['PonderStressHRac'],
                                                               invar_sc['ax']['StressHmoyRac'],
                                                               invar_sc['ax']['AgePiv'], invar[
                                                                   'dTTsol'])  # (dStressH, dPonder, dStressHmoy, dAgePiv, dTT)

    invar_sc['ax']['dlRac'] = rt.calc_dLong_roots(ParamP, invar_sc['ax']['NRac'], invar['dTTsol'],
                                                  invar_sc['ax']['QDCRac'], invar_sc['ax']['StressHRac'],
                                                  invar_sc['ax'][
                                                      'PonderStressHRac'])  # passe STEPS, mais devrait filer les dTT de chaque plante
    invar_sc['ax']['cumlRac'] = IOxls.add_dic(invar_sc['ax']['dlRac'], invar_sc['ax']['cumlRac'])
    invar['RLen1'], invar['RLen2'], invar['RLen3'], invar['RLentot'] = rt.cumul_plante_Lrac(nbplantes,
                                                                                            invar_sc['ax']['cumlRac'])
    dl1, dl2, dl3, dltot = rt.cumul_plante_Lrac(nbplantes,
                                                invar_sc['ax']['dlRac'])  # calcul des delta de longueur par plante
    invar['dRLen2'].append(dl2)  # stocke les dl du jour pour cacalcul senescence de plus tard
    invar['dRLen3'].append(dl3)
    # invar['SRL'] = invar['RLentot']/(invar['MS_rac_fine'][0]+10e-15)
    # print invar_sc['ax']['QDCRac']

    # print 'graine', graineC, dltot, invar['Surfcoty'], invar['Mcoty']#

    dur2 = (array(riri.get_lsparami(ParamP, 'GDs2')) + array(
        riri.get_lsparami(ParamP, 'LDs2'))) / 20.  # en jours a 20 degres!
    dur3 = (array(riri.get_lsparami(ParamP, 'GDs3')) + array(
        riri.get_lsparami(ParamP, 'LDs3'))) / 20.  # en jours a 20 degres!
    invar['dRLenSentot'], invar['dMSenRoot'] = rt.calc_root_senescence(invar['dRLen2'], invar['dRLen3'], dur2, dur3,
                                                                       array(invar['SRL']))
    invar['RLTotNet'] = array(invar['RLTotNet']) + dltot - invar['dRLenSentot']
    invar['MS_rac_fineNet'] = array(invar['MS_rac_fineNet']) + rac_fine - invar['dMSenRoot']
    invar['SRL'] = invar['RLTotNet'] / (invar['MS_rac_fineNet'][0] + 10e-15)

    invar['perteN_rac_fine'] = invar['dMSenRoot'] * invar['Npc_rac_fine'] / 100.
    # sortir une variable cumule d'N des rac mortes? -> compement a invar['Nrac_fine'] qui comprend les deux


    # calcul senesc a faire a l'echelle des axes plutot? -> a priori pas necessaire

    invar['R_DemandC_Root'] = rt.calc_QDplante(nbplantes, invar_sc['ax']['QDCRac'], invar_sc['ax']['cumlRac'],
                                               invar['RLentot'])
    invar['R_DemandC_Shoot'] = aer / (array(IOxls.dic2vec(nbplantes, invar['DemCp'])) + 10e-15)

    # if '0_0_0' in invar_sc['ax']['NRac'].keys():
    #    print invar_sc['ax']['NRac']['0_0_0']
    #    print invar_sc['ax']['QDCRac']['0_0_0']
    #    print invar_sc['ax']['dlRac']['0_0_0']
    # print invar['RLentot'], invar['MS_rac_fine'], invar['RLentot'][0]/(invar['MS_rac_fine'][0]+0.00000001)

    # calcul demandN -> a depalcer dans le starteach comme pour C?? -> pas utilise actuellement
    if lsApex != []:
        I_I0profilInPlant = sh.cumul_lenIN(lsApex, tab, I_I0profilInPlant, deltaI_I0, nbI_I0)

    # pas utilise
    for nump in range(nbplantes):
        invar['DemandN_Feuil'][nump] = sum(I_I0profilLfPlant[nump] * NaClasses)
        invar['DemandN_Pet'][nump] = sum(I_I0profilPetPlant[nump] * NlClasses)
        invar['DemandN_Stem'][nump] = sum(I_I0profilInPlant[nump] * NlinClasses)
        # invar['DemandN_Tot'][nump] = invar['DemandN_Feuil'][nump] + invar['DemandN_Pet'][nump] + invar['DemandN_Stem'][nump]

    invar['DemandN_Tot'] = ls_demandeN_bis * 1000.
    # print invar['DemandN_Tot'][0], sum(ls_Act_Nuptake_plt[0]), sum(ls_Act_Nuptake_plt[0])/(invar['DemandN_Tot'][0]+10e-12), sum(S.m_NO3)

    Npc = (array(invar['DemandN_Feuil']) + array(invar['DemandN_Pet']) + array(invar['DemandN_Stem'])) * 100. / array(
        invar['MS_aerien'])

    # temps de calcul
    past_time = time.time() - start_time



    # sorties
    outvar['TT'].append(['TT', DOY] + invar['TT'])
    outvar['time'].append(['time', DOY] + [past_time] * nbplantes)
    outvar['cutNB'].append(['cutNB', DOY] + [cutNB] * nbplantes)
    outvar['SurfPlante'].append(['SurfPlante', DOY] + list(map(sum, invar['SurfPlante'])))
    outvar['PARaPlante'].append(
        ['PARaPlante', DOY] + invar['PARaPlanteU'].tolist())  # append(['PARaPlante',DOY]+invar['parap'].tolist())
    outvar['PARiPlante'].append(['PARiPlante', DOY] + invar['parip'].tolist())
    outvar['epsi'].append(['epsi', DOY] + ls_epsi.tolist())
    outvar['dMSaer'].append(['dMSaer', DOY] + aer.tolist())
    outvar['Hplante'].append(['Hplante', DOY] + invar['Hplante'])
    outvar['Dplante'].append(['Dplante', DOY] + invar['Dplante'])
    outvar['RLTot'].append(['RLTot', DOY] + invar['RLentot'])
    outvar['RDepth'].append(['RDepth', DOY] + invar['RDepth'])
    outvar['MS_aerien'].append(['MSaerien', DOY] + invar['MS_aerien'])
    outvar['MS_feuil'].append(['MSfeuil', DOY] + invar['MS_feuil'])
    outvar['MS_tot'].append(['MStot', DOY] + invar['MS_tot'])
    outvar['countSh'].append(['countSh', DOY] + invar['countSh'])
    outvar['countShExp'].append(['countShExp', DOY] + invar['countShExp'])
    outvar['demandC'].append(['demandC', DOY] + IOxls.dic2vec(nbplantes, invar['DemCp']))
    outvar['Leaf_Stem'].append(['Leaf_Stem', DOY] + invar['L_Sp'].tolist())
    outvar['NBsh'].append(['NBsh', DOY] + invar['NBsh'])
    outvar['NBI'].append(['NBI', DOY] + invar['NBI'])
    outvar['FTSW'].append(['FTSW', DOY] + ls_ftsw)
    outvar['Etransp'].append(['Etransp', DOY] + ls_transp)
    outvar['DemandN_Feuil'].append(['DemandN_Feuil', DOY] + invar['DemandN_Feuil'])
    outvar['DemandN_Pet'].append(['DemandN_Pet', DOY] + invar['DemandN_Pet'])
    outvar['DemandN_Stem'].append(['DemandN_Stem', DOY] + invar['DemandN_Stem'])
    outvar['DemandN_Tot'].append(['DemandN_Tot', DOY] + invar['DemandN_Tot'].tolist())
    outvar['Npc'].append(['Npc', DOY] + Npc.tolist())
    outvar['NBD1'].append(['NBD1', DOY] + invar['NBD1'])
    outvar['NBB'].append(['NBB', DOY] + invar['NBB'])
    outvar['NBBexp'].append([['NBBexp', DOY] + invar['NBBexp']])
    outvar['R_DemandC_Root'].append(['R_DemandC_Root', DOY] + invar['R_DemandC_Root'])
    outvar['SRL'].append(['SRL', DOY] + invar['SRL'].tolist())
    outvar['DemandN_Tot_Aer'].append(['DemandN_Tot_Aer', DOY] + invar['DemandN_TotAer'].tolist())
    outvar['Naerien'].append(['Naerien', DOY] + invar['Naerien'].tolist())
    outvar['Npc_aer'].append(['Npc_aer', DOY] + invar['Npc_aer'].tolist())  # -> ancien Npc_bis
    outvar['Npc_piv'].append(['Npc_piv', DOY] + invar['Npc_piv'].tolist())
    outvar['Npc_rac_fine'].append(['Npc_rac_fine', DOY] + invar['Npc_rac_fine'].tolist())
    outvar['Nuptake_sol'].append(['Nuptake_sol', DOY] + invar['Nuptake_sol'].tolist())
    outvar['NNI'].append(['NNI', DOY] + invar['NNI'].tolist())
    outvar['Ndfa'].append(['Ndfa', DOY] + invar['Ndfa'].tolist())
    outvar['Qfix'].append(['Qfix', DOY] + invar['Qfix'].tolist())
    outvar['dMSenFeuil'].append(['dMSenFeuil', DOY] + invar['dMSenFeuil'])
    outvar['dMSenTige'].append(['dMSenTige', DOY] + invar['dMSenTige'])
    outvar['MS_pivot'].append(['MS_pivot', DOY] + invar['MS_pivot'])
    outvar['MS_rac_fine'].append(['MS_rac_fine', DOY] + invar['MS_rac_fine'])
    outvar['R_DemandC_Shoot'].append(['R_DemandC_Shoot', DOY] + invar['R_DemandC_Shoot'].tolist())
    outvar['RUE'].append(['RUE', DOY] + invar['RUEactu'].tolist())
    outvar['DemCp'].append(['DemCp', DOY] + IOxls.dic2vec(nbplantes, invar['DemCp']))
    outvar['remob'].append(['remob', DOY] + invar['remob'].tolist())
    outvar['dRLenSentot'].append(['dRLenSentot', DOY] + invar['dRLenSentot'].tolist())
    outvar['dMSenRoot'].append(['dMSenRoot', DOY] + invar['dMSenRoot'].tolist())
    outvar['RLTotNet'].append(['RLTotNet', DOY] + array(invar['RLTotNet']).tolist())
    outvar['MS_rac_fineNet'].append(['MS_rac_fineNet', DOY] + invar['MS_rac_fineNet'].tolist())
    outvar['perteN_rac_fine'].append(['perteN_rac_fine', DOY] + invar['perteN_rac_fine'].tolist())
    outvar['NBphyto'].append(['NBphyto', DOY] + invar['NBphyto'])
    outvar['NBapexAct'].append(
        ['NBapexAct', DOY] + invar['NBapexAct'])  # pour correction du nb phyto par rapport au comptage observe
    outvar['transpi'].append(['transpi', DOY] + invar['transpi'])
    outvar['cumtranspi'].append(['cumtranspi', DOY] + invar['cumtranspi'].tolist())

    # !! ces 4 sorties lucas ne sont pas au format attentdu!
    outvar['phmgPet'].append(['phmgPet', DOY] + list(map(max, invar['phmgPet'])))
    outvar['phmgEntr'].append(['phmgEntr', DOY] + list(map(max, invar['phmgEntr'])))
    outvar['phmgPet_m'].append(['phmgPet_m', DOY] + list(map(min, invar['phmgPet_m'])))
    outvar['phmgEntr_m'].append(['phmgEntr_m', DOY] + list(map(min, invar['phmgEntr_m'])))


    return invar, invar_sc, outvar, I_I0profilInPlant, ls_ftswStress, ls_NNIStress



def update_residue_mat(ls_mat_res, vCC, S, carto, lims_sol, ParamP, invar, opt_residu):
    """ Distribute senescing tissues in ls_mat_res - After plant senescence/per residu type """
    # ajout dans la matrice des residus
    for nump in range(len(invar['dMSenRoot'])):
        voxsol = riri.WhichVoxel(array(carto[nump]), [0., 0., 0.],
                                 [len(lims_sol[0]) - 1, len(lims_sol[1]) - 1, len(lims_sol[2]) - 1],
                                 [S.dxyz[0][0] * 100., S.dxyz[1][0] * 100., S.dxyz[2][0] * 100.])
        groupe_resid = int(ParamP[nump]['groupe_resid'])
        ls_mat_res[groupe_resid * 4 + 2][voxsol[2]][voxsol[1]][voxsol[0]] += invar['dMSenRoot'][nump]
        # a revoir: tenir compte du groupe_resid
        # tout mis en surface: faire une distrib dans le sol en profondeur!

    # ajout des pivots a faire avant mse a jour des cres
    if opt_residu == 1:  # option residu activee: mise a jour des cres
        if sum(list(map(sum, ls_mat_res))) > 0.:  # si de nouveaux residus (ou supeieur a un seuil
            for i in range(len(ls_mat_res)):
                mat_res = ls_mat_res[i]
                if sum(mat_res) > 0.:
                    S.mixResMat(mat_res, i, vCC[i])

    # calcul senesc a faire a l'echelle des axes plutot? -> a priori pas necessaire
    return [ls_mat_res, S]

#verif seescence des pivots?






#daily loop separated in 4 sub-funtionen 4 fonctions
#disentangle plant and soil steps at first! -> to allow external calls

#invar, outvar, ls_epsi, ls_demandeN_bis, temps = daily_growth_loop(ParamP, invar, outvar, res_trans, meteo_j, nbplantes, surfsolref, ls_ftswStress, ls_NNIStress, lsApex, lsApexAll)
#S, stateEV, ls_ftsw, ls_transp, ls_Act_Nuptake_plt = step_bilanWN_sol(S, par_SN, lims_sol, surfsolref, stateEV, Uval, b_, meteo_j,  mng_j, ParamP, invar, ls_epsi, ls_systrac, ls_demandeN_bis, opt_residu)
#invar, invar_sc, outvar, I_I0profilInPlant, ls_ftswStress, ls_NNIStress = Update_stress_loop(ParamP, invar, invar_sc, temps, DOY, nbplantes, surfsolref, ls_epsi, ls_ftsw, ls_transp, ls_Act_Nuptake_plt, ls_demandeN_bis, ls_ftswStress, lsOrgans, lsApex, start_time, cutNB, deltaI_I0, nbI_I0, I_I0profilLfPlant, I_I0profilPetPlant, I_I0profilInPlant, NlClasses, NaClasses, NlinClasses, outvar)
#ls_mat_res, S = update_residue_mat(ls_mat_res, vCC, S, carto, lims_sol, ParamP, invar, opt_residu)


#pourquoi residu semblent pas affecter les sorties et ls_mat_res remis a zero juste pres??? (parametrage de durre de vie?)
#completer les commentaires...
#separer ecriture de outvar dans une fonction specifique??





























###################################### old
#initial
def daily_growth_loop_oldini(ParamP, par_SN, invar, invar_sc, outvar, res_trans, S, Uval, stateEV, DOY, meteo_j, mng_j, PP, res_root, nbplantes, surfsolref, ls_ftswStress, past_time, lsOrgans, ls_NNIStress, ls_mat_res, lsApex, lsApexAll, ls_systrac, lims_sol, b_, opt_residu, vCC, carto, start_time, cutNB, deltaI_I0, nbI_I0, I_I0profilLfPlant, I_I0profilPetPlant, I_I0profilInPlant, NlClasses, NaClasses, NlinClasses):
    """ """
    #global ParamP, par_SN, invar, invar_sc, outvar, res_trans
    #global S, Uval, stateEV, DOY, meteo_j, mng_j, PP, res_root, nbplantes, surfsolref, ls_ftswStress, past_time, lsOrgans, ls_NNIStress, ls_mat_res
    #global lsApex, lsApexAll, ls_systrac, lims_sol, b_, opt_residu, vCC, carto, start_time, cutNB, I_I0profilInPlant, deltaI_I0, nbI_I0, I_I0profilLfPlant, I_I0profilPetPlant, I_I0profilInPlant, NlClasses, NaClasses, NlinClasses
    #beaucoup de ces vaiables globales a passer comme argument de fonction?

    # calcul de ls_epsi
    invar['parap'] = array(list(map(sum, invar['PARaPlante'])))
    invar['parip'] = array(list(map(sum, invar['PARiPlante'])))
    # qatot= sum(res_trans[-1][:][:])*3600.*24/1000000. + sum(invar['parip'])#(MJ.day-1) #approximatif! a reprendre avec un vrai bilan radiatif
    # print sum(res_trans[-1][:][:]), sum(res_trans[-1][:][:])*3600.*24/1000000., sum(res_trans[-1][:][:])*3600.*24/1000000.  +   sum(invar['parip'])
    # ls_epsi = invar['parip']/qatot.tolist() #a reprendre : approximatif slmt! -> changera un peu avec un vrai bilan radiatif
    # transmi_sol = 1-sum(ls_epsi)
    # epsi = 1-transmi_sol #a reprendre pour differencier cible et vois #
    transmi_sol = sum(res_trans[-1][:][:]) / (meteo_j['I0'] * surfsolref)  # bon
    epsi = 1. - transmi_sol  # bon
    ls_epsi = epsi * invar['parip'] / (sum(invar['parip']) + 10e-15)

    graineC, graineN = sh.reserves_graine(invar, ParamP)

    # calcul de Biomasse tot
    stressHRUE = array(ls_ftswStress['WaterTreshRUE'])
    stressNRUE = array(ls_NNIStress['NTreshRUE'])
    stressFIX = 1 - array(invar['Ndfa']) * array(
        riri.get_lsparami(ParamP, 'NODcost'))  # coeff 0.15 = 15% reduction RUE a 100% fixation -> a passer en paarmetre
    invar['RUEactu'] = array(riri.get_lsparami(ParamP, 'RUE')) * stressHRUE * stressNRUE * stressFIX
    invar['PARaPlanteU'] = array(ls_epsi) * 0.95 * meteo_j[
        'I0'] * 3600. * 24 / 1000000. * surfsolref  # facteur 0.95 pour reflectance / PARa used for calculation
    dM = invar['PARaPlanteU'] * invar['RUEactu'] + graineC
    # dM2 = array(dpar) * array(get_lsparami(ParamP, 'RUE'))

    # allocation
    froot = sh.rootalloc(riri.get_lsparami(ParamP, 'alloc_root'), invar['MS_aer_cumul'])  # fraction aux racines
    for nump in range(nbplantes):
        if invar['germination'][nump] < 2:  # tout aux racines avant apparition de la premiere feuille
            froot[nump] = 0.99

    invar['remob'] = sh.Cremob(array(IOxls.dic2vec(nbplantes, invar['DemCp'])), invar['R_DemandC_Shoot'],
                               invar['MS_pivot'])  # vraiment marginal
    rac_fine = dM * froot * array(
        riri.get_lsparami(ParamP, 'frac_rac_fine'))  # * rtd.filtre_ratio(invar['R_DemandC_Shoot'])
    pivot = dM * froot * (1 - array(riri.get_lsparami(ParamP, 'frac_rac_fine'))) - invar['remob']
    aer = dM - rac_fine - pivot + invar['remob']
    ffeuil = array(IOxls.dic2vec(nbplantes, invar['DemCp_lf'])) / (
                array(IOxls.dic2vec(nbplantes, invar['DemCp'])) + 10e-12)  # fraction aux feuilles
    feuil = aer * ffeuil
    tige = aer * (1 - ffeuil)

    invar['Mtot'].append(dM.tolist())
    invar['Mrac_fine'].append(rac_fine.tolist())  # matrice des delta MSrac fine par date
    invar['Mpivot'].append(pivot.tolist())  # matrice des delta MSpivot par date
    invar['Maerien'].append(aer.tolist())  # matrice des delta MSaerien par date
    invar['Mfeuil'].append(feuil.tolist())  # matrice des delta MSfeuil par date
    invar['MS_pivot'] = list(map(sum, IOtable.t_list(invar['Mpivot'])))  # vecteur des MSpivot cumule au temps t
    invar['MS_aerien'] = list(map(sum, IOtable.t_list(invar['Maerien'])))  # vecteur des MSaerien cumule au temps t
    invar['MS_feuil'] = list(map(sum, IOtable.t_list(invar['Mfeuil'])))  # vecteur des MSfeuil cumule au temps t
    invar['MS_aer_cumul'] += aer
    invar['MS_tot'] = list(map(sum, IOtable.t_list(invar['Mtot'])))
    invar['MS_rac_fine'] = list(map(sum, IOtable.t_list(invar['Mrac_fine'])))  # vecteur des MSraines_fines cumule au temps t
    invar['DiampivMax'] = sqrt(invar['MS_pivot'] * array(riri.get_lsparami(ParamP, 'DPivot2_coeff')))
    # invar['RLTot'] = array(map(sum, IOtable.t_list(invar['Mrac_fine']))) * array(riri.get_lsparami(ParamP, 'SRL')) #somme de toutes les racinesfines produites par plante
    invar['NBsh'], invar['NBI'] = sh.calcNB_NI(lsApex, nbplantes, seuilcountTige=0.25, seuilNItige=0.25)
    nbsh_2, nb1_2 = sh.calcNB_NI(lsApexAll, nbplantes, seuilcountTige=0.25,
                                 seuilNItige=0.25)  # recalcul sur tous les axes pour eviter bug des arret de tiges
    for nump in range(nbplantes):
        if nb1_2[nump] > invar['NBI'][nump]:
            invar['NBI'][nump] = nb1_2[nump]

    invar['L_Sp'] = array(invar['MS_feuil']) / (array(invar['MS_aerien']) - array(invar['MS_feuil']) + 10e-12)

    # ajout des bilan C plante pour sorties / m2
    outvar['BilanC_PARa'].append(sum(invar['PARaPlanteU']) / surfsolref)
    outvar['BilanC_RUE'].append(sum(dM) / sum(invar['PARaPlanteU']))
    outvar['BilanCdMStot'].append(sum(dM) / surfsolref)
    outvar['BilanCdMrac_fine'].append(sum(rac_fine) / surfsolref)
    outvar['BilanCdMpivot'].append(sum(pivot) / surfsolref)
    outvar['BilanCdMaer'].append(sum(aer) / surfsolref)
    outvar['BilanCdMSenFeuil'].append(sum(invar['dMSenFeuil']) / surfsolref)
    outvar['BilanCdMSenTige'].append(sum(invar['dMSenTige']) / surfsolref)

    # print("MS AERIEN",invar['MS_aerien'],invar['MS_aer_cumul'])
    # print invar['Mtot']

    # for nump in range(nbplantes):
    #    RLProfil[nump] = rtd.updateRootLenprofil(invar['RLTot'][nump], RprospectProfil[nump], RLProfil[nump])

    # ancien pas base sur enveloppes
    # ls_roots = sol.build_ls_roots_mult(RLProfil, S)

    # testRL = updateRootDistrib(invar['RLTot'][0], ls_systrac[0], lims_sol)
    # ls_roots = rtd.build_ls_roots_mult(invar['RLTot'], ls_systrac, lims_sol) #ancien calcul base sur SRL fixe
    ls_roots = rtd.build_ls_roots_mult(array(invar['RLTotNet']) * 100. + 10e-15, ls_systrac,
                                       lims_sol)  # !*100 pour passer en cm et tester absoption d'azote (normalement m) #a passer apres calcul de longuer de racine!

    # preparation des entrees eau
    Rain = meteo_j['Precip']
    Irrig = mng_j['Irrig']  # ['irrig_Rh1N']#R1N = sol_nu

    # preparation des entrees azote
    mapN_Rain = 1. * S.m_1[0, :, :] * Rain * par_SN['concrr']  # Nmin de la pluie
    mapN_Irrig = 1. * S.m_1[0, :, :] * Irrig * par_SN['concrr']  # Nmin de l'eau d'irrigation
    mapN_fertNO3 = 1. * S.m_1[0, :, :] * mng_j['FertNO3'] * S.m_vox_surf[0, :, :] / 10000.  # kg N par voxel
    mapN_fertNH4 = 1. * S.m_1[0, :, :] * mng_j['FertNH4'] * S.m_vox_surf[0, :, :] / 10000.  # kg N par voxel
    S.updateTsol(meteo_j['Tsol'])  # (meteo_j['TmoyDay'])#(meteo_j['Tsol'])# #Tsol forcee comme dans STICS

    ls_demandeN = array(invar[
                            'DemandN_Tot']) * 0.001 + 1e-15  # en kg N.plant-1 #[1e-12]*nbplantes #sera a renseigner -> la, force a zero - devra utiliser invar['DemandN_Tot'] qui est mis a jour + loin #en kg N
    Npc_aer = array(invar['Naerien']) / (
                aer + array(invar['MS_aerien'])) * 100.  # Npc avec accroissement de biomasse pour calculer la demande
    Npc_piv = array(invar['Npivot']) / (pivot + array(invar['MS_pivot'])) * 100.
    Npc_rac_fine = array(invar['Nrac_fine']) / (rac_fine + array(invar['MS_rac_fine'])) * 100.

    invar['NreservPiv'] = array(invar['Npivot']) * (Npc_piv - array(riri.get_lsparami(ParamP, 'NminPiv'))) / Npc_piv
    invar['NreservPiv'][invar['NreservPiv'] < 0.] = 0.  # verifier que depasse pas zero!!

    ls_demandeN_aer = solN.demandeNdefaut2(MSp=array(invar['MS_aerien']), dMSp=aer, Npc=Npc_aer, surfsolref=surfsolref,
                                           a=array(riri.get_lsparami(ParamP, 'ADIL')),
                                           b1=array(riri.get_lsparami(ParamP, 'BDILi')), b2=array(
            riri.get_lsparami(ParamP, 'BDIL'))) * 0.001 + 1e-15  # en kg N.plant-1
    ls_demandN_piv = solN.demandeNroot(array(invar['MS_pivot']), pivot, Npc_piv, surfsolref,
                                       array(riri.get_lsparami(ParamP, 'NoptPiv'))) * 0.001 + 1e-15  # en kg N.plant-1
    ls_demandN_rac_fine = solN.demandeNroot(array(invar['MS_rac_fine']), rac_fine, Npc_rac_fine, surfsolref, array(
        riri.get_lsparami(ParamP, 'NoptFR'))) * 0.001 + 1e-15  # en kg N.plant-1

    ls_demandeN_bis = ls_demandeN_aer + ls_demandN_piv + ls_demandN_rac_fine
    fracNaer = ls_demandeN_aer / ls_demandeN_bis
    fracNpiv = ls_demandN_piv / ls_demandeN_bis
    fracNrac_fine = ls_demandN_rac_fine / ls_demandeN_bis

    invar['DemandN_TotAer'] = ls_demandeN_aer

    # print invar['Maerien']#invar['MS_aerien']
    # print aer

    # step bilans
    treshEffRoots_ = 10e10  # valeur pour forcer a prendre densite effective
    ls_transp, evapo_tot, Drainage, stateEV, ls_m_transpi, m_evap, ls_ftsw = S.stepWBmc(meteo_j['Et0'] * surfsolref,
                                                                                        ls_roots, ls_epsi,
                                                                                        Rain * surfsolref,
                                                                                        Irrig * surfsolref, stateEV,
                                                                                        par_SN['ZESX'], leafAlbedo=0.15,
                                                                                        U=Uval, b=b_, FTSWThreshold=0.4,
                                                                                        treshEffRoots=treshEffRoots_,
                                                                                        opt=1)
    S.stepNB(par_SN)
    if opt_residu == 1:  # s'ily a des residus
        S.stepResidueMin(par_SN)
        S.stepMicrobioMin(par_SN)
    S.stepNitrif(par_SN)
    ActUpNtot, ls_Act_Nuptake_plt, ls_DQ_N, idmin = S.stepNuptakePlt(par_SN, ParamP, ls_roots, ls_m_transpi,
                                                                     ls_demandeN_bis)
    S.stepNINFILT(mapN_Rain, mapN_Irrig, mapN_fertNO3, mapN_fertNH4, Drainage, opt=1)

    #if sum(ls_transp) + evapo_tot > meteo_j['Et0'] * surfsolref:
    #    print meteo_j['Et0'] * surfsolref, sum(ls_transp), evapo_tot  # Rain*surfsolref, Irrig*surfsolref,

    # update des indices de stress hydrique par plante
    p1, p2, p3, p4, p5, p6, p7, p8, p9 = [], [], [], [], [], [], [], [], []  # liste de parametres
    for nump in range(nbplantes):
        p1.append(ParamP[nump]['WaterTreshExpSurf'])
        p2.append(ParamP[nump]['WaterTreshDevII'])
        p3.append(ParamP[nump]['WaterTreshDevI'])
        p4.append(ParamP[nump]['WaterTreshFix'])
        p5.append(ParamP[nump]['WaterTreshRUE'])
        p6.append(ParamP[nump]['NTreshRUE'])
        p7.append(ParamP[nump]['NTreshExpSurf'])
        p8.append(ParamP[nump]['NTreshDev'])
        p9.append(ParamP[nump]['NTreshDevII'])

    ls_ftswStress = {}
    ls_ftswStress['WaterTreshExpSurf'] = list(map(sh.FTSW_resp, ls_ftsw, p1))
    ls_ftswStress['WaterTreshDevII'] = list(map(sh.FTSW_resp, ls_ftsw, p2))
    ls_ftswStress['WaterTreshDevI'] = list(map(sh.FTSW_resp, ls_ftsw, p3))
    ls_ftswStress['WaterTreshFix'] = list(map(sh.FTSW_resp, ls_ftsw, p4))
    ls_ftswStress['WaterTreshRUE'] = list(map(sh.FTSW_resp, ls_ftsw, p5))

    # Uptake N et allocation
    invar['Nuptake_sol'] = array(list(map(sum, ls_Act_Nuptake_plt))) * 1000 + graineN  # g N.plant-1 #test ls_demandeN_bis*1000.#
    try:
        NremobC = invar['remob'] * invar['Npc_piv'] / 100.  # remobilise N pivot qui part avec le C
        invar['Naerien'] += invar['Nuptake_sol'] * fracNaer + NremobC  # uptake N va dans partie aeriennes au prorata des demandes
        invar['Npivot'] += invar['Nuptake_sol'] * fracNpiv - NremobC
    except:  # 1er step
        NremobC = 0.
        invar['Naerien'] += invar['Nuptake_sol'] * fracNaer + NremobC
        invar['Npivot'] += invar['Nuptake_sol'] * fracNpiv
        print('rem')

    invar['Nrac_fine'] += invar['Nuptake_sol'] * fracNrac_fine

    # Fixation et allocation
    maxFix = sh.Ndfa_max(invar['TT'], riri.get_lsparami(ParamP, 'DurDevFix')) * array(
        riri.get_lsparami(ParamP, 'MaxFix')) / 1000. * aer  # * invar['dTT']
    stressHFix = array(ls_ftswStress['WaterTreshFix']) * maxFix  # effet hydrique
    invar['Qfix'] = sh.ActualFix(ls_demandeN_bis * 1000., invar['Nuptake_sol'], stressHFix)  # g N.plant-1
    invar['Ndfa'] = invar['Qfix'] / (invar['Qfix'] + invar['Nuptake_sol'] + 1e-15)

    delta_besoinN_aerien = ls_demandeN_aer * 1000. - invar['Qfix'] * fracNaer - invar[
        'Nuptake_sol'] * fracNaer - NremobC  # besoin N are sont ils couverts? g N.plant-1
    NremobN = minimum(delta_besoinN_aerien, invar['NreservPiv'])  # si pas couvert remobilisation N du pivot directement
    NremobN[NremobN < 0.] = 0.  # verifie que pas de negatif

    # print 'Npivot', invar['Npivot'][0:2]
    # print 'NreservPiv', invar['NreservPiv'][0:2]
    # print 'delta_besoinN', delta_besoinN_aerien[0:2]
    # print 'NremobN', NremobN[0:2]

    invar['Naerien'] += invar['Qfix'] * fracNaer + NremobN
    invar['Npivot'] += invar['Qfix'] * fracNpiv - NremobN
    invar['NreservPiv'] -= NremobN
    invar['Nrac_fine'] += invar['Qfix'] * fracNrac_fine  # total : vivantes et mortes

    # effet feedback N pas fait (priorite) -> necessaire???
    # mise a jour Npc et calcul NNI

    invar['Npc_aer'] = array(invar['Naerien']) / (aer + array(invar['MS_aerien'])) * 100.  # %
    invar['Npc_piv'] = array(invar['Npivot']) / (pivot + array(invar['MS_pivot'])) * 100.  # %
    invar['Npc_rac_fine'] = array(invar['Nrac_fine']) / (rac_fine + array(invar['MS_rac_fine'])) * 100.  # %

    # print 'Npc_piv', invar['Npc_piv'][0:2]

    critN_inst = solN.critN(sum(aer + array(invar['MS_aerien'])) / (surfsolref * 100.))  # azote critique couvert
    invar['NNI'] = invar['Npc_aer'] / critN_inst

    # update des indices de stress N par plante
    ls_NNIStress = {}
    ls_NNIStress['NTreshRUE'] = list(map(sh.NNI_resp, invar['NNI'], p6))
    ls_NNIStress['NTreshExpSurf'] = list(map(sh.NNI_resp, invar['NNI'], p7))
    ls_NNIStress['NTreshDev'] = list(map(sh.NNI_resp, invar['NNI'], p8))
    ls_NNIStress['NTreshDevII'] = list(map(sh.NNI_resp, invar['NNI'], p9))

    # print invar['TT'], Ndfa_max(invar['TT'], riri.get_lsparami(ParamP, 'DurDevFix')), maxFix, stressHFix
    # print invar['TT'], ls_demandeN_bis, invar['Nuptake_sol'], stressHFix
    # print sum(mapN_Rain), sum(mapN_Irrig), sum(mapN_fertNO3), sum(mapN_fertNH4), meteo_j['Tsol']
    # print ls_demandeN_bis, ls_demandeN, Npc_temp, array(map(sum, ls_Act_Nuptake_plt)), invar['Naerien'] #pour convertir en g N
    # print invar['Npc_bis']
    # print ls_demandeN_bis[0], ls_demandeN
    # print solN.critN(sum(aer+array(invar['MS_aerien']))#, invar['Npc_bis']

    # calcul offre/demandeC
    tab = IOtable.conv_dataframe(IOtable.t_list(lsOrgans))
    # OffCp = calcOffreC (tab, 'plt')#pas utilise??!
    # invar['DemCp'] = calcDemandeC(tab, 'plt')#attention, pour que calcul soit bon, faut le STEPS  suivant mis a jour!-> a faire en StartEach
    # invar['L_Sp'] = sh.calcLeafStemRatio(ParamP, tab, lsAxes)

    # calcul surf par tige
    invar_sc['plt']['Surf'], invar_sc['plt']['SurfVerte'], invar_sc['sh']['Surf'], invar_sc['sh']['SurfVerte'], \
    invar_sc['ax']['Surf'], invar_sc['ax']['SurfVerte'], invar_sc['plt']['PARaF'], invar_sc['sh']['PARaF'], \
    invar_sc['ax']['PARaF'], invar_sc['ax']['AgePiv'], invar_sc['ax']['MaxPARaF'] = sh.calcSurfLightScales(ParamP,
                                                                                                           IOtable.conv_dataframe(
                                                                                                               IOtable.t_list(
                                                                                                                   lsOrgans)))
    # calcul de fraction de PARa par pivot
    invar_sc['ax']['fPARaPiv'] = rt.calc_daxfPARaPiv(nbplantes, invar_sc['ax']['AgePiv'], invar_sc['plt']['PARaF'],
                                                     invar_sc['ax']['PARaF'])
    # calcul demande par pivot
    invar_sc['ax']['DemCRac'], invar_sc['ax']['NRac'] = rt.calc_DemandC_roots(ParamP, invar_sc['ax']['AgePiv'],
                                                                              invar['dTTsol'],
                                                                              invar_sc['ax']['QDCmoyRac'], nbnodale)

    # calcul biomasse, diametres pivots indivs, QDC des racines, increment de longueur et SRL
    daxPiv = rt.distrib_dM_ax(invar_sc['ax']['fPARaPiv'], pivot, Frac_piv_sem=riri.get_lsparami(ParamP, 'Frac_piv_sem'),
                              Frac_piv_loc=riri.get_lsparami(ParamP,
                                                             'Frac_piv_loc'))  # rt.distrib_dM_ax(invar_sc['ax']['fPARaPiv'], pivot)
    invar_sc['ax']['MaxPiv'] = IOxls.add_dic(daxPiv, invar_sc['ax']['MaxPiv'])
    invar_sc['ax']['DiampivMax'] = rt.calc_DiamPiv(ParamP, invar_sc['ax']['MaxPiv'])
    invar_sc['ax']['OfrCRac'] = rt.distrib_dM_ax(invar_sc['ax']['fPARaPiv'], rac_fine,
                                                 Frac_piv_sem=riri.get_lsparami(ParamP, 'Frac_piv_sem'),
                                                 Frac_piv_loc=riri.get_lsparami(ParamP, 'Frac_piv_loc'))
    invar_sc['ax']['QDCRac'] = rt.calc_QDC_roots(invar_sc['ax']['OfrCRac'], invar_sc['ax']['DemCRac'])
    invar_sc['ax']['QDCmoyRac'] = rt.calc_QDCmoy_roots(invar_sc['ax']['QDCRac'], invar_sc['ax']['QDCmoyRac'],
                                                       invar_sc['ax']['AgePiv'], invar['dTTsol'])
    invar_sc['ax']['StressHmoyRac'] = rt.calc_StressHmoy_roots(invar_sc['ax']['StressHRac'],
                                                               invar_sc['ax']['PonderStressHRac'],
                                                               invar_sc['ax']['StressHmoyRac'],
                                                               invar_sc['ax']['AgePiv'], invar[
                                                                   'dTTsol'])  # (dStressH, dPonder, dStressHmoy, dAgePiv, dTT)

    invar_sc['ax']['dlRac'] = rt.calc_dLong_roots(ParamP, invar_sc['ax']['NRac'], invar['dTTsol'],
                                                  invar_sc['ax']['QDCRac'], invar_sc['ax']['StressHRac'],
                                                  invar_sc['ax'][
                                                      'PonderStressHRac'])  # passe STEPS, mais devrait filer les dTT de chaque plante
    invar_sc['ax']['cumlRac'] = IOxls.add_dic(invar_sc['ax']['dlRac'], invar_sc['ax']['cumlRac'])
    invar['RLen1'], invar['RLen2'], invar['RLen3'], invar['RLentot'] = rt.cumul_plante_Lrac(nbplantes,
                                                                                            invar_sc['ax']['cumlRac'])
    dl1, dl2, dl3, dltot = rt.cumul_plante_Lrac(nbplantes,
                                                invar_sc['ax']['dlRac'])  # calcul des delta de longueur par plante
    invar['dRLen2'].append(dl2)  # stocke les dl du jour pour cacalcul senescence de plus tard
    invar['dRLen3'].append(dl3)
    # invar['SRL'] = invar['RLentot']/(invar['MS_rac_fine'][0]+10e-15)
    # print invar_sc['ax']['QDCRac']

    # print 'graine', graineC, dltot, invar['Surfcoty'], invar['Mcoty']#

    dur2 = (array(riri.get_lsparami(ParamP, 'GDs2')) + array(
        riri.get_lsparami(ParamP, 'LDs2'))) / 20.  # en jours a 20 degres!
    dur3 = (array(riri.get_lsparami(ParamP, 'GDs3')) + array(
        riri.get_lsparami(ParamP, 'LDs3'))) / 20.  # en jours a 20 degres!
    invar['dRLenSentot'], invar['dMSenRoot'] = rt.calc_root_senescence(invar['dRLen2'], invar['dRLen3'], dur2, dur3,
                                                                       array(invar['SRL']))
    invar['RLTotNet'] = array(invar['RLTotNet']) + dltot - invar['dRLenSentot']
    invar['MS_rac_fineNet'] = array(invar['MS_rac_fineNet']) + rac_fine - invar['dMSenRoot']
    invar['SRL'] = invar['RLTotNet'] / (invar['MS_rac_fineNet'][0] + 10e-15)

    invar['perteN_rac_fine'] = invar['dMSenRoot'] * invar['Npc_rac_fine'] / 100.
    # sortir une variable cumule d'N des rac mortes? -> compement a invar['Nrac_fine'] qui comprend les deux

    # ajout dans la matrice des residus
    for nump in range(len(invar['dMSenRoot'])):
        voxsol = riri.WhichVoxel(array(carto[nump]), [0., 0., 0.],
                                 [len(lims_sol[0]) - 1, len(lims_sol[1]) - 1, len(lims_sol[2]) - 1],
                                 [S.dxyz[0][0] * 100., S.dxyz[1][0] * 100., S.dxyz[2][0] * 100.])
        groupe_resid = int(ParamP[nump]['groupe_resid'])
        ls_mat_res[groupe_resid * 4 + 2][voxsol[2]][voxsol[1]][voxsol[0]] += invar['dMSenRoot'][nump]
        # a revoir: tenir compte du groupe_resid
        # tout mis en surface: faire une distrib dans le sol en profondeur!

    # ajout des pivots a faire avant mse a jour des cres
    if opt_residu == 1:  # option residu activee: mise a jour des cres
        if sum(map(sum, ls_mat_res)) > 0.:  # si de nouveaux residus (ou supeieur a un seuil
            for i in range(len(ls_mat_res)):
                mat_res = ls_mat_res[i]
                if sum(mat_res) > 0.:
                    S.mixResMat(mat_res, i, vCC[i])

    # calcul senesc a faire a l'echelle des axes plutot? -> a priori pas necessaire

    invar['R_DemandC_Root'] = rt.calc_QDplante(nbplantes, invar_sc['ax']['QDCRac'], invar_sc['ax']['cumlRac'],
                                               invar['RLentot'])
    invar['R_DemandC_Shoot'] = aer / (array(IOxls.dic2vec(nbplantes, invar['DemCp'])) + 10e-15)

    # if '0_0_0' in invar_sc['ax']['NRac'].keys():
    #    print invar_sc['ax']['NRac']['0_0_0']
    #    print invar_sc['ax']['QDCRac']['0_0_0']
    #    print invar_sc['ax']['dlRac']['0_0_0']
    # print invar['RLentot'], invar['MS_rac_fine'], invar['RLentot'][0]/(invar['MS_rac_fine'][0]+0.00000001)

    # calcul demandN -> a depalcer dans le starteach comme pour C?? -> pas utilise actuellement
    if lsApex != []:
        I_I0profilInPlant = sh.cumul_lenIN(lsApex, tab, I_I0profilInPlant, deltaI_I0, nbI_I0)

    # pas utilise
    for nump in range(nbplantes):
        invar['DemandN_Feuil'][nump] = sum(I_I0profilLfPlant[nump] * NaClasses)
        invar['DemandN_Pet'][nump] = sum(I_I0profilPetPlant[nump] * NlClasses)
        invar['DemandN_Stem'][nump] = sum(I_I0profilInPlant[nump] * NlinClasses)
        # invar['DemandN_Tot'][nump] = invar['DemandN_Feuil'][nump] + invar['DemandN_Pet'][nump] + invar['DemandN_Stem'][nump]

    invar['DemandN_Tot'] = ls_demandeN_bis * 1000.
    # print invar['DemandN_Tot'][0], sum(ls_Act_Nuptake_plt[0]), sum(ls_Act_Nuptake_plt[0])/(invar['DemandN_Tot'][0]+10e-12), sum(S.m_NO3)

    Npc = (array(invar['DemandN_Feuil']) + array(invar['DemandN_Pet']) + array(invar['DemandN_Stem'])) * 100. / array(
        invar['MS_aerien'])

    # temps de calcul
    past_time = time.time() - start_time


    # sorties
    outvar['TT'].append(['TT', DOY] + invar['TT'])
    outvar['time'].append(['time', DOY] + [past_time] * nbplantes)
    outvar['cutNB'].append(['cutNB', DOY] + [cutNB] * nbplantes)
    outvar['SurfPlante'].append(['SurfPlante', DOY] + list(map(sum, invar['SurfPlante'])))
    outvar['PARaPlante'].append(
        ['PARaPlante', DOY] + invar['PARaPlanteU'].tolist())  # append(['PARaPlante',DOY]+invar['parap'].tolist())
    outvar['PARiPlante'].append(['PARiPlante', DOY] + invar['parip'].tolist())
    outvar['epsi'].append(['epsi', DOY] + ls_epsi.tolist())
    outvar['dMSaer'].append(['dMSaer', DOY] + aer.tolist())
    outvar['Hplante'].append(['Hplante', DOY] + invar['Hplante'])
    outvar['Dplante'].append(['Dplante', DOY] + invar['Dplante'])
    outvar['RLTot'].append(['RLTot', DOY] + invar['RLentot'])
    outvar['RDepth'].append(['RDepth', DOY] + invar['RDepth'])
    outvar['MS_aerien'].append(['MSaerien', DOY] + invar['MS_aerien'])
    outvar['MS_feuil'].append(['MSfeuil', DOY] + invar['MS_feuil'])
    outvar['MS_tot'].append(['MStot', DOY] + invar['MS_tot'])
    outvar['countSh'].append(['countSh', DOY] + invar['countSh'])
    outvar['countShExp'].append(['countShExp', DOY] + invar['countShExp'])
    outvar['demandC'].append(['demandC', DOY] + IOxls.dic2vec(nbplantes, invar['DemCp']))
    outvar['Leaf_Stem'].append(['Leaf_Stem', DOY] + invar['L_Sp'].tolist())
    outvar['NBsh'].append(['NBsh', DOY] + invar['NBsh'])
    outvar['NBI'].append(['NBI', DOY] + invar['NBI'])
    outvar['FTSW'].append(['FTSW', DOY] + ls_ftsw)
    outvar['Etransp'].append(['Etransp', DOY] + ls_transp)
    outvar['DemandN_Feuil'].append(['DemandN_Feuil', DOY] + invar['DemandN_Feuil'])
    outvar['DemandN_Pet'].append(['DemandN_Pet', DOY] + invar['DemandN_Pet'])
    outvar['DemandN_Stem'].append(['DemandN_Stem', DOY] + invar['DemandN_Stem'])
    outvar['DemandN_Tot'].append(['DemandN_Tot', DOY] + invar['DemandN_Tot'].tolist())
    outvar['Npc'].append(['Npc', DOY] + Npc.tolist())
    outvar['NBD1'].append(['NBD1', DOY] + invar['NBD1'])
    outvar['NBB'].append(['NBB', DOY] + invar['NBB'])
    outvar['NBBexp'].append([['NBBexp', DOY] + invar['NBBexp']])
    outvar['R_DemandC_Root'].append(['R_DemandC_Root', DOY] + invar['R_DemandC_Root'])
    outvar['SRL'].append(['SRL', DOY] + invar['SRL'].tolist())
    outvar['DemandN_Tot_Aer'].append(['DemandN_Tot_Aer', DOY] + invar['DemandN_TotAer'].tolist())
    outvar['Naerien'].append(['Naerien', DOY] + invar['Naerien'].tolist())
    outvar['Npc_aer'].append(['Npc_aer', DOY] + invar['Npc_aer'].tolist())  # -> ancien Npc_bis
    outvar['Npc_piv'].append(['Npc_piv', DOY] + invar['Npc_piv'].tolist())
    outvar['Npc_rac_fine'].append(['Npc_rac_fine', DOY] + invar['Npc_rac_fine'].tolist())
    outvar['Nuptake_sol'].append(['Nuptake_sol', DOY] + invar['Nuptake_sol'].tolist())
    outvar['NNI'].append(['NNI', DOY] + invar['NNI'].tolist())
    outvar['Ndfa'].append(['Ndfa', DOY] + invar['Ndfa'].tolist())
    outvar['Qfix'].append(['Qfix', DOY] + invar['Qfix'].tolist())
    outvar['dMSenFeuil'].append(['dMSenFeuil', DOY] + invar['dMSenFeuil'])
    outvar['dMSenTige'].append(['dMSenTige', DOY] + invar['dMSenTige'])
    outvar['MS_pivot'].append(['MS_pivot', DOY] + invar['MS_pivot'])
    outvar['MS_rac_fine'].append(['MS_rac_fine', DOY] + invar['MS_rac_fine'])
    outvar['R_DemandC_Shoot'].append(['R_DemandC_Shoot', DOY] + invar['R_DemandC_Shoot'].tolist())
    outvar['RUE'].append(['RUE', DOY] + invar['RUEactu'].tolist())
    outvar['DemCp'].append(['DemCp', DOY] + IOxls.dic2vec(nbplantes, invar['DemCp']))
    outvar['remob'].append(['remob', DOY] + invar['remob'].tolist())
    outvar['dRLenSentot'].append(['dRLenSentot', DOY] + invar['dRLenSentot'].tolist())
    outvar['dMSenRoot'].append(['dMSenRoot', DOY] + invar['dMSenRoot'].tolist())
    outvar['RLTotNet'].append(['RLTotNet', DOY] + array(invar['RLTotNet']).tolist())
    outvar['MS_rac_fineNet'].append(['MS_rac_fineNet', DOY] + invar['MS_rac_fineNet'].tolist())
    outvar['perteN_rac_fine'].append(['perteN_rac_fine', DOY] + invar['perteN_rac_fine'].tolist())
    outvar['NBphyto'].append(['NBphyto', DOY] + invar['NBphyto'])
    outvar['NBapexAct'].append(
        ['NBapexAct', DOY] + invar['NBapexAct'])  # pour correction du nb phyto par rapport au comptage observe

    # !! ces 4 sorties lucas ne sont pas au format attentdu!
    outvar['phmgPet'].append(['phmgPet', DOY] + list(map(max, invar['phmgPet'])))
    outvar['phmgEntr'].append(['phmgEntr', DOY] + list(map(max, invar['phmgEntr'])))
    outvar['phmgPet_m'].append(['phmgPet_m', DOY] + list(map(min, invar['phmgPet_m'])))
    outvar['phmgEntr_m'].append(['phmgEntr_m', DOY] + list(map(min, invar['phmgEntr_m'])))

    # res_root.append(rtd.convd(RLProfil[0])) #pour exporter profil de racine (le faire pour tous les systemes?

    # HR sol
    # out_HR.append([DOY]+mean(S.HRp(), axis=1)[id_out,0].tolist())

    #return invar, invar_sc, outvar, S
    #return ParamP, par_SN, invar, invar_sc, outvar, res_trans, S, Uval, stateEV, DOY, meteo_j, mng_j, PP, res_root, nbplantes, surfsolref, ls_ftswStress, past_time, lsOrgans, ls_NNIStress, ls_mat_res, lsApex, lsApexAll, ls_systrac, lims_sol, b_, opt_residu, vCC, carto, start_time, cutNB, deltaI_I0, nbI_I0, I_I0profilLfPlant, I_I0profilPetPlant, I_I0profilInPlant, NlClasses, NaClasses, NlinClasses
    return invar, invar_sc, outvar, S, stateEV, I_I0profilInPlant, ls_ftswStress, ls_NNIStress, ls_mat_res


#after reorganising calculation order
def daily_growth_loop_modif(ParamP, par_SN, invar, invar_sc, outvar, res_trans, S, Uval, stateEV, DOY, meteo_j, mng_j, PP, res_root, nbplantes, surfsolref, ls_ftswStress, past_time, lsOrgans, ls_NNIStress, ls_mat_res, lsApex, lsApexAll, ls_systrac, lims_sol, b_, opt_residu, vCC, carto, start_time, cutNB, deltaI_I0, nbI_I0, I_I0profilLfPlant, I_I0profilPetPlant, I_I0profilInPlant, NlClasses, NaClasses, NlinClasses):
    """ """
    #global ParamP, par_SN, invar, invar_sc, outvar, res_trans
    #global S, Uval, stateEV, DOY, meteo_j, mng_j, PP, res_root, nbplantes, surfsolref, ls_ftswStress, past_time, lsOrgans, ls_NNIStress, ls_mat_res
    #global lsApex, lsApexAll, ls_systrac, lims_sol, b_, opt_residu, vCC, carto, start_time, cutNB, I_I0profilInPlant, deltaI_I0, nbI_I0, I_I0profilLfPlant, I_I0profilPetPlant, I_I0profilInPlant, NlClasses, NaClasses, NlinClasses
    #beaucoup de ces vaiables globales a passer comme argument de fonction?

    # calcul de ls_epsi
    invar['parap'] = array(list(map(sum, invar['PARaPlante'])))
    invar['parip'] = array(list(map(sum, invar['PARiPlante'])))
    # qatot= sum(res_trans[-1][:][:])*3600.*24/1000000. + sum(invar['parip'])#(MJ.day-1) #approximatif! a reprendre avec un vrai bilan radiatif
    # print sum(res_trans[-1][:][:]), sum(res_trans[-1][:][:])*3600.*24/1000000., sum(res_trans[-1][:][:])*3600.*24/1000000.  +   sum(invar['parip'])
    # ls_epsi = invar['parip']/qatot.tolist() #a reprendre : approximatif slmt! -> changera un peu avec un vrai bilan radiatif
    # transmi_sol = 1-sum(ls_epsi)
    # epsi = 1-transmi_sol #a reprendre pour differencier cible et vois #
    transmi_sol = sum(res_trans[-1][:][:]) / (meteo_j['I0'] * surfsolref)  # bon
    epsi = 1. - transmi_sol  # bon
    ls_epsi = epsi * invar['parip'] / (sum(invar['parip']) + 10e-15)

    graineC, graineN = sh.reserves_graine(invar, ParamP)

    # calcul de Biomasse tot
    stressHRUE = array(ls_ftswStress['WaterTreshRUE'])
    stressNRUE = array(ls_NNIStress['NTreshRUE'])
    stressFIX = 1 - array(invar['Ndfa']) * array(
        riri.get_lsparami(ParamP, 'NODcost'))  # coeff 0.15 = 15% reduction RUE a 100% fixation -> a passer en paarmetre
    invar['RUEactu'] = array(riri.get_lsparami(ParamP, 'RUE')) * stressHRUE * stressNRUE * stressFIX
    invar['PARaPlanteU'] = array(ls_epsi) * 0.95 * meteo_j[
        'I0'] * 3600. * 24 / 1000000. * surfsolref  # facteur 0.95 pour reflectance / PARa used for calculation
    dM = invar['PARaPlanteU'] * invar['RUEactu'] + graineC
    # dM2 = array(dpar) * array(get_lsparami(ParamP, 'RUE'))

    # allocation
    froot = sh.rootalloc(riri.get_lsparami(ParamP, 'alloc_root'), invar['MS_aer_cumul'])  # fraction aux racines
    for nump in range(nbplantes):
        if invar['germination'][nump] < 2:  # tout aux racines avant apparition de la premiere feuille
            froot[nump] = 0.99

    invar['remob'] = sh.Cremob(array(IOxls.dic2vec(nbplantes, invar['DemCp'])), invar['R_DemandC_Shoot'],
                               invar['MS_pivot'])  # vraiment marginal
    rac_fine = dM * froot * array(
        riri.get_lsparami(ParamP, 'frac_rac_fine'))  # * rtd.filtre_ratio(invar['R_DemandC_Shoot'])
    pivot = dM * froot * (1 - array(riri.get_lsparami(ParamP, 'frac_rac_fine'))) - invar['remob']
    aer = dM - rac_fine - pivot + invar['remob']
    ffeuil = array(IOxls.dic2vec(nbplantes, invar['DemCp_lf'])) / (
                array(IOxls.dic2vec(nbplantes, invar['DemCp'])) + 10e-12)  # fraction aux feuilles
    feuil = aer * ffeuil
    tige = aer * (1 - ffeuil)

    invar['Mtot'].append(dM.tolist())
    invar['Mrac_fine'].append(rac_fine.tolist())  # matrice des delta MSrac fine par date
    invar['Mpivot'].append(pivot.tolist())  # matrice des delta MSpivot par date
    invar['Maerien'].append(aer.tolist())  # matrice des delta MSaerien par date
    invar['Mfeuil'].append(feuil.tolist())  # matrice des delta MSfeuil par date
    invar['MS_pivot'] = list(map(sum, IOtable.t_list(invar['Mpivot'])))  # vecteur des MSpivot cumule au temps t
    invar['MS_aerien'] = list(map(sum, IOtable.t_list(invar['Maerien'])))  # vecteur des MSaerien cumule au temps t
    invar['MS_feuil'] = list(map(sum, IOtable.t_list(invar['Mfeuil'])))  # vecteur des MSfeuil cumule au temps t
    invar['MS_aer_cumul'] += aer
    invar['MS_tot'] = list(map(sum, IOtable.t_list(invar['Mtot'])))
    invar['MS_rac_fine'] = list(map(sum, IOtable.t_list(invar['Mrac_fine'])))  # vecteur des MSraines_fines cumule au temps t
    invar['DiampivMax'] = sqrt(invar['MS_pivot'] * array(riri.get_lsparami(ParamP, 'DPivot2_coeff')))
    # invar['RLTot'] = array(map(sum, IOtable.t_list(invar['Mrac_fine']))) * array(riri.get_lsparami(ParamP, 'SRL')) #somme de toutes les racinesfines produites par plante
    invar['NBsh'], invar['NBI'] = sh.calcNB_NI(lsApex, nbplantes, seuilcountTige=0.25, seuilNItige=0.25)
    nbsh_2, nb1_2 = sh.calcNB_NI(lsApexAll, nbplantes, seuilcountTige=0.25,
                                 seuilNItige=0.25)  # recalcul sur tous les axes pour eviter bug des arret de tiges
    for nump in range(nbplantes):
        if nb1_2[nump] > invar['NBI'][nump]:
            invar['NBI'][nump] = nb1_2[nump]

    invar['L_Sp'] = array(invar['MS_feuil']) / (array(invar['MS_aerien']) - array(invar['MS_feuil']) + 10e-12)



    # print("MS AERIEN",invar['MS_aerien'],invar['MS_aer_cumul'])
    # print invar['Mtot']

    ls_demandeN = array(invar[
                            'DemandN_Tot']) * 0.001 + 1e-15  # en kg N.plant-1 #[1e-12]*nbplantes #sera a renseigner -> la, force a zero - devra utiliser invar['DemandN_Tot'] qui est mis a jour + loin #en kg N
    Npc_aer = array(invar['Naerien']) / (
                aer + array(invar['MS_aerien'])) * 100.  # Npc avec accroissement de biomasse pour calculer la demande
    Npc_piv = array(invar['Npivot']) / (pivot + array(invar['MS_pivot'])) * 100.
    Npc_rac_fine = array(invar['Nrac_fine']) / (rac_fine + array(invar['MS_rac_fine'])) * 100.

    invar['NreservPiv'] = array(invar['Npivot']) * (Npc_piv - array(riri.get_lsparami(ParamP, 'NminPiv'))) / Npc_piv
    invar['NreservPiv'][invar['NreservPiv'] < 0.] = 0.  # verifier que depasse pas zero!!

    ls_demandeN_aer = solN.demandeNdefaut2(MSp=array(invar['MS_aerien']), dMSp=aer, Npc=Npc_aer, surfsolref=surfsolref,
                                           a=array(riri.get_lsparami(ParamP, 'ADIL')),
                                           b1=array(riri.get_lsparami(ParamP, 'BDILi')), b2=array(
            riri.get_lsparami(ParamP, 'BDIL'))) * 0.001 + 1e-15  # en kg N.plant-1
    ls_demandN_piv = solN.demandeNroot(array(invar['MS_pivot']), pivot, Npc_piv, surfsolref,
                                       array(riri.get_lsparami(ParamP, 'NoptPiv'))) * 0.001 + 1e-15  # en kg N.plant-1
    ls_demandN_rac_fine = solN.demandeNroot(array(invar['MS_rac_fine']), rac_fine, Npc_rac_fine, surfsolref, array(
        riri.get_lsparami(ParamP, 'NoptFR'))) * 0.001 + 1e-15  # en kg N.plant-1

    ls_demandeN_bis = ls_demandeN_aer + ls_demandN_piv + ls_demandN_rac_fine
    fracNaer = ls_demandeN_aer / ls_demandeN_bis
    fracNpiv = ls_demandN_piv / ls_demandeN_bis
    fracNrac_fine = ls_demandN_rac_fine / ls_demandeN_bis

    invar['DemandN_TotAer'] = ls_demandeN_aer

    # print invar['Maerien']#invar['MS_aerien']
    # print aer

    # ajout des bilan C plante pour sorties / m2
    outvar['BilanC_PARa'].append(sum(invar['PARaPlanteU']) / surfsolref)
    outvar['BilanC_RUE'].append(sum(dM) / sum(invar['PARaPlanteU']))
    outvar['BilanCdMStot'].append(sum(dM) / surfsolref)
    outvar['BilanCdMrac_fine'].append(sum(rac_fine) / surfsolref)
    outvar['BilanCdMpivot'].append(sum(pivot) / surfsolref)
    outvar['BilanCdMaer'].append(sum(aer) / surfsolref)
    outvar['BilanCdMSenFeuil'].append(sum(invar['dMSenFeuil']) / surfsolref)
    outvar['BilanCdMSenTige'].append(sum(invar['dMSenTige']) / surfsolref)



    # for nump in range(nbplantes):
    #    RLProfil[nump] = rtd.updateRootLenprofil(invar['RLTot'][nump], RprospectProfil[nump], RLProfil[nump])

    # ancien pas base sur enveloppes
    # ls_roots = sol.build_ls_roots_mult(RLProfil, S)
    # testRL = updateRootDistrib(invar['RLTot'][0], ls_systrac[0], lims_sol)
    # ls_roots = rtd.build_ls_roots_mult(invar['RLTot'], ls_systrac, lims_sol) #ancien calcul base sur SRL fixe
    ls_roots = rtd.build_ls_roots_mult(array(invar['RLTotNet']) * 100. + 10e-15, ls_systrac,
                                       lims_sol)  # !*100 pour passer en cm et tester absoption d'azote (normalement m) #a passer apres calcul de longuer de racine!

    # preparation des entrees eau
    Rain = meteo_j['Precip']
    Irrig = mng_j['Irrig']  # ['irrig_Rh1N']#R1N = sol_nu

    # preparation des entrees azote
    mapN_Rain = 1. * S.m_1[0, :, :] * Rain * par_SN['concrr']  # Nmin de la pluie
    mapN_Irrig = 1. * S.m_1[0, :, :] * Irrig * par_SN['concrr']  # Nmin de l'eau d'irrigation
    mapN_fertNO3 = 1. * S.m_1[0, :, :] * mng_j['FertNO3'] * S.m_vox_surf[0, :, :] / 10000.  # kg N par voxel
    mapN_fertNH4 = 1. * S.m_1[0, :, :] * mng_j['FertNH4'] * S.m_vox_surf[0, :, :] / 10000.  # kg N par voxel
    S.updateTsol(meteo_j['Tsol'])  # (meteo_j['TmoyDay'])#(meteo_j['Tsol'])# #Tsol forcee comme dans STICS






    # step bilans
    treshEffRoots_ = 10e10  # valeur pour forcer a prendre densite effective
    ls_transp, evapo_tot, Drainage, stateEV, ls_m_transpi, m_evap, ls_ftsw = S.stepWBmc(meteo_j['Et0'] * surfsolref,
                                                                                        ls_roots, ls_epsi,
                                                                                        Rain * surfsolref,
                                                                                        Irrig * surfsolref, stateEV,
                                                                                        par_SN['ZESX'], leafAlbedo=0.15,
                                                                                        U=Uval, b=b_, FTSWThreshold=0.4,
                                                                                        treshEffRoots=treshEffRoots_,
                                                                                        opt=1)
    S.stepNB(par_SN)
    if opt_residu == 1:  # s'ily a des residus
        S.stepResidueMin(par_SN)
        S.stepMicrobioMin(par_SN)
    S.stepNitrif(par_SN)
    ActUpNtot, ls_Act_Nuptake_plt, ls_DQ_N, idmin = S.stepNuptakePlt(par_SN, ParamP, ls_roots, ls_m_transpi,
                                                                     ls_demandeN_bis)
    S.stepNINFILT(mapN_Rain, mapN_Irrig, mapN_fertNO3, mapN_fertNH4, Drainage, opt=1)

    #if sum(ls_transp) + evapo_tot > meteo_j['Et0'] * surfsolref:
    #    print meteo_j['Et0'] * surfsolref, sum(ls_transp), evapo_tot  # Rain*surfsolref, Irrig*surfsolref,


    # Uptake N et allocation
    invar['Nuptake_sol'] = array(list(map(sum, ls_Act_Nuptake_plt))) * 1000 + graineN  # g N.plant-1 #test ls_demandeN_bis*1000.#
    try:
        NremobC = invar['remob'] * invar['Npc_piv'] / 100.  # remobilise N pivot qui part avec le C
        invar['Naerien'] += invar['Nuptake_sol'] * fracNaer + NremobC  # uptake N va dans partie aeriennes au prorata des demandes
        invar['Npivot'] += invar['Nuptake_sol'] * fracNpiv - NremobC
    except:  # 1er step
        NremobC = 0.
        invar['Naerien'] += invar['Nuptake_sol'] * fracNaer + NremobC
        invar['Npivot'] += invar['Nuptake_sol'] * fracNpiv
        print('rem')

    invar['Nrac_fine'] += invar['Nuptake_sol'] * fracNrac_fine

    # Fixation et allocation
    maxFix = sh.Ndfa_max(invar['TT'], riri.get_lsparami(ParamP, 'DurDevFix')) * array(
        riri.get_lsparami(ParamP, 'MaxFix')) / 1000. * aer  # * invar['dTT']
    stressHFix = array(ls_ftswStress['WaterTreshFix']) * maxFix  # effet hydrique
    invar['Qfix'] = sh.ActualFix(ls_demandeN_bis * 1000., invar['Nuptake_sol'], stressHFix)  # g N.plant-1
    invar['Ndfa'] = invar['Qfix'] / (invar['Qfix'] + invar['Nuptake_sol'] + 1e-15)

    delta_besoinN_aerien = ls_demandeN_aer * 1000. - invar['Qfix'] * fracNaer - invar[
        'Nuptake_sol'] * fracNaer - NremobC  # besoin N are sont ils couverts? g N.plant-1
    NremobN = minimum(delta_besoinN_aerien, invar['NreservPiv'])  # si pas couvert remobilisation N du pivot directement
    NremobN[NremobN < 0.] = 0.  # verifie que pas de negatif

    # print 'Npivot', invar['Npivot'][0:2]
    # print 'NreservPiv', invar['NreservPiv'][0:2]
    # print 'delta_besoinN', delta_besoinN_aerien[0:2]
    # print 'NremobN', NremobN[0:2]

    invar['Naerien'] += invar['Qfix'] * fracNaer + NremobN
    invar['Npivot'] += invar['Qfix'] * fracNpiv - NremobN
    invar['NreservPiv'] -= NremobN
    invar['Nrac_fine'] += invar['Qfix'] * fracNrac_fine  # total : vivantes et mortes

    # effet feedback N pas fait (priorite) -> necessaire???
    # mise a jour Npc et calcul NNI

    invar['Npc_aer'] = array(invar['Naerien']) / (aer + array(invar['MS_aerien'])) * 100.  # %
    invar['Npc_piv'] = array(invar['Npivot']) / (pivot + array(invar['MS_pivot'])) * 100.  # %
    invar['Npc_rac_fine'] = array(invar['Nrac_fine']) / (rac_fine + array(invar['MS_rac_fine'])) * 100.  # %

    # print 'Npc_piv', invar['Npc_piv'][0:2]

    critN_inst = solN.critN(sum(aer + array(invar['MS_aerien'])) / (surfsolref * 100.))  # azote critique couvert
    invar['NNI'] = invar['Npc_aer'] / critN_inst


    # update des indices de stress hydrique par plante
    p1, p2, p3, p4, p5, p6, p7, p8, p9 = [], [], [], [], [], [], [], [], []  # liste de parametres
    for nump in range(nbplantes):
        p1.append(ParamP[nump]['WaterTreshExpSurf'])
        p2.append(ParamP[nump]['WaterTreshDevII'])
        p3.append(ParamP[nump]['WaterTreshDevI'])
        p4.append(ParamP[nump]['WaterTreshFix'])
        p5.append(ParamP[nump]['WaterTreshRUE'])
        p6.append(ParamP[nump]['NTreshRUE'])
        p7.append(ParamP[nump]['NTreshExpSurf'])
        p8.append(ParamP[nump]['NTreshDev'])
        p9.append(ParamP[nump]['NTreshDevII'])

    ls_ftswStress = {}
    ls_ftswStress['WaterTreshExpSurf'] = list(map(sh.FTSW_resp, ls_ftsw, p1))
    ls_ftswStress['WaterTreshDevII'] = list(map(sh.FTSW_resp, ls_ftsw, p2))
    ls_ftswStress['WaterTreshDevI'] = list(map(sh.FTSW_resp, ls_ftsw, p3))
    ls_ftswStress['WaterTreshFix'] = list(map(sh.FTSW_resp, ls_ftsw, p4))
    ls_ftswStress['WaterTreshRUE'] = list(map(sh.FTSW_resp, ls_ftsw, p5))

    # update des indices de stress N par plante
    ls_NNIStress = {}
    ls_NNIStress['NTreshRUE'] = list(map(sh.NNI_resp, invar['NNI'], p6))
    ls_NNIStress['NTreshExpSurf'] = list(map(sh.NNI_resp, invar['NNI'], p7))
    ls_NNIStress['NTreshDev'] = list(map(sh.NNI_resp, invar['NNI'], p8))
    ls_NNIStress['NTreshDevII'] = list(map(sh.NNI_resp, invar['NNI'], p9))

    # print invar['TT'], Ndfa_max(invar['TT'], riri.get_lsparami(ParamP, 'DurDevFix')), maxFix, stressHFix
    # print invar['TT'], ls_demandeN_bis, invar['Nuptake_sol'], stressHFix
    # print sum(mapN_Rain), sum(mapN_Irrig), sum(mapN_fertNO3), sum(mapN_fertNH4), meteo_j['Tsol']
    # print ls_demandeN_bis, ls_demandeN, Npc_temp, array(map(sum, ls_Act_Nuptake_plt)), invar['Naerien'] #pour convertir en g N
    # print invar['Npc_bis']
    # print ls_demandeN_bis[0], ls_demandeN
    # print solN.critN(sum(aer+array(invar['MS_aerien']))#, invar['Npc_bis']

    # calcul offre/demandeC
    tab = IOtable.conv_dataframe(IOtable.t_list(lsOrgans))
    # OffCp = calcOffreC (tab, 'plt')#pas utilise??!
    # invar['DemCp'] = calcDemandeC(tab, 'plt')#attention, pour que calcul soit bon, faut le STEPS  suivant mis a jour!-> a faire en StartEach
    # invar['L_Sp'] = sh.calcLeafStemRatio(ParamP, tab, lsAxes)

    # calcul surf par tige
    invar_sc['plt']['Surf'], invar_sc['plt']['SurfVerte'], invar_sc['sh']['Surf'], invar_sc['sh']['SurfVerte'], \
    invar_sc['ax']['Surf'], invar_sc['ax']['SurfVerte'], invar_sc['plt']['PARaF'], invar_sc['sh']['PARaF'], \
    invar_sc['ax']['PARaF'], invar_sc['ax']['AgePiv'], invar_sc['ax']['MaxPARaF'] = sh.calcSurfLightScales(ParamP,
                                                                                                           IOtable.conv_dataframe(
                                                                                                               IOtable.t_list(
                                                                                                                   lsOrgans)))
    # calcul de fraction de PARa par pivot
    invar_sc['ax']['fPARaPiv'] = rt.calc_daxfPARaPiv(nbplantes, invar_sc['ax']['AgePiv'], invar_sc['plt']['PARaF'],
                                                     invar_sc['ax']['PARaF'])
    # calcul demande par pivot
    invar_sc['ax']['DemCRac'], invar_sc['ax']['NRac'] = rt.calc_DemandC_roots(ParamP, invar_sc['ax']['AgePiv'],
                                                                              invar['dTTsol'],
                                                                              invar_sc['ax']['QDCmoyRac'])

    # calcul biomasse, diametres pivots indivs, QDC des racines, increment de longueur et SRL
    daxPiv = rt.distrib_dM_ax(invar_sc['ax']['fPARaPiv'], pivot, Frac_piv_sem=riri.get_lsparami(ParamP, 'Frac_piv_sem'),
                              Frac_piv_loc=riri.get_lsparami(ParamP,
                                                             'Frac_piv_loc'))  # rt.distrib_dM_ax(invar_sc['ax']['fPARaPiv'], pivot)
    invar_sc['ax']['MaxPiv'] = IOxls.add_dic(daxPiv, invar_sc['ax']['MaxPiv'])
    invar_sc['ax']['DiampivMax'] = rt.calc_DiamPiv(ParamP, invar_sc['ax']['MaxPiv'])
    invar_sc['ax']['OfrCRac'] = rt.distrib_dM_ax(invar_sc['ax']['fPARaPiv'], rac_fine,
                                                 Frac_piv_sem=riri.get_lsparami(ParamP, 'Frac_piv_sem'),
                                                 Frac_piv_loc=riri.get_lsparami(ParamP, 'Frac_piv_loc'))
    invar_sc['ax']['QDCRac'] = rt.calc_QDC_roots(invar_sc['ax']['OfrCRac'], invar_sc['ax']['DemCRac'])
    invar_sc['ax']['QDCmoyRac'] = rt.calc_QDCmoy_roots(invar_sc['ax']['QDCRac'], invar_sc['ax']['QDCmoyRac'],
                                                       invar_sc['ax']['AgePiv'], invar['dTTsol'])
    invar_sc['ax']['StressHmoyRac'] = rt.calc_StressHmoy_roots(invar_sc['ax']['StressHRac'],
                                                               invar_sc['ax']['PonderStressHRac'],
                                                               invar_sc['ax']['StressHmoyRac'],
                                                               invar_sc['ax']['AgePiv'], invar[
                                                                   'dTTsol'])  # (dStressH, dPonder, dStressHmoy, dAgePiv, dTT)

    invar_sc['ax']['dlRac'] = rt.calc_dLong_roots(ParamP, invar_sc['ax']['NRac'], invar['dTTsol'],
                                                  invar_sc['ax']['QDCRac'], invar_sc['ax']['StressHRac'],
                                                  invar_sc['ax'][
                                                      'PonderStressHRac'])  # passe STEPS, mais devrait filer les dTT de chaque plante
    invar_sc['ax']['cumlRac'] = IOxls.add_dic(invar_sc['ax']['dlRac'], invar_sc['ax']['cumlRac'])
    invar['RLen1'], invar['RLen2'], invar['RLen3'], invar['RLentot'] = rt.cumul_plante_Lrac(nbplantes,
                                                                                            invar_sc['ax']['cumlRac'])
    dl1, dl2, dl3, dltot = rt.cumul_plante_Lrac(nbplantes,
                                                invar_sc['ax']['dlRac'])  # calcul des delta de longueur par plante
    invar['dRLen2'].append(dl2)  # stocke les dl du jour pour cacalcul senescence de plus tard
    invar['dRLen3'].append(dl3)
    # invar['SRL'] = invar['RLentot']/(invar['MS_rac_fine'][0]+10e-15)
    # print invar_sc['ax']['QDCRac']

    # print 'graine', graineC, dltot, invar['Surfcoty'], invar['Mcoty']#

    dur2 = (array(riri.get_lsparami(ParamP, 'GDs2')) + array(
        riri.get_lsparami(ParamP, 'LDs2'))) / 20.  # en jours a 20 degres!
    dur3 = (array(riri.get_lsparami(ParamP, 'GDs3')) + array(
        riri.get_lsparami(ParamP, 'LDs3'))) / 20.  # en jours a 20 degres!
    invar['dRLenSentot'], invar['dMSenRoot'] = rt.calc_root_senescence(invar['dRLen2'], invar['dRLen3'], dur2, dur3,
                                                                       array(invar['SRL']))
    invar['RLTotNet'] = array(invar['RLTotNet']) + dltot - invar['dRLenSentot']
    invar['MS_rac_fineNet'] = array(invar['MS_rac_fineNet']) + rac_fine - invar['dMSenRoot']
    invar['SRL'] = invar['RLTotNet'] / (invar['MS_rac_fineNet'][0] + 10e-15)

    invar['perteN_rac_fine'] = invar['dMSenRoot'] * invar['Npc_rac_fine'] / 100.
    # sortir une variable cumule d'N des rac mortes? -> compement a invar['Nrac_fine'] qui comprend les deux


    # calcul senesc a faire a l'echelle des axes plutot? -> a priori pas necessaire

    invar['R_DemandC_Root'] = rt.calc_QDplante(nbplantes, invar_sc['ax']['QDCRac'], invar_sc['ax']['cumlRac'],
                                               invar['RLentot'])
    invar['R_DemandC_Shoot'] = aer / (array(IOxls.dic2vec(nbplantes, invar['DemCp'])) + 10e-15)

    # if '0_0_0' in invar_sc['ax']['NRac'].keys():
    #    print invar_sc['ax']['NRac']['0_0_0']
    #    print invar_sc['ax']['QDCRac']['0_0_0']
    #    print invar_sc['ax']['dlRac']['0_0_0']
    # print invar['RLentot'], invar['MS_rac_fine'], invar['RLentot'][0]/(invar['MS_rac_fine'][0]+0.00000001)

    # calcul demandN -> a depalcer dans le starteach comme pour C?? -> pas utilise actuellement
    if lsApex != []:
        I_I0profilInPlant = sh.cumul_lenIN(lsApex, tab, I_I0profilInPlant, deltaI_I0, nbI_I0)

    # pas utilise
    for nump in range(nbplantes):
        invar['DemandN_Feuil'][nump] = sum(I_I0profilLfPlant[nump] * NaClasses)
        invar['DemandN_Pet'][nump] = sum(I_I0profilPetPlant[nump] * NlClasses)
        invar['DemandN_Stem'][nump] = sum(I_I0profilInPlant[nump] * NlinClasses)
        # invar['DemandN_Tot'][nump] = invar['DemandN_Feuil'][nump] + invar['DemandN_Pet'][nump] + invar['DemandN_Stem'][nump]

    invar['DemandN_Tot'] = ls_demandeN_bis * 1000.
    # print invar['DemandN_Tot'][0], sum(ls_Act_Nuptake_plt[0]), sum(ls_Act_Nuptake_plt[0])/(invar['DemandN_Tot'][0]+10e-12), sum(S.m_NO3)

    Npc = (array(invar['DemandN_Feuil']) + array(invar['DemandN_Pet']) + array(invar['DemandN_Stem'])) * 100. / array(
        invar['MS_aerien'])

    # temps de calcul
    past_time = time.time() - start_time






    # sorties
    outvar['TT'].append(['TT', DOY] + invar['TT'])
    outvar['time'].append(['time', DOY] + [past_time] * nbplantes)
    outvar['cutNB'].append(['cutNB', DOY] + [cutNB] * nbplantes)
    outvar['SurfPlante'].append(['SurfPlante', DOY] + list(map(sum, invar['SurfPlante'])))
    outvar['PARaPlante'].append(
        ['PARaPlante', DOY] + invar['PARaPlanteU'].tolist())  # append(['PARaPlante',DOY]+invar['parap'].tolist())
    outvar['PARiPlante'].append(['PARiPlante', DOY] + invar['parip'].tolist())
    outvar['epsi'].append(['epsi', DOY] + ls_epsi.tolist())
    outvar['dMSaer'].append(['dMSaer', DOY] + aer.tolist())
    outvar['Hplante'].append(['Hplante', DOY] + invar['Hplante'])
    outvar['Dplante'].append(['Dplante', DOY] + invar['Dplante'])
    outvar['RLTot'].append(['RLTot', DOY] + invar['RLentot'])
    outvar['RDepth'].append(['RDepth', DOY] + invar['RDepth'])
    outvar['MS_aerien'].append(['MSaerien', DOY] + invar['MS_aerien'])
    outvar['MS_feuil'].append(['MSfeuil', DOY] + invar['MS_feuil'])
    outvar['MS_tot'].append(['MStot', DOY] + invar['MS_tot'])
    outvar['countSh'].append(['countSh', DOY] + invar['countSh'])
    outvar['countShExp'].append(['countShExp', DOY] + invar['countShExp'])
    outvar['demandC'].append(['demandC', DOY] + IOxls.dic2vec(nbplantes, invar['DemCp']))
    outvar['Leaf_Stem'].append(['Leaf_Stem', DOY] + invar['L_Sp'].tolist())
    outvar['NBsh'].append(['NBsh', DOY] + invar['NBsh'])
    outvar['NBI'].append(['NBI', DOY] + invar['NBI'])
    outvar['FTSW'].append(['FTSW', DOY] + ls_ftsw)
    outvar['Etransp'].append(['Etransp', DOY] + ls_transp)
    outvar['DemandN_Feuil'].append(['DemandN_Feuil', DOY] + invar['DemandN_Feuil'])
    outvar['DemandN_Pet'].append(['DemandN_Pet', DOY] + invar['DemandN_Pet'])
    outvar['DemandN_Stem'].append(['DemandN_Stem', DOY] + invar['DemandN_Stem'])
    outvar['DemandN_Tot'].append(['DemandN_Tot', DOY] + invar['DemandN_Tot'].tolist())
    outvar['Npc'].append(['Npc', DOY] + Npc.tolist())
    outvar['NBD1'].append(['NBD1', DOY] + invar['NBD1'])
    outvar['NBB'].append(['NBB', DOY] + invar['NBB'])
    outvar['NBBexp'].append([['NBBexp', DOY] + invar['NBBexp']])
    outvar['R_DemandC_Root'].append(['R_DemandC_Root', DOY] + invar['R_DemandC_Root'])
    outvar['SRL'].append(['SRL', DOY] + invar['SRL'].tolist())
    outvar['DemandN_Tot_Aer'].append(['DemandN_Tot_Aer', DOY] + invar['DemandN_TotAer'].tolist())
    outvar['Naerien'].append(['Naerien', DOY] + invar['Naerien'].tolist())
    outvar['Npc_aer'].append(['Npc_aer', DOY] + invar['Npc_aer'].tolist())  # -> ancien Npc_bis
    outvar['Npc_piv'].append(['Npc_piv', DOY] + invar['Npc_piv'].tolist())
    outvar['Npc_rac_fine'].append(['Npc_rac_fine', DOY] + invar['Npc_rac_fine'].tolist())
    outvar['Nuptake_sol'].append(['Nuptake_sol', DOY] + invar['Nuptake_sol'].tolist())
    outvar['NNI'].append(['NNI', DOY] + invar['NNI'].tolist())
    outvar['Ndfa'].append(['Ndfa', DOY] + invar['Ndfa'].tolist())
    outvar['Qfix'].append(['Qfix', DOY] + invar['Qfix'].tolist())
    outvar['dMSenFeuil'].append(['dMSenFeuil', DOY] + invar['dMSenFeuil'])
    outvar['dMSenTige'].append(['dMSenTige', DOY] + invar['dMSenTige'])
    outvar['MS_pivot'].append(['MS_pivot', DOY] + invar['MS_pivot'])
    outvar['MS_rac_fine'].append(['MS_rac_fine', DOY] + invar['MS_rac_fine'])
    outvar['R_DemandC_Shoot'].append(['R_DemandC_Shoot', DOY] + invar['R_DemandC_Shoot'].tolist())
    outvar['RUE'].append(['RUE', DOY] + invar['RUEactu'].tolist())
    outvar['DemCp'].append(['DemCp', DOY] + IOxls.dic2vec(nbplantes, invar['DemCp']))
    outvar['remob'].append(['remob', DOY] + invar['remob'].tolist())
    outvar['dRLenSentot'].append(['dRLenSentot', DOY] + invar['dRLenSentot'].tolist())
    outvar['dMSenRoot'].append(['dMSenRoot', DOY] + invar['dMSenRoot'].tolist())
    outvar['RLTotNet'].append(['RLTotNet', DOY] + array(invar['RLTotNet']).tolist())
    outvar['MS_rac_fineNet'].append(['MS_rac_fineNet', DOY] + invar['MS_rac_fineNet'].tolist())
    outvar['perteN_rac_fine'].append(['perteN_rac_fine', DOY] + invar['perteN_rac_fine'].tolist())
    outvar['NBphyto'].append(['NBphyto', DOY] + invar['NBphyto'])
    outvar['NBapexAct'].append(
        ['NBapexAct', DOY] + invar['NBapexAct'])  # pour correction du nb phyto par rapport au comptage observe

    # !! ces 4 sorties lucas ne sont pas au format attentdu!
    outvar['phmgPet'].append(['phmgPet', DOY] + list(map(max, invar['phmgPet'])))
    outvar['phmgEntr'].append(['phmgEntr', DOY] + list(map(max, invar['phmgEntr'])))
    outvar['phmgPet_m'].append(['phmgPet_m', DOY] + list(map(min, invar['phmgPet_m'])))
    outvar['phmgEntr_m'].append(['phmgEntr_m', DOY] + list(map(min, invar['phmgEntr_m'])))

    # res_root.append(rtd.convd(RLProfil[0])) #pour exporter profil de racine (le faire pour tous les systemes?



    # ajout dans la matrice des residus (en dernier)
    for nump in range(len(invar['dMSenRoot'])):
        voxsol = riri.WhichVoxel(array(carto[nump]), [0., 0., 0.],
                                 [len(lims_sol[0]) - 1, len(lims_sol[1]) - 1, len(lims_sol[2]) - 1],
                                 [S.dxyz[0][0] * 100., S.dxyz[1][0] * 100., S.dxyz[2][0] * 100.])
        groupe_resid = int(ParamP[nump]['groupe_resid'])
        ls_mat_res[groupe_resid * 4 + 2][voxsol[2]][voxsol[1]][voxsol[0]] += invar['dMSenRoot'][nump]
        # a revoir: tenir compte du groupe_resid
        # tout mis en surface: faire une distrib dans le sol en profondeur!

    # ajout des pivots a faire avant mse a jour des cres
    if opt_residu == 1:  # option residu activee: mise a jour des cres
        if sum(map(sum, ls_mat_res)) > 0.:  # si de nouveaux residus (ou supeieur a un seuil
            for i in range(len(ls_mat_res)):
                mat_res = ls_mat_res[i]
                if sum(mat_res) > 0.:
                    S.mixResMat(mat_res, i, vCC[i])




    # HR sol
    # out_HR.append([DOY]+mean(S.HRp(), axis=1)[id_out,0].tolist())

    #return invar, invar_sc, outvar, S
    #return ParamP, par_SN, invar, invar_sc, outvar, res_trans, S, Uval, stateEV, DOY, meteo_j, mng_j, PP, res_root, nbplantes, surfsolref, ls_ftswStress, past_time, lsOrgans, ls_NNIStress, ls_mat_res, lsApex, lsApexAll, ls_systrac, lims_sol, b_, opt_residu, vCC, carto, start_time, cutNB, deltaI_I0, nbI_I0, I_I0profilLfPlant, I_I0profilPetPlant, I_I0profilInPlant, NlClasses, NaClasses, NlinClasses
    return invar, invar_sc, outvar, S, stateEV, I_I0profilInPlant, ls_ftswStress, ls_NNIStress, ls_mat_res

