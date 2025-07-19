# View Assist Companion - BETA

This is an Android application and Home Assistant integration to compliment the amazing [View Assist project by @dinki](https://github.com/dinki/View-Assist). It has been built from the ground up to simplify the setup of devices when using View Assist and provide a lower barrier to entry to get up and running.

## How is this different from existing solutions?

Other solutions are a combination of applications for voice and display and often have quite an involved setup. VACA is a 1-stop shop of voice and browser support providing a simplified setup with just a signle Android application install. Built specifically for View Assist also means that it provides the features and capabilities needed to support this project, without having to piece other solutions together.

## Will it work for me?

It has been tested on the following devices:

- Lenovo ThinkSmart View
- Lenovo Smart Display 10"
- Lenovo Smart Clock 2
- Samsung S24

If you are using a different device and have issues, please log an issue in the repository and we will do our best to solve it with you.

## So what does it do?

The integration and Android application together have the following features:

- Supports mdns/zeroconf for easy setup
- Uses the Wyoming protocol to provide an experience similar to setting up a HA Voice Preview Edition (except with a display!)
- Provides a web browser with auto loading of the HA dashboard upon connection from HA
- On device wakeword support to reduce network traffic of streaming wakeword solutions and remove the need to install openwakeword or similar.
  - Choose from 6 wakewords
  - Choose from 4 different wakeword detection sounds (plus a No sound option)
- Media player to support streaming audio (tested with Radio browser and Music Assistant)
- Microphone gain control and mute switch
- Screen controls to keep screen on (or let it sleep), set brightness and control auto brightness
- Pull down to refresh screen function
- Volume controls for voice responses, music and volume ducking (lowering music when listening for a command)
- Last command (STT) and response (TTS) sensors
- Sensors to show ambient light levels and device orientation (where available)
- Start on boot
- Securtity to prevent intrusion once paired to a HA server

## Installation

There are 2 components to this solution, a HA custom integration and an Android application.

### Custom Integration

As is common with new custom instegrations, it can take a little while to be fully available via HACs. However, you can add this as a custom respository by the following link to then provide the normal HACs install and update experience.

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=msp1974&repository=ViewAssist_Companion_App&category=Integration)

### Android Application

The app is not currently available in the Play store and will need to be downloaded from the apk folder in this repository and installed on your device.
