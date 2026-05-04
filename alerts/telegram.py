#!/usr/bin/env python3
"""
alerts/telegram.py — Telegram Service
Centralized photo/text sending with Markdown escaping, chunked messages, topic threading.
"""

import io
import logging
from typing import Optional

from telegram import Bot
from telegram.error import TelegramError

from core.config import settings

logger = logging.getLogger("Telegram")

# Characters that need escaping in MarkdownV2
_MARKDOWN_V2_SPECIAL = r'_*[]()~`>#+-=|{}.!'


class TelegramService:
    """
    Centralized Telegram messaging service.
    
    Usage:
        tg = TelegramService()
        await tg.send_photo(chart_buffer, "Caption text")
        await tg.send_text("Long analysis text")
    """

    def __init__(self):
        self.token = settings.telegram_token
        self.chat_id = settings.chat_id
        self.topic_id = int(settings.topic_id) if settings.topic_id else None
        self._bot: Optional[Bot] = None

        if not self.token or not self.chat_id:
            logger.warning("TELEGRAM_TOKEN or CHAT_ID missing. Messages will be logged only.")

    @property
    def bot(self) -> Optional[Bot]:
        if self._bot is None and self.token:
            self._bot = Bot(token=self.token)
        return self._bot

    @property
    def is_configured(self) -> bool:
        return bool(self.token and self.chat_id)

    async def send_photo(self, photo: io.BytesIO, caption: str = "",
                         parse_mode: str = "Markdown") -> bool:
        """Send a photo with caption to Telegram."""
        if not self.is_configured:
            logger.info(f"[Mock] Photo sent. Caption: {caption[:80]}...")
            return False

        try:
            # Truncate caption to Telegram limit (1024 chars)
            if len(caption) > 1024:
                caption = caption[:1020] + "..."

            await self.bot.send_photo(
                chat_id=self.chat_id,
                photo=photo,
                caption=caption,
                parse_mode=parse_mode,
                message_thread_id=self.topic_id
            )
            logger.info("Photo sent to Telegram.")
            return True

        except TelegramError as e:
            logger.error(f"Telegram photo error: {e}")
            # Retry without parse_mode if formatting fails
            try:
                photo.seek(0)
                await self.bot.send_photo(
                    chat_id=self.chat_id,
                    photo=photo,
                    caption=caption,
                    message_thread_id=self.topic_id
                )
                logger.info("Photo sent (plain mode fallback).")
                return True
            except TelegramError as e2:
                logger.error(f"Telegram photo fallback error: {e2}")
                return False

    async def send_text(self, text: str,
                        parse_mode: str = "Markdown") -> bool:
        """Send a text message, auto-chunking if longer than 4096 chars."""
        if not self.is_configured:
            logger.info(f"[Mock] Text sent: {text[:80]}...")
            return False

        try:
            chunks = self._chunk_text(text, 4096)
            for chunk in chunks:
                await self.bot.send_message(
                    chat_id=self.chat_id,
                    text=chunk,
                    parse_mode=parse_mode,
                    message_thread_id=self.topic_id
                )
            logger.info(f"Text sent ({len(chunks)} chunk(s)).")
            return True

        except TelegramError as e:
            logger.error(f"Telegram text error: {e}")
            # Retry without parse_mode
            try:
                chunks = self._chunk_text(text, 4096)
                for chunk in chunks:
                    await self.bot.send_message(
                        chat_id=self.chat_id,
                        text=chunk,
                        message_thread_id=self.topic_id
                    )
                return True
            except TelegramError as e2:
                logger.error(f"Telegram text fallback error: {e2}")
                return False

    def _chunk_text(self, text: str, max_len: int = 4096) -> list:
        """Split text into Telegram-safe chunks."""
        if len(text) <= max_len:
            return [text]

        chunks = []
        lines = text.split('\n')
        current = ""

        for line in lines:
            if len(current) + len(line) + 1 > max_len:
                if current:
                    chunks.append(current)
                current = line
            else:
                current = current + '\n' + line if current else line

        if current:
            chunks.append(current)

        return chunks
