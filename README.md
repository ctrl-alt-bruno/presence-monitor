# Presence Monitor

Desliga o monitor automaticamente quando você sai da frente do computador, e o liga de volta quando retorna — sem botão, sem timer, sem configuração.

Usa a câmera RGB para detectar seu rosto a cada 3 segundos via MediaPipe. Roda como tray icon, consome CPU apenas no momento da verificação.

## Instalação

**Requisitos:** Windows 10/11 · Python 3.11+ · câmera RGB

```
pip install -r requirements.txt
python presence_monitor.py
```

O modelo de detecção (~1 MB) é baixado automaticamente na primeira execução.

Para iniciar com o Windows:

```
python presence_monitor.py --install
```

## Uso

Após iniciar, o programa fica apenas como ícone na bandeja do sistema. Nenhuma janela, nenhuma interação necessária.

**Ícone:**

| Cor      | Significado      |
|----------|------------------|
| Verde    | Presente         |
| Azul     | Ausente          |
| Cinza    | Detecção pausada |
| X branco | Monitor desligado |

**Menu (botão direito no ícone):**

| Item                      | Descrição                                          |
|---------------------------|----------------------------------------------------|
| Pausar / Retomar detecção | Suspende o monitoramento sem encerrar              |
| Ligar automático ON/OFF   | Habilita ligamento automático ao detectar presença |
| Delay: N strikes          | Detecções consecutivas necessárias para agir       |
| Ligar / Desligar monitor  | Controle manual imediato                           |
| Iniciar com o Windows     | Registra ou remove do início automático            |
| Sair                      | Encerra o programa                                 |

## Como funciona

A câmera captura um frame a cada 3 segundos (padrão). O MediaPipe analisa se há um rosto na imagem. Após 3 verificações consecutivas sem rosto, o monitor apaga. Com o ligar automático ativo, 3 detecções consecutivas o acendem novamente.

O número de verificações (strikes) e o intervalo são ajustáveis pelo menu — de 1 a 10 strikes, com o tempo equivalente exibido em segundos.

O estado real do monitor é rastreado via `RegisterPowerSettingNotification` (`GUID_MONITOR_POWER_ON`), então o ícone reflete a realidade independente de quem ligou ou desligou o monitor.

## Parâmetros de linha de comando

| Parâmetro      | Descrição                                     |
|----------------|-----------------------------------------------|
| *(nenhum)*     | Modo normal — apenas tray icon, sem console   |
| `--debug`      | Output no terminal + janela de câmera ao vivo |
| `--install`    | Registra no início automático do Windows      |
| `--uninstall`  | Remove do início automático                   |

## Ajuste fino

As constantes no topo do script controlam o comportamento padrão:

| Constante        | Padrão | Descrição                                    |
|------------------|--------|----------------------------------------------|
| `CAMERA_INDEX`   | `0`    | Índice da câmera (0 = padrão do sistema)     |
| `CHECK_INTERVAL` | `3.0`  | Segundos entre verificações                  |
| `ABSENT_STREAK`  | `3`    | Strikes iniciais (ajustável pelo menu)       |
| `MIN_CONFIDENCE` | `0.5`  | Confiança mínima do detector (0.0–1.0)       |

## Debug

```
python presence_monitor.py --debug
```

Exibe no terminal e abre a janela da câmera com o rosto demarcado:

```
PRESENTE  rostos=1  +2/3  mon=ON
ausente   rostos=0  -1/3  mon=ON
```

- `+2/3` — streak de presença atual / threshold
- `-1/3` — streak de ausência atual / threshold
- `mon` — estado do monitor rastreado pelo Windows
