from ssl import SSLContext,SSLSocket,SSL_ERROR_WANT_READ,SSL_ERROR_WANT_WRITE,PROTOCOL_SSLv23
import socket

ctx=SSLContext(PROTOCOL_SSLv23)
ctx.load_cert_chain()
sock=socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.setblocking(False)
sock.connect(())
sc=ctx.wrap_socket(sock,server_side=False)
sc.do_handshake()