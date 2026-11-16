# -*- coding: utf-8 -*-
"""
encerrar_servicos_cbi.py — Aplicativo Desktop Nativo (Tkinter) + CLI para
Encerrar Qualquer Serviço, Porta ou Todos os Processos dos Aplicativos CBI (00 a 15).

Uso Desktop (Tkinter):
  python encerrar_servicos_cbi.py

Uso Linha de Comando (para .bat de 1 clique):
  python encerrar_servicos_cbi.py --all --yes
  python encerrar_servicos_cbi.py --service 08_gerador_laudos
  python encerrar_servicos_cbi.py --port 8760
  python encerrar_servicos_cbi.py --list
"""

from __future__ import annotations

import argparse
from datetime import datetime
import json
import os
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Dict, List, Optional, Set

APP_DIR = os.path.dirname(os.path.abspath(__file__))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

import cbi_services_core as core


class EncerradorServicosApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("CBI KillSwitch — Encerrador Universal de Serviços e Processos CBI")
        self.root.geometry("1160x720")
        self.root.minsize(940, 580)
        self.root.configure(bg="#F8FAFC")

        self.snapshot: Optional[Dict[str, Any]] = None
        self.checked_items: Set[str] = set()
        self.row_payloads: Dict[str, Dict[str, Any]] = {}
        self.force_var = tk.BooleanVar(value=True)
        self.include_central_var = tk.BooleanVar(value=True)
        self.show_stopped_var = tk.BooleanVar(value=False)
        self.port_entry_var = tk.StringVar(value="")
        self.scanning = False

        self._setup_styles()
        self._build_ui()
        self.refresh_async()

    def _setup_styles(self) -> None:
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure("Kill.Treeview", rowheight=27, font=("Segoe UI", 9), background="#FFFFFF", fieldbackground="#FFFFFF")
        style.configure("Kill.Treeview.Heading", font=("Segoe UI", 9, "bold"), background="#E2E8F0", foreground="#0F172A")

    def _build_ui(self) -> None:
        # 1. Header de Controle
        header = tk.Frame(self.root, bg="#18181B", height=66, padx=18, pady=10)
        header.pack(fill="x")
        header.pack_propagate(False)

        left_h = tk.Frame(header, bg="#18181B")
        left_h.pack(side="left", fill="y")
        tk.Label(
            left_h,
            text="ENCERRADOR UNIVERSAL DE SERVIÇOS — ECOSSISTEMA CBI",
            bg="#18181B",
            fg="#FEF2F2",
            font=("Segoe UI", 13, "bold"),
        ).pack(anchor="w")
        tk.Label(
            left_h,
            text="Encerre processos individuais, árvores travadas, portas ocupadas ou todo o ecossistema com segurança.",
            bg="#18181B",
            fg="#FCA5A5",
            font=("Segoe UI", 8),
        ).pack(anchor="w")

        right_h = tk.Frame(header, bg="#18181B")
        right_h.pack(side="right", fill="y")
        tk.Button(
            right_h,
            text="Abrir Monitor de Serviços",
            command=self._open_monitor_app,
            bg="#0284C7",
            fg="#FFFFFF",
            relief="flat",
            padx=11,
            pady=6,
            font=("Segoe UI", 9, "bold"),
            cursor="hand2",
        ).pack(side="right", padx=(8, 0), pady=4)
        tk.Button(
            right_h,
            text="Re-escanear Ativos",
            command=self.refresh_async,
            bg="#3F3F46",
            fg="#FFFFFF",
            relief="flat",
            padx=11,
            pady=6,
            font=("Segoe UI", 9, "bold"),
            cursor="hand2",
        ).pack(side="right", pady=4)

        # 2. Painel de Ação Rápida / Emergência
        panic_bar = tk.Frame(self.root, bg="#FEF2F2", bd=1, relief="solid", padx=16, pady=10)
        panic_bar.pack(fill="x", padx=16, pady=(12, 6))

        left_p = tk.Frame(panic_bar, bg="#FEF2F2")
        left_p.pack(side="left", fill="y")

        tk.Button(
            left_p,
            text="ENCERRAR TODOS OS SERVIÇOS CBI",
            command=self._kill_all_clicked,
            bg="#DC2626",
            fg="#FFFFFF",
            activebackground="#991B1B",
            activeforeground="#FFFFFF",
            relief="flat",
            padx=16,
            pady=8,
            font=("Segoe UI", 10, "bold"),
            cursor="hand2",
        ).pack(side="left", padx=(0, 14))

        opts_p = tk.Frame(left_p, bg="#FEF2F2")
        opts_p.pack(side="left")
        tk.Checkbutton(
            opts_p,
            text="Forçar encerramento imediato (SIGKILL / taskkill /F /T)",
            variable=self.force_var,
            bg="#FEF2F2",
            activebackground="#FEF2F2",
            font=("Segoe UI", 8, "bold"),
            fg="#7F1D1D",
        ).pack(anchor="w")
        tk.Checkbutton(
            opts_p,
            text="Incluir 00_CENTRAL_INTEGRADA_CBI (Porta 8700)",
            variable=self.include_central_var,
            bg="#FEF2F2",
            activebackground="#FEF2F2",
            font=("Segoe UI", 8),
            fg="#7F1D1D",
        ).pack(anchor="w")

        right_p = tk.Frame(panic_bar, bg="#FEF2F2")
        right_p.pack(side="right", fill="y")
        tk.Label(right_p, text="Liberar Porta:", bg="#FEF2F2", fg="#7F1D1D", font=("Segoe UI", 9, "bold")).pack(side="left", padx=(0, 6))
        tk.Entry(right_p, textvariable=self.port_entry_var, width=8, font=("Segoe UI", 10)).pack(side="left", padx=(0, 6))
        tk.Button(
            right_p,
            text="Matar Porta",
            command=self._kill_port_clicked,
            bg="#B45309",
            fg="#FFFFFF",
            relief="flat",
            padx=10,
            pady=6,
            font=("Segoe UI", 9, "bold"),
            cursor="hand2",
        ).pack(side="left")

        # 3. Barra de Seleção
        sel_bar = tk.Frame(self.root, bg="#E2E8F0", padx=16, pady=7)
        sel_bar.pack(fill="x", padx=16, pady=(4, 4))

        self.lbl_summary = tk.Label(sel_bar, text="Escaneando processos ativos...", bg="#E2E8F0", fg="#0F172A", font=("Segoe UI", 9, "bold"))
        self.lbl_summary.pack(side="left")

        tk.Button(
            sel_bar,
            text="ENCERRAR SELECIONADOS",
            command=self._kill_selected_clicked,
            bg="#B91C1C",
            fg="#FFFFFF",
            relief="flat",
            padx=12,
            pady=4,
            font=("Segoe UI", 9, "bold"),
            cursor="hand2",
        ).pack(side="right", padx=(8, 0))
        tk.Button(
            sel_bar,
            text="Limpar Seleção",
            command=self._clear_checks,
            bg="#475569",
            fg="#FFFFFF",
            relief="flat",
            padx=9,
            pady=4,
            font=("Segoe UI", 8, "bold"),
            cursor="hand2",
        ).pack(side="right", padx=4)
        tk.Button(
            sel_bar,
            text="Selecionar Todos Ativos",
            command=self._select_all_active,
            bg="#1D4ED8",
            fg="#FFFFFF",
            relief="flat",
            padx=9,
            pady=4,
            font=("Segoe UI", 8, "bold"),
            cursor="hand2",
        ).pack(side="right", padx=4)
        tk.Checkbutton(
            sel_bar,
            text="Mostrar também apps parados",
            variable=self.show_stopped_var,
            command=self._render_table,
            bg="#E2E8F0",
            activebackground="#E2E8F0",
            font=("Segoe UI", 8),
        ).pack(side="right", padx=12)

        # 4. Tabela com Checkboxes (clique na linha/checkbox alterna marcação)
        paned = tk.PanedWindow(self.root, orient="vertical", sashwidth=6, bg="#CBD5E1")
        paned.pack(fill="both", expand=True, padx=16, pady=(2, 12))

        table_wrap = tk.Frame(paned, bg="#FFFFFF")
        cols = ("chk", "code", "name", "status", "port", "pids", "ram", "cmd")
        self.tree = ttk.Treeview(table_wrap, columns=cols, show="headings", style="Kill.Treeview")
        for cid, txt, w, anchor in [
            ("chk", "Sel.", 45, "center"),
            ("code", "Cód", 50, "center"),
            ("name", "Aplicativo / Processo Detectado", 280, "w"),
            ("status", "Estado", 85, "center"),
            ("port", "Porta", 65, "center"),
            ("pids", "PIDs", 110, "center"),
            ("ram", "RAM (MB)", 80, "e"),
            ("cmd", "Linha de Comando / Executável", 390, "w"),
        ]:
            self.tree.heading(cid, text=txt)
            self.tree.column(cid, width=w, anchor=anchor)

        self.tree.tag_configure("ACTIVE", background="#FEF2F2", foreground="#991B1B")
        self.tree.tag_configure("ORPHAN", background="#FFFBEB", foreground="#92400E")
        self.tree.tag_configure("STOPPED", background="#FFFFFF", foreground="#64748B")

        vsb = ttk.Scrollbar(table_wrap, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self.tree.bind("<ButtonRelease-1>", self._on_tree_click)
        paned.add(table_wrap, height=380)

        # 5. Console de Execução / Auditoria
        console_frame = tk.Frame(paned, bg="#0F172A")
        tk.Label(
            console_frame,
            text="CONSOLE DE ENCERRAMENTO & AUDITORIA EM TEMPO REAL (clique em qualquer linha acima para marcar/desmarcar)",
            bg="#1E293B",
            fg="#E2E8F0",
            font=("Segoe UI", 8, "bold"),
            anchor="w",
            padx=10,
            pady=4,
        ).pack(fill="x")
        self.txt_log = tk.Text(console_frame, bg="#0F172A", fg="#A7F3D0", font=("Consolas", 9), relief="flat", padx=10, pady=8)
        self.txt_log.pack(fill="both", expand=True)
        paned.add(console_frame, height=180)
        self._log("Encerrador CBI pronto. Use os checkboxes para encerrar itens específicos ou o botão vermelho para encerrar todos.")

    def _log(self, msg: str) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        self.txt_log.configure(state="normal")
        self.txt_log.insert("end", f"[{ts}] {msg}\n")
        self.txt_log.see("end")
        self.txt_log.configure(state="disabled")

    def refresh_async(self) -> None:
        if self.scanning:
            return
        self.scanning = True
        self.lbl_summary.configure(text="Escaneando processos e portas TCP...")

        def worker() -> None:
            try:
                snap = core.scan_all_services()
            except Exception as exc:
                snap = {"ok": False, "error": str(exc), "services": [], "orphan_processes": [], "summary": {}}
            self.root.after(0, lambda: self._apply_snapshot(snap))

        threading.Thread(target=worker, daemon=True).start()

    def _apply_snapshot(self, snap: Dict[str, Any]) -> None:
        self.scanning = False
        self.snapshot = snap
        s = snap.get("summary", {})
        self.lbl_summary.configure(
            text=f"Ativos agora: {s.get('active_all', 0)} serviço(s) | "
                 f"{s.get('active_pids', 0)} PID(s) | "
                 f"{s.get('total_ram_mb', 0.0):.1f} MB RAM | "
                 f"Órfãos: {s.get('orphan_processes', 0)}"
        )
        self._render_table()

    def _render_table(self) -> None:
        if not self.snapshot:
            return
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.row_payloads.clear()
        show_stopped = self.show_stopped_var.get()

        valid_ids = set()
        for svc in self.snapshot.get("services", []):
            is_active = bool(svc["pids"] or svc["tcp_open"])
            if not is_active and not show_stopped:
                continue
            iid = f"svc::{svc['id']}"
            valid_ids.add(iid)
            checked = "[X]" if iid in self.checked_items else "[ ]"
            cmd_preview = svc["processes"][0]["cmdline"] if svc["processes"] else "(inativo)"
            pids_str = ", ".join(str(p) for p in svc["pids"]) if svc["pids"] else "-"
            tag = "ACTIVE" if is_active else "STOPPED"

            self.row_payloads[iid] = {
                "kind": "service",
                "service_id": svc["id"],
                "name": svc["name"],
                "port": svc["port"],
                "pids": list(svc["pids"]),
                "is_active": is_active,
            }
            self.tree.insert(
                "",
                "end",
                iid=iid,
                values=(
                    checked,
                    svc["code"],
                    svc["name"],
                    svc["status"],
                    svc["port"] or "-",
                    pids_str,
                    f"{svc['ram_mb']:.1f}" if svc["ram_mb"] > 0 else "-",
                    cmd_preview,
                ),
                tags=(tag,),
            )

        for op in self.snapshot.get("orphan_processes", []):
            iid = f"pid::{op['pid']}"
            valid_ids.add(iid)
            checked = "[X]" if iid in self.checked_items else "[ ]"
            ports_str = ", ".join(str(p) for p in op.get("listening_ports", [])) or "-"
            self.row_payloads[iid] = {
                "kind": "orphan",
                "pid": op["pid"],
                "name": f"Órfão: {op['name']}",
                "pids": [op["pid"]],
                "is_active": True,
            }
            self.tree.insert(
                "",
                "end",
                iid=iid,
                values=(
                    checked,
                    "PID",
                    f"Processo Órfão CBI: {op['name']}",
                    "ÓRFÃO",
                    ports_str,
                    str(op["pid"]),
                    f"{op.get('rss_mb', 0.0):.1f}",
                    op.get("cmdline", ""),
                ),
                tags=("ORPHAN",),
            )

        self.checked_items &= valid_ids
        if not self.row_payloads:
            self._log("Nenhum serviço CBI ativo encontrado neste momento.")

    def _on_tree_click(self, event: tk.Event) -> None:
        iid = self.tree.identify_row(event.y)
        if not iid or iid not in self.row_payloads:
            return
        if iid in self.checked_items:
            self.checked_items.remove(iid)
        else:
            self.checked_items.add(iid)
        vals = list(self.tree.item(iid, "values"))
        vals[0] = "[X]" if iid in self.checked_items else "[ ]"
        self.tree.item(iid, values=vals)

    def _select_all_active(self) -> None:
        self.checked_items = {iid for iid, p in self.row_payloads.items() if p.get("is_active")}
        self._render_table()

    def _clear_checks(self) -> None:
        self.checked_items.clear()
        self._render_table()

    def _kill_selected_clicked(self) -> None:
        if not self.checked_items:
            sel = self.tree.selection()
            if sel:
                self.checked_items.update(sel)
        if not self.checked_items:
            messagebox.showinfo("Nada selecionado", "Marque um ou mais serviços/processos ativos para encerrar.")
            return

        targets = [self.row_payloads[iid] for iid in self.checked_items if iid in self.row_payloads]
        names = "\n".join(f"- {t['name']} (PIDs: {t['pids'] or 'porta ' + str(t.get('port'))})" for t in targets)
        if not messagebox.askyesno("Confirmar Encerramento", f"Deseja encerrar os {len(targets)} item(ns) selecionado(s)?\n\n{names}"):
            return

        force = self.force_var.get()
        self._log(f"Iniciando encerramento de {len(targets)} item(ns) (force={force})...")

        def worker() -> None:
            logs: List[str] = []
            for t in targets:
                if t["kind"] == "service":
                    r = core.terminate_service(t["service_id"], force=force)
                    logs.append(f"[OK] {r.get('message')} | porta livre={r.get('port_freed')}")
                else:
                    r = core.terminate_pids(t["pids"], force=force, reason="orphan_gui")
                    logs.append(f"[OK] Órfão PID {t['pids']}: {r.get('killed_count')} encerrado(s).")
            self.root.after(0, lambda: self._after_kill_action(logs))

        threading.Thread(target=worker, daemon=True).start()

    def _kill_all_clicked(self) -> None:
        force = self.force_var.get()
        inc_central = self.include_central_var.get()
        msg = "Deseja encerrar TODOS os serviços e processos ativos do Ecossistema CBI agora?"
        if inc_central:
            msg += "\n(Incluindo a Central Integrada porta 8700)"
        if not messagebox.askyesno("ENCERRAMENTO GERAL CBI", msg, icon="warning"):
            return

        self._log(f"EXECUTANDO ENCERRAMENTO GERAL (force={force}, incluir_central={inc_central})...")

        def worker() -> None:
            res = core.terminate_all_services(force=force, include_central=inc_central, include_orphans=True)
            lines = [res.get("message", "Concluído.")]
            for r in res.get("results", []):
                lines.append(f"  -> PID {r['pid']}: {'OK' if r['ok'] else 'FALHA'} ({r['message']})")
            self.root.after(0, lambda: self._after_kill_action(lines, popup_summary=res.get("message")))

        threading.Thread(target=worker, daemon=True).start()

    def _kill_port_clicked(self) -> None:
        raw_port = self.port_entry_var.get().strip()
        if not raw_port.isdigit():
            messagebox.showerror("Porta Inválida", "Informe um número de porta TCP válido (ex: 8760).")
            return
        port = int(raw_port)
        force = self.force_var.get()
        self._log(f"Encerrando processo na porta TCP {port} (force={force})...")

        def worker() -> None:
            res = core.terminate_by_port(port, force=force)
            msg = f"Porta {port}: {res.get('message')} (livre={res.get('port_freed', True)})"
            self.root.after(0, lambda: self._after_kill_action([msg], popup_summary=msg))

        threading.Thread(target=worker, daemon=True).start()

    def _after_kill_action(self, log_lines: List[str], popup_summary: Optional[str] = None) -> None:
        for line in log_lines:
            self._log(line)
        self.checked_items.clear()
        self.refresh_async()
        if popup_summary:
            messagebox.showinfo("Encerramento Concluído", popup_summary)

    def _open_monitor_app(self) -> None:
        mon_script = os.path.join(APP_DIR, "monitor_servicos_cbi.py")
        if os.path.exists(mon_script):
            subprocess.Popen([sys.executable, mon_script], cwd=APP_DIR)


def run_cli(args: argparse.Namespace) -> int:
    if args.list:
        snap = core.scan_all_services()
        print(json.dumps(snap, ensure_ascii=False, indent=2))
        return 0

    if args.port:
        res = core.terminate_by_port(args.port, force=not args.graceful)
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return 0 if res.get("ok") else 1

    if args.service:
        res = core.terminate_service(args.service, force=not args.graceful)
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return 0 if res.get("ok") else 1

    if args.all:
        if not args.yes:
            ans = input("Confirma encerrar TODOS os serviços CBI ativos? [s/N]: ").strip().lower()
            if ans not in ("s", "sim", "y", "yes"):
                print("Operação cancelada.")
                return 0
        res = core.terminate_all_services(
            force=not args.graceful,
            include_central=not args.keep_central,
            include_orphans=True,
        )
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return 0

    return -1


def main() -> None:
    parser = argparse.ArgumentParser(description="Encerrador Universal de Serviços CBI (Desktop Tkinter + CLI)")
    parser.add_argument("--all", action="store_true", help="Encerra todos os serviços ativos do ecossistema CBI")
    parser.add_argument("--yes", "-y", action="store_true", help="Confirma automaticamente sem perguntar no terminal")
    parser.add_argument("--service", type=str, help="Encerra um serviço específico pelo ID (ex: 08_gerador_laudos)")
    parser.add_argument("--port", type=int, help="Encerra o processo que estiver usando a porta TCP informada")
    parser.add_argument("--list", action="store_true", help="Lista serviços e processos ativos em JSON")
    parser.add_argument("--graceful", action="store_true", help="Tenta encerramento suave antes de forçar kill")
    parser.add_argument("--keep-central", action="store_true", help="Mantém a 00_CENTRAL_INTEGRADA_CBI ativa ao encerrar todos")
    args = parser.parse_args()

    cli_rc = run_cli(args)
    if cli_rc != -1:
        sys.exit(cli_rc)

    root = tk.Tk()
    EncerradorServicosApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
