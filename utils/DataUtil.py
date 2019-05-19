import re
import platform

class ReqSM(object):
    
    def __init__(self):
        self.data=b''
        self.headers=None
        self.CRLF=b'\r\n'
        self.DCRLF=b'\r\n\r\n'
        self.header_complete=False
        self.header={}
        self.method=None
        self.path=None
        self.version=None
    
    def is_finished(self):
        if not self.header_complete:
            if self.DCRLF in self.data:
                l=self.data.split(self.DCRLF)
                self.headers=l[0]
                if len(l)>1:
                    self.data=b''.join(l[1:])
                self.generate_header()
                self.header_complete=True
            else:
                return False
        return self.is_streaming_end()

    def is_streaming_end(self):
        if self.method==Method.GET or self.method==Method.CONNECT:
            return True
        elif self.method==Method.POST:
            if ContentType.multipart in self.content_type:
                s=self.content_type.split(b';')[1]
                boundary=s.split(b'=')[1]
                end=b'--'+boundary+b'--'
                if end in self.data:
                    return True
            else:
                length=self.content_length
                if length<=len(self.data):
                    return True
            return False

    def generate_header(self):
        l=self.headers.split(self.CRLF)
        firstLine=l[0].split(b' ')
        self.method=firstLine[0]
        self.path=firstLine[1]
        self.version=firstLine[2]
        if len(l)>1:
            for i in range(1,len(l)):
                line=l[i].split(b':')
                self.header[line[0].strip()]=line[1].strip()
        #print(self.method,self.path,self.version)
        #print(self.header)
            
    @property
    def content_length(self):
        return int(self.header.get(b'Content-Length'))

    @property
    def Host(self):
        return self.header.get(b'Host')

    @property
    def content_type(self):
        return self.header.get(b'Content-Type')

        
class RespSM(object):

    def __init__(self):
        self.data = b''
        self.headers = None
        self.CR = b'\r'
        self.CRLF = b'\r\n'
        self.DCRLF = b'\r\n\r\n'
        self.header_complete = False
        self.header = {}
        self.version = None
        self.code = None
        self.status = None
        self.cursor=0
        self.buf=b''


    def is_finished(self):
        if not self.header_complete:
            if self.DCRLF in self.data:
                l = self.data.split(self.DCRLF)
                self.headers = l[0]
                if len(l) > 1:
                    self.data = b''.join(l[1:])
                self.generate_header()
                self.header_complete = True
            else:
                return False
        return self.is_streaming_end()

    def is_streaming_end(self):
        if self.transfer_encoding==ContentType.chunked:
            return self.is_chunked_ok()
        else:
            length = self.content_length
            if length <= len(self.data):
                return True

    def is_chunked_ok(self):
        while True:
            shif = 1
            cursor = self.cursor
            try:
                while self.data[cursor + shif] != self.CR[0]:
                    shif += 1
                size = int(self.data[cursor:cursor + shif], 16)
                if size == 0:
                    if self.data[cursor + shif:cursor + shif + 4]==self.DCRLF:
                        return True
                    else:
                        return False
                else:
                    if len(self.data[cursor + shif + 2:]) > size + 2:
                        self.cursor = cursor + shif + size + 4
                        buf=self.data[cursor + shif + 2:cursor + shif + size + 4].strip()
                        if len(buf)!=size:
                            return False
                        self.buf+=buf
                        continue
                    else:
                        return False
            except IndexError:
                return False



    @property
    def transfer_encoding(self):
        return self.header.get(b'Transfer-Encoding')


    def generate_header(self):
        l = self.headers.split(self.CRLF)
        firstLine = l[0].split(b' ')
        self.version = firstLine[0]
        self.code = firstLine[1]
        self.status = b' '.join(firstLine[2:])
        if len(l) > 1:
            for i in range(1, len(l)):
                line = l[i].split(b':')
                self.header[line[0].strip()] = line[1].strip()

    @property
    def content_length(self):
        return int(self.header.get(b'Content-Length'))

class Method(object):
    GET=b'GET'
    POST=b'POST'
    CONNECT=b'CONNECT'

class ErrorCode(object):
    WSAEINTR = 10004
    EWOULDBLOCK = 10035
    EINPROGRESS = 10036

class ContentType(object):
    multipart=b'multipart/form-data'
    json=b'bapplication/json'
    xml=b'text/xml'
    urlencoded=b'application/x-www-form-urlencoded'
    chunked=b'chunked'
    gzip=b'gzip'


class Tools(object):

    @staticmethod
    def get_error_code(error):
        ver = platform.python_version()
        sys = platform.system()
        if ver < '3.0':
            pattern = re.compile(r'\[Errno\s(\d+)\]')
        else:
            if sys == 'Windows':
                pattern = re.compile(r'\[WinError\s(\d+)\]')
        code_list = pattern.findall(error)
        if code_list:
            return int(code_list[0])
        return None

buf=b'POST /hhhhhh HTTP/1.1\r\nHost: 192.168.1.175\r\nContent-Type:multipart/form-data; boundary=----WebKitFormBoundaryrGKCBY7qhFd3TrwA\r\nContent-Length:14\r\n\r\nssgsgsgevsvv\r\n------WebKitFormBoundaryrGKCBY7qhFd3TrwA--'
buf=b'6\r\nqwerty\r\n1\r\na\r\nf\r\nqqqqqqqqwerty15\r\n0\r\n\r\n'
reqsm=ReqSM()
respsm=RespSM()
respsm.data=buf

print(respsm.is_chunked_ok())


respbuf=b'''
HTTP/1.1 200 OK
Bdpagetype: 3
Bdqid: 0x93fcce2f00007009
Cache-Control: private
Ckpacknum: 2
Ckrndstr: f00007009
Connection: Keep-Alive
Content-Encoding: gzip
Content-Type: text/html;charset=utf-8
Date: Mon, 06 May 2019 09:26:11 GMT
Server: BWS/1.1
Set-Cookie: delPer=0; path=/; domain=.baidu.com
Set-Cookie: BD_CK_SAM=1;path=/
Set-Cookie: PSINO=5; domain=.baidu.com; path=/
Set-Cookie: BDSVRTM=12; path=/
Set-Cookie: H_PS_PSSID=1445_21113_28774_28724_28964_28837_28584_26350_28701; path=/; domain=.baidu.com
Strict-Transport-Security: max-age=172800
Vary: Accept-Encoding
X-Ua-Compatible: IE=Edge,chrome=1
Transfer-Encoding: chunked

'''
