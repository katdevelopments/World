import sys
import os
import subprocess
import ctypes
import site # Add this import

def run_as_admin():
    """
    Checks if the script is running with admin privileges. If not, it re-launches
    itself with a UAC prompt and exits the current instance.
    """
    try:
        is_admin = (os.getuid() == 0)
    except AttributeError:
        is_admin = ctypes.windll.shell32.IsUserAnAdmin() != 0

    if not is_admin:
        ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, " ".join(sys.argv), None, 1)
        sys.exit(0)

def check_and_install_dependencies():
    """Checks for required packages and installs them if they are missing."""
    # --- FIX: Add user's site-packages to the Python path ---
    # This helps find modules even if the environment PATH is not set correctly,
    # a common issue with Microsoft Store versions of Python.
    user_site_packages = site.getusersitepackages()
    if user_site_packages not in sys.path:
        sys.path.append(user_site_packages)

    required_packages = {
        "customtkinter": "customtkinter",
        "requests": "requests",
    }
    for import_name, package_name in required_packages.items():
        try:
            __import__(import_name)
        except ImportError:
            print(f"'{package_name}' not found. Installing...")
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", package_name])
            except subprocess.CalledProcessError:
                print(f"FATAL: Failed to install {package_name}. Please install it manually.")
                sys.exit(1)

# --- Pre-flight Checks ---
if __name__ == "__main__":
    run_as_admin()
    check_and_install_dependencies()

# --- Main Application ---
import customtkinter as ctk
import requests
import shutil
import tempfile
import time
import threading
from urllib3.exceptions import InsecureRequestWarning
from tkinter import messagebox

