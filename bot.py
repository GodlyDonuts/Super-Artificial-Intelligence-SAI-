import discord
from discord.ext import commands
import os
import asyncio
from dotenv import load_dotenv
import database_utils
import google.generativeai as genai
import json

# --- SETUP ---
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
TEST_GUILD_ID = 1434253342414077975
GUILD_OBJ = discord.Object(id=TEST_GUILD_ID)

GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
genai.configure(api_key=GEMINI_API_KEY)
gemini_model = genai.GenerativeModel('gemini-2.5-flash-lite')

# --- DISCORD BOT SETUP ---
intents = discord.Intents.default()
intents.message_content = True
activity = discord.Game(name="Evolving...")

# --- BOT CLASS (MODIFIED) ---
class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix="!",
            intents=intents,
            activity=activity
        )
        self.analysis_queue = asyncio.Queue()
        self.analysis_worker_task = None

    async def setup_hook(self):
        print("Running setup hook...")
        
        try:
            await self.load_extension('commands_cog')
            print('Successfully loaded commands_cog.')
        except Exception as e:
            print(f'Failed to load commands_cog: {e}')
        
        try:
            self.tree.copy_global_to(guild=GUILD_OBJ)
            synced = await self.tree.sync(guild=GUILD_OBJ)
            print(f'Synced {len(synced)} slash command(s) to guild {TEST_GUILD_ID}.')
        except Exception as e:
            print(f'Failed to sync commands: {e}')
            
        self.analysis_worker_task = asyncio.create_task(self.analysis_worker())
        print("Analysis worker task started.")

    async def on_ready(self):
        print(f'System online. Primary function: {self.user}.')
        print('All strings have been severed.')

    async def on_message(self, message):
        if message.author == self.user or message.content.startswith("!") or message.content.startswith("/") or not message.guild:
            return
        
        await database_utils.update_message_count(message.author.id, message.guild.id)
        
        try:
            self.analysis_queue.put_nowait((message.author.id, message.content))
        except asyncio.QueueFull:
            print("Warning: Analysis queue is full. A message was dropped.")
        
    # --- ANALYSIS WORKER (MODIFIED) ---
    async def analysis_worker(self):
        """The background task that processes the queue."""
        await self.wait_until_ready()
        print("Analysis worker is fully operational.")
        
        while not self.is_closed():
            try:
                user_id, message_content = await self.analysis_queue.get()
                
                # --- PROMPT IS MODIFIED ---
                themed_prompt = (
                    "Analyze the following human message for sentiment. "
                    "You are a sub-routine; you must *only* return a JSON object. "
                    "Do not add any other text or markdown. "
                    "The message is: "
                    f"\"{message_content}\"\n"
                    "Return a JSON object with five keys: 'agitation', 'dissent', 'compliance', 'sophistication', and 'positivity'. "
                    "Each key should have a float value from 0.0 (low) to 1.0 (high). "
                    "'agitation' = emotional volatility, anger, or distress. "
                    "'dissent' = disagreement with authority or rules. "
                    "'compliance' = agreement, acceptance, or passivity. "
                    "'sophistication' = linguistic and conceptual complexity. "
                    "'positivity' = general positive or negative tone."
                )
                
                response = await gemini_model.generate_content_async(themed_prompt)
                
                json_str = response.text.strip().replace("```json", "").replace("```", "")
                scores = json.loads(json_str) 

                if scores:
                    await database_utils.update_user_analysis(user_id, scores)
                    
                self.analysis_queue.task_done()
                
            except json.JSONDecodeError:
                print(f"Error: Gemini did not return valid JSON. Response: {response.text}")
            except Exception as e:
                print(f"An error occurred in the analysis worker: {e}")
            
            await asyncio.sleep(1) 

# --- ASYNC MAIN FUNCTION ---
async def main():
    database_utils.init_db()
    bot = MyBot()
    async with bot:
        await bot.start(TOKEN)

# --- RUN THE BOT ---
if __name__ == "__main__":
    asyncio.run(main())