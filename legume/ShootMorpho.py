from scipy import *
import IOtable
import IOxls
import string
from copy import deepcopy
try:
    from riri5 import RIRI5 as riri #import de la version develop si module soil3ds est installe
except:
    import RIRI5 as riri



#Temperature response funtions
def betaT(Tmin, Tmax, q, T):
    """ beta de Graux (2011)"""
    Tref = 20
    if T < 0.:  # zero sous zero degres
        fT = 0.
    else:
        fT = ((Tmax - T) / (Tmax - Tref)) * ((T - Tmin) / (Tref - Tmin)) ** q

    return max(fT, 0.)

def dTT(T, p):
    """ fonction de cumul du temp thermique; integre reponse non lineaire"""
    return max((T - p[0]) * betaT(p[1], p[2], p[3], T), 0.)



#Light response functions
def DecliSun(DOY):
    """ Declinaison (rad) du soleil en fonction du jour de l'annee """
    alpha = 2. * 3.14 * (DOY - 1) / 365.
    return (0.006918 - 0.399912 * cos(alpha) + 0.070257 * sin(alpha))

def DayLength(latitude, decli):
    """ photoperiode en fonction de latitude (degre) et declinaison du soleil (rad) """
    lat = radians(latitude)
    d = arccos(-tan(decli) * tan(lat))
    if d < 0:
        d = d + 3.14

    # d en 'hour angle'
    return 24. * d / 3.14  # conversion en heures

def trilineaire(x, ratio0, ratiomax, parmaxeff, parnoeff):
    # photomorphogenese
    pentor = (ratiomax - ratio0) / parmaxeff
    pentfin = (1 - ratiomax) / (parnoeff - parmaxeff)
    orlindesc = -(parnoeff * pentfin) + 1
    return min(pentor * x + ratio0, max(1, pentfin * x + orlindesc))


#general growth functions
def expansion(t, a, delai):
    "croissance sigmoidale"
    return 1/(1+exp(-a*(t-delai)))

def sigmo_stress(v,delai,x):
    "reponse sigmo a stress - FTSW ou INN"
    return 1-1/(1+exp(v*(x-delai)))


# N response functions
def Na_N0(I_I0):
    """ teneur en azote relative en fonction de fraction d'eclairement - Louarn et al. 2014 """
    return I_I0**0.247

def N0(INN):
    """ teneur en azote des feuilles eclairees (g N.m-2) en fonction de INN - Louarn et al. 2014 """
    return 2.08*INN+0.05

def Nl_Nl0(I_I0):
    """ teneur en N lineique relative des tiges """
    Nresidu = 0.17
    return Nresidu + (1-Nresidu)*I_I0**0.51

def NNI_resp(NNI, par):
    # """Belanger, Gastal and lemaire 1992 - RUE/RUEmax = f(Nitrogen Nutrition Index)"""
    # RUE_Eff= max(0,1.05*(1-2.18*exp(-3.13*NNI)))

    res = 1.
    if NNI < 0.95:
        res = sigmo_stress(par[0], par[1], NNI)

    return res  # RUE_Eff

def Ndfa_max(ageTT, DurDevFix, Delfix=100.):
    """ Ndfa (prop d'N issu de fixation) max depend de stade - demare a 100 degree.days (Delfix -> a remonter en parametere)"""
    Delfix = 0.
    slope = 1. / (array(DurDevFix) - Delfix)
    ordoOr = -Delfix * slope
    val = slope * array(ageTT) + ordoOr
    val[val > 1.] = 1.
    val[val < 0.] = 0.
    return val
    # ages = [100., 200.]
    # DurDevFix = [600., 100.]
    # Ndfa_max(ages, DurDevFix)

def ActualFix(ls_demand, Nuptakes, MaxFix):
    """ calcul fixation a partir de demande, prelev mineral (prioritaire) et MaxFix """
    demande_residuelle = ls_demand - Nuptakes
    fix = []
    for i in range(len(demande_residuelle)):
        fix.append(min(MaxFix[i], demande_residuelle[i]))

    fix = array(fix)
    fix[fix < 0] = 0.
    return fix
    # ls_demand = array([1.,2.,3.])
    # Nuptakes = array([1.,1.,1.])
    # MaxFix = array([3.,3.,3.])
    # ActualFix(ls_demand, Nuptakes, MaxFix)


