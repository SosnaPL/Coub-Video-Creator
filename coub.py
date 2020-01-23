from coub_api.schemas.constants import Section, Category
from coub_api import CoubApi
import aiohttp
import aiofiles
import os
import subprocess
import datetime
import sys
import shutil
import time
import glob

czas = time.time()

print("STARTING")

api = CoubApi()
coubs = []
recent_coubs = []

required_time = 10
got_time = 0

#Checking if coub was in previous compilations
last_coubs = open("recent_coubs.txt", "r+")
for recent_coub in last_coubs.read().split(" "):
	recent_coubs.append(recent_coub)

#Creating next title number
with open("title_number.txt", 'r+') as f:
    number = int(f.read())
    number += 1
    f.seek(0)
    f.write(str(number))
    f.truncate()

#Copying needed files to new compilation folder
name = "compilation-" + datetime.datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
os.mkdir(name)
water = shutil.copy('watermarklogo.png', name)
przerywnik = shutil.copy('przerywnik.mkv', name)
ytup = shutil.copy('ytupload.py', name)
secret = shutil.copy('client_secrets.json', name)
auth02 = shutil.copy('ytupload.py-oauth2.json', name)
os.chdir(name)

#Variables that contains arguments needed to upload our compilation
out_title = "COUB ANIME COMPILATION #" + str(number)
out_file = "outputwithwatermark.mkv"
out_status = "public"

#Getting needed coubs with specified category and section as well as some other stuff
current_page = 1
while got_time <= required_time:
	response = api.timeline.section(section=Section.RISING, category=Category.ANIME, page=current_page)
	for coub in response.coubs:
		if not coub.age_restricted and not coub.audio_copyright_claim and coub.permalink not in recent_coubs and coub.audio_file_url and coub.duration > 5.0:
			coubs.append(coub)
			got_time += coub.duration
		if got_time >= required_time:
			break
	sys.stdout.write("Got {}s/{}s        \r".format(round(got_time), required_time))
	sys.stdout.flush()
	current_page += 1
print("")
got_time = round(got_time)
import asyncio

pending = len(coubs)
being_downloaded = 0
being_converted = 0
ready_to_join = 0

#Encoding individual coubs
async def run(coub):
	global pending
	global being_downloaded
	global being_merged
	global being_converted
	global being_timescaled
	global ready_to_join
	
	being_downloaded += 1
	xd = await asyncio.create_subprocess_shell(
		"youtube-dl -o \"" + coub.permalink + ".mp4\" https://coub.com/view/" + coub.permalink, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
	await xd.communicate()
	
	async with aiohttp.ClientSession() as session:
		async with session.get(str(coub.audio_file_url)) as resp:
			f = await aiofiles.open(coub.permalink+".mp3", mode='wb')
			await f.write(await resp.read())
			await f.close()
			
	f = await aiofiles.open(coub.permalink+".mp4", mode='r+b')
	await f.seek(0)
	await f.write(b"\x00\x00")
	await f.close()
	
	being_downloaded -= 1
	being_converted += 1

	xd2 = await asyncio.create_subprocess_shell(
		"ffmpeg -i  \"" + coub.permalink + ".mp4\" -i \"" + coub.permalink + ".mp3\" -shortest -c:v copy -c:a libopus merged_" + coub.permalink + ".mkv", stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
	await xd2.communicate()
	
	being_converted -= 1
	pending -= 1
	ready_to_join += 1

#Printing lifetime status of encoded coubs
async def print_status():
	while pending > 0:
		await asyncio.sleep(2)
		sys.stdout.write("P: {} D: {} C: {} R: {}                            \r".format(pending, being_downloaded, being_converted, ready_to_join))
		sys.stdout.flush()
#Checking if word have its counterpart in ascii code (used later on tags)
def is_alpha(word):
	try:
		return word.encode('ascii').isalpha()
	except:
		return False
loop = asyncio.ProactorEventLoop()
asyncio.set_event_loop(loop)
tasks = [run(x) for x in coubs]
tasks.append(print_status())
loop.run_until_complete(asyncio.wait(tasks))
converting = False

print("")

#Scaling and padding recently encoded coubs to match each other
padded = 0
async def pad(coub):
    global padded
    xd2 = subprocess.run(
        "ffmpeg -y -i merged_" + coub.permalink + ".mkv -vf scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2 -c:v h264_nvenc padded_fixed_merged_" + coub.permalink + ".mkv", shell=True, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
    padded += 1
    sys.stdout.write("Padded {}/{}     \r".format(padded, len(coubs)))
    sys.stdout.flush()
    
tasks = [pad(x) for x in coubs]
loop.run_until_complete(asyncio.wait(tasks))

print("")

print("Padding przerywnik")
subprocess.run(["ffmpeg", "-i", "przerywnik.mkv", "-vf", "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2", "przerywnik_padded.mkv"], stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)

print("Writing to file...")
with open("files.txt", "w") as f:
	for i, coub in enumerate(coubs,1):
		f.write("file 'padded_fixed_merged_" + coub.permalink + ".mkv'\n")
		if i != len(coubs):
			f.write("file 'przerywnik_padded.mkv' \n")

print("Adding description")		
with open("description.txt", "w") as f:
	duration = 0
	for i, coub in enumerate(coubs,1):
		sec = duration
		min = 0
		while sec>=60:
			sec -= 60
			min += 1
		sec = int(sec)
		if sec<10:
			sec = "0" + str(sec)
		f.write(str(min) + ":" + str(sec) + " https://coub.com/view/" + coub.permalink + "\n")
		if i != len(coubs):
			duration += coub.duration + 0.5
		else:
			duration += coub.duration
		print(str(i) + ". " + str(coub.duration))
	if duration%60<10:
		print("Final length " + str(int(duration/60)) + ":" + "0" + str(int(duration%60)))
	else:
		print("Final length " + str(int(duration/60)) + ":" + str(int(duration%60)))

print("Adding tags")		
with open("tags.txt", "w", encoding="utf-8") as f:
	tags = []
	tags_length = 0
	for coub in coubs:
		for tag in coub.tags:
			fixed_tag = str(tag.to_string().split("'")[1])
			if tags_length >= 450:
				break
			if fixed_tag and is_alpha(fixed_tag) and len(fixed_tag) < 25 and fixed_tag not in tags:
				tags.append(fixed_tag)
				f.write(fixed_tag + ",")
				tags_length += len(fixed_tag) + 1

print("Adding used coubs")
for coub in coubs:
	last_coubs.write(str(coub.permalink) + " ")
last_coubs.close()

print("Concatenating!")
subprocess.run(["ffmpeg", "-f", "concat", "-safe", "0", "-i", "files.txt", "-c", "copy", "output.mkv"], stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)

print("Adding watermark")
subprocess.run(["ffmpeg", "-i", "output.mkv", "-vf", "movie=watermarklogo.png [watermark]; [in][watermark] overlay=main_w-overlay_w-10:10 [out]", "-c:v", "h264_nvenc", "outputwithwatermark.mkv"], stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)

#os.system('ytupload.py --file="' + out_file + '" --title="' + out_title + '" --privacyStatus="' + out_status + '"')

print("Removing useless files...")
files = glob.glob('*.*')
for file in files:
	if file == "outputwithwatermark.mkv" or file == "tags.txt" or file == "description.txt":
		return
	os.remove(file)

czas = time.time() - czas
print("Executing program took "+ str(int(czas/60)) + ":" + str(int(czas%60)))
