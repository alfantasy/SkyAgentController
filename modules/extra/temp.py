import clr
import os

# Подключение DLL
libre_hw_monitor_path = os.path.join(os.getcwd(), "modules", "extra", "LHM", "LibreHardwareMonitorLib.dll")
clr.AddReference(libre_hw_monitor_path)

from LibreHardwareMonitor import Hardware # type: ignore

# Словарь для перевода типов оборудования на русский
HARDWARE_TYPE_TRANSLATION = {
    "Cpu": "Процессор",
    "GpuNvidia": "Видеокарта NVIDIA",
    "GpuAmd": "Видеокарта AMD",
    "GpuIntel": "Видеокарта Intel",
    "Memory": "Оперативная память",
    "Storage": "Жесткий диск",
    "Motherboard": "Материнская плата",
    "Network": "Сетевая карта",
    "Cooler": "Охлаждение",
    "Battery": "Батарея",
    "Psu": "Блок питания"
}

# Словарь для перевода названий датчиков на русский
SENSOR_NAME_TRANSLATION = {
    "CPU Core": "Ядро процессора",
    "CPU Package": "ЦП (общая)",
    "CPU Total": "Нагрузка ЦП",
    "GPU Core": "Графическое ядро",
    "GPU Memory": "Память видеокарты",
    "GPU Fan": "Вентилятор видеокарты",
    "GPU Power": "Питание видеокарты",
    "Temperature": "Температура",
    "Used Space": "Использовано места",
    "Memory Used": "Использовано памяти",
    "Memory Available": "Доступно памяти",
    "Read Activity": "Активность чтения",
    "Write Activity": "Активность записи",
    "Total Activity": "Общая активность",
    "GPU Video Engine": "Нагрузка движка",
    "GPU Bus": "Нагрузка шины",
    "GPU Board Power": "Питание материнской платы",
    "D3D Dedicated": "Выделенная память на D3D",
    "D3D Shared": "Общая память на D3D",
    "D3D 3D": '3D рендер',
    "D3D Overlay": 'Оверлей',
    "D3D Video Decode": 'Декодирование видео',
    "D3D Copy": 'Копирование D3D',
    "D3D Security": 'Безопасность D3D',
    "D3D Video Encode": 'Кодирование видео',
    "D3D VR": 'VR',
    "GPU Hot Spot": 'Тепловая точка',
    "GPU Package": 'Пакет видеокарты',
    "GPU PCIe Rx": 'PCIe Прием',
    "GPU PCIe Tx": 'PCIe Передача',
    "Virtual Memory": 'Виртуальная память',
    "Virtual": 'Виртуальная память',
    "Memory": 'Память',
    "CPU Memory": 'Память процессора',
    "CPU Platform": 'Платформа процессора',
    "Bus Speed": 'Скорость шины',
    "Core Max": 'Максимальная нагрузка ядра',
    "Core Average": 'Средняя нагрузка ядра',
    # Добавьте другие переводы по необходимости
}

def translate_hardware_type(hw_type):
    """Переводит тип оборудования на русский"""
    return HARDWARE_TYPE_TRANSLATION.get(hw_type, hw_type)

def translate_sensor_name(sensor_name):
    """Переводит название датчика на русский"""
    for eng, rus in SENSOR_NAME_TRANSLATION.items():
        if eng in sensor_name:
            return sensor_name.replace(eng, rus)
    return sensor_name

def get_temperatures():
    computer = Hardware.Computer()
    computer.IsCpuEnabled = True
    computer.IsGpuEnabled = True
    computer.IsMemoryEnabled = True
    computer.IsMotherboardEnabled = True
    computer.IsStorageEnabled = True
    computer.Open()

    hardware_data = {}

    for hardware in computer.Hardware:
        hardware.Update()
        hardware_type = str(hardware.HardwareType)
        hardware_name = hardware.Name.strip()
        
        if hardware_type not in hardware_data:
            hardware_data[hardware_type] = {}

        if hardware_name not in hardware_data[hardware_type]:
            hardware_data[hardware_type][hardware_name] = {}

        for sensor in hardware.Sensors:
            sensor_name = sensor.Name.strip()
            sensor_value = sensor.Value

            if sensor_value is not None:
                rounded_value = round(float(sensor_value), 1)
                translated_name = translate_sensor_name(sensor_name)
                hardware_data[hardware_type][hardware_name][translated_name] = rounded_value

    return hardware_data