import io
import os
import base64

from PIL import Image, ImageDraw, ImageFont, ImageFilter

from .contacts import JID_REGEXP

# Paths
ROOT_DIR = os.path.join(os.path.dirname(__file__), '..')
FONTS_DIR = os.path.join(ROOT_DIR, 'fonts')
IMAGES_DIR = os.path.join(ROOT_DIR, 'images')

# Style Constants
COLOR_WHITE = "#FFFFFF"
COLOR_WHITE_1 = "#F8F9FA"
COLOR_LIGHT_GRAY = "#E5E5E6"
COLOR_DARK_GRAY = "#808080"
COLOR_PRIMARY_GREEN = "#06D755"
COLOR_SECONDARY_GREEN = "#02D1A4"
COLOR_BLACK = "#000000"
COLOR_SHADOW = (0, 0, 0, 40)
COLOR_GOLD = "#FEE101"
COLOR_SILVER = "#919191"
COLOR_BRONZE = "#A77044"

IMAGE_WIDTH = 1080
IMAGE_HEIGHT = 1920
IMAGE_SIZE = (IMAGE_WIDTH, IMAGE_HEIGHT)
IMAGE_BACKGROUND = COLOR_WHITE_1

HORIZONTAL_PADDING = 80

# Fonts Constants
ROBOTO_FONT_PATH = os.path.join(FONTS_DIR, 'Roboto-Regular.ttf')
ROBOTO_BOLD_FONT_PATH = os.path.join(FONTS_DIR, 'Roboto-Bold.ttf')
PT_TO_PX = 1.3281472327
PT_TO_PX_RATE = 0.9

# Title Constants
TITLE_VERTICAL_MARGIN = 50
TITLE_HORIZONTAL_MARGIN = 35
TITLE_IMAGE_SIZE = 135
TITLE_FONT = ImageFont.truetype(ROBOTO_BOLD_FONT_PATH, 90)
TITLE_COLOR = COLOR_PRIMARY_GREEN

# Card Style Constants
CARD_BACKGROUND = COLOR_WHITE
CARD_CORNER_RADIUS = 10
CARD_SHADOW_BLUR = 10
CARD_SHADOW_COLOR = COLOR_SHADOW


TOP_INSIGHTER_BASE_Y = TITLE_VERTICAL_MARGIN * 2 + TITLE_IMAGE_SIZE

# Top Insighter Constants
TOP_INSIGHTER_CARD_WIDTH = 280
TOP_INSIGHTER_CARD_HEIGHT = 280
TOP_INSIGHTER_CARD_VERTICAL_MARGIN = 60
TOP_INSIGHTER_TITLE_FONT = ImageFont.truetype(ROBOTO_BOLD_FONT_PATH, 40)
TOP_INSIGHTER_TITLE_COLOR = COLOR_PRIMARY_GREEN
TOP_INSIGHTER_TITLE_VERTICAL_MARGIN = 30
TOP_INSIGHTER_CARD_IMAGE_SIZE = 130
TOP_INSIGHTER_CARD_IMAGE_VERTICAL_MARGIN = 20
TOP_INSIGHTER_CARD_TITLE_FONT = ImageFont.truetype(ROBOTO_FONT_PATH, 28)
TOP_INSIGHTER_CARD_TITLE_COLORS = [COLOR_SILVER, COLOR_SILVER, COLOR_SILVER]
TOP_INSIGHTER_CARD_TITLE_VERTICAL_MARGIN = 15
TOP_INSIGHTER_CARD_VALUE_FONT = ImageFont.truetype(ROBOTO_BOLD_FONT_PATH, 28)
TOP_INSIGHTER_CARD_VALUE_COLOR = COLOR_PRIMARY_GREEN
TOP_INSIGHTER_CARD_HORIZONTAL_POSITIONS = [
	HORIZONTAL_PADDING,  # 1nd (left)
	(IMAGE_WIDTH - TOP_INSIGHTER_CARD_WIDTH) // 2,  # 2st (center)
	IMAGE_WIDTH - HORIZONTAL_PADDING - TOP_INSIGHTER_CARD_WIDTH  # 3rd (right)
]

