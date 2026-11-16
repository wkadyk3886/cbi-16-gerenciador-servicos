# -*- coding: utf-8 -*-
"""
cbi_services_core.py — Motor Unificado de Monitoramento e Encerramento de Serviços CBI.

100% Pure Python 3.11 stdlib (sem dependências externas).
Compatível com Windows (ambiente de produção .exe/.bat/python.exe) e Linux.

Responsabilidades:
1. Catálogo completo de todos os 16+ aplicativos do Ecossistema CBI (00..15 + Orquestrador).
2. Auto-detecção do diretório raiz (suporta tanto `PROGRAMAS_/00_...` quanto `wkadyk3886/cbi-00-...`).
3. Varredura em tempo real de portas TCP, saúde HTTP, PIDs em escuta, processos por linha de comando/executável,
   uso de memória RAM (MB), Uptime e processos órfãos.
4. Encerramento seguro ou forçado de qualquer serviço individual, PID avulso, porta específica ou de TODOS
   os serviços do ecossistema CBI, além de inicialização e reinício.
"""

from __future__ import annotations

import concurrent.futures
import csv
import http.client
import io
import json
import os
import re
import signal
import socket
import subprocess
import sys
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(APP_DIR, "data")
LOGS_DIR = os.path.join(APP_DIR, "logs")
HISTORY_FILE = os.path.join(DATA_DIR, "historico_acoes.json")


def _ensure_dirs() -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(LOGS_DIR, exist_ok=True)


def discover_ecosystem_root() -> str:
    """Descobre a pasta raiz contendo os aplicativos CBI (layout PROGRAMAS_ ou layout git cbi-*)."""
    candidates = [
        os.path.abspath(os.path.join(APP_DIR, "..")),
        os.path.abspath(os.path.join(APP_DIR, "..", "..")),
        os.path.abspath(os.path.join(APP_DIR, "..", "..", "..")),
        os.getcwd(),
        os.path.abspath(os.path.join(os.getcwd(), "..")),
    ]
    if getattr(sys, "frozen", False):
        exe_dir = os.path.dirname(os.path.abspath(sys.executable))
        candidates.insert(0, os.path.abspath(os.path.join(exe_dir, "..")))
        candidates.insert(0, os.path.abspath(os.path.join(exe_dir, "..", "..")))

    markers = (
        "00_CENTRAL_INTEGRADA_CBI",
        "08_GERADOR_DE_LAUDOS",
        "cbi-00-central-integrada",
        "cbi-08-gerador-de-laudos",
    )
    for base in candidates:
        if any(os.path.exists(os.path.join(base, m)) for m in markers):
            return base
    return os.path.abspath(os.path.join(APP_DIR, "..", ".."))


def _resolve_path(root: str, win_folder: str, repo_folder: str, *subparts: str) -> str:
    """Resolve caminho aceitando tanto nomes de pasta Windows (`08_GERADOR_DE_LAUDOS`) quanto repo (`cbi-08-gerador-de-laudos`)."""
    bases = [root, os.path.abspath(os.path.join(root, ".."))]
    for base in bases:
        p_win = os.path.join(base, win_folder, *subparts)
        if os.path.exists(p_win) or os.path.exists(os.path.join(base, win_folder)):
            return p_win
        p_repo = os.path.join(base, repo_folder, *subparts)
        if os.path.exists(p_repo) or os.path.exists(os.path.join(base, repo_folder)):
            return p_repo
    return os.path.join(root, win_folder, *subparts)


@dataclass
class ServiceSpec:
    id: str
    code: str
    name: str
    category: str
    port: Optional[int]
    win_folder: str
    repo_folder: str
    app_subpath: Tuple[str, ...]
    entry_script: str
    exe_names: Tuple[str, ...]
    bat_names: Tuple[str, ...]
    cmd_mode: str = "script"  # script | uvicorn | flask_app | desktop
    extra_env: Optional[Dict[str, str]] = None
    match_tokens: Tuple[str, ...] = ()

    def resolve_cwd(self, root: str) -> str:
        return _resolve_path(root, self.win_folder, self.repo_folder, *self.app_subpath)

    def resolve_script(self, root: str) -> str:
        return os.path.join(self.resolve_cwd(root), self.entry_script)


