import os
import shutil
import json
import pandas as pd
import matplotlib.pyplot as plt
import streamlit as st
import streamlit_hotkeys as hotkeys
import random
import sqlite3
from datetime import datetime

############ CHANGE ############
SOURCE_DIR = r"ПУТЬ_ДО_СЫРОЙ_ПАПКИ"

# Folder names
DETAILS_DIR = "Детали"
DAMAGES_DIR = "Повреждения"
TRASH_DIR = "Корзина"
BROKEN_DIR = "Чёто не то"

# All managed directories
MANAGED_DIRS = [DETAILS_DIR, DAMAGES_DIR, TRASH_DIR, BROKEN_DIR]

# State database for saving progress
STATE_DB = "sorting_state.db"

# Test user IDs
USER_IDS = [
    "admin",
    "1", 
    "2", 
    "3"
]

# Create directories
def create_directories():
    for dir_name in MANAGED_DIRS:
        os.makedirs(dir_name, exist_ok=True)

# Get all image files in a directory
def get_images_in_dir(directory):
    images = []
    for file in os.listdir(directory):
        if file.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp')):
            images.append(os.path.join(directory, file))
    return sorted(images)

# Calculate folder stats
def get_folder_stats(directory):
    count = 0
    total_size = 0
    for file in os.listdir(directory):
        file_path = os.path.join(directory, file)
        if os.path.isfile(file_path):
            count += 1
            total_size += os.path.getsize(file_path)
    return count, total_size / (1024 * 1024)  # Size in MB

# Calculate folder stats for a specific set of basenames
def get_folder_stats_for_batch(directory, batch_basenames):
    count = 0
    total_size = 0
    for file in os.listdir(directory):
        if file in batch_basenames:
            file_path = os.path.join(directory, file)
            if os.path.isfile(file_path):
                count += 1
                total_size += os.path.getsize(file_path)
    return count, total_size / (1024 * 1024)  # Size in MB

