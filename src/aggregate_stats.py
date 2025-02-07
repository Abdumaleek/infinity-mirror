import os
import numpy as np
import pandas as pd
from scipy.stats import entropy
from scipy.spatial import distance

import src.graph_comparison

def compute_mono_stat(dataset, model, stat, agg):
    def _convert(agg):
        for trial in agg.keys():
            for gen in agg[trial].keys():
                agg[trial][gen] = np.asarray(agg[trial][gen])
        return agg

    def _unwrap(agg, model):
        for trial in agg.keys():
            for gen in agg[trial].keys():
                if agg[trial][gen] != {}:
                    agg[trial][gen] = list(agg[trial][gen].values())
                else:
                    agg[trial][gen] = []
        return agg

    def _normalize_graphlets(agg):
        for trial in agg.keys():
            for gen in agg[trial].keys():
                if agg[trial][gen] != {}:
                    graphlets = agg[trial][gen]
                    total = sum(graphlets.values())

                    for idx, count in graphlets.items():
                        if total != 0:
                            graphlets[idx] = count/total
                        else:
                            graphlets[idx] = 0

                    agg[trial][gen] = graphlets
        return agg

    if stat == 'b_matrix':
        agg = _convert(agg)
        rows = portrait_js(dataset, model, agg)
    elif stat == 'degree_dist':
        rows = degree_js(dataset, model, agg)
    elif stat == 'laplacian_eigenvalues':
        agg = _convert(agg)
        rows = lambda_dist(dataset, model, agg)
    elif stat == 'netlsd':
        pass #TODO
    elif stat == 'pagerank':
        agg = _unwrap(agg, model)
        rows = pagerank_js(dataset, model, agg)
    elif stat == 'pgd_graphlet_counts':
        agg = _normalize_graphlets(agg)
        rows = pgd_rgfd(dataset, model, agg)
    elif stat == 'average_path_length':
        rows = average_path_length(dataset, model, agg)
    elif stat == 'average_clustering':
        rows = average_clustering(dataset, model, agg)
    elif stat == 'apl_cc':
        rows = apl_cc(dataset, model, agg)
    else:
        raise NotImplementedError
    return pd.DataFrame(rows)

def compute_bi_stat(dataset, model, stat, agg1, agg2):
    if stat == 'apl_cc':
        rows = apl_cc(dataset, model, agg1, agg2)
    else:
        raise NotImplementedError
    return pd.DataFrame(rows)

def apl_cc(dataset, model, agg1, agg2):
    rows = {'dataset': [], 'model': [], 'trial': [], 'gen': [], 'clu': [], 'pl': []}

    for trial in agg1.keys():
        for gen in agg1[trial].keys():
            clu = agg1[trial][gen]
            pl = agg2[trial][gen]

            rows['dataset'].append(dataset)
            rows['model'].append(model)
            rows['trial'].append(trial)
            rows['gen'].append(gen)
            rows['clu'].append(clu)
            rows['pl'].append(pl)
    return rows

def average_clustering(dataset, model, agg):
    rows = {'dataset': [], 'model': [], 'trial': [], 'gen': [], 'avg_clustering': []}

    for trial in agg.keys():
        for gen in agg[trial].keys():
            avg_clustering = agg[trial][gen]

            rows['dataset'].append(dataset)
            rows['model'].append(model)
            rows['trial'].append(trial)
            rows['gen'].append(gen)
            rows['avg_clustering'].append(avg_clustering)
    return rows

def average_path_length(dataset, model, agg):
    rows = {'dataset': [], 'model': [], 'trial': [], 'gen': [], 'avg_pl': []}

    for trial in agg.keys():
        for gen in agg[trial].keys():
            avg_pl = agg[trial][gen]

            rows['dataset'].append(dataset)
            rows['model'].append(model)
            rows['trial'].append(trial)
            rows['gen'].append(gen)
            rows['avg_pl'].append(avg_pl)
    return rows

def degree_js(dataset, model, agg):
    rows = {'dataset': [], 'model': [], 'trial': [], 'gen': [], 'degree_js': []}

    for trial in agg.keys():
        dist1 = agg[trial][0]

        for gen in agg[trial].keys():
            if gen != 0:
                dist2 = agg[trial][gen]
                union = set(dist1.keys()) | set(dist2.keys())

                for key in union:
                    dist1[key] = dist1.get(key, 0)
                    dist2[key] = dist1.get(key, 0)

                deg1 = np.asarray(list(dist1.values())) + 0.00001
                deg2 = np.asarray(list(dist2.values())) + 0.00001

                deg_js = distance.jensenshannon(deg1, deg2, base=2.0)

                rows['dataset'].append(dataset)
                rows['model'].append(model)
                rows['trial'].append(trial)
                rows['gen'].append(gen)
                rows['degree_js'].append(deg_js)
    return rows

