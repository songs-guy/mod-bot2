import discord
from discord import app_commands
from discord.ext import commands
import datetime 
import os
import asyncio
import random
import re
import logging
import time
from collections import defaultdict
from threading import Thread
from flask import Flask, request
from supabase import create_client, Client

# ----- Logging Setup -----
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('discord_bot')

# ----- Flask Server for Render -----
app = Flask('')

# Storage for Recent Logs on the Webpage
recent_logs = []

@app.route('/')
def home():
    # Creating the HTML Dashboard - Clean, ID-free, with Embed Presets
    log_html = "".join([f"<li style='margin-bottom:12px; border-bottom: 1px solid #4f545c; padding-bottom: 8px;'><b>{l['user']}:</b> {l['content']} <br><small style='color:gray;'>🕒 {l['time']}</small></li>" for l in recent_logs])
    
    # Generate Member Presets
    members_string = "".join([f"<option value='{m.id}'>{m.name}</option>" for g in bot.guilds for m in g.members if not m.bot])

    # Generate Channel Presets
    channels_string = "".join([f"<option value='{c.id}'>#{c.name}</option>" for g in bot.guilds for c in g.text_channels])

    return f'''
    <html>
        <head>
            <title>Bot Master Console Pro</title>
            <style>
                body {{ 
                    background-color: #23272a; 
                    color: white; 
                    font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; 
                    display: flex; 
                    flex-direction: row; 
                    justify-content: center; 
                    align-items: flex-start;
                    gap: 50px; 
                    padding: 80px; 
                    margin: 0;
                }}
                .card {{ 
                    background: #2c2f33; 
                    padding: 55px; 
                    border-radius: 25px; 
                    border: 2px solid #7289da; 
                    width: 900px; 
                    box-shadow: 0 15px 40px rgba(0,0,0,0.6);
                }}
                .log-card {{ 
                    background: #2c2f33; 
                    padding: 40px; 
                    border-radius: 25px; 
                    border: 2px solid #43b581; 
                    width: 600px;  
                    height: 1100px; 
                    overflow-y: auto; 
                }}
                input, select, textarea {{ 
                    width: 100%; 
                    padding: 22px; 
                    margin-top: 15px; 
                    border-radius: 12px; 
                    border: 2px solid #4f545c; 
                    background: #40444b; 
                    color: white; 
                    box-sizing: border-box; 
                    font-size: 1.15em;
                    transition: all 0.3s;
                }}
                input:focus, select:focus, textarea:focus {{
                    border-color: #7289da;
                    background: #4f545c;
                    outline: none;
                    box-shadow: 0 0 10px rgba(114, 137, 218, 0.2);
                }}
                label {{ 
                    font-size: 1.1em; 
                    color: #7289da; 
                    font-weight: bold; 
                    margin-top: 35px; 
                    display: flex; 
                    align-items: center;
                    gap: 10px;
                    text-transform: uppercase;
                    letter-spacing: 1.5px;
                }}
                button {{ 
                    background: #43b581; 
                    color: white; 
                    border: none; 
                    padding: 30px; 
                    border-radius: 15px; 
                    cursor: pointer; 
                    font-weight: 900; 
                    width: 100%; 
                    margin-top: 50px; 
                    font-size: 1.6em; 
                    text-transform: uppercase;
                    box-shadow: 0 6px 20px rgba(67, 181, 129, 0.4);
                    transition: all 0.2s;
                }}
                button:hover {{ background: #3ca374; transform: translateY(-3px); box-shadow: 0 8px 25px rgba(67, 181, 129, 0.5); }}
                button:active {{ transform: translateY(1px); }}
                .embed-section {{ 
                    border-top: 3px solid #4f545c; 
                    margin-top: 45px; 
                    padding-top: 40px; 
                }}
                textarea {{ 
                    min-height: 300px; 
                    resize: vertical; 
                    line-height: 1.6;
                }}
                h2 {{ font-size: 3em; margin-bottom: 40px; color: white; text-shadow: 2px 2px 4px rgba(0,0,0,0.3); }}
                h3 {{ font-size: 2.2em; margin-bottom: 25px; }}
                .icon {{ font-style: normal; font-size: 1.3em; }}
            </style>
        </head>
        <body>
            <div class="card">
                <h2 style="text-align:center; margin-top:0;">🌐 Bot Command Pro</h2>
                <form action="/execute" method="post">
                    <label><i class="icon">🔑</i> Dashboard Password</label>
                    <input type="password" name="pwd" placeholder="Enter secure admin password...">
                    
                    <label><i class="icon">📺</i> Target Channel</label>
                    <select name="channel_preset">
                        <option value="">-- Click to Select Channel --</option>
                        {channels_string}
                    </select>

                    <label><i class="icon">👤</i> Target Member</label>
                    <select name="member_target">
                        <option value="">-- Click to Select Member --</option>
                        {members_string}
                    </select>
                    
                    <label><i class="icon">⚡</i> System Action</label>
                    <select name="action" style="background: #7289da; font-weight: bold; border-color: #7289da;">
                        <option value="say">💬 Plain Text Message</option>
                        <option value="embed">🎨 Custom Rich Embed</option>
                        <option value="image">🖼️ Quick Image Post</option>
                        <option value="dm">📧 DM User</option>
                        <option value="kick">👢 Kick User</option>
                        <option value="ban">🔨 Ban User</option>
                        <option value="warn">⚠️ Warn User</option>
                        <option value="purge">🧹 Purge Channel</option>
                    </select>
                    
                    <div class="embed-section">
                        <h4 style="color: #b9bbbe; margin: 0 0 20px 0; text-transform: uppercase;">Embed Configuration</h4>
                        
                        <label><i class="icon">📌</i> Embed Title</label>
                        <input type="text" name="eb_title" placeholder="Announcement Header...">
                        
                        <label><i class="icon">🌈</i> Accent Color (HEX)</label>
                        <input type="text" name="eb_color" placeholder="#7289da">
                        
                        <label><i class="icon">📝</i> Content Body</label>
                        <textarea name="payload" placeholder="Type your full message or detailed embed description here..."></textarea>
                        
                        <label><i class="icon">🖼️</i> Image URL</label>
                        <input type="text" name="eb_image" placeholder="https://example.com/image.png">
                    </div>

                    <button type="submit">🚀 Execute Bot Command</button>
                </form>
            </div>

            <div class="log-card">
                <h3 style="color: #43b581; margin-top: 0; position: sticky; top: 0; background: #2c2f33; padding: 20px 0; z-index: 10;">📡 Live Activity Stream</h3>
                <ul style="list-style: none; padding: 0; font-size: 1.2em;">
                    {log_html if log_html else "<li style='color: #72767d;'>System idle. Waiting for logs...</li>"}
                </ul>
            </div>
        </body>
    </html>
    '''

