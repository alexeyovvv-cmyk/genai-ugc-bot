"""Shared dispatcher instance for the bot."""
from aiogram import Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

# Create FSM storage
storage = MemoryStorage()

# Create shared dispatcher instance with FSM storage
dp = Dispatcher(storage=storage)
