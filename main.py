#!/usr/bin/env python
# coding: utf-8
#
# Filename:   main.py
# Author:     Peinan ZHANG
# Created at: 2022-10-27

import os
import requests, json, time
import argparse
from datetime import datetime
from typing import List


def get_arg(args, arg_name, default_value, argtype=str):
    return args.get(arg_name, type=argtype) if arg_name in args else default_value

def build_slack_message(actor, actor_avatar, repo_name, repo_star, repo_lang, repo_desc, repo_avatar, created_at,
                        starts_with_divider=False) -> str:
    repo_owner = repo_name.split('/')[0]

    # created_at example: '2019-11-26T07:29:15Z'
    d = datetime.strptime(created_at.split('T')[0], '%Y-%m-%d')
    t = datetime.strptime(created_at.split('T')[1][:-1], '%H:%M:%S')
    dt = datetime(d.year, d.month, d.day, t.hour, t.minute, t.second)

    # create message blocks for slack
    blocks = {"blocks": [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*<https://github.com/{repo_name}|{repo_name}>*\n{repo_desc}\n\n*{repo_lang}*      *★{repo_star}*"
            },
            "accessory": {
                "type": "image",
                "image_url": f"{repo_avatar}",
                "alt_text": f"{repo_owner}"
            }
        },
        {
            "type": "context",
            "elements": [
                {
                    "type": "image",
                    "image_url": f"{actor_avatar}",
                    "alt_text": f"{actor}"
                },
                {
                    "type": "mrkdwn",
                    "text": f"starred by <https://github.com/{actor}|{actor}>  |  <!date^{int(dt.timestamp())}^{{date_short}} {{time}}|{created_at}>"
                }
            ]
        }
    ]}

    if starts_with_divider:
        blocks['blocks'] = [{'type': 'divider'}] + blocks['blocks']

    return json.dumps(blocks)

def post_to_slack(item, starts_with_divider=False):
    requests.post(SLACK_WEBHOOK_URL, headers={'Content-Type': 'application/json'},
                  data=build_slack_message(
                      actor=item['actor'],
                      actor_avatar=item['actor_avatar'],
                      repo_name=item['repo_name'],
                      repo_star=item['repo_star'],
                      repo_lang=item['repo_lang'],
                      repo_desc=item['repo_desc'],
                      repo_avatar=item['repo_avatar'],
                      created_at=item['created_at'],
                      starts_with_divider=starts_with_divider,
                  ))

def ghstarlog(args):
    flag_not_posted = args.not_posted
    flat_post_to_slack = args.post_to_slack

    gh_activity_url = f'{GITHUB_API_ENDPOINT}/users/peinan/received_events/public'
    gh_repo_url     = f'{GITHUB_API_ENDPOINT}/repos/' + '{repo_name}'

    acts = requests.get(gh_activity_url).json()
    starred_items = []
    event_ids = []
    for act in acts:
        if 'action' in act['payload'] and act['payload']['action'] == 'started':
            event_id = act['id']
            repo_name = act['repo']['name']

            repo = requests.get(gh_repo_url.format(repo_name=repo_name)).json()

            starred_items.append({
                'event_id': act['id'],
                'actor': act['actor']['login'],
                'actor_avatar': act['actor']['avatar_url'],
                'repo_name': repo_name,
                'repo_avatar': repo['owner']['avatar_url'],
                'repo_star': repo['stargazers_count'],
                'repo_lang': repo['language'],
                'repo_desc': repo['description'],
                'created_at': act['created_at'],
            })
            event_ids.append(event_id)

    # sort the list from new->old to old->new
    starred_items = starred_items[::-1]
    event_ids = event_ids[::-1]

    if flag_not_posted:
        latest_event_id = requests.get(SHEETDB_URL + '?limit=1').json()[0]['event_id']
        offset = event_ids.index(latest_event_id) if latest_event_id in event_ids else 0

        starred_items = starred_items[offset+1:] if offset+1 <= len(starred_items) else []

    if flat_post_to_slack:
        if not starred_items: return 'Nothing to post.'

        for i, item in enumerate(starred_items):
            post_to_slack(item, starts_with_divider=False if i==0 else True)
            time.sleep(1)
        return_msg = f'{len(starred_items)} posted.'

        if flag_not_posted:
            latest_item = starred_items[-1]
            requests.patch(SHEETDB_URL + '/id/1', headers={'Content-Type': 'application/json'},
                           data=json.dumps({'data':
                               [{'created_at': latest_item['created_at'], 'event_id': latest_item['event_id'],
                               'actor': latest_item['actor'], 'repo_name': latest_item['repo_name']}]
                           })
            )

        return return_msg

    return json.dumps(starred_items)


if __name__ == '__main__':
    GITHUB_API_ENDPOINT = 'https://api.github.com'
    SHEETDB_URL = os.environ['SHEETDB_URL']
    SLACK_WEBHOOK_URL = os.environ['SLACK_WEBHOOK_URL']

    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument('-n', '--not-posted', type=bool, default=True)
    parser.add_argument('-s', '--post-to-slack', type=bool, default=True)
    args = parser.parse_args()

    ghstarlog(args)

