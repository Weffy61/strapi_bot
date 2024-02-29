from io import BytesIO
from urllib.parse import urljoin

import requests


def get_cart(api_key, query, url):
    headers = {
        'Authorization': f'bearer {api_key}',
    }

    cart_response = requests.get(urljoin(url, 'api/carts'), headers=headers)

    cart_response.raise_for_status()
    cart = cart_response.json()
    if cart['data']:
        cart_id = cart['data'][0].get('id')

    else:
        payload = {
            'data': {
                'user_telegram_id': query.message.chat.id
            }
        }
        response = requests.post(urljoin(url, 'api/carts'), headers=headers, json=payload)
        response.raise_for_status()
        cart_id = response.json()['data']['id']F
    return cart_id


def add_item_to_cart(item_id, api_key, url, query):
    cart_id = get_cart(api_key, query, url)
    item = get_item(item_id, cart_id, api_key, url)
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


def clear_cart(update, context, url):
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



def get_item(item_id, cart_id, api_key, url):

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


def get_items(api_key, url):
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
    return products


def create_order(user_telegram_id, client_email, headers, url):
    cart_response = requests.get(urljoin(url, 'api/carts'),
                                 headers=headers,
                                 params={'user_telegram_id': user_telegram_id})
    cart_response.raise_for_status()
    cart = cart_response.json()['data'][0]['id']
    payload = {
        'data': {
            'client_email': client_email,
            'cart': cart
        }
    }
    order_response = requests.post(urljoin(url, 'api/orders'), headers=headers, json=payload)
    order_response.raise_for_status()


def get_cart_items(user_id, headers, url):
    payload = {
        'user_telegram_id': user_id,
        'populate[0]': 'cart_items.product'
    }

    response = requests.get(urljoin(url, 'api/carts'), headers=headers, params=payload)
    response.raise_for_status()
    cart = response.json()
    return cart


def get_item_image(product_details, url):
    image_url = urljoin(
        url,
        product_details.get('picture')['data']['attributes']['formats']['small']['url']
    )
    response = requests.get(image_url)
    image = BytesIO(response.content)
    return image
