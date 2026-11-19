# Registro de Padronização Visual — PROJETO `TEMA_VISTOCAR`

- **Repositório:** `wkadyk3886/cbi-16-gerenciador-servicos`
- **Branch-base:** `main`
- **Branch de trabalho:** `TEMA_VISTOCAR`
- **Data de início:** 2026-11-18
- **Situação da implementação:** Concluída na branch `TEMA_VISTOCAR` (aguardando revisão e autorização para push/PR)

## Identidade Visual Aplicada
- **Tema padrão ativo:** `cbi` — Fundo Preto/Grafite (`#090A0D` / `#12151B` / `#1A1E27`), primária Carmim CBI (`#C02626`) extraída do logotipo oficial CBI e destaque Ouro VistoCar (`#FFC30B`) extraído do logotipo oficial do Grupo VistoCar.
- **Variante institucional alternável:** `vistocar` — Azul Institucional (`#071326` / `#0E1F3B` / `#1D4ED8`) + Ouro VistoCar (`#FFC30B`), alternável em 1 clique e sincronizada com a Central Integrada (`cbi-00`).
- **Logotipos oficiais preservados integralmente:** Grupo VistoCar (`logo_vistocar.jpg`), CBI Produtos Perigosos (`logo_cbi.jpeg` / `logo_cbi_pp.png`) e VistoVap (`logo_vistovap.png` / `logo_vistovap.svg`).

## Componentes Implementados
- Módulo `vistocar_tk_theme.py`, cabeçalhos institucionais CBI Preto/Grafite com faixa carmim e subtítulo ouro VistoCar, KPI cards, toolbars e tabelas ttk padronizadas no Monitor e no Encerrador.

## Arquivos Criados
- `16_MONITOR_GERENCIADOR_SERVICOS/tokens.json`
- `16_MONITOR_GERENCIADOR_SERVICOS/vistocar_tk_theme.py`

## Arquivos Modificados
- `16_MONITOR_GERENCIADOR_SERVICOS/encerrar_servicos_cbi.py`
- `16_MONITOR_GERENCIADOR_SERVICOS/monitor_servicos_cbi.py`

## Testes Executados
- pytest tests/test_monitor_and_stopper.py: 5/5 passed; py_compile OK em monitor_servicos_cbi.py, encerrar_servicos_cbi.py e vistocar_tk_theme.py.

## Problemas Identificados
- Nenhum erro de compilação, rota HTTP ou regressão funcional identificado após a padronização.
- Observação operacional: testes de interface gráfica desktop (`Tkinter`/`CustomTkinter`) e recompilação de executáveis `.exe` (PyInstaller) e `.apk` (Android Gradle) devem ser validados visualmente no ambiente Windows/Android de destino quando os binários forem regenerados.

## Pendências
- Aguardando aprovação visual e autorização expressa para `git push` da branch `TEMA_VISTOCAR` e abertura de Pull Request (sem merge automático em `main`).
- Regeneração dos binários `.exe` / `.apk` (somente após aprovação final da branch `TEMA_VISTOCAR`).

## Commits Realizados
- `769cc34` — feat(theme): aplicação do Design System TEMA_VISTOCAR (CBI & Grupo VistoCar) em cbi-16-gerenciador-servicos
