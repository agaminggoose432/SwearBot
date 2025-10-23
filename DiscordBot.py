import discord
from discord.ext import commands
from discord.ext import voice_recv
import asyncio
import soundfile
import openai
from openai import OpenAI
import resampy
import numpy
import io
import wave
import json

swear_words = {"Use some imagination"}


api_key = "private get your own API key :3"
client = OpenAI(api_key=api_key)

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

discord.opus._load_default()

@bot.command()
async def test(ctx, seconds: int = 1):
    def callback(user, data: voice_recv.VoiceData):
        print(f"Recieved a packet from {user}")
    
    await ctx.send("Testing active")
    vc = await ctx.author.voice.channel.connect(cls=voice_recv.VoiceRecvClient)
    sink = voice_recv.WaveSink(destination="Audio/demo_audio.wav")
    sink = TranscriptionSink(bot)
    vc.listen(sink)
    channel = ctx.channel
    ctx.bot.loop.create_task(sink.transcribe_periodically(channel))
    await ctx.send("listening")

@bot.command()
async def join(ctx):    
    if ctx.author.voice:
        channel = ctx.author.voice.channel
        try:
            vc = await ctx.author.voice.channel.connect(cls=voice_recv.VoiceRecvClient)
            sink = voice_recv.WaveSink(destination="Audio/demo_audio.wav")
            sink = TranscriptionSink(bot)
            vc.listen(sink)
            channel = ctx.channel
            ctx.bot.loop.create_task(sink.transcribe_periodically(channel))
            await ctx.send(f"✅ Joined {channel.name}")
            print(f"Connected to: {channel.name} successfully")
            vc.listen(voice_recv.WaveSink)
        except Exception as e:
            await ctx.send(f"❌ Failed to join voice channel: {e}")
    else:
        await ctx.send("You must be in a voice channel!")
        
async def output(channel, text):
    await channel.send(text)

# Leave voice channel
@bot.command()
async def leave(ctx):
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
        await ctx.send("👋 Left the voice channel!")
    else:
        await ctx.send("I’m not in a voice channel!")

        
class TranscriptionSink(voice_recv.AudioSink):
    
    def __init__(self, bot):
        super().__init__()
        self.bot = bot
        self.buffers = {}  # user_id -> bytearray
        
    def wants_opus(self) -> bool:
        # We want PCM, not raw Opus
        return False

    def write(self, user, data):
        # data.pcm is 20ms of PCM16LE @ 48000 Hz
        if user.id not in self.buffers:
            self.buffers[user.id] = bytearray()
        self.buffers[user.id].extend(data.pcm)
        
    def cleanup(self):
        # Free buffers/recognizers
        self.buffers.clear()

    async def transcribe_periodically(self, channel, interval=15):
        """Every few seconds, send buffered audio to Whisper."""
        while True:
            await asyncio.sleep(interval)
            for user_id, pcm in list(self.buffers.items()):
                if len(pcm) < 3 * 48000:  # ~1 sec of audio
                    continue
                # Copy & clear buffer
                audio_bytes = bytes(pcm)
                self.buffers[user_id].clear()
                # Convert PCM to WAV in memory
                wav_io = io.BytesIO()
                with wave.open(wav_io, "wb") as wf:
                    wf.setnchannels(1)
                    wf.setsampwidth(2)
                    wf.setframerate(48000)
                    wf.writeframes(audio_bytes)
                wav_io.seek(0)
                # Send to OpenAI Whisper
                try:
                    result = client.audio.transcriptions.create(
                        model="gpt-4o-transcribe",  # or "whisper-1"
                        file=("audio.wav", wav_io.read()),
                    )
                    text = result.text
                    if text:
                        print(f"{user_id}: {text}")
                        for word in swear_words:
                            if word in text.lower():
                                print(f"Word flagged!!! Found {word} in a speech from {user_id}")
                                await SwearFound(channel, user_id, word)       
                except Exception as e:
                    print("Transcription error:", e)
 
    
@bot.command()
async def getDebt(ctx):
    file = open('data.json', 'r')
    debt_dictionary = json.load(file)
    file.close()
    
    guild_id = str(ctx.channel.guild.id)
    user_id = str(ctx.author.id)
    
    
    debt =  debt_dictionary[guild_id]["users"][user_id]["debt"]
    await ctx.send("You currently owe: " + str(debt))


async def SwearFound(channel, user_id, swearWord):
    file = open('data.json', 'r')
    debt_dictionary = json.load(file)
    file.close()
    
    guild_id = str(channel.guild.id)
    user_id = str(user_id)
    
    if guild_id not in debt_dictionary:
        print("Adding new guild + user to data")
        debt_dictionary[guild_id] = {"users": {user_id: {"debt": 0}}}
    elif user_id not in debt_dictionary[guild_id]["users"]:
        print("Adding new user to data")
        debt_dictionary[guild_id]["users"][user_id] = {"debt": 0}
        
    with open("data.json", "w") as f:
        debt_dictionary[guild_id]["users"][user_id]["debt"] += 15
        json.dump(debt_dictionary, f, indent=4)
        debt =  debt_dictionary[guild_id]["users"][user_id]["debt"]
        if debt >= 150:
            await Punishment(channel.guild, user_id)
        await output(channel, f"{swearWord} has been said by <@{user_id}> they now owe {debt}")
      
async def Punishment(guild, user_id):
    role = discord.utils.get(guild.roles, name="potty mouth")
    if role != None:
        print("adding role")
        for user in guild.members:
            print(f"comparing: {user.id} to {user_id}")
            if user.id == int(user_id):
                await user.add_roles(role)
                print(f"added role to: {user}") 
    else:
        print("creating + adding role")
        role = await guild.create_role(name="potty mouth")
        await role.edit(colour=discord.Colour(0xF080FF))
        await role.move(end=True)
        for user in guild.members:
            if user.id == int(user_id):
                await user.add_roles(role)
                print(f"added role to: {user}") 

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")


bot.run("No key for you!!!!")
