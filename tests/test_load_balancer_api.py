from unittest.mock import patch, MagicMock
import pytest

import load_balancer as lb


@pytest.fixture
def client():
    lb.managed_servers.clear()
    lb.ring = lb.ConsistentHashRing(slots=lb.SLOTS, num_virtual_servers=lb.VIRTUAL_SERVERS)
    lb.app.config["TESTING"] = True
    with lb.app.test_client() as c:
        yield c


@patch("load_balancer.spawn_container")
def test_add_basic(mock_spawn, client):
    resp = client.post("/add", json={"n": 2, "hostnames": ["s1"]})
    data = resp.get_json()
    assert resp.status_code == 200
    assert data["message"]["N"] == 2
    assert "s1" in data["message"]["replicas"]
    assert mock_spawn.call_count == 2


@patch("load_balancer.spawn_container")
def test_add_hostname_list_too_long(mock_spawn, client):
    resp = client.post("/add", json={"n": 1, "hostnames": ["s1", "s2"]})
    assert resp.status_code == 400
    assert "more than newly added" in resp.get_json()["message"]


def test_add_invalid_n_type(client):
    resp = client.post("/add", json={"n": "two", "hostnames": []})
    assert resp.status_code == 400


@patch("load_balancer.remove_container")
@patch("load_balancer.spawn_container")
def test_rm_basic(mock_spawn, mock_remove, client):
    client.post("/add", json={"n": 3, "hostnames": ["s1", "s2", "s3"]})
    resp = client.delete("/rm", json={"n": 1, "hostnames": ["s1"]})
    data = resp.get_json()
    assert resp.status_code == 200
    assert data["message"]["N"] == 2
    assert "s1" not in data["message"]["replicas"]


@patch("load_balancer.remove_container")
@patch("load_balancer.spawn_container")
def test_rm_hostname_list_too_long(mock_spawn, mock_remove, client):
    client.post("/add", json={"n": 2, "hostnames": ["s1", "s2"]})
    resp = client.delete("/rm", json={"n": 1, "hostnames": ["s1", "s2"]})
    assert resp.status_code == 400
    assert "more than removable" in resp.get_json()["message"]


@patch("load_balancer.remove_container")
@patch("load_balancer.spawn_container")
def test_rm_more_than_exist(mock_spawn, mock_remove, client):
    client.post("/add", json={"n": 1, "hostnames": ["s1"]})
    resp = client.delete("/rm", json={"n": 5, "hostnames": []})
    assert resp.status_code == 400


@patch("load_balancer.requests.get")
@patch("load_balancer.spawn_container")
def test_route_success(mock_spawn, mock_get, client):
    client.post("/add", json={"n": 1, "hostnames": ["s1"]})
    mock_resp = MagicMock(status_code=200)
    mock_resp.json.return_value = {"message": "Hello from s1", "status": "successful"}
    mock_get.return_value = mock_resp

    resp = client.get("/home")
    assert resp.status_code == 200
    assert resp.get_json()["message"] == "Hello from s1"


@patch("load_balancer.requests.get")
@patch("load_balancer.spawn_container")
def test_route_unknown_endpoint_becomes_400(mock_spawn, mock_get, client):
    client.post("/add", json={"n": 1, "hostnames": ["s1"]})
    mock_get.return_value = MagicMock(status_code=404)

    resp = client.get("/other")
    assert resp.status_code == 400
    assert "does not exist" in resp.get_json()["message"]


def test_route_with_no_servers_returns_503(client):
    resp = client.get("/home")
    assert resp.status_code == 503