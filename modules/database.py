import sqlite3

class Database:
    '''
    ### Основной класс базы данных для базирования серверной агентированной части.
    '''

    def __init__(self, db_path: str = "skyagent.db") -> None:
        '#### Создание соединения с базой данных.'
        self.sq = sqlite3.connect(db_path)
        print(f'Database «{db_path}» has been connected to Agent.')
        self.sq.cursor().execute("""CREATE TABLE IF NOT EXISTS users (
                        id INTEGER PRIMARY KEY AUTOINCREMENT, 
                        token TEXT NOT NULL UNIQUE,
                        ip TEXT DEFAULT NULL
                    );""")
        self.sq.cursor().execute("""CREATE TABLE IF NOT EXISTS temp_regist (
                        id INTEGER PRIMARY KEY AUTOINCREMENT, 
                        token TEXT NOT NULL UNIQUE,
                        ip TEXT NOT NULL
                    );""")
        self.sq.commit()
    
    ## Унифицированные функции ##

    def cur(self, *args, **kwargs) -> sqlite3.Cursor:
        '#### Возвращает курсор базы данных.'
        return self.sq.cursor()
    
    def exec(self, sql: str, params: tuple = None) -> None:
        '#### Выполнение SQL-запроса.'
        cur = self.cur()
        cur.execute(sql, params)
        self.sq.commit()

    def execmany(self, sql: str, params: tuple = None) -> None:
        '#### Выполнение нескольких SQL-запросов.'
        cur = self.cur()
        cur.executemany(sql, params)
        self.sq.commit()

    def fetchone(self, sql: str, params: tuple = None, lastrowid: bool = False) -> tuple:
        '#### Выполнение SQL-запроса и возврат первого результата.'
        cur = self.cur()
        cur.execute(sql, params)
        if lastrowid:
            return {"lastrowid": cur.lastrowid, "data": cur.fetchone()}
        return cur.fetchone()
        
    def fetchall(self, sql: str, params: tuple = None, lastrowid: bool = False) -> tuple:
        '#### Выполнение SQL-запроса и возврат всех результатов.'
        cur = self.cur()
        cur.execute(sql, params)
        if lastrowid:
            return {"lastrowid": cur.lastrowid, "data": cur.fetchall()}
        return cur.fetchall()
    
    ## Унифицированные функции ##

    ## Функции управления пользовательскими данными и аутентификацией ##
    def create_new_user(self, token: str, ip: str):
        '#### Создание нового пользователя.'
        self.exec("INSERT INTO users (token, ip) VALUES (?, ?)", (token, ip))

    def check_user(self, token: str):
        '#### Проверка пользователя.'
        dt = self.fetchone("SELECT * FROM users WHERE token = ?", (token,))
        if not dt:
            return False
        return True

    def get_user_by_token(self, token: str):
        '#### Получение пользователя по токену.'
        return self.fetchone("SELECT * FROM users WHERE token = ?", (token,))
    
    def get_user_by_ip(self, ip: str):
        '#### Получение пользователя по IP.'
        return self.fetchone("SELECT * FROM users WHERE ip = ?", (ip,))
    
    def get_user_by_id(self, id_select: int):
        '#### Получение пользователя по ID.'
        return self.fetchone("SELECT * FROM users WHERE id = ?", (id_select,))

    def get_all_users(self):
        '#### Получение всех пользователей.'
        return self.fetchall("SELECT * FROM users")

    def remove_user(self, token: str):
        '#### Удаление пользователя.'
        self.exec("DELETE FROM users WHERE token = ?", (token,))

    def add_new_temp_reg(self, token: str, ip: str):
        '#### Добавление временного пользователя.'
        self.exec("INSERT INTO temp_regist (token, ip) VALUES (?, ?)", (token, ip))

    def check_temp_reg(self, token: str):
        '#### Проверка временного пользователя.'
        dt = self.fetchone("SELECT * FROM temp_regist WHERE token = ?", (token,))
        if not dt:
            return False
        return True
    
    def delete_temp_reg(self, token: str):
        '#### Удаление временного пользователя.'
        self.exec("DELETE FROM temp_regist WHERE token = ?", (token,))

    def register_user(self, token: str, ip: str):
        '#### Регистрация пользователя.'
        dt = self.fetchone("SELECT * FROM temp_regist WHERE token = ?", (token,))
        if not dt:
            return False
        self.delete_temp_reg(token)
        self.create_new_user(token, ip)
        return True
    ## Функции управления пользовательскими данными и аутентификацией ##

