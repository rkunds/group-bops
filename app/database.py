from pymongo import MongoClient
import requests
import random
import json
import string


client = MongoClient("put link to mongodb db here")

user_ref = client.spotify.users
room_ref = client.spotify.rooms


def create_user(uuid, token):
    if user_ref.count_documents({"uuid": uuid}, limit=1) != 0:
        return
    else:
        request = requests.get("https://api.spotify.com/v1/me", headers={
                               "Authorization": "Bearer {token}".format(token=token["access_token"])}).json()

        user = {
            "uuid": uuid,
            "spotify_id": request["id"],
            "username": request["display_name"],
            "email": request["email"],
            "img_url": request["images"][0]["url"],
            "likedsongs": [],
            "nextsongs": [],
            "playlist_id": ""
        }

        user_ref.insert_one(user)

        return user


def create_room():
    roomid = "".join(random.choice(string.ascii_uppercase) for _ in range(6))
    if room_ref.count_documents({"roomid": roomid}, limit=1) != 0:
        return create_room()
    else:
        room_ref.insert_one(
            {
                "roomid": roomid,
                "users": [],
                "likedsongs": [],
            }
        )
        return roomid


def create_room(roomid):
    if room_ref.count_documents({"roomid": roomid}, limit=1) != 0:
        return create_room("".join(random.choice(string.ascii_uppercase) for _ in range(6)))

    room_ref.insert_one({
        "roomid": roomid,
        "users": [],
        "likedsongs": []
    })

    return roomid
##########


def user_join_room(uuid, roomid):
    if room_ref.count_documents({"roomid": roomid}, limit=1) == 0:
        create_room(roomid)
    room_ref.update_one({"roomid": roomid}, {"$addToSet": {"users": uuid}})
    return roomid


def user_leave_room(uuid, roomid):
    room_ref.update_one({"roomid": roomid}, {"$pull": {"uuid": uuid}})

##########


def user_like_song(uuid, songid):
    user_ref.update_one({"uuid": uuid}, {"$push": {"likedsongs": songid}})


def update_room_liked(roomid):
    song_list = set()

    users = room_ref.find_one({"roomid": roomid})

    users = users["users"]

    for user in users:
        songs = user_ref.find_one({"uuid": user})["likedsongs"]
        if songs is None:
            return None
        for song in songs:
            song_list.add(song)

    for song in song_list:
        num = 0
        for u in users:
            if song in user_ref.find_one({"uuid": u})["likedsongs"]:
                num += 1
        if num == len(users) and num != 1:
            room_ref.update_one({"roomid": roomid}, {
                                "$push": {"likedsongs": song}})


def get_next_song(uuid, roomid, token):
    songlist = user_ref.find_one({"uuid": uuid})["nextsongs"]

    if len(songlist) == 0:
        songs = generate_songs(token, roomid)
        if songs is None:
            return "add more songs"
        elif not songs:
            return False

        songlist = user_ref.find_one({"uuid": uuid})["nextsongs"]

    song = songlist.pop(0)

    user_ref.update_one({"uuid": uuid}, {"$set": {"nextsongs": songlist}})

    return song


