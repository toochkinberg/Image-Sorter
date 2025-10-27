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
import json
from PIL import Image

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
TEMP_PREVIEW_DIR = os.getenv('TEMP_PREVIEW_DIR')
TEMP_BUFFER_DIR = os.getenv('TEMP_BUFFER_DIR')
STATS_CACHE_FILE = os.getenv('STATS_CACHE_FILE', 'stats_cache.json')

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
    hotkeys.hk("action_q", "q"),
    hotkeys.hk("action_q", "й"),
    hotkeys.hk("action_w", "w"),
    hotkeys.hk("action_w", "ц"),
    hotkeys.hk("action_e", "e"),
    hotkeys.hk("action_e", "у"),
    hotkeys.hk("action_del", "Delete"),
])

# Create directories
def create_directories():
    for dir_name in list(BATCH_DIRS.values()) + MANAGED_DIRS + [TEMP_PREVIEW_DIR, TEMP_BUFFER_DIR]:
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

# Save stats to file
def save_stats_to_file(source_data, managed_data, total_data):
    stats = {
        "source_data": source_data,
        "managed_data": managed_data,
        "total_data": total_data,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    with open(STATS_CACHE_FILE, 'w') as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

# Load stats from file
def load_stats_from_file():
    if not os.path.exists(STATS_CACHE_FILE):
        return None
    try:
        with open(STATS_CACHE_FILE, 'r') as f:
            return json.load(f)
    except:
        return None

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
    history.reverse()
    return history

# Clear temporary directory (specific to preview or buffer)
def clear_temp_dir(temp_dir):
    if os.path.exists(temp_dir):
        for file in os.listdir(temp_dir):
            file_path = os.path.join(temp_dir, file)
            if os.path.isfile(file_path):
                try:
                    os.remove(file_path)
                except Exception as e:
                    log_action("system", os.path.basename(file_path), f"Ошибка удаления временного файла: {str(e)}")

# Check if image is valid
def is_valid_image(file_path):
    try:
        with Image.open(file_path) as img:
            img.verify()
        return True
    except Exception:
        return False

create_directories()
st.title("Image Sorter")
st.header("Распределение по папкам")

st.sidebar.header("Вход пользователя")
if 'previous_user_id' not in st.session_state:
    st.session_state['previous_user_id'] = None

user_id = st.sidebar.text_input("Введите ID пользователя", value=st.session_state.get('user_id', ""))
if user_id != st.session_state.get('previous_user_id') and user_id in USER_IDS:
    clear_temp_dir(TEMP_BUFFER_DIR)
    st.session_state['image_buffer'] = []
    st.session_state['trash_buffer'] = []  # Новый буфер для Корзины
    st.session_state['broken_buffer'] = []  # Новый буфер для Необработанного
    st.session_state['current_sort_index'] = 0
    st.session_state['current_trash_index'] = 0
    st.session_state['current_broken_index'] = 0
    st.session_state['previous_user_id'] = user_id
    st.session_state['user_id'] = user_id
    log_action(user_id, "system", "Смена пользователя, буферы очищены")

if user_id not in USER_IDS:
    st.sidebar.error("Неверный ID пользователя.")
    st.stop()
st.sidebar.success("Успех!")

# Get user's source dir
user_source_dir = SOURCE_DIR if user_id == "admin" else BATCH_DIRS.get(user_id, SOURCE_DIR)

# Initialize buffers for sorting
if 'image_buffer' not in st.session_state:
    st.session_state['image_buffer'] = []
if 'trash_buffer' not in st.session_state:
    st.session_state['trash_buffer'] = []  # Инициализация буфера Корзины
if 'broken_buffer' not in st.session_state:
    st.session_state['broken_buffer'] = []  # Инициализация буфера Необработанного
if 'current_sort_index' not in st.session_state:
    st.session_state['current_sort_index'] = 0
if 'current_trash_index' not in st.session_state:
    st.session_state['current_trash_index'] = 0
if 'current_broken_index' not in st.session_state:
    st.session_state['current_broken_index'] = 0

# Function to fill image buffer (for general sorting)
def fill_image_buffer():
    buffer_size = 50
    current_buffer = st.session_state['image_buffer']
    current_buffer = [item for item in current_buffer if os.path.exists(item['original'])]
    
    remaining_source_images = get_images_in_dir(user_source_dir)
    images_to_add_count = max(0, buffer_size - len(current_buffer))
    if images_to_add_count > 0 and remaining_source_images:
        images_to_add = random.sample(
            remaining_source_images,
            min(images_to_add_count, len(remaining_source_images))
        )
        for img in images_to_add:
            if os.path.exists(img):
                temp_path = os.path.join(TEMP_BUFFER_DIR, os.path.basename(img))
                shutil.copy(img, temp_path)
                if is_valid_image(temp_path):
                    current_buffer.append({'original': img, 'temp': temp_path})
                else:
                    os.remove(temp_path)
        current_buffer = current_buffer[:buffer_size]
        st.session_state['image_buffer'] = current_buffer
        log_action(user_id, "fill_image_buffer", f"Добавлено {len(images_to_add)} изображений в буфер сортировки, текущий размер: {len(current_buffer)}")

# Function to fill trash buffer (for trash deletion mode)
def fill_trash_buffer():
    buffer_size = 50
    current_buffer = st.session_state['trash_buffer']
    current_buffer = [item for item in current_buffer if os.path.exists(item['original'])]
    
    remaining_trash_images = get_images_in_dir(TRASH_DIR)
    images_to_add_count = max(0, buffer_size - len(current_buffer))
    if images_to_add_count > 0 and remaining_trash_images:
        images_to_add = random.sample(
            remaining_trash_images,
            min(images_to_add_count, len(remaining_trash_images))
        )
        for img in images_to_add:
            if os.path.exists(img):
                temp_path = os.path.join(TEMP_BUFFER_DIR, os.path.basename(img))
                shutil.copy(img, temp_path)
                if is_valid_image(temp_path):
                    current_buffer.append({'original': img, 'temp': temp_path})
                else:
                    os.remove(temp_path)
        current_buffer = current_buffer[:buffer_size]
        st.session_state['trash_buffer'] = current_buffer
        log_action(user_id, "fill_trash_buffer", f"Добавлено {len(images_to_add)} изображений в буфер Корзины, текущий размер: {len(current_buffer)}")

# Function to fill broken buffer (for broken deletion mode)
def fill_broken_buffer():
    buffer_size = 50
    current_buffer = st.session_state['broken_buffer']
    current_buffer = [item for item in current_buffer if os.path.exists(item['original'])]
    
    remaining_broken_images = get_images_in_dir(BROKEN_DIR)
    images_to_add_count = max(0, buffer_size - len(current_buffer))
    if images_to_add_count > 0 and remaining_broken_images:
        images_to_add = random.sample(
            remaining_broken_images,
            min(images_to_add_count, len(remaining_broken_images))
        )
        for img in images_to_add:
            if os.path.exists(img):
                temp_path = os.path.join(TEMP_BUFFER_DIR, os.path.basename(img))
                shutil.copy(img, temp_path)
                if is_valid_image(temp_path):
                    current_buffer.append({'original': img, 'temp': temp_path})
                else:
                    os.remove(temp_path)
        current_buffer = current_buffer[:buffer_size]
        st.session_state['broken_buffer'] = current_buffer
        log_action(user_id, "fill_broken_buffer", f"Добавлено {len(images_to_add)} изображений в буфер Необработанного, текущий размер: {len(current_buffer)}")

tab1, tab2, tab3, tab4 = st.tabs(["Стата", "Предпросмотр", "Сортировка", "Журнал (плейбой чи шо)"])

with tab1:
    st.write("### Статистика")
    cached_stats = load_stats_from_file()
    if cached_stats:
        st.write(f"Последнее обновление статистики: {cached_stats['timestamp']}")
        st.write("#### Исходные и батчи")
        st.dataframe(pd.DataFrame(cached_stats['source_data']), use_container_width=True)
        st.write("#### Категории сортировки")
        st.dataframe(pd.DataFrame(cached_stats['managed_data']), use_container_width=True)
        st.write("#### Общий итог")
        st.dataframe(pd.DataFrame(cached_stats['total_data']), use_container_width=True)

        labels = [row["Папка"] for row in cached_stats['source_data'] if row["Папка"] != "Итого в батчах"]
        counts = [row["Количество изображений"] for row in cached_stats['source_data'] if row["Папка"] != "Итого в батчах"]
        if sum(counts) > 0:
            fig, ax = plt.subplots()
            ax.pie(counts, labels=labels, autopct="%1.1f%%", colors=["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728"])
            ax.set_title("Распределение количества изображений по исходным и батчам")
            st.write("#### Распределение по исходным и батчам")
            st.pyplot(fig)

        labels = [row["Папка"] for row in cached_stats['managed_data']]
        counts = [row["Количество изображений"] for row in cached_stats['managed_data']]
        if sum(counts) > 0:
            fig, ax = plt.subplots()
            ax.pie(counts, labels=labels, autopct="%1.1f%%", colors=["#9467bd", "#8c564b", "#e377c2", "#7f7f7f"])
            ax.set_title("Распределение количества изображений по категориям")
            st.write("#### Распределение по категориям сортировки")
            st.pyplot(fig)

    if user_id == "admin":
        if st.button("Рассчитать статистику"):
            try:
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

                total_data = [{
                    "Папка": "Итого",
                    "Количество изображений": batch_total_count + managed_total_count,
                    "Размер (GB)": f"{(batch_total_size + managed_total_size) / 1024:.3f}"
                }]

                save_stats_to_file(source_data, managed_data, total_data)
                st.success("Статистика успешно обновлена.")
                st.rerun()
            except Exception as e:
                st.error(f"Ошибка при расчете статистики: {e}")
                if cached_stats:
                    st.write("Показана последняя сохраненная статистика.")

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
                        if os.path.exists(p):
                            shutil.move(p, os.path.join(batch_dir, os.path.basename(p)))
                            moved_counts[uid] += 1
                log_action(user_id, "Распределение по батчам", f"Равномерно распределено {sum(moved_counts.values())} изображений")
                st.success("Изображения распределены равномерно по батчам.")
                st.rerun()

            selected_uid = st.selectbox("Выбрать батч для всех файлов", ["1", "2", "3"])
            if st.button("Закинуть все в выбранный батч"):
                batch_dir = BATCH_DIRS[selected_uid]
                os.makedirs(batch_dir, exist_ok=True)
                moved_count = 0
                for p in source_images:
                    if os.path.exists(p):
                        shutil.move(p, os.path.join(batch_dir, os.path.basename(p)))
                        moved_count += 1
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
    
    clear_temp_dir(TEMP_PREVIEW_DIR)
    
    if folder == "Все батчи":
        images = []
        for bdir in BATCH_DIRS.values():
            images.extend(get_images_in_dir(bdir))
        images = sorted(images)
    else:
        dir_path = dir_mapping.get(folder, folder)
        images = get_images_in_dir(dir_path)
    
    if images:
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
        end_idx = min(start_idx + per_page, len(images))
        images_to_copy = images[start_idx:end_idx]
        
        if st.button("Загрузить изображения для просмотра"):
            clear_temp_dir(TEMP_PREVIEW_DIR)
            temp_images = []
            for img in images_to_copy:
                if os.path.exists(img) and is_valid_image(img):
                    temp_path = os.path.join(TEMP_PREVIEW_DIR, os.path.basename(img))
                    shutil.copy(img, temp_path)
                    temp_images.append(temp_path)
            
            num_columns = 5
            for i in range(0, len(temp_images), num_columns):
                cols = st.columns(num_columns)
                for j, col in enumerate(cols):
                    if i + j < len(temp_images):
                        img_path = temp_images[i + j]
                        try:
                            col.image(img_path)
                            col.write(os.path.basename(img_path))
                        except Exception as e:
                            col.write(f"Ошибка загрузки: {os.path.basename(img_path)} ({str(e)})")
    else:
        st.write("Нет изображений для просмотра.")

with tab3:
    if 'previous_mode' not in st.session_state:
        st.session_state['previous_mode'] = None

    mode2 = st.selectbox("Выберите режим сортировки", [
        "Режим общей сортировки",
        "Режим удаления (из Корзины)",
        "Режим удаления (из необработанного)"
    ])

    if mode2 != st.session_state.get('previous_mode'):
        clear_temp_dir(TEMP_BUFFER_DIR)
        st.session_state['image_buffer'] = []
        st.session_state['trash_buffer'] = []
        st.session_state['broken_buffer'] = []
        st.session_state['current_sort_index'] = 0
        st.session_state['current_trash_index'] = 0
        st.session_state['current_broken_index'] = 0
        st.session_state['previous_mode'] = mode2
        log_action(user_id, "system", f"Смена режима сортировки на {mode2}, буферы очищены")

    if mode2 == "Режим общей сортировки":
        st.header("Режим общей сортировки")
        fill_image_buffer()
        buffer = st.session_state['image_buffer']
        
        if buffer:
            current_index = st.session_state['current_sort_index']
            if current_index >= len(buffer):
                current_index = 0
                st.session_state['current_sort_index'] = 0
            img_data = buffer[current_index]
            img_path = img_data['temp']
            original_path = img_data['original']
            try:
                st.image(img_path, use_container_width=True)
                st.write(os.path.basename(img_path))
            except Exception as e:
                st.error(f"Ошибка рендеринга изображения: {str(e)}. Используйте кнопку 'Чёто не то (E)' для перемещения в {BROKEN_DIR}.")

            def move_file(original_path, destination_dir, action_name):
                if not os.path.exists(original_path):
                    st.error(f"Файл не найден: {os.path.basename(original_path)}")
                    return False
                try:
                    shutil.move(original_path, os.path.join(destination_dir, os.path.basename(original_path)))
                    log_action(user_id, os.path.basename(original_path), f"Перемещено в {destination_dir}")
                    return True
                except Exception as e:
                    st.error(f"Ошибка перемещения в {destination_dir}: {e}")
                    return False

            action_performed = False
            if hotkeys.pressed("action_q"):
                if move_file(original_path, DETAILS_DIR, "Перемещено в DETAILS"):
                    os.remove(img_path)
                    buffer.pop(current_index)
                    st.session_state['image_buffer'] = buffer
                    st.session_state['current_sort_index'] = min(current_index, len(buffer) - 1)
                    st.success(f"Изображение перемещено в {DETAILS_DIR}")
                    action_performed = True
            elif hotkeys.pressed("action_w"):
                if move_file(original_path, DAMAGES_DIR, "Перемещено в DAMAGES"):
                    os.remove(img_path)
                    buffer.pop(current_index)
                    st.session_state['image_buffer'] = buffer
                    st.session_state['current_sort_index'] = min(current_index, len(buffer) - 1)
                    st.success(f"Изображение перемещено в {DAMAGES_DIR}")
                    action_performed = True
            elif hotkeys.pressed("action_e"):
                if move_file(original_path, BROKEN_DIR, "Перемещено в BROKEN"):
                    os.remove(img_path)
                    buffer.pop(current_index)
                    st.session_state['image_buffer'] = buffer
                    st.session_state['current_sort_index'] = min(current_index, len(buffer) - 1)
                    st.success(f"Изображение перемещено в {BROKEN_DIR}")
                    action_performed = True
            elif hotkeys.pressed("action_del"):
                if move_file(original_path, TRASH_DIR, "Перемещено в TRASH"):
                    os.remove(img_path)
                    buffer.pop(current_index)
                    st.session_state['image_buffer'] = buffer
                    st.session_state['current_sort_index'] = min(current_index, len(buffer) - 1)
                    st.success(f"Изображение перемещено в {TRASH_DIR}")
                    action_performed = True

            col1, col2, col3, col4 = st.columns(4)
            if col1.button("Детали (Q)"):
                if move_file(original_path, DETAILS_DIR, "Перемещено в DETAILS"):
                    os.remove(img_path)
                    buffer.pop(current_index)
                    st.session_state['image_buffer'] = buffer
                    st.session_state['current_sort_index'] = min(current_index, len(buffer) - 1)
                    st.success(f"Изображение перемещено в {DETAILS_DIR}")
                    st.rerun()
            if col2.button("Повреждения (W)"):
                if move_file(original_path, DAMAGES_DIR, "Перемещено в DAMAGES"):
                    os.remove(img_path)
                    buffer.pop(current_index)
                    st.session_state['image_buffer'] = buffer
                    st.session_state['current_sort_index'] = min(current_index, len(buffer) - 1)
                    st.success(f"Изображение перемещено в {DAMAGES_DIR}")
                    st.rerun()
            if col3.button("Чёто не то (E)"):
                if move_file(original_path, BROKEN_DIR, "Перемещено в BROKEN"):
                    os.remove(img_path)
                    buffer.pop(current_index)
                    st.session_state['image_buffer'] = buffer
                    st.session_state['current_sort_index'] = min(current_index, len(buffer) - 1)
                    st.success(f"Изображение перемещено в {BROKEN_DIR}")
                    st.rerun()
            if col4.button("Корзина (DEL)"):
                if move_file(original_path, TRASH_DIR, "Перемещено в TRASH"):
                    os.remove(img_path)
                    buffer.pop(current_index)
                    st.session_state['image_buffer'] = buffer
                    st.session_state['current_sort_index'] = min(current_index, len(buffer) - 1)
                    st.success(f"Изображение перемещено в {TRASH_DIR}")
                    st.rerun()

            if action_performed:
                st.rerun()
        else:
            st.write("Все изображения из вашей директории отсортированы.")

    elif mode2 == "Режим удаления (из Корзины)":
        st.header("Режим удаления из Корзины")
        fill_trash_buffer()
        buffer = st.session_state['trash_buffer']
        
        if buffer:
            current_index = st.session_state['current_trash_index']
            if current_index >= len(buffer):
                current_index = 0
                st.session_state['current_trash_index'] = 0
            img_data = buffer[current_index]
            img_path = img_data['temp']
            original_path = img_data['original']
            try:
                st.image(img_path, use_container_width=True)
                st.write(os.path.basename(img_path))
            except Exception as e:
                st.write(f"Ошибка загрузки: {os.path.basename(img_path)} ({str(e)})")

            def move_file(original_path, destination_dir, action_name):
                if not os.path.exists(original_path):
                    st.error(f"Файл не найден: {os.path.basename(original_path)}")
                    return False
                try:
                    shutil.move(original_path, os.path.join(destination_dir, os.path.basename(original_path)))
                    log_action(user_id, os.path.basename(original_path), f"Перемещено в {destination_dir}")
                    return True
                except Exception as e:
                    st.error(f"Ошибка перемещения в {destination_dir}: {e}")
                    return False

            action_performed = False
            if hotkeys.pressed("action_q"):
                if move_file(original_path, DETAILS_DIR, "Перемещено в DETAILS"):
                    os.remove(img_path)
                    buffer.pop(current_index)
                    st.session_state['trash_buffer'] = buffer
                    st.session_state['current_trash_index'] = min(current_index, len(buffer) - 1)
                    st.success(f"Изображение перемещено в {DETAILS_DIR}")
                    action_performed = True
            elif hotkeys.pressed("action_w"):
                if move_file(original_path, DAMAGES_DIR, "Перемещено в DAMAGES"):
                    os.remove(img_path)
                    buffer.pop(current_index)
                    st.session_state['trash_buffer'] = buffer
                    st.session_state['current_trash_index'] = min(current_index, len(buffer) - 1)
                    st.success(f"Изображение перемещено в {DAMAGES_DIR}")
                    action_performed = True
            elif hotkeys.pressed("action_del"):
                if os.path.exists(original_path):
                    os.remove(original_path)
                    os.remove(img_path)
                    buffer.pop(current_index)
                    st.session_state['trash_buffer'] = buffer
                    st.session_state['current_trash_index'] = min(current_index, len(buffer) - 1)
                    log_action(user_id, os.path.basename(original_path), "Удалено")
                    st.success("Изображение удалено")
                    action_performed = True

            col1, col2, col3 = st.columns(3)
            if col1.button("Детали (Q)"):
                if move_file(original_path, DETAILS_DIR, "Перемещено в DETAILS"):
                    os.remove(img_path)
                    buffer.pop(current_index)
                    st.session_state['trash_buffer'] = buffer
                    st.session_state['current_trash_index'] = min(current_index, len(buffer) - 1)
                    st.success(f"Изображение перемещено в {DETAILS_DIR}")
                    st.rerun()
            if col2.button("Повреждения (W)"):
                if move_file(original_path, DAMAGES_DIR, "Перемещено в DAMAGES"):
                    os.remove(img_path)
                    buffer.pop(current_index)
                    st.session_state['trash_buffer'] = buffer
                    st.session_state['current_trash_index'] = min(current_index, len(buffer) - 1)
                    st.success(f"Изображение перемещено в {DAMAGES_DIR}")
                    st.rerun()
            if col3.button("Удалить (DEL)"):
                if os.path.exists(original_path):
                    os.remove(original_path)
                    os.remove(img_path)
                    buffer.pop(current_index)
                    st.session_state['trash_buffer'] = buffer
                    st.session_state['current_trash_index'] = min(current_index, len(buffer) - 1)
                    log_action(user_id, os.path.basename(original_path), "Удалено")
                    st.success("Изображение удалено")
                    st.rerun()

            if action_performed:
                st.rerun()
        else:
            st.write("Нет изображений в Корзине.")

    elif mode2 == "Режим удаления (из необработанного)":
        st.header("Режим удаления из необработанного")
        fill_broken_buffer()
        buffer = st.session_state['broken_buffer']
        
        if buffer:
            current_index = st.session_state['current_broken_index']
            if current_index >= len(buffer):
                current_index = 0
                st.session_state['current_broken_index'] = 0
            img_data = buffer[current_index]
            img_path = img_data['temp']
            original_path = img_data['original']
            try:
                st.image(img_path, use_container_width=True)
                st.write(os.path.basename(img_path))
            except Exception as e:
                st.write(f"Ошибка загрузки: {os.path.basename(img_path)} ({str(e)})")

            def move_file(original_path, destination_dir, action_name):
                if not os.path.exists(original_path):
                    st.error(f"Файл не найден: {os.path.basename(original_path)}")
                    return False
                try:
                    shutil.move(original_path, os.path.join(destination_dir, os.path.basename(original_path)))
                    log_action(user_id, os.path.basename(original_path), f"Перемещено в {destination_dir}")
                    return True
                except Exception as e:
                    st.error(f"Ошибка перемещения в {destination_dir}: {e}")
                    return False

            action_performed = False
            if hotkeys.pressed("action_q"):
                if move_file(original_path, SOURCE_DIR, "Возвращено в Source"):
                    os.remove(img_path)
                    buffer.pop(current_index)
                    st.session_state['broken_buffer'] = buffer
                    st.session_state['current_broken_index'] = min(current_index, len(buffer) - 1)
                    st.success("Изображение возвращено в Source")
                    action_performed = True
            elif hotkeys.pressed("action_del"):
                if os.path.exists(original_path):
                    os.remove(original_path)
                    os.remove(img_path)
                    buffer.pop(current_index)
                    st.session_state['broken_buffer'] = buffer
                    st.session_state['current_broken_index'] = min(current_index, len(buffer) - 1)
                    log_action(user_id, os.path.basename(original_path), "Удалено")
                    st.success("Изображение удалено")
                    action_performed = True

            col1, col2 = st.columns(2)
            if col1.button("Вернуть в Source (Q)"):
                if move_file(original_path, SOURCE_DIR, "Возвращено в Source"):
                    os.remove(img_path)
                    buffer.pop(current_index)
                    st.session_state['broken_buffer'] = buffer
                    st.session_state['current_broken_index'] = min(current_index, len(buffer) - 1)
                    st.success("Изображение возвращено в Source")
                    st.rerun()
            if col2.button("Удалить (DEL)"):
                if os.path.exists(original_path):
                    os.remove(original_path)
                    os.remove(img_path)
                    buffer.pop(current_index)
                    st.session_state['broken_buffer'] = buffer
                    st.session_state['current_broken_index'] = min(current_index, len(buffer) - 1)
                    log_action(user_id, os.path.basename(original_path), "Удалено")
                    st.success("Изображение удалено")
                    st.rerun()

            if action_performed:
                st.rerun()
        else:
            st.write("Нет изображений в необработанном.")

with tab4:
    st.header("Журнал действий")
    history = read_action_history()
    if history:
        df = pd.DataFrame(history)
        per_page = 50
        total_pages = (len(df) + per_page - 1) // per_page if per_page < len(df) else 1
        current_page = st.selectbox("Страница", range(1, total_pages + 1)) if total_pages > 1 else 1
        start_idx = (current_page - 1) * per_page
        end_idx = start_idx + per_page
        df_page = df.iloc[start_idx:end_idx]
        st.dataframe(df_page, use_container_width=True)
    else:
        st.write("Журнал пуст или файл отсутствует.")