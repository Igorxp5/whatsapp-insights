# WhatsApp Insights

whatsapp-insights is a Python project for getting insights about your contacts/messages in WhatsApp. The main features are generating a **chart race video** and a **insights cards image**.

## Features

###  Insights Image

<p>
  <img width="400" src="https://user-images.githubusercontent.com/8163093/133190605-5988593b-081a-440e-93f6-12fed9e1b2d4.png" />
</p>

###  Chart Race

<p>
    <img width="700" src="https://user-images.githubusercontent.com/8163093/133349562-78063a78-292a-45cc-9491-146ed49feafb.gif" />
</p>

## Pre-requisites

Before try this project out read [Disclaimer](#Disclaimer) section.

You need have installed in your machine following tools: 

- [Python 3.8](https://www.python.org/downloads/)
- [Android SDK](https://developer.android.com/studio#command-tools) (for database key extraction)
- [ChromeDriver](https://chromedriver.chromium.org/downloads) for your Chrome browser version (for contact profile image extraction)

Also, have installed the latest version of WhatsApp in your smartphone.

### How to setup the project manually

After you have installed all pre-requisites, run following command to clone this project: 
```bash
git clone https://github.com/Igorxp5/whatsapp-insights
```

Then access the cloned project folder and install all Python requirements:
```bash
cd whatsapp-insights
pip install -r requirements.txt
```

## Usage

*Currently we support just accounts running in Android platform. If you're a iOS user, you can try to pull your WhatsApp database using [WhatsApp Parser Tool](https://github.com/B16f00t/whapa) or moving your Account to an Android device like Android Emulator.*


### Extract WhatsApp Database Key

Database backup for Android platform is stored at **/sdcard/WhatsApp/Databases**. You can access it using your Android File Manager, but you can't read it because it's encrypted. The only way to read it, it's having the key to decrypt it. That key is stored in internal directory of the app, but you can't access it. For key extraction we're gonna use a Android Emulator with root permissions to access internal files of WhatsApp.

**Note: During this process you will be disconnected from your WhatsApp account in your device.**

**Note²: Before extracting the database key using this tool, backup your messages in Settings > Chats > Chat Backup.**

```bash
python main.py extract-key
```

#### Options

- **--no-backup:** For default the tool opens the WhatsApp in your device connected to the machine, and trigger the back up.
- **--serial:** Pass your Android device serial connected to the machine (if you have more than one connected).
- **--show-emulator:** If you want to follow login steps seeing what's going on the emulator, you can add that flag.

See more options running ```python main.py extract-key --help```.


### Extract WhatsApp Database

For WhatsApp database extraction you need the key databae already in the workspace folder, it will be needed for decrypting step.

```bash
python main.py extract-database
```

#### Options

- **--no-backup:** For default the tool opens the WhatsApp in your device connected to the machine, and trigger the back up.
- **--serial:** Pass your Android device serial connected to the machine (if you have more than one connected).

See more options running ```python main.py extract-database --help```.


### Extract Contacts Profile Image

To show your contacts profile image in the chart race video or insights image, you need to extract those images. This tool connects to your account via WhatsApp Web and get the images of all your contacts that you've messaged (excluding group profile images). You need provide the ```msgtore.db``` file to the script, so it can pull just contact profile images.

```bash
python main.py extract-profile-images
```

#### Options

- **--msg-store:** If you have saved ```msgstore.db``` out of the project workspace in you can pass the path to it here.
- **--chromedriver:** Pass here the **chromedriver** binary for your Chrome brower version.

See more options running ```python main.py extract-profile-images --help```.


### Generate Insights Image

To create the insights image you need ```msgstore.db```, export your contacts to ```vcf``` file and your contacts profile images.

```bash
python main.py generate-image --contacts contacts.vcf --msg-store msgstore.db --profile-pictures-dir ./profile_pictures
```

#### Options

- **--contact:** ```vcf``` file containg your contacts. You can export that using Android Contacts app.
- **--msg-store:** If you have saved ```msgstore.db``` out of the project workspace in you can pass the path to it here.
- **--locale:** Set the language of the insights descriptions. Currenly supporting: ```en_US``` and ```pt_BR```.
- **--profile-pictures-dir:** Directory with your contacts profile images. Set this if you have saved them out of the project workspace.
- **--top-insighters:** Set the insighter to be present in the top of the image. See [Insighters](#Insighters) section.
- **--insighters:** Set the insighters to be present in the cards of the image (separated by whitespace). You can choose up to 6 insighters. See [Insighters](#Insighters) section.

See more options running ```python main.py generate-image --help```.


### Generate Chart Race video

Like generating insights image, for generate chart race video you need ```msgstore.db```, export your contacts to ```vcf``` file and your contacts profile images.

```bash
python main.py generate-video --contacts contacts.vcf --msg-store msgstore.db --profile-pictures-dir ./profile_pictures
```


#### Options

- **--contact:** ```vcf``` file containg your contacts. You can export that using Android Contacts app. 
- **--msg-store:** If you have saved ```msgstore.db``` out of the project workspace in you can pass the path to it here.
- **--locale:** Set the language of the insights descriptions. Currenly supporting: ```en_US``` and ```pt_BR```.
- **--profile-pictures-dir:** Directory with your contacts profile images. Set this if you have saved them out of the project workspace.


## Insighters

For generating insights image, you currently have some **insighters**:

- **LongestAudioInsighter:** The user with the longest audio among your messages.
- **GreatestAudioAmountInsighter:** The user that sent you the greatest amount of audio messages.
- **GreatestAmountOfDaysTalkingInsighter:** The user that you've talked for more days.
- **GreatestPhotoAmountInsighter:** The user that sent you the greatest amount of photos.
- **GreatestMessagesAmountInsighter:** The user that sent you the greatest amount of messages in general.
- **LongestConversationInsighter:** The user that you spent more time talking without exit from the chat (messages separated by a maximum of 1 minute).
- **GreatestMyStatusAnsweredInsighter:** The user that answered your status more than anyone other contact.
- **LongestCallInsighter:** The user that you spent more time in a single call.
- **GreatestCallAmountInsighter:** The user that made with you the greatest amount of calls.
- **LongestTimeInCallsInsighter:** The user that you spent more time in calls in the total.


## Disclaimer

The process to get those insights requires you pull your WhatsApp message database and key to decrypt the database of your account. Be careful about exposing those two files, anyone can read your WhatsApp messages history having them.

Using automated scripts/third-party programs for accessing the WhatsApp services are not allowed by [WhatsApp Terms of Service](https://www.whatsapp.com/legal/updates/terms-of-service/?lang=en). Use the project at your own risk.

Any contributor of this project is not responsible, and expressly disclaims all liability for damages of any kind arising from the use, reference or reliance on this tool.


## License
[MIT](https://choosealicense.com/licenses/mit/)


## Credits

- Profile images for demonstratation from https://thispersondoesnotexist.com/.
- Decrypt WhatsApp database code from https://github.com/B16f00t/whapa/.
