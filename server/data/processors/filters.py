import logging
from collections import defaultdict
from typing import List
import numpy as np
import scipy.sparse as sparse
import data.models as models
from data.processors import Modifier
from data.processors.ranking import sid_to_nodes, build_edge_dict, node_to_sid

logger = logging.getLogger('data.graph.filters')


class BottomReplyToEdgeFilter(Modifier):
    def __init__(self, *args, top_edges=None, **kwargs):
        """
        Filters all edges except top edges for specific edge type
        :param args:
        :param top_edges: the number of top edges to keep for each node
        :param kwargs:
        """
        super().__init__(*args, **kwargs)
        self.top_edges = self.conf_getint('top_edges', top_edges)

        logger.debug(f'{self.__class__.__name__} initialised with '
                     f'top_edges={self.top_edges}')

    @classmethod
    def short_name(cls) -> str:
        return 'brtef'

    @classmethod
    def edge_type(cls) -> str:
        return "reply_to"

    def modify(self, graph_to_modify):
        filtered_edges = []
        edge_dict = build_edge_dict(graph_to_modify)
        for comment in graph_to_modify.comments:
            for j, split in enumerate(comment.splits):
                node_edges = edge_dict[node_to_sid(node=None, a=graph_to_modify.id2idx[comment.id], b=j)]
                print(node_edges)
                node_edges = sorted(node_edges, key=lambda e: e.wgts[self.__class__.edge_type()], reverse=True)[
                             :self.top_edges]
                for edge in node_edges:
                    if edge not in filtered_edges:
                        filtered_edges.append(edge)
        print(self.top_edges, len(filtered_edges))
        graph_to_modify.edges = filtered_edges

        return graph_to_modify


# todo: add bottom edge filters for other edge types


class SimilarityEdgeFilter(Modifier):
    def __init__(self, *args, threshold=None, **kwargs):
        """
        Removes all edges of the specific type below a threshold
        :param args:
        :threshold: value for edges to filter
        :param kwargs:
        """
        super().__init__(*args, **kwargs)
        self.threshold = self.conf_getfloat("threshold", threshold)

        logger.debug(f'{self.__class__.__name__} initialised with '
                     f'threshold={self.threshold}')

    @classmethod
    def short_name(cls) -> str:
        return 'sef'

    @classmethod
    def edge_type(cls) -> str:
        return "similarity"

    def modify(self, graph_to_modify):
        # note that edge_type is function call here and in BottomSimilarityEdgeFilter it can be an attribute
        for e in graph_to_modify.edges:
            print(e.wgts[0][0])
        graph_to_modify.edges = [edge for edge in graph_to_modify.edges if edge.wgts[0][0] > self.threshold]
        # graph_to_modify.edges = [edge for edge in graph_to_modify.edges if edge.wgts[self.__class__.edge_type()][0] > self.threshold]
        return graph_to_modify


class BottomSimilarityEdgeFilter(Modifier):
    def __init__(self, *args, top_edges=None, **kwargs):
        """
        Filters all edges except top edges for specific edge type
        :param args:
        :param top_edges: the number of top edges to keep for each node
        :param kwargs:
        """
        super().__init__(*args, **kwargs)
        self.top_edges = self.conf_getint('d', top_edges)

        logger.debug(f'{self.__class__.__name__} initialised with '
                     f'top_edges={self.top_edges}')

    @classmethod
    def short_name(cls) -> str:
        return 'bsef'

    @classmethod
    def edge_type(cls) -> str:
        return "similarity"

    def modify(self, graph_to_modify):
        filtered_edges = []
        edge_dict = build_edge_dict(graph_to_modify)

        # for node_id in graph.id2idx.keys():
        for comment in graph_to_modify.comments:
            for j, split in enumerate(comment.splits):
                node_edges = edge_dict[node_to_sid(node=None, a=comment.id, b=j)]
                node_edges = sorted(node_edges, key=lambda e: e.wgts[self.__class__.edge_type()], reverse=True)[
                             :self.top_edges]
                for edge in node_edges:
                    if edge not in filtered_edges:
                        filtered_edges.append(edge)
        graph_to_modify.edges = filtered_edges

        return graph_to_modify


class PageRankFilter(Modifier):
    def __init__(self, *args, k=None, strict=None, **kwargs):
        """
        Remove edges from a graph not connected to top-k nodes
        :param args:
        :k: top k page-ranked items to choose
        :strict: filter edges strictly (only allow edges between top-k nodes) or not (edge only needs on top-k node)
        :param kwargs:
        """
        super().__init__(*args, **kwargs)
        self.k = self.conf_getint("k", k)
        self.strict = self.conf_getboolean('strict', strict)

        logger.debug(f'{self.__class__.__name__} initialised with '
                     f'k={self.k} and strict={self.strict}')

    @classmethod
    def short_name(cls) -> str:
        return 'prf'

    @classmethod
    def split_type(cls) -> str:
        return "pagerank"

    def modify(self, graph_to_modify):
        page_ranks = {node_to_sid(node=None, a=comment.id, b=j): split.wgts[models.SplitWeights.PAGERANK]
                      for comment in graph_to_modify.comments for j, split in enumerate(comment.splits)}
        filtered_ranks = {k: v for k, v in sorted(page_ranks.items(), key=lambda item: item[1], reverse=True)[:self.k]}

        if self.strict:
            graph_to_modify.edges = [edge for edge in graph_to_modify.edges
                                     if node_to_sid(edge.src) in filtered_ranks and node_to_sid(
                    edge.tgt) in filtered_ranks]
        else:
            graph_to_modify.edges = [edge for edge in graph_to_modify.edges
                                     if
                                     node_to_sid(edge.src) in filtered_ranks or node_to_sid(edge.tgt) in filtered_ranks]

        return graph_to_modify
