import re
import requests
import logging
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)

# Bot Token
BOT_TOKEN = "7967153901:AAEEK5Pl548sDdokgwSURX0G4DKFZCl-vZE"

# Optimized Proxy Sources
PROXY_SOURCES = {
    "http": [
        "https://api.proxyscrape.com/v2/?request=getproxies&protocol=http",
        "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
    ],
    "socks4": [
        "https://api.proxyscrape.com/v2/?request=getproxies&protocol=socks4",
        "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks4.txt",
    ],
    "socks5": [
        "https://api.proxyscrape.com/v2/?request=getproxies&protocol=socks5",
        "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks5.txt",
    ],
}

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Cache for working proxies
proxy_cache = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send instant response with proxy options."""
    keyboard = [
        [InlineKeyboardButton("HTTP", callback_data="http")],
        [InlineKeyboardButton("SOCKS4", callback_data="socks4")],
        [InlineKeyboardButton("SOCKS5", callback_data="socks5")],
        [InlineKeyboardButton("Generate Fresh Proxies", callback_data="generate")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "⚡ *Proxy Generator & Checker Bot*\n\n"
        "Select proxy type or generate fresh proxies:",
        reply_markup=reply_markup
    )

async def gen_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /gen command to force fresh proxy generation."""
    keyboard = [
        [InlineKeyboardButton("HTTP", callback_data="gen_http")],
        [InlineKeyboardButton("SOCKS4", callback_data="gen_socks4")],
        [InlineKeyboardButton("SOCKS5", callback_data="gen_socks5")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🔄 *Generate Fresh Proxies*\n\n"
        "Select proxy type to generate fresh proxies:",
        reply_markup=reply_markup
    )

async def send_proxies(chat_id, proxy_type, context, force_fresh=False):
    """Send proxies with option to force fresh generation."""
    if force_fresh or proxy_type not in proxy_cache or not proxy_cache[proxy_type]:
        # Send generating message
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"⏳ Generating fresh {proxy_type.upper()} proxies..."
        )
        
        # Get fresh proxies
        proxies = await asyncio.to_thread(scrape_proxies, proxy_type)
        working = await asyncio.to_thread(check_proxies, proxies, proxy_type)
        proxy_cache[proxy_type] = working
        
        if working:
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"✅ Fresh {proxy_type.upper()} Proxies ({len(working)} working):\n\n" + 
                     "\n".join(working[:50])  # Show first 50
            )
        else:
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"❌ No working {proxy_type.upper()} proxies found. Try again later."
            )
    else:
        # Send cached proxies
        cached = proxy_cache[proxy_type][:50]
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"⚡ {proxy_type.upper()} Proxies (cached):\n\n" + 
                 "\n".join(cached) +
                 f"\n\n🔄 Use /gen to get fresh proxies"
        )

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle all button presses."""
    query = update.callback_query
    await query.answer()
    
    if query.data.startswith('gen_'):
        # Force fresh generation
        proxy_type = query.data[4:]
        await send_proxies(query.message.chat_id, proxy_type, context, force_fresh=True)
    elif query.data == 'generate':
        # Show generate options
        keyboard = [
            [InlineKeyboardButton("HTTP", callback_data="gen_http")],
            [InlineKeyboardButton("SOCKS4", callback_data="gen_socks4")],
            [InlineKeyboardButton("SOCKS5", callback_data="gen_socks5")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            text="🔄 Select proxy type to generate:",
            reply_markup=reply_markup
        )
    else:
        # Normal proxy request
        proxy_type = query.data
        await send_proxies(query.message.chat_id, proxy_type, context)

async def check_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /check command to verify proxies."""
    if not context.args:
        await update.message.reply_text(
            "❌ Please provide proxies to check in format:\n"
            "/check 1.1.1.1:8080 2.2.2.2:8081 ..."
        )
        return
    
    proxies = []
    for arg in context.args:
        if re.match(r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d{2,5}', arg):
            proxies.append(arg)
    
    if not proxies:
        await update.message.reply_text("❌ No valid proxies found in your input")
        return
    
    await update.message.reply_text(f"🔍 Checking {len(proxies)} proxies...")
    
    # Determine proxy type (default to HTTP)
    proxy_type = "http"
    if len(context.args) > 0 and context.args[0].lower() in ['socks4', 'socks5']:
        proxy_type = context.args[0].lower()
        proxies = proxies[1:]
    
    working = await asyncio.to_thread(check_proxies, proxies, proxy_type)
    
    if working:
        await update.message.reply_text(
            f"✅ Working {proxy_type.upper()} Proxies ({len(working)}/{len(proxies)}):\n\n" + 
            "\n".join(working)
        )
    else:
        await update.message.reply_text("❌ No working proxies found")

def scrape_proxies(proxy_type):
    """Scrape proxies from sources."""
    all_proxies = set()
    
    for url in PROXY_SOURCES[proxy_type]:
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                found = re.findall(r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d{2,5}', response.text)
                all_proxies.update(found)
        except Exception as e:
            logger.error(f"Error scraping {url}: {e}")
    
    return list(all_proxies)

def check_proxies(proxies, proxy_type):
    """Check if proxies are working."""
    working = []
    test_url = "http://www.google.com"
    
    def check_single_proxy(proxy):
        try:
            proxies_dict = {
                "http": f"{proxy_type}://{proxy}",
                "https": f"{proxy_type}://{proxy}"
            }
            response = requests.get(test_url, proxies=proxies_dict, timeout=5)
            if response.status_code == 200:
                return proxy
        except:
            return None
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        results = list(executor.map(check_single_proxy, proxies))
    
    working = [proxy for proxy in results if proxy is not None]
    return working

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show help message."""
    help_text = """
🤖 *Proxy Generator & Checker Bot*

*Commands:*
/start - Show proxy options
/gen - Generate fresh proxies
/check [type] proxy1 proxy2... - Check proxies (type optional: socks4/socks5)
/help - This message

*Examples:*
/gen - Generate fresh proxies
/check 1.1.1.1:8080 2.2.2.2:8081
/check socks5 1.1.1.1:8080 2.2.2.2:8081
"""
    await update.message.reply_text(help_text, parse_mode="Markdown")

def main():
    """Start the bot."""
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Add handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("gen", gen_command))
    app.add_handler(CommandHandler("check", check_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CallbackQueryHandler(button))
    
    # Start the bot
    app.run_polling()

if __name__ == "__main__":
    import concurrent.futures
    main()
