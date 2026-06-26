import asyncio
import os
import datetime
from typing import Dict, Any, Optional
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler
)
from browser import RegistrationBrowser
from config import logger, TELEGRAM_BOT_TOKEN, PORTAL_USERNAME, PORTAL_PASSWORD, PUBLIC_URL

# Conversation states for Credentials setup
AWAITING_USERNAME, AWAITING_PASSWORD = range(2)

# Session storage for active users
# Structure:
# {
#     chat_id: {
#         "username": str,
#         "password": str,
#         "browser": RegistrationBrowser,
#         "monitor_task": asyncio.Task,
#         "categories": [...],
#         "selections": {},  # {category_index: option_value}
#         "confirm_screenshot": str,
#         "status_msg_id": int,
#         "status_logs": []
#     }
# }
user_sessions: Dict[int, Dict[str, Any]] = {}

def get_or_create_session(chat_id: int) -> Dict[str, Any]:
    """Retrieves or creates a session for the specified chat ID."""
    if chat_id not in user_sessions:
        user_sessions[chat_id] = {
            "username": "",
            "password": "",
            "browser": RegistrationBrowser(),
            "monitor_task": None,
            "categories": [],
            "selections": {},
            "confirm_screenshot": "",
            "status_msg_id": None,
            "status_logs": []
        }
    return user_sessions[chat_id]

# --- Live Logging Utility ---

async def log_status_event(chat_id: int, context: ContextTypes.DEFAULT_TYPE, event_text: str):
    """Appends an event to the rolling logs and edits the live status message."""
    session = get_or_create_session(chat_id)
    msg_id = session.get("status_msg_id")
    if not msg_id:
        return
        
    now_str = datetime.datetime.now().strftime("%H:%M:%S")
    log_entry = f"• `[{now_str}]` {event_text}"
    
    # Maintain rolling log of last 5 entries
    session["status_logs"].append(log_entry)
    if len(session["status_logs"]) > 5:
        session["status_logs"].pop(0)
        
    log_content = "\n".join(session["status_logs"])
    text = (
        "🔍 *KARE Student Portal Live Monitor*\n\n"
        "*Recent Status Log:*\n"
        f"{log_content}\n\n"
        "🕒 _Continuous polling is active._"
    )
    
    # Action buttons for log screen
    buttons = []
    if PUBLIC_URL:
        buttons.append([
            InlineKeyboardButton("🖥️ Open Live Mini App", web_app=WebAppInfo(url=f"{PUBLIC_URL}/remote/control/{chat_id}"))
        ])
    buttons.append([
        InlineKeyboardButton("🛑 Stop Monitoring", callback_data="dashboard:toggle_monitor"),
        InlineKeyboardButton("◀️ Dashboard Menu", callback_data="dashboard:main")
    ])
    
    try:
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=msg_id,
            text=text,
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode="Markdown"
        )
    except Exception as e:
        if "message is not modified" not in str(e).lower():
            logger.warning(f"Could not edit status log message: {e}")

# --- Credentials Setup Conversation ---

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Starts the bot interaction. Directs to dashboard if already configured."""
    chat_id = update.effective_chat.id
    session = get_or_create_session(chat_id)
    
    user = session["username"]
    pwd = session["password"]
    
    # Credentials already exist, bypass setup and go straight to dashboard
    if user and pwd:
        await send_dashboard(chat_id, context, update_msg=update.message)
        return ConversationHandler.END
        
    greeting = (
        "👋 *Welcome to KARE Course Registration Bot!*\n\n"
        "To automate your registration under high-load conditions, I need to log into your student portal.\n\n"
        "👤 Please enter your *KARE Student Registration ID* (e.g., 2021102001):"
    )
    await update.message.reply_text(greeting, parse_mode="Markdown")
    return AWAITING_USERNAME

async def start_creds_setup_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Triggered via inline button on dashboard to edit/reset credentials."""
    query = update.callback_query
    await query.answer()
    chat_id = update.effective_chat.id
    session = get_or_create_session(chat_id)
    
    session["username"] = ""
    session["password"] = ""
    
    await query.edit_message_text(
        "👤 Please enter your *KARE Student Registration ID* (e.g., 2021102001):",
        parse_mode="Markdown"
    )
    return AWAITING_USERNAME

