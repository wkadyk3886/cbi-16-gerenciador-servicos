# -*- coding: utf-8 -*-
"""
PROJETO: TEMA_VISTOCAR — Módulo de Design System para Aplicativos Desktop
Compatível com Tkinter, ttk e CustomTkinter.

Centraliza a paleta oficial das variantes:
  - 'cbi'      (padrão): Preto/Grafite + Carmim Oficial CBI (#C02626) + Ouro Oficial Grupo VistoCar (#FFC30B)
  - 'vistocar'         : Azul Institucional (#071326 / #1D4ED8) + Ouro Oficial Grupo VistoCar (#FFC30B)
"""

from typing import Dict, Any

THEME_TOKENS: Dict[str, Dict[str, str]] = {
    "cbi": {
        "label": "CBI • Preto & Grafite",
        "primary": "#C02626",
        "primary_hover": "#A31B1B",
        "secondary": "#232833",
        "secondary_hover": "#2E3544",
        "accent": "#FFC30B",
        "accent_hover": "#E5AD00",
        "bg": "#090A0D",
        "bg_deep": "#050608",
        "surface": "#12151B",
        "surface_elevated": "#1A1E27",
        "surface_hover": "#222733",
        "input_bg": "#0D1015",
        "text_primary": "#F4F5F7",
        "text_secondary": "#9CA3AF",
        "text_muted": "#6B7280",
        "text_on_primary": "#FFFFFF",
        "text_on_accent": "#090A0D",
        "border": "#262C38",
        "border_strong": "#384152",
        "success": "#16A34A",
        "success_hover": "#15803D",
        "warning": "#F59E0B",
        "error": "#EF4444",
        "error_hover": "#DC2626",
        "info": "#38BDF8",
    },
    "vistocar": {
        "label": "Grupo VistoCar • Azul Institucional",
        "primary": "#1D4ED8",
        "primary_hover": "#1E40AF",
        "secondary": "#162C4E",
        "secondary_hover": "#1E3A66",
        "accent": "#FFC30B",
        "accent_hover": "#E5AD00",
        "bg": "#071326",
        "bg_deep": "#040C1A",
        "surface": "#0E1F3B",
        "surface_elevated": "#152B4F",
        "surface_hover": "#1C3866",
        "input_bg": "#0A172D",
        "text_primary": "#F8FAFC",
        "text_secondary": "#A7BCD8",
        "text_muted": "#6E89AD",
        "text_on_primary": "#FFFFFF",
        "text_on_accent": "#071326",
        "border": "#1F3B66",
        "border_strong": "#2E528A",
        "success": "#16A34A",
        "success_hover": "#15803D",
        "warning": "#F59E0B",
        "error": "#EF4444",
        "error_hover": "#DC2626",
        "info": "#38BDF8",
    },
}

FONT_SANS = "Segoe UI"
FONT_MONO = "Consolas"


def get_theme(variant: str = "cbi") -> Dict[str, str]:
    """Retorna o dicionário de tokens da variante institucional solicitada ('cbi' ou 'vistocar')."""
    key = (variant or "cbi").strip().lower()
    return dict(THEME_TOKENS.get(key, THEME_TOKENS["cbi"]))


def apply_ttk_theme(style: Any, variant: str = "cbi") -> Dict[str, str]:
    """Aplica o Design System TEMA_VISTOCAR a um ttk.Style preservando toda a estrutura de widgets."""
    t = get_theme(variant)
    try:
        style.theme_use("clam")
    except Exception:
        pass

    style.configure(".", background=t["bg"], foreground=t["text_primary"], font=(FONT_SANS, 9))
    style.configure("TFrame", background=t["bg"])
    style.configure("Card.TFrame", background=t["surface"], relief="flat")
    style.configure("TLabel", background=t["bg"], foreground=t["text_primary"], font=(FONT_SANS, 9))
    style.configure("Muted.TLabel", background=t["bg"], foreground=t["text_secondary"], font=(FONT_SANS, 9))
    style.configure("Card.TLabel", background=t["surface"], foreground=t["text_primary"], font=(FONT_SANS, 9))
    style.configure("TLabelframe", background=t["surface"], foreground=t["accent"], bordercolor=t["border"])
    style.configure("TLabelframe.Label", background=t["surface"], foreground=t["accent"], font=(FONT_SANS, 9, "bold"))

    style.configure(
        "TButton",
        background=t["secondary"],
        foreground=t["text_primary"],
        bordercolor=t["border_strong"],
        padding=(10, 6),
        font=(FONT_SANS, 9, "bold"),
    )
    style.map(
        "TButton",
        background=[("active", t["secondary_hover"]), ("disabled", t["surface"])],
        foreground=[("disabled", t["text_muted"])],
    )

    style.configure(
        "Primary.TButton",
        background=t["primary"],
        foreground=t["text_on_primary"],
        bordercolor=t["primary"],
        padding=(12, 6),
        font=(FONT_SANS, 9, "bold"),
    )
    style.map("Primary.TButton", background=[("active", t["primary_hover"])])

    style.configure(
        "TEntry",
        fieldbackground=t["input_bg"],
        foreground=t["text_primary"],
        insertcolor=t["accent"],
        bordercolor=t["border"],
    )
    style.configure(
        "TCombobox",
        fieldbackground=t["input_bg"],
        background=t["surface_elevated"],
        foreground=t["text_primary"],
        bordercolor=t["border"],
    )
    style.configure("TNotebook", background=t["bg"], bordercolor=t["border"])
    style.configure(
        "TNotebook.Tab",
        background=t["surface"],
        foreground=t["text_secondary"],
        padding=(12, 6),
        font=(FONT_SANS, 9, "bold"),
    )
    style.map(
        "TNotebook.Tab",
        background=[("selected", t["primary"]), ("active", t["surface_hover"])],
        foreground=[("selected", t["text_on_primary"])],
    )
    style.configure(
        "Treeview",
        background=t["surface"],
        fieldbackground=t["surface"],
        foreground=t["text_primary"],
        bordercolor=t["border"],
        rowheight=28,
        font=(FONT_SANS, 9),
    )
    style.configure(
        "Treeview.Heading",
        background=t["surface_elevated"],
        foreground=t["text_secondary"],
        bordercolor=t["border_strong"],
        font=(FONT_SANS, 9, "bold"),
        relief="flat",
    )
    style.map(
        "Treeview",
        background=[("selected", t["primary"])],
        foreground=[("selected", t["text_on_primary"])],
    )
    return t


def configure_ctk(ctk_module: Any, variant: str = "cbi") -> Dict[str, str]:
    """Configura modo escuro institucional no CustomTkinter e retorna os tokens ativos."""
    try:
        ctk_module.set_appearance_mode("dark")
    except Exception:
        pass
    return get_theme(variant)
