import tkinter as tk
from tkinter import ttk, filedialog
import threading
from meerko_bittorent.client import MeerkoClient

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Meerko Bittorent Client")
        self.geometry("470x500")
        self.client = None
        self.download_thread = None

        # Main frame
        main_frame = ttk.Frame(self, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Torrent source
        ttk.Label(main_frame, text="Torrent Source (file or magnet):").grid(row=0, column=0, sticky="w", pady=2)
        self.torrent_source_entry = ttk.Entry(main_frame, width=60)
        self.torrent_source_entry.grid(row=1, column=0, columnspan=2, sticky="ew", pady=2)
        self.browse_torrent_button = ttk.Button(main_frame, text="Browse...", command=self.browse_torrent)
        self.browse_torrent_button.grid(row=1, column=2, sticky="w", padx=5)

        # Save path
        ttk.Label(main_frame, text="Save Path:").grid(row=2, column=0, sticky="w", pady=2)
        self.save_path_entry = ttk.Entry(main_frame, width=60)
        self.save_path_entry.grid(row=3, column=0, columnspan=2, sticky="ew", pady=2)
        self.browse_save_path_button = ttk.Button(main_frame, text="Browse...", command=self.browse_save_path)
        self.browse_save_path_button.grid(row=3, column=2, sticky="w", padx=5)

        # Proxy settings (initially disabled)
        proxy_frame = ttk.LabelFrame(main_frame, text="Proxy Settings", padding="10")
        proxy_frame.grid(row=4, column=0, columnspan=3, sticky="ew", pady=10)
        
        self.proxy_enabled = tk.BooleanVar()
        self.proxy_check = ttk.Checkbutton(proxy_frame, text="Enable Proxy", variable=self.proxy_enabled, command=self.toggle_proxy_fields)
        self.proxy_check.grid(row=0, column=0, columnspan=2, sticky="w")

        ttk.Label(proxy_frame, text="Type:").grid(row=1, column=0, sticky="w", pady=2)
        self.proxy_type_entry = ttk.Entry(proxy_frame)
        self.proxy_type_entry.grid(row=1, column=1, sticky="ew", pady=2)

        ttk.Label(proxy_frame, text="Host:").grid(row=2, column=0, sticky="w", pady=2)
        self.proxy_host_entry = ttk.Entry(proxy_frame)
        self.proxy_host_entry.grid(row=2, column=1, sticky="ew", pady=2)

        ttk.Label(proxy_frame, text="Port:").grid(row=3, column=0, sticky="w", pady=2)
        self.proxy_port_entry = ttk.Entry(proxy_frame)
        self.proxy_port_entry.grid(row=3, column=1, sticky="ew", pady=2)
        
        ttk.Label(proxy_frame, text="Username:").grid(row=4, column=0, sticky="w", pady=2)
        self.proxy_user_entry = ttk.Entry(proxy_frame)
        self.proxy_user_entry.grid(row=4, column=1, sticky="ew", pady=2)

        ttk.Label(proxy_frame, text="Password:").grid(row=5, column=0, sticky="w", pady=2)
        self.proxy_pass_entry = ttk.Entry(proxy_frame, show="*")
        self.proxy_pass_entry.grid(row=5, column=1, sticky="ew", pady=2)

        self.toggle_proxy_fields()

        # Action buttons
        action_frame = ttk.Frame(main_frame)
        action_frame.grid(row=5, column=0, columnspan=3, pady=10)

        self.start_button = ttk.Button(action_frame, text="Start Download", command=self.start_download)
        self.start_button.pack(side="left", padx=5)
        self.stop_button = ttk.Button(action_frame, text="Stop", command=self.stop_download)
        self.stop_button.pack(side="left", padx=5)
        
        # Progress display
        progress_frame = ttk.LabelFrame(main_frame, text="Progress", padding="10")
        progress_frame.grid(row=6, column=0, columnspan=3, sticky="ew", pady=10)
        
        self.progress_label = ttk.Label(progress_frame, text="Status: Idle")
        self.progress_label.pack(fill=tk.X)
        self.progress_bar = ttk.Progressbar(progress_frame, orient="horizontal", length=100, mode="determinate")
        self.progress_bar.pack(fill=tk.X, pady=5)


    def browse_torrent(self):
        file_path = filedialog.askopenfilename(filetypes=[("Torrent files", "*.torrent"), ("All files", "*.*")])
        if file_path:
            self.torrent_source_entry.delete(0, tk.END)
            self.torrent_source_entry.insert(0, file_path)

    def browse_save_path(self):
        dir_path = filedialog.askdirectory()
        if dir_path:
            self.save_path_entry.delete(0, tk.END)
            self.save_path_entry.insert(0, dir_path)
            
    def toggle_proxy_fields(self):
        state = "normal" if self.proxy_enabled.get() else "disabled"
        self.proxy_type_entry.config(state=state)
        self.proxy_host_entry.config(state=state)
        self.proxy_port_entry.config(state=state)
        self.proxy_user_entry.config(state=state)
        self.proxy_pass_entry.config(state=state)

    def start_download(self):
        torrent_source = self.torrent_source_entry.get()
        save_path = self.save_path_entry.get()

        if not torrent_source or not save_path:
            # Or show a message box
            self.progress_label.config(text="Status: Torrent source and save path are required.")
            return

        proxy_settings = None
        if self.proxy_enabled.get():
            proxy_settings = {
                'type': self.proxy_type_entry.get(),
                'host': self.proxy_host_entry.get(),
                'port': int(self.proxy_port_entry.get()),
            }
            if self.proxy_user_entry.get() and self.proxy_pass_entry.get():
                proxy_settings['username'] = self.proxy_user_entry.get()
                proxy_settings['password'] = self.proxy_pass_entry.get()

        self.client = MeerkoClient(proxy_settings)
        self.download_thread = threading.Thread(target=self._download_thread, args=(torrent_source, save_path), daemon=True)
        self.download_thread.start()

    def _download_thread(self, torrent_source, save_path):
        for status in self.client.download(torrent_source, save_path):
            self.after(0, self._update_progress, status)
        self.after(0, self._on_download_complete)

    def _update_progress(self, status):
        state_str = ['queued', 'checking', 'downloading metadata', \
                     'downloading', 'finished', 'seeding', 'allocating', 'checking fastresume']
        
        self.progress_bar['value'] = status.progress * 100
        
        status_line = (
            f"Progress: {status.progress * 100:.2f}% | "
            f"Peers: {status.num_peers} | "
            f"Down: {status.download_rate / 1000:.2f} kB/s | "
            f"Up: {status.upload_rate / 1000:.2f} kB/s | "
            f"State: {state_str[status.state]}"
        )
        if status.is_seeding:
            share_ratio = (status.total_upload / status.total_wanted) if status.total_wanted > 0 else 0
            status_line += f" | Share Ratio: {share_ratio:.2f}"
            
        self.progress_label.config(text=status_line)

    def _on_download_complete(self):
        self.progress_label.config(text="Status: Download and seeding finished!")
        self.client = None

    def stop_download(self):
        if self.client:
            self.client.stop()

if __name__ == "__main__":
    app = App()
    app.mainloop()