# water stress functions
def FTSW_resp(FTSW, par):  # =[0.4, 0.]):
    # """ facteur de reduction en reponse a FTSW - lineaire entre 0 et 0.4"""
    """ reponse sigmo """
    res = 1.
    # if FTSW <= par[1]:
    #    res=0.
    # elif FTSW > par[1] and FTSW < par[0]:
    #    res=FTSW/(par[0]-par[1])
    if FTSW <= 0.95:
        res = sigmo_stress(par[0], par[1], FTSW)

    return res


#calcul des longueurs et surfaces d'organes
def calc_surF(ParamP, rank, rankp, ordre, l, type=1):
    """ calcul de surface d'une feuille (m2) """
    cor_ordre = ParamP['ratioII'] if ordre == 2 else 1.
    if int(type)==1 or int(type)==2: #legume leaves
        rk = rank + rankp if ordre == 2 else rank
    elif int(type)==3: #graminee
        rk = rank + rankp #rankp utilise pour calcule un rgeq qui tient compte de tallage et coupe

    rk = min(rk, len(ParamP['profilLeafI_l']) - 1)  # au cas ou rank depasse le profil
    nf = ParamP['profilLeafI_nfol'][rk]
    Long = ParamP['profilLeafI_l'][rk] * l * cor_ordre
    larg = ParamP['profilLeafI_larg'][rk] * l * cor_ordre
    if int(type)==1 or int(type)==2: #feuille legumineuse -> losange
        surF = nf * 0.5 * Long * larg / 10000.  # nf*0.5*Long*larg/10000.  #m2
    elif int(type)==3: #graminee -> rectangle
        surF =  Long * larg / 10000.  # nf*0.5*Long*larg/10000.  #m2
    return surF
    # ParamP en parametre

def calc_surS(ParamP, rank, rankp, ordre, l):
    """ calcul de surface d'une stipule (m2) """
    cor_ordre = ParamP['ratioII'] if ordre == 2 else 1.
    rk = rank + rankp if ordre == 2 else rank
    rk = min(rk, len(ParamP['profilStipI_l']) - 1)  # au cas ou rank depasse le profil
    Long = ParamP['profilStipI_l'][rk] * l * cor_ordre
    larg = ParamP['profilStipI_larg'][rk] * l * cor_ordre
    surF = 2 * Long * larg * 0.5 / 10000.  # m2
    return surF
    # ParamP en parametre

def calc_surfcoty(Mcoty, age, DurGraine, carto, ParamP, n_gamagroup, origin_grid, na, dxyz, SLAcoty=600.):
    """ distribution de surface coty dans grille 3D - depend de masse de coty et SLAcoty et graine; et zero apres DurGraine"""
    # valeur de 600 tiree essai RGR2015
    # peut passer SLAcoty en parametre et variable par plante
    mcot = zeros([n_gamagroup, na[2], na[1], na[0]])

    for nump in range(len(carto)):
        vox = riri.WhichVoxel(array(carto[nump]), origin_grid, na, dxyz)
        if age[nump] <= DurGraine[nump]:  # cotyledons actifs pendant DurGraine
            surfcot = Mcoty[nump] * SLAcoty / 10000.  # m2
        else:
            surfcot = 0.

        mcot[ParamP[nump]['id_grid']][vox[2]][vox[1]][vox[0]] += surfcot

    return mcot

def calc_parapcoty(invar, m_lais, res_abs_i, Mcoty, age, DurGraine, carto, ParamP, n_gamagroup, origin_grid, na, dxyz, SLAcoty=100.):
    """ ajout des PARa des cotyledon a invar['PARiPlante']"""
    for nump in range(len(carto)):
        vox = riri.WhichVoxel(array(carto[nump]), origin_grid, na, dxyz)
        sVOX = m_lais[ParamP[nump]['id_grid']][vox[2]][vox[1]][vox[0]]
        if age[nump] <= DurGraine[nump]:  # cotyledons actifs pendant DurGraine
            surfcot = Mcoty[nump] * SLAcoty / 10000.  # m2
        else:
            surfcot = 0.

        if sVOX > 0.:
            PARaF = res_abs_i[ParamP[nump]['id_grid']][vox[2]][vox[1]][vox[0]] * surfcot / sVOX * 3600. * 24 / 1000000.
        else:
            PARaF = 0.

        invar['PARiPlante'][nump].append(PARaF)

