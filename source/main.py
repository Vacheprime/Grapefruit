from android.permissions import request_permissions, Permission
from android.storage import primary_external_storage_path
debug_path = primary_external_storage_path()
from kivy.lang import Builder
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.textinput import TextInput
from kivy.app import App
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.widget import Widget
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.popup import Popup
from kivy.graphics import Rectangle, Color, RoundedRectangle
from kivy.core.clipboard import Clipboard
	
import youtube_dl
from youtube_dl.utils import DownloadError
import threading
import asyncio
from ffmpeg import FFmpeg
import os
import shutil
import stat

os.chmod("./ffmpeg", stat.S_IXUSR + stat.S_IRUSR)

request_permissions([Permission.WRITE_EXTERNAL_STORAGE, Permission.INTERNET])
if not os.path.isdir("download_sandbox"):
    os.mkdir("./download_sandbox")
output_path = primary_external_storage_path()
output_path += "/Download/"
debug_path = primary_external_storage_path()
download_thread = None
loop = asyncio.get_event_loop()

for file in os.listdir("download_sandbox"):
    os.remove(f"download_sandbox/{file}")


def get_bare_filename(filename):
    reverse_filename = filename[::-1]
    extension_len = []
    for letter in reverse_filename:
        if letter == ".":
            extension_len.append(letter)
            break
        else:
            extension_len.append(letter)
    bare_filename = filename[:-len(extension_len)]
    return bare_filename


def cleanup():
    for tmpfile in os.listdir("download_sandbox"):
        os.remove(f"download_sandbox/{tmpfile}")

        
class Ytdl_Logger():

    def debug(self, msg):
        pass

    def warning(self, msg):
        pass

    def error(self, msg):
        pass


class Popup_Layout(FloatLayout):
    def __init__(self, text_info, **kwargs):
        super(Popup_Layout, self).__init__(**kwargs)
        self.cols = 1
        self.popup_info.text = text_info


class DownloadWindow(Screen):
    def __init__(self, **kwargs):
        super(DownloadWindow, self).__init__(**kwargs)

    def dirty_exit(self):
        self.manager.screens[0].cancel_download = True


