import discord
from discord import app_commands
from discord.ext import commands
import datetime 
import os
import asyncio
import random
import re
from collections import defaultdict
from threading import Thread
from flask import Flask

# ----- Render Keep-Alive Server -----
app = Flask('')

@app.route('/')
def home(): 
    return "Ultra-Security Moderation Bot is Online"

def run(): 
    app.run(host='0.0.0.0', port=8080)

def keep_alive(): 
    Thread(target=run).start()

# ----- Configuration -----
TOKEN = os.getenv("DISCORD_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL") 
SWEAR_WORDS = ["badword1", "badword2", "badword3"] 
MUTED_ROLE_NAME = "Muted"
VERIFIED_ROLE_NAME = "Member"
UNVERIFIED_ROLE_NAME = "Unverified"
MIN_ACCOUNT_AGE_DAYS = 1

intents = discord.Intents.default()
intents.members = True 
intents.message_content = True 
intents.guilds = True

# Data Tracking for Anti-Raid
user_message_logs = defaultdict(list)
log_config = {
    "messageDelete": True,
    "messageEdit": True,
    "guildMemberAdd": True,
    "guildMemberRemove": True
}

# ----- Captcha Modal System -----

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
        if self.user_answer.value == str(self.answer):
            verified_role = discord.utils.get(interaction.guild.roles, name=VERIFIED_ROLE_NAME)
            unverified_role = discord.utils.get(interaction.guild.roles, name=UNVERIFIED_ROLE_NAME)

            if not verified_role:
                try:
                    verified_role = await interaction.guild.create_role(name=VERIFIED_ROLE_NAME, reason="Verification Role")
                except discord.Forbidden:
                    await interaction.response.send_message("❌ Error: I don't have permission to create roles.", ephemeral=True)
                    return

            await interaction.user.add_roles(verified_role)
            if unverified_role and unverified_role in interaction.user.roles:
                await interaction.user.remove_roles(unverified_role)
            
            await interaction.response.send_message("✅ Success! You have passed the captcha and gain full access.", ephemeral=True)
            send_to_webhook("🛡️ Verification Success", f"User: {interaction.user.mention}\nMethod: Math Captcha", discord.Color.green(), interaction.user)
        else:
            await interaction.response.send_message("❌ Incorrect answer. Please try again.", ephemeral=True)

class VerifyView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Verify Identity", style=discord.ButtonStyle.blurple, custom_id="verify_persistent", emoji="🛡️")
    async def verify_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_age = (discord.utils.utcnow() - interaction.user.created_at).days
        if user_age < MIN_ACCOUNT_AGE_DAYS:
            await interaction.response.send_message(f"❌ Security Alert: Your account is too new. Minimum age: {MIN_ACCOUNT_AGE_DAYS} day(s).", ephemeral=True)
            return

        answer = random.randint(11, 60)
        await interaction.response.send_modal(CaptchaModal(answer))

# ----- Bot Core Class -----

class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        self.add_view(VerifyView())
        await self.tree.sync()
        print(f"[{datetime.datetime.now()}] Slash commands and UI views synced.")

bot = MyBot()

# ----- Logging & Webhook System -----

def send_to_webhook(title, description, color, member=None):
    if not WEBHOOK_URL:
        return
    try:
        webhook = discord.SyncWebhook.from_url(WEBHOOK_URL)
        embed = discord.Embed(
            title=title, 
            description=description, 
            color=color, 
            timestamp=discord.utils.utcnow()
        )
        if member:
            embed.set_footer(text=f"Member ID: {member.id}", icon_url=member.display_avatar.url if member.display_avatar else None)
        webhook.send(embed=embed)
    except Exception as e:
        print(f"Webhook Failure: {e}")

# ----- Moderation Helper Functions -----

async def ensure_muted_role(guild):
    role = discord.utils.get(guild.roles, name=MUTED_ROLE_NAME)
    if not role:
        try:
            role = await guild.create_role(name=MUTED_ROLE_NAME, reason="Auto-Moderation Mute Role")
            for channel in guild.channels:
                await channel.set_permissions(role, send_messages=False, add_reactions=False, speak=False)
        except discord.Forbidden:
            print(f"Cannot create Mute role in {guild.name}")
    return role

# ----- Global Security Events -----

