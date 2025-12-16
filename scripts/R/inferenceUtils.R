
readAndVerifyData <- function(path) {
  #browser()
  data = read.csv(path)
  if (ncol(data) == 1) return ("Data must be a ','-separated CSV file.")
  if (!all(names(data)[1:3] == c('id', 'name', 'weight'))) return("The first 3 columns of the dataset must be 'id', 'name', 'weight'.") 
  if (sum(is.na(data)) > 0 || sum(data == '') > 0) return ("There can be no blank cells in the dataset.")
  if (sum(is.na(as.integer(data[,3]))) > 0 || sum(as.numeric(data[,3]) %% 1 != 0) > 0) return ("The 3rd column ('weight') must have all integer values.")
  return(data)
}

preprocessData <- function(df, use_ancestral, poly_choice, merge_iir) {
  
  assert({poly_choice %in% c("Replace all with ?", 
                             "Replace unique with ?", 
                             "Replace with majority",
                             "GA Binary Encoding", 
                             "Remove entire character",
                             "CLDF")})
  
  if (!use_ancestral && names(df)[4] == 'PIE') {
    df <- df[,-4]
  }
  
  if (merge_iir) {
    df <- merge_two_cols(df, 'Indic', 'Iranian', 'IndoIranian')
  }
  
  # Count the # of poly states per language and max poly width
  numpoly = rep(0, nrow(df))
  polywid = rep(0, nrow(df))
  for (col in 4:(ncol(df))) {
    bools <- grepl('/', df[,col])
    numpoly <- numpoly + as.integer(bools)
    cnts <- str_count(df[,col], '/')
    polywid <- pmax(polywid, cnts)
  }
  polywid <- polywid + 1
  polywid[polywid==1] = '-'
  
  res <- list(df_with_poly=df)
  
  if (poly_choice == "Replace all with ?") {# == "Replace with '?'") { # Replace polymorphism with ?'s
    for (col in 4:(ncol(df))) {
      bools <- grepl('/', df[,col])
      df[bools,col] <- '?'
    }
  }
  else if (poly_choice == "Replace with majority") {
    for (char in 1:nrow(df)) {
      # First get counts of each state
      dct = list()
      sts = df[char, 4:ncol(df)]
      if (!any(grepl('/', sts))) next
      for (col in 4:ncol(df)) {
        state = df[char,col ]
        state = as.character(state)
        if (grepl('/', state)) {
          splt <- str_split(state, '/')[[1]]
          for (st in splt) {
            if (st %in% names(dct)) dct[[st]] = dct[[st]] + 1
            else dct[[st]] = 1
          }
        }
        else {
          st = state
          if (!is.null(names(dct)) && (st %in% names(dct))) dct[[st]] <- dct[[st]] + 1
          else dct[[st]] = 1
        }
      }
      
      # Now, replace each polymorphic state with the one with highest counts. Ties go to lowest id (so it's arbitrary and deterministic).
      for (col in 4:ncol(df)) {
        state = df[char, col]
        if (grepl('/', state)) {
          splt <- str_split(state, '/')[[1]]
          max_cnt <- 0
          argmax <- NULL
          for (st in splt) {
            if (dct[[st]] > max_cnt) {
              max_cnt <- dct[[st]]
              argmax <- c(argmax, st)
            }
          }
          if (length(argmax) > 1) argmax <- argmax[order(argmax)][1]
          df[char, col] <- argmax
        }
        else next
      }
    }
  }
  else if (poly_choice == "Replace unique with ?") {
    for (char in 1:nrow(df)) {
      # First get counts of each state
      sts = unlist(df[char, 4:ncol(df)])
      if (!any(grepl('/', sts))) next
      
      unique_sts <- unique(sts)
      sts_copy = sts
      sts_copy[grepl('/', sts_copy)] <- -1
      sts_copy[sts == '?'] <- -1
      sts_copy <- as.integer(sts_copy)
      new_id <- max(sts_copy) + 1
      
      sts_h <- c('NA', 'NA', 'NA', sts)
      for (state in unique_sts) {
        if (!grepl('/', state)) next
        else if (sum(sts == state) == 1) df[char, sts_h == state] <- '?'
        else if (sum(sts == state) > 1) {
          df[char, sts_h == state] <- new_id
          new_id <- new_id + 1
        }
        else stop()
      }
      assert ({!any(is.na(df[char,]))})
    }
  }
  else if (poly_choice == "GA Binary Encoding" || poly_choice == 'CLDF') {
    df <- replaceQsWithNums(df)
    new_df = data.frame(matrix(ncol=ncol(df),nrow=0))
    names(new_df) <- names(df)
    for (char in 1:nrow(df)) {
      dct = list()
      sts = df[char, 4:ncol(df)]
      # if (!any(grepl('/', sts))) next
      for (col in 4:ncol(df)) {
        state = df[char,col ]
        state = as.character(state)
        if (grepl('/', state)) {
          splt <- str_split(state, '/')[[1]]
          for (st in splt) {
            if (st %in% names(dct)) dct[[st]] = dct[[st]] + 1
            else dct[[st]] = 1
          }
        }
        else {
          st = state
          if (!is.null(names(dct)) && (st %in% names(dct))) dct[[st]] <- dct[[st]] + 1
          else dct[[st]] = 1
        }
      }
      nms <- as.integer(names(dct))
      nms <- nms[order(nms)]
      for (nm in nms) {
        new_row = data.frame(matrix(ncol=ncol(df),nrow=1))
        names(new_row) <- names(df)
        new_row[1,'id'] = paste0(df[char,'id'], '_', nm)
        new_row[1,'feature'] = paste0(df[char,'feature'], '_', nm)
        new_row[1,'weight'] = df[char,'weight']
        for (j in 4:ncol(df)) {
          st = df[char,j]
          if (grepl('/', st)) {
            splt <- as.integer(str_split(st, '/')[[1]])
            new_row[1,j] = as.integer(nm %in% splt)
          }
          else new_row[1,j] = as.integer(nm == st)
        }
        if(!all(!is.na(new_row))) {
          print(new_row)
        }
        assert(all(!is.na(new_row)))
        new_df <- rbind(new_df, new_row)
      }
    }
    assert(all(!is.na(new_df)))
    df = new_df
  }
  else if (poly_choice == "Remove entire character") {
    rows_to_keep = c()
    for (r in 1:nrow(df)) {
      row = df[r,4:ncol(df)]
      if (!any(grepl('/', row))) { # Keep row
        rows_to_keep <- c(rows_to_keep, r)
      }
    }
    df = df[rows_to_keep,]
    
  }
  else { # Expand into sep chars
    assert ({FALSE})
  }
  
  # just confirm no poly left
  for (col in 4:ncol(df)) {
    assert({!any(grepl('/', df[,col]))})
  }
  
  if (poly_choice == 'CLDF') {
    df = df[,names(df)[names(df) != 'weight' & names(df) != 'feature']]
    melted =reshape2::melt(df)
    names(melted) <- c('Feature_ID', 'Language_ID', 'Value')
    melted <- melted[,c(2,1,3)]
    df=melted
    
  }
  res$df = df
  res$num_poly = numpoly
  res$polywid = polywid
  
  res
}

