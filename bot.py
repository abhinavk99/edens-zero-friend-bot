from apscheduler.schedulers.blocking import BlockingScheduler
from datetime import datetime
import praw
import prawcore
import re
import config as cfg

reddit = praw.Reddit(client_id=cfg.reddit_id,
                     client_secret=cfg.reddit_secret,
                     password=cfg.reddit_password,
                     user_agent=cfg.reddit_user_agent,
                     username=cfg.reddit_username)

sched = BlockingScheduler()

chapters_info = {}

def read_chapters_file():
    with open('chapters.txt') as f:
        for line in f:
            tokens = line.split()
            chapters_info[tokens[0]] = tokens[1]

def scan_chapter(link):
    # TODO
    pass

def post_comment(submission):
    # TODO
    pass

def get_chapter_number(title):
    if '[disc]' in title:
        match_obj = re.search(r'chapter (\d+)', title)
        if match_obj is not None:
            chapter_number = match_obj.groups()[0]
            print(chapter_number)
            if chapter_number not in chapters_info:
                return chapter_number
    return None

def is_new_submission(submission):
    return submission not in reddit.user.me().new(limit = 5)

@sched.scheduled_job('interval', seconds=600)
def search_for_post():
    print("Checking for new Eden's Zero chapter at " + str(datetime.now()))
    try:
        for submission in reddit.subreddit('manga').search("Eden's Zero", sort='new', time_filter='day'):
            title = submission.title.lower()
            print(title)
            chapter_number = get_chapter_number(title)
            if chapter_number is not None and is_new_submission(submission):
                scan_chapter(submission.url)
                post_comment(submission)
    except prawcore.exceptions.ServerError:
        print("Error with searching for a new Eden's Zero chapter")

read_chapters_file()
search_for_post()
sched.start()