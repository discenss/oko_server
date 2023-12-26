import telebot
from telebot import types
from datetime import datetime
from oko_db.db import DB
from telebot.types import LabeledPrice, ShippingOption
import time


def read_bot_keys(file_path):
    with open(file_path, 'r') as file:
        first_line = file.readline().rstrip()
        second_line = file.readline().rstrip()

    return first_line, second_line

# Пример использования функции
file_path = 'file.txt'  # Укажите путь к вашему файлу
bot_id, payment_token = read_bot_keys(file_path)
bot = telebot.TeleBot(bot_id)

report_for_date = 'Введіть дату у форматі РРРР-ММ-ДД (Наприклад 1991-08-24)'
report_for_date_or_exit = "Ведіть дату у форматі РРРР-ММ-ДД (Наприклад 1991-08-24) или /menu для виходу"
est_name_and_password_for_subsc = "Введіть назву_закладу та пароль через пробіл. Наприклад:\n MyBar MyPassword"
top_up_account = "Введіть суму поповнення"

def send_bot_message(message, tg_id):
    bot.send_message(tg_id, message)

@bot.pre_checkout_query_handler(func=lambda query: True)
def process_pre_checkout(query):
    bot.answer_pre_checkout_query(pre_checkout_query_id=query.id, ok=True)

@bot.message_handler(content_types=['successful_payment'])
def handle_successful_payment(message):
    db = DB()
    db.addmomey_for_tg_user(message.from_user.id, message.successful_payment.total_amount / 100)
    bot.reply_to(message, "Ви успішно поповнили рахунок. Баланс %s" % db.get_money_for_tg_user(message.from_user.id))
    show_main_menu(message)

def show_main_menu(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)  # создание новых кнопок
    btn1 = types.KeyboardButton('Профіль')
    btn2 = types.KeyboardButton('Отримати звіт за дату')
    btn3 = types.KeyboardButton('Підписатись на щоденний звіт')
    btn4 = types.KeyboardButton('Написати до сервісу')
    btn5 = types.KeyboardButton('Поповнити рахунок')

    markup.add(btn1, btn2, btn3, btn4, btn5)
    bot.send_message(message.from_user.id, 'Оберіть потрібну дію', reply_markup=markup)

@bot.message_handler(commands=['start'])
def start(message):

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn1 = types.KeyboardButton("👋 Почати")
    markup.add(btn1)
    bot.send_message(message.from_user.id, "👋 Привіт! Я твій бот для роботы с відео спостереженням. \n"
                                           "/start - почати с початку\n"
                                           "Якщо ви тільки розпочали роботу с ботом то Вам необхідно мати 'Назву закладу' та 'Пароль'. Цю інформацію може отримати у власника закладу.\n "
                                           "Наступний крок - підписатися не щоденний звіт\n"
                                           "/menu - показати меню ", reply_markup=markup)

@bot.message_handler(commands=['menu'])
def start(message):

    show_main_menu(message)

@bot.message_handler(func=lambda message: message.reply_to_message is not None and
                                          (message.reply_to_message.text == report_for_date or
                                            message.reply_to_message.text ==  report_for_date_or_exit))

@bot.message_handler(func=lambda message: message.reply_to_message is not None and
                                          message.reply_to_message.text == est_name_and_password_for_subsc)

@bot.message_handler(func=lambda message: message.reply_to_message is not None and
                                          message.reply_to_message.text == top_up_account)

