import os
import random
import string
import threading
import time
import requests
from flask import Flask, jsonify, request
from consistent_hash import ConsistentHashRing

app = Flask(__name__)

SLOTS = 512
VIRTUAL_SERVERS = 9
ring = ConsistentHashRing(slots=SLOTS, num_virtual_servers=VIRTUAL_SERVERS)
managed_servers = set()
lock = threading.Lock()


def generate_random_name():
    return "server_" + "".join(random.choices(string.ascii_lowercase + string.digits, k=6))


def spawn_container(container_name):
    cmd = (
        f"sudo docker run --name {container_name} --network net1 "
        f"--network-alias {container_name} -e SERVER_ID={container_name} "
        f"-d server-image:latest"
    )
    os.popen(cmd).read()


def remove_container(container_name):
    os.system(f"sudo docker stop {container_name} && sudo docker rm {container_name}")


def health_check_loop():
    while True:
        time.sleep(2)
        with lock:
            servers_to_check = list(managed_servers)
        for server in servers_to_check:
            try:
                res = requests.get(f"http://{server}:5000/heartbeat", timeout=1.5)
                if res.status_code != 200:
                    raise Exception("Bad heartbeat")
            except Exception:
                with lock:
                    if server in managed_servers:
                        print(f"[health] {server} is down — replacing...")
                        ring.remove_server(server)
                        managed_servers.remove(server)
                        os.system(f"sudo docker rm -f {server} > /dev/null 2>&1")
                        new_server = generate_random_name()
                        spawn_container(new_server)
                        ring.add_server(new_server)
                        managed_servers.add(new_server)
                        print(f"[health] Spawned replacement: {new_server}")


@app.route('/rep', methods=['GET'])
def get_replicas():
    with lock:
        return jsonify({
            "message": {
                "N": len(managed_servers),
                "replicas": sorted(list(managed_servers))
            },
            "status": "successful"
        }), 200


@app.route('/add', methods=['POST'])
def add_replicas():
    data = request.get_json() or {}
    n = data.get("n", 0)
    hostnames = data.get("hostnames", [])

    if not isinstance(n, int) or n <= 0:
        return jsonify({"message": "<Error> 'n' must be a positive integer", "status": "failure"}), 400

    if len(hostnames) > n:
        return jsonify({
            "message": "<Error> Length of hostname list is more than newly added instances",
            "status": "failure"
        }), 400

    with lock:
        for idx in range(n):
            name = hostnames[idx] if idx < len(hostnames) else generate_random_name()
            if name not in managed_servers:
                spawn_container(name)
                ring.add_server(name)
                managed_servers.add(name)
        return jsonify({
            "message": {
                "N": len(managed_servers),
                "replicas": sorted(list(managed_servers))
            },
            "status": "successful"
        }), 200


@app.route('/rm', methods=['DELETE'])
def remove_replicas():
    data = request.get_json() or {}
    n = data.get("n", 0)
    hostnames = data.get("hostnames", [])

    if not isinstance(n, int) or n <= 0:
        return jsonify({"message": "<Error> 'n' must be a positive integer", "status": "failure"}), 400

    if len(hostnames) > n:
        return jsonify({
            "message": "<Error> Length of hostname list is more than removable instances",
            "status": "failure"
        }), 400

    with lock:
        if n > len(managed_servers):
            return jsonify({
                "message": "<Error> Cannot remove more servers than currently exist",
                "status": "failure"
            }), 400

        for name in hostnames:
            if name in managed_servers:
                remove_container(name)
                ring.remove_server(name)
                managed_servers.remove(name)
                n -= 1

        # Remove remaining randomly to reach the requested count
        while n > 0 and managed_servers:
            random_server = random.choice(list(managed_servers))
            remove_container(random_server)
            ring.remove_server(random_server)
            managed_servers.remove(random_server)
            n -= 1

        return jsonify({
            "message": {
                "N": len(managed_servers),
                "replicas": sorted(list(managed_servers))
            },
            "status": "successful"
        }), 200


@app.route('/<path:server_path>', methods=['GET'])
def route_request(server_path):
    """
    Route any GET request to a server replica via consistent hashing.
    If the endpoint doesn't exist on the server, proxy the 404 back as an error.
    """
    request_id = random.randint(100000, 999999)
    with lock:
        target_server = ring.get_server(request_id)

    if not target_server:
        return jsonify({
            "message": "<Error> No active server containers available",
            "status": "failure"
        }), 503

    try:
        res = requests.get(f"http://{target_server}:5000/{server_path}", timeout=2.0)
        if res.status_code == 404:
            return jsonify({
                "message": f"<Error> '/{server_path}' endpoint does not exist in server replicas",
                "status": "failure"
            }), 400
        return jsonify(res.json()), res.status_code

    except Exception as e:
        return jsonify({
            "message": f"<Error> Failed to communicate with target server: {str(e)}",
            "status": "failure"
        }), 500


if __name__ == '__main__':
    initial_servers = ["server_1", "server_2", "server_3"]
    for s in initial_servers:
        spawn_container(s)
        ring.add_server(s)
        managed_servers.add(s)

    monitor_thread = threading.Thread(target=health_check_loop, daemon=True)
    monitor_thread.start()

    app.run(host='0.0.0.0', port=5000)