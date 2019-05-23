from ssl import SSLContext,SSLSocket,SSL_ERROR_WANT_READ,SSL_ERROR_WANT_WRITE,PROTOCOL_SSLv23
import socket
from os import path
import conf

req=b'''
GET https://api.passport.pptv.com/refreshToken?appver=7.8.0&format=json&appplt=iph&platform=iphone4&refreshToken=b5da0983df8841238e0a76d3e7b0414a&auth=55b7c50dc1adfc3bcabe2d9b2015e35c&appid=com.pptv.iphoneapp HTTP/1.1
Host: api.passport.pptv.com
Cookie: _snstyxuid=9729D5428EF67QI2; _snstyxuid=3E29D54288A667A2; __ssav=155292409430254348%7C1552924094302%7C1552924094302%7C1552924094302%7C1%7C1%7C1; _snvd=1552924094671zlnHzVZjMXj; Hm_lvt_7adaa440f53512a144c13de93f4c22db=1552924094; PUID=c121250dcaec4aa78d445afcf0be39b4; __crt=1547478856711
Connection: keep-alive
hiro_trace_type: SDK
Accept: */*
User-Agent: Browser/7.8.0.1911 (iPhone; iOS 10.3.3; Scale/3.00)
Accept-Language: zh-cn
hiro_trace_id: 6e6a7530159e48dcbe3b2cc7060b6b0e
Accept-Encoding: gzip, deflate

'''
host='api.passport.pptv.com'
clientcert=path.join(path.abspath(path.dirname(path.dirname(__file__))),'certs','soul_client.pem')
servercert=path.join(path.abspath(path.dirname(path.dirname(__file__))),'certs','sn_new_server.crt')
serverkey=path.join(path.abspath(path.dirname(path.dirname(__file__))),'certs','sn_new_server_key.pem')
print(clientcert)

ctx=SSLContext(PROTOCOL_SSLv23)
ctx.load_cert_chain(certfile=clientcert)
sock=socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.setblocking(True)
sock.connect((host,443))
sc=ctx.wrap_socket(sock,server_side=False)
sc.do_handshake()