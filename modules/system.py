import platform
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

    def info_system(self, hours, minutes):
        ram = psutil.virtual_memory()
        data_reject = {
            "cpu": {
                "model": platform.processor(),
                "usage": psutil.cpu_percent(interval=1),
                "cores": psutil.cpu_count(logical=True),
                "freq": f"{psutil.cpu_freq().current:.0f}MHz" if psutil.cpu_freq() else "N/A"                
            },
            "ram": {
                "total": f"{ram.total / (1024**3):.1f}GB",
                "used": f"{ram.used / (1024**3):.1f}GB",
                "percent": ram.percent
            },
            "os": {
                "name": platform.system(),
                "release": platform.version(),
                "arch": platform.machine(),
                "uptime": f"{hours}h {minutes}m"
            },
            "temp": self.format_temp()            
        }
        return data_reject
    
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