from io import BytesIO
import logging
import textwrap
from urllib.parse import urljoin

from environs import Env
import redis
import requests
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Filters, Updater
from telegram.ext import CallbackQueryHandler, CommandHandler, MessageHandler


logger = logging.getLogger('Telegram logger')


def start(update, context):
    api_key = context.bot_data.get('strapi')
    api_url = urljoin(url, 'api/products')
    headers = {
        'Authorization': f'bearer {api_key}'
    }

    payload = {
        'populate': '*'
    }

    response = requests.get(api_url, headers=headers, params=payload)
    response.raise_for_status()
    products = response.json()
    dispatcher.bot_data['products'] = products

    update.message.reply_text('Please choose:', reply_markup=get_main_menu_kb(context))
    return "HANDLE_DESCRIPTION"


def clear_cart(update, context):
    query = update.callback_query
    query.answer()
    user_id = update.callback_query.message.chat_id
    api_key = context.bot_data.get('strapi')

    headers = {
        'Authorization': f'bearer {api_key}',
    }

    payload = {
        'user_telegram_id': user_id,
        'populate[0]': 'cart_items'
    }

    response = requests.get(urljoin(url, 'api/carts'), headers=headers, params=payload)
    response.raise_for_status()
    cart = response.json()
    if cart['data']:
        cart_id = cart['data'][0]['id']
        response_cart = requests.delete(urljoin(url, f'api/carts/{cart_id}'), headers=headers)
        response_cart.raise_for_status()
        cart_items = cart['data'][0]['attributes']['cart_items']['data']
        for cart_item in cart_items:
            cart_item_id = cart_item['id']
            response_cart_id = requests.delete(urljoin(url, f'api/cart-items/{cart_item_id}'), headers=headers)
            response_cart_id.raise_for_status()


def waiting_email(update, context):
    query = update.callback_query
    query.answer()
    context.bot.send_message(
        chat_id=query.message.chat_id,
        text='Введите ваш email:')
    context.bot.deleteMessage(chat_id=query.message.chat_id, message_id=query.message.message_id)
    return 'HANDLE_CART'


def handle_menu(update, context):
    query = update.callback_query
    query.answer()
    if query.data == 'show_cart':
        return handle_cart(update, context)
    elif query.data == 'clear_cart':
        clear_cart(update, context)
    elif query.data == 'pay_order':
        return waiting_email(update, context)
    if query.data.startswith('add_item'):
        item_id = query.data.split('.')[-1]
        api_key = context.bot_data.get('strapi')
        headers = {
            'Authorization': f'bearer {api_key}',
        }

        cart_response = requests.get(urljoin(url, 'api/carts'), headers=headers)

        cart_response.raise_for_status()
        cart = cart_response.json()
        if cart['data']:
            cart_id = cart['data'][0].get('id')
            add_item_to_cart(item_id, cart_id, api_key)

        else:
            payload = {
                'data': {
                    'user_telegram_id': query.message.chat.id
                }
            }
            response = requests.post(urljoin(url, 'api/carts'), headers=headers, json=payload)
            response.raise_for_status()
            cart_id = response.json()['data']['id']
            add_item_to_cart(item_id, cart_id, api_key)

    context.bot.send_message(
        chat_id=query.message.chat_id,
        reply_markup=get_main_menu_kb(context),
        text='Please choose:')

    context.bot.deleteMessage(chat_id=query.message.chat_id, message_id=query.message.message_id)
    return "HANDLE_DESCRIPTION"


def handle_cart(update, context):
    api_key = context.bot_data.get('strapi')
    headers = {
        'Authorization': f'bearer {api_key}',
    }

    if update.message:
        cart_response = requests.get(urljoin(url, 'api/carts'),
                                     headers=headers,
                                     params={'user_telegram_id': update.message.chat_id})
        cart_response.raise_for_status()
        cart = cart_response.json()['data'][0]['id']
        payload = {
            'data': {
                'client_email': update.message.text,
                'cart': cart
            }
        }
        order_response = requests.post(urljoin(url, 'api/orders'), headers=headers, json=payload)
        order_response.raise_for_status()
        context.bot.send_message(
            chat_id=update.message.chat_id,
            text='Вас заказ успешно оформлен')
        return 'HANDLE_MENU'

    query = update.callback_query
    query.answer()

    user_id = update.callback_query.message.chat_id

    payload = {
        'user_telegram_id': user_id,
        'populate[0]': 'cart_items.product'
    }

    response = requests.get(urljoin(url, 'api/carts'), headers=headers, params=payload)
    response.raise_for_status()
    cart = response.json()
    total_price = 0
    message = ''
    keyboard = [
        [InlineKeyboardButton('В меню', callback_data='back')]

    ]

    if cart['data']:
        cart_items = cart['data'][0]['attributes']['cart_items']['data']
        for cart_item in cart_items:
            count = cart_item['attributes']['weight']
            product = cart_item['attributes']['product']['data']['attributes']['title']
            price = cart_item['attributes']['product']['data']['attributes']['price']
            message += f'Наименование - {product} - {count} кг, \n'
            total_price += count * price
        message += f'Итоговая стоимость: {total_price} руб'
        keyboard.append([InlineKeyboardButton('Оплатить позиции', callback_data='pay_order')])
        keyboard.append([InlineKeyboardButton('Удалить позиции', callback_data='clear_cart')])
    else:
        message += 'У вас отсутствуют товары в корзине'

    reply_markup = InlineKeyboardMarkup(keyboard)

    context.bot.send_message(
        chat_id=query.message.chat_id,
        reply_markup=reply_markup,
        text=message)

    context.bot.deleteMessage(chat_id=query.message.chat_id, message_id=query.message.message_id)

    return 'HANDLE_MENU'


