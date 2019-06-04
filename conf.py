from os import path
client_password='soulapp123!@#1'
convert_p12topem_cmd='pkcs12 -clcerts -nokeys -out soul_client.pem -in soul_client.p12 -password pass:soulapp123!@#1'
clientcert=path.join(path.abspath(path.dirname(__file__)),'certs','soul_client.pem')
servercert=path.join(path.abspath(path.dirname(__file__)),'certs','sn_new_server.crt')
serverkey=path.join(path.abspath(path.dirname(__file__)),'certs','sn_new_server_key.pem')
unsupport=[
        b'e.crashlytics.com',
        b'ssac.suning.com',
        b'pancake.apple.com',
        b'p29-buy.itunes.apple.com',
        b'gsp64-ssl.ls.apple.com'
    ]