def lambda_dist(dataset, model, agg):
    rows = {'dataset': [], 'model': [], 'trial': [], 'gen': [], 'lambda_dist': []}

    for trial in agg.keys():
        u = agg[trial][0]

        for gen in agg[trial].keys():
            if gen != 0:
                v = agg[trial][gen]
                m = min([u.shape[0], v.shape[0]])
                L = np.sqrt(np.sum((u[:m] - v[:m])**2))

                rows['dataset'].append(dataset)
                rows['model'].append(model)
                rows['trial'].append(trial)
                rows['gen'].append(gen)
                rows['lambda_dist'].append(L)
    return rows

#TODO
def netlsd(dataset, model, agg):
    rows = {'dataset': [], 'model': [], 'trial': [], 'gen': [], 'netlsd': []}
    raise NotImplementedError

def pagerank_js(dataset, model, agg):
    rows = {'dataset': [], 'model': [], 'trial': [], 'gen': [], 'pagerank_js': []}

    for trial in agg.keys():
        pr1 = agg[trial][0]

        for gen in agg[trial].keys():
            if gen != 0:
                pr2 = agg[trial][gen]
                try:
                    hist_upperbound = max(max(pr1), max(pr2))
                except ValueError as e:
                    continue

                g1_hist = np.histogram(pr1, range=(0, hist_upperbound), bins=100)[0] + 0.00001
                g2_hist = np.histogram(pr2, range=(0, hist_upperbound), bins=100)[0] + 0.00001
                pr_js = distance.jensenshannon(g1_hist, g2_hist, base=2.0)

                rows['dataset'].append(dataset)
                rows['model'].append(model)
                rows['trial'].append(trial)
                rows['gen'].append(gen)
                rows['pagerank_js'].append(pr_js)
    return rows

def pgd_rgfd(dataset, model, agg):
    rows = {'dataset': [], 'model': [], 'trial': [], 'gen': [], 'pgd_rgfd': []}

    for trial in agg.keys():
        for gen in agg[trial].keys():
            rgfd = 0
            first = agg[trial][0]

            if gen != 0:
                curr = agg[trial][gen]

                for graphlet in curr.keys():
                    rgfd += np.abs(first[graphlet] - curr[graphlet])

                rows['dataset'].append(dataset)
                rows['model'].append(model)
                rows['trial'].append(trial)
                rows['gen'].append(gen)
                rows['pgd_rgfd'].append(rgfd)
    return rows

def portrait_js(dataset, model, agg):
    def _pad_portraits_to_same_size(B1, B2):
        ns, ms = B1.shape
        nl, ml = B2.shape

        lastcol1 = max(np.nonzero(B1)[1])
        lastcol2 = max(np.nonzero(B2)[1])
        lastcol = max(lastcol1, lastcol2)
        B1 = B1[:, :lastcol + 1]
        B2 = B2[:, :lastcol + 1]

        BigB1 = np.zeros((max(ns, nl), lastcol + 1))
        BigB2 = np.zeros((max(ns, nl), lastcol + 1))

        BigB1[:B1.shape[0], :B1.shape[1]] = B1
        BigB2[:B2.shape[0], :B2.shape[1]] = B2

        return BigB1, BigB2

    def _calculate_portrait_divergence(BG, BH):
        BG, BH = _pad_portraits_to_same_size(BG, BH)

        L, K = BG.shape
        V = np.tile(np.arange(K), (L, 1))

        XG = BG * V / (BG * V).sum()
        XH = BH * V / (BH * V).sum()

        P = XG.ravel()
        Q = XH.ravel()

        M = 0.55 * (P + Q)
        KLDpm = entropy(P, M, base=2)
        KLDqm = entropy(Q, M, base=2)
        JSDpq = 0.5 * (KLDpm + KLDqm)

        return JSDpq

    rows = {'dataset': [], 'model': [], 'trial': [], 'gen': [], 'portrait_js': []}

    for trial in agg.keys():
        for gen in agg[trial].keys():
            if gen != 0:
                d = _calculate_portrait_divergence(agg[trial][0], agg[trial][gen])

                rows['dataset'].append(dataset)
                rows['model'].append(model)
                rows['trial'].append(trial)
                rows['gen'].append(gen)
                rows['portrait_js'].append(d)
    return rows
