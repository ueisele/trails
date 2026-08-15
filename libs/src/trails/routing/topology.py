"""Disjoint sets, and the point clustering that turns coordinates into nodes."""

import numpy as np
import shapely


class UnionFind:
    """Disjoint sets over ``0 .. size - 1``, each named by its smallest member.

    Joining by smallest index rather than by rank costs a little depth and buys
    the property everything here depends on: the name of a set never depends on
    the order its members were joined in, so two runs over the same data label
    the same sets the same way.
    """

    def __init__(self, size: int) -> None:
        """Start with every item in a set of its own.

        Args:
            size: Number of items
        """
        self._parent = np.arange(size, dtype=np.int64)

    def find(self, item: int) -> int:
        """Return the name of the set holding an item.

        Args:
            item: Item to look up

        Returns:
            Smallest item in the same set
        """
        parent = self._parent
        root = int(item)
        while parent[root] != root:
            root = int(parent[root])

        # Flatten the path walked, so the next lookup is direct.
        node = int(item)
        while node != root:
            parent[node], node = root, int(parent[node])
        return root

    def union(self, left: int, right: int) -> None:
        """Join the sets holding two items.

        Args:
            left: One item
            right: The other
        """
        left_root, right_root = self.find(left), self.find(right)
        if left_root == right_root:
            return
        if left_root < right_root:
            self._parent[right_root] = left_root
        else:
            self._parent[left_root] = right_root

    def labels(self) -> np.ndarray:
        """Return the set name of every item.

        Returns:
            Array of the same length as the item count
        """
        return np.array([self.find(item) for item in range(len(self._parent))], dtype=np.int64)


def cluster_points(coords: np.ndarray, tolerance_m: float) -> np.ndarray:
    """Label coordinates lying within a tolerance of each other as one point.

    Rounding to a grid would be cheaper but breaks exactly where it matters: two
    coordinates a millimetre apart still fall on opposite sides of a boundary
    now and then, and a node that splits in two disconnects the network there.

    Args:
        coords: ``(n, 2)`` array of projected coordinates
        tolerance_m: Distance below which two coordinates are the same point

    Returns:
        Array of ``n`` labels; the label is the index of the smallest member of
        the cluster, so it is stable across runs
    """
    if len(coords) == 0:
        return np.empty(0, dtype=np.int64)

    points = np.asarray(shapely.points(coords))
    left, right = shapely.STRtree(points).query(points, predicate="dwithin", distance=tolerance_m)

    groups = UnionFind(len(coords))
    for one, other in zip(left, right, strict=True):
        groups.union(int(one), int(other))
    return groups.labels()


def dense_ids(labels: np.ndarray) -> np.ndarray:
    """Renumber arbitrary labels to ``0 .. distinct - 1``, keeping their order.

    Args:
        labels: Labels as returned by :func:`cluster_points`

    Returns:
        Array of the same length holding small consecutive ids
    """
    _, dense = np.unique(labels, return_inverse=True)
    return np.asarray(dense, dtype=np.int64).reshape(labels.shape)
