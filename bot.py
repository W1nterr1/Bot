
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
DEVELOPER_ROLE_ID = 1549047984506019870
COOLDOWN_DAYS = 7
ALLOWED_CHANNEL_ID = 1549047455797084271

COOLDOWN_FILE = "cooldowns. json"
CODES_FILE = "codes.json"
DISCOUNTS_FILE = "discounts.json"

DEFAULT_DISCOUNTS = [
    (5, 20),   # -5 zł
    (15, 7),   # -15 zł
    (25, 1),   # -25 zł
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


def can_use(user_id):
    data = load_json(COOLDOWN_FILE)
    user_id = str(user_id)

    if user_id not in data:
        return True, None

    last_use = datetime.fromisoformat(data[user_id])
    next_use = last_use + timedelta(days=COOLDOWN_DAYS)

    if datetime.now() >= next_use:
        return True, None

    remaining = next_use - datetime.now()
    return False, f"Możesz użyć komendy ponownie za **{remaining.days}d {remaining.seconds//3600}h**."


def set_cooldown(user_id):
    data = load_json(COOLDOWN_FILE)
    data[str(user_id)] = datetime.now().isoformat()
    save_json(COOLDOWN_FILE, data)


def losuj_znizke():
    r = random.uniform(0, 100)
    cumulative = 0

    for amount, chance in load_discounts():
        cumulative += chance
        if r <= cumulative:
            return amount

    return None


def generuj_kod(znizka, user_id, username):
    kod = f"ZN{znizka}-" + "".join(
        secrets.choice(string.ascii_uppercase + string.digits)
        for _ in range(6)
    )

    codes = load_json(CODES_FILE)
    codes[kod] = {
        "znizka": znizka,
        "user_id": user_id,
        "username": username,
        "data": datetime.now().isoformat(),
        "uzyty": False
    }

    save_json(CODES_FILE, codes)
    return kod


class ZnizkaView(discord.ui.View):
    def __init__(self, znizka, user_id, username):
        super().__init__(timeout=300)
        self.znizka = znizka
        self.user_id = user_id
        self.username = username
        self.uzyto = False

    @discord.ui.button(label="Użyj zniżki", style=discord.ButtonStyle.green, emoji="🎫")
    async def uzyj(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("To nie Twoja zniżka!", ephemeral=True)

        if self.uzyto:
            return await interaction.response.send_message("Już użyłeś tej zniżki.", ephemeral=True)

        self.uzyto = True
        button.disabled = True
        button.label = "Użyto"
        await interaction.message.edit(view=self)

        kod = generuj_kod(self.znizka, self.user_id, self.username)

        try:
            embed = discord.Embed(
                title="🎫 Twój kod zniżki",
                description=f"**Kod:** `{kod}`\n**Wartość:** **-{self.znizka} zł**",
                color=discord.Color.green()
            )
            embed.set_footer(text="Zachowaj ten kod – jest unikalny")
            await interaction.user.send(embed=embed)

            await interaction.response.send_message(
                f"✅ Kod został wysłany na DM!\n`{kod}`",
                ephemeral=True
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                f"⚠️ Nie mogę wysłać DM.\n`{kod}`",
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
        print(e)


@bot.tree.command(name="znizka", description="Losuj zniżkę raz na tydzień")
async def znizka(interaction: discord.Interaction):
    if interaction.channel_id != ALLOWED_CHANNEL_ID:
        return await interaction.response.send_message(
            f"❌ Komenda działa tylko na <#{ALLOWED_CHANNEL_ID}>",
            ephemeral=True
        )

    ok, msg = can_use(interaction.user.id)
    if not ok:
        return await interaction.response.send_message(msg, ephemeral=True)

    wynik = losuj_znizke()
    set_cooldown(interaction.user.id)

    if wynik is None:
        embed = discord.Embed(
            title="😔 Tym razem się nie udało",
            description="Nie wylosowałeś żadnej zniżki. Spróbuj ponownie za tydzień!",
            color=discord.Color.red()
        )
        return await interaction.response.send_message(embed=embed)

    if wynik == 25:
        color = discord.Color.gold()
        emoji = "🔥"
    elif wynik == 15:
        color = discord.Color.green()
        emoji = "✨"
    else:
        color = discord.Color.blue()
        emoji = "🎫"

    embed = discord.Embed(
        title=f"{emoji} Wylosowałeś zniżkę!",
        description=f"**-{wynik} zł**",
        color=color
    )
    embed.set_footer(text="Kliknij przycisk poniżej, aby odebrać kod.")

    await interaction.response.send_message(
        embed=embed,
        view=ZnizkaView(wynik, interaction.user.id, str(interaction.user))
    )


@bot.tree.command(name="sprawdzkod", description="Sprawdź kod zniżki")
@app_commands.describe(kod="Kod np. ZN5-ABC123")
async def sprawdzkod(interaction: discord.Interaction, kod: str):
    if not (
        interaction.user.guild_permissions.administrator
        or any(r.id == DEVELOPER_ROLE_ID for r in interaction.user.roles)
    ):
        return await interaction.response.send_message(
            "❌ Brak uprawnień.",
            ephemeral=True
        )

    codes = load_json(CODES_FILE)
    kod = kod.upper().strip()

    if kod not in codes:
        return await interaction.response.send_message(
            embed=discord.Embed(
                title="❌ Kod nie istnieje",
                color=discord.Color.red()
            ),
            ephemeral=True
        )

    info = codes[kod]

    embed = discord.Embed(
        title="✅ Kod prawidłowy",
        color=discord.Color.green()
    )
    embed.add_field(name="Zniżka", value=f"**-{info['znizka']} zł**")
    embed.add_field(name="Użytkownik", value=info["username"])
    embed.add_field(
        name="Data",
        value=info["data"][:16].replace("T", " "),
        inline=False
    )

    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="szanse", description="Pokaż szanse na zniżki")
async def szanse(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🎲 Aktualne szanse",
        description=(
            "**72%** → Nic\n"
            "**20%** → -5 zł\n"
            "**7%** → -15 zł\n"
            "**1%** → -25 zł"
        ),
        color=discord.Color.blurple()
    )

    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="edytujszanse", description="Edytuj szanse (tylko właściciel)")
@app_commands.describe(
    procent="Kwota zniżki",
    szansa="Nowa szansa"
)
async def edytujszanse(interaction: discord.Interaction, procent: int, szansa: int):
    if interaction.user.id != interaction.guild.owner_id:
        return await interaction.response.send_message(
            "❌ Tylko właściciel serwera.",
            ephemeral=True
        )

    discounts = load_discounts()
    found = False

    for i, (p, c) in enumerate(discounts):
        if p == procent:
            discounts[i] = (procent, szansa)
            found = True
            break

    if not found:
        discounts.append((procent, szansa))
        discounts.sort(key=lambda x: x[0])

    save_json(DISCOUNTS_FILE, discounts)

    await interaction.response.send_message(
        "✅ Zapisano nowe szanse.",
        ephemeral=True
    )


bot.run(TOKEN)
