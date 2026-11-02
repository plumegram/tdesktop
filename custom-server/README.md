# PlumeGram Desktop — сборка Telegram Desktop под свой MTProto-сервер

Форк [telegramdesktop/tdesktop](https://github.com/telegramdesktop/tdesktop) (ветка `custom-server`),
в котором вместо серверов Telegram вшит собственный MTProto-сервер `84.21.173.237`
и RSA-ключ этого сервера.

## Что именно изменено

| Файл | Изменение |
|---|---|
| `Telegram/SourceFiles/mtproto/mtproto_dc_options.cpp` | `kBuiltInDcs` — все DC (1–5) указывают на `84.21.173.237:443`. IPv6-эндпоинты Telegram удалены. `kPublicRSAKeys` и `kTestPublicRSAKeys` — публичный ключ сервера (fingerprint `0x1a47636d1496dcc5`). Добавлен флаг `kLockDcOptions`. |
| `Telegram/SourceFiles/core/version.h` | `AppName` → `PlumeGram Desktop` (своя папка данных `%APPDATA%\PlumeGram Desktop`, не конфликтует с установленным Telegram), `AppId` → свой GUID (свой single-instance и группа на панели задач). |
| `.github/workflows/custom-windows.yml` | Сборка Release x64 в GitHub Actions с выгрузкой `Telegram.exe`. |

Официальные DC-адреса Telegram в коде больше не встречаются — проверяется скриптом
`custom-server/tools/verify_patch.py`.

## Ключи сервера (проверено 02.11.2026)

```
server_rsa.key                     -> 2048 bit, e=65537, fp=0x1a47636d1496dcc5
server_rsa_public_pkcs1.pem        -> совпадает с приватным ключом
server_rsa_public_spki.pem         -> тот же ключ в формате SPKI
```

Важно: `E:\keys\last_export.txt` **устарел**. Он описывает ключ от 23.10.2026
(`server_rsa.key.old_20261023_201459`, fp `0x04b0dd4239debe16`), а не текущий.
В клиент вшит актуальный ключ `0x1a47636d1496dcc5`.

Отпечаток считается так же, как в tdesktop: `sha1(tl_bytes(n) || tl_bytes(e))[12:20]`.
Пересчитать после любой ротации ключа:

```
python custom-server\tools\key_fingerprint.py E:\keys\server_rsa_public_pkcs1.pem
```

## Как собрать

### Вариант A — GitHub Actions (не нужен Visual Studio)

1. Запушь этот репозиторий (ветка `custom-server`) в свой GitHub-аккаунт.
2. Вкладка **Actions** → **Custom server build** → **Run workflow**.
3. Через ~40–70 минут скачай артефакт `PlumeGram-Desktop-win64` → внутри `Telegram.exe`.

Сборка статическая, Qt внутрь — один exe, ничего доустанавливать не нужно.

### Вариант B — локально

Нужны: Visual Studio 2026 (workload «Desktop development with C++»), Windows SDK
`10.0.26100.0`, Python 3.10+, Git, ~12 ГБ на диске, права администратора для установки VS.

```
powershell -ExecutionPolicy Bypass -File custom-server\build-local.ps1
```

Скрипт сам подтянет Qt и остальные библиотеки официальным `prepare/win.bat`,
сконфигурирует Release и соберёт `out\Release\Telegram.exe`.

## Сменить IP / порт / ключ

Всё в одном месте — `Telegram/SourceFiles/mtproto/mtproto_dc_options.cpp`:

```cpp
constexpr auto kCustomServerIp = "84.21.173.237";
constexpr auto kCustomServerPort = 443;
constexpr bool kLockDcOptions = false;   // true = игнорировать DC из help.getConfig
```

После правки — пересобрать. Проверить, что ничего не забыто:

```
python custom-server\tools\verify_patch.py --source E:\tdesktop --key E:\keys\server_rsa.key --ip 84.21.173.237
```

Альтернатива без пересборки (только адреса, не ключ): положить рядом с exe файл
`.tdesktop-endpoints` (пример — `custom-server/tdesktop-endpoints.example`).
Ключ всё равно должен быть в бинарнике.

## Что должен уметь сервер

Клиент — обычный MTProto-клиент, поэтому сервер обязан поддерживать:

- транспорт: **abridged** (`0xef`) или **intermediate** (`0xeeeeeeee`) по «голому» TCP;
- `req_pq_multi` → `resPQ` с одним из отпечатков выше;
- DH-обмен (`req_DH_params` / `set_client_DH_params`) и `auth_key`;
- `help.getConfig`, `help.getNearestDc`, `updates.getState`, `auth.*`, `messages.*` и т.д.;
- `api_id`/`api_hash`, с которыми собран клиент: `2040` / `b18441a1ff607e10a989891a5462e627`
  (меняются через `-D TDESKTOP_API_ID` / `-D TDESKTOP_API_HASH` в `configure.bat`).

## Результат проверки сервера на 02.11.2026 (важно)

Скрипт `custom-server/tools/probe_mtproto.py` и сканирование портов показали:

```
открытые порты 1-65535:  22, 80, 443
443  -> настоящий TLS 1.3 (веб-клиент «PlumeGram Wallet», /health -> {"ok": true})
80   -> тот же веб-клиент
req_pq_multi по abridged/intermediate на 443 -> ответа нет
```

То есть **наружу не выставлен ни один «голый» MTProto-порт**, а на 443 висит HTTPS
с веб-кошельком. Такой клиент подключиться не сможет: он ходит в MTProto по TCP,
а не по TLS. Нужно одно из:

1. открыть отдельный порт (например 5222/8443) и направить его прямо в MTProto-сервер —
   тогда в патче ставим этот порт;
2. поставить перед MTProto `nginx stream` с мультиплексированием по первым байтам
   (`0xef`/`0xee`) на 443 — тогда порт остаётся 443;
3. если сервер умеет только MTProto-over-TLS/WebSocket — это уже не стандартный
   транспорт tdesktop, потребуется отдельный транспорт в коде клиента (обсуждаемо).

Проверить, где слушает MTProto, можно так:

```
python custom-server\tools\probe_mtproto.py --host 84.21.173.237 --ports 1-20000 --scan
python custom-server\tools\probe_mtproto.py --host 84.21.173.237 --ports 443,5222,8443 --keys E:\keys
```

Вторая команда заодно напечатает отпечатки, которые отдаёт сервер, — так сразу видно,
актуальный ли ключ вшит в клиент.

## Ограничения

- Автообновление и отправка краш-репортов отключены при сборке
  (`DESKTOP_APP_DISABLE_AUTOUPDATE=ON`, `DESKTOP_APP_DISABLE_CRASH_REPORTS=ON`).
- Клиент использует собственный `api_id`; если сервер проверяет его строго —
  поменяй define'ы при конфигурации.
- Патч не меняет протокол: клиент остаётся совместимым с MTProto, который отдаёт сервер.
