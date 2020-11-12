import os
from re import L
import sys
import readline
from datetime import date
import pickle
import argparse
from typing import Iterable, List, Optional, Tuple

from github import Github
from github.TeamDiscussion import TeamDiscussion
from github.NamedUser import NamedUser
from github.GithubException import UnknownObjectException

from slug import slugify

comment = """
**Yesterday**:
 - {yesterday}

**Today**:
 - {today}

**Blockers**:
 - {blockers}

**Shoutouts**:
 - {shoutouts}

<sub>Sent with [Standup](https://github.com/NoahCardoza/standup)</sub>
""".strip()


class UsernameAutocompletion:
    def __init__(self, team_members, org_members):
        self.team_members = self._normalize_members(team_members)
        self.org_members = self._normalize_members(org_members)
        self.matches = []
    
    @staticmethod
    def _normalize_members(members):
        return [(member.lower(), member) for member in members]

    def __enter__(self):
        readline.set_completer(self.completer)
        readline.set_completer_delims(readline.get_completer_delims().replace('@', ''))
        return self

    def __exit__(self, err, trace, stack):
        readline.set_completer(None)

    def _complete(self, text):
        if not text:
            begin = readline.get_begidx()
            line = readline.get_line_buffer()[:begin]
            words = line.split()
            if not words:
                return
            
            if words[-1].startswith('@'):
                self.matches = []
                return 'for '

        if not text.startswith('@'):
            return

        text = text[1:]
        [text, members] = [text[1:], self.org_members] if text.startswith('@') else [text, self.team_members]
        text = text.lower()

        self.matches = [i[1] for i in members if i[0].startswith(text)]

        if len(self.matches) == 1:
            self.matches[0]=  f'@{self.matches[0]} '

    def completer(self, text, state):
        if state == 0:
            self._complete(text)

        if state < len(self.matches):
            return self.matches[state]


def to_ordinal(n: int) -> str:
    return 'trnshddt'[0xc0006c000000006c>>2*n&3::4]


def find_latest_standup_discussion(discussions) -> Tuple[str, Optional[TeamDiscussion]]:
    today = date.today()
    standup_tital_match = today.strftime(f"Standup (%A, %B %d{to_ordinal(today.day)}, %Y)")
    for discussion in discussions:
        if standup_tital_match == discussion.title:
            return (standup_tital_match, discussion)
    return (standup_tital_match, None)


def join_items(items: Iterable[str]) -> str:
    return '\n - '.join(items)


def post_shoutout(discussion: TeamDiscussion, shoutout: str) -> str:
    headers, data = discussion._requester.requestJsonAndCheck(
    "POST", discussion.url + "/comments", input={
            'body': shoutout
    })
    return data['html_url']


def lift_login(items: Iterable[NamedUser]) -> List[str]:
    return [i.login for i in items]


def remove_last_line():
    sys.stdout.write("\033[F")
    sys.stdout.write("\033[K")

def collect_items() -> Tuple[str, ...]:
    line = input(' - ')
    if line and not line[0] == '@':
        return (line, *collect_items())
    remove_last_line()
    print()
    return tuple()


def defualt_to_na(items: Tuple[str, ...]) -> Tuple[str, ...]:
    if items:
        return items

    sys.stdout.write("\033[F")
    print(' - N/A\n')
    return ('N/A',)

def get_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Simple standups!')
    parser.add_argument('team', help='Github organization\'s team name')
    parser.add_argument('--organization', '-o', help='Github organization name', default='MLH-Fellowship')
    return parser.parse_args()

def main():
    readline.parse_and_bind("tab:complete")

    print(f"Loading...")
    args = get_args()

    g = Github(os.environ['STANDUP_GITHUB_API_KEY'])

    try:
        org = g.get_organization(args.organization)
    except UnknownObjectException:
        print('Error: organization does not exist.')
        return
    
    try:
        team = org.get_team_by_slug(slugify(args.team).lower())
    except UnknownObjectException:
        print('Error: team does not exist.')
        return
    (title, discussion) = find_latest_standup_discussion(team.get_discussions())

    if not discussion:
        print(f'Error: No discussion was not found with title matching: {title}')
        exit()


    team_members = team.get_members()
    org_members = org.get_members()

    remove_last_line()

    with UsernameAutocompletion(
            team_members=lift_login(team_members),
            org_members=lift_login(org_members)
        ):
        print('Yesterday:')
        yesterday = collect_items()

        print('Today:')
        today = collect_items()

        print('Blockers:')
        blockers = defualt_to_na(collect_items())

        print('Shoutouts:')
        readline.set_startup_hook(lambda: readline.insert_text('@'))
        shoutouts = defualt_to_na(collect_items())
        readline.set_startup_hook(None)

    url = post_shoutout(discussion, comment.format(
        yesterday=join_items(yesterday),
        today=join_items(today),
        blockers=join_items(blockers),
        shoutouts=join_items(shoutouts),
    ))

    print(url)
    print("Submitted!")


if __name__ == '__main__':
    main()