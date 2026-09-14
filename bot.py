import discord
from discord import app_commands
from discord.ext import commands
import random, json, os, string, secrets
from datetime import datetime, timedelta

TOKEN = os.getenv("TOKEN")
GUILD_ID = None
DEVELOPER_ROLE_ID = 1549047984506019870
COOLDOWN_DAYS = 7
ALLOWED_CHANNEL_ID = 1549047455797084271

COOLDOWN_FILE="cooldowns.json"
CODES_FILE="codes.json"
DISCOUNTS_FILE="discounts.json"

DEFAULT_DISCOUNTS=[(5,20),(15,10),(25,2)]

intents=discord.Intents.default()
intents.message_content=True
bot=commands.Bot(command_prefix="!", intents=intents)

def load_json(f):
    if os.path.exists(f):
        with open(f,"r",encoding="utf-8") as x:return json.load(x)
    return {}

def save_json(f,d):
    with open(f,"w",encoding="utf-8") as x:json.dump(d,x,indent=2)

def load_discounts():
    d=load_json(DISCOUNTS_FILE)
    if not d:
        save_json(DISCOUNTS_FILE,DEFAULT_DISCOUNTS)
        return DEFAULT_DISCOUNTS
    return d

def can_use(uid):
    d=load_json(COOLDOWN_FILE); uid=str(uid)
    if uid not in d:return True,None
    nxt=datetime.fromisoformat(d[uid])+timedelta(days=COOLDOWN_DAYS)
    if datetime.now()>=nxt:return True,None
    rem=nxt-datetime.now()
    return False,f"MoÅ¼esz uÅ¼yÄ komendy ponownie za **{rem.days}d {rem.seconds//3600}h**."

def set_cooldown(uid):
    d=load_json(COOLDOWN_FILE); d[str(uid)]=datetime.now().isoformat(); save_json(COOLDOWN_FILE,d)

def losuj_znizke():
    r=random.uniform(0,100); c=0
    for a,s in load_discounts():
        c+=s
        if r<=c:return a
    return None

def generuj_kod(z,uid,name):
    kod=f"ZN{z}-"+''.join(secrets.choice(string.ascii_uppercase+string.digits) for _ in range(6))
    d=load_json(CODES_FILE)
    d[kod]={"znizka":z,"user_id":uid,"username":name,"data":datetime.now().isoformat(),"uzyty":False}
    save_json(CODES_FILE,d); return kod

class ZnizkaView(discord.ui.View):
    def __init__(self,z,uid,name):
        super().__init__(timeout=300); self.z=z; self.uid=uid; self.name=name; self.used=False
    @discord.ui.button(label="UÅ¼yj zniÅ¼ki",style=discord.ButtonStyle.green,emoji="ð«")
    async def use(self,i,b):
        if i.user.id!=self.uid:return await i.response.send_message("To nie Twoja zniÅ¼ka!",ephemeral=True)
        if self.used:return await i.response.send_message("JuÅ¼ uÅ¼yÅeÅ tej zniÅ¼ki.",ephemeral=True)
        self.used=True; b.disabled=True; b.label="UÅ¼yto"; await i.message.edit(view=self)
        kod=generuj_kod(self.z,self.uid,self.name)
        try:
            e=discord.Embed(title="ð« TwÃ³j kod zniÅ¼ki",description=f"**Kod:** `{kod}`\n**WartoÅÄ:** **-{self.z} zÅ**",color=discord.Color.green())
            e.set_footer(text="Zachowaj ten kod â jest unikalny")
            await i.user.send(embed=e)
            await i.response.send_message(f"â Kod zostaÅ wysÅany na DM!\n`{kod}`",ephemeral=True)
        except discord.Forbidden:
            await i.response.send_message(f"â ï¸ Nie mogÄ wysÅaÄ DM.\n`{kod}`",ephemeral=True)

@bot.event
async def on_ready():
    print(f"Zalogowano jako {bot.user}")
    if GUILD_ID: await bot.tree.sync(guild=discord.Object(id=GUILD_ID))
    else: await bot.tree.sync()

@bot.tree.command(name="znizka",description="Losuj zniÅ¼kÄ raz na tydzieÅ")
async def znizka(i:discord.Interaction):
    if i.channel_id!=ALLOWED_CHANNEL_ID:
        return await i.response.send_message(f"â Komenda dziaÅa tylko na <#{ALLOWED_CHANNEL_ID}>",ephemeral=True)
    ok,msg=can_use(i.user.id)
    if not ok:return await i.response.send_message(msg,ephemeral=True)
    z=losuj_znizke(); set_cooldown(i.user.id)
    if z is None:
        e=discord.Embed(title="ð Tym razem siÄ nie udaÅo",description="Nie wylosowaÅeÅ Å¼adnej zniÅ¼ki. SprÃ³buj ponownie za tydzieÅ!",color=discord.Color.red())
        return await i.response.send_message(embed=e)
    color=discord.Color.gold() if z==25 else discord.Color.green() if z==15 else discord.Color.blue()
    emoji="ð¥" if z==25 else "â¨" if z==15 else "ð«"
    e=discord.Embed(title=f"{emoji} WylosowaÅeÅ zniÅ¼kÄ!",description=f"**-{z} zÅ**",color=color)
    e.set_footer(text="Kliknij przycisk poniÅ¼ej, aby odebraÄ kod.")
    await i.response.send_message(embed=e,view=ZnizkaView(z,i.user.id,str(i.user)))

@bot.tree.command(name="sprawdzkod",description="SprawdÅº kod zniÅ¼ki")
@app_commands.describe(kod="Kod np. ZN5-ABC123")
async def sprawdzkod(i:discord.Interaction,kod:str):
    if not(i.user.guild_permissions.administrator or any(r.id==DEVELOPER_ROLE_ID for r in i.user.roles)):
        return await i.response.send_message("â Brak uprawnieÅ.",ephemeral=True)
    d=load_json(CODES_FILE); kod=kod.upper().strip()
    if kod not in d:
        return await i.response.send_message(embed=discord.Embed(title="â Kod nie istnieje",color=discord.Color.red()),ephemeral=True)
    info=d[kod]
    e=discord.Embed(title="â Kod prawidÅowy",color=discord.Color.green())
    e.add_field(name="ZniÅ¼ka",value=f"-{info['znizka']} zÅ")
    e.add_field(name="UÅ¼ytkownik",value=info["username"])
    e.add_field(name="Data",value=info["data"][:16].replace("T"," "),inline=False)
    await i.response.send_message(embed=e,ephemeral=True)

@bot.tree.command(name="szanse",description="PokaÅ¼ szanse")
async def szanse(i:discord.Interaction):
    txt="68% â Nic\n20% â -5 zÅ\n10% â -15 zÅ\n2% â -25 zÅ"
    await i.response.send_message(embed=discord.Embed(title="ð² Aktualne szanse",description=txt,color=discord.Color.blurple()))

@bot.tree.command(name="edytujszanse",description="Edytuj szanse")
@app_commands.describe(procent="Kwota",szansa="Nowa szansa")
async def edytujszanse(i:discord.Interaction,procent:int,szansa:int):
    if i.user.id!=i.guild.owner_id:
        return await i.response.send_message("â Tylko wÅaÅciciel.",ephemeral=True)
    d=load_discounts(); found=False
    for x,(p,c) in enumerate(d):
        if p==procent:d[x]=(procent,szansa); found=True
    if not found:d.append((procent,szansa))
    save_json(DISCOUNTS_FILE,d)
    await i.response.send_message("â Zapisano.",ephemeral=True)

bot.run(TOKEN)
