"""Tests for the disjoint sets and the point clustering built on them."""

import numpy as np
from trails.routing.topology import UnionFind, cluster_points, dense_ids


class TestUnionFind:
    """Test UnionFind."""

    def test_every_item_starts_alone(self):
        """Test that nothing is joined until it is asked for."""
        groups = UnionFind(4)
        assert groups.labels().tolist() == [0, 1, 2, 3]

    def test_joined_items_share_a_label(self):
        """Test that a union puts two items in one set."""
        groups = UnionFind(4)
        groups.union(1, 3)
        assert groups.find(3) == groups.find(1)

    def test_set_is_named_by_its_smallest_member(self):
        """Test the property chain ids depend on: the label is order-free."""
        forwards, backwards = UnionFind(5), UnionFind(5)
        for one, other in ((3, 4), (2, 3), (1, 2)):
            forwards.union(one, other)
        for one, other in ((1, 2), (2, 3), (3, 4)):
            backwards.union(other, one)
        assert forwards.labels().tolist() == backwards.labels().tolist() == [0, 1, 1, 1, 1]

    def test_joining_a_set_to_itself_changes_nothing(self):
        """Test that a repeated union is harmless."""
        groups = UnionFind(3)
        groups.union(0, 1)
        groups.union(1, 0)
        assert groups.labels().tolist() == [0, 0, 2]


class TestClusterPoints:
    """Test cluster_points."""

    def test_empty_input(self):
        """Test with no coordinates at all."""
        assert cluster_points(np.empty((0, 2)), 0.01).tolist() == []

    def test_coordinates_within_tolerance_become_one_point(self):
        """Test that a hairline difference does not split a node in two."""
        coords = np.array([[0.0, 0.0], [0.001, 0.0], [5.0, 0.0]])
        labels = cluster_points(coords, 0.01)
        assert labels[0] == labels[1]
        assert labels[2] != labels[0]

    def test_coordinates_beyond_tolerance_stay_apart(self):
        """Test that the tolerance is respected."""
        coords = np.array([[0.0, 0.0], [0.5, 0.0]])
        assert len(set(cluster_points(coords, 0.01).tolist())) == 2

    def test_a_chain_of_near_points_clusters_transitively(self):
        """Test that clustering follows the links rather than a fixed radius."""
        coords = np.array([[0.0, 0.0], [0.008, 0.0], [0.016, 0.0]])
        assert len(set(cluster_points(coords, 0.01).tolist())) == 1

    def test_label_does_not_depend_on_input_order_of_a_cluster(self):
        """Test that the smallest member names the cluster."""
        coords = np.array([[9.0, 0.0], [0.0, 0.0], [0.001, 0.0]])
        assert cluster_points(coords, 0.01).tolist() == [0, 1, 1]


class TestDenseIds:
    """Test dense_ids."""

    def test_labels_are_renumbered_keeping_their_order(self):
        """Test that arbitrary labels become consecutive ones."""
        assert dense_ids(np.array([7, 0, 7, 3])).tolist() == [2, 0, 2, 1]

    def test_empty_input(self):
        """Test with nothing to renumber."""
        assert dense_ids(np.empty(0, dtype=np.int64)).tolist() == []
