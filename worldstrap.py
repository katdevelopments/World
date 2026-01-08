import sys
import os
import subprocess
import ctypes
import site
import threading
import time
import tempfile
import shutil
import traceback

def global_exception_handler(exc_type, exc_value, exc_traceback):
    print("\n" + "="*60)
    print("CRITICAL UNHANDLED EXCEPTION")
    print("="*60)
    traceback.print_exception(exc_type, exc_value, exc_traceback)
    print("="*60)
    print("The application has crashed. See error above.")
    input("Press Enter to exit...")
    sys.exit(1)

sys.excepthook = global_exception_handler

def run_as_admin():
    print("[Startup] Checking permissions...")
    try:
        is_admin = (os.getuid() == 0)
    except AttributeError:
        try:
            is_admin = ctypes.windll.shell32.IsUserAnAdmin() != 0
        except Exception:
            is_admin = False

    if not is_admin:
        print("[Startup] Requesting elevation...")
        script_path = os.path.abspath(sys.argv[0])
        params = ' '.join([f'"{arg}"' for arg in sys.argv[1:]])
        
        try:
            if not script_path.endswith(".exe"):
                cmd = f'"{script_path}" {params}'
                ret = ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, cmd, None, 1)
            else:
                ret = ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, params, None, 1)
            
            if int(ret) > 32:
                print("[Startup] Elevation request sent. Exiting parent process.")
                sys.exit(0)
            else:
                print(f"[Startup] Failed to elevate privileges. Error code: {ret}")
                input("Press Enter to exit...")
                sys.exit(1)
        except Exception as e:
            print(f"[Startup] Elevation failed with exception: {e}")
            input("Press Enter to exit...")
            sys.exit(1)
    else:
        print("[Startup] Running with Admin privileges.")

def check_and_install_dependencies():
    print("[Startup] Checking dependencies...")
    user_site_packages = site.getusersitepackages()
    if user_site_packages not in sys.path:
        sys.path.append(user_site_packages)

    required_packages = {
        "customtkinter": "customtkinter",
        "requests": "requests",
        "PIL": "Pillow",
        "win32api": "pywin32"
    }
    
    needs_restart = False
    for import_name, package_name in required_packages.items():
        try:
            __import__(import_name)
        except ImportError:
            print(f"'{package_name}' (for {import_name}) not found. Installing...")
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", package_name])
                needs_restart = True
            except subprocess.CalledProcessError:
                print(f"FATAL: Failed to install {package_name}. Please install it manually.")
                input("Press Enter to exit...")
                sys.exit(1)
            except Exception as e:
                print(f"FATAL: Unexpected error installing {package_name}: {e}")
                input("Press Enter to exit...")
                sys.exit(1)