@app.route('/execute', methods=['POST'])
def execute():
    typed_pwd = request.form.get('pwd')
    channel_preset = request.form.get('channel_preset')
    member_target = request.form.get('member_target')
    action = request.form.get('action')
    payload = request.form.get('payload')
    
    eb_title = request.form.get('eb_title')
    eb_color_str = request.form.get('eb_color', '#7289da')
    eb_image = request.form.get('eb_image')

    actual_pwd = os.getenv("DASHBOARD_PWD", "admin")

    # Selection Logic based on Action
    final_target = channel_preset if action in ["say", "embed", "image", "purge"] else member_target

    if typed_pwd != actual_pwd: return "❌ Access Denied. <a href='/'>Back</a>"
    if not final_target: return "⚠️ Error: Please select a target from the dropdowns. <a href='/'>Back</a>"

    try:
        if action == "embed":
            channel = bot.get_channel(int(final_target))
            color_value = int(eb_color_str.lstrip('#'), 16) if eb_color_str.startswith('#') else 0x7289da
            embed = discord.Embed(title=eb_title, description=payload, color=color_value)
            if eb_image: embed.set_image(url=eb_image)
            bot.loop.create_task(channel.send(embed=embed))
            return f"✅ Embed sent to #{channel.name}. <a href='/'>Back</a>"

        if action == "say":
            channel = bot.get_channel(int(final_target))
            bot.loop.create_task(channel.send(payload))
            return f"✅ Message sent. <a href='/'>Back</a>"

        if action == "image":
            channel = bot.get_channel(int(final_target))
            embed = discord.Embed().set_image(url=payload)
            bot.loop.create_task(channel.send(payload, embed=embed))
            return f"✅ Image sent. <a href='/'>Back</a>"

        if action == "dm":
            user = bot.get_user(int(final_target))
            if user:
                bot.loop.create_task(user.send(payload))
                return f"✅ DM sent to {user.name}. <a href='/'>Back</a>"

        if action == "kick":
            for g in bot.guilds:
                m = g.get_member(int(final_target))
                if m: bot.loop.create_task(m.kick(reason=payload)); return f"✅ Kicked {m.name}. <a href='/'>Back</a>"
        if action == "ban":
            for g in bot.guilds:
                m = g.get_member(int(final_target))
                if m: bot.loop.create_task(m.ban(reason=payload)); return f"✅ Banned {m.name}. <a href='/'>Back</a>"
        if action == "purge":
            channel = bot.get_channel(int(final_target))
            bot.loop.create_task(channel.purge(limit=int(payload)))
            return f"✅ Purged {payload} messages. <a href='/'>Back</a>"
        if action == "warn" and supabase:
            data = {"guild_id": "Web", "user_id": final_target, "reason": payload, "moderator": "Web-Admin", "created_at": datetime.datetime.utcnow().isoformat()}
            supabase.table("warnings").insert(data).execute()
            return f"✅ Warning logged. <a href='/'>Back</a>"

        return "❌ Action failed. <a href='/'>Back</a>"
    except Exception as e:
        return f"❌ Handshake Error: {e} <a href='/'>Back</a>"

