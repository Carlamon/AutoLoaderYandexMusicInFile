from yandex_music import Client
from yandex_music.exceptions import NetworkError
import time
from YM__client_token import token

TOKEN = token
client = Client(TOKEN).init()
client.request._timeout = 60 

liked_tracks = client.users_likes_tracks()

print("Скачиваю треки из избранного! ")

for item in liked_tracks:
    try:
        track = item.fetch_track()
        print(f"Лайкнут: {track.title}")
        # Поиск трека
        search_query = f"{track.title} {track.artists[0].name}"
        search_result = client.search(search_query)
        # Скачивание
        track.download(f'music/{track.title}.mp3')  
        print(f'Трек {track.title} скачан.')
    except Exception as e:
        print(f"Ошибка при загрузки трека - {track.title} {track.artists[0].name}: {e}")
        time.sleep(2.5)
        continue
print("Скачивание плейлиста закончено.")

