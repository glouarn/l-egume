

dir <- choose.dir()
#"C:\\devel\\l-egume\\legume\\test"


library("readxl")
source(paste(dir, "fonctions_analyses.r",sep="\\"))
source(paste(dir, "fonctions_mef.r",sep="\\"))



dirlast <-  paste(dir, "lastvalid",sep="\\")
#dirlast <-  paste(dir, "test_champ",sep="\\") #pour visu dossier sorties champ
setwd(dirlast)#(dir0)#
pathobs <- paste(dir, "obs", sep="\\")





ls_files <- list.files(dirlast)#(dir0)#


#recupere la liste des toto file names du dossier de travail
ls_toto <- ls_files[grepl('toto', ls_files)]

#creation du dataFrame dtoto et recup des info fichier
dtoto <- as.data.frame(t(as.data.frame(strsplit(ls_toto, '_'))))#[,c(2,3,6,7,8,9,10)]
row.names(dtoto) <- 1: length(dtoto[,1])
dtoto <- dtoto[,c(2,3,4,5,6,7,8,9)]
names(dtoto) <- c('usm','lsystem','mix','damier','scenario','Mng', 'seed','meteo')
dtoto$name <- ls_toto
dtoto$seed <- substr(as.character(dtoto$seed), 1, 1)
dtoto$scenario <- substr(as.character(dtoto$scenario), 9, nchar(as.character(dtoto$scenario)))
dtoto$keysc <- paste(dtoto$scenario, dtoto$mix, dtoto$Mng, dtoto$meteo, dtoto$damier)# ajout d'une cle unique par scenario
#dtoto$damier <- as.numeric(substr(as.character(dtoto$damier), 7, 7))

#split de dtoto et stockage dans une liste de scenatios
sp_dtoto <- split(dtoto, dtoto$keysc)
#names(sp_dtoto)




#rapport des graphs dynamiques
nomrap <- paste( 'rapport_eval-Dyn',Sys.Date(),basename(dirlast),'.pdf', sep="_")
pdf(paste(dir,nomrap, sep='\\'), onefile=T)


for (key in names(sp_dtoto))#
{
  #analyse par usm
  #key <- names(sp_dtoto)[20]#dileg luz


  ls_toto_paquet <- sp_dtoto[[key]]$name
  
  #recuperation par paquet des fichiers de base (pas de stockage de l'ensemble des fichiers en memoire)
  ltoto <- read_ltoto(ls_toto_paquet)
  #version locale du paquet de doto
  dtoto <- sp_dtoto[[key]]
  
  #recup du nom des esp et traitement
  mix <- strsplit(ls_toto_paquet[1], '_')[[1]][4] #suppose paquet fait par traitement
  esp <- strsplit(mix, '-')[[1]][1] #'Fix2'
  esp2 <- strsplit(mix, '-')[[1]][2] #'nonFixSimTest'
  meteo <- strsplit(ls_toto_paquet[1], '_')[[1]][9]
  damier <- strsplit(ls_toto_paquet[1], '_')[[1]][5]
  
  #recup des obs correspondant
  namexl <- paste0(meteo, "_obs.xls")#"morpholeg14_obs.xls"
  trait <- if (esp == esp2 & damier=="homogeneous0") "ISO" else "HD-M2" #sera a adapter selon les melanges ou a renommer "timbale-krasno"
  if (meteo == "DivLeg15" | meteo == "LusignanDivLeg" | meteo == "LusignanAsso16")
  {
    trait <- "HD"
  }
  #trait <- if (esp == esp2 & damier=="homogeneous0" & meteo=="morpholegRGR15") "LD"
  onglet <- paste0(meteo, "_",trait,"_",esp)#"morpholeg14_ISO_timbale" #marche pour isole; a revoir pour autres
  #onglet <- "F_E1D1_B_R1" #"force!!
  obs <- read_excel(paste(pathobs,namexl,sep="\\"), sheet = onglet, col_names = TRUE, na = "")
  
  #calcul de la moyenne des simuls
  #pour l'espece 1
  simmoy <- build_simmoy(ltoto, lsusm=names(ltoto), esp)
  
    
  #fait les graph dynamiques
  #recup de surfsolref
  dat <- ltoto[[1]]
  surfsolref <- dat[dat$V1=='pattern',3] #m2
  #pour l'espece 1
  dynamic_graphs(simmoy, name=onglet, obs=obs, surfsolref=surfsolref) 
  
  #complement pour l'espece 2 si besoin
  if (esp != esp2 & damier!="homogeneous0")
  { 
    onglet2 <- paste0(meteo, "_",trait,"_",esp2)#"morpholeg14_ISO_timbale" #marche pour isole; a revoir pour autres
    obs2 <- read_excel(paste(pathobs,namexl,sep="\\"), sheet = onglet2, col_names = TRUE, na = "")
    simmoy2 <- build_simmoy(ltoto, lsusm=names(ltoto), esp2) 
    dynamic_graphs(simmoy2, name=onglet2, obs=obs2, surfsolref=surfsolref)
  }

}

