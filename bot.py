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
ALLOWED_CHANNEL_ID = 1549047455797084271
DEVELOPER_ROLE_ID = 1549047984506019870

COOLDOWN_FILE = "cooldowns.json"
CODES_FILE = "codes.json"
DISCOUNTS_FILE = "discounts.json"

DEFAULT_DISCOUNTS = [
    (5,  35),
    (10, 30),
    (15, 20),
    (20, 10),
    (25, 4),
    (30, 1),
]

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

def load_discounts():
    data = load_json(DISCOUNTS_FILE)
    if not data:
        save_json(DISCOUNTS_FILE, DEFAULT_DISCOUNTS)
        return DEFAULT_DISCOUNTS
    return data

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
    discounts = load_discounts()
    r = random.uniform(0, 100)
    cumulative = 0
    for percent, chance in discounts:
        cumulative += chance
        if r <= cumulative:
            return percent
    return discounts[-1][0]

def generuj_kod(znizka: int, user_id: int, username: str) -> str:
    losowa = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(6))
    kod = f"ZN{znizka}-{losowa}"
    
    codes = load_json(CODES_FILE)
    codes[kod] = {
        "znizka": znizka,
        "user_id": user_id,
        "username": username,
        "data": datetime.now().isoformat(),
        "
