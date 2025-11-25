import configparser
import os
import libtorrent as lt

def load_proxy_settings():
    config_path = 'config.ini'
    if not os.path.exists(config_path):
        return None

    config = configparser.ConfigParser()
    config.read(config_path)

    proxy_settings = None
    if 'Proxy' in config:
        proxy_config = config['Proxy']
        
        # Check for required proxy settings
        if not all(k in proxy_config for k in ['type', 'host', 'port']):
            return None

        proxy_type_str = proxy_config.get('type', 'socks5').lower()
        proxy_type = lt.proxy_type_t.socks5
        if proxy_type_str == 'http':
            proxy_type = lt.proxy_type_t.http
        elif proxy_type_str == 'socks5_pw':
             proxy_type = lt.proxy_type_t.socks5_pw

        proxy_settings = {
            "type": proxy_type,
            "host": proxy_config.get('host'),
            "port": proxy_config.getint('port'),
        }
        if 'username' in proxy_config and 'password' in proxy_config:
            proxy_settings["username"] = proxy_config.get('username')
            proxy_settings["password"] = proxy_config.get('password')
    
    return proxy_settings