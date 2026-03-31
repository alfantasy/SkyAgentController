from typing import Any, Callable, Optional # Для аннотации типов
from functools import wraps # Для декорирования
import loguru # Модуль для логгирования (основная либа)
import os # Работа с файлами
from datetime import datetime, timezone # Работа с датой и временем

class MainLogger:
    '''### Логгирование, где используется библиотека loguru.
    Содержит подготовленные обработчики с цветовыми обозначениями.'''

    def __init__(self):
        self.tag = '[SS Standalone] '
        os.makedirs('logs', exist_ok=True)
        log_filename = f"logs/logger_{datetime.now(timezone.utc).strftime('%d-%m-%Y')}.log"
        self.object_logger = loguru.logger
        self.object_logger.add(log_filename, format='{time:DD.MM.YYYY HH:mm:ss} | {level} | {message}', retention='10 days', rotation="00:00", colorize=True)

        self.colours = {
            'green': '\033[92m',
            'white': '\033[97m',
            'red': '\033[91m',
            'blue': '\033[94m',
            'cyan': '\033[96m',
            'yellow': '\033[93m',
            'grey': '\033[90m',
            'uncolor': '\033[0m'
        }

        self.colours_and_styles = {
            'italic': {
                'red': '\033[3;91m',
                'green': '\033[3;92m',
                'yellow': '\033[3;93m',
                'blue': '\033[3;94m',
                'magenta': '\033[3;95m',
                'cyan': '\033[3;96m',
                'white': '\033[3;97m',
                'uncolor': '\033[0m'
            },
            'bold': {
                'red': '\033[1;91m',
                'green': '\033[1;92m',
                'yellow': '\033[1;93m',
                'blue': '\033[1;94m',
                'magenta': '\033[1;95m',
                'cyan': '\033[1;96m',
                'white': '\033[1;97m',
                'uncolor': '\033[0m'
            }
        }

    def __obj_logger__(self):
        return self.object_logger
    
    def catch(
        self,
        reraise: bool = False,
        default: Any = None,
        on_error: Optional[Callable] = None,
        exclude: Optional[tuple] = None,
    ):
        def decorator(func):
            # Проверяем, является ли функция асинхронной
            import inspect
            
            if inspect.iscoroutinefunction(func):
                @wraps(func)
                async def wrapper(*args, **kwargs):
                    try:
                        return await func(*args, **kwargs)
                    except Exception as e:
                        return self._handle_error(e, func, reraise, default, on_error, exclude)
                return wrapper
            else:
                @wraps(func)
                def wrapper(*args, **kwargs):
                    try:
                        return func(*args, **kwargs)
                    except Exception as e:
                        return self._handle_error(e, func, reraise, default, on_error, exclude)
                return wrapper
        return decorator

    def _handle_error(self, e, func, reraise, default, on_error, exclude):
        '''Внутренний метод для обработки логики ошибки (DRY)'''
        if exclude and isinstance(e, exclude):
            raise e

        # Логируем через твой же printerr (он запишет в loguru и в консоль)
        self.printerr(f"Исключение в функции {func.__name__}: {str(e)}", print_on=True)
        
        # Loguru позволяет прокинуть traceback в лог без reraise
        self.object_logger.exception(f"Detailed traceback for {func.__name__}:")

        if on_error:
            on_error(e)

        if reraise:
            raise e

        return default

    def printd(self, text: str, print_on: bool = False):
        '''### Auto-Logging function
        Вывод дебаг-сообщение
        
        :param text: текст для вывода сообщения
        :type text: str
        :param print_on: переменная, отвечающая за логгирование в консоль
        :type print_on: bool'''        

        if print_on:
            print(self.colours['cyan'] + self.tag + text + self.colours['uncolor'])
        self.object_logger.debug(self.colours['cyan'] + self.tag + text + self.colours['uncolor'])

    def prints(self, text: str, print_on: bool = False):
        '''#### Auto-Logging function
        Вывод сообщения об успешном выполнении.
        
        :param text: текст для вывода сообщения
        :type text: str
        :param print_on: переменная, отвечающая за логгирование в консоль
        :type print_on: bool'''
        if print_on:
            print(self.colours['green'] + self.tag + text + self.colours['uncolor'])
        self.object_logger.success(self.colours['green'] + self.tag + text + self.colours['uncolor'])

    def printw(self, text: str, print_on: bool = False):
        '''#### Auto-Logging function
        Вывод сообщения об предупреждении.

        :param text: текст для вывода сообщения
        :type text: str
        :param print_on: переменная, отвечающая за логгирование в консоль
        :type print_on: bool'''
        if print_on:
            print(self.colours['white'] + self.tag + text + self.colours['uncolor'])
        self.object_logger.warning(self.colours['white'] + self.tag + text + self.colours['uncolor'])

    def printerr(self, text: str, print_on: bool = False):
        '''#### Auto-Logging function
        Вывод об ошибке.

        :param text: текст для вывода сообщения
        :type text: str
        :param print_on: переменная, отвечающая за логгирование в консоль
        :type print_on: bool'''
        if print_on:
            print(self.colours['red'] + self.tag + text + self.colours['uncolor'])
        self.object_logger.error(self.colours_and_styles['italic']['red'] + self.tag + text + self.colours['uncolor'])

    def printinf(self, text: str, print_on: bool = False):
        '''#### Auto-Logging function
        Вывод сообщения с информацией.

        :param text: текст для вывода сообщения
        :type text: str
        :param print_on: переменная, отвечающая за логгирование в консоль
        :type print_on: bool'''
        if print_on:
            print(self.colours['blue'] + self.tag + text + self.colours['uncolor'])
        self.object_logger.info(self.colours['blue'] + self.tag + text + self.colours['uncolor'])

    def printy(self, text: str, print_on: bool = False):
        '''#### Auto-Logging function
        Вывод сообщения об успешном выполнении.

        :param text: текст для вывода сообщения
        :type text: str
        :param print_on: переменная, отвечающая за логгирование в консоль
        :type print_on: bool'''
        if print_on:
            print(self.colours['yellow'] + self.tag + text + self.colours['uncolor'])
        self.object_logger.success(self.colours['yellow'] + self.tag + text + self.colours['uncolor'])

    def printa(self, text: str, color: str, type: str, style: str = None, logon: bool = True):
        '''#### NoAuto-Logging function
        Вывод любого сообщения с указанием цвета и типа.
        Имеет возможность отключать авто-перенос сообщения в лог.

        :param text: текст для вывода сообщения
        :type text: str
        :param color: выбор цвета по типу
        :type color: str
        :param type: выбор типа сообщения
        :type type: str
        :param style: применение типа стиля к сообщениям
        :type style: str
        :param logon: разрешение логгирования в спец-логгер
        :type logon: bool'''
        uncolor = self.colours['uncolor']
        clr = self.colours[color]
        if style is not None:
            clr = self.colours_and_styles[style][color]
        if type == 'info':
            print(clr + self.tag + text + uncolor)
            if logon == True:
                self.object_logger.info(clr + self.tag + text + uncolor)
        elif type == 'error':
            print(clr + self.tag + text + uncolor)
            if logon == True:
                self.object_logger.error(clr + self.tag +  text + uncolor)
        elif type == 'warning':
            print(clr + self.tag + text + uncolor)
            if logon == True:
                self.object_logger.warning(clr + self.tag + text + uncolor)
        elif type == 'success':
            print(clr + self.tag + text + uncolor)
            if logon == True:
                self.object_logger.success(clr + self.tag + text + uncolor)
        elif type == 'debug':
            print(clr + self.tag + text + uncolor)
            if logon == True:
                self.object_logger.debug(clr + self.tag + text + uncolor)    

    def check_rotation(self):
        self.printinf("Проверка ротации лог-файлов...")
        list_dirs = os.listdir('logs')
        for item_file in list_dirs:
            strp_time_split = item_file.split('_')[1].split('.')[0]
            delta_days = (datetime.now(timezone.utc) - datetime.strptime(strp_time_split, '%d-%m-%Y').replace(tzinfo=timezone.utc)).days
            if delta_days > 5:
                os.remove(f"logs/{item_file}")
        self.printinf("Ротация лог-файлов завершена. Все лог-файлы старше 5 дней успешно удалены.")


instance_logger = MainLogger()