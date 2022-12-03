import io
import os
import cv2
import tqdm
import math
import base64
import random
import typing
import logging
import colorsys
import datetime
import calendar
import dataclasses

import numpy as np

from . import utils
from .contacts import Contact, JID_REGEXP

from PIL import Image, ImageDraw, ImageFont

# Paths
ROOT_DIR = os.path.join(os.path.dirname(__file__), '..')
FONTS_DIR = os.path.join(ROOT_DIR, 'fonts')
IMAGES_DIR = os.path.join(ROOT_DIR, 'images')

# Style Constants
COLOR_WHITE = 255, 255, 255, 255
COLOR_WHITE_1 = 248, 249, 250, 255
COLOR_LIGHT_GRAY = 229, 229, 230, 255
COLOR_DARK_GRAY = 128, 128, 128, 255
COLOR_DARK_GRAY_1 = 80, 80, 80, 255
COLOR_DARK_GRAY_2 = 21, 21, 21, 255

IMAGE_WIDTH = 1920
IMAGE_HEIGHT = 1080
IMAGE_MODE = 'RGBA'
IMAGE_SIZE = IMAGE_WIDTH, IMAGE_HEIGHT
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
CHART_BAR_HEIGHT_AND_MARGIN = CHART_BAR_HEIGHT + CHART_BAR_VERTICAL_MARGIN

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

# Video settings
VIDEO_FRAME_RATE = 60
VIDEO_END_FREEZE_TIME = 5
DEFAULT_DAYS_PER_SECOND = 5
VIDEO_SPEED = 4  # x4 (drop frames)
ELAPSED_TIMESTAMP_BY_FRAME = (86400 * DEFAULT_DAYS_PER_SECOND) / VIDEO_FRAME_RATE

# Animation settings
SCALE_GROWTH_RATE = 1
ANIMATION_SMOOTHNESS = 1  # The higher the smoothness, the less accurate the amount of messages on the time scale

# Date transition animation settings
DATE_TRANSITION_DURATION = 0.7
DATE_TRANSITION_TOTAL_FRAMES = math.ceil(DATE_TRANSITION_DURATION * VIDEO_FRAME_RATE)
DATE_TRANSITION_Y_OFFSET = 50
DATE_TRANSITION_Y_OFFSET_STEP = DATE_TRANSITION_Y_OFFSET / (DATE_TRANSITION_DURATION * VIDEO_FRAME_RATE)
DATE_TRANSITION_OPACITY_STEP = 1 / (DATE_TRANSITION_DURATION * VIDEO_FRAME_RATE)

# Chart bar transition animation settings
CHART_BAR_TRANSITION_DURATION = 0.4 
CHART_BAR_TRANSITION_TOTAL_FRAMES = math.ceil(CHART_BAR_TRANSITION_DURATION * VIDEO_FRAME_RATE)
CHART_BAR_FADE_IN_Y = CHART_BASE_Y + ((CHART_BAR_TOTAL_USERS - 1) * CHART_BAR_HEIGHT_AND_MARGIN) + 1
CHART_BAR_FADE_OUT_MAX_Y = CHART_BASE_Y + CHART_HEIGHT + CHART_BAR_HEIGHT_AND_MARGIN

DEFAULT_PROFILE_IMAGE = Image.open(os.path.join(IMAGES_DIR, 'profile-image.png'))
DATE_FORMAT = '%b %Y'


@dataclasses.dataclass
class ContactBar:
    color: typing.Tuple[int, int, int]
    contact_name: str = None
    value: float = 0
    profile_image: Image = None


@dataclasses.dataclass
class PodiumUser:
    contact: Contact
    value: float

    def __hash__(self):
        return hash(f'_____{self.__class__.__name__}_____{self.contact.jid}_____')


@dataclasses.dataclass
class ContactBarAnimationState:
    podium_index: int
    contact_bar: ContactBar
    position: typing.Tuple[int, int] = (0, 0)
    final_position: typing.Tuple[int, int] = (0, 0)
    layer: int = 0
    opacity: float = 1
    left_frames: int = 0 


