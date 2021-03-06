#########
## fonctions de lecture et de mise en forme R pour analyse des sorties de simul l-egume
#########


read_ltoto <- function(ls_toto)
{
  #recuperer par paquet les fichiers toto du dossier de travail dans une liste ltoto
  ltoto <- vector('list', length(ls_toto))
  names(ltoto) <- ls_toto
  
  for (i in 1:length(ls_toto))
  {
    name <- ls_toto[i]
    ltoto[[name]] <- read.table(name, header=T, sep=';')
  }
  ltoto
}



## fonction de mise en formse des simule

moysimval <- function(ltoto, lsusm, var,esp=NA)
{
  # Fait moyenne de la somme pour toute les plantes d'une variable var pour une liste d'usm simulee
  #utilise pour construire le tableau simmoy
  #version GL adapt lucas (v4)
  #
  res <- vector("list",length(lsusm))
  names(res) <- lsusm
  for (usm in lsusm)
  {
    
    if (is.na(esp))
    {dat <- ltoto[[usm]]
    } else
    {
      #garde uniquement col esp
      nomcol <- names(ltoto[[usm]])
      idcols <- grepl(esp, nomcol)
      dat <- cbind(ltoto[[usm]][,c(1:2)], ltoto[[usm]][,idcols])
    }
    
    nbplt <- length(dat)-2
    xplt <- as.matrix(dat[dat$V1==var,3:(3+nbplt-1)], ncol=nbplt)
    xsum <- rowSums(xplt)
    res[[usm]] <- xsum
  }
  xav <- rowSums(as.data.frame(res))/length(lsusm)
  xav
}
#LAI <- moysimval(ltoto, lsusm, var='SurfPlante')/ surfsolref






build_simmoy <- function(ltoto, lsusm, esp=NA)
{
  #moy des simul des differentes graines d'un meme usm avec moysimval (pour variables dynamiques)
  
  #recup info generale sur la premier usm
  #dat <- ltoto[[lsusm[1]]]
  if (is.na(esp))
  {dat <- ltoto[[lsusm[1]]]
  } else
  {
    #garde uniquement col esp
    nomcol <- names(ltoto[[lsusm[1]]])
    idcols <- grepl(esp, nomcol)
    dat <- cbind(ltoto[[lsusm[1]]][,c(1:2)], ltoto[[lsusm[1]]][,idcols])
  }
  
  TT <- dat[dat$V1=='TT',3] #peut changer selon les plantes!
  STEPS <- dat[dat$V1=='TT',2]
  nbplt <- length(dat)-2
  surfsolref <- dat[dat$V1=='pattern',3] #m2
  
  LAI <- moysimval(ltoto, lsusm, var='SurfPlante', esp)/ surfsolref
  MSA <- moysimval(ltoto,lsusm, var='MSaerien', esp)/ surfsolref
  MSpiv <- moysimval(ltoto,lsusm, var='MS_pivot', esp)/ surfsolref
  MSracfine <- moysimval(ltoto,lsusm, var='MS_rac_fine', esp)/ surfsolref
  MSrac <- MSpiv + MSracfine
  NBI <- moysimval(ltoto,lsusm, var='NBI', esp)/ nbplt
  NBI <- pmax(0, NBI - 0.75) #correction des simuls pour les comptages decimaux
  #NBIquart <- quantsimval(ltoto,lsusm, var_='NBI',esp=esp)
  NBphyto <- moysimval(ltoto, lsusm, var='NBphyto', esp)/ surfsolref
  Nbapex <- moysimval(ltoto, lsusm, var='NBapexAct', esp)/ surfsolref
  NBphyto <- pmax(0,NBphyto - 0.5*Nbapex) #correction simuls pour les comptages decimaux
  
  RDepth <- moysimval(ltoto,lsusm, var='RDepth', esp)/ nbplt
  Hmax <- moysimval(ltoto,lsusm, var='Hplante', esp)/ nbplt
  FTSW <- moysimval(ltoto,lsusm, var='FTSW', esp)/ nbplt
  NNI <- moysimval(ltoto,lsusm, var='NNI', esp)/ nbplt
  R_DemandC_Root <- moysimval(ltoto,lsusm, var='R_DemandC_Root', esp)/ nbplt
  cutNB <- moysimval(ltoto,lsusm, var='cutNB', esp)/ nbplt
  
  simmoy <- data.frame(STEPS, TT, NBI, NBphyto, LAI, MSA, MSpiv, MSracfine, MSrac, RDepth, Hmax, FTSW, NNI, R_DemandC_Root, cutNB)
  simmoy
}#version revue par Lucas tient cmpte du nom de l'espece dans les assos

