import os
import shutil
import json
from PIL import Image
import streamlit as st
from streamlit.components.v1 import html

# Hardcoded source directory (change this to your actual path)
SOURCE_DIR = r"C:\Main\Thrash\images"  # Замените на реальный путь к директории с изображениями

# Folder names
DETAILS_DIR = "Details"
DAMAGES_DIR = "Damages"
TRASH_DIR = "Trash"
BROKEN_DIR = "Broken"

# All managed directories
MANAGED_DIRS = [DETAILS_DIR, DAMAGES_DIR, TRASH_DIR, BROKEN_DIR]

# State file for saving progress
STATE_FILE = "sorting_state.json"

# Function to create directories if they don't exist
def create_directories():
    for dir_name in MANAGED_DIRS:
        os.makedirs(dir_name, exist_ok=True)

# Function to get all image files in a directory
def get_images_in_dir(directory):
    images = []
    for file in os.listdir(directory):
        if file.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp')):
            images.append(os.path.join(directory, file))
    return sorted(images)

# Function to calculate folder stats
def get_folder_stats(directory):
    count = 0
    total_size = 0
    for file in os.listdir(directory):
        file_path = os.path.join(directory, file)
        if os.path.isfile(file_path):
            count += 1
            total_size += os.path.getsize(file_path)
    return count, total_size / (1024 * 1024)  # Size in MB

# Function to load state
def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'r') as f:
            return json.load(f)
    return {
        "processed_images": [],  # List of images already sorted from source
        "current_sort_index": 0,
        "current_trash_index": 0,
        "current_broken_index": 0
    }

# Function to save state
def save_state(state):
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f)

# Initialize directories
create_directories()

# Load state
state = load_state()

# Streamlit app
st.title("Image Sorter")

# Display overall stats
st.header("Распределение по папкам")
stats = {}
total_count = 0
total_size = 0
for dir_name in [SOURCE_DIR] + MANAGED_DIRS:
    count, size = get_folder_stats(dir_name if dir_name == SOURCE_DIR else dir_name)
    name = "Source" if dir_name == SOURCE_DIR else dir_name
    stats[name] = (count, size)
    total_count += count
    total_size += size

st.write(f"Всего изображений: {total_count}, Общий вес: {total_size:.2f} MB")
for name, (count, size) in stats.items():
    st.write(f"{name}: {count} изображений, {size:.2f} MB")

# Mode selection
mode = st.selectbox("Выберите режим", [
    "Просмотр всего кучей",
    "Просмотр отдельной папки",
    "Режим сортировки",
    "Режим удаления (из Корзины)",
    "Режим удаления (из Битого)"
])

# Get all images from source, excluding processed ones
all_source_images = get_images_in_dir(SOURCE_DIR)
remaining_source_images = [img for img in all_source_images if img not in state["processed_images"]]

if mode == "Просмотр всего кучей":
    st.header("Просмотр всех изображений")
    all_images = []
    for dir_name in [SOURCE_DIR] + MANAGED_DIRS:
        all_images.extend(get_images_in_dir(dir_name if dir_name == SOURCE_DIR else dir_name))
    
    if all_images:
        for img_path in all_images:
            try:
                st.image(img_path, use_column_width=True)
                st.write(os.path.basename(img_path))
            except:
                st.write(f"Ошибка загрузки: {img_path}")
    else:
        st.write("Нет изображений для просмотра.")

elif mode == "Просмотр отдельной папки":
    st.header("Просмотр отдельной папки")
    folder = st.selectbox("Выберите папку", ["Source"] + MANAGED_DIRS)
    dir_path = SOURCE_DIR if folder == "Source" else folder
    images = get_images_in_dir(dir_path)
    
    if images:
        for img_path in images:
            try:
                st.image(img_path, use_column_width=True)
                st.write(os.path.basename(img_path))
            except:
                st.write(f"Ошибка загрузки: {img_path}")
    else:
        st.write("Нет изображений в этой папке.")

