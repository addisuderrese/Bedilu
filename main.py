import os
import json
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext

# Set up logging
logging.basicConfig(level=logging.INFO)

# Environment variable for the bot token
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")

# Initialize bot, dispatcher, and memory storage
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# --- Game Logic ---

def load_characters():
    """Loads the character database from the JSON file."""
    try:
        with open('characters.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        logging.error("characters.json not found.")
        return []
    except json.JSONDecodeError:
        logging.error("Error decoding characters.json.")
        return []

def get_next_question(remaining_characters):
    """
    Determines the best next question to ask by finding the attribute
    that splits the remaining characters most evenly.
    """
    question_counts = {}
    for character in remaining_characters:
        for attribute, value in character["attributes"].items():
            if attribute not in question_counts:
                question_counts[attribute] = {}
            if value not in question_counts[attribute]:
                question_counts[attribute][value] = 0
            question_counts[attribute][value] += 1

    best_question = None
    min_difference = float('inf')

    for attribute, values in question_counts.items():
        if len(values) > 1:
            counts = list(values.values())
            difference = max(counts) - min(counts)
            if difference < min_difference:
                min_difference = difference
                best_question = attribute

    return best_question


# --- Handlers ---

@dp.message(CommandStart())
async def send_welcome(message: types.Message, state: FSMContext):
    """
    Handles the /start command.
    Initializes the game state and asks the first question.
    """
    await state.update_data(
        remaining_characters=load_characters(),
        asked_questions=set()
    )
    await message.answer("Think of a character, and I will try to guess who it is! I will ask you a series of yes/no questions.")
    await ask_question(message.chat.id, state)

async def ask_question(chat_id: int, state: FSMContext):
    """
    Asks the next logical question or makes a guess.
    """
    data = await state.get_data()
    remaining_characters = data.get("remaining_characters", [])
    asked_questions = data.get("asked_questions", set())

    if not remaining_characters:
        await bot.send_message(chat_id, "I give up! I couldn't figure out your character.")
        await state.clear()
        return

    if len(remaining_characters) == 1:
        guess = remaining_characters[0]["name"]
        await bot.send_message(chat_id, f"I think your character is {guess}!")
        await state.clear()
        return

    next_question_attribute = get_next_question(remaining_characters)

    if not next_question_attribute or next_question_attribute in asked_questions:
        await bot.send_message(chat_id, "I'm running out of questions... I give up!")
        await state.clear()
        return

    asked_questions.add(next_question_attribute)
    await state.update_data(asked_questions=asked_questions, current_question=next_question_attribute)

    # For simplicity, we'll ask about the most common value for the attribute
    # A more advanced version could present all possible values.
    possible_values = list(set(c["attributes"].get(next_question_attribute) for c in remaining_characters if next_question_attribute in c["attributes"]))

    # We will formulate the question around the first possible value.
    # This works best for boolean-like attributes.
    question_text = f"Is your character {next_question_attribute.replace('_', ' ')}: {possible_values[0]}?"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Yes", callback_data=f"yes:{possible_values[0]}")],
        [InlineKeyboardButton(text="No", callback_data=f"no:{possible_values[0]}")],
        [InlineKeyboardButton(text="Maybe", callback_data="maybe")]
    ])
    await bot.send_message(chat_id, question_text, reply_markup=keyboard)


@dp.callback_query()
async def process_callback(callback_query: types.CallbackQuery, state: FSMContext):
    """
    Processes the user's answer from the inline keyboard.
    """
    answer, value = callback_query.data.split(":", 1) if ":" in callback_query.data else (callback_query.data, None)

    data = await state.get_data()
    remaining_characters = data.get("remaining_characters", [])
    current_question = data.get("current_question")

    if answer == "yes":
        remaining_characters = [
            char for char in remaining_characters
            if char["attributes"].get(current_question) == value
        ]
    elif answer == "no":
        remaining_characters = [
            char for char in remaining_characters
            if char["attributes"].get(current_question) != value
        ]
    # "Maybe" answer doesn't filter the list for this simple implementation

    await state.update_data(remaining_characters=remaining_characters)
    await callback_query.message.delete()
    await ask_question(callback_query.from_user.id, state)


async def main():
    """Starts the bot."""
    if not BOT_TOKEN:
        logging.critical("No BOT_TOKEN found. Please set the TELEGRAM_BOT_TOKEN environment variable.")
        return
    await dp.start_polling(bot)

if __name__ == '__main__':
    import asyncio
    asyncio.run(main())