#simmoy <- build_simmoy(ltoto, lsusm=names(ltoto))
#simmoy <- build_simmoy(ltoto, lsusm=names(ltoto), esp="timbale")


dynamic_graphs <- function(simmoy, name, obs=NULL, surfsolref=NULL)
{
  #serie de figure pour rapport dynamique d'une simulation Avec ou sans ajouts de points observe
  #pour obs ajoute si dataframe fourni au format obs (teste morpholeg)
  
  op <- par(mfrow = c(3,1), #lignes, colonnes
            oma = c(5.,2.,3,0) + 0.1, #outer margins c(bottom, left, top, right)
            mar = c(0,4,0,2) + 0.1) #marges internes a chaque compartiment c(bottom, left, top, right)
  
  
  #1) Leaf area components
  plot(simmoy$STEPS, simmoy$NBI, type='l', xlab='Time',ylab='Nb phytomere I', labels=F, ylim=c(0,1.5*max(simmoy$NBI)))
  axis(2,labels=T) #remet tick labels y
  title(main=name, outer=T)
  if (!is.null(obs) & 'NBI' %in% names(obs)) 
  {  points(obs$DOY, obs$NBI, pch=16) }
  
  
  plot(simmoy$STEPS, simmoy$NBphyto, type='l', xlab='Time',ylab='Nb phytomere tot', labels=F, ylim=c(0,1.5*max(simmoy$NBphyto)))
  axis(2,labels=T) #remet tick labels y
  if (!is.null(obs) & 'nb_phyto_tot' %in% names(obs))
  { points(obs$DOY, obs$nb_phyto_tot/surfsolref, pch=16) }
  
  
  plot(simmoy$STEPS, simmoy$LAI, type='l', xlab='Time',ylab='LAI', labels=F, ylim=c(0,1.5*max(simmoy$LAI)))
  axis(2,labels=T) #remet tick labels y
  axis(1,labels=T) #remet tick labels x
  title(xlab='DOY', outer=T)
  if (!is.null(obs) & 'LAI' %in% names(obs))
  { points(obs$DOY, obs$LAI, pch=16) } 
  if (!is.null(obs) & 'surf_tot' %in% names(obs))
  { points(obs$DOY, obs$surf_tot/ (10000*surfsolref), pch=16) } #a reprendre fait 2 courbes actuellement pour eviter bug
  
  #2)MS et taille
  plot(simmoy$STEPS, -simmoy$RDepth, type='l', xlab='Time',ylab='RDepth', labels=F, ylim=c(-1.5*max(simmoy$RDepth),0))
  axis(2,labels=T) #remet tick labels y
  title(main=name, outer=T)
  if (!is.null(obs) & 'long_pivot' %in% names(obs))
  { points(obs$DOY, -obs$long_pivot, pch=16)}
  
  
  plot(simmoy$STEPS, simmoy$Hmax, type='l', xlab='Time',ylab='Hmax', labels=F, ylim=c(0,1.5*max(simmoy$Hmax)))
  axis(2,labels=T) #remet tick labels y
  if (!is.null(obs) & 'Hmax' %in% names(obs))
  { points(obs$DOY, obs$Hmax, pch=16) }
  
  plot(simmoy$STEPS, simmoy$MSA, type='l', xlab='Time',ylab='MS', labels=F, ylim=c(0,1.5*max(simmoy$MSA)))
  axis(2,labels=T) #remet tick labels y
  axis(1,labels=T) #remet tick labels x
  title(xlab='DOY', outer=T)
  points(simmoy$STEPS, simmoy$MSrac, type='l', lty=2)
  if (!is.null(obs) & 'MSaerien' %in% names(obs) & 'MSroot_tot' %in% names(obs))
  { 
    points(obs$DOY, obs$MSaerien/surfsolref, pch=16)
    points(obs$DOY, obs$MSroot_tot/surfsolref)
  }
  
  
  #3) fonctions de stress
  plot(simmoy$STEPS, simmoy$FTSW, type='l', xlab='Time',ylab='FTSW', labels=F, ylim=c(0,1.1))
  axis(2,labels=T) #remet tick labels y
  title(main=name, outer=T)
  
  plot(simmoy$STEPS, simmoy$NNI, type='l', xlab='Time',ylab='NNI', labels=F, ylim=c(0, 1.2*max(simmoy$NNI)))
  axis(2,labels=T) #remet tick labels y
  
  plot(simmoy$STEPS, simmoy$R_DemandC_Root, type='l', xlab='Time',ylab='R_DemandC_Root', labels=F, ylim=c(0,1.1))
  axis(2,labels=T) #remet tick labels y
  axis(1,labels=T) #remet tick labels x
  title(xlab='DOY', outer=T)
}
#dynamic_graphs(simmoy, onglet, obs, surfsolref)

