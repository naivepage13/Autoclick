"""Quadrado indicador (verde = ativo, vermelho = parado) na lateral da tela."""
import tkinter as tk

from .winapi import user32


class Indicator:
    """Quadrado na lateral direita da tela: verde = ativo, vermelho = parado.
    Não rouba foco nem intercepta cliques."""
    SIZE = 28

    def __init__(self, root):
        self.win = tk.Toplevel(root)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
        self.win.geometry(f"{self.SIZE}x{self.SIZE}+{sw - self.SIZE - 4}+{sh // 2 - self.SIZE // 2}")
        self.win.configure(bg="#d32f2f")
        self.win.update_idletasks()
        # click-through, sem foco, fora da barra de tarefas
        hwnd = user32.GetParent(self.win.winfo_id()) or self.win.winfo_id()
        style = user32.GetWindowLongW(hwnd, -20)
        user32.SetWindowLongW(hwnd, -20, style | 0x80000 | 0x20 | 0x80 | 0x8000000)

    def set(self, active):
        self.win.configure(bg="#2e7d32" if active else "#d32f2f")
        self.win.attributes("-topmost", True)
