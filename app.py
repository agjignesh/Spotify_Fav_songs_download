from flask import Flask, render_template, request, redirect, url_for, send_file, session, after_this_request
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import time
from pytube import Search
import os
import shutil
from threading import Thread
import json
import logging
from moviepy.editor import *
import eyed3

time_till = 3000

# Set up logging
logging.basicConfig(level=logging.INFO)

app = Flask(__name__)

# Use environment variables for secrets
app.secret_key = "asdfsdfer79847997974fdafadfa"
app.config['SESSION_COOKIE_NAME'] = 'fdjsffdsjfa4urwe89eur89'
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0

# Use a constant for the token info session key
TOKEN_INFO_KEY = "token_info"

# Global Threads dict 
threads = {}

# Download_status dict
download_status_dict = {}

# Spotify OAuth
def create_spotify_Oauth():
    return SpotifyOAuth(
        client_id="d05e844b98594009899fd6e3d355455f",
        client_secret="24d00a7095be4fa29f05c52fe58bb061",
        redirect_uri = url_for('authorize', _external=True),
        scope="user-library-read",
    )

# Get access token
def get_token():
    token_info = session.get(TOKEN_INFO_KEY, None)
    if not token_info:
        raise Exception("Token not found in session")
    now = int(time.time())
    is_expired = token_info['expires_at'] - now < 60 
    if (is_expired):
        sp_oauth = create_spotify_Oauth()
        token_info = sp_oauth.refresh_access_token(token_info['refresh_token'])
    return token_info['access_token']

# Fetch user's saved tracks
def fetch_saved_tracks(sp):
    songs = []
    i = 0
    while True:
        items = sp.current_user_saved_tracks(limit=50, offset=i*50)['items']
        for item in items:
            if(len(item['track']['name'])<5 or item['track']['duration_ms']/1000>600):
                continue
            songs.append((item['track']['name'], item['track']['duration_ms']/1000, item['track']['artists'][0]['name'], item['track']['album']['name'], item['track']['album']['release_date']))
        if len(items) < 50:
            break
        i += 1
    return songs

def convertToNumber (s):
    a = str(int.from_bytes(s.encode(), 'little'))
    return a[:2]+a[-4:]

def get_user_unique_id(sp):
    return convertToNumber(sp.current_user()['id'])

def remove_file_after_time(file_name, time_till = 400):
    """time is in seconds"""
    time.sleep(time_till)
    if os.path.exists(file_name):
        os.remove(file_name)
    logging.info(f"Removed {file_name}")


# Login route
@app.route('/')
def login():
    sp_oauth = create_spotify_Oauth()
    auth_url = sp_oauth.get_authorize_url()
    session.clear()
    if(os.path.exists('.cache')):
        os.remove('.cache')
    return render_template('index.html', auth_url=auth_url)


# Authorize route
@app.route('/authorize')
def authorize():
    sp_oauth = create_spotify_Oauth()
    session.clear()
    code = request.args.get('code')
    token_info = sp_oauth.get_access_token(code)
    session[TOKEN_INFO_KEY] = token_info
    return redirect(url_for('songs', _external=True))

# Songs route
@app.route('/songs')
def songs():
    try:
        access_token = get_token()
    except Exception as e:
        logging.error(e)
        return redirect(url_for("login"))
    
    sp = spotipy.Spotify(access_token)
    songs = fetch_saved_tracks(sp)
    return render_template('songs.html', songs=songs)

# Downloading route
@app.route('/downloading')
def downloading():
    try:
        access_token = get_token()
    except Exception as e:
        logging.error(e)
        return redirect(url_for("login"))
    
    global download_status_dict, threads

    sp = spotipy.Spotify(access_token)
    songs_to_download = fetch_saved_tracks(sp)
    user_id = get_user_unique_id(sp)

    if(user_id in threads):
        return render_template('downloading.html', user_id=user_id)

    download_status_dict[user_id] = 0
    threads[user_id] = Thread(target=download_song, args=(songs_to_download, user_id,))
    threads[user_id].start()

    return render_template('downloading.html', user_id=user_id)

# Status route
@app.route('/status/<user_id>', methods=['GET'])
def getStatus(user_id):
  global download_status_dict
  logging.info(user_id)
  statusList = {'status': download_status_dict[user_id]}
  return json.dumps(statusList)

# Downloaded route
@app.route('/downloaded/<user_id>', methods=['GET'])
def downloaded(user_id):

    @after_this_request
    def remove(response):
        global download_status_dict, threads, remove_zip_files

        session.clear()

        if user_id in download_status_dict:
            download_status_dict.pop(user_id)
        if user_id in threads:
            threads.pop(user_id)

        if(os.path.exists('.cache')):
            os.remove('.cache')

        t = Thread(target=remove_file_after_time, args=(f'songs{user_id}.zip',time_till,))
        t.start()

        return response

    return send_file(f'songs{user_id}.zip', as_attachment=True)



def MP4ToMP3(mp4, mp3):
    FILETOCONVERT = AudioFileClip(mp4)
    FILETOCONVERT.write_audiofile(mp3)
    FILETOCONVERT.close()

# Add metadata to song
def add_metadata(mp3, song, artist, album, release_date):
    audiofile = eyed3.load(mp3)
    audiofile.tag.artist = artist
    audiofile.tag.album = album
    audiofile.tag.title = song
    year = release_date[:4] if isinstance(release_date, str) and len(release_date) >= 4 else release_date
    audiofile.tag.release_date = year
    audiofile.tag.save()



# Download song
def download_song(songs, user_id):

    global download_status_dict

    if not os.path.exists(f"songs{user_id}"):
        os.mkdir(f"songs{user_id}")

    no_of_songs = len(songs)
    itr = 0

    for song, duration, artist, album, date in songs:
        logging.info(f"Downloading {song} by {artist}")

        download_status_dict[user_id] = (itr)*100//no_of_songs

        s = Search(f"{song} by {artist} song")
        for i in s.results:
            if(i.length>=duration-10 and i.length<=duration+10):
                ori_path = i.streams.get_audio_only().download(os.path.join(os.getcwd(), f"songs{user_id}"))
                new_path = ori_path[:-4] + '.mp3'
                if not os.path.exists(new_path):
                    MP4ToMP3(ori_path, new_path)
                    os.remove(ori_path)
                    add_metadata(new_path, song, artist, album, date)
                break
        else:
            logging.warning(f"{song} not found")
        
        itr += 1

    if os.path.exists(f'songs{user_id}.zip'):
        os.remove(f'songs{user_id}.zip')    

    if os.path.exists(f'songs{user_id}'):
        shutil.make_archive(f'songs{user_id}', 'zip', f'songs{user_id}')
        shutil.rmtree(f'songs{user_id}')
    else:
        return redirect(url_for("login", _external=True))
    
    download_status_dict[user_id] = 100
    return False



# if __name__ == '__main__':
#     app.run(debug=True)