SERVICE_CATALOG: List[ServiceSpec] = [
    ServiceSpec(
        id="00_central_integrada",
        code="00",
        name="00. Central Integrada CBI (Hub)",
        category="Hub & Orquestração",
        port=8700,
        win_folder="00_CENTRAL_INTEGRADA_CBI",
        repo_folder="cbi-00-central-integrada",
        app_subpath=("00_CENTRAL_INTEGRADA_CBI",),
        entry_script="app.py",
        exe_names=("CentralCBI.exe",),
        bat_names=("INICIAR_CENTRAL.bat", "INICIAR_ECOSSISTEMA_CBI.bat"),
        match_tokens=("00_central_integrada_cbi", "cbi-00-central-integrada", "centralcbi.exe"),
    ),
    ServiceSpec(
        id="01_ruido_workflex",
        code="01",
        name="01. Editor de Ruído — Workflex DecFlex 320",
        category="Editores de Equipamentos",
        port=5320,
        win_folder="01_EDITOR_RUIDO_WORKFLEX",
        repo_folder="cbi-01-editor-ruido-workflex",
        app_subpath=("Workflex", "APP"),
        entry_script="app.py",
        exe_names=("EditorDecFlex.exe",),
        bat_names=("iniciar_editor.bat",),
        cmd_mode="flask_app",
        match_tokens=("01_editor_ruido_workflex", "cbi-01-editor-ruido-workflex", "decflex", "editordecflex.exe"),
    ),
    ServiceSpec(
        id="02_gases_multigas",
        code="02",
        name="02. Editor de Gases — NAPRO PC-Multigás",
        category="Editores de Equipamentos",
        port=5055,
        win_folder="02_EDITOR_GASES_MULTIGAS",
        repo_folder="cbi-02-editor-gases-multigas",
        app_subpath=("NAPRO", "PC-Multigas", "APP_ANALISE"),
        entry_script="app.py",
        exe_names=("App_Analise.exe",),
        bat_names=("Iniciar_App_Analise.bat", "Iniciar_Executavel_App_Analise.bat"),
        match_tokens=("02_editor_gases_multigas", "cbi-02-editor-gases-multigas", "app_analise", "pc-multigas"),
    ),
    ServiceSpec(
        id="03_opacidade_l1_napro",
        code="03",
        name="03. Editor Opacidade L1 — NAPRO NA9000T",
        category="Editores de Equipamentos",
        port=5056,
        win_folder="03_EDITOR_OPACIDADE_L1_NAPRO_NA9000T",
        repo_folder="cbi-03-editor-opacidade-l1-na9000t",
        app_subpath=("NAPRO", "NA9000T", "APP_OPACIDADE_NA9000T"),
        entry_script="app.py",
        exe_names=("App_Opacidade_NA9000T.exe",),
        bat_names=(),
        extra_env={"NA9000T_PORT": "5056"},
        match_tokens=("03_editor_opacidade_l1_napro_na9000t", "cbi-03-editor-opacidade-l1-na9000t", "app_opacidade_na9000t"),
    ),
    ServiceSpec(
        id="04_opacidade_l1_snapon",
        code="04",
        name="04. Editor Opacidade L1 — Snap-on OPAL1",
        category="Editores de Equipamentos",
        port=8501,
        win_folder="04_EDITOR_OPACIDADE_L1_SNAPON_OPAL1",
        repo_folder="cbi-04-editor-opacidade-l1-snapon",
        app_subpath=("Snap-on_OPAL1", "CSM-5000", "APP"),
        entry_script="app.py",
        exe_names=("CSM5000_Desktop.exe",),
        bat_names=("iniciar_app.bat",),
        cmd_mode="uvicorn",
        match_tokens=("04_editor_opacidade_l1_snapon_opal1", "cbi-04-editor-opacidade-l1-snapon", "snap-on_opal1"),
    ),
    ServiceSpec(
        id="05_opacidade_l2_snapon",
        code="05",
        name="05. Editor Opacidade L2 — Snap-on L2",
        category="Editores de Equipamentos",
        port=8500,
        win_folder="05_EDITOR_OPACIDADE_L2_SNAPON_L2",
        repo_folder="cbi-05-editor-opacidade-l2-snapon",
        app_subpath=("Snap-on_L2", "CSM-5000", "APP"),
        entry_script="app.py",
        exe_names=("CSM5000_Desktop.exe",),
        bat_names=("iniciar_app.bat",),
        cmd_mode="uvicorn",
        match_tokens=("05_editor_opacidade_l2_snapon_l2", "cbi-05-editor-opacidade-l2-snapon", "snap-on_l2"),
    ),
    ServiceSpec(
        id="06_frenometro_l1_duo",
        code="06",
        name="06. Editor Frenômetro L1 — NAPRO DUO",
        category="Editores de Equipamentos",
        port=5050,
        win_folder="06_EDITOR_FRENOMETRO_L1_NAPRO_DUO",
        repo_folder="cbi-06-editor-frenometro-l1-napro-duo",
        app_subpath=("NAPRO", "web_editor"),
        entry_script="server.py",
        exe_names=("EditorNaproDUO.exe",),
        bat_names=("start_editor.bat", "Iniciar_Editor_Web.bat"),
        match_tokens=("06_editor_frenometro_l1_napro_duo", "cbi-06-editor-frenometro-l1-napro-duo", "editornaproduo.exe"),
    ),
    ServiceSpec(
        id="07_frenometro_l2_netbrake",
        code="07",
        name="07. Editor Frenômetro L2 — NetBrake",
        category="Editores de Equipamentos",
        port=8088,
        win_folder="07_EDITOR_FRENOMETRO_L2_NETBRAKE",
        repo_folder="cbi-07-editor-frenometro-l2-netbrake",
        app_subpath=("NetBrake",),
        entry_script="app.py",
        exe_names=("NetBrake_Editor.exe", "VerificadorNetBrake.exe"),
        bat_names=("Iniciar_Editor_Web.bat", "Iniciar_NetBrake_Editor.bat"),
        cmd_mode="flask_app",
        match_tokens=("07_editor_frenometro_l2_netbrake", "cbi-07-editor-frenometro-l2-netbrake", "netbrake_editor.exe", "verificadornetbrake.exe"),
    ),
    ServiceSpec(
        id="08_gerador_laudos",
        code="08",
        name="08. Gerador de Laudos Integrado",
        category="Laudos & Qualidade",
        port=8760,
        win_folder="08_GERADOR_DE_LAUDOS",
        repo_folder="cbi-08-gerador-de-laudos",
        app_subpath=("LAUDOS", "APP"),
        entry_script="server.py",
        exe_names=("GeradorLaudos.exe",),
        bat_names=("INICIAR_APP_LAUDOS.bat",),
        match_tokens=("08_gerador_de_laudos", "cbi-08-gerador-de-laudos", "geradorlaudos.exe"),
    ),
    ServiceSpec(
        id="09_controle_cbi",
        code="09",
        name="09. Controle CBI Qualidade (.xlsm)",
        category="Laudos & Qualidade",
        port=8765,
        win_folder="09_CONTROLE_CBI_QUALIDADE",
        repo_folder="cbi-09-controle-cbi-qualidade",
        app_subpath=("Lista CBI", "APP"),
        entry_script="server.py",
        exe_names=("ControleCBI.exe",),
        bat_names=("Iniciar_Controle_CBI.bat",),
        match_tokens=("09_controle_cbi_qualidade", "cbi-09-controle-cbi-qualidade", "controlecbi.exe"),
    ),
    ServiceSpec(
        id="10_validacao_itl",
        code="10",
        name="10. Validação de Software ITL (Desktop)",
        category="Laudos & Qualidade",
        port=None,
        win_folder="10_VALIDACAO_SOFTWARE_ITL",
        repo_folder="cbi-10-validacao-software-itl",
        app_subpath=("PROG VALIDAÇÃO",),
        entry_script="app.py",
        exe_names=("ValidacaoITL.exe",),
        bat_names=("INICIAR_VALIDACAO.bat",),
        cmd_mode="desktop",
        match_tokens=("10_validacao_software_itl", "cbi-10-validacao-software-itl", "validacaoitl.exe"),
    ),
    ServiceSpec(
        id="11_peso_eixo_inspeso",
        code="11",
        name="11. Conversor Peso por Eixo — Inspeso",
        category="Utilitários & Engenharia",
        port=8550,
        win_folder="11_CONVERSOR_PESO_EIXO_INSPESO",
        repo_folder="cbi-11-conversor-peso-eixo-inspeso",
        app_subpath=("PESO EIXO APP",),
        entry_script="app.py",
        exe_names=("Inspeso.exe",),
        bat_names=("INICIAR_APLICATIVO.bat",),
        match_tokens=("11_conversor_peso_eixo_inspeso", "cbi-11-conversor-peso-eixo-inspeso", "inspeso.exe"),
    ),
    ServiceSpec(
        id="12_oficina_vistovap",
        code="12",
        name="12. Oficina VistoVap — Estoque & Orçamentos",
        category="Operação & Oficina",
        port=5080,
        win_folder="12_OFICINA_VISTOVAP",
        repo_folder="cbi-12-oficina-vistovap",
        app_subpath=("OFICINA", "APP"),
        entry_script="app.py",
        exe_names=("VistoVap_Oficina.exe",),
        bat_names=("iniciar_app.bat",),
        match_tokens=("12_oficina_vistovap", "cbi-12-oficina-vistovap", "vistovap_oficina.exe"),
    ),
    ServiceSpec(
        id="13_protetor_licenciamento",
        code="13",
        name="13. Protetor de Licenciamento Ed25519",
        category="Segurança & Licenças",
        port=5090,
        win_folder="13_PROTETOR_LICENCIAMENTO",
        repo_folder="cbi-13-protetor-licenciamento",
        app_subpath=("PROTETOR", "programa2_admin_web"),
        entry_script="app.py",
        exe_names=("ProtetorAdmin.exe", "ProtetorCliente.exe"),
        bat_names=("iniciar_painel.bat",),
        match_tokens=("13_protetor_licenciamento", "cbi-13-protetor-licenciamento", "protetoradmin.exe", "protetorcliente.exe"),
    ),
    ServiceSpec(
        id="14_catalogo_normas",
        code="14",
        name="14. Catálogo de Normas & Escopos CBI",
        category="Normas & Técnica",
        port=8770,
        win_folder="14_CATALOGO_NORMAS_ESCOPOS_CBI",
        repo_folder="cbi-14-catalogo-normas-escopos",
        app_subpath=("CATALOGO_APP",),
        entry_script="app.py",
        exe_names=("CatalogoNormasCBI.exe",),
        bat_names=("INICIAR_CATALOGO.bat",),
        match_tokens=("14_catalogo_normas_escopos_cbi", "cbi-14-catalogo-normas-escopos", "catalogonormascbi.exe"),
    ),
    ServiceSpec(
        id="15_informacoes_tecnicas",
        code="15",
        name="15. Informações Técnicas (ANFAVEA/Motores)",
        category="Normas & Técnica",
        port=8780,
        win_folder="15_INFORMACOES_TECNICAS",
        repo_folder="cbi-15-informacoes-tecnicas",
        app_subpath=("15_INFORMACOES_TECNICAS",),
        entry_script="app.py",
        exe_names=("InformacoesTecnicas.exe",),
        bat_names=("INICIAR_APLICATIVO.bat",),
        match_tokens=("15_informacoes_tecnicas", "cbi-15-informacoes-tecnicas", "informacoestecnicas.exe"),
    ),
    ServiceSpec(
        id="orquestrador_ecossistema",
        code="ORQ",
        name="ORQ. Orquestrador Geral (start_all_services.py)",
        category="Hub & Orquestração",
        port=None,
        win_folder="00_CENTRAL_INTEGRADA_CBI",
        repo_folder="cbi-00-central-integrada",
        app_subpath=(),
        entry_script="start_all_services.py",
        exe_names=(),
        bat_names=("INICIAR_ECOSSISTEMA_CBI.bat",),
        match_tokens=("start_all_services.py",),
    ),
]

