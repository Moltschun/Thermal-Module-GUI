# -*- coding: utf-8 -*-

"""
Axion Controller Module v4.0 (Lite)
- Removed: Snapshot, Exposure, WB placeholders
- Kept: RTSP Low Latency, Digital Gain, Raw Recording
"""

import os
import time
import logging
import cv2
import numpy as np
from datetime import datetime
from threading import Thread, Lock

from PySide6.QtCore import (
    QObject, Signal, Property, QThread, 
    Slot, QMutex, QMutexLocker
)
from PySide6.QtGui import QImage, QColor
from PySide6.QtQuick import QQuickImageProvider

# === [BOOST] УСКОРЕНИЕ RTSP ===
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
    """Модуль фоновой записи (без тормозов интерфейса)"""
    def __init__(self):
        self.recording = False
        self.queue = []
        self.lock = Lock()
        self.save_thread = None
        
    def start(self):
        self.queue = []
        self.recording = True
        logger.info(">>> START RECORDING")
        
    def add_frame(self, frame):
        if self.recording:
            with self.lock:
                self.queue.append(frame.copy())
                
    def stop(self):
        self.recording = False
        logger.info(f">>> STOP RECORDING. Buffer: {len(self.queue)}")
        self.save_thread = Thread(target=self._save_worker, args=(self.queue,))
        self.save_thread.start()
        
    def _save_worker(self, frames):
        if not frames: return
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        folder = os.path.join("Recordings", f"Session_{timestamp}")
        os.makedirs(folder, exist_ok=True)
        
        logger.info(f"Saving {len(frames)} frames to {folder}...")
        for i, frame in enumerate(frames):
            fname = os.path.join(folder, f"frame_{i:04d}.tiff")
            cv2.imwrite(fname, frame)
        logger.info("Save complete.")

class AxionWorker(QThread):
    frame_ready = Signal(QImage)
    status_changed = Signal(str)
    fps_updated = Signal(float)
    
    RTSP_URL = "rtsp://admin:Admin123@192.168.1.102:554/stream/live?dev=0&chn=0"

    def __init__(self, recorder):
        super().__init__()
        self.recorder = recorder
        self.running = False
        self.cap = None
        self.digital_gain = 1.0

    def run(self):
        self.status_changed.emit("Подключение...")
        self.running = True
        
        while self.running:
            self.cap = cv2.VideoCapture(self.RTSP_URL, cv2.CAP_FFMPEG)
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            
            if not self.cap.isOpened():
                self.status_changed.emit("Ошибка сети...")
                time.sleep(2)
                continue
            
            self.status_changed.emit("ONLINE")
            fps_counter = 0
            fps_timer = time.time()
            
            while self.running and self.cap.isOpened():
                ret, frame = self.cap.read()
                if not ret: break
                
                # 1. Запись
                self.recorder.add_frame(frame)
                
                # 2. Обработка (Gain)
                display_frame = self._process_frame(frame)
                qimage = self._convert_to_qimage(display_frame)
                self.frame_ready.emit(qimage)
                
                # 3. FPS
                fps_counter += 1
                if time.time() - fps_timer >= 1.0:
                    fps = fps_counter / (time.time() - fps_timer)
                    self.fps_updated.emit(fps)
                    fps_counter = 0
                    fps_timer = time.time()

            if self.cap: self.cap.release()
                
        self.status_changed.emit("Остановлено")

    def _process_frame(self, frame):
        if self.digital_gain == 1.0: return frame
        return cv2.convertScaleAbs(frame, alpha=self.digital_gain, beta=0)

    def _convert_to_qimage(self, cv_img):
        try:
            rgb = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb.shape
            return QImage(rgb.data, w, h, ch * w, QImage.Format_RGB888).copy()
        except: return QImage()
        
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