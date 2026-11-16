# -*- coding: utf-8 -*-
import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

APP_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

import cbi_services_core as core


class _DummyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

    def log_message(self, format, *args):
        return


class TestMonitorAndStopper(unittest.TestCase):
    def test_catalog_covers_all_apps_00_to_15(self):
        codes = {s.code for s in core.SERVICE_CATALOG}
        for i in range(16):
            self.assertIn(f"{i:02d}", codes, f"App {i:02d} ausente do catálogo")
        self.assertIn("ORQ", codes)

    def test_scan_structure_and_csv_export(self):
        snap = core.scan_all_services()
        self.assertTrue(snap["ok"])
        self.assertGreaterEqual(snap["summary"]["total_services"], 17)
        with tempfile.TemporaryDirectory() as tmpd:
            out_csv = os.path.join(tmpd, "snap.csv")
            core.export_snapshot_csv(snap, out_csv)
            self.assertTrue(os.path.exists(out_csv))
            with open(out_csv, "r", encoding="utf-8-sig") as fh:
                content = fh.read()
            self.assertIn("15_informacoes_tecnicas" if False else "8780", content)

    def test_start_detect_and_terminate_real_service_15(self):
        # Garante limpeza antes
        core.terminate_service("15_informacoes_tecnicas", force=True)
        res_start = core.start_service("15_informacoes_tecnicas", prefer_exe=False)
        try:
            self.assertTrue(res_start["ok"], res_start)
            self.assertTrue(res_start["port_ready"], "Porta 8780 deveria subir")

            snap = core.scan_all_services()
            svc15 = next(s for s in snap["services"] if s["id"] == "15_informacoes_tecnicas")
            self.assertEqual(svc15["status"], "ONLINE")
            self.assertTrue(svc15["tcp_open"])
            self.assertEqual(svc15["http_status"], 200)
            self.assertTrue(len(svc15["pids"]) >= 1)

            res_stop = core.terminate_service("15_informacoes_tecnicas", force=True)
            self.assertTrue(res_stop["ok"])
            self.assertTrue(res_stop["port_freed"])

            snap_after = core.scan_all_services()
            svc15_after = next(s for s in snap_after["services"] if s["id"] == "15_informacoes_tecnicas")
            self.assertEqual(svc15_after["status"], "OFFLINE")
            self.assertFalse(svc15_after["tcp_open"])
        finally:
            core.terminate_service("15_informacoes_tecnicas", force=True)

    def test_terminate_by_port_process(self):
        # Sobe um subprocesso HTTP simples escutando em porta alta temporária e mata pela porta
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
        s.close()

        proc = subprocess.Popen(
            [sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            ready = False
            for _ in range(20):
                time.sleep(0.15)
                if core._probe_port_and_http(port)["tcp_open"]:
                    ready = True
                    break
            self.assertTrue(ready, "Servidor de teste não subiu")

            res = core.terminate_by_port(port, force=True)
            self.assertTrue(res["ok"], res)
            self.assertGreaterEqual(res["killed_count"], 1)
            self.assertTrue(res["port_freed"])
        finally:
            try:
                proc.kill()
            except Exception:
                pass

    def test_cli_json_outputs(self):
        out_mon = subprocess.check_output(
            [sys.executable, os.path.join(APP_DIR, "monitor_servicos_cbi.py"), "--snapshot-json"],
            text=True,
        )
        data_mon = json.loads(out_mon)
        self.assertTrue(data_mon["ok"])

        out_stop = subprocess.check_output(
            [sys.executable, os.path.join(APP_DIR, "encerrar_servicos_cbi.py"), "--list"],
            text=True,
        )
        data_stop = json.loads(out_stop)
        self.assertTrue(data_stop["ok"])


if __name__ == "__main__":
    unittest.main()
