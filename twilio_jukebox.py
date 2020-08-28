from twilio.twiml.messaging_response import MessagingResponse
from flask import Flask, request, session
from spotipy.oauth2 import SpotifyOAuth
import spotipy
import os
import requests
from dotenv import load_dotenv
load_dotenv()

app = Flask(__name__)

app.secret_key = os.environ.get("FLASK_APP_SECRET")


@app.route("/jukebox", methods=['POST'])
def jukebox():
    """
    Chatbot's main logic
    """
    valid_response = False
    resp_messages = []
    # Incoming message
    incoming_msg = request.values.get('Body', '').lower()

    if (incoming_msg == 'search' and 'search' not in session) \
            or incoming_msg == 'search-again':
        resp_message = create_help_message("ask_search")
        resp_messages.append(resp_message)
        session['results'] = []
        session['search'] = True
        session['offset'] = 0
        session['next_result'] = True
        valid_response = True
        resp = send_message(resp_messages)

    elif incoming_msg == 'more' \
            and session['search'] \
            and len(session['results']) > 0 \
            and session['next_result']:
        results, next = search(
            session['search_str'], session['offset'], session['results'])
        resp_message = respond_results(results, session['offset'])
        resp_messages.append(resp_message)
        session['offset'] += 8
        valid_response = True
        if next is None:
            help_message = create_help_message("all_results")
            session['next_result'] = False
        else:
            help_message = create_help_message("more_results")
            session['next_result'] = True
        resp_messages.append(help_message)
        resp = send_message(resp_messages)

    elif incoming_msg == 'more' and not session['next_result']:
        help_message = create_help_message("more_with_no_results")
        resp_messages.append(help_message)
        resp = send_message(resp_messages)
        valid_response = True

    elif 'search' in session \
            and not incoming_msg.isnumeric() \
            and (
                incoming_msg != 'search-again'
                and incoming_msg != 'stop-search'
            ):
        results, next = search(incoming_msg, 0, [])
        if results == []:
            help_message = create_help_message("no_results")
        else:
            session['results'] = results
            resp_message = respond_results(results, session['offset'])
            resp_messages.append(resp_message)
            session['offset'] += 8
            session['search_str'] = incoming_msg
            if next is None:
                help_message = create_help_message("all_results")
                session['next_result'] = False
            else:
                help_message = create_help_message("more_results")
                session['next_result'] = True
        resp_messages.append(help_message)
        resp = send_message(resp_messages)
        valid_response = True

    elif incoming_msg.isnumeric() and int(incoming_msg) in [
            result[0] for result in session['results']]:
        # Valid response with an integer that corresponds to a displayed song
        current_songs_in_playlist = get_playlist_songs()
        selected_song_uri = session['results'][int(incoming_msg)-1][4]
        selected_song_name = session['results'][int(incoming_msg)-1][1]
        selected_song_artist = session['results'][int(incoming_msg)-1][3]

        if selected_song_uri in current_songs_in_playlist:
            help_message = create_help_message("song_selected")
        else:
            add_song_to_playlist(selected_song_uri)
            help_message = "Great! The song _{}_ has been added to the " \
                "playlist. Have fun!".format(selected_song_name)
            fun_fact = get_fun_fact(selected_song_name, selected_song_artist)
            session.clear()
        resp_messages.append(help_message)
        if selected_song_uri not in current_songs_in_playlist \
                and fun_fact is not None:
            resp_messages.append(fun_fact)
        resp = send_message(resp_messages)
        valid_response = True

    elif incoming_msg == 'stop-search':
        session.clear()
        help_message = "Got it. Bye!"
        resp_messages.append(help_message)
        resp = send_message(resp_messages)
        valid_response = True

    if valid_response is False:
        resp_message = create_help_message("help")
        resp_messages.append(resp_message)
        resp = send_message(resp_messages)

    print(session)

    return str(resp)


def send_message(messages):
    """
    Receives a list and sends the TwiML response message(s)
    """
    resp = MessagingResponse()

    for message in messages:
        resp.message(message)

    return resp


def create_help_message(message):
    """
    List of response messages depending on what needs to be sent back
    to the user.
    """
    if message == "ask_search":
        return "Ok, which song / album / artist are you looking for? " \
            "Try being as specific as possible. E.g.: _Bad Michael Jackson_"
    elif message == "all_results":
        return "These are all the results. Please type the " \
            "number of the song you would like to add to the playlist " \
            "(example: *9*) or type *search-again* to start a new search. " \
            "You can type *stop-search* to end at any time"
    elif message == "more_results":
        return "Please type the number of the song you would like to add to " \
            "the playlist (Example: *9*). If you would like to see more " \
            "results, type *more* or *search-again* to start a new search. " \
            "You can type *stop-search* to end at any time"
    elif message == "no_results":
        return "No results found. Please try again. You can type " \
            "*stop-search* to end at any time"
    elif message == "more_with_no_results":
        return "No more results are available. Please type the number of " \
            "the song you would like to add to the playlist (Example: *9*) " \
            "or type *search-again* to start a new search. You can type " \
            "*stop-search* to end at any time"
    elif message == "song_selected":
        return "The selected song is already on the playlist. Please select " \
            "a different one or type *search-again* to start a new search"
    elif message == "help":
        return "Hello! I can help you search and add music to our Spotify " \
            "playlist. Let's type *search* to begin!"


