import asyncio
import aiohttp
import pandas as pd
from PIL import Image, ImageDraw, ImageFont
import os
import re
import datetime
import streamlit as st
import discord

# Discord bot token and channel ID are now loaded from environment variables
BOT_TOKEN = os.getenv('DISCORD_BOT_TOKEN')  # Use environment variables for security
DISCORD_CHANNEL_ID = os.getenv('DISCORD_CHANNEL_ID')

# Create directories for valid URLs and generated cards
VALID_URLS_DIR = 'valid_urls'
LIVE_CARDS_DIR = 'generated_live_cards'
ICON_CARDS_DIR = 'generated_icon_cards'

# Create the directories if they don't exist
os.makedirs(VALID_URLS_DIR, exist_ok=True)
os.makedirs(LIVE_CARDS_DIR, exist_ok=True)
os.makedirs(ICON_CARDS_DIR, exist_ok=True)

# Function to read URLs from the specified file
def read_urls_from_file(urls_file):
    if os.path.exists(urls_file):
        with open(urls_file, 'r') as file:
            return [url.strip() for url in file.readlines() if url.strip()]
    return []

# Function to read previously valid URLs from the file for a given code
def read_previous_valid_urls(code):
    valid_urls_file = os.path.join(VALID_URLS_DIR, f'valid_urls_{code}.txt')
    if os.path.exists(valid_urls_file):
        with open(valid_urls_file, 'r') as file:
            return set(file.read().splitlines())
    return set()

# Function to write valid URLs to the file for a given code
def write_valid_urls(code, valid_urls):
    valid_urls_file = os.path.join(VALID_URLS_DIR, f'valid_urls_{code}.txt')
    with open(valid_urls_file, 'a') as file:
        for url in valid_urls:
            file.write(f"{url}\n")

# Function to check if URLs are valid
async def check_url(session, url):
    try:
        async with session.head(url) as response:
            if response.status == 200:
                return True
    except Exception as e:
        print(f"Error checking URL: {url} | Exception: {e}")
    return False

# Function to process URLs and match with CSV
async def process_urls(urls, code, csv_data, previous_valid_urls):
    valid_numbers = []
    async with aiohttp.ClientSession() as session:
        full_urls = [url.replace('CODE', code) for url in urls]
        tasks = [check_url(session, url) for url in full_urls]
        results = await asyncio.gather(*tasks)

    for result, full_url in zip(results, full_urls):
        if result:
            number_match = re.search(r'p(\d+)_', full_url)
            if number_match:
                number = number_match.group(1)
                if number not in previous_valid_urls:  # Check if number is not in previously valid URLs
                    valid_numbers.append(number)
                else:
                    print(f"Skipping previously valid number: {number}")
            else:
                print(f"Could not extract player number from URL: {full_url}")
        else:
            print(f"Invalid URL: {full_url}")

    output_data = []
    for number in valid_numbers:
        id_key = f"p{number}"
        if id_key in csv_data.index:
            player_data = {
                'Name': csv_data.loc[id_key, 'Name'],
                'Country': csv_data.loc[id_key, 'Country'],
                'League': csv_data.loc[id_key, 'League'],
            }
            if 'Club' in csv_data.columns:  # Check if the 'Club' column exists
                player_data['Club'] = csv_data.loc[id_key, 'Club']
            output_data.append(player_data)
        else:
            print(f"ID not found in CSV: {id_key}")

    return output_data, valid_numbers

# Function to resize images for consistency
def resize_image(image_path, size):
    try:
        image = Image.open(image_path).convert("RGBA")
        return image.resize(size, Image.LANCZOS)
    except Exception as e:
        print(f"Error loading image {image_path}: {e}")
        return None

# Function to generate player card images with high DPI
def generate_card_image(name, country, league, club, background_image, output_dir, card_type):
    try:
        dpi = 300
        base_image = Image.open(background_image).convert("RGBA")

        if base_image.size == (256, 256):
            base_image = base_image.resize((512, 512), Image.LANCZOS)

        base_image = base_image.resize((base_image.width * 2, base_image.height * 2), Image.LANCZOS)
        base_image.info['dpi'] = (dpi, dpi)
        draw = ImageDraw.Draw(base_image)

        font_path = os.path.join(os.getcwd(), "Fonts", "CruyffSansCondensed-Bold.otf")
        font_size_name = 90
        font_name = ImageFont.truetype(font_path, font_size_name)

        name_text_capitalized = name.upper()
        text_bbox = draw.textbbox((0, 0), name_text_capitalized, font=font_name)
        text_width = text_bbox[2] - text_bbox[0]
        text_x = (base_image.width - text_width) // 2
        text_y = 670

        # Set text color based on card type
        text_color = (255, 255, 255) if card_type == 'LIVE' else (66, 52, 15)
        draw.text((text_x, text_y), name_text_capitalized, fill=text_color, font=font_name)

        # Always use dark directory for ICONS and check background color for LIVE cards
        flags_dir = os.path.join(os.getcwd(), "Flags")
        league_dir = os.path.join(os.getcwd(), "Leagues_Dark")  # Always dark for ICONS
        club_dir = os.path.join(os.getcwd(), "Clubs_Dark")  # Always dark for ICONS

        country_image = resize_image(os.path.join(flags_dir, f"{country}.png"), (112, 112))
        league_image = resize_image(os.path.join(league_dir, f"{league}.png"), (96, 96))
        club_image = resize_image(os.path.join(club_dir, f"{club}.png"), (96, 96)) if card_type == 'LIVE' else None

        # Position for logos and flags for LIVE cards
        if card_type == 'LIVE':
            if country_image:
                base_image.paste(country_image, (258, 756), country_image)  # Position for the flag
            if league_image:
                base_image.paste(league_image, (468, 756), league_image)   # Position for the league logo
            if club_image:
                base_image.paste(club_image, (672, 756), club_image)  # Position for the club image
        else:  # For ICON cards, do not use club images
            if country_image:
                base_image.paste(country_image, (332, 756), country_image)  # Position for the flag
            if league_image:
                base_image.paste(league_image, (588, 756), league_image)  # Use the dark directory for leagues

        output_path = os.path.join(output_dir, f"{name.replace(' ', '_')}.png")
        base_image.save(output_path, format="PNG", dpi=(dpi, dpi))

        return output_path
    except Exception as e:
        print(f"Error generating card image for {name}: {e}")
        return None