def run(): 
    app.run(host='0.0.0.0', port=8080)

def keep_alive(): 
    Thread(target=run).start()

# ----- Configuration -----
TOKEN = os.getenv("DISCORD_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL") 
SUPA_URL = os.getenv("SUPABASE_URL")
SUPA_KEY = os.getenv("SUPABASE_KEY")

# --- Swear Filter List ---
SWEAR_WORDS = ["badword1", "badword2", "badword3"] 
MUTED_ROLE_NAME = "Muted"
VERIFIED_ROLE_NAME = "Member"
UNVERIFIED_ROLE_NAME = "Unverified"
MIN_ACCOUNT_AGE_DAYS = 1

# Initialize Supabase
supabase = None
if SUPA_URL and SUPA_KEY:
    try:
        supabase = create_client(SUPA_URL, SUPA_KEY)
        logger.info("✅ Supabase connection initialized.")
    except Exception as e:
        logger.error(f"❌ Supabase failed: {e}")

intents = discord.Intents.all()
user_message_logs = defaultdict(list)

# ----- Captcha Modal Logic -----

class CaptchaModal(discord.ui.Modal, title="Security Verification"):
    def __init__(self, answer: int):
        super().__init__()
        self.answer = answer
        self.user_answer = discord.ui.TextInput(
            label=f"Anti-Bot: What is {answer - 7} + 7?",
            placeholder="Type the result here...",
            min_length=1,
            max_length=3,
            required=True
        )
        self.add_item(self.user_answer)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            if self.user_answer.value == str(self.answer):
                verified_role = discord.utils.get(interaction.guild.roles, name=VERIFIED_ROLE_NAME)
                unverified_role = discord.utils.get(interaction.guild.roles, name=UNVERIFIED_ROLE_NAME)

                if verified_role:
                    await interaction.user.add_roles(verified_role)
                if unverified_role and unverified_role in interaction.user.roles:
                    await interaction.user.remove_roles(unverified_role)
                
                await interaction.response.send_message("✅ Success! You are verified.", ephemeral=True)
                send_to_webhook("🛡️ Verification Success", f"User: {interaction.user.mention}", discord.Color.green(), interaction.user)
            else:
                await interaction.response.send_message("❌ Incorrect answer. Try again.", ephemeral=True)
        except Exception as e:
            logger.error(f"Captcha Error: {e}")

