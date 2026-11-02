# PlumeGram Desktop — сборка Telegram Desktop под свой MTProto-сервер

Форк [telegramdesktop/tdesktop](https://github.com/telegramdesktop/tdesktop) (ветка `custom-server`),
в котором вместо серверов Telegram вшит собственный сервер `84.21.173.237:20443`
и RSA-ключ этого сервера.

## Что именно изменено

| Файл | Изменение |
|---|---|
| `Telegram/SourceFiles/mtproto/mtproto_dc_options.cpp` | `kBuiltInDcs` — все DC (1–5) указывают на `84.21.173.237:20443`. IPv6-эндпоинты Telegram удалены. `kPublicRSAKeys` и `kTestPublicRSAKeys` — публичный ключ сервера (fingerprint `0x1a47636d1496dcc5`). Добавлен флаг `kLockDcOptions`. |
| `Telegram/SourceFiles/core/version.h` | `AppName` → `PlumeGram Desktop` (своя папка данных `%APPDATA%\PlumeGram Desktop`, не конфликтует с установленным Telegram), `AppId` → свой GUID (свой single-instance и группа на панели задач). |
| `.github/workflows/custom-windows.yml` | Сборка Release x64 в GitHub Actions с выгрузкой `Telegram.exe`. |

Официальных DC-адресов Telegram в коде больше нет — проверяется
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

Отпечаток считается как в tdesktop: `sha1(tl_bytes(n) || tl_bytes(e))[12:20]`, little endian.
Пересчитать после ротации ключа:

```
python custom-server\tools\key_fingerprint.py E:\keys\server_rsa_public_pkcs1.pem
```

## Как собрать (GitHub Actions, без Visual Studio)

1. Запушь репозиторий в свой GitHub:
   ```
   cd E:\tdesktop
   git remote add origin https://github.com/<твой-аккаунт>/tdesktop.git
   git push -u origin custom-server
   ```
2. Вкладка **Actions** → **Custom server build** → **Run workflow** (или просто пуш в ветку `custom-server`).
3. Через ~40–70 минут скачай артефакт `PlumeGram-Desktop-win64` → внутри `Telegram.exe`.

Сборка статическая: Qt и OpenSSL внутри, один exe, ничего доустанавливать не нужно.

### Локальная сборка (если появится VS)

Нужны Visual Studio 2026 с workload «Desktop development with C++», Windows SDK
`10.0.26100.0`, Python 3.10+, Git, ~12 ГБ диска и права администратора для установки VS.

```
powershell -ExecutionPolicy Bypass -File custom-server\build-local.ps1
```

Скрипт сам подтянет Qt официальным `prepare/win.bat`, сконфигурирует Release
и соберёт `out\Release\Telegram.exe`.

### Грабли: `skip-release` и конфигурация

Официальный CI телеграмовцев собирает **Debug** и поэтому вызывает
`prepare\win.bat skip-release silent` — флаг выкидывает все Release-команды из
скриптов сборки библиотек. Если потом собрать приложение в Release, линковка
падает:

```
LNK1181: cannot open input file '...\Libraries\win64\openssl3\out\libssl.lib'
LNK1181: cannot open input file '...\Libraries\win64\tg_angle\out\Release\tg_angle.lib'
LNK2038: mismatch detected for 'RuntimeLibrary': 'MT_StaticRelease' doesn't match 'MTd_StaticDebug'
```

Поэтому в `custom-windows.yml` `skip-release` **не передаётся**: собираются оба
набора библиотек. Холодный прогон занимает ~2.5 часа (Debug-набор ~90 мин +
Release-набор ~70 мин), плюс ~40 мин на само приложение. Кэш `Libraries`
сохраняется сразу после сборки библиотек, чтобы падение на линковке не
обнуляло прогресс.

## Сменить IP / порт / ключ

Всё в одном месте — `Telegram/SourceFiles/mtproto/mtproto_dc_options.cpp`:

```cpp
constexpr auto kCustomServerIp = "84.21.173.237";
constexpr auto kCustomServerPort = 20443;
constexpr bool kLockDcOptions = false;   // true = игнорировать DC из help.getConfig
```

После правки — пересобрать. Проверить консистентность патча:

```
python custom-server\tools\verify_patch.py --source E:\tdesktop --key E:\keys\server_rsa.key --ip 84.21.173.237 --port 20443
```

Без пересборки можно поменять только адреса — файлом `.tdesktop-endpoints` рядом с exe
(пример: `custom-server/tdesktop-endpoints.example`). Ключ всё равно живёт в бинарнике.

## Что должен уметь сервер

Клиент — обычный MTProto-клиент, поэтому сервер обязан поддерживать:

- транспорт: **abridged** (`0xef`), **intermediate** (`0xeeeeeeee`) или **padded intermediate** (`0xdddddddd`)
  по «голому» TCP, без TLS впереди;
- `req_pq_multi` → `resPQ` с одним из отпечатков выше;
- DH-обмен (`req_DH_params` / `set_client_DH_params`) и `auth_key`;
- `help.getConfig`, `help.getNearestDc`, `updates.getState`, `auth.*`, `messages.*` и т.д.;
- `api_id`/`api_hash`, с которыми собран клиент: `2040` / `b18441a1ff607e10a989891a5462e627`
  (меняются через `-D TDESKTOP_API_ID` / `-D TDESKTOP_API_HASH` в `configure.bat`).

## Результат проверки сервера (02.11.2026)

```
открытые порты:            22, 80, 443, 20443
443   -> настоящий TLS 1.3, веб-клиент «PlumeGram Wallet», /health -> {"ok": true}
20443 -> TCP-соединение принимается, но:
         abridged / intermediate / full / padded intermediate + req_pq_multi -> ответа нет
         obfuscated2 (0xdd/0xee) -> сервер сразу закрывает соединение
         TLS ClientHello -> EOF
```

То есть порт 20443 слушает, но **на стандартные транспорты tdesktop не отвечает**.
Возможные причины и что делать:

1. **Сервер ждёт fake-TLS (MTProxy-стиль, secret `ee…`)** — тогда нужен секрет,
   и в клиенте придётся дописать этот транспорт (или ходить через MTProxy-клиент).
2. **Сервер ждёт obfuscated2 с секретом `dd…`** — то же самое, нужен секрет.
3. **Фильтрация по IP** — сервер может пускать только «свои» адреса; проверь с той
   машины, где точно работает официальный клиент/их веб-клиент.
4. **20443 — это не MTProto, а что-то другое** (панель, прокси, заглушка).

Диагностика (запускать там, где сервер точно доступен):

```
python custom-server\tools\probe_mtproto.py --host 84.21.173.237 --ports 20443 --keys E:\keys
python custom-server\tools\probe_mtproto.py --host 84.21.173.237 --ports 1-65535 --scan
```

Если сервер ответит `resPQ`, скрипт напечатает отпечатки ключей — сразу видно,
актуальный ли ключ вшит в клиент.

## Ограничения

- Автообновление и краш-репорты отключены при сборке
  (`DESKTOP_APP_DISABLE_AUTOUPDATE=ON`, `DESKTOP_APP_DISABLE_CRASH_REPORTS=ON`).
- Патч не меняет протокол: клиент говорит ровно тот MTProto, который отдаёт сервер.
- Если сервер проверяет `api_id` строго — поменяй define'ы при конфигурации.
