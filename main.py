import os
import threading
import uvicorn
from bot import build_application
from config import logger
from web_server import app as web_app

def start_web_server():
    """Runs the FastAPI remote control server in a daemon thread."""
    port = int(os.getenv("PORT", 8080))
    logger.info(f"Starting remote control web server on port {port}...")
    config = uvicorn.Config(web_app, host="0.0.0.0", port=port, log_level="warning")
    server = uvicorn.Server(config)
    server.run()

def main():
    """Main entrypoint for the KARE Course Registration Bot."""
    logger.info("==============================================")
    logger.info("Starting KARE Course Registration Bot...")
    logger.info("==============================================")
    
    # Start the web server in a background daemon thread
    web_thread = threading.Thread(target=start_web_server, daemon=True)
    web_thread.start()
    logger.info("Remote control web server started in background thread.")
    
    try:
        # Build and configure the telegram bot application
        app = build_application()
        
        logger.info("Telegram Bot Application built. Starting polling loop...")
        app.run_polling()
        
    except KeyboardInterrupt:
        logger.info("Bot process interrupted by user.")
    except Exception as e:
        logger.critical(f"Application crashed during startup: {e}")
    finally:
        logger.info("Bot process terminated.")

if __name__ == "__main__":
    main()