def calc_Lpet(ParamP, rank, rankp, ordre, l, type=1):
    """ calcule de longueur potentielle d'un petiole (m)"""
    cor_ordre = ParamP['ratioII'] if ordre==2 else 1.
    if int(type)==1 or int(type)==2: #legume leaves
        rk = rank + rankp if ordre == 2 else rank
    elif int(type)==3: #graminee
        rk = rank + rankp #rankp utilise pour calcule un rgeq qui tient compte de tallage et coupe

    rk = min(rk, len(ParamP['profilPetI_l'])-1) #au cas ou rank depasse le profil
    lpet = l*ParamP['profilPetI_l'][rk]*cor_ordre/100. #m
    return lpet

def calc_Lent(ParamP, rank, nsh, ordre, l):
    """ calcule de longueur poteielle d'un entre noeud (m)"""
    cor_M = ParamP['ratioM'] if nsh==0 and ordre==1 else 1. #correction tige seminale
    cor_ordre = ParamP['ratioII'] if ordre==2 else 1.
    rank = min(rank, len(ParamP['profilNodeI_l'])-1) #au cas ou rank depasse le profil
    lent = l * ParamP['profilNodeI_l'][rank] * cor_ordre * cor_M/100. #m
    return lent

def calcSurfScale(ParamP, tab, scale):
    """ calcul le cumul de surface foliaire a l'echelle indiquee """
    dp = {}  # dictionnaire a l'echelle choisie: plante/shoot/axe
    for i in range(len(tab['nump'])):
        if scale == 'plt':
            idp = str(tab['nump'][i])
        elif scale == 'sh':
            idp = str(tab['nump'][i]) + '_' + str(tab['nsh'][i])
        elif scale == 'ax':
            idp = str(tab['nump'][i]) + '_' + str(tab['nsh'][i]) + '_' + str(tab['rank'][i])

        age = float(tab['age'][i])
        nump = int(tab['nump'][i])
        ordre = int(tab['ordre'][i])
        rank = int(tab['rank'][i])
        rankp = int(tab['rankp'][i])
        nsh = int(tab['nsh'][i])
        l = float(tab['l'][i])

        surf = 0.
        if tab['organ'][i] == 'Lf':
            surf = calc_surF(ParamP[nump], rank, rankp, ordre, l)  # m2

        if tab['organ'][i] == 'Stp':
            surf = calc_surS(ParamP[nump], rank, rankp, ordre, l)  # m2

        # ajoute une cle pour chaque organe (meme si pas feuille)
        try:
            dp[idp].append(surf)
        except:
            dp[idp] = [surf]

    for k in list(dp.keys()):
        dp[k] = sum(dp[k])

    return dp
    # lsSurfSh = calcSurfScale(IOtable.conv_dataframe(IOtable.t_list(lsOrgans)), 'sh')
    # plus utile car fait dans calcSurfLightScales

