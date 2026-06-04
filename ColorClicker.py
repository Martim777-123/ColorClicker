import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
import json
import os
import math
import colorsys
import struct
import wave
import tempfile
import random

try:
    import mss
    MSS_AVAILABLE = True
except ImportError:
    MSS_AVAILABLE = False

try:
    from PIL import Image, ImageTk
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

try:
    from pynput import keyboard as pynput_keyboard
    from pynput import mouse as pynput_mouse
    from pynput.mouse import Button, Controller as MouseController
    PYNPUT_AVAILABLE = True
except ImportError:
    PYNPUT_AVAILABLE = False

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False

APP_NAME      = "ColorClicker"
CONFIG_FILE   = os.path.join(os.path.expanduser("~"), ".colorclicker_config.json")
PROFILES_FILE = os.path.join(os.path.expanduser("~"), ".colorclicker_profiles.json")

DEFAULT_CONFIG = {
    "click_sound":      True,
    "live_overlay":     True,
    "region_highlight": True,
    "hotkey":           "f6",
}

BG       = "#f4f4f4"
SURFACE  = "#ffffff"
SURFACE2 = "#ebebeb"
BORDER   = "#d0d0d0"
TEXT     = "#111111"
TEXT2    = "#555555"
TEXT3    = "#999999"
ACCENT   = "#111111"
ACCENT2  = "#333333"
RED      = "#e53935"
GREEN    = "#2e7d32"

FNT_TITLE = ("Segoe UI", 20, "bold")
FNT_HEAD  = ("Segoe UI", 12, "bold")
FNT_LABEL = ("Segoe UI", 8,  "bold")
FNT_BODY  = ("Segoe UI", 10)
FNT_BOLD  = ("Segoe UI", 10, "bold")
FNT_SMALL = ("Segoe UI", 9)
FNT_BTN   = ("Segoe UI", 13, "bold")


def hex_to_rgb(h):
    h = h.strip().lstrip('#')
    if len(h) != 6:
        raise ValueError
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

def rgb_to_hex(r, g, b):
    return f'#{int(r):02x}{int(g):02x}{int(b):02x}'

def luminance(r, g, b):
    return 0.299*r + 0.587*g + 0.114*b

def generate_tone(freqs, duration=0.06, volume=0.08, gap=0.015):
    sr = 44100
    buf = []
    for freq in freqs:
        n = int(sr * duration)
        for i in range(n):
            fade = 1.0 - (i / n)
            val = int(32767 * volume * math.sin(2 * math.pi * freq * (i / sr)) * fade)
            buf.append(struct.pack('<h', max(-32768, min(32767, val))))
        for _ in range(int(sr * gap)):
            buf.append(struct.pack('<h', 0))
    return b''.join(buf), sr

