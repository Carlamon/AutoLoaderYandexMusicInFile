import os
import threading
import tkinter as tk
from tkinter import ttk, simpledialog
import pygame
from yandex_music import Client
from YM__client_token import token
from mutagen.mp3 import MP3

# --- КОНФИГУРАЦИЯ ---
BASE_PATH = "./music"
TOKEN = token
BG_COLOR = "#0b0b0b"
SIDEBAR_COLOR = "#000000"
ACCENT_COLOR = "#FF0000" 
TEXT_COLOR = "#FFFFFF"
TRACK_BG = "#151515"

if not os.path.exists(BASE_PATH):
    os.makedirs(BASE_PATH)

pygame.mixer.pre_init(44100, -16, 2, 2048)
pygame.mixer.init()

class MusicApp:
    def __init__(self, root):
        self.root = root
        self.root.title("fuck player the best YM!")
        self.root.geometry("1100x750")
        self.root.configure(bg=BG_COLOR)
        
        self.client = Client(TOKEN).init()
        self.current_playlist = "All"
        self.current_track_path = None
        self.is_paused = False
        self.loop_mode = "sequence" 
        
        self.after_id = None 
        self.current_start_time = 0
        self.is_dragging = False # Флаг, чтобы ползунок не дергался при перемотке

        self.setup_ui()
        self.bind_keys() # Горячие клавиши
        self.update_playback_info()
        self.refresh_list()

    def setup_ui(self):
        self.root.columnconfigure(1, weight=1)
        self.root.rowconfigure(0, weight=1)

        sidebar = tk.Frame(self.root, bg=SIDEBAR_COLOR, width=280)
        sidebar.grid(row=0, column=0, sticky="nsew")
        sidebar.grid_propagate(False)

        tk.Label(sidebar, text="FUCK PLAYER", fg=ACCENT_COLOR, bg=SIDEBAR_COLOR, font=("Impact", 26)).pack(pady=20)

        self.web_search = tk.Entry(sidebar, bg="#1a1a1a", fg="white", insertbackground="white", border=0)
        self.web_search.pack(fill="x", padx=20, pady=5, ipady=8)
        self.web_search.bind("<Return>", lambda e: self.start_web_download())
        
        tk.Button(sidebar, text="FIND & DOWNLOAD", bg=ACCENT_COLOR, fg="white", font=("Arial", 9, "bold"), 
                  command=self.start_web_download, relief="flat").pack(pady=5, fill="x", padx=20)

        self.local_search = tk.Entry(sidebar, bg="#1a1a1a", fg="white", border=0)
        self.local_search.pack(fill="x", padx=20, pady=5, ipady=8)
        self.local_search.bind("<KeyRelease>", self.on_local_search_change)

        tk.Label(sidebar, text="MY PLAYLISTS:", fg="white", bg=SIDEBAR_COLOR).pack(pady=(30, 5))
        tk.Button(sidebar, text="+ CREATE NEW", bg="#222", fg=ACCENT_COLOR, command=self.add_playlist_dialog, relief="flat").pack(fill="x", padx=20)

        self.pl_listbox = tk.Listbox(sidebar, bg=SIDEBAR_COLOR, fg="white", border=0, highlightthickness=0, font=("Arial", 11), selectbackground=ACCENT_COLOR)
        self.pl_listbox.pack(fill="both", expand=True, padx=15, pady=10)
        self.pl_listbox.bind("<<ListboxSelect>>", self.change_playlist)
        self.update_playlists_view()

        main_area = tk.Frame(self.root, bg=BG_COLOR)
        main_area.grid(row=0, column=1, sticky="nsew")

        ctrl = tk.Frame(main_area, bg="#050505", height=130)
        ctrl.pack(fill="x", side="bottom", ipady=15)

        # Слайдер с фиксом перетаскивания
        self.seek_slider = ttk.Scale(ctrl, from_=0, to=100, orient="horizontal", command=self.on_slider_move)
        self.seek_slider.pack(fill="x", padx=50, pady=(5, 0))
        self.seek_slider.bind("<ButtonPress-1>", lambda e: setattr(self, 'is_dragging', True))
        self.seek_slider.bind("<ButtonRelease-1>", lambda e: setattr(self, 'is_dragging', False))

        btn_frame = tk.Frame(ctrl, bg="#050505")
        btn_frame.pack(pady=10)

        self.loop_btn = tk.Button(btn_frame, text="MODE: SEQUENCE", bg="#333", fg="white", command=self.toggle_loop, relief="flat", width=18)
        self.loop_btn.pack(side="left", padx=15)

        self.play_pause_btn = tk.Button(btn_frame, text="PAUSE", bg=ACCENT_COLOR, fg="white", width=14, command=self.toggle_pause, relief="flat")
        self.play_pause_btn.pack(side="left", padx=15)

        self.canvas = tk.Canvas(main_area, bg=BG_COLOR, highlightthickness=0)
        self.scroll_frame = tk.Frame(self.canvas, bg=BG_COLOR)
        self.canvas.create_window((0, 0), window=self.scroll_frame, anchor="nw", width=800)
        self.canvas.pack(side="left", fill="both", expand=True, padx=25, pady=15)
        self.scroll_frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind_all("<MouseWheel>", lambda e: self.canvas.yview_scroll(int(-1*(e.delta/120)), "units"))

    def bind_keys(self):
        """Биндим горячие клавиши."""
        self.root.bind("<space>", lambda e: self.toggle_pause())
        self.root.bind("<Right>", lambda e: self.fast_forward(10))
        self.root.bind("<Left>", lambda e: self.fast_forward(-10))

    def fast_forward(self, seconds):
        if self.current_track_path:
            current_pos = (pygame.mixer.music.get_pos() / 1000) + self.current_start_time
            self.play_music(self.current_track_path, start_time=max(0, current_pos + seconds))

    def on_local_search_change(self, event):
        if self.after_id: self.root.after_cancel(self.after_id)
        self.after_id = self.root.after(200, self.refresh_list)

    def refresh_list(self):
        for w in self.scroll_frame.winfo_children(): w.destroy()
        sq = self.local_search.get().lower()
        d = BASE_PATH if self.current_playlist == "All" else os.path.join(BASE_PATH, self.current_playlist)
        if os.path.exists(d):
            self.tracks_files = [os.path.join(d, f) for f in sorted(os.listdir(d)) if f.endswith(".mp3")]
            for f_path in self.tracks_files:
                if sq in os.path.basename(f_path).lower():
                    self.add_track_ui(f_path)

    def add_track_ui(self, f_path):
        frame = tk.Frame(self.scroll_frame, bg=TRACK_BG, cursor="hand2")
        frame.pack(fill="x", pady=2, ipady=7, padx=5)
        tk.Label(frame, text="🎵", fg=ACCENT_COLOR, bg=TRACK_BG).pack(side="left", padx=12)
        lbl = tk.Label(frame, text=os.path.basename(f_path)[:-4], fg="white", bg=TRACK_BG)
        lbl.pack(side="left")
        for w in [frame, lbl]: w.bind("<Button-1>", lambda e: self.play_music(f_path))

    def play_music(self, path, start_time=0):
        self.current_track_path = path
        self.current_start_time = start_time
        pygame.mixer.music.load(path)
        pygame.mixer.music.play(start=start_time)
        self.is_paused = False
        self.play_pause_btn.config(text="PAUSE")

    def toggle_pause(self):
        if self.is_paused: pygame.mixer.music.unpause(); self.play_pause_btn.config(text="PAUSE")
        else: pygame.mixer.music.pause(); self.play_pause_btn.config(text="PLAY")
        self.is_paused = not self.is_paused

    def on_slider_move(self, val):
        if self.current_track_path and self.is_dragging:
            self.play_music(self.current_track_path, start_time=float(val))

    def update_playback_info(self):
        if self.current_track_path and (pygame.mixer.music.get_busy() or self.is_paused):
            try:
                audio = MP3(self.current_track_path)
                self.seek_slider.config(to=audio.info.length)
                if not self.is_dragging:
                    curr = (pygame.mixer.music.get_pos() / 1000) + self.current_start_time
                    self.seek_slider.set(curr)
            except: pass
        
        # Автопереключение
        if self.current_track_path and not pygame.mixer.music.get_busy() and not self.is_paused:
            if self.loop_mode == "loop_one": self.play_music(self.current_track_path)
            else: self.play_next()

        self.root.after(500, self.update_playback_info)

    def play_next(self):
        if hasattr(self, 'tracks_files') and self.current_track_path in self.tracks_files:
            idx = (self.tracks_files.index(self.current_track_path) + 1) % len(self.tracks_files)
            self.play_music(self.tracks_files[idx])

    def toggle_loop(self):
        self.loop_mode = "loop_one" if self.loop_mode == "sequence" else "sequence"
        self.loop_btn.config(text=f"MODE: {self.loop_mode.upper()}", bg=ACCENT_COLOR if self.loop_mode=="loop_one" else "#333")

    def start_web_download(self):
        q = self.web_search.get()
        if q: threading.Thread(target=self.download_task, args=(q,), daemon=True).start(); self.web_search.delete(0, tk.END)

    def download_task(self, query):
        try:
            s = self.client.search(query)
            if s.tracks:
                t = s.tracks.results[0]
                name = f"{', '.join([a.name for a in t.artists])} - {t.title}.mp3".replace("/", "-")
                p = os.path.join(BASE_PATH, "" if self.current_playlist == "All" else self.current_playlist, name)
                t.download(p); self.root.after(0, self.refresh_list)
        except: pass

    def update_playlists_view(self):
        self.pl_listbox.delete(0, tk.END); self.pl_listbox.insert(tk.END, "All")
        for d in sorted([d for d in os.listdir(BASE_PATH) if os.path.isdir(os.path.join(BASE_PATH, d))]): self.pl_listbox.insert(tk.END, d)

    def add_playlist_dialog(self):
        n = simpledialog.askstring("NEW", "Name:")
        if n: p = os.path.join(BASE_PATH, n); os.makedirs(p, exist_ok=True); self.update_playlists_view()

    def change_playlist(self, event):
        s = self.pl_listbox.curselection()
        if s: self.current_playlist = self.pl_listbox.get(s); self.refresh_list()

if __name__ == "__main__":
    root = tk.Tk(); app = MusicApp(root); root.mainloop()
