import discord
from discord import app_commands
from discord.ext import commands
import random
import json
import os
from datetime import datetime, timedelta
import string
import secrets

TOKEN = os.getenv("TOKEN")
GUILD_ID = None
COOLDOWN_DAYS = 7

DISCOUNTS = [
    (5,  35),
    (10, 30),
    (15, 20),
    (20, 10),
    (25, 4),
    (30, 1),
]

COOLDOWN_FILE = "cooldowns.json"
CODES_FILE = "codes.json"

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

def load_json(filename):
    if os.path.exists(filename):
        with open(filename, "r") as f:
            return json.load(f)
    return {}

def save_json(filename, data):
    with open(filename, "w") as f:
        json.dump(data, f, indent=2)

def can_use(user_id: int):
    data = load_json(COOLDOWN_FILE)
    user_id = str(user_id)
    
    if user_id not in data:
        return True, None
    
    last_use = datetime.fromisoformat(data[user_id])
    next_use = last_use + timedelta(days=COOLDOWN_DAYS)
    
    if datetime.now() >= next_use:
        return True, None
    
    remaining = next_use - datetime.now()
    days = remaining.days
    hours = remaining.seconds // 3600
    return False, f"Możesz użyć komendy ponownie za **{days}d {hours}h**."

def set_cooldown(user_id: int):
    data = load_json(COOLDOWN_FILE)
    data[str(user_id)] = datetime.now().isoformat()
    save_json(COOLDOWN_FILE, data)

def losuj_znizke():
    r = random.uniform(0, 100)
    cumulative = 0
    for percent, chance in DISCOUNTS:
        cumulative += chance
        if r <= cumulative:
            return percent
    return DISCOUNTS[-1][0]

def generuj_kod(znizka: int, user_id: int, username: str) -> str:
    losowa = ''.join
