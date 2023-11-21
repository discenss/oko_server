import os.path
from multiprocessing.connection import Client
import schedule
import time
import logging
from oko_db.db import DB
import re
from bot import send_bot_message
from datetime import datetime
from dateutil.relativedelta import relativedelta
logging.basicConfig(filename='dispatcher.log', filemode='w', level=logging.DEBUG)

days_untin_final = "У вас залишилося %s до завершення підписки\n"
users_money = "У вас на рахунку %s\n"
license_name_and_price = "Ви викостовуете для закладу %s підписку %s. Baм поповнити рахунок на %s грн"
paying_for_license = "З Вашого рахунку списано %s за використання підписки %s для закладу %s. На на рахунку залишок %s"
def get_date_from_file(source_path):
    match = re.search(r'(\d{4}-\d{2}-\d{2})', source_path)
    if match:
        date_string = match.group(1)
        converted_date = datetime.strptime(date_string, '%Y-%m-%d').date()
        return converted_date
    else:
        return False

def run_processing():

    print(" Processing started")
    db = DB()
    db.cur.execute("SELECT * FROM establishments")
    rows = db.cur.fetchall()
    list_not_resp = []
    for i in range(len(rows)):
        id, name, adress, passw, license_id, owner_id, report_type, path, date = rows[i]
        if path!= None and os.path.isdir(path):
            for file in os.listdir(path):
                if file.endswith('.mp4') and get_date_from_file(file):
                        #and os.path.isfile(os.path.join(path, file)[:-3]+'json'):
                    date_string = get_date_from_file(file)
                    if date_string:
                        days_difference = (datetime.now().date() - date_string).days
                        if days_difference > 2:
                            continue
                        date = str(date_string)
                        # Формируем запрос на выборку данных из таблицы по дате
                        query = f"SELECT * FROM REPORT WHERE REALDATE = '{date}' AND ESTABLISHMENT_ID = {id}"
                        # Выполняем запрос и получаем результат
                        db.cur.execute(query)

                        try:
                            d = db.cur.fetchall()
                            if len(d) > 0:
                                continue

                            while True:
                                ip_server, id_server, device = db.get_server_for_task(list_not_resp)
                                if len(ip_server) < 1:
                                    return ''

                                try:
                                    address = (ip_server, 8443)
                                    conn = Client(address)
                                    if os.path.isdir(os.path.join(path,'frames')) is False:
                                        try:
                                            os.mkdir(os.path.join(path,'frames'))
                                        except:
                                            logging.info(
                                                str(datetime.now()[:-7]) + " Not connected to server " + ip_server)

                                    command = f"--source={os.path.join(path, file)} --project={os.path.join(path,'frames')} --est={name} --id={id_server} --device={device}"
                                    print(command)
                                    conn.send(command)
                                    conn.send('close')
                                    conn.close()
                                    break
                                except:
                                    logging.info(str(datetime.now()[:-7]) + " Not connected to server " + ip_server)
                                    list_not_resp.append(ip_server)
                                    pass
                                    continue

                        except:
                            pass

    else:
        return None
def license_check():
    db = DB()
    rows = db.get_full_est_list()
    #rows = db.cur.fetchall()
    for i in range(len(rows)):
        id, name, adress, passw, license_id, owner_id, report_type, path, date = rows[i]
        days_difference = (date - datetime.now().date()).days
        lic_name, lic_price = db.get_license_name_and_price(license_id)
        tg_id = db.get_telegram_id(owner_id)
        tg_user_money = db.get_money_for_tg_user(tg_id)
        if ( days_difference < 7 and days_difference >= 0 and lic_name == "Test"):
            result_string = days_untin_final % (days_difference)
            if (tg_user_money == 0):
                send_bot_message(result_string + " У вас на рахунку 0 грн. Тариф базовий буде призначений автоматично. Якщо треба змінити, тоді звертайтесь до оператора", tg_id)

        elif ( days_difference < 7 and days_difference > 0 and lic_name !="Test"):
            money = db.get_money_for_tg_user(tg_id)
            if (money < lic_price):
                result_string = days_untin_final % (days_difference)
                result_string = result_string + users_money % (money) + license_name_and_price %(name, lic_name, lic_price - money)
                send_bot_message(result_string, tg_id)

        elif (days_difference <= 0 and lic_name != "Test"):
            if (tg_user_money >= lic_price ):
                db.addmomey_for_tg_user(tg_id, lic_price * -1)
                result_string = paying_for_license %(lic_price, lic_name, name, db.get_money_for_tg_user(tg_id))
                today = datetime.today()
                one_month_later = today + relativedelta(months=1)
                db.db_set_date_license_expired(one_month_later.date(), id)
                send_bot_message(result_string, tg_id)


# Планирование задачи на выполнение каждый день в определенное время
schedule.every().day.at("03:00").do(run_processing)
schedule.every().day.at("03:00").do(license_check)

def main():
    #license_check()
    run_processing()
    while True:
        schedule.run_pending()
        time.sleep(1)


if __name__ == '__main__':
    #bot.polling(none_stop=True, interval=0)  # обязательная для работы бота часть
    main()
