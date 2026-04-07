from yandex_music import Client
from YM__client_token import token

token = token
client = Client(token).init()
client.request._timeout = 60

track_list = []
while True:
    track = input("Введите название трека и автора:- ")
    if track == '0' or track == 'exit':
        print(f"Ваш трек лист для скачивания {track_list}")
        break
    else:
        track_list.append(track)


# Поиск трека
for track in track_list:
    search_result = client.search(track)
    track = search_result.tracks.results[0]
# Скачивание
    track.download(f'music/{track.title}.mp3')  
    print(f'Трек {track.title} скачан.')