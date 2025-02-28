#!/usr/bin/env python3

import logging
from dotenv import load_dotenv
import os
from telegram import Update, ForceReply, BotCommand, BotCommandScopeChat, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, ConversationHandler, CallbackQueryHandler
import re
import paramiko
import psycopg2

class config:
    """Конфигурация приложения"""

    # уровень логирования
    log_level="NOTSET"
    # файл журнала
    log_file=None

    # токен бота
    token=None

    #ssh-хост
    ssh_host=None
    #ssh-порт
    ssh_port=22
    #ssh пользователь
    ssh_user=None
    #ssh пароль
    ssh_pass=None

    # параметры подключения к базе данных
    db_host=None
    db_port=5432
    db_user=None
    db_password=None
    db_database=None
    db_schema="public"

    """Параметры приложения"""
    def __init__(self):
        """Загрузка параметров приложения"""
        # Использование стандартного .env
        load_dotenv()
        # Параметры логирования
        self.log_level=os.environ.get("LOGLEVEL", default=self.log_level)
        if not self.log_level in ["NOTSET", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
            raise BaseException(f"Неизвестный уровень логирования - {self.log_level}")
        self.log_file=os.environ.get("LOGFILE", default=None)
        # токен бота
        try: self.token = os.environ["TOKEN"]
        except KeyError: raise BaseException("Требуется api-ключ бота")
        # ssh
        try: self.ssh_host = os.environ["SSH_HOST"]
        except KeyError: raise BaseException("Требуется имя хоста удаленного сервера")
        try: self.ssh_port=int(os.environ.get("SSH_PORT", default=self.ssh_port))
        except ValueError: raise BaseException("Номер порта SSH должен быть числом")
        try: self.ssh_user = os.environ["SSH_USER"]
        except KeyError: raise BaseException("Требуется имя пользователя удаленного сервера")
        try: self.ssh_pass = os.environ["SSH_PASS"]
        except KeyError: raise BaseException("Требуется имя пароль удаленного сервера")
        # база данных
        try: self.db_host = os.environ["DB_HOST"]
        except KeyError: raise BaseException("Требуется имя сервера базы данных")
        try: self.db_port=int(os.environ.get("DB_PORT", default=self.db_port))
        except ValueError: raise BaseException("Номер порта БД должен быть числом")
        try: self.db_user = os.environ["DB_USER"]
        except KeyError: raise BaseException("Требуется имя входа базы данных")
        try: self.db_password = os.environ["DB_PASS"]
        except KeyError: raise BaseException("Требуется пароль базы данных")
        try: self.db_database = os.environ["DB_DTBS"]
        except KeyError: raise BaseException("Требуется имя базы данных")
        self.db_schema=os.environ.get("DB_SCHM", default=self.db_schema)


class remote_execution:
    """Удаленный запуск"""
    # клиент
    client=None

    safe_args_regex=re.compile('^[a-zA-Z0-9.,_-]+$')

    def run_pipes(self, command:str, args:dict={}):
        """Выполнение удаленной команды.
        Возвращает сырые пайпы
        
        :param command: команда
        :param args: аргументы
        """
        # проверка аргументов
        for a in args:
            if not self.safe_args_regex.match(args[a]):
                logging.warning(f"remote_execution.run_pipes: unsafe argument: {args[a]}")
                return None
        # конечная строка
        real_comm=command.format_map(args)
        # запуск
        logging.debug(f"remote_execution.run: try to run {real_comm}")
        return self.client.exec_command(real_comm)

    def run(self, command:str, args:list=[]):
        """Выполнение удаленной команды.
        Возвращает конечную стоку.
        
        :param command: команда
        :param args: аргументы
        """
        pipes=self.run_pipes(command=command, args=args)
        if not pipes:
            logging.warning(f"remote_execution.run: unable to get data")
            return None
        data = pipes[1].read()+pipes[2].read()
        data = str(data).replace('\\n', '\n').replace('\\t', '\t')[2:-1]
        return data

    def close(self):
        """Завершить работу"""
        self.client.close()

    ##
    # Инициализация класса
    ## 
    def __init__(self, config: config):
        """Инициализация удаленного подключения

        :param config: класс с конфигурацией
        """
        self.client=paramiko.SSHClient()
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.client.connect(
            hostname=config.ssh_host,
            port=config.ssh_port,
            username=config.ssh_user,
            password=config.ssh_pass
        )

class db: 
    """"Работа с базой данных"""

    # подключение
    conn=None

    # таблица email`ов
    email_tbl="emails"
    # таблица номеров телефонов
    phones_tbl="phones"

    def close(self):
        """Закрытие подключения к БД"""
        self.conn.close()

    def __init__(self, config: config):
        """Инициализация подключение и создание базы данных

        :param config: класс с конфигурацией
        """
        # подключение
        self.conn=psycopg2.connect(
            dbname=config.db_database,
            user=config.db_user,
            password=config.db_password,
            host=config.db_host,
            port=config.db_port,
            options=f"-c search_path={config.db_schema}"
        )
        cursor = self.conn.cursor()
        # создание структуры
        logging.debug("Создание структуры базы данных")
        for table in [self.email_tbl, self.phones_tbl]:
            cursor.execute(f"CREATE SEQUENCE IF NOT EXISTS {table}_seq INCREMENT BY 1 START 1 NO CYCLE NO MAXVALUE CACHE 1")
            cursor.execute(f"CREATE TABLE IF NOT EXISTS {table} (id INT DEFAULT nextval('{table}_seq') unique not null, record VARCHAR(64) not null)")
        self.conn.commit()
        cursor.close()

    def get_records(self, table: str):
        """Получение списка из базы данных
        
        :param table: имя таблицы"""
        cursor = self.conn.cursor()
        cursor.execute(f"SELECT id,record FROM {table}")
        data=cursor.fetchall()
        cursor.close()
        return data
    
    def add_records(self, table: str, list: list):
        """Добавление в базу данных
        
        :param table: имя таблицы
        :param list: добавляемые элементы"""
        cursor = self.conn.cursor()
        # проще чем executemany
        save_data=[]
        for row in list:
            save_data.append((row,))
        cursor.executemany(f"INSERT INTO {table} (record) VALUES (%s)", vars_list=save_data)
        self.conn.commit()
        cursor.close()
        return True

    def get_emails(self):
        """Получение email"""
        return self.get_records(self.email_tbl)
    
    def get_phones(self):
        """Получение номеров телефонов"""
        return self.get_records(self.phones_tbl)
    
    def add_emails(self, list: list):
        """Добавление email
        
        :param list: добавляемые элементы"""
        return self.add_records(self.email_tbl, list)
    
    def add_phones(self, list: list):
        """Добавление номеров телефонов
        
        :param list: добавляемые элементы"""
        return self.add_records(self.phones_tbl, list)

class bot:
    """Бот"""

    # простое регулярное выражение для поиска email
    # да, я знаю про RFC
    email_regex=re.compile(r'[a-zA-Z0-9+_.-]+@[a-zA-Z0-9.-]+')

    # просто регулярное выражение для поиска номеров телефонов:
    # 8XXXXXXXXXX
    # 8(XXX)XXXXXXX
    # 8 XXX XXX XX XX
    # 8 (XXX) XXX XX XX
    # 8-XXX-XXX-XX-XX
    # Также вместо ‘8’ на первом месте может быть ‘+7’.
    phone_number_regex=re.compile(r'(?:\+7|8)'
                                  +r'(?:'
                                    +r'\s*[-(]?\d{3}[-)]?'
                                    +r'\s*[-]?\d{3}'
                                    +r'\s*[-]?\d{2}'
                                    +r'\s*[-]?\d{2}'
                                  +r')')
    
    # сложность пароля
    # - Пароль должен содержать не менее восьми символов.
    # - Пароль должен включать как минимум одну заглавную букву (A–Z).
    # - Пароль должен включать хотя бы одну строчную букву (a–z).
    # - Пароль должен включать хотя бы одну цифру (0–9).
    # - Пароль должен включать хотя бы один специальный символ, такой как !@#$%^&*().
    password_verify_complexity_tests=[
        re.compile(r'.{8}'),
        re.compile(r'[A-Z]'),
        re.compile(r'[a-z]'),
        re.compile(r'\d'),
        re.compile(r'[!@#$%&*()^]'),
    ]

    def do_start(self, update: Update, context):
        """/start"""
        user = update.effective_user
        update.message.reply_text(f"Привет {user.full_name}!\nИспользуй /help для подсказки") 

    def find_re_report(self, input: str, re: re.Pattern, save_id: int=0, save_type: str=None):
        """Поиск регулярного выражения и вывод информации
        
        :param input: входная строка
        :param re: регулярное выражение"""
        # поиск
        search=re.findall(input)
        logging.debug(f"find_re_report: found {len(search)}")
        # если ничего не найдено - Null:
        if not search:
            return None
        if save_id and save_id > 0 and save_type:
            logging.debug(f"save search for do_save_button")
            self.__save_data[save_id]={"type": save_type, "list": search}
        # формируем вывод
        output=""
        for i in range(len(search)):
            output += f"{i+1}. {search[i]}\n"
        return output

    __save_data={}
    def do_save_button(self, update: Update, context):
        """Команда поддержка работы кнопки save"""
        id=update.effective_user.id
        # вызов из сообщения и callback_query
        if update.callback_query:
            msg=update.callback_query.message
        else:
            msg=update.message
        if id in self.__save_data:
            if self.__save_data[id]["type"] == "emails":
                logging.error(f"[U:{update.effective_user.username}] save emails to DB")
                self.db.add_emails(self.__save_data[id]["list"])
                del self.__save_data[id]
                msg.reply_text("Сохранено")
            elif self.__save_data[id]["type"] == "phones":
                logging.error(f"[U:{update.effective_user.username}] save phones to DB")
                self.db.add_phones(self.__save_data[id]["list"])
                del self.__save_data[id]
                msg.reply_text("Сохранено")
            else:
                logging.error(f"[U:{update.effective_user.username}] save to DB unknown type {self.__save_data[id]['type']}")
                msg.reply_text("Неизвестная ошибка")
        else:
            logging.error(f"[U:{update.effective_user.username}] save to DB unknown id {id}")
            msg.reply_text("Неизвестная ошибка")

    ##
    # Поиск Email`ов
    ##
    def find_email(self, update: Update, context):
        """/find_email - получение и проверка ввода пользователя"""
        input = update.message.text
        reply=self.find_re_report(input, self.email_regex, update.effective_user.id, "emails")
        if not reply:
            logging.info(f"[U:{update.effective_user.username}] find_email: not found")
            update.message.reply_text("Не найдены email-адреса")
            return
        update.message.reply_text(reply,
                                  reply_markup=InlineKeyboardMarkup(
                                            [
                                                [InlineKeyboardButton(f"Сохранить результат", callback_data="save_search")]
                                            ]
                                        )
                                    )
        logging.info(f"[U:{update.effective_user.username}] find_email: end")
        return ConversationHandler.END

    def do_find_email(self, update: Update, context):
        """/find_email - инициализация диалога"""
        logging.info(f"[U:{update.effective_user.username}] find_email: start")
        update.message.reply_text(f'Введите текст для поиска email-адресов')
        return 'find_email'

    def do_get_emails(self, update: Update, context):
        """/get_emails - получение из БД"""
        logging.info(f"[U:{update.effective_user.username}] get_emails")
        rows=self.db.get_emails()
        output=""
        if rows:
            # формируем вывод
            for i in range(len(rows)):
                output += f"{rows[i][0]}. {rows[i][1]}\n"
        else:
            output="Нет данных"
        update.message.reply_text(output)

    ##
    # Поиск номеров телефонов
    ##
    def find_phone_number(self, update: Update, context):
        """/find_phone_number - получение и проверка ввода пользователя"""
        input = update.message.text
        reply=self.find_re_report(input, self.phone_number_regex, update.effective_user.id, "phones")
        if not reply:
            logging.info(f"[U:{update.effective_user.username}] find_phone_number: not found")
            update.message.reply_text("Не найдены номера телефонов")
            return
        update.message.reply_text(reply,
                                  reply_markup=InlineKeyboardMarkup(
                                            [
                                                [InlineKeyboardButton(f"Сохранить результат", callback_data="save_search")]
                                            ]
                                        )
                                    )        
        logging.info(f"[U:{update.effective_user.username}] find_phone_number: end")
        return ConversationHandler.END
    
    def do_find_phone_number(self, update: Update, context):
        """/find_phone_number - инициализация диалога"""
        logging.info(f"[U:{update.effective_user.username}] find_phone_number: start")
        update.message.reply_text(f'Введите текст для поиска номеров телефона')
        return 'find_phone_number'

    def do_get_phones(self, update: Update, context):
        """/get_phones - получение из БД"""
        logging.info(f"[U:{update.effective_user.username}] get_phones")
        rows=self.db.get_phones()
        output=""
        if rows:
            # формируем вывод
            for i in range(len(rows)):
                output += f"{rows[i][0]}. {rows[i][1]}\n"
        else:
            output="Нет данных"
        update.message.reply_text(output)

    ##
    # Проверка сложности пароля
    ##
    def verify_password(self, update: Update, context):
        """/verify_password - получение и проверка ввода пользователя"""
        input = update.message.text
        # проходим тесты
        passed_tests=0
        for test in self.password_verify_complexity_tests:
            if test.findall(input): passed_tests += 1
        logging.info(f"[U:{update.effective_user.username}] verify_password: passed {passed_tests}")
        # количество пройденных тестов должно совпадать с количеством
        if passed_tests == len(self.password_verify_complexity_tests):
            update.message.reply_text("Пароль сложный")
        else:
            update.message.reply_text("Пароль простой")
        logging.info(f"[U:{update.effective_user.username}] verify_password: end")
        return ConversationHandler.END

    def do_verify_password(self, update: Update, context):
        """/verify_password - инициализация диалога"""
        logging.info(f"[U:{update.effective_user.username}] verify_password: start")
        update.message.reply_text(f'Введите пароль для проверки')
        return 'verify_password'

    def more(self, id, text:str, max_char:int=3096, max_lines:int=500):
        """Разбить вывод по строкам чтобы влезать в лимит сообщений
        
        :param id: id буфера more
        :param text: текст для разбивки
        :param max_char: максимальный размер одного блока
        :param max_lines: максимальное количество строк
        """
        lines_no_limits=text.splitlines()
        logging.debug(f"more: input have {len(lines_no_limits)} lines in {len(text)} chars")
        # делим строки при выходе за границы размера
        lines=[]
        for i in lines_no_limits:
            if len(i) > max_char:
                split_line_parts=len(i)//max_char + int(len(i)%max_char > 0)
                logging.debug(f"more: split line ({len(i)} chars) to {split_line_parts} parts")
                for j in range(split_line_parts):
                    lines.append(i[j+max_char:(j+1)+max_char])
            else:
                lines.append(i)
        lines_no_limits=None
        logging.debug(f"more: output have {len(lines)} lines")
        # теперь разбираемся с страницами
        pages=[]
        page=lines[0]
        current_page_chars=len(lines[0])+1
        current_page_lines=1
        for i in range(1, (len(lines)-1)):
            current_page_chars += len(lines[i])+1
            current_page_lines += 1
            # если переполнено
            if (
                ( current_page_chars >= max_char ) or
                ( current_page_lines >= max_lines )
            ):
                # то новая страница
                pages.append(page)
                page=lines[i]
                current_page_chars=len(lines[i])+1
                current_page_lines=1
            else:
                # иначе - добавляем строку к текущей
                page += f"\n{lines[i]}"
        pages.append(page)
        logging.debug(f"more: output have {len(pages)} pages")
        self.__more_pages[id]={"pages":pages,"current": 1, "total": len(pages)}

    __more_pages={}
    def do_more(self, update: Update, context):
        """Команда поддержка работы кнопки more"""
        id=update.effective_user.id
        # вызов из сообщения и callback_query
        if update.callback_query:
            msg=update.callback_query.message
        else:
            msg=update.message
        if id in self.__more_pages:
            cur_more=self.__more_pages[id]            
            if cur_more and (cur_more["total"]>1) and (cur_more["current"] < cur_more["total"]):
                logging.debug(f"more: next_page")
                msg.reply_text(
                    f"```\n{cur_more['pages'][cur_more['current']-1]}\n```",
                    parse_mode='MarkdownV2',
                    reply_markup=InlineKeyboardMarkup(
                            [
                                [InlineKeyboardButton(f"--More-- Page {cur_more['current']} of {cur_more['total']}", callback_data="more")]
                            ]
                        )
                    )
                self.__more_pages[id]["current"] += 1
            elif cur_more and (cur_more["current"] == cur_more["total"]):
                msg.reply_text(
                    f"```\n{cur_more['pages'][cur_more['current']-1]}\n```",
                    parse_mode='MarkdownV2'
                    )
                if self.__more_pages[id]: del self.__more_pages[id]
            else:
                logging.debug(f"more: no new data - reset more")
                if self.__more_pages[id]: del self.__more_pages[id]
                msg.reply_text(f"No more data")
        else:
            msg.reply_text(f"No more data")

    ##
    # apt-list с поддержкой поиска
    ##
    def get_apt_list_filter(self, update: Update, context):
        input = update.message.text
        logging.info(f"[U:{update.effective_user.username}] get_apt_list: do filter")
        data=self.exec.run("apt list --installed {pkg} &>/dev/null && apt-cache show {pkg} || apt list | grep {pkg}", {"pkg": input})
        if data:
            self.more(update.effective_user.id,data)
            self.do_more(update, context)
        else:
             update.message.reply_text("Недопустимые данные, попробуйте еще.")
        return "get_apt_list"
        
    def get_apt_list_end(self, update: Update, context):
        logging.info(f"[U:{update.effective_user.username}] get_apt_list: end")
        update.message.reply_text("Прекращаю работу с /get_apt_list")
        # сброс меню
        self.updater.bot.delete_my_commands(
            scope=BotCommandScopeChat(
                chat_id=update.effective_chat.id
            )
        )
        return ConversationHandler.END

    # меню для команды
    def do_get_apt_list(self, update: Update, context):
        """/get_apt_list - старт"""
        logging.info(f"[U:{update.effective_user.username}] get_apt_list: start")
        # подсказка и данные
        update.message.reply_text("Напечатайте уточнение для поиска\n"
                                  +"Когда будет найден один пакет - будет выдана его детальная информация")
        self.more(update.effective_user.id,self.exec.run("apt list --installed"))
        self.do_more(update, context)
        return "get_apt_list"

    ##
    # Команда удаленного запуска
    ##
    __remote_exec_comm={
        'get_release': {
            "desc": "Релиз ОС",
            "cmd": 'cat /etc/*release*',
            },
        'get_uname': {
            "desc": "Архитектура процессора, имя хоста системы и версия ядра.",
            "cmd": 'uname -a',
            },
        'get_uptime': {
            "desc": "Время работы ОС",
            "cmd": 'uptime',
            },
        'get_df': {
            "desc": "Использование файловой системы",
            "cmd": 'df -h',
            },
        'get_free': {
            "desc": "Использование оперативной памяти",
            "cmd": 'free -m',
            },
        'get_mpstat': {
            "desc": "Сбор информации о производительности",
            "cmd": 'mpstat',
            },
        'get_w': {
            "desc": "Работающие пользователи",
            "cmd": 'w',
            },
        'get_auths': {
            "desc": "События входа в систему",
            "cmd": 'journalctl --no-pager SYSLOG_FACILITY=10 -n 10',
            },
        'get_critical': {
            "desc": "Критические события системы",
            "cmd": 'journalctl --no-pager -p 2 -n5',
            },
        'get_ps': {
            "desc": "Информация о процессах",
            "cmd": 'ps -axf',
            },
        'get_ss': {
            "desc": "Информация об всех сокетах",
            "cmd": 'ss -a',
            },
        'get_ss_listen': {
            "desc": "Информация об прослушивателях",
            "cmd": 'ss -l',
            },
        'get_ss_connected': {
            "desc": "Информация об активных (connected) сокетах",
            'cmd': 'ss state connected'
            },
        'get_services': {
            "desc": "Состояние сервисов",
            "cmd": 'systemctl --no-pager --type=service'
            },
        'get_repl_logs': {
            "desc": "Журнал лога БД репликации",
            "cmd": 'docker logs the-laxian-key-db_main-1 2>&1 | grep -i replication | tail -n 10'
            },
    }
    def do_simple_remote_exec(self, update: Update, context):
        """/get_[имя]"""
        # проблема составными командами
        if not update.message.text:
            logging.debug(f"[U:{update.effective_user.username}] do_simple_remote_exec: unknown {update.message.text}")
            return
        comm=update.message.text.split()[0][1:]
        logging.info(f"[U:{update.effective_user.username}] do_simple_remote_exec: start {comm}")
        if not self.__remote_exec_comm[comm]:
            raise BaseException("Неизвестная команда")
        self.more(update.effective_user.id,self.exec.run(self.__remote_exec_comm[comm]["cmd"]))
        self.do_more(update, context)

    ##
    # Справка и меню
    ##
    __bot_main_menu=[]
    def register_to_main_menu(self, cmd:str, desc:str):
        """
        Регистрация информации о справке

        :param cmd: имя команды
        :param decs: описание
        """
        logging.debug(f"main_menu: adding {cmd}")
        self.__bot_main_menu.append(BotCommand(command=cmd, description=desc))
    
    def main_menu(self):
        """Основное меню"""
        # очистка списка команд
        logging.debug("main_menu: set default menu")
        # очистка меню по-уполномочию
        self.updater.bot.delete_my_commands()
        self.updater.bot.set_my_commands(commands=self.__bot_main_menu)

    def do_help(self, update: Update, context):
        logging.info(f"[U:{update.effective_user.username}] help: start")
        data="Справка по использованию бота:"
        for i in self.__bot_main_menu:
            data += f"\n/{i.command} - {i.description}"
        update.message.reply_text(data)

    def do_cancel(self, update: Update, context):
        """Общая команда отмены диалога"""
        logging.info(f"[U:{update.effective_user.username}] cancel ")
        update.message.reply_text('Завершение диалога')
        return ConversationHandler.END

    ##
    # Инициализация класса
    ## 
    def __init__(self, config: config):
        """Инициализация бота

        :param config: класс с конфигурацией
        """
        # конфигурация
        self.config=config
        # инициализация бота
        logging.debug("Инициализация бота")
        self.updater = Updater(config.token, use_context=True)
        dp = self.updater.dispatcher
        # общая функция отмены диалога
        cancel_conversation=CommandHandler('cancel', self.do_cancel)
        # регистрация /start
        dp.add_handler(CommandHandler("start", self.do_start))
        # регистрация /help
        dp.add_handler(CommandHandler("help", self.do_help))
        # регистрация кнопки save
        dp.add_handler(CallbackQueryHandler(self.do_save_button, pattern="save_search"))
        # регистрация /find_email
        self.register_to_main_menu("find_email", "Поиск email-адресов в тексте")
        dp.add_handler(
            ConversationHandler(
                entry_points=[CommandHandler("find_email", self.do_find_email)],
                states={
                    'find_email': [MessageHandler(Filters.text & ~Filters.command, self.find_email)]
                },
                fallbacks=[cancel_conversation]
            )
        )
        # регистрация /get_emails
        self.register_to_main_menu("get_emails", "Сохраненные email")
        dp.add_handler(CommandHandler("get_emails", self.do_get_emails))
        # регистрация /find_phone_number
        self.register_to_main_menu("find_phone_number", "Поиск телефонных номеров в тексте")
        dp.add_handler(
            ConversationHandler(
                entry_points=[CommandHandler("find_phone_number", self.do_find_phone_number)],
                states={
                    'find_phone_number': [MessageHandler(Filters.text & ~Filters.command, self.find_phone_number)]
                },
                fallbacks=[]
            )
        )
        # регистрация /get_phones
        self.register_to_main_menu("get_phone_numbers", "Сохраненные телефонные номера")
        dp.add_handler(CommandHandler("get_phone_numbers", self.do_get_phones))
        
        # регистрация /verify_password
        self.register_to_main_menu("verify_password", "Проверка сложности пароля")
        dp.add_handler(
            ConversationHandler(
                entry_points=[CommandHandler("verify_password", self.do_verify_password)],
                states={
                    'verify_password': [MessageHandler(Filters.text & ~Filters.command, self.verify_password)]
                },
                fallbacks=[cancel_conversation]
            )
        )
        # регистрация /вызова команд
        for comm in self.__remote_exec_comm:
            self.register_to_main_menu(comm, self.__remote_exec_comm[comm]["desc"])
            dp.add_handler(CommandHandler(comm, self.do_simple_remote_exec))
        # регистрация /get_apt_list
        self.register_to_main_menu("get_apt_list", "Вывод списка пакетов, поиск и вывод информации")
        dp.add_handler(
            ConversationHandler(
                entry_points=[CommandHandler("get_apt_list", self.do_get_apt_list)],
                states={
                    'get_apt_list': [MessageHandler(Filters.text & ~Filters.command, self.get_apt_list_filter)],
                },
                fallbacks=[cancel_conversation]
            )
        )
        # подсказка по cancel
        self.register_to_main_menu("cancel", "Отмена ввода данных")
        # регистрация кнопки more
        dp.add_handler(CallbackQueryHandler(self.do_more, pattern="more"))
        # меню
        self.main_menu()

    def start(self):
        # база данных
        logging.info("Подключение к БД")
        self.db=db(self.config)
        # инициализация удаленного запуска
        logging.info("Инициализация удаленного подключения")
        self.exec=remote_execution(self.config)
        # Запускаем бота
        logging.info("Запуск бота")
        self.updater.start_polling()
        # Останавливаем бота при нажатии Ctrl+C
        self.updater.idle()
        logging.info("Прерывание работы")
        self.exec.close()
        self.db.close()

def main():
    # инициализация логирования в консоль
    logging.basicConfig(level=logging.DEBUG, format=' %(asctime)s - %(levelname)s - %(message)s')
    # загрузка конфигурации
    c=config()
    # настойка уровня логирования
    logger=logging.getLogger()
    logger.setLevel(getattr(logging,c.log_level))
    logging.debug(f"log_level: {c.log_level}")
    # сохранение в файл
    if c.log_file:
        logging.info(f"log to file: {c.log_file}")
        logging_file_handler=logging.FileHandler(c.log_file)
        logging_file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        logging_file_handler.setLevel(getattr(logging,c.log_level))
        logger.addHandler(logging_file_handler)
    # инициализация бота
    b=bot(c)
    b.start()

if __name__ == '__main__':
    """ Запуск main()"""
    main()