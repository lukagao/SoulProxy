from ssl import SSLContext,SSLSocket,SSL_ERROR_WANT_READ,SSL_ERROR_WANT_WRITE,PROTOCOL_SSLv23,SSLWantReadError,SSLWantWriteError
import socket
from os import path
from selectors import DefaultSelector, EVENT_READ, EVENT_WRITE
import time
import conf

req=b'''
POST https://ulogs.umeng.com/unify_logs HTTP/1.1
Host: ulogs.umeng.com
Content-Type: ut/a
Accept: */*
Connection: keep-alive
X-Umeng-Sdk: a/5.5.4 7.8.0/iOS/PP%E8%A7%86%E9%A2%91/iPhone8,2/10.3.3 37148931915139B18C75E4F9E30B51A6
Msg-Type: envelope/json
X-Umeng-UTC: 1559054937144
Accept-Language: zh-cn
User-Agent: PPTViPhone/7.8.0.1911 CFNetwork/811.5.4 Darwin/16.7.0
Accept-Encoding: gzip, deflate
Content-Length: 2

ab

'''
host='ulogs.umeng.com'
clientcert=path.join(path.abspath(path.dirname(path.dirname(__file__))),'certs','soul_client.pem')
servercert=path.join(path.abspath(path.dirname(path.dirname(__file__))),'certs','sn_new_server.crt')
serverkey=path.join(path.abspath(path.dirname(path.dirname(__file__))),'certs','sn_new_server_key.pem')




selector=DefaultSelector()
ctx=SSLContext(PROTOCOL_SSLv23)
ctx.load_cert_chain(certfile=clientcert)
sock=socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.setblocking(False)
selector.register(sock,EVENT_WRITE)
try:
    sock.connect((host,443))
except BlockingIOError:
    pass

while True:
    events=selector.select(2)
    if events:
        break
selector.unregister(sock)

sc=ctx.wrap_socket(sock,server_side=False,do_handshake_on_connect=False)

selector.register(sc,EVENT_WRITE | EVENT_READ)

while True:
    events = selector.select(2)
    if events:
        try:
            sc.do_handshake()
            break
        except SSLWantReadError:
            pass
        except SSLWantWriteError:
            pass
selector.unregister(sc)
print(sc.send(req))
while True:
    try:
        print(sc.recv(2048))
        break
    except SSLWantReadError:
        pass

#selector.unregister(sc)
#selector.unregister(sc)

def g1():
    for i in range(3):
        yield i
        print(i)
    return 1

def g2():
    for i in range(3,5):
        yield i
        print(i)

def g():
    yield from g1()
    yield from g2()
    print('end')

gen=g()
try:
    while True:
        gen.send(None)
except StopIteration as e:
    print(e.value)


b=b'Proxy-Connection'
b=b'Connection'
a=b'adadadadad'
print(a.split(b':'))