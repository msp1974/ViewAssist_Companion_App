# View Assist Companion App

[![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg?style=for-the-badge)](https://github.com/hacs/integration)
[![downloads](https://shields.io/github/downloads/msp1974/ViewAssist_Companion_App/latest/total?style=for-the-badge)](https://github.com/msp1974/ViewAssist_Companion_App)
[![downloads](https://shields.io/github/downloads/msp1974/ViewAssist_Companion_App/total?style=for-the-badge)](https://github.com/msp1974/ViewAssist_Companion_App)
[![version](https://shields.io/github/v/release/msp1974/ViewAssist_Companion_App?style=for-the-badge)](https://github.com/msp1974/ViewAssist_Companion_App)
[![Latest Release](https://img.shields.io/badge/dynamic/json?style=for-the-badge&color=41BDF5&logo=home-assistant&label=integration%20usage&suffix=%20installs&cacheSeconds=15600&url=https://analytics.home-assistant.io/custom_integrations.json&query=$.vaca.total)](https://analytics.home-assistant.io/custom_integrations.json)

**The easiest way to build your own smart display with View Assist and Home Assistant!**

View Assist Companion App (VACA for short) is an Android app and Home Assistant integration that turns an old Android device into a voice controlled smart display. Together with the amazing [View Assist project by @dinki](https://github.com/dinki/View-Assist), you can build your own Alexa Show or Google Home replacement.

Other solutions have historically needed a mix of apps for voice and display, with an involved setup. VACA is a one-stop shop for voice, media and browser display, all from a single Android app install. It is built for View Assist, but works without it too.

<p align="center">
  <a href="https://github.com/msp1974/ViewAssist_Companion_App/wiki/Getting-Started"><b>🚀 Get Started</b></a> &nbsp;•&nbsp;
  <a href="https://github.com/msp1974/ViewAssist_Companion_App/wiki"><b>📖 Wiki</b></a> &nbsp;•&nbsp;
  <a href="https://github.com/msp1974/ViewAssist_Companion_App/issues"><b>🐛 Issues</b></a> &nbsp;•&nbsp;
  <a href="https://discord.gg/3WXXfGAf8T"><b>💬 Discord</b></a>
</p>

## ✨ Key Features

| | |
|---|---|
| 🎙️ **On-device voice** | Wake word detection runs on the device, so there is no audio streaming until you speak and no need for openWakeWord in your HA setup. Supports OpenWakeWord (onnx and tflite) and MicroWakeWord engines, with built-in wake words or your own custom ones. |
| 🏠 **Native Assist integration** | Appears in Home Assistant as an Assist satellite. Choose the voice assistant per device, with continued conversation, announcements and start conversation support. |
| 🖥️ **Browser display** | Automatically loads your HA dashboards and View Assist views. Control dark mode, zoom and text size. |
| 🔆 **Device screen control** | Control the screen from Home Assistant: on/off, brightness and auto brightness, screen always on, timeout, orientation, screen saver and status bar. Wake the screen with the wake word, motion, proximity or a bump, and use gesture and proximity events in your automations. |
| 🎵 **Media** | A media player for music, radio and alerts, with Sendspin / Music Assistant support, separate volumes for voice, music, alarms and ducking, and alarm sounds. |
| 📷 **Camera & motion** | Camera motion and face detection with adjustable motion sensitivity, plus a camera stream from the device. |
| 📡 **Bluetooth proxy** | Use the device as a Bluetooth proxy for Home Assistant. |
| 🎧 **Flexible audio** | Select Bluetooth, USB or wired microphones and speakers, with mic gain and noise suppression. |
| ⚙️ **Highly configurable** | A large number of switches, selects and numbers per device, an on-device settings menu and in-app updates. |

## 🧩 What You Get in Home Assistant

Each device is added with a full set of entities and an action for your automations.

| Type | Examples |
|---|---|
| **Assist satellite** | Voice pipeline, announcements, start conversation |
| **Media player** | Play media, volume and stop, with Sendspin support |
| **Switches** | Mute, screen, auto brightness, screen always on, dark mode, do not disturb, continue conversation, alarm, screen saver, motion detection, screen-on triggers, Sendspin, Bluetooth proxy, video stream |
| **Selects** | Assistant, wake word engine, wake word and sound, screen timeout, orientation, audio input / output, noise suppression, alarm sound |
| **Numbers** | Mic gain, screen brightness, voice / music / alarm / ducking volume, wake word threshold, zoom, text size, motion / bump / proximity sensitivity |
| **Sensors** | Battery, light level, orientation, current path, last motion, app version, last speech (STT), last response (TTS), last intent |
| **Binary sensors** | Connected, battery charging, screen, motion |
| **Buttons** | Wake, interrupt, refresh, wake screen, sleep screen |
| **Events** | Gesture, proximity |
| **Camera** | Device camera stream |

### ⚙️ Configuration Options

Most settings are available in the Home Assistant device page, and the majority are also available on the device in Quick Actions → Menu → Configuration. See [Configuration Options](https://github.com/msp1974/ViewAssist_Companion_App/wiki/Configuration-Options) for what each one does.

<p align="center">
  <img width="480" alt="Configuration options" src="https://github.com/user-attachments/assets/bb461af9-751b-446f-83a5-c8352ba3a62a" />
</p>

<p align="center">
  <img width="300" alt="Configuration entities, part 1" src="https://github.com/user-attachments/assets/167a6a63-eebc-4b9a-baff-509e78e56a69" />
  &nbsp;
  <img width="300" alt="Configuration entities, part 2" src="https://github.com/user-attachments/assets/8da86fe9-a689-4e16-8418-3f4fcd3e076b" />
</p>

### 🎛️ Controls, Sensors & Events

Controls, sensors and events are described in [Sensors, Controls & Events](https://github.com/msp1974/ViewAssist_Companion_App/wiki/Controls,-Sensors-and-Events). Sensors depend on what your device supports.

<p align="center">
  <img width="300" alt="Controls" src="https://github.com/user-attachments/assets/8d0227a9-237d-4a36-a02c-1defe0942a45" />
  &nbsp;
  <img width="300" alt="Sensors" src="https://github.com/user-attachments/assets/44f7db39-95a0-45d4-a092-593684a92c3e" />
</p>

### 🛠️ Action: `vaca.send_event`

Send a custom event to one or more devices from automations and scripts:

| Event | Purpose |
|---|---|
| `navigate` | Open a dashboard path, e.g. `{"path": "/view-assist/clock"}` |
| `toast-message` | Show a message on the device |
| `alarm` | Trigger an alarm |
| `wake` / `interrupt` | Wake the device or interrupt the current response |
| `refresh` | Reload the display |
| `get-logs` | Retrieve device logs |

```yaml
action: vaca.send_event
target:
  entity_id: assist_satellite.kitchen_display
data:
  event_name: navigate
  event_value:
    path: /view-assist/clock
```

## 📲 Installation

1. Install the integration through [HACS](https://hacs.xyz) (requires Home Assistant 2026.9.0 or later).
2. Install the VACA Android app on your device (see the Getting Started guide for the download).
3. The device is discovered automatically in Home Assistant. Confirm it to add it.

Full instructions are in the [Getting Started guide](https://github.com/msp1974/ViewAssist_Companion_App/wiki/Getting-Started).

## 📱 Device Compatibility

VACA runs on most Android 8+ devices. Keep the device powered, as on-device wake word and camera motion detection use a lot of battery.

- **Tested:** Amazon Echo 5 / 8 Gen 1\*, Lenovo ThinkSmart View, Lenovo Smart Display 10", Lenovo Smart Clock 2 (some out of memory issues reported), Samsung S24 / S25, Samsung Tab S6 / A9, Xiaomi Smart Clock
- **Community reported:** Amazon Fire 8 (2021), Amazon Fire 10 (2022), Amazon Echo Show 5 Gen 2\*, Sonoff NSPanel Pro, Samsung Galaxy Tab A8, Surface Duo 2

\* Requires LineageOS. The OS build is fairly new and may have stability issues.

Sensors depend on what your device supports. If your device has issues, please [log an issue](https://github.com/msp1974/ViewAssist_Companion_App/issues).

## 📚 Documentation

| | |
|---|---|
| [Getting Started](https://github.com/msp1974/ViewAssist_Companion_App/wiki/Getting-Started) | Installation and first setup |
| [Configuration Options](https://github.com/msp1974/ViewAssist_Companion_App/wiki/Configuration-Options) | Integration and device options |
| [Sensors, Controls & Events](https://github.com/msp1974/ViewAssist_Companion_App/wiki/Controls,-Sensors-and-Events) | All entities explained |
| [Actions](https://github.com/msp1974/ViewAssist_Companion_App/wiki/Actions) | Using actions in automations |
| [Working with View Assist](https://github.com/msp1974/ViewAssist_Companion_App/wiki/Working-with-View-Assist) | Using VACA with View Assist |
| [Custom Files](https://github.com/msp1974/ViewAssist_Companion_App/wiki/Custom-Files) | Custom wake words and sounds (v0.12+) |
| [Wake Word & Voice Recognition](https://github.com/msp1974/ViewAssist_Companion_App/wiki/Wake-Word-Detection-&-Voice-Recognition) | Tuning detection |
| [On Device Menu](https://github.com/msp1974/ViewAssist_Companion_App/wiki/Settings-Menu) | Settings on the device |
| [Diagnostics](https://github.com/msp1974/ViewAssist_Companion_App/wiki/Diagnostics) | Diagnostic information |
| [FAQs](https://github.com/msp1974/ViewAssist_Companion_App/wiki/FAQs) / [Troubleshooting](https://github.com/msp1974/ViewAssist_Companion_App/wiki/Troubleshooting) | Help when things go wrong |

## 🤝 Support & Community

- **Bugs and requests:** [open an issue](https://github.com/msp1974/ViewAssist_Companion_App/issues)
- **Chat and help:** the [View Assist Discord server](https://discord.gg/3WXXfGAf8T)

## 📸 Screenshots (using View Assist views)


<img width="960" height="480" alt="image" src="https://github.com/user-attachments/assets/164e00e7-55e9-48e3-8e9f-dc7bd35104b5" />

<img width="960" height="600" alt="image" src="https://github.com/user-attachments/assets/3657a43f-6e7c-4bae-860d-75f11fd3a215" />