elif mode == "Режим сортировки":
    st.header("Режим сортировки")
    if remaining_source_images:
        current_index = state["current_sort_index"]
        if current_index >= len(remaining_source_images):
            current_index = 0
            state["current_sort_index"] = 0
            save_state(state)
        
        img_path = remaining_source_images[current_index]
        try:
            st.image(img_path, use_column_width=True)
            st.write(os.path.basename(img_path))
        except:
            st.write(f"Ошибка загрузки: {img_path}")
            # Move to Broken if can't load
            shutil.move(img_path, os.path.join(BROKEN_DIR, os.path.basename(img_path)))
            state["processed_images"].append(img_path)
            state["current_sort_index"] = min(current_index + 1, len(remaining_source_images) - 1)
            save_state(state)
            st.experimental_rerun()

        col1, col2, col3, col4 = st.columns(4)
        if col1.button("Детали"):
            shutil.move(img_path, os.path.join(DETAILS_DIR, os.path.basename(img_path)))
            state["processed_images"].append(img_path)
            state["current_sort_index"] = min(current_index + 1, len(remaining_source_images) - 1)
            save_state(state)
            st.experimental_rerun()
        
        if col2.button("Повреждения"):
            shutil.move(img_path, os.path.join(DAMAGES_DIR, os.path.basename(img_path)))
            state["processed_images"].append(img_path)
            state["current_sort_index"] = min(current_index + 1, len(remaining_source_images) - 1)
            save_state(state)
            st.experimental_rerun()
        
        if col3.button("Корзина"):
            shutil.move(img_path, os.path.join(TRASH_DIR, os.path.basename(img_path)))
            state["processed_images"].append(img_path)
            state["current_sort_index"] = min(current_index + 1, len(remaining_source_images) - 1)
            save_state(state)
            st.experimental_rerun()
        
        if col4.button("Битое"):
            shutil.move(img_path, os.path.join(BROKEN_DIR, os.path.basename(img_path)))
            state["processed_images"].append(img_path)
            state["current_sort_index"] = min(current_index + 1, len(remaining_source_images) - 1)
            save_state(state)
            st.experimental_rerun()
    else:
        st.write("Все изображения из исходной директории отсортированы.")

elif mode == "Режим удаления (из Корзины)":
    st.header("Режим удаления из Корзины")
    trash_images = get_images_in_dir(TRASH_DIR)
    if trash_images:
        current_index = state["current_trash_index"]
        if current_index >= len(trash_images):
            current_index = 0
            state["current_trash_index"] = 0
            save_state(state)
        
        img_path = trash_images[current_index]
        try:
            st.image(img_path, use_column_width=True)
            st.write(os.path.basename(img_path))
        except:
            st.write(f"Ошибка загрузки: {img_path}")

        col1, col2, col3 = st.columns(3)
        if col1.button("Детали"):
            shutil.move(img_path, os.path.join(DETAILS_DIR, os.path.basename(img_path)))
            state["current_trash_index"] = min(current_index + 1, len(trash_images) - 1)
            save_state(state)
            st.experimental_rerun()
        
        if col2.button("Повреждения"):
            shutil.move(img_path, os.path.join(DAMAGES_DIR, os.path.basename(img_path)))
            state["current_trash_index"] = min(current_index + 1, len(trash_images) - 1)
            save_state(state)
            st.experimental_rerun()
        
        if col3.button("Удалить"):
            os.remove(img_path)
            state["current_trash_index"] = min(current_index + 1, len(trash_images) - 1)
            save_state(state)
            st.experimental_rerun()
    else:
        st.write("Нет изображений в Корзине.")

elif mode == "Режим удаления (из Битого)":
    st.header("Режим удаления из Битого")
    broken_images = get_images_in_dir(BROKEN_DIR)
    if broken_images:
        current_index = state["current_broken_index"]
        if current_index >= len(broken_images):
            current_index = 0
            state["current_broken_index"] = 0
            save_state(state)
        
        img_path = broken_images[current_index]
        try:
            st.image(img_path, use_column_width=True)
            st.write(os.path.basename(img_path))
        except:
            st.write(f"Ошибка загрузки: {img_path}")

        col1, col2 = st.columns(2)
        if col1.button("Вернуть в Source"):
            shutil.move(img_path, os.path.join(SOURCE_DIR, os.path.basename(img_path)))
            # Remove from processed if it was there
            if img_path in state["processed_images"]:
                state["processed_images"].remove(img_path)
            state["current_broken_index"] = min(current_index + 1, len(broken_images) - 1)
            save_state(state)
            st.experimental_rerun()
        
        if col2.button("Удалить"):
            os.remove(img_path)
            state["current_broken_index"] = min(current_index + 1, len(broken_images) - 1)
            save_state(state)
            st.experimental_rerun()
    else:
        st.write("Нет изображений в Битом.")

# To run the app: streamlit run this_script.py