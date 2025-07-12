import json
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils import executor
from aiogram.contrib.middlewares.logging import LoggingMiddleware

API_TOKEN = "7939460560:AAEqdNygqbB9hlSJFvH3R8qd4c7yhrg1Ua0"  # Replace with your bot token

# Configure logging
logging.basicConfig(level=logging.INFO)

# Initialize bot and dispatcher
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)
dp.middleware.setup(LoggingMiddleware())

# Load characters database from JSON
with open("characters.json", "r") as f:
    CHARACTERS = json.load(f)

# Extract all possible questions (attributes)
ALL_QUESTIONS = set()
for char in CHARACTERS:
    ALL_QUESTIONS.update(char["attributes"].keys())

# In-memory storage of user sessions
sessions = {}

# Start command handler
@dp.message_handler(commands=["start"])
async def start_game(message: types.Message):
    user_id = message.from_user.id
    # Initialize session
    sessions[user_id] = {
        "possible_characters": CHARACTERS.copy(),
        "answered_questions": {}
    }
    await message.answer(
        "Think of a character. I will try to guess it by asking yes/no/maybe questions."
    )
    await ask_next_question(user_id, message)


async def ask_next_question(user_id, message_or_callback):
    session = sessions[user_id]
    unanswered = ALL_QUESTIONS - set(session["answered_questions"].keys())

    if not session["possible_characters"]:
        await message_or_callback.answer("I give up! 🤷‍♂️")
        sessions.pop(user_id, None)
        return

    if len(session["possible_characters"]) == 1:
        name = session["possible_characters"][0]["name"]
        await message_or_callback.answer(f"Is it... **{name}**? 🎉", parse_mode="Markdown")
        sessions.pop(user_id, None)
        return

    if not unanswered:
        await message_or_callback.answer("I don't have any more questions! I give up.")
        sessions.pop(user_id, None)
        return

    # Pick the question that splits the remaining characters most evenly
    best_question = None
    best_diff = len(session["possible_characters"])
    for question in unanswered:
        yes_count = sum(
            1 for c in session["possible_characters"] if c["attributes"].get(question) == "yes"
        )
        no_count = sum(
            1 for c in session["possible_characters"] if c["attributes"].get(question) == "no"
        )
        maybe_count = sum(
            1 for c in session["possible_characters"] if c["attributes"].get(question) == "maybe"
        )
        # Calculate how balanced the split is
        counts = [yes_count, no_count, maybe_count]
        diff = max(counts) - min(counts)
        if diff < best_diff:
            best_diff = diff
            best_question = question

    # Send question with inline buttons
    buttons = [
        InlineKeyboardButton("Yes", callback_data=f"{best_question}:yes"),
        InlineKeyboardButton("No", callback_data=f"{best_question}:no"),
        InlineKeyboardButton("Maybe", callback_data=f"{best_question}:maybe"),
    ]
    keyboard = InlineKeyboardMarkup().add(*buttons)
    await message_or_callback.answer(f"Is your character: **{best_question.replace('_', ' ')}?**", parse_mode="Markdown", reply_markup=keyboard)


@dp.callback_query_handler(lambda c: ":" in c.data)
async def handle_answer(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    if user_id not in sessions:
        await callback_query.answer("Please start a new game with /start")
        return

    data = callback_query.data
    question, answer = data.split(":")
    session = sessions[user_id]
    session["answered_questions"][question] = answer

    # Filter characters
    filtered = []
    for char in session["possible_characters"]:
        char_answer = char["attributes"].get(question)
        if char_answer == answer:
            filtered.append(char)
    session["possible_characters"] = filtered

    await ask_next_question(user_id, callback_query)


if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
