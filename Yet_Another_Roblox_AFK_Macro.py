#!C:\Users\devin\AppData\Local\Programs\Python\Python312\python.exe
from config import *

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
    def __init__(self, key, interval=1.0, hold_duration=None):
        self.key = key
        self.interval = interval
        self.hold_duration = hold_duration
        self.running = Event()
        self.thread = Thread(target=self._loop)
        self.thread.daemon = True
        self.thread.start()

    def _loop(self):
        while True:
            self.running.wait()
            if is_roblox_focused():
                keyboard.press(self.key)
                if self.hold_duration:
                    time.sleep(self.hold_duration)
                    keyboard.release(self.key)
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
        check_for_updates()
        self.root = tk.Tk()
        # anywhere you click that isn't an Entry will defocus
        self.root.bind("<Button-1>", self._defocus_if_not_entry)
        try:
            image_data = base64.b64decode(icon_base64())
            pil_image = Image.open(BytesIO(image_data))
            icon_tk = ImageTk.PhotoImage(pil_image)
            self.root.iconphoto(False, icon_tk)
            self._icon_ref = icon_tk  # prevent garbage collection
        except Exception as e:
            print(f"Error setting window icon: {e}")
        self.key_labels = {}
        self.toggle_buttons = {}
        self.remove_buttons = {}

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

        # Interval text box and title
        tk.Label(self.key_frame, text="Interval (s):", fg="white", bg="#1e1e1e") \
            .grid(row=0, column=1, padx=5)

        self.interval_entry = tk.Entry(
            self.key_frame,
            width=10,
            fg="white",                # user text color
            bg="#1e1e1e",              # dark background
            insertbackground="white"   # caret color
        )
        self.interval_entry.grid(row=1, column=1, padx=5)

        # Hold(s) text box and title
        tk.Label(self.key_frame, text="Hold (s):", fg="white", bg="#1e1e1e").grid(row=0, column=2, padx=5)
        self.hold_entry = tk.Entry(
            self.key_frame,
            width=10,
            fg="gray",                 # placeholder color
            bg="#1e1e1e",              # match your dark bg
            insertbackground="white"   # cursor color
        )       
        self._set_placeholder_if_empty(self.hold_entry, "(optional)")
        self.hold_entry.bind("<FocusIn>", lambda e: self._clear_placeholder(self.hold_entry, "(optional)"))
        self.hold_entry.bind("<FocusOut>", lambda e: self._set_placeholder_if_empty(self.hold_entry, "(optional)"))
        self.hold_entry.bind("<KeyPress>",lambda e: self._clear_placeholder(self.hold_entry, "(optional)"))
        self.hold_entry.grid(row=1, column=2, padx=5)

        self.auto_start = tk.IntVar()
        self.auto_start_check = tk.Checkbutton(
            self.key_frame,
            text="Auto-start",
            variable=self.auto_start,
            bg="#1e1e1e",
            fg="white",
            selectcolor="#1e1e1e",
            command=self.save_config
        )
        self.auto_start_check.grid(row=1, column=3, padx=5)

        self.add_btn = tk.Button(self.key_frame, text="Add Key", command=self.add_key, bg="#007acc", fg="white", width=10)
        self.add_btn.grid(row=1, column=4, padx=5)

        self.hold_durations = {}

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

        # Bottom row buttons
        # Disable All button
        self.disable_all_btn = tk.Button(
            self.button_frame, text="Disable All",
            command=self.disable_all,
            bg="#444", fg="white"
        )
        self.disable_all_btn.grid(row=0, column=0, sticky="w", padx=(5,2), pady=5) 
               
        # Enable All button
        self.enable_all_btn = tk.Button(
            self.button_frame, text="Enable All",
            command=self.enable_all,
            bg="#444", fg="white"
        )
        self.enable_all_btn.grid(row=0, column=1, sticky="w", padx=(2,5), pady=5)
        
        # ── spacer ── push help/readme to the right
        self.button_frame.grid_columnconfigure(2, weight=1)

        # Help button "?"
        self.help_btn = tk.Button(
            self.button_frame, text="?", width=3,
            command=self.show_config_path,
            bg="#444", fg="white"
        )
        self.help_btn.grid(row=0, column=3, padx=(5,2), pady=5)

        # Read Me button 
        self.readme_btn = tk.Button(
            self.button_frame, text="READ ME",
            command=self.show_readme,
            bg="#444", fg="white"
        )
        self.readme_btn.grid(row=0, column=4, sticky="e", padx=(2,5), pady=5)

        # Column spacer
        self.button_frame.grid_columnconfigure(2, weight=1)        # Make only column 2 expand, so Disable/Enable stay left, Help/Read Me stay right
        for c in (0,1,3,4):
            self.button_frame.grid_columnconfigure(c, weight=0)

        self.root.protocol("WM_DELETE_WINDOW", self.quit_app)
        self.root.after(500, self.update_roblox_focus)
        os.makedirs(APPDATA_DIR, exist_ok=True)
        self.interval_mapping   = {}
        self.hold_durations     = {}
        self.key_loopers        = {}
        self.toggle_buttons     = {}
        self.remove_buttons     = {}
        self.key_labels         = {}
        self.key_order = []
        self.load_config()
        self.update_display()
        self.setup_tray_icon()

    # Hold(s) text box placeholder functions
    def _set_placeholder_if_empty(self, entry, placeholder):
        if not entry.get():
            entry.insert(0, placeholder)
            entry.config(fg="gray")
        
    def _clear_placeholder(self, entry, placeholder):
        if entry.get() == placeholder:
            entry.delete(0, tk.END)
            entry.config(fg="white")
            
    def _defocus_if_not_entry(self, event):
    # if the click target isn’t an input box, drop focus back to the root
        if not isinstance(event.widget, tk.Entry):
            self.root.focus_set()

    def disable_all(self):
        for looper in self.key_loopers.values():
            looper.stop()
        for btn in self.toggle_buttons.values():
            btn.config(bg="gray")
        self.save_config()
        
    def enable_all(self):
        for looper in self.key_loopers.values():
            looper.start()
        for btn in self.toggle_buttons.values():
            btn.config(bg="green")
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
            "The script will automatically save your settings on each UI interaction.\n\n"
            "- Use [ Set Key ] to select a key to loop.\n"
            "- Enter a delay interval in seconds.\n"
            "- Optionally, enter a hold duration in seconds.\n"
            "- Click [ Add Key ] to start tracking.\n"
            "- Use the buttons to toggle key loops on/off.\n"
            "- To remove a key, press the red [ X ] button.\n"
            "- Checking 'Auto-start' will start the key loop immediately after adding.\n"
            "- [ Disable All ] and [ Enable All ] buttons for toggling loop.\n"
            "- [ ? ] button to check config path.\n\n"
            "Delete afk_config.json to wipe keys.\n\n"
            "The script will only press keys when Roblox is the active window for user protection.\n"
            "Warning: Roblox window detection includes the roblox home app!\n"
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
        hold_str = self.hold_entry.get().strip()

        # --- basic presence checks ---
        if not key or not interval_str:
            messagebox.showwarning("Input Error", "Key and interval are required.")
            return

        # --- parse interval ---
        try:
            interval = float(interval_str)
            if interval <= 0:
                raise ValueError
        except ValueError:
            messagebox.showwarning("Input Error", "Interval must be a positive number.")
            return

        # --- parse optional hold duration ---
        hold_duration = None
        if hold_str and hold_str != "(optional)":
            try:
                hold_duration = float(hold_str)
            except ValueError:
                messagebox.showerror("Error", "Invalid hold duration.")
                return

        if key in self.interval_mapping:
            # --- UPDATE existing key, don't change its place in key_order ---
            self.interval_mapping[key] = interval
            self.hold_durations[key]  = hold_duration

            # replace or update the looper
            old = self.key_loopers.pop(key, None)
            if old:
                old.stop()
            looper = KeyLooper(key, interval, hold_duration)
            self.key_loopers[key] = looper
            if self.auto_start.get():
                looper.start()

        else:
            # --- NEW key: append to order as before ---
            self.interval_mapping[key] = interval
            self.hold_durations[key]  = hold_duration
            self.key_order.append(key)

            looper = KeyLooper(key, interval, hold_duration)
            self.key_loopers[key] = looper
            if self.auto_start.get():
                looper.start()

        # --- persist and redraw ---
        self.save_config()
        self.update_display()

    def remove_key_direct(self, key):
        # Stop the looper if it's running
        if key in self.key_loopers:
            self.key_loopers[key].stop()
            del self.key_loopers[key]

        # Remove the key from the mappings and order
        if key in self.interval_mapping:
            del self.interval_mapping[key]
        if key in self.hold_durations:
            del self.hold_durations[key]
        if key in self.key_order:
            self.key_order.remove(key)

        # Clear any UI elements associated with this key
        if key in self.key_labels:
            self.key_labels[key].destroy()
            del self.key_labels[key]
        if key in self.toggle_buttons:
            self.toggle_buttons[key].destroy()
            del self.toggle_buttons[key]
        if key in self.remove_buttons:
            self.remove_buttons[key].destroy()
            del self.remove_buttons[key]

        # Save the updated config
        self.save_config()

        # Update the UI display
        self.update_display()


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
        # 1) Remove any leftover widgets for keys that have been deleted
        existing = set(self.key_labels.keys())
        to_remove = existing - set(self.key_order)
        for key in to_remove:
            lbl = self.key_labels.pop(key, None)
            if lbl: lbl.destroy()
            btn = self.toggle_buttons.pop(key, None)
            if btn: btn.destroy()
            rmv = self.remove_buttons.pop(key, None)
            if rmv: rmv.destroy()

        # 2) Walk through the ordered list and grid each row
        for row, key in enumerate(self.key_order):
            interval = self.interval_mapping[key]
            hold     = self.hold_durations.get(key)
            hold_text= f" | Hold(s): {hold}s" if hold else ""
            label_txt     = f"{key} | {interval}s{hold_text}"

            # ensure there's a looper
            looper = self.key_loopers.get(key)
            if not looper:
                looper = KeyLooper(key, interval, hold)
                self.key_loopers[key] = looper

            # safety: skip if somehow the config dicts got out of sync
            if key not in self.interval_mapping:
                continue

            # create widgets if missing
            if key not in self.key_labels:
                lbl = tk.Label(self.scrollable_frame,
                            text=label_txt,
                            bg="#2e2e2e", fg="white",
                            anchor="w", width=30)
                btn = tk.Button(self.scrollable_frame,
                                text="ON/OFF", width=6,
                                fg="white", relief="raised",
                                command=lambda k=key: self.toggle_key(k))
                rmv = tk.Button(self.scrollable_frame,
                                text="❌", width=3,
                                bg="#cc3300", fg="white",
                                command=lambda k=key: self.remove_key_direct(k))

                self.key_labels[key]       = lbl
                self.toggle_buttons[key]   = btn
                self.remove_buttons[key]   = rmv
            else:
                lbl = self.key_labels[key]
                btn = self.toggle_buttons[key]
                rmv = self.remove_buttons[key]
                # update text in case interval/hold changed
                lbl.config(text=label_txt)

            # place them into the grid
            lbl.grid(row=row, column=0, sticky="w", padx=(5,0), pady=4)
            is_running = looper.running.is_set()
            btn.config(bg="green" if is_running else "gray")
            btn.grid(row=row, column=1, padx=5, pady=4)
            rmv.grid(row=row, column=2, padx=(0,5), pady=4)
                
    def save_config(self):
        try:
            config = {
                "version": CONFIG_VERSION,
                "order": self.key_order,
                "intervals": self.interval_mapping,
                "hold_durations": self.hold_durations,
                "auto_start": self.auto_start.get()
            }
            with open(CONFIG_FILE, "w") as f:
                json.dump(config, f, indent=4)
        except Exception as e:
            messagebox.showerror("Save Error", f"Failed to save config: {e}")

    def load_config(self):
        # 1) Defaults in case the file is missing or invalid
        self.key_order        = []
        self.interval_mapping = {}
        self.hold_durations   = {}
        self.auto_start.set(False)

        if not os.path.exists(CONFIG_FILE):
            return

        try:
            with open(CONFIG_FILE, "r") as f:
                cfg = json.load(f)
        except Exception as e:
            messagebox.showerror("Load Error", f"Failed to load config: {e}")
            return

        # 2) Migrate old v1 → v2 if someone still has "intervals"
        if "intervals" in cfg and "interval_mapping" not in cfg:
            cfg["interval_mapping"] = cfg.pop("intervals")
            cfg.setdefault("hold_durations", {})
            cfg["order"] = list(cfg["interval_mapping"].keys())

            # write that back immediately so everyone shares the new schema
            cfg["version"] = CONFIG_VERSION
            cfg["auto_start"] = cfg.get("auto_start", False)
            with open(CONFIG_FILE, "w") as f:
                json.dump(cfg, f, indent=2)

        # 3) Load from the proper fields
        self.interval_mapping = cfg.get("interval_mapping", {})
        self.hold_durations   = cfg.get("hold_durations", {})
        self.auto_start.set(cfg.get("auto_start", False))

        # Always fall back to the mapping order if "order" is missing
        raw_order = cfg.get("order", list(self.interval_mapping.keys()))
        # 4) Filter to avoid stray keys
        self.key_order = [k for k in raw_order if k in self.interval_mapping]

        # 5) Clear out any existing loopers/buttons/labels
        self.key_loopers.clear()
        self.toggle_buttons.clear()
        self.remove_buttons.clear()
        self.key_labels.clear()

        # 6) Recreate loopers (auto-starting if needed) in the exact saved order
        for key in self.key_order:
            interval = self.interval_mapping[key]
            hold     = self.hold_durations.get(key)
            looper   = KeyLooper(key, interval, hold)
            self.key_loopers[key] = looper
            if self.auto_start.get():
                looper.start()

        # 7) Finally, draw the grid in that order
        self.update_display()
                    
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
