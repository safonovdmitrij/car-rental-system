"""Local HTTPS acceptance configuration, without installing system trust."""


def local_tls_config(storage,https_port,backend_port):
    return {
        'admin':{'disabled':True,'config':{'persist':False}},
        'storage':{'module':'file_system','root':str(storage)},
        'logging':{'logs':{'default':{'level':'ERROR'}}},
        'apps':{
            'pki':{'certificate_authorities':{'local':{'install_trust':False}}},
            'tls':{'certificates':{'automate':['localhost']},'automation':{'policies':[{'subjects':['localhost'],'issuers':[{'module':'internal'}]}]}},
            'http':{'servers':{'api':{
                'listen':[f'127.0.0.1:{https_port}'],
                'automatic_https':{'disable_redirects':True},
                'tls_connection_policies':[{}],
                'routes':[{'handle':[{'handler':'reverse_proxy','upstreams':[{'dial':f'127.0.0.1:{backend_port}'}]}]}],
            }}},
        },
    }