#sans points d'obsevation
#dynamic_graphs(simmoy, name=names(ltoto)[1]) 

#avec points d'observation...
#namexl <- "morpholeg14_obs.xls"
#onglet <- "morpholeg14_ISO_timbale"
#obs <- read_excel(paste(pathobs,namexl,sep="\\"), sheet = onglet, col_names = TRUE, na = "")
#dynamic_graphs(simmoy, name=names(ltoto)[1], obs=obs, surfsolref=1) 




mef_dosbssim <- function(var, varsim, obs, simmoy, name='', corobs=1., cutNB=0.)
{
  #mise en forme d'un dictionnaire observe, simule a partir du tableau des obs et du simmoy et des noms de variables var/varsim
  #suppose pas que variable observe et simulee ont le meme nom!
  idvar <- which(names(obs)==var)
  
  obs[obs[,idvar] < 0. & !is.na(obs[,idvar]), idvar] <- NA #retire les -999
  DOYmes <- obs$DOY[!is.na(obs[,idvar])] #recupere les liste de DOY des points mesures sans les NA
  obsvar <- obs[!is.na(obs[,idvar]), idvar]
  
  #recupere les DOY de simulation correspondant
  idDOYsim <- simmoy$STEPS %in% DOYmes
  idvar_sim <- which(names(simmoy)==varsim)
  simvar <- simmoy[idDOYsim, idvar_sim]
  
  #gestion des cas ou pas de simul face aux obs
  if (length(simvar)<length(obsvar))
  {
    #DOYmes qui n'ont pas de sim
    DOYsimOK <-simmoy[idDOYsim, 1]
    DOYsimKO <- DOYmes[! DOYmes %in% DOYsimOK]
    idDOYsimOK <- DOYmes %in% DOYsimOK
    obsvar <- obsvar[idDOYsimOK]
    DOYmes <- DOYsimOK
    #afficher un warnings!
  }
  
  
  if (length(simvar)>0)
  {dobssim <- data.frame(usm= rep(name, length(obsvar)), var=rep(var, length(obsvar)) , DOY=DOYmes, obs=obsvar*corobs, sim=simvar,corobs=rep(corobs, length(obsvar))) 
  names(dobssim)[4] <- "obs" #car bug de changement de nom de colonne
  }
  else
  {dobssim <- NULL
  }
  
  dobssim
}


