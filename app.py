from flask import Flask, render_template, request, redirect, url_for, send_file, session
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import time
from pytube import Search
import os
import shutil
import music_tag
from threading import Thread
import json
import logging


# Set up logging
logging.basicConfig(level=logging.INFO)

app = Flask(__name__)

# Use environment variables for secrets
app.secret_key = "spotify-login-session"
app.config['SESSION_COOKIE_NAME'] = 'spotify-login-session'

# Use a constant for the token info session key
TOKEN_INFO_KEY = "token_info"

# Initialize download status
download_status = 0

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

# Login route
@app.route('/')
def login():
    sp_oauth = create_spotify_Oauth()
    auth_url = sp_oauth.get_authorize_url()

    # Change to base directory
    base_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(base_dir)
    
    # Clear cache and old songs
    for path in ['.cache', 'songs.zip', 'songs']:
        if os.path.exists(path):
            if os.path.isfile(path):
                os.remove(path)
            else:
                shutil.rmtree(path)
    
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
    
    sp = spotipy.Spotify(access_token)
    songs_to_download = fetch_saved_tracks(sp)
    
    global download_status
    download_status = 0
    
    t = Thread(target=download_song, args=(songs_to_download,))
    t.start()
    session.clear()

    return render_template('downloading.html')

# Status route
@app.route('/status', methods=['GET'])
def getStatus():
  statusList = {'status': download_status}
  return json.dumps(statusList)

# Downloaded route
@app.route('/downloaded')
def downloaded():
    session.clear()
    return send_file('songs.zip', as_attachment=True)

# Add metadata to song
def add_metadata(mp3, song, artist, album, release_date):
    file = music_tag.load_file(mp3)
    file['title'] = song
    file['artist'] = artist
    file['album'] = album
    file['year'] = release_date
    file.save()

# Download song
def download_song(songs):
    global download_status
    if not os.path.exists("songs"):
        os.mkdir("songs")
    
    os.chdir("songs")

    start_time = time.time()
    no_of_songs = len(songs)
    itr = 0

    for song, duration, artist, album, date in songs:
        logging.info(f"Downloading {song} by {artist}")

        s = Search(f"{song} by {artist} song")
        for i in s.results:
            if(i.length>=duration-10 and i.length<=duration+10):
                ori_path = i.streams.get_audio_only().download()
                new_path = ori_path[:-4] + '.mp3'
                if not os.path.exists(new_path):
                    os.rename(ori_path, new_path)
                    add_metadata(new_path, song, artist, album, date)
                break
        else:
            logging.warning(f"{song} not found")
        
        download_status = (itr+1)*100//no_of_songs
        itr += 1

    # Change to base directory
    base_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(base_dir)

    if os.path.exists('songs.zip'):
        os.remove('songs.zip')    

    if os.path.exists('songs'):
        shutil.make_archive('songs', 'zip', 'songs')
        shutil.rmtree('songs')
    else:
        return redirect(url_for("login", _external=True))

# if __name__ == '__main__':
#     app.run(debug=True)