@dataclasses.dataclass
class AnimationState:
    current_frame: int = 0
    scale: float = GRID_MIN_SCALE
    base_image: Image = None
    current_date: datetime.datetime = None
    group_message_range_timedelta: datetime.timedelta = None
    frame_step_timedelta: datetime.timedelta = None
    date_transition_start_frame: int = None
    contact_bar_states: typing.Dict[PodiumUser, ContactBarAnimationState] = dataclasses.field(default_factory=lambda: {})


class Podium:
    def __init__(self, contacts):
        self._podium_users = dict()
        self._podium = []
        self._sorted = False
        for contact in contacts:
            podium_user = PodiumUser(contact, 0)
            self._podium.append(podium_user)
            self._podium_users[contact.jid] = podium_user

    def __len__(self):
        return len(self._podium)
    
    def __iter__(self):
        if not self._sorted:
            self._podium.sort(reverse=True, key=lambda user: user.value)
            self._sorted = True
        return iter(self._podium)

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


def mask_image_by_circle(image, opacity=1):
    mask = Image.new('L', image.size, 0)
    draw = ImageDraw.Draw(mask) 
    draw.ellipse((0, 0) + image.size, fill=max(0, min(255, int(opacity * 255))))
    mask = mask.resize(image.size, Image.ANTIALIAS)
    image.putalpha(mask)
    return image


def create_profile_image(profile_image, size, opacity=1):
    if isinstance(profile_image, str):
        profile_image = Image.open(profile_image)
    profile_image = mask_image_by_circle(profile_image, opacity)
    profile_image = profile_image.resize(size, Image.ANTIALIAS)
    return profile_image


def scale_user_bar_with(value, scale):
    return max((CHART_WIDTH / scale) * value, CHART_BAR_HEIGHT)


def color_opacity(color, opacity):
    opacity = max(0, min(255, int(opacity * 255)))
    return color[:3] + (opacity,)


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
    return int(r * 256), int(g * 256), int(b * 256), 255


def random_color(hue_range, saturation_range, brightness_range):
    hue = random.uniform(*hue_range)
    saturation = random.uniform(*saturation_range)
    brightness_range = random.uniform(*brightness_range)
    r, g, b = colorsys.hsv_to_rgb(hue, saturation, brightness_range)
    return int(r * 256), int(g * 256), int(b * 256), 255


def draw_text(image, text, fill, position, font, letter_spacing=0):
    width, height = get_text_size(text, font, letter_spacing)
    width, height = int(width), int(height)

    text_placeholder = Image.new('RGBA', (width, height), (255, 255, 255, 0))
    draw = ImageDraw.Draw(text_placeholder)

    x, y = position
    text_center_offset = get_offset_center(image.size, (width, height))
    x = text_center_offset[0] if x == 'center' else x
    y = text_center_offset[1] // 2 if y == 'center' else y

    x, y = int(x), int(y)

    drawed_width = 0
    for _, letter in enumerate(text):
        draw.text((drawed_width, 0), letter, fill=fill, font=font)
        drawed_width += font.getsize(letter)[0] + letter_spacing

    image.paste(text_placeholder, (x, y), mask=text_placeholder)


def draw_title(image):
    center_text(image, TITLE_TEXT, TITLE_TEXT_FONT, TITLE_COLOR, 
                0, TITLE_BASE_Y, width=IMAGE_WIDTH)


def draw_date(image, date, y_offset=0, opacity=1):
    opacity = int(max(0, min(255, opacity * 255)))
    color = DATE_COLOR[:3] + (opacity,)
    text = date.strftime(DATE_FORMAT).upper()
    width, height = get_text_size(text, DATE_FONT)
    x = IMAGE_WIDTH - width - HORIZONTAL_PADDING
    y = IMAGE_HEIGHT - VERTICAL_PADDING - height + y_offset
    draw_text(image, text, color, (x, y), DATE_FONT)


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