merge_two_cols <- function (df, col1, col2, new_name) {
  new_df <- df
  new_df[[new_name]] <- NA
  for (i in 1:nrow(df)) {
    col1_state <- df[i,col1]
    col2_state <- df[i,col2]
    if (col1_state == col2_state) new_df[i,new_name] <- col1_state
    else if (col1_state == '?' && col2_state != "?") new_df[i,new_name] <- col2_state
    else if (col2_state == '?' && col1_state != "?") new_df[i,new_name] <- col1_state
    else {
      sum_col1_state = sum(df[i,4:ncol(df)] == col1_state)
      sum_col2_state = sum(df[i,4:ncol(df)] == col2_state)
      if (sum_col1_state == 1 && sum_col2_state > 1) { # do col2 state
        new_df[i,new_name] <- col2_state
      }
      else if (sum_col2_state == 1 && sum_col1_state > 1) { # do col1 state
        new_df[i,new_name] <- col1_state
      }
      else if (sum_col1_state > 1 && sum_col2_state > 1) {
        stop("This is the case where the 2 languages can't be merged.....")
      }
      else if (sum_col1_state == 1 && sum_col2_state == 1) new_df[i, new_name] <- '?'
      else stop("This is an impossible case to reach (something must be wrong in code if gets to here)....")
    }
  }
  new_df <- new_df[,-which(names(new_df) == col1)]
  new_df <- new_df[,-which(names(new_df) == col2)]
  return(new_df)
}

