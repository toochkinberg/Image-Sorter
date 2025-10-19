import os
import shutil
import pandas as pd
import matplotlib.pyplot as plt
import streamlit as st
import streamlit_hotkeys as hotkeys
import random
from dotenv import load_dotenv
import threading
from datetime import datetime

load_dotenv()

############ ALL CONSTANTS FROM .ENV ############
SOURCE_DIR = os.getenv('SOURCE_DIR')
BATCH1_DIR = os.getenv('BATCH1_DIR')
BATCH2_DIR = os.getenv('BATCH2_DIR')
BATCH3_DIR = os.getenv('BATCH3_DIR')
DETAILS_DIR = os.getenv('DETAILS_DIR')
DAMAGES_DIR = os.getenv('DAMAGES_DIR')
TRASH_DIR = os.getenv('TRASH_DIR')
BROKEN_DIR = os.getenv('BROKEN_DIR')
ACTION_HISTORY_FILE = os.getenv('ACTION_HISTORY_FILE', 'action_history.log')

# Batch directories mapping
BATCH_DIRS = {
    "lev": BATCH1_DIR,
    "dan": BATCH2_DIR,
    "yura": BATCH3_DIR
}

# All managed directories
MANAGED_DIRS = [DETAILS_DIR, DAMAGES_DIR, TRASH_DIR, BROKEN_DIR]

# All source-like directories (for stats and viewing)
ALL_SOURCE_DIRS = [SOURCE_DIR, BATCH1_DIR, BATCH2_DIR, BATCH3_DIR]

# Test user IDs
USER_IDS = os.getenv('USER_IDS', 'admin,1,2,3').split(',')

hotkeys.activate([
    hotkeys.hk("action_q", "q"),  # Q для действий на Q (детали или возврат в source)
    hotkeys.hk("action_q", "й"),  # Й для действий на Q
    hotkeys.hk("action_w", "w"),  # W для повреждений
    hotkeys.hk("action_w", "ц"),  # Ц для повреждений
    hotkeys.hk("action_e", "e"),  # E для "Чёто не то"
    hotkeys.hk("action_e", "у"),  # У для "Чёто не то"
    hotkeys.hk("action_del", "Delete"),  # Delete для корзины или удаления
])

# Create directories
def create_directories():
    for dir_name in list(BATCH_DIRS.values()) + MANAGED_DIRS:
        os.makedirs(dir_name, exist_ok=True)

# Get all image files in a directory
def get_images_in_dir(directory):
    if directory is None or not os.path.exists(directory):
        return []
    images = []
    for file in os.listdir(directory):
        if file.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp')):
            images.append(os.path.join(directory, file))
    return sorted(images)

# Calculate folder stats
def get_folder_stats(directory):
    if directory is None or not os.path.exists(directory):
        return 0, 0.0
    count = 0
    total_size = 0
    for file in os.listdir(directory):
        file_path = os.path.join(directory, file)
        if os.path.isfile(file_path):
            count += 1
            total_size += os.path.getsize(file_path)
    return count, total_size / (1024 * 1024)  # Size in MB

# Log action to file thread-safely
log_lock = threading.Lock()

def log_action(user_id, filename, action):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"{timestamp} | {user_id} | {filename} | {action}"
    with log_lock:
        with open(ACTION_HISTORY_FILE, 'a') as f:
            f.write(log_entry + '\n')

# Read action history from file
def read_action_history():
    if not os.path.exists(ACTION_HISTORY_FILE):
        return []
    history = []
    with open(ACTION_HISTORY_FILE, 'r') as f:
        for line in f:
            parts = line.strip().split(' | ')
            if len(parts) == 4:
                history.append({
                    "Время": parts[0],
                    "Пользователь": parts[1],
                    "Файл": parts[2],
                    "Действие": parts[3]
                })
    # Reverse the list to show newest first
    history.reverse()
    return history

create_directories()
st.title("Image Sorter")
st.header("Распределение по папкам")

st.sidebar.header("Вход пользователя")
user_id = st.sidebar.text_input("Введите ID пользователя", "")
if user_id not in USER_IDS:
    st.sidebar.error("Неверный ID пользователя.")
    st.stop()
st.sidebar.success("Успех!")

# Get user's source dir
user_source_dir = SOURCE_DIR if user_id == "admin" else BATCH_DIRS.get(user_id, SOURCE_DIR)