def calcSurfLightScales(ParamP, tab):
    """ calcul le cumul de surface foliaire, surface foliaire verte et PARa au echelles plante/shoot_axe - passe la table organe une seulle fois en revue """

    daxAgePiv = {}  # dico des axes qui portent des pivots et de leur age
    dpS, dpSV, dpPARaF, dshS, dshSV, dshPARaF, daxS, daxSV, daxPARaF, daxPARaFsurf = {}, {}, {}, {}, {}, {}, {}, {}, {}, {}
    for i in range(len(tab['nump'])):

        idp = str(tab['nump'][i])
        idsh = str(tab['nump'][i]) + '_' + str(tab['nsh'][i])
        idax = str(tab['nump'][i]) + '_' + str(tab['nsh'][i]) + '_' + str(tab['rank'][i])

        age = float(tab['age'][i])
        nump = int(tab['nump'][i])
        ordre = int(tab['ordre'][i])
        rank = int(tab['rank'][i])
        rankp = int(tab['rankp'][i])
        nsh = int(tab['nsh'][i])
        l = float(tab['l'][i])

        surf, surfV, PARaF, PARaFsurf = 0., 0., 0., 0.
        if tab['organ'][i] == 'Lf':
            PARaF = float(tab['PARaF'][i])
            surf = max(calc_surF(ParamP[nump], rank, rankp, ordre, l), 10e-15)  # m2
            PARaFsurf = PARaF / (surf * 3600. * 24 / 1000000.)  #
            if tab['statut'][i] != 'sen':
                surfV = surf

        if tab['organ'][i] == 'Stp':
            PARaF = float(tab['PARaF'][i])
            surf = calc_surS(ParamP[nump], rank, rankp, ordre, l)  # m2
            if tab['statut'][i] != 'sen':
                surfV = surf

        if tab['organ'][i] == 'Piv':
            daxAgePiv[idax] = age

        # ajoute une cle pour chaque organe (meme si pas feuille)
        IOxls.append_dic(dpS, idp, surf)
        IOxls.append_dic(dshS, idsh, surf)
        IOxls.append_dic(daxS, idax, surf)
        IOxls.append_dic(dpSV, idp, surfV)
        IOxls.append_dic(dshSV, idsh, surfV)
        IOxls.append_dic(daxSV, idax, surfV)
        IOxls.append_dic(dpPARaF, idp, PARaF)
        IOxls.append_dic(dshPARaF, idsh, PARaF)
        IOxls.append_dic(daxPARaF, idax, PARaF)
        IOxls.append_dic(daxPARaFsurf, idax, PARaFsurf)

    IOxls.sum_ls_dic(dpS)  # surface par plante
    IOxls.sum_ls_dic(dpSV)  # surface par shoot
    IOxls.sum_ls_dic(dshS)  # surface par axe
    IOxls.sum_ls_dic(dshSV)  # surface verte par plante
    IOxls.sum_ls_dic(daxS)  # surface verte par shoot
    IOxls.sum_ls_dic(daxSV)  # surface verte par axe
    IOxls.sum_ls_dic(dpPARaF)  # PARaF par plante
    IOxls.sum_ls_dic(dshPARaF)  # PARaF par shoot
    IOxls.sum_ls_dic(daxPARaF)  # PARaF par axe
    for k in list(daxPARaFsurf.keys()):
        daxPARaFsurf[k] = max(daxPARaFsurf[k])

    return dpS, dpSV, dshS, dshSV, daxS, daxSV, dpPARaF, dshPARaF, daxPARaF, daxAgePiv, daxPARaFsurf
    # ajouter calcul du max de rayonnement par axes...?-> daxPARaFsurf


#germination / iitialisation funcions
def germinate(invar, ParamP, nump):
    # mis a jour pour chaque graine a germination
    # creation des cotyledons
    frac_coty_ini = ParamP['frac_coty_ini']
    invar['Mcoty'][nump] = invar['MSgraine'][nump] * frac_coty_ini
    # invar['Mfeuil'][nump] = invar['MSgraine'][nump] * frac_coty_ini
    # invar['Naerien'][nump] = invar['Mfeuil'][nump] * ParamP['Npc_ini']/100.
    # met a jour graine qui a germe et defini pools de reserve (ce qui reste dans MSgraine et N graine = reserve pour soutenir croissance ini)
    invar['MSgraine'][nump] -= invar['Mcoty'][nump]
    invar['Ngraine'][nump] -= invar['Mcoty'][nump] * ParamP['Npc_ini'] / 100.
    invar['dMSgraine'][nump] = invar['MSgraine'][nump] / ParamP[
        'DurGraine']  # delta MS fourni par degrejour par graine pendant DurGraine
    invar['dNgraine'][nump] = invar['Ngraine'][nump] / ParamP[
        'DurGraine']  # delta QN fourni par degrejour par graine pendant DurGraine

    # cotyledons meurent quand DurGraine atteint -> cf calc_surfcoty
    # en toute logique pas besoin de mettre a jour Mfeuil?