def draw_contact_bar(image, x, y, width, profile_image, contact_name, value, color, opacity):
    x -= CHART_BAR_LABEL_MARGIN

    # Label
    text_width, text_height = get_text_size(contact_name, CHART_BAR_LABEL_TEXT_FONT)

    label_height = text_height + CHART_BAR_LABEL_VERTICAL_PADDING * 2
    label_width = text_width + CHART_BAR_LABEL_HORIZONTAL_PADDING * 2
    label_x = x - label_width
    label_y = y + (CHART_BAR_HEIGHT - label_height) // 2

    text_box = round_rectangle((label_width, label_height), 0, color_opacity(CHART_BAR_LABEL_COLOR, opacity))
    image.paste(text_box, (label_x, label_y), text_box.convert(IMAGE_MODE))
    
    center_text(image, contact_name, CHART_BAR_LABEL_TEXT_FONT, color_opacity(CHART_BAR_LABEL_TEXT_COLOR, opacity),
                label_x, label_y, label_width, label_height)
    
    x += CHART_BAR_LABEL_MARGIN

    # Bar
    radius = CHART_BAR_HEIGHT // 2
    bar = round_rectangle((width, CHART_BAR_HEIGHT), radius, color_opacity(color, opacity))
    image.paste(bar, (x, y), bar.convert(IMAGE_MODE))

    # Value
    text_x = x + width + CHART_BAR_VALUE_MARGIN
    text_y = y + (CHART_BAR_HEIGHT - text_height) / 2
    draw_text(image, '{:,}'.format(value), color_opacity(CHART_BAR_VALUE_TEXT_COLOR, opacity), 
              (text_x, text_y), CHART_BAR_VALUE_TEXT_FONT)
    
    if opacity < 1:
        profile_image = create_profile_image(profile_image, (CHART_BAR_HEIGHT, CHART_BAR_HEIGHT), opacity)

    image.paste(profile_image, (x + width - CHART_BAR_HEIGHT, y), profile_image.convert(IMAGE_MODE))


def frame_generate_base_image():
    image = Image.new(IMAGE_MODE, IMAGE_SIZE, color=IMAGE_BACKGROUND)
    draw_title(image)
    return image


def frame_handle_date_transition(image, animation_state):
    current_month_last_day = calendar.monthrange(animation_state.current_date.year, animation_state.current_date.month)[1]
    next_month = datetime.datetime(year=animation_state.current_date.year, month=animation_state.current_date.month, day=current_month_last_day)
    next_month += datetime.timedelta(days=1)
    remaining_frames_to_next_month = math.ceil((next_month - animation_state.current_date) / animation_state.frame_step_timedelta)
    is_month_close_to_change = remaining_frames_to_next_month <= DATE_TRANSITION_TOTAL_FRAMES
    
    if not animation_state.date_transition_start_frame and is_month_close_to_change:
        animation_state.date_transition_start_frame = animation_state.current_frame
    
    if animation_state.date_transition_start_frame and not is_month_close_to_change:
        animation_state.date_transition_start_frame = None

    if not animation_state.date_transition_start_frame:
        draw_date(image, animation_state.current_date)
    else:
        date_transition_frame = animation_state.current_frame - animation_state.date_transition_start_frame

        current_date_y_offset = int(-DATE_TRANSITION_Y_OFFSET_STEP * date_transition_frame)
        current_date_opacity = 1 - (DATE_TRANSITION_OPACITY_STEP * date_transition_frame)
        draw_date(image, animation_state.current_date, y_offset=current_date_y_offset, opacity=current_date_opacity)

        next_date_y_offset = DATE_TRANSITION_Y_OFFSET - (DATE_TRANSITION_Y_OFFSET_STEP * date_transition_frame)
        next_date_opacity = DATE_TRANSITION_OPACITY_STEP * date_transition_frame
        draw_date(image, next_month, y_offset=next_date_y_offset, opacity=next_date_opacity)


def frame(animation_state):
    if not animation_state.base_image:
        animation_state.base_image = image = frame_generate_base_image()

    image = animation_state.base_image.copy()

    frame_handle_date_transition(image, animation_state)

    draw_scale(image, animation_state.scale)

    # Draw low layers first
    contact_bar_states = sorted(animation_state.contact_bar_states.values(), key=lambda s: s.layer)
    for contact_bar_state in contact_bar_states:
        if contact_bar_state.position[1] < CHART_BAR_FADE_OUT_MAX_Y:
            contact_bar = contact_bar_state.contact_bar
            bar_width = int(scale_user_bar_with(contact_bar.value, animation_state.scale))
            draw_contact_bar(image, *contact_bar_state.position, bar_width, contact_bar.profile_image, contact_bar.contact_name, 
                             contact_bar.value, contact_bar.color, contact_bar_state.opacity)

    return image


