import discord
from discord import app_commands
from discord.ext import commands
import datetime 
import os
import asyncio
import random
import re
import logging
from collections import defaultdict
from threading import Thread
from flask import Flask

# ----- Standard Logging Setup -----
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('discord_bot')

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
        try:
            if self.user_answer.value == str(self.answer):
                verified_role = discord.utils.get(interaction.guild.roles, name=VERIFIED_ROLE_NAME)
                unverified_role = discord.utils.get(interaction.guild.roles, name=UNVERIFIED_ROLE_NAME)

                if not verified_role:
                    await interaction.response.send_message(f"❌ Error: Role '{VERIFIED_ROLE_NAME}' not found.", ephemeral=True)
                    return

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

# ----- Bot Core Class -----

class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        self.add_view(VerifyView())
        await self.tree.sync()
        logger.info("Slash commands and UI views synced.")

bot = MyBot()

# ----- Logging & Webhook System -----

def send_to_webhook(title, description, color, member=None):
    if not WEBHOOK_URL:
        return
    try:
        webhook = discord.SyncWebhook.from_url(WEBHOOK_URL)
        embed = discord.Embed(title=title, description=description, color=color, timestamp=discord.utils.utcnow())
        if member:
            embed.set_footer(text=f"Member ID: {member.id}")
        webhook.send(embed=embed)
    except Exception as e:
        logger.error(f"Webhook Failure: {e}")

# ----- Moderation Helper Functions -----

async def ensure_muted_role(guild):
    role = discord.utils.get(guild.roles, name=MUTED_ROLE_NAME)
    if not role:
        try:
            role = await guild.create_role(name=MUTED_ROLE_NAME, reason="Auto-Mod Mute Role")
            for channel in guild.channels:
                await channel.set_permissions(role, send_messages=False, add_reactions=False)
        except Exception as e:
            logger.error(f"Cannot create Mute role: {e}")
    return role

# ----- Global Security Events -----

@bot.event
async def on_message(message):
    if message.author.bot or not message.guild:
        return

    # 1. Swear Filter
    if any(word.lower() in message.content.lower() for word in SWEAR_WORDS):
        await message.delete()
        send_to_webhook("🚫 Content Filtered", f"User: {message.author.mention}\nMessage: {message.content}", discord.Color.red(), message.author)
        return

    # 2. Anti-Raid Logic
    now = datetime.datetime.utcnow()
    user_message_logs[message.author.id].append(now)
    user_message_logs[message.author.id] = [t for t in user_message_logs[message.author.id] if (now - t).total_seconds() < 5]

    if len(user_message_logs[message.author.id]) >= 5:
        mute_role = await ensure_muted_role(message.guild)
        if mute_role and mute_role not in message.author.roles:
            await message.author.add_roles(mute_role)
            await message.channel.send(f"🔇 {message.author.mention} auto-muted for spamming.")
            send_to_webhook("🔇 Auto-Mute", f"User: {message.author.mention}", discord.Color.dark_red(), message.author)
            await asyncio.sleep(60)
            await message.author.remove_roles(mute_role)
        return

    await bot.process_commands(message)

@bot.event
async def on_message_delete(message):
    if not log_config["messageDelete"] or message.author.bot: return
    
    # Ghost Ping Detection
    mention_pattern = r'<@!?([0-9]+)>|<@&([0-9]+)>'
    if re.search(mention_pattern, message.content):
        send_to_webhook("👻 Ghost Ping", f"User: {message.author.mention}\nContent: {message.content}", discord.Color.yellow(), message.author)
    else:
        send_to_webhook("🗑️ Deleted", f"User: {message.author.mention}\nContent: {message.content}", discord.Color.red(), message.author)

@bot.event
async def on_message_edit(before, after):
    if not log_config["messageEdit"] or before.author.bot or before.content == after.content: return
    send_to_webhook("✏️ Edited", f"User: {before.author.mention}\n**Old:** {before.content}\n**New:** {after.content}", discord.Color.orange(), before.author)

@bot.event
async def on_member_join(member):
    unverified = discord.utils.get(member.guild.roles, name=UNVERIFIED_ROLE_NAME)
    if unverified:
        await member.add_roles(unverified)
    send_to_webhook("👋 New Member", f"{member.mention} joined.", discord.Color.blue(), member)

