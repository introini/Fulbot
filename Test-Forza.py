from bs4 import BeautifulSoup, FeatureNotFound
import pandas as pd
import requests
from time import sleep
import re
from pathlib import Path
import yaml
import praw

class Team:
    def __init__(self, name, locality):
        self.name = name
        self.locality = locality
        self.lineup = []

def game_link(soup, when):
    """
    Return string
    
    soup: BeautifulSoup
    when: string
    """
    link = soup.find('a', {'class': f'MatchlistItem-{when}'})
    return f'https://forzafootball.com{link["href"]}'

def game_time(soup):
    """
    Returns string
    
    soup: BeautifulSoup
    """
    time_div = soup.find('div', {'class': 'MatchInfo-state-text2'})
    return time_div.get_text()

def team(soup, locality):
    """
    Returns string
   
    soup: BeautifulSoup
    locality: string
    """
    team_div = soup.find('a', {'class': f'MatchInfo-{locality}'})
    team_text = team_div.contents[1].get_text()
    return team_text

def score(soup):
    """
    Return string
    
    soup: BeautifulSoup
    """
    score_div = soup.find('div', {'class': 'MatchInfo-state-text'})
    score_text = score_div.get_text().split('-')
    return score_text

def format_score(home_team, score, time, away_team):
    """
    Return string
    
    Markdown format for display

    home: string
    score: list
    time: string
    away_team: string
    """
    formatted_score = f'#### {home_team} {score[0]} {time} {score[1]} {away_team}'
    return formatted_score


def get_event_info(soup, _type, team):
    """
    Return tuple

    soup: BeautifulSoup
    _type: string
    team: string
    """
    main = soup.find('div', {'class': 'Event-text'}).get_text()
    event_time = soup.find('div', {'class': 'Event-time'}).get_text()
    if len(event_time) > 4:
        event_time = int(event_time[0:2]) + int(event_time[-1])
    else:
        event_time = int(event_time.strip().strip('\''))
    sub = soup.find('div', {'class': 'Event-subText'})

    if _type == 'goal' or _type == 'substitution':
        if sub != None:
            return (_type, main, sub.get_text(), event_time, team[0], team[1])
        else:
            return (_type, main, 'Sin asistencia', event_time, team[0], team[1])
    
    card = soup.find('rect')['fill']
    if card == '#fc0':
        card = 'Amarilla'
    if card == '#ff5100':
        card = 'Roja'
      
    return (_type, main, card, event_time, team[0], team[1])

def format_events(all_events):
    """
    Return string

    all_events: list
    """
    formatted_events = []
    for events in all_events:
        if events[0] == 'substitution':
            formatted_events.append(f'* {events[3]}\' - sale {events[2]}, entra {events[1]}')
        if events[0] == 'card':
            formatted_events.append(f'* {events[3]}\' - tarjeta {events[2]} para {events[1]}')
        if events[0] == 'goal':
            gol = 'gol'
            if 'River Plate' == events[4]:
                gol = 'GOOOOOOOOOOOOOOOOOOOOOL'
            formatted_events.append(f'* {events[3]}\' - {gol} de {events[4]} {events[1]}, {events[2]}')
    markdown = ""
    for e in formatted_events:
        markdown += f'{e}\n'
    return markdown

def parse_state(soup):
    """
    Return string

    soup: BeautifulSoup
    """
    state = ""
    for i in soup:
        if "Primer tiempo" in i.text and "En curso" in i.text:
            state = f'arranco el {i.text.strip("En curso")}'
        elif "Primer tiempo" in i.text and "En curso" not in i.text:
            state = f'fin del Primer tiempo {i.text.strip("Primer tiempo")}'
        elif "Segundo tiempo" in i.text and "En curso" in i.text:
            state = f'arranco el {i.text.strip("En curso")}'
        elif "Segundo tiempo" in i.text and "En curso" not in i.text:
            state = f'fin del Segundo tiempo {i.text.strip("Segundo tiempo")}'
    return state


