import io
import os
import cv2
import tqdm
import math
import base64
import random
import logging
import colorsys
import datetime
import collections

import numpy as np

from . import utils
from .contacts import Contact, JID_REGEXP

from PIL import Image, ImageDraw, ImageFont

# Paths
ROOT_DIR = os.path.join(os.path.dirname(__file__), '..')
FONTS_DIR = os.path.join(ROOT_DIR, 'fonts')
IMAGES_DIR = os.path.join(ROOT_DIR, 'images')

# Style Constants
COLOR_WHITE = '#FFFFFF'
COLOR_WHITE_1 = '#F8F9FA'
COLOR_LIGHT_GRAY = '#E5E5E6'
COLOR_DARK_GRAY = '#808080'
COLOR_DARK_GRAY_1 = '#505050'
COLOR_DARK_GRAY_2 = '#151515'

IMAGE_WIDTH = 1920
IMAGE_HEIGHT = 1080
IMAGE_MODE = 'RGBA'
IMAGE_SIZE = (IMAGE_WIDTH, IMAGE_HEIGHT)
IMAGE_BACKGROUND = COLOR_WHITE_1
DEFAULT_LANGUAGE = 'pt'

RESOLUTION_FACTOR  = 1920 / 1920

HORIZONTAL_PADDING = round(80 * RESOLUTION_FACTOR)
VERTICAL_PADDING = round(30 * RESOLUTION_FACTOR)

# Fonts Constants
ROBOTO_FONT_PATH = os.path.join(FONTS_DIR, 'Roboto-Regular.ttf')
ROBOTO_BOLD_FONT_PATH = os.path.join(FONTS_DIR, 'Roboto-Bold.ttf')
ROBOTO_LIGHT_FONT_PATH = os.path.join(FONTS_DIR, 'Roboto-Light.ttf')
PT_TO_PX = 1.3281472327
PT_TO_PX_RATE = 0.9

# Title text
TITLE_TEXT = 'CHART RACE'
TITLE_COLOR = COLOR_DARK_GRAY_1
TITLE_TEXT_SIZE = round(70 * RESOLUTION_FACTOR)
TITLE_TEXT_FONT = ImageFont.truetype(ROBOTO_BOLD_FONT_PATH, TITLE_TEXT_SIZE)
TITLE_BASE_Y = VERTICAL_PADDING

# Axis constants
AXIS_COLOR = COLOR_DARK_GRAY_1
AXIS_STROKE_WIDTH = 4

# Chart bar constants
CHART_BAR_TOTAL_USERS = 10
CHART_BAR_HEIGHT = round(57 * RESOLUTION_FACTOR)
CHART_BAR_VERTICAL_MARGIN = round(27 * RESOLUTION_FACTOR)
CHART_BAR_LABEL_COLOR = COLOR_DARK_GRAY_2
CHART_BAR_LABEL_MARGIN = round(20 * RESOLUTION_FACTOR)
CHART_BAR_LABEL_VERTICAL_PADDING = round(10 * RESOLUTION_FACTOR)
CHART_BAR_LABEL_HORIZONTAL_PADDING = round(20 * RESOLUTION_FACTOR)
CHART_BAR_LABEL_TEXT_SIZE = round(25 * RESOLUTION_FACTOR)
CHART_BAR_LABEL_TEXT_FONT = ImageFont.truetype(ROBOTO_LIGHT_FONT_PATH, CHART_BAR_LABEL_TEXT_SIZE)
CHART_BAR_LABEL_TEXT_COLOR = COLOR_WHITE
CHART_BAR_VALUE_TEXT_SIZE = round(27 * RESOLUTION_FACTOR)
CHART_BAR_VALUE_TEXT_FONT = ImageFont.truetype(ROBOTO_FONT_PATH, CHART_BAR_VALUE_TEXT_SIZE)
CHART_BAR_VALUE_TEXT_COLOR = COLOR_DARK_GRAY_2
CHART_BAR_VALUE_MARGIN = round(10 * RESOLUTION_FACTOR)

# Random color range
CHART_BAR_COLOR_HUE_RANGE = [0.35, 0.45]
CHART_BAR_COLOR_SATURATION_RANGE = [0.4, 0.55]
CHART_BAR_COLOR_BRIGHTNESS_RANGE = [0.2, 0.5]
MAX_CONTACT_BAR_COLOR_BRIGHTNESS = 0.6
MIN_CONTACT_BAR_COLOR_SATURATION = 0.6

