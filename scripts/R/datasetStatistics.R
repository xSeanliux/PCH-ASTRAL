

library(shiny)
library(plotly)
library(optparse)
library(dplyr)
library(stringr)
library(ape)
library(testit)
library(phangorn)
library(castor)
print(getwd())

source('inferenceUtils.R')

numtrees = 32
numreplicas = 4
POLYMORPHISM = list('mod', 'modhigh', 'high', 'veryhigh')
SUFFIX="-hihp"

getCharCountsForMp1 <- function(numedge=0, factor='1.0', do_morph=FALSE) {
  res = data.frame()
  morph_dir = ''
  if(do_morph == FALSE) {
    morph_dir = 'no-morph'
  }
  for (c in POLYMORPHISM) {
    tot_mono_rows = c()
    informative_chrs = c()

    for (t in 1:numtrees) {
      for (r in 1:numreplicas) {
        if (numedge == 0) file = paste0('../OneMostProb/data/simulated_data-', factor, SUFFIX, '/', c,'_noborrowing/', morph_dir,'/', 'sim_tree',t,'_',r,'.csv')
        else {
          assert({FALSE})
        #   if (c %in% 1:5) ch = c+5
        #   else if (c==11) ch = 12
        #   else assert({FALSE})
        #   file = paste0("../SimulationPipeline/sim_outputs/config", ch, "/sim_net", numedge, '-', t, '_', r, '.csv')
        }
        df = read.csv(file)
        doubledf <- preprocessData(df, FALSE, 'Replace with majority', FALSE)$df
        uninf = findUninformativeCharacters(doubledf)$uninf
        n_informative = nrow(doubledf)-length(uninf)
        tot_mono_rows <- c(tot_mono_rows, nrow(doubledf))
        informative_chrs <- c(informative_chrs, n_informative)
        if(is.nan(n_informative)) {
            print(doublef)
            print(uninf)
        }
      }
    }
    # print(c('The length of vec is ', length(tot_mono_rows)))
    # assert({length(vec) == 128})
    
    # if (c == 11) c=6
    res = rbind(res, data.frame(
                          inf_mp4_chrs=mean(informative_chrs),inf_mp4_chrs_se=sd(informative_chrs)))
  }
  res
}


print(c("Number of MP4 parsimony-informative characters for suffix", SUFFIX))
print(paste(POLYMORPHISM, collapse = '  '))
for(factor in list('1.0','2.0','4.0','8.0')) {
  for(morph in list(TRUE)) {
    print(sprintf("Factor: %s, Morph: %d", factor, morph))
    res = getCharCountsForMp1(factor=factor, do_morph=morph)
    print(c(res[['inf_mp4_chrs']]))
  }
}
