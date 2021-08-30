import os
import re
import tqdm
import time
import logging
import subprocess
import collections

from threading  import Thread
from queue import Queue, Empty

SDK_MANAGER_BIN = 'sdkmanager.bat' if os.name == 'nt' else 'sdkamanger'
APKSIGNER_BIN = 'apksigner.bat' if os.name == 'nt' else 'apksigner'

SDKPackage = collections.namedtuple('SDKPackage', ['name', 'version', 'description', 'path'])


class ListSDKPackagesError(RuntimeError):
    def __init__(self):
        super().__init__('an error has ocurred while listing SDK packages')


class InstallPackageError(RuntimeError):
    def __init__(self):
        super().__init__('an error has ocurred while installing SDK packages')


class NoBuildToolsInstalledError(RuntimeError):
    def __init__(self):
        super().__init__('no build tools installed')


class SDKManager:
    def __init__(self, android_home=None, sdk_manager=None):
        self._android_home = None
        self._sdk_manager = None

        if android_home:
            self.ANDROID_HOME = android_home
        if sdk_manager:
            self.SDK_MANAGER = sdk_manager
        
        if not self._sdk_manager:
            raise ValueError('SDK Manager path was not provided') 

    @property
    def ANDROID_HOME(self):
        return self._android_home

    @ANDROID_HOME.setter
    def ANDROID_HOME(self, path):
        self._android_home = path
        self._sdk_manager = os.path.join(self._android_home, 'tools', 'bin', SDK_MANAGER_BIN)

    @property
    def SDK_MANAGER(self):
        return self._sdk_manager
    
    @SDK_MANAGER.setter
    def SDK_MANAGER(self, path):
        self._sdk_manager = path
    
    def get_all_packages(self):
        return self._get_all_packages()
    
    def install_package(self, *packages, timeout=2400):
        process = subprocess.Popen([self.SDK_MANAGER, '--install'] + list(packages), shell=True)
        process.wait(timeout)
        if process.poll() != 0:
            raise InstallPackageError
    
    def get_installed_build_tools(self):
        installed_packages, _ = self.get_all_packages()
        return [p for p in installed_packages if p.name.startswith('build-tools')]
    
    def get_apk_sha256_signature(self, apk):
        dump = subprocess.check_output([self._get_apksigner_bin(), 'verify', 
                                        '--verbose', '--print-certs', apk], text=True)
        match = re.search(r'certificate SHA-256 digest: (\S+)', dump)
        return match and match.group(1)
    
    def _get_apksigner_bin(self):
        build_tools = self.get_installed_build_tools()
        if not build_tools:
            raise NoBuildToolsInstalledError
        latest_build_tools = max(build_tools, key=lambda p: p.version)
        return os.path.join(self.ANDROID_HOME, latest_build_tools.path, APKSIGNER_BIN)

    def _get_all_packages(self, timeout=30):
        logging.info('Listing packages in SDK Manager')
        process = subprocess.Popen([self.SDK_MANAGER, '--list'], text=True, stdout=subprocess.PIPE, shell=True)
        out, _ = process.communicate(timeout)
        if process.poll() != 0:
            raise ListSDKPackagesError
        logging.info('Parsing packages in SDK Manager')

        _, packages = out.split('Installed packages:\n')
        installed_packages, _, available_packages = packages.partition('Available Packages:\n')

        available_packages, _, _ = available_packages.partition('Available Updates:\n')

        return self._parse_packages_list(installed_packages), self._parse_packages_list(available_packages)

    @staticmethod
    def _parse_packages_list(raw, header=True):
        if header:
            raw = raw.split('\n', 2)[-1].strip('\n')
        packages = []
        for line in raw.split('\n'):
            columns = line.split('|')
            columns = [s.strip() for s in columns]
            columns += [None] * (4 - len(columns))
            packages.append(SDKPackage(*columns))
        return packages


if __name__ == '__main__':
    sdk_manager = SDKManager(android_home='C:\\Users\\Igorxp5\\AppData\\Local\\Android\\Sdk', sdk_manager='C:\\Users\\Igorxp5\\AppData\\Local\\Android\\Sdk\\cmdline-tools\\latest\\bin\\sdkmanager.bat')
    installed_packages, available_packages = sdk_manager.get_all_packages()
    sdk_manager.install_package('system-images;android-29;google_apis;x86_64')
    # print(installed_packages)
    # print(sdk_manager.get_apk_sha256_signature('C:\\Users\\Igorxp5\\Downloads\\com.whatsapp_2.21.16.20-211620005_minAPI16(x86_64)(nodpi)_apkmirror.com.apk'))
