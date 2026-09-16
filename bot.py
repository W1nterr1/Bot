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

PRIZES = [
    ("Nic", 72),
    ("-5 zł", 20),
    ("-15 zł", 7),
    ("-25 zł", 1),
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

def losuj_nagrode():
    r = random.uniform(0, 100)
    cumulative = 0
    for nagroda, szansa in PRIZES:
        cumulative += szansa
        if r <= cumulative:
            return nagroda
    return PRIZES[-1][0]

def generuj_kod(nagroda: str, user_id: int, username: str) -> str:
    losowa = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(6))
    kod = f"ZN-{losowa}"
    
    codes = load_json(CODES_FILE)
    codes[kod] = {
        "nagroda": nagroda,
        "user_id": user_id,
        "username": username,
        "data": datetime.now().isoformat(),
        "uzyty": False
    }
    save_json(CODES_FILE, codes)
    
    return kod

def is_admin_or_developer(interaction: discord.Interaction) -> bool:
    if interaction.user.guild_permissions.administrator:
        return True
    role = interaction.guild.get_role(DEVELOPER_ROLE_ID)
    if role and role in interaction.user.roles:
        return True
    return False
    class ZnizkaView(discord.ui.View):
    def __init__(self, nagroda: str, user_id: int, username: str):
        super().__init__(timeout=300)
        self.nagroda = nagroda
        self.user_id = user_id
        self.username = username
        self.uzyto = False

    @discord.ui.button(label="Odbierz nagrodę", style=discord.ButtonStyle.green, emoji="🎁")
    async def odbierz(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("To nie Twoja nagroda!", ephemeral=True)
            return

        if self.uzyto:
            await interaction.response.send_message("Już odebrałeś tę nagrodę.", ephemeral=True)
            return

        self.uzyto = True
        button.disabled = True
        button.label = "Odebrano"
        await interaction.message.edit(view=self)

        if self.nagroda == "Nic":
            await interaction.response.send_message("Tym razem nic nie wygrałeś 😢", ephemeral=True)
            return

        kod = generuj_kod(self.nagroda, self.user_id, self.username)

        try:
            embed_dm = discord.Embed(
                title="🎁 Twoja nagroda!",
                description=f"**Kod:** `{kod}`\n**Nagroda:** **{self.nagroda}**",
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
        synced = await bot.tree.sync()
        print(f"Zsynchronizowano {len(synced)} komend")
    except Exception as e:
        print(f"Błąd sync: {e}")
        @bot.tree.command(name="znizka", description="Losuj nagrodę (raz na tydzień)")
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

    nagroda = losuj_nagrode()
    set_cooldown(interaction.user.id)

    if nagroda == "Nic":
        color = discord.Color.dark_grey()
        emoji = "😢"
    elif nagroda == "-5 zł":
        color = discord.Color.blue()
        emoji = "💙"
    elif nagroda == "-15 zł":
        color = discord.Color.green()
        emoji = "💚"
    else:
        color = discord.Color.gold()
        emoji = "🔥"

    embed = discord.Embed(
        title=f"{emoji} Wylosowałeś!",
        description=f"**{nagroda}**",
        color=color
    )
    
    if nagroda != "Nic":
        embed.set_footer(text="Kliknij przycisk poniżej, żeby otrzymać kod na DM")
        view = ZnizkaView(nagroda, interaction.user.id, str(interaction.user))
        await interaction.response.send_message(embed=embed, view=view)
    else:
        await interaction.response.send_message(embed=embed)

@bot.tree.command(name="nadajznizke", description="Nadaj komuś nagrodę ręcznie (tylko admin)")
@app_commands.describe(
    uzytkownik="Osoba, której nadajesz nagrodę",
    nagroda="Nagroda (np. -5 zł, -15 zł, -25 zł)"
)
@app_commands.checks.has_permissions(administrator=True)
async def nadajznizke(interaction: discord.Interaction, uzytkownik: discord.Member, nagroda: str):
    kod = generuj_kod(nagroda, uzytkownik.id, str(uzytkownik))

    try:
        embed_dm = discord.Embed(
            title="🎁 Otrzymałeś nagrodę!",
            description=f"**Kod:** `{kod}`\n**Nagroda:** **{nagroda}**\nNadane przez administrację",
            color=discord.Color.green()
        )
        await uzytkownik.send(embed=embed_dm)
        await interaction.response.send_message(
            f"✅ Nadano **{nagroda}** użytkownikowi {uzytkownik.mention}\nKod: `{kod}`",
            ephemeral=True
        )
    except discord.Forbidden:
        await interaction.response.send_message(
            f"⚠️ Nie mogę wysłać DM do {uzytkownik.mention}.\nKod: `{kod}`",
            ephemeral=True
        )
        @bot.tree.command(name="sprawdzkod", description="Sprawdź czy kod jest prawdziwy")
@app_commands.describe(kod="Kod do sprawdzenia")
async def sprawdzkod(interaction: discord.Interaction, kod: str):
    if not is_admin_or_developer(interaction):
        await interaction.response.send_message("❌ Nie masz uprawnień do tej komendy.", ephemeral=True)
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
    embed = discord.Embed(title="✅ Kod prawidłowy", color=discord.Color.green())
    embed.add_field(name="Nagroda", value=f"**{info['nagroda']}**", inline=True)
    embed.add_field(name="Wylosował", value=info['username'], inline=True)
    embed.add_field(name="Data", value=info['data'][:16].replace("T", " "), inline=False)
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="szanse", description="Pokaż aktualne szanse")
async def szanse(interaction: discord.Interaction):
    text = "\n".join([f"**{szansa}%** → {nagroda}" for nagroda, szansa in PRIZES])
    embed = discord.Embed(title="🎲 Aktualne szanse", description=text, color=discord.Color.blurple())
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="metody", description="Pokaż dostępne metody płatności")
async def metody(interaction: discord.Interaction):
    embed = discord.Embed(
        title="💳 Metody płatności",
        description="Dostępne metody:",
        color=discord.Color.blue()
    )
    
    embed.add_field(name="<:blik:1549695394101858304> BLIK", value="Płatność BLIK", inline=False)
    embed.add_field(name="<:blik:1549695394101858304> Kod BLIK", value="Kod BLIK", inline=False)
    embed.add_field(name="<:psc:1549694445769728090> PSC", value="Paysafecard", inline=False)
    
    embed.set_footer(text="Po wyborze metody napisz do administracji")
    
    await interaction.response.send_message(embed=embed)

bot.run(TOKEN)
