import logging
import sys
import textwrap

from environs import Env
import redis
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Filters, Updater
from telegram.ext import CallbackQueryHandler, CommandHandler, MessageHandler

from strapi import clear_cart, get_items, create_order, get_cart_items, get_item_image, add_item_to_cart

logger = logging.getLogger('Telegram logger')


def start(update, context):
    update.message.reply_text('Please choose:', reply_markup=get_main_menu_kb(context))
    return "HANDLE_DESCRIPTION"


def waiting_email(update, context):
    query = update.callback_query
    query.answer()
    context.bot.send_message(
        chat_id=query.message.chat_id,
        text='Введите ваш email:')
    context.bot.delete_message(chat_id=query.message.chat_id, message_id=query.message.message_id)
    return 'HANDLE_CART'


def handle_menu(update, context):
    query = update.callback_query
    url = context.bot_data.get('url')
    query.answer()
    if query.data == 'show_cart':
        return handle_cart(update, context)
    elif query.data == 'clear_cart':
        clear_cart(update, context, url)
    elif query.data == 'pay_order':
        return waiting_email(update, context)
    if query.data.startswith('add_item'):
        item_id = query.data.split('.')[-1]
        api_key = context.bot_data.get('strapi')
        add_item_to_cart(item_id, api_key, url, query)

    context.bot.send_message(
        chat_id=query.message.chat_id,
        reply_markup=get_main_menu_kb(context),
        text='Please choose:')

    context.bot.delete_message(chat_id=query.message.chat_id, message_id=query.message.message_id)
    return "HANDLE_DESCRIPTION"


def handle_cart(update, context):
    api_key = context.bot_data.get('strapi')
    url = context.bot_data.get('url')

    headers = {
        'Authorization': f'bearer {api_key}',
    }
    if update.message:
        client_email = update.message.text
        user_telegram_id = update.message.chat_id
        create_order(user_telegram_id, client_email, headers, url)
        context.bot.send_message(
            chat_id=update.message.chat_id,
            text='Вас заказ успешно оформлен')
        return 'HANDLE_MENU'

    query = update.callback_query
    query.answer()

    user_id = update.callback_query.message.chat_id
    cart = get_cart_items(user_id, headers, url)

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

    context.bot.delete_message(chat_id=query.message.chat_id, message_id=query.message.message_id)

    return 'HANDLE_MENU'


def get_main_menu_kb(context):
    api_key = context.bot_data.get('strapi')
    url = context.bot_data.get('url')
    products = get_items(api_key, url)
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


def handle_description(update, context):
    query = update.callback_query
    query.answer()
    if query.data == 'show_cart':
        return handle_cart(update, context)

    elif query.data == 'pay_order':
        return 'WAITING_EMAIL'

    url = context.bot_data.get('url')
    api_key = context.bot_data.get('strapi')
    products = get_items(api_key, url)
    product = products.get('data')[int(query.data) - 1]
    product_details = product.get('attributes')

    image = get_item_image(product_details, url)
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
    context.bot.delete_message(chat_id=query.message.chat_id, message_id=query.message.message_id)

    return "HANDLE_MENU"


def handle_error(update, context):
    exception = context.error
    logger.exception(f'Бот завершил работу с ошибкой: {exception}', exc_info=True)


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


def main():
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
        dispatcher.bot_data['url'] = url
        logging.basicConfig(
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
        )
        logger.setLevel(logging.INFO)
        logger.info('Strapi-shop bot запущен')

        dispatcher.add_handler(CallbackQueryHandler(handle_users_reply))
        dispatcher.add_handler(MessageHandler(Filters.text, handle_users_reply))
        dispatcher.add_handler(CommandHandler('start', handle_users_reply))
        dispatcher.add_error_handler(handle_error)

        dispatcher.bot_data['redis'] = redis_db
        dispatcher.bot_data['strapi'] = strapi_api_key
        updater.start_polling()
    except Exception:
        handle_error(*sys.exc_info())


if __name__ == '__main__':
    main()
