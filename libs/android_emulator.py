import os
import random
import atexit
import subprocess

from .android import Android
from .sdk_manager import SDKManager

EMULATOR_BIN = 'emulator.exe' if os.name == 'nt' else 'emulator'
AVD_MANAGER_BIN = 'avdmanager.bat' if os.name == 'nt' else 'avdmanager'


class CreateAVDError(RuntimeError):
    def __init__(self):
        super().__init__('an error has ocurred while creating android virtual device')


class EmulatorNotStartedError(RuntimeError):
    pass


class AndroidEmulator:
    JAVA_BIN_DIR = os.path.join(os.environ.get('JAVA_HOME'), 'bin') if os.environ.get('JAVA_HOME') else None 
    ANDROID_HOME = os.environ.get('ANDROID_HOME')
    AVD_MANAGER = os.environ.get('AVD_MANAGER')
    EMULATOR = None
    DEFAULT_ARGS = ['-no-boot-anim', '-netfast', '-delay-adb', '-writable-system']

    def __init__(self, name, show_window=True, port=None):
        window_flag = ['-no-window'] if not show_window else []
        
        console_port = port or str(random.randint(5570, 5580))

        self.proc = self.start_emulator(name, ['-port', console_port] + window_flag + self.DEFAULT_ARGS)
        self.adb = Android(f'emulator-{console_port}')

        atexit.register(self.shutdown)

    def shutdown(self):
        if hasattr(self, 'proc') and self.proc.poll() is None:
            self.proc.terminate()

    def wait_boot(self, timeout=300):
        try:
            self.adb.wait_boot(timeout=timeout)
        except subprocess.TimeoutExpired:
            raise EmulatorNotStartedError
    
    @staticmethod
    def avd_manager():
        return AndroidEmulator.AVD_MANAGER or os.path.join(AndroidEmulator.ANDROID_HOME, 'tools', 'bin', AVD_MANAGER_BIN)
    
    @staticmethod
    def emulator():
        return AndroidEmulator.EMULATOR or os.path.join(AndroidEmulator.ANDROID_HOME, 'emulator', EMULATOR_BIN)

    @staticmethod
    def create_avd(name, device, package, abi=None, force=False, timeout=60):
        force_flag = ['--force'] if force else []
        abi = ['--abi', abi] if abi else []
        cmd = [AndroidEmulator.avd_manager(), '-v', 'create', 'avd', '--name', name, 
               '--package', package, '--device', device]
        cmd = cmd + force_flag + abi
        proc = subprocess.Popen(cmd, shell=True)
        proc.wait(timeout)
        
        if proc.poll() != 0:
            raise CreateAVDError
    
    @staticmethod
    def start_emulator(name, args, logging=True, **kwargs):
        if not logging:
            kwargs['stdout'] = subprocess.PIPE
            kwargs['stderr'] = subprocess.PIPE
        cmd = [AndroidEmulator.emulator(), f'@{name}'] + args
        return subprocess.Popen(cmd, **kwargs, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    @staticmethod
    def available_avd():
        cmd = [AndroidEmulator.emulator(), '-list-avds']
        return subprocess.check_output(cmd, text=True).strip('\n').split('\n')
