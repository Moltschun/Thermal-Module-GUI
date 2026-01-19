# -*- coding: utf-8 -*-

"""
Axion Controller Module.

Драйвер для работы с сетевым тепловизором Pergam Axion через RTSP.
Использует OpenCV для захвата потока.
"""

import time
import logging
import cv2
import numpy as np

from PySide6.QtCore import (
    QObject, Signal, Property, QThread, 
    Slot, QMutex, QMutexLocker
)
from PySide6.QtGui import QImage, QColor
from PySide6.QtQuick import QQuickImageProvider

# Настройка логгера
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Axion_System")

class LiveImageProvider(QQuickImageProvider):
    """
    Тот же провайдер, что и раньше. Zero-Copy механизм.
    """
    def __init__(self):
        super().__init__(QQuickImageProvider.ImageType.Image)
        self._current_image = QImage(800, 600, QImage.Format_RGB888)
        self._current_image.fill(QColor("black"))
        self.mutex = QMutex()

    def requestImage(self, id, size, requestedSize):
        with QMutexLocker(self.mutex):
            return self._current_image
            
    def update_image(self, image):
        with QMutexLocker(self.mutex):
            if not image.isNull():
                self._current_image = image

class AxionWorker(QThread):
    """
    Сетевой рабочий поток.
    Захватывает RTSP поток через OpenCV.
    """
    frame_ready = Signal(QImage)
    status_changed = Signal(str)
    fps_updated = Signal(float)
    
    # === НАСТРОЙКИ ПОДКЛЮЧЕНИЯ ===
    # Ссылка из документации DALI/Pergam
    RTSP_URL = "rtsp://admin:Admin123@192.168.1.102:554/stream/live?dev=0&chn=0"

    def __init__(self):
        super().__init__()
        self.running = False
        self.cap = None
        
        # Программные настройки (Digital Processing)
        self.digital_gain = 1.0    # Умножитель яркости
        self.digital_gamma = 1.0   # Гамма-коррекция

    def run(self):
        logger.info(f"Connecting to Axion: {self.RTSP_URL}")
        self.status_changed.emit("Подключение...")
        self.running = True
        
        while self.running:
            # 1. Инициализация захвата
            self.cap = cv2.VideoCapture(self.RTSP_URL, cv2.CAP_FFMPEG)
            
            # Оптимизация буфера для снижения задержки (Latency)
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            
            if not self.cap.isOpened():
                self.status_changed.emit("Ошибка сети. Рестарт через 3с...")
                logger.error("Failed to open RTSP stream. Retrying...")
                time.sleep(3)
                continue
            
            self.status_changed.emit("Камера запущена")
            logger.info("Stream opened successfully")
            
            fps_counter = 0
            fps_timer = time.time()
            
            # 2. Цикл чтения кадров
            while self.running and self.cap.isOpened():
                ret, frame = self.cap.read()
                
                if not ret:
                    logger.warning("Frame drop or connection lost")
                    break # Выход из внутреннего цикла -> переподключение
                
                # Обработка кадра
                processed_frame = self._process_frame(frame)
                qimage = self._convert_to_qimage(processed_frame)
                
                self.frame_ready.emit(qimage)
                
                # Считаем FPS
                fps_counter += 1
                if time.time() - fps_timer >= 1.0:
                    fps = fps_counter / (time.time() - fps_timer)
                    self.fps_updated.emit(fps)
                    fps_counter = 0
                    fps_timer = time.time()

            # Если вышли из цикла чтения - освобождаем ресурсы перед рестартом
            if self.cap:
                self.cap.release()
                
        self.status_changed.emit("Остановлено")

    def _process_frame(self, frame):
        """
        Программная обработка яркости/контраста,
        так как через RTSP мы не можем менять настройки сенсора напрямую.
        """
        if self.digital_gain == 1.0 and self.digital_gamma == 1.0:
            return frame
            
        # Применяем Gain (просто умножаем пиксели)
        res = cv2.convertScaleAbs(frame, alpha=self.digital_gain, beta=0)
        return res

    def _convert_to_qimage(self, cv_img):
        """Конвертация BGR -> QImage"""
        try:
            # RTSP отдает BGR
            rgb = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb.shape
            bytes_per_line = ch * w
            img = QImage(rgb.data, w, h, bytes_per_line, QImage.Format_RGB888)
            return img.copy()
        except Exception:
            return QImage()
            
    def stop(self):
        self.running = False
        self.wait()
        
    def set_params(self, gain, gamma):
        # Gain слайдер от 0 до 40 -> переводим в множитель 1.0 ... 3.0
        # Gamma слайдер от 0.8 до 3.0
        self.digital_gain = 1.0 + (gain / 20.0) 
        self.digital_gamma = gamma # Пока не используем сложную гамму для скорости

