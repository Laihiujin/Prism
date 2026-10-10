"""RESP2 transport for the bundled Windows Redis server."""
from kombu.transport.redis import Channel, Transport


class RESP2Channel(Channel):
    def _connparams(self, asynchronous=False):
        params = super()._connparams(asynchronous=asynchronous)
        params["protocol"] = 2
        return params


class RESP2Transport(Transport):
    Channel = RESP2Channel
