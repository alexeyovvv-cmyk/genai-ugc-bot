"""Handlers module for the Telegram bot.

This module contains all the message and callback handlers organized by functionality.
"""

from aiogram import Dispatcher


def register_all_handlers(dp: Dispatcher):
    """
    Register all handlers with the dispatcher.
    
    Args:
        dp: The aiogram Dispatcher instance
    """
    # Import all handler modules to register their decorators
    from . import (
        start,
        character_selection,
        character_editing,
        voice_selection,
        generation,
        my_generations,
        feedback,
        credits,
        navigation
    )
    
    # Handlers are registered via decorators when modules are imported
    # No additional registration needed
