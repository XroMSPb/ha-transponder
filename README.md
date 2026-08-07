# ЗСД / Автодор Транспондер для Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![GitHub Release](https://img.shields.io/github/release/yourname/ha-transponder.svg)](https://github.com/yourname/ha-transponder/releases)
[![License](https://img.shields.io/github/license/yourname/ha-transponder.svg)](LICENSE)
[![Project Maintenance](https://img.shields.io/badge/maintained-yes-green.svg)](https://github.com/yourname/ha-transponder)

Пользовательская интеграция для Home Assistant, которая показывает баланс личного
кабинета транспондеров платных дорог в виде сенсоров.

**Реализовано:**

- 🟢 **ЗСД — Магистраль Северной Столицы** (`cabinet.nch-spb.com`, платформа Onyma xRM)

**В планах:**

- ⚪ **Автодор** (следующий этап)

---

## Возможности

- Отдельный сенсор баланса на каждый договор (`device_class: monetary`, валюта `RUB`).
- Атрибуты: номер договора, статус, время актуальности данных.
- Настройка через UI (config flow), без правки `configuration.yaml`.
- Повторная авторизация (reauth) при смене пароля или истечении сессии.
- Настраиваемый интервал опроса (по умолчанию 30 мин, минимум 5).
- Русский и английский интерфейс.

---

## Как это работает

У кабинета ЗСД нет публичного API, поэтому интеграция повторяет действия браузера:

1. `POST /onyma/` с логином и паролем → cookie сессии.
2. `POST /onyma/system/literpc/` с вызовом RPC-пакета `toll-balance-refresher` →
   JSON с HTML-фрагментом, содержащим актуальный баланс по всем договорам.

Из ответа извлекаются баланс, номер договора (`Договор`), статус (`Статус`) и
время обновления. `iot_class: cloud_polling` — данные опрашиваются периодически.
Пожалуйста, не ставьте слишком короткий интервал: запросы идут на реальный сервер
личного кабинета.

---

## Установка

### Через HACS (рекомендуется)

1. HACS → ⋮ (меню) → **Пользовательские репозитории** (Custom repositories).
2. Добавьте URL этого репозитория, категория — **Integration**.
3. Установите **ЗСД Транспондер** и перезапустите Home Assistant.

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=yourname&repository=ha-transponder&category=integration)

### Вручную

Скопируйте папку `custom_components/zsd_transponder/` в каталог
`config/custom_components/` вашего Home Assistant и перезапустите его.

---

## Настройка

**Настройки → Устройства и службы → Добавить интеграцию → «ЗСД Транспондер».**

Введите логин и пароль от [cabinet.nch-spb.com](https://cabinet.nch-spb.com).
Учётные данные хранятся в записи конфигурации Home Assistant и отправляются
только на сервер кабинета ЗСД.

Интервал опроса можно изменить позже через кнопку **Настроить** (Options) у
интеграции.

### Сущность

Один сенсор на каждый договор, например `sensor.zsd_1234567_kt001_balans`:

| Параметр      | Пример          |
|---------------|-----------------|
| Состояние     | `716.25` (RUB)  |
| `contract`    | `1234567-KT001` |
| `status`      | `Активен`       |
| `updated_at`  | `10:05:55`      |

---

## Карточка на панель (Lovelace)

См. [`lovelace/zsd_card.yaml`](lovelace/zsd_card.yaml). Замените
`sensor.zsd_balance` на реальный `entity_id`. Карточка показывает договор, статус
и крупный баланс — в стиле личного кабинета.

---

## Проверка перед установкой

Можно убедиться, что логин и парсер работают, не заходя в Home Assistant:

```bash
pip install aiohttp
python tools/test_login.py --username ВАШ_ЛОГИН
```

Скрипт запросит пароль (ничего не сохраняется) и выведет разобранный баланс.
Используется тот же код, что и в интеграции.

---

## Устранение неполадок

- **`invalid_auth`** — проверьте логин/пароль на сайте кабинета вручную.
- **`cannot_connect`** — сайт недоступен или изменил ответ; повторите позже.
- Данные не обновляются — увеличьте интервал опроса; возможна временная
  блокировка частых запросов на стороне сервера.

---

## Отказ от ответственности

Неофициальная интеграция. Не связана с ЗСД / Магистраль Северной Столицы / Onyma
и Автодор. Сам кабинет указывает, что данные о балансе носят справочный характер.
Используйте на свой риск: разметка или процесс входа на сайте могут измениться и
сломать парсинг.

---

## Лицензия

[MIT](LICENSE)
