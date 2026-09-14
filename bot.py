
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
ALLOWED_CHANNEL_ID = 1549047455797084271   # kanał na którym działa /znizka

COOLDOWN_FILE = "cooldowns.json"
CODES_FILE = "codes.json"
DISCOUNTS_FILE = "discounts.json"

DEFAULT_DISCOUNTS = [
    (5, 35),
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
    losowa = "".join(
        secrets.choice(string.ascii_uppercase + string.digits)
        for _ in range(6)
    )
    kod = f"ZN{znizka}-{losowa}"

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
    def __init__(self, znizka: int, user_id: int, username: str):
        super().__init__(timeout=300)
        self.znizka = znizka
        self.user_id = user_id
        self.username = username
        self.uzyto = False

    @discord.ui.button(label="Użyj zniżki", style=discord.ButtonStyle.green, emoji="🎫")
    async def uzyj_znizki(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "To nie Twoja zniżka!",
                ephemeral=True
            )
            return

        if self.uzyto:
            await interaction.response.send_message(
                "Już użyłeś tej zniżki.",
                ephemeral=True
            )
            return

        self.uzyto = True
        button.disabled = True
        button.label = "Użyto"
        await interaction.message.edit(view=self)

        kod = generuj_kod(self.znizka, self.user_id, self.username)

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
    if interaction.channel_id != ALLOWED_CHANNEL_ID:
        await interaction.response.send_message(
            f"❌ Tej komendy można używać tylko na kanale <#{ALLOWED_CHANNEL_ID}>",
            ephemeral=True
        )
        return

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

    view = ZnizkaView(
        znizka_procent,
        interaction.user.id,
        str(interaction.user)
    )

    await interaction.response.send_message(embed=embed, view=view)


@bot.tree.command(name="nadajznizke", description="Nadaj komuś zniżkę ręcznie (tylko admin)")
@app_commands.describe(
    uzytkownik="Osoba, której nadajesz zniżkę",
    procent="Procent zniżki (np. 15)"
)
@app_commands.checks.has_permissions(administrator=True)
async def nadajznizke(interaction: discord.Interaction, uzytkownik: discord.Member, procent: int):
    if procent < 1 or procent > 100:
        await interaction.response.send_message(
            "Procent musi być między 1 a 100.",
            ephemeral=True
        )
        return

    kod = generuj_kod(procent, uzytkownik.id, str(uzytkownik))

    try:
        embed_dm = discord.Embed(
            title="🎫 Otrzymałeś zniżkę!",
            description=f"**Kod:** `{kod}`\n**Wartość:** **{procent}%**\nNadane przez administrację",
            color=discord.Color.green()
        )

        await uzytkownik.send(embed=embed_dm)

        await interaction.response.send_message(
            f"✅ Nadano **{procent}%** zniżki użytkownikowi {uzytkownik.mention}\nKod: `{kod}`",
            ephemeral=True
        )

    except discord.Forbidden:
        await interaction.response.send_message(
            f"⚠️ Nie mogę wysłać DM do {uzytkownik.mention}.\nKod: `{kod}`",
            ephemeral=True
        )


@bot.tree.command(name="sprawdzkod", description="Sprawdź czy kod zniżki jest prawdziwy (admin lub deweloper)")
@app_commands.describe(kod="Kod do sprawdzenia np. ZN15-ABC123")
async def sprawdzkod(interaction: discord.Interaction, kod: str):
    if not (
        interaction.user.guild_permissions.administrator
        or any(role.id == DEVELOPER_ROLE_ID for role in interaction.user.roles)
    ):
        await interaction.response.send_message(
            "❌ Tylko administrator lub deweloper może używać tej komendy.",
            ephemeral=True
        )
        return

    codes = load_json(CODES_FILE)
    kod = kod.upper().strip()

    if kod not in codes:
        embed = discord.Embed(
            title="❌ Kod nieprawidłowy",
            description=f"Kod `{kod}` nie istnieje w systemie.",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    info = codes[kod]

    embed = discord.Embed(
        title="✅ Kod prawidłowy",
        color=discord.Color.green()
    )
    embed.add_field(
        name="Zniżka",
        value=f"**{info['znizka']}%**",
        inline=True
    )
    embed.add_field(
        name="Wylosował",
        value=info["username"],
        inline=True
    )
    embed.add_field(
        name="Data",
        value=info["data"][:16].replace("T", " "),
        inline=False
    )

    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="szanse", description="Pokaż aktualne szanse na zniżki")
async def szanse(interaction: discord.Interaction):
    discounts = load_discounts()
    text = "\n".join(
        [f"**{p}%** → `{c}%` szans" for p, c in discounts]
    )

    embed = discord.Embed(
        title="Aktualne szanse dropu",
        description=text,
        color=discord.Color.blurple()
    )

    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="edytujszanse", description="Zmień szansę na konkretną zniżkę (tylko właściciel serwera)")
@app_commands.describe(
    procent="Procent zniżki (np. 15)",
    szansa="Nowa szansa w % (np. 25)"
)
async def edytujszanse(interaction: discord.Interaction, procent: int, szansa: int):
    if interaction.user.id != interaction.guild.owner_id:
        await interaction.response.send_message(
            "❌ Tylko właściciel serwera może tego używać.",
            ephemeral=True
        )
        return

    if szansa < 0 or szansa > 100:
        await interaction.response.send_message(
            "Szansa musi być między 0 a 100.",
            ephemeral=True
        )
        return

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

    total = sum(c for _, c in discounts)

    if total != 100:
        await interaction.response.send_message(
            f"⚠️ Zapisano, ale suma szans wynosi teraz **{total}%** (powinno być 100%).",
            ephemeral=True
        )
    else:
        await interaction.response.send_message(
            f"✅ Ustawiono **{procent}%** zniżki na **{szansa}%** szans.",
            ephemeral=True
        )

    save_json(DISCOUNTS_FILE, discounts)


bot.run(TOKEN)