writeNexus <- function(df, criterion, do_weight, is_exhaustive, keep, hash="") {
  print(c('hash: <', hash,'>'))
  assert({criterion %in% c('Maximum Parsimony', 'Gray-Atkinson', 'Dollo Maximum Parsimony', 'TraitLab', 'NJ', 'UPGMA', 'NJ-dist', 'UPGMA-dist')})
  toprint <- c()

  # Taxa block
  if (!(criterion %in% c('UPGMA-dist', 'NJ-dist'))) taxa = names(df)[4:length(names(df))]
  else taxa <- names(df)
  ntax = length(df)
  if (criterion != 'TraitLab') {
    toprint <- c(toprint, '#NEXUS\n\nbegin taxa;', paste0('\tdimensions ntax=', length(taxa), ';'), '\ttaxlabels')
    for (tax in taxa) {
      toprint <- c(toprint, paste0('\t\t', tax))
    }
    toprint <- c(toprint, '\t;\nend;')
  }
  else {
    toprint <- c(toprint, paste0('#NEXUS\n\nbegin data;\n\tdimensions ntax=', length(taxa), ' nchar=', nrow(df), ';\n\tmatrix'))
  }

  
  symbols = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789@~"
  
  # Char block
  if (!(criterion %in% c('UPGMA-dist', 'NJ-dist'))) {
    if (criterion != 'TraitLab') {
      if (criterion != 'Gray-Atkinson') line <- paste0('\nbegin characters;\n\tdimensions nchar=', nrow(df), ';\n\tformat missing=? RespectCase symbols="',symbols ,'" transpose;\n\tmatrix')
      else line <- paste0('\nbegin characters;\n\tdimensions nchar=', nrow(df), ';\n\tformat missing=? datatype=restriction;\n\tmatrix')
      toprint <- c(toprint, line)
    }
    if (criterion %in% c('Gray-Atkinson', 'TraitLab')) all_ministr <- c()
    for (char in 1:nrow(df)) {
      # First get list of states present
      states_char <- c()
      for (state in df[char,4:ncol(df)]) {
        if (state == '?') next
        else states_char <- c(states_char, state)
      }
      states_char <- unique(states_char)
      states_char <- states_char[order(states_char)]
      if (length(states_char) < 1 || length(states_char) > nchar(symbols)) stop(paste0('You cannot have more than ', nchar(symbols), ' states for any character.'))
      if (criterion == 'Gray-Atkinson' || criterion == 'Dollo Maximum Parsimony' || criterion == 'TraitLab') {
        if (length(states_char) == 1) assert({'0' %in% states_char || '1' %in% states_char})
        else if (length(states_char) == 2) assert({'0' %in% states_char && '1' %in% states_char})
        else if (length(states_char) == 3) assert({'0' %in% states_char && '1' %in% states_char && '?' %in% states_char})
        else assert({FALSE})
      }
      
      # Now convert to string
      ministr <- ''
      for (state in df[char,4:ncol(df)]) {
        if (state == '?') ministr <- paste0(ministr, '?')
        else {
          if (criterion == 'Gray-Atkinson' || criterion =='TraitLab') {
            ministr <- paste0(ministr, state) 
          }
          else {
            idx <- which(states_char == state)
            ministr <- paste0(ministr, substr(symbols, idx, idx))
          }
          
        }
      }
      if (criterion != 'Gray-Atkinson' && criterion != 'TraitLab') toprint <- c(toprint, paste0('\t\t', df[char,1], '\t', ministr))
      else all_ministr <- c(all_ministr, ministr)
    }
    if (criterion %in% c('Gray-Atkinson', 'TraitLab')) { # It doesn't like tranposed version......
      newstrs <- c()
      for (i in 1:length(all_ministr)) {
        str <- all_ministr[i]
        if (i!=1) assert({nchar(str) == length(newstrs)})
        for (j in 1:nchar(all_ministr[i])) {
          if (i == 1) newstrs <- c(newstrs, substr(str, j, j))
          else newstrs[j] <- paste0(newstrs[j], substr(str, j, j))
        }
      }
      
      
    }
    if (criterion == 'Gray-Atkinson') for (i in 1:length(newstrs)) toprint <- c(toprint, paste0('\t\t', 't', i, '\t', newstrs[i])) # THINK probably this should be like line below?
    if (criterion == 'TraitLab') for (i in 1:length(newstrs)) toprint <- c(toprint, paste0('\t\t', taxa[i], '\t', newstrs[i]))
    toprint <- c(toprint, '\t;\nend;')
    
    # Assumption block for dollo only
    if (criterion == 'Dollo Maximum Parsimony') {
      toprint <- c(toprint, '\nbegin assumptions;\n\toptions deftype=dollo.up;\nend;')
    }
  }
  
  else {
    toprint <- c(toprint, paste0('\nbegin distances;\n\tformat triangle = both;\n\tmatrix'))
    for (i in 1:nrow(df)) {
      line <- paste0('\t\t',names(df)[i])
      for (j in 1:nrow(df)) {
        if (is.na(df[i,j])) line <- c(line, round(df[j,i],1))
        else line <- c(line, round(df[i,j],1))
      }
      if (i == nrow(df)) line[length(line)] = paste0(line[length(line)], ';')
      toprint <- c(toprint, paste0(line, collapse='\t'))
    }
    toprint <- c(toprint, 'end;')
  }
  
  # Paup or MrBayes block
  if (criterion != 'Gray-Atkinson' && criterion != 'TraitLab') {
    toprint <- c(toprint, '\nbegin paup;')
    if (criterion %in% c('Maximum Parsimony', 'Dollo Maximum Parsimony')) {
      if (is_exhaustive) fst <- "\tset criterion=parsimony;"
      else fst <- "\tset criterion=parsimony maxtrees=1024 increase=no;"
      
      if (do_weight) {
        fst <- paste0(fst, '\n\tweights')
        unique_weights <- unique(df[,'weight'])
        for (weight in unique_weights) {
          fst <- paste0(fst, ' ', weight, ':', paste0(which(df[,'weight'] == weight), collapse = ' '))
          if (weight != unique_weights[length(unique_weights)]) fst <- paste0(fst, ',')
        }
        fst <- paste0(fst, ';')
      }
      if (!is.null(keep)) kp <- paste0(' keep=', keep)
      else kp <- ''
      toprint <- c(toprint, fst)
      if (!is_exhaustive) toprint <- c(toprint, paste0('\thsearch start=stepwise addseq=random nreps=25 swap=tbr', kp, ';'))
      else toprint <- c(toprint, paste0('\talltrees', kp, ';'))
    }
    else if (criterion == 'UPGMA' || criterion == 'NJ' || criterion == 'UPGMA-dist' || criterion == 'NJ-dist' ) {
      assert({is.null(is_exhaustive)})
      assert ({is.null(keep)})
      assert({is.null(do_weight)})
      if (criterion == 'UPGMA') fst <- "\tUPGMA;"
      else if (criterion == 'NJ') fst <- "\tNJ;"
      else if (criterion == 'UPGMA-dist') fst <- "\tUPGMA;"
      else if (criterion == 'NJ-dist') fst <- "\tNJ;"
      toprint <- c(toprint, fst)
    }
    else stop()
    
    if (is.null(keep) && !(criterion %in% c('UPGMA-dist', 'NJ-dist'))) toprint <- c(toprint, '\tfilter best=yes;')
    if (!(criterion %in% c('UPGMA-dist', 'NJ-dist'))) toprint <- c(toprint, paste(c('\tpscores all/ ci ri rc hi scorefile=paup_out_', hash,'.scores replace=yes;'), collapse=''))
    toprint <- c(toprint, paste(c('\tsavetrees file=paup_out_', hash, '.trees replace=yes format=nexus;'), collapse=''))
    toprint <- c(toprint, '\tquit;\nend;')
  }
  else if (criterion == 'Gray-Atkinson') {
    toprint <- c(toprint, '\nbegin mrbayes;')
    toprint <- c(toprint, 'set autoclose=yes nowarn=yes;')
    # toprint <- c(toprint, 'set usebeagle=yes beagledevice=cpu')
    # toprint <- c(toprint, 'set beaglescaling=dynamic beaglesse=yes;')
    toprint <- c(toprint, 'lset rates=gamma;')
    toprint <- c(toprint, 'mcmcp ngen=250000 printfreq=10000 samplefreq=500')
    toprint <- c(toprint, paste(c('nruns=1 nchains=4 savebrlens=yes filename=Bayes_out_', hash, ';'), collapse=''))
    toprint <- c(toprint, 'mcmc;')
    toprint <- c(toprint, 'set nowarnings=yes;')
    toprint <- c(toprint, paste(c('sumt filename=Bayes_out_', hash, ' burnin=100000;'), collapse='')) # believe this burn in is just for the summary stats (e.g. con tree), meaning it throws out the first 100 (of the 200 in this case)
    toprint <- c(toprint, 'quit;')
    toprint <- c(toprint, 'end;')
  }
  else if (criterion == 'TraitLab') {
    # Comment this out if don't want clade or root constraints
    toprint <- c(toprint, 'begin clades;\n')
    
    # Clade constraints
    for (i in 1:length(taxa)) {
      toprint <- c(toprint, paste0('CLADE NAME = ', taxa[i]))
      toprint <- c(toprint, 'ROOTMIN = 0')
      toprint <- c(toprint, 'ROOTMAX = 15999')
      toprint <- c(toprint, paste0('TAXA = ', taxa[i], ';\n'))
    }
    
    # Root constraints
    toprint <- c(toprint, paste0('CLADE NAME = ', 'root'))
    toprint <- c(toprint, 'ROOTMIN = 15998')
    toprint <- c(toprint, 'ROOTMAX = 15999')
    taxalist = paste0(taxa, collapse = ',')
    toprint <- c(toprint, paste0('TAXA = ', taxalist, ';\n'))
    
    
    toprint <- c(toprint, 'end;')
  }
  paste0(toprint, sep='\n')

  
}

distanceFunctionQ <- function (string1, string2) {
  state1 = as.character(string1)
  state2 = as.character(string2)
  if (grepl('/', state1)) {
    splt <- str_split(state1, '/')[[1]]
    osplt <- splt[order(splt)]
    state1 <- paste0(osplt, collapse = '/')
  }
  if (grepl('/', state2)) {
    splt <- str_split(state2, '/')[[1]]
    osplt <- splt[order(splt)]
    state2 <- paste0(osplt, collapse = '/')
  }
  if (state1 == state2) return (0)
  else return (1)
}
# testDistFxn(1)