#var <-'NBI'#ls_var <- c('NBI','nb_phyto_tot','surf_tot','long_pivot','Hmax','MSaerien')
#varsim <- 'NBI'#ls_varsim <- c('NBI','NBphyto','LAI', 'RDepth', 'Hmax','MSA')
#dobssim <- mef_dosbssim(var, varsim, obs, simmoy, corobs=1.)



merge_dobssim <- function(ls_dobssim)
{
  #reuni dans un seul dataframe les differents dobssim d'une liste
  dobssim <- ls_dobssim[[1]]
  if (length(ls_dobssim)>1)
  {
    for (i in 2:length(ls_dobssim)) 
    {
      dobssim <- rbind(dobssim, ls_dobssim[[i]])
    }
  }
  dobssim
}



plot_obssim <- function(dobssim, name='', displayusm=F)
{
  #conversion
  #dobssim$obs <- dobssim$obs*convert #suppose conversion la meme pour tous les obs!!!
  #dobssim deja corrige maintenat!
  
  #plot d'un obs-sim avec les indicateurs de qualite
  #calcul des indicateurs
  res_rmse <- signif(rmse(dobssim$obs,dobssim$sim),3) #RMSE
  res_rrmse <- signif(rrmseCoucheney(dobssim$obs,dobssim$sim),3)#rRMSE
  res_rmses <- rmsesCoucheney(dobssim$obs,dobssim$sim)#RMSEs
  res_rmseu <- rmseuCoucheney(dobssim$obs,dobssim$sim)#RMSEu
  res_prmses <- signif(pRMSEs(rmse(dobssim$obs,dobssim$sim), res_rmses),3)#pRMSEs
  res_prmseu <- signif(pRMSEu(rmse(dobssim$obs,dobssim$sim), res_rmseu),3)#pRMSEu
  res_EF <- signif(efficiencyCoucheney(dobssim$obs,dobssim$sim),3)#Efficiency
  res_r2 <- signif(summary(lm(dobssim$sim~dobssim$obs))$r.squared,3)#r2
  
  
  plot(dobssim$obs, dobssim$sim, xlim=c(0, 1.5*max(dobssim$obs)), ylim=c(0, 1.5*max(dobssim$obs)), xlab='obs', ylab='sim', main=name)
  points(c(0, 1.5*max(dobssim$obs)), c(0, 1.5*max(dobssim$obs)), type='l')
  if (length(dobssim$obs)>2)
  { abline(lm(dobssim$sim~dobssim$obs), col=2)}
  text(0.2*max(dobssim$obs) , 1.4*max(dobssim$obs), cex=0.8, paste("rmse: ", res_rmse))
  text(0.2*max(dobssim$obs) , 1.3*max(dobssim$obs), cex=0.8, paste("rRMSE: ", res_rrmse))
  text(0.2*max(dobssim$obs) , 1.2*max(dobssim$obs), cex=0.8, paste("pRMSEs: ", res_prmses))
  text(0.2*max(dobssim$obs) , 1.1*max(dobssim$obs), cex=0.8, paste("pRMSEu: ", res_prmseu))
  text(0.2*max(dobssim$obs) , 1.*max(dobssim$obs), cex=0.8, paste("EF: ", res_EF))
  text(0.2*max(dobssim$obs) , 0.9*max(dobssim$obs), cex=0.8, paste("R2: ", res_r2))
  
  #ajout des points par usm si option activee (completer dico_col)
  if (displayusm==T)
  {
    splt <- split(dobssim, dobssim$usm)
    #ls_pch <- c(1,16,1,16,1,16)
    #ls_col <- c(1,1,2,2,3,3)
    dico_col <- data.frame(expe=c('morpholeg14', 'morpholeg15','combileg15','combileg16','morpholegRGR15'), col=c(1,1,2,2,3),pch=c(16,1,1,16,1))
    
    for (i in 1:length(splt))
    {
      expe <- strsplit(names(splt)[i], '_')[[1]][1]
      points(splt[[i]]$obs, splt[[i]]$sim, pch=dico_col$pch[dico_col$expe==expe], col=dico_col$col[dico_col$expe==expe])
    }
  }#rq: code couleur change selon les variables, selon nb ds split ; pour garder cst faudrait un dico
  
  
}

