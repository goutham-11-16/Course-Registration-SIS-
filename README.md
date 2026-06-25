# KARE Course Registration Automated Bot ⚡

An automated Python Telegram Bot designed to assist KARE (Kalasalingam Academy of Research and Education) students with course registrations. It polls the Student Information System (SIS) portal, bypasses 502/504 server gateway errors, captures screenshots, and provides a mobile-friendly progressive selection interface to secure course registrations quickly.

---

## Key Features

- 👤 **Multi-User Isolation**: Multiple users can run the bot concurrently. User sessions, credentials, and Chrome instances are completely isolated in memory.
- 🔒 **Secure Credentials**: Logins are encrypted in memory using **AES-256-GCM** and never saved to plaintext logs or files.
- ⚡ **Dynamic Inline Dashboard**: Manage credentials, monitor the portal, and configure settings entirely within a single, auto-updating Telegram message.
- 🔄 **Smart Monitor Loop**: Continuous background polling with exponential backoff on server 502/504 gateway failures.
- 📸 **Live Screenshot Feed**: Sends periodic screenshots during downtime, and a live screenshot of the registration page once online.
- 📱 **Mobile-Optimized Interface**: Course names are parsed and listed in the text, and selected using a compact number button grid to prevent button text truncation on mobile screens.
- 🛡️ **Stealth Automation**: Integrates `selenium-stealth` and eager page load strategies to bypass security verification and speed up navigation.
- 🛠️ **Two-Step Confirmation**: Injects your selections, loads the confirmation page, sends a screenshot for review, and submits only when you click "Confirm & Submit".

---

## Deployment Options

### Option A: Local Installation (Windows, macOS, Linux)

#### Prerequisites
1. **Python 3.10+** (Python 3.13 is fully supported).
2. **Google Chrome** browser installed on your machine.

#### Setup Steps

1. **Clone the Repository**
   ```bash
   git clone https://github.com/goutham-11-16/Course-Registration-SIS-.git
   cd Course-Registration-SIS-
   ```

2. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure Environment Variables**
   Create a `.env` file in the root directory:
   ```env
   TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
   HEADLESS=False
   ```
   *Note: If you run locally, keeping `HEADLESS=False` lets you see the browser actions in real-time. Change to `True` for background operation.*

4. **Run the Bot**
   ```bash
   python main.py
   ```

5. **Test the Browser Module (Optional)**
   You can verify browser interactions using the local test script:
   ```bash
   python test_browser.py mock
   ```

---

### Option B: Cloud Deployment (Railway.app)

Deploying to **Railway** allows the bot to run 24/7 in the cloud.

1. **Fork or Push to GitHub**: Upload this repository to your GitHub account.
2. **Link to Railway**:
   - Go to [Railway.app](https://railway.app/) and create a new project.
   - Select **Deploy from GitHub repo** and connect this repository.
3. **Add Environment Variables**:
   Under the **Variables** tab on Railway, add:
   - `TELEGRAM_BOT_TOKEN` = `your_telegram_bot_token_here`
   - `HEADLESS` = `True`
4. **Deploy**: Railway will read the `Dockerfile` automatically, install Python, download Google Chrome, install dependencies, and start the polling loop.

---

## Telegram Bot Commands & Navigation

1. Send `/start` to activate the bot.
2. If credentials aren't set, it will prompt for your **KARE Registration ID** and **Password** (the password message is deleted automatically for security).
3. The **Premium Dashboard** will appear. Click `[🚀 Start Monitoring]` to begin polling.
4. If the site is down, the log will edit live to show the failure count and connection status.
5. Once the registration page opens, you will receive an alert and a screenshot. 
6. Use the inline buttons to select courses for each category, click `[🚀 Submit Selections]`, check the confirmation screenshot, and click `[🚀 YES, Finalize Registration]` to finish.
