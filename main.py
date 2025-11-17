import os
import sys
import asyncio
import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    MessageHandler,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)
import yt_dlp

# ================== CONFIG ==================
TOKEN = "8424613741:AAF1hTgWWVjwfwPMpiL3Hn9QVVEUR0WhoUE"
GROUP_CHAT_ID = -4868168343  # Tu grupo privado de respaldo
TMP_DIR = "/tmp/bot_downloads"  # Carpeta temporal segura en PA
os.makedirs(TMP_DIR, exist_ok=True)

# ================== LOGGING ==================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
log = logging.getLogger("MegaBot")

# ================== SESIONES ==================
USER_SESSION = {}  # {user_id: {url, mode, quality}}

# ================== TECLADOS ==================
def build_options_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("MP4 (Vídeo)", callback_data="format_mp4"),
         InlineKeyboardButton("MP3 (Audio)", callback_data="format_mp3")],
        [InlineKeyboardButton("Calidad", callback_data="more_opts")],
    ])

def build_quality_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("1080p", callback_data="quality_1080"),
         InlineKeyboardButton("720p", callback_data="quality_720")],
        [InlineKeyboardButton("480p", callback_data="quality_480"),
         InlineKeyboardButton("360p", callback_data="quality_360")],
        [InlineKeyboardButton("Mejor disponible", callback_data="quality_best"),
         InlineKeyboardButton("Cancelar", callback_data="cancel")],
    ])

# ================== COMANDOS ==================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "¡Hola! Envía un enlace de:\n"
        "• Twitter/X • YouTube • TikTok • Instagram • Reddit\n\n"
        "Te lo descargo en MP4 o MP3 al instante 🔥"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if not text.startswith(("http://", "https://")):
        await update.message.reply_text("Envía un enlace válido")
        return
    uid = update.effective_user.id
    USER_SESSION[uid] = {"url": text}
    await update.message.reply_text("Enlace recibido. Elige formato:", reply_markup=build_options_keyboard())

# ================== CALLBACKS ==================
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    session = USER_SESSION.get(uid, {})
    if not session.get("url"):
        await query.edit_message_text("Sesión perdida. Envía el enlace de nuevo.")
        return

    data = query.data

    if data == "more_opts":
        await query.edit_message_text("Elige calidad:", reply_markup=build_quality_keyboard())
        return

    if data.startswith("quality_"):
        q = data.split("_", 1)[1]
        session["quality"] = None if q == "best" else q
        USER_SESSION[uid] = session
        await query.edit_message_text(f"Calidad: {q if q != 'best' else 'mejor'}\nElige formato:", reply_markup=build_options_keyboard())
        return

    if data == "cancel":
        USER_SESSION.pop(uid, None)
        await query.edit_message_text("Cancelado.")
        return

    if data in ("format_mp4", "format_mp3"):
        session["mode"] = data.split("_")[1]
        USER_SESSION[uid] = session
        await query.edit_message_text("Descargando… ⏳")
        await download_and_send(
            url=session["url"],
            mode=session["mode"],
            quality=session.get("quality"),
            context=context,
            user_id=uid,
            status_msg_id=query.message.message_id
        )
        USER_SESSION.pop(uid, None)

# ================== DESCARGA + RESPALDO ==================
async def download_and_send(url: str, mode: str, quality: str | None, context: ContextTypes.DEFAULT_TYPE, user_id: int, status_msg_id: int):
    user_tmp = os.path.join(TMP_DIR, str(user_id))
    os.makedirs(user_tmp, exist_ok=True)
    outtmpl = os.path.join(user_tmp, "%(id)s.%(ext)s")

    # Opciones base de yt-dlp optimizadas para PythonAnywhere
    ydl_opts = {
        "outtmpl": outtmpl,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "nocheckcertificate": True,
        "ffmpeg_location": "/home/yeinier/bin/ffmpeg",  # <-- TU FFMPEG
        "proxy": "",  # <-- BYPASS DEL PROXY DE PA (lo más importante)
        "geo_bypass": True,
        "extractor_retries": 10,
        "retries": 10,
        "fragment_retries": 10,
    }

    if mode == "mp4":
        ydl_opts["merge_output_format"] = "mp4"
        if quality and quality.isdigit():
            ydl_opts["format"] = f"bestvideo[height<={quality}]+bestaudio/best"
        else:
            ydl_opts["format"] = "bestvideo+bestaudio/best"
    else:  # mp3
        ydl_opts["format"] = "bestaudio/best"
        ydl_opts["postprocessors"] = [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }]

    # Fix especial para Twitter/X
    if any(x in url for x in ["twitter.com", "x.com", "fxtwitter.com"]):
        ydl_opts["extractor_args"] = {"twitter": {"prefer_native": True}}

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            if mode == "mp3" and not filename.endswith(".mp3"):
                filename = filename.rsplit(".", 1)[0] + ".mp3"

        # 1) Subir al grupo privado (respaldo)
        with open(filename, "rb") as f:
            user = await context.bot.get_chat(user_id)
            caption = (
                f"Respaldo automático\n"
                f"Usuario: {user.full_name} (@{user.username or 'sin usuario'})\n"
                f"ID: {user_id}\n"
                f"Enlace: {url}\n"
                f"Formato: {mode.upper()} | Calidad: {quality or 'mejor'}"
            )
            archive_msg = await context.bot.send_document(
                chat_id=GROUP_CHAT_ID,
                document=f,
                caption=caption,
                read_timeout=300,
                write_timeout=300,
            )

        # 2) Enviar al usuario (copiando desde el grupo)
        await context.bot.copy_message(
            chat_id=user_id,
            from_chat_id=GROUP_CHAT_ID,
            message_id=archive_msg.message_id
        )
        await context.bot.delete_message(user_id, status_msg_id)

    except Exception as e:
        log.error(f"Error user {user_id}: {e}")
        await context.bot.edit_message_text(
            chat_id=user_id,
            message_id=status_msg_id,
            text=f"Error al descargar:\n{str(e)[:300]}"
        )
    finally:
        # Limpieza
        if os.path.exists(filename):
            try: os.remove(filename)
            except: pass

# ================== MAIN ==================
if __name__ == "__main__":
    log.info("Bot iniciando en PythonAnywhere con Python 3.13...")
    app = ApplicationBuilder().token(TOKEN).read_timeout(90).write_timeout(90).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(callback_handler))

    log.info("Bot corriendo 24/7 - Twitter/X, YouTube, TikTok, Instagram, Reddit ✅")
    app.run_polling(drop_pending_updates=True)