class WorldstrapApp(ctk.CTk):
    VERSION_HASH_URL = "https://raw.githubusercontent.com/katdevelopments/World/refs/heads/main/compatibilityhash"
    
    def __init__(self):
        super().__init__()

        self.ROBLOX_INSTALL_PATH = self.get_roblox_install_path()

        # --- Window Configuration ---
        self.title("World Strap Updater")
        self.geometry("450x280")
        self.resizable(False, False)
        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("blue")

        # --- UI Elements ---
        self.setup_ui()
        
        # --- Start the main process ---
        self.start_process_thread()

    def get_roblox_install_path(self):
        program_files = os.environ.get("ProgramFiles(x86)", os.environ.get("ProgramFiles"))
        return os.path.join(program_files, 'Roblox', 'Versions')

    def setup_ui(self):
        """Creates and configures the user interface elements."""
        main_frame = ctk.CTkFrame(self)
        main_frame.pack(pady=20, padx=20, fill="both", expand=True)

        title_label = ctk.CTkLabel(main_frame, text="World Strap", font=ctk.CTkFont(size=32, weight="bold"))
        title_label.pack(pady=(10, 15))

        self.status_label = ctk.CTkLabel(main_frame, text="Initializing...", font=ctk.CTkFont(size=14))
        self.status_label.pack(pady=10)

        self.progress_bar = ctk.CTkProgressBar(main_frame, width=350)
        self.progress_bar.set(0)
        self.progress_bar.pack(pady=15)
        
        self.info_label = ctk.CTkLabel(main_frame, text="", font=ctk.CTkFont(size=12), text_color="gray")
        self.info_label.pack(pady=5)

    def start_process_thread(self):
        thread = threading.Thread(target=self.run_update_process)
        thread.daemon = True
        thread.start()

    def run_update_process(self):
        installer_path = None
        try:
            self.update_status("Checking API compatibility...")
            self.progress_bar.set(0.1)
            target_hash = self.get_target_version_hash()
            if not target_hash: return

            self.update_status(f"Required version: {target_hash[:12]}...")
            self.progress_bar.set(0.2)
            
            if self.is_version_installed(target_hash):
                self.update_status("Roblox is up to date.", "green")
                self.progress_bar.set(1.0)
                self.after(3000, self.close_app)
                return

            self.update_status("Managing API compatibility...")
            self.remove_outdated_versions(target_hash)

            self.update_status("Downloading compatibility update...")
            installer_path = self.download_installer(target_hash)
            if not installer_path: return

            self.update_status("Applying compatibility update...")
            self.progress_bar.set(0.8)
            if not self.run_silent_installer(installer_path): return

            self.update_status("Verifying update...")
            self.progress_bar.set(0.95)
            if self.is_version_installed(target_hash, verify=True):
                self.update_status("Update complete.", "green")
                self.progress_bar.set(1.0)
                self.after(3000, self.close_app)
            else:
                self.handle_error("Update failed. Could not find new version.")
        except Exception as e:
            self.handle_error(f"A critical error occurred: {e}")
        finally:
            if installer_path and os.path.exists(installer_path):
                os.remove(installer_path)

    def get_target_version_hash(self):
        try:
            requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)
            response = requests.get(self.VERSION_HASH_URL, verify=False, timeout=10)
            response.raise_for_status()
            return response.text.strip()
        except requests.RequestException as e:
            self.handle_error(f"Could not fetch compatibility hash: {e}")
            return None

    def download_installer(self, version_hash):
        url = f"https://setup.rbxcdn.com/version-{version_hash}-RobloxPlayerInstaller.exe"
        installer_path = os.path.join(tempfile.gettempdir(), f"RobloxInstaller_{version_hash}.exe")
        try:
            with requests.get(url, stream=True, verify=False, timeout=300) as r:
                r.raise_for_status()
                total_size = int(r.headers.get('content-length', 0))
                with open(installer_path, 'wb') as f:
                    bytes_downloaded = 0
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
                        bytes_downloaded += len(chunk)
                        if total_size > 0:
                            progress = (bytes_downloaded / total_size)
                            self.progress_bar.set(0.2 + (progress * 0.6))
                            self.info_label.configure(text=f"{bytes_downloaded/1024/1024:.1f} MB / {total_size/1024/1024:.1f} MB")
            self.info_label.configure(text="")
            return installer_path
        except requests.RequestException as e:
            self.handle_error(f"Download failed: {e}")
            return None

    def run_silent_installer(self, installer_path):
        try:
            # --- FIX: Removed check=True to prevent exit code errors ---
            subprocess.run([installer_path, "/quiet"], timeout=180)
            time.sleep(10)
            return True
        except Exception as e:
            self.handle_error(f"Installer failed: {e}")
            return False

    def is_version_installed(self, version_hash, verify=False):
        version_folder = os.path.join(self.ROBLOX_INSTALL_PATH, f"version-{version_hash}")
        target_exe = os.path.join(version_folder, "RobloxPlayerBeta.exe")
        if verify:
            timeout, start_time = 60, time.time()
            while not os.path.exists(target_exe):
                time.sleep(2)
                if time.time() - start_time > timeout: return False
        return os.path.exists(target_exe)
    
    def remove_outdated_versions(self, target_hash):
        if not os.path.exists(self.ROBLOX_INSTALL_PATH): return
        target_folder_name = f"version-{target_hash}"
        for item in os.listdir(self.ROBLOX_INSTALL_PATH):
            if item.startswith("version-") and item != target_folder_name:
                try:
                    shutil.rmtree(os.path.join(self.ROBLOX_INSTALL_PATH, item))
                except OSError: pass

    def close_app(self):
        """Fades the window out smoothly and then closes the application."""
        try:
            alpha = self.attributes("-alpha")
            if alpha > 0.1:
                alpha -= 0.1
                self.attributes("-alpha", alpha)
                self.after(20, self.close_app)
            else:
                self.destroy()
        except Exception:
            self.destroy()

    def update_status(self, message, color=None):
        self.status_label.configure(text=message)
        if color:
            self.status_label.configure(text_color=color)

    def show_error_dialog(self, message):
        messagebox.showerror("Error", message)
        self.update_status("An error occurred. Please close.", "red")
        self.after(5000, self.close_app)

    def handle_error(self, message):
        self.after(0, lambda: self.show_error_dialog(str(message)))

if __name__ == "__main__":
    try:
        app = WorldstrapApp()
        app.mainloop()
        sys.exit(0)
    except Exception as e:
        # Fallback for critical errors before the UI can even start
        try:
            root = ctk.CTk()
            root.withdraw()
            messagebox.showerror("Critical Error", f"A critical startup error occurred:\n\n{e}")
        except:
            print(f"A critical error occurred and the GUI could not be displayed: {e}")

