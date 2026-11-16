# -*- coding: utf-8 -*-
"""
monitor_servicos_cbi.py — Aplicativo Desktop Nativo (Tkinter) para Monitoramento
em Tempo Real dos Serviços Ativos de Todos os Aplicativos CBI (00 a 15 + Orquestrador).

Uso:
  python monitor_servicos_cbi.py                 -> Abre a janela Desktop Tkinter
  python monitor_servicos_cbi.py --snapshot-json -> Imprime o snapshot JSON no stdout e sai
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import webbrowser
from typing import Any, Dict, List, Optional

APP_DIR = os.path.dirname(os.path.abspath(__file__))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

import cbi_services_core as core


class MonitorServicosApp:
    def __init__(self, root: tk.Tk, auto_interval_sec: int = 3) -> None:
        self.root = root
        self.root.title("CBI Monitor — Monitoramento de Serviços Ativos (Apps 00 a 15)")
        self.root.geometry("1240x760")
        self.root.minsize(1020, 620)
        self.root.configure(bg="#F1F5F9")

        self.snapshot: Optional[Dict[str, Any]] = None
        self.scanning = False
        self.filter_mode = tk.StringVar(value="TODOS")
        self.search_var = tk.StringVar(value="")
        self.interval_var = tk.StringVar(value=f"{auto_interval_sec}s" if auto_interval_sec > 0 else "Manual")
        self._after_id: Optional[str] = None
        self.selected_service_id: Optional[str] = None

        self._setup_styles()
        self._build_ui()

        self.search_var.trace_add("write", lambda *_: self._render_table())
        self.refresh_async()
        self._schedule_next_refresh()

    def _setup_styles(self) -> None:
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure("Treeview", rowheight=27, font=("Segoe UI", 9), background="#FFFFFF", fieldbackground="#FFFFFF")
        style.configure("Treeview.Heading", font=("Segoe UI", 9, "bold"), background="#E2E8F0", foreground="#0F172A")
        style.map("Treeview", background=[("selected", "#DBEAFE")], foreground=[("selected", "#0F172A")])

    def _build_ui(self) -> None:
        # 1. Header escuro institucional
        header = tk.Frame(self.root, bg="#0B1220", height=64, padx=18, pady=10)
        header.pack(fill="x")
        header.pack_propagate(False)

        left_h = tk.Frame(header, bg="#0B1220")
        left_h.pack(side="left", fill="y")
        tk.Label(
            left_h,
            text="MONITOR DE SERVIÇOS ATIVOS — ECOSSISTEMA CBI",
            bg="#0B1220",
            fg="#F8FAFC",
            font=("Segoe UI", 13, "bold"),
        ).pack(anchor="w")
        self.lbl_root_dir = tk.Label(
            left_h,
            text=f"Raiz detectada: {core.discover_ecosystem_root()}",
            bg="#0B1220",
            fg="#94A3B8",
            font=("Segoe UI", 8),
        )
        self.lbl_root_dir.pack(anchor="w")

        right_h = tk.Frame(header, bg="#0B1220")
        right_h.pack(side="right", fill="y")
        tk.Button(
            right_h,
            text="Abrir Encerrador de Serviços",
            command=self._open_stopper_app,
            bg="#DC2626",
            fg="#FFFFFF",
            activebackground="#B91C1C",
            activeforeground="#FFFFFF",
            relief="flat",
            padx=12,
            pady=6,
            font=("Segoe UI", 9, "bold"),
            cursor="hand2",
        ).pack(side="right", padx=(8, 0), pady=4)
        tk.Button(
            right_h,
            text="Atualizar Agora",
            command=self.refresh_async,
            bg="#0EA5E9",
            fg="#FFFFFF",
            activebackground="#0284C7",
            activeforeground="#FFFFFF",
            relief="flat",
            padx=12,
            pady=6,
            font=("Segoe UI", 9, "bold"),
            cursor="hand2",
        ).pack(side="right", pady=4)

        # 2. KPI Cards
        kpi_bar = tk.Frame(self.root, bg="#F1F5F9", padx=16, pady=10)
        kpi_bar.pack(fill="x")

        self.kpi_vars: Dict[str, tk.StringVar] = {}
        kpi_defs = [
            ("online_web", "Servidores Web Online", "#059669"),
            ("active_pids", "Processos Ativos (PIDs)", "#0284C7"),
            ("total_ram", "RAM Total Consumida", "#7C3AED"),
            ("orphans", "Processos Órfãos/Extras", "#D97706"),
            ("last_scan", "Última Verificação", "#334155"),
        ]
        for idx, (key, title, color) in enumerate(kpi_defs):
            card = tk.Frame(kpi_bar, bg="#FFFFFF", bd=1, relief="solid", highlightbackground="#CBD5E1")
            card.grid(row=0, column=idx, sticky="nsew", padx=4)
            kpi_bar.columnconfigure(idx, weight=1)
            tk.Frame(card, bg=color, height=3).pack(fill="x")
            tk.Label(card, text=title, bg="#FFFFFF", fg="#64748B", font=("Segoe UI", 8, "bold"), anchor="w", padx=10).pack(fill="x", pady=(6, 0))
            var = tk.StringVar(value="-")
            self.kpi_vars[key] = var
            tk.Label(card, textvariable=var, bg="#FFFFFF", fg="#0F172A", font=("Segoe UI", 14, "bold"), anchor="w", padx=10).pack(fill="x", pady=(2, 8))

        # 3. Toolbar (Filtros + Busca + Auto-refresh + Ações)
        toolbar = tk.Frame(self.root, bg="#E2E8F0", padx=16, pady=8)
        toolbar.pack(fill="x")

        tk.Label(toolbar, text="Filtro:", bg="#E2E8F0", fg="#0F172A", font=("Segoe UI", 9, "bold")).pack(side="left")
        for label, val in [("Todos", "TODOS"), ("Somente Ativos", "ATIVOS"), ("Inativos / Offline", "INATIVOS")]:
            tk.Radiobutton(
                toolbar,
                text=label,
                variable=self.filter_mode,
                value=val,
                command=self._render_table,
                bg="#E2E8F0",
                activebackground="#E2E8F0",
                font=("Segoe UI", 9),
            ).pack(side="left", padx=(4, 6))

        tk.Label(toolbar, text="Buscar:", bg="#E2E8F0", fg="#0F172A", font=("Segoe UI", 9, "bold")).pack(side="left", padx=(12, 4))
        search_entry = tk.Entry(toolbar, textvariable=self.search_var, width=24, font=("Segoe UI", 9))
        search_entry.pack(side="left", padx=(0, 12))

        tk.Label(toolbar, text="Auto-atualizar:", bg="#E2E8F0", fg="#0F172A", font=("Segoe UI", 9, "bold")).pack(side="left")
        cmb = ttk.Combobox(toolbar, textvariable=self.interval_var, values=["Manual", "2s", "3s", "5s", "10s"], width=8, state="readonly")
        cmb.pack(side="left", padx=(4, 12))
        cmb.bind("<<ComboboxSelected>>", lambda *_: self._schedule_next_refresh())

        # Action buttons on the right side of toolbar
        tk.Button(toolbar, text="Exportar CSV", command=self._export_csv, bg="#475569", fg="#FFFFFF", relief="flat", padx=9, pady=4, font=("Segoe UI", 8, "bold"), cursor="hand2").pack(side="right", padx=3)
        tk.Button(toolbar, text="Abrir Navegador", command=self._open_selected_browser, bg="#2563EB", fg="#FFFFFF", relief="flat", padx=9, pady=4, font=("Segoe UI", 8, "bold"), cursor="hand2").pack(side="right", padx=3)
        tk.Button(toolbar, text="Reiniciar", command=self._restart_selected, bg="#D97706", fg="#FFFFFF", relief="flat", padx=9, pady=4, font=("Segoe UI", 8, "bold"), cursor="hand2").pack(side="right", padx=3)
        tk.Button(toolbar, text="Iniciar Serviço", command=self._start_selected, bg="#059669", fg="#FFFFFF", relief="flat", padx=9, pady=4, font=("Segoe UI", 8, "bold"), cursor="hand2").pack(side="right", padx=3)

        # 4. PanedWindow (Tabela principal em cima, Inspector/Abas em baixo)
        paned = tk.PanedWindow(self.root, orient="vertical", sashwidth=6, bg="#CBD5E1")
        paned.pack(fill="both", expand=True, padx=16, pady=(8, 12))

        table_frame = tk.Frame(paned, bg="#FFFFFF")
        cols = ("code", "name", "status", "port", "http_lat", "pids", "ram", "uptime", "exe")
        self.tree = ttk.Treeview(table_frame, columns=cols, show="headings", selectmode="browse")
        headers = [
            ("code", "Cód", 50, "center"),
            ("name", "Aplicativo / Serviço CBI", 290, "w"),
            ("status", "Status", 95, "center"),
            ("port", "Porta", 65, "center"),
            ("http_lat", "HTTP / Latência", 115, "center"),
            ("pids", "PIDs Ativos", 120, "center"),
            ("ram", "RAM (MB)", 85, "e"),
            ("uptime", "Uptime", 85, "center"),
            ("exe", "Executável / Script Principal", 240, "w"),
        ]
        for cid, text, width, anchor in headers:
            self.tree.heading(cid, text=text)
            self.tree.column(cid, width=width, anchor=anchor)

        self.tree.tag_configure("ONLINE", background="#ECFDF5", foreground="#065F46")
        self.tree.tag_configure("ATIVO", background="#EFF6FF", foreground="#1E40AF")
        self.tree.tag_configure("TRAVADO", background="#FEF3C7", foreground="#92400E")
        self.tree.tag_configure("OFFLINE", background="#FFFFFF", foreground="#64748B")
        self.tree.tag_configure("INATIVO", background="#FFFFFF", foreground="#64748B")

        vsb = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self.tree.bind("<<TreeviewSelect>>", self._on_select_row)
        self.tree.bind("<Double-1>", lambda *_: self._open_selected_browser())
        paned.add(table_frame, height=410)

        # Bottom Notebook: Detalhes, Processos Órfãos, Histórico
        bottom_nb = ttk.Notebook(paned)

        # Tab 1: Detalhes do serviço selecionado
        tab_details = tk.Frame(bottom_nb, bg="#0F172A")
        self.txt_details = tk.Text(
            tab_details,
            bg="#0F172A",
            fg="#E2E8F0",
            font=("Consolas", 9),
            relief="flat",
            padx=12,
            pady=10,
            wrap="word",
        )
        self.txt_details.pack(fill="both", expand=True)
        self.txt_details.insert("1.0", "Selecione qualquer serviço na tabela acima para inspecionar PIDs, portas, linha de comando e caminho.")
        self.txt_details.configure(state="disabled")
        bottom_nb.add(tab_details, text="Detalhes do Serviço & Processo")

        # Tab 2: Processos Órfãos / Extras CBI
        tab_orphans = tk.Frame(bottom_nb, bg="#FFFFFF")
        self.tree_orphans = ttk.Treeview(tab_orphans, columns=("pid", "name", "ports", "ram", "uptime", "cmd"), show="headings")
        for cid, txt, w in [
            ("pid", "PID", 75),
            ("name", "Processo", 150),
            ("ports", "Portas em Escuta", 120),
            ("ram", "RAM (MB)", 85),
            ("uptime", "Uptime", 90),
            ("cmd", "Linha de Comando", 580),
        ]:
            self.tree_orphans.heading(cid, text=txt)
            self.tree_orphans.column(cid, width=w)
        self.tree_orphans.pack(fill="both", expand=True)
        bottom_nb.add(tab_orphans, text="Processos Órfãos / Extras (0)")
        self.bottom_nb = bottom_nb
        self.tab_orphans = tab_orphans

        # Tab 3: Histórico de Operações
        tab_hist = tk.Frame(bottom_nb, bg="#FFFFFF")
        self.txt_history = tk.Text(tab_hist, bg="#F8FAFC", fg="#0F172A", font=("Consolas", 9), relief="flat", padx=10, pady=8)
        self.txt_history.pack(fill="both", expand=True)
        bottom_nb.add(tab_hist, text="Histórico de Operações")

        paned.add(bottom_nb, height=200)

        # Statusbar
        self.lbl_status = tk.Label(self.root, text="Pronto.", bg="#0B1220", fg="#CBD5E1", anchor="w", padx=14, pady=4, font=("Segoe UI", 8))
        self.lbl_status.pack(fill="x", side="bottom")

    def _schedule_next_refresh(self) -> None:
        if self._after_id is not None:
            try:
                self.root.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None
        val = self.interval_var.get().strip()
        if val.endswith("s") and val[:-1].isdigit():
            ms = int(val[:-1]) * 1000
            self._after_id = self.root.after(ms, self._auto_tick)

    def _auto_tick(self) -> None:
        self.refresh_async()
        self._schedule_next_refresh()

    def refresh_async(self) -> None:
        if self.scanning:
            return
        self.scanning = True
        self.lbl_status.configure(text="Varrendo portas TCP, HTTP e processos ativos...")

        def worker() -> None:
            try:
                snap = core.scan_all_services()
                hist = core.get_action_history(limit=40)
            except Exception as exc:
                snap = {"ok": False, "error": str(exc), "services": [], "orphan_processes": [], "summary": {}}
                hist = []
            self.root.after(0, lambda: self._apply_snapshot(snap, hist))

        threading.Thread(target=worker, daemon=True).start()

    def _apply_snapshot(self, snap: Dict[str, Any], hist: List[Dict[str, Any]]) -> None:
        self.scanning = False
        self.snapshot = snap
        s = snap.get("summary", {})
        self.kpi_vars["online_web"].set(f"{s.get('online_web', 0)} / {s.get('web_services', 0)}")
        self.kpi_vars["active_pids"].set(str(s.get("active_pids", 0)))
        self.kpi_vars["total_ram"].set(f"{s.get('total_ram_mb', 0.0):.1f} MB")
        self.kpi_vars["orphans"].set(str(s.get("orphan_processes", 0)))
        self.kpi_vars["last_scan"].set(snap.get("scanned_at", "-").split(" ")[-1])

        self._render_table()
        self._render_orphans()
        self._render_history(hist)
        self.lbl_status.configure(
            text=f"Última varredura: {snap.get('scanned_at', '-')} | "
                 f"Web Online: {s.get('online_web', 0)}/{s.get('web_services', 0)} | "
                 f"PIDs ativos: {s.get('active_pids', 0)} | "
                 f"RAM total: {s.get('total_ram_mb', 0.0):.1f} MB"
        )

    def _render_table(self) -> None:
        if not self.snapshot:
            return
        prev_sel = self.selected_service_id
        for item in self.tree.get_children():
            self.tree.delete(item)

        mode = self.filter_mode.get()
        q = self.search_var.get().strip().lower()

        for svc in self.snapshot.get("services", []):
            is_active = svc["status"] in ("ONLINE", "ATIVO", "TRAVADO")
            if mode == "ATIVOS" and not is_active:
                continue
            if mode == "INATIVOS" and is_active:
                continue
            if q:
                haystack = f"{svc['code']} {svc['name']} {svc['port'] or ''} {' '.join(str(p) for p in svc['pids'])} {' '.join(svc['exe_names'])}".lower()
                if q not in haystack:
                    continue

            http_lat = "-"
            if svc["port"]:
                if svc["tcp_open"]:
                    http_s = f"HTTP {svc['http_status']}" if svc.get("http_status") else "TCP OK"
                    lat_s = f"{svc['latency_ms']}ms" if svc.get("latency_ms") is not None else ""
                    http_lat = f"{http_s} ({lat_s})"
                else:
                    http_lat = "Porta fechada"

            pids_str = ", ".join(str(p) for p in svc["pids"]) if svc["pids"] else "-"
            ram_str = f"{svc['ram_mb']:.1f}" if svc["ram_mb"] > 0 else "-"
            exe_str = svc["exe_names"][0] if svc["exe_names"] else os.path.basename(svc["script_path"])
            if svc["exe_names"] and not svc["exe_exists"]:
                exe_str = f"{exe_str} (via .py)"

            self.tree.insert(
                "",
                "end",
                iid=svc["id"],
                values=(
                    svc["code"],
                    svc["name"],
                    svc["status"],
                    svc["port"] or "Desktop",
                    http_lat,
                    pids_str,
                    ram_str,
                    svc["uptime"] or "-",
                    exe_str,
                ),
                tags=(svc["status"],),
            )
            if prev_sel and prev_sel == svc["id"]:
                self.tree.selection_set(svc["id"])

        self._update_details_panel()

    def _render_orphans(self) -> None:
        for item in self.tree_orphans.get_children():
            self.tree_orphans.delete(item)
        orphans = self.snapshot.get("orphan_processes", []) if self.snapshot else []
        self.bottom_nb.tab(self.tab_orphans, text=f"Processos Órfãos / Extras ({len(orphans)})")
        for op in orphans:
            self.tree_orphans.insert(
                "",
                "end",
                values=(
                    op["pid"],
                    op["name"],
                    ", ".join(str(p) for p in op.get("listening_ports", [])) or "-",
                    f"{op.get('rss_mb', 0.0):.1f}",
                    op.get("uptime") or "-",
                    op.get("cmdline", ""),
                ),
            )

    def _render_history(self, hist: List[Dict[str, Any]]) -> None:
        self.txt_history.configure(state="normal")
        self.txt_history.delete("1.0", "end")
        if not hist:
            self.txt_history.insert("1.0", "Nenhuma operação registrada ainda.")
        else:
            lines = []
            for h in hist[:30]:
                lines.append(f"[{h.get('timestamp')}] {h.get('action')} -> {h.get('target')} ({h.get('status')}) | {json.dumps(h.get('details', {}), ensure_ascii=False)}")
            self.txt_history.insert("1.0", "\n".join(lines))
        self.txt_history.configure(state="disabled")

    def _on_select_row(self, _event=None) -> None:
        sel = self.tree.selection()
        self.selected_service_id = sel[0] if sel else None
        self._update_details_panel()

    def _get_selected_service(self) -> Optional[Dict[str, Any]]:
        if not self.snapshot or not self.selected_service_id:
            return None
        return next((s for s in self.snapshot.get("services", []) if s["id"] == self.selected_service_id), None)

    def _update_details_panel(self) -> None:
        svc = self._get_selected_service()
        self.txt_details.configure(state="normal")
        self.txt_details.delete("1.0", "end")
        if not svc:
            self.txt_details.insert("1.0", "Selecione qualquer serviço na tabela acima para ver detalhes completos.")
        else:
            lines = [
                f"Serviço: {svc['name']}  |  Status: {svc['status']}  |  Categoria: {svc['category']}",
                f"Pasta  : {svc['cwd']} ({'EXISTE' if svc['cwd_exists'] else 'NÃO ENCONTRADA'})",
                f"Script : {svc['script_path']} ({'OK' if svc['script_exists'] else 'AUSENTE'})",
                f"EXEs   : {', '.join(svc['exe_names']) or 'N/A'} ({'Compilado' if svc['exe_exists'] else 'Execução via Python'})",
                f"URL    : {svc['url'] or 'Aplicativo Desktop (sem porta HTTP)'}",
                "-" * 96,
            ]
            if svc["processes"]:
                for p in svc["processes"]:
                    lines.append(
                        f"  PID {p['pid']} (PPID {p['ppid']}) | RAM {p['rss_mb']} MB | "
                        f"Uptime: {p['uptime'] or '-'} | Portas: {p.get('listening_ports', [])}\n"
                        f"    CMD: {p['cmdline']}"
                    )
            else:
                lines.append("  Nenhum processo em execução vinculado a este aplicativo no momento.")
            self.txt_details.insert("1.0", "\n".join(lines))
        self.txt_details.configure(state="disabled")

    def _start_selected(self) -> None:
        svc = self._get_selected_service()
        if not svc:
            messagebox.showinfo("Selecionar serviço", "Selecione um aplicativo na tabela para iniciar.")
            return
        self.lbl_status.configure(text=f"Iniciando {svc['name']}...")
        self.root.update_idletasks()
        res = core.start_service(svc["id"])
        self.refresh_async()
        if res.get("ok"):
            messagebox.showinfo("Serviço Iniciado", res.get("message", "OK"))
        else:
            messagebox.showerror("Erro ao Iniciar", res.get("error", "Falha desconhecida"))

    def _restart_selected(self) -> None:
        svc = self._get_selected_service()
        if not svc:
            messagebox.showinfo("Selecionar serviço", "Selecione um aplicativo na tabela para reiniciar.")
            return
        self.lbl_status.configure(text=f"Reiniciando {svc['name']}...")
        self.root.update_idletasks()
        res = core.restart_service(svc["id"])
        self.refresh_async()
        messagebox.showinfo("Reinício Concluído", res.get("message", "OK"))

    def _open_selected_browser(self) -> None:
        svc = self._get_selected_service()
        if not svc:
            return
        if not svc.get("url"):
            messagebox.showinfo("Aplicativo Desktop", f"{svc['name']} é um aplicativo Desktop sem interface Web.")
            return
        webbrowser.open(svc["url"])

    def _export_csv(self) -> None:
        if not self.snapshot:
            return
        path = filedialog.asksaveasfilename(
            title="Exportar Snapshot de Serviços CBI",
            defaultextension=".csv",
            filetypes=[("Planilha CSV", "*.csv"), ("JSON", "*.json")],
            initialfile="servicos_cbi_snapshot.csv",
        )
        if not path:
            return
        if path.lower().endswith(".json"):
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(self.snapshot, fh, ensure_ascii=False, indent=2)
        else:
            core.export_snapshot_csv(self.snapshot, path)
        messagebox.showinfo("Exportação Concluída", f"Relatório salvo em:\n{path}")

    def _open_stopper_app(self) -> None:
        stopper_script = os.path.join(APP_DIR, "encerrar_servicos_cbi.py")
        if os.path.exists(stopper_script):
            subprocess.Popen([sys.executable, stopper_script], cwd=APP_DIR)


def main() -> None:
    parser = argparse.ArgumentParser(description="Monitor de Serviços Ativos CBI (Desktop Tkinter)")
    parser.add_argument("--snapshot-json", action="store_true", help="Imprime o snapshot JSON de todos os serviços e sai")
    parser.add_argument("--interval", type=int, default=3, help="Intervalo de auto-atualização em segundos (padrão: 3)")
    args = parser.parse_args()

    if args.snapshot_json:
        print(json.dumps(core.scan_all_services(), ensure_ascii=False, indent=2))
        return

    root = tk.Tk()
    MonitorServicosApp(root, auto_interval_sec=args.interval)
    root.mainloop()


if __name__ == "__main__":
    main()