distanceFunctionJaccard <- function (string1, string2) {
  state1 = as.character(string1)
  state2 = as.character(string2)
  if (grepl('/', state1)) {
    splt <- str_split(state1, '/')[[1]]
    osplt <- splt[order(splt)]
    state1 <- osplt
  }
  if (grepl('/', state2)) {
    splt <- str_split(state2, '/')[[1]]
    osplt <- splt[order(splt)]
    state2 <- osplt
  }
  union = unique(c(state1, state2))
  int = 0
  for (i in union) {
    if (i %in% state1 && i %in% state2) int = int + 1
  }
  return (1-int / length(union))
}
# testDistFxn(2)


distanceFunctionOverlapCoeff <- function (string1, string2) {
  state1 = as.character(string1)
  state2 = as.character(string2)
  if (grepl('/', state1)) {
    splt <- str_split(state1, '/')[[1]]
    osplt <- splt[order(splt)]
    state1 <- osplt
  }
  if (grepl('/', state2)) {
    splt <- str_split(state2, '/')[[1]]
    osplt <- splt[order(splt)]
    state2 <- osplt
  }
  union = unique(c(state1, state2))
  int = 0
  for (i in union) {
    if (i %in% state1 && i %in% state2) int = int + 1
  }
  return(1-int/min(length(state1), length(state2)))
}
#testDistFxn(3)

testDistFxn <- function(fxn_id) {# internal use - unit cases
  # REMEMBER: these are all distances, so basically 1 - similarity
  string1s <- c('1', '1', '1',   '1/2', '1/2','1/2', '1/2',   '1/2')
  string2s <- c('1', '2', '1/2', '1/2', '1',  '2/3', '1/2/3', '2/3/4')
  if (fxn_id == 1) {
    ans <- c(0, 1, 1, 0, 1, 1,1,1)
    fxn = distanceFunctionQ
  } else if (fxn_id == 2) {
    ans <- c(0, 1, 1/2, 0, 1/2, 2/3, 1/3, 3/4) 
    fxn = distanceFunctionJaccard
  } else if (fxn_id == 3) {
    ans <- c(0, 1, 0, 0, 0, 1/2, 0, 1/2) 
    fxn = distanceFunctionOverlapCoeff
  }
  
  all_passed = TRUE
  for (i in 1:length(string1s)) {
    print(c(string1s[i], string2s[i]))
    res <- fxn(string1s[i], string2s[i])
    print(c(res, ans[i]))
    if (res == ans[i]) print("Passed!")
    else print("Failed!")
    if (res != ans[i]) all_passed = FALSE
    print('-------')
  }
  if (all_passed) print ("ALL PASSED")
  else print("FAILED!")

  
  
  
}


computeDistanceMatrix <- function(df, dist_fxn) {
  taxa = names(df)[4:length(names(df))]
  res = data.frame(matrix(nrow=length(taxa),ncol=length(taxa)), row.names = taxa)
  names(res) = taxa
  for (i in 1:length(taxa)) {
    for (j in i: length(taxa)) {
      if (j < i) next
      taxa_i = taxa[i]
      taxa_j = taxa[j]
      seq_i = df[[taxa_i]]
      seq_j = df[[taxa_j]]
      dist = 0
      assert({length(seq_j)  == length(seq_i)})
      for (k in 1:length(seq_i)) {
        dist = dist + dist_fxn(seq_i[k], seq_j[k])
      }
      res[i,j] = dist
    }
  }
  res
}
  
  
readTrees <- function(df, is_weighted) {
  trees = read.nexus('paup_out.trees', tree.names = NULL, force.multi = TRUE)
  scores = read.csv('paup_out.scores', sep='\t')$Length
  new_trees = list()
  unique_scores <- unique(scores)
  unique_scores <- unique_scores[order(unique_scores)]
  nms <- c()
  i<- 1
  for (score in unique_scores) {
    idxes <- which(scores == score)
    for (idx in idxes) {
      new_trees[[i]] <- trees[[idx]]
      ret_weighted <- findIncompatChars(trees[[idx]], df, TRUE)
      ret_unweighted <- findIncompatChars(trees[[idx]], df, FALSE)
      
      #browser()

      ps_score_unweighted <- ret_unweighted$ps_score
      ps_score_weighted <- ret_weighted$ps_score
      incompat_score_unweighted <- nrow(ret_unweighted$df)
      incompat_score_weighted <- sum(ret_weighted$df$weight)

      # these checks are required when score is parismony, but not if criterion was sthg else
      # if (is_weighted) assert({score == ps_score_weighted})
      # else assert({score == ps_score_unweighted})
      
      nms <- c(nms, paste0("Tree ", i, ' (', ps_score_unweighted, ' | ', ps_score_weighted, ' | ', incompat_score_unweighted, ' | ', incompat_score_weighted, ')'))
      i <- i + 1
    } 
  }
  list(trees=new_trees, names=nms, scores = scores[order(scores)])
  
}

# makeGreedyConsensus<- function(trees, maj_tree=NULL) {
#   res = prop.part(trees$trees, check.labels = TRUE)
#   cnts = attr(res, 'number')
#   labels = attr(res, 'labels')
#   cnts_order = order(cnts, decreasing = TRUE)
#   if (is.null(maj_tree)) {
#     maj_tree = consensus(trees$trees, p=0.5, check.labels=TRUE, rooted=FALSE)
#     maj_tree$node.label = NULL
#   }
#   for (i in 1:length(cnts_order)) {
#     index = cnts_order[i]
#     if (i == 1) assert({length(res[[index]]) ==  length(trees$trees[[1]]$tip.label)}) # should be all the leaves
#     else {
#       
#     }
#   }
# }

makeConsensusTrees <- function(trees) {
  strict <- consensus(trees$trees, p=1, check.labels=TRUE, rooted=FALSE)
  majority <- consensus(trees$trees, p=0.5, check.labels=TRUE, rooted=FALSE)
  strict$node.label = NULL
  majority$node.label = NULL
  nms <- c('Strict Consensus', 'Majority Consensus')
  list(trees=list(strict, majority), names=nms)
}

replaceQsWithNums <- function(df) {
  for (i in 1:nrow(df)) {
    # start <- max(as.integer(df[i,4:ncol(df)][df[i,4:ncol(df)] != '?']))+1
    start <- 1000
    for (q in 4:ncol(df)) {
      if (df[i, q] == '?') {
        df[i, q] = start
        start <- start + 1
      }
    }
  }
  df
}