# Chart constants
CHART_WIDTH = round(1200 * RESOLUTION_FACTOR)
CHART_HEIGHT = CHART_BAR_TOTAL_USERS * CHART_BAR_HEIGHT + (CHART_BAR_TOTAL_USERS - 1) * CHART_BAR_VERTICAL_MARGIN

# Grid constants
GRID_TOTAL_COLUMNS = 8
GRID_COLOR = COLOR_LIGHT_GRAY
GRID_STROKE_WIDTH = 1
GRID_SCALE_VERTICAL_MARGIN = round(20 * RESOLUTION_FACTOR)
GRID_SCALE_TEXT_SIZE = round(25 * RESOLUTION_FACTOR)
GRID_SCALE_TEXT_COLOR = COLOR_DARK_GRAY_1
GRID_SCALE_TEXT_FONT = ImageFont.truetype(ROBOTO_FONT_PATH, GRID_SCALE_TEXT_SIZE)
GRID_SCALE_TEXT_MARGIN = round(10 * RESOLUTION_FACTOR)
GRID_SCALE_BASE_Y = TITLE_BASE_Y + TITLE_TEXT_SIZE + GRID_SCALE_VERTICAL_MARGIN

GRID_MIN_SCALE = 1500
GRID_FIRST_USER_SCALE_FACTOR = 1.10
GRID_SCALE_ANIMATION = [[2, 1], [5, 2], [10, 4], [20, 10]] # [Divisors, Limits to the divisors] 

# Chart position
CHART_BASE_X = (IMAGE_WIDTH - CHART_WIDTH) // 2 + AXIS_STROKE_WIDTH
CHART_BASE_Y = GRID_SCALE_BASE_Y + GRID_SCALE_TEXT_SIZE + GRID_SCALE_VERTICAL_MARGIN

# Date text
DATE_TEXT_SIZE = 60
DATE_FONT = ImageFont.truetype(ROBOTO_BOLD_FONT_PATH, DATE_TEXT_SIZE)
DATE_COLOR = COLOR_DARK_GRAY

VIDEO_FRAME_RATE = 60
VIDEO_END_FREEZE_TIME = 5
DEFAULT_DAYS_PER_SECOND = 5
ANIMATION_SMOOTHNESS = 1  # The higher the smoothness, the less accurate the amount of messages on the time scale
VIDEO_SPEED = 1  # Drop frames
SCALE_GROWTH_RATE = 1

DEFAULT_PROFILE_IMAGE = Image.open(os.path.join(IMAGES_DIR, 'profile-image.png'))
DATE_FORMAT = '%b %Y'

ContactBar = collections.namedtuple('ContactBar', ['contact_name', 'value', 'profile_image', 'color'])

create_frame_cache_data = {'image': None, 'date': None}

class PodiumUser:
    def __init__(self, contact, value):
        self.contact = contact
        self.value = value


class Podium:
    def __init__(self, contacts):
        self._podium_users = dict()
        self._podium = []
        self._sorted = False
        for contact in contacts:
            podium_user = PodiumUser(contact, 0)
            self._podium.append(podium_user)
            self._podium_users[contact.jid] = podium_user

    def __getitem__(self, index):
        if not self._sorted:
            self._podium.sort(reverse=True, key=lambda user: user.value)
            self._sorted = True
        return self._podium[index]

    def increment_user_messages(self, jid, increment):
        self._podium_users[jid].value += increment
        self._sorted = False


def get_offset_center(image_size, obj_size):
    return (image_size[0] - obj_size[0]) // 2, (image_size[1] - obj_size[1]) // 2


def get_text_size(text, font, letter_spacing=0):
    width, height = font.getsize(text)
    width += letter_spacing * (len(text) - 1) * 0.75
    return round(width), round(height)


def center_text(image, text, font, fill, x, y, width=None, height=None):
    text_size = font.getsize(text)
    if width:
        x += (width - text_size[0]) // 2
    if height:
        y += (height - text_size[1]) // 2
    return draw_text(image, text, fill, (x, y), font)


def round_corner(radius, fill):
    corner = Image.new(IMAGE_MODE, (radius, radius), (0, 0, 0, 0))
    draw = ImageDraw.Draw(corner)
    draw.pieslice((0, 0, radius * 2, radius * 2), 180, 270, fill=fill)
    return corner