def play_pcm(pcm, sr):
    try:
        tmp = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
        with wave.open(tmp.name, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sr)
            wf.writeframes(pcm)
        tmp.close()
        if os.name == 'nt':
            import winsound
            winsound.PlaySound(tmp.name, winsound.SND_FILENAME | winsound.SND_ASYNC)
        else:
            import subprocess
            subprocess.Popen(['aplay', tmp.name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass

def play_start():
    pcm, sr = generate_tone([500, 700, 900])
    threading.Thread(target=play_pcm, args=(pcm, sr), daemon=True).start()

def play_stop():
    pcm, sr = generate_tone([900, 700, 500])
    threading.Thread(target=play_pcm, args=(pcm, sr), daemon=True).start()


class Btn(tk.Button):
    STYLES = {
        'primary':   (ACCENT,   '#ffffff', ACCENT2,   '#ffffff'),
        'secondary': (SURFACE2, TEXT2,     BORDER,    TEXT),
        'danger':    ('#fdecea', RED,       '#f5c6cb', RED),
        'ghost':     (BG,       TEXT3,     SURFACE2,  TEXT2),
    }
    def __init__(self, parent, text, command=None, style='primary', **kw):
        bg, fg, hbg, hfg = self.STYLES.get(style, self.STYLES['primary'])
        super().__init__(parent, text=text, command=command,
                         bg=bg, fg=fg, activebackground=hbg, activeforeground=hfg,
                         relief='flat', font=FNT_BOLD, cursor='hand2',
                         padx=14, pady=7, bd=0, **kw)
        self._bg = bg; self._hbg = hbg; self._fg = fg; self._hfg = hfg
        self.bind('<Enter>', lambda e: self.configure(bg=hbg, fg=hfg))
        self.bind('<Leave>', lambda e: self.configure(bg=self._bg, fg=self._fg))

    def set_style(self, style):
        bg, fg, hbg, hfg = self.STYLES.get(style, self.STYLES['primary'])
        self._bg = bg; self._hbg = hbg; self._fg = fg; self._hfg = hfg
        self.configure(bg=bg, fg=fg, activebackground=hbg, activeforeground=hfg)


class Card(tk.Frame):
    def __init__(self, parent, **kw):
        super().__init__(parent, bg=SURFACE, highlightbackground=BORDER,
                         highlightthickness=1, relief='flat', **kw)


class RegionSelector(tk.Toplevel):
    def __init__(self, parent, callback):
        super().__init__(parent)
        self.callback = callback
        self.sx = self.sy = None
        self.rect = None
        self.attributes('-fullscreen', True)
        self.attributes('-alpha', 0.3)
        self.configure(bg='#000000', cursor='crosshair')
        self.lift()
        self.focus_force()
        self.canvas = tk.Canvas(self, bg='#000000', highlightthickness=0)
        self.canvas.pack(fill='both', expand=True)
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        self.canvas.create_text(sw//2, sh//2,
            text="Drag to select a region  •  Esc to cancel",
            fill='#ffffff', font=("Segoe UI", 16), justify='center')
        self.canvas.bind('<Button-1>', self._press)
        self.canvas.bind('<B1-Motion>', self._drag)
        self.canvas.bind('<ButtonRelease-1>', self._release)
        self.bind('<Escape>', lambda e: (self.destroy(), self.callback(None)))

    def _press(self, e):
        self.sx, self.sy = e.x, e.y
        if self.rect:
            self.canvas.delete(self.rect)

    def _drag(self, e):
        if self.rect:
            self.canvas.delete(self.rect)
        self.rect = self.canvas.create_rectangle(
            self.sx, self.sy, e.x, e.y,
            outline='#ffffff', width=2, fill='#ffffff', stipple='gray12')

    def _release(self, e):
        if self.sx is None:
            return
        x1, y1 = min(self.sx, e.x), min(self.sy, e.y)
        x2, y2 = max(self.sx, e.x), max(self.sy, e.y)
        self.destroy()
        if x2-x1 > 10 and y2-y1 > 10:
            self.callback((x1, y1, x2, y2))
        else:
            self.callback(None)


class RegionOverlay(tk.Toplevel):
    def __init__(self, region):
        super().__init__()
        x1, y1, x2, y2 = region
        w, h = x2-x1, y2-y1
        self.overrideredirect(True)
        self.wm_attributes('-alpha', 0.22)
        self.geometry(f'{w}x{h}+{x1}+{y1}')
        self.configure(bg='#1565c0')
        canvas = tk.Canvas(self, bg='#1565c0', highlightthickness=0)
        canvas.pack(fill='both', expand=True)
        canvas.create_rectangle(2, 2, w-2, h-2, outline='#90caf9', width=2, fill='')
        self.lower()

    def close(self):
        try:
            self.destroy()
        except Exception:
            pass


class ColorWheelPicker(tk.Toplevel):
    def __init__(self, parent, callback):
        super().__init__(parent)
        self.callback = callback
        self.selected = (255, 0, 0)
        self.wimg = None
        self.wphoto = None
        self.updating_from_hex = False
        SIZE = 200
        self.SIZE = SIZE

        self.title("Pick a Color")
        self.configure(bg=BG)
        self.resizable(False, False)
        self.geometry("360x420")
        self.grab_set()
        self.transient(parent)

        tk.Label(self, text="Pick a Color", bg=BG, fg=TEXT, font=FNT_HEAD).pack(pady=(16, 2))
        tk.Label(self, text="Click the wheel or type a hex value",
                 bg=BG, fg=TEXT3, font=FNT_SMALL).pack()

        self.canvas = tk.Canvas(self, width=SIZE, height=SIZE, bg=BG,
                                highlightthickness=0, cursor='crosshair')
        self.canvas.pack(pady=10)
        self.canvas.bind('<Button-1>', self._wheel_click)
        self.canvas.bind('<B1-Motion>', self._wheel_click)

        row = tk.Frame(self, bg=BG)
        row.pack(pady=4)

        self.swatch = tk.Label(row, bg='#ff0000', width=4, height=2, relief='flat')
        self.swatch.pack(side='left', padx=(0, 10))

        self.hex_var = tk.StringVar(value='#ff0000')
        ef = tk.Frame(row, bg=BORDER, padx=1, pady=1)
        ef.pack(side='left')
        self.hex_entry = tk.Entry(ef, textvariable=self.hex_var, width=9,
                     bg=SURFACE, fg=TEXT, insertbackground=TEXT,
                     relief='flat', font=("Segoe UI", 12), bd=6)
        self.hex_entry.pack()
        self.hex_var.trace_add('write', self._on_hex_type)

        brow = tk.Frame(self, bg=BG)
        brow.pack(pady=12)
        Btn(brow, "Confirm", command=self._confirm, style='primary').pack(side='left', padx=5)

        self.after(50, self._draw_wheel)

    def _draw_wheel(self):
        if not PIL_AVAILABLE:
            tk.Label(self, text="Install Pillow to use the color wheel.\npip install pillow",
                     bg=BG, fg=RED, font=FNT_BODY).pack()
            return
        SIZE = self.SIZE
        img = Image.new('RGB', (SIZE, SIZE), BG)
        cx = cy = SIZE // 2
        r = SIZE // 2 - 4
        px = img.load()
        for y in range(SIZE):
            for x in range(SIZE):
                dx, dy = x-cx, y-cy
                d = math.sqrt(dx*dx + dy*dy)
                if d <= r:
                    hue = (math.atan2(dy, dx) + math.pi) / (2*math.pi)
                    sat = d / r
                    rv, gv, bv = colorsys.hsv_to_rgb(hue, sat, 1.0)
                    px[x, y] = (int(rv*255), int(gv*255), int(bv*255))
        self.wimg = img
        self.wphoto = ImageTk.PhotoImage(img)
        self.canvas.create_image(0, 0, anchor='nw', image=self.wphoto)

    def _wheel_click(self, e):
        if not self.wimg:
            return
        x = max(0, min(e.x, self.SIZE-1))
        y = max(0, min(e.y, self.SIZE-1))
        try:
            self.selected = self.wimg.getpixel((x, y))
            self.updating_from_hex = True
            h = rgb_to_hex(*self.selected)
            self.hex_var.set(h)
            self.swatch.configure(bg=h)
            self.updating_from_hex = False
        except Exception:
            pass

    def _on_hex_type(self, *args):
        if self.updating_from_hex:
            return
        val = self.hex_var.get().strip()
        if not val.startswith('#'):
            val = '#' + val
        if len(val) == 7:
            try:
                rgb = hex_to_rgb(val)
                self.selected = rgb
                self.swatch.configure(bg=val)
            except Exception:
                pass

    def _confirm(self):
        val = self.hex_var.get().strip()
        if not val.startswith('#'):
            val = '#' + val
        if len(val) == 7:
            try:
                self.selected = hex_to_rgb(val)
            except Exception:
                pass
        self.callback(self.selected)
        self.destroy()


class OverlayHUD:
    def __init__(self):
        self.win = None
        self.label = None

    def show(self, clicks, status, fps):
        if self.win is None or not self.win.winfo_exists():
            self.win = tk.Toplevel()
            self.win.overrideredirect(True)
            self.win.attributes('-topmost', True)
            self.win.attributes('-alpha', 0.92)
            self.win.geometry('+12+12')
            self.win.configure(bg='#111111')
            self.label = tk.Label(self.win, bg='#111111', fg='#ffffff',
                                  font=("Segoe UI", 10, "bold"), padx=12, pady=6)
            self.label.pack()
        color = '#4caf50' if status == 'Running' else '#ef5350'
        self.label.configure(
            text=f"  ●  {status}   Clicks: {clicks}   {fps:.0f}/s  ",
            fg=color)

    def hide(self):
        if self.win and self.win.winfo_exists():
            self.win.destroy()
        self.win = None
        self.label = None


class ColorClicker:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title(APP_NAME)
        self.root.configure(bg=BG)
        self.root.resizable(False, False)
        self.root.geometry("500x780")

        self.config   = self._load(CONFIG_FILE,   DEFAULT_CONFIG)
        self.profiles = self._load(PROFILES_FILE, {"profiles": [], "active": ""})

        self.running     = False
        self.click_count = 0
        self.region      = None
        self.colors      = []
        self.excl_colors  = []
        self.extra_regions = []
        self.region_hl   = None

        self.overlay         = OverlayHUD()
        self.hotkey_listener = None
        self.screen_listener = None

        self._style_ttk()

        self.main_frame   = tk.Frame(self.root, bg=BG)
        self.config_frame = tk.Frame(self.root, bg=BG)

        self._build_main()
        self._build_config_page()

        self.main_frame.pack(fill='both', expand=True)

        self._start_hotkeys()
        self._load_active_profile()

        self.root.protocol("WM_DELETE_WINDOW", self._close)
        self.root.mainloop()

    def _load(self, path, default):
        try:
            if os.path.exists(path):
                with open(path) as f:
                    return json.load(f)
        except Exception:
            pass
        return dict(default)

    def _save_file(self, path, data):
        try:
            with open(path, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

    def _style_ttk(self):
        s = ttk.Style()
        s.theme_use('clam')
        s.configure('TCombobox', fieldbackground=SURFACE, background=SURFACE,
                    foreground=TEXT, selectbackground=SURFACE2, selectforeground=TEXT)
        s.map('TCombobox', fieldbackground=[('readonly', SURFACE)])

    def _section_label(self, parent, text):
        tk.Label(parent, text=text, bg=BG, fg=TEXT3,
                 font=FNT_LABEL).pack(anchor='w', pady=(14, 4), padx=20)

    def _small_entry(self, parent, var, width=7):
        ef = tk.Frame(parent, bg=BORDER, padx=1, pady=1)
        tk.Entry(ef, textvariable=var, width=width, bg=SURFACE, fg=TEXT,
                 insertbackground=TEXT, relief='flat', font=FNT_BODY,
                 bd=5, justify='center').pack()
        return ef

    def _build_main(self):
        p = self.main_frame

        header = tk.Frame(p, bg=BG)
        header.pack(fill='x', padx=20, pady=(22, 0))
        tk.Label(header, text="ColorClicker", bg=BG, fg=TEXT, font=FNT_TITLE).pack(side='left')
        tk.Button(header, text="⚙", bg=BG, fg=TEXT3, relief='flat',
                  font=("Segoe UI", 15), cursor='hand2', bd=0,
                  activebackground=BG, activeforeground=TEXT,
                  command=self._show_config).pack(side='right', pady=4)

        tk.Frame(p, bg=BORDER, height=1).pack(fill='x', padx=20, pady=10)

        scroll_container = tk.Frame(p, bg=BG)
        scroll_container.pack(fill='both', expand=True)

        self._canvas = tk.Canvas(scroll_container, bg=BG, highlightthickness=0)
        scrollbar = tk.Scrollbar(scroll_container, orient='vertical', command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side='right', fill='y')
        self._canvas.pack(side='left', fill='both', expand=True)

        self._scroll_frame = tk.Frame(self._canvas, bg=BG)
        self._scroll_win = self._canvas.create_window((0, 0), window=self._scroll_frame, anchor='nw')

        def on_frame_configure(e):
            self._canvas.configure(scrollregion=self._canvas.bbox('all'))

        def on_canvas_configure(e):
            self._canvas.itemconfig(self._scroll_win, width=e.width)

        self._scroll_frame.bind('<Configure>', on_frame_configure)
        self._canvas.bind('<Configure>', on_canvas_configure)

        def on_mousewheel(e):
            self._canvas.yview_scroll(int(-1 * (e.delta / 120)), 'units')

        self._canvas.bind_all('<MouseWheel>', on_mousewheel)

        p = self._scroll_frame

        self._section_label(p, "SCAN REGION")
        reg_card = Card(p)
        reg_card.pack(fill='x', padx=20)
        reg_inner = tk.Frame(reg_card, bg=SURFACE)
        reg_inner.pack(fill='x', padx=14, pady=10)
        self.region_label = tk.Label(reg_inner, text="No region selected",
                                     bg=SURFACE, fg=TEXT3, font=FNT_BODY, anchor='w')
        self.region_label.pack(side='left', fill='x', expand=True)
        Btn(reg_inner, "Clear",  command=self._clear_region,  style='ghost').pack(side='right', padx=(4, 0))
        Btn(reg_inner, "Select", command=self._select_region, style='secondary').pack(side='right', padx=(4, 0))

        self._section_label(p, "TARGET COLORS")
        color_card = Card(p)
        color_card.pack(fill='x', padx=20)
        btn_row = tk.Frame(color_card, bg=SURFACE)
        btn_row.pack(fill='x', padx=14, pady=(10, 6))
        Btn(btn_row, "Color Wheel",      command=self._add_color,   style='secondary').pack(side='left')
        Btn(btn_row, "Pick from Screen", command=self._pick_screen, style='secondary').pack(side='left', padx=(6, 0))
        self.color_list = tk.Frame(color_card, bg=SURFACE)
        self.color_list.pack(fill='x', padx=14, pady=(0, 10))
        self._refresh_colors()

        self._section_label(p, "CLICK SETTINGS")
        sc = Card(p)
        sc.pack(fill='x', padx=20)
        inner = tk.Frame(sc, bg=SURFACE)
        inner.pack(fill='x', padx=14, pady=10)

        tol_row = tk.Frame(inner, bg=SURFACE)
        tol_row.pack(fill='x', pady=(0, 2))
        tk.Label(tol_row, text="Color Tolerance", bg=SURFACE, fg=TEXT2, font=FNT_BOLD).pack(side='left')
        self.tol_val_label = tk.Label(tol_row, text="20", bg=SURFACE, fg=TEXT, font=FNT_BOLD)
        self.tol_val_label.pack(side='right')
        tk.Label(inner, text="How close a color needs to be to match. Higher = less strict.",
                 bg=SURFACE, fg=TEXT3, font=FNT_SMALL, wraplength=430, justify='left').pack(anchor='w', pady=(0, 4))
        self.tol_var = tk.IntVar(value=20)
        tk.Scale(inner, from_=0, to=100, orient='horizontal', variable=self.tol_var,
                 bg=SURFACE, fg=TEXT2, highlightthickness=0, troughcolor=SURFACE2,
                 activebackground=ACCENT, relief='flat', showvalue=False, sliderlength=20,
                 command=lambda v: self.tol_val_label.configure(text=str(int(float(v))))).pack(fill='x', pady=(0, 10))

        int_row = tk.Frame(inner, bg=SURFACE)
        int_row.pack(fill='x', pady=(0, 6))
        tk.Label(int_row, text="Click Interval (seconds)", bg=SURFACE, fg=TEXT2, font=FNT_BODY).pack(side='left')
        self.interval_var = tk.StringVar(value="0.10")
        self._small_entry(int_row, self.interval_var).pack(side='right')

        rand_row = tk.Frame(inner, bg=SURFACE)
        rand_row.pack(fill='x', pady=(0, 6))
        self.rand_var = tk.BooleanVar(value=False)
        tk.Checkbutton(rand_row, text="Randomize interval (more human-like)",
                       variable=self.rand_var, bg=SURFACE, activebackground=SURFACE,
                       fg=TEXT2, selectcolor=SURFACE2, font=FNT_BODY,
                       relief='flat', cursor='hand2').pack(side='left')

        mode_row = tk.Frame(inner, bg=SURFACE)
        mode_row.pack(fill='x', pady=(0, 6))
        tk.Label(mode_row, text="Click Mode", bg=SURFACE, fg=TEXT2, font=FNT_BODY).pack(side='left')
        self.click_mode = tk.StringVar(value="left")
        for m in ['left', 'right', 'both']:
            tk.Radiobutton(mode_row, text=m.capitalize(), variable=self.click_mode, value=m,
                           bg=SURFACE, activebackground=SURFACE, fg=TEXT2,
                           selectcolor=SURFACE2, font=FNT_BODY, relief='flat',
                           cursor='hand2').pack(side='right', padx=4)

        lim_row = tk.Frame(inner, bg=SURFACE)
        lim_row.pack(fill='x', pady=(0, 6))
        tk.Label(lim_row, text="Click Limit  (0 = unlimited)", bg=SURFACE, fg=TEXT2, font=FNT_BODY).pack(side='left')
        self.limit_var = tk.StringVar(value="0")
        self._small_entry(lim_row, self.limit_var).pack(side='right')

        off_row = tk.Frame(inner, bg=SURFACE)
        off_row.pack(fill='x', pady=(0, 2))
        tk.Label(off_row, text="Click Offset Randomization", bg=SURFACE, fg=TEXT2, font=FNT_BOLD).pack(side='left')
        self.offset_val_label = tk.Label(off_row, text="0 px", bg=SURFACE, fg=TEXT, font=FNT_BOLD)
        self.offset_val_label.pack(side='right')
        tk.Label(inner, text="Randomly shifts each click by up to this many pixels. Looks more natural.",
                 bg=SURFACE, fg=TEXT3, font=FNT_SMALL, wraplength=430, justify='left').pack(anchor='w', pady=(0, 4))
        self.offset_var = tk.IntVar(value=0)
        tk.Scale(inner, from_=0, to=30, orient='horizontal', variable=self.offset_var,
                 bg=SURFACE, fg=TEXT2, highlightthickness=0, troughcolor=SURFACE2,
                 activebackground=ACCENT, relief='flat', showvalue=False, sliderlength=20,
                 command=lambda v: self.offset_val_label.configure(text=f"{int(float(v))} px")).pack(fill='x', pady=(0, 6))

        jitter_row = tk.Frame(inner, bg=SURFACE)
        jitter_row.pack(fill='x', pady=(0, 8))
        self.jitter_var = tk.BooleanVar(value=False)
        tk.Checkbutton(jitter_row, text="Click jitter  (nudges the mouse around the spot before clicking)",
                       variable=self.jitter_var, bg=SURFACE, activebackground=SURFACE,
                       fg=TEXT2, selectcolor=SURFACE2, font=FNT_BODY,
                       relief='flat', cursor='hand2').pack(side='left')

        mp_row = tk.Frame(inner, bg=SURFACE)
        mp_row.pack(fill='x', pady=(0, 2))
        tk.Label(mp_row, text="Multi-Click Points", bg=SURFACE, fg=TEXT2, font=FNT_BOLD).pack(side='left')
        self.multiclick_val_label = tk.Label(mp_row, text="1", bg=SURFACE, fg=TEXT, font=FNT_BOLD)
        self.multiclick_val_label.pack(side='right')
        tk.Label(inner, text="How many spread-out points on the matched area to click each pass. "
                             "Useful for clicking all over a large object like a ball.",
                 bg=SURFACE, fg=TEXT3, font=FNT_SMALL, wraplength=430, justify='left').pack(anchor='w', pady=(0, 4))
        self.multiclick_var = tk.IntVar(value=1)
        tk.Scale(inner, from_=1, to=20, orient='horizontal', variable=self.multiclick_var,
                 bg=SURFACE, fg=TEXT2, highlightthickness=0, troughcolor=SURFACE2,
                 activebackground=ACCENT, relief='flat', showvalue=False, sliderlength=20,
                 command=lambda v: self.multiclick_val_label.configure(text=str(int(float(v))))).pack(fill='x', pady=(0, 4))

        self._section_label(p, "EXCLUDED COLORS")
        excl_card = Card(p)
        excl_card.pack(fill='x', padx=20)
        excl_top = tk.Frame(excl_card, bg=SURFACE)
        excl_top.pack(fill='x', padx=14, pady=(10, 4))
        tk.Label(excl_top, text="Colors to never click, even if they match a target.",
                 bg=SURFACE, fg=TEXT3, font=FNT_SMALL).pack(side='left')
        excl_btns = tk.Frame(excl_card, bg=SURFACE)
        excl_btns.pack(fill='x', padx=14, pady=(0, 6))
        Btn(excl_btns, "Color Wheel",      command=self._add_excl_color,        style='secondary').pack(side='left')
        Btn(excl_btns, "Pick from Screen", command=self._pick_screen_excl,      style='secondary').pack(side='left', padx=(6, 0))
        self.excl_list = tk.Frame(excl_card, bg=SURFACE)
        self.excl_list.pack(fill='x', padx=14, pady=(0, 10))
        self._refresh_excl()

        self._section_label(p, "SCAN REGIONS")
        mreg_card = Card(p)
        mreg_card.pack(fill='x', padx=20)
        mreg_top = tk.Frame(mreg_card, bg=SURFACE)
        mreg_top.pack(fill='x', padx=14, pady=(10, 4))
        tk.Label(mreg_top, text="Add multiple regions — the clicker scans all of them each pass.",
                 bg=SURFACE, fg=TEXT3, font=FNT_SMALL).pack(side='left')
        mreg_btns = tk.Frame(mreg_card, bg=SURFACE)
        mreg_btns.pack(fill='x', padx=14, pady=(0, 6))
        Btn(mreg_btns, "Add Region", command=self._add_extra_region, style='secondary').pack(side='left')
        self.extra_regions_frame = tk.Frame(mreg_card, bg=SURFACE)
        self.extra_regions_frame.pack(fill='x', padx=14, pady=(0, 10))
        self._refresh_extra_regions()

        self._section_label(p, "PROFILES")
        pc = Card(p)
        pc.pack(fill='x', padx=20)
        pi = tk.Frame(pc, bg=SURFACE)
        pi.pack(fill='x', padx=14, pady=10)
        self.profile_var = tk.StringVar(value="")
        self.profile_combo = ttk.Combobox(pi, textvariable=self.profile_var,
                                          font=FNT_BODY, state='readonly', width=16)
        self.profile_combo.pack(side='left')
        self._refresh_profiles()
        for label, cmd, st in [("Load", self._load_profile, 'secondary'),
                                ("Save", self._save_profile, 'secondary'),
                                ("Delete", self._del_profile, 'ghost')]:
            Btn(pi, label, command=cmd, style=st).pack(side='left', padx=(6, 0))

        self.status_label = tk.Label(p, text="Ready", bg=BG, fg=TEXT3, font=FNT_SMALL)
        self.status_label.pack(anchor='w', padx=24, pady=(12, 0))

        self.start_btn = tk.Button(p, text="Start", command=self._toggle,
                                   bg=ACCENT, fg='#ffffff',
                                   activebackground=ACCENT2, activeforeground='#ffffff',
                                   relief='flat', font=FNT_BTN,
                                   pady=16, cursor='hand2', bd=0)
        self.start_btn.pack(fill='x', padx=20, pady=(6, 20))

    def _build_config_page(self):
        p = self.config_frame

        header = tk.Frame(p, bg=BG)
        header.pack(fill='x', padx=20, pady=(22, 0))
        tk.Button(header, text="← Back", command=self._show_main,
                  bg=BG, fg=TEXT2, relief='flat', font=FNT_BOLD,
                  cursor='hand2', bd=0, activebackground=BG,
                  activeforeground=TEXT).pack(side='left')
        tk.Label(header, text="Settings", bg=BG, fg=TEXT, font=FNT_TITLE).pack(side='left', padx=(10, 0))

        tk.Frame(p, bg=BORDER, height=1).pack(fill='x', padx=20, pady=10)

        tk.Label(p, text="TOGGLES", bg=BG, fg=TEXT3, font=FNT_LABEL).pack(anchor='w', padx=20, pady=(6, 4))
        toggle_card = Card(p)
        toggle_card.pack(fill='x', padx=20)
        ti = tk.Frame(toggle_card, bg=SURFACE)
        ti.pack(fill='x', padx=14, pady=8)

        self.cfg_vars = {}
        for key, label in [
            ('click_sound',      'Play sound on Start / Stop'),
            ('live_overlay',     'Show live HUD overlay'),
            ('region_highlight', 'Highlight the scan region'),
        ]:
            v = tk.BooleanVar(value=self.config.get(key, True))
            self.cfg_vars[key] = v
            row = tk.Frame(ti, bg=SURFACE)
            row.pack(fill='x', pady=5)
            tk.Label(row, text=label, bg=SURFACE, fg=TEXT2, font=FNT_BODY, anchor='w').pack(side='left')
            tk.Checkbutton(row, variable=v, bg=SURFACE, activebackground=SURFACE,
                           selectcolor=SURFACE2, relief='flat', cursor='hand2').pack(side='right')

        tk.Label(p, text="HOTKEY", bg=BG, fg=TEXT3, font=FNT_LABEL).pack(anchor='w', padx=20, pady=(14, 4))
        hk_card = Card(p)
        hk_card.pack(fill='x', padx=20)
        hi = tk.Frame(hk_card, bg=SURFACE)
        hi.pack(fill='x', padx=14, pady=10)
        row = tk.Frame(hi, bg=SURFACE)
        row.pack(fill='x')
        tk.Label(row, text="Start / Stop Hotkey", bg=SURFACE, fg=TEXT2, font=FNT_BODY).pack(side='left')
        self.hk_var = tk.StringVar(value=self.config.get('hotkey', 'f6'))
        self._small_entry(row, self.hk_var, width=6).pack(side='right')
        tk.Label(hi, text="Press this key to toggle the clicker on and off.",
                 bg=SURFACE, fg=TEXT3, font=FNT_SMALL).pack(anchor='w', pady=(4, 0))

        Btn(p, "Save Settings", command=self._save_config, style='primary').pack(pady=18, padx=20, fill='x')

    def _show_main(self):
        self.config_frame.pack_forget()
        self.main_frame.pack(fill='both', expand=True)

    def _show_config(self):
        self.main_frame.pack_forget()
        self.config_frame.pack(fill='both', expand=True)

    def _save_config(self):
        for k, v in self.cfg_vars.items():
            self.config[k] = v.get()
        self.config['hotkey'] = self.hk_var.get().lower().strip()
        self._save_file(CONFIG_FILE, self.config)
        self._restart_hotkeys()
        self._show_main()

    def _select_region(self):
        self._hide_hl()
        self.root.withdraw()
        self.root.update()
        def after_select(region):
            self.root.deiconify()
            if region:
                self.region = region
                x1, y1, x2, y2 = region
                self.region_label.configure(
                    text=f"({x1}, {y1})  →  ({x2}, {y2})   {x2-x1} × {y2-y1} px",
                    fg=TEXT)
                if self.config.get('region_highlight', True):
                    self.root.after(100, lambda: self._show_hl(region))
        self.root.after(150, lambda: RegionSelector(self.root, after_select))

    def _show_hl(self, region):
        self._hide_hl()
        try:
            self.region_hl = RegionOverlay(region)
        except Exception:
            pass

    def _hide_hl(self):
        if self.region_hl:
            try:
                self.region_hl.close()
            except Exception:
                pass
            self.region_hl = None

    def _clear_region(self):
        self.region = None
        self.region_label.configure(text="No region selected", fg=TEXT3)
        self._hide_hl()

    def _add_color(self):
        ColorWheelPicker(self.root, self._on_color)

    def _pick_screen(self):
        if not PYNPUT_AVAILABLE or not MSS_AVAILABLE:
            messagebox.showwarning("Missing dependency", "pynput and mss are required for screen picking.")
            return
        if self.screen_listener:
            return
        self.root.withdraw()
        self.root.update()

        picked = [False]

        def on_click(x, y, button, pressed):
            if not pressed or picked[0]:
                return
            picked[0] = True
            color = None
            try:
                with mss.mss() as sct:
                    mon = {'left': int(x), 'top': int(y), 'width': 1, 'height': 1}
                    img = sct.grab(mon)
                    b, g, r = img.raw[0], img.raw[1], img.raw[2]
                    color = (r, g, b)
            except Exception:
                pass
            self.screen_listener = None
            def finish():
                if color:
                    self.colors.append(color)
                    self._refresh_colors()
                self.root.deiconify()
            self.root.after(0, finish)
            return False

        self.screen_listener = pynput_mouse.Listener(on_click=on_click)
        self.screen_listener.daemon = True
        self.screen_listener.start()

    def _add_excl_color(self):
        ColorWheelPicker(self.root, self._on_excl_color)

    def _pick_screen_excl(self):
        if not PYNPUT_AVAILABLE or not MSS_AVAILABLE:
            messagebox.showwarning("Missing dependency", "pynput and mss are required for screen picking.")
            return
        if self.screen_listener:
            return
        self.root.withdraw()
        self.root.update()
        picked = [False]

        def on_click(x, y, button, pressed):
            if not pressed or picked[0]:
                return
            picked[0] = True
            color = None
            try:
                with mss.mss() as sct:
                    mon = {'left': int(x), 'top': int(y), 'width': 1, 'height': 1}
                    img = sct.grab(mon)
                    b, g, r = img.raw[0], img.raw[1], img.raw[2]
                    color = (r, g, b)
            except Exception:
                pass
            self.screen_listener = None
            def finish():
                if color:
                    self.excl_colors.append(color)
                    self._refresh_excl()
                self.root.deiconify()
            self.root.after(0, finish)
            return False

        self.screen_listener = pynput_mouse.Listener(on_click=on_click)
        self.screen_listener.daemon = True
        self.screen_listener.start()

    def _on_excl_color(self, rgb):
        self.excl_colors.append(rgb)
        self._refresh_excl()

    def _refresh_excl(self):
        for w in self.excl_list.winfo_children():
            w.destroy()
        if not self.excl_colors:
            tk.Label(self.excl_list, text="No excluded colors",
                     bg=SURFACE, fg=TEXT3, font=FNT_SMALL, pady=4).pack()
            return
        for i, (r, g, b) in enumerate(self.excl_colors):
            h = rgb_to_hex(r, g, b)
            row = tk.Frame(self.excl_list, bg=SURFACE2)
            row.pack(fill='x', pady=2)
            tk.Label(row, bg=h, width=3, height=1).pack(side='left', padx=(8, 10), pady=4)
            tk.Label(row, text=f"{h}   rgb({r}, {g}, {b})",
                     bg=SURFACE2, fg=TEXT2, font=FNT_SMALL).pack(side='left')
            idx = i
            tk.Button(row, text="✕", command=lambda i=idx: self._remove_excl(i),
                      bg=SURFACE2, fg=TEXT3, relief='flat', font=FNT_SMALL,
                      cursor='hand2', activebackground=SURFACE2,
                      activeforeground=RED, bd=0).pack(side='right', padx=8)

    def _remove_excl(self, i):
        if 0 <= i < len(self.excl_colors):
            self.excl_colors.pop(i)
            self._refresh_excl()

    def _add_extra_region(self):
        self.root.withdraw()
        self.root.update()
        def after_select(region):
            self.root.deiconify()
            if region:
                self.extra_regions.append(region)
                self._refresh_extra_regions()
        self.root.after(150, lambda: RegionSelector(self.root, after_select))

    def _refresh_extra_regions(self):
        for w in self.extra_regions_frame.winfo_children():
            w.destroy()
        if not self.extra_regions:
            tk.Label(self.extra_regions_frame, text="No extra regions added",
                     bg=SURFACE, fg=TEXT3, font=FNT_SMALL, pady=4).pack()
            return
        for i, (x1, y1, x2, y2) in enumerate(self.extra_regions):
            row = tk.Frame(self.extra_regions_frame, bg=SURFACE2)
            row.pack(fill='x', pady=2)
            tk.Label(row, text=f"  Region {i+1}   ({x1},{y1}) → ({x2},{y2})   {x2-x1}×{y2-y1}",
                     bg=SURFACE2, fg=TEXT2, font=FNT_SMALL).pack(side='left', pady=4)
            idx = i
            tk.Button(row, text="✕", command=lambda i=idx: self._remove_extra_region(i),
                      bg=SURFACE2, fg=TEXT3, relief='flat', font=FNT_SMALL,
                      cursor='hand2', activebackground=SURFACE2,
                      activeforeground=RED, bd=0).pack(side='right', padx=8)

    def _remove_extra_region(self, i):
        if 0 <= i < len(self.extra_regions):
            self.extra_regions.pop(i)
            self._refresh_extra_regions()

    def _on_color(self, rgb):
        self.colors.append(rgb)
        self._refresh_colors()

    def _refresh_colors(self):
        for w in self.color_list.winfo_children():
            w.destroy()
        if not self.colors:
            tk.Label(self.color_list, text="No colors added yet",
                     bg=SURFACE, fg=TEXT3, font=FNT_SMALL, pady=6).pack()
            return
        for i, (r, g, b) in enumerate(self.colors):
            h = rgb_to_hex(r, g, b)
            row = tk.Frame(self.color_list, bg=SURFACE2)
            row.pack(fill='x', pady=2)
            tk.Label(row, bg=h, width=3, height=1).pack(side='left', padx=(8, 10), pady=5)
            tk.Label(row, text=f"{h}   rgb({r}, {g}, {b})",
                     bg=SURFACE2, fg=TEXT2, font=FNT_SMALL).pack(side='left')
            idx = i
            tk.Button(row, text="✕", command=lambda i=idx: self._remove_color(i),
                      bg=SURFACE2, fg=TEXT3, relief='flat', font=FNT_SMALL,
                      cursor='hand2', activebackground=SURFACE2,
                      activeforeground=RED, bd=0).pack(side='right', padx=8)

    def _remove_color(self, i):
        if 0 <= i < len(self.colors):
            self.colors.pop(i)
            self._refresh_colors()

    def _toggle(self):
        if self.running:
            self._stop()
        else:
            self._start()

    def _start(self):
        if not self.colors:
            messagebox.showwarning("No colors", "Add at least one target color first.")
            return
        if self.region is None:
            messagebox.showwarning("No region", "Select a scan region first.")
            return
        if not MSS_AVAILABLE or not NUMPY_AVAILABLE or not PYNPUT_AVAILABLE:
            messagebox.showwarning("Missing dependencies", "Install mss, numpy and pynput to run the clicker.")
            return
        self.running = True
        self.click_count = 0
        self.start_btn.configure(text="Stop", bg=RED, activebackground='#c62828')
        self.status_label.configure(text="Running...", fg=GREEN)
        if self.config.get('click_sound', True):
            play_start()
        if self.config.get('live_overlay', True):
            self.overlay.show(0, 'Running', 0)
        self.root.iconify()
        threading.Thread(target=self._loop, daemon=True).start()

    def _stop(self):
        self.running = False
        self.start_btn.configure(text="Start", bg=ACCENT, activebackground=ACCENT2)
        self.status_label.configure(text=f"Stopped  —  {self.click_count} clicks", fg=TEXT3)
        if self.config.get('click_sound', True):
            play_stop()
        self.root.after(800, self.overlay.hide)
        self.root.deiconify()

    def _loop(self):
        mc = MouseController()
        x1, y1, x2, y2 = self.region
        all_regions = [(x1, y1, x2, y2)] + list(self.extra_regions)
        monitors = [{'left': rx1, 'top': ry1, 'width': rx2-rx1, 'height': ry2-ry1}
                    for rx1, ry1, rx2, ry2 in all_regions]
        targets      = [np.array(c, dtype=np.int32) for c in self.colors]
        excl_targets = [np.array(c, dtype=np.int32) for c in self.excl_colors]
        frame_times  = []

        with mss.mss() as sct:
            while self.running:
                t0 = time.time()

                try:
                    limit = int(self.limit_var.get())
                except Exception:
                    limit = 0
                try:
                    interval = float(self.interval_var.get())
                except Exception:
                    interval = 0.1
                tolerance   = self.tol_var.get()
                mode        = self.click_mode.get()
                rand        = self.rand_var.get()
                offset      = self.offset_var.get()
                jitter      = self.jitter_var.get()
                multiclick  = self.multiclick_var.get()

                if limit > 0 and self.click_count >= limit:
                    self.root.after(0, self._stop)
                    break

                clicked = False
                try:
                    for (rx1, ry1, rx2, ry2), mon in zip(all_regions, monitors):
                        if clicked:
                            break
                        img = sct.grab(mon)
                        arr = np.frombuffer(img.raw, dtype=np.uint8).reshape((img.height, img.width, 4))
                        arr_rgb = arr[:, :, 2::-1].astype(np.int32)
                        for tc in targets:
                            diff = arr_rgb - tc
                            dist = np.sqrt((diff**2).sum(axis=2))
                            matches = np.argwhere(dist <= tolerance)
                            if not len(matches):
                                continue

                            valid = []
                            for py, px in matches:
                                is_excl = False
                                if excl_targets:
                                    pixel = arr_rgb[py, px]
                                    for ec in excl_targets:
                                        if np.sqrt(((pixel - ec)**2).sum()) <= tolerance:
                                            is_excl = True
                                            break
                                if not is_excl:
                                    valid.append((int(py), int(px)))

                            if not valid:
                                continue

                            if multiclick == 1:
                                chosen = [valid[0]]
                            else:
                                step = max(1, len(valid) // multiclick)
                                chosen = valid[::step][:multiclick]
                                if len(chosen) < multiclick and len(valid) >= multiclick:
                                    chosen = random.sample(valid, multiclick)

                            for py, px in chosen:
                                abs_x = rx1 + px
                                abs_y = ry1 + py
                                if offset > 0:
                                    abs_x += random.randint(-offset, offset)
                                    abs_y += random.randint(-offset, offset)
                                mc.position = (abs_x, abs_y)
                                if jitter:
                                    for _ in range(3):
                                        mc.position = (abs_x + random.randint(-4, 4),
                                                       abs_y + random.randint(-4, 4))
                                        time.sleep(0.01)
                                    mc.position = (abs_x, abs_y)
                                    time.sleep(0.01)
                                if mode in ('left', 'both'):
                                    mc.click(Button.left)
                                if mode in ('right', 'both'):
                                    mc.click(Button.right)
                                self.click_count += 1
                                if multiclick > 1:
                                    time.sleep(0.015)

                            clicked = True
                            break
                        if clicked:
                            break
                except Exception:
                    pass

                elapsed = time.time() - t0
                frame_times.append(elapsed)
                if len(frame_times) > 10:
                    frame_times.pop(0)
                avg = sum(frame_times) / len(frame_times)
                fps = 1.0 / avg if avg > 0 else 0

                if self.config.get('live_overlay', True):
                    c = self.click_count
                    self.root.after(0, lambda c=c, f=fps: self.overlay.show(c, 'Running', f))

                sleep = interval * (random.uniform(0.7, 1.4) if rand else 1.0)
                time.sleep(max(0, sleep - elapsed))

    def _start_hotkeys(self):
        if not PYNPUT_AVAILABLE:
            return

        def on_press(key):
            try:
                name = key.name if hasattr(key, 'name') else str(key).replace("'", "")
                if name == self.config.get('hotkey', 'f6'):
                    if self.running:
                        self.root.after(0, self._stop)
                    else:
                        self.root.after(0, self._start)
            except Exception:
                pass

        self.hotkey_listener = pynput_keyboard.Listener(on_press=on_press)
        self.hotkey_listener.daemon = True
        self.hotkey_listener.start()

    def _restart_hotkeys(self):
        if self.hotkey_listener:
            try:
                self.hotkey_listener.stop()
            except Exception:
                pass
        self._start_hotkeys()

    def _refresh_profiles(self):
        names = [p['name'] for p in self.profiles.get('profiles', [])]
        self.profile_combo['values'] = names
        active = self.profiles.get('active', '')
        self.profile_var.set(active if active in names else (names[0] if names else ''))

    def _load_active_profile(self):
        active = self.profiles.get('active', '')
        for p in self.profiles.get('profiles', []):
            if p['name'] == active:
                self._apply(p)
                return

    def _load_profile(self):
        name = self.profile_var.get()
        if not name:
            return
        for p in self.profiles.get('profiles', []):
            if p['name'] == name:
                self._apply(p)
                self.profiles['active'] = name
                self._save_file(PROFILES_FILE, self.profiles)
                return

    def _apply(self, p):
        self.colors = [tuple(c) for c in p.get('colors', [])]
        self.excl_colors = [tuple(c) for c in p.get('excl_colors', [])]
        self.extra_regions = [tuple(r) for r in p.get('extra_regions', [])]
        val = p.get('tolerance', 20)
        self.tol_var.set(val)
        self.tol_val_label.configure(text=str(val))
        self.interval_var.set(f"{p.get('interval', 0.1):.2f}")
        self.rand_var.set(p.get('randomize_interval', False))
        self.click_mode.set(p.get('click_mode', 'left'))
        self.limit_var.set(str(p.get('click_limit', 0)))
        ov = p.get('offset', 0)
        self.offset_var.set(ov)
        self.offset_val_label.configure(text=f"{ov} px")
        self.jitter_var.set(p.get('jitter', False))
        mv = p.get('multiclick', 1)
        self.multiclick_var.set(mv)
        self.multiclick_val_label.configure(text=str(mv))
        reg = p.get('region')
        if reg:
            self.region = tuple(reg)
            x1, y1, x2, y2 = self.region
            self.region_label.configure(
                text=f"({x1}, {y1})  →  ({x2}, {y2})   {x2-x1} × {y2-y1} px", fg=TEXT)
            if self.config.get('region_highlight', True):
                self.root.after(200, lambda: self._show_hl(self.region))
        self._refresh_colors()
        self._refresh_excl()
        self._refresh_extra_regions()

    def _save_profile(self):
        name = self.profile_var.get().strip()
        if not name:
            messagebox.showwarning("No name", "Type a profile name in the box first.")
            return
        try:
            interval = float(self.interval_var.get())
        except Exception:
            interval = 0.1
        try:
            limit = int(self.limit_var.get())
        except Exception:
            limit = 0
        p = {
            'name': name,
            'colors': [list(c) for c in self.colors],
            'excl_colors': [list(c) for c in self.excl_colors],
            'extra_regions': [list(r) for r in self.extra_regions],
            'tolerance': self.tol_var.get(),
            'offset': self.offset_var.get(),
            'jitter': self.jitter_var.get(),
            'multiclick': self.multiclick_var.get(),
            'interval': interval,
            'randomize_interval': self.rand_var.get(),
            'click_mode': self.click_mode.get(),
            'click_limit': limit,
            'region': list(self.region) if self.region else None,
        }
        profs = self.profiles.get('profiles', [])
        for i, pr in enumerate(profs):
            if pr['name'] == name:
                profs[i] = p
                break
        else:
            profs.append(p)
        self.profiles['profiles'] = profs
        self.profiles['active'] = name
        self._save_file(PROFILES_FILE, self.profiles)
        self._refresh_profiles()
        self.profile_var.set(name)

    def _del_profile(self):
        name = self.profile_var.get()
        if not name:
            return
        self.profiles['profiles'] = [p for p in self.profiles.get('profiles', []) if p['name'] != name]
        self._save_file(PROFILES_FILE, self.profiles)
        self._refresh_profiles()

    def _close(self):
        self.running = False
        self.overlay.hide()
        self._hide_hl()
        if self.hotkey_listener:
            try:
                self.hotkey_listener.stop()
            except Exception:
                pass
        if self.screen_listener:
            try:
                self.screen_listener.stop()
            except Exception:
                pass
        self.root.destroy()


if __name__ == '__main__':
    ColorClicker()