findUninformativeCharacters <- function(df) {
  uninf <- c()
  numbigstates <- c()
  df <- replaceQsWithNums(df)
  for (char in 1:nrow(df)) {
    states <- as.character(df[char,4:ncol(df)])
    unique_states <- unique(states)
    states_with_atleast2 <- c()
    for (state in unique_states) {
      if (sum(states == state) >= 2) states_with_atleast2 <- c(states_with_atleast2, state)
    }
    if (length(states_with_atleast2) < 2) {
      uninf <- c(uninf, char)
    }
    numbigstates <- c(numbigstates, length(states_with_atleast2))
  }
  
  list(uninf=uninf, numbigstates=numbigstates)
}

genUninfCharText <- function(uninf_chars, df) {
  if (length(uninf_chars) == 0) return("There are no parsimony-uninformative characters in the dataset. Great!")
  else {
    str <- paste0("There are ", length(uninf_chars), " parsimony-uninformative characters in the dataset. They are:<br>")
    str <- paste0(str, '<ul>')
    for (char in uninf_chars) {
      str <- paste0(str, '<li>', df[char,1], '&emsp;', df[char,2], '</li>')
    }
    str <- paste0(str, "</ul>You can sort the table below by the column 'is_informative' to see the states for these characters.")
    
    return(str)
  }
}

genIncompatCharTable <- function(incompat_chars, df) {
  if (length(incompat_chars) == 0) stop("Does not run in this case (FIX)")
  else {
    ids <- c()
    nms <- c()
    rcs <- c()
    
    str <- paste0("There are ", length(incompat_chars), " incompatible characters on this tree. They are:<br>")
    str <- paste0(str, '<ul>')
    for (char in incompat_chars) {
      str <- paste0(str, '<li>', df[char,1], '&emsp;', df[char,2], '</li>')
    }

    return(str)
  }
}

buildPhyDat <- function (df ) {
  df <- replaceQsWithNums(df)
  lst <- as.list(df[,4:ncol(df)])
  levels =unique(as.vector(as.matrix(df[,4:ncol(df)])))
  phyDat(lst, type = 'USER', levels = levels)
}

findIncompatChars <- function(tree, df, is_weighted, return_all_chars = FALSE) {
  ids <- c()
  nms <- c()
  rcs <- c()
  scores <- c()
  xtrachange <- c()
  if (is_weighted) weights <- c()
  df_noqs <- replaceQsWithNums(df)
  ps_score = 0
  for (i in 1:nrow(df)) {
    alignment_i = buildPhyDat(df[i,]) # note: this replaces ?'s so no need to worry
    score_i =  parsimony(tree, alignment_i)
    score_iq = score_i - sum(df[i,4:ncol(df)] == '?')
    if (!is_weighted) ps_score <- ps_score + score_iq
    else ps_score <- ps_score + (score_iq * df[i,3])
    states <- as.character(df_noqs[i,4:ncol(df_noqs)])
    unique_states <- unique(states)
    rc_i <- length(unique_states)
    assert({score_i >= rc_i - 1})
    is_compat <- (score_i == (rc_i - 1))
    if (!is_compat || return_all_chars) {
      ids <- c(ids, df[i, 1])
      nms <- c(nms, df[i, 2])
      rcs <- c(rcs, rc_i)
      scores <- c(scores, score_i)
      xtrachange <- c(xtrachange, score_i - rc_i + 1)
      if (is_weighted ) weights <- c(weights, df[i,3])
    }
  }
  if (!is_weighted) ret <- (data.frame(id=ids, feature=nms, rc=rcs, score=scores, extra_changes=xtrachange))
  else ret <- (data.frame(id=ids, feature=nms, weight=weights, rc=rcs, score=scores, extra_changes=xtrachange))
  
  list(ps_score=ps_score, df=ret)
}


findEnforcingChars <- function(tree, df) {
  assert(!is.rooted(tree))
  if (!is.binary(tree)) {
    return (data.frame()) # If non binary tree, then dont do this function (should probably support in the future)
  }
  edge <- makeEdges(tree) #data.frame(tree$edge, edge_num=1:nrow(tree$edge))
  non_leaf_edges <- edge[edge$edge_num != ' ',]#edge[edge[,2] %in% edge[,1],]
  df_noqs <- replaceQsWithNums(df)
  res = list()
  edge_ids <- c()
  char_ids <- c()
  char_names <- c()
  for (idx in 1:nrow(non_leaf_edges)) {
    collapsed_tree <- collapseEdge(tree, non_leaf_edges[idx,1], non_leaf_edges[idx,2])
    enforcing_ids <- c()
    enforcing_names <- c()
    for (i in 1:nrow(df)) {
      alignment_i = buildPhyDat(df[i,]) # note: this replaces ?'s so no need to worry
      score_i =  parsimony(tree, alignment_i)
      score_i2 =  parsimony(collapsed_tree, alignment_i)
      #if (df[i,1] == 'p16')browser()
      #if (non_leaf_edges[idx,3] == 21 && df[i,1] == 'p19') browser ()
      if (score_i2 > score_i) {
        enforcing_ids <- c(enforcing_ids, df[i,1])
        enforcing_names <- c(enforcing_names, df[i,2])
      }
    }
    res[[idx]] <- enforcing_ids
    if (length(enforcing_ids) > 0) {
      edge_ids <- c(edge_ids, rep(non_leaf_edges[idx,3], length(enforcing_ids)))
      char_ids <- c(char_ids, enforcing_ids)
      char_names <- c(char_names, enforcing_names)
    } else {
      warning( " FOR SOME REASON AN EDGE HAS NO ENFORCING CHARACTERS")
      #assert ({FALSE}) # probably you called this function with a rooted tree if it enters here. (should call it on unrooted tree)
    }
    
    

    
  }
  # list(enforcing_chars=data.frame(edge_id=edge_ids, char_id=char_ids, char_name=char_names),
  #      edges = edge)
  data.frame(edge_id=edge_ids, char_id=char_ids, char_name=char_names)
}

