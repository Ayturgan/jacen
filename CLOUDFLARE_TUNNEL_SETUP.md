# Настройка Cloudflare Tunnel на новом ПК (config уже есть)

Эта инструкция для переноса бота на новый Windows-ПК, когда файл `config.yml` туннеля уже создан.

## Что должно быть заранее

- Домен подключён к Cloudflare.
- Туннель уже создан в аккаунте Cloudflare.
- На новом ПК есть:
  - `C:\Users\<USER>\.cloudflared\config.yml`
  - `C:\Users\<USER>\.cloudflared\<TUNNEL_ID>.json` (credentials-file)
- Бот локально запускается, например, на `http://localhost:8000`.

## 1) Установка cloudflared

```powershell
winget install Cloudflare.cloudflared
cloudflared --version
```

Если `winget` недоступен, установить MSI с официального сайта Cloudflare.

## 2) Проверка конфига

Проверь, что в `config.yml` корректные поля:

```yaml
tunnel: <TUNNEL_ID>
credentials-file: C:\Users\<USER>\.cloudflared\<TUNNEL_ID>.json

ingress:
  - hostname: api.yourdomain.com
    service: http://localhost:8000
  - service: http_status:404
```

Важно:
- `hostname` должен быть вашим поддоменом.
- `service` должен совпадать с локальным портом API бота.
- путь в `credentials-file` должен существовать на новом ПК.

## 3) Проверка, что DNS-привязка уже есть

```powershell
cloudflared tunnel list
cloudflared tunnel info <TUNNEL_NAME_OR_ID>
```

Если нужно заново привязать поддомен:

```powershell
cloudflared tunnel route dns <TUNNEL_NAME> api.yourdomain.com
```

## 4) Тестовый запуск туннеля

```powershell
cloudflared tunnel run <TUNNEL_NAME>
```

Ожидаемое в логах:
- `Registered tunnel connection`

Если видишь периодические `Retrying connection` — это допустимо при кратких сетевых сбоях.

## 5) Автозапуск как сервис Windows

```powershell
cloudflared service install
sc query cloudflared
```

После этого туннель будет подниматься автоматически после перезагрузки.

## 6) Запуск бота

1. Подними backend бота на том же порту, что в `config.yml` (например `8000`).
2. Убедись, что endpoint здоровья отвечает:

```powershell
curl http://localhost:8000/health
```

(Если в проекте другой путь health-check — используй его.)

## 7) Telegram webhook (если используешь webhook-режим)

Установить webhook:

```text
https://api.telegram.org/bot<BOT_TOKEN>/setWebhook?url=https://api.yourdomain.com/webhook
```

Проверить:

```text
https://api.telegram.org/bot<BOT_TOKEN>/getWebhookInfo
```

## 8) Частые проблемы и решение

### Ошибка DNS timeout

Пример: `Failed to refresh DNS local resolver ... i/o timeout`

Что делать:
- выставить DNS на ПК: `1.1.1.1` и `8.8.8.8`;
- проверить, что VPN/прокси не ломают UDP/QUIC;
- обновить `cloudflared`;
- при нестабильной сети запустить с HTTP2:

```powershell
cloudflared tunnel run <TUNNEL_NAME> --protocol http2
```

### Порт недоступен

- проверь, что бот реально слушает `localhost:<PORT>`;
- проверь соответствие порта в `config.yml`.

### Туннель есть, но домен не открывается

- проверить, что `hostname` в `ingress` совпадает с поддоменом;
- проверить DNS route командой `cloudflared tunnel route dns ...`;
- подождать обновление DNS (обычно быстро, но иногда до нескольких минут).

## 9) Мини-чеклист

- [ ] `cloudflared --version` работает
- [ ] `config.yml` и `<TUNNEL_ID>.json` на месте
- [ ] `cloudflared tunnel run <TUNNEL_NAME>` даёт `Registered tunnel connection`
- [ ] Бот отвечает локально на нужном порту
- [ ] `api.yourdomain.com` доступен извне
- [ ] webhook установлен и `getWebhookInfo` без ошибок
