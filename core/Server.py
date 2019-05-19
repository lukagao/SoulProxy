import socket
from selectors import DefaultSelector, EVENT_READ, EVENT_WRITE
from utils.DataUtil import ReqSM, RespSM, Method, buf, Tools, ErrorCode


class Loop(object):

    def __init__(self):
        self.svr = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.svr.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.svr.setblocking(False)
        self.svr.bind(('0.0.0.0', 5230))
        self.svr.listen(1000)
        self.selector = DefaultSelector()
        self.selector.register(self.svr, EVENT_READ, self.on_accept)

    def on_accept(self, s):
        try:
            conn, addr = s.accept()
        except IOError as e:
            error = Tools.get_error_code(str(e))
            if error == ErrorCode.WSAEINTR or error == ErrorCode.EWOULDBLOCK:
                pass
            else:
                raise IOError(str(e))
        proxy = Proxy(conn)
        proxy.engine.core = proxy.core()
        next(proxy.engine.core)
        # self.selector.register(self.conn, EVENT_READ, self.on_read)
        #print(conn.fileno(), addr)

    def on_read(self, s):
        pass

    def run(self):
        while True:
            events = self.selector.select(0)
            for key, mask in events:
                if key.fileobj == self.svr and (mask | EVENT_READ):
                    callback = key.data
                    callback(key.fileobj)
                else:
                    callback = key.data
                    callback(key.fileobj)


class Engine(object):

    def __init__(self):
        self.core = None

    def set_result(self, result):
        self.core.send(result)


class Proxy(object):

    def __init__(self, conn):
        self.to_cli = conn
        self.CRLF = b'\r\n'
        self.DCRLF = b'\r\n\r\n'
        self.selector = loop.selector
        self.engine = Engine()
        self.reqsm = ReqSM()
        self.respsm=RespSM()
        self.port = 5173
        self.to_svr=None
        self.cursor=0
        self.buf=None

    def core(self):
        print('core start')

        yield from self.read_req()
        if self.reqsm.method==Method.CONNECT:
            '''process HTTPS connect
            '''
            #print('connect method')
            self.to_svr = self.connect_remote(b'127.0.0.1', 443)
            #response http estabished
            #self.send_resp(b'')
            #do handshake
        else:
            self.to_svr = self.connect_remote(b'127.0.0.1',5173)
        yield from self.send_req()
        yield from self.read_resp()
        yield from self.send_resp()


    def read_req(self):
        #read request data from app
        self.selector.register(self.to_cli, EVENT_READ, self.on_read)
        while True:
            chunk = yield self.engine
            #print(b'request chunk is :'+chunk)
            if chunk:
                self.reqsm.data += chunk
                if self.reqsm.is_finished():
                    #print(self.reqsm.Host+b' is finished')
                    break
            else:
                #print(b'get nothing!resqm data is '+self.reqsm.data)
                raise IOError('Client unexpected closed')
        self.selector.unregister(self.to_cli)


    def read_resp(self):
        #read server response data
        self.selector.register(self.to_svr,EVENT_READ,self.on_read)
        while True:
            chunk=yield self.engine
            if chunk:
                self.respsm.data+=chunk
                if self.respsm.is_finished():
                    break
            else:
                raise IOError('Server unexpected closed')
        self.selector.unregister(self.to_svr)

    def send_req(self,buf=None):
        #send app request data to server
        if buf:
            self.buf=buf
        else:
            self.buf=self.reqsm.headers + self.DCRLF + self.reqsm.data
        size=len(self.buf)
        count=0
        while True:
            sent = yield self.engine
            count+=sent
            self.cursor = count
            if count>=size:
                break
        self.buf=None
        self.cursor=0
        self.selector.unregister(self.to_svr)

    def send_resp(self,buf=None):
        #send server response data to app
        self.selector.register(self.to_cli,EVENT_WRITE,self.on_send)
        if buf:
            self.buf=buf
        else:
            self.buf = self.respsm.headers + self.DCRLF + self.respsm.data
        size=len(self.buf)
        count=0
        while True:
            sent=yield self.engine
            count+=sent
            self.cursor = count
            if count>=size:
                break
        self.buf=None
        self.cursor=0
        self.selector.unregister(self.to_cli)

    def on_read(self,s):
        try:
            self.engine.set_result(s.recv(2048))
        except IOError as e:
            error = Tools.get_error_code(str(e))
            if error == ErrorCode.WSAEINTR or error == ErrorCode.EWOULDBLOCK:
                pass
            else:
                raise IOError(str(e))

    def on_send(self,s):
        print('send start')
        try:
            self.engine.set_result(s.send(self.buf[self.cursor:]))
        except IOError as e:
            error = Tools.get_error_code(str(e))
            if error == ErrorCode.WSAEINTR or error == ErrorCode.EWOULDBLOCK:
                pass
            else:
                raise IOError(str(e))
        print(b'send data '+ self.buf[self.cursor:])

    def connect_remote(self,host,port):
        #connect to server
        #to_svr is the connection to server
        to_svr = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        to_svr.setblocking(False)
        #to_svr.settimeout(1)
        try:
            to_svr.connect((host, port))
        except IOError as e:
            error = Tools.get_error_code(str(e))
            if error == ErrorCode.WSAEINTR or error == ErrorCode.EWOULDBLOCK:
                pass
            else:
                raise IOError(str(e))
        self.selector.register(to_svr, EVENT_WRITE, self.on_send)
        return to_svr


loop = Loop()
loop.run()



