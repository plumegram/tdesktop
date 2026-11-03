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

### Грабли: breakpad, ATL и VS 18

В Release-части стейджа `breakpad` `prepare` собирает тул `dump_syms`, а он
тянет ATL-заголовки. На `windows-latest` стоит **Visual Studio 18 Enterprise**
(`C:\Program Files\Microsoft Visual Studio\18\Enterprise`), где ATL живёт в
`VC\Tools\MSVC\14.44.35207\atlmfc`, а сгенерированный `dump_syms.vcxproj`
жёстко прописывает старый путь:

```
/I"C:\Program Files\Microsoft Visual Studio\18\Enterprise\\VC\atlmfc\include"
```

Такого каталога нет — отсюда падение всего `prepare`:

```
pdb_source_line_writer.h(36,10): error C1083: Cannot open include file: 'atlcomcli.h'
dia_util.cc(31,10): error C1083: Cannot open include file: 'atlbase.h'
[27/36](Libraries/breakpad): FAILED
```

Установка компонента `Microsoft.VisualStudio.Component.VC.ATL` через
`vs_installer` **не помогает**: ATL встаёт в `VC\Tools\MSVC\<ver>\atlmfc`, а
`vcxproj` смотрит в `VC\atlmfc` (и оттуда же ждёт `atls.lib` на линковке).

Поэтому `dump_syms` в этой сборке просто не собирается: в форке из стейджа
`breakpad` (`Telegram/build/prepare/prepare.py`) убраны три строки —

```
    cd tools\windows\dump_syms
    gyp dump_syms.gyp --format=msvs
    msbuild -m dump_syms.vcxproj /property:Configuration=Release /property:Platform="x64"
```

`dump_syms` нужен только для генерации `.sym`-файлов к крэш-репортам, а они
здесь выключены (`-D DESKTOP_APP_DISABLE_CRASH_REPORTS=ON`). Сам breakpad
(`common`, `crash_generation_client`, `exception_handler`) собирается как обычно.

Если `.sym` когда-нибудь понадобятся — проще всего подложить junction
`VC\atlmfc` → `VC\Tools\MSVC\<ver>\atlmfc` и вернуть эти строки.

### Грабли: инсталл Qt нельзя чистить

`prepare` собирает Qt в `Libraries\win64\qt_6.11.2` (нижний регистр, с
подчёркиванием), а ставит в `Libraries\win64\Qt-6.11.2`.

Пробовали перевести стейдж на `-release` вместо `-debug-and-release`, чтобы
сэкономить ~40 минут и пару гигабайт кэша. Так нельзя: Qt, собранный без
debug-конфигурации, экспортирует `rcc`/`moc`/`qsb` без адреса для Release, и
`configure` падает ещё до компиляции:

```
CMake Error in CMakeLists.txt:
  IMPORTED_LOCATION not set for imported target "Qt6::rcc" configuration "Release".
CMake Error: AUTORCC for target external_microtex_bundled:
  The "rcc" executable "Qt6::rcc-NOTFOUND" does not exist.
```

Поэтому стейдж оставлен как в апстриме: `-debug-and-release`, сборка и установка
Debug, затем Release.

Второе, и важное: **из `Qt-6.11.2` нельзя удалять ничего**. `Qt6*Targets.cmake`
ссылается на каждый установленный `.obj` по пути, и `configure` падает ещё до
компиляции:

```
CMake Error at .../Qt6Gui/Qt6GuiTargets.cmake:144 (message):
  The imported target "Qt6::Gui_resources_1" references the file
  ".../lib/objects-Debug/Gui_resources_1/.qt/rcc/qrc_qpdf_init.cpp.obj"
  but this file does not exist.
```

На этом легко поймать себя, если добавить в CI шаг «почистить `*.obj` перед
сохранением кэша» — именно так и вышло. Сейчас шаг удаляет только
`Libraries\win64\qt_*` (сборочное дерево) и `*.pdb`/`*.ilk`, а инсталл Qt не
трогает.

### Грабли: файл подкачки раннера — это потолок всей сборки

У `windows-latest` маленький файл подкачки фиксированного размера, поэтому у
джоба есть жёсткий лимит зафиксированной памяти (commit limit). Когда он
выбирается, компилятор и линковщик падают «на ровном месте», хотя RAM ещё есть:

```
error C3859: Failed to create virtual memory for PCH
    the system returned code 1455: The paging file is too small for this operation to complete.
error C1060: compiler is out of heap space
LINK : fatal error LNK1102: out of memory
```

Симптом характерный: **сотни файлов падают в одну и ту же секунду**, и все
файлы после них тоже. Это не ошибка в коде и не «мало оперативки под
компилятор» — это лимит commit'а.

Что сделано:

- сборка идёт с `--parallel 2` (а не по умолчанию — по узлу на ядро): каждый
  `cl.exe` держит в памяти копию огромного PCH проекта `Telegram`, четыре штуки
  не влезают;
- при падении автоматически повторяется с `--parallel 1` — объектники остаются
  на месте, поэтому ретрай компилирует только упавшие файлы (~25 минут вместо
  двух часов);
- `CMAKE_MSVC_DEBUG_INFORMATION_FORMAT=` — без `/Zi` и `/DEBUG`, то есть без
  многогигабайтного `Telegram.pdb`. Именно его генерация добивала `link.exe`
  (`LNK1102`), а краш-репорты здесь всё равно выключены;
- `TMP`/`TEMP` перенесены на `D:` — на `C:` живёт файл подкачки, и мусор рядом
  с ним мешает Windows его увеличивать.

В лог печатается шаг «Report memory and free space» — размер pagefile, свободное
место и commit limit, чтобы следующее падение сразу читалось с числами.

Если Qt всё же почистили — удалить `Libraries\win64\cache_keys\qt_6.11.2`:
prepare сам снесёт и `qt_6.11.2`, и `Qt-6.11.2` (у каждого стейджа перед запуском
выполняется `removeDir(stage_name)`, а в начале win-блока — `removeDir(Qt-...)`),
и пересоберёт стейдж с нуля.

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