# Function to create a collage of images
def create_collage(images, output_path, event_name="Event Name"):
    image_width, image_height = images[0].size
    tile_width = image_width
    tile_height = image_height
    collage_width = tile_width * 7
    collage_height = tile_height * 4

    collage = Image.new('RGBA', (collage_width, collage_height), (0, 0, 0, 0))

    for i, image in enumerate(images):
        x = (i % 7) * tile_width
        y = (i // 7) * tile_height
        collage.paste(image, (x, y))

    collage = collage.resize((3947, 2255), Image.LANCZOS)

    background_image_path = os.path.join(os.getcwd(), "Leaks2.png")
    background = Image.open(background_image_path)

    x_position = (background.width - collage.width) // 2
    y_position = 474
    background.paste(collage, (x_position, y_position), collage)

    welcome_font = ImageFont.truetype(os.path.join(os.getcwd(), "Fonts", "CruyffSansCondensed-Bold.otf"), size=200)
    draw = ImageDraw.Draw(background)
    text_bbox = draw.textbbox((0, 0), event_name, font=welcome_font)
    text_width = text_bbox[2] - text_bbox[0]
    text_x = (background.width - text_width) // 2
    text_y = 210

    draw.text((text_x, text_y), event_name, fill=(255, 255, 255), font=welcome_font)

    background.save(output_path)
    return output_path

# Function to send image to Discord channel
async def send_to_discord(file_path):
    try:
        if BOT_TOKEN and DISCORD_CHANNEL_ID:
            client = discord.Client(intents=discord.Intents.default())

            @client.event
            async def on_ready():
                print(f"Logged in as {client.user}")
                channel = client.get_channel(int(DISCORD_CHANNEL_ID))
                if channel:
                    with open(file_path, 'rb') as f:
                        picture = discord.File(f)
                        await channel.send(file=picture)
                await client.close()

            await client.start(BOT_TOKEN)
        else:
            print("Bot token or channel ID not set.")
    except Exception as e:
        print(f"Error sending image to Discord: {e}")

# Function to read CSV data and process images and collages
async def process_and_send_collage(urls_file, csv_file, code, event_name, card_type):
    urls = read_urls_from_file(urls_file)
    previous_valid_urls = read_previous_valid_urls(code)
    csv_data = pd.read_csv(csv_file).set_index('ID')

    output_data, valid_numbers = await process_urls(urls, code, csv_data, previous_valid_urls)

    generated_images = []
    output_dir = LIVE_CARDS_DIR if card_type == 'LIVE' else ICON_CARDS_DIR

    background_image = 'Leaks_Live.png' if card_type == 'LIVE' else 'Leaks_Icon.png'
    
    for player in output_data:
        player_name = player['Name']
        player_country = player['Country']
        player_league = player['League']
        player_club = player.get('Club', 'Unknown')
        image_path = generate_card_image(player_name, player_country, player_league, player_club, background_image, output_dir, card_type)
        if image_path:
            generated_images.append(Image.open(image_path))

    if generated_images:
        collage_path = os.path.join(output_dir, f"{code}_collage.png")
        create_collage(generated_images, collage_path, event_name)
        await send_to_discord(collage_path)

    write_valid_urls(code, valid_numbers)

# Streamlit Interface
def main():
    st.title("Image Generator and Discord Sender")
    
    urls_file = st.text_input("Enter the path to the URLs file", "urls.txt")
    csv_file = st.text_input("Enter the path to the CSV file", "players.csv")
    code = st.text_input("Enter the code for replacement", "123")
    event_name = st.text_input("Enter the event name", "Event Name")
    card_type = st.selectbox("Select card type", ['LIVE', 'ICON'])
    
    if st.button("Generate and Send Collage"):
        asyncio.run(process_and_send_collage(urls_file, csv_file, code, event_name, card_type))

if __name__ == '__main__':
    main()