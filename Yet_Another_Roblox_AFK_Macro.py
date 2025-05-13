from config import *

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

def is_roblox_focused():
    try:
        hwnd = win32gui.GetForegroundWindow()
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        exe = psutil.Process(pid).name().lower()
        return exe == "robloxplayerbeta.exe"
    except Exception:
        return False

def get_embedded_icon():
    try:
        image_data = base64.b64decode(icon_base64())
        return Image.open(BytesIO(image_data)).resize((64, 64), Image.Resampling.LANCZOS)
    except Exception as e:
        print(f"Failed to load tray icon: {e}")
        return Image.new("RGB", (64, 64), "black")

class AFKGui:
    def __init__(self):
        check_for_updates()
        self.root = tk.Tk()
        self.root.title("Yet Another Roblox AFK Macro")
        self.root.geometry("460x580")
        self.root.configure(bg="#1e1e1e")
        self.root.attributes("-topmost", True)
        self.root.bind("<Button-1>", self._defocus_if_not_entry)

        self.key_order = []
        self.key_mapping = {}
        self.hold_mapping = {}
        self.key_threads = {}
        self.auto_start = tk.IntVar()

        self._init_icon()
        self._init_ui()

        os.makedirs(APPDATA_DIR, exist_ok=True)
        self.load_config()
        self.update_display()
        self.setup_tray_icon()
        self.root.protocol("WM_DELETE_WINDOW", self.quit_app)
        self.root.after(500, self.update_roblox_focus)

    def disable_all(self):
        self.key_threads.clear()
        for btn in self.buttons.values():
            btn.config(bg="gray")
        self.save_config()

    def enable_all(self):
        for key in self.key_order:
            if key not in self.key_threads:
                interval = self.key_mapping.get(key)
                hold = self.hold_mapping.get(key)
                thread = Thread(target=self._press_loop, args=(key, interval, hold), daemon=True)
                self.key_threads[key] = thread
                thread.start()
                self.buttons[key].config(bg="green")
        self.save_config()

    def show_config_path(self):
        path = CONFIG_FILE
        if messagebox.askyesno("Config File Location", f"Your config is stored at:\n\n{path}\n\nOpen folder?"):
            os.startfile(os.path.dirname(path))

    def show_readme(self):
        instructions = (
            "This is Yet Another Roblox AFK Macro!\n\n"
            "- Set a key to simulate.\n"
            "- Set interval and optionally a hold duration.\n"
            "- Add and toggle keys ON/OFF.\n"
            "- Keys only press when Roblox is focused.\n"
            "- Config auto-saves.\n"
            "- Disable All / Enable All buttons manage all keys."
        )
        messagebox.showinfo("Instructions", instructions)

    def _init_icon(self):
        try:
            image_data = base64.b64decode(icon_base64())
            pil_image = Image.open(BytesIO(image_data))
            icon_tk = ImageTk.PhotoImage(pil_image)
            self.root.iconphoto(False, icon_tk)
            self._icon_ref = icon_tk
        except Exception as e:
            print(f"Error setting window icon: {e}")

    def _init_ui(self):
        self.roblox_status = tk.StringVar(value="Roblox Not Focused")
        self.roblox_label = tk.Label(self.root, textvariable=self.roblox_status, font=("Arial", 10), fg="gray", bg="#1e1e1e")
        self.roblox_label.pack(pady=5)
        tk.Label(self.root, text="Assign keys and interval.", font=("Arial", 12), fg="white", bg="#1e1e1e").pack(pady=5)

        self.key_frame = tk.Frame(self.root, bg="#1e1e1e")
        self.key_frame.pack(pady=10)
        self.key_var = tk.StringVar()

        self.key_btn = tk.Button(self.key_frame, text="Set Key", command=self.capture_key, width=10)
        self.key_btn.grid(row=1, column=0, padx=5)
        ToolTip(self.key_btn, "Click and press a single key to set the looped key")

        tk.Label(self.key_frame, text="Interval (s):", fg="white", bg="#1e1e1e").grid(row=0, column=1, padx=5)
        self.interval_entry = tk.Entry(self.key_frame, width=10, fg="white", bg="#1e1e1e", insertbackground="white")
        self.interval_entry.grid(row=1, column=1, padx=5)

        tk.Label(self.key_frame, text="Hold (s):", fg="white", bg="#1e1e1e").grid(row=0, column=2, padx=5)
        self.hold_entry = tk.Entry(self.key_frame, width=10, fg="gray", bg="#1e1e1e", insertbackground="white")
        self.hold_entry.insert(0, "(optional)")
        self.hold_entry.bind("<FocusIn>", lambda e: self._clear_placeholder(self.hold_entry, "(optional)"))
        self.hold_entry.bind("<FocusOut>", lambda e: self._set_placeholder_if_empty(self.hold_entry, "(optional)"))
        self.hold_entry.grid(row=1, column=2, padx=5)

        tk.Checkbutton(self.key_frame, text="Auto-start", variable=self.auto_start, bg="#1e1e1e", fg="white", selectcolor="#1e1e1e", command=self.save_config).grid(row=1, column=3, padx=5)
        tk.Button(self.key_frame, text="Add Key", command=self.add_key, bg="#007acc", fg="white", width=10).grid(row=1, column=4, padx=5)

        tk.Label(self.root, text="Configured Keys:", fg="white", bg="#1e1e1e").pack()

        self.canvas_frame = tk.Frame(self.root, bg="#1e1e1e")
        self.button_frame = tk.Frame(self.root, bg="#1e1e1e")
        self.button_frame.pack(side="bottom", fill="x", pady=10, padx=10)
        
        #Bottom Buttons
        tk.Button(self.button_frame, text="Disable All", command=self.disable_all, bg="#444", fg="white").grid(row=0, column=0, sticky="w", padx=(5,2), pady=5)
        tk.Button(self.button_frame, text="Enable All", command=self.enable_all, bg="#444", fg="white").grid(row=0, column=1, sticky="w", padx=(2,5), pady=5)
        self.button_frame.grid_columnconfigure(2, weight=1)

        tk.Button(self.button_frame, text="?", width=3, command=self.show_config_path, bg="#444", fg="white").grid(row=0, column=3, padx=(5,2), pady=5)
        tk.Button(self.button_frame, text="READ ME", command=self.show_readme, bg="#444", fg="white").grid(row=0, column=4, sticky="e", padx=(2,5), pady=5)
        
        self.canvas_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        self.canvas = tk.Canvas(self.canvas_frame, bg="#1e1e1e", highlightthickness=0)
        self.scrollbar = tk.Scrollbar(self.canvas_frame, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = tk.Frame(self.canvas, bg="#1e1e1e")
        self.buttons = {}

        self.scrollable_frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.bind_all("<MouseWheel>", lambda e: self.canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"))
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

    def _set_placeholder_if_empty(self, entry, placeholder):
        if not entry.get():
            entry.insert(0, placeholder)
            entry.config(fg="gray")

    def _clear_placeholder(self, entry, placeholder):
        if entry.get() == placeholder:
            entry.delete(0, tk.END)
            entry.config(fg="white")

    def _defocus_if_not_entry(self, event):
        if not isinstance(event.widget, tk.Entry):
            self.root.focus_set()

    def capture_key(self):
        def worker():
            self.key_btn.config(text="Press key...")
            self.root.update()
            try:
                event = keyboard.read_event(suppress=True)
                if event.event_type == "down":
                    key = event.name
                    self.root.after(0, lambda: (
                        self.key_var.set(key.lower()),
                        self.key_btn.config(text=f"Key: {key.lower()}")
                    ))
            except:
                self.root.after(0, lambda: self.key_btn.config(text="Set Key"))
        Thread(target=worker, daemon=True).start()

    def _press_loop(self, key, interval, hold):
        while key in self.key_threads:
            if not is_roblox_focused():
                time.sleep(0.5)
                continue
            keyboard.press(key)
            if hold:
                time.sleep(hold)
            keyboard.release(key)
            time.sleep(interval)

    def add_key(self):
        key = self.key_var.get().strip().lower()
        try:
            interval = float(self.interval_entry.get().strip())
            if interval <= 0:
                raise ValueError
        except ValueError:
            messagebox.showwarning("Input Error", "Interval must be a positive number.")
            return

        hold_str = self.hold_entry.get().strip()
        hold = None
        if hold_str and hold_str != "(optional)":
            try:
                hold = float(hold_str)
                if hold < 0:
                    raise ValueError
            except ValueError:
                messagebox.showwarning("Input Error", "Hold duration must be a non-negative number.")
                return

        self.key_mapping[key] = interval
        self.hold_mapping[key] = hold

        if key not in self.key_order:
            self.key_order.append(key)
        else:
            if key in self.key_threads:
                del self.key_threads[key]
                thread = Thread(target=self._press_loop, args=(key, interval, hold), daemon=True)
                self.key_threads[key] = thread
                thread.start()

        if self.auto_start.get() and key not in self.key_threads:
            self.toggle_key(key)

        self.save_config()
        self.update_display()

    def toggle_key(self, key):
        if key in self.key_threads:
            del self.key_threads[key]
            self.buttons[key].config(bg="gray")
        else:
            self.buttons[key].config(bg="green")
            interval = self.key_mapping[key]
            hold = self.hold_mapping.get(key)
            thread = Thread(target=self._press_loop, args=(key, interval, hold), daemon=True)
            self.key_threads[key] = thread
            thread.start()

    def remove_key(self, key):
        self.key_mapping.pop(key, None)
        self.hold_mapping.pop(key, None)
        self.key_threads.pop(key, None)
        if key in self.key_order:
            self.key_order.remove(key)
        self.update_display()
        self.save_config()

    def update_display(self):
        self.root.after_idle(self._render_key_display)

    def _render_key_display(self):
        if not hasattr(self, 'row_widgets'):
            self.row_widgets = {}
            self.buttons = {}

        current_keys = set(self.key_order)
        existing_keys = set(self.row_widgets.keys())

        # Remove rows for keys no longer present
        for key in existing_keys - current_keys:
            for widget in self.row_widgets[key]:
                widget.destroy()
            del self.row_widgets[key]
            self.buttons.pop(key, None)

        # Add or update rows
        for i, key in enumerate(self.key_order):
            interval = self.key_mapping.get(key)
            hold = self.hold_mapping.get(key)
            if interval is None:
                continue

            hold_text = f" | Hold: {hold}s" if hold else ""
            text = f"{key} | {interval}s{hold_text}"
            btn_bg = "green" if key in self.key_threads else "gray"

            if key not in self.row_widgets:
                row_frame = tk.Frame(self.scrollable_frame, bg="#1e1e1e")
                lbl = tk.Label(row_frame, text=text, bg="#2e2e2e", fg="white", anchor="w", width=30)
                btn = tk.Button(row_frame, text="ON/OFF", bg=btn_bg, fg="white", command=lambda k=key: self.toggle_key(k))
                rmv = tk.Button(row_frame, text="❌", bg="#cc3300", fg="white", width=3, command=lambda k=key: self.remove_key(k))

                lbl.grid(row=0, column=0, padx=5, sticky="w")
                btn.grid(row=0, column=1, padx=5)
                rmv.grid(row=0, column=2, padx=5)

                row_frame.grid(row=i, column=0, columnspan=3, sticky="we", pady=2)
                row_frame.grid_columnconfigure(0, weight=1)

                self.row_widgets[key] = [row_frame, lbl, btn, rmv]
                self.buttons[key] = btn
            else:
                _, lbl, btn, _ = self.row_widgets[key]
                lbl.config(text=text)
                btn.config(bg=btn_bg)

        self.scrollable_frame.update_idletasks()
        
    def update_roblox_focus(self):
        focused = is_roblox_focused()
        self.roblox_status.set("Roblox Focused" if focused else "Roblox Not Focused")
        color = "green" if focused else "gray"
        self.roblox_label.config(fg=color)
        self.root.after(500, self.update_roblox_focus)
        
    def save_config(self):
        try:
            config = {
                "version": CONFIG_VERSION,
                "order": self.key_order,
                "intervals": self.key_mapping,
                "holds": self.hold_mapping,
                "auto_start": self.auto_start.get()
            }
            with open(CONFIG_FILE, "w") as f:
                json.dump(config, f, indent=4)
        except Exception as e:
            messagebox.showerror("Save Error", f"Failed to save config: {e}")

    def load_config(self):
        if not os.path.exists(CONFIG_FILE):
            return
        try:
            with open(CONFIG_FILE, "r") as f:
                cfg = json.load(f)
            self.key_mapping = cfg.get("intervals", {})
            self.hold_mapping = cfg.get("holds", {})
            self.key_order = cfg.get("order", list(self.key_mapping.keys()))
            self.auto_start.set(cfg.get("auto_start", False))
        except Exception as e:
            messagebox.showerror("Load Error", f"Failed to load config: {e}")

    def setup_tray_icon(self):
        image = get_embedded_icon()
        menu = (
            pystray.MenuItem("Show", self.show_window),
            pystray.MenuItem("Quit", self.quit_app),
        )
        self.icon = pystray.Icon("roblox_afk", image, "Roblox AFK Macro", menu)
        Thread(target=self.icon.run, daemon=True).start()

    def show_window(self, icon, item):
        self.root.deiconify()

    def quit_app(self, icon=None, item=None):
        self.key_threads.clear()
        if hasattr(self, 'icon') and self.icon:
            self.icon.visible = False
            self.icon.stop()
        self.root.quit()

    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    AFKGui().run()
