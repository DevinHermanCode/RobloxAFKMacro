#!C:\Users\devin\AppData\Local\Programs\Python\Python312\python.exe
from config import *

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
APPDATA_DIR = os.path.join(os.getenv("APPDATA"), "RobloxAFKMacro")
CONFIG_FILE = os.path.join(APPDATA_DIR, "afk_config.json")

def get_embedded_icon():
    try:
        image_data = base64.b64decode(icon_base64())
        return Image.open(BytesIO(image_data)).resize((64, 64), Image.Resampling.LANCZOS)
    except Exception as e:
        print(f"Failed to load tray icon: {e}")
        return Image.new("RGB", (64, 64), "black")

class ToolTip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tipwindow = None
        self.widget.bind("<Enter>", self.show_tip)
        self.widget.bind("<Leave>", self.hide_tip)

    def show_tip(self, event=None):
        if self.tipwindow or not self.text:
            return
        x, y, _cx, cy = self.widget.bbox("insert")
        x += self.widget.winfo_rootx() + 25
        y += self.widget.winfo_rooty() + cy + 20
        self.tipwindow = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        label = tk.Label(tw, text=self.text, justify='left', background="lightyellow", relief='solid', borderwidth=1, font=("tahoma", "8", "normal"))
        label.pack(ipadx=1)

    def hide_tip(self, event=None):
        if self.tipwindow:
            self.tipwindow.destroy()
            self.tipwindow = None

class KeyLooper:
    def __init__(self, key, interval=1.0):
        self.key = key
        self.interval = interval
        self.running = Event()
        self.thread = Thread(target=self._loop)
        self.thread.daemon = True
        self.thread.start()

    def _loop(self):
        while True:
            self.running.wait()
            if is_roblox_focused():
                keyboard.send(self.key)
            time.sleep(self.interval)

    def start(self):
        self.running.set()

    def stop(self):
        self.running.clear()

    def toggle(self):
        if self.running.is_set():
            self.stop()
        else:
            self.start()

    def is_running(self):
        return self.running.is_set()

def is_roblox_focused():
    hwnd = win32gui.GetForegroundWindow()
    try:
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        exe = psutil.Process(pid).name().lower()
        return exe == "robloxplayerbeta.exe"
    except Exception:
        return False

