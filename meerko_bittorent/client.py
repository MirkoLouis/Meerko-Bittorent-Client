import libtorrent as lt
import time
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class MeerkoClient:
    def __init__(self, proxy_settings=None):
        # Initialize the libtorrent session
        self.ses = lt.session({'listen_interfaces': '0.0.0.0:6881'})
        self.apply_performance_settings()
        if proxy_settings:
            self.configure_proxy(proxy_settings)
        self.h = None
        self.running = False

    def apply_performance_settings(self):
        settings = self.ses.get_settings()
        # Enable UPnP and NAT-PMP for port forwarding
        settings['enable_upnp'] = True
        settings['enable_natpmp'] = True
        # Increase cache size to 256MB
        settings['cache_size'] = 16384  # 16384 * 16KB blocks = 256MB
        # Increase connections limit
        settings['connections_limit'] = 1000
        # Unlimited active downloads and seeds
        settings['active_downloads'] = 1
        settings['active_seeds'] = -1
        # Use rate_based_choker for choking algorithm
        settings['choking_algorithm'] = lt.choking_algorithm_t.rate_based_choker
        # Increase send buffer watermark
        settings['send_buffer_watermark'] = 500 * 1024
        self.ses.apply_settings(settings)
        logger.info("Performance settings applied.")

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
        self.running = True
        try:
            # Add the torrent
            if torrent_source.startswith('magnet:'):
                self.h = lt.add_magnet_uri(self.ses, torrent_source, {'save_path': save_path})
                logger.info("Fetching metadata from magnet link...")
                while not self.h.has_metadata():
                    if not self.running:
                        return
                    time.sleep(0.1)
                logger.info("Metadata received.")
            else:
                info = lt.torrent_info(torrent_source)
                self.h = self.ses.add_torrent({'ti': info, 'save_path': save_path})
            
            logger.info(f"Starting download for: {self.h.name()}")

            # Download and seed loop
            while self.running:
                s = self.h.status()
                
                # Check if seeding is complete (share ratio >= 1.0)
                if s.is_seeding and s.total_upload >= s.total_wanted:
                    logger.info("\nSeeding complete (1.0 ratio reached).")
                    break

                yield s
                time.sleep(1)

        except Exception as e:
            logger.error(f"An error occurred: {e}", exc_info=True)
        finally:
            if self.h:
                self.ses.remove_torrent(self.h)
            logger.info("Shutting down session.")
            self.running = False

    def stop(self):
        self.running = False