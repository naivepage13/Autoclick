# AutoClick Macro

Repetidor de teclas e gravador de macros para Windows, com interface mínima
(tkinter) e **sem dependências externas** — só Python 3.9+.

## Recursos
- Repete uma tecla (ou botão do mouse) em um intervalo configurável.
- Grava e reproduz macros de teclado, com repetições (0 = infinito); salva/abre em `.json`.
- Atalhos globais configuráveis (padrão F6 / F7 / F8), aceitam os botões laterais do mouse.
- Indicador na lateral direita da tela: 🟩 ativo / 🟥 parado.

## Uso
```powershell
python main.pyw        # ou: python -m autoclick
```
O indicador pode não aparecer sobre jogos em tela cheia exclusiva; use modo janela ou janela sem bordas.

## Estrutura
```
autoclick/
  winapi.py     SendInput, leitura de teclas, nomes de teclas
  indicator.py  quadrado verde/vermelho
  app.py        interface e lógica
main.pyw        launcher
```

## Aviso
Automação pode violar os termos de uso de alguns jogos e ser detectada por
sistemas anti-cheat. Use por sua conta e risco.

## Licença
MIT