async def handle_username_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Saves username and prompts for password."""
    chat_id = update.effective_chat.id
    session = get_or_create_session(chat_id)
    
    username = update.message.text.strip()
    session["username"] = username
    logger.info(f"Received Username for chat {chat_id}: {username}")
    
    await update.message.reply_text(
        "🔑 *Great! Now please enter your portal password.*\n"
        "_(For security, your password message will be deleted from the chat history immediately after receipt)_"
    )
    return AWAITING_PASSWORD

async def handle_password_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Saves password, deletes password message, and shows dashboard."""
    chat_id = update.effective_chat.id
    session = get_or_create_session(chat_id)
    
    password = update.message.text.strip()
    session["password"] = password
    logger.info(f"Received Password for chat {chat_id}. Deleting message...")
    
    # Securely delete the user's password message
    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=update.message.message_id)
    except Exception as e:
        logger.warning(f"Could not delete password message: {e}")
        
    await update.message.reply_text("🛡️ *Credentials loaded securely in memory!*")
    await send_dashboard(chat_id, context)
    return ConversationHandler.END

async def cancel_setup(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancels credential setup."""
    await update.message.reply_text("❌ Setup cancelled. Use /start to configure your login details.")
    return ConversationHandler.END

# --- Dashboard & Controls ---

async def send_dashboard(chat_id: int, context: ContextTypes.DEFAULT_TYPE, query=None, update_msg=None):
    """Draws/edits the unified inline dashboard controller."""
    session = get_or_create_session(chat_id)
    
    monitoring = session["monitor_task"] is not None and not session["monitor_task"].done()
    
    text = (
        "⚡ *KARE Student Bot Premium Dashboard* ⚡\n\n"
        "Welcome! Manage credentials, monitor portal, and execute selections completely inline.\n\n"
        f"👤 *Username ID:* `{session.get('username')}`\n"
        f"🔍 *Monitor Loop:* {'🟢 Running' if monitoring else '🔴 Stopped'}"
    )
    
    buttons = []
    # Dynamic Monitor Toggle Button
    if monitoring:
        buttons.append([
            InlineKeyboardButton("📋 View Monitor Logs", callback_data="dashboard:logs"),
            InlineKeyboardButton("🛑 Stop Monitoring", callback_data="dashboard:toggle_monitor")
        ])
    else:
        buttons.append([
            InlineKeyboardButton("🚀 Start Monitoring", callback_data="dashboard:toggle_monitor")
        ])
        
    # Show WebApp remote control button if monitoring is active or browser is active
    if PUBLIC_URL and (monitoring or session["browser"].is_session_alive()):
        buttons.append([
            InlineKeyboardButton("🖥️ Open Live Mini App", web_app=WebAppInfo(url=f"{PUBLIC_URL}/remote/control/{chat_id}"))
        ])
        
    buttons.append([
        InlineKeyboardButton("📊 Session Status", callback_data="dashboard:status"),
        InlineKeyboardButton("⚙️ Edit Credentials", callback_data="dashboard:edit_creds")
    ])
    buttons.append([
        InlineKeyboardButton("👥 User Directory", callback_data="dashboard:users"),
        InlineKeyboardButton("⚡ Premium Features", callback_data="dashboard:premium")
    ])
    buttons.append([
        InlineKeyboardButton("❓ Help Guide", callback_data="dashboard:help")
    ])
    
    markup = InlineKeyboardMarkup(buttons)
    
    if query:
        await query.edit_message_text(text=text, reply_markup=markup, parse_mode="Markdown")
    elif update_msg:
        await update_msg.reply_text(text=text, reply_markup=markup, parse_mode="Markdown")
    else:
        await context.bot.send_message(chat_id=chat_id, text=text, reply_markup=markup, parse_mode="Markdown")

async def handle_dashboard_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Routes callback clicks from the dashboard controls."""
    query = update.callback_query
    await query.answer()
    
    chat_id = update.effective_chat.id
    session = get_or_create_session(chat_id)
    data = query.data
    
    if data == "dashboard:main":
        await send_dashboard(chat_id, context, query=query)
        
    elif data == "dashboard:logs":
        # Draw logs screen
        session["status_msg_id"] = query.message.message_id
        await log_status_event(chat_id, context, "Resumed logs view.")
        
    elif data == "dashboard:toggle_monitor":
        monitoring = session["monitor_task"] is not None and not session["monitor_task"].done()
        if monitoring:
            # Stop it
            logger.info(f"Stopping monitor loop via inline for chat {chat_id}")
            if session["monitor_task"]:
                session["monitor_task"].cancel()
                session["monitor_task"] = None
            if session["browser"]:
                await asyncio.to_thread(session["browser"].close_driver)
            await send_dashboard(chat_id, context, query=query)
        else:
            # Start it
            user = session["username"]
            pwd = session["password"]
            if not user or not pwd:
                await query.edit_message_text(
                    "⚠️ *Credentials missing!*\n\nPlease click Edit Credentials to enter login details.",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Back", callback_data="dashboard:main")]]),
                    parse_mode="Markdown"
                )
                return
            
            session["status_msg_id"] = query.message.message_id
            session["status_logs"] = []
            await log_status_event(chat_id, context, "Initializing monitor...")
            session["monitor_task"] = asyncio.create_task(monitor_loop(chat_id, user, pwd, context))
            
    elif data == "dashboard:status":
        monitoring = session["monitor_task"] is not None and not session["monitor_task"].done()
        browser_alive = session["browser"].is_session_alive()
        
        status_text = (
            "📊 *KARE Bot Status Details:*\n\n"
            f"• *Portal Credentials:* Configured\n"
            f"• *Monitoring Loop:* {'🟢 Running' if monitoring else '🔴 Stopped'}\n"
            f"• *Browser Session:* {'🟢 Active' if browser_alive else '🔴 Inactive'}\n"
            f"• *Selections Configured:* {len(session.get('selections', {}))} categories\n"
            f"• *Polling URL:* `{session['browser'].driver.current_url if browser_alive else 'None'}`"
        )
        buttons = [[InlineKeyboardButton("◀️ Back to Menu", callback_data="dashboard:main")]]
        await query.edit_message_text(text=status_text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="Markdown")
        
    elif data == "dashboard:premium":
        premium_text = (
            "⚡ *KARE BOT PREMIUM ENTERPRISE* ⚡\n\n"
            "👑 *Active Status:* Premium Plan Enabled\n\n"
            "🚀 *Premium Features Engaged:*\n"
            "• *Unlimited 502/504 Retries* - Activated (exponential backoff)\n"
            "• *Stealth Fingerprint Spoofing* - Activated (hiding automation markers)\n"
            "• *Multi-threaded worker execution* - Activated (zero-freeze interaction)\n"
            "• *Continuous Status Log Edits* - Activated (real-time progress feedback)\n"
            "• *Automated Error Screenshot Uploads* - Activated (every 5 failures)\n"
            "• *Multiple Concurrent User Sessions* - Activated (multi-user ready)\n\n"
            "🔒 _Premium Enterprise features are fully integrated into your instance._"
        )
        buttons = [[InlineKeyboardButton("◀️ Back to Menu", callback_data="dashboard:main")]]
        await query.edit_message_text(premium_text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="Markdown")
        
    elif data == "dashboard:help":
        help_text = (
            "❓ *KARE Course Registration Bot Help Guide:*\n\n"
            "1. Click *Edit Credentials* to set your portal registration ID and password.\n"
            "2. Click *Start Monitoring* to connect to the KARE portal and begin polling.\n"
            "3. The bot will refresh every 5 seconds, logging attempts inline. If server gateway errors (502/504) are encountered, it automatically handles retries and sends periodic error screenshots.\n"
            "4. Once the registration page opens, you'll see a nested button menu to choose courses.\n"
            "5. Make selections, click Submit, review the screenshot, and confirm the final submission."
        )
        buttons = [[InlineKeyboardButton("◀️ Back to Menu", callback_data="dashboard:main")]]
        await query.edit_message_text(help_text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="Markdown")
        
    elif data == "dashboard:users":
        await send_users_list(chat_id, context, query=query)

# --- Monitor Polling Loop ---

async def monitor_loop(chat_id: int, user: str, pwd: str, context: ContextTypes.DEFAULT_TYPE):
    """Background task that logs into KARE portal and polls registration page."""
    session = get_or_create_session(chat_id)
    browser = session["browser"]
    poll_interval = 5.0
    consecutive_errors = 0
    attempt_count = 0
    
    try:
        # Step 1: Login with retries
        login_success = False
        login_attempts = 0
        login_wait_time = 2.0
        max_login_wait = 30.0
        
        while not login_success:
            login_attempts += 1
            await log_status_event(chat_id, context, f"Attempting portal login (Attempt {login_attempts})...")
            try:
                login_success = await asyncio.to_thread(browser.login, user, pwd)
                if login_success:
                    await log_status_event(chat_id, context, "🟢 Login successful!")
                else:
                    await log_status_event(chat_id, context, "❌ Login aborted: missing credentials.")
                    return
            except Exception as e:
                err_desc = "Login Error"
                if browser.last_error_type == "unreachable":
                    err_desc = "Site Unreachable / Timeout"
                elif "gateway" in str(e).lower():
                    err_desc = "502/504 Gateway Error"
                
                await log_status_event(
                    chat_id, 
                    context, 
                    f"❌ Login failed: {err_desc}. Retrying in {int(login_wait_time)}s..."
                )
                await asyncio.sleep(login_wait_time)
                login_wait_time = min(login_wait_time * 1.5, max_login_wait)
            
        # Step 2: Poll registration page
        while True:
            attempt_count += 1
            logger.info(f"Polling registration page for chat {chat_id} (Attempt {attempt_count})...")
            await log_status_event(chat_id, context, f"Checking registration page (Attempt {attempt_count})...")
            
            categories = await asyncio.to_thread(browser.check_registration_live)
            
            if categories is not None:
                logger.success(f"Registration is live! Scraped categories: {categories}")
                await log_status_event(chat_id, context, "🎉 Success! Registration page loaded!")
                
                session["categories"] = categories
                session["selections"] = {} # Reset choices
                
                # Delete monitor status message
                try:
                    await context.bot.delete_message(chat_id=chat_id, message_id=session["status_msg_id"])
                except Exception:
                    pass
                
                await context.bot.send_message(
                    chat_id=chat_id,
                    text="🔔 *ALERT: Registration page is loaded successfully!* 🔔\nSelect your courses below:",
                    parse_mode="Markdown"
                )
                
                # Send the registration page screenshot
                screenshot_path = browser.last_registration_screenshot
                if screenshot_path and os.path.exists(screenshot_path):
                    try:
                        await context.bot.send_photo(
                            chat_id=chat_id,
                            photo=open(screenshot_path, "rb"),
                            caption="📷 Portal View of the Live Course Registration Page"
                        )
                    except Exception as e:
                        logger.error(f"Failed to send registration live screenshot: {e}")
                
                await send_main_menu(chat_id, context)
                break
                
            # Check error state
            if browser.last_check_had_error:
                consecutive_errors += 1
                err_desc = "502/504 Server Error"
                screenshot_prefix = "gateway_error"
                if browser.last_error_type == "unreachable":
                    err_desc = "Site Unreachable / Timeout"
                    screenshot_prefix = "unreachable_error"
                
                await log_status_event(chat_id, context, f"⚠️ Attempt {attempt_count}: {err_desc} (Failures: {consecutive_errors})")
                
                # Screenshot upload every 5 errors
                if consecutive_errors % 5 == 0:
                    await log_status_event(chat_id, context, "📸 Capturing error page screenshot...")
                    screenshot_path = browser.save_debug_screenshot(f"{screenshot_prefix}_attempt_{attempt_count}")
                    if screenshot_path and os.path.exists(screenshot_path):
                        try:
                            await context.bot.send_photo(
                                chat_id=chat_id,
                                photo=open(screenshot_path, "rb"),
                                caption=f"📷 Portal status at Attempt {attempt_count} ({consecutive_errors} consecutive failures)."
                            )
                        except Exception as e:
                            logger.error(f"Failed to send error photo: {e}")
            else:
                consecutive_errors = 0 # Reset error counter if page loaded successfully but form isn't live
                await log_status_event(chat_id, context, f"ℹ️ Attempt {attempt_count}: Portal online, registration not active yet.")

            await asyncio.sleep(poll_interval)
            
    except asyncio.CancelledError:
        logger.info(f"Monitor loop cancelled for chat {chat_id}")
        await log_status_event(chat_id, context, "🛑 Monitoring loop stopped.")
    except Exception as e:
        logger.error(f"Error in monitor loop: {e}")
        await log_status_event(chat_id, context, f"💥 Critical error: {e}. Restarting browser...")
        await asyncio.to_thread(browser.close_driver)
        session["monitor_task"] = asyncio.create_task(monitor_loop(chat_id, user, pwd, context))

# --- Interactive Courses Menu Navigation ---

async def send_main_menu(chat_id: int, context: ContextTypes.DEFAULT_TYPE, query=None):
    """Sends or edits the message to show the Main Category Selection Menu."""
    session = get_or_create_session(chat_id)
    categories = session["categories"]
    selections = session["selections"]
    
    text = (
        "📚 *Course Registration Main Menu*\n\n"
        "Click a category to select a course. Once all desired categories are configured, click Submit."
    )
    
    buttons = []
    # Build list of category buttons
    for idx, cat in enumerate(categories):
        selected_val = selections.get(idx)
        if selected_val:
            opt_text = next((o["text"] for o in cat["options"] if o["value"] == selected_val), "Selected")
            if len(opt_text) > 25:
                opt_text = opt_text[:22] + "..."
            btn_label = f"✅ {cat['name'].split('(')[0].strip()} ({opt_text})"
        else:
            btn_label = f"❌ {cat['name'].split('(')[0].strip()} (Not Selected)"
            
        buttons.append([InlineKeyboardButton(btn_label, callback_data=f"menu:category:{idx}")])
        
    # Actions row
    buttons.append([
        InlineKeyboardButton("🚀 Submit Selections", callback_data="menu:submit"),
        InlineKeyboardButton("❌ Cancel", callback_data="menu:cancel")
    ])
    
    if PUBLIC_URL:
        buttons.append([
            InlineKeyboardButton("🖥️ Open Live Mini App", web_app=WebAppInfo(url=f"{PUBLIC_URL}/remote/control/{chat_id}"))
        ])
        
    markup = InlineKeyboardMarkup(buttons)
    
    if query:
        await query.edit_message_text(text=text, reply_markup=markup, parse_mode="Markdown")
    else:
        await context.bot.send_message(chat_id=chat_id, text=text, reply_markup=markup, parse_mode="Markdown")

async def send_category_options(chat_id: int, context: ContextTypes.DEFAULT_TYPE, cat_idx: int, query):
    """Edits the keyboard to display a numbered list of course options and a grid of compact number buttons."""
    session = get_or_create_session(chat_id)
    category = session["categories"][cat_idx]
    
    options_lines = []
    for opt_idx, opt in enumerate(category["options"]):
        # Clean/escape markdown special characters
        clean_text = opt["text"].replace("*", "\\*").replace("_", "\\_").replace("`", "\\`").replace("[", "\\[")
        options_lines.append(f"*{opt_idx + 1}\\.* {clean_text}")
        
    options_list = "\n".join(options_lines)
    
    text = (
        f"📝 *Category Options:* {category['name'].split('(')[0].strip()}\n\n"
        "Choose an option by clicking its number below:\n\n"
        f"{options_list}"
    )
    
    buttons = []
    row = []
    for opt_idx in range(len(category["options"])):
        btn = InlineKeyboardButton(str(opt_idx + 1), callback_data=f"select:{cat_idx}:{opt_idx}")
        row.append(btn)
        if len(row) == 4: # 4 buttons per row (e.g. [ 1 ] [ 2 ] [ 3 ] [ 4 ])
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
        
    buttons.append([InlineKeyboardButton("◀️ Back to Categories", callback_data="menu:main")])
    markup = InlineKeyboardMarkup(buttons)
    await query.edit_message_text(text=text, reply_markup=markup, parse_mode="Markdown")

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Routes callback queries from inline course selection buttons."""
    query = update.callback_query
    await query.answer()
    
    chat_id = update.effective_chat.id
    session = get_or_create_session(chat_id)
    data = query.data
    
    if data == "menu:main":
        await send_main_menu(chat_id, context, query=query)
        
    elif data.startswith("menu:category:"):
        cat_idx = int(data.split(":")[-1])
        await send_category_options(chat_id, context, cat_idx, query)
        
    elif data.startswith("select:"):
        parts = data.split(":")
        cat_idx = int(parts[1])
        opt_idx = int(parts[2])
        
        category = session["categories"][cat_idx]
        opt = category["options"][opt_idx]
        
        # Save selection
        session["selections"][cat_idx] = opt["value"]
        logger.info(f"Selected index {cat_idx} -> {opt['text']}")
        
        await send_main_menu(chat_id, context, query=query)
        
    elif data == "menu:submit":
        if not session["selections"]:
            await query.edit_message_text(
                text="⚠️ *You haven't selected any courses!*\n\nPlease configure at least one category before submitting.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Back", callback_data="menu:main")]]),
                parse_mode="Markdown"
            )
            return
            
        await query.edit_message_text("⏳ Injecting selections into form and loading confirmation screen...")
        await execute_injection_and_confirm(chat_id, context)
        
    elif data == "menu:cancel":
        await query.edit_message_text("❌ Course selection cancelled.")
        await stop_cmd_silent(chat_id)
        await send_dashboard(chat_id, context, query=query)
        
    elif data == "menu:confirm_final":
        await query.edit_message_text("🚀 Submitting final registration to KARE portal...")
        await execute_final_submission(chat_id, context)

# --- User Session Management ---

async def send_users_list(chat_id: int, context: ContextTypes.DEFAULT_TYPE, query=None):
    """Sends/edits message to display all active sessions with details and deletion controls."""
    text = (
        "👥 *Active KARE Bot User Sessions*\n\n"
        "Select a user below to manage, or click delete to purge. Press back to return to Dashboard."
    )
    
    buttons = []
    if not user_sessions:
        text = "👥 *Active KARE Bot User Sessions*\n\nNo active user sessions currently configured in memory."
    else:
        for cid, sess in user_sessions.items():
            username = sess.get("username") or "Unconfigured"
            buttons.append([
                InlineKeyboardButton(f"👤 {username} (ID: {cid})", callback_data=f"user:details:{cid}"),
                InlineKeyboardButton("🗑️ Delete", callback_data=f"user:delete:{cid}")
            ])
            
    # Include dashboard back button at bottom
    buttons.append([InlineKeyboardButton("◀️ Back to Dashboard", callback_data="dashboard:main")])
    
    markup = InlineKeyboardMarkup(buttons)
    if query:
        await query.edit_message_text(text=text, reply_markup=markup, parse_mode="Markdown")
    else:
        await context.bot.send_message(chat_id=chat_id, text=text, reply_markup=markup, parse_mode="Markdown")

async def handle_user_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles callbacks for inline user directory."""
    query = update.callback_query
    await query.answer()
    
    chat_id = update.effective_chat.id
    data = query.data
    
    if data == "user:list":
        await send_users_list(chat_id, context, query=query)
        
    elif data.startswith("user:details:"):
        target_cid = int(data.split(":")[-1])
        sess = user_sessions.get(target_cid)
        if not sess:
            await query.edit_message_text(
                "❌ Session not found.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Back", callback_data="user:list")]])
            )
            return
            
        monitoring = sess["monitor_task"] is not None and not sess["monitor_task"].done()
        browser_alive = sess["browser"].is_session_alive()
        
        detail_text = (
            f"👤 *User Session Details:*\n\n"
            f"• *Registration ID:* `{sess.get('username')}`\n"
            f"• *Chat ID:* `{target_cid}`\n"
            f"• *Monitoring status:* {'🟢 Running' if monitoring else '🔴 Stopped'}\n"
            f"• *Browser session:* {'🟢 Active' if browser_alive else '🔴 Inactive'}\n"
            f"• *Selections:* {len(sess.get('selections', {}))} items configured"
        )
        
        buttons = [
            [InlineKeyboardButton("🗑️ Delete Session", callback_data=f"user:delete:{target_cid}")],
            [InlineKeyboardButton("◀️ Back to Directory", callback_data="user:list")]
        ]
        await query.edit_message_text(text=detail_text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="Markdown")
        
    elif data.startswith("user:delete:"):
        target_cid = int(data.split(":")[-1])
        
        if target_cid in user_sessions:
            sess = user_sessions[target_cid]
            if sess["monitor_task"] and not sess["monitor_task"].done():
                sess["monitor_task"].cancel()
            if sess["browser"]:
                await asyncio.to_thread(sess["browser"].close_driver)
            del user_sessions[target_cid]
            logger.success(f"Purged session for chat ID {target_cid}")
            
        await query.edit_message_text(
            f"🗑️ Session for Chat ID `{target_cid}` has been deleted.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Back to Directory", callback_data="user:list")]]),
            parse_mode="Markdown"
        )

