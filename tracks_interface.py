import os
import threading
import tkinter as tk
from tkinter import ttk, simpledialog
import pygame
from yandex_music import Client
from YM__client_token import token
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, APIC, TIT2, TPE1
from PIL import Image, ImageTk
import io

# --- КОНФИГУРАЦИЯ ---
BASE_PATH = "./music"
TOKEN = token
BG_COLOR = "#0b0b0b"
SIDEBAR_COLOR = "#000000"
ACCENT_COLOR = "#FF0000" # Красный для агрессивного стиля
TEXT_COLOR = "#FFFFFF"
TRACK_BG = "#151515"

if not os.path.exists(BASE_PATH):
    os.makedirs(BASE_PATH)

pygame.mixer.init()

class MusicApp:
    def __init__(self, root):
        self.root = root
        self.root.title("fuck player the best YM!")
        self.root.geometry("1200x850")
        self.root.configure(bg=BG_COLOR)
        
        self.client = Client(TOKEN).init()
        self.current_playlist = "All"
        self.current_track_path = None
        self.is_paused = False
        self.loop_mode = "sequence" # sequence / loop_one
        
        self.cover_cache = {}
        self.after_id = None # Для устранения лагов поиска

        self.setup_ui()
        self.update_playback_info()
        self.refresh_list()

    def setup_ui(self):
        self.root.columnconfigure(1, weight=1)
        self.root.rowconfigure(0, weight=1)

        # САЙДБАР
        sidebar = tk.Frame(self.root, bg=SIDEBAR_COLOR, width=280)
        sidebar.grid(row=0, column=0, sticky="nsew")
        sidebar.grid_propagate(False)

        tk.Label(sidebar, text="FUCK PLAYER", fg=ACCENT_COLOR, bg=SIDEBAR_COLOR, font=("Impact", 24)).pack(pady=20)

        # Поиск для загрузки
        tk.Label(sidebar, text="DOWNLOAD FROM YM:", fg="gray", bg=SIDEBAR_COLOR).pack()
        self.web_search = tk.Entry(sidebar, bg="#1a1a1a", fg="white", insertbackground="white", border=0)
        self.web_search.pack(fill="x", padx=20, pady=5, ipady=5)
        tk.Button(sidebar, text="GET TRACK", bg=ACCENT_COLOR, fg="white", font=("Arial", 10, "bold"), 
                  command=self.start_web_download, relief="flat").pack(pady=5, fill="x", padx=20)

        # Поиск по локальным файлам (с фиксом лагов)
        tk.Label(sidebar, text="SEARCH LOCAL:", fg="gray", bg=SIDEBAR_COLOR).pack(pady=(20, 0))
        self.local_search = tk.Entry(sidebar, bg="#1a1a1a", fg="white", border=0)
        self.local_search.pack(fill="x", padx=20, pady=5, ipady=5)
        self.local_search.bind("<KeyRelease>", self.on_search_change)

        # Плейлисты
        tk.Label(sidebar, text="PLAYLISTS:", fg="white", bg=SIDEBAR_COLOR).pack(pady=(20, 5))
        self.pl_listbox = tk.Listbox(sidebar, bg=SIDEBAR_COLOR, fg="white", border=0, highlightthickness=0, font=("Arial", 11))
        self.pl_listbox.pack(fill="both", expand=True, padx=15)
        self.pl_listbox.bind("<<ListboxSelect>>", self.change_playlist)
        
        self.update_playlists_view()

        # ОСНОВНАЯ ЗОНА
        main_area = tk.Frame(self.root, bg=BG_COLOR)
        main_area.grid(row=0, column=1, sticky="nsew")

        # ПАНЕЛЬ УПРАВЛЕНИЯ (Сверху)
        ctrl = tk.Frame(main_area, bg="#050505", height=150)
        ctrl.pack(fill="x", side="bottom", ipady=10)

        # Слайдер перемотки
        self.seek_slider = ttk.Scale(ctrl, from_=0, to=100, orient="horizontal", command=self.seek_track)
        self.seek_slider.pack(fill="x", padx=50, pady=(10, 0))

        btn_frame = tk.Frame(ctrl, bg="#050505")
        btn_frame.pack(pady=10)

        self.loop_btn = tk.Button(btn_frame, text="MODE: SEQUENCE", bg="#333", fg="white", command=self.toggle_loop, relief="flat")
        self.loop_btn.pack(side="left", padx=10)

        self.play_pause_btn = tk.Button(btn_frame, text="PAUSE", bg=ACCENT_COLOR, fg="white", width=10, 
                                        command=self.toggle_pause, font=("Arial", 10, "bold"))
        self.play_pause_btn.pack(side="left", padx=10)

        # Скролл список
        self.canvas = tk.Canvas(main_area, bg=BG_COLOR, highlightthickness=0)
        self.scroll_frame = tk.Frame(self.canvas, bg=BG_COLOR)
        self.canvas.create_window((0, 0), window=self.scroll_frame, anchor="nw", width=900)
        self.canvas.pack(side="left", fill="both", expand=True, padx=20, pady=20)
        
        self.scroll_frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind_all("<MouseWheel>", lambda e: self.canvas.yview_scroll(int(-1*(e.delta/120)), "units"))

    # --- ФИКС ЛАГОВ ПОИСКА ---
    def on_search_change(self, event):
        if self.after_id:
            self.root.after_cancel(self.after_id)
        self.after_id = self.root.after(300, self.refresh_list)

    # --- ЛОГИКА ТРЕКОВ И ОБЛОЖЕК ---
    def get_track_data(self, f_path):
        data = {"duration": 0, "cover": None, "title": "Unknown", "artist": "Unknown"}
        try:
            audio = MP3(f_path, ID3=ID3)
            data["duration"] = audio.info.length
            data["title"] = audio.get("TIT2", [os.path.basename(f_path)])[0]
            data["artist"] = audio.get("TPE1", ["Unknown Artist"])[0]
            
            if f_path in self.cover_cache:
                data["cover"] = self.cover_cache[f_path]
            else:
                for tag in audio.tags.values():
                    if isinstance(tag, APIC):
                        img = Image.open(io.BytesIO(tag.data)).resize((60, 60), Image.LANCZOS)
                        data["cover"] = ImageTk.PhotoImage(img)
                        self.cover_cache[f_path] = data["cover"]
                        break
        except: pass
        return data

    def refresh_list(self):
        for w in self.scroll_frame.winfo_children(): w.destroy()
        sq = self.local_search.get().lower()
        
        files = []
        path = BASE_PATH if self.current_playlist == "All" else os.path.join(BASE_PATH, self.current_playlist)
        
        for root, _, filenames in os.walk(path):
            for f in filenames:
                if f.endswith(".mp3") and sq in f.lower():
                    files.append(os.path.join(root, f))

        for f_path in sorted(files):
            self.add_track_ui(f_path)

    def add_track_ui(self, f_path):
        data = self.get_track_data(f_path)
        frame = tk.Frame(self.scroll_frame, bg=TRACK_BG, cursor="hand2")
        frame.pack(fill="x", pady=2, ipady=5)

        if data["cover"]:
            tk.Label(frame, image=data["cover"], bg=TRACK_BG).pack(side="left", padx=10)
        else:
            tk.Label(frame, text="💿", fg=ACCENT_COLOR, bg=TRACK_BG, font=20).pack(side="left", padx=15)

        txt_frame = tk.Frame(frame, bg=TRACK_BG)
        txt_frame.pack(side="left", fill="both")
        tk.Label(txt_frame, text=data["title"], fg="white", bg=TRACK_BG, font=("Arial", 10, "bold")).pack(anchor="w")
        tk.Label(txt_frame, text=data["artist"], fg="gray", bg=TRACK_BG, font=("Arial", 8)).pack(anchor="w")

        frame.bind("<Button-1>", lambda e: self.play_music(f_path))

    # --- УПРАВЛЕНИЕ ---
    def play_music(self, path):
        self.current_track_path = path
        pygame.mixer.music.load(path)
        pygame.mixer.music.play()
        self.is_paused = False
        self.play_pause_btn.config(text="PAUSE")

    def toggle_pause(self):
        if self.is_paused:
            pygame.mixer.music.unpause()
            self.play_pause_btn.config(text="PAUSE")
        else:
            pygame.mixer.music.pause()
            self.play_pause_btn.config(text="PLAY")
        self.is_paused = not self.is_paused

    def seek_track(self, val):
        if self.current_track_path:
            target = float(val)
            pygame.mixer.music.set_pos(target)

    def toggle_loop(self):
        if self.loop_mode == "sequence":
            self.loop_mode = "loop_one"
            self.loop_btn.config(text="MODE: LOOP ONE", bg=ACCENT_COLOR)
        else:
            self.loop_mode = "sequence"
            self.loop_btn.config(text="MODE: SEQUENCE", bg="#333")

    def update_playback_info(self):
        """Обновляет слайдер и следит за окончанием трека."""
        if pygame.mixer.music.get_busy() or self.is_paused:
            if self.current_track_path:
                d = self.get_track_data(self.current_track_path)
                self.seek_slider.config(to=d["duration"])
                # pygame.mixer.music.get_pos() возвращает мс
                curr = pygame.mixer.music.get_pos() / 1000 
                self.seek_slider.set(curr)
        
        # Проверка окончания трека
        if self.current_track_path and not pygame.mixer.music.get_busy() and not self.is_paused:
            if self.loop_mode == "loop_one":
                self.play_music(self.current_track_path)
            # Здесь можно добавить логику переключения на следующий

        self.root.after(1000, self.update_playback_info)

    # --- СКАЧИВАНИЕ С ОБЛОЖКОЙ ---
    def start_web_download(self):
        q = self.web_search.get()
        if q:
            threading.Thread(target=self.download_with_meta, args=(q,), daemon=True).start()
            self.web_search.delete(0, tk.END)

    def download_with_meta(self, query):
        try:
            search = self.client.search(query)
            if search.tracks:
                track = search.tracks.results[0]
                artists = ", ".join([a.name for a in track.artists])
                filename = f"{artists} - {track.title}.mp3".replace("/", "-")
                path = os.path.join(BASE_PATH, filename)
                
                track.download(path)
                
                # Вшиваем обложку и метаданные
                audio = MP3(path, ID3=ID3)
                try: audio.add_tags()
                except: pass
                
                # Скачиваем обложку
                img_url = track.get_cover_url('m100x100')
                img_data = self.client.request.retrieve(f"https://{img_url}")
                
                audio.tags.add(APIC(encoding=3, mime='image/jpeg', type=3, desc='Cover', data=img_data))
                audio.tags.add(TIT2(encoding=3, text=track.title))
                audio.tags.add(TPE1(encoding=3, text=artists))
                audio.save()
                
                self.root.after(0, self.refresh_list)
        except Exception as e: print(f"Download Error: {e}")

    def update_playlists_view(self):
        self.pl_listbox.delete(0, tk.END)
        self.pl_listbox.insert(tk.END, "All")
        for d in os.listdir(BASE_PATH):
            if os.path.isdir(os.path.join(BASE_PATH, d)): self.pl_listbox.insert(tk.END, d)

    def change_playlist(self, event):
        sel = self.pl_listbox.curselection()
        if sel:
            self.current_playlist = self.pl_listbox.get(sel)
            self.refresh_list()

if __name__ == "__main__":
    root = tk.Tk()
    app = MusicApp(root)
    root.mainloop()
