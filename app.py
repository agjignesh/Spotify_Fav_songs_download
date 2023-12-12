from flask import Flask, render_template, request, redirect, url_for, send_file, session, send_file
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import time
from pytube import YouTube
from pytube import Search
import os
import shutil
import music_tag


app = Flask(__name__)
all_songs = []

app.secret_key = "spotify-login-session"
app.config['SESSION_COOKIE_NAME'] = 'spotify-login-session'
Token_info = "token_info"

@app.route('/')
def login():
    sp_oauth = create_spotify_Oauth()
    auth_url = sp_oauth.get_authorize_url()
    if(os.path.exists('.cache')):
        os.remove('.cache')
    
    if(os.path.exists('songs.zip')):
        os.remove('songs.zip')
    
    return render_template('index.html', auth_url=auth_url)

@app.route('/authorize')
def authorize():
    sp_oauth = create_spotify_Oauth()
    session.clear()
    code = request.args.get('code')
    token_info = sp_oauth.get_access_token(code)
    session[Token_info] = token_info
    return redirect(url_for('songs', _external=True))


@app.route('/songs')
def songs():
    try :
        access_token = get_token()
    except :
        return redirect(url_for("login"))
    
    sp = spotipy.Spotify(access_token)
    
    
    i = 0
    while True:
        items = sp.current_user_saved_tracks(limit=50, offset=i*50)['items']
        for item in items:
            if(len(item['track']['name'])<5 or item['track']['duration_ms']/1000>600):
                continue
            all_songs.append((item['track']['name'], item['track']['duration_ms']/1000, item['track']['artists'][0]['name'], item['track']['album']['name'], item['track']['album']['release_date']))
        if len(items) < 50:
            break
        i += 1
    session['songs'] = all_songs
    return render_template('songs.html', songs=all_songs)

@app.route('/downloading')
def downloading():
    if(len(all_songs)==0):
        return redirect(url_for('login'))
    return download_song(all_songs)


# def MP4ToMP3(mp4, mp3):
#     FILETOCONVERT = AudioFileClip(mp4)
#     FILETOCONVERT.write_audiofile(mp3)
#     FILETOCONVERT.close()

def add_metadata(mp3, song, artist, album, release_date):
    file = music_tag.load_file(mp3)
    file['title'] = song
    file['artist'] = artist
    file['album'] = album
    file['year'] = release_date
    file.save()
    # audiofile = eyed3.load(mp3)
    # audiofile.tag.artist = artist
    # audiofile.tag.album = album
    # audiofile.tag.title = song
    # audiofile.tag.release_date = release_date
    # audiofile.tag.save()

def download_song(songs):
    # download all the songs in the list songs into a new folder songs
    if not os.path.exists("songs"):
        os.mkdir("songs")
        os.chdir("songs")
    else:
        os.chdir("songs")
        for file in os.listdir():
            os.remove(file)

    start_time = time.time()

    for song, duration, artist, album, date in songs:
        
        # if more then 10 min have passed since the start, stop
        if(time.time()-start_time>600):
            break

        # print()
        # print("--------------------------------------------------")
        # print(f"Downloading {song} by {artist}")
        # print("--------------------------------------------------")


        s = Search(f"{song} by {artist} song")
        for i in s.results:
            if(i.length>=duration-5 and i.length<=duration+5):
                ori_path = i.streams.get_audio_only().download()
                new_path = ori_path[:-4] + '.mp3'
                if not os.path.exists(new_path):
                    os.rename(ori_path, new_path)
                    add_metadata(new_path, song, artist, album, date)
                break
        else:
            print(f"{song} not found")
    os.chdir("..")

    if(os.path.exists('songs.zip')):
        os.remove('songs.zip')
    shutil.make_archive('songs', 'zip', 'songs')

    return send_file('songs.zip', as_attachment=True)


def get_token():
    token_info = session.get(Token_info, None)
    if not token_info:
        raise "exception"
    now = int(time.time())
    is_expired = token_info['expires_at'] - now < 60 
    if (is_expired):
        sp_oauth = create_spotify_Oauth()
        token_info = sp_oauth.refresh_access_token(token_info['refresh_token'])
    return token_info['access_token']

def create_spotify_Oauth():
    return SpotifyOAuth(
        client_id="d05e844b98594009899fd6e3d355455f",
        client_secret="24d00a7095be4fa29f05c52fe58bb061",
        redirect_uri = url_for('authorize', _external=True),
        scope="user-library-read",
    )


# if __name__ == '__main__':
#     app.run(debug=True)
