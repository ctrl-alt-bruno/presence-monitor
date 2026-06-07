# Presence Monitor

Detecta presença via câmera RGB e controla o monitor automaticamente.

## Requisitos

- Windows 10 ou 11 (64-bit)
- Python 3.11+ — https://python.org/downloads (marcar **"Add Python to PATH"**)
- Câmera RGB (ex: Logitech StreamCam)

## Instalação

```
pip install -r requirements.txt
python presence_monitor.py
```

Na primeira execução, o modelo de detecção (~1 MB) é baixado automaticamente.

## Parâmetros

| Parâmetro      | Descrição                                       |
|----------------|-------------------------------------------------|
| *(nenhum)*     | Modo normal — apenas tray icon, sem console     |
| `--debug`      | Output no terminal + janela de câmera ao vivo   |
| `--install`    | Registra no início automático do Windows        |
| `--uninstall`  | Remove do início automático                     |

## Constantes (topo do script)

| Constante        | Padrão | Descrição                                        |
|------------------|--------|--------------------------------------------------|
| `CAMERA_INDEX`   | `0`    | Índice da câmera (0 = padrão do sistema)         |
| `CHECK_INTERVAL` | `3.0`  | Segundos entre verificações                      |
| `ABSENT_STREAK`  | `3`    | Strikes padrão (≈ 9 s) — ajustável pelo menu     |
| `MIN_CONFIDENCE` | `0.5`  | Confiança mínima do MediaPipe (0.0–1.0)          |

## Ícone da bandeja

| Cor     | Significado      |
|---------|------------------|
| Verde   | Presente         |
| Azul    | Ausente          |
| Cinza   | Detecção pausada |
| X branco | Monitor OFF     |

## Menu (botão direito)

| Item                       | Descrição                                           |
|----------------------------|-----------------------------------------------------|
| Pausar / Retomar detecção  | Suspende o monitoramento sem encerrar               |
| Ligar automático ON/OFF    | Habilita ligamento automático ao detectar presença  |
| Delay: N strikes           | Quantidade de detecções consecutivas para agir      |
| Ligar monitor              | Liga manualmente                                    |
| Desligar monitor           | Desliga manualmente                                 |
| Iniciar com o Windows      | Registra ou remove início automático                |
| Sair                       | Encerra o programa                                  |

## Como funciona

A câmera captura um frame a cada `CHECK_INTERVAL` segundos. O MediaPipe
(`blaze_face_short_range`) detecta se há um rosto na imagem.

- **Desligar:** `ABSENT_STREAK` verificações consecutivas sem rosto → monitor OFF
- **Ligar** (quando habilitado): `ABSENT_STREAK` verificações consecutivas com rosto → monitor ON

O estado real do monitor é rastreado via `GUID_MONITOR_POWER_ON`
(`RegisterPowerSettingNotification`), então o ícone reflete a realidade
independente de quem ligou ou desligou o monitor.

## Debug

```
python presence_monitor.py --debug
```

```
PRESENTE  rostos=1  +2/3  mon=ON
```

- `rostos` — quantos rostos detectados no frame
- `+2/3` — streak de presença; `-1/3` seria streak de ausência
- `mon` — estado do monitor conforme rastreado pelo Windows