# ----- Force Sync Command -----

@bot.command()
@commands.has_permissions(administrator=True)
async def sync(ctx):
    await bot.tree.sync()
    await ctx.send("🔄 Commands synced!")

# ----- Moderation Slash Commands -----

@bot.tree.command(name="kick", description="Kick a member from the server")
@app_commands.checks.has_permissions(kick_members=True)
async def kick(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
    try:
        await member.kick(reason=reason)
        await interaction.response.send_message(f"✅ {member.display_name} has been kicked.")
        send_to_webhook("👞 Member Kicked", f"User: {member.mention}\nMod: {interaction.user.mention}\nReason: {reason}", discord.Color.orange(), member)
    except Exception as e:
        await interaction.response.send_message(f"❌ Failed to kick: {e}", ephemeral=True)

@bot.tree.command(name="ban", description="Ban a member from the server")
@app_commands.checks.has_permissions(ban_members=True)
async def ban(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
    try:
        await member.ban(reason=reason)
        await interaction.response.send_message(f"✅ {member.display_name} has been banned.")
        send_to_webhook("🔨 Member Banned", f"User: {member.mention}\nMod: {interaction.user.mention}\nReason: {reason}", discord.Color.dark_red(), member)
    except Exception as e:
        await interaction.response.send_message(f"❌ Failed to ban: {e}", ephemeral=True)

@bot.tree.command(name="softban", description="Ban and immediately unban to clear messages")
@app_commands.checks.has_permissions(ban_members=True)
async def softban(interaction: discord.Interaction, member: discord.Member, reason: str = "Softban (Message Scrub)"):
    try:
        await member.ban(reason=reason, delete_message_days=7)
        await interaction.guild.unban(member)
        await interaction.response.send_message(f"🧼 {member.display_name} has been soft-banned (messages cleared).")
        send_to_webhook("🧼 Soft-Ban", f"User: {member.mention}\nMod: {interaction.user.mention}\nReason: {reason}", discord.Color.light_grey(), member)
    except Exception as e:
        await interaction.response.send_message(f"❌ Failed to soft-ban: {e}", ephemeral=True)

@bot.tree.command(name="setup_verify", description="Deploy verification")
@app_commands.checks.has_permissions(administrator=True)
async def setup_verify(interaction: discord.Interaction):
    embed = discord.Embed(title="🔒 Security Portal", description="Click to verify.", color=discord.Color.green())
    await interaction.channel.send(embed=embed, view=VerifyView())
    await interaction.response.send_message("Deployed.", ephemeral=True)

@bot.tree.command(name="lock", description="Lock or Unlock the current channel")
@app_commands.checks.has_permissions(manage_channels=True)
async def lock(interaction: discord.Interaction):
    channel = interaction.channel
    overwrite = channel.overwrites_for(interaction.guild.default_role)
    overwrite.send_messages = not overwrite.send_messages
    status = "unlocked" if overwrite.send_messages else "locked"
    await channel.set_permissions(interaction.guild.default_role, overwrite=overwrite)
    await interaction.response.send_message(f"Channel is now **{status}**.")

@bot.tree.command(name="lockdown", description="Lock all channels")
@app_commands.checks.has_permissions(administrator=True)
async def lockdown(interaction: discord.Interaction, state: bool):
    await interaction.response.defer(ephemeral=True)
    for channel in interaction.guild.text_channels:
        overwrites = channel.overwrites_for(interaction.guild.default_role)
        overwrites.send_messages = not state
        await channel.set_permissions(interaction.guild.default_role, overwrite=overwrites)
    await interaction.followup.send(f"Lockdown {'enabled' if state else 'disabled'}.")

@bot.tree.command(name="purge", description="Mass delete")
@app_commands.checks.has_permissions(manage_messages=True)
async def purge(interaction: discord.Interaction, amount: int):
    await interaction.response.defer(ephemeral=True)
    deleted = await interaction.channel.purge(limit=amount)
    await interaction.followup.send(f"Purged {len(deleted)} messages.")

@bot.event
async def on_ready():
    logger.info(f"✅ Bot Ready: {bot.user}")

if __name__ == "__main__":
    keep_alive()
    if TOKEN:
        bot.run(TOKEN)