if __name__ == "__main__":
    run_as_admin()
    
    check_and_install_dependencies()

    print("[Startup] Loading libraries...")
    try:
        import customtkinter as ctk
        import requests
        from urllib3.exceptions import InsecureRequestWarning
        from tkinter import messagebox
        import tkinter as tk
        from PIL import Image, ImageTk
        
        import win32gui
        import win32ui
        import win32con
        import win32api
    except ImportError as e:
        print(f"Critical Import Error: {e}")
        print("Please restart the application.")
        input("Press Enter to exit...")
        sys.exit(1)

    class WorldstrapApp(ctk.CTk):
        VERSION_HASH_URL = "https://raw.githubusercontent.com/katdevelopments/World/refs/heads/main/compatibilityhash"
        WORLD_EXE_PATH = r"C:\Program Files (x86)\World\Release\world.exe"
        
        def __init__(self):
            super().__init__()
            print("[App] Initializing UI...")

            self.ROBLOX_INSTALL_PATH = self.get_roblox_install_path()
            self.is_closing = False

            self.title("World Strap Updater")
            self.geometry("500x350")
            self.minsize(400, 300)
            self.resizable(True, True)
            
            self.attributes("-alpha", 0.0)
            self.attributes("-topmost", True)
            
            ctk.set_appearance_mode("Dark")
            
            self.center_window()

            self.setup_ui()
            
            self.bind("<Configure>", self.on_resize)
            self.protocol("WM_DELETE_WINDOW", self.on_close)
            
            self.fade_in()
            self.start_process_thread()
            print("[App] UI Initialized.")

        def center_window(self):
            self.update_idletasks()
            width = self.winfo_width()
            height = self.winfo_height()
            x = (self.winfo_screenwidth() // 2) - (width // 2)
            y = (self.winfo_screenheight() // 2) - (height // 2)
            self.geometry(f'{width}x{height}+{x}+{y}')

        def setup_ui(self):
            self.canvas = ctk.CTkCanvas(self, highlightthickness=0)
            self.canvas.place(relx=0, rely=0, relwidth=1, relheight=1)

            self.main_frame = ctk.CTkFrame(self, fg_color="#1a1a1a", corner_radius=15, bg_color="transparent")
            self.main_frame.place(relx=0.5, rely=0.5, anchor="center", relwidth=0.85, relheight=0.8)

            self.content_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
            self.content_frame.pack(fill="both", expand=True, padx=20, pady=20)

            self.header_frame = ctk.CTkFrame(self.content_frame, fg_color="transparent")
            self.header_frame.pack(pady=(10, 20))

            self.world_icon = self.load_icon()
            self.icon_label = ctk.CTkLabel(self.header_frame, text="", image=self.world_icon)
            self.icon_label.pack(side="left", padx=(0, 15))

            self.title_label = ctk.CTkLabel(
                self.header_frame, 
                text="World Strap", 
                font=ctk.CTkFont(family="Segoe UI", size=32, weight="bold")
            )
            self.title_label.pack(side="left")

            self.status_label = ctk.CTkLabel(
                self.content_frame, 
                text="Initializing...", 
                font=ctk.CTkFont(family="Segoe UI", size=16),
                text_color="#E0E0E0"
            )
            self.status_label.pack(pady=(10, 5))

            self.progress_bar = ctk.CTkProgressBar(self.content_frame, width=350, height=12, corner_radius=6)
            self.progress_bar.set(0)
            self.progress_bar.pack(pady=15, fill="x")
            self.progress_bar.configure(progress_color="#3B8ED0")

            self.info_label = ctk.CTkLabel(
                self.content_frame, 
                text="", 
                font=ctk.CTkFont(family="Segoe UI", size=12), 
                text_color="#A0A0A0"
            )
            self.info_label.pack(side="bottom", pady=5)

        def on_resize(self, event):
            if event.widget == self:
                self.draw_gradient()

        def draw_gradient(self):
            width = self.winfo_width()
            height = self.winfo_height()
            
            self.canvas.delete("gradient")
            
            c1 = (10, 20, 40)
            c2 = (60, 80, 110)
            
            steps = 100
            
            for i in range(steps):
                r = int(c1[0] + (c2[0] - c1[0]) * i / steps)
                g = int(c1[1] + (c2[1] - c1[1]) * i / steps)
                b = int(c1[2] + (c2[2] - c1[2]) * i / steps)
                color_hex = f"#{r:02x}{g:02x}{b:02x}"
                
                y0 = i * (height / steps)
                y1 = (i + 1) * (height / steps)
                
                self.canvas.create_rectangle(
                    0, y0, width, y1 + 1, 
                    fill=color_hex, outline="", tags="gradient"
                )
                
            self.canvas.tag_lower("gradient")

        def load_icon(self):
            try:
                if os.path.exists(self.WORLD_EXE_PATH):
                    pil_img = self.extract_icon_as_pil(self.WORLD_EXE_PATH, size=(64, 64))
                    
                    if pil_img:
                        self.app_icon = ImageTk.PhotoImage(pil_img)
                        self.wm_iconphoto(False, self.app_icon)

                        return ctk.CTkImage(light_image=pil_img, size=(48, 48))
            except Exception as e:
                print(f"Icon load warning: {e}")
            return None

        def extract_icon_as_pil(self, exe_path, size=(32, 32)):
            try:
                large_icons, small_icons = win32gui.ExtractIconEx(exe_path, 0, 1)
                hicon = None
                
                if large_icons: 
                    hicon = large_icons[0]
                elif small_icons: 
                    hicon = small_icons[0]
                else: 
                    return None

                if large_icons:
                    for i in large_icons[1:]: win32gui.DestroyIcon(i)
                    if not hicon and large_icons: hicon = large_icons[0]
                if small_icons:
                    for i in small_icons: 
                        if i != hicon: win32gui.DestroyIcon(i)

                hdc = win32ui.CreateDCFromHandle(win32gui.GetDC(0))
                hbmp = win32ui.CreateBitmap()
                hbmp.CreateCompatibleBitmap(hdc, size[0], size[1])
                hmemdc = hdc.CreateCompatibleDC()
                hmemdc.SelectObject(hbmp)
                
                hmemdc.DrawIcon((0, 0), hicon)
                bmp_bits = hbmp.GetBitmapBits(True)
                
                img = Image.frombuffer(
                    'RGBA', 
                    (size[0], size[1]), 
                    bmp_bits, 'raw', 'BGRA', 0, 1
                )
                
                win32gui.DestroyIcon(hicon)
                hmemdc.DeleteDC()
                hdc.DeleteDC()
                win32gui.DeleteObject(hbmp.GetHandle())
                
                return img
            except Exception:
                return None

        def start_process_thread(self):
            thread = threading.Thread(target=self.run_update_process)
            thread.daemon = True
            thread.start()

        def thread_safe_update(self, func, *args):
            if not self.is_closing:
                self.after(0, lambda: func(*args))

        def update_ui_status(self, text, color=None, progress=None, info=None):
            if self.is_closing: return
            
            self.status_label.configure(text=text)
            if color:
                text_color = "#2ECC71" if color == "green" else "#E74C3C" if color == "red" else "#E0E0E0"
                self.status_label.configure(text_color=text_color)
            
            if progress is not None:
                self.progress_bar.set(progress)
                
            if info is not None:
                self.info_label.configure(text=info)

        def run_update_process(self):
            installer_path = None
            try:
                self.thread_safe_update(self.update_ui_status, "Checking API compatibility...", None, 0.1)
                time.sleep(0.5) 
                
                target_hash = self.get_target_version_hash()
                if not target_hash: return

                self.thread_safe_update(self.update_ui_status, f"Target: {target_hash[:8]}...", None, 0.2)
                
                if self.is_version_installed(target_hash):
                    self.thread_safe_update(self.update_ui_status, "Roblox is up to date!", "green", 1.0)
                    time.sleep(2)
                    self.thread_safe_update(self.close_app)
                    return

                self.thread_safe_update(self.update_ui_status, "Cleaning old versions...", None, 0.3)
                self.remove_outdated_versions(target_hash)

                self.thread_safe_update(self.update_ui_status, "Downloading update...", None, 0.4)
                installer_path = self.download_installer(target_hash)
                if not installer_path: return

                self.thread_safe_update(self.update_ui_status, "Installing...", None, 0.8, "Please wait, this may take a moment.")
                self.run_silent_installer(installer_path)

                self.thread_safe_update(self.update_ui_status, "Verifying...", None, 0.9)
                if self.is_version_installed(target_hash, verify=True):
                    self.thread_safe_update(self.update_ui_status, "Update Complete!", "green", 1.0)
                    time.sleep(2)
                    self.thread_safe_update(self.close_app)
                else:
                    self.thread_safe_update(self.handle_error, "Verification failed. Roblox may not have installed correctly.")

            except Exception as e:
                self.thread_safe_update(self.handle_error, f"Critical Error: {str(e)}")
            finally:
                if installer_path and os.path.exists(installer_path):
                    try: os.remove(installer_path)
                    except: pass

        def get_target_version_hash(self):
            try:
                requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)
                response = requests.get(self.VERSION_HASH_URL, verify=False, timeout=10)
                response.raise_for_status()
                return response.text.strip()
            except Exception as e:
                self.thread_safe_update(self.handle_error, f"Hash Check Failed: {e}")
                return None

        def download_installer(self, version_hash):
            url = f"https://setup.rbxcdn.com/version-{version_hash}-RobloxPlayerInstaller.exe"
            path = os.path.join(tempfile.gettempdir(), f"RobloxInstaller_{version_hash}.exe")
            
            try:
                with requests.get(url, stream=True, verify=False, timeout=300) as r:
                    r.raise_for_status()
                    total = int(r.headers.get('content-length', 0))
                    downloaded = 0
                    
                    with open(path, 'wb') as f:
                        for chunk in r.iter_content(8192):
                            if self.is_closing: return None
                            f.write(chunk)
                            downloaded += len(chunk)
                            if total > 0:
                                prog = 0.4 + (downloaded / total * 0.4)
                                mb_curr = downloaded / 1024 / 1024
                                mb_total = total / 1024 / 1024
                                if downloaded % (1024*128) == 0: 
                                    self.thread_safe_update(self.update_ui_status, "Downloading...", None, prog, f"{mb_curr:.1f}MB / {mb_total:.1f}MB")
                return path
            except Exception as e:
                self.thread_safe_update(self.handle_error, f"Download Error: {e}")
                return None

        def run_silent_installer(self, path):
            try:
                subprocess.run([path, "/quiet"], timeout=180, check=False)
                time.sleep(5)
                return True
            except Exception as e:
                print(f"Installer warning: {e}")
                return True

        def is_version_installed(self, version_hash, verify=False):
            folder = os.path.join(self.ROBLOX_INSTALL_PATH, f"version-{version_hash}")
            exe = os.path.join(folder, "RobloxPlayerBeta.exe")
            
            if verify:
                start = time.time()
                while time.time() - start < 60:
                    if os.path.exists(exe): return True
                    time.sleep(1)
                return False
            return os.path.exists(exe)

        def remove_outdated_versions(self, target_hash):
            if not os.path.exists(self.ROBLOX_INSTALL_PATH): return
            target_name = f"version-{target_hash}"
            
            for item in os.listdir(self.ROBLOX_INSTALL_PATH):
                if item.startswith("version-") and item != target_name:
                    try:
                        shutil.rmtree(os.path.join(self.ROBLOX_INSTALL_PATH, item))
                    except: pass

        def get_roblox_install_path(self):
            pf = os.environ.get("ProgramFiles(x86)", os.environ.get("ProgramFiles"))
            return os.path.join(pf, 'Roblox', 'Versions')

        def fade_in(self):
            try:
                alpha = self.attributes("-alpha")
                if alpha < 1.0:
                    self.attributes("-alpha", alpha + 0.05)
                    self.after(20, self.fade_in)
            except: pass

        def on_close(self):
            self.is_closing = True
            self.destroy()
            sys.exit(0)

        def close_app(self):
            self.is_closing = True
            try:
                alpha = self.attributes("-alpha")
                if alpha > 0.0:
                    self.attributes("-alpha", alpha - 0.1)
                    self.after(30, self.close_app)
                else:
                    self.destroy()
                    sys.exit(0)
            except:
                self.destroy()
                sys.exit(0)

        def handle_error(self, message):
            if not self.is_closing:
                messagebox.showerror("World Strap Error", str(message))
                self.close_app()

    print("[Startup] Starting application loop...")
    try:
        app = WorldstrapApp()
        app.mainloop()
    except Exception as e:
        print(f"CRITICAL ERROR IN MAINLOOP: {e}")
        input("Press Enter to exit...")