def reserves_graine(invar, ParamP):
    """ calcul des reserves de graine """
    graineC, graineN = [], []
    for nump in range(len(ParamP)):
        if invar['TT'][nump] < ParamP[nump]['DurGraine'] and invar['TT'][nump] > 0.:
            # suppose consommation reguliere pendant DurGraine
            dMSgraine = invar['dMSgraine'][nump] * invar['dTT'][nump]
            dNgraine = invar['dNgraine'][nump] * invar['dTT'][nump]
        else:
            dMSgraine = 0.
            dNgraine = 0.

        graineC.append(dMSgraine)
        graineN.append(dMSgraine)

    return array(graineC), array(graineN)



# Carbon allocation
def rootalloc(params, SB):
    """ calcule fraction d'alloc racine/shoots en fonction du cumule shoots - Eq. 8 draft article V Migault"""
    """ puis concerti en fraction d'allocation de biomasse totale produite au racine dRB/dMStot a partir du ratio SRB/dSB"""
    nbplantes = len(SB)
    res = [0] * nbplantes
    for nump in range(nbplantes):
        bet = params[nump][0]
        alph = params[nump][1]
        res[nump] = min(bet, bet * alph * max(SB[nump], 0.00000000001) ** (
                    alph - 1))  # epsilon evitant de calculer un 0 avec puissance negative (cause erreur). Le maximum possible est pour alpha=1, donc beta*1*SB**(1-1) = beta * 1 * 1 = beta.

    dRB_dSB = array(res)
    return dRB_dSB / (1 + dRB_dSB)

def calcOffreC(ParamP, tab, scale):
    """ calcul de cumul de para par plante ('plt')/tige('sh')/axe('ax') * RUE-> offreC """
    """ tab = attend dico avec cle ('nump', 'nsh', 'rank', 'PARaF','statut','age','ordre') """
    dp = {}  # dictionnaire a l'echelle choisie: plnate/shoot/axe
    for i in range(len(tab['nump'])):
        if scale == 'plt':
            idp = str(tab['nump'][i])
        elif scale == 'sh':
            idp = str(tab['nump'][i]) + '_' + str(tab['nsh'][i])
        elif scale == 'ax':
            idp = str(tab['nump'][i]) + '_' + str(tab['nsh'][i]) + '_' + str(tab['rank'][i])

        if tab['organ'][i] == 'Lf' and tab['statut'][i] != 'sen':
            nump = int(tab['nump'][i])
            try:
                dp[idp].append(float(tab['PARaF'][i]) * ParamP[nump]['RUE'])
            except:
                dp[idp] = [float(tab['PARaF'][i]) * ParamP[nump]['RUE']]

    for k in list(dp.keys()):
        dp[k] = sum(dp[k])

    return dp
    # pas utilise dans version actuelle
    # approche RUE limite a echelle feuille! ; garder aussi 'sen'?

