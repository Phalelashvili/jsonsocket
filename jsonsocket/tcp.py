#!/usr/bin/env python3
import socket
from threading import Thread

from jsonsocket.errors import NoClient, ConnectFirst
from jsonsocket.helpers import send as _send, receive as _recv, TimeoutError


class Server(object):
    """
    A JSON socket server used to communicate with a JSON socket client. All the
    data is serialized in JSON. How to use it:

    server = Server(host, port)
    while True:
      server.accept()
      data = server.recv()
      # shortcut: data = server.accept().recv()
      server.send({'status': 'ok'})
    """

    backlog = 5
    client = None

    def __init__(self, host, port):
        self.socket = socket.socket()
        self.socket.bind((host, port))
        self.host = host
        self.port = port
        self.socket.listen(self.backlog)
        self.__accepting = False

    def __del__(self):
        self.close()

    @property
    def client_connected(self):
        return self.client is not None

    @property
    def accepting_connections(self):
        return self.__accepting

    def accept(self):
        # if a client is already connected, disconnect it
        if self.client:
            self.client.close()
        self.__accepting = True
        self.client, self.client_addr = self.socket.accept()
        self.__accepting = False
        return self

    def send(self, data):
        if not self.client:
            raise NoClient()
        _send(self.client, data, socket_type="tcp")
        return self

    def recv(self, close_on_timeout=False, **kwargs):
        if not self.client:
            raise NoClient()
        try:
            res = _recv(self.client, socket_type="tcp", **kwargs)
        except TimeoutError:
            if close_on_timeout:
                self.close()
            return None
        return res

    def close(self):
        if self.client:
            self.client.close()
            self.client = None
        if self.socket:
            # if self.accepting_connections:
            if self.__accepting:
                c = Client()
                c.connect("localhost", self.port)
                c.close()
            self.socket.close()
            self.socket = None


class Client(object):
    """
    A JSON socket client used to communicate with a JSON socket server. All the
    data is serialized in JSON. How to use it:

    data = {
      'name': 'Patrick Jane',
      'age': 45,
      'children': ['Susie', 'Mike', 'Philip']
    }
    client = Client()
    client.connect(host, port)
    client.send(data)
    response = client.recv()
    # or in one line:
    response = Client().connect(host, port).send(data).recv()
    """

    socket = None

    def __init__(self, timeout=3):
        self.socket = socket.socket()
        self.socket.settimeout(timeout)

    def __del__(self):
        self.close()

    def connect(self, host, port):
        self.socket.connect((host, port))
        return self

    def send(self, data):
        if not self.socket:
            raise ConnectFirst()
        _send(self.socket, data, socket_type="tcp")
        return self

    def recv(self, **kwargs):
        if not self.socket:
            raise ConnectFirst()
        return _recv(self.socket, socket_type="tcp", **kwargs)

    def recv_and_close(self, **kwargs):
        data = self.recv(**kwargs)
        self.close()
        return data

    def close(self):
        if self.socket:
            self.socket.close()
            self.socket = None


class ServerAsync(Thread):
    def __init__(self, host, port, new_client_callback, new_message_callback, client_disconnect_callback=None,
                 exception_callback=None, timeout=5):
        super(ServerAsync, self).__init__()
        self.exception_callback = exception_callback
        self.client_disconnect_callback = client_disconnect_callback
        self.timeout = timeout
        self.new_message_callback = new_message_callback
        self.new_client_callback = new_client_callback
        self.server = Server(host, port)
        self.__running = True

    def stop(self):
        self.__running = False
        self.server.close()

    def run(self):
        try:
            while self.__running:
                self.server.accept()
                if not self.__running:
                    break
                client_addr = self.server.client_addr
                if self.new_client_callback:
                    self.new_client_callback(client_addr, self)
                while 1:
                    try:
                        data = self.server.recv(timeout=self.timeout)
                    except (NoClient, socket.error):
                        break
                    if data is not None:
                        self.new_message_callback(data, self)
                    else:
                        break
                if self.client_disconnect_callback:
                    self.client_disconnect_callback(client_addr, self)
        except Exception as e:
            if self.exception_callback:
                self.exception_callback(e)
            else:
                raise

    def send(self, data):
        self.server.send(data)

    @property
    def client_addr(self):
        return self.server.client_addr

    @property
    def client(self):
        return self.server.client

    def __enter__(self):
        self.start()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()
        self.server.close()
        self.join()


class ClientAsync(Thread):
    def __init__(self, new_message_callback, host_disconnect_callback=None,
                 exception_callback=None):
        super(ClientAsync, self).__init__()
        self.exception_callback = exception_callback
        self.host_disconnect_callback = host_disconnect_callback
        self.new_message_callback = new_message_callback
        self.__running = True

    def connect(self, host, port):
        self.host_addr = (host, port)
        self._client = Client()
        return self._client.connect(host, port)

    def stop(self):
        self.__running = False
        self._client.close()

    def run(self):
        try:
            while self.__running:
                while 1:
                    try:
                        data = self._client.recv()
                    except (NoClient, socket.error):
                        break
                    if data is not None:
                        self.new_message_callback(data, self)
                    else:
                        break
                if self.host_disconnect_callback:
                    self.host_disconnect_callback(self.host_addr, self)
        except Exception as e:
            if self.exception_callback:
                self.exception_callback(e)
            else:
                raise

    def send(self, data):
        self._client.send(data)

    @property
    def client_addr(self):
        return self._client.client_addr

    @property
    def client(self):
        return self._client.client

    def __enter__(self):
        self.start()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()
        self._client.close()
        self.join()

    def close(self):
        if self._client.socket:
            self._client.socket.close()
            self._client.socket = None
