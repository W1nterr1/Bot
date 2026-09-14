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

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

def load_cooldowns():
    if os.path.exists(COOLDOWN_FILE):
        with open(COOLDOWN_FILE, "r") as f:
            return json.load(f)
    return {}

def save_cooldowns(data):
    with open(COOLDOWN_FILE, "w") as f:
        json.dump(data, f, indent=2)

def can_use(user_id: int):
    data = load_cooldowns()
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
    data = load_cooldowns()
    data[str(user_id)] = datetime.now().isoformat()
    save_cooldowns(data)

def losuj_znizke():
    r = random.uniform(0, 100)
    cumulative = 0
    for percent, chance in DISCOUNTS:
        cumulative += chance
        if r <= cumulative:
            return percent
    return DISCOUNTS[-1][0]

def generuj_kod(znizka: int) -> str:
    losowa = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(6))
    return f"ZN{znizka}-{losowa}"

class ZnizkaView(discord.ui.View):
    def __init__(self, znizka: int, user_id: int):
        super().__init__(timeout=300)
        self.znizka = znizka
        self.user_id = user_id
        self.uzyto = False

    @discord.ui.button(label="Użyj zniżki", style=discord.ButtonStyle.green, emoji="🎫")
    async def uzyj_znizki(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("To nie Twoja zniżka!", ephemeral=True)
            return

        if self.uzyto:
            await interaction.response.send_message("Już użyłeś tej zniżki.", ephemeral=True)
            return

        self.uzyto = True
        button.disabled = True
        button.label = "Użyto"
        await interaction.message.edit(view=self)

        kod = generuj_kod(self.znizka)

        try:
            embed_dm = discord.Embed(
                title="🎫 Twój kod zniżki",
                description=f"**Kod:** `{kod}`\n**Wartość:** **{self.znizka}%**",
                color=discord.Color.green()
            )
            embed_dm.set_footer(text="Zachowaj ten kod – jest unikalny")
            await interaction.user.send(embed=embed_dm)
            
            await interaction.response.send_message(
                f"✅ Kod został wysłany na Twoje DM!\nKod: `{kod}`",
                ephemeral=True
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                f"⚠️ Nie mogę wysłać Ci DM.\nTwój kod: `{kod}`",
                ephemeral=True
            )

@bot.event
async def on_ready():
    print(f"Zalogowano jako {bot.user}")
    try:
        if GUILD_ID:
            synced = await bot.tree.sync(guild=discord.Object(id=GUILD_ID))
        else:
            synced = await bot.tree.sync()
        print(f"Zsynchronizowano {len(synced)} komend")
    except Exception as e:
        print(f"Błąd sync: {e}")

@bot.tree.command(name="znizka", description="Losuj zniżkę (raz na tydzień)")
async def znizka(interaction: discord.Interaction):
    moze, msg = can_use(interaction.user.id)
    if not moze:
        await interaction.response.send_message(msg, ephemeral=True)
        return

    znizka_procent = losuj_znizke()
    set_cooldown(interaction.user.id)

    if znizka_procent >= 25:
        color = discord.Color.gold()
        emoji = "🔥"
    elif znizka_procent >= 15:
        color = discord.Color.green()
        emoji = "✨"
    else:
        color = discord.Color.blue()
        emoji = "🎫"

    embed = discord.Embed(
        title=f"{emoji} Wylosowałeś zniżkę!",
        description=f"**{znizka_procent}%** zniżki",
        color=color
    )
    embed.set_footer(text="Kliknij przycisk poniżej, żeby otrzymać kod na DM")

    view = ZnizkaView(znizka_procent, interaction.user.id)
    await interaction.response.send_message(embed=embed, view=view)

@bot.tree.command(name="szanse", description="Pokaż aktualne szanse na zniżki")
@app_commands.checks.has_permissions(administrator=True)
async def szanse(interaction: discord.Interaction):
    text = "\n".join([f"**{p}%** → `{c}%` szans" for p, c in DISCOUNTS])
    embed = discord.Embed(title="Aktualne szanse dropu", description=text, color=discord.Color.blurple())
    await interaction.response.send_message(embed=embed, ephemeral=True)

bot.run(TOKEN)
