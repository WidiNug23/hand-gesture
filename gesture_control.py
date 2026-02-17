import cv2
import math
import numpy as np
import mediapipe as mp
import pyautogui
import time
import winsound
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
from ctypes import cast, POINTER
from comtypes import CLSCTX_ALL
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
import screen_brightness_control as sbc

# =========================
# AUDIO SYSTEM VOLUME SETUP
# =========================
devices = AudioUtilities.GetSpeakers()
interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
volume = cast(interface, POINTER(IAudioEndpointVolume))

# =========================
# MEDIAPIPE HAND DETECTION SETUP
# =========================
model_path = "hand_landmarker.task"
base_options = python.BaseOptions(model_asset_path=model_path)
options = vision.HandLandmarkerOptions(
    base_options=base_options,
    num_hands=2
)
detector = vision.HandLandmarker.create_from_options(options)

# =========================
# CAMERA SETUP
# =========================
cap = cv2.VideoCapture(0)
print("Sistem berjalan... Tekan 'q' untuk keluar.")

# =========================
# STATE VARIABLES
# =========================
control_mode = False
toggle_cooldown = 0
toggle_delay = 2

last_action_time = 0
last_screenshot_time = 0
delay = 1.2

pinch_hold_time = 0.3
pinch_start_time = 0
pinch_active_mode = False

smooth_brightness = 0
smooth_volume = 0
smoothing_factor = 0.15

# =========================
# SCREENSHOT TEXT STATE
# =========================
screenshot_text_time = 0
screenshot_text_duration = 0.8  # tampil 0.8 detik

# =========================
# MAIN LOOP
# =========================
while cap.isOpened():
    success, img = cap.read()
    if not success:
        break

    img = cv2.flip(img, 1)
    h, w, _ = img.shape
    rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
    result = detector.detect(mp_image)
    current_time = time.time()

    if result.hand_landmarks:
        for idx, landmarks in enumerate(result.hand_landmarks):
            handedness = result.handedness[idx][0].category_name

            # =========================
            # GAMBAR TITIK JARI
            # =========================
            for lm in landmarks:
                cx, cy = int(lm.x * w), int(lm.y * h)
                cv2.circle(img, (cx, cy), 4, (0, 255, 0), -1)

            # =========================
            # LANDMARK JARI
            # =========================
            thumb_tip = landmarks[4]
            index_tip = landmarks[8]
            thumb_ip = landmarks[3]
            index_pip = landmarks[6]
            middle_tip = landmarks[12]
            middle_pip = landmarks[10]
            ring_tip = landmarks[16]
            ring_pip = landmarks[14]
            pinky_tip = landmarks[20]
            pinky_pip = landmarks[18]

            # =========================
            # DETEKSI JARI TERBUKA
            # =========================
            if handedness == "Right":
                thumb_open = thumb_tip.x > thumb_ip.x
            else:
                thumb_open = thumb_tip.x < thumb_ip.x

            index_open = index_tip.y < index_pip.y
            middle_open = middle_tip.y < middle_pip.y
            ring_open = ring_tip.y < ring_pip.y
            pinky_open = pinky_tip.y < pinky_pip.y
            total_open = [thumb_open, index_open, middle_open, ring_open, pinky_open].count(True)

            # =========================
            # TOGGLE CONTROL MODE (KEPAL)
            # =========================
            fist = total_open == 0
            if fist and current_time - toggle_cooldown > toggle_delay:
                control_mode = not control_mode
                toggle_cooldown = current_time
                if control_mode:
                    winsound.Beep(1200, 300)
                else:
                    winsound.Beep(500, 400)

            # =========================
            # TAMPILKAN STATUS MODE
            # =========================
            mode_text = "CONTROL MODE ON" if control_mode else "CONTROL MODE OFF"
            mode_color = (0, 255, 0) if control_mode else (0, 0, 255)
            cv2.putText(img, mode_text, (w//2 - 150, 40),
                        cv2.FONT_HERSHEY_DUPLEX, 1, mode_color, 2)

            if not control_mode:
                continue

            # =========================
            # GESTURE RIGHT HAND FIRST (PRIORITAS)
            # =========================
            if handedness == "Right":
                # ✋ Play / Pause → semua jari kecuali ibu jari terbuka
                if index_open and middle_open and ring_open and pinky_open and not thumb_open:
                    if current_time - last_action_time > delay:
                        pyautogui.press("space")
                        last_action_time = current_time

                # ✌️ Screenshot → index & middle terbuka
                elif index_open and middle_open and not ring_open and not pinky_open and not thumb_open:
                    if current_time - last_screenshot_time > delay:
                        pyautogui.screenshot(f"screenshot_{int(current_time)}.png")
                        last_screenshot_time = current_time
                        screenshot_text_time = current_time

            # =========================
            # PINCH DISTANCE (HANYA UNTUK VOLUME / BRIGHTNESS)
            # =========================
            x1, y1 = int(thumb_tip.x * w), int(thumb_tip.y * h)
            x2, y2 = int(index_tip.x * w), int(index_tip.y * h)
            distance = math.hypot(x2 - x1, y2 - y1)

            pinch_threshold = 250  # harus benar-benar dekat
            pinch_active_mode = distance < pinch_threshold

            # =========================
            # LEFT HAND → BRIGHTNESS CONTROL
            # =========================
            if handedness == "Left" and pinch_active_mode:
                target_brightness = min(max((distance / pinch_threshold) * 130, 0), 100)
                smooth_brightness = smooth_brightness * (1 - smoothing_factor) + target_brightness * smoothing_factor
                sbc.set_brightness(int(smooth_brightness))
                cv2.putText(img,
                            f'BRIGHTNESS: {int(smooth_brightness)}%',
                            (20, 100),
                            cv2.FONT_HERSHEY_DUPLEX,
                            1,
                            (0, 255, 0),
                            2)

            # =========================
            # RIGHT HAND → VOLUME CONTROL
            # =========================
            elif handedness == "Right" and pinch_active_mode:
                target_volume = min(max((distance / pinch_threshold) * 130, 0), 70)
                smooth_volume = smooth_volume * (1 - smoothing_factor) + target_volume * smoothing_factor
                volume.SetMasterVolumeLevelScalar(smooth_volume / 100, None)
                cv2.putText(img,
                            f'VOLUME: {int(smooth_volume)}%',
                            (w - 320, 100),
                            cv2.FONT_HERSHEY_DUPLEX,
                            1,
                            (255, 0, 0),
                            2)

            # =========================
            # VISUAL GARIS PINCH (SELALU ANTARA THUMB & INDEX)
            # =========================
            if pinch_active_mode:
                cv2.line(img, (x1, y1), (x2, y2), (255, 255, 255), 2)
                cv2.circle(img, (x1, y1), 8, (0, 255, 0), -1)
                cv2.circle(img, (x2, y2), 8, (0, 255, 0), -1)

    # =========================
    # TAMPILKAN TEKS SCREENSHOT JIKA BARU SAJA DIAMBIL
    # =========================
    if current_time - screenshot_text_time < screenshot_text_duration:
        cv2.putText(img,
                    "Screenshot Taken",
                    (w//2 - 150, h - 40),
                    cv2.FONT_HERSHEY_DUPLEX,
                    1,
                    (255, 255, 0),
                    2)

    # =========================
    # TAMPILKAN FRAME
    # =========================
    cv2.imshow("adalah pokonya", img)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