dev.off()

#! NA dans fichier obs genere des bug de format + noms d'onglets a repredre...






#rapport des graphs obs-sim
nomrap <- paste( 'rapport_eval-Obs-Sim',Sys.Date(),basename(dirlast),'.pdf', sep="_")
pdf(paste(dir,nomrap, sep='\\'), onefile=T)



#construction du ls_dobsim d'une espece pour les plante isolee
esp_ <- 'timbale'#'giga'#'formica'#'sevanskij'#'leo'#'canto'#'kayanne'#
#ls_expe <- c('morpholeg14', 'morpholeg15')
ls_expe <- names(sp_dtoto)[grepl(esp_, names(sp_dtoto)) & grepl("homogeneous0", names(sp_dtoto)) & grepl("morpholeg", names(sp_dtoto))]#cle comportant le bon geno
#ls_expe <- names(sp_dtoto)[grepl(esp_, names(sp_dtoto)) & grepl("damier4", names(sp_dtoto))]#cle comportant le bon geno
ls_var <- c('NBI','nb_phyto_tot','surf_tot','Hmax','MSaerien')#,'long_pivot')
ls_varsim <- c('NBI','NBphyto','LAI', 'Hmax','MSA')#, 'RDepth')


ls_dobssim <- build_ls_dobssim(esp_, ls_expe, ls_var, ls_varsim)
#erreur dans la recuperation de Rdepth de 2015 (dates avant le debut??) 
#erreur d'affihage qd tableau vide?


#figure des obs sim de l'espece
layout(matrix(1:6,2,3, byrow=T))
for (var in ls_varsim) #var <- "NBI"#"MSA"#"LAI"#"NBphyto"#
{
  mobssim <- merge_dobssim(ls_dobssim[[var]])
  plot_obssim(mobssim, name=paste(esp_, "ISO/LD", var), displayusm=T)
}


#construction du ls_dobsim d'une espece pour les couverts denses
esp_ <- 'timbale'#'giga'#'formica'#'sevanskij'#'leo'#'canto'#'kayanne'#
#ls_expe <- c('morpholeg14', 'morpholeg15')
#ls_expe <- names(sp_dtoto)[grepl(esp_, names(sp_dtoto)) & grepl("homogeneous0", names(sp_dtoto))]#cle comportant le bon geno
ls_expe <- names(sp_dtoto)[grepl(esp_, names(sp_dtoto)) & grepl("damier4", names(sp_dtoto))]#cle comportant le bon geno
ls_var <- c('NBI','nb_phyto_tot','surf_tot','Hmax','MSaerien')#,'long_pivot')
ls_varsim <- c('NBI','NBphyto','LAI', 'Hmax','MSA')#, 'RDepth')


ls_dobssim <- build_ls_dobssim(esp_, ls_expe, ls_var, ls_varsim)
#erreur dans la recuperation de Rdepth de 2015 (dates avant le debut??) 
#erreur d'affihage qd tableau vide?



#figure des obs sm de l'espece
layout(matrix(1:6,2,3, byrow=T))
for (var in ls_varsim) #var <- "NBI"#"MSA"#"LAI"#"NBphyto"#
{
  mobssim <- merge_dobssim(ls_dobssim[[var]])
  plot_obssim(mobssim, name=paste(esp_, "HD", var), displayusm=T)
}


dev.off()




#finir le rapport

#tester avec melange a 2 especes -> OK pour dynamique / bug pas non plus pour obs-sim

#seprer simul plante isole et melanges dans les eval....? dans ls_expe


#fait par lucas
#separer NBI pousse ini et repousse dans eval + pour HD sim=comptage sur les decile superrieur de tige qui poussent

#visiblement pb d'unite dans les figures de NBphyto et LAI de combileg??? -> pb des 7 premieres tiges??




