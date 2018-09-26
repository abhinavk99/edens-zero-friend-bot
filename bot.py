import requests
import zipfile
import io
import os
import json
import praw
import prawcore
import logging
import re
from time import sleep
from apscheduler.schedulers.blocking import BlockingScheduler
from datetime import datetime
from base64 import b64encode
from bs4 import BeautifulSoup
import config as cfg

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

ENDPOINT_URL = 'https://vision.googleapis.com/v1/images:annotate'
DIRECTORY = 'images'

TITLE_PREFIX = 'Submission Title - {}'
LOG_MSG = "Checking for new Eden's Zero chapter in /r/{} at " + \
    str(datetime.now())
SERVER_ERROR = "Error with searching for a new Eden's Zero chapter in /r/{}"
RATELIMITED = 'Got ratelimited. Trying again in 9 minutes.'

FRIEND_TEXT = 'Times "friend" was said in chapter {}: {} times.\n\n'
TOTAL_FRIEND_TEXT = 'Total times "friend" was said: {} times in {} chapters.\n\n'
AVERAGE_FRIEND_TEXT = 'Average "friends" per chapter: {}\n\n'

CHAPTER_LINK = 'https://github.com/abhinavk99/edens-zero-friend-bot/blob/master/chapters.md'
CHAPTERS_INFO = f'[See the friend count for each chapter]({CHAPTER_LINK})\n\n'

GITHUB_LINK = 'https://github.com/abhinavk99/edens-zero-friend-bot'
PM_LINK = 'https://www.reddit.com/message/compose/?to=edenszerofriendbot'
FOOTER = f'---\n^^[source]({GITHUB_LINK}) ^^on ^^github, ^^[message]({PM_LINK}) ^^the ^^bot ^^for ^^any ^^questions'

reddit = praw.Reddit(
    client_id=cfg.reddit_id,
    client_secret=cfg.reddit_secret,
    password=cfg.reddit_password,
    user_agent=cfg.reddit_user_agent,
    username=cfg.reddit_username
)

sched = BlockingScheduler()

chapters_info = {}


def main():
    read_chapters_file()
    search_in_manga()
    search_in_edens_zero()
    sched.start()


@sched.scheduled_job('interval', seconds=600)
def search_in_manga():
    logger.debug(LOG_MSG.format('manga'))
    try:
        for submission in reddit.subreddit('manga').search("Eden's Zero", sort='new', time_filter='day'):
            logger.debug(TITLE_PREFIX.format(submission.title))
            title = submission.title.lower()
            if '[disc]' in title:
                analyze_submission(submission, title)
    except prawcore.exceptions.ServerError:
        logger.error(SERVER_ERROR.format('manga'))


@sched.scheduled_job('interval', seconds=600)
def search_in_edens_zero():
    logger.debug(LOG_MSG.format('EdensZero'))
    try:
        for submission in reddit.subreddit('EdensZero').search("Chapter", sort='new', time_filter='day'):
            logger.debug(TITLE_PREFIX.format(submission.title))
            title = submission.title.lower()
            if 'discussion' in title:
                analyze_submission(submission, title)
    except prawcore.exceptions.ServerError:
        logger.error(SERVER_ERROR.format('EdensZero'))


def analyze_submission(submission, title):
    chapter_number = get_chapter_number(title)
    if chapter_number is not None and submission not in [comment.parent() for comment in reddit.user.me().new(limit=10)]:
        logger.info(TITLE_PREFIX.format(submission.title))
        if chapter_number not in chapters_info:
            download_chapter(submission.url, chapter_number)
            scan_chapter(chapter_number)
        post_comment(submission, chapter_number)
        write_chapters_file(chapter_number)


def get_chapter_number(title):
    # Try two possible regex patterns to get the chapter number
    match_obj = re.search(r'chapter\s(\d+)', title)
    if match_obj is None:
        match_obj = re.search(r'ch\.?\s?(\d+)', title)
    if match_obj is not None:
        chapter_number = int(match_obj.groups()[0])
        logger.debug(f'Chapter {chapter_number}')
        return chapter_number
    return None


def scan_chapter(chapter_number):
    total_friends = 0
    for filename in os.listdir(os.path.join(os.getcwd(), DIRECTORY, str(chapter_number))):
        logger.debug(filename)
        img_requests = []
        with open(os.path.join(os.getcwd(), DIRECTORY, str(chapter_number), filename), 'rb') as image_file:
            content = b64encode(image_file.read()).decode()
            img_requests.append({
                'image': {'content': content},
                'features': [{
                    'type': 'TEXT_DETECTION',
                    'maxResults': 1
                }]
            })
        img_requests_data = json.dumps({'requests': img_requests}).encode()
        response = requests.post(
            ENDPOINT_URL,
            data=img_requests_data,
            params={'key': cfg.google_api_key},
            headers={'Content-Type': 'application/json'}
        )
        data = response.json()['responses'][0]
        if 'fullTextAnnotation' in data:
            text = data['fullTextAnnotation']['text'].lower()
            logger.debug(f'Text for {filename}:\n{text}')
            friends = text.count('friend')
            logger.debug(friends)
            total_friends += friends
        else:
            logger.debug(data)
    logger.info(f'Number of times the word friend appeared: {total_friends}')
    chapters_info[chapter_number] = total_friends


def download_chapter(link, chapter_number):
    r = requests.get(link)
    soup = BeautifulSoup(r.text, 'html.parser')
    download_link = soup.select('div.icon_wrapper.fleft.larg')[
        0].find('a').attrs['href']
    logger.debug(f'Download link - {download_link}')
    r = requests.get(download_link)
    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        z.extractall(os.path.join(os.getcwd(), DIRECTORY, str(chapter_number)))


def post_comment(submission, chapter_number):
    reply_text = ''
    total_friends = 0
    num_chapters = 0
    for key in sorted(chapters_info.keys(), reverse=True):
        logger.debug(f'Chapter {key}: {chapters_info[key]} times')
        if key == chapter_number:
            reply_text += FRIEND_TEXT.format(key, chapters_info[key])
        total_friends += chapters_info[key]
        num_chapters += 1
    reply_text += TOTAL_FRIEND_TEXT.format(total_friends, num_chapters)
    reply_text += AVERAGE_FRIEND_TEXT.format(
        round(total_friends / num_chapters, 2))
    reply_text += CHAPTERS_INFO
    reply_text += FOOTER
    logger.info(reply_text)
    try:
        submission.reply(reply_text)
    except praw.exceptions.APIException:
        logger.error(RATELIMITED)
        sleep(650)
        submission.reply(reply_text)


def read_chapters_file():
    with open('chapters.txt') as f:
        for line in f:
            tokens = line.split()
            chapters_info[int(tokens[0])] = int(tokens[1])


def write_chapters_file(chapter_number):
    with open('chapters.txt', 'w') as f:
        for key in sorted(chapters_info.keys()):
            f.write(f'{key} {chapters_info[key]}\n')
    with open('chapters.md', 'a+') as f:
        chapter_markdown = f'| {chapter_number} | {chapters_info[chapter_number]} |\n'
        if f.read().find(chapter_markdown) == -1:
            f.write(chapter_markdown)


if __name__ == '__main__':
    main()
