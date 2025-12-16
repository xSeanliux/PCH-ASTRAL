import argparse
import pandas as pd
from Bio import Phylo

def process_tree(mapping_path, tree_path, format='newick', outgroup=None):
    """
    Process a tree by rooting it with outgroup and renaming nodes based on language families.

    Args:
        mapping_path (str): Path to a TSV file with columns 'Language' and 'Family'.
        tree_path (str): Path to a Newick or NEXUS tree file.
        format (str): Format of the tree file (default is 'newick').
        outgroup (list of str): List of languages to use as outgroup for rooting the tree.

    Returns:
        Phylo.BaseTree.Tree: The processed tree.
    """
    tree = Phylo.read(tree_path, format)
    
    if outgroup:
        tree.root_with_outgroup(outgroup)
    
    df = pd.read_csv(mapping_path, sep='\t')
    language_to_family = dict(zip(df['Language'], df['Family']))
    
    for clade in tree.get_terminals():
        assert clade.name in language_to_family, f"{clade.name} not specified in {mapping_path}."
        setattr(clade, 'family', language_to_family[clade.name].upper())
        setattr(clade, 'count', 1)
    
    def collapse_uniform_family_node(node):
        for child in node.clades:
            collapse_uniform_family_node(child)

        if not node.is_terminal():
            families = [getattr(child, 'family', None) for child in node.clades]
            print(families)
            if len(set(families)) == 1 and None not in families:
                setattr(node, 'count', sum([child.count for child in node.clades]))
                setattr(node, 'name', f"{families[0]} ({node.count})")
                setattr(node, 'family', families[0])
                node.clades = []
    
    collapse_uniform_family_node(tree.root)
    
    return tree

def main():
    parser = argparse.ArgumentParser(
        description="Process a phylogenetic tree and rename nodes based on language families.",
        epilog="Example usage:\n  python process_tree.py languages.tsv language_tree.newick --output processed_tree.newick"
    )
    
    parser.add_argument('mapping_path', type=str, help="Path to the TSV file containing language to family mappings.")
    parser.add_argument('tree_path', type=str, help="Path to the tree file (Newick or NEXUS format).")
    parser.add_argument('--format', type=str, default='newick', choices=['newick', 'nexus'], help="Format of the tree file (default: 'newick').")
    parser.add_argument('--outgroup', type=str, nargs='*', help="List of languages to root the tree with (optional).")
    parser.add_argument('--output', type=str, help="Path to save the resultant tree in Newick format (optional).")
    
    args = parser.parse_args()
    
    tree = process_tree(args.mapping_path, args.tree_path, format=args.format, outgroup=args.outgroup)
    
    if args.output:
        Phylo.write(tree, args.output, format='newick', plain=True)
        print(f"Processed tree saved to {args.output}")
    
    Phylo.draw_ascii(tree)

if __name__ == "__main__":
    main()