def generate_songs(token, roomid):
    token = token["access_token"]

    room = room_ref.find_one({"roomid": roomid})
    users = room["users"]

    likedsongs = room["likedsongs"]

    songlist = set()
    songgens = []
    print(likedsongs)
    if len(likedsongs) == 0:
        for u in users:
            user = user_ref.find_one({"uuid": u})["likedsongs"]
            for song in user:
                songlist.add(song)

            if len(songlist) == 0:
                return None
    else:
        if len(likedsongs) <= 5:
            for song in likedsongs:
                songlist.add(song)

        else:
            for _ in range(5):
                songlist.add(likedsongs.pop(
                    random.randrange(0, len(likedsongs) - 1)))

    songlist = list(songlist)

    while len(songlist) > 0:
        songgens.append(songlist.pop(random.randrange(len(songlist))))

    while not len(songgens) <= 5:
        songgens.pop(random.randrange(len(songgens)))

    song_uri = ",".join(songgens)
    print(song_uri)
    song_json = []

    request = requests.get("https://api.spotify.com/v1/recommendations?limit=10&market=US&seed_tracks=" +
                           song_uri, headers={"Authorization": "Bearer {token}".format(token=token)}).json()
    if "tracks" not in request:
        return False
    songs = request["tracks"]
    for song in songs:
        song_data = {
            "artist": song["artists"][0]["name"],
            "artist_url": song["artists"][0]["external_urls"]["spotify"],
            "song_url": song["external_urls"],
            "song_id": song["id"],
            "song_name": song["name"],
            "song_preview": song["preview_url"],
            "song_img": song["album"]["images"][0]["url"],
            "song_uri": song["uri"]
        }

        if song_data["song_preview"] is None:
            song_data["song_preview"] = requests.get("https://api.spotify.com/v1/tracks/" + song_data["song_id"] + "?market=US", headers={
                                                     "Authorization": "Bearer {auth_token}".format(auth_token=token)}).json()["preview_url"]

        song_json.append(song_data)

    update_room_liked(roomid)

    update_room_queue(roomid, song_json)

    return song_json


def update_room_queue(roomid, song_json):
    users = room_ref.find_one({"roomid": roomid})["users"]
    for user in users:
        user_ref.update_one({"uuid": user}, {"$set": {"nextsongs": song_json}})


def get_room_liked(roomid, token):
    room_liked = room_ref.find_one({"roomid": roomid})["likedsongs"]
    token = token["access_token"]
    if len(room_liked) == 0:
        return []
    else:
        song_list = []
        headers = {"Authorization": "Bearer {token}".format(token=token)}
        for song in room_liked:
            r = requests.get(
                "https://api.spotify.com/v1/tracks/" + song, headers=headers).json()
            song_list.append({
                "artistName": r["artists"][0]["name"],
                "songName": r["name"]
            })
        return song_list


def get_user_liked(uuid, token):
    user_liked = user_ref.find_one({"uuid": uuid})["likedsongs"]
    token = token["access_token"]
    if len(user_liked) == 0:
        return []
    else:
        song_list = []
        headers = {"Authorization": "Bearer {token}".format(token=token)}
        for song in user_liked:
            r = requests.get(
                "https://api.spotify.com/v1/tracks/" + song, headers=headers).json()
            song_list.append({
                "artistName": r["artists"][0]["name"],
                "songName": r["name"]
            })
        return song_list


def generate_room_playlist(roomid, uuid, playlist_name, playlist_desc, token):
    room = room_ref.find_one({"roomid": roomid})
    room_liked = room["likedsongs"]
    if not len(room_liked) > 0:
        return {
            "error": {
                "message": "not enough songs"
            },
            "code": 400,
            "message": "not enough songs"
        }

    headers = {"Authorization": "Bearer {token}".format(
        token=token["access_token"]), "Content-Type": "application/json"}
    spotify_id = user_ref.find_one({"uuid": uuid})["spotify_id"]

    requests.delete("https://api.spotify.com/v1/playlists/" + user_ref.find_one(
        {"uuid": uuid})["playlist_id"] + "/followers", headers=headers)

    playlist = requests.post("https://api.spotify.com/v1/users/" + spotify_id + "/playlists", headers=headers, data=json.dumps({
        "name": playlist_name,
        "description": playlist_desc,
        "public": False,
        "collaborative": True,
    })).json()

    print(playlist)
    data = {
        "uris": []
    }

    for song in room_liked:
        data["uris"].append("spotify:track:" + song)

    user_ref.update_one(
        {"uuid": uuid}, {"$set": {"playlist_id": playlist["id"]}})

    print(requests.post("https://api.spotify.com/v1/playlists/" +
          playlist["id"] + "/tracks", headers=headers, data=json.dumps(data)))

    return {
        "playlist_url": ("https://open.spotify.com/playlist/" + playlist["id"]),
        "playlist_name": playlist_name
    }