def handle_reply(message):
    if message.reply_to_message.text == report_for_date or message.reply_to_message.text == report_for_date_or_exit:
        try:
            date = datetime.strptime(message.text, '%Y-%m-%d')
            bot.reply_to(message, f'Ви ввели вірний формат дати: {date}')
            bot.reply_to(message, f'Йде перевірка')
            bot.reply_to(message, f'Вы получите отчёт как только база данных будет готова')
            show_main_menu(message)

        except ValueError:
            bot.reply_to(message, 'Невірний формат дати.')
            markup = types.ForceReply(selective=False)
            bot.send_message(message.from_user.id, report_for_date_or_exit, reply_markup=markup)

    elif message.reply_to_message.text == est_name_and_password_for_subsc:
        if(len(message.text.split(' ')) ==2):
            name, passw = message.text.split(' ')
            bot.reply_to(message, f'Ви ввели назву закладу: {name}\nПароль: {passw}')
            db = DB()
            res = db.subscribe_user_to_est(message.from_user.id, name, passw)
            if (res == 'success'):
                markup = types.ForceReply(selective=False)
                bot.send_message(message.from_user.id, f'Ви успішно підписані на регулярний звіт. Очікуйте наступного звіту', reply_markup=markup)
            else:
                markup = types.ForceReply(selective=False)
                bot.send_message(message.from_user.id, res, reply_markup=markup)

            show_main_menu(message)
        else:
            bot.reply_to(message, f'Ви не ввели назву_закладу і пароль')
            show_main_menu(message)
    elif message.reply_to_message.text == top_up_account:
        try:
            val = int(message.text)
            prices = [LabeledPrice(label='Product', amount=val * 100)]
            bot.send_invoice(
                chat_id=message.chat.id,
                title="OKO AI",
                description="Відео спостереження для вашого бізнесу",
                provider_token=payment_token,  # Get this from your payment provider setup
                currency="UAH",
                is_flexible=False,  # True If you want to send a flexible invoice
                prices=prices,
                start_parameter="start_param",
                invoice_payload="payload"
            )
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True)  # создание новых кнопок
            btn1 = types.KeyboardButton('Назад в меню')

            markup.add(btn1)
            bot.send_message(message.from_user.id, 'Або повернутися', reply_markup=markup)
        except ValueError:
            bot.reply_to(message, 'Не правильний формат числа')
            markup = types.ForceReply(selective=False)
            bot.send_message(message.from_user.id, top_up_account, reply_markup=markup)


@bot.message_handler(content_types=['text'])
def get_text_messages(message):

    if message.text == '👋 Почати':
        markup = types.ForceReply(selective=False)
        bot.send_message(message.from_user.id, est_name_and_password_for_subsc, reply_markup=markup)
    elif message.text == 'Назад в меню':
        show_main_menu(message)

    elif message.text == 'Профіль':
        db = DB()
        est_subs = db.get_est_list_for_tg_user(message.from_user.id)
        if est_subs is None:
            messg = 'Ви не підписані на жоден заклад\n'
        else:
            ests = ' '.join(est_subs)
            messg = 'Ви підписані на заклади: ' + ests

        est_subs = db.get_est_name_by_owner_id(message.from_user.id)

        if est_subs is None:
            messg += " \nВи не зареєстровані як власник закладу"
        else:
            ests = ' '.join(est_subs)
            messg =  messg + '\nВи зареєсровані власником: ' + ests

        messg = messg + f"\nУ вас на рахунку {db.get_money_for_tg_user(message.from_user.id)} UAH"

        bot.send_message(message.from_user.id,
                         messg,
                         parse_mode='Markdown')

    elif message.text == 'Отримати звіт за дату':
        markup = types.ForceReply(selective=False)
        bot.send_message(message.from_user.id, report_for_date, reply_markup=markup)

    elif message.text == 'Підписатись на щоденний звіт':
        markup = types.ForceReply(selective=False)
        bot.send_message(message.from_user.id, est_name_and_password_for_subsc, reply_markup=markup)

    elif message.text == 'Отримати інформацію про заклад':
        markup = types.ForceReply(selective=False)
        bot.send_message(message.from_user.id, "Введине название заведения и пароль",
                         reply_markup=markup)

    elif message.text == "Поповнити рахунок":
        markup = types.ForceReply(selective=False)
        db = DB()
        bot.send_message(message.from_user.id, top_up_account, reply_markup=markup)
        #markup = types.ReplyKeyboardMarkup(resize_keyboard=True)  # создание новых кнопок
        #btn1 = types.KeyboardButton('Назад в меню')

        #markup.add(btn1)
        #bot.send_message(message.from_user.id, 'Або натисніть кнопку Назад в меню', reply_markup=markup)


if __name__ == '__main__':
    while True:
        try:
            bot.polling(none_stop=True)
        except ConnectionError as e:
            print("Connection error, retrying...", e)
            time.sleep(15)