class InputWindow(Screen):
    def __init__(self, **kwargs):
        super(InputWindow, self).__init__(**kwargs)
        self.url_input = self.ids.url_input
        self.progress_hook_index = 1
        self.type = None
        self.video_titles = []
        self.total_videos = 0
        self.tmpfilename = ""
        self.filename = ""
        self.total_bytes = 0
        self.cancel_download = False
        self.downloaded_videos = 0
        self.download_event_loop = None

    def paste_clipboard(self):
        self.url_input.text = Clipboard.paste()

    def popup(self, title, text_info):
        layout = Popup_Layout(text_info)
        popup_window = Popup(title=title, content=layout, size_hint=(0.8, 0.5))
        popup_window.open()
    
    def reinit_values(self):
        self.manager.screens[1].progress_label.text = ""
        self.manager.screens[1].download_progress.value = 0
        self.manager.screens[1].video_info.text = ""
        self.progress_hook_index = 1
        self.manager.current = "InputWindow"
        self.downloaded_videos = 0
        self.cancel_download = False
        self.video_titles.clear()

    def download(self):
        global download_thread
        url = self.url_input.text
        self.url_input.text = ""
        self.download_event_loop = asyncio.new_event_loop()
        self.manager.screens[1].progress_label.text = "Starting download..."
        download_thread = threading.Thread(target=self.download_audio, args=(url, ), daemon=True)
        download_thread.start()

    def download_audio(self, url, codec="mp3"):
        """
        Function: Download audio from URL
        param codec : audio codec chosen to download/convert. Default is mp3
        param url : url to download from
        """
        global download_thread
        asyncio.set_event_loop(self.download_event_loop)
        loop = asyncio.get_event_loop()
        ytdl_opts = {"format":"bestaudio/best", "progress_hooks": [self.progress_hook], "nocheckcertificate": True, "logger": Ytdl_Logger(), "outtmpl": "download_sandbox/%(title)s.%(ext)s"}
        ytdl = youtube_dl.YoutubeDL(ytdl_opts)
        try:
            with ytdl as yt:
                info_dict = yt.extract_info(url, download=False)
                try:
                    info_dict["_type"]
                    self.type = "playlist"
                    self.total_videos = len(info_dict["entries"])
                    for video in info_dict["entries"]:
                        self.video_titles.append(video["title"])
                except:
                    self.type = "single_video"
                    self.video_titles.append(info_dict["title"])
                if self.type == "playlist":
                    for video in info_dict["entries"]:
                        try:
                            yt.download([video["webpage_url"]])
                        except KeyboardInterrupt:
                            break
                        bare_filename = get_bare_filename(self.filename)
                        ffmpeg = FFmpeg(executable="./ffmpeg").option("y").input(self.filename, {"-threads": "0"}).output(f"{bare_filename}.mp3", {"-threads": "0"})

                        @ffmpeg.on("progress")
                        def ffmpeg_progress_hook(progress):
                            if self.cancel_download:
                                ffmpeg.terminate()
                            ffmpeg_progress = progress.size*100//self.total_bytes
                            self.manager.screens[1].download_progress.value = 1 + ffmpeg_progress/100
                            self.manager.screens[1].progress_label.text = f"Converting {ffmpeg_progress}%"

                        @ffmpeg.on("completed")
                        def on_completed():
                            self.manager.screens[1].download_progress.value = 2
                            self.manager.screens[1].progress_label.text = f"Converting 100%"
                        if not self.cancel_download:
                            loop.run_until_complete(ffmpeg.execute())
                            if not self.cancel_download:
                                os.remove(self.filename)
                                bare_filename = bare_filename.split("/")[-1]
                                shutil.move(f"download_sandbox/{bare_filename}.mp3", f"{output_path}{bare_filename}.mp3")
                                self.downloaded_videos += 1
                            else:
                                break
                        else:
                            break
                elif self.type == "single_video":
                    try:
                        yt.download([url])
                    except KeyboardInterrupt:
                        pass
                    bare_filename = get_bare_filename(self.filename)
                    ffmpeg = FFmpeg(executable="./ffmpeg").option("y").input(self.filename, {"-threads": "0"}).output(f"{bare_filename}.mp3", {"-threads": "0"})

                    @ffmpeg.on("progress")
                    def ffmpeg_progress_hook(progress):
                        if self.cancel_download:
                            ffmpeg.terminate()
                        ffmpeg_progress = progress.size*100//self.total_bytes
                        self.manager.screens[1].download_progress.value = 1 + ffmpeg_progress/100
                        self.manager.screens[1].progress_label.text = f"Converting {ffmpeg_progress}%"

                    @ffmpeg.on("completed")
                    def on_completed():
                        self.manager.screens[1].download_progress.value = 2
                        
                    if not self.cancel_download:
                        loop.run_until_complete(ffmpeg.execute())
                        if not self.cancel_download:
                            os.remove(self.filename)
                            bare_filename = bare_filename.split("/")[-1]
                            shutil.move(f"download_sandbox/{bare_filename}.mp3", f"{output_path}{bare_filename}.mp3")
                            self.downloaded_videos += 1

            if self.cancel_download:
                self.popup("Cancel", f"Download Canceled: {self.downloaded_videos} video(s) downloaded")
                self.reinit_values()
                cleanup()
                self.download_event_loop.close()
            else:
                self.popup("Download", f"Download finished: {self.downloaded_videos} video(s) downloaded")
                self.reinit_values()
                cleanup()
                self.download_event_loop.close()

        except DownloadError as e:
            if "search YouTube" in str(e):
                self.popup("Error", "Invalid link")
            else:
                self.popup("Error", f"Unknown error occured: {self.downloaded_videos} video(s) downloaded")
                print(str(e) + e.__doc__)
            
            cleanup()
            self.reinit_values()
            self.download_event_loop.close()

        except Exception as e:
            self.popup("Error", f"Error occured: {e} {e.__doc__}")
            self.reinit_values()
            cleanup()
            self.download_event_loop.close()

    def progress_hook(self, d):
        video_info = self.manager.screens[1].video_info
        progress_label = self.manager.screens[1].progress_label
        download_progress_bar = self.manager.screens[1].download_progress
        if d["status"] == "downloading":
            self.tmpfilename = d["tmpfilename"]
            self.filename = d["filename"]
            self.total_bytes = d["total_bytes"]
            download_progress = d["downloaded_bytes"]*100//d["total_bytes"]
            if self.type == "single_video":
                download_progress_bar.value = download_progress/100
                progress_label.text = f"Downloading: {download_progress}%"
                video_info.text = f"title: {self.video_titles[0]} - Video {self.progress_hook_index} of 1"
            elif self.type == "playlist":
                download_progress_bar.value = download_progress/100
                progress_label.text = f"Downloading: {download_progress}%"
                video_info.text = f"(playlist) title: {self.video_titles[self.progress_hook_index - 1]} - Video {self.progress_hook_index} of {self.total_videos}"
        elif d["status"] == "finished":
            progress_label.text = "Converting..."
            self.progress_hook_index += 1

        if self.cancel_download:
            raise KeyboardInterrupt




kv = Builder.load_file("display.kv")
class Main(App):
    def build(self):
        sm = ScreenManager()
        sm.add_widget(InputWindow())
        sm.add_widget(DownloadWindow())
        sm.current = "InputWindow"
        return sm

    def on_pause(self):
        return True

    def on_resume(self):
        pass

Main().run()
