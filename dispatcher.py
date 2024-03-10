import os.path
from multiprocessing.connection import Client

import schedule
import time
from oko_db.db import DB
import re
from bot import send_bot_message
from datetime import datetime
from dateutil.relativedelta import relativedelta
import logging
logging.getLogger("urllib3").setLevel(logging.CRITICAL)
logging.basicConfig(filename='db.log', filemode='w', level=logging.DEBUG)

days_untin_final = "У вас %s днів до закінчення дії підписки\n"
users_money = "У вас на рахунку %s\n"
license_name_and_price = "Ви використовуете для закладу %s підписку %s. Вам необхідно поповнити рахунок на %s"
paying_for_license = "З вашого рахунку знято %sгрн за використання підписки %s для закладу %s. Залишок на рахунку %s"

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
        id, name, adress, passw, license_id, owner_id, report_type, path, date, extra = rows[i]
        if (date - datetime.now().date()).days < 0:
            logging.error(
                f" Subscription expired for {name}")
            continue
        if path!= None and os.path.isdir(path):

            for file in os.listdir(path):
                if file.endswith('.mp4') and get_date_from_file(file):
                        #and os.path.isfile(os.path.join(path, file)[:-3]+'json'):
                    date_string = get_date_from_file(file)
                    if date_string:
                        days_difference = (datetime.now().date() - date_string).days
                        if days_difference > 14:
                            try:
                                os.remove(os.path.join(path, file))
                                os.remove(os.path.join(path, file)[:-3] + 'xspf')
                                if db.get_report_type(name) != "none":
                                    os.remove(os.path.join(path, file)[:-3] + 'json')

                            except Exception as e:
                                logging.error(
                                    f"{datetime.now():%Y-%m-%d %H:%M:%S} - An error occurred with file deleting: {e}")
                                continue

                            continue

                        if days_difference > 3:
                            continue

                        if db.get_report_type(name) != "none":
                            if os.path.isfile(os.path.join(path, file)[:-3] + 'json') is False:
                                logging.error(
                                    f"{datetime.now():%Y-%m-%d %H:%M:%S} - Not found JSON file: {os.path.join(path, file)[:-3] + 'json'}")
                                continue

                        date = str(date_string)
                        query = f"SELECT * FROM REPORT WHERE REALDATE = '{date}' AND ESTABLISHMENT_ID = {id}"
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
                                    ip_server, id_server, device = db.get_server_for_task(list_not_resp)
                                    if not ip_server:
                                        return ''

                                    address = (ip_server, 8443)
                                    conn = Client(address)

                                    command = f"--source={os.path.join(path, file)} --est={name} --id={id_server} --device={device}"
                                    print(command)
                                    logging.info(
                                        f"{datetime.now():%Y-%m-%d %H:%M:%S} STARTED {command}")
                                    conn.send(command)
                                    conn.send('close')
                                    conn.close()
                                    break
                                except OSError as e:
                                    logging.error(
                                        f"{datetime.now():%Y-%m-%d %H:%M:%S} - Failed to create directory: {e}")
                                    break
                                except ConnectionError as e:
                                    logging.error(
                                        f"{datetime.now():%Y-%m-%d %H:%M:%S} - Not connected to server {ip_server}: {e}")
                                    list_not_resp.append(ip_server)
                                    break
                                except Exception as e:
                                    logging.error(
                                        f"{datetime.now():%Y-%m-%d %H:%M:%S} - An unexpected error occurred: {e}")
                                    list_not_resp.append(ip_server)
                                    break

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
        if ( days_difference < 1 and days_difference >= 0 and lic_name == "Test"):
            result_string = days_untin_final % (days_difference)
            if (tg_user_money == 0):
                send_bot_message(result_string + " У вас на рахунку 0 грн. Поповніть рахунок та зверніться до оператора щоб узгодити тип підписки. ", tg_id)
                logging.info(f"{datetime.now():%Y-%m-%d %H:%M:%S} - Закончен тестовый период для заведения {name} и telegram id {tg_id}")


        elif ( days_difference < 7 and days_difference > 0 and lic_name !="Test"):
            money = db.get_money_for_tg_user(tg_id)
            if (money < lic_price):
                result_string = days_untin_final % (days_difference)
                result_string = result_string + users_money % (money) + license_name_and_price %(name, lic_name, lic_price - money)
                send_bot_message(result_string, tg_id)
                logging.info(
                    f"{datetime.now():%Y-%m-%d %H:%M:%S} - Заканчивается подписка для заведения {name} и telegram id {tg_id}. Сумма {lic_price}")

        elif (days_difference <= 0 and lic_name != "Test"):
            if (tg_user_money >= lic_price ):
                db.addmomey_for_tg_user(tg_id, lic_price * -1)
                result_string = paying_for_license %(lic_price, lic_name, name, db.get_money_for_tg_user(tg_id))
                today = datetime.today()
                one_month_later = today + relativedelta(months=1)
                db.db_set_date_license_expired(one_month_later.date(), id)
                send_bot_message(result_string, tg_id)
                logging.info(
                    f"{datetime.now():%Y-%m-%d %H:%M:%S} - Снята оплата для заведения {name} и telegram id {tg_id}. Сумма {lic_price}")
            else:
                logging.info(
                    f"{datetime.now():%Y-%m-%d %H:%M:%S} - Недостаточно денег для оплаты подписки для заведения '{name}' и telegram id '{tg_id}'. Сумма '{lic_price}'")


        #elif (days_difference <= 0 and lic_name == "Test"):
        #    lic_name, lic_price = db.get_license_name_and_price(1)
        #    if (tg_user_money >= lic_price ):
        #        db.addmomey_for_tg_user(tg_id, lic_price * -1)
        #        result_string = paying_for_license %(lic_price, lic_name, name, db.get_money_for_tg_user(tg_id))
        #        today = datetime.today()
        #        one_month_later = today + relativedelta(months=1)
        #        db.db_set_date_license_expired(one_month_later.date(), id)
        #        send_bot_message(result_string, tg_id)


# Планирование задачи на выполнение каждый день в определенное время
schedule.every().day.at("03:00").do(run_processing)
schedule.every().day.at("03:00").do(license_check)

def main():
    #license_check()
    #run_processing()
    while True:
        schedule.run_pending()
        time.sleep(1)


if __name__ == '__main__':
    #bot.polling(none_stop=True, interval=0)  # обязательная для работы бота часть
    main()
