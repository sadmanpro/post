import re
import os
import shutil
import asyncio
from telegram import (
    Update, InputFile, BotCommand
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    filters, ContextTypes
)

# === BOT SETTINGS ===
TEXT_DEFAULT_PREFIX = "✅ Text Update:"
BASE_PREFIX = "📌 HSC-24:"
CHANNEL_LINK = "https://t.me/addlist/qwlJ7Ve1bW8xNzg1"
SUFFIX_TEXT = "🎓 Study on Telegram!"
DEFAULT_DOC_PREFIX = "DOC-UPDATE_"

def escape_md2(text: str) -> str:
    return re.sub(r'([_*\[\]()~`>#+\-=|{}.!])', r'\\\1', text)

user_data = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_data[user_id] = {
        'pdf_list': [],
        'thumbnail_id': None,
        'custom_doc_prefix': DEFAULT_DOC_PREFIX,
        'expecting_custom_prefix': False
    }
    await update.message.reply_text(
        "🔰 *Welcome!*\n\n"
        "Set your custom thumbnail, prefix, or finish the work.\n\n"
        "👉 *Commands:*\n"
        "/setprefix — Set a DOC prefix (example: SOT -)\n"
        "/setthumbnail — Upload a custom thumbnail\n"
        "/finish — Send all final PDFs in order",
        parse_mode="MarkdownV2"
    )

async def setprefix(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_state = user_data.setdefault(user_id, {})
    user_state['expecting_custom_prefix'] = True
    await update.message.reply_text(
        "✏️ Send me your desired DOC prefix now.\nExample: SOT -"
    )

async def setthumbnail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📷 Send me a photo now to set as your custom thumbnail."
    )

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_state = user_data.setdefault(user_id, {})
    photo = update.message.photo[-1]
    user_state['thumbnail_id'] = photo.file_id
    await update.message.reply_text("✅ Thumbnail saved!")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()
    user_state = user_data.setdefault(user_id, {
        'pdf_list': [],
        'custom_doc_prefix': DEFAULT_DOC_PREFIX
    })

    if user_state.get('expecting_custom_prefix'):
        user_state['custom_doc_prefix'] = text
        user_state['expecting_custom_prefix'] = False
        await update.message.reply_text(
            f"✅ DOC prefix set to: `{escape_md2(text)}`",
            parse_mode="MarkdownV2"
        )
        return

    if update.message.reply_to_message and update.message.reply_to_message.document:
        new_name = text
        doc_message_id = update.message.reply_to_message.message_id

        for doc in user_state['pdf_list']:
            if doc['message_id'] == doc_message_id and not doc.get('finalized', False):
                file = await context.bot.get_file(doc['file_id'])
                tmp_dir = f"./tmp_user_{user_id}"
                os.makedirs(tmp_dir, exist_ok=True)

                final_name = f"{user_state['custom_doc_prefix']}{new_name}.pdf"
                final_path = os.path.join(tmp_dir, final_name)
                await file.download_to_drive(final_path)

                thumb = user_state.get('thumbnail_id')

                await update.message.reply_document(
                    document=InputFile(final_path, filename=final_name),
                    thumbnail=thumb
                )

                doc['path'] = final_path
                doc['name'] = final_name
                doc['finalized'] = True

                await update.message.reply_text(
                    f"✅ Renamed & uploaded: `{escape_md2(final_name)}`",
                    parse_mode="MarkdownV2"
                )
                break
        return

    if 'uni_update' not in user_state:
        user_state['uni_update'] = text
        await update.message.reply_text("✏️ Write the body:")
    elif 'body' not in user_state:
        user_state['body'] = text
        await update.message.reply_text(
            "📎 Great! Now upload PDF(s).\nReply each with file name. Use /finish when done."
        )
    else:
        await update.message.reply_text(
            "✅ Ready. Upload PDFs or use /finish."
        )

async def handle_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_state = user_data.setdefault(user_id, {'pdf_list': [], 'custom_doc_prefix': DEFAULT_DOC_PREFIX})

    if 'uni_update' not in user_state or 'body' not in user_state:
        await update.message.reply_text("❗ Use /start first.")
        return

    document = update.message.document
    user_state['pdf_list'].append({
        'file_id': document.file_id,
        'message_id': update.message.message_id,
        'finalized': False
    })

    await update.message.reply_text(
        "✏️ Write the file name in reply to this document."
    )

async def finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_state = user_data.get(user_id, {})

    pdf_list = user_state.get('pdf_list', [])
    if not pdf_list:
        await update.message.reply_text("❗ No PDFs found. Upload first.")
        return

    safe_text_prefix = f"*{escape_md2(TEXT_DEFAULT_PREFIX)}*"
    safe_base = f"*{escape_md2(BASE_PREFIX + ' ' + user_state['uni_update'])}*"
    safe_body = escape_md2(user_state['body'])
    safe_suffix = f"*[{escape_md2(SUFFIX_TEXT)}]({CHANNEL_LINK})*"

    final_caption = f"{safe_text_prefix} {safe_base}\n\n✨ {safe_body}\n\n👉 {safe_suffix}"
    thumb = user_state.get('thumbnail_id')

    for i, doc in enumerate(pdf_list):
        if not doc.get('finalized', False):
            await update.message.reply_text(
                f"⚠️ Not finalized: Please reply with file name for PDF uploaded in message ID {doc['message_id']}"
            )
            continue

        caption = final_caption if i == len(pdf_list) - 1 else None
        await update.message.reply_document(
            document=InputFile(doc['path'], filename=doc['name']),
            caption=caption,
            parse_mode="MarkdownV2" if caption else None,
            thumbnail=thumb
        )

    shutil.rmtree(f"./tmp_user_{user_id}", ignore_errors=True)
    user_data.pop(user_id, None)

    await update.message.reply_text("✅ All files sent in order. Session cleared!")

async def set_bot_commands(app):
    commands = [
        BotCommand("start", "Start the bot"),
        BotCommand("setprefix", "Set a DOC prefix"),
        BotCommand("setthumbnail", "Upload a custom thumbnail"),
        BotCommand("finish", "Send all final PDFs in order")
    ]
    await app.bot.set_my_commands(commands)

async def main():
    TOKEN = os.getenv("BOT_TOKEN")
    app = (
        ApplicationBuilder()
        .token(TOKEN)
        .connect_timeout(60)
        .read_timeout(60)
        .write_timeout(60)
        .get_updates_http_version("1.1")
        .build()
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("setprefix", setprefix))
    app.add_handler(CommandHandler("setthumbnail", setthumbnail))
    app.add_handler(CommandHandler("finish", finish))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.Document.PDF, handle_pdf))

    await set_bot_commands(app)

    print("✅ Bot running...")
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