# Load state
def load_state():
    conn = sqlite3.connect(STATE_DB, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL;")
    cursor.execute('''CREATE TABLE IF NOT EXISTS app_state (id INTEGER PRIMARY KEY, data TEXT)''')
    cursor.execute('''INSERT OR IGNORE INTO app_state (id, data) VALUES (1, '{}')''')
    conn.commit()
    
    cursor.execute('''SELECT data FROM app_state WHERE id = 1''')
    data_str = cursor.fetchone()[0]
    if data_str:
        state = json.loads(data_str)
    else:
        state = {}
    
    # Initialize if empty or missing keys
    if not state or not all(key in state for key in ["global_processed", "batches", "user_processed", "current_sort_index", "current_trash_index", "current_broken_index"]):
        state = {
            "global_processed": [],  
            "batches": {"1": [], "2": [], "3": []},  
            "user_processed": {"1": [], "2": [], "3": [], "admin": []},  
            "current_sort_index": {"1": 0, "2": 0, "3": 0, "admin": 0},  
            "current_trash_index": {"1": 0, "2": 0, "3": 0, "admin": 0},  
            "current_broken_index": {"1": 0, "2": 0, "3": 0, "admin": 0}  
        }
    
    # Distribute images into batches if not already done (check if batches are empty)
    if not any(state["batches"].values()):
        all_images = get_images_in_dir(SOURCE_DIR)
        if all_images:
            random.shuffle(all_images)  # Shuffle for fair distribution
            batch_size = len(all_images) // 3
            state["batches"]["1"] = all_images[:batch_size]
            state["batches"]["2"] = all_images[batch_size:2*batch_size]
            state["batches"]["3"] = all_images[2*batch_size:]  # Remainder goes to user 3
        save_state(state)  # Save after initialization
    
    conn.close()
    return state

# Save state
def save_state(state):
    conn = sqlite3.connect(STATE_DB, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL;")
    json_data = json.dumps(state, indent=2)
    cursor.execute('''UPDATE app_state SET data = ? WHERE id = 1''', (json_data,))
    conn.commit()
    conn.close()

# Rebuild state from existing files in directories
def rebuild_state():
    state = {
        "global_processed": [],
        "batches": {"1": [], "2": [], "3": []},
        "user_processed": {"1": [], "2": [], "3": [], "admin": []},
        "current_sort_index": {"1": 0, "2": 0, "3": 0, "admin": 0},
        "current_trash_index": {"1": 0, "2": 0, "3": 0, "admin": 0},
        "current_broken_index": {"1": 0, "2": 0, "3": 0, "admin": 0}
    }
    
    # Collect all images from managed directories
    processed_images = []
    for dir_name in MANAGED_DIRS:
        processed_images.extend(get_images_in_dir(dir_name))
    
    # Add processed images to global_processed and distribute to user_processed
    if processed_images:
        random.shuffle(processed_images)
        batch_size = len(processed_images) // 3
        state["global_processed"] = processed_images
        state["user_processed"]["1"] = processed_images[:batch_size]
        state["user_processed"]["2"] = processed_images[batch_size:2*batch_size]
        state["user_processed"]["3"] = processed_images[2*batch_size:]
        state["user_processed"]["admin"] = processed_images  # Admin has access to all processed
    
    # Distribute unprocessed images from SOURCE_DIR to batches
    all_source_images = get_images_in_dir(SOURCE_DIR)
    unprocessed_images = [img for img in all_source_images if img not in state["global_processed"]]
    if unprocessed_images:
        random.shuffle(unprocessed_images)
        batch_size = len(unprocessed_images) // 3
        state["batches"]["1"] = unprocessed_images[:batch_size]
        state["batches"]["2"] = unprocessed_images[batch_size:2*batch_size]
        state["batches"]["3"] = unprocessed_images[2*batch_size:]
    
    save_state(state)
    return state

# Log action to history
def log_action(user_id, filename, action):
    conn = sqlite3.connect(STATE_DB, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL;")
    cursor.execute('''CREATE TABLE IF NOT EXISTS action_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT,
        user_id TEXT,
        filename TEXT,
        action TEXT
    )''')
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute('''INSERT INTO action_history (timestamp, user_id, filename, action)
                     VALUES (?, ?, ?, ?)''', (timestamp, user_id, filename, action))
    conn.commit()
    conn.close()

hotkeys.activate([
    hotkeys.hk("details", "q"),  # Q для "Детали"
    hotkeys.hk("details", "й"),  # Q для "Детали"
    hotkeys.hk("damages", "w"),  # W для "Повреждения"
    hotkeys.hk("damages", "ц"),  # W для "Повреждения"
    hotkeys.hk("broken", "e"),   # E для "Чёто не то" (Broken)
    hotkeys.hk("broken", "у"),   # E для "Чёто не то" (Broken)
    hotkeys.hk("trash", "Delete"),  # Delete для "Корзина"
])

create_directories()
state = load_state()
st.title("Image Sorter")
st.header("Распределение по папкам")

st.sidebar.header("Вход пользователя")
user_id = st.sidebar.text_input("Введите ID пользователя", "")
if user_id not in USER_IDS:
    st.sidebar.error("Неверный ID пользователя.")
    st.stop()
st.sidebar.success("Успех!")

# Get images based on user
all_source_images = get_images_in_dir(SOURCE_DIR)
if user_id == "admin":
    remaining_source_images = [img for img in all_source_images if img not in state["global_processed"]]
else:
    remaining_source_images = [img for img in state["batches"].get(user_id, []) if img not in state["global_processed"]]

tab1, tab2, tab3, tab4 = st.tabs(["Стата и предпросмотр", "Сортировка", "Статистика по пользователям", "Журнал (плейбой чи шо)"])

with tab1:
    # Collect info
    data = []
    total_count = 0
    total_size = 0
    for dir_name in [SOURCE_DIR] + MANAGED_DIRS:
        count, size = get_folder_stats(dir_name if dir_name == SOURCE_DIR else dir_name)
        name = "На обработку" if dir_name == SOURCE_DIR else dir_name
        data.append({
            "Папка": name,
            "Количество изображений": count,
            "Размер (GB)": f"{size / 1024:.3f}"
        })
        total_count += count
        total_size += size

    data.append({
        "Папка": "Итого",
        "Количество изображений": total_count,
        "Размер (GB)": f"{total_size / 1024:.3f}"
    })

    df = pd.DataFrame(data)

    st.dataframe(df, use_container_width=True)

    labels = [row["Папка"] for row in data if row["Папка"] != "Итого"]
    counts = [row["Количество изображений"] for row in data if row["Папка"] != "Итого"]

    fig, ax = plt.subplots()
    ax.pie(counts, labels=labels, autopct="%1.1f%%", colors=["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd"])
    ax.set_title("Распределение количества изображений по папкам")

    st.write("### Распределение изображений по папкам")
    st.pyplot(fig)

    # Mode selection
    mode = st.selectbox("Выберите режим просмотра", [
        "Просмотр всех изображений",
        "Просмотр по папкам"
    ])

    if mode == "Просмотр всех изображений":
        st.header("Просмотр всех изображений")
        all_images = []
        for dir_name in [SOURCE_DIR] + MANAGED_DIRS:
            all_images.extend(get_images_in_dir(dir_name if dir_name == SOURCE_DIR else dir_name))
        
        if all_images:
            # Pagination options
            per_page_options = [50, 100, 200, "Custom", "All"]
            per_page_choice = st.selectbox("Количество изображений на странице", per_page_options)
            
            if per_page_choice == "Custom":
                per_page = st.number_input("Введите количество", min_value=1, value=50)
            elif per_page_choice == "All":
                per_page = len(all_images)
            else:
                per_page = per_page_choice
            
            total_pages = (len(all_images) + per_page - 1) // per_page if per_page < len(all_images) else 1
            
            current_page = st.selectbox("Страница", range(1, total_pages + 1)) if total_pages > 1 else 1
            
            start_idx = (current_page - 1) * per_page
            end_idx = start_idx + per_page
            images_to_show = all_images[start_idx:end_idx]
            
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

    elif mode == "Просмотр по папкам":
        st.header("Просмотр по папкам")
        folder = st.selectbox("Выберите папку", ["На обработку"] + MANAGED_DIRS)
        dir_path = SOURCE_DIR if folder == "На обработку" else folder
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

with tab2:
    mode2 = st.selectbox("Выберите режим сортировки", [
        "Режим общей сортировки",
        "Режим удаления (из Корзины)",
        "Режим удаления (из необработанного)"
    ])

    if mode2 == "Режим общей сортировки":
        st.header("Режим общей сортировки")
        if remaining_source_images:
            current_index = state["current_sort_index"][user_id]
            if current_index >= len(remaining_source_images):
                current_index = 0
                state["current_sort_index"][user_id] = 0
                save_state(state)
            
            img_path = remaining_source_images[current_index]
            try:
                st.image(img_path, use_container_width=True)
                st.write(os.path.basename(img_path))
            except:
                st.write(f"Ошибка загрузки: {img_path}")
                # Move to Broken if can't load
                shutil.move(img_path, os.path.join(BROKEN_DIR, os.path.basename(img_path)))
                state["global_processed"].append(img_path)
                state["user_processed"][user_id].append(img_path)
                state["current_sort_index"][user_id] = min(current_index + 1, len(remaining_source_images) - 1)
                log_action(user_id, os.path.basename(img_path), f"Перемещено в {BROKEN_DIR} (автоматически)")
                save_state(state)
                st.rerun()

            # Hotkeys with streamlit-hotkeys
            if hotkeys.pressed("details"):  # Q для "Детали"
                try:
                    shutil.move(img_path, os.path.join(DETAILS_DIR, os.path.basename(img_path)))
                    state["global_processed"].append(img_path)
                    state["user_processed"][user_id].append(img_path)
                    state["current_sort_index"][user_id] = min(current_index + 1, len(remaining_source_images) - 1)
                    log_action(user_id, os.path.basename(img_path), f"Перемещено в {DETAILS_DIR}")
                    st.success(f"Изображение перемещено в {DETAILS_DIR}")
                    save_state(state)
                except Exception as e:
                    st.error(f"Ошибка перемещения в {DETAILS_DIR}: {e}")
                st.rerun()
            
            if hotkeys.pressed("damages"):  # W для "Повреждения"
                try:
                    shutil.move(img_path, os.path.join(DAMAGES_DIR, os.path.basename(img_path)))
                    state["global_processed"].append(img_path)
                    state["user_processed"][user_id].append(img_path)
                    state["current_sort_index"][user_id] = min(current_index + 1, len(remaining_source_images) - 1)
                    log_action(user_id, os.path.basename(img_path), f"Перемещено в {DAMAGES_DIR}")
                    st.success(f"Изображение перемещено в {DAMAGES_DIR}")
                    save_state(state)
                except Exception as e:
                    st.error(f"Ошибка перемещения в {DAMAGES_DIR}: {e}")
                st.rerun()
            
            if hotkeys.pressed("broken"):  # E для "Чёто не то" (Broken)
                try:
                    shutil.move(img_path, os.path.join(BROKEN_DIR, os.path.basename(img_path)))
                    state["global_processed"].append(img_path)
                    state["user_processed"][user_id].append(img_path)
                    state["current_sort_index"][user_id] = min(current_index + 1, len(remaining_source_images) - 1)
                    log_action(user_id, os.path.basename(img_path), f"Перемещено в {BROKEN_DIR}")
                    st.success(f"Изображение перемещено в {BROKEN_DIR}")
                    save_state(state)
                except Exception as e:
                    st.error(f"Ошибка перемещения в {BROKEN_DIR}: {e}")
                st.rerun()
            
            if hotkeys.pressed("trash"):  # Delete для "Корзина"
                try:
                    shutil.move(img_path, os.path.join(TRASH_DIR, os.path.basename(img_path)))
                    state["global_processed"].append(img_path)
                    state["user_processed"][user_id].append(img_path)
                    state["current_sort_index"][user_id] = min(current_index + 1, len(remaining_source_images) - 1)
                    log_action(user_id, os.path.basename(img_path), f"Перемещено в {TRASH_DIR}")
                    st.success(f"Изображение перемещено в {TRASH_DIR}")
                    save_state(state)
                except Exception as e:
                    st.error(f"Ошибка перемещения в {TRASH_DIR}: {e}")
                st.rerun()

            # Buttons (for convenience, with hotkey hints)
            col1, col2, col3, col4 = st.columns(4)
            if col1.button("Детали (Q)"):
                try:
                    shutil.move(img_path, os.path.join(DETAILS_DIR, os.path.basename(img_path)))
                    state["global_processed"].append(img_path)
                    state["user_processed"][user_id].append(img_path)
                    state["current_sort_index"][user_id] = min(current_index + 1, len(remaining_source_images) - 1)
                    log_action(user_id, os.path.basename(img_path), f"Перемещено в {DETAILS_DIR}")
                    st.success(f"Изображение перемещено в {DETAILS_DIR}")
                    save_state(state)
                except Exception as e:
                    st.error(f"Ошибка перемещения в {DETAILS_DIR}: {e}")
                st.rerun()
            
            if col2.button("Повреждения (W)"):
                try:
                    shutil.move(img_path, os.path.join(DAMAGES_DIR, os.path.basename(img_path)))
                    state["global_processed"].append(img_path)
                    state["user_processed"][user_id].append(img_path)
                    state["current_sort_index"][user_id] = min(current_index + 1, len(remaining_source_images) - 1)
                    log_action(user_id, os.path.basename(img_path), f"Перемещено в {DAMAGES_DIR}")
                    st.success(f"Изображение перемещено в {DAMAGES_DIR}")
                    save_state(state)
                except Exception as e:
                    st.error(f"Ошибка перемещения в {DAMAGES_DIR}: {e}")
                st.rerun()
            
            if col3.button("Чёто не то (E)"):
                try:
                    shutil.move(img_path, os.path.join(BROKEN_DIR, os.path.basename(img_path)))
                    state["global_processed"].append(img_path)
                    state["user_processed"][user_id].append(img_path)
                    state["current_sort_index"][user_id] = min(current_index + 1, len(remaining_source_images) - 1)
                    log_action(user_id, os.path.basename(img_path), f"Перемещено в {BROKEN_DIR}")
                    st.success(f"Изображение перемещено в {BROKEN_DIR}")
                    save_state(state)
                except Exception as e:
                    st.error(f"Ошибка перемещения в {BROKEN_DIR}: {e}")
                st.rerun()
            
            if col4.button("Корзина (DEL)"):
                try:
                    shutil.move(img_path, os.path.join(TRASH_DIR, os.path.basename(img_path)))
                    state["global_processed"].append(img_path)
                    state["user_processed"][user_id].append(img_path)
                    state["current_sort_index"][user_id] = min(current_index + 1, len(remaining_source_images) - 1)
                    log_action(user_id, os.path.basename(img_path), f"Перемещено в {TRASH_DIR}")
                    st.success(f"Изображение перемещено в {TRASH_DIR}")
                    save_state(state)
                except Exception as e:
                    st.error(f"Ошибка перемещения в {TRASH_DIR}: {e}")
                st.rerun()
        else:
            st.write("Все изображения из вашей директории отсортированы.")

    elif mode2 == "Режим удаления (из Корзины)":
        st.header("Режим удаления из Корзины")
        trash_images = get_images_in_dir(TRASH_DIR)
        if user_id != "admin":
            trash_images = [img for img in trash_images if img in state["batches"].get(user_id, []) or img in state["user_processed"][user_id]]
        
        if trash_images:
            current_index = state["current_trash_index"][user_id]
            if current_index >= len(trash_images):
                current_index = 0
                state["current_trash_index"][user_id] = 0
                save_state(state)
            
            img_path = trash_images[current_index]
            try:
                st.image(img_path, use_container_width=True)
                st.write(os.path.basename(img_path))
            except:
                st.write(f"Ошибка загрузки: {img_path}")

            col1, col2, col3 = st.columns(3)
            if col1.button("Детали"):
                try:
                    shutil.move(img_path, os.path.join(DETAILS_DIR, os.path.basename(img_path)))
                    state["current_trash_index"][user_id] = min(current_index + 1, len(trash_images) - 1)
                    log_action(user_id, os.path.basename(img_path), f"Перемещено в {DETAILS_DIR}")
                    save_state(state)
                    st.rerun()
                except Exception as e:
                    st.error(f"Ошибка перемещения в {DETAILS_DIR}: {e}")
            
            if col2.button("Повреждения"):
                try:
                    shutil.move(img_path, os.path.join(DAMAGES_DIR, os.path.basename(img_path)))
                    state["current_trash_index"][user_id] = min(current_index + 1, len(trash_images) - 1)
                    log_action(user_id, os.path.basename(img_path), f"Перемещено в {DAMAGES_DIR}")
                    save_state(state)
                    st.rerun()
                except Exception as e:
                    st.error(f"Ошибка перемещения в {DAMAGES_DIR}: {e}")
            
            if col3.button("Удалить"):
                try:
                    os.remove(img_path)
                    state["current_trash_index"][user_id] = min(current_index + 1, len(trash_images) - 1)
                    log_action(user_id, os.path.basename(img_path), "Удалено")
                    save_state(state)
                    st.rerun()
                except Exception as e:
                    st.error(f"Ошибка удаления: {e}")
        else:
            st.write("Нет изображений в Корзине для вашего доступа.")

    elif mode2 == "Режим удаления (из необработанного)":
        st.header("Режим удаления из необработанного")
        broken_images = get_images_in_dir(BROKEN_DIR)
        if user_id != "admin":
            broken_images = [img for img in broken_images if img in state["batches"].get(user_id, []) or img in state["user_processed"][user_id]]
        
        if broken_images:
            current_index = state["current_broken_index"][user_id]
            if current_index >= len(broken_images):
                current_index = 0
                state["current_broken_index"][user_id] = 0
                save_state(state)
            
            img_path = broken_images[current_index]
            try:
                st.image(img_path, use_container_width=True)
                st.write(os.path.basename(img_path))
            except:
                st.write(f"Ошибка загрузки: {img_path}")

            col1, col2 = st.columns(2)
            if col1.button("Вернуть в Source"):
                try:
                    shutil.move(img_path, os.path.join(SOURCE_DIR, os.path.basename(img_path)))
                    if img_path in state["global_processed"]:
                        state["global_processed"].remove(img_path)
                    if img_path in state["user_processed"][user_id]:
                        state["user_processed"][user_id].remove(img_path)
                    state["current_broken_index"][user_id] = min(current_index + 1, len(broken_images) - 1)
                    log_action(user_id, os.path.basename(img_path), "Возвращено в Source")
                    save_state(state)
                    st.rerun()
                except Exception as e:
                    st.error(f"Ошибка перемещения в Source: {e}")
            
            if col2.button("Удалить"):
                try:
                    os.remove(img_path)
                    state["current_broken_index"][user_id] = min(current_index + 1, len(broken_images) - 1)
                    log_action(user_id, os.path.basename(img_path), "Удалено")
                    save_state(state)
                    st.rerun()
                except Exception as e:
                    st.error(f"Ошибка удаления: {e}")
        else:
            st.write("Нет изображений в необработанном для вашего доступа.")

with tab3:
    if user_id == "admin":
        for uid in ["1", "2", "3"]:
            st.subheader(f"Статистика для пользователя {uid}")
            batch_basenames = set(os.path.basename(img) for img in state["batches"].get(uid, []))
            data = []
            total_count = 0
            total_size = 0
            for dir_name in [SOURCE_DIR] + MANAGED_DIRS:
                dir_path = dir_name if dir_name != SOURCE_DIR else SOURCE_DIR
                count, size = get_folder_stats_for_batch(dir_path, batch_basenames)
                name = "На обработку" if dir_name == SOURCE_DIR else dir_name
                data.append({
                    "Папка": name,
                    "Количество изображений": count,
                    "Размер (GB)": f"{size / 1024:.3f}"
                })
                total_count += count
                total_size += size

            data.append({
                "Папка": "Итого",
                "Количество изображений": total_count,
                "Размер (GB)": f"{total_size / 1024:.3f}"
            })

            df = pd.DataFrame(data)
            st.dataframe(df, use_container_width=True)

            labels = [row["Папка"] for row in data if row["Папка"] != "Итого"]
            counts = [row["Количество изображений"] for row in data if row["Папка"] != "Итого"]

            if sum(counts) > 0:
                fig, ax = plt.subplots()
                ax.pie(counts, labels=labels, autopct="%1.1f%%", colors=["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd"])
                ax.set_title(f"Распределение количества изображений для пользователя {uid}")
                st.pyplot(fig)
            else:
                st.write("Нет данных для диаграммы.")

        # New functionality for admin: Check and rebuild state
        st.subheader("Проверка и перезаполнение базы")
        if st.button("Проверить и перезаполнить базу"):
            state = rebuild_state()
            st.success("База данных проверена и перезаполнена.")
            st.rerun()

        # New functionality for admin: Distribute new files
        st.subheader("Распределение новых файлов")
        all_batched = [item for sublist in state["batches"].values() for item in sublist]
        new_images = [img for img in all_source_images if img not in all_batched and img not in state["global_processed"]]
        st.write(f"Найдено новых изображений: {len(new_images)}")

        if len(new_images) > 0:
            if st.button("Распределить равномерно между батчами"):
                random.shuffle(new_images)
                batch_size = len(new_images) // 3
                state["batches"]["1"].extend(new_images[:batch_size])
                state["batches"]["2"].extend(new_images[batch_size:2*batch_size])
                state["batches"]["3"].extend(new_images[2*batch_size:])
                save_state(state)
                st.success("Новые изображения распределены равномерно.")
                st.rerun()

            selected_uid = st.selectbox("Выбрать батч для всех новых", ["1", "2", "3"])
            if st.button("Закинуть все новые в выбранный батч"):
                state["batches"][selected_uid].extend(new_images)
                save_state(state)
                st.success(f"Новые изображения добавлены в батч {selected_uid}.")
                st.rerun()
        else:
            st.write("Нет новых изображений для распределения.")

    else:
        st.subheader(f"Ваша статистика (пользователь {user_id})")
        batch_basenames = set(os.path.basename(img) for img in state["batches"].get(user_id, []))
        data = []
        total_count = 0
        total_size = 0
        for dir_name in [SOURCE_DIR] + MANAGED_DIRS:
            dir_path = dir_name if dir_name != SOURCE_DIR else SOURCE_DIR
            count, size = get_folder_stats_for_batch(dir_path, batch_basenames)
            name = "На обработку" if dir_name == SOURCE_DIR else dir_name
            data.append({
                "Папка": name,
                "Количество изображений": count,
                "Размер (GB)": f"{size / 1024:.3f}"
            })
            total_count += count
            total_size += size

        data.append({
            "Папка": "Итого",
            "Количество изображений": total_count,
            "Размер (GB)": f"{total_size / 1024:.3f}"
        })

        df = pd.DataFrame(data)
        st.dataframe(df, use_container_width=True)

        labels = [row["Папка"] for row in data if row["Папка"] != "Итого"]
        counts = [row["Количество изображений"] for row in data if row["Папка"] != "Итого"]

        if sum(counts) > 0:
            fig, ax = plt.subplots()
            ax.pie(counts, labels=labels, autopct="%1.1f%%", colors=["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd"])
            ax.set_title("Распределение количества изображений в вашем батче")
            st.pyplot(fig)
        else:
            st.write("Нет данных для диаграммы.")

with tab4:
    st.subheader("История действий")
    conn = sqlite3.connect(STATE_DB, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL;")
    cursor.execute('''CREATE TABLE IF NOT EXISTS action_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT,
        user_id TEXT,
        filename TEXT,
        action TEXT
    )''')
    if user_id == "admin":
        cursor.execute('''SELECT timestamp, user_id, filename, action FROM action_history ORDER BY timestamp DESC''')
    else:
        cursor.execute('''SELECT timestamp, user_id, filename, action FROM action_history WHERE user_id = ? ORDER BY timestamp DESC''', (user_id,))
    history = cursor.fetchall()
    conn.close()

    if history:
        df = pd.DataFrame(history, columns=["Время", "Пользователь", "Имя файла", "Действие"])
        st.dataframe(df, use_container_width=True)
    else:
        st.write("История действий пуста.")