class VerifyView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Verify Identity", style=discord.ButtonStyle.blurple, custom_id="verify_persistent", emoji="🛡️")
    async def verify_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_age = (discord.utils.utcnow() - interaction.user.created_at).days
        if user_age < MIN_ACCOUNT_AGE_DAYS:
            await interaction.response.send_message(f"❌ Account too new. Need {MIN_ACCOUNT_AGE_DAYS} day(s).", ephemeral=True)
            return

        answer = random.randint(11, 60)
        await interaction.response.send_modal(CaptchaModal(answer))

# ----- Helper Functions -----

def send_to_webhook(title, description, color, member=None):
    if not WEBHOOK_URL: return
    try:
        webhook = discord.SyncWebhook.from_url(WEBHOOK_URL)
        embed = discord.Embed(title=title, description=description, color=color, timestamp=discord.utils.utcnow())
        if member: embed.set_footer(text=f"Member ID: {member.id}")
        webhook.send(embed=embed)
    except Exception as e:
        logger.error(f"Webhook Failure: {e}")

async def ensure_muted_role(guild):
    role = discord.utils.get(guild.roles, name=MUTED_ROLE_NAME)
    if not role:
        try:
            role = await guild.create_role(name=MUTED_ROLE_NAME, reason="Auto-Mod Mute Role")
            for channel in guild.channels:
                await channel.set_permissions(role, send_messages=False, add_reactions=False)
        except: pass
    return role

# ----- Bot Class -----

class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        self.add_view(VerifyView())
        await self.tree.sync()
        logger.info("Slash commands synced.")

bot = MyBot()

# ----- Global Events -----

@bot.event
async def on_ready():
    logger.info(f"✅ Bot Ready: {bot.user}")

@bot.event
async def on_message(message):
    if message.author.bot or not message.guild: return

    # Adding to Web Dashboard Logs
    timestamp = datetime.datetime.now().strftime("%H:%M:%S")
    recent_logs.insert(0, {"user": message.author.name, "content": message.content[:50], "time": timestamp})
    if len(recent_logs) > 15: recent_logs.pop()

    # --- Swear Filter Execution ---
    if any(word.lower() in message.content.lower() for word in SWEAR_WORDS):
        await message.delete()
        send_to_webhook("🚫 Filtered", f"User: {message.author.mention}\nMsg: {message.content}", discord.Color.red(), message.author)
        return

    # Anti-Spam
    now = datetime.datetime.utcnow()
    user_message_logs[message.author.id].append(now)
    user_message_logs[message.author.id] = [t for t in user_message_logs[message.author.id] if (now - t).total_seconds() < 5]

    if len(user_message_logs[message.author.id]) >= 5:
        mute_role = await ensure_muted_role(message.guild)
        if mute_role and mute_role not in message.author.roles:
            await message.author.add_roles(mute_role)
            await message.channel.send(f"🔇 {message.author.mention} auto-muted for spamming.")
            await asyncio.sleep(60)
            await message.author.remove_roles(mute_role)
        return

    await bot.process_commands(message)

# ----- Moderation Slash Commands -----

