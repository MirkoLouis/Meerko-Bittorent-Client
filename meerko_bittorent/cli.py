import argparse
import libtorrent as lt
from meerko_bittorent.client import MeerkoClient
from meerko_bittorent.config import load_proxy_settings

def main():
    # Load default proxy settings from config file
    proxy_settings = load_proxy_settings()

    parser = argparse.ArgumentParser(description="Meerko Bittorent Client")
    parser.add_argument("torrent_source", help="Path to the .torrent file or a magnet link")
    parser.add_argument("save_path", help="Path to the directory to save the files")

    # Proxy arguments
    parser.add_argument("--proxy-type", help="Proxy type (e.g., socks5, http)", dest="proxy_type")
    parser.add_argument("--proxy-host", help="Proxy host", dest="proxy_host")
    parser.add_argument("--proxy-port", help="Proxy port", dest="proxy_port", type=int)
    parser.add_argument("--proxy-user", help="Proxy username", dest="proxy_user")
    parser.add_argument("--proxy-pass", help="Proxy password", dest="proxy_pass")
    parser.add_argument("--no-proxy", help="Disable proxy even if configured", action="store_true")


    args = parser.parse_args()

    # Override config with command-line arguments
    if args.no_proxy:
        proxy_settings = None
    elif args.proxy_type and args.proxy_host and args.proxy_port:
        proxy_settings = {
            "type": lt.proxy_type_t.socks5 if args.proxy_type.lower() == 'socks5' else lt.proxy_type_t.http,
            "host": args.proxy_host,
            "port": args.proxy_port,
        }
        if args.proxy_user and args.proxy_pass:
            proxy_settings["username"] = args.proxy_user
            proxy_settings["password"] = args.proxy_pass

    client = MeerkoClient(proxy_settings=proxy_settings)
    client.download(args.torrent_source, args.save_path)

if __name__ == "__main__":
    main()