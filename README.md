# 16 — Monitor e Encerrador de Serviços CBI (`cbi-16-gerenciador-servicos`)

Utilitários nativos Desktop (**Tkinter — 100% Python 3.11 stdlib, sem navegador web**) e CLI para monitorar em tempo real e encerrar qualquer serviço, porta ou árvore de processos de todos os aplicativos do Ecossistema CBI (**00 a 15 + Orquestrador**).

## Aplicativos Incluídos (`16_MONITOR_GERENCIADOR_SERVICOS/`)

1. **`monitor_servicos_cbi.py`** (`ABRIR_MONITOR_SERVICOS.bat`)
   - Painel Desktop Tkinter em tempo real para todos os 16 aplicativos + Orquestrador.
   - Exibe status (`ONLINE`, `OFFLINE`, `TRAVADO`, `ATIVO`), porta TCP, status HTTP, latência (ms), PIDs, consumo de RAM (MB), uptime, processos órfãos e histórico de eventos.
   - Permite iniciar, reiniciar, abrir no navegador ou exportar snapshot em CSV/JSON.

2. **`encerrar_servicos_cbi.py`** (`ABRIR_ENCERRADOR_SERVICOS.bat` / `ENCERRAR_TODOS_SERVICOS_AGORA.bat`)
   - Utilitário Desktop Tkinter + CLI para encerrar qualquer serviço individual, processos selecionados via checkbox, processos órfãos, processo por porta TCP (`Matar Porta`), ou **TODOS os serviços CBI** com 1 clique.
   - CLI disponível para automação/atalhos:
     - `python encerrar_servicos_cbi.py --all --yes`
     - `python encerrar_servicos_cbi.py --service 08_gerador_laudos`
     - `python encerrar_servicos_cbi.py --port 8760`
     - `python encerrar_servicos_cbi.py --list`

## Integração com o Ecossistema
Integrado nativamente à **00_CENTRAL_INTEGRADA_CBI** (`:8700`) via rotas `/api/servicos/*` e aba **Monitor & Encerrador** na Central.
