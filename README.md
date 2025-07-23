# View Assist Companion - BETA

This is an Android application and Home Assistant integration to compliment the amazing [View Assist project by @dinki](https://github.com/dinki/View-Assist). It has been built from the ground up to simplify the setup of devices when using View Assist and provide a lower barrier to entry to get up and running.

## How is this different from existing solutions?

Other solutions are a combination of applications for voice and display and often have quite an involved setup. VACA is a 1-stop shop of voice and browser support providing a simplified setup with just a single Android application install. Built specifically for View Assist also means that it provides the features and capabilities needed to support this project, without having to piece other solutions together.

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

**NOTE**: You will need the latest dev version of the View Assist integration which has support for VACA to be able to select the microphone entity when setting up the device in View Assist

### Custom Integration

As is common with new custom integrations, it can take a little while to be fully available via HACs. However, you can add this as a custom respository by the following link to then provide the normal HACs install and update experience.

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=msp1974&repository=ViewAssist_Companion_App&category=Integration)

### Android Application

The app is not currently available in the Play store and will need to be downloaded from the apk folder in this repository and installed on your device.

# FAQs

### My device detects the wake word ok but then doesn't hear what I am saying

This is caused by the mic gain setting either being too low or too high. Too low and it will struggle to hear you, too high and it will clip the audio and make your voice unintelligable.

- On a Lenovo TSV, start at 1 and don't go any more than 5
- On a Lenovo LSD 8 & 10, try a setting of around 60 and adjust between 40 and 80 to get the best result
- On other devices, always start at 1 and adjust in increments of 1 if it hears you but needs to be more sensitive or in increments of 10 if it doesn't hear you at all when set to 1.

---

### My device doesn't pick up the wake word or picks up too many false positives

Try adjusting the wake word threshold. It is default set to 80 but play around with it until it works the best. The lower the setting the more it will detect but becomes more suseptable to fale positives. The higher it is, the more likley background noise will stop it detecting. Default is 80 as that seems to be the best compromise in most tested situations.

---

### I dont understand how to turn the screen off on my device

There is some variation here with how devices will turn on/off their screens.

- Lenovo TSV - use the keep screen on switch and set the screen timeout on your device low. When keep screen on if set to off, it will sleep on this screne timeout. Turin keep screen on back to on, will wake up the screen.
- Lenovo LSD - use the brightness slider and set to 0 to turn screen off
- Lenovo SC2 - set auto brightness to off and then set brightness to 0.
- Other devices - try any of the above solutions. In the main, the more modern the device the more likley the TSV solution is the right answer.

---

### Can I use a custom wake word

This is a future ambition but for now it is limited to those listed and built into the app

---

### Can I use a custom wake word sound

See above answer!

---
