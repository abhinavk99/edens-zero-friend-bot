from apscheduler.schedulers.blocking import BlockingScheduler
import logging, re
from datetime import datetime
import praw, prawcore
import requests, zipfile, io, os, shutil
from bs4 import BeautifulSoup
import config as cfg
from google.cloud import vision
from google.cloud.vision import types

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

TITLE_PREFIX = 'Submission Title - {}'
LOG_MSG = "Checking for new Eden's Zero chapter in /r/{} at " + str(datetime.now())
SERVER_ERROR = "Error with searching for a new Eden's Zero chapter in /r/{}"

GITHUB_LINK = 'https://github.com/abhinavk99/edens-zero-friend-bot'
PM_LINK = 'https://www.reddit.com/message/compose/?to=edenszerofriendbot'
FOOTER = '---\n^^[source]({}) ^^on ^^github, ^^[message]({}) ^^the ^^bot ^^for ^^any ^^questions'.format(GITHUB_LINK, PM_LINK)

reddit = praw.Reddit(client_id=cfg.reddit_id,
                     client_secret=cfg.reddit_secret,
                     password=cfg.reddit_password,
                     user_agent=cfg.reddit_user_agent,
                     username=cfg.reddit_username)

sched = BlockingScheduler()

chapters_info = {}


def main():
    scan_chapter('https://jaiminisbox.com/reader/read/eden-s-zero/en/0/2/page/1')
    # read_chapters_file()
    # search_in_manga()
    # search_in_edens_zero()
    # sched.start()


@sched.scheduled_job('interval', seconds=600)
def search_in_manga():
    logger.debug(LOG_MSG.format('manga'))
    try:
        for submission in reddit.subreddit('manga').search("Eden's Zero", sort='new', time_filter='week'):
            logger.debug(TITLE_PREFIX.format(submission.title))
            title = submission.title.lower()
            if '[disc]' in title:
                analyze_submission(submission, title)
    except prawcore.exceptions.ServerError:
        print(SERVER_ERROR.format('manga'))


@sched.scheduled_job('interval', seconds=600)
def search_in_edens_zero():
    logger.debug(LOG_MSG.format('EdensZero'))
    try:
        for submission in reddit.subreddit('EdensZero').search("Chapter", sort='new', time_filter='week'):
            logger.debug(TITLE_PREFIX.format(submission.title))
            title = submission.title.lower()
            if 'links + discussion' in title:
                analyze_submission(submission, title)
    except prawcore.exceptions.ServerError:
        logger.error(SERVER_ERROR.format('EdensZero'))


def analyze_submission(submission, title):
    chapter_number = get_chapter_number(title)
    if chapter_number is not None and submission not in reddit.user.me().new(limit=5):
        logger.info(TITLE_PREFIX.format(submission.title))
        scan_chapter(submission.url)
        post_comment(submission)
        write_chapters_file()


def get_chapter_number(title):
    match_obj = re.search(r'chapter (\d+)', title)
    if match_obj is not None:
        chapter_number = int(match_obj.groups()[0])
        logger.debug('Chapter {}'.format(chapter_number))
        if chapter_number not in chapters_info:
            return chapter_number
    return None


def scan_chapter(link):
    r = requests.get(link)
    soup = BeautifulSoup(r.text, 'html.parser')
    download_link = soup.select('div.icon_wrapper.fleft.larg')[0].find('a').attrs['href']
    logger.debug('Download link - {}'.format(download_link))
    r = requests.get(download_link)
    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        z.extractall(os.path.join(os.getcwd(), 'images'))
    client = vision.ImageAnnotatorClient()
    for filename in os.listdir(os.path.join(os.getcwd(), 'images')):
        print(filename)
        with io.open(os.path.join(os.getcwd(), 'images', filename), 'rb') as image_file:
            content = image_file.read()
        # image = types.Image(content=content)
    # shutil.rmtree('./images')


def post_comment(submission):
    # TODO
    pass


def read_chapters_file():
    with open('chapters.txt') as f:
        for line in f:
            tokens = line.split()
            chapters_info[int(tokens[0])] = int(tokens[1])


def write_chapters_file():
    with open('chapters.txt', 'w') as f:
        for key in sorted(chapters_info.keys()):
            f.write('{} {}\n'.format(key, chapters_info[key]))


if __name__ == '__main__':
    main()