# --- Automation Tasks (Thread Safe) ---

async def execute_injection_and_confirm(chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    """Runs Selenium form injection in a background thread and presents confirmation screenshot."""
    session = get_or_create_session(chat_id)
    browser = session["browser"]
    selections = session["selections"]
    
    try:
        screenshot_path = await asyncio.to_thread(browser.inject_selections_and_submit, selections)
        session["confirm_screenshot"] = screenshot_path
        
        summary_lines = []
        for idx, cat in enumerate(session["categories"]):
            val = selections.get(idx)
            opt_text = next((o["text"] for o in cat["options"] if o["value"] == val), "Not Selected")
            summary_lines.append(f"• *{cat['name'].split('(')[0].strip()}*:\n  `{opt_text}`")
            
        summary = "\n".join(summary_lines)
        message_text = (
            "🧐 *Course Registration Summary:*\n\n"
            f"{summary}\n\n"
            "Below is the screenshot from the KARE Portal confirmation screen.\n"
            "❓ *Do you want to finalize the registration?*"
        )
        
        if screenshot_path and os.path.exists(screenshot_path):
            await context.bot.send_photo(
                chat_id=chat_id,
                photo=open(screenshot_path, "rb"),
                caption="KARE Portal Confirmation Page"
            )
            
        buttons = [
            [
                InlineKeyboardButton("🚀 YES, Finalize Registration", callback_data="menu:confirm_final"),
                InlineKeyboardButton("❌ NO, Cancel", callback_data="menu:cancel")
            ]
        ]
        await context.bot.send_message(
            chat_id=chat_id,
            text=message_text,
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode="Markdown"
        )
        
    except Exception as e:
        logger.error(f"Failed injection: {e}")
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"❌ *Failed to load confirmation page:* {e}\n\nThe browser session has been left open. Click cancel to return to dashboard."
        )