# Get remaining source images based on user
if user_id == "admin":
    remaining_source_images = []
    for bdir in list(BATCH_DIRS.values()) + [SOURCE_DIR]:
        remaining_source_images.extend(get_images_in_dir(bdir))
else:
    remaining_source_images = get_images_in_dir(user_source_dir)

# Initialize session state for indices
if 'current_sort_index' not in st.session_state:
    st.session_state['current_sort_index'] = 0
if 'current_trash_index' not in st.session_state:
    st.session_state['current_trash_index'] = 0
if 'current_broken_index' not in st.session_state:
    st.session_state['current_broken_index'] = 0

tab1, tab2, tab3, tab4 = st.tabs(["Стата", "Предпросмотр", "Сортировка", "Журнал (плейбой чи шо)"])

with tab1:
    # Collect info for source and batch stats
    source_data = []
    batch_total_count = 0
    batch_total_size = 0
    folder_names = {
        SOURCE_DIR: "Исходные (SOURCE)",
        BATCH1_DIR: "Батч 1",
        BATCH2_DIR: "Батч 2",
        BATCH3_DIR: "Батч 3"
    }
    for dir_name in [d for d in ALL_SOURCE_DIRS if d]:
        count, size = get_folder_stats(dir_name)
        name = folder_names.get(dir_name, dir_name)
        source_data.append({
            "Папка": name,
            "Количество изображений": count,
            "Размер (GB)": f"{size / 1024:.3f}"
        })
        if dir_name in BATCH_DIRS.values():
            batch_total_count += count
            batch_total_size += size

    source_data.append({
        "Папка": "Итого в батчах",
        "Количество изображений": batch_total_count,
        "Размер (GB)": f"{batch_total_size / 1024:.3f}"
    })

    # Collect info for managed dirs stats
    managed_data = []
    managed_total_count = 0
    managed_total_size = 0
    for dir_name in [d for d in MANAGED_DIRS if d]:
        count, size = get_folder_stats(dir_name)
        managed_data.append({
            "Папка": dir_name,
            "Количество изображений": count,
            "Размер (GB)": f"{size / 1024:.3f}"
        })
        managed_total_count += count
        managed_total_size += size

    # Total stats
    total_data = [{
        "Папка": "Итого",
        "Количество изображений": batch_total_count + managed_total_count,
        "Размер (GB)": f"{(batch_total_size + managed_total_size) / 1024:.3f}"
    }]

    # Display tables
    st.write("### Исходные и батчи")
    st.dataframe(pd.DataFrame(source_data), use_container_width=True)

    st.write("### Категории сортировки")
    st.dataframe(pd.DataFrame(managed_data), use_container_width=True)

    st.write("### Общий итог")
    st.dataframe(pd.DataFrame(total_data), use_container_width=True)

    # Pie chart for source and batch dirs
    labels = [row["Папка"] for row in source_data if row["Папка"] != "Итого в батчах"]
    counts = [row["Количество изображений"] for row in source_data if row["Папка"] != "Итого в батчах"]
    if sum(counts) > 0:
        fig, ax = plt.subplots()
        ax.pie(counts, labels=labels, autopct="%1.1f%%", colors=["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728"])
        ax.set_title("Распределение количества изображений по исходным и батчам")
        st.write("### Распределение по исходным и батчам")
        st.pyplot(fig)

    # Pie chart for managed dirs
    labels = [row["Папка"] for row in managed_data]
    counts = [row["Количество изображений"] for row in managed_data]
    if sum(counts) > 0:
        fig, ax = plt.subplots()
        ax.pie(counts, labels=labels, autopct="%1.1f%%", colors=["#9467bd", "#8c564b", "#e377c2", "#7f7f7f"])
        ax.set_title("Распределение количества изображений по категориям")
        st.write("### Распределение по категориям сортировки")
        st.pyplot(fig)

    # Functionality for admin: Distribute files from SOURCE_DIR to batch dirs
    if user_id == "admin":
        st.subheader("Распределение файлов из SOURCE_DIR в батчи")
        source_images = get_images_in_dir(SOURCE_DIR)
        st.write(f"Изображений в SOURCE_DIR: {len(source_images)}")

        if len(source_images) > 0:
            if st.button("Распределить равномерно между батчами"):
                random.shuffle(source_images)
                batch_size = len(source_images) // 3
                batches = {
                    "lev": source_images[:batch_size],
                    "dan": source_images[batch_size:2*batch_size],
                    "yura": source_images[2*batch_size:]
                }
                moved_counts = {"lev": 0, "dan": 0, "yura": 0}
                for uid, paths in batches.items():
                    batch_dir = BATCH_DIRS[uid]
                    os.makedirs(batch_dir, exist_ok=True)
                    for p in paths:
                        shutil.move(p, os.path.join(batch_dir, os.path.basename(p)))
                        moved_counts[uid] += 1
                # Log summary
                log_action(user_id, "Распределение по батчам", f"Равномерно распределено {len(source_images)} изображений")
                st.success("Изображения распределены равномерно по батчам.")
                st.rerun()

            selected_uid = st.selectbox("Выбрать батч для всех файлов", ["1", "2", "3"])
            if st.button("Закинуть все в выбранный батч"):
                batch_dir = BATCH_DIRS[selected_uid]
                os.makedirs(batch_dir, exist_ok=True)
                moved_count = 0
                for p in source_images:
                    shutil.move(p, os.path.join(batch_dir, os.path.basename(p)))
                    moved_count += 1
                # Log summary
                summary = f"Перемещено {moved_count} изображений в батч {selected_uid}"
                log_action(user_id, "Распределение в батч", summary)
                st.success(f"Все изображения добавлены в батч {selected_uid}.")
                st.rerun()
        else:
            st.write("Нет изображений в SOURCE_DIR для распределения.")

