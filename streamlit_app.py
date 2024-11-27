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
        # Debug message
        print(f"Generating card for {name} from {country}, {league}, {club}")
        
        # Validate background image
        if not os.path.exists(background_image):
            print(f"Background image does not exist: {background_image}")
            return None
        
        # Load background image
        base_image = Image.open(background_image).convert("RGBA")
        width, height = base_image.size
        print(f"Loaded background image with dimensions: {width}x{height}")
        
        # Create drawing context
        draw = ImageDraw.Draw(base_image)

        # Define font (update path to an existing font file on your system)
        font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"  # Adjust path as needed
        if not os.path.exists(font_path):
            print("Font file not found. Using default font.")
            font = ImageFont.load_default()
        else:
            font = ImageFont.truetype(font_path, size=40)

        # Add text
        text = f"{name}\n{country}\n{league}\n{club}"
        text_x, text_y = 50, 50
        draw.text((text_x, text_y), text, font=font, fill="white")
        print(f"Added text to the image at position ({text_x}, {text_y})")
        
        # Ensure output directory exists
        os.makedirs(output_dir, exist_ok=True)

        # Save image
        output_path = os.path.join(output_dir, f"{name.replace(' ', '_')}.png")
        base_image.save(output_path, format="PNG", dpi=(300, 300))
        print(f"Image saved successfully for {name} at {output_path}")
        
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

    background_image_path = os.path.join(os.getcwd(), "Leaks3.png")
    background = Image.open(background_image_path)

    x_position = (background.width - collage.width) // 2
    y_position = 474
    background.paste(collage, (x_position, y_position), collage)

    welcome_font = ImageFont.truetype(os.path.join(os.getcwd(), "Fonts", "CruyffSansCondensed-Bold.otf"), size=200)
    draw = ImageDraw.Draw(background)
    text_bbox = draw.textbbox((0, 0), event_name, font=welcome_font)
    text_width = text_bbox[2] - text_bbox[0]
    text_x = (background.width - text_width) // 2
    text_y = 228
    draw.text((text_x, text_y), event_name, fill=(255, 255, 255), font=welcome_font)

    current_date = datetime.date.today().strftime("%Y-%m-%d")
    date_font = ImageFont.truetype(os.path.join(os.getcwd(), "Fonts", "CruyffSansCondensed-Bold.otf"), size=137)
    text_bbox = draw.textbbox((0, 0), current_date, font=date_font)
    date_text_width = text_bbox[2] - text_bbox[0]
    date_x = background.width - date_text_width - 50
    draw.text((date_x, text_y), current_date, fill=(255, 255, 255), font=date_font)

    background.save(output_path, format="PNG", dpi=(300, 300))

# Function to send the collage image to Discord
async def send_collage_to_discord(collage_path):
    intents = discord.Intents.default()
    client = discord.Client(intents=intents)
    
    leaks_role_id = os.getenv('DISCORD_LEAKS_ROLE_ID')  # Retrieve the Leaks role ID

    async def send_image():
        channel = client.get_channel(int(DISCORD_CHANNEL_ID))
        if channel:
            with open(collage_path, 'rb') as f:
                picture = discord.File(f)
                # Mention the Leaks role
                role_mention = f"<@&{leaks_role_id}>"
                await channel.send(content=f"", file=picture)
        else:
            print("Channel not found")

    @client.event
    async def on_ready():
        await send_image()
        await client.close()

    await client.start(BOT_TOKEN)

# Streamlit main function
def main():
    st.title("Player Card Generator")

    event_name = st.text_input("Enter the event name")
    if not event_name:
        st.warning("Please enter an event name.")
        return

    choice = st.radio("What type of cards do you want to generate?", ('LIVE', 'ICONS'))

    if choice == 'LIVE':
        urls_file = 'urls.txt'
        csv_file = 'player_data.csv'
        output_dir = LIVE_CARDS_DIR
    else:
        urls_file = 'iconurls.txt'
        csv_file = 'IconCardData.csv'
        output_dir = ICON_CARDS_DIR

    code = st.text_input("Enter the code")
    if not code:
        st.warning("Please enter a code.")
        return

    # Load previously valid URLs for the given code
    previous_valid_urls = read_previous_valid_urls(code)

    # Read the CSV data
    csv_data = pd.read_csv(csv_file, index_col='ID')

    # Read URLs from the specified file
    urls = read_urls_from_file(urls_file)
    if not urls:
        st.warning("No URLs found in the file.")
        return

    # Check for the background image in the "Card Art" directory
    card_art_dir = 'Card Art'
    background_image_path = os.path.join(card_art_dir, f"{code}.png")  # Assuming the image is named as the code

    if os.path.exists(background_image_path):
        background_image = Image.open(background_image_path)
        st.image(background_image, caption="Background image loaded from Card Art directory.")
    else:
        background_image = st.file_uploader("Upload the card background image", type=["png"])
        if not background_image:
            st.warning("Please upload a background image.")
            return

    if st.button("Process URLs and Generate Cards"):
        st.info("Processing URLs, please wait...")

        # Process URLs while excluding previously valid URLs
        output_data, valid_numbers = asyncio.run(process_urls(urls, code, csv_data, previous_valid_urls))

        # Write valid URLs to the file
        write_valid_urls(code, valid_numbers)

        st.write(f"Valid numbers found: {valid_numbers}")

        image_paths = []
        for player in output_data:
            name = player['Name']
            country = player['Country']
            league = player['League']
            club = player['Club'] if choice == 'LIVE' else None  # No club for ICON cards

            image_path = generate_card_image(name, country, league, club, background_image, output_dir, choice)  # Pass choice as card_type
            if image_path:
                image_paths.append(image_path)

        if image_paths:
            st.success("Player cards generated successfully!")

            # Create collages in batches of 28 images
            collage_paths = []
            for i in range(0, len(image_paths), 28):  # Process in batches of 28
                collage_path = os.path.join(output_dir, f"{event_name}_collage_{i//28 + 1}.png")
                images_batch = [Image.open(image_path) for image_path in image_paths[i:i + 28]]
                create_collage(images_batch, collage_path, event_name=event_name)
                collage_paths.append(collage_path)
                st.image(collage_path)

                # Send each collage to Discord
                asyncio.run(send_collage_to_discord(collage_path))
                st.success(f"Collage {i//28 + 1} sent to Discord successfully!")
        else:
            st.error("No images were generated.")

if __name__ == "__main__":
    main()
