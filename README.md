# Kawach  Browser Activity Monitor

## About the Project

Kawach is a Chrome browser extension designed to monitor selected browser activities with user consent. It is connected to the Kawach backend, which analyzes the collected activities using a weighted-scoring system.

The main goal of Kawach is to provide a safety layer for online browser activity and help identify potentially risky activities.

## Features

The extension can detect:

- Website visits
- Search queries
- Sent chat messages
- Visible webpage text
- File uploads
- File downloads
- Form submission metadata
- Page and domain information

## How It Works

The basic working flow is:

User Browser  
↓  
Kawach Chrome Extension  
↓  
Activity Detection  
↓  
SafeSignal/Kawach Backend  
↓  
Risk Analysis  
↓  
Parent Dashboard

The extension collects selected browser activities and sends the required information to the backend for analysis.

## Privacy and Security

Kawach is designed for consent-based monitoring.

The extension does not capture:

- Passwords
- Authentication tokens
- Cookies
- Unrestricted keystrokes
- Unsent chat drafts
- Chat history

For file uploads, the extension collects basic file information such as the filename, file type, size and upload details. The actual file content is not read or sent.

## Setting Up the Extension

1. Open Chrome.
2. Go to `chrome://extensions`.
3. Enable **Developer mode**.
4. Click **Load unpacked**.
5. Select the `extension` folder from the Kawach project.
6. Open the Kawach extension and review its settings.

## Backend Connection

The browser extension can be connected to the SafeSignal/Kawach backend using a one-time pairing code.

After the device is paired, selected browser activities can be sent to the backend for processing.

## Project Purpose

Kawach aims to make online browsing safer by monitoring selected browser activities, analyzing potentially risky signals and providing authorized monitoring through the SafeSignal/Kawach system.

## Contribution

This contribution adds clear project documentation explaining the purpose, features, working process, privacy measures and setup instructions of the Kawach project.