# http://blog.phytools.org/2016/08/resolving-one-or-more-multifurcations.html
resolveNode<-function(tree,node){
  dd<-Children(tree,node)
  if(length(dd)>2){
    EL<-!is.null(tree$edge.length)
    if(!EL) tree<-compute.brlen(tree)
    n<-length(dd)
    tt<-lapply(allTrees(n,TRUE,dd),untangle,"read.tree")
    ROOT<-node==(Ntip(tree)+1)
    SPL<-if(!ROOT) splitTree(tree,split=list(node=node,
                                             bp=tree$edge.length[which(tree$edge[,2]==node)])) else
                                               list(NULL,tree)
    KIDS<-Children(SPL[[2]],SPL[[2]]$edge[1,1])
    KIDS<-setNames(KIDS,dd)[KIDS>Ntip(SPL[[2]])]
    SUBS<-list()
    if(length(KIDS)>0)
      for(i in 1:length(KIDS)) 
        SUBS[[i]]<-extract.clade(SPL[[2]],KIDS[i])
    obj<-list()
    for(i in 1:length(tt)){
      tt[[i]]$edge.length<-rep(0,nrow(tt[[i]]$edge))
      for(j in 1:Ntip(tt[[i]]))
        tt[[i]]$edge.length[which(tt[[i]]$edge[,2]==j)]<-
          tree$edge.length[which(tree$edge[,2]==
                                   as.numeric(tt[[i]]$tip.label[j]))]
      ind<-as.numeric(tt[[i]]$tip.label)<=Ntip(tree)
      tt[[i]]$tip.label[ind]<-
        tree$tip.label[as.numeric(tt[[i]]$tip.label[ind])]
      if(length(KIDS)>0)
        for(j in 1:length(KIDS))
          tt[[i]]<-bind.tree(tt[[i]],SUBS[[j]],
                             where=which(tt[[i]]$tip.label==
                                           names(KIDS)[j]))    
      obj[[i]]<-if(!ROOT) bind.tree(SPL[[1]],tt[[i]],
                                    where=which(SPL[[1]]$tip.label=="NA")) else
                                      tt[[i]]
      if(!EL) obj[[i]]$edge.length<-NULL
    }
    class(obj)<-"multiPhylo"
  } else obj<-tree
  obj
}

# http://blog.phytools.org/2016/08/resolving-one-or-more-multifurcations.html
resolveAllNodesForRooted<-function(tree){
  foo<-function(node,tree) length(Children(tree,node))
  nodes<-1:tree$Nnode+Ntip(tree) ## all nodes
  nodes<-nodes[sapply(1:tree$Nnode+Ntip(tree),foo,
                      tree=tree)>2]
  for(i in 1:length(nodes)){
    if(i==1) obj<-resolveNode(tree,nodes[i])
    else {
      for(j in 1:length(obj)){
        MM<-matchNodes(tree,obj[[j]])
        NODE<-MM[which(MM[,1]==nodes[i]),2]
        if(j==1) tmp<-resolveNode(obj[[j]],NODE)
        else tmp<-c(tmp,resolveNode(obj[[j]],NODE))
      }
      obj<-tmp
    }
  }
  obj
}

resolveAllNodesForUnrooted <- function(tree) {
  trees = resolveAllNodesForRooted(tree)
  trees = unroot.multiPhylo(trees)
  res = list()
  for (i in 1:length(trees)) {
    tree_i = trees[[i]]
    assert(!is.rooted(tree_i))
    found_tree=FALSE
    for (j in names(res)) {
      tree_j = trees[[as.integer(j)]]
      is_equal = all.equal(tree_i, tree_j, use.edge.length =FALSE)
      if (is_equal) {
        found_tree = TRUE
        break
      }
    }
    if (!found_tree) {
      res[[as.character(i)]] = tree_i
    }
  }
  class(res) = 'multiPhylo'
  res
}


collapseEdge <- function(tree, node1, node2) {
  tree2 <- tree
  tree2$edge <- tree$edge[!(tree$edge[,1] == node1 & tree$edge[,2] == node2),]
  tree2$edge[tree2$edge[,1]==node2,1] = node1
  tree2$Nnode = tree2$Nnode - 1
  #tree2$node.label <- rep(1, tree2$Nnode)
  unodes <- unique(c(tree2$edge[,1], tree2$edge[,2]))
  unodes <- unodes[order(unodes)]
  for (idx in 1:nrow(tree2$edge)) {
    tree2$edge[idx, 1] = which(unodes == tree2$edge[idx, 1])
    tree2$edge[idx, 2] = which(unodes == tree2$edge[idx, 2])
  }
  tree2
}

findCharsSupportingClade <- function(checkboxSelection, data) {
  idxes = c()
  data_ <- replaceQsWithNums(data)
  for (i in 1:nrow(data_)) {
    row = data_[i,4:ncol(data_)]
    nms = names(row) %in% checkboxSelection
    row = as.character(unlist(row))
    assert({all(row != '?')})
    states = row[nms]
    if (length(unique(states)) > 1) next
    unique_state = unique(states)
    if (sum(row == unique_state) == length(checkboxSelection)) { # Only occurs here
      idxes <- c(idxes, i)
    }
  }
  data[idxes,]
}

findCharsIncompatOnAnyTree <- function(trees, df, is_weighted, do_names=FALSE, names=NULL) {
  if (!do_names) assert(is.null(names))
  else {
    if (is.null(names)) names = 1:length(trees$trees)
    else assert({length(names)==length(trees$trees)})
  }
  ids <- c()
  nms <- c()
  if (is_weighted) weights <- c()
  cnts <- c()
  if (do_names) trees_incompat=list()
  
  for (i in 1:length(trees$trees)) {
    incompat_chars <- findIncompatChars(trees$trees[[i]], df, is_weighted)$df
    if (nrow(incompat_chars) > 0) {
      for (j in 1:nrow(incompat_chars)) {
        id <- incompat_chars[j,1]
        nm <- incompat_chars[j,2]
        wt <- incompat_chars[j,3]
        if (id %in% ids) {
          idx <- which(ids == id)
          cnts[idx] <- cnts[idx] + 1
          if (do_names) trees_incompat[[idx]] = c(trees_incompat[[idx]], names[i])
        }
        else {
          ids <- c(ids, id)
          nms <- c(nms, nm)
          cnts <- c(cnts, 1)
          if (is_weighted) weights <- c(weights, wt)
          if (do_names) trees_incompat[[length(trees_incompat)+1]] = names[i]
        }
      }
    }
  }
  if (is_weighted) res <- data.frame(id=ids, feature=nms, weight=weights, count=cnts)
  else res <- data.frame(id=ids, feature=nms, count=cnts)
  if (do_names) {
    res$names = unlist(lapply(X=trees_incompat, FUN=function(x) paste0(x, collapse=', ')))
  }
  
  return(res)
}



