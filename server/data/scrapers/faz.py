import re
from data.scrapers import Scraper, NoCommentsWarning, UnknownStructureWarning
from datetime import datetime
from collections import defaultdict
import logging
import data.models as models

logger = logging.getLogger('scraper')


class FAZScraper(Scraper):

    @staticmethod
    def assert_url(url):
        return re.match(r'(https?://)?(www\.)?faz\.net/.*', url)

    @classmethod
    def _scrape(cls, url):
        query_url = f'{url}?printPagedArticle=true#pageIndex_2'
        bs = Scraper.get_html(query_url)
        article = cls._scrape_article(bs, url)
        try:
            comments = cls._scrape_comments(url)
            if len(comments) == 0:
                raise IndexError
        except IndexError:
            raise NoCommentsWarning(f'No Comments found at : {query_url}')

        return article, comments

    @staticmethod
    def _scrape_author(bs):
        author = bs.select('span.atc-MetaAuthor')

        if author:
            author = author[0].get_text().strip()
        else:
            return None
        return author

    @classmethod
    def _scrape_article(cls, bs, url):
        try:
            article = models.ArticleBase(
                url=url,
                title=bs.select('span.atc-HeadlineEmphasisText')[0].get_text().strip() + ' - ' +
                      bs.select('span.atc-HeadlineText')[0].get_text().strip(),
                summary=bs.select('p.atc-IntroText')[0].get_text().strip(),
                author=cls._scrape_author(bs),
                text='\n\n'.join([e.get_text().strip() for e in bs.select('div.atc-Text p')]),
                published_time=datetime.strptime(bs.select('time.atc-MetaTime')[0]['title'], '%d.%m.%Y %H:%M Uhr'),
                scraper=str(cls)
            )
        except IndexError:
            raise UnknownStructureWarning(f'Article structure unknown at {url}')
        return article

    @classmethod
    def generate_id(cls, author, time):
        return f'{author}"-"{time.replace(" ", "")}'

    # todo: walk all comment pages
    @classmethod
    def _scrape_comments(cls, url):

        url = f'{url}?ot=de.faz.ArticleCommentsElement.comments.ajax.ot&action=commentList'

        comments = []
        comment_page_count = 1
        parents2childs = defaultdict(list)
        while True:
            # am I done?
            this_page_url = f'{url}&page={comment_page_count}'
            bs = cls.get_html(this_page_url)
            if bs is None:
                break
            if len(bs) == 0:
                break

            for e in bs.select('li.lst-Comments_Item'):
                number_of_replies = e.select('p.lst-Comments_CommentNumberOfReplies')
                if number_of_replies:
                    number_of_replies = number_of_replies[0].get_text().split()[0]
                else:
                    number_of_replies = 0
                author = e.select('span.lst-Comments_CommentInfoUsernameText')[0].get_text()
                time = e.select('span.lst-Comments_CommentInfoDateText')[0].get_text()
                cid = cls.generate_id(author, time)
                if cid in parents2childs.keys():
                    print("Duplicate id!")
                    if cid.endswith('_'):
                        splitt = cid.split('_')
                        cid = f'{"".join(splitt[:-2])}_{int(splitt[-2]) + 1}_'
                    else:
                        cid = f'{cid}_1_'

                if int(number_of_replies) > 0:
                    for child in e.select('li.lst-Comments_Item'):
                        child_author = child.select('span.lst-Comments_CommentInfoUsernameText')[0].get_text()
                        child_time = child.select('span.lst-Comments_CommentInfoDateText')[0].get_text()
                        child_id = cls.generate_id(child_author, child_time)

                        parents2childs[cid].append(child_id)

            child2parent = cls.revert_parents2childs(parents2childs)
            for e in bs.select('li.lst-Comments_Item'):
                comments.append(cls._parse_comment(e, child2parent))
            comment_page_count += 1

        return comments

    @classmethod
    def revert_parents2childs(cls, parents2childs):
        child2parents = {}
        for parent, childs in parents2childs.items():
            for child in childs:
                child2parents[child] = parent
        return child2parents

    @classmethod
    def _parse_comment(cls, e, child2parent):

        user_id = e.select('span.lst-Comments_CommentInfoUsernameText')[0].get_text()
        author = e.select('span.lst-Comments_CommentInfoNameText')[0].get_text()

        time = e.select('span.lst-Comments_CommentInfoDateText')[0].get_text()
        text = e.select('p.js-lst-Comments_CommentTitle')[0].get_text().strip() + ' ' + \
               e.select('p.lst-Comments_CommentText')[0].get_text().strip()

        cid = cls.generate_id(user_id, time)

        reply_to = child2parent.get(cid)
        number_of_replies = e.select('p.lst-Comments_CommentNumberOfReplies')
        if number_of_replies:
            number_of_replies = number_of_replies[0].get_text().split()[0]
        else:
            number_of_replies = 0

        return models.CommentBase(
            comment_id=cid,
            username=author,
            timestamp=datetime.strptime(time, '%d.%m.%Y - %H:%M'),
            text=text,
            reply_to=reply_to,
            num_replies=number_of_replies,
            user_id=e.select('span.lst-Comments_CommentInfoUsernameText')[0].get_text().replace('(', '').replace(')',
                                                                                                                 '')
        )


if __name__ == '__main__':
    FAZScraper.test_scraper(
        [
            'https://www.faz.net/aktuell/gesellschaft/menschen/rapper-fler-im-interview-ueber-bushido-und-arafat-abou-chaker-16518885.html',
            'https://www.faz.net/aktuell/technik-motor/sicherheitskontrolle-am-flughafen-frankfurt-blamage-ohne-ende-16514693.html',
            'https://www.faz.net/aktuell/feuilleton/medien/tv-kritik-maischberger-mit-stefan-aust-und-dirk-rossmann-16472805.html',
            'https://www.faz.net/aktuell/rhein-main/drei-mutmassliche-is-anhaenger-in-offenbach-festgenommen-16481443.html',
            'https://www.faz.net/aktuell/politik/inland/bauernproteste-agrarwende-hat-harte-fronten-geschaffen-16505290.html'
        ][:])