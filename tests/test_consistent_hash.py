from consistent_hash import ConsistentHashRing


def test_empty_ring_returns_none():
    ring = ConsistentHashRing(slots=64, num_virtual_servers=3)
    assert ring.get_server(123456) is None


def test_add_server_places_k_virtual_nodes():
    ring = ConsistentHashRing(slots=64, num_virtual_servers=4)
    ring.add_server("s1")
    occupied = [s for s in ring.ring if s is not None]
    assert len(occupied) == 4
    assert all(s == "s1" for s in occupied)


def test_remove_server_clears_all_its_slots():
    ring = ConsistentHashRing(slots=64, num_virtual_servers=4)
    ring.add_server("s1")
    ring.add_server("s2")
    ring.remove_server("s1")
    assert "s1" not in ring.ring
    assert ring.get_server(999999) == "s2"


def test_remove_nonexistent_server_is_noop():
    ring = ConsistentHashRing(slots=64, num_virtual_servers=4)
    ring.add_server("s1")
    ring.remove_server("does_not_exist")
    assert ring.get_server(1) == "s1"


def test_collision_probing_resolves(monkeypatch):
    ring = ConsistentHashRing(slots=10, num_virtual_servers=1)
    monkeypatch.setattr(ring, "_hash_virtual_server", lambda name, j: 0)

    ring.add_server("A")
    ring.add_server("B")

    occupied = {s for s in ring.ring if s is not None}
    assert occupied == {"A", "B"}
    assert ring.ring[0] == "A"
    assert ring.ring[1] == "B"


def test_routing_is_deterministic_for_same_request_id():
    ring = ConsistentHashRing(slots=128, num_virtual_servers=9)
    ring.add_server("s1")
    ring.add_server("s2")
    ring.add_server("s3")
    first = ring.get_server(555555)
    second = ring.get_server(555555)
    assert first == second