SERVICE_BY_ID: Dict[str, ServiceSpec] = {s.id: s for s in SERVICE_CATALOG}
CBI_PORTS: Dict[int, ServiceSpec] = {s.port: s for s in SERVICE_CATALOG if s.port is not None}


def append_action_log(action: str, target: str, status: str, details: Dict[str, Any]) -> None:
    _ensure_dirs()
    entry = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "action": action,
        "target": target,
        "status": status,
        "details": details,
    }
    log_line = f"[{entry['timestamp']}] {action} | {target} | {status} | {json.dumps(details, ensure_ascii=False)}\n"
    try:
        with open(os.path.join(LOGS_DIR, "gerenciador_servicos.log"), "a", encoding="utf-8") as fh:
            fh.write(log_line)
    except Exception:
        pass
    try:
        hist: List[Dict[str, Any]] = []
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, "r", encoding="utf-8") as fh:
                hist = json.load(fh)
        hist.insert(0, entry)
        with open(HISTORY_FILE, "w", encoding="utf-8") as fh:
            json.dump(hist[:200], fh, ensure_ascii=False, indent=2)
    except Exception:
        pass


def get_action_history(limit: int = 50) -> List[Dict[str, Any]]:
    if not os.path.exists(HISTORY_FILE):
        return []
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data[:limit] if isinstance(data, list) else []
    except Exception:
        return []