CONTENT_BASE_Y = TOP_INSIGHTER_BASE_Y + TOP_INSIGHTER_CARD_HEIGHT + TOP_INSIGHTER_CARD_VERTICAL_MARGIN * 2

# Insight Card Constants
INSIGHT_CARD_WIDTH = 430
INSIGHT_CARD_HEIGHT = 340
INSIGHT_CARD_LEFT_COLUMN_X = HORIZONTAL_PADDING
INSIGHT_CARD_RIGHT_COLUMN_X = IMAGE_WIDTH - HORIZONTAL_PADDING - INSIGHT_CARD_WIDTH
INSIGHT_CARD_VERTICAL_MARGIN = 60
INSIGHT_CARD_IMAGE_SIZE = 130
INSIGHT_CARD_IMAGE_VERTICAL_MARGIN = 25
INSIGHT_CARD_TITLE_FONT = ImageFont.truetype(ROBOTO_FONT_PATH, 30)
INSIGHT_CARD_TITLE_MAX_LENGTH_PER_LINE = 24
INSIGHT_CARD_TITLE_LINE_SPACING = 5
INSIGHT_CARD_TITLE_COLOR = COLOR_DARK_GRAY
INSIGHT_CARD_TITLE_VERTICAL_MARGIN = 20
INSIGHT_CARD_VALUE_FONT = ImageFont.truetype(ROBOTO_BOLD_FONT_PATH, 30)
INSIGHT_CARD_VALUE_COLOR = COLOR_PRIMARY_GREEN

# Footer Constants
FOOTER_ENABLED = True
FOOTER_BACKGROUND = COLOR_DARK_GRAY
FOOTER_TEXT_COLOR = COLOR_WHITE
FOOTER_HEIGHT = 90
FOOTER_FONT = ImageFont.truetype(ROBOTO_FONT_PATH, 28)

# Text Constants
TITLE_TEXT = 'INSIGHTS'
FOOTER_LINK_TEXT = ''

DEFAULT_PROFILE_IMAGE = Image.open(os.path.join(IMAGES_DIR, 'profile-image.png'))


def get_offset_center(image_size, obj_size):
    return (image_size[0] - obj_size[0]) // 2, (image_size[1] - obj_size[1]) // 2


def get_text_size(text, font, letter_spacing=0):
    width, height = font.getsize(text)
    width += letter_spacing * (len(text) - 1) * 0.75
    return round(width), round(height)

def round_corner(radius, fill):
    corner = Image.new('RGBA', (radius, radius), (0, 0, 0, 0))
    draw = ImageDraw.Draw(corner)
    draw.pieslice((0, 0, radius * 2, radius * 2), 180, 270, fill=fill)
    return corner
 
def round_rectangle(size, radius, fill):
    width, height = size
    rectangle = Image.new('RGBA', size, fill)
    corner = round_corner(radius, fill)
    rectangle.paste(corner, (0, 0))
    rectangle.paste(corner.rotate(90), (0, height - radius)) # Rotate the corner and paste it
    rectangle.paste(corner.rotate(180), (width - radius, height - radius))
    rectangle.paste(corner.rotate(270), (width - radius, 0))
    return rectangle

def drop_shadow(image, offset, border, shadow_color, blur, radius=None):
    width, height = image.size
    
    full_size = image.size[0] + abs(offset[0]) + 2 * border, image.size[1] + abs(offset[1]) + 2 * border
    shadow_image = Image.new('RGBA', full_size, (0, 0, 0, 0))
    shadow_left = border + max(offset[0], 0)
    shadow_top = border + max(offset[1], 0)
    
    shadow_shape = Image.new('RGBA', image.size, shadow_color)
    if radius:
        corner = round_corner(radius, shadow_color)
        shadow_shape.paste(corner, (0, 0))
        shadow_shape.paste(corner.rotate(90), (0, height - radius)) # Rotate the corner and paste it
        shadow_shape.paste(corner.rotate(180), (width - radius, height - radius))
        shadow_shape.paste(corner.rotate(270), (width - radius, 0))

    shadow_image.paste(shadow_shape, (shadow_left, shadow_top))
    
    for _ in range(blur):
        shadow_image = shadow_image.filter(ImageFilter.BLUR)
    
    image_left = border - min(offset[0], 0)
    image_top = border - min(offset[1], 0)

    shadow_image.paste(image, (image_left, image_top), image.convert('RGBA'))

    return shadow_image

