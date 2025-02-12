from collections import Counter
import os
import sys; sys.path.append('./../../')
import pickle
import numpy as np
import pandas as pd
import networkx as nx
import scipy.stats as st
import multiprocessing as mp
from pathlib import Path
from src.Tree import TreeNode
from src.utils import load_pickle
from src.graph_stats import GraphStats
from src.graph_comparison import GraphPairCompare

def init(filename: str, gname: str = '', reindex_nodes: bool = False, first_label: int = 0, take_lcc: bool = True) -> nx.Graph:
    """
    :param filename: path to input file
    :param gname: name of the graph
    """
    possible_extensions = ['.g', '.gexf', '.gml', '.txt', '.mat']
    filename = filename
    path = Path(filename)
    #assert check_file_exists(path), f'Path: "{self.path}" does not exist'

    if gname == '':
        gname = path.stem

    graph: nx.Graph = read(path, gname)
    graph: nx.Graph = preprocess(graph, reindex_nodes=reindex_nodes, first_label=first_label, take_lcc=take_lcc)
    assert graph.name != '', 'Graph name is empty'
    return graph

def read(path: str, gname: str) -> nx.Graph:
    """
    Reads the graph based on its extension
    returns the largest connected component
    :return:
    """
    #CP.print_blue(f'Reading "{self.gname}" from "{self.path}"')
    extension = path.suffix
    #assert extension in possible_extensions, f'Invalid extension "{extension}", supported extensions: {possible_extensions}'

    str_path = str(path)

    if extension in ('.g', '.txt'):
        graph: nx.Graph = nx.read_edgelist(str_path, nodetype=int)

    elif extension == '.gml':
        graph: nx.Graph = nx.read_gml(str_path)

    elif extension == '.gexf':
        graph: nx.Graph = nx.read_gexf(str_path)

    elif extension == '.mat':
        mat = np.loadtxt(fname=str_path, dtype=bool)
        graph: nx.Graph = nx.from_numpy_array(mat)
    else:
        raise (NotImplementedError, f'{extension} not supported')

    graph.name = gname
    return graph

def preprocess(graph: nx.Graph, reindex_nodes: bool, first_label: int = 0, take_lcc: bool = True) -> nx.Graph:
    """
    Preprocess the graph - taking the largest connected components, re-index nodes if needed
    :return:
    """
    #CP.print_none('Pre-processing graph....')
    #CP.print_none(f'Original graph "{self.gname}" n:{self.graph.order():,} '
    #              f'm:{self.graph.size():,} #components: {nx.number_connected_components(self.graph)}')

    if take_lcc and nx.number_connected_components(graph) > 1:
        ## Take the LCC
        component_sizes = [len(c) for c in sorted(nx.connected_components(graph), key=len, reverse=True)]

        #CP.print_none(f'Taking the largest component out of {len(component_sizes)} components: {component_sizes}')

        graph_lcc = nx.Graph(graph.subgraph(max(nx.connected_components(graph), key=len)))

        perc_nodes = graph_lcc.order() / graph.order() * 100
        perc_edges = graph_lcc.size() / graph.size() * 100
        #CP.print_orange(f'LCC has {print_float(perc_nodes)}% of nodes and {print_float(perc_edges)}% edges in the original graph')

        graph = graph_lcc

    selfloop_edges = list(nx.selfloop_edges(graph))
    if len(selfloop_edges) > 0:
        #CP.print_none(f'Removing {len(selfloop_edges)} self-loops')
        graph.remove_edges_from(selfloop_edges)  # remove self-loops

    if reindex_nodes:
        # re-index nodes, stores the old label in old_label
        graph = nx.convert_node_labels_to_integers(graph, first_label=first_label,
                                                        label_attribute='old_label')
        #CP.print_none(
        #    f'Re-indexing nodes to start from {first_label}, old labels are stored in node attr "old_label"')

    #CP.print_none(f'Pre-processed graph "{self.gname}" n:{self.graph.order():,} m:{self.graph.size():,}')
    return graph

def load_data(base_path, dataset, model, seq_flag, rob_flag):
    if model == 'GraphRNN':
        path = os.path.join(base_path, model, f'{dataset}_size10_ratio5')
        for subdir, dirs, files in os.walk(path):
            for filename in files:
                if '1000' in filename:
                    print(f'loading {subdir} {filename} ...', end='', flush=True)
                    pkl = load_pickle(os.path.join(subdir, filename))
                    print('done')
                    yield pkl, model
        return
    else:
        path = os.path.join(base_path, dataset, model)
        for subdir, dirs, files in os.walk(path):
            for filename in files[: 5]:
                if 'csv' not in filename:
                    # if 'seq' not in filename and 'rob' not in filename:
                    print(f'loading {subdir} {filename} ... ', end='', flush=True)
                    pkl = load_pickle(os.path.join(subdir, filename))
                    trial = filename.split('_')[2].strip('.pkl.gz')
                    print('done')
                    yield pkl, trial

def mkdir_output(path):
    if not os.path.isdir(path):
        try:
            os.mkdir(path)
        except OSError:
            print('ERROR: could not make directory {path} for some reason')
    return

