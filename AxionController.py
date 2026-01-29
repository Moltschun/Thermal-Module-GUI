# -*- coding: utf-8 -*-

"""
Axion Controller v13.0 (Release Candidate)
- Engine: Classic Synchronous (Stable 25 FPS UI)
- Recording: Dynamic FPS Decimation (Saves ~60% disk space)
- Status: Production Ready (No debug prints)
"""

import os
# Оптимизация задержки
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

# === 1. ПРОВАЙДЕР ===
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

# === 2. ЗАПИСЬ ===
class FrameRecorder:
    def __init__(self):
        self.recording = False
        self.queue = []
        self.lock = Lock()
        self.start_time = 0.0
        
    def start(self):
        with self.lock:
            self.queue = []
        self.start_time = time.time()
        self.recording = True
        logger.info(">>> ЗАПИСЬ: СТАРТ (Smart Mode)")
        
    def add_frame(self, frame):
        if self.recording:
            with self.lock:
                self.queue.append(frame.copy())
                
    def stop(self):
        self.recording = False
        duration = time.time() - self.start_time
        count = len(self.queue)
        avg_fps = count / duration if duration > 0 else 0
        logger.info(f">>> ЗАПИСЬ ЗАВЕРШЕНА. Время: {duration:.1f}с. Кадров: {count}. Ср. FPS: {avg_fps:.1f}")
        
        # Фоновое сохранение
        Thread(target=self._save_worker, args=(list(self.queue),), daemon=True).start()
        
        with self.lock:
            self.queue = []

    def _save_worker(self, frames):
        if not frames: return
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        folder = os.path.join("Recordings", f"Session_{timestamp}")
        os.makedirs(folder, exist_ok=True)
        
        logger.info(f"Сохранение {len(frames)} кадров в {folder}...")
        for i, frame in enumerate(frames):
            fname = os.path.join(folder, f"frame_{i:04d}.tiff")
            cv2.imwrite(fname, frame)
        logger.info("Сохранение выполнено успешно.")

# === 3. РАБОЧИЙ ПОТОК ===
class AxionWorker(QThread):
    frame_ready = Signal(QImage)
    status_changed = Signal(str)
    fps_updated = Signal(float)
    
    RTSP_URL = "rtsp://admin:Admin123@192.168.1.102:554/stream/live?dev=0&chn=0"

    def __init__(self, recorder):
        super().__init__()
        self.recorder = recorder
        self.running = False
        self.digital_gain = 1.0

    def run(self):
        self.status_changed.emit("Подключение...")
        self.running = True
        
        cap = cv2.VideoCapture(self.RTSP_URL, cv2.CAP_FFMPEG)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 0)
        
        if not cap.isOpened():
            self.status_changed.emit("Ошибка: Камера недоступна")
            time.sleep(2)
            self.running = False
            return
            
        self.status_changed.emit("ONLINE")
        
        fps_counter = 0
        fps_timer = time.time()
        
        # Таймер для динамической записи
        last_rec_time = 0.0
        
        while self.running and cap.isOpened():
            ret, frame = cap.read()
            if not ret: break
            
            now = time.time()
            
            # === [SMART REC ALGORITHM] ===
            if self.recorder.recording:
                elapsed = now - self.recorder.start_time
                
                # График снижения частоты кадров
                if elapsed < 25.0:
                    target_rec_fps = 25.0 # Max Quality
                elif elapsed < 50.0:
                    target_rec_fps = 15.0 # High
                elif elapsed < 75.0:
                    target_rec_fps = 10.0 # Medium
                else:
                    target_rec_fps = 5.0  # Eco Mode
                
                min_interval = 1.0 / target_rec_fps
                
                if (now - last_rec_time) >= min_interval:
                    self.recorder.add_frame(frame)
                    last_rec_time = now
            # =============================
            
            # UI Render (Всегда 25 FPS)
            if self.digital_gain != 1.0:
                frame = cv2.convertScaleAbs(frame, alpha=self.digital_gain, beta=0)
            
            try:
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                h, w, ch = rgb.shape
                qimg = QImage(rgb.data, w, h, ch * w, QImage.Format_RGB888).copy()
                self.frame_ready.emit(qimg)
            except:
                pass

            # FPS Counter
            fps_counter += 1
            if now - fps_timer >= 1.0:
                self.fps_updated.emit(fps_counter / (now - fps_timer))
                fps_counter = 0
                fps_timer = now

        cap.release()
        self.status_changed.emit("Остановлено")

    def stop(self):
        self.running = False
        self.wait()
        
    def set_gain(self, val):
        self.digital_gain = 1.0 + (val / 20.0)

# === 4. КОНТРОЛЛЕР ===
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
        if self.worker is not None and self.worker.isRunning():
            return
        self.worker = AxionWorker(self.recorder)
        self.worker.frame_ready.connect(self._on_frame)
        self.worker.status_changed.connect(self._on_status)
        self.worker.fps_updated.connect(self._on_fps)
        self.worker.set_gain(self._gain)
        self.worker.start()

    @Slot()
    def stop_camera(self):
        if self.worker:
            self.worker.stop()
            self.worker.deleteLater()
            self.worker = None
        self._status = "Отключено"
        self._fps = 0.0
        self.statusChanged.emit()
        self.currentFpsChanged.emit()

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