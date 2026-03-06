import scipy.io as sio
import cv2
import numpy as np
import tkinter as tk
from tkinter import filedialog

def open_and_view_mat():
    # Создаем скрытое окно для вызова диалога Windows
    root = tk.Tk()
    root.withdraw()
    
    file_path = filedialog.askopenfilename(
        title="Выберите файл тепловизионных данных",
        filetypes=[("MATLAB Files", "*.mat")]
    )
    
    if not file_path:
        print("[-] Операция отменена пользователем.")
        return

    try:
        # Загрузка данных
        payload = sio.loadmat(file_path)
        data = payload['data']
        info = payload['info'][0] # Извлекаем строку из массива объектов MATLAB
        
        total_frames = data.shape[0]
        curr = 0
        
        print(f"[+] Файл загружен: {file_path}")
        print(f"[+] Метаданные: {info}")
        print("[!] Управление: 'D' - вперед, 'A' - назад, 'ESC' - выход")

        while True:
            # Преобразуем RGB (Matlab) в BGR (OpenCV)
            frame = cv2.cvtColor(data[curr], cv2.COLOR_RGB2BGR)
            
            # Рендерим интерфейс поверх кадра
            header = f"Frame: {curr + 1}/{total_frames}"
            cv2.rectangle(frame, (0, 0), (220, 40), (0, 0, 0), -1)
            cv2.putText(frame, header, (10, 25), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

            cv2.imshow("Axion MAT Viewer", frame)
            
            key = cv2.waitKey(0) & 0xFF
            
            if key == ord('d') or key == 83: # Вправо
                curr = (curr + 1) % total_frames
            elif key == ord('a') or key == 81: # Влево
                curr = (curr - 1) % total_frames
            elif key == 27 or key == ord('q'): # ESC или Q
                break
                
        cv2.destroyAllWindows()
        
    except KeyError:
        print("[-] Ошибка: В файле отсутствуют ключи 'data' или 'info'.")
    except Exception as e:
        print(f"[-] Критическая ошибка: {e}")

if __name__ == "__main__":
    open_and_view_mat()