@bot.event
async def on_message(message):
    if message.author.bot or not message.guild:
        return

    # 1. Swear Filter
    content_lower = message.content.lower()
    if any(word.lower() in content_lower for word in SWEAR_WORDS):
        await message.delete()
        await message.channel.send(f"⚠️ {message.author.mention}, that language is not permitted here.", delete_after=5)
        send_to_webhook("🚫 Content Filtered", f"User: {message.author.mention}\nChannel: {message.channel.mention}\nMessage: {message.content}", discord.Color.red(), message.author)
        return

    # 2. Anti-Raid / Spam Detection Logic
    now = datetime.datetime.utcnow()
    user_message_logs[message.author.id].append(now)
    user_message_logs[message.author.id] = [t for t in user_message_logs[message.author.id] if (now - t).total_seconds() < 5]

    if len(user_message_logs[message.author.id]) >= 5:
        mute_role = await ensure_muted_role(message.guild)
        if mute_role and mute_role not in message.author.roles:
            await message.author.add_roles(mute_role)
            await message.channel.send(f"🔇 {message.author.mention} auto-muted for 60s (Spam Detection).")
            send_to_webhook("🔇 Auto-Mute", f"User: {message.author.mention}\nReason: Rapid message spam.", discord.Color.dark_red(), message.author)
            await asyncio.sleep(60)
            await message.author.remove_roles(mute_role)
        return

    await bot.process_commands(message)

@bot.event
async def on_message_delete(message):
    if not log_config["messageDelete"] or message.author.bot: return
    
    # 3. Ghost Ping Detection
    mention_pattern = r'<@!?([0-9]+)>|<@&([0-9]+)>'
    has_mention = re.search(mention_pattern, message.content)
    
    if has_mention:
        send_to_webhook(
            "👻 Ghost Ping Detected", 
            f"User: {message.author.mention}\nChannel: {message.channel.mention}\n**Deleted Content:** {message.content}", 
            discord.Color.yellow(), 
            message.author
        )
    else:
        send_to_webhook("🗑️ Message Deleted", f"User: {message.author.mention}\nChannel: {message.channel.mention}\nContent: {message.content or '[No text content]'}", discord.Color.red(), message.author)

@bot.event
async def on_message_edit(before, after):
    if not log_config["messageEdit"] or before.author.bot or before.content == after.content: return
    send_to_webhook("✏️ Message Edited", f"User: {before.author.mention}\nChannel: {before.channel.mention}\n**Old:** {before.content}\n**New:** {after.content}", discord.Color.orange(), before.author)

@bot.event
async def on_member_join(member):
    unverified_role = discord.utils.get(member.guild.roles, name=UNVERIFIED_ROLE_NAME)
    if not unverified_role:
        try:
            unverified_role = await member.guild.create_role(name=UNVERIFIED_ROLE_NAME, reason="Verification Requirement")
        except: pass
    
    if unverified_role:
        await member.add_roles(unverified_role)
    
    send_to_webhook("👋 New Member", f"{member.mention} has joined.\nAccount Age: {(discord.utils.utcnow() - member.created_at).days} days.", discord.Color.blue(), member)

# ----- Moderation Slash Commands -----

@bot.tree.command(name="setup_verify", description="Deploy the verification portal")
@app_commands.checks.has_permissions(administrator=True)
async def setup_verify(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🔒 Server Security Portal",
        description=(
            "Welcome! To prevent bot raids, we require all new members to verify.\n\n"
            "**Instructions:**\n"
            "1. Click the button below.\n"
            "2. Solve the math problem in the popup.\n"
            "3. Gain instant access to the server."
        ),
        color=discord.Color.from_rgb(46, 204, 113)
    )
    await interaction.channel.send(embed=embed, view=VerifyView())
    await interaction.response.send_message("✅ Verification portal deployed.", ephemeral=True)

@bot.tree.command(name="lockdown", description="Globally lock/unlock all text channels")
@app_commands.checks.has_permissions(administrator=True)
async def lockdown(interaction: discord.Interaction, state: bool):
    await interaction.response.defer(ephemeral=True)
    msg = "enabled" if state else "disabled"
    for channel in interaction.guild.text_channels:
        overwrites = channel.overwrites_for(interaction.guild.default_role)
        overwrites.send_messages = not state
        await channel.set_permissions(interaction.guild.default_role, overwrite=overwrites)
    await interaction.followup.send(f"🚨 Server lockdown {msg}.")
    send_to_webhook("🚨 GLOBAL LOCKDOWN", f"State: {msg}\nBy: {interaction.user.mention}", discord.Color.dark_grey())

@bot.tree.command(name="purge", description="Mass remove messages")
@app_commands.checks.has_permissions(manage_messages=True)
async def purge(interaction: discord.Interaction, amount: int):
    await interaction.response.defer(ephemeral=True)
    deleted = await interaction.channel.purge(limit=amount)
    await interaction.followup.send(f"🧹 Purged {len(deleted)} messages.")

@bot.event
async def on_ready():
    print(f"✅ SYSTEM READY: {bot.user} is operational.")

if __name__ == "__main__":
    keep_alive()
    if TOKEN:
        bot.run(TOKEN)