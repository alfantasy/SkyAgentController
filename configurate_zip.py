import os
import zipfile

def get_interactive_config():
    # 1. Имя архива
    default_zip = "main.zip"
    user_zip = input(f"Введите имя архива (по умолчанию '{default_zip}'): ").strip()
    name_zip = user_zip if user_zip else default_zip
    if not name_zip.endswith('.zip'):
        name_zip += '.zip'

    # 2. Корневая папка внутри
    default_root = os.path.splitext(name_zip)[0]
    user_root = input(f"Введите корневую папку внутри архива (по умолчанию '{default_root}'): ").strip()
    root_folder_name = user_root if user_root else default_root

    # 3. Исключения (динамические)
    print("\nПодсказка: введите через запятую имена файлов или папок, которые НУЖНО ИСКЛЮЧИТЬ (например: .env, secrets.py)")
    exclude_input = input("Исключить: ").strip()
    user_excludes = [x.strip() for x in exclude_input.split(',') if x.strip()]

    return name_zip, root_folder_name, user_excludes

def create_zip(zip_name, root_in_zip, items, extra_excludes):
    # Стандартные исключения (вшитые)
    base_excludes = ["__pycache__", ".git", ".ipynb_checkpoints"]
    all_excludes = set(base_excludes + extra_excludes)

    with zipfile.ZipFile(zip_name, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for item in items:
            name = item["name"]
            
            if not os.path.exists(name) or name in all_excludes:
                continue

            if item["type"] == "folder":
                for root, dirs, files in os.walk(name):
                    # Модифицируем dirs для исключения папок из обхода
                    dirs[:] = [d for d in dirs if d not in all_excludes]
                    
                    for file in files:
                        if file in all_excludes:
                            continue
                        
                        file_path = os.path.join(root, file)
                        arcname = os.path.join(root_in_zip, file_path)
                        zipf.write(file_path, arcname)
            
            elif item["type"] == "file":
                arcname = os.path.join(root_in_zip, name)
                zipf.write(name, arcname)

if __name__ == "__main__":
    # Список объектов из твоего ТЗ
    folders_and_file = [
        {"type": "folder", "name": "modules"},
        {"type": "folder", "name": "routers"},
        {"type": "folder", "name": "saved_scripts"},
        {"type": "file", "name": "main.py"},
        {"type": "file", "name": "updater.json"},
        {"type": "file", "name": "requirements.txt"},
        {"type": "file", "name": "config.py"}
    ]

    # Получаем настройки от пользователя
    name_zip, root_folder_name, user_excludes = get_interactive_config()

    try:
        if os.path.exists(name_zip):
            print("❌ Архив с таким именем уже существует. Убираем.")
            os.remove(name_zip)
        create_zip(name_zip, root_folder_name, folders_and_file, user_excludes)
        print(f"\n✅ Готово!")
        print(f"Архив: {name_zip}")
        print(f"Корневая папка внутри: {root_folder_name}/")
        if user_excludes:
            print(f"Исключены пользователем: {', '.join(user_excludes)}")
    except Exception as e:
        print(f"❌ Произошла ошибка: {e}")