def round_rectangle(size, radius, fill):
    width, height = size
    rectangle = Image.new(IMAGE_MODE, size, fill)
    corner = round_corner(radius, fill)
    rectangle.paste(corner, (0, 0))
    rectangle.paste(corner.rotate(90), (0, height - radius)) # Rotate the corner and paste it
    rectangle.paste(corner.rotate(180), (width - radius, height - radius))
    rectangle.paste(corner.rotate(270), (width - radius, 0))
    return rectangle


def mask_image_by_circle(image):
    mask = Image.new('L', image.size, 0)
    draw = ImageDraw.Draw(mask) 
    draw.ellipse((0, 0) + image.size, fill=255)
    mask = mask.resize(image.size, Image.ANTIALIAS)
    image.putalpha(mask)
    return image


def create_profile_image(profile_image, size):
    if isinstance(profile_image, str):
        profile_image = Image.open(profile_image)
    profile_image = mask_image_by_circle(profile_image)
    profile_image = profile_image.resize(size, Image.ANTIALIAS)
    return profile_image


def scale_user_bar_with(value, scale):
    return max((CHART_WIDTH / scale) * value, CHART_BAR_HEIGHT)


def choose_contact_bar_color(contact):
    if not contact.profile_image:
        return random_color(CHART_BAR_COLOR_HUE_RANGE, CHART_BAR_COLOR_SATURATION_RANGE, CHART_BAR_COLOR_BRIGHTNESS_RANGE)
    image = Image.open(io.BytesIO(base64.b64decode(contact.profile_image)))
    total_pixels = image.size[0] * image.size[1]
    dominant_color = max([c for c in image.getcolors(total_pixels) if len(c[1]) >= 3 or c[1][3] >= 70], key=lambda c: c[0])[1]
    dominant_color = [c / 255 for c in dominant_color]
    dominant_color = [dominant_color[i] for i in range(3)]  # remove alpha if it's present
    hue, saturation, brightness = colorsys.rgb_to_hsv(*dominant_color)
    r, g, b = colorsys.hsv_to_rgb(hue, max(saturation, MIN_CONTACT_BAR_COLOR_SATURATION), min(brightness, MAX_CONTACT_BAR_COLOR_BRIGHTNESS))
    return int(r * 256), int(g * 256), int(b * 256)


def random_color(hue_range, saturation_range, brightness_range):
    hue = random.uniform(*hue_range)
    saturation = random.uniform(*saturation_range)
    brightness_range = random.uniform(*brightness_range)
    r, g, b = colorsys.hsv_to_rgb(hue, saturation, brightness_range)
    return int(r * 256), int(g * 256), int(b * 256)


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


def draw_title(image):
    center_text(image, TITLE_TEXT, TITLE_TEXT_FONT, TITLE_COLOR, 
                0, TITLE_BASE_Y, width=IMAGE_WIDTH)


def draw_date(image, date):
    text = date.strftime(DATE_FORMAT).upper()
    width, height = get_text_size(text, DATE_FONT)
    x = IMAGE_WIDTH - width - HORIZONTAL_PADDING
    y = IMAGE_HEIGHT - VERTICAL_PADDING - height
    draw_text(image, text, DATE_COLOR, (x, y), DATE_FONT)


