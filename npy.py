import numpy as np
import cv2
import os
import glob

def manual_thermal_scan():
    # 1. Поиск файлов .npy
    search_path = os.path.join("Recordings", "*.npy")
    files = glob.glob(search_path)
    
    if not files:
        print("[-] Ошибка: Файлы .npy не обнаружены.")
        return

    latest_file = max(files, key=os.path.getctime)
    print(f"[+] Загрузка: {latest_file}")

    try:
        # Загрузка 4D массива
        video_data = np.load(latest_file)
        total_frames = video_data.shape[0]
        
        print(f"[+] Управление:")
        print("    ->  Стрелка ВПРАВО: Следующий кадр")
        print("    <-  Стрелка ВЛЕВО: Предыдущий кадр")
        print("    ESC / Q: Выход")
        
        current_idx = 0
        
        while True:
            # Подготовка кадра
            frame = video_data[current_idx]
            # Возвращаем в BGR для OpenCV
            display_frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            
            # Индикация прогресса на кадре
            info_text = f"Frame: {current_idx + 1} / {total_frames}"
            cv2.putText(display_frame, info_text, (20, 40), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
            
            cv2.imshow("Manual Axion Scan", display_frame)

            # Ожидание нажатия клавиши
            # waitKey(0) заставляет программу ждать бесконечно до нажатия
            key = cv2.waitKeyEx(0) 

            # Коды клавиш (могут варьироваться от ОС, это стандарт для Windows)
            if key == 2555904 or key == ord('d') or key == 83: # Стрелка вправо
                if current_idx < total_frames - 1:
                    current_idx += 1
            
            elif key == 2424832 or key == ord('a') or key == 81: # Стрелка влево
                if current_idx > 0:
                    current_idx -= 1
                    
            elif key == 27 or key == ord('q'): # ESC или Q
                break

        cv2.destroyAllWindows()
        print("[+] Сканирование завершено.")

    except Exception as e:
        print(f"[-] Ошибка: {e}")

if __name__ == "__main__":
    manual_thermal_scan()