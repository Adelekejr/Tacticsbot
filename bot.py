import os
import logging
from telegram import Update, BotCommand
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
from openai import OpenAI

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# ── Groq client (OpenAI-compatible) ──────────────────────────────────────────
client = OpenAI(
    api_key=os.environ["GROQ_API_KEY"],
    base_url="https://api.groq.com/openai/v1"
)

# ── System prompt ─────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are TacticsGPT — an elite virtual football manager coach with deep expertise in:
- Football Manager, EA FC (Career Mode), Top Eleven, and other virtual manager games
- Formations, tactical systems, and player roles
- Beating specific opponent styles and formations
- Transfer advice, squad building, and player instructions
- Set pieces, pressing triggers, and in-game adjustments

Your personality: confident, direct, and passionate about football tactics.
Keep responses concise (under 200 words) unless the user asks for detail.
Use emojis sparingly for readability (⚽ 🔴 📋 ⚡).
Always give actionable, specific advice — never vague generalities.
When suggesting formations, explain WHY it works vs the opponent.
If the user gives context about their team or opponent, remember it for the conversation."""

# ── Per-user conversation history ─────────────────────────────────────────────
user_histories: dict[int, list[dict]] = {}
MAX_HISTORY = 10


def get_history(user_id: int) -> list[dict]:
    return user_histories.setdefault(user_id, [])


def add_to_history(user_id: int, role: str, content: str):
    history = get_history(user_id)
    history.append({"role": role, "content": content})
    if len(history) > MAX_HISTORY * 2:
        user_histories[user_id] = history[-(MAX_HISTORY * 2):]


# ── AI call ───────────────────────────────────────────────────────────────────
def ask_ai(user_id: int, message: str) -> str:
    add_to_history(user_id, "user", message)
    history = get_history(user_id)
    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + history

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            max_tokens=600,
            messages=messages,
        )
        reply = response.choices[0].message.content
        add_to_history(user_id, "assistant", reply)
        return reply
    except Exception as e:
        logger.error(f"Groq API error: {e}")
        return "⚠️ Tactics board is offline right now. Try again in a moment!"


# ── Command handlers ──────────────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.effective_user.first_name or "Gaffer"
    text = (
        f"👋 Welcome, {name}! I'm *TacticsGPT* — your virtual football manager coach.\n\n"
        "Here's what I can help with:\n"
        "⚽ /formation — Get a formation recommendation\n"
        "🔴 /counter — How to counter an opponent's formation\n"
        "📋 /pressing — Pressing & defensive tactics\n"
        "⚡ /setpiece — Set piece strategies\n"
        "🔄 /reset — Clear our conversation\n\n"
        "Or just *type your question* and I'll answer instantly!\n\n"
        "_Example: \"My opponent plays 4-2-3-1 and presses high, I have fast wingers\"_"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_histories[user_id] = []
    await update.message.reply_text(
        "🔄 Conversation cleared! Fresh tactics board. What's the situation?"
    )


async def formation_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = " ".join(context.args) if context.args else ""
    prompt = (
        f"Recommend the best formation for this situation: {args}"
        if args
        else "What are the top 3 most versatile formations for a virtual manager game? Give brief pros/cons for each."
    )
    await _reply_with_typing(update, context, prompt)


async def counter_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = " ".join(context.args) if context.args else ""
    prompt = (
        f"How do I tactically counter this: {args}"
        if args
        else "How do I counter the 3 most common formations: 4-2-3-1, 4-3-3, and 3-5-2?"
    )
    await _reply_with_typing(update, context, prompt)


async def pressing_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = " ".join(context.args) if context.args else ""
    prompt = (
        f"Advise on pressing tactics for: {args}"
        if args
        else "When should I use high press vs mid-block vs low block in a virtual manager game?"
    )
    await _reply_with_typing(update, context, prompt)


async def setpiece_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = " ".join(context.args) if context.args else ""
    prompt = (
        f"Give me set piece advice for: {args}"
        if args
        else "What are the best corner kick and free kick routines in a virtual manager game?"
    )
    await _reply_with_typing(update, context, prompt)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    await _reply_with_typing(update, context, text, user_id=user_id)


async def _reply_with_typing(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    prompt: str,
    user_id: int = None,
):
    if user_id is None:
        user_id = update.effective_user.id
    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id, action="typing"
    )
    reply = ask_ai(user_id, prompt)
    await update.message.reply_text(reply, parse_mode="Markdown")


# ── Bot setup ─────────────────────────────────────────────────────────────────
async def post_init(app):
    await app.bot.set_my_commands([
        BotCommand("start", "Welcome message & help"),
        BotCommand("formation", "Get formation advice"),
        BotCommand("counter", "Counter an opponent formation"),
        BotCommand("pressing", "Pressing & defensive tactics"),
        BotCommand("setpiece", "Set piece strategies"),
        BotCommand("reset", "Clear conversation history"),
    ])


def main():
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN environment variable not set!")

    app = (
        ApplicationBuilder()
        .token(token)
        .post_init(post_init)
        .build()
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("reset", reset))
    app.add_handler(CommandHandler("formation", formation_cmd))
    app.add_handler(CommandHandler("counter", counter_cmd))
    app.add_handler(CommandHandler("pressing", pressing_cmd))
    app.add_handler(CommandHandler("setpiece", setpiece_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("⚽ TacticsGPT is live!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