def generate_frame_data(animation_state, podium, profile_images, contact_colors):
    if not animation_state.contact_bar_states:
        animation_state.contact_bar_states = dict()
        for i, podium_user in enumerate(podium):
            display_name = podium_user.contact.display_name or f'+{JID_REGEXP.search(podium_user.contact.jid).group(1)}'
            profile_image = profile_images[podium_user.contact.jid]
            contact_color = contact_colors[podium_user.contact.jid]
            contact_bar = ContactBar(contact_color, display_name, profile_image=profile_image)
            animation_state.contact_bar_states[podium_user] = contact_bar_state = ContactBarAnimationState(i, contact_bar)
            contact_bar_state.position = CHART_BASE_X, CHART_BASE_Y + i * CHART_BAR_HEIGHT_AND_MARGIN
            contact_bar_state.final_position = contact_bar_state.position

    for i, podium_user in enumerate(podium):
        contact_bar_state = animation_state.contact_bar_states[podium_user]
        contact_bar_state.contact_bar.value = int(podium_user.value)
        contact_bar_state.layer = len(podium) - i

        if i != contact_bar_state.podium_index:
            contact_bar_state.podium_index = i
            contact_bar_state.left_frames = CHART_BAR_TRANSITION_TOTAL_FRAMES
            contact_bar_state.final_position = CHART_BASE_X, CHART_BASE_Y + i * CHART_BAR_HEIGHT_AND_MARGIN

        if contact_bar_state.left_frames > 0:
            x_step = (contact_bar_state.final_position[0] - contact_bar_state.position[0]) // contact_bar_state.left_frames
            y_step = (contact_bar_state.final_position[1] - contact_bar_state.position[1]) // contact_bar_state.left_frames
            contact_bar_state.position = contact_bar_state.position[0] + x_step, contact_bar_state.position[1] + y_step

            contact_bar_state.left_frames -= 1

        if contact_bar_state.position[1] < CHART_BAR_FADE_IN_Y:
            contact_bar_state.opacity = 1
        else:
            contact_bar_state.opacity = contact_bar_state.position[1] - CHART_BAR_FADE_IN_Y
            contact_bar_state.opacity = max(0, min(1, 1 - (contact_bar_state.opacity / CHART_BAR_HEIGHT)))

    first_user_based_scale = podium[0].value * GRID_FIRST_USER_SCALE_FACTOR
    animation_state.scale = max(GRID_MIN_SCALE, first_user_based_scale, animation_state.scale * SCALE_GROWTH_RATE)


def generate_video_frames(messages, start_date, frame_step_timedelta, podium, profile_images, contact_colors):
    frame_image = None
    group_message_range_timedelta = datetime.timedelta(days=7 * ANIMATION_SMOOTHNESS)
    animation_state = AnimationState(current_date=start_date, frame_step_timedelta=frame_step_timedelta,
                                     group_message_range_timedelta=group_message_range_timedelta)
    next_step_date = animation_state.current_date + group_message_range_timedelta
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
                    generate_frame_data(animation_state, podium, profile_images, contact_colors)
                    frame_image = frame(animation_state)
                    drop_counter += drop_increment
                else:
                    drop_counter -= 1

                yield frame_image

                animation_state.current_frame += 1
                animation_state.current_date += frame_step_timedelta

            next_step_date = animation_state.current_date + group_message_range_timedelta
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

    podium = Podium(contact_manager.get_users())
    
    logging.info('Rendering video...')
    total_frames = (end_date - start_date).total_seconds() / ELAPSED_TIMESTAMP_BY_FRAME
    fourcc = cv2.VideoWriter.fourcc(*'mp4v')
    video_writer = cv2.VideoWriter(output, fourcc, VIDEO_FRAME_RATE, IMAGE_SIZE)
    frame_step_timedelta = datetime.timedelta(seconds=ELAPSED_TIMESTAMP_BY_FRAME)
    with utils.context_locale(locale_):
        frames = generate_video_frames(messages, start_date, frame_step_timedelta, podium, profile_images, contact_colors)
        tqdm_iterator = tqdm.tqdm(frames, total=total_frames)
        try:
            for frame in tqdm_iterator:
                cv_image = cv2.cvtColor(np.array(frame), cv2.COLOR_RGBA2BGR)
                video_writer.write(cv_image)
        finally:
            video_writer.release()