# ==============================================================================
# INSPEÇÃO NATIVA DE PORTAS TCP E PROCESSOS (WINDOWS & LINUX)
# ==============================================================================

def _probe_port_and_http(port: Optional[int], timeout: float = 0.35) -> Dict[str, Any]:
    if not port:
        return {"tcp_open": False, "latency_ms": None, "http_status": None}
    t0 = time.perf_counter()
    tcp_open = False
    http_status: Optional[int] = None
    try:
        with socket.create_connection(("127.0.0.1", int(port)), timeout=timeout):
            tcp_open = True
    except OSError:
        pass
    latency_ms = round((time.perf_counter() - t0) * 1000, 1) if tcp_open else None
    if tcp_open:
        try:
            conn = http.client.HTTPConnection("127.0.0.1", int(port), timeout=0.6)
            conn.request("GET", "/")
            resp = conn.getresponse()
            http_status = int(resp.status)
            resp.read(256)
            conn.close()
        except Exception:
            http_status = None
    return {"tcp_open": tcp_open, "latency_ms": latency_ms, "http_status": http_status}


def _enumerate_os_processes_and_ports() -> Tuple[Dict[int, Dict[str, Any]], Dict[int, List[int]]]:
    """
    Retorna:
      procs: {pid: {pid, ppid, name, cmdline, rss_mb, uptime}}
      port_to_pids: {port: [pid1, pid2, ...]}
    """
    if os.name == "nt":
        return _enum_windows()
    return _enum_linux()


def _enum_windows() -> Tuple[Dict[int, Dict[str, Any]], Dict[int, List[int]]]:
    procs: Dict[int, Dict[str, Any]] = {}
    port_to_pids: Dict[int, List[int]] = {}
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

    # 1. netstat -ano -p tcp -> listening ports
    try:
        out = subprocess.check_output(
            ["netstat", "-ano", "-p", "tcp"],
            text=True,
            encoding="cp850",
            errors="ignore",
            timeout=5,
            creationflags=flags,
        )
        for line in out.splitlines():
            parts = line.split()
            if len(parts) >= 5 and parts[0].upper() == "TCP" and parts[3].upper() in ("LISTENING", "ESCUTANDO"):
                addr = parts[1]
                pid_str = parts[4]
                if ":" in addr and pid_str.isdigit():
                    port_str = addr.rsplit(":", 1)[-1]
                    if port_str.isdigit():
                        p_num = int(port_str)
                        pid_val = int(pid_str)
                        if pid_val > 0:
                            port_to_pids.setdefault(p_num, [])
                            if pid_val not in port_to_pids[p_num]:
                                port_to_pids[p_num].append(pid_val)
    except Exception:
        pass

    # 2. PowerShell CIM process list (fast, gives full CommandLine + WorkingSetSize + CreationDate)
    ps_ok = False
    try:
        ps_cmd = (
            "Get-CimInstance Win32_Process | "
            "Select-Object ProcessId,ParentProcessId,Name,CommandLine,WorkingSetSize,CreationDate | "
            "ConvertTo-Json -Compress"
        )
        raw = subprocess.check_output(
            ["powershell", "-NoProfile", "-Command", ps_cmd],
            text=True,
            encoding="utf-8",
            errors="ignore",
            timeout=8,
            creationflags=flags,
        )
        items = json.loads(raw) if raw.strip() else []
        if isinstance(items, dict):
            items = [items]
        for item in items:
            pid = int(item.get("ProcessId") or 0)
            if pid <= 0:
                continue
            ws = float(item.get("WorkingSetSize") or 0)
            procs[pid] = {
                "pid": pid,
                "ppid": int(item.get("ParentProcessId") or 0),
                "name": str(item.get("Name") or ""),
                "cmdline": str(item.get("CommandLine") or item.get("Name") or ""),
                "rss_mb": round(ws / (1024 * 1024), 1),
                "uptime": "",
            }
        ps_ok = bool(procs)
    except Exception:
        pass

    # Fallback: tasklist /FO CSV /NH
    if not ps_ok:
        try:
            raw = subprocess.check_output(
                ["tasklist", "/FO", "CSV", "/NH"],
                text=True,
                encoding="cp850",
                errors="ignore",
                timeout=5,
                creationflags=flags,
            )
            reader = csv.reader(io.StringIO(raw))
            for row in reader:
                if len(row) >= 5 and row[1].strip().isdigit():
                    pid = int(row[1].strip())
                    mem_digits = re.sub(r"[^\d]", "", row[4])
                    rss_mb = round(int(mem_digits) / 1024.0, 1) if mem_digits else 0.0
                    procs[pid] = {
                        "pid": pid,
                        "ppid": 0,
                        "name": row[0].strip(),
                        "cmdline": row[0].strip(),
                        "rss_mb": rss_mb,
                        "uptime": "",
                    }
        except Exception:
            pass

    return procs, port_to_pids


