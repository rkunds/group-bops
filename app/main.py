import os
import spotipy
import uuid
import requests
import random
import string
import database as db

from dotenv import load_dotenv
from flask import Flask, render_template, session, request, redirect
from time import time

load_dotenv()

app = Flask(__name__)
app.secret_key = os.urandom(24)

CLIENT_ID = os.environ.get("APP_ID")
CLIENT_SEC = os.environ.get("APP_KEY")

SCOPE = "user-top-read, user-library-read, playlist-modify-public, playlist-modify-private, user-read-email"
REDIRECT_URI = "https://rkunds-group-bops.uk.r.appspot.com/user/login/callback"


@app.route("/")
def index():
    return render_template("index.html", **get_data())


@app.route("/user/login")
def user_login():
    sp_oauth = spotipy.oauth2.SpotifyOAuth(
        client_id=CLIENT_ID, client_secret=CLIENT_SEC, scope=SCOPE, redirect_uri=REDIRECT_URI)
    auth_url = sp_oauth.get_authorize_url()
    return redirect(auth_url)


@app.route("/user/login/callback")
def callback():
    if session.get("uuid") is None:
        session["uuid"] = str(uuid.uuid4())

    oauth = spotipy.oauth2.SpotifyOAuth(
        client_id=CLIENT_ID, client_secret=CLIENT_SEC, scope=SCOPE, redirect_uri=REDIRECT_URI)
    code = request.args.get("code")
    token = oauth.get_access_token(code)

    session["token"] = token

    user = db.create_user(session.get("uuid"), session.get("token"))

    session["username"] = user["username"]
    session["email"] = user["email"]
    session["img_url"] = user["img_url"]

    return redirect("/user/home")


@app.route("/user/logout")
def logout():
    session.clear()
    return redirect("/")


@app.route("/user/home")
def user_home():
    return redirect("/")


def refresh_token():
    if session.get("token") is None:
        return False

    token = session.get("token")

    if (token["expires_at"] - time()) < 0:
        oauth = spotipy.oauth2.SpotifyOAuth(
            client_id=CLIENT_ID, client_secret=CLIENT_SEC, scope=SCOPE, redirect_uri=REDIRECT_URI)
        token = oauth.refresh_access_token(
            session.get("token").get("refresh_token"))

        session["token"] = token

    return True


@app.route("/createroom")
def create_room():
    roomid = ''.join(random.choice(string.ascii_uppercase) for _ in range(6))
    roomid = db.create_room(roomid)
    return redirect("/room/" + roomid + "/songchoice")


@app.route("/room/<roomid>")
def join_room(roomid):
    if not refresh_token():
        return redirect("/user/login")
    data = get_data()
    roomid = roomid.upper()
    roomid = db.user_join_room(session.get("uuid"), roomid)
    return render_template("room.html", roomid=roomid, **data)


@app.route("/room/<roomid>/songchoice")
def songchoice(roomid):
    roomid = roomid.upper()
    return render_template("songchoice.html", roomid=roomid, **get_data())


@app.route("/room/<roomid>/leave")
def leave_room(roomid):
    db.user_leave_room(session.get("uuid"), roomid)
    return redirect("/user/home")


@app.route("/user/like")
def user_like_song():
    songid = request.args.get("songid")
    db.user_like_song(session.get("uuid"), songid)
    return f"song {songid} has been added to {session.get('uuid')}"


@app.route("/song/search")
def song_search():
    song_name = request.args.get("q")
    result_data = []

    if song_name:
        token = session.get("token")["access_token"]
        headers = {"Authorization": "Bearer {token}".format(token=token)}
        request_data = requests.get("https://api.spotify.com/v1/search" + "?q=" + song_name +
                                    "&market=US&type=track&limit=5", headers=headers).json()["tracks"]["items"]

        for song in request_data:
            song_data = {
                "artist": song["artists"][0]["name"],
                "artist_url": song["artists"][0]["external_urls"]["spotify"],
                "song_url": song["external_urls"]["spotify"],
                "songid": song["id"],
                "song_name": song["name"],
                "song_img": song["album"]["images"][0]["url"]
            }
            result_data.append(song_data)

    return render_template("searchresults.html", results=result_data)


@app.route("/room/<roomid>/getnext")
def get_next(roomid):
    if not refresh_token():
        return redirect("/user/login")
    songs = db.get_next_song(session.get("uuid"), roomid, session.get("token"))
    if not songs:
        return redirect("/user/login")
    elif songs == "add more songs":
        return redirect("/room/" + roomid + "/songchoice")
    return db.get_next_song(session.get("uuid"), roomid, session.get("token"))


@app.route("/room/<roomid>/getplaylist")
def get_nav(roomid):
    return render_template("getplaylist.html", roomid=roomid, **get_data())


@app.route("/room/<roomid>/genplaylist")
def get_playlist(roomid):
    refresh_token()
    playlist_name = request.args.get("name")
    playlist_desc = ""
    if "desc" in request.args:
        playlist_desc = request.args.get("desc")
    playlist = db.generate_room_playlist(roomid, session.get(
        "uuid"), playlist_name, playlist_desc, session.get("token"))
    if "error" in playlist:
        return playlist
    return {"playlist": playlist}


def get_data():
    if session.get("uuid") is None:
        return {"logged_in": False}
    else:
        return {
            "logged_in": True,
            "uuid": session.get("uuid"),
            "username": session.get("username"),
            "email": session.get("email"),
            "img_url": session.get("img_url"),
        }


if __name__ == "__main__":
    app.run()