class AxionController(QObject):
    """
    Контроллер для Pergam Axion.
    API совместим с CameraController (те же сигналы и свойства).
    """
    imagePathChanged = Signal()
    statusChanged = Signal()
    currentFpsChanged = Signal()
    
    # Свойства для совместимости с QML
    gainValueChanged = Signal()
    wbRedValueChanged = Signal() # Будет использоваться как Gamma/Brightness
    exposureValueChanged = Signal() # Заглушка

    def __init__(self):
        super().__init__()
        self._image_path = ""
        self._status = "Готов"
        self._fps = 0.0
        
        # Значения слайдеров
        self._gain = 0.0
        self._wb_red = 1.0 # Используем как доп. параметр
        self._exposure = 20000.0
        
        self.worker = None
        self.provider = None

    def set_image_provider(self, provider):
        self.provider = provider

    @Slot()
    def start_camera(self):
        if self.worker and self.worker.isRunning(): return
        
        self.worker = AxionWorker()
        self.worker.frame_ready.connect(self._on_frame)
        self.worker.status_changed.connect(self._on_status)
        self.worker.fps_updated.connect(self._on_fps)
        self.worker.start()
        
        # Применяем настройки сразу
        self.worker.set_params(self._gain, self._wb_red)

    @Slot()
    def stop_camera(self):
        if self.worker:
            self.worker.stop()
            self.worker = None

    def _on_frame(self, qimg):
        if self.provider:
            self.provider.update_image(qimg)
            self._image_path = f"image://live/frame_{time.time()}"
            self.imagePathChanged.emit()

    def _on_status(self, msg):
        self._status = msg
        self.statusChanged.emit()

    def _on_fps(self, val):
        self._fps = val
        self.currentFpsChanged.emit()
        
    @Slot(str, str, int)
    def capture_photo(self, path, fmt, q):
        # Заглушка для фото
        logger.info(f"Снимок сохранен в {path}")

    # === QML PROPERTIES ===
    
    @Property(str, notify=imagePathChanged)
    def imagePath(self): return self._image_path

    @Property(str, notify=statusChanged)
    def status(self): return self._status

    @Property(float, notify=currentFpsChanged)
    def currentFps(self): return self._fps

    # --- Слайдеры ---
    # Gain
    @Property(float, notify=gainValueChanged)
    def gainValue(self): return self._gain
    @gainValue.setter
    def gainValue(self, val):
        self._gain = val
        if self.worker: self.worker.set_params(self._gain, self._wb_red)
        self.gainValueChanged.emit()

    # WB Red (используем как Gamma/Contrast в этом контроллере)
    @Property(float, notify=wbRedValueChanged)
    def wbRedValue(self): return self._wb_red
    @wbRedValue.setter
    def wbRedValue(self, val):
        self._wb_red = val
        if self.worker: self.worker.set_params(self._gain, self._wb_red)
        self.wbRedValueChanged.emit()

    # Exposure (пока заглушка, т.к. по RTSP нельзя менять выдержку)
    @Property(float, notify=exposureValueChanged)
    def exposureValue(self): return self._exposure
    @exposureValue.setter
    def exposureValue(self, val):
        self._exposure = val
        self.exposureValueChanged.emit()