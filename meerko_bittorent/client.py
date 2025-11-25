import libtorrent as lt
import time
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class MeerkoClient:
    def __init__(self, proxy_settings=None):
        # Initialize the libtorrent session
        self.ses = lt.session({'listen_interfaces': '0.0.0.0:6881'})
        if proxy_settings:
            self.configure_proxy(proxy_settings)

    def configure_proxy(self, proxy_settings):
        # Apply proxy settings to the session
        settings = self.ses.get_settings()
        settings['proxy_type'] = proxy_settings['type']
        settings['proxy_hostname'] = proxy_settings['host']
        settings['proxy_port'] = proxy_settings['port']
        if 'username' in proxy_settings and 'password' in proxy_settings:
            settings['proxy_username'] = proxy_settings['username']
            settings['proxy_password'] = proxy_settings['password']
        # Force proxy for all connections
        settings['force_proxy'] = True
        settings['anonymous_mode'] = True
        self.ses.apply_settings(settings)
        logger.info("Proxy configured.")

    def download(self, torrent_source, save_path):
        h = None # Initialize h to None
        try:
            # Add the torrent
            if torrent_source.startswith('magnet:'):
                h = lt.add_magnet_uri(self.ses, torrent_source, {'save_path': save_path})
                logger.info("Fetching metadata from magnet link...")
                while not h.has_metadata():
                    time.sleep(1)
                logger.info("Metadata received.")
            else:
                info = lt.torrent_info(torrent_source)
                h = self.ses.add_torrent({'ti': info, 'save_path': save_path})
            
            logger.info(f"Starting download for: {h.name()}")

            # Download and seed loop
            while True:
                s = h.status()
                state_str = ['queued', 'checking', 'downloading metadata', \
                        'downloading', 'finished', 'seeding', 'allocating', 'checking fastresume']

                # Check if seeding is complete (share ratio >= 1.0)
                if s.is_seeding and s.total_upload >= s.total_wanted:
                    logger.info("\nSeeding complete (1.0 ratio reached).")
                    break

                status_line = (
                    f"Progress: {s.progress * 100:.2f}% | "
                    f"Peers: {s.num_peers} | "
                    f"Down: {s.download_rate / 1000:.2f} kB/s | "
                    f"Up: {s.upload_rate / 1000:.2f} kB/s | "
                    f"State: {state_str[s.state]}"
                )
                if s.is_seeding:
                    share_ratio = (s.total_upload / s.total_wanted) if s.total_wanted > 0 else 0
                    status_line += f" | Share Ratio: {share_ratio:.2f}"

                print(status_line, end='\r')
                time.sleep(1)

            logger.info("\nDownload and seeding process finished!")

        except KeyboardInterrupt:
            logger.info("\nProcess interrupted by user (Ctrl+C).")
            if h:
                self.ses.remove_torrent(h)
                logger.info("Torrent removed from session.")
        except Exception as e:
            logger.error(f"An error occurred: {e}", exc_info=True)
        finally:
            logger.info("Shutting down session.")