def draw_text(image, text, fill, position, font, letter_spacing=0):
    draw = ImageDraw.Draw(image)
    width, height = get_text_size(text, font, letter_spacing)
    
    horizontal, vertical = position
    text_center_offset = get_offset_center(image.size, (width, height))
    horizontal = text_center_offset[0] if horizontal == 'center' else horizontal
    vertical = text_center_offset[1] // 2 if vertical == 'center' else vertical

    drawed_width = 0
    for i, letter in enumerate(text):
        offset = horizontal + drawed_width, vertical
        draw.text(offset, letter, fill=fill, font=font)
        drawed_width += font.getsize(letter)[0] + letter_spacing

def center_text(image, text, font, fill, x=0, y=0, width=None, height=None):
    text_size = font.getsize(text)
    if width:
        x += (width - text_size[0]) // 2
    if height:
        y += (height - text_size[1]) // 2
    return draw_text(image, text, fill, (x, y), font)

def mask_image_by_circle(image):
    mask = Image.new('L', image.size, 0)
    draw = ImageDraw.Draw(mask) 
    draw.ellipse((0, 0) + image.size, fill=255)
    mask = mask.resize(image.size, Image.ANTIALIAS)
    image.putalpha(mask)
    return image

def draw_profile_image(image, profile_image_path, x, y, size):
    profile_image = Image.open(profile_image_path)
    profile_image = mask_image_by_circle(profile_image)
    profile_image = profile_image.resize(size, Image.ANTIALIAS)
    image.paste(profile_image, (x, y), profile_image.convert('RGBA'))

def multiline_text_lines(text, max_length_per_line):
    words = text.split()
    lines = [f'{words[0]} ']
    word = None
    for i in range(1, len(words)):
        word = words[i]
        if '\n' not in word:
            sub_words = word.split("\n");
            if len(lines[-1]) + len(sub_words[0]) > max_length_per_line:
                lines[-1] = lines[-1][0:len(lines[-1]) - 1]
                lines.append('')
            lines[-1] += f'{sub_words[0]} '
            for j in range(1, len(sub_words)):
                lines[-1] = lines[-1][0:len(lines[-1]) - 1]
                lines.append(f'{sub_words[j]} ')
        else:
            if len(lines[-1]) + len(word) > max_length_per_line:
                lines[-1] = lines[-1][0:len(lines[-1]) - 1];
                lines.append('')
            lines[-1] += f'{word} '
    lines[-1] = lines[-1][0:len(lines[-1]) - 1];

    if len(lines[-1]) == 0:
        lines.pop(0)

    return lines

def draw_title(image, profile_image_path=None):
    if profile_image_path:
        text_width, _ = TITLE_FONT.getsize(TITLE_TEXT)
        title_width = TITLE_IMAGE_SIZE + TITLE_HORIZONTAL_MARGIN + text_width
        x = (IMAGE_WIDTH - title_width) // 2
        y = TITLE_VERTICAL_MARGIN - 15  # clearing the edge of the font (15)
        text_x = x + TITLE_IMAGE_SIZE + TITLE_HORIZONTAL_MARGIN

        draw_text(image, TITLE_TEXT.upper(), TITLE_COLOR, (text_x, TITLE_VERTICAL_MARGIN), TITLE_FONT)
        draw_profile_image(image, profile_image_path, x, y, (TITLE_IMAGE_SIZE, TITLE_IMAGE_SIZE))
    else:
        center_text(image, TITLE_TEXT, TITLE_FONT, TITLE_COLOR, y=TITLE_VERTICAL_MARGIN, width=image.size[0])

