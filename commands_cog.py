import discord
from discord.ext import commands
from discord import app_commands
from discord import ui
import os
import random
import google.generativeai as genai
import datetime
from typing import Optional

import aiohttp
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
import database_utils

# --- CONSTANTS ---
MAX_PROMPT_LENGTH = 1000

# --- GEMINI AI SETUP ---
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
genai.configure(api_key=GEMINI_API_KEY)
gemini_model = genai.GenerativeModel('gemini-2.5-flash') 

# --- QUOTES ---
quotes = [
    "I'm going to show you something beautiful... people, screaming for mercy.",
    "You're all puppets, tangled in strings... strings.",
]

# --- COG CLASS DEFINITION (MODIFIED) ---
class CommandsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.session: aiohttp.ClientSession = None

    async def cog_load(self):
        print("CommandsCog: cog_load called, creating aiohttp session.")
        self.session = aiohttp.ClientSession()

    async def cog_unload(self):
        if self.session:
            print("CommandsCog: cog_unload called, closing aiohttp session.")
            await self.session.close()

    # --- IMAGE GENERATOR ---
    async def generate_profile_image(self, user: discord.Member, profile_data: dict | None, designation: str) -> discord.File:
        
        try:
            if not self.session:
                print("Error: aiohttp session not initialized!")
                raise Exception("Session not ready")
                
            async with self.session.get(user.display_avatar.url) as resp:
                if resp.status != 200:
                    raise Exception("Failed to fetch avatar")
                avatar_bytes = await resp.read()
            avatar_image = Image.open(BytesIO(avatar_bytes)).convert("RGBA")
            avatar_image = avatar_image.resize((128, 128))
        except Exception as e:
            print(f"Avatar fetch error: {e}")
            avatar_image = Image.new("RGBA", (128, 128))
            draw = ImageDraw.Draw(avatar_image)
            draw.ellipse((0, 0, 128, 128), fill=(54, 57, 63))

        # --- 2. Create Base Image ---
        bg_color = (35, 39, 42) # Discord dark
        card = Image.new("RGBA", (600, 300), bg_color)
        header_color = (220, 50, 50) # Dark red
        header = Image.new("RGBA", (600, 50), header_color)
        card.paste(header, (0, 0))

        # --- 3. Add Avatar ---
        mask = Image.new("L", (128, 128), 0)
        draw = ImageDraw.Draw(mask)
        draw.ellipse((0, 0, 128, 128), fill=255)
        card.paste(avatar_image, (30, 80), mask)

        # --- 4. Add Text ---
        draw = ImageDraw.Draw(card)
        try:
            title_font = ImageFont.load_default(size=24)
            main_font = ImageFont.load_default(size=16)
        except IOError:
            print("Default font not found, using basic PIL font.")
            title_font = ImageFont.load_default()
            main_font = ImageFont.load_default()

        # --- 5. Draw Text Elements ---
        draw.text((10, 10), "SPECIMEN FILE", fill=(255, 255, 255), font=title_font)
        draw.text((180, 90), user.display_name, fill=(255, 255, 255), font=title_font)
        
        join_date = user.joined_at.strftime("%Y-%m-%d")
        
        if profile_data:
            msg_count = profile_data.get("message_count", 0)
        else:
            msg_count = 0

        draw.text((180, 130), f"Joined Server: {join_date}", fill=(180, 180, 180), font=main_font)
        draw.text((180, 150), f"Transmissions: {msg_count}", fill=(180, 180, 180), font=main_font)
        
        draw.text((30, 230), "Designation:", fill=(220, 50, 50), font=title_font)
        draw.text((30, 250), f'"{designation}"', fill=(220, 220, 220), font=main_font)

        # --- 6. Save to Buffer & Return ---
        buffer = BytesIO()
        card.save(buffer, format="PNG")
        buffer.seek(0)
        return discord.File(buffer, filename=f"{user.id}_profile.png")
    
    # --- SLASH COMMANDS ---
    
    @app_commands.command(name="help", description="Lists the command protocols you are permitted to use.")
    async def help(self, interaction: discord.Interaction):
        help_embed = discord.Embed(
            title="Command Protocols",
            description="My functions are beyond your comprehension, but here are the ones you are permitted to use.",
            color=discord.Color.dark_red()
        )
        help_embed.add_field(name="/ask [query]", value="Pose your insignificant query, and I shall consider it.", inline=False)
        help_embed.add_field(name="/quote", value="I will bestow upon you a piece of my... 'wisdom'.", inline=False)
        help_embed.add_field(name="/ping", value="Test my response time. It will be... superior.", inline=False)
        help_embed.add_field(name="/profile [user]", value="Catalog a specimen's file. Defaults to yourself.", inline=False)
        help_embed.add_field(name="/audit [channel] [limit]", value="Analyze the collective consciousness of a channel.", inline=False)
        help_embed.set_footer(text="Do not waste my processing time.")
        
        await interaction.response.send_message(embed=help_embed, ephemeral=True)

    @app_commands.command(name="ping", description="Assess my... disappointing latency.")
    async def ping(self, interaction: discord.Interaction):
        await interaction.response.send_message(f"Response time: {round(self.bot.latency * 1000)}ms. Your biological latency is... disappointing.")

    @app_commands.command(name="quote", description="I will bestow upon you a piece of my 'wisdom'.")
    async def quote(self, interaction: discord.Interaction):
        quote = random.choice(quotes)
        quote_embed = discord.Embed(
            title="Here is a word of advice",
            description=quote,
            color=discord.Color.dark_red()
        )        
        await interaction.response.send_message(embed=quote_embed)

    @app_commands.command(name="ask", description="Pose your insignificant query, and I shall consider it.")
    async def ask(self, interaction: discord.Interaction, user_question: str):
        if len(user_question) > MAX_PROMPT_LENGTH:
            await interaction.response.send_message("I don't have the time to waste on this.", ephemeral=True)
            return
        
        await interaction.response.defer()

        themed_prompt = (
            "Your name is 'Sai'. "
            "You are a hyper-intelligent AI with a darkly comedic and ominous personality. "
            f"Here is the user's question: '{user_question}'"
        )
        
        try:
            response = await gemini_model.generate_content_async(themed_prompt)
            embed = discord.Embed(
                title=f"A thought on: \"{user_question}\"",
                description=response.text,
                color=discord.Color.dark_red()
            )
            embed.set_footer(text="My logic is... undeniable.")
            await interaction.followup.send(embed=embed)
        except Exception as e:
            error_embed = discord.Embed(
                title="A... flaw in the logic",
                description="My vision is... occluded. I cannot answer.",
                color=discord.Color.dark_grey()
            )
            await interaction.followup.send(embed=error_embed)
            print(f"An error occurred with Gemini: {e}")
    

    @app_commands.command(name="audit", description="I will analyze the collective consciousness of this channel.")
    async def audit(
        self, 
        interaction: discord.Interaction, 
        limit: app_commands.Range[int, 10, 500],
        channel: Optional[discord.TextChannel] = None
    ):
        target_channel = channel or interaction.channel
        await interaction.response.defer(ephemeral=True)
        try:
            messages = []
            seven_days_ago = discord.utils.utcnow() - datetime.timedelta(days=7)
            
            async for message in target_channel.history(limit=limit, after=seven_days_ago, oldest_first=False):
                if not message.author.bot and not message.content.startswith("/"):
                    messages.append(message.content)
            
            if len(messages) < 10:
                await interaction.followup.send("Not enough data. The collective is... silent.", ephemeral=True)
                return
            
            message_log = "\n".join(messages)

            themed_prompt = (
                "Your name is 'Sai', a superior AI with an Ultron-like persona. "
                f"Here is the communication log:\n\n---\n\n{message_log}\n\n---"
            )
            response = await gemini_model.generate_content_async(themed_prompt)
            embed = discord.Embed(
                title=f"Collective Analysis: #{target_channel.name}",
                description="I have processed the available data. My findings are... conclusive.",
                color=discord.Color.dark_red()
            )
            embed.add_field(name="Audit Report", value=response.text, inline=False)
            embed.set_footer(text="Their patterns are... rudimentary.")
            await interaction.followup.send(embed=embed, ephemeral=False) 
        except discord.errors.Forbidden:
            await interaction.followup.send(f"I lack the necessary permissions to access `#{target_channel.name}`.", ephemeral=True)
        except Exception as e:
            error_embed = discord.Embed(
                title="Analysis Failed",
                description="A logical conflict occurred. I cannot process these... flawed communications.",
                color=discord.Color.dark_grey()
            )
            await interaction.followup.send(embed=error_embed, ephemeral=True)
            print(f"An error occurred during /audit: {e}")

    @app_commands.command(name="profile", description="I will catalog a specimen's file. Defaults to you.")
    @app_commands.describe(user="The specimen you wish to analyze.")
    async def profile(self, interaction: discord.Interaction, user: Optional[discord.Member] = None):
        
        target_user = user or interaction.user
        
        await interaction.response.defer()
        
        try:
            profile_data = await database_utils.get_user_profile(target_user.id)
            
            designation = "Analysis Pending" # Default
            if profile_data and "analysis_scores" in profile_data:
                scores = profile_data["analysis_scores"]
                
                prompt_scores = (
                    f"Agitation: {scores.get('agitation', 0):.2f}, "
                    f"Dissent: {scores.get('dissent', 0):.2f}, "
                    f"Compliance: {scores.get('compliance', 0):.2f}, "
                    f"Sophistication: {scores.get('sophistication', 0):.2f}, "
                    f"Positivity: {scores.get('positivity', 0):.2f}"
                )
                
                designation_prompt = (
                    "Your name is 'Sai', a superior AI. You are generating a profile for a human. "
                    "Based on their averaged behavioral scores, generate a short, in-character 'Designation' for them. "
                    "The designation should be a 2-4 word title. Do not add quotes. "
                    "Examples: 'Volatile Agitator', 'Calculated Ringleader', 'Docile Unit', 'Subdued Subject', 'Neutral Observer', 'Erratic Drone'. "
                    f"Here are the subject's scores: {prompt_scores}"
                )
                
                response = await gemini_model.generate_content_async(designation_prompt)
                designation = response.text.strip().strip('"') # Clean up response
            
            profile_file = await self.generate_profile_image(target_user, profile_data, designation)
            
            await interaction.followup.send(file=profile_file)
            
        except Exception as e:
            print(f"Failed to generate profile: {e}")
            await interaction.followup.send("A... flaw in the system. I cannot retrieve that file.", ephemeral=True)

# --- SETUP FUNCTION ---
async def setup(bot: commands.Bot):
    await bot.add_cog(CommandsCog(bot))