#plot_obssim(dobssim, name='test', displayusm=T)





build_ls_dobssim <-function(esp_, ls_expe, ls_var, ls_varsim)
{
  #construit un arbre (liste de liste) de tableau dobssim pour une espece et plusieurs variables / plusieurs usm-expe
  
  #construit un ls_dobssim vide pour une espece et plusieurs expe et variables
  ls_dobssim <- vector('list', length(ls_varsim))
  names(ls_dobssim) <- ls_varsim
  for (i in ls_varsim)
  {
    ls_dobssim[[i]] <- vector('list', length(ls_expe))
    names(ls_dobssim[[i]]) <- ls_expe
  }
  
  #boucle pour toutes les variables et les usm
  for (i in 1:length(ls_varsim))
    try({
      var <- ls_var[i]#'surf_tot'#'nb_phyto_tot'#'NBI'#
      varsim <- ls_varsim[i]#'LAI'#'NBphyto'#'NBI'#
      
      for (key in ls_expe)
        try({
          #calcul simul moy
          ls_toto_paquet <- sp_dtoto[[key]]$name
          
          #recuperation par paquet des fichiers de base (pas de stockage de l'ensemble des fichiers en memoire)
          ltoto <- read_ltoto(ls_toto_paquet)
          #version locale du paquet de doto
          dtoto <- sp_dtoto[[key]]
          
          mix <- strsplit(ls_toto_paquet[1], '_')[[1]][4] #suppose paquet fait par traitement
          esp <- strsplit(mix, '-')[[1]][1] #'Fix2'
          esp2 <- strsplit(mix, '-')[[1]][2] #'nonFixSimTest'
          meteo <- strsplit(ls_toto_paquet[1], '_')[[1]][9]
          damier <- strsplit(ls_toto_paquet[1], '_')[[1]][5]
          
          
          #constrcution du dobsim
          #calcul de la moyenne des simuls pour esp_
          simmoy <- build_simmoy(ltoto, lsusm=names(ltoto), esp_)  
          
          #recup des obs correspondant
          namexl <- paste0(meteo, "_obs.xls")#"morpholeg14_obs.xls"
          trait <- if (esp == esp2 & damier=="homogeneous0") "ISO" else "HD-M2"#sera a reprndre pour diffeents traitement
          #trait <- if (esp == esp2 & damier=="homogeneous0" & meteo=="morpholegRGR15") "LD"
          onglet <- paste0(meteo, "_",trait,"_",esp_)#"morpholeg14_ISO_timbale" #marche pour isole; a revoir pour autres
          obs <- read_excel(paste(pathobs,namexl,sep="\\"), sheet = onglet, col_names = TRUE, na = "")
          
          
          #calcul des facteurs de correction selon varsim
          if (varsim=='NBI') {corr=1.}
          if (varsim=='NBphyto') {corr=1./surfsolref}        
          if (varsim=='LAI') {corr=1/(10000*surfsolref)}
          if (varsim=='RDepth') {corr=1.}
          if (varsim=='Hmax') {corr=1.}
          if (varsim=='MSA') {corr=1./surfsolref}
          
          
          ls_dobssim[[varsim]][[key]] <- mef_dosbssim(var, varsim, obs, simmoy, name=onglet, corobs=corr)
        })
    })
  ls_dobssim
}

