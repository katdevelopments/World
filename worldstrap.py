import sys
import os
import subprocess
import ctypes
import site

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
    user_site_packages = site.getusersitepackages()
    if user_site_packages not in sys.path:
        sys.path.append(user_site_packages)

    required_packages = {
        "customtkinter": "customtkinter",
        "requests": "requests",
        "PIL": "Pillow",
        "win32api": "pywin32" # Added for Windows icon extraction
    }
    for import_name, package_name in required_packages.items():
        try:
            __import__(import_name)
        except ImportError:
            print(f"'{package_name}' (for {import_name}) not found. Installing...")
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
import io
# import base64 # No longer needed
from urllib3.exceptions import InsecureRequestWarning
from tkinter import messagebox
from PIL import Image, ImageTk

# Import windows modules for icon extraction
try:
    import win32gui
    import win32ui
    import win32con
    import win32api
except ImportError:
    # The dependency checker should have caught this, but as a safeguard:
    print("FATAL: pywin32 libraries not found. Please run: pip install pywin32")
    # We can't use messagebox here as tkinter isn't fully init'd
    sys.exit(1)


class WorldstrapApp(ctk.CTk):
    VERSION_HASH_URL = "https://raw.githubusercontent.com/katdevelopments/World/refs/heads/main/compatibilityhash"
    # Path to the executable from which to extract the icon
    WORLD_EXE_PATH = r"C:\Program Files (x86)\World\Release\world.exe"
    
    def __init__(self):
        super().__init__()

        self.ROBLOX_INSTALL_PATH = self.get_roblox_install_path()
        # self.temp_icon_path = None # No longer needed

        # --- Window Configuration ---
        self.title("World Strap Updater")
        self.geometry("480x320")
        self.resizable(True, True) # Allow the window to be resized
        # self.overrideredirect(True) # Removed to allow dragging via title bar
        self.attributes("-alpha", 0.0) # Start transparent for fade-in
        self.attributes("-topmost", True)
        
        # Center the window
        self.center_window()

        # --- UI Elements ---
        self.setup_ui()
        
        # --- Start the main process ---
        self.fade_in()
        self.start_process_thread()

    def center_window(self):
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f'{width}x{height}+{x}+{y}')

    def extract_icon_as_pil(self, exe_path, size=(32, 32)):
        """Extracts the icon from an executable and returns it as a PIL Image."""
        try:
            # Extract large icon (index 0)
            large_icons, small_icons = win32gui.ExtractIconEx(exe_path, 0, 1)
            
            if not large_icons:
                if not small_icons:
                    print(f"Error: No icons found in {exe_path}.")
                    return None
                print("Warning: No large icon found, using small icon.")
                hicon = small_icons[0]
                ico_x = win32api.GetSystemMetrics(win32con.SM_CXSMICON)
                ico_y = win32api.GetSystemMetrics(win32con.SM_CYSMICON)
                # Clean up other icons
                for icon in large_icons: win32gui.DestroyIcon(icon)
                for i, icon in enumerate(small_icons):
                    if i != 0: win32gui.DestroyIcon(icon)
            else:
                hicon = large_icons[0]
                ico_x = win32api.GetSystemMetrics(win32con.SM_CXICON)
                ico_y = win32api.GetSystemMetrics(win32con.SM_CYICON)
                # Clean up other icons
                for i, icon in enumerate(large_icons):
                    if i != 0: win32gui.DestroyIcon(icon)
                for icon in small_icons: win32gui.DestroyIcon(icon)
            
            # Create a device context
            hdc = win32ui.CreateDCFromHandle(win32gui.GetDC(0))
            hbmp = win32ui.CreateBitmap()
            hbmp.CreateCompatibleBitmap(hdc, ico_x, ico_y)
            hmemdc = hdc.CreateCompatibleDC()
            
            hmemdc.SelectObject(hbmp)
            
            # Draw the icon
            hmemdc.DrawIcon((0, 0), hicon)
            
            # Get bitmap bits
            bmp_bits = hbmp.GetBitmapBits(True)
            
            # Create PIL image
            img = Image.frombuffer(
                'RGBA',
                (ico_x, ico_y),
                bmp_bits,
                'raw',
                'BGRA',
                0,
                1
            )
            
            # Clean up
            win32gui.DestroyIcon(hicon)
            hmemdc.DeleteDC()
            hdc.DeleteDC()
            win32gui.DeleteObject(hbmp.GetHandle())

            if size != (ico_x, ico_y):
                 img = img.resize(size, Image.Resampling.LANCZOS)

            return img
            
        except Exception as e:
            print(f"Failed to extract icon from {self.WORLD_EXE_PATH}: {e}")
            # Clean up just in case
            try: win32gui.DestroyIcon(hicon)
            except: pass
            try: hmemdc.DeleteDC()
            except: pass
            try: hdc.DeleteDC()
            except: pass
            return None

    def setup_ui(self):
        """Creates and configures the visually enhanced user interface."""
        # --- Background Gradient ---
        self.canvas = ctk.CTkCanvas(self, width=480, height=320, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)

        # Create gradient
        gradient_colors = ["#0d1b2a", "#1b263b", "#415a77"]
        for i, color in enumerate(gradient_colors):
            self.canvas.create_rectangle(0, i*107, 480, (i+1)*107, fill=color, outline="")

        # --- Glassmorphism Frame ---
        main_frame = ctk.CTkFrame(self, fg_color="transparent")
        main_frame.place(relx=0.5, rely=0.5, anchor="center")

        # --- Icon and Title ---
        title_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        title_frame.pack(pady=(20, 10))
        
        try:
            # --- NEW ICON LOGIC ---
            if not os.path.exists(self.WORLD_EXE_PATH):
                print(f"Warning: Icon path not found: {self.WORLD_EXE_PATH}")
                raise FileNotFoundError("World.exe not found at specified path")

            icon_image = self.extract_icon_as_pil(self.WORLD_EXE_PATH, size=(32, 32))
            
            if icon_image:
                self.world_icon = ctk.CTkImage(light_image=icon_image, size=(32, 32))
                
                icon_label = ctk.CTkLabel(title_frame, text="", image=self.world_icon)
                icon_label.pack(side="left", padx=(0, 10))
            else:
                print("Warning: Could not extract icon. Continuing without it.")
            # --- END NEW ICON LOGIC ---

        except Exception as e:
            print(f"Warning: Could not load application icon. Continuing without it. Error: {e}")
            # No temp file to clean up anymore

        title_label = ctk.CTkLabel(title_frame, text="World Strap", font=ctk.CTkFont(family="Segoe UI", size=36, weight="bold"))
        title_label.pack(side="left")

        self.status_label = ctk.CTkLabel(main_frame, text="Initializing...", font=ctk.CTkFont(family="Segoe UI", size=16))
        self.status_label.pack(pady=20)

        self.progress_bar = ctk.CTkProgressBar(main_frame, width=400, height=10)
        self.progress_bar.set(0)
        self.progress_bar.pack(pady=15)
        
        self.info_label = ctk.CTkLabel(main_frame, text="", font=ctk.CTkFont(family="Segoe UI", size=12), text_color="#A9A9A9")
        self.info_label.pack(pady=10)

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
            self.run_silent_installer(installer_path)

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
            subprocess.run([installer_path, "/quiet"], timeout=180)
            time.sleep(10)
            return True
        except Exception as e:
            # We ignore errors here as per the user's request
            print(f"Installer may have finished with a non-zero exit code, proceeding anyway. Details: {e}")
            return True


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

    def fade_in(self):
        alpha = self.attributes("-alpha")
        if alpha < 1.0:
            alpha += 0.05
            self.attributes("-alpha", alpha)
            self.after(15, self.fade_in)

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

    def get_roblox_install_path(self):
        program_files = os.environ.get("ProgramFiles(x86)", os.environ.get("ProgramFiles"))
        return os.path.join(program_files, 'Roblox', 'Versions')

    def update_status(self, message, color=None):
        self.status_label.configure(text=message)
        if color == "green":
            self.status_label.configure(text_color="#2ECC71")
        elif color == "red":
            self.status_label.configure(text_color="#E74C3C")
        else:
            self.status_label.configure(text_color="white")


    def show_error_dialog(self, message):
        messagebox.showerror("Error", message)
        self.update_status("An error occurred. Exiting.", "red")
        self.after(3000, self.close_app)

    def handle_error(self, message):
        self.after(0, lambda: self.show_error_dialog(str(message)))

if __name__ == "__main__":
    try:
        app = WorldstrapApp()
        app.mainloop()
        sys.exit(0)
    except Exception as e:
        # --- FIX: Use standard tkinter for the final error message to prevent crashing ---
        try:
            import tkinter as tk
            from tkinter import messagebox
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror("Critical Error", f"A critical startup error occurred:\n\n{e}")
        except ImportError:
            # Fallback for systems without even basic tkinter
            print(f"A critical error occurred and the GUI could not be displayed: {e}")
