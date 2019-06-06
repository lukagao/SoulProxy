import socket
from selectors import DefaultSelector, EVENT_READ, EVENT_WRITE
from utils.DataUtil import ReqSM, RespSM, Method, Tools, ErrorCode
import ssl
import conf
import re

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

    def run(self):
        while True:
            events = self.selector.select(2)
            for key, mask in events:
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
                del proxy
        except StopIteration as e:
            sr=e.value
            if sr==0:
                pass
            elif sr==1:
                pass
            else:
                pass
            proxy.show()
            proxy.end()
            del proxy

class CallBack(object):

    def __init__(self,**kwargs):
        method,host,path,query,regx = (
            kwargs.get('method'),
            kwargs.get('host'),
            kwargs.get('path'),
            kwargs.get('query'),
            kwargs.get('regx')
        )
        self.method=method
        self.host = host.encode() if type(host)==str else host
        self.path = path.encode() if type(path) == str else path
        self.query = query.encode() if type(query) == str else query
        self.regx = regx.encode() if type(regx) == str else regx



    def invoke(self,data):
        return self.method(data)

class Proxy(object):

    __bf_cbs=[]
    __af_cbs=[]
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
        self.is_error = False
        self.error = None
        self.output=[]
        #0:client,1:server
        self.which=0
        self.support=True
        #0:http,1:https,-1:unknown
        self.protocol=0

    @classmethod
    def set_cb_before_request(cls,method,host=None,path=None,query=None,regx=None,**kwargs):
        args = [method, host, path, query, regx]
        names = Proxy.set_cb_after_response.__code__.co_varnames[1:]
        for index in range(len(args)):
            kwargs[names[index]] = args[index]
        cls.__bf_cbs.append(CallBack(**kwargs))

    @classmethod
    def set_cb_after_response(cls,method,host=None,path=None,query=None,regx=None,**kwargs):
        args=[method,host,path,query,regx]
        names=Proxy.set_cb_after_response.__code__.co_varnames[1:]
        for index in range(len(args)):
            kwargs[names[index]]=args[index]
        print(kwargs)
        cls.__af_cbs.append(CallBack(**kwargs))


    #to do:
    #now ,do not use keep alive(should send Connection:close), if need this ,
    #a while loop is nessary,and should not close the conn after response to client.
    def core(self):
        yield from self.read_req()
        if not self.reqsm.host:
            self.protocol=-1
            return -1
        if self.reqsm.host in conf.unsupport and self.reqsm.method==Method.CONNECT:
            self.support=False
            self.protocol=1
            self.output.append(b'do not support: '+self.reqsm.host)
            self.output.append(b'connect hraders: ' + self.reqsm.headers)
            self.to_svr = self.connect_remote(self.reqsm.host, self.reqsm.port)
            yield from self.send_resp(b'HTTP/1.1 200 Connection Established\r\n\r\n')
            self.reqsm.reset()
            yield from self.tunnel()
            return 0
        else:
            if self.reqsm.method == Method.CONNECT:
                '''process HTTPS connectdo not support
                '''
                self.protocol=1
                self.output.append(b'connect hraders: ' + self.reqsm.headers)
                self.to_svr = self.connect_remote(self.reqsm.host, self.reqsm.port)
                yield from self.send_resp(b'HTTP/1.1 200 Connection Established\r\n\r\n')
                # do handshake as https server with client
                to_cli_ctx = ssl.SSLContext(ssl.PROTOCOL_SSLv23)
                to_cli_ctx.load_cert_chain(conf.servercert, conf.serverkey)
                self.to_cli = to_cli_ctx.wrap_socket(self.to_cli, server_side=True, do_handshake_on_connect=False)
                yield from self.handshake(self.to_cli)
                self.reqsm.reset()
                yield from self.read_req()
                # do handshake as htts client with server
                to_svr_ctx = ssl.SSLContext(ssl.PROTOCOL_SSLv23)
                to_svr_ctx.load_cert_chain(conf.clientcert)
                self.to_svr = to_svr_ctx.wrap_socket(self.to_svr, server_side=False, do_handshake_on_connect=False)
                yield from self.handshake(self.to_svr)
            else:
                self.to_svr = self.connect_remote(self.reqsm.host, self.reqsm.port)
            self.do_bf_cbs()
            yield from self.send_req()
            yield from self.read_resp()
            self.do_af_cbs()
            yield from self.send_resp()
            return 1

    def tunnel(self):
        print('start tunnel')
        while True:
            self.selector.register(self.to_cli, EVENT_READ, self.on_read)
            self.selector.register(self.to_svr, EVENT_READ, self.on_read)
            chunk = yield self.which
            self.selector.unregister(self.to_svr)
            self.selector.unregister(self.to_cli)
            if chunk:
                if self.which==0:
                    self.reqsm.data+=chunk
                    yield from self.send_req(chunk)
                else:
                    self.respsm.data+=chunk
                    yield from self.send_resp(chunk)
            else:
                self.output.append(str(self.which)+' closed.')
                break

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
        if s==self.to_cli:
            self.which=0
        else:
            self.which=1
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
        except Exception as e:
            self.is_error=True
            self.output.append(str(e))
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
            self.is_error = True
            self.output.append(str(e))
            self.engine.set_result(self,False)


    def handshake(self,ss):
        self.selector.register(ss,EVENT_READ | EVENT_WRITE,self.on_handshake)
        while True:
            r=yield self.engine
            if r:
                break
        self.output.append(self.reqsm.host+b': handshake ok')
        self.selector.unregister(ss)

    def is_cb_match(self,cb):
        if cb.method is None:
            return False
        host, path, query, regx = (cb.host, cb.path, cb.query, cb.regx)
        if host:
            patt = re.compile(host)
            if not patt.findall(self.reqsm.host):
                return False
        l = self.reqsm.path.split(b'?')
        req_path = l[0]
        req_query = b''
        if len(l) >= 2:
            req_query = l[1]
        if path:
            patt = re.compile(path)
            if not patt.findall(req_path):
                return False
        if query:
            patt = re.compile(query)
            if not patt.findall(req_query):
                return False
        if regx:
            patt = re.compile(regx)
            if not patt.findall(self.reqsm.headers + self.reqsm.DCRLF + self.reqsm.data):
                return False
        return True


    def do_bf_cbs(self):
        if self.__bf_cbs:
            for cb in self.__bf_cbs:
                if self.is_cb_match(cb):
                    cb.invoke(self.reqsm)

    def do_af_cbs(self):
        if self.__af_cbs:
            for cb in self.__af_cbs:
                if self.is_cb_match(cb):
                    cb.invoke(self.respsm)

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
#loop.run()
Proxy.set_cb_after_response('ggg','aaaa')