#esp_ <- 'timbale'#'giga'#'formica'#'sevanskij'#'leo'#'canto'#'kayanne'#
#ls_expe <- c('morpholeg14', 'morpholeg15')
#ls_expe <- names(sp_dtoto)[grepl(esp_, names(sp_dtoto))]#cle comportant le bon geno
#ls_var <- c('NBI','nb_phyto_tot','surf_tot','Hmax','MSaerien')#,'long_pivot')
#ls_varsim <- c('NBI','NBphyto','LAI', 'Hmax','MSA')#, 'RDepth')
#ls_dobssim <- build_ls_dobssim(esp, ls_expe, ls_var, ls_varsim)




























##old vesions (GL 2)
moysimval1 <- function(ltoto, lsusm, var)
{
  # Fait moyenne de la somme pour toute les plantes d'une variable var pour une liste d'usm simulee
  #utilise pour construire le tableau simmoy
  #version initiale GL (v2)
  
  res <- vector("list",length(lsusm))
  names(res) <- lsusm
  for (usm in lsusm)
  {
    dat <- ltoto[[usm]]
    nbplt <- length(dat)-2
    xplt <- as.matrix(dat[dat$V1==var,3:(3+nbplt-1)], ncol=nbplt)
    xsum <- rowSums(xplt)
    res[[usm]] <- xsum
  }
  xav <- rowSums(as.data.frame(res))/length(lsusm)
  xav
}
#LAI <- moysimval(ltoto, lsusm, var='SurfPlante')/ surfsolref



build_simmoy1 <- function(ltoto, lsusm)
{
  #moy des simul des differentes graines d'un meme usm avec moysimval (pour variables dynamiques)
  
  dat <- ltoto[[lsusm[1]]]
  TT <- dat[dat$V1=='TT',3] #peut changer selon les plantes!
  STEPS <- dat[dat$V1=='TT',2]
  nbplt <- length(dat)-2
  surfsolref <- dat[dat$V1=='pattern',3] #m2
  
  LAI <- moysimval(ltoto, lsusm, var='SurfPlante')/ surfsolref
  MSA <- moysimval(ltoto,lsusm, var='MSaerien')/ surfsolref
  MSpiv <- moysimval(ltoto,lsusm, var='MS_pivot')/ surfsolref
  MSracfine <- moysimval(ltoto,lsusm, var='MS_rac_fine')/ surfsolref
  MSrac <- MSpiv + MSracfine
  NBI <- moysimval(ltoto,lsusm, var='NBI')/ nbplt
  NBI <- pmax(0, NBI - 0.75) #correction des simuls pour les comptages decimaux
  #NBIquart <- quantsimval(ltoto,lsusm, var_='NBI',esp=esp)
  NBphyto <- moysimval(ltoto, lsusm, var='NBphyto')/ surfsolref
  Nbapex <- moysimval(ltoto, lsusm, var='NBapexAct')/ surfsolref
  NBphyto <- pmax(0,NBphyto - 0.5*Nbapex) #correction simuls pour les comptages decimaux
  
  RDepth <- moysimval(ltoto,lsusm, var='RDepth')/ nbplt
  Hmax <- moysimval(ltoto,lsusm, var='Hplante')/ nbplt
  FTSW <- moysimval(ltoto,lsusm, var='FTSW')/ nbplt
  NNI <- moysimval(ltoto,lsusm, var='NNI')/ nbplt
  R_DemandC_Root <- moysimval(ltoto,lsusm, var='R_DemandC_Root')/ nbplt
  cutNB <- moysimval(ltoto,lsusm, var='cutNB')/ nbplt
  
  simmoy <- data.frame(STEPS, TT, NBI, NBphyto, LAI, MSA, MSpiv, MSracfine, MSrac, RDepth, Hmax, FTSW, NNI, R_DemandC_Root, cutNB)
  simmoy
}#version revue par Lucas tient cmpte du nom de l'espece dans les assos

#simmoy <- build_simmoy(ltoto, lsusm=names(ltoto))



