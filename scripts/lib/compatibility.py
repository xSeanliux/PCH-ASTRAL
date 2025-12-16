from scripts.lib.utils import get_values
import numpy as np
from Bio import Phylo

class MonoCharacterCompatibilty:
    """
    Given a csv of monomorphic characters, utilities to check if a given tree is compatible with the character set. 

    Notes: 
    1. Characters must be supplied in the format given in (https://github.com/marccanby/LingPhyloSimulator/blob/main/example/ie_dataset.csv).
    2. Character set must be monomorphic. Polymorphic compatibility is TODO.
    3. If you are testing for quartet compatibility, use the quartet_compatible function (it is much faster). 
    """
    def __init__(self, chars_csv_file):
        names, values = get_values(chars_csv_file)
        values = np.asarray(values)
        self.names = names
        self.values = values
        try:
            for v in values:
                for x in v:
                    assert(len(x) == 1)
        except:
            print("Warning: Characters given are not monomorphic.")
        self.name_to_id = {
            n: i for i, n in enumerate(names)
        }
    def quartet_compatible(self, a: str, b: str, c: str, d: str):
        """
        a,b,c,d: names representing ab|cd
        returns if (ab|cd) is compatible with all characters in the given character set 
        equivalently, if (ab|cd) does not contradict any character, that is, 
        no character supports (ac|bd) or (ad|bc).
        """
        l = [a, b, c, d]
        ids = list(map(
            lambda x: self.name_to_id[x],
            l
        ))
        relevant_columns = self.values[:, ids, :]
        column_equals = np.array([
            relevant_columns[:, i] == relevant_columns[:, j]
            for i in range(2) 
            for j in range(2, 4)
        ]) 
        not_compatible = ((column_equals[0] & column_equals[3]) | (column_equals[1] & column_equals[2])) & (relevant_columns[:, 0] != relevant_columns[:, 1])
        # not_compatible_indices, _ = np.where(not_compatible == True)
        return not not_compatible.any()

    def tree_compatible(self, tree: Phylo.BaseTree.TreeMixin):
        """
        Check if the tree is compatible with the given character set. 
        Compatibility is defined with parsimony: 
        """
        raise NotImplementedError
