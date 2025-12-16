library(shiny)
library(optparse)
library(dplyr)
library(stringr)
library(ape)
library(testit)
library(phangorn)
library(castor)

option_list = list(
  make_option(c("-f", "--input-data"), type="character", default=NULL, 
              help="dataset file name", metavar="character"),
  make_option(c("-o", "--output-file"), type="character", default=NULL, 
              help="Output Nexus file", metavar="character"),
  make_option(c("-p", "--resolve-poly"), type="integer", default=NULL, 
              help="How to resolve poly (1,2,3,4)", metavar="character"),
  make_option(c("-m", "--morph-weight"), type="double", default=NULL, 
              help="How to weight morph characters", metavar="character"),
  make_option(c("-H", "--hash"), type="character", default="", 
              help="Unique hash of the run", metavar="character"),
  make_option(c("-O", "--original-weights"), action="store_true", default=FALSE,
              help="Use original weights", metavar="character")
); 

opt_parser = OptionParser(option_list=option_list);
opt = parse_args(opt_parser);

for (x in unlist(lapply(option_list, function(x) slot(x, 'long_flag')))) assert (paste0(substr(x, 2, nchar(x)), ' cannot be null'), {!is.null(opt[[substr(x, 3, nchar(x))]])})

# orig_wd <- getwd()
# ROOT <- Sys.getenv("TALLIS")
# setwd(paste(ROOT,'LingPhyloR', sep=""))
source("scripts/R/inferenceUtils.R", local=T)
# setwd(orig_wd)

buildNexusFromFile <- function(file, poly_resolve, file_save, morph_weight, hash, use_dataset_weights=FALSE) {
  # print("Start") 
  # if(typeof(poly_resolve) == "character") {
  #   poly_resolve = strtoi(poly_resolve)
  # }
  # print(c('Poly resolve = ', poly_resolve, "type = ", typeof(poly_resolve)))
  df <- read.csv(file)
  for (i in 1:nrow(df)) {
    if(use_dataset_weights != TRUE) {
      if(substr(df[i,'id'], 1,1) == 'o') {
        if (substr(df[i,'id'], 2,2) == 'm') {
          df[i,'weight'] = morph_weight
        } # else assert({substr(df[i,'id'], 2,2) == 'l' && df[i,'weight'] == 1})
      } else {
        if (substr(df[i,'id'], 1,1) == 'm') {
          df[i,'weight'] = morph_weight
        } # else assert({substr(df[i,'id'], 1,1) == 'l' && df[i,'weight'] == 1})
      }
    } else {
      # print("Using dataset character weights.")
    }
  }

  #### NOTES ####
  # 1: MP 2 (Replace all with ?)
  # 2: MP 3 (Replace unique with ?)
  # 3: MP 4 (Replace with majority)
  # 4: GA
  # 5: MP 1 (Remove entire character)
  # 6: MP with Binary Encoding
  # 7: Dollo MP with Binary Encoding
  # 8: BEAST Covarion
  # 9: TraitLab
  # 10: UPGMA 4 (i.e. do reduction of MP 4, which actually isnt very smart)
  # 11: NJ 4 (same)
  # 12 UPGMA 1 (Exact match)
  # 13 UPGMA 2 (Jaccard similarity)
  # 14 UPGMA 3 (Overlap coefficient)
  # 15 NJ 1 (Exact match)
  # 16 NJ 2 (Jaccard similarity)
  # 17 NJ 3 (Overlap coefficient)
  
  polyOptions = c("Replace all with ?", 
                  "Replace unique with ?", 
                  "Replace with majority", 
                  'GA Binary Encoding',
                  "Remove entire character", 
                  'GA Binary Encoding', 
                  'GA Binary Encoding',
                  NA,
                  'GA Binary Encoding',
                  "Replace with majority",
                  "Replace with majority")
  if (poly_resolve %in% c(1,2,3,4,5,6,7,8,9, 10, 11)) {
    assert({poly_resolve %in% c(1,2,3,4,5,6,7,8,9, 10, 11)})
    poly_choice = polyOptions[poly_resolve]
    print(c("Poly choice is ", poly_choice)) 
    doubledf <- preprocessData(df, TRUE, poly_choice, FALSE)

    df = doubledf$df
    # print("Saving df to mp4_path")
    # write.table(df, file=mp4_path, sep=',', row.names=FALSE, quote=FALSE)
  }
  else {
    assert({poly_resolve %in% c(12,13,14,15,16,17)})
    if (poly_resolve %in% c(12,15)) fxn <- distanceFunctionQ
    else if (poly_resolve %in% c(13,16)) fxn <- distanceFunctionJaccard
    else if (poly_resolve %in% c(14,17)) fxn <- distanceFunctionOverlapCoeff
    df <- computeDistanceMatrix(df, fxn)
  }



  if (poly_resolve %in% c(1,2,3,5,6)) crit <- 'Maximum Parsimony'
  else if (poly_resolve ==4) crit <- 'Gray-Atkinson'
  else if (poly_resolve ==7) crit <- 'Dollo Maximum Parsimony'
  else if (poly_resolve == 8) { # BEAST covarion
    write.csv(df, paste0(file_save, '.csv')) # file_save should not have an extension in this case
    toprint <- c('[admin]\nbasename=expt\nlog_every=2000') # \nscreenlog=False
    toprint <- c(toprint, '[MCMC]\nchainlength=1000000')
    toprint <- c(toprint, '[model expt]')
    toprint <- c(toprint, 'model=covarion\nbinarized=True\ngamma_categories=4')#\nrate_variation=True')
    toprint <- c(toprint, paste0('data=',file_save, '.csv'))
    toprint <- c(toprint, '[clock default]\ntype=relaxed')
    toprint <- paste0(toprint, collapse='\n')
    sink(paste0(file_save, '.conf'))
    cat(toprint)
    sink()
  }
  else if (poly_resolve == 9) crit <- 'TraitLab'
  else if (poly_resolve == 10) crit <- 'UPGMA'
  else if (poly_resolve == 11) crit <- 'NJ'
  else if (poly_resolve %in% c(12,13,14)) crit <- 'UPGMA-dist'
  else if (poly_resolve %in% c(15,16,17)) crit <- 'NJ-dist'
  else assert({FALSE})
  if (poly_resolve != 8) {
    if (poly_resolve %in% c(10,11,12,13,14,15,16,17)) {
      isexhaust = NULL
      mweight = NULL
    }
    else {
      isexhaust = FALSE
      mweight = morph_weight != 1 && !(poly_resolve %in% c(4,6,7))
    }
    if(use_dataset_weights) {
      mweight = TRUE
    }
    
    nexus_str <- writeNexus(df, crit, mweight, isexhaust, NULL, hash)
    if (!is.null(file_save)) {
      sink(file_save)
      cat(nexus_str)
      sink()
    }
    else {
      cat (nexus_str)
    }
  }
}

buildNexusFromFile(opt[['input-data']], opt[['resolve-poly']], opt[['output-file']], opt[['morph-weight']], opt[['hash']], opt[["original-weights"]])