with tab2:
    st.header("Просмотр по папкам")
    if user_id == "admin":
        folder_options = ["Исходные (SOURCE)", "Батч 1", "Батч 2", "Батч 3", "Все батчи"] + MANAGED_DIRS
    else:
        folder_options = ["Мой батч"] + MANAGED_DIRS
    folder = st.selectbox("Выберите папку", folder_options)
    dir_mapping = {
        "Исходные (SOURCE)": SOURCE_DIR,
        "Батч 1": BATCH1_DIR,
        "Батч 2": BATCH2_DIR,
        "Батч 3": BATCH3_DIR,
        "Мой батч": user_source_dir
    }
    if folder == "Все батчи":
        images = []
        for bdir in BATCH_DIRS.values():
            images.extend(get_images_in_dir(bdir))
        images = sorted(images)
    else:
        dir_path = dir_mapping.get(folder, folder)
        images = get_images_in_dir(dir_path)
    
    if images:
        # Pagination options
        per_page_options = [50, 100, 200, "Custom", "All"]
        per_page_choice = st.selectbox("Количество изображений на странице", per_page_options)
        
        if per_page_choice == "Custom":
            per_page = st.number_input("Введите количество", min_value=1, value=50)
        elif per_page_choice == "All":
            per_page = len(images)
        else:
            per_page = per_page_choice
        
        total_pages = (len(images) + per_page - 1) // per_page if per_page < len(images) else 1
        
        current_page = st.selectbox("Страница", range(1, total_pages + 1)) if total_pages > 1 else 1
        
        start_idx = (current_page - 1) * per_page
        end_idx = start_idx + per_page
        images_to_show = images[start_idx:end_idx]
        
        # Grid display
        num_columns = 5
        for i in range(0, len(images_to_show), num_columns):
            cols = st.columns(num_columns)
            for j, col in enumerate(cols):
                if i + j < len(images_to_show):
                    img_path = images_to_show[i + j]
                    try:
                        col.image(img_path)
                        col.write(os.path.basename(img_path))
                    except:
                        col.write(f"Ошибка загрузки: {os.path.basename(img_path)}")
    else:
        st.write("Нет изображений для просмотра.")