def draw_scale(image, scale):
    scale = int(scale)
    
    scale_ten_power = 10 ** (len(str(scale)) - 1)
    divisor = 0

    for base_divisor, base_limit in GRID_SCALE_ANIMATION:
        if scale <= base_limit * scale_ten_power:
            divisor = base_divisor * scale_ten_power / 10
            break

    total_markers = math.floor(scale / divisor)

    draw = ImageDraw.Draw(image)

    grid_unit_width = CHART_WIDTH / (scale / divisor)
    for c in range(total_markers + 1):
        x = CHART_BASE_X + grid_unit_width * c
        value = int(c * divisor)
        text = '{:,}'.format(value)
        text_width, text_height = get_text_size(text, GRID_SCALE_TEXT_FONT)
        draw_text(image, text, GRID_SCALE_TEXT_COLOR, (x - text_width // 2, GRID_SCALE_BASE_Y), GRID_SCALE_TEXT_FONT)
        x1 = x2 = x
        y1 = GRID_SCALE_BASE_Y + text_height + GRID_SCALE_TEXT_MARGIN 
        y2 = CHART_BASE_Y + CHART_HEIGHT
        draw.line([x1, y1, x2, y2], GRID_COLOR, GRID_STROKE_WIDTH)


def draw_contact_bar(image, x, y, width, profile_image, contact_name, value, color, resize_profile_image=True):
    x -= CHART_BAR_LABEL_MARGIN

    # Label
    text_width, text_height = get_text_size(contact_name, CHART_BAR_LABEL_TEXT_FONT)

    label_height = text_height + CHART_BAR_LABEL_VERTICAL_PADDING * 2
    label_width = text_width + CHART_BAR_LABEL_HORIZONTAL_PADDING * 2
    label_x = x - label_width
    label_y = y + (CHART_BAR_HEIGHT - label_height) / 2

    draw = ImageDraw.Draw(image)
    draw.rectangle((label_x, label_y, label_x + label_width, label_y + label_height), fill=CHART_BAR_LABEL_COLOR)

    center_text(image, contact_name, CHART_BAR_LABEL_TEXT_FONT, CHART_BAR_LABEL_TEXT_COLOR,
                label_x, label_y, label_width, label_height)
    
    x += CHART_BAR_LABEL_MARGIN

    # Bar
    radius = CHART_BAR_HEIGHT // 2
    bar = round_rectangle((width, CHART_BAR_HEIGHT), radius, color)
    image.paste(bar, (x, y), bar.convert(IMAGE_MODE))

    # Value
    text_x = x + width + CHART_BAR_VALUE_MARGIN
    text_y = y + (CHART_BAR_HEIGHT - text_height) / 2
    draw_text(image, '{:,}'.format(value), CHART_BAR_VALUE_TEXT_COLOR, 
              (text_x, text_y), CHART_BAR_VALUE_TEXT_FONT)
    
    # User profile image
    if resize_profile_image:
        profile_image = create_profile_image(profile_image, (CHART_BAR_HEIGHT, CHART_BAR_HEIGHT))
    image.paste(profile_image, (x + width - CHART_BAR_HEIGHT, y), profile_image.convert(IMAGE_MODE))


def frame(contacts_bars, scale, date, resize_profile_image=True):
    global create_frame_cache_data

    if create_frame_cache_data['date'] != date:
        image = Image.new(IMAGE_MODE, IMAGE_SIZE, color=IMAGE_BACKGROUND)
        draw_title(image)
        draw_date(image, date)
        create_frame_cache_data['date'] = date
        create_frame_cache_data['image'] = image

    image = create_frame_cache_data['image'].copy()

    draw_scale(image, scale)

    for i, contact_bar in enumerate(contacts_bars):
        bar_width = int(scale_user_bar_with(contact_bar.value, scale))
        y = CHART_BASE_Y + i * (CHART_BAR_HEIGHT + CHART_BAR_VERTICAL_MARGIN)
        draw_contact_bar(image, CHART_BASE_X, y, bar_width, contact_bar.profile_image, contact_bar.contact_name, 
                         contact_bar.value, contact_bar.color, resize_profile_image=resize_profile_image)

    return image


def generate_frame_data(podium, profile_images, contact_colors, last_scale):
    contacts_bars = []
    for i in range(CHART_BAR_TOTAL_USERS):
        if podium[i].value == 0:
            break
        podium_user = podium[i]
        display_name = podium_user.contact.display_name or f'+{JID_REGEXP.search(podium_user.contact.jid).group(1)}'
        value = int(podium_user.value)
        profile_image = profile_images[podium_user.contact.jid]
        contact_color = contact_colors[podium_user.contact.jid]
        contact_bar = ContactBar(display_name, value, profile_image, contact_color)
        contacts_bars.append(contact_bar)
    
    first_user_based_scale = podium[0].value * GRID_FIRST_USER_SCALE_FACTOR
    scale = max(GRID_MIN_SCALE, first_user_based_scale, last_scale * SCALE_GROWTH_RATE)

    return contacts_bars, scale

def generate_video_frames(messages, start_date, frame_step_timedelta,
                          podium, profile_images, contact_colors):
    frame_image = None
    scale = GRID_MIN_SCALE
    current_date = start_date
    group_message_range_timedelta = datetime.timedelta(days=7 * ANIMATION_SMOOTHNESS)
    next_step_date = current_date + group_message_range_timedelta
    frames_by_group = group_message_range_timedelta // frame_step_timedelta
    user_total_messages = dict()
    drop_counter = 0
    drop_increment = (1 / (1 - VIDEO_SPEED)) if VIDEO_SPEED != 1 else 0
    for message in messages:
        if message.date < next_step_date:
            user_total_messages.setdefault(message.remote_jid, 0)
            user_total_messages[message.remote_jid] += 1
        else:
            for remote_jid in user_total_messages:
                user_total_messages[remote_jid] = user_total_messages[remote_jid] / frames_by_group

            for _ in range(frames_by_group):
                for remote_jid in user_total_messages:
                    podium.increment_user_messages(remote_jid, user_total_messages[remote_jid])

                if drop_counter < 1:
                    contacts_bars, scale = generate_frame_data(podium, profile_images, contact_colors, scale)
                    frame_image = frame(contacts_bars, scale, current_date, resize_profile_image=False)
                    drop_counter += drop_increment
                else:
                    drop_counter -= 1

                yield frame_image
                
            current_date += group_message_range_timedelta
            next_step_date = current_date + group_message_range_timedelta
            user_total_messages = dict()

    # TODO: Last messages aren't being included

    if frame_image:
        for _ in range(VIDEO_END_FREEZE_TIME * VIDEO_FRAME_RATE):
            yield frame_image

def group_messages_by_contact_name(contact_manager, sorted_messages):
    messages = list(sorted_messages)
    contact_name_most_recent = dict()
    for message in messages:
        contact = contact_manager.get(message.remote_jid)
        if contact.display_name:
            for c in contact_manager.get_contacts_by_display_name(contact.display_name):
                contact_name_most_recent[c.jid] = contact
    
    for message in messages:
        if message.remote_jid in contact_name_most_recent:
            message.remote_jid = contact_name_most_recent[message.remote_jid].jid
    
    return messages


def create_chart_race_video(contact_manager, message_manager, output, locale_='en_US.UTF-8',
                            group_contact_by_name=True, exclude_no_display_name_contacts=False):
    logging.info('Sorting messages by date...')
    sorted_messages = list(message_manager)
    sorted_messages.sort(key=lambda message: message.date)
    logging.info('Messages sorted!')

    logging.info('Excluding groups...')
    messages = []
    for message in sorted_messages:
        if Contact.is_user(message.remote_jid):
            contact = contact_manager.get(message.remote_jid)
            if (not exclude_no_display_name_contacts or (contact and contact.display_name)):
                messages.append(message)

    if group_contact_by_name:
        logging.info('Grouping contacts by name...')
        messages = group_messages_by_contact_name(contact_manager, messages)

    logging.info('Rendering profile images...')
    profile_images = dict()
    contact_colors = dict()
    for contact in contact_manager.get_users():
        if contact.profile_image:
            profile_images[contact.jid] = Image.open(io.BytesIO(base64.b64decode(contact.profile_image)))
        else:
            profile_images[contact.jid] = DEFAULT_PROFILE_IMAGE
        profile_images[contact.jid] = create_profile_image(profile_images[contact.jid], (CHART_BAR_HEIGHT, CHART_BAR_HEIGHT))
        contact_colors[contact.jid] = choose_contact_bar_color(contact)

    start_date = messages[0].date
    end_date = messages[-1].date

    elapsed_timestamp_by_frame = (86400 * DEFAULT_DAYS_PER_SECOND) / VIDEO_FRAME_RATE

    podium = Podium(contact_manager.get_users())
    
    logging.info('Rendering video...')
    total_frames = (end_date - start_date).total_seconds() / elapsed_timestamp_by_frame
    fourcc = cv2.VideoWriter.fourcc(*'mp4v')
    video_writer = cv2.VideoWriter(output, fourcc, VIDEO_FRAME_RATE, IMAGE_SIZE)
    frame_step_timedelta = datetime.timedelta(seconds=elapsed_timestamp_by_frame)
    with utils.context_locale(locale_):
        frames = generate_video_frames(messages, start_date, frame_step_timedelta, podium, profile_images, contact_colors)
        tqdm_iterator = tqdm.tqdm(frames, total=total_frames)
        try:
            for frame in tqdm_iterator:
                cv_image = cv2.cvtColor(np.array(frame), cv2.COLOR_RGBA2BGR)
                video_writer.write(cv_image)
        finally:
            video_writer.release()