addButtonsToTable <- function (df, label, table_id, id_col) {
  if (nrow(df) == 0) return(df)
  buttons <- character(nrow(df))
  for (i in 1:nrow(df)) {
    buttons[i] <- paste(as.character(actionButton(paste0(table_id, "_select_", df[[id_col]][i]), label = label, onclick = 'Shiny.onInputChange(\"table_button\",  this.id)'))
    )
  }
  
  df <- data.frame(Select = buttons, df)
}



annotateTree <- function (tree, df, character) {
  assert({is.rooted(tree)})
  idx = which(df$id == character)
  df_ <- replaceQsWithNums(df)
  states <- df_[idx,4:ncol(df_)]
  ordering = unique(as.character(states))
  ordering = ordering[order(ordering)]
  states_in_order <- c()
  for (name in tree$tip.label) {
    states_in_order <- c(states_in_order, which(ordering==states[[name]]))
  }
  res = asr_max_parsimony(tree, states_in_order)
  #browser()
  res=res$ancestral_likelihoods
  final_res = c()
  for (state in states_in_order) final_res <- c(final_res, ordering[state])
  for (i in 1:nrow(res)) {
    states =  which(res[i,] > 0)#which(res[i,]==max(res[i,]))
    has_multiple = length(states) > 1
    if (!has_multiple) {
      state_here = ordering[states]
    }
    else {
      state_here = '{'
      for (q in 1:length(states)) {
        state_here <- paste0(state_here, ordering[states[q]])
        if (q != length(states)) state_here <- paste0(state_here, ',')
      }
      state_here = paste0(state_here, '}')
    }
    final_res <- c(final_res, state_here)
  }
  
  #alignment_i = buildPhyDat(df[idx,])
  

  # Since the tree was rooted, it had 2n-1 (rather than 2n-2) nodes - and so final_res has 2n-1 items
  # A bit post hoc, but now match with bipartitions. Since root doesn't matter for this, we'll end up with 2n-2 items.
  
  edge = makeEdges(tree)
  edge$label =NA
  for (i in 1:nrow(edge)) {
    edge$label[i] = final_res[edge$node[i]]
  }

  edge
}



makeTreeplot <- function (orig_tree, 
                          root, 
                          do_edge_label, 
                          node_states=NULL, 
                          enforcing_chars=NULL,
                          show_root_at_left=FALSE,
                          do_slanted=FALSE){
  assert(!is.null(root)) # not sure we allow this - if do, just double check works for everything
  if (show_root_at_left) {
    assert ({length(root)==1})
  }
  if (do_slanted) {
    assert({!show_root_at_left})
    assert({is.null(enforcing_chars)})
    assert({is.null(node_states)})
    assert({!do_edge_label})
  }
  tree = root(orig_tree, root, resolve.root=TRUE)
  orig_tree=tree
  if (show_root_at_left) {
    tree = drop.tip(tree, tip = root)
    tree$root.edge=1
  }
  tree$edge.length = rep(1,nrow(tree$edge))
  if (do_slanted) {
    print(tree)
    p1 <- ggtree(tree, layout = 'slanted')
    return(p1)
  }
  if (show_root_at_left) p1 <- ggtree(tree) + geom_rootedge()
  else p1 <- ggtree(tree)
  p1$data$label[!is.na(p1$data$label)] <- (paste0(' ', p1$data$label))[!is.na(p1$data$label)]

  if (!is.null(node_states)) {
    # So node_states has the states by bipartition basically.
    # We need to turn this into a vector in the order of 'node': basically the label at 'node'.
    # This is not that hard.
    if (show_root_at_left) {
      root_id = which(orig_tree$tip.label == root)
      root_state=node_states$label[node_states$node == root_id]
      # Now save the state below the state above the root.
      root_parent = node_states$parent[node_states$node == root_id]
      assert({!(root_parent %in% node_states$node)})
      below_root_parents = node_states[node_states$parent == root_parent,]
      assert({nrow(below_root_parents) == 2})
      state_below_root_parent = below_root_parents$label[below_root_parents$node != root_id]
      
      node_states = cbind(tree$edge, data.frame(edge_num=node_states$edge_num[2:(nrow(node_states)-1)], label=node_states$label[2:(nrow(node_states)-1)]))
      names(node_states) = c('parent', 'node', 'edge_num', 'label')
    }
    vec = c()
    node_ids = unique(c(node_states$parent, node_states$node))
    node_ids = node_ids[order(node_ids)]
    assert ({length(node_ids) == nrow(node_states) + 1}) # believe this is based on it being rooted, which is currenltly an assertion
    for (i in node_ids) {
      if (!(i %in% node_states$node)) {
        # This had better be the root. Let's check. (But if we've removed the root by showing on left, dont need to do this)
        if (!show_root_at_left) {
          rows_where_this_is_parent = node_states[node_states$parent == i,]
          assert({nrow(rows_where_this_is_parent) == 2})
          assert({length(root) == 1}) # if this is not the case, would have to recursively check that one side has all the levaes in root...leave for future work...not sure would be an actual issue though.
          labsh = tree$tip.label[rows_where_this_is_parent$node]
          assert({any(labsh==root)}) # root must be one of these! the other is the rest of the tree. again, only works if root is a leaf, otherwise need to check recursively.
          vec <- c(vec, '')
        }
        else {
          vec <- c(vec, state_below_root_parent)
        }
      }
      else {
        row_id = which(node_states$node == i)
        annot = node_states[row_id, 'label']
        vec <- c(vec, annot)
      }
    }
    node <- data.frame(as.data.frame(p1$data[,c('parent', 'node')]), state=vec)
    colnames(node)=c('parent','node','state')
    is_leaf = !(node[,2] %in% node[,1])
    node_leaf = node
    node_leaf$state[!is_leaf] = ''
    p1 <- p1  %<+% node_leaf + geom_text(aes(x=x, label=state), nudge_y = 0.25, colour = 'red')
    
    node <- data.frame(as.data.frame(p1$data[,c('parent', 'node')]), state=vec)
    colnames(node)=c('parent','node','state2')
    node_nonleaf =  node
    node_nonleaf$state2[is_leaf] = ''
    p1 <- p1  %<+% node_nonleaf + geom_text(aes(x=x, label=state2), nudge_x = 0.15, colour = 'red')
  }
  if (do_edge_label) {
    edge <- makeEdges(orig_tree) # invariant no matter root
    if (show_root_at_left) edge = cbind(tree$edge, data.frame(edge_num=edge$edge_num[2:(nrow(edge)-1)]))
    names(edge) <- c('parent', 'node', 'edge_num')
    edge2=edge
    edge2$edge_num[edge2$edge_num != ' ']=paste0('(',edge2$edge_num[edge2$edge_num != ' '],')')
    p1 <- p1  %<+% edge2 + geom_text(aes(x=branch, label=edge_num), nudge_y = -0.35, size=3)
  }
  else edge=NULL
  if (!is.null(enforcing_chars)) {
    if (is.null(edge)) edge = makeEdges(orig_tree) # invariant no matter root - so the edge ids are guaranteed to match up with the enforcing_chars
    cnts <- count(enforcing_chars, edge_id)
    joined = left_join(edge, cnts, by=c('edge_num'='edge_id'))
    non_leaf_edges <- edge[edge$edge_num != ' ',]
    is_non_leaf = joined$edge_num %in% non_leaf_edges$edge_num
    joined$n[!is_non_leaf] = ' '
    #joined$n[is_non_leaf & is.na(joined$n)] = 0
    assert({!all(is.na(joined))})
    joined = joined[,-3]
    colnames(joined)=c("parent", "node", "num_support")

    p1 <- p1  %<+% joined + geom_text(aes(x=branch, label=num_support), nudge_y = .25, colour = 'blue')
  }
  
  p3 <- ggplotly(p1) %>% layout(margin=list(l=80,r=80,b=0,t=0,pad=0), height=400, width=800)
  p3 <- p3 %>% add_trace(x=p1$data$x, y=p1$data$y, text=p1$data$label, mode='text', cliponaxis=FALSE, textposition='right')
  if (show_root_at_left) {
    x=-1
    y=p1$data$y[p1$data$x==0]
    p3 <- p3 %>% add_trace(x=x,y=y,text=paste0(root, ' '), mode='text', cliponaxis=FALSE,textposition='left')
    if (!is.null(node_states)) {
      p3 <- p3 %>% add_trace(x=x,y=y+0.25,text=root_state, mode='text', cliponaxis=FALSE,textposition='right', textfont=list(color='red'))
    }
  }
  p3 <- p3 %>% layout(showlegend = FALSE)
  p3
}

