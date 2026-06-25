from bot import build_application
from config import logger

def main():
    """Main entrypoint for the KARE Course Registration Bot."""
    logger.info("==============================================")
    logger.info("Starting KARE Course Registration Bot...")
    logger.info("==============================================")
    
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