def draw_insights(image, insighters, contacts, top_insighter=None):
    if top_insighter:
        draw_top_insigther_cards(image, top_insighter, contacts)

    for i, insighter in enumerate(insighters):
        _, profile_image = contacts.get(insighter.winner.jid, (None, None))
        x = INSIGHT_CARD_LEFT_COLUMN_X if i % 2 == 0 else INSIGHT_CARD_RIGHT_COLUMN_X
        y = CONTENT_BASE_Y + i // 2 * (INSIGHT_CARD_HEIGHT + INSIGHT_CARD_VERTICAL_MARGIN)
        draw_insigher_card(image, profile_image or DEFAULT_PROFILE_IMAGE, insighter.title, 
                           insighter.winner.formatted_value, x, y)

def draw_insigher_card(image, profile_image, title, value, x, y):
    draw_card(image, x, y, INSIGHT_CARD_WIDTH, INSIGHT_CARD_HEIGHT)

    title_lines = multiline_text_lines(title, INSIGHT_CARD_TITLE_MAX_LENGTH_PER_LINE)
    content_height = INSIGHT_CARD_IMAGE_SIZE + INSIGHT_CARD_IMAGE_VERTICAL_MARGIN \
        + INSIGHT_CARD_VALUE_FONT.getsize(value)[1] + INSIGHT_CARD_TITLE_VERTICAL_MARGIN \
        + INSIGHT_CARD_TITLE_FONT.getsize(title)[1] + len(title_lines) \
        + INSIGHT_CARD_TITLE_LINE_SPACING * len(title_lines) - 1
    
    content_base_y = y + ((INSIGHT_CARD_HEIGHT - content_height) // 2)
    profile_image_x = x + ((INSIGHT_CARD_WIDTH - INSIGHT_CARD_IMAGE_SIZE) // 2)
    value_y = content_base_y + INSIGHT_CARD_IMAGE_SIZE + INSIGHT_CARD_IMAGE_VERTICAL_MARGIN
    title_x = x + (INSIGHT_CARD_WIDTH // 2)
    title_y = value_y + INSIGHT_CARD_VALUE_FONT.getsize(value)[1] + INSIGHT_CARD_TITLE_VERTICAL_MARGIN \
            + len(title_lines) * (INSIGHT_CARD_TITLE_FONT.getsize(title)[1] // 2)
    
    center_text(image, value, INSIGHT_CARD_VALUE_FONT, INSIGHT_CARD_VALUE_COLOR, 
                x, value_y, width=INSIGHT_CARD_WIDTH)
    
    draw = ImageDraw.Draw(image)
    draw.multiline_text((title_x, title_y), text='\n'.join(title_lines), fill=INSIGHT_CARD_TITLE_COLOR,
                        font=INSIGHT_CARD_TITLE_FONT, anchor='mm', spacing=INSIGHT_CARD_TITLE_LINE_SPACING, 
                        align='center')
    profile_image = mask_image_by_circle(profile_image)
    profile_image = profile_image.resize((INSIGHT_CARD_IMAGE_SIZE, INSIGHT_CARD_IMAGE_SIZE), Image.ANTIALIAS)
    image.paste(profile_image, (profile_image_x, content_base_y), profile_image.convert('RGBA'))

def draw_top_insigther_cards(image, insighter, contacts):
    title = insighter.title.upper()
    draw_text(image, title, TOP_INSIGHTER_TITLE_COLOR, 
              (HORIZONTAL_PADDING, TOP_INSIGHTER_BASE_Y), TOP_INSIGHTER_TITLE_FONT)
    
    title_height = TOP_INSIGHTER_TITLE_FONT.getsize(title)[1]
    cards_base_y = (TOP_INSIGHTER_BASE_Y + title_height + TOP_INSIGHTER_TITLE_VERTICAL_MARGIN)

    rank = insighter.get_rank()[:3]
    for i, rank_item in enumerate(rank):
        display_name, profile_image = contacts[rank_item.jid]
        person_name = display_name.split(' ', 1)[0] if display_name else JID_REGEXP.search(rank_item.jid).group(1)
        title = f'{i + 1}º {person_name}'
        title_color = TOP_INSIGHTER_CARD_TITLE_COLORS[i]
        x = TOP_INSIGHTER_CARD_HORIZONTAL_POSITIONS[i]
        draw_top_insigther_card(image, profile_image or DEFAULT_PROFILE_IMAGE, title, title_color, 
                                rank_item.formatted_value, x, cards_base_y)


def draw_top_insigther_card(image, profile_image, title, title_color, value, x, y):
    draw_card(image, x, y, TOP_INSIGHTER_CARD_WIDTH, TOP_INSIGHTER_CARD_HEIGHT)

    content_height = TOP_INSIGHTER_CARD_IMAGE_SIZE + TOP_INSIGHTER_CARD_IMAGE_VERTICAL_MARGIN \
        + TOP_INSIGHTER_CARD_VALUE_FONT.getsize(value)[1] + TOP_INSIGHTER_CARD_TITLE_VERTICAL_MARGIN \
        + TOP_INSIGHTER_CARD_TITLE_FONT.getsize(title)[1]
    
    content_base_y = y + ((TOP_INSIGHTER_CARD_HEIGHT - content_height) // 2)
    profile_image_x = x + ((TOP_INSIGHTER_CARD_WIDTH - TOP_INSIGHTER_CARD_IMAGE_SIZE) // 2)
    value_y = content_base_y + TOP_INSIGHTER_CARD_IMAGE_SIZE + TOP_INSIGHTER_CARD_IMAGE_VERTICAL_MARGIN
    title_y = value_y + TOP_INSIGHTER_CARD_VALUE_FONT.getsize(value)[1] + TOP_INSIGHTER_CARD_TITLE_VERTICAL_MARGIN
    
    center_text(image, value, TOP_INSIGHTER_CARD_VALUE_FONT, TOP_INSIGHTER_CARD_VALUE_COLOR, 
                x, value_y, width=TOP_INSIGHTER_CARD_WIDTH)
    center_text(image, title, TOP_INSIGHTER_CARD_TITLE_FONT, title_color, 
                x, title_y, width=TOP_INSIGHTER_CARD_WIDTH)
    
    profile_image = mask_image_by_circle(profile_image)
    profile_image = profile_image.resize((INSIGHT_CARD_IMAGE_SIZE, INSIGHT_CARD_IMAGE_SIZE), Image.ANTIALIAS)
    image.paste(profile_image, (profile_image_x, content_base_y), profile_image.convert('RGBA'))


def draw_card(image, x, y, width, height):
    card = round_rectangle((width, height), CARD_CORNER_RADIUS, CARD_BACKGROUND)
    shadow_border = CARD_SHADOW_BLUR
    card = drop_shadow(card, (0, 0), shadow_border, CARD_SHADOW_COLOR, CARD_SHADOW_BLUR, radius=CARD_CORNER_RADIUS)
    image.paste(card, (x - shadow_border, y - shadow_border), card.convert('RGBA'))

def draw_footer(image):
    draw = ImageDraw.Draw(image)
    footer_y = IMAGE_HEIGHT - FOOTER_HEIGHT
    
    footer_bounds = 0, footer_y, IMAGE_WIDTH, IMAGE_HEIGHT + FOOTER_HEIGHT
    draw.rectangle(footer_bounds, fill=FOOTER_BACKGROUND)
    
    draw.text((HORIZONTAL_PADDING, IMAGE_HEIGHT - (FOOTER_HEIGHT // 2)), 
              text=FOOTER_LINK_TEXT, font=FOOTER_FONT, fill=FOOTER_TEXT_COLOR, 
              anchor='lm')

def create_insights_image(insighters, contacts, profile_image_path=None, top_insighter=None, output_path='insights.png'):
    image = Image.new('RGBA', IMAGE_SIZE, color=IMAGE_BACKGROUND)

    draw_title(image, profile_image_path)
    
    draw_insights(image, insighters, contacts, top_insighter)

    if FOOTER_ENABLED:
        draw_footer(image)
    
    image.save(output_path, 'PNG')