def get_main_menu_kb(context):
    products = context.bot_data.get('products')
    keyboard = [
        [InlineKeyboardButton(
            product.get('attributes')['title'],
            callback_data=product.get('id'))]
        for product in products.get('data')
    ]
    keyboard.append(
        [InlineKeyboardButton('Корзина', callback_data='show_cart')]
    )
    reply_markup = InlineKeyboardMarkup(keyboard)
    return reply_markup


def get_item(item_id, cart_id, api_key):

    headers = {
        'Authorization': f'bearer {api_key}',
    }

    payload = {
        'populate[0]': 'cart_items.product'
    }

    response = requests.get(urljoin(url, f'api/carts/{cart_id}'), headers=headers, params=payload)
    response.raise_for_status()
    cart_items = response.json()['data']['attributes']['cart_items']['data']
    for item in cart_items:
        if item['attributes']['product']['data']['id'] == int(item_id):
            return {'item_id': item['id'], 'item_weight': item['attributes']['weight']}
    return


def add_item_to_cart(item_id, cart_id, api_key):
    item = get_item(item_id, cart_id, api_key)
    headers = {
        'Authorization': f'bearer {api_key}',
    }
    if item:
        payload = {
            'data': {
                'weight': item['item_weight'] + 1
            }
        }
        response = requests.put(urljoin(url, f'api/cart-items/{item["item_id"]}'),
                                headers=headers,
                                json=payload)
        response.raise_for_status()
    else:
        payload = {
            'data': {
                'product': item_id,
                'cart': cart_id,
                'weight': 1
            }
        }
        response = requests.post(urljoin(url, 'api/cart-items/'), headers=headers, json=payload)
        response.raise_for_status()


def handle_description(update, context):
    query = update.callback_query
    query.answer()
    if query.data == 'show_cart':
        return handle_cart(update, context)

    elif query.data == 'pay_order':
        return 'WAITING_EMAIL'

    products = context.bot_data.get('products')
    product = products.get('data')[int(query.data) - 1]
    product_details = product.get('attributes')

    image_url = urljoin(
        url,
        product_details.get('picture')['data']['attributes']['formats']['small']['url']
    )
    response = requests.get(image_url)
    image = BytesIO(response.content)
    keyboard = [
        [InlineKeyboardButton('Добавить в корзину', callback_data=f'add_item.{product["id"]}')],
        [InlineKeyboardButton('Корзина', callback_data='show_cart')],
        [InlineKeyboardButton('Назад', callback_data='back')]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    message = textwrap.dedent(f'''
       {product_details.get('title')} {product_details.get('price')} руб. 

       {product_details.get('description')}
       ''')

    context.bot.send_photo(chat_id=query.message.chat_id, photo=image, caption=message, reply_markup=reply_markup)
    context.bot.deleteMessage(chat_id=query.message.chat_id, message_id=query.message.message_id)

    return "HANDLE_MENU"


def handle_error(exception):
    logger.exception(f'Бот завершил работу с ошибкой: {exception}', exc_info=True)


def error_handler(update, context):
    handle_error(context.error)


def handle_users_reply(update, context):
    db = context.bot_data.get('redis')
    if update.message:
        user_reply = update.message.text
        chat_id = update.message.chat_id
    elif update.callback_query:
        user_reply = update.callback_query.data
        chat_id = update.callback_query.message.chat_id
    else:
        return
    if user_reply == '/start':
        user_state = 'START'
    else:
        user_state = db.get(chat_id).decode("utf-8")

    states_functions = {
        'START': start,
        'HANDLE_MENU': handle_menu,
        'HANDLE_DESCRIPTION': handle_description,
        'HANDLE_CART': handle_cart,
        'WAITING_EMAIL': waiting_email
    }
    state_handler = states_functions[user_state]
    next_state = state_handler(update, context)
    db.set(chat_id, next_state)


if __name__ == '__main__':
    try:
        env = Env()
        env.read_env()
        token = env.str("TELEGRAM_TOKEN")
        redis_password = env.str("REDIS_DATABASE_PASSWORD")
        redis_host = env.str("REDIS_DATABASE_HOST")
        redis_port = env.str("REDIS_DATABASE_PORT")
        strapi_api_key = env.str("STRAPI_API_KEY")
        url = env.str("STRAPI_URL", 'http://localhost:1337')

        redis_db = redis.Redis(
            host=redis_host,
            port=redis_port,
            password=redis_password)

        updater = Updater(token)
        dispatcher = updater.dispatcher

        logging.basicConfig(
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
        )
        logger.setLevel(logging.INFO)
        logger.info('Strapi-shop bot запущен')

        dispatcher.add_handler(CallbackQueryHandler(handle_users_reply))
        dispatcher.add_handler(MessageHandler(Filters.text, handle_users_reply))
        dispatcher.add_handler(CommandHandler('start', handle_users_reply))
        dispatcher.add_error_handler(error_handler)

        dispatcher.bot_data['redis'] = redis_db
        dispatcher.bot_data['strapi'] = strapi_api_key
        updater.start_polling()
    except Exception as e:
        handle_error(e)
