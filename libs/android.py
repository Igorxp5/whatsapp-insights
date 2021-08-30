import logging
import re
import os
import io
import time
import shlex
import tempfile
import subprocess

from PIL import Image
from lxml import etree


class WaitforTimeout(RuntimeError):
    pass


class NotReachedToActivityError(RuntimeError):
    def __init__(self, activity):
        super().__init__('device did not reach to activity: {}'.format(activity))


class NotReachedToWindowError(RuntimeError):
    def __init__(self, window_name, pattern):
        super().__init__('device did not reach to window: {} with pattern: {}'.format(window_name, pattern))


class Android:
    def __init__(self, serial):
        self.serial = serial
        self.ui = UIAutomator(self)
    
    def adb(self, cmd, timeout=120, text=True, **kwargs):
        if not isinstance(cmd, list):
            cmd = shlex.split(cmd)
        cmd = ['adb', '-s', self.serial, 'wait-for-device'] + [str(a) for a in cmd]
        logging.debug(f'ADB call: {shlex.join(cmd)}')
        out = subprocess.check_output(cmd, text=text, shell=True, timeout=timeout, **kwargs)
        return out.rstrip('\n') if text else out

    def root(self):
        subprocess.Popen(['adb', '-s', self.serial, 'wait-for-device', 'root'], shell=True).wait(timeout=15)
    
    def pull(self, src, dst, timeout=600):
        process = subprocess.Popen(['adb', '-s', self.serial, 'wait-for-device', 'pull', src, dst], shell=True, text=True,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, err = process.communicate(timeout=timeout)
        if process.poll() == 1 and 'No such file or directory' in out:
            raise FileNotFoundError(src)
        if process.poll() > 0:
            raise RuntimeError('error while pulling file: {}'.format(out))
    
    def window_size(self):
        match = re.search(r'Physical size: (\d+)x(\d+)', self.shell(['wm', 'size']))
        return {'width': int(match.group(1)), 'height': int(match.group(2))}
    
    def current_activity(self):
        return self.shell(['dumpsys activity a . | grep -E "mResumedActivity" | cut -d " " -f 8'])
    
    def current_package(self):
        return self.current_activity().split('/', 1)[0]
    
    def waitfor_activity(self, activity, timeout=15):
        start_time = time.time()
        while time.time() - start_time < timeout:
            if self.current_activity() == activity:
                return
        raise NotReachedToActivityError(activity)
    
    def waitfor_window(self, window_name, pattern, timeout=10):
        start_time = time.time()
        
        if not isinstance(pattern, re.Pattern):
            pattern = re.compile(pattern)
        
        windows = self._get_windows()
        
        while time.time() - start_time < timeout:
            for window_info, window_data in windows:
                if window_info[2] == window_name and pattern.search(window_data):
                    return
        return NotReachedToWindowError(window_name, pattern)
    
    def shell(self, cmd, **kwargs):
        if not isinstance(cmd, list):
            cmd = shlex.split(cmd)
        return self.adb(['shell'] + cmd, **kwargs)
    
    def wait_boot(self, timeout=300):
        self.shell(['getprop', 'sys.boot_completed'], timeout=timeout)

    def text(self, text, step=10):
        for start in range(0, len(text), step):
            self.shell(['input', 'text', text[start:start + step]])
            time.sleep(0.3)
    
    def tap(self, x, y):
        self.shell(['input', 'tap', x, y])
    
    def swipe(self, x1, y1, x2, y2, duration):
        self.shell(['input', 'swipe', x1, y1, x2, y2, duration])
    
    def scroll_down(self):
        window_size = self.window_size()
        x1 = window_size['width'] // 2
        y1 = window_size['height'] - 200
        x2 = x1
        y2 = 200
        self.swipe(x1, y1, x2, y2, 1400)
    
    def keyevent(self, keyevent):
        self.shell(['input', 'keyevent', keyevent])
    
    def power(self):
        self.keyevent(26)
    
    def enter(self):
        self.keyevent(66)
    
    def home(self):
        self.keyevent(3)
    
    def back(self):
        self.keyevent(4)
    
    def recents(self):
        self.keyevent(187)
    
    def is_keyboard_up(self):
        dump = self.shell(['dumpsys', 'window', 'windows'])
        return bool(re.search(r'mInputMethodTarget in display#', dump))
    
    def is_screen_on(self):
        dump = self.shell(['dumpsys power | grep "mWakefulness="'])
        return 'Awake' in dump
    
    def is_unlocked(self):
        dump = self.shell(['dumpsys power | grep "mHoldingWakeLockSuspendBlocker="'])
        return 'true' in dump
    
    def start_activity(self, component_name, args, **kwargs):
        self.shell(['am', 'start', '-n', component_name] + list(args), **kwargs)

    def clear_app(self, package):
        self.shell(['pm', 'clear', package])
    
    def uninstall_app(self, package):
        self.shell(['pm', 'uninstall', package])

    def force_stop(self, package):
        self.shell(['am', 'force-stop', package])
    
    def screenshot(self, crop_bounds=None):
        image_data = self.adb(['exec-out', 'screencap', '-p'], text=False)
        image = Image.open(io.BytesIO(image_data))
        if crop_bounds:
            image = image.crop(crop_bounds)
        return image
    
    def _get_windows(self):
        dump = self.shell(['dumpsys', 'window', 'windows'])
        lines = dump.split('\n')
        dump_iterator = iter(lines)
        
        # Ignore first line
        next(dump_iterator)
        
        windows = []
        window = tuple()
        window_data = ''
        for line in dump_iterator:
            match = re.search(r'Window #(\d+) Window\{(\S+).*?(\S+)\}', line)
            if match:
                if window:
                    windows.append([window, window_data])
                window = match.groups()
            else:
                window_data += line.strip() + '\n'
        else:
            windows.append([window, window_data])
        
        return windows


class UIAutomator:
    def __init__(self, android):
        self.android = android
        self._dump_file = os.path.join(tempfile.gettempdir(), f'{self.android.serial}_dump.xml')
        self.tree = None
    
    def find_elements(self, force_dump=False, **kwargs):
        nodes = []
        if self.tree is not None and not force_dump:
            nodes = self._find_nodes(**kwargs)
        if not nodes:
            self.dump()
            nodes = self._find_nodes(**kwargs)
        return [UIElement(self, node) for node in nodes]
    
    def find_element(self, force_dump=True, **kwargs):
        elements = self.find_elements(force_dump=force_dump, **kwargs)
        return elements[0] if elements else None

    def waitfor_element(self, timeout=15, **kwargs):
        start_time = time.time()
        while time.time() - start_time < timeout:
            element = self.find_element(**kwargs)
            if element:
                return element
        raise WaitforTimeout

    def dump(self):
        self.android.shell(['uiautomator', 'dump'], stderr=subprocess.PIPE)
        self.android.adb(['pull', '/sdcard/window_dump.xml', self._dump_file])

        with open(self._dump_file, 'rb') as file:
            content = file.read()
            self.tree = etree.XML(content)
    
    def _find_nodes(self, **kwargs):
        if 'id' in kwargs:
            kwargs['id'] = f'{self.android.current_package()}:id/{kwargs["id"]}'
            kwargs['resource-id'] = kwargs['id']
            del kwargs['id']
        rules = [f'contains(@{k}, "{v.pattern}")' if isinstance(v, re.Pattern) else f'@{k}="{v}"' for k, v in kwargs.items()]
        rules = ' and '.join(rules)
        return self.tree.xpath(f'//node[{rules}]')


class UIElement:
    def __init__(self, uiautomator, node):
        self.uiautomator = uiautomator
        self.node = node
        self._bounds = [int(b) for b in re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', self.node.attrib['bounds']).groups()]

    def width(self):
        return self._bounds[2] - self._bounds[0]

    def height(self):
        return self._bounds[3] - self._bounds[1]
    
    def x(self):
        return self._bounds[0] + self.width() // 2

    def y(self):
        return self._bounds[1] + self.height() // 2
    
    def bounds(self):
        return self._bounds

    def tap(self):
        self.uiautomator.android.tap(self.x(), self.y())

    def text(self):
        return self.node.attrib['text']
    
    def contentDesc(self):
        return self.node.attrib['content-desc']