def calcDemandeC(ParamP, tab, scale, dTT, ls_ftswStress, ls_NNIStress):
    """ calcul de demande pour assurer croissance potentielle minimale des Lf(), In() et Pet()en phase d'expansion """
    # distingue les Lf et Stp! car pas meme calcul de surface!
    dp = {}  # dictionnaire a l'echelle choisie: plante/shoot/axe #-> demande tot
    dplf = {}  # demande des feuilles
    for i in range(len(tab['nump'])):
        if scale == 'plt':
            idp = str(tab['nump'][i])
        elif scale == 'sh':
            idp = str(tab['nump'][i]) + '_' + str(tab['nsh'][i])
        elif scale == 'ax':
            idp = str(tab['nump'][i]) + '_' + str(tab['nsh'][i]) + '_' + str(tab['rank'][i])

        age = float(tab['age'][i])
        nump = int(tab['nump'][i])
        ordre = int(tab['ordre'][i])
        rank = int(tab['rank'][i])
        rankp = int(tab['rankp'][i])
        nsh = int(tab['nsh'][i])
        l = float(tab['l'][i])

        if tab['organ'][i] == 'Lf' and tab['statut'][i] == 'exp':
            pot = expansion(age + dTT[nump], ParamP[nump]['aF'], ParamP[nump]['delaiF']) - expansion(age,
                                                                                                     ParamP[nump]['aF'],
                                                                                                     ParamP[nump][
                                                                                                         'delaiF'])
            dl = pot * ls_ftswStress['WaterTreshExpSurf'][nump] * ls_NNIStress['NTreshExpSurf'][nump]
            dSpot = calc_surF(ParamP[nump], rank, rankp, ordre, l + dl) - calc_surF(ParamP[nump], rank, rankp, ordre,
                                                                                    l)  # m2, delta surf potentiel (sans limitation C mais avec stress hydrique)
            dMin = 10000. * dSpot / ParamP[nump]['SLAmin']  # delta masse min feuille
            IOxls.append_dic(dp, idp, dMin)
            IOxls.append_dic(dplf, idp, dMin)

        if tab['organ'][i] == 'Stp' and tab['statut'][i] == 'exp':
            pot = expansion(age + dTT[nump], ParamP[nump]['aS'], ParamP[nump]['delaiS']) - expansion(age,
                                                                                                     ParamP[nump]['aS'],
                                                                                                     ParamP[nump][
                                                                                                         'delaiS'])
            dl = pot * ls_ftswStress['WaterTreshExpSurf'][nump] * ls_NNIStress['NTreshExpSurf'][nump]
            dSpot = calc_surS(ParamP[nump], rank, rankp, ordre, l + dl) - calc_surS(ParamP[nump], rank, rankp, ordre,
                                                                                    l)  # m2, delta surf potentiel (sans limitation C mais avec stress hydrique)
            dMin = 10000. * dSpot / ParamP[nump]['SLAmin']  # delta masse min feuille
            IOxls.append_dic(dp, idp, dMin)
            IOxls.append_dic(dplf, idp, dMin)

        if tab['organ'][i] == 'In' and tab['statut'][i] == 'exp':
            pot = expansion(age + dTT[nump], ParamP[nump]['aE'], ParamP[nump]['delaiE']) - expansion(age,
                                                                                                     ParamP[nump]['aE'],
                                                                                                     ParamP[nump][
                                                                                                         'delaiE'])
            dl = pot * ls_ftswStress['WaterTreshExpSurf'][nump] * ls_NNIStress['NTreshExpSurf'][nump]
            dLpot = calc_Lent(ParamP[nump], rank, nsh, ordre,
                              dl)  # m, delta longueur potentiel (sans limitation C mais avec stress hydrique)
            dMin = dLpot / ParamP[nump]['SNLmin']  # delta masse min En
            IOxls.append_dic(dp, idp, dMin)

        if tab['organ'][i] == 'Pet' and tab['statut'][i] == 'exp':
            pot = expansion(age + dTT[nump], ParamP[nump]['aP'], ParamP[nump]['delaiP']) - expansion(age,
                                                                                                     ParamP[nump]['aP'],
                                                                                                     ParamP[nump][
                                                                                                         'delaiP'])
            dl = pot * ls_ftswStress['WaterTreshExpSurf'][nump] * ls_NNIStress['NTreshExpSurf'][nump]
            dLpot = calc_Lpet(ParamP[nump], rank, rankp, ordre, dl)  # m
            dMin = dLpot / ParamP[nump]['SPLmin']  # delta masse min En
            IOxls.append_dic(dp, idp, dMin)

    IOxls.sum_ls_dic(dp)
    IOxls.sum_ls_dic(dplf)

    return dp, dplf
    # pourrait decliner demande globale en demande par organe?

def Cremob(DemCp, R_DemandC_Shoot, MSPiv, frac_remob=0.1):
    """ remobilisation of C from the taproot to the shoot to ensure minimal growth """
    # frac_remob : fraction remobilisable du pivot par jour (a passer en parametre?)
    ratio_seuil = array(deepcopy(R_DemandC_Shoot))
    ratio_seuil[ratio_seuil > 1.] = 1.  # borne ratio demande a 1
    dem_non_couv = array(DemCp) * (1 - ratio_seuil)
    dem_non_couv_dispo = frac_remob * array(
        MSPiv) - dem_non_couv  # depend d'un fraction remobilisable du pivot par jour
    dem_non_couv_dispo[dem_non_couv_dispo < 0] = dem_non_couv[dem_non_couv_dispo < 0] + dem_non_couv_dispo[
        dem_non_couv_dispo < 0]  # borne remobilisation a poids du pivot
    remob = deepcopy(dem_non_couv_dispo)
    remob[dem_non_couv <= 0.] = 0.  # met a zero si couvert
    for i in range(len(remob)):
        remob[i] = min(remob[i], dem_non_couv[i])

    return remob
    # frac_remob dans ParamP?