def _enum_linux() -> Tuple[Dict[int, Dict[str, Any]], Dict[int, List[int]]]:
    procs: Dict[int, Dict[str, Any]] = {}
    port_to_pids: Dict[int, List[int]] = {}

    # 1. Read /proc/<pid>
    boot_time = 0.0
    try:
        with open("/proc/stat", "r", encoding="utf-8", errors="ignore") as fh:
            for line in fh:
                if line.startswith("btime "):
                    boot_time = float(line.split()[1])
                    break
    except Exception:
        pass
    clk_tck = os.sysconf(os.sysconf_names["SC_CLK_TCK"]) if hasattr(os, "sysconf") else 100
    now_ts = time.time()

    try:
        pids = [int(name) for name in os.listdir("/proc") if name.isdigit()]
    except Exception:
        pids = []

    for pid in pids:
        try:
            with open(f"/proc/{pid}/cmdline", "rb") as fh:
                raw_cmd = fh.read()
            cmdline = raw_cmd.replace(b"\x00", b" ").decode("utf-8", errors="ignore").strip()
            with open(f"/proc/{pid}/comm", "r", encoding="utf-8", errors="ignore") as fh:
                name = fh.read().strip()
            if not cmdline:
                cmdline = name
            ppid = 0
            uptime_str = ""
            try:
                with open(f"/proc/{pid}/stat", "r", encoding="utf-8", errors="ignore") as fh:
                    stat_txt = fh.read()
                rparen = stat_txt.rfind(")")
                if rparen != -1:
                    after = stat_txt[rparen + 2 :].split()
                    if len(after) >= 20:
                        ppid = int(after[1])
                        start_ticks = int(after[19])
                        if boot_time > 0 and clk_tck > 0:
                            elapsed = max(0, int(now_ts - (boot_time + start_ticks / clk_tck)))
                            uptime_str = _format_duration(elapsed)
            except Exception:
                pass

            rss_mb = 0.0
            try:
                with open(f"/proc/{pid}/status", "r", encoding="utf-8", errors="ignore") as fh:
                    for line in fh:
                        if line.startswith("VmRSS:"):
                            kb = int(line.split()[1])
                            rss_mb = round(kb / 1024.0, 1)
                            break
            except Exception:
                pass

            procs[pid] = {
                "pid": pid,
                "ppid": ppid,
                "name": name,
                "cmdline": cmdline,
                "rss_mb": rss_mb,
                "uptime": uptime_str,
            }
        except Exception:
            continue

    # 2. Listening TCP ports via ss -ltnp (fast & reliable)
    try:
        out = subprocess.check_output(["ss", "-ltnp"], text=True, stderr=subprocess.DEVNULL, timeout=4)
        for line in out.splitlines():
            m_port = re.search(r":(\d+)\s+", line)
            if not m_port:
                continue
            p_num = int(m_port.group(1))
            for m_pid in re.finditer(r"pid=(\d+)", line):
                pid_val = int(m_pid.group(1))
                port_to_pids.setdefault(p_num, [])
                if pid_val not in port_to_pids[p_num]:
                    port_to_pids[p_num].append(pid_val)
    except Exception:
        # Pure /proc fallback (socket inodes)
        inode_to_port: Dict[str, int] = {}
        for tcp_file in ("/proc/net/tcp", "/proc/net/tcp6"):
            try:
                with open(tcp_file, "r", encoding="utf-8", errors="ignore") as fh:
                    for line in fh.readlines()[1:]:
                        cols = line.split()
                        if len(cols) >= 10 and cols[3] == "0A":  # TCP_LISTEN
                            p_hex = cols[1].rsplit(":", 1)[-1]
                            inode_to_port[cols[9]] = int(p_hex, 16)
            except Exception:
                pass
        if inode_to_port:
            for pid in list(procs.keys()):
                fd_dir = f"/proc/{pid}/fd"
                try:
                    for fd_name in os.listdir(fd_dir):
                        target = os.readlink(os.path.join(fd_dir, fd_name))
                        if target.startswith("socket:[") and target.endswith("]"):
                            inode = target[8:-1]
                            if inode in inode_to_port:
                                p_num = inode_to_port[inode]
                                port_to_pids.setdefault(p_num, [])
                                if pid not in port_to_pids[p_num]:
                                    port_to_pids[p_num].append(pid)
                except Exception:
                    pass

    return procs, port_to_pids


def _format_duration(seconds: int) -> str:
    if seconds < 60:
        return f"{seconds}s"
    if seconds < 3600:
        return f"{seconds // 60}m {seconds % 60:02d}s"
    hours = seconds // 3600
    mins = (seconds % 3600) // 60
    return f"{hours}h {mins:02d}m"


def _get_ancestor_pids(procs: Dict[int, Dict[str, Any]]) -> set:
    ancestors = set()
    curr = os.getpid()
    for _ in range(32):
        if curr <= 1 or curr in ancestors:
            break
        ancestors.add(curr)
        info = procs.get(curr)
        if not info:
            if curr == os.getpid():
                curr = os.getppid()
                continue
            break
        curr = int(info.get("ppid") or 0)
    ancestors.add(os.getppid())
    return ancestors


def _is_self_or_manager(pid: int, cmdline_low: str, ancestor_pids: Optional[set] = None) -> bool:
    if pid == os.getpid() or pid == os.getppid():
        return True
    if ancestor_pids and pid in ancestor_pids:
        return True
    if "monitor_servicos_cbi.py" in cmdline_low or "encerrar_servicos_cbi.py" in cmdline_low:
        return True
    if "monitorservicoscbi.exe" in cmdline_low or "encerrarservicoscbi.exe" in cmdline_low:
        return True
    return False


def _match_process_to_service(
    proc: Dict[str, Any],
    svc: ServiceSpec,
    listening_ports: List[int],
    ancestor_pids: Optional[set] = None,
) -> bool:
    pid = proc["pid"]
    cmd_low = proc["cmdline"].lower()
    name_low = proc["name"].lower()
    if _is_self_or_manager(pid, cmd_low, ancestor_pids=ancestor_pids):
        return False

    # 1. Exact listening port match
    if svc.port and svc.port in listening_ports:
        return True

    # Avoid false positive on generic shells (bash/sh/cmd) unless running the exact .bat/.exe
    is_shell = name_low in ("bash", "sh", "zsh", "dash", "cmd.exe", "powershell.exe", "pwsh.exe")

    # 2. Match executable name directly (except shared CSM5000_Desktop.exe unless cmd matches folder)
    for exe in svc.exe_names:
        exe_low = exe.lower()
        if exe_low == "csm5000_desktop.exe":
            if (name_low == exe_low or exe_low in cmd_low) and any(t in cmd_low for t in svc.match_tokens):
                return True
        elif name_low == exe_low or exe_low in cmd_low:
            return True

    if is_shell:
        return False

    # 3. Match explicit tokens in non-shell process command line
    for tok in svc.match_tokens:
        if tok in cmd_low:
            return True

    return False


