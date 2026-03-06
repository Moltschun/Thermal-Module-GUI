# -*- coding: utf-8 -*-

import os
import glob
import numpy as np
import cv2
import time
from scipy.io import savemat

def convert_latest_session_to_mat():
    recordings_path = "Recordings"
    
    # Проверка наличия директории
    if not os.path.exists(recordings_path):
        print("[-] Ошибка: Директория Recordings не обнаружена.")
        return

    # Поиск сессий
    sessions = [os.path.join(recordings_path, d) for d in os.listdir(recordings_path) if d.startswith("Thermal_")]
    if not sessions:
        print("[-] Ошибка: Сессии записи не найдены.")
        return
        
    # Выбор последней сессии
    last_session = max(sessions, key=os.path.getctime)
    print(f"[+] Обнаружена последняя сессия: {last_session}")
    
    # Сбор TIFF файлов
    files = sorted(glob.glob(os.path.join(last_session, "*.tiff")))
    if not files:
        print("[-] Ошибка: В выбранной сессии нет .tiff файлов.")
        return
        
    print(f"[+] Начат процесс сборки {len(files)} кадров. Пожалуйста, подождите...")
    
    # Чтение и конвертация кадров
    frames = [cv2.imread(f) for f in files]
    frames_rgb = [cv2.cvtColor(f, cv2.COLOR_BGR2RGB) for f in frames if f is not None]
    
    # Формирование 4D массива NumPy (Кадры, Высота, Ширина, Каналы)
    video_data = np.array(frames_rgb, dtype=np.uint8)
    
    # Формирование требуемой структуры для MATLAB
    mat_structure = {
        "data": video_data,
        "frequency": 25.0, 
        "info": "Thermal sensor data. Palette: IRON."
    }
    
    # Сохранение в .mat
    output_filename = last_session + ".mat"
    savemat(output_filename, mat_structure)
    
    print(f"[+] Успех. Данные сохранены в формате MATLAB: {output_filename}")

if __name__ == "__main__":
    convert_latest_session_to_mat()