with tab3:
    mode2 = st.selectbox("Выберите режим сортировки", [
        "Режим общей сортировки",
        "Режим удаления (из Корзины)",
        "Режим удаления (из необработанного)"
    ])

    if mode2 == "Режим общей сортировки":
        st.header("Режим общей сортировки")
        if remaining_source_images:
            current_index = st.session_state['current_sort_index']
            if current_index >= len(remaining_source_images):
                current_index = 0
                st.session_state['current_sort_index'] = 0
            img_path = remaining_source_images[current_index]
            try:
                st.image(img_path, use_container_width=True)
                st.write(os.path.basename(img_path))
            except:
                st.write(f"Ошибка загрузки: {img_path}")
                shutil.move(img_path, os.path.join(BROKEN_DIR, os.path.basename(img_path)))
                log_action(user_id, os.path.basename(img_path), f"Перемещено в {BROKEN_DIR} (автоматически)")
                st.session_state['current_sort_index'] = min(current_index + 1, len(remaining_source_images) - 1)
                st.rerun()

            # Обработка хоткеев для общей сортировки
            action_performed = False
            if hotkeys.pressed("action_q"):  # Q/й для "Детали"
                try:
                    shutil.move(img_path, os.path.join(DETAILS_DIR, os.path.basename(img_path)))
                    log_action(user_id, os.path.basename(img_path), f"Перемещено в {DETAILS_DIR}")
                    st.session_state['current_sort_index'] = min(current_index + 1, len(remaining_source_images) - 1)
                    st.success(f"Изображение перемещено в {DETAILS_DIR}")
                    action_performed = True
                except Exception as e:
                    st.error(f"Ошибка перемещения в {DETAILS_DIR}: {e}")
            elif hotkeys.pressed("action_w"):  # W/ц для "Повреждения"
                try:
                    shutil.move(img_path, os.path.join(DAMAGES_DIR, os.path.basename(img_path)))
                    log_action(user_id, os.path.basename(img_path), f"Перемещено в {DAMAGES_DIR}")
                    st.session_state['current_sort_index'] = min(current_index + 1, len(remaining_source_images) - 1)
                    st.success(f"Изображение перемещено в {DAMAGES_DIR}")
                    action_performed = True
                except Exception as e:
                    st.error(f"Ошибка перемещения в {DAMAGES_DIR}: {e}")
            elif hotkeys.pressed("action_e"):  # E/у для "Чёто не то"
                try:
                    shutil.move(img_path, os.path.join(BROKEN_DIR, os.path.basename(img_path)))
                    log_action(user_id, os.path.basename(img_path), f"Перемещено в {BROKEN_DIR}")
                    st.session_state['current_sort_index'] = min(current_index + 1, len(remaining_source_images) - 1)
                    st.success(f"Изображение перемещено в {BROKEN_DIR}")
                    action_performed = True
                except Exception as e:
                    st.error(f"Ошибка перемещения в {BROKEN_DIR}: {e}")
            elif hotkeys.pressed("action_del"):  # Delete для "Корзина"
                try:
                    shutil.move(img_path, os.path.join(TRASH_DIR, os.path.basename(img_path)))
                    log_action(user_id, os.path.basename(img_path), f"Перемещено в {TRASH_DIR}")
                    st.session_state['current_sort_index'] = min(current_index + 1, len(remaining_source_images) - 1)
                    st.success(f"Изображение перемещено в {TRASH_DIR}")
                    action_performed = True
                except Exception as e:
                    st.error(f"Ошибка перемещения в {TRASH_DIR}: {e}")

            # Кнопки
            col1, col2, col3, col4 = st.columns(4)
            if col1.button("Детали (Q)"):
                try:
                    shutil.move(img_path, os.path.join(DETAILS_DIR, os.path.basename(img_path)))
                    log_action(user_id, os.path.basename(img_path), f"Перемещено в {DETAILS_DIR}")
                    st.session_state['current_sort_index'] = min(current_index + 1, len(remaining_source_images) - 1)
                    st.success(f"Изображение перемещено в {DETAILS_DIR}")
                    st.rerun()
                except Exception as e:
                    st.error(f"Ошибка перемещения в {DETAILS_DIR}: {e}")
            if col2.button("Повреждения (W)"):
                try:
                    shutil.move(img_path, os.path.join(DAMAGES_DIR, os.path.basename(img_path)))
                    log_action(user_id, os.path.basename(img_path), f"Перемещено в {DAMAGES_DIR}")
                    st.session_state['current_sort_index'] = min(current_index + 1, len(remaining_source_images) - 1)
                    st.success(f"Изображение перемещено в {DAMAGES_DIR}")
                    st.rerun()
                except Exception as e:
                    st.error(f"Ошибка перемещения в {DAMAGES_DIR}: {e}")
            if col3.button("Чёто не то (E)"):
                try:
                    shutil.move(img_path, os.path.join(BROKEN_DIR, os.path.basename(img_path)))
                    log_action(user_id, os.path.basename(img_path), f"Перемещено в {BROKEN_DIR}")
                    st.session_state['current_sort_index'] = min(current_index + 1, len(remaining_source_images) - 1)
                    st.success(f"Изображение перемещено в {BROKEN_DIR}")
                    st.rerun()
                except Exception as e:
                    st.error(f"Ошибка перемещения в {BROKEN_DIR}: {e}")
            if col4.button("Корзина (DEL)"):
                try:
                    shutil.move(img_path, os.path.join(TRASH_DIR, os.path.basename(img_path)))
                    log_action(user_id, os.path.basename(img_path), f"Перемещено в {TRASH_DIR}")
                    st.session_state['current_sort_index'] = min(current_index + 1, len(remaining_source_images) - 1)
                    st.success(f"Изображение перемещено в {TRASH_DIR}")
                    st.rerun()
                except Exception as e:
                    st.error(f"Ошибка перемещения в {TRASH_DIR}: {e}")

            # Вызываем rerun только после успешного действия
            if action_performed:
                st.rerun()
        else:
            st.write("Все изображения из вашей директории отсортированы.")

    elif mode2 == "Режим удаления (из Корзины)":
        st.header("Режим удаления из Корзины")
        trash_images = get_images_in_dir(TRASH_DIR)
        if trash_images:
            current_index = st.session_state['current_trash_index']
            if current_index >= len(trash_images):
                current_index = 0
                st.session_state['current_trash_index'] = 0
            img_path = trash_images[current_index]
            try:
                st.image(img_path, use_container_width=True)
                st.write(os.path.basename(img_path))
            except:
                st.write(f"Ошибка загрузки: {img_path}")

            # Обработка хоткеев
            action_performed = False
            if hotkeys.pressed("action_q"):  # Q/й для "Детали"
                try:
                    shutil.move(img_path, os.path.join(DETAILS_DIR, os.path.basename(img_path)))
                    log_action(user_id, os.path.basename(img_path), f"Перемещено в {DETAILS_DIR}")
                    st.session_state['current_trash_index'] = min(current_index + 1, len(trash_images) - 1)
                    st.success(f"Изображение перемещено в {DETAILS_DIR}")
                    action_performed = True
                except Exception as e:
                    st.error(f"Ошибка перемещения в {DETAILS_DIR}: {e}")
            elif hotkeys.pressed("action_w"):  # W/ц для "Повреждения"
                try:
                    shutil.move(img_path, os.path.join(DAMAGES_DIR, os.path.basename(img_path)))
                    log_action(user_id, os.path.basename(img_path), f"Перемещено в {DAMAGES_DIR}")
                    st.session_state['current_trash_index'] = min(current_index + 1, len(trash_images) - 1)
                    st.success(f"Изображение перемещено в {DAMAGES_DIR}")
                    action_performed = True
                except Exception as e:
                    st.error(f"Ошибка перемещения в {DAMAGES_DIR}: {e}")
            elif hotkeys.pressed("action_del"):  # Delete для удаления
                try:
                    os.remove(img_path)
                    log_action(user_id, os.path.basename(img_path), "Удалено")
                    st.session_state['current_trash_index'] = min(current_index + 1, len(trash_images) - 1)
                    st.success("Изображение удалено")
                    action_performed = True
                except Exception as e:
                    st.error(f"Ошибка удаления: {e}")

            # Кнопки
            col1, col2, col3 = st.columns(3)
            if col1.button("Детали (Q)"):
                try:
                    shutil.move(img_path, os.path.join(DETAILS_DIR, os.path.basename(img_path)))
                    log_action(user_id, os.path.basename(img_path), f"Перемещено в {DETAILS_DIR}")
                    st.session_state['current_trash_index'] = min(current_index + 1, len(trash_images) - 1)
                    st.success(f"Изображение перемещено в {DETAILS_DIR}")
                    st.rerun()
                except Exception as e:
                    st.error(f"Ошибка перемещения в {DETAILS_DIR}: {e}")
            if col2.button("Повреждения (W)"):
                try:
                    shutil.move(img_path, os.path.join(DAMAGES_DIR, os.path.basename(img_path)))
                    log_action(user_id, os.path.basename(img_path), f"Перемещено в {DAMAGES_DIR}")
                    st.session_state['current_trash_index'] = min(current_index + 1, len(trash_images) - 1)
                    st.success(f"Изображение перемещено в {DAMAGES_DIR}")
                    st.rerun()
                except Exception as e:
                    st.error(f"Ошибка перемещения в {DAMAGES_DIR}: {e}")
            if col3.button("Удалить (DEL)"):
                try:
                    os.remove(img_path)
                    log_action(user_id, os.path.basename(img_path), "Удалено")
                    st.session_state['current_trash_index'] = min(current_index + 1, len(trash_images) - 1)
                    st.success("Изображение удалено")
                    st.rerun()
                except Exception as e:
                    st.error(f"Ошибка удаления: {e}")

            # Вызываем rerun только после успешного действия
            if action_performed:
                st.rerun()
        else:
            st.write("Нет изображений в Корзине.")

    elif mode2 == "Режим удаления (из необработанного)":
        st.header("Режим удаления из необработанного")
        broken_images = get_images_in_dir(BROKEN_DIR)
        if broken_images:
            current_index = st.session_state['current_broken_index']
            if current_index >= len(broken_images):
                current_index = 0
                st.session_state['current_broken_index'] = 0
            img_path = broken_images[current_index]
            try:
                st.image(img_path, use_container_width=True)
                st.write(os.path.basename(img_path))
            except:
                st.write(f"Ошибка загрузки: {img_path}")

            # Обработка хоткеев для режима удаления из необработанного
            action_performed = False
            if hotkeys.pressed("action_q"):  # Q/й для "Вернуть в Source"
                try:
                    shutil.move(img_path, os.path.join(SOURCE_DIR, os.path.basename(img_path)))
                    log_action(user_id, os.path.basename(img_path), "Возвращено в Source")
                    st.session_state['current_broken_index'] = min(current_index + 1, len(broken_images) - 1)
                    st.success("Изображение возвращено в Source")
                    action_performed = True
                except Exception as e:
                    st.error(f"Ошибка перемещения в Source: {e}")
            elif hotkeys.pressed("action_del"):  # Delete для удаления
                try:
                    os.remove(img_path)
                    log_action(user_id, os.path.basename(img_path), "Удалено")
                    st.session_state['current_broken_index'] = min(current_index + 1, len(broken_images) - 1)
                    st.success("Изображение удалено")
                    action_performed = True
                except Exception as e:
                    st.error(f"Ошибка удаления: {e}")

            # Кнопки
            col1, col2 = st.columns(2)
            if col1.button("Вернуть в Source (Q)"):
                try:
                    shutil.move(img_path, os.path.join(SOURCE_DIR, os.path.basename(img_path)))
                    log_action(user_id, os.path.basename(img_path), "Возвращено в Source")
                    st.session_state['current_broken_index'] = min(current_index + 1, len(broken_images) - 1)
                    st.success("Изображение возвращено в Source")
                    st.rerun()
                except Exception as e:
                    st.error(f"Ошибка перемещения в Source: {e}")
            if col2.button("Удалить (DEL)"):
                try:
                    os.remove(img_path)
                    log_action(user_id, os.path.basename(img_path), "Удалено")
                    st.session_state['current_broken_index'] = min(current_index + 1, len(broken_images) - 1)
                    st.success("Изображение удалено")
                    st.rerun()
                except Exception as e:
                    st.error(f"Ошибка удаления: {e}")

            # Вызываем rerun только после успешного действия
            if action_performed:
                st.rerun()
        else:
            st.write("Нет изображений в необработанном.")

with tab4:
    st.header("Журнал действий")
    history = read_action_history()
    if history:
        df = pd.DataFrame(history)
        # Pagination for history
        per_page = 50
        total_pages = (len(df) + per_page - 1) // per_page if per_page < len(df) else 1
        current_page = st.selectbox("Страница", range(1, total_pages + 1)) if total_pages > 1 else 1
        start_idx = (current_page - 1) * per_page
        end_idx = start_idx + per_page
        df_page = df.iloc[start_idx:end_idx]
        st.dataframe(df_page, use_container_width=True)
    else:
        st.write("Журнал пуст или файл отсутствует.")