def scan_all_services(root_dir: Optional[str] = None) -> Dict[str, Any]:
    """
    Executa varredura completa em todos os aplicativos CBI + processos e portas do sistema.
    """
    root = root_dir or discover_ecosystem_root()
    procs, port_to_pids = _enumerate_os_processes_and_ports()
    ancestor_pids = _get_ancestor_pids(procs)

    # Invert port_to_pids -> pid_to_ports
    pid_to_ports: Dict[int, List[int]] = {}
    for p_num, pids in port_to_pids.items():
        for pid in pids:
            pid_to_ports.setdefault(pid, []).append(p_num)

    # Probe all ports concurrently (< 0.4s total)
    ports_to_probe = [s.port for s in SERVICE_CATALOG if s.port is not None]
    probe_results: Dict[int, Dict[str, Any]] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as pool:
        futs = {pool.submit(_probe_port_and_http, port): port for port in ports_to_probe}
        for fut in concurrent.futures.as_completed(futs):
            p = futs[fut]
            try:
                probe_results[p] = fut.result()
            except Exception:
                probe_results[p] = {"tcp_open": False, "latency_ms": None, "http_status": None}

    services_out: List[Dict[str, Any]] = []
    matched_pids = set()

    for svc in SERVICE_CATALOG:
        cwd = svc.resolve_cwd(root)
        script_path = svc.resolve_script(root)
        exe_paths = [os.path.join(cwd, e) for e in svc.exe_names]
        exe_exists = any(os.path.exists(p) for p in exe_paths)
        script_exists = os.path.exists(script_path)

        matched_procs: List[Dict[str, Any]] = []
        for pid, proc in procs.items():
            p_ports = pid_to_ports.get(pid, [])
            if _match_process_to_service(proc, svc, p_ports, ancestor_pids=ancestor_pids):
                p_copy = dict(proc)
                p_copy["listening_ports"] = sorted(p_ports)
                matched_procs.append(p_copy)
                matched_pids.add(pid)

        matched_procs.sort(key=lambda x: x["pid"])
        probe = probe_results.get(svc.port, {"tcp_open": False, "latency_ms": None, "http_status": None})
        tcp_open = bool(probe["tcp_open"])

        if svc.port:
            if tcp_open and matched_procs:
                status = "ONLINE"
            elif tcp_open and not matched_procs:
                status = "ONLINE"
            elif not tcp_open and matched_procs:
                status = "TRAVADO"
            else:
                status = "OFFLINE"
        else:
            status = "ATIVO" if matched_procs else "INATIVO"

        total_ram_mb = round(sum(p.get("rss_mb", 0.0) for p in matched_procs), 1)
        uptimes = [p.get("uptime", "") for p in matched_procs if p.get("uptime")]

        services_out.append({
            "id": svc.id,
            "code": svc.code,
            "name": svc.name,
            "category": svc.category,
            "port": svc.port,
            "status": status,
            "tcp_open": tcp_open,
            "http_status": probe.get("http_status"),
            "latency_ms": probe.get("latency_ms"),
            "pids": [p["pid"] for p in matched_procs],
            "processes": matched_procs,
            "process_count": len(matched_procs),
            "ram_mb": total_ram_mb,
            "uptime": uptimes[0] if uptimes else "",
            "cwd": cwd,
            "cwd_exists": os.path.exists(cwd),
            "script_path": script_path,
            "script_exists": script_exists,
            "exe_names": list(svc.exe_names),
            "exe_exists": exe_exists,
            "bat_names": list(svc.bat_names),
            "url": f"http://127.0.0.1:{svc.port}" if svc.port else None,
        })

    # Detect unmatched processes that mention "cbi", "laudos", "workflex", "multigas", "napro", "snapon", etc.
    orphan_procs: List[Dict[str, Any]] = []
    orphan_keywords = (
        "cbi-", "_editor_", "_gerador_", "_controle_", "_validacao_", "_conversor_",
        "_oficina_", "_protetor_", "_catalogo_", "_informacoes_tecnicas",
        "start_all_services", "laudos/app", "lista cbi", "workflex", "netbrake", "vistovap",
    )
    for pid, proc in procs.items():
        if pid in matched_pids:
            continue
        cmd_low = proc["cmdline"].lower()
        name_low = proc["name"].lower()
        if _is_self_or_manager(pid, cmd_low, ancestor_pids=ancestor_pids):
            continue
        if name_low in ("bash", "sh", "zsh", "dash", "cmd.exe", "powershell.exe", "pwsh.exe"):
            continue
        if any(k in cmd_low for k in orphan_keywords):
            p_copy = dict(proc)
            p_copy["listening_ports"] = sorted(pid_to_ports.get(pid, []))
            orphan_procs.append(p_copy)

    web_services = [s for s in services_out if s["port"] is not None]
    online_count = sum(1 for s in web_services if s["status"] == "ONLINE")
    active_all_count = sum(1 for s in services_out if s["status"] in ("ONLINE", "ATIVO", "TRAVADO"))
    total_pids = sum(s["process_count"] for s in services_out) + len(orphan_procs)
    total_ram = round(
        sum(s["ram_mb"] for s in services_out) + sum(p.get("rss_mb", 0.0) for p in orphan_procs),
        1,
    )

    return {
        "ok": True,
        "scanned_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "root_dir": root,
        "summary": {
            "total_services": len(services_out),
            "web_services": len(web_services),
            "online_web": online_count,
            "offline_web": len(web_services) - online_count,
            "active_all": active_all_count,
            "active_pids": total_pids,
            "orphan_processes": len(orphan_procs),
            "total_ram_mb": total_ram,
        },
        "services": services_out,
        "orphan_processes": orphan_procs,
    }


# ==============================================================================
# AÇÕES: ENCERRAR, MATAR PORTA, INICIAR E REINICIAR
# ==============================================================================

