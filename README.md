# iCamera for Home Assistant

A Home Assistant integration for iCamera IP cameras, providing motion detection, email notifications, and configurable motion windows.

## Features

- Motion detection control
- Email notification settings (Email must be configured in the camera)
- Up to 4 configurable motion detection windows (use homeassistant-camera-motion-card to modify window coordinates through UI)
- Camera resolution control (including hidden 1280x720 resolution)
- Integration with Home Assistant's camera platform

## Installation

### Method 1: HACS (Recommended)

1. Open HACS in your Home Assistant instance
2. Click the three dots in the top right corner
3. Select "Custom repositories"
4. Add this repository URL and select "Integration" as the category
5. Click "Add"
6. Find "iCamera" in the list of integrations and click "Download"
7. Restart Home Assistant

### Method 2: Manual Installation

1. Download the latest release from GitHub
2. Copy the `custom_components/icamera` directory to your Home Assistant `custom_components` directory
3. Restart Home Assistant

## Configuration

1. Go to Home Assistant Settings > Devices & Services
2. Click "Add Integration"
3. Search for "iCamera"
4. Follow the configuration flow to add your camera

## Available Entities

### Camera

- Main camera stream

### Switches

- Motion Detection: Enable/disable motion detection
- Send Email on Motion: Toggle email notifications
- Motion Window 1-4: Enable/disable individual motion detection windows

## Support

If you encounter any issues or have suggestions for improvements:

- Open an issue on GitHub
- Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.