def events(soup):
    """
    Return list

    soup: BeautifulSoup
    """
    home_team = soup.find('a', {'class': 'MatchInfo-home'}).get_text()
    away_team = soup.find('a', {'class': 'MatchInfo-away'}).get_text()
    events_div = soup.findAll('div', {'class': 'Event'})
    goals = list()
    cards = list()
    subs = list()
    for event in events_div:
        team = [away_team, 'away'] if 'Event-reverse' in event.div['class'] else [home_team, 'home']
        if 'goal' in event.div['class'][0]:
            goals.append(get_event_info(event, 'goal', team))
        if 'card' in event.div['class'][0]:
            cards.append(get_event_info(event, 'card', team))
        if 'substitution' in event.div['class'][0]:
            subs.append(get_event_info(event, 'substitution', team))
    all_events = goals + cards + subs
    all_events.sort(key=lambda x:x[3])
    return all_events

def lineup(soup, locality):
    """
    Return dict

    soup: BeautifulSoup
    locality: string
    """
    team_info = dict()
    name = soup.find('div', {'class': f'LineupFormations-label-{locality}'})
    if name == None:
        return False
    starters = []
    lineup_div = soup.find('div', {'class': f'LineupFormations-team-{locality}'})
    lineup_rows = lineup_div.findAll('div', {'class': 'LineupFormations-row'})
    for row in lineup_rows:
        for player in row.findAll('a', {'class': 'LineupFormations-player'}):
            player_name = player.find('div', {'class': 'LineupFormations-player-text'})
            starters.append(player_name.get_text())
    team_info['name'] = name.get_text()
    team_info['starters'] = starters
    return team_info

def format_lineup(home_lineup, away_lineup):
    """
    Return string 
    
    Markdown format for display

    home_lineup: dict
    away_lineup: dict
    """ 
    df = pd.DataFrame(columns=[home_lineup["name"],away_lineup["name"]])
    df[home_lineup["name"]] = home_lineup["starters"]
    df[away_lineup["name"]] = away_lineup["starters"]
    lineup_markdown = df.to_markdown(index=False, stralign='center')
    return lineup_markdown

def make_soup(link: str) -> BeautifulSoup:
    """
    Return BeautifulSoup

    link: string
    """
    request = requests.get(link)
    soup = BeautifulSoup(request.text, features="html.parser")
    return soup

if __name__ == '__main__':
    TEAM = 'https://forzafootball.com/es/team/river-plate-3182'
    bs = make_soup(TEAM)
    WHEN = 'live' if bs.find('a', 'MatchlistItem-live') is not None else 'before'
    MATCH_INFO = game_link(bs, WHEN)
    
    if WHEN == 'live':
        LINEUPS = f'{game_link(bs, WHEN)}/lineups'
        bs = make_soup(LINEUPS)
        home = lineup(bs, 'home')
        away = lineup(bs, 'away')

    """ Connect To Reddit and update the page """
    keyPath = Path('./keys.yml').resolve()
    secrets = yaml.safe_load(open(keyPath, 'r'))
    reddit = praw.Reddit(
        client_id=secrets['client_id'],
        client_secret=secrets['client_secret'],
        user_agent=secrets['user_agent'],
        username=secrets['username'],
        password=secrets['password'],
    )

    data = {'title': f'[MT] {home["name"]} - {away["name"]}', 'lineups': '', 'events': []}

    if home != False and away != False:
        data['lineups'] = format_lineup(home, away)

    selftext = f'{data["lineups"]}\n{data["events"]}'


    # post = reddit.subreddit('CARiverPlateTest').submit(title=data['title'], selftext=selftext)

    # print(data['lineups'])
    # bs = make_soup(MATCH_INFO)
    # print(game_time(bs))

    # for i in range(45):    
    #     r = requests.get(MATCH_INFO)
    #     bs = BeautifulSoup(r.text, features="html.parser")
    #     formatted_score = format_score(home["name"], score(bs), game_time(bs), away["name"])
    #     formatted_events = format_events(events(bs))
    #     if len(data['events']) < len(formatted_events): 
    #         data['events'] = formatted_events
    #         selftext = f'{formatted_score}\n\n{data["lineups"]}\n{data["events"]}'
    #         print(selftext)
            # post.edit(f'{formatted_score}\n\n{data["lineups"]}\n{data["events"]}')
            # print("".join(data['events']))
        
        # sleep(60)

    # for i in range(37):
    #     r = requests.get(SCORE)
    #     bs = BeautifulSoup(r.text, features='html.parser')
    #     print(f'{team(bs,"home")} {score(bs)[0]} {game_time(bs)} {score(bs)[1]} {team(bs,"away")}')
    #     sleep(60)