@bot.tree.command(name="purge", description="Delete a specified number of messages")
@app_commands.checks.has_permissions(manage_messages=True)
async def purge(interaction: discord.Interaction, amount: int):
    await interaction.response.defer(ephemeral=True)
    try:
        deleted = await interaction.channel.purge(limit=amount)
        await interaction.followup.send(f"Successfully deleted {len(deleted)} messages.")
        send_to_webhook("Purge Executed", f"Moderator: {interaction.user.mention}\nAmount: {len(deleted)}\nChannel: {interaction.channel.mention}", discord.Color.blue())
    except Exception as e:
        await interaction.followup.send(f"Error: {e}")

@bot.tree.command(name="warn", description="Issue a permanent warning")
@app_commands.checks.has_permissions(manage_messages=True)
async def warn(interaction: discord.Interaction, member: discord.Member, reason: str):
    if not supabase: return await interaction.response.send_message("DB not connected.", ephemeral=True)
    
    data = {
        "guild_id": str(interaction.guild.id),
        "user_id": str(member.id),
        "reason": reason,
        "moderator": interaction.user.name,
        "created_at": datetime.datetime.utcnow().isoformat()
    }
    
    try:
        supabase.table("warnings").insert(data).execute()
        await interaction.response.send_message(f"Warned **{member.display_name}** for: `{reason}`")
        send_to_webhook("Warned", f"User: {member.mention}\nMod: {interaction.user.mention}\nReason: {reason}", discord.Color.gold(), member)
    except Exception as e:
        await interaction.response.send_message(f"DB Error: {e}", ephemeral=True)

@bot.tree.command(name="warnings", description="View a member's warning history")
async def warnings(interaction: discord.Interaction, member: discord.Member):
    if not supabase: return await interaction.response.send_message("DB error.", ephemeral=True)
    try:
        response = supabase.table("warnings").select("*").eq("user_id", str(member.id)).execute()
        user_warns = response.data
        if not user_warns:
            return await interaction.response.send_message(f"{member.display_name} has a clean record.")
        embed = discord.Embed(title=f"Record: {member.display_name}", color=discord.Color.orange())
        for w in user_warns:
            date = w['created_at'].split("T")[0]
            embed.add_field(name=f"Date: {date}", value=f"Reason: {w['reason']}\nBy: {w['moderator']}", inline=False)
        await interaction.response.send_message(embed=embed)
    except Exception as e:
        await interaction.response.send_message(f"Error: {e}")

@bot.tree.command(name="kick", description="Kick a member")
@app_commands.checks.has_permissions(kick_members=True)
async def kick(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
    await member.kick(reason=reason)
    await interaction.response.send_message(f"Kicked {member.display_name}")

@bot.tree.command(name="ban", description="Ban a member")
@app_commands.checks.has_permissions(ban_members=True)
async def ban(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
    await member.ban(reason=reason)
    await interaction.response.send_message(f"Banned {member.display_name}")

@bot.tree.command(name="slowmode", description="Set channel slowmode")
@app_commands.checks.has_permissions(manage_channels=True)
async def slowmode(interaction: discord.Interaction, seconds: int):
    await interaction.channel.edit(slowmode_delay=seconds)
    await interaction.response.send_message(f"Slowmode set to {seconds} seconds.")

@bot.tree.command(name="setup_verify", description="Deploy the verification portal")
@app_commands.checks.has_permissions(administrator=True)
async def setup_verify(interaction: discord.Interaction):
    embed = discord.Embed(title="🛡️ Security Verification", description="Click the button below to verify.", color=discord.Color.blue())
    await interaction.channel.send(embed=embed, view=VerifyView())
    await interaction.response.send_message("Portal deployed.", ephemeral=True)

@bot.command()
@commands.has_permissions(administrator=True)
async def sync(ctx):
    await bot.tree.sync()
    await ctx.send("Commands synced!")

if __name__ == "__main__":
    keep_alive()
    if TOKEN:
        bot.run(TOKEN)
