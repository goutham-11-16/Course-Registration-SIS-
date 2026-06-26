import os
from fastapi import FastAPI, Response
from fastapi.responses import HTMLResponse
from config import logger
from bot import user_sessions

app = FastAPI(title="KARE Remote Control Web Server")

@app.get("/remote/control/{chat_id}", response_class=HTMLResponse)
async def remote_control(chat_id: int):
    session = user_sessions.get(chat_id)
    if not session:
        return HTMLResponse(content="<h3>No active session found for this user in bot memory. Please send /start first.</h3>", status_code=404)
    
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>KARE Portal Live Remote</title>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg-color: #0b0f19;
            --card-bg: rgba(255, 255, 255, 0.05);
            --border-color: rgba(255, 255, 255, 0.1);
            --accent-color: #3b82f6;
            --accent-hover: #2563eb;
            --text-color: #f3f4f6;
            --text-secondary: #9ca3af;
        }}

        body {{
            margin: 0;
            padding: 0;
            background-color: var(--bg-color);
            color: var(--text-color);
            font-family: 'Outfit', sans-serif;
            display: flex;
            flex-direction: column;
            align-items: center;
            min-height: 100vh;
            overflow-x: hidden;
        }}

        header {{
            width: 100%;
            padding: 15px 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            background: rgba(15, 23, 42, 0.6);
            backdrop-filter: blur(12px);
            border-bottom: 1px solid var(--border-color);
            box-sizing: border-box;
            position: sticky;
            top: 0;
            z-index: 100;
        }}

        .title {{
            font-weight: 800;
            font-size: 1.2rem;
            letter-spacing: 0.5px;
            background: linear-gradient(135deg, #60a5fa, #3b82f6);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}

        .status-badge {{
            font-size: 0.75rem;
            padding: 4px 10px;
            border-radius: 9999px;
            background: rgba(16, 185, 129, 0.1);
            color: #10b981;
            border: 1px solid rgba(16, 185, 129, 0.2);
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 5px;
        }}

        .status-badge::before {{
            content: '';
            display: inline-block;
            width: 6px;
            height: 6px;
            background-color: #10b981;
            border-radius: 50%;
            animation: pulse 1.5s infinite;
        }}

        @keyframes pulse {{
            0% {{ transform: scale(0.9); opacity: 0.5; }}
            50% {{ transform: scale(1.2); opacity: 1; }}
            100% {{ transform: scale(0.9); opacity: 0.5; }}
        }}

        .container {{
            width: 100%;
            max-width: 800px;
            padding: 15px;
            box-sizing: border-box;
            display: flex;
            flex-direction: column;
            gap: 15px;
            align-items: center;
        }}

        .screen-card {{
            width: 100%;
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 16px;
            overflow: hidden;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5);
            position: relative;
            aspect-ratio: 16/10;
        }}

        .screen-img {{
            width: 100%;
            height: 100%;
            object-fit: contain;
            cursor: crosshair;
            display: block;
        }}

        .controls-card {{
            width: 100%;
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 16px;
            padding: 15px;
            box-sizing: border-box;
            display: flex;
            flex-direction: column;
            gap: 12px;
            backdrop-filter: blur(8px);
        }}

        .input-group {{
            display: flex;
            gap: 10px;
            width: 100%;
        }}

        .text-input {{
            flex-grow: 1;
            background: rgba(0, 0, 0, 0.4);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            color: var(--text-color);
            padding: 10px 12px;
            font-family: inherit;
            font-size: 0.95rem;
            outline: none;
            transition: border-color 0.3s;
        }}

        .text-input:focus {{
            border-color: var(--accent-color);
        }}

        .btn {{
            background: var(--accent-color);
            color: white;
            border: none;
            border-radius: 8px;
            padding: 10px 16px;
            font-family: inherit;
            font-weight: 600;
            cursor: pointer;
            transition: background 0.2s, transform 0.1s;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 6px;
        }}

        .btn:hover {{
            background: var(--accent-hover);
        }}

        .btn:active {{
            transform: scale(0.98);
        }}

        .btn-secondary {{
            background: rgba(255, 255, 255, 0.08);
            color: var(--text-color);
            border: 1px solid var(--border-color);
        }}

        .btn-secondary:hover {{
            background: rgba(255, 255, 255, 0.15);
        }}

        .keypad-grid {{
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 8px;
            width: 100%;
        }}

        @media (max-width: 480px) {{
            .keypad-grid {{
                grid-template-columns: repeat(3, 1fr);
            }}
        }}

        .loader-overlay {{
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(11, 15, 25, 0.7);
            backdrop-filter: blur(3px);
            display: flex;
            justify-content: center;
            align-items: center;
            opacity: 0;
            pointer-events: none;
            transition: opacity 0.2s;
            z-index: 10;
        }}

        .loader-overlay.active {{
            opacity: 1;
            pointer-events: auto;
        }}

        .spinner {{
            width: 40px;
            height: 40px;
            border: 4px solid rgba(255, 255, 255, 0.1);
            border-top-color: var(--accent-color);
            border-radius: 50%;
            animation: spin 1s linear infinite;
        }}

        @keyframes spin {{
            to {{ transform: rotate(360deg); }}
        }}
    </style>
</head>
<body>

    <header>
        <div class="title">KARE Live Remote</div>
        <div class="status-badge">Live Feed</div>
    </header>

    <div class="container">
        <div class="screen-card">
            <div class="loader-overlay" id="loader">
                <div class="spinner"></div>
            </div>
            <img class="screen-img" id="screen" src="/remote/screenshot/{chat_id}" alt="Browser Screenshot" />
        </div>

        <div class="controls-card">
            <div class="input-group">
                <input type="text" class="text-input" id="text-input" placeholder="Type text here..." onkeydown="if(event.key==='Enter') sendText()" />
                <button class="btn" onclick="sendText()">⌨️ Send</button>
            </div>

            <div class="keypad-grid">
                <button class="btn btn-secondary" onclick="sendKey('backspace')">⌫ Backspace</button>
                <button class="btn btn-secondary" onclick="sendKey('tab')">⇥ Tab</button>
                <button class="btn btn-secondary" onclick="sendKey('enter')">↵ Enter</button>
                <button class="btn btn-secondary" onclick="sendKey('escape')">⎋ Esc</button>
                <button class="btn btn-secondary" onclick="sendKey('up')">▲ Up</button>
                <button class="btn btn-secondary" onclick="sendKey('down')">▼ Down</button>
                <button class="btn btn-secondary" onclick="sendKey('left')">◀ Left</button>
                <button class="btn btn-secondary" onclick="sendKey('right')">▶ Right</button>
                <button class="btn btn-secondary" style="grid-column: span 2;" onclick="refreshScreen()">🔄 Refresh Feed</button>
            </div>
        </div>
    </div>

    <script>
        const chatId = "{chat_id}";
        const screenImg = document.getElementById('screen');
        const loader = document.getElementById('loader');
        const textInput = document.getElementById('text-input');

        function showLoader() {{
            loader.classList.add('active');
        }}

        function hideLoader() {{
            loader.classList.remove('active');
        }}

        function refreshScreen() {{
            showLoader();
            const timestamp = new Date().getTime();
            screenImg.src = `/remote/screenshot/${{chatId}}?t=${{timestamp}}`;
        }}

        screenImg.onload = function() {{
            hideLoader();
        }};

        screenImg.onerror = function() {{
            hideLoader();
        }};

        screenImg.addEventListener('click', function(e) {{
            showLoader();
            const rect = screenImg.getBoundingClientRect();
            
            const x = (e.clientX - rect.left) / rect.width;
            const y = (e.clientY - rect.top) / rect.height;

            fetch(`/remote/click/${{chatId}}?x=${{x}}&y=${{y}}`)
                .then(r => r.json())
                .then(data => {{
                    refreshScreen();
                }})
                .catch(err => {{
                    console.error(err);
                    hideLoader();
                }});
        }});

        function sendText() {{
            const val = textInput.value;
            if (!val) return;
            showLoader();
            textInput.value = '';
            
            fetch(`/remote/type/${{chatId}}?text=${{encodeURIComponent(val)}}`)
                .then(r => r.json())
                .then(data => {{
                    refreshScreen();
                }})
                .catch(err => {{
                    console.error(err);
                    hideLoader();
                }});
        }}

        function sendKey(key) {{
            showLoader();
            fetch(`/remote/key/${{chatId}}?key=${{key}}`)
                .then(r => r.json())
                .then(data => {{
                    refreshScreen();
                }})
                .catch(err => {{
                    console.error(err);
                    hideLoader();
                }});
        }}
    </script>
</body>
</html>"""
    return HTMLResponse(content=html_content)

@app.get("/remote/screenshot/{chat_id}")
async def remote_screenshot(chat_id: int):
    session = user_sessions.get(chat_id)
    if not session or not session.get("browser"):
        return Response(status_code=404, content="No active session found.")
    
    browser = session["browser"]
    if not browser.is_session_alive():
        return Response(status_code=400, content="Browser session is inactive.")
    
    try:
        png_data = browser.driver.get_screenshot_as_png()
        return Response(content=png_data, media_type="image/png")
    except Exception as e:
        logger.error(f"Failed to capture remote screenshot: {e}")
        return Response(status_code=500, content=f"Failed: {e}")

@app.get("/remote/click/{chat_id}")
async def remote_click(chat_id: int, x: float, y: float):
    session = user_sessions.get(chat_id)
    if not session or not session.get("browser"):
        return {"status": "error", "message": "No active session."}
    
    browser = session["browser"]
    driver = browser.driver
    try:
        size = driver.get_window_size()
        width = size['width']
        height = size['height']
        
        click_x = int(width * x)
        click_y = int(height * y)
        
        logger.info(f"Remote click at ({click_x}, {click_y}) on window size ({width}x{height})")
        
        driver.execute_script("""
            var el = document.elementFromPoint(arguments[0], arguments[1]);
            if (el) {
                el.click();
                el.focus();
            }
        """, click_x, click_y)
        return {"status": "success"}
    except Exception as e:
        logger.error(f"Remote click failed: {e}")
        return {"status": "error", "message": str(e)}

@app.get("/remote/type/{chat_id}")
async def remote_type(chat_id: int, text: str):
    session = user_sessions.get(chat_id)
    if not session or not session.get("browser"):
        return {"status": "error", "message": "No active session."}
    
    browser = session["browser"]
    driver = browser.driver
    try:
        logger.info(f"Remote type text: {text}")
        active_element = driver.switch_to.active_element
        active_element.send_keys(text)
        return {"status": "success"}
    except Exception as e:
        logger.error(f"Remote type failed: {e}")
        return {"status": "error", "message": str(e)}

@app.get("/remote/key/{chat_id}")
async def remote_key(chat_id: int, key: str):
    session = user_sessions.get(chat_id)
    if not session or not session.get("browser"):
        return {"status": "error", "message": "No active session."}
    
    browser = session["browser"]
    driver = browser.driver
    try:
        from selenium.webdriver.common.keys import Keys
        active_element = driver.switch_to.active_element
        
        key_map = {
            "backspace": Keys.BACKSPACE,
            "tab": Keys.TAB,
            "enter": Keys.ENTER,
            "escape": Keys.ESCAPE,
            "up": Keys.ARROW_UP,
            "down": Keys.ARROW_DOWN,
            "left": Keys.ARROW_LEFT,
            "right": Keys.ARROW_RIGHT
        }
        
        selenium_key = key_map.get(key.lower())
        if selenium_key:
            logger.info(f"Remote send key: {key}")
            active_element.send_keys(selenium_key)
            return {"status": "success"}
        else:
            return {"status": "error", "message": f"Unsupported key: {key}"}
    except Exception as e:
        logger.error(f"Remote key press failed: {e}")
        return {"status": "error", "message": str(e)}
