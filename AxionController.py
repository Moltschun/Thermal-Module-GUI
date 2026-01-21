# -*- coding: utf-8 -*-

"""
Axion Controller v6.0 (Zero Latency Fix)
- FIXED: FFMPEG flags applied BEFORE importing cv2 (Critical!)
- Architecture: Reader Thread (Net) + Worker Thread (UI)
"""

import os

# === [КРИТИЧЕСКИ ВАЖНО] ===
# Настройки должны быть строго ДО импорта cv2!
# Иначе библиотека загрузится с дефолтным буфером в 3 секунды.
os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;udp|fflags;nobuffer|flags;low_delay"

import time
import logging
import cv2
import threading
from threading import Thread, Lock

from PySide6.QtCore import (
    QObject, Signal, Property, QThread, 
    Slot, QMutex, QMutexLocker
)
from PySide6.QtGui import QImage, QColor
from PySide6.QtQuick import QQuickImageProvider

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Axion_System")

# === 1. ПРОВАЙДЕР ДЛЯ QML ===
class LiveImageProvider(QQuickImageProvider):
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

# === 2. ФОНОВАЯ ЗАПИСЬ ===
class FrameRecorder:
    def __init__(self):
        self.recording = False
        self.queue = []
        self.lock = Lock()
        
    def start(self):
        with self.lock:
            self.queue = []
        self.recording = True
        logger.info(">>> ЗАПИСЬ НАЧАТА")
        
    def add_frame(self, frame):
        if self.recording:
            with self.lock:
                self.queue.append(frame.copy())
                
    def stop(self):
        self.recording = False
        logger.info(f">>> ОСТАНОВКА ЗАПИСИ. Буфер: {len(self.queue)}")
        Thread(target=self._save_worker, args=(list(self.queue),), daemon=True).start()
        with self.lock:
            self.queue = []

    def _save_worker(self, frames):
        if not frames: return
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        folder = os.path.join("Recordings", f"Session_{timestamp}")
        os.makedirs(folder, exist_ok=True)
        
        logger.info(f"Сохранение: {folder}...")
        for i, frame in enumerate(frames):
            fname = os.path.join(folder, f"frame_{i:04d}.tiff")
            cv2.imwrite(fname, frame)
        logger.info("Сохранение завершено.")

# === 3. ПОТОК-ЧИТАТЕЛЬ (СЕТЬ) ===
class RTSPReader(Thread):
    def __init__(self, url):
        super().__init__()
        self.url = url
        self.running = False
        self.latest_frame = None
        self.lock = Lock()
        self.connected = False

    def run(self):
        self.running = True
        logger.info(f"Reader Start: {self.url}")
        
        while self.running:
            # Явно указываем бэкенд FFMPEG
            cap = cv2.VideoCapture(self.url, cv2.CAP_FFMPEG)
            
            # Агрессивное отключение буфера
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 0) 
            
            if not cap.isOpened():
                self.connected = False
                time.sleep(1)
                continue
            
            self.connected = True
            logger.info("RTSP Connected! Draining buffer...")
            
            while self.running and cap.isOpened():
                ret, frame = cap.read()
                if not ret: break
                
                # Мгновенная перезапись (Drop frame policy)
                with self.lock:
                    self.latest_frame = frame
            
            cap.release()
            self.connected = False

    def get_frame(self):
        with self.lock:
            return self.latest_frame

    def stop(self):
        self.running = False
        self.join()

# === 4. ПОТОК-ХУДОЖНИК (UI) ===
class AxionWorker(QThread):
    frame_ready = Signal(QImage)
    status_changed = Signal(str)
    fps_updated = Signal(float)
    
    RTSP_URL = "rtsp://admin:Admin123@192.168.1.102:554/stream/live?dev=0&chn=0"

    def __init__(self, recorder):
        super().__init__()
        self.recorder = recorder
        self.running = False
        self.reader = None
        self.digital_gain = 1.0

    def run(self):
        self.status_changed.emit("Запуск...")
        self.running = True
        
        self.reader = RTSPReader(self.RTSP_URL)
        self.reader.start()
        
        fps_counter = 0
        fps_timer = time.time()
        
        # Переменная для проверки "свежести" кадра
        last_frame_id = 0 
        
        while self.running:
            if not self.reader.connected:
                self.status_changed.emit("Поиск сети...")
                time.sleep(0.1)
                continue
            
            self.status_changed.emit("ONLINE")
            
            frame = self.reader.get_frame()
            
            # Проверка: если кадр тот же самый (Reader не успел получить новый),
            # мы не перерисовываем его, чтобы не грузить UI зря.
            # Но так как объекты frame в памяти меняются, просто проверим на None
            if frame is None:
                time.sleep(0.001)
                continue
                
            # 1. Запись
            self.recorder.add_frame(frame)
            
            # 2. Gain
            if self.digital_gain != 1.0:
                frame = cv2.convertScaleAbs(frame, alpha=self.digital_gain, beta=0)
            
            # 3. Конвертация
            try:
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                h, w, ch = rgb.shape
                qimg = QImage(rgb.data, w, h, ch * w, QImage.Format_RGB888).copy()
                self.frame_ready.emit(qimg)
            except Exception:
                pass

            # 4. FPS
            fps_counter += 1
            if time.time() - fps_timer >= 1.0:
                real_fps = fps_counter / (time.time() - fps_timer)
                self.fps_updated.emit(real_fps)
                fps_counter = 0
                fps_timer = time.time()
                
            # Важно: даем Reader'у шанс захватить управление (GIL)
            time.sleep(0.005) 

        if self.reader:
            self.reader.stop()
        self.status_changed.emit("Остановлено")

    def stop(self):
        self.running = False
        self.wait()
        
    def set_gain(self, val):
        self.digital_gain = 1.0 + (val / 20.0)

# === 5. КОНТРОЛЛЕР ===
class AxionController(QObject):
    imagePathChanged = Signal()
    statusChanged = Signal()
    currentFpsChanged = Signal()
    gainValueChanged = Signal()
    isRecordingChanged = Signal()

    def __init__(self):
        super().__init__()
        self._image_path = ""
        self._status = "Готов"
        self._fps = 0.0
        self._gain = 0.0
        self.recorder = FrameRecorder()
        self.worker = None
        self.provider = None

    def set_image_provider(self, provider):
        self.provider = provider

    @Slot()
    def start_camera(self):
        if self.worker and self.worker.isRunning(): return
        self.worker = AxionWorker(self.recorder)
        self.worker.frame_ready.connect(self._on_frame)
        self.worker.status_changed.connect(self._on_status)
        self.worker.fps_updated.connect(self._on_fps)
        self.worker.start()
        self.worker.set_gain(self._gain)

    @Slot()
    def stop_camera(self):
        if self.worker:
            self.worker.stop()
            self.worker = None

    @Slot()
    def toggle_recording(self):
        if self.recorder.recording:
            self.recorder.stop()
        else:
            self.recorder.start()
        self.isRecordingChanged.emit()

    @Property(bool, notify=isRecordingChanged)
    def isRecording(self): return self.recorder.recording

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

    @Property(str, notify=imagePathChanged)
    def imagePath(self): return self._image_path

    @Property(str, notify=statusChanged)
    def status(self): return self._status

    @Property(float, notify=currentFpsChanged)
    def currentFps(self): return self._fps

    @Property(float, notify=gainValueChanged)
    def gainValue(self): return self._gain
    @gainValue.setter
    def gainValue(self, val):
        self._gain = val
        if self.worker: self.worker.set_gain(val)
        self.gainValueChanged.emit()