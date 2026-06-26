import os
import sys
from dotenv import load_dotenv
from loguru import logger
from Crypto.Cipher import AES
import base64

# Load environment variables from .env
load_dotenv()

# Configure loguru logger
logger.remove()
logger.add(
    sys.stderr,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level:8}</level> | <cyan>{module}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level=os.getenv("LOG_LEVEL", "INFO")
)

# Enable logging to a file for persistent error tracking
logger.add(
    "bot_debug.log",
    rotation="10 MB",
    retention="10 days",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level:8} | {module}:{line} - {message}",
    level="DEBUG"
)

# App Configuration
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
PORTAL_USERNAME = os.getenv("PORTAL_USERNAME")
PORTAL_PASSWORD = os.getenv("PORTAL_PASSWORD")
HEADLESS = os.getenv("HEADLESS", "False").lower() in ("true", "1", "yes")

URL_LOGIN = os.getenv("URL_LOGIN", "https://sis.kalasalingam.ac.in/login")
URL_REGISTRATION = os.getenv("URL_REGISTRATION", "https://sis.kalasalingam.ac.in/registration")
PUBLIC_URL = os.getenv("PUBLIC_URL")


# Credentials Encryption/Decryption Helpers
# We use the Telegram Bot Token as a key component to derive a 256-bit AES key.
def get_encryption_key() -> bytes:
    """Derives a 32-byte key from the Telegram bot token and username."""
    token = TELEGRAM_BOT_TOKEN or "default_secret_fallback_key"
    username = PORTAL_USERNAME or "default_user"
    combined = (token + username).encode("utf-8")
    # Simple hash-like key derivation using slice/padding to ensure 32 bytes
    if len(combined) >= 32:
        return combined[:32]
    return combined.ljust(32, b'\0')

def encrypt_text(text: str) -> str:
    """Encrypts text using AES-GCM and returns a base64 encoded string containing nonce + tag + ciphertext."""
    if not text:
        return ""
    key = get_encryption_key()
    cipher = AES.new(key, AES.MODE_GCM)
    ciphertext, tag = cipher.encrypt_and_digest(text.encode("utf-8"))
    
    # Pack everything together
    packed = cipher.nonce + tag + ciphertext
    return base64.b64encode(packed).decode("utf-8")

def decrypt_text(encrypted_b64: str) -> str:
    """Decrypts base64 encoded AES-GCM data."""
    if not encrypted_b64:
        return ""
    try:
        key = get_encryption_key()
        packed = base64.b64decode(encrypted_b64.encode("utf-8"))
        
        # AES-GCM nonce is 16 bytes by default in pycryptodome if not specified, 
        # or 12 bytes. Let's make sure we unpack it properly.
        # pycryptodome GCM nonce is 16 bytes by default, tag is 16 bytes.
        nonce = packed[:16]
        tag = packed[16:32]
        ciphertext = packed[32:]
        
        cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
        decrypted = cipher.decrypt_and_verify(ciphertext, tag)
        return decrypted.decode("utf-8")
    except Exception as e:
        logger.error(f"Failed to decrypt credentials: {e}")
        return ""

# Auto-decrypt credentials if they appear encrypted (e.g. starting with prefix 'enc:')
if PORTAL_PASSWORD and PORTAL_PASSWORD.startswith("enc:"):
    logger.info("Encrypted password detected in configuration. Decrypting...")
    PORTAL_PASSWORD = decrypt_text(PORTAL_PASSWORD[4:])
    if not PORTAL_PASSWORD:
        logger.error("Failed to decrypt PORTAL_PASSWORD! Check your configuration and token.")

# Create directories if they don't exist
os.makedirs("screenshots", exist_ok=True)

# Validation of essential config
def validate_config():
    if not TELEGRAM_BOT_TOKEN:
        logger.warning("TELEGRAM_BOT_TOKEN is not set in environment or .env!")
    if not PORTAL_USERNAME or not PORTAL_PASSWORD:
        logger.warning("PORTAL_USERNAME or PORTAL_PASSWORD is not set!")
    logger.info("Configuration validated successfully.")

validate_config()

# Cache webdriver-manager globally at boot to avoid race conditions
from webdriver_manager.chrome import ChromeDriverManager
logger.info("Pre-caching Chrome WebDriver binary path to prevent concurrency conflicts...")
CHROME_DRIVER_PATH = ChromeDriverManager().install()
logger.info(f"WebDriver cached at: {CHROME_DRIVER_PATH}")
