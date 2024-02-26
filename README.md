# Strapi shop bot

Телеграм бот - магазин с работой через [Strapi](https://strapi.io/).

## Установка бота

Python 3.10 должен быть уже установлен. Далее используйте `pip`(or `pip3`, если имеется конфликт с Python2) 
для установки зависомостей:

```commandline
git clone https://github.com/Weffy61/strapi_bot.git
```

## Установка зависимостей
Переход в директорию с исполняемым файлом

```commandline
cd strapi_bot
```

Установка
```commandline
pip install -r requirements.txt
```

## Установка Strapi

Установите [Strapi](https://github.com/strapi/strapi), создайте проект. Также убедитесь, что у вас установлен 
[NodeJS](https://nodejs.org/en).

## Запуск Strapi

Запустите проект командой:
```shell
npm run start
```
Проект будет запущен с выключенной автоперезагрузкой.

Либо:

```shell
npm run develop
```

Автоперезагрузка будет включена.

## Предварительная Подготовка

### Подготовка Strapi

Зайдите в админ панель Strapi и создайте следующие модели:

- Product:
    - title(Text)
    - description(Text)
    - picture(Media)
    - price(Number)

- Cart:
    - users_permissions_users(Relation with User (from: users-permissions))
    - user_telegram_id(Number)

- CartItem:
    - product(Relation with Product)
    - cart(Relation with Cart)
    - weight(Number)

- Order:
    - client_email(Email)
    - cart(Relation with Cart)

Создайте Api Token в админ-панели Strapi.

### Подготовка телеграм

Создайте бота в [botfather](https://t.me/BotFather).


### Подготовка Redis

[Установите](https://timeweb.cloud/tutorials/redis/ustanovka-i-nastrojka-redis-dlya-raznyh-os) Redis, 
либо воспользуйтесь [облачным сервисом](https://redis.com). Получите адрес, порт и пароль.

## Создание и настройка .env

Создайте в корне папки `strapi_bot` файл `.env`. Откройте его для редактирования любым текстовым редактором
и запишите туда данные в таком формате: `ПЕРЕМЕННАЯ=значение`.
Доступны следующие переменные:
 - TELEGRAM_TOKEN - ваш телеграм бот API ключ.
 - REDIS_DATABASE_HOST - ваш Redis адрес
 - REDIS_DATABASE_PORT - ваш Redis порт
 - REDIS_DATABASE_PASSWORD - ваш Redis пароль
 - STRAPI_URL - url адрес Strapi. По умолчанию используется `http://localhost:1337`

## Запуск телеграм бота

```shell
python3 bot.py
```