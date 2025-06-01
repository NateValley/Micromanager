import discord
import aiohttp
import asyncio
import os

from datetime import datetime
from zoneinfo import ZoneInfo

from aiohttp import web

from dotenv import load_dotenv
load_dotenv()

TOKEN = os.getenv("TOKEN")

channel_id_str = os.getenv("CHANNEL_ID")
if not channel_id_str:
	raise ValueError("CHANNEL_ID is not set!")
CHANNEL_ID = int(channel_id_str)

CHECK_INTERVAL = 1		# in seconds

# ===========================================

async def handle_ping(request):
	return web.Response(text="Micromanager is alive frfr!")

async def start_web_server():
	app = web.Application()
	app.router.add_get("/", handle_ping)
	runner = web.AppRunner(app)
	await runner.setup()
	site = web.TCPSite(runner, "0.0.0.0", int(os.getenv("PORT", 8080)))
	await site.start()

# ===========================================

intents = discord.Intents.default()
class InvasionClient(discord.Client):
	async def setup_hook(self):
		self.bg_task = asyncio.create_task(invasion_loop(self))

client = InvasionClient(intents=intents)

async def fetch_invasions():
	async with aiohttp.ClientSession() as session:
		async with session.get("https://www.toontownrewritten.com/api/invasions") as resp:
			return await resp.json()

invasion_messages = {}  # district => discord.Message

async def invasion_loop(client):
	global invasion_messages
	await client.wait_until_ready()
	channel = client.get_channel(CHANNEL_ID)

	await clear_bot_messages(channel)

	while not client.is_closed():
		try:
			data = await fetch_invasions()
			invasions = data.get("invasions", {})
			active_districts = set(invasions.keys())

			# Handle current invasions
			for district, invasion_info in invasions.items():
				embed = await create_invasion_embed(district, invasion_info)

				if district not in invasion_messages:
					# Send new embed
					msg = await channel.send(embed=embed)
					invasion_messages[district] = msg
				else:
					# Update only if content has changed
					msg = invasion_messages[district]
					old_embed = msg.embeds[0].to_dict() if msg.embeds else {}
					if old_embed != embed.to_dict():
						await msg.edit(embed=embed)

			# Handle ended invasions
			ended_districts = [d for d in invasion_messages if d not in active_districts]
			for district in ended_districts:
				try:
					await invasion_messages[district].delete()
				except discord.NotFound:
					pass  # message already deleted
				del invasion_messages[district]
		
		except Exception as e:
			print(f"❌ Invasion Loop Error! {e}")
			
		await asyncio.sleep(CHECK_INTERVAL)

async def create_invasion_embed(district, invasion_info):
	cog = invasion_info.get("type", "Unknown Cog").replace("\u0003", "").strip()
	cog = fix_cog_name(cog)
	
	progress = invasion_info.get("progress", "0/0")
	start_timestamp = invasion_info.get("startTimestamp", 0)

	current, total = progress.split("/")
	remaining = int(total) - int(current)
	progress_percentage = int(current) / int(total) * 100

	start_time = format_start_time(start_timestamp)

	embed = discord.Embed(
		title=f"⚙️ {cog} Invasion! ⚙️ 🌎 Located in {district}! 🌎",
		color=discord.Color.green()
	)

	embed.set_image(url=get_cog_image_url(cog))

	embed.add_field(name="Remaining", value=f"{remaining} Cogs left", inline=True)
	embed.add_field(name="Progress", value=f"{progress_percentage:.1f}%", inline=True)
	
	if progress_percentage < 50:
		embed.color = discord.Color.green()
	elif progress_percentage >= 50 and progress_percentage < 85:
		embed.color = discord.Color.yellow()
	else:
		embed.color = discord.Color.red()
	
	embed.set_footer(text=f"Started at {start_time}")
	return embed

async def clear_bot_messages(channel):
	async for msg in channel.history(limit=100):
		if msg.author == client.user:
			try:
				await msg.delete()
			except discord.NotFound:
				pass


# ===========================================

def get_cog_image_url(cog_name):
	safe_name = cog_name.lower().replace(" ", "_")
	return f"https://raw.githubusercontent.com/NateValley/Micromanager/main/images/{safe_name}.png"

def format_start_time(unix_timestamp):
	dt = datetime.fromtimestamp(unix_timestamp, tz=ZoneInfo("America/Los_Angeles"))
	return dt.strftime("%I:%M %p %Z")

def fix_cog_name(cog_name):
	if cog_name == "Glad Hander":
		cog_name = "Glad Handler"
		return cog_name

# ===========================================


@client.event
async def on_ready():
	print(f'Logged in as {client.user}')

async def main():
	await start_web_server()
	await client.start(TOKEN)

asyncio.run(main())