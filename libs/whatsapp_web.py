import os
import io
import re
import time
import base64
import tkinter

from PIL import ImageTk, Image
from threading import Thread, Event

from selenium import webdriver
from selenium.webdriver import ChromeOptions
from selenium.common.exceptions import NoSuchElementException

USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.159 Safari/537.36 Edg/92.0.902.84'

WHATSAPP_API_SCRIPT = os.path.join(os.path.dirname(__file__), '..', 'scripts', 'whatsapp_api.js')
DEFAULT_IMPLICITY_WAIT = 15


class WhatsAppWeb:
    def __init__(self, executable_path, headless=True):
        options = ChromeOptions()
        options.headless = headless
        options.add_argument('--incognito')
        options.add_argument('--lang=en_US')
        options.add_argument('--window-size=1366x768')
        options.add_argument('disable-blink-features=AutomationControlled')
        options.add_argument(f'user-agent={USER_AGENT}')
        options.add_argument("--log-level=OFF")
        options.add_experimental_option('excludeSwitches', ['enable-logging'])

        self._driver = webdriver.Chrome(executable_path=executable_path, options=options)
        self._driver.implicitly_wait(DEFAULT_IMPLICITY_WAIT)
        self._driver.get('https://web.whatsapp.com')
        self._login()

    def get_contact_profile_image_url(self, jid):
        search_field = self._driver.find_element_by_xpath('//*[@data-testid="chat-list-search"]')
        self._driver.execute_script("arguments[0].click();", search_field)
        time.sleep(1)
        phone_number = jid.split('@', 1)[0]
        search_field.send_keys(phone_number)
        time.sleep(2)
        self._driver.implicitly_wait(2)
        try:
            url = self._driver.find_element_by_xpath('//*[@data-testid="chatlist-status-v3-ring"]//img').get_attribute('src')
        except NoSuchElementException:
            return None
        finally:
            try:
                self._driver.find_element_by_xpath('//*[@data-testid="x-alt"]').click()
            except NoSuchElementException:
                pass
            self._driver.implicitly_wait(DEFAULT_IMPLICITY_WAIT)
        return url

    def get_user_profile_image_url(self):
        try:
            self._driver.find_element_by_xpath('//header[@data-testid="chatlist-header"]//img').click()
            url = self._driver.find_element_by_xpath('//*[@id="app"]//div[@title="Photo Picker"]//img').get_attribute('src')
        finally:
            try:
                self._driver.find_element_by_xpath('//*[@data-testid="back"]').click()
            except NoSuchElementException:
                pass
        return url

    def _login(self):
        def _check_login(quit_event):
            try:
                self._driver.find_element_by_xpath("//header[@data-testid='chatlist-header']")
            except NoSuchElementException:
                raise RuntimeError('login state was not identified')
            finally:
                quit_event.set()
        
        qr_code = self._get_qr_image()
        
        quit_event = Event()

        Thread(target=_check_login, args=(quit_event,), daemon=True).start()
        
        self._show_image(qr_code, 'WhatsApp Web QR Code', quit_event)
        

    def _show_image(self, image, title, quit_event):
        def _wait_quit_event(tk, event):
            event.wait()
            tk.destroy()

        root = tkinter.Tk()
        root.title(title)
        render = ImageTk.PhotoImage(image)
        img = tkinter.Label(image=render)
        img.pack(side=tkinter.TOP)
        
        Thread(target=_wait_quit_event, args=(root, quit_event), daemon=True).start()
        root.mainloop()

    def _get_qr_image(self):
        canvas_element = self._driver.find_element_by_xpath('//canvas[@aria-label="Scan me!"]')
        image_url = self._driver.execute_script('return arguments[0].toDataURL()', canvas_element)
        base64_data = re.sub('^data:image/.+;base64,', '', image_url)
        return Image.open(io.BytesIO(base64.b64decode(base64_data)))
    
    def _load_whatsapp_api(self):
        with open(WHATSAPP_API_SCRIPT) as file:
            self._driver.execute_script(file.read())
        self._driver.execute_script('window.whatsapp_api = new window.WhatsAppAPI();')