def get_user_token():
    """
    Obtain an access token from Spotify
    """
    oauth = SpotifyOAuth(
        username=os.environ.get("SPOTIPY_CLIENT_USERNAME"),
        scope='playlist-modify-private'
    )
    user_token = oauth.get_access_token(as_dict=False, check_cache=True)

    return user_token


def create_spotify_client():
    """
    Creates Spotify API client
    """
    user_token = get_user_token()
    spotify = spotipy.Spotify(auth=user_token)

    return spotify


def search(search_str, offset_val=0, results=[]):
    """
    Returns a list of coincidences either on songs, albums or artists as well
    as if there are more results to show next
    """
    spotify = create_spotify_client()
    api_results = spotify.search(
        q=search_str,
        limit=8,
        market=os.environ.get("SPOTIFY_MARKET"),
        offset=offset_val
    )
    items = api_results['tracks']['items']
    next = api_results['tracks']['next']

    if len(items) > 0:
        for id, item in enumerate(items):
            song = item['name']
            album = item['album']['name']
            artist = item['artists'][0]['name']
            uri = item['uri']
            new_item = [id+1+int(offset_val), song, album, artist, uri]
            results.append(new_item)

    return results, next


def respond_results(results, offset_val):
    """
    Receives the search result and formats it to text for response
    """
    text_results = ''

    for i in range(offset_val, len(results)):
        text_results += "{}.  🎵 {} \n     💿 {} \n     👤 {} \n" \
            "---------------------------------\n".format(
                results[i][0], results[i][1], results[i][2], results[i][3])

    return text_results


def get_playlist_songs():
    """
    Retrieve the list uris from the songs in the playlist
    """
    spotify = create_spotify_client()
    results = spotify.user_playlist(
        user=os.environ.get("SPOTIPY_CLIENT_USERNAME"),
        playlist_id=os.environ.get("SPOTIFY_PLAYLIST_URI")
    )
    items = results['tracks']['items']

    return [item['track']['uri'] for item in items if len(items) > 0]


def add_song_to_playlist(uri):
    """
    Will add the selected song to the playlist by song uri
    """
    spotify = create_spotify_client()

    spotify.user_playlist_add_tracks(
        user=os.environ.get("SPOTIPY_CLIENT_USERNAME"),
        playlist_id=os.environ.get("SPOTIFY_PLAYLIST_URI"),
        tracks=[uri])

    return spotify


def get_fun_fact(song_title, artist_name):
    """
    Will get the information retrieved from the Genius API and send it
    back to the user. In case there is no information, will return None
    """
    base_url = 'https://api.genius.com'
    headers = {
        'Authorization':
        'Bearer ' +
        os.environ.get("GENIUS_ACCESS_TOKEN")
    }
    api_path = search_song_on_genius(
        song_title, artist_name, base_url, headers
    )

    if api_path is None:
        return None
    else:
        fun_fact_message = get_song_info_from_genius(
            api_path, base_url, headers
        )

    if len(fun_fact_message) > 1:
        return "_Did you know...?_ 🤔💭\n\n" + fun_fact_message
    else:
        return None


def search_song_on_genius(song_title, artist_name, base_url, headers):
    """
    Will search for a song based on the song and artist provided
    """
    search_url = base_url + '/search'

    if "(feat" in song_title or "(with" in song_title:
        song_title = song_title.split('(')[0].rstrip()
    if "-" in song_title:
        song_title = song_title.split('-')[0].rstrip()

    data = {'q': song_title + ' ' + artist_name}
    response = requests.get(search_url, data=data, headers=headers)
    json = response.json()

    if len(json['response']['hits']) == 0:  # No results found
        return None
    else:
        api_path = json['response']['hits'][0]['result']['api_path']

    return api_path


def get_song_info_from_genius(api_path, base_url, headers):
    """
    Will loop through the structure looking for the text that corresponds
    to the first "about" paragraph of a specific song by path
    """
    song_url = base_url + api_path
    response = requests.get(song_url, headers=headers)
    json = response.json()
    resp_song = json['response']['song']
    resp_description = resp_song['description']['dom']['children']
    about_paragraph = resp_description[0]['children']

    def get_about_info(about_paragraph):
        song_fact = ''
        try:
            for parent in about_paragraph:
                if type(parent) == str:
                    song_fact += parent
                else:
                    song_fact += get_about_info(parent['children'])
        except KeyError:
            return song_fact
        return song_fact

    song_fact = get_about_info(about_paragraph)

    return song_fact


if __name__ == "__main__":
    app.run(debug=True)
