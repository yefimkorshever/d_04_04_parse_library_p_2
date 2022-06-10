import argparse
import json
import os
import sys
from pathlib import Path
from time import sleep
from urllib.parse import unquote, urljoin, urlsplit

import requests
from bs4 import BeautifulSoup
from pathvalidate import sanitize_filename
from tqdm import tqdm


def create_arg_parser():
    description = 'The program parses tululu.org library'
    parser = argparse.ArgumentParser(description=description)

    parser.add_argument('--start_page',
                        help='start page (obligatory)',
                        required=True,
                        type=int,
                        )

    parser.add_argument('--end_page',
                        help='end page (if omitted loading up to'
                        ' the last page)',
                        default=0,
                        type=int,
                        )
    return parser


def check_for_redirect(response):
    if response.history:
        raise requests.HTTPError('redirection detected')


def parse_book_card(response):

    soup = BeautifulSoup(response.text, 'lxml')
    div_content = soup.select_one('div#content')
    title_text = div_content.select_one('h1').text
    title, author = title_text.split(sep='::')
    img_src = div_content.select_one('img')['src']

    span_tags = soup.select('.texts span')
    comments = [span_tag.text for span_tag in span_tags]

    genres_links = soup.select_one('span.d_book').select('a')
    genres = [genre_link.text for genre_link in genres_links]

    return {
        'title': title.strip(),
        'author': author.strip(),
        'img_src': urljoin(response.url, img_src),
        'comments': comments,
        'genres': genres,
    }


def download_image(book_card, folder):
    url = book_card['img_src']
    response = requests.get(url)
    response.raise_for_status()
    check_for_redirect(response)

    filename = urlsplit(url).path.split(sep='/')[-1]
    valid_filename = unquote(filename)
    file_path = os.path.join(folder, valid_filename)
    with open(file_path, 'wb') as file:
        file.write(response.content)

    book_card['img_src'] = file_path


def download_txt(url, payload, book_card, folder):
    filename = book_card['title']
    response = requests.get(url, params=payload)
    response.raise_for_status()
    check_for_redirect(response)

    valid_filename = f'{sanitize_filename(filename)}.txt'
    file_path = os.path.join(folder, valid_filename)
    with open(file_path, 'w', encoding='utf-8') as file:
        file.write(response.text)

    book_card['book_path'] = file_path


def save_books_catalog(books_catalog):
    books_dump = json.dumps(books_catalog, ensure_ascii=False, indent="\t")
    with open('books_catalog.json', 'w', encoding="UTF-8") as registry_file:
        registry_file.write(books_dump)


def parse_books_page(books_collection, page_response):
    soup = BeautifulSoup(page_response.text, 'lxml')
    tables_tags = soup.select('div#content table')
    for table_tag in tables_tags:
        relative_book_url = table_tag.select_one('a')['href']
        absolute_book_url = urljoin(page_response.url, relative_book_url)
        book_id = relative_book_url.strip('/b')
        books_collection.append((absolute_book_url, book_id))


def get_books_collection(start_page, end_page):
    end_page_search = end_page == 0
    if end_page_search:
        end_page = sys.maxsize

    parsed_urls = []
    books_collection = []
    for page_id in range(start_page, end_page):
        page_url = f'https://tululu.org/l55/{page_id}/'

        try:
            page_response = requests.get(page_url)
            page_response.raise_for_status()
            check_for_redirect(page_response)
        except requests.exceptions.HTTPError as http_fail:
            if (
                end_page_search and
                http_fail.args and
                http_fail.args[0] == 'redirection detected'
            ):
                break

            print(
                f'HTTP error occurred while downloading {page_url}:',
                http_fail,
                file=sys.stderr
            )
            if end_page_search:
                break

        except requests.exceptions.ConnectionError as connect_fail:
            print(
                f'Connection error occurred while downloading{page_url}:',
                connect_fail,
                file=sys.stderr
            )
            if end_page_search:
                break
            sleep(2)
            continue

        parse_books_page(books_collection, page_response)
        parsed_urls.append(page_response.url)

    if parsed_urls:
        print(f'parsed pages: {parsed_urls[0]} - {parsed_urls[-1]}')
    else:
        print('no pages to parse')
    return books_collection


def main():

    arg_parser = create_arg_parser()
    namespace = arg_parser.parse_args()
    books_collection = get_books_collection(
        namespace.start_page,
        namespace.end_page
    )
    errors_texts = []
    books_catalog = []

    image_folder = 'images'
    txt_folder = 'books'
    Path(f'./{image_folder}').mkdir(exist_ok=True)
    Path(f'./{txt_folder}').mkdir(exist_ok=True)
    print('downloading books...')
    for url, book_id in tqdm(books_collection):
        try:
            response = requests.get(url)
            response.raise_for_status()
            check_for_redirect(response)

            book_card = parse_book_card(response)

            payload = {'id': book_id}
            download_txt(
                'https://tululu.org/txt.php',
                payload,
                book_card,
                txt_folder
            )
            download_image(book_card, image_folder)
        except requests.exceptions.HTTPError as http_fail:
            errors_texts.append(
                f'HTTP error occurred while downloading '
                f'book {url}: {http_fail}'
            )

            continue

        except requests.exceptions.ConnectionError as connect_fail:
            errors_texts.append(
                'Connection error occurred while downloading'
                f'book {url}: {connect_fail}'
            )
            sleep(2)
            continue

        books_catalog.append(book_card)

    save_books_catalog(books_catalog)

    for error_text in errors_texts:
        print(error_text,  file=sys.stderr)


if __name__ == '__main__':
    main()
