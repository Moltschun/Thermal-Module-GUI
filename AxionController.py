# -*- coding: utf-8 -*-

"""
Axion Controller v13.1 (Thermal Edition)
- Palette: IRON (via cv2.COLORMAP_INFERNO)
- Hardware: Optimized for Raspberry Pi 5
"""

import os
import glob
import numpy as np
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

# Оптимизация задержки для RTSP
os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;udp|fflags;nobuffer|flags;low_delay"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Axion_System")

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
        logger.info(">>> ЗАПИСЬ СТАРТ: Режим IRON")
        
    def add_frame(self, frame):
        if self.recording:
            with self.lock:
                self.queue.append(frame.copy())
                
    def stop(self):
        self.recording = False
        duration = time.time() - self.start_time
        count = len(self.queue)
        logger.info(f">>> ЗАПИСЬ ЗАВЕРШЕНА. Кадров: {count}")
        Thread(target=self._save_worker, args=(list(self.queue),), daemon=True).start()
        with self.lock:
            self.queue = []

    def _save_worker(self, frames):
        if not frames: return
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        folder = os.path.join("Recordings", f"Thermal_{timestamp}")
        os.makedirs(folder, exist_ok=True)
        for i, frame in enumerate(frames):
            fname = os.path.join(folder, f"frame_{i:04d}.tiff")
            cv2.imwrite(fname, frame)
        logger.info(f"Данные сохранены в {folder}")

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
        self.status_changed.emit("Захват...")
        self.running = True
        
        cap = cv2.VideoCapture(self.RTSP_URL, cv2.CAP_FFMPEG)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 0)
        
        if not cap.isOpened():
            self.status_changed.emit("ОШИБКА СЕНСОРА")
            return
            
        self.status_changed.emit("ONLINE")
        fps_counter = 0
        fps_timer = time.time()
        last_rec_time = 0.0
        
        while self.running and cap.isOpened():
            ret, frame = cap.read()
            if not ret: break
            
            # 1. Применяем усиление (Gain)
            if self.digital_gain != 1.0:
                frame = cv2.convertScaleAbs(frame, alpha=self.digital_gain, beta=0)

            # 2. ПРЕОБРАЗОВАНИЕ В IRON (Inferno)
            # Если камера выдает цветной шум, переводим в ч/б для чистого наложения карты
            if len(frame.shape) == 3:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            else:
                gray = frame
            
            # Накладываем палитру IRON
            thermal_frame = cv2.applyColorMap(gray, cv2.COLORMAP_INFERNO)
            
            now = time.time()
            # 3. Динамическая запись (Smart FPS)
            if self.recorder.recording:
                elapsed = now - self.recorder.start_time
                target_rec_fps = 25.0 if elapsed < 25.0 else (15.0 if elapsed < 50.0 else 5.0)
                if (now - last_rec_time) >= (1.0 / target_rec_fps):
                    self.recorder.add_frame(thermal_frame)
                    last_rec_time = now
            
            # 4. Вывод в UI
            try:
                # В OpenCV после applyColorMap получаем BGR, конвертируем в RGB для Qt
                rgb = cv2.cvtColor(thermal_frame, cv2.COLOR_BGR2RGB)
                h, w, ch = rgb.shape
                qimg = QImage(rgb.data, w, h, ch * w, QImage.Format_RGB888).copy()
                self.frame_ready.emit(qimg)
            except Exception:
                pass

            fps_counter += 1
            if now - fps_timer >= 1.0:
                self.fps_updated.emit(fps_counter / (now - fps_timer))
                fps_counter = 0
                fps_timer = now

        cap.release()
        self.status_changed.emit("OFFLINE")

    def stop(self):
        self.running = False
        self.wait()
        
    def set_gain(self, val):
        self.digital_gain = 1.0 + (val / 20.0)

class AxionController(QObject):
    imagePathChanged = Signal()
    statusChanged = Signal()
    currentFpsChanged = Signal()
    gainValueChanged = Signal()
    isRecordingChanged = Signal()
    progressChanged = Signal(float)

    def __init__(self):
        super().__init__()
        self._image_path = ""
        self._status = "Инициализация"
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
        self.worker.set_gain(self._gain)
        self.worker.start()

    @Slot()
    def stop_camera(self):
        if self.worker:
            self.worker.stop()
            self.worker = None
        self._status = "ОТКЛЮЧЕНО"
        self.statusChanged.emit()

    @Slot()
    def toggle_recording(self):
        if self.recorder.recording: self.recorder.stop()
        else: self.recorder.start()
        self.isRecordingChanged.emit()

    @Slot()
    def convert_to_npy(self):
        recordings_path = "Recordings"
        if not os.path.exists(recordings_path): return
        sessions = [os.path.join(recordings_path, d) for d in os.listdir(recordings_path) if d.startswith("Thermal_")]
        if not sessions: return
        
        last_session = max(sessions, key=os.path.getctime)
        
        def run_conversion():
            files = sorted(glob.glob(os.path.join(last_session, "*.tiff")))
            if not files: return
            frames = [cv2.imread(f) for f in files]
            # Сохраняем уже в IRON-палитре (RGB)
            frames_rgb = [cv2.cvtColor(f, cv2.COLOR_BGR2RGB) for f in frames if f is not None]
            np.save(last_session + ".npy", np.array(frames_rgb, dtype=np.uint8))
            logger.info(f"Массив NumPy готов: {last_session}.npy")

        Thread(target=run_conversion, daemon=True).start()

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