def _kill_pid_tree(pid: int, force: bool = False) -> Tuple[bool, str]:
    if pid == os.getpid() or pid <= 0:
        return False, f"PID {pid} protegido (auto-proteção)"
    try:
        if os.name == "nt":
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            cmd = ["taskkill", "/PID", str(pid), "/T"]
            if force:
                cmd.append("/F")
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=6, creationflags=flags)
            if res.returncode == 0:
                return True, f"PID {pid} encerrado via taskkill"
            if not force:
                res_f = subprocess.run(
                    ["taskkill", "/PID", str(pid), "/T", "/F"],
                    capture_output=True,
                    text=True,
                    timeout=6,
                    creationflags=flags,
                )
                return res_f.returncode == 0, (res_f.stdout or res_f.stderr).strip()
            return False, (res.stdout or res.stderr).strip()
        else:
            sig = signal.SIGKILL if force else signal.SIGTERM
            os.kill(pid, sig)
            if not force:
                for _ in range(12):
                    time.sleep(0.1)
                    try:
                        os.kill(pid, 0)
                    except ProcessLookupError:
                        return True, f"PID {pid} encerrado (SIGTERM)"
                os.kill(pid, signal.SIGKILL)
                return True, f"PID {pid} encerrado (SIGKILL após timeout)"
            return True, f"PID {pid} encerrado (SIGKILL)"
    except ProcessLookupError:
        return True, f"PID {pid} já não estava em execução"
    except PermissionError as exc:
        return False, f"Sem permissão para encerrar PID {pid}: {exc}"
    except Exception as exc:
        return False, f"Erro ao encerrar PID {pid}: {exc}"


def terminate_pids(pids: List[int], force: bool = True, reason: str = "manual") -> Dict[str, Any]:
    results = []
    killed = 0
    for pid in sorted(set(int(p) for p in pids if int(p) > 0)):
        ok, msg = _kill_pid_tree(pid, force=force)
        if ok:
            killed += 1
        results.append({"pid": pid, "ok": ok, "message": msg})
    append_action_log("ENCERRAR_PIDS", f"{len(pids)} PIDs ({reason})", "OK" if killed else "NONE", {"results": results})
    return {"ok": True, "killed_count": killed, "results": results}


def terminate_by_port(port: int, force: bool = True) -> Dict[str, Any]:
    _, port_to_pids = _enumerate_os_processes_and_ports()
    pids = port_to_pids.get(int(port), [])
    if not pids:
        probe = _probe_port_and_http(int(port))
        if not probe["tcp_open"]:
            return {"ok": True, "port": int(port), "killed_count": 0, "message": f"Porta {port} já está livre."}
        return {"ok": False, "port": int(port), "killed_count": 0, "message": f"Porta {port} aberta, mas nenhum PID identificável sem elevação."}
    res = terminate_pids(pids, force=force, reason=f"porta:{port}")
    time.sleep(0.25)
    after = _probe_port_and_http(int(port))
    res["port"] = int(port)
    res["port_freed"] = not after["tcp_open"]
    res["message"] = f"Porta {port}: {res['killed_count']} processo(s) encerrado(s)."
    return res


def terminate_service(service_id: str, force: bool = True, root_dir: Optional[str] = None) -> Dict[str, Any]:
    snap = scan_all_services(root_dir=root_dir)
    target = next((s for s in snap["services"] if s["id"] == service_id), None)
    if not target:
        return {"ok": False, "error": f"Serviço desconhecido: {service_id}"}
    pids = list(target["pids"])
    if not pids and target["port"]:
        return terminate_by_port(int(target["port"]), force=force)
    if not pids:
        return {"ok": True, "service_id": service_id, "killed_count": 0, "message": f"{target['name']} já está parado."}
    res = terminate_pids(pids, force=force, reason=service_id)
    port_freed = True
    if target["port"]:
        time.sleep(0.25)
        port_freed = not _probe_port_and_http(int(target["port"]))["tcp_open"]
    append_action_log("ENCERRAR_SERVICO", service_id, "OK", {"pids": pids, "port_freed": port_freed})
    return {
        "ok": True,
        "service_id": service_id,
        "name": target["name"],
        "killed_count": res["killed_count"],
        "port_freed": port_freed,
        "results": res["results"],
        "message": f"{target['name']}: {res['killed_count']} processo(s) encerrado(s).",
    }


def terminate_all_services(
    force: bool = True,
    include_central: bool = True,
    include_orphans: bool = True,
    root_dir: Optional[str] = None,
) -> Dict[str, Any]:
    """Encerra o Orquestrador primeiro (para não relançar filhos) e depois todos os aplicativos ativos."""
    t0 = time.perf_counter()
    snap = scan_all_services(root_dir=root_dir)

    ordered_ids: List[str] = []
    # 1. Orquestrador primeiro
    ordered_ids.append("orquestrador_ecossistema")
    # 2. Aplicativos web e desktop (01..15)
    for s in snap["services"]:
        if s["id"] in ("orquestrador_ecossistema", "00_central_integrada"):
            continue
        if s["pids"] or s["tcp_open"]:
            ordered_ids.append(s["id"])
    # 3. Central Integrada (00) por último, se solicitado
    if include_central:
        ordered_ids.append("00_central_integrada")

    pids_to_kill: List[int] = []
    services_hit: List[str] = []
    for sid in ordered_ids:
        svc = next((x for x in snap["services"] if x["id"] == sid), None)
        if not svc:
            continue
        if svc["pids"]:
            pids_to_kill.extend(svc["pids"])
            services_hit.append(svc["name"])

    if include_orphans:
        for op in snap["orphan_processes"]:
            pids_to_kill.append(op["pid"])

    # Dedup preserving order (orquestrador first)
    unique_pids: List[int] = []
    for pid in pids_to_kill:
        if pid not in unique_pids and pid != os.getpid():
            unique_pids.append(pid)

    results = []
    killed_count = 0
    for pid in unique_pids:
        ok, msg = _kill_pid_tree(pid, force=force)
        if ok:
            killed_count += 1
        results.append({"pid": pid, "ok": ok, "message": msg})

    time.sleep(0.35)
    after_snap = scan_all_services(root_dir=root_dir)
    elapsed_ms = round((time.perf_counter() - t0) * 1000, 1)

    summary = {
        "ok": True,
        "killed_count": killed_count,
        "targeted_pids": unique_pids,
        "services_targeted": services_hit,
        "remaining_online_web": after_snap["summary"]["online_web"],
        "remaining_active_pids": after_snap["summary"]["active_pids"],
        "elapsed_ms": elapsed_ms,
        "results": results,
        "message": (
            f"Encerramento geral concluído em {elapsed_ms} ms: "
            f"{killed_count}/{len(unique_pids)} processo(s) encerrado(s). "
            f"Serviços online restantes: {after_snap['summary']['online_web']}."
        ),
    }
    append_action_log("ENCERRAR_TODOS", "ECOSSISTEMA_CBI", "OK", {
        "killed": killed_count,
        "remaining_online": after_snap["summary"]["online_web"],
        "include_central": include_central,
    })
    return summary