def compute_graph_stats(root):
    print('computing GraphStats... ', end='', flush=True)
    if type(root) is list:
        graph_stats = [GraphStats(graph=g, run_id = 1) for g in root]
    else:
        graph_stats = [GraphStats(graph=node.graph, run_id=1) for node in [root] + list(root.descendants)]
    print('done')
    return graph_stats

def absolute(graph_stats):
    for gs in graph_stats[1:]:
        comparator = GraphPairCompare(graph_stats[0], gs)
        delta = comparator.deltacon0()
        yield delta

def sequential(graph_stats):
    prev = graph_stats[0]
    for curr in graph_stats[1:]:
        comparator = GraphPairCompare(prev, curr)
        delta = comparator.deltacon0()
        yield delta
        prev = curr

def absolute_delta(graph_stats):
    print('absolute... ', end='', flush=True)
    abs_delta = [x for x in absolute(graph_stats)]
    print('done')
    return abs_delta

def sequential_delta(graph_stats):
    print('sequential... ', end='', flush=True)
    seq_delta = [x for x in sequential(graph_stats)]
    print('done')
    return seq_delta

def length_chain(root):
    return len(root.descendants)

def flatten(L):
    return [item for sublist in L for item in sublist]

def compute_stats(delta):
    padding = max(len(l) for l in delta)
    for idx, l in enumerate(delta):
        while len(delta[idx]) < padding:
            delta[idx] += [np.NaN]
    mean = np.nanmean(delta, axis=0)
    ci = []
    for row in np.asarray(delta).T:
        ci.append(st.t.interval(0.95, len(row)-1, loc=np.mean(row), scale=st.sem(row)))
    return np.asarray(mean), np.asarray(ci)

def construct_table(abs_delta, seq_delta, model):
    abs_mean, abs_ci = compute_stats(abs_delta)
    seq_mean, seq_ci = compute_stats(seq_delta)
    gen = [x + 1 for x in range(len(abs_mean))]

    rows = {'model': model, 'gen': gen, 'abs_mean': abs_mean, 'abs-95%': abs_ci[:,0], 'abs+95%': abs_ci[:,1], 'seq_mean': seq_mean, 'seq-95%': seq_ci[:,0], 'seq+95%': seq_ci[:,1]}

    df = pd.DataFrame(rows)
    return df

def construct_full_table(abs_delta, seq_delta, model, trials):
    #abs_mean, abs_ci = compute_stats(abs_delta)
    #seq_mean, seq_ci = compute_stats(seq_delta)
    #gen = [x + 1 for x in range(len(abs_mean))]

    gen = []
    for t in trials:
        gen += [x + 1 for x in range(len(t))]

    rows = {'model': model, 'trial': flatten(trials), 'gen': gen, 'abs': abs_delta}#, 'seq': seq_delta}

    df = pd.DataFrame(rows)
    return df

def main():
    base_path = '/data/infinity-mirror'
    input_path = '/home/dgonza26/infinity-mirror/input'
    # dataset = 'flights'
    dataset = 'clique-ring-500-4'
    # models = ['CNRG', 'BUGGE']
    models = ['Kronecker']
    # models = ['GCN_AE', 'Linear_AE']
    #model = models[0]

    #output_path = os.path.join(base_path, dataset, models[0], 'jensen-shannon')
    #output_path = '/home/dgonza26/infinity-mirror/data/deltacon/'
    output_path = os.path.join(base_path, 'stats', 'deltacon')
    mkdir_output(output_path)

    for model in models:
        abs_delta = []
        seq_delta = []
        trials = []
        if model == 'GraphRNN':
            R = [root for root, model in load_data(base_path, dataset, model, True, True)]
            if dataset == 'clique-ring-500-4':
                g = nx.ring_of_cliques(500, 4)
            else:
                g = init(os.path.join(input_path, f'{dataset}.g'))
            roots = [[g] + list(r) for r in zip(*R)]
            for root in roots:
                graph_stats = compute_graph_stats(root)
                abs_delta.append(absolute_delta(graph_stats))
                seq_delta.append(sequential_delta(graph_stats))
        else:
            for root, trial in load_data(base_path, dataset, model, True, False):
                graph_stats = compute_graph_stats(root)
                trials.append([trial for _ in graph_stats[1:]])
                # try:
                #     assert root.children[0].stats['deltacon0'] is not None
                #     assert root.children[0].stats['deltacon0'] != {}
                # except Exception as e:
                    #abs_delta.append(absolute_delta(graph_stats))
                    #seq_delta.append(sequential_delta(graph_stats))
                abs_delta += absolute_delta(graph_stats)
                # else:
                #     abs_delta += [node.stats['deltacon0'] for node in root.descendants]
                #try:
                #    assert root.children[0].stats_seq['deltacon0'] is not None
                #except Exception as e:
                #    seq_delta += sequential_delta(graph_stats)
                #else:
                #    seq_delta += [node.stats_seq['deltacon0'] for node in root.descendants]

        df = construct_full_table(abs_delta, seq_delta, model, trials)
        df.to_csv(f'{output_path}/{dataset}_{model}_deltacon.csv', float_format='%.7f', sep='\t', index=False, na_rep='nan')
        print(f'wrote {output_path}/{dataset}_{model}_deltacon.csv')
        #df.to_csv(f'{output_path}/{dataset}_{model}_delta.csv', float_format='%.7f', sep='\t', index=False, na_rep='nan')

    return

main()