class AFKGui:
    def __init__(self):
        self.root = tk.Tk()
        try:
            image_data = base64.b64decode(icon_base64())
            pil_image = Image.open(BytesIO(image_data))
            icon_tk = ImageTk.PhotoImage(pil_image)
            self.root.iconphoto(False, icon_tk)
            self._icon_ref = icon_tk  # prevent garbage collection
        except Exception as e:
            print(f"Error setting window icon: {e}")

        self.root.title("Yet Another Roblox AFK Macro")
        self.root.geometry("460x580")
        self.root.configure(bg="#1e1e1e")
        self.root.attributes("-topmost", True)

        self.key_loopers = {}
        self.interval_mapping = {}
        self.toggle_buttons = {}

        self.roblox_status = tk.StringVar(value="Roblox Not Focused")
        self.roblox_label = tk.Label(self.root, textvariable=self.roblox_status, font=("Arial", 10), fg="gray", bg="#1e1e1e")
        self.roblox_label.pack(pady=5)

        self.instructions = tk.Label(self.root, text="Assign keys and interval.", font=("Arial", 12), fg="white", bg="#1e1e1e")
        self.instructions.pack(pady=5)

        self.key_frame = tk.Frame(self.root, bg="#1e1e1e")
        self.key_frame.pack(pady=10)

        self.key_var = tk.StringVar()

        self.key_btn = tk.Button(self.key_frame, text="Set Key", command=self.capture_key, width=10)
        self.key_btn.grid(row=1, column=0, padx=5)
        ToolTip(self.key_btn, "Click and press a single key to set the looped key")

        tk.Label(self.key_frame, text="Interval (s):", fg="white", bg="#1e1e1e").grid(row=0, column=1, padx=5)
        self.interval_entry = tk.Entry(self.key_frame, width=10)
        self.interval_entry.grid(row=1, column=1, padx=5)

        self.auto_start = tk.IntVar()
        self.auto_start_check = tk.Checkbutton(
            self.key_frame,
            text="Auto-start",
            variable=self.auto_start,
            bg="#1e1e1e",
            fg="white",
            selectcolor="#1e1e1e",
            command=self.save_config  # 👈 bind toggle to save
        )
        self.auto_start_check.grid(row=1, column=2, padx=5)

        self.add_btn = tk.Button(self.key_frame, text="Add Key", command=self.add_key, bg="#007acc", fg="white", width=10)
        self.add_btn.grid(row=1, column=3, padx=5)

        # was used mostly for testing - text="" left blank cus lazy | orginally text="Config Saved!" but was removed
        # removing this properly requires some other save function changes; cant be bothered
        self.save_label = tk.Label(self.root, text="", fg="lime", bg="#1e1e1e", font=("Arial", 10))
        self.save_label.place_forget()

        tk.Label(self.root, text="Configured Keys:", fg="white", bg="#1e1e1e").pack()

        self.canvas_frame = tk.Frame(self.root, bg="#1e1e1e")
        self.canvas_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        self.canvas = tk.Canvas(self.canvas_frame, bg="#1e1e1e", highlightthickness=0)
        self.scrollbar = tk.Scrollbar(self.canvas_frame, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = tk.Frame(self.canvas, bg="#1e1e1e")

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(
                scrollregion=self.canvas.bbox("all")
            )
        )

        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        # Mousewheel scroll binding (cross-platform)
        def _on_mousewheel(event):
            self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        self.canvas.bind_all("<MouseWheel>", _on_mousewheel)  # Windows/macOS
        self.canvas.bind_all("<Button-4>", lambda e: self.canvas.yview_scroll(-1, "units"))  # Linux scroll up
        self.canvas.bind_all("<Button-5>", lambda e: self.canvas.yview_scroll(1, "units"))   # Linux scroll down

        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        self.toggle_frame = tk.Frame(self.scrollable_frame, bg="#1e1e1e")
        self.toggle_frame.grid(row=0, column=1, sticky="nsew", padx=(5, 0))

        self.button_frame = tk.Frame(self.root, bg="#1e1e1e")
        self.button_frame.pack(side="bottom", fill="x", pady=10, padx=10)

        # Bottom button row
        self.disable_all_btn = tk.Button(
            self.button_frame, text="Disable All",
            command=self.disable_all,
            bg="#444", fg="white"
        )
        self.disable_all_btn.grid(row=0, column=0, sticky="w")

        self.help_btn = tk.Button(
            self.button_frame, text="?", width=3,
            command=self.show_config_path,
            bg="#444", fg="white"
        )
        self.help_btn.grid(row=0, column=1)

        self.readme_btn = tk.Button(
            self.button_frame, text="READ ME",
            command=self.show_readme,
            bg="#444", fg="white"
        )
        self.readme_btn.grid(row=0, column=2, sticky="e")

        # Center column weight for alignment
        self.button_frame.grid_columnconfigure(0, weight=1)
        self.button_frame.grid_columnconfigure(1, weight=0)
        self.button_frame.grid_columnconfigure(2, weight=1)

        self.root.protocol("WM_DELETE_WINDOW", self.quit_app)
        self.root.after(500, self.update_roblox_focus)
        os.makedirs(APPDATA_DIR, exist_ok=True)
        self.load_config()
        self.setup_tray_icon()

    def disable_all(self):
        for looper in self.key_loopers.values():
            looper.stop()
        for btn in self.toggle_buttons.values():
            btn.config(bg="gray")
        self.save_config()
        
    def show_config_path(self):
        path = CONFIG_FILE
        response = messagebox.askyesno(
            "Config File Location",
            f"Your config is stored at:\n\n{path}\n\nOpen folder?"
        )
        if response:
            os.startfile(os.path.dirname(path))

    def show_readme(self):
        instructions = (
            "This is Yet Another Roblox AFK Macro!\n\n"
            "- Use 'Set Key' to select a key to loop.\n"
            "- Enter a delay interval in seconds.\n"
            "- Click 'Add Key' to start tracking.\n"
            "- Use the buttons to toggle key loops on/off.\n"
            "- To remove a key, press the red X button next to it.\n"
            "- The script will automatically save your settings on each UI interaction.\n"
            "- Checking 'Auto-start' will start the key loop immediately after adding.\n"
            "- 'Disable All' turns off every active loop.\n"
            "- Check your config file location with the '?' button.\n\n"
            "Delete afk_config.json to wipe keys.\n\n"
            "The script will only press keys when Roblox is the active window for user protection.\n"
            "Warning: Includes the roblox home app"
        )
        messagebox.showinfo("Instructions", instructions)
        
    def capture_key(self):
        def worker():
            self.key_btn.config(text="Press key...")
            self.root.update()
            try:
                combo = keyboard.read_event(suppress=True)
                while combo.name == "enter":
                    combo = keyboard.read_event(suppress=True)
                if combo.event_type == "down":
                    key = combo.name
                    self.root.after(0, lambda: (
                        self.key_var.set(key.lower()),
                        self.key_btn.config(text=f"Key: {key.lower()}")
                    ))
            except:
                self.root.after(0, lambda: (
                    self.key_var.set(""),
                    self.key_btn.config(text="Set Key")
                ))

        Thread(target=worker, daemon=True).start()

    def add_key(self):
        key = self.key_var.get().strip().lower()
        interval_str = self.interval_entry.get().strip()

        if not key or not interval_str:
            messagebox.showwarning("Input Error", "Key and interval are required.")
            return

        try:
            interval = float(interval_str)
            if interval <= 0:
                raise ValueError
        except ValueError:
            messagebox.showwarning("Input Error", "Interval must be a positive number.")
            return

        if key in self.key_loopers:
            messagebox.showwarning("Duplicate Key", f"Key '{key}' is already assigned.")
            return

        looper = KeyLooper(key, interval)
        self.key_loopers[key] = looper
        self.interval_mapping[key] = interval

        row_index = len(self.toggle_buttons)

        # Key label
        key_label = tk.Label(self.scrollable_frame, text=f"{key} | {interval}s", bg="#2e2e2e", fg="white", anchor="w", width=30)
        key_label.grid(row=row_index, column=0, sticky="w", pady=4, padx=(5, 0))

        # Toggle button
        toggle_btn = tk.Button(self.scrollable_frame, text="ON/OFF", width=6, bg="gray", fg="white", relief="raised",
                            command=lambda k=key: self.toggle_key(k))
        toggle_btn.grid(row=row_index, column=1, padx=5, pady=4)
        self.toggle_buttons[key] = toggle_btn

        # ❌ Remove button
        remove_btn = tk.Button(self.scrollable_frame, text="❌", width=3, bg="#cc3300", fg="white",
                            command=lambda k=key: self.remove_key_direct(k))
        remove_btn.grid(row=row_index, column=2, padx=(0, 5), pady=4)

        if self.auto_start.get():
            looper.start()
            toggle_btn.config(bg="green")

        self.save_config()
        self.key_var.set("")
        self.key_btn.config(text="Set Key")
        self.interval_entry.delete(0, tk.END)

    def remove_key_direct(self, key):
        if key in self.key_loopers:
            self.key_loopers[key].stop()
            del self.key_loopers[key]
            del self.interval_mapping[key]
            if key in self.toggle_buttons:
                self.toggle_buttons[key].destroy()
                del self.toggle_buttons[key]
        self.update_display()
        self.save_config()

    def toggle_key(self, key):
        if key not in self.key_loopers:
            return
        looper = self.key_loopers[key]
        looper.toggle()
        self.toggle_buttons[key].config(bg="green" if looper.is_running() else "gray")
        self.save_config()

    def update_roblox_focus(self):
        if is_roblox_focused():
            self.roblox_status.set("Roblox Focused")
            self.roblox_label.config(fg="green")
        else:
            self.roblox_status.set("Roblox Not Focused")
            self.roblox_label.config(fg="gray")
        self.root.after(500, self.update_roblox_focus)

    def update_display(self):
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()

        self.toggle_buttons.clear()

        for i, key in enumerate(self.interval_mapping):
            interval = self.interval_mapping[key]
            looper = self.key_loopers.get(key)
            if not looper:
                looper = KeyLooper(key, interval)
                self.key_loopers[key] = looper

            label = tk.Label(self.scrollable_frame, text=f"{key} | {interval}s", bg="#2e2e2e", fg="white", anchor="w", width=30)
            label.grid(row=i, column=0, sticky="w", padx=(5, 0), pady=4)

            toggle_btn = tk.Button(self.scrollable_frame, text="ON/OFF", width=6,
                                bg="green" if looper.is_running() else "gray", fg="white",
                                command=lambda k=key: self.toggle_key(k))
            toggle_btn.grid(row=i, column=1, padx=5, pady=4)
            self.toggle_buttons[key] = toggle_btn

            remove_btn = tk.Button(self.scrollable_frame, text="❌", width=3, bg="#cc3300", fg="white",
                                command=lambda k=key: self.remove_key_direct(k))
            remove_btn.grid(row=i, column=2, padx=(0, 5), pady=4)

    def save_config(self):
        try:
            with open(CONFIG_FILE, 'w') as f:
                json.dump({
                    "intervals": self.interval_mapping,
                    "auto_start": self.auto_start.get()
                }, f)
            self.save_label.place(relx=0.5, rely=0.88, anchor='center')
            self.save_label.lift()
            self.root.after(1500, self.save_label.place_forget)
        except Exception as e:
            messagebox.showerror("Save Error", f"Failed to save config: {e}")

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    data = json.load(f)
                self.interval_mapping = data.get("intervals", {})
                auto_start_value = 1 if data.get("auto_start", True) else 0
                self.auto_start.set(auto_start_value)
                if auto_start_value:
                    self.auto_start_check.select()
                else:
                    self.auto_start_check.deselect()
                self.key_loopers.clear()
                self.toggle_buttons.clear()
                self.update_display()
            except Exception as e:
                messagebox.showerror("Load Error", f"Failed to load config: {e}")

    def hide_window(self):
        self.root.withdraw()

    def show_window(self, icon, item):
        self.root.deiconify()

    def quit_app(self, icon=None, item=None):
        if hasattr(self, 'icon') and self.icon:
            self.icon.visible = False # cleans up the icon in system tray
            self.icon.stop()
        self.root.quit()

    def setup_tray_icon(self):
        image = get_embedded_icon()

        menu = (
            pystray.MenuItem("Show", self.show_window),
            pystray.MenuItem("Quit", self.quit_app),
        )

        self.icon = pystray.Icon("roblox_afk", image, "Roblox AFK Macro", menu)
        thread = Thread(target=self.icon.run, daemon=True)
        thread.start()

    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    gui = AFKGui()
    gui.run()