def start_service(service_id: str, prefer_exe: bool = True, root_dir: Optional[str] = None) -> Dict[str, Any]:
    root = root_dir or discover_ecosystem_root()
    svc = SERVICE_BY_ID.get(service_id)
    if not svc:
        return {"ok": False, "error": f"Serviço desconhecido: {service_id}"}

    if svc.port and _probe_port_and_http(svc.port)["tcp_open"]:
        return {"ok": True, "already_running": True, "port_ready": True, "service_id": service_id, "port": svc.port, "message": f"{svc.name} já está ONLINE na porta {svc.port}."}

    cwd = svc.resolve_cwd(root)
    if not os.path.exists(cwd):
        return {"ok": False, "error": f"Pasta do serviço não encontrada: {cwd}"}

    env = os.environ.copy()
    env["NO_BROWSER"] = "1"
    if svc.port:
        env["PORT"] = str(svc.port)
    if svc.extra_env:
        env.update(svc.extra_env)

    python_bin = "/tmp/venv/bin/python3" if os.path.exists("/tmp/venv/bin/python3") else sys.executable

    cmd: Optional[List[str]] = None
    # On Windows, if compiled EXE exists and prefer_exe is True, launch the standalone EXE
    if os.name == "nt" and prefer_exe:
        for exe_name in svc.exe_names:
            cand_exe = os.path.join(cwd, exe_name)
            if os.path.exists(cand_exe):
                cmd = [cand_exe]
                break

    if cmd is None:
        script_path = svc.resolve_script(root)
        if not os.path.exists(script_path):
            return {"ok": False, "error": f"Script principal não encontrado: {script_path}"}
        if svc.cmd_mode == "flask_app":
            cmd = [python_bin, "-c", f"from app import app; app.run(host='0.0.0.0', port={svc.port}, debug=False, threaded=True)"]
        elif svc.cmd_mode == "uvicorn":
            cmd = [python_bin, "-c", f"import uvicorn; from app import app; uvicorn.run(app, host='0.0.0.0', port={svc.port}, log_level='warning')"]
        else:
            cmd = [python_bin, svc.entry_script]

    popen_kwargs: Dict[str, Any] = {
        "cwd": cwd,
        "env": env,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
        "stdin": subprocess.DEVNULL,
    }
    if os.name == "nt":
        popen_kwargs["creationflags"] = (
            getattr(subprocess, "DETACHED_PROCESS", 0)
            | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            | getattr(subprocess, "CREATE_NO_WINDOW", 0)
        )
    else:
        popen_kwargs["start_new_session"] = True

    proc = subprocess.Popen(cmd, **popen_kwargs)

    port_ready = False
    if svc.port:
        for _ in range(18):
            time.sleep(0.25)
            if _probe_port_and_http(svc.port, timeout=0.25)["tcp_open"]:
                port_ready = True
                break

    append_action_log("INICIAR_SERVICO", service_id, "OK", {"pid": proc.pid, "port_ready": port_ready, "cmd": cmd})
    return {
        "ok": True,
        "service_id": service_id,
        "name": svc.name,
        "pid": proc.pid,
        "port": svc.port,
        "port_ready": port_ready,
        "message": f"{svc.name} iniciado (PID {proc.pid})" + (f" — Porta {svc.port} {'ONLINE' if port_ready else 'subindo'}" if svc.port else "."),
    }


def restart_service(service_id: str, force: bool = True, root_dir: Optional[str] = None) -> Dict[str, Any]:
    stop_res = terminate_service(service_id, force=force, root_dir=root_dir)
    time.sleep(0.3)
    start_res = start_service(service_id, root_dir=root_dir)
    append_action_log("REINICIAR_SERVICO", service_id, "OK" if start_res.get("ok") else "ERROR", {
        "stop": stop_res.get("killed_count", 0),
        "start_pid": start_res.get("pid"),
    })
    return {"ok": start_res.get("ok", False), "stop": stop_res, "start": start_res, "message": start_res.get("message", "")}


def export_snapshot_csv(snapshot: Dict[str, Any], filepath: str) -> str:
    cols = ["code", "name", "category", "status", "port", "http_status", "latency_ms", "process_count", "pids", "ram_mb", "uptime", "cwd"]
    with open(filepath, "w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.writer(fh, delimiter=";")
        writer.writerow(cols)
        for svc in snapshot.get("services", []):
            writer.writerow([
                svc.get("code", ""),
                svc.get("name", ""),
                svc.get("category", ""),
                svc.get("status", ""),
                svc.get("port") or "",
                svc.get("http_status") or "",
                svc.get("latency_ms") or "",
                svc.get("process_count", 0),
                ",".join(str(p) for p in svc.get("pids", [])),
                svc.get("ram_mb", 0.0),
                svc.get("uptime", ""),
                svc.get("cwd", ""),
            ])
    return filepath
