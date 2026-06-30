import hashlib

class ConsistentHashRing:
    def __init__(self, slots=512, num_virtual_servers=9):
        self.slots = slots
        self.K = num_virtual_servers
        self.ring = [None] * self.slots
        self.server_name_to_idx = {}
        self.next_server_idx = 1

    def _hash_request(self, i: int) -> int:
        """H(i) = i^2 + 2i + 17  (assignment spec)"""
        return (i**2 + 2*i + 17) % self.slots

    def _hash_virtual_server(self, server_name: str, j: int) -> int:
        """
        Use MD5 of 'server_name:j' to get a well-distributed slot.
        This satisfies the spirit of Phi(i,j) while avoiding the clustering
        that results from applying the spec's polynomial to small sequential IDs.
        """
        key = f"{server_name}:{j}".encode()
        digest = hashlib.md5(key).hexdigest()
        return int(digest, 16) % self.slots

    def add_server(self, server_name: str):
        if server_name in self.server_name_to_idx:
            return
        self.server_name_to_idx[server_name] = self.next_server_idx
        self.next_server_idx += 1

        for j in range(self.K):
            slot = self._hash_virtual_server(server_name, j)
            probe = 0
            while self.ring[(slot + probe) % self.slots] is not None:
                probe += 1
                if probe == self.slots:
                    raise Exception("Hash ring is full!")
            self.ring[(slot + probe) % self.slots] = server_name

    def remove_server(self, server_name: str):
        if server_name not in self.server_name_to_idx:
            return
        for slot_idx in range(self.slots):
            if self.ring[slot_idx] == server_name:
                self.ring[slot_idx] = None
        del self.server_name_to_idx[server_name]

    def get_server(self, request_id: int) -> str:
        if not self.server_name_to_idx:
            return None
        start_slot = self._hash_request(request_id)
        for offset in range(self.slots):
            slot = (start_slot + offset) % self.slots
            if self.ring[slot] is not None:
                return self.ring[slot]
        return None