# Super special and important function - because edge ids are assigned by bipartition, not internal node labelings. So doesn't matter where root is.
# But still remember: the interanl nodes of tree$edge change depending on root
# but the edge_num is invariant reagardless of this. So, for many downstream applications, can use edge number to reference things regardless of display or root location.
makeEdges <- function(tree) {
  splits <- prop.part(tree)
  labels_of_splits = attr(splits, 'labels')
  labels_of_tips = tree$tip.label
  num_leaves = length(tree$tip.label)
  result = list()
  label_that_must_be_there = which(labels_of_splits == labels_of_tips[1])
  sorting_criterion = c()
  
  newsplits = list()
  cnt=1
  for (i in 1:length(splits)) { # get rid of trivial splits that show up for some reason
    if (length(splits[[i]]) %in% c(num_leaves, num_leaves-1, 1)) next
    else newsplits[[cnt]] = splits[[i]]
    cnt = cnt + 1
  }
  splits=newsplits
  for (i in 1:length(splits)) {
    splt <- splits[[i]]
    if (!(label_that_must_be_there %in% splt)) {
      splt <-  (1:num_leaves)[!((1:num_leaves) %in% splt)]
    }
    assert({label_that_must_be_there %in% splt})
    ordered = c()
    for (x in labels_of_tips) {
      id_in_splits = which(labels_of_splits == x)
      if (id_in_splits %in% splt) ordered <- c(ordered, id_in_splits)
    }
    assert({all(ordered[order(ordered)] == splt[order(splt)])})
    result[[i]] = ordered
    sorting_criterion = c(sorting_criterion,paste0(ordered,collapse=';'))
  }
  ord = order(sorting_criterion)
  splits=list()
  for (i in 1:length(ord)) {
    j = ord[i]
    splits[[i]] = result[[j]]
  }
  splts=splits

  
  edge <- data.frame(tree$edge, edge_num=NA) # this will vary depending on the rooting of tree; h/v, we will add in the numbers so that it is consistent with the splits which are root invariant
  names(edge) = c('parent', 'node', 'edge_num')
  assert({num_leaves-3==length(splts)}) # splits additionally has the entire leaveset as a bipartition
  iteration = 1
  unreduced = 1:num_leaves
  mapping=list()
  while (sum(!is.na(edge$edge_num)) != num_leaves - 3) {
    for (parent in unique(edge$parent)) {
      sub = edge[edge$parent==parent,]
      assert({nrow(sub) %in% c(2,3)})
      if (sum(sub$node %in% unreduced) == 2) {
        children = sub$node[sub$node %in% unreduced]
        if (iteration > 1) {
          newchildren = c()
          for (x in children) {
            if (x <= num_leaves) newchildren <- c(newchildren, x)
            else {
              newchildren = c(newchildren, mapping[[as.character(x)]])
              mapping[[as.character(x)]] = NULL
              unreduced=unreduced[unreduced != x]
            }
            
          }
          children=newchildren
        }
        
        children = children[order(children)]
        antichildren = (1:num_leaves)[!((1:num_leaves) %in% children)]
        antichildren=antichildren[order(antichildren)]
        found=FALSE
        for (jj in 1:length(splts)) {
          if ((length(splts[[jj]]) == length(children) && all(children%in% splts[[jj]])) || (length(splts[[jj]]) == length(antichildren) && all(antichildren%in% splts[[jj]]))) {
            found=TRUE
            break
          }
        }
        assert({found})
        if (nrow(sub) == 3 ) clade_num = sub$node[!(sub$node %in% unreduced)]
        else clade_num = parent
        edge$edge_num[edge$node == clade_num] = jj
        mapping[[as.character(clade_num)]] = children
        unreduced = unreduced[!(unreduced %in% children)]
        unreduced <- c(unreduced, clade_num)
      }
    }
    iteration = iteration + 1
  }
  edge$edge_num[is.na(edge$edge_num)] = ' ' 
  colnames(edge)=c("parent", "node", "edge_num")
  edge
}
# makeEdges(tree)
# makeEdges(root(tree, 'Albanian'))
# makeEdges(root(tree, c('Italic', 'Celtic')))




