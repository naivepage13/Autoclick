"""Janela principal: repetição de tecla, gravação e reprodução de macros."""
import json
import queue
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from .indicator import Indicator
from .winapi import SCAN_VKS, is_down, key_name, send_key

HK_LABELS = {"auto": "Ligar/desligar repetição", "rec": "Gravar macro",
             "play": "Reproduzir macro"}


class App:
    def __init__(self, root):
        self.root = root
        root.title("AutoClick")
        root.resizable(False, False)

        self.target_vk = 0x20  # espaço por padrão
        self.hotkeys = {"auto": 0x75, "rec": 0x76, "play": 0x77}  # F6, F7, F8
        self.capturing = None  # "target" ou nome de um atalho
        self.auto_stop = threading.Event()
        self.auto_thread = None
        self.auto_on = False
        self.play_on = False
        self.recording = False
        self.rec_events = []
        self.rec_start = 0.0
        self.macro = []
        self.play_stop = threading.Event()
        self.play_thread = None
        self.ui_q = queue.Queue()

        pad = {"padx": 8, "pady": 4}
        f = ttk.LabelFrame(root, text="Repetir tecla")
        f.grid(row=0, column=0, sticky="ew", **pad)
        ttk.Label(f, text="Tecla:").grid(row=0, column=0, **pad)
        self.key_lbl = ttk.Label(f, width=24)
        self.key_lbl.grid(row=0, column=1, **pad)
        self.key_btn = ttk.Button(f, text="Escolher", command=lambda: self.start_capture("target"))
        self.key_btn.grid(row=0, column=2, **pad)
        ttk.Label(f, text="Intervalo (ms):").grid(row=1, column=0, **pad)
        self.interval = tk.StringVar(value="100")
        ttk.Entry(f, textvariable=self.interval, width=8).grid(row=1, column=1, sticky="w", **pad)
        self.auto_btn = ttk.Button(f, command=self.toggle_auto)
        self.auto_btn.grid(row=1, column=2, **pad)

        m = ttk.LabelFrame(root, text="Macro")
        m.grid(row=1, column=0, sticky="ew", **pad)
        self.rec_btn = ttk.Button(m, command=self.toggle_rec)
        self.rec_btn.grid(row=0, column=0, **pad)
        self.play_btn = ttk.Button(m, command=self.toggle_play)
        self.play_btn.grid(row=0, column=1, **pad)
        ttk.Label(m, text="Repetições (0 = infinito):").grid(row=1, column=0, columnspan=2, **pad)
        self.loops = tk.StringVar(value="1")
        ttk.Entry(m, textvariable=self.loops, width=6).grid(row=1, column=2, **pad)
        ttk.Button(m, text="Salvar...", command=self.save).grid(row=2, column=0, **pad)
        ttk.Button(m, text="Abrir...", command=self.load).grid(row=2, column=1, **pad)

        h = ttk.LabelFrame(root, text="Teclas de atalho (aceita botões laterais do mouse)")
        h.grid(row=2, column=0, sticky="ew", **pad)
        self.hk_lbl, self.hk_btn = {}, {}
        for i, name in enumerate(HK_LABELS):
            ttk.Label(h, text=HK_LABELS[name] + ":").grid(row=i, column=0, sticky="w", **pad)
            self.hk_lbl[name] = ttk.Label(h, width=24)
            self.hk_lbl[name].grid(row=i, column=1, **pad)
            self.hk_btn[name] = ttk.Button(h, text="Alterar",
                                           command=lambda n=name: self.start_capture(n))
            self.hk_btn[name].grid(row=i, column=2, **pad)

        self.top_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(root, text="Sempre no topo", variable=self.top_var,
                        command=lambda: root.attributes("-topmost", self.top_var.get())
                        ).grid(row=3, column=0, sticky="w", **pad)
        self.status = tk.StringVar(value="Pronto.")
        ttk.Label(root, textvariable=self.status).grid(row=4, column=0, sticky="w", **pad)

        self.indicator = Indicator(root)
        self.refresh_labels()
        threading.Thread(target=self.listener, daemon=True).start()
        self.pump()
        root.protocol("WM_DELETE_WINDOW", self.close)

    # ------------------------------------------------ UI helpers
    def ui(self, fn):
        self.ui_q.put(fn)

    def pump(self):
        try:
            while True:
                self.ui_q.get_nowait()()
        except queue.Empty:
            pass
        self.root.after(30, self.pump)

    def set_status(self, text):
        self.ui(lambda: self.status.set(text))

    def get_int(self, var, default, minimum=0):
        try:
            return max(minimum, int(float(var.get())))
        except ValueError:
            return default

    def is_auto(self):
        return self.auto_on

    def is_play(self):
        return self.play_on

    def refresh_labels(self):
        self.key_lbl.config(text=key_name(self.target_vk))
        for n, vk in self.hotkeys.items():
            self.hk_lbl[n].config(text=key_name(vk))
        self.key_btn.config(state="normal")
        for b in self.hk_btn.values():
            b.config(state="normal")
        hk = {n: key_name(v) for n, v in self.hotkeys.items()}
        self.auto_btn.config(text=("Parar" if self.is_auto() else "Iniciar") + f" ({hk['auto']})")
        self.rec_btn.config(text=("Parar gravação" if self.recording else "Gravar") + f" ({hk['rec']})")
        self.play_btn.config(text=("Parar" if self.is_play() else "Reproduzir") + f" ({hk['play']})")
        self.indicator.set(self.auto_on or self.play_on)

    # ------------------------------------------------ captura de tecla
    def start_capture(self, what):
        self.capturing = what
        self.key_btn.config(state="disabled")
        for b in self.hk_btn.values():
            b.config(state="disabled")
        lbl = self.key_lbl if what == "target" else self.hk_lbl[what]
        lbl.config(text="Pressione uma tecla...")

    def finish_capture(self, vk):
        what, self.capturing = self.capturing, None

        def apply():
            if what == "target":
                self.target_vk = vk
            else:
                clash = [n for n, h in self.hotkeys.items() if h == vk and n != what]
                if clash:
                    self.status.set("Essa tecla já é outro atalho.")
                else:
                    self.hotkeys[what] = vk
                    self.status.set(f"Atalho definido: {key_name(vk)}")
            self.refresh_labels()

        self.ui(apply)

    # ------------------------------------------------ autoclick
    def toggle_auto(self):
        if self.is_auto():
            self.auto_stop.set()
            return
        self.auto_stop = threading.Event()
        interval = self.get_int(self.interval, 100, 1) / 1000
        vk = self.target_vk
        stop = self.auto_stop

        def run():
            self.ui(self.refresh_labels)
            self.set_status(f"Repetindo [{key_name(vk)}]...")
            try:
                while not stop.is_set():
                    send_key(vk, True)
                    time.sleep(0.01)
                    send_key(vk, False)
                    stop.wait(max(0.001, interval - 0.01))
            finally:
                send_key(vk, False)
                self.auto_on = False
                self.ui(self.refresh_labels)
                self.set_status("Repetição parada.")

        self.auto_on = True
        self.auto_thread = threading.Thread(target=run, daemon=True)
        self.auto_thread.start()
        self.refresh_labels()

    # ------------------------------------------------ gravação
    def toggle_rec(self):
        if self.recording:
            self.recording = False
            self.macro = list(self.rec_events)
            self.status.set(f"Macro gravada: {len(self.macro)} eventos.")
            self.refresh_labels()
            return
        self.play_stop.set()
        self.rec_events = []
        self.rec_start = time.perf_counter()
        self.recording = True
        self.status.set("Gravando... (aperte o atalho de gravação para parar)")
        self.refresh_labels()

    # ------------------------------------------------ reprodução
    def toggle_play(self):
        if self.is_play():
            self.play_stop.set()
            return
        if self.recording:
            self.toggle_rec()
        if not self.macro:
            self.status.set("Nenhuma macro gravada.")
            return
        self.play_stop = threading.Event()
        stop = self.play_stop
        events = list(self.macro)
        loops = self.get_int(self.loops, 1)

        def run():
            self.ui(self.refresh_labels)
            held = set()
            n = 0
            try:
                while not stop.is_set() and (loops == 0 or n < loops):
                    n += 1
                    self.set_status(f"Reproduzindo... volta {n}" + (f"/{loops}" if loops else ""))
                    t0 = time.perf_counter()
                    for t, vk, down in events:
                        wait = t - (time.perf_counter() - t0)
                        if wait > 0 and stop.wait(wait):
                            break
                        if stop.is_set():
                            break
                        send_key(vk, down)
                        (held.add if down else held.discard)(vk)
                    else:
                        continue
                    break
            finally:
                for vk in held:
                    send_key(vk, False)
                self.play_on = False
                self.ui(self.refresh_labels)
                self.set_status("Reprodução parada.")

        self.play_on = True
        self.play_thread = threading.Thread(target=run, daemon=True)
        self.play_thread.start()
        self.refresh_labels()

    # ------------------------------------------------ salvar/abrir
    def save(self):
        if not self.macro:
            messagebox.showinfo("AutoClick", "Nenhuma macro para salvar.")
            return
        p = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("Macro", "*.json")])
        if p:
            with open(p, "w") as fh:
                json.dump(self.macro, fh)
            self.status.set("Macro salva.")

    def load(self):
        p = filedialog.askopenfilename(filetypes=[("Macro", "*.json")])
        if not p:
            return
        try:
            with open(p) as fh:
                self.macro = [(float(t), int(vk), bool(d)) for t, vk, d in json.load(fh)]
            self.status.set(f"Macro carregada: {len(self.macro)} eventos.")
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("AutoClick", f"Arquivo inválido: {e}")

    # ------------------------------------------------ listener global
    def listener(self):
        prev = {}
        actions = {"auto": self.toggle_auto, "rec": self.toggle_rec, "play": self.toggle_play}
        while True:
            time.sleep(0.004)
            for vk in SCAN_VKS:
                d = is_down(vk)
                if d == prev.get(vk, False):
                    continue
                prev[vk] = d
                if self.capturing:
                    if d:
                        self.finish_capture(vk)
                    continue
                name = next((n for n, h in self.hotkeys.items() if h == vk), None)
                if name:
                    if d:
                        self.ui(actions[name])
                elif self.recording:
                    self.rec_events.append((time.perf_counter() - self.rec_start, vk, d))

    def close(self):
        self.auto_stop.set()
        self.play_stop.set()
        self.root.destroy()


def main():
    root = tk.Tk()
    App(root)
    root.mainloop()
