import io
import base64


def time_delta_to_str(time, units, round_=False):
    factors = {'d': 3600 * 24, 'h': 3600, 'm': 60, 's': 1}
    
    if round_:
        last_suffix_factor = factors[units[-1]]
        time += last_suffix_factor - time % last_suffix_factor
    
    result = []
    for unit in units:
        factor = factors[unit]
        value = int(time / factor)
        time = time % factor
        if value > 0:
            result.append(f'{value}{unit}')
    
    return ' '.join(result)

def pillow_image_to_base64(image, format):
    buffer = io.BytesIO()
    image.save(buffer, format)
    buffer.seek(0)
    return base64.b64encode(buffer.getvalue())
