from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


def check_for_redirect(response):
    if response.history:
        raise requests.HTTPError('redirected')


def get_books_urls():
    pass


def main():
    books_catalog = {}
    for page_id in range(1, 11):
        page_url = f'https://tululu.org/l55/{page_id}/'
        page_response = requests.get(page_url)
        page_response.raise_for_status()
        check_for_redirect(page_response)

        soup = BeautifulSoup(page_response.text, 'lxml')
        tables_tags = soup.find('div', id='content').find_all('table')
        for table_tag in tables_tags:
            relative_book_url = table_tag.find_all('a')[1]['href']
            absolute_book_url = urljoin(page_response.url, relative_book_url)

            print(absolute_book_url)


if __name__ == '__main__':
    main()
