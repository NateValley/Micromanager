import discord
import aiohttp
import asyncio
import os

from aiohttp import web

from dotenv import load_dotenv
load_dotenv()

TOKEN = os.getenv("TOKEN")

channel_id_str = os.getenv("CHANNEL_ID")
if not channel_id_str:
	raise ValueError("CHANNEL_ID is not set!")
CHANNEL_ID = int(channel_id_str)

CHECK_INTERVAL = 1		# in seconds

async def handle_ping(request):
	return web.Response(text="Micromanager is alive!")

async def start_web_server():
	app = web.Application()
	app.router.add_get("/", handle_ping)
	runner = web.AppRunner(app)
	await runner.setup()
	site = web.TCPSite(runner, "0.0.0.0", int(os.getenv("PORT", 8080)))
	await site.start()

intents = discord.Intents.default()
class InvasionClient(discord.Client):
	async def setup_hook(self):
		self.bg_task = asyncio.create_task(invasion_loop(self))

client = InvasionClient(intents=intents)

async def fetch_invasions():
	async with aiohttp.ClientSession() as session:
		async with session.get("https://www.toontownrewritten.com/api/invasions") as resp:
			return await resp.json()

invasion_message = None  # single discord.Message for all invasions

async def invasion_loop(client):
	global invasion_message
	await client.wait_until_ready()
	channel = client.get_channel(CHANNEL_ID)

	while not client.is_closed():
		data = await fetch_invasions()
		invasions = data.get("invasions", {})

		if invasions:
			# Build one big string with all invasions info
			combined_content = ""
			for district, invasion_info in invasions.items():
				cog = invasion_info.get("type", "Unknown Cog")
				progress = invasion_info.get("progress", "0/0")
				current, total = progress.split("/")
				remaining = int(total) - int(current)
				progress_percentage = int(current) / int(total) * 100
				combined_content += f"**{cog}** invasion in **{district}**! `{remaining}` left. ({progress_percentage:.1f}%)\n"

			if invasion_message is None:
				# Send first message
				invasion_message = await channel.send(combined_content)
			else:
				# Edit existing message if content changed
				if invasion_message.content != combined_content:
					await invasion_message.edit(content=combined_content)

		else:
			# No invasions active, delete message if exists
			if invasion_message is not None:
				await invasion_message.delete()
				invasion_message = None

		await asyncio.sleep(CHECK_INTERVAL)


@client.event
async def on_ready():
	print(f'Logged in as {client.user}')

async def main():
	await start_web_server()
	await client.start(TOKEN)

client.run(TOKEN)