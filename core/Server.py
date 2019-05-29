import socket
from selectors import DefaultSelector, EVENT_READ, EVENT_WRITE
from utils.DataUtil import ReqSM, RespSM, Method, buf, Tools, ErrorCode
import ssl
import conf

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
            events = self.selector.select(2)
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

    def set_result(self, proxy,result):
        try:
            if not proxy.is_error:
                self.core.send(result)
            else:
                proxy.show()
                proxy.end()
        except StopIteration as e:
            sr=e.value
            if sr==0:
                print(b'do not support this host: '+proxy.reqsm.host)
            else:
                print('Success process!')
            proxy.show()
            proxy.end()

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
        self.handshake_ok=False
        #do handshake as https server with client
        self.to_cli_ctx=ssl.SSLContext(ssl.PROTOCOL_SSLv23)
        #do handshake as htts client with server
        self.to_svr_ctx=ssl.SSLContext(ssl.PROTOCOL_SSLv23)
        self.is_error = False
        self.error = None
        self.output=[]

    def core(self):
        yield from self.read_req()
        if self.reqsm.host in [b'apm.suning.cn',b'sportlive.suning.com',b'ulogs.umengcloud.com',b'click.suning.cn',b'bpus.pptv.com',b'ssac.suning.com',b'pancake.apple.com',b'snsis.suning.com',b'ulogs.umeng.com',b'p29-buy.itunes.apple.com',b'e.crashlytics.com',b'gsp64-ssl.ls.apple.com']:
            self.end()
            return 0
        else:
            if self.reqsm.method == Method.CONNECT:
                '''process HTTPS connect
                '''
                self.output.append(b'connect hraders: ' + self.reqsm.headers)
                self.to_svr = self.connect_remote(self.reqsm.host, self.reqsm.port)
                yield from self.send_resp(b'HTTP/1.1 200 Connection Established\r\n\r\n')
                self.to_cli_ctx.load_cert_chain(conf.servercert, conf.serverkey)
                self.to_cli = self.to_cli_ctx.wrap_socket(self.to_cli, server_side=True, do_handshake_on_connect=False)
                yield from self.handshake(self.to_cli)
                self.reqsm.reset()
                yield from self.read_req()
                self.to_svr_ctx.load_cert_chain(conf.clientcert)
                self.to_svr = self.to_svr_ctx.wrap_socket(self.to_svr, server_side=False, do_handshake_on_connect=False)
                yield from self.handshake(self.to_svr)
            else:
                self.to_svr = self.connect_remote(self.reqsm.host, self.reqsm.port)
            yield from self.send_req()
            yield from self.read_resp()
            yield from self.send_resp()
            return 1

    def read_req(self):
        #read request data from app
        self.selector.register(self.to_cli, EVENT_READ, self.on_read)
        while True:
            chunk = yield self.engine
            if chunk:
                self.reqsm.data += chunk
                if self.reqsm.is_finished():
                    break
            else:
                self.is_error=True
                self.output.append('Client unexpected closed.')
                break
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
                self.is_error = True
                self.output.append('Server unexpected closed.')
                break
        self.selector.unregister(self.to_svr)

    def send_req(self,buf=None):
        #send app request data to server
        self.selector.register(self.to_svr, EVENT_WRITE, self.on_send)
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
            self.engine.set_result(self,s.recv(2048))
        except ssl.SSLWantReadError:
            pass
        except IOError as e:
            error = Tools.get_error_code(str(e))
            if error == ErrorCode.WSAEINTR or error == ErrorCode.EWOULDBLOCK:
                pass
            else:
                self.is_error = True
                self.output.append(str(e))
        except Exception as e:
            self.is_error=True
            self.output.append(str(e))



    def on_send(self,s):
        try:
            self.engine.set_result(self,s.send(self.buf[self.cursor:]))
        except ssl.SSLWantWriteError:
            pass
        except IOError as e:
            error = Tools.get_error_code(str(e))
            if error == ErrorCode.WSAEINTR or error == ErrorCode.EWOULDBLOCK:
                pass
            else:
                self.is_error = True
                self.output.append(str(e))
        except Exception as e:
            self.is_error=True
            self.output.append(str(e))


    def connect_remote(self,host,port):
        #connect to server
        #to_svr is the connection to server
        to_svr = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        to_svr.setblocking(False)
        try:
            to_svr.connect((host, port))
        except IOError as e:
            error = Tools.get_error_code(str(e))
            if error == ErrorCode.WSAEINTR or error == ErrorCode.EWOULDBLOCK:
                pass
            else:
                raise IOError(str(e))
        return to_svr

    def on_handshake(self,ss):
        try:
            ss.do_handshake()
            self.engine.set_result(self,True)
        except ssl.SSLWantWriteError:
            self.engine.set_result(self,False)
        except ssl.SSLWantReadError:
            self.engine.set_result(self,False)
        except Exception as e:
            self.engine.set_result(self,False)
            self.is_error=True
            self.output.append(str(e))

    def handshake(self,ss):
        self.selector.register(ss,EVENT_READ | EVENT_WRITE,self.on_handshake)
        while True:
            r=yield self.engine
            if r:
                break
        self.output.append(self.reqsm.host+b': handshake ok')
        self.selector.unregister(ss)

    def show(self):
        print('---------------------------------------------------------------------------------------------------------------')
        self.output.append(b'Host: '+self.reqsm.host+b' Port: '+str(self.reqsm.port).encode())
        print(self.output)
        print(self.reqsm.headers + self.DCRLF+ self.reqsm.data)
        print(self.respsm.headers + self.DCRLF + self.respsm.data)
        print('---------------------------------------------------------------------------------------------------------------')

    def release(self,s):
        if s:
            try:
                self.selector.unregister(s)
            except KeyError:
                pass
            s.close()

    def end(self):
        self.release(self.to_cli)
        self.release(self.to_svr)


loop = Loop()
loop.run()
