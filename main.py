import asyncio
import base64
import io
import os

import aiohttp
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message
from aiogram.enums import ChatMemberStatus


# --- Настройки через переменные окружения (задаются в Railway) ---
BOT_TOKEN = os.environ["BOT_TOKEN"]            # токен от @BotFather
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]  # ключ с aistudio.google.com

CHANNEL_USERNAME = "@ykm1nd"
CHANNEL_LINK = "https://t.me/ykm1nd"

GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    f"{os.environ.get('MODEL', 'gemini-2.5-flash')}:generateContent"
)


bot = Bot(BOT_TOKEN)
dp = Dispatcher()


async def check_subscription(message: Message):
    try:
        member = await bot.get_chat_member(
            CHANNEL_USERNAME,
            message.from_user.id
        )

        return member.status in {
            ChatMemberStatus.MEMBER,
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.CREATOR
        }

    except Exception as e:
        print("Ошибка проверки подписки:", e)
        return False


async def analyze_photo(image_bytes: bytes):
    image_base64 = base64.b64encode(image_bytes).decode("utf-8")

    prompt = """
Ты — оценщик внешности по фотографии.

Внимательно проанализируй ИМЕННО человека на переданной фотографии.

Дай субъективную оценку привлекательности от 1 до 10.

Оценка должна зависеть от конкретной фотографии и человека.
Не используй одну и ту же оценку для всех фотографий.

Учитывай:
- лицо и пропорции;
- глаза, нос, губы, подбородок и челюсть;
- кожу;
- волосы;
- симметрию;
- общий внешний вид;
- гармоничность черт.

Не оценивай качество фотографии, освещение или камеру.

Ответь строго в таком формате:

Оценка: X/10

Почему:
кратко объясни основные причины оценки.

Что хорошо:
- пункт
- пункт
- пункт

Что можно улучшить:
- пункт
- пункт

Будь честным и объективным. Не придумывай характеристики, которых не видно на фотографии.
"""

    data = {
        "contents": [{
            "parts": [
                {"text": prompt},
                {
                    "inline_data": {
                        "mime_type": "image/jpeg",
                        "data": image_base64
                    }
                }
            ]
        }],
        "safety_settings": [
            {"category": c, "threshold": "BLOCK_NONE"}
            for c in [
                "HARM_CATEGORY_HARASSMENT",
                "HARM_CATEGORY_HATE_SPEECH",
                "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                "HARM_CATEGORY_DANGEROUS_CONTENT"
            ]
        ]
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(
            GEMINI_URL,
            params={"key": GEMINI_API_KEY},
            json=data,
            timeout=aiohttp.ClientTimeout(total=120)
        ) as response:

            if response.status != 200:
                error = await response.text()
                raise Exception(
                    f"Gemini ошибка {response.status}: {error}"
                )

            result = await response.json()

    try:
        return result["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError):
        raise Exception(f"Неожиданный ответ Gemini: {result}")


@dp.message(F.photo)
async def photo_handler(message: Message):

    subscribed = await check_subscription(message)

    if not subscribed:
        await message.answer(
            "❌ Сначала подпишись на канал:\n\n"
            f"{CHANNEL_LINK}\n\n"
            "После подписки отправь фотографию ещё раз."
        )
        return

    await message.answer("🔎 Анализирую фотографию...")

    try:
        photo = message.photo[-1]

        file = await bot.get_file(photo.file_id)

        buffer = io.BytesIO()

        await bot.download_file(
            file.file_path,
            buffer
        )

        image_bytes = buffer.getvalue()

        result = await analyze_photo(image_bytes)

        await message.answer(result)

    except Exception as e:
        print("ОШИБКА:", e)

        await message.answer(
            "❌ Не удалось проанализировать фотографию.\n"
            "Попробуй ещё раз чуть позже."
        )


@dp.message()
async def other_messages(message: Message):

    if message.text == "/start":
        await message.answer(
            "👋 Отправь фотографию лица.\n\n"
            "Перед оценкой необходимо подписаться на канал."
        )
    else:
        await message.answer(
            "📸 Отправь фотографию."
        )


async def main():
    print("Бот запущен")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
