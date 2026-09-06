"""
PipMan - Modern Python Package Manager (v2.4)
A sleek, modern GUI for managing pip packages with real-time log terminal.
"""

import csv
import datetime
import importlib.metadata as im
import io
import json
import os
import queue
import shutil
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import urllib.request
import webbrowser

# High-DPI Awareness on Windows
try:
    from ctypes import windll
    windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass

# Theme Colors - Dark Emerald / Cyberpunk Palette matching reference design
THEME = {
    "bg_root": "#0b1113",
    "bg_main": "#0d1618",
    "bg_card": "#12231e",
    "bg_card_hover": "#173429",
    "bg_card_border": "#1a3b31",
    "bg_header": "#10201c",
    "border_glow": "#10b981",
    "border_dark": "#1e3831",
    "accent_mint": "#2ee59d",
    "accent_cyan": "#2dd4bf",
    "accent_yellow": "#facc15",
    "text_main": "#f8fafc",
    "text_muted": "#859ea4",
    "text_dim": "#526e75",
    "btn_update_border": "#10b981",
    "btn_update_fg": "#2ee59d",
    "btn_uninstall_border": "#284a40",
    "btn_uninstall_fg": "#94a3b8",
    "btn_uninstall_hover_bg": "#dc2626",
    "terminal_bg": "#070c0e",
    "terminal_fg": "#cbd5e1",
    "terminal_prompt": "#2ee59d",
    "terminal_cmd": "#38bdf8",
    "terminal_error": "#f87171",
    "terminal_success": "#34d399",
}


def find_target_python():
    """Locates the host/target Python interpreter dynamically on ANY Windows PC."""
    if not getattr(sys, "frozen", False):
        return sys.executable

    # 1. Check active virtualenv or conda environment on the PC
    for env_var in ["VIRTUAL_ENV", "CONDA_PREFIX"]:
        val = os.environ.get(env_var)
        if val:
            for p in [os.path.join(val, "python.exe"), os.path.join(val, "Scripts", "python.exe")]:
                if os.path.isfile(p):
                    return p

    # 2. Check Windows PATH for python / py / python3
    for name in ["python", "py", "python3"]:
        found = shutil.which(name)
        if found and "WindowsApps" not in found:  # prefer direct installation over MS Store redirect
            return found

    # 3. Check Windows Registry (where official Python installers register)
    try:
        import winreg
        for root_key in [winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE]:
            try:
                with winreg.OpenKey(root_key, r"Software\Python\PythonCore") as core_key:
                    num_subkeys = winreg.QueryInfoKey(core_key)[0]
                    for i in range(num_subkeys):
                        ver = winreg.EnumKey(core_key, i)
                        try:
                            with winreg.OpenKey(core_key, rf"{ver}\InstallPath") as inst_key:
                                exe_path, _ = winreg.QueryValueEx(inst_key, "ExecutablePath")
                                if os.path.isfile(exe_path):
                                    return exe_path
                        except Exception:
                            pass
            except Exception:
                pass
    except Exception:
        pass

    # 4. Search standard installation directories on any drive
    candidates = []
    local_app = os.environ.get("LOCALAPPDATA", "")
    if local_app:
        py_dir = os.path.join(local_app, "Programs", "Python")
        if os.path.isdir(py_dir):
            for sub in os.listdir(py_dir):
                candidate_exe = os.path.join(py_dir, sub, "python.exe")
                if os.path.isfile(candidate_exe):
                    candidates.append(candidate_exe)

    for drive in ["C:\\", "D:\\"]:
        for prefix in [
            "Python314", "Python313", "Python312", "Python311", "Python310", "Python39", "Python38"
        ]:
            candidates.append(os.path.join(drive, prefix, "python.exe"))
            candidates.append(os.path.join(drive, "Program Files", prefix, "python.exe"))

    for c in candidates:
        if os.path.isfile(c):
            return c

    # 5. Fallback to standard PATH command
    fallback = shutil.which("python") or shutil.which("py") or "python"
    return fallback


def discover_site_packages(python_exe):
    """Discovers user & global site-packages directories from the target Python."""
    try:
        cmd = [
            python_exe,
            "-c",
            "import site, json; print(json.dumps([site.getusersitepackages()] + site.getsitepackages()))",
        ]
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=5, creationflags=flags)
        if res.returncode == 0:
            dirs = json.loads(res.stdout.strip())
            return [d for d in dirs if os.path.isdir(d)]
    except Exception:
        pass

    # Fallback to standard site-packages in sys.path
    import site
    try:
        dirs = [site.getusersitepackages()] + site.getsitepackages()
        return [d for d in dirs if os.path.isdir(d)]
    except Exception:
        return None


class PipManApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("PipMan (v2.4)")
        self.root.geometry("1060x720")
        self.root.minsize(860, 560)
        self.root.configure(bg=THEME["bg_root"])

        # Detect Python Environment
        self.target_python = find_target_python()
        self.site_dirs = discover_site_packages(self.target_python)

        # State
        self.all_packages = []
        self.filtered_packages = []
        self.sort_key = "name"
        self.sort_desc = False
        self.is_loading = False
        self.log_visible = True
        self.log_height = 185
        self.active_process = None
        self.pypi_cache = {}
        self.placeholder_active = True

        # Thread Safety Queue
        self.msg_queue = queue.Queue()

        self._setup_fonts()
        self._create_layout()

        # Start periodic GUI queue processor
        self.root.after(80, self._process_queue)

        # Initial Welcome Message & Scanning
        self.log_line("PipMan (v2.4) initialized.", tag="info")
        self.log_line(f"Active Python: {self.target_python}", tag="dim")
        self.refresh_packages()

    def _setup_fonts(self):
        self.font_title = ("Segoe UI", 13, "bold")
        self.font_subtitle = ("Segoe UI", 10, "bold")
        self.font_bold = ("Segoe UI", 9, "bold")
        self.font_regular = ("Segoe UI", 9)
        self.font_small = ("Segoe UI", 8)
        self.font_mono = ("Consolas", 9)

    def _create_layout(self):
        # Outer Card Container with Subtle Emerald Glow Border
        self.outer_card = tk.Frame(
            self.root,
            bg=THEME["bg_main"],
            highlightbackground=THEME["border_dark"],
            highlightthickness=1,
            bd=0,
        )
        self.outer_card.pack(fill=tk.BOTH, expand=True, padx=14, pady=14)

        # Top Bar
        self._create_top_bar()

        # Sub-header: Installed Packages Count & Refresh Button
        self._create_section_header()

        # Table Header (Sortable Columns)
        self._create_table_header()

        # Table Body (Scrollable Rows)
        self._create_table_body()

        # Bottom Log & Activity Terminal
        self._create_log_panel()

    def _create_top_bar(self):
        self.top_bar = tk.Frame(self.outer_card, bg=THEME["bg_main"], height=50)
        self.top_bar.pack(fill=tk.X, padx=16, pady=(12, 6))

        # Brand / Title
        brand_frame = tk.Frame(self.top_bar, bg=THEME["bg_main"])
        brand_frame.pack(side=tk.LEFT, anchor=tk.W)

        title_lbl = tk.Label(
            brand_frame,
            text="PipMan",
            font=self.font_title,
            fg=THEME["text_main"],
            bg=THEME["bg_main"],
        )
        title_lbl.pack(side=tk.LEFT)

        ver_lbl = tk.Label(
            brand_frame,
            text=" (v2.4)",
            font=("Segoe UI", 10),
            fg=THEME["text_muted"],
            bg=THEME["bg_main"],
        )
        ver_lbl.pack(side=tk.LEFT)

        # Center Search Bar & Header Refresh Button
        center_frame = tk.Frame(self.top_bar, bg=THEME["bg_main"])
        center_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(30, 20))

        search_box = tk.Frame(
            center_frame,
            bg="#132321",
            highlightbackground="#223a34",
            highlightthickness=1,
            bd=0,
            padx=10,
            pady=4,
        )
        search_box.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=1)

        self.search_var = tk.StringVar()
        self.search_entry = tk.Entry(
            search_box,
            textvariable=self.search_var,
            font=self.font_regular,
            bg="#132321",
            fg=THEME["text_dim"],
            insertbackground=THEME["accent_mint"],
            bd=0,
            relief=tk.FLAT,
        )
        self.search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(2, 6))
        self.search_entry.insert(0, "Search installed packages...")

        self.search_entry.bind("<FocusIn>", self._on_search_focus_in)
        self.search_entry.bind("<FocusOut>", self._on_search_focus_out)
        self.search_var.trace_add("write", lambda *args: self._on_search_change())

        search_icon = tk.Label(
            search_box,
            text="🔍",
            font=("Segoe UI", 9),
            fg=THEME["text_muted"],
            bg="#132321",
        )
        search_icon.pack(side=tk.RIGHT, padx=2)

        # Top round refresh icon
        self.btn_top_refresh = tk.Button(
            center_frame,
            text="↻",
            font=("Segoe UI", 12, "bold"),
            bg="#132321",
            fg=THEME["accent_mint"],
            activebackground="#1e3831",
            activeforeground="#ffffff",
            bd=0,
            highlightthickness=1,
            highlightbackground="#223a34",
            padx=9,
            pady=2,
            cursor="hand2",
            command=self.refresh_packages,
        )
        self.btn_top_refresh.pack(side=tk.LEFT, padx=(8, 0))

    def _create_section_header(self):
        sec_frame = tk.Frame(self.outer_card, bg=THEME["bg_main"])
        sec_frame.pack(fill=tk.X, padx=16, pady=(8, 8))

        self.lbl_installed = tk.Label(
            sec_frame,
            text="INSTALLED PACKAGES (0)",
            font=self.font_subtitle,
            fg=THEME["text_muted"],
            bg=THEME["bg_main"],
        )
        self.lbl_installed.pack(side=tk.LEFT)

        # Right-aligned Refresh button with bright mint border
        self.btn_refresh = tk.Button(
            sec_frame,
            text="Refresh",
            font=self.font_bold,
            bg="#0f221e",
            fg=THEME["accent_mint"],
            activebackground=THEME["accent_mint"],
            activeforeground="#0b1113",
            bd=0,
            highlightthickness=1,
            highlightbackground=THEME["border_glow"],
            padx=14,
            pady=3,
            cursor="hand2",
            command=self.refresh_packages,
        )
        self.btn_refresh.pack(side=tk.RIGHT)
        self._bind_button_hover(
            self.btn_refresh, "#0f221e", THEME["accent_mint"], THEME["accent_mint"], "#0b1113"
        )

    def _create_table_header(self):
        self.header_frame = tk.Frame(
            self.outer_card,
            bg=THEME["bg_header"],
            highlightbackground="#1d352e",
            highlightthickness=1,
            bd=0,
            height=34,
        )
        self.header_frame.pack(fill=tk.X, padx=16, pady=(0, 4))

        self.columns = [
            ("Package Name", "name", 0.28, tk.W),
            ("Current Version", "version", 0.15, tk.W),
            ("Latest Version", "latest", 0.15, tk.W),
            ("Size", "size", 0.12, tk.W),
            ("Installed Date", "date", 0.16, tk.W),
            ("Actions", None, 0.14, tk.CENTER),
        ]

        self.header_cols = {}
        for col_name, col_key, ratio, anchor in self.columns:
            btn_text = f"{col_name} ⇅" if col_key else col_name
            lbl = tk.Label(
                self.header_frame,
                text=btn_text,
                font=self.font_bold,
                fg=THEME["text_muted"],
                bg=THEME["bg_header"],
                anchor=anchor,
                padx=8,
                pady=6,
                cursor="hand2" if col_key else "arrow",
            )
            if col_key:
                lbl.bind("<Button-1>", lambda e, k=col_key: self._toggle_sort(k))
                lbl.bind("<Enter>", lambda e, w=lbl: w.config(fg=THEME["accent_mint"]))
                lbl.bind("<Leave>", lambda e, w=lbl: w.config(fg=THEME["text_muted"]))
            self.header_cols[col_name] = lbl

        self._render_header_grid()
        self.header_frame.bind("<Configure>", lambda e: self._render_header_grid())

    def _render_header_grid(self):
        for col_name, _, ratio, _ in self.columns:
            lbl = self.header_cols[col_name]
            lbl.place(relx=self._get_col_relx(col_name), rely=0, relwidth=ratio, relheight=1.0)

    def _get_col_relx(self, target_col):
        relx = 0.0
        for col_name, _, ratio, _ in self.columns:
            if col_name == target_col:
                return relx
            relx += ratio
        return relx

    def _create_table_body(self):
        self.table_container = tk.Frame(self.outer_card, bg=THEME["bg_main"])
        self.table_container.pack(fill=tk.BOTH, expand=True, padx=16, pady=(0, 8))

        self.canvas = tk.Canvas(
            self.table_container, bg=THEME["bg_main"], highlightthickness=0, bd=0
        )
        self.scrollbar = ttk.Scrollbar(
            self.table_container, orient=tk.VERTICAL, command=self.canvas.yview
        )
        self.scrollable_frame = tk.Frame(self.canvas, bg=THEME["bg_main"])

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")),
        )

        self.canvas_window = self.canvas.create_window(
            (0, 0), window=self.scrollable_frame, anchor="nw"
        )

        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.bind(
            "<Configure>", lambda e: self.canvas.itemconfig(self.canvas_window, width=e.width)
        )

        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)

        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def _create_log_panel(self):
        self.log_container = tk.Frame(
            self.outer_card,
            bg=THEME["bg_main"],
            highlightbackground="#192e29",
            highlightthickness=1,
            bd=0,
        )
        self.log_container.pack(fill=tk.X, padx=16, pady=(0, 10))

        self.log_header = tk.Frame(self.log_container, bg="#101a1c", height=28)
        self.log_header.pack(fill=tk.X)

        lbl_log_title = tk.Label(
            self.log_header,
            text="Log & Activity",
            font=self.font_bold,
            fg=THEME["text_main"],
            bg="#101a1c",
            padx=10,
            pady=4,
        )
        lbl_log_title.pack(side=tk.LEFT)

        btn_clear = tk.Label(
            self.log_header,
            text="✕",
            font=self.font_regular,
            fg=THEME["text_muted"],
            bg="#101a1c",
            padx=8,
            cursor="hand2",
        )
        btn_clear.pack(side=tk.RIGHT)
        btn_clear.bind("<Button-1>", lambda e: self.clear_log())
        btn_clear.bind("<Enter>", lambda e: btn_clear.config(fg=THEME["accent_mint"]))
        btn_clear.bind("<Leave>", lambda e: btn_clear.config(fg=THEME["text_muted"]))

        self.btn_toggle_log = tk.Label(
            self.log_header,
            text="—",
            font=self.font_bold,
            fg=THEME["text_muted"],
            bg="#101a1c",
            padx=8,
            cursor="hand2",
        )
        self.btn_toggle_log.pack(side=tk.RIGHT)
        self.btn_toggle_log.bind("<Button-1>", lambda e: self.toggle_log_panel())
        self.btn_toggle_log.bind(
            "<Enter>", lambda e: self.btn_toggle_log.config(fg=THEME["accent_mint"])
        )
        self.btn_toggle_log.bind(
            "<Leave>", lambda e: self.btn_toggle_log.config(fg=THEME["text_muted"])
        )

        self.terminal_frame = tk.Frame(
            self.log_container, bg=THEME["terminal_bg"], height=self.log_height
        )
        self.terminal_frame.pack(fill=tk.BOTH, expand=True)
        self.terminal_frame.pack_propagate(False)

        self.log_text = tk.Text(
            self.terminal_frame,
            font=self.font_mono,
            bg=THEME["terminal_bg"],
            fg=THEME["terminal_fg"],
            insertbackground=THEME["accent_mint"],
            bd=0,
            padx=12,
            pady=8,
            wrap=tk.WORD,
            state=tk.DISABLED,
        )
        self.log_scroll = ttk.Scrollbar(
            self.terminal_frame, orient=tk.VERTICAL, command=self.log_text.yview
        )
        self.log_text.configure(yscrollcommand=self.log_scroll.set)

        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.log_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.log_text.tag_config("prompt", foreground=THEME["terminal_prompt"])
        self.log_text.tag_config("cmd", foreground=THEME["terminal_cmd"])
        self.log_text.tag_config("output", foreground=THEME["terminal_fg"])
        self.log_text.tag_config("success", foreground=THEME["terminal_success"])
        self.log_text.tag_config("error", foreground=THEME["terminal_error"])
        self.log_text.tag_config("info", foreground=THEME["accent_cyan"])
        self.log_text.tag_config("dim", foreground=THEME["text_dim"])

    def _on_mousewheel(self, event):
        if self.canvas.winfo_height() < self.scrollable_frame.winfo_height():
            self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _bind_button_hover(self, widget, normal_bg, normal_fg, hover_bg, hover_fg):
        widget.bind("<Enter>", lambda e: widget.config(bg=hover_bg, fg=hover_fg))
        widget.bind("<Leave>", lambda e: widget.config(bg=normal_bg, fg=normal_fg))

    def _on_search_focus_in(self, event):
        if self.placeholder_active:
            self.search_entry.delete(0, tk.END)
            self.search_entry.config(fg=THEME["text_main"])
            self.placeholder_active = False

    def _on_search_focus_out(self, event):
        if not self.search_entry.get().strip():
            self.placeholder_active = True
            self.search_entry.delete(0, tk.END)
            self.search_entry.insert(0, "Search installed packages...")
            self.search_entry.config(fg=THEME["text_dim"])

    def _on_search_change(self):
        if self.placeholder_active:
            return
        query = self.search_var.get().strip()
        self._apply_filter(query)

    # -------------------------------------------------------------
    # Robust Package Scanning & Discovery
    # -------------------------------------------------------------
    def refresh_packages(self):
        if self.is_loading:
            return
        self.is_loading = True
        self.btn_refresh.config(text="Scanning...", state=tk.DISABLED)
        self.btn_top_refresh.config(state=tk.DISABLED)
        self.log_line("Scanning installed packages in active environment...", tag="info")

        threading.Thread(target=self._scan_worker, daemon=True).start()

    def _calc_package_size(self, d, pkg_name):
        """Calculates accurate package size across RECORD metadata, files, and disk directories."""
        size_bytes = 0

        # 1. Check RECORD metadata (fastest & most accurate)
        try:
            record_txt = d.read_text("RECORD")
            if record_txt:
                for row in csv.reader(io.StringIO(record_txt)):
                    if len(row) >= 3 and row[2].strip().isdigit():
                        size_bytes += int(row[2].strip())
        except Exception:
            pass

        # 2. Check d.files locate
        if size_bytes == 0:
            try:
                if d.files:
                    for f in d.files:
                        try:
                            fp = f.locate()
                            if os.path.isfile(fp):
                                size_bytes += os.path.getsize(fp)
                        except Exception:
                            pass
            except Exception:
                pass

        # 3. Scan matching directories in site_dirs
        if size_bytes == 0 and self.site_dirs:
            norm_name = pkg_name.replace("-", "_").lower()
            for sdir in self.site_dirs:
                if not os.path.isdir(sdir):
                    continue
                try:
                    for entry in os.listdir(sdir):
                        el = entry.lower()
                        if el == norm_name or el.startswith(norm_name + "-"):
                            full_p = os.path.join(sdir, entry)
                            if os.path.isdir(full_p):
                                size_bytes += sum(
                                    os.path.getsize(os.path.join(r, f))
                                    for r, _, fs in os.walk(full_p)
                                    for f in fs
                                    if os.path.isfile(os.path.join(r, f))
                                )
                            elif os.path.isfile(full_p):
                                size_bytes += os.path.getsize(full_p)
                except Exception:
                    pass

        return size_bytes / (1024 * 1024)

    def _calc_folder_size(self, pkg_name):
        """Calculates disk size for a package name by inspecting site directories."""
        size_bytes = 0
        if not self.site_dirs:
            return 0.0
        norm_name = pkg_name.replace("-", "_").lower()
        for sdir in self.site_dirs:
            if not os.path.isdir(sdir):
                continue
            try:
                for entry in os.listdir(sdir):
                    el = entry.lower()
                    if el == norm_name or el.startswith(norm_name + "-") or el.startswith(norm_name + "."):
                        full_p = os.path.join(sdir, entry)
                        if os.path.isdir(full_p):
                            size_bytes += sum(
                                os.path.getsize(os.path.join(r, f))
                                for r, _, fs in os.walk(full_p)
                                for f in fs
                                if os.path.isfile(os.path.join(r, f))
                            )
                        elif os.path.isfile(full_p):
                            size_bytes += os.path.getsize(full_p)
            except Exception:
                pass
        return size_bytes / (1024 * 1024)

    def _scan_worker(self):
        packages = []
        seen_names = set()
        try:
            # 1. Discover via importlib.metadata with discovered site_dirs
            search_paths = self.site_dirs if self.site_dirs else None
            try:
                dists = list(im.distributions(paths=search_paths) if search_paths else im.distributions())
            except Exception:
                dists = list(im.distributions())

            for d in dists:
                try:
                    name = d.metadata.get("Name") or getattr(d, "name", "Unknown")
                    if name.lower() in seen_names:
                        continue
                    seen_names.add(name.lower())

                    version = d.version or "0.0.0"

                    # Multi-stage size calculation
                    size_mb = self._calc_package_size(d, name)

                    # Installed date from dist-info timestamp
                    installed_date = "Unknown"
                    try:
                        if hasattr(d, "_path") and os.path.exists(d._path):
                            installed_date = datetime.datetime.fromtimestamp(
                                os.path.getmtime(d._path)
                            ).strftime("%Y-%m-%d")
                        else:
                            loc = d.locate_file("")
                            if os.path.exists(loc):
                                installed_date = datetime.datetime.fromtimestamp(
                                    os.path.getmtime(loc)
                                ).strftime("%Y-%m-%d")
                    except Exception:
                        pass

                    cached_latest = self.pypi_cache.get(name.lower(), version)

                    packages.append({
                        "name": name,
                        "version": version,
                        "latest": cached_latest,
                        "size": size_mb,
                        "date": installed_date,
                    })
                except Exception:
                    pass

            # 2. Fallback if importlib found 0 (e.g. frozen without path access)
            if not packages and self.target_python:
                self.log_queue_msg("Querying environment package list...", "dim")
                cmd = [self.target_python, "-m", "pip", "list", "--format=json"]
                flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=10, creationflags=flags)
                if res.returncode == 0:
                    raw_list = json.loads(res.stdout.strip())
                    for item in raw_list:
                        p_name = item.get("name", "Unknown")
                        p_ver = item.get("version", "0.0.0")
                        size_mb = self._calc_folder_size(p_name)
                        packages.append({
                            "name": p_name,
                            "version": p_ver,
                            "latest": p_ver,
                            "size": size_mb,
                            "date": datetime.date.today().strftime("%Y-%m-%d"),
                        })

        except Exception as e:
            self.msg_queue.put(("log", f"Scan error: {e}", "error"))

        self.msg_queue.put(("scan_done", packages))

    def log_queue_msg(self, text, tag="output"):
        self.msg_queue.put(("log", text, tag))

    def _check_pypi_latest(self, package_name):
        def worker():
            try:
                url = f"https://pypi.org/pypi/{package_name}/json"
                req = urllib.request.Request(url, headers={"User-Agent": "PipMan-v2.4"})
                with urllib.request.urlopen(req, timeout=4) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    latest_ver = data.get("info", {}).get("version")
                    if latest_ver:
                        self.pypi_cache[package_name.lower()] = latest_ver
                        self.msg_queue.put(("update_latest_ver", (package_name, latest_ver)))
            except Exception:
                pass

        threading.Thread(target=worker, daemon=True).start()

    def _apply_filter(self, query=""):
        q = query.strip().lower()
        if not q or self.placeholder_active or q == "search installed packages...":
            self.filtered_packages = list(self.all_packages)
        else:
            self.filtered_packages = [
                p for p in self.all_packages if q in p["name"].lower()
            ]

        self._sort_packages_data()
        self._render_table_rows()

    def _toggle_sort(self, key):
        if self.sort_key == key:
            self.sort_desc = not self.sort_desc
        else:
            self.sort_key = key
            self.sort_desc = False

        for col_name, col_key, ratio, anchor in self.columns:
            if col_key:
                lbl = self.header_cols[col_name]
                if col_key == self.sort_key:
                    indicator = " ▼" if self.sort_desc else " ▲"
                    lbl.config(text=f"{col_name}{indicator}", fg=THEME["accent_mint"])
                else:
                    lbl.config(text=f"{col_name} ⇅", fg=THEME["text_muted"])

        self._sort_packages_data()
        self._render_table_rows()

    def _sort_packages_data(self):
        if self.sort_key == "name":
            self.filtered_packages.sort(
                key=lambda x: x["name"].lower(), reverse=self.sort_desc
            )
        elif self.sort_key == "version":
            self.filtered_packages.sort(
                key=lambda x: x["version"], reverse=self.sort_desc
            )
        elif self.sort_key == "latest":
            self.filtered_packages.sort(
                key=lambda x: x["latest"], reverse=self.sort_desc
            )
        elif self.sort_key == "size":
            self.filtered_packages.sort(
                key=lambda x: x["size"], reverse=self.sort_desc
            )
        elif self.sort_key == "date":
            self.filtered_packages.sort(
                key=lambda x: x["date"], reverse=self.sort_desc
            )

    # -------------------------------------------------------------
    # Table Rendering
    # -------------------------------------------------------------
    def _render_table_rows(self):
        for child in self.scrollable_frame.winfo_children():
            child.destroy()

        self.lbl_installed.config(
            text=f"INSTALLED PACKAGES ({len(self.filtered_packages)})"
        )

        if not self.filtered_packages:
            if not self.target_python:
                # No Python found on this machine
                empty_card = tk.Frame(
                    self.scrollable_frame,
                    bg=THEME["bg_card"],
                    highlightbackground=THEME["border_glow"],
                    highlightthickness=1,
                    bd=0,
                    padx=20,
                    pady=25,
                )
                empty_card.pack(fill=tk.X, padx=10, pady=20)

                tk.Label(
                    empty_card,
                    text="⚠️  No Python Installation Detected on this Computer",
                    font=self.font_title,
                    fg=THEME["accent_mint"],
                    bg=THEME["bg_card"],
                ).pack(pady=(0, 6))

                tk.Label(
                    empty_card,
                    text="PipMan requires a Python environment to manage and install packages.\nPlease install Python or select an existing Python executable below:",
                    font=self.font_regular,
                    fg=THEME["text_muted"],
                    bg=THEME["bg_card"],
                    justify=tk.CENTER,
                ).pack(pady=(0, 16))

                btn_frame = tk.Frame(empty_card, bg=THEME["bg_card"])
                btn_frame.pack()

                btn_dl = tk.Button(
                    btn_frame,
                    text="⬇ Download Python (python.org)",
                    font=self.font_bold,
                    bg="#112520",
                    fg=THEME["accent_mint"],
                    activebackground=THEME["accent_mint"],
                    activeforeground="#0b1113",
                    bd=0,
                    highlightthickness=1,
                    highlightbackground=THEME["border_glow"],
                    padx=14,
                    pady=6,
                    cursor="hand2",
                    command=self._open_python_download,
                )
                btn_dl.pack(side=tk.LEFT, padx=8)
                self._bind_button_hover(btn_dl, "#112520", THEME["accent_mint"], THEME["accent_mint"], "#0b1113")

                btn_browse = tk.Button(
                    btn_frame,
                    text="📁 Browse Python Path...",
                    font=self.font_bold,
                    bg="#162325",
                    fg=THEME["text_main"],
                    activebackground="#223a3e",
                    activeforeground="#ffffff",
                    bd=0,
                    highlightthickness=1,
                    highlightbackground="#2d484d",
                    padx=14,
                    pady=6,
                    cursor="hand2",
                    command=self.select_custom_python,
                )
                btn_browse.pack(side=tk.LEFT, padx=8)
                self._bind_button_hover(btn_browse, "#162325", THEME["text_main"], "#223a3e", "#ffffff")
            else:
                empty_lbl = tk.Label(
                    self.scrollable_frame,
                    text="No packages match your search.",
                    font=self.font_regular,
                    fg=THEME["text_dim"],
                    bg=THEME["bg_main"],
                    pady=40,
                )
                empty_lbl.pack(fill=tk.X)
            return

        for index, pkg in enumerate(self.filtered_packages, start=1):
            self._create_row_card(index, pkg)

    def _create_row_card(self, index, pkg):
        row_frame = tk.Frame(
            self.scrollable_frame,
            bg=THEME["bg_card"],
            highlightbackground=THEME["bg_card_border"],
            highlightthickness=1,
            bd=0,
            height=38,
        )
        row_frame.pack(fill=tk.X, pady=3, ipady=3)
        row_frame.pack_propagate(False)

        def on_enter(e):
            row_frame.config(bg=THEME["bg_card_hover"], highlightbackground=THEME["border_glow"])
            for widget in row_frame.winfo_children():
                if isinstance(widget, (tk.Label, tk.Frame)):
                    widget.config(bg=THEME["bg_card_hover"])

        def on_leave(e):
            row_frame.config(bg=THEME["bg_card"], highlightbackground=THEME["bg_card_border"])
            for widget in row_frame.winfo_children():
                if isinstance(widget, (tk.Label, tk.Frame)):
                    widget.config(bg=THEME["bg_card"])

        row_frame.bind("<Enter>", on_enter)
        row_frame.bind("<Leave>", on_leave)

        # 1. Package Name (Numbered: "1. matplotlib")
        name_text = f"{index}.  {pkg['name']}"
        lbl_name = tk.Label(
            row_frame,
            text=name_text,
            font=self.font_bold,
            fg=THEME["text_main"],
            bg=THEME["bg_card"],
            anchor=tk.W,
            padx=10,
        )
        lbl_name.place(relx=self._get_col_relx("Package Name"), rely=0, relwidth=0.28, relheight=1.0)
        lbl_name.bind("<Enter>", on_enter)
        lbl_name.bind("<Leave>", on_leave)

        # 2. Current Version
        lbl_ver = tk.Label(
            row_frame,
            text=pkg["version"],
            font=self.font_regular,
            fg=THEME["text_main"],
            bg=THEME["bg_card"],
            anchor=tk.W,
            padx=10,
        )
        lbl_ver.place(relx=self._get_col_relx("Current Version"), rely=0, relwidth=0.15, relheight=1.0)
        lbl_ver.bind("<Enter>", on_enter)
        lbl_ver.bind("<Leave>", on_leave)

        # 3. Latest Version
        latest_fg = THEME["text_main"]
        if pkg["latest"] != pkg["version"]:
            latest_fg = THEME["accent_yellow"]

        lbl_latest = tk.Label(
            row_frame,
            text=pkg["latest"],
            font=self.font_regular,
            fg=latest_fg,
            bg=THEME["bg_card"],
            anchor=tk.W,
            padx=10,
            cursor="hand2",
        )
        lbl_latest.place(relx=self._get_col_relx("Latest Version"), rely=0, relwidth=0.15, relheight=1.0)
        lbl_latest.bind("<Enter>", on_enter)
        lbl_latest.bind("<Leave>", on_leave)
        lbl_latest.bind("<Button-1>", lambda e, p=pkg["name"]: self._check_pypi_latest(p))

        # 4. Size
        if pkg["size"] >= 1.0:
            size_display = f"{pkg['size']:.1f} MB"
        elif pkg["size"] >= 0.001:
            size_display = f"{pkg['size']*1024:.0f} KB"
        else:
            size_display = "< 1 KB"
        lbl_size = tk.Label(
            row_frame,
            text=size_display,
            font=self.font_regular,
            fg=THEME["text_main"],
            bg=THEME["bg_card"],
            anchor=tk.W,
            padx=10,
        )
        lbl_size.place(relx=self._get_col_relx("Size"), rely=0, relwidth=0.12, relheight=1.0)
        lbl_size.bind("<Enter>", on_enter)
        lbl_size.bind("<Leave>", on_leave)

        # 5. Installed Date
        lbl_date = tk.Label(
            row_frame,
            text=pkg["date"],
            font=self.font_regular,
            fg=THEME["text_muted"],
            bg=THEME["bg_card"],
            anchor=tk.W,
            padx=10,
        )
        lbl_date.place(relx=self._get_col_relx("Installed Date"), rely=0, relwidth=0.16, relheight=1.0)
        lbl_date.bind("<Enter>", on_enter)
        lbl_date.bind("<Leave>", on_leave)

        # 6. Actions
        actions_frame = tk.Frame(row_frame, bg=THEME["bg_card"])
        actions_frame.place(relx=self._get_col_relx("Actions"), rely=0, relwidth=0.14, relheight=1.0)
        actions_frame.bind("<Enter>", on_enter)
        actions_frame.bind("<Leave>", on_leave)

        btn_update = tk.Button(
            actions_frame,
            text="Update",
            font=self.font_small,
            bg="#112520",
            fg=THEME["accent_mint"],
            activebackground=THEME["accent_mint"],
            activeforeground="#0b1113",
            bd=0,
            highlightthickness=1,
            highlightbackground=THEME["btn_update_border"],
            padx=8,
            pady=1,
            cursor="hand2",
            command=lambda p=pkg["name"]: self.update_package(p),
        )
        btn_update.pack(side=tk.LEFT, padx=(0, 6), pady=4)
        self._bind_button_hover(
            btn_update, "#112520", THEME["accent_mint"], THEME["accent_mint"], "#0b1113"
        )

        btn_uninstall = tk.Button(
            actions_frame,
            text="Uninstall",
            font=self.font_small,
            bg="#112520",
            fg=THEME["btn_uninstall_fg"],
            activebackground=THEME["btn_uninstall_hover_bg"],
            activeforeground="#ffffff",
            bd=0,
            highlightthickness=1,
            highlightbackground=THEME["btn_uninstall_border"],
            padx=8,
            pady=1,
            cursor="hand2",
            command=lambda p=pkg["name"]: self.uninstall_package(p),
        )
        btn_uninstall.pack(side=tk.LEFT, pady=4)
        self._bind_button_hover(
            btn_uninstall,
            "#112520",
            THEME["btn_uninstall_fg"],
            THEME["btn_uninstall_hover_bg"],
            "#ffffff",
        )

    # -------------------------------------------------------------
    # Subprocess Operations with Target Python
    # -------------------------------------------------------------
    def update_package(self, package_name):
        if self.active_process and self.active_process.poll() is None:
            messagebox.showwarning(
                "Task Busy", "Another pip operation is already running.", parent=self.root
            )
            return

        cmd = [self.target_python, "-m", "pip", "install", "--upgrade", package_name]
        cmd_str = f"pip install --upgrade {package_name}"
        self.log_prompt_cmd(cmd_str)
        self._execute_pip_async(cmd, on_success=self.refresh_packages)

    def uninstall_package(self, package_name):
        if self.active_process and self.active_process.poll() is None:
            messagebox.showwarning(
                "Task Busy", "Another pip operation is already running.", parent=self.root
            )
            return

        confirm = messagebox.askyesno(
            "Confirm Uninstall",
            f"Are you sure you want to uninstall '{package_name}'?",
            parent=self.root,
        )
        if not confirm:
            return

        cmd = [self.target_python, "-m", "pip", "uninstall", "-y", package_name]
        cmd_str = f"pip uninstall -y {package_name}"
        self.log_prompt_cmd(cmd_str)
        self._execute_pip_async(cmd, on_success=self.refresh_packages)

    def _execute_pip_async(self, cmd_args, on_success=None):
        def worker():
            try:
                flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
                self.active_process = subprocess.Popen(
                    cmd_args,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    creationflags=flags,
                )

                for line in iter(self.active_process.stdout.readline, ""):
                    if line:
                        self.msg_queue.put(("log", line.rstrip(), "output"))

                self.active_process.stdout.close()
                code = self.active_process.wait()

                if code == 0:
                    self.msg_queue.put(
                        ("log", "Command completed successfully (exit code 0)", "success")
                    )
                    if on_success:
                        self.msg_queue.put(("callback", on_success))
                else:
                    self.msg_queue.put(("log", f"Command exited with code {code}", "error"))

            except Exception as e:
                self.msg_queue.put(("log", f"Execution error: {e}", "error"))

            self.msg_queue.put(("prompt_end", None))

        threading.Thread(target=worker, daemon=True).start()

    # -------------------------------------------------------------
    # Queue Processing & Terminal Logs
    # -------------------------------------------------------------
    def _process_queue(self):
        try:
            while not self.msg_queue.empty():
                item = self.msg_queue.get_nowait()
                msg_type = item[0]

                if msg_type == "log":
                    text, tag = item[1], item[2] if len(item) > 2 else "output"
                    self.log_line(text, tag=tag)
                elif msg_type == "scan_done":
                    self.all_packages = item[1]
                    self.is_loading = False
                    self.btn_refresh.config(text="Refresh", state=tk.NORMAL)
                    self.btn_top_refresh.config(state=tk.NORMAL)
                    self.log_line(f"Loaded {len(self.all_packages)} installed packages.", tag="success")
                    self.log_line("pipman ~$ ", tag="prompt", end="")
                    self._apply_filter(self.search_var.get().strip())
                elif msg_type == "update_latest_ver":
                    pkg_name, latest_ver = item[1]
                    for p in self.all_packages:
                        if p["name"].lower() == pkg_name.lower():
                            p["latest"] = latest_ver
                    self._apply_filter(self.search_var.get().strip())
                elif msg_type == "prompt_end":
                    self.log_line("pipman ~$ ", tag="prompt", end="")
                elif msg_type == "callback":
                    item[1]()
        except Exception:
            pass

        self.root.after(80, self._process_queue)

    def log_line(self, text, tag="output", end="\n"):
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, text + end, tag)
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)

    def log_prompt_cmd(self, cmd_text):
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, "pipman ~$ ", "prompt")
        self.log_text.insert(tk.END, cmd_text + "\n", "cmd")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)

    def clear_log(self):
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete("1.0", tk.END)
        self.log_text.insert(tk.END, "pipman ~$ ", "prompt")
        self.log_text.config(state=tk.DISABLED)

    def toggle_log_panel(self):
        if self.log_visible:
            self.terminal_frame.pack_forget()
            self.btn_toggle_log.config(text="□")
            self.log_visible = False
        else:
            self.terminal_frame.pack(fill=tk.BOTH, expand=True)
            self.btn_toggle_log.config(text="—")
            self.log_visible = True
    def _open_python_download(self):
        webbrowser.open("https://www.python.org/downloads/")
        self.log_line("Opened https://www.python.org/downloads/ in default browser.", tag="info")

    def select_custom_python(self):
        file_path = filedialog.askopenfilename(
            title="Select Python Executable",
            filetypes=[("Python Executable", "python.exe;*.exe"), ("All Files", "*.*")],
            parent=self.root,
        )
        if file_path and os.path.isfile(file_path):
            self.target_python = file_path
            self.site_dirs = discover_site_packages(self.target_python)
            self.log_line(f"Active Python set to: {self.target_python}", tag="success")
            self.refresh_packages()


def main():
    root = tk.Tk()
    app = PipManApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