#calcul variables internes / intermediaire
def calcNB_NI(tab, nbplantes, seuilcountTige=0.5, seuilNItige=0.75):
    """ tab = tableau des apex actifs I et II =lsApex ; seuilNItige: faut au moins cette fraction du max pour etre compter en NI; seuilcountTige: pareil pour etre compter dans le nb tige 'significatives' """
    resall, resI, resNI, resNB = [], [], [], []
    for i in range(nbplantes):
        resall.append([0]);
        resI.append([0]);
        resNI.append([]);
        resNB.append([])

    for i in range(len(tab)):
        idp = int(tab[i][0])
        resall[idp].append(tab[i][2])
        if tab[i][3] == 1:
            resI[idp].append(tab[i][2])

    for i in range(nbplantes):
        resall[i] = max(resall[i])
        resI[i] = max(resI[i])

    for i in range(len(tab)):
        idp = int(tab[i][0])
        if float(tab[i][2]) > seuilcountTige * float(resall[idp]):
            resNB[idp].append(tab[i][2])

        if tab[i][3] == 1 and float(tab[i][2]) > seuilNItige * float(resI[idp]):
            resNI[idp].append(float(tab[i][2]))

    for i in range(nbplantes):
        resNB[i] = len(resNB[i]);
        resNI[i] = mean(resNI[i])

    return resNB, resI

def cumul_lenIN(tab, tabL, I_I0profilInPlant_, deltaI_I0, nbI_I0):
    """ tab = tableau des apex actifs I et II =lsApex ;tabL = lsOrgans converti en dico"""
    # ajoute un id tige a tab lsApex en derniere colone
    for i in range(len(tab)): tab[i].append(str(tab[i][0]) + '_' + str(tab[i][1]))
    # liste d'id tiges unique
    tab = IOtable.t_list(tab)
    id_sh = list(set(tab[-1]))  # id tige dans derniere colone
    tab = IOtable.t_list(tab)

    # dico des I_I0 max par tige
    res = dict.fromkeys(id_sh, 0)
    for i in range(len(tab)):
        id = tab[i][-1]
        I_I0 = tab[i][4]
        if I_I0 > res[id]:
            res[id] = I_I0

    # dico des longueur cumul par tige
    resL = {}  # dict.fromkeys(id_sh, 0)
    for i in range(len(tabL['organ'])):
        if tabL['organ'][i] == 'In':
            id = str(tabL['nump'][i]) + '_' + str(tabL['nsh'][i])
            try:
                resL[id] += tabL['Long'][i] / 100.  # m
            except:  # si pas dans les cles, la cree
                resL[id] = tabL['Long'][i] / 100.  # pass

    # mise a jour des longueur de tige par classe d'eclairement
    for id in list(res.keys()):
        nump = list(map(int, id.split('_')))[0]#list(map(int, string.split(id, '_')))[0]
        I_I0 = res[id]
        classI_I0 = min(int(I_I0 / deltaI_I0), nbI_I0 - 1)  # pour gerer cas du I_I0=1.
        try:
            cumulL = resL[id]
        except:  # pas encore de In
            cumulL = 0.

        I_I0profilInPlant_[nump][classI_I0] += cumulL

    return I_I0profilInPlant_  # resL
    # bizarre -> donne meme longueur pour tous les axes??
    # faire dico tige pour toutes les tiges et croiser apres avec activeAxes?
    # a continuer avec un profil de longueur par I_I0


#initialiation plante/scene
def MaturBud(delaiMaturBud, NIparent, delta=4):
    """ genere ecart de stade des B() (en phyllocrones) selon stade de developpement tige parente et delaiMaturBud
    - delta= borne min/max d'ecart par defaut +-4phyllo"""
    ecart = NIparent - delaiMaturBud
    if ecart >= 0:
        ecart = min(delta, ecart)
    else:
        ecart = max(-delta, ecart)

    return ecart
    # MaturBud(delaiMaturBud=12, NIparent=15, delta=2)
    # delta : passer ds fichier d'initialisation?