async def execute_final_submission(chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    """Runs final Selenium submission in a background thread."""
    session = get_or_create_session(chat_id)
    browser = session["browser"]
    
    try:
        success_screenshot = await asyncio.to_thread(browser.finalize_registration)
        
        await context.bot.send_message(
            chat_id=chat_id,
            text="🎉 *Registration Completed Successfully!* 🎉"
        )
        
        if success_screenshot and os.path.exists(success_screenshot):
            await context.bot.send_photo(
                chat_id=chat_id,
                photo=open(success_screenshot, "rb"),
                caption="KARE Portal Success Screen"
            )
            
    except Exception as e:
        logger.error(f"Submission failed: {e}")
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"❌ *Final registration submission failed:* {e}"
        )
    finally:
        await stop_cmd_silent(chat_id)
        await send_dashboard(chat_id, context)

async def stop_cmd_silent(chat_id: int):
    """Wipes browser session and monitoring tasks silently."""
    session = get_or_create_session(chat_id)
    if session["monitor_task"] and not session["monitor_task"].done():
        session["monitor_task"].cancel()
        session["monitor_task"] = None
    if session["browser"]:
        await asyncio.to_thread(session["browser"].close_driver)

# --- Configuration & Assembly ---

def build_application() -> Application:
    """Configures and builds the Telegram Application."""
    if not TELEGRAM_BOT_TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN is missing!")
        
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Credentials Conversation Handler (starts on Command start OR Callback edit_creds)
    cred_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", start_cmd),
            CallbackQueryHandler(start_creds_setup_callback, pattern=r"^dashboard:edit_creds$")
        ],
        states={
            AWAITING_USERNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_username_input)],
            AWAITING_PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_password_input)]
        },
        fallbacks=[CommandHandler("cancel", cancel_setup)],
        allow_reentry=True
    )
    
    # Register handlers
    app.add_handler(cred_handler)
    
    # Inline Callback Routing
    app.add_handler(CallbackQueryHandler(handle_dashboard_callbacks, pattern=r"^dashboard:"))
    app.add_handler(CallbackQueryHandler(handle_callback, pattern=r"^(menu:|select:)"))
    app.add_handler(CallbackQueryHandler(handle_user_callback, pattern=r"^user:"))
    
    return app
