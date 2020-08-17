import requests


def search_song(song_title, artist_name, base_url, headers):
    """
    Will search for a song based on the song and artist provided
    """
    search_url = base_url + '/search'
    if "(" in song_title:
        song_title = song_title.split('(')[0].rstrip()
    if "-" in song_title:
        song_title = song_title.split('-')[0].rstrip()
    print(song_title, artist_name)
    data = {'q': song_title + ' ' + artist_name}
    response = requests.get(search_url, data=data, headers=headers)
    json = response.json()

    if len(json['response']['hits']) == 0:  # No results found
        return None
    else:
        api_path = json['response']['hits'][0]['result']['api_path']

    return api_path


def get_song_info(api_path, base_url, headers):
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

    def get_about_info(about_parragraph):
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


# print(search_song('Tokyo Drifting (with Denzel Curry)', 'Glass Animals'))
# print(get_song_info("/songs/3647572"))


# json['response']['song']['description']['dom']['children'][0]['children'][0]
