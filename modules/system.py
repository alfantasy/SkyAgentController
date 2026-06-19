import platform
import time
from fastapi import HTTPException, Response
import base64, os, uuid, psutil, mss, io
from PIL import Image

from modules.extra.temp import get_temperatures, translate_hardware_type, translate_sensor_name

class System:
    '''
    #### Управление системой при помощи сторонних библиотек, а также внутренних запросов.
    '''
    def __init__(self):
        pass

    def get_mac_address_network(self):
        '''
        #### Получение MAC-Address сетевого интерфейса на запущенном ПК.
        '''
        mac = ':'.join(['{:02x}'.format((uuid.getnode() >> elements) & 0xff) for elements in range(0,2*6,2)][::-1])
        return mac
    
    def get_cpu(self):
        '''
        #### Получение информации о процессоре.
        '''
        cpu = psutil.cpu_percent(5)
        return cpu
    
    def get_ram_procent(self):
        '''
        #### Получение информации о памяти.
        '''
        ram = psutil.virtual_memory()[2]
        return ram
    
    def get_ram_int(self):
        '''
        #### Получение информации о памяти.
        '''
        ram = psutil.virtual_memory()[3]/1000000000
        return ram
    
    def get_disk(self):
        '''
        #### Получение информации об объеме дискового пространства.
        '''
        disk = psutil.disk_usage('/').percent
        return disk
    
    def get_disk_int(self):
        '''
        #### Получение информации об объеме дискового пространства.
        '''
        disk = psutil.disk_usage('/').total/1000000000
        return disk
    
    def get_disk_free(self):
        '''
        #### Получение информации о свободном дисковом пространстве.
        '''
        disk = psutil.disk_usage('/').free/1000000000
        return disk
    
    def get_disk_free_int(self):
        '''
        #### Получение информации о свободном дисковом пространстве.
        '''
        disk = psutil.disk_usage('/').free
        return disk 
    
    def get_swap(self):
        '''
        #### Получение информации об объеме свап-пространства.
        '''
        swap = psutil.swap_memory().total
        return swap
    
    def get_swap_int(self):
        '''
        #### Получение информации об объеме свап-пространства.
        '''
        swap = psutil.swap_memory().total/1000000000
        return swap
    
    def get_swap_free(self):
        '''
        #### Получение информации о свободном свап-пространстве.
        '''
        swap = psutil.swap_memory().free
        return swap
    
    def data_hardware(self):
        '''
        #### Получение глобальной информации об оборудовании.
        '''
        return get_temperatures()
    
    def tr_h_type(self, type):
        '''
        #### Перевод типа оборудования.
        '''
        return translate_hardware_type(type)
    
    def kill_process(self, pid):
        try:
            proc = psutil.Process(pid)
            proc.terminate()  # или proc.kill()
            proc.wait(timeout=3)
            return {"status": "ok"}
        except psutil.NoSuchProcess:
            return {"error": "process_not_found"}
        except Exception as e:
            return {"error": str(e)}

    def get_filtered_process_list(self):
        process_list = []
        system_accounts = {
            'NT AUTHORITY\\СИСТЕМА',
            'NT AUTHORITY\\SYSTEM',
            'NT AUTHORITY\\LOCAL SERVICE',
            'NT AUTHORITY\\NETWORK SERVICE'  # Добавляем на случай, если нужно исключить и его
        }
        
        for proc in psutil.process_iter(['pid', 'name', 'username', 'exe']):
            try:
                process_info = proc.as_dict(attrs=['pid', 'name', 'username', 'exe'])
                
                # Пропускаем системные процессы
                if process_info['username'] in system_accounts:
                    continue
                    
                process_list.append(process_info)
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
        
        # Сортируем процессы по имени (без учета регистра)
        return sorted(process_list, key=lambda x: x['name'].lower())    

    def format_temp(self) -> list:
        not_sensors = ['Скорость шины', '3D рендер', "VR", 'PCIe Прием', 'PCIe Передача', 'Безопасность D3D', 'Копирование D3D', 'Оверлей', '3D рендер', "GPU Video Engine", "CPU Память", "Нагрузка движка", "Нагрузка шины", "D3D Dedicated Использовано памяти", "D3D Shared Использовано памяти", "Пакет видеокарты", "Ядро процессора #1", "Ядро процессора #2", "Ядро процессора #3", "Ядро процессора #4", "Питание материнской платы", "Платформа процессора", "Ядро процессора", "Декодирование видео", "Кодирование видео", "Ядро процессораs"]
        list_temp = []
        temp = self.data_hardware()
        for data_type in temp:
            rus_type = self.tr_h_type(data_type)
            for device in temp[data_type]:
                for sensor in temp[data_type][device]:
                    if sensor in not_sensors:
                        continue
                    list_temp.append({"type": rus_type, "device": device, "sensor": sensor, "temp": temp[data_type][device][sensor]})
        return list_temp

    def get_ram_info(self):
        ram = psutil.virtual_memory()
        return {
            "total": f"{ram.total / (1024**3):.1f}GB",
            "used": f"{ram.used / (1024**3):.1f}GB",
            "percent": ram.percent
        }
    
    def get_heavy_processes(self):
        heavy_processes = []
        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
            try:
                heavy_processes.append({
                    "pid": proc.pid,
                    "name": proc.name(),
                    "cpu": f"{proc.cpu_percent()}%",
                    "ram": f"{proc.memory_percent():.1f}%"  # округлим для красоты
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue

        heavy_processes = sorted(heavy_processes, key=lambda x: float(x['ram'].replace('%', '')), reverse=True)[:5]
        return heavy_processes
    
    def get_services(self):
        services_list = []
        if platform.system() == "Windows":
            import win32service # type: ignore
            if win32service:
                try:
                    access = win32service.SC_MANAGER_ENUMERATE_SERVICE | win32service.SC_MANAGER_CONNECT
                    scm = win32service.OpenSCManager(None, None, access)
                    type_filter = win32service.SERVICE_WIN32
                    state_filter = win32service.SERVICE_STATE_ALL
                    statuses = win32service.EnumServicesStatusEx(scm, type_filter, state_filter, None)
                    
                    for service in statuses:
                        # 🎯 БРОНЕБОЙНЫЙ ОПРЕДЕЛИТЕЛЬ СТАТУСА:
                        # В разных версиях pywin32 статус лежит либо в 'ServiceStatusProcess', либо прямо в корне
                        status_info = service.get('ServiceStatusProcess') or service
                        current_state = status_info.get('CurrentState')

                        if current_state == win32service.SERVICE_RUNNING:
                            services_list.append({
                                "name": service.get('ServiceName', 'Unknown'),
                                "display": service.get('DisplayName', 'Unknown'),
                                "status": "RUNNING"
                            })
                            
                    # Опционально: срезаем до первых 20 запущенных, чтобы не перегружать сеть
                    services_list = services_list[:20]
                    return services_list
                except Exception as e:
                    services_list = [{"error": f"Failed to get Win services: {str(e)}"}]  
                    return services_list

    def get_autostart_programs(self):
        autostart_list = []
        try:
            import winreg
            paths = [
                (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run"),
                (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Run")
            ]
            for hive, path in paths:
                try:
                    with winreg.OpenKey(hive, path, 0, winreg.KEY_READ) as key:
                        for i in range(winreg.QueryInfoKey(key)[1]):
                            name, val, _ = winreg.EnumValue(key, i)
                            autostart_list.append({"name": name, "path": val})
                except FileNotFoundError:
                    continue
            return autostart_list
        except Exception as e:
            autostart_list = [{"error": f"Failed to get Win autostart: {str(e)}"}]
            return autostart_list         
        
    def get_os_info(self):
        uptime_seconds = time.time() - psutil.boot_time()
        hours, remainder = divmod(int(uptime_seconds), 3600)
        minutes, seconds = divmod(remainder, 60)
        return {
            "name": platform.system(),
            "release": platform.version(),
            "type_release": platform.release(),
            "arch": platform.machine(),
            "uptime": f"{hours}h {minutes}m"
        }
    
    def get_cpu_info(self):
        return {
            "model": platform.processor(),
            "usage": psutil.cpu_percent(interval=1),
            "cores": psutil.cpu_count(logical=True),
            "freq": f"{psutil.cpu_freq().current:.0f}MHz" if psutil.cpu_freq() else "N/A"
        }
    
    def info_system(self, choice: list = None):
        if choice is None:
            choice = ["cpu", "ram", "os", "drives", "temp", "services", "heavy_processes", "autostart"]
        data_reject = {
            "cpu": self.get_cpu_info() if choice and "cpu" in choice else None,
            "ram": self.get_ram_info() if choice and "ram" in choice else None,
            "os": self.get_os_info() if choice and "os" in choice else None,
            "drives": self.get_all_drives() if choice and "drives" in choice else None,
            "temp": self.format_temp() if choice and "temp" in choice else None,
            "unique": {
                "services": self.get_services() if choice and "services" in choice else None,
                "heavy_processes": self.get_heavy_processes() if choice and "heavy_processes" in choice else None,
                "autostart": self.get_autostart_programs() if choice and "autostart" in choice else None
            }     
        }
        return data_reject
    

    def get_all_drives(self):
        drives = []
        for part in psutil.disk_partitions():
            # Игнорируем CD-ROM и диски без файловой системы, чтобы не вылетало ошибок
            if not part.fstype:
                continue
                
            try:
                usage = psutil.disk_usage(part.mountpoint)
                drives.append({
                    "device": part.device,
                    "mountpoint": part.mountpoint,
                    "fstype": part.fstype,
                    "total_int": usage.total,
                    "total_percent": usage.percent,
                    "available_int": usage.free,
                    "usage_int": usage.used,
                    # Добавим для удобства форматированные значения или статус
                    "status": "active"
                })
            except (PermissionError, OSError):
                # Это на случай заблокированных дисков или пустых картридеров
                continue
                
        return drives

    def get_monitors(self):
        with mss.mss() as sct:
            monitors = []
            for i, m in enumerate(sct.monitors[1:], 1):
                monitors.append({
                    "id": i,
                    "width": m["width"],
                    "height": m["height"],
                    "name": f"Monitor {i} ({m['width']}x{m['height']})",
                })
        return monitors    

    def screenshot_reject(self, monitor_id: int, quality: int):
        with mss.mss() as sct:
            if monitor_id >= len(sct.monitors):
                raise HTTPException(status_code=404, detail="Monitor not found")
            
            monitor = sct.monitors[monitor_id]
            sct_img = sct.grab(monitor)
            
            # Конвертируем в PIL
            img = Image.frombytes("RGB", sct_img.size, sct_img.rgb)
            
            # Оптимизируем: сохраняем в JPEG с выбранным качеством для скорости
            buffered = io.BytesIO()
            img.save(buffered, format="JPEG", quality=quality)
            
            # Возвращаем байты напрямую с правильным media_type
            return Response(content=buffered.getvalue(), media_type="image/jpeg")
        
    def check_admin(self):
        """Выполнение проверки, является ли авторизированный клиент

        администратором в системе или нет.
        """
        sys_platform = platform.system()

        if sys_platform == "Windows":
            try:
                # IsUserAnAdmin() возвращает 1, если запущено от админа, и 0 в противном случае
                import ctypes
                return ctypes.windll.shell32.IsUserAnAdmin() != 0
            except Exception:
                # На случай, если вызов сорвется в специфичном окружении
                return False

        elif sys_platform == "Linux":
            try:
                # На Linux UID или эффективный UID (euid) у root всегда равен 0
                return os.geteuid() == 0
            except AttributeError:
                # Фолбэк на обычный getuid, если euid почему-то недоступен
                return os.getuid() == 0

        return False