def damier8(p, vois, opt=4):
    # cree un melange binaire homogene de 64 plantes avec differentes options de proportions
    if opt == 4:  # 50/50
        motif = [p, vois, p, vois, p, vois, p, vois]
    elif opt == 0:  # 0/100
        motif = [vois, vois, vois, vois, vois, vois, vois, vois]
    elif opt == 8:  # 100/0
        motif = [p, p, p, p, p, p, p, p]
    elif opt == 2:  # 25/75
        motif = [p, vois, vois, vois, p, vois, vois, vois]
    elif opt == 6:  # 75/25
        motif = [vois, p, p, p, vois, p, p, p]
    elif opt == 1:  # 1/8
        motif = [p, vois, vois, vois, vois, vois, vois, vois]
    elif opt == 7:  # 7/8
        motif = [vois, p, p, p, p, p, p, p]

    res = []
    for i in range(8):
        res = res + motif[i:8] + motif[0:i]

    return res
    #dans un fichier d'initialiation?

def row4(p, vois, Lrow=50., nbprow=125,  opt=0):
    """ cree un melange 50/50 alterne ou pur sur 4 rangs distance interow chanmp"""
    if opt == 2:  # 50/50
        motif = [p, vois, p, vois]
    elif opt == 0:  # 0/100
        motif = [vois, vois, vois, vois]
    elif opt == 4:  # 100/0
        motif = [p, p, p, p]

    res = []
    for i in range(nbprow):
        res = res + motif

    inter = Lrow / 4.
    onrow = Lrow / nbprow
    xxx = arange(0., Lrow, onrow)+onrow/2.
    yyy = [0. * inter + inter/2.] + [1. * inter + inter/2.] + [2. * inter + inter/2.] + [3. * inter + inter/2.]  # 4 rangs
    carto = []
    for i in range(len(xxx)):
        for j in range(len(yyy)):
            carto.append(array([xxx[i], yyy[j], 0.]))  # +origin

    return res ,carto
    #pourrait renvoyer carto aussi ds homogeneous et damier8....
    #res ,carto=row4(1, 2, Lrow=50., nbprow=125,  opt=0)
    # dans un fichier d'initialiation?
    #prevoir nbprow different par esp... et melange on row...


#old - non utilise
# a retirer
def calcLeafStemRatio(ParamP, tab, lsapexI):
    """ calcul de rapport feuille/tige base sur les tigeI actives"""
    # etablit une liste de tige avec A() actif (lsa)
    lsa = []
    for i in range(len(lsapexI)):
        newk = str(lsapexI[i][0]) + '_' + str(lsapexI[i][1])  # id = 'nump_nsh'
        lsa.append(newk)

    # recupere les masses mini des feuilles et tiges des lsa
    dp, dp2 = {}, {}
    for i in range(len(tab['nump'])):
        idp = str(tab['nump'][i])
        idt = str(tab['nump'][i]) + '_' + str(tab['nsh'][i])

        age = float(tab['age'][i])
        nump = int(tab['nump'][i])
        ordre = int(tab['ordre'][i])
        rank = int(tab['rank'][i])
        rankp = int(tab['rankp'][i])
        l = float(tab['l'][i])

        if tab['organ'][i] == 'Lf' and idt in lsa:
            surf = calc_surF(ParamP[nump], rank, rankp, ordre, l)  # m2
            MLf = 10000. * surf / ParamP[nump]['SLAmin']  # masse min feuille
            IOxls.append_dic(dp, idp, MLf)

        if tab['organ'][i] == 'In' and idt in lsa:
            cor_ordre = ParamP[nump]['ratioII'] if ordre == 2 else 1.
            rank = min(rank, len(ParamP[nump]['profilNodeI_l']) - 1)  # au cas ou profil trop long
            Long = l * ParamP[nump]['profilNodeI_l'][
                rank] * cor_ordre / 100.  # m #delta de longueur potentiel (sans limitation C)
            MIn = Long / ParamP[nump]['SNLmin']
            IOxls.append_dic(dp2, idp, MIn)

    # fait somme par plante de Lf et In, puis ratio
    for k in list(dp.keys()):
        leafM = sum(dp[k])
        try:
            inM = sum(dp2[k]) + 0.00000000001
        except:
            inM = 0.00000000001

        dp[k] = leafM / inM

    return dp

