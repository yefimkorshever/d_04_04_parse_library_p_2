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
                        metavar='[start page]',
                        help='page to start with (default: 1)',
                        default=1,
                        type=int,
                        )

    parser.add_argument('--end_page',
                        metavar='[end page]',
                        help='page to end with (if omitted loading up to'
                        ' the last page)',
                        default=get_end_page_id(),
                        type=int,
                        )

    parser.add_argument('--dest_folder',
                        metavar='[destination folder]',
                        help='destination folder for parsing results'
                        ' (root project folder by default)',
                        default='.',
                        )

    parser.add_argument('--json_path',
                        metavar='[json path]',
                        help='path to json books catalog file'
                        ' (books_catalog.json by default)',
                        )

    parser.add_argument('--skip_imgs',
                        help='do not download images',
                        action="store_true",
                        )

    parser.add_argument('--skip_txt',
                        help='do not download texts',
                        action="store_true",
                        )

    return parser


def get_end_page_id():
    response = requests.get('https://tululu.org/l55/1/')
    response.raise_for_status()
    check_for_redirect(response)
    soup = BeautifulSoup(response.text, 'lxml')
    return int(soup.select('.npage')[-1].text) + 1


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


def save_books_catalog(books_catalog, json_path, dest_folder):
    if json_path:
        file_path = os.path.normpath(json_path)
    elif dest_folder != '.':
        file_path = os.path.join(dest_folder, 'books_catalog.json')
    else:
        file_path = 'books_catalog.json'

    books_dump = json.dumps(books_catalog, ensure_ascii=False, indent="\t")
    with open(file_path, 'w', encoding="UTF-8") as registry_file:
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
    print(f'seek pages {start_page} - {end_page - 1}...')
    parsed_urls = []
    books_collection = []
    for page_id in range(start_page, end_page):
        page_url = f'https://tululu.org/l55/{page_id}/'

        page_response = requests.get(page_url)
        page_response.raise_for_status()
        check_for_redirect(page_response)
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

    dest_folder = os.path.normpath(namespace.dest_folder)
    image_folder = os.path.join(dest_folder, 'images')
    txt_folder = os.path.join(dest_folder, 'books')
    Path(image_folder).mkdir(exist_ok=True)
    Path(txt_folder).mkdir(exist_ok=True)
    print('downloading books...')
    for url, book_id in tqdm(books_collection):
        try:
            response = requests.get(url)
            response.raise_for_status()
            check_for_redirect(response)

            book_card = parse_book_card(response)

            if not namespace.skip_txt:
                payload = {'id': book_id}
                download_txt(
                    'https://tululu.org/txt.php',
                    payload,
                    book_card,
                    txt_folder
                )

            if not namespace.skip_imgs:
                download_image(book_card, image_folder)
        except requests.exceptions.HTTPError as fail:
            errors_texts.append(
                f'HTTP error occurred while downloading '
                f'book {url}: {fail}'
            )

            continue

        except requests.exceptions.ConnectionError as fail:
            errors_texts.append(
                'Connection error occurred while downloading'
                f'book {url}: {fail}'
            )
            sleep(2)
            continue

        books_catalog.append(book_card)

    save_books_catalog(books_catalog, namespace.json_path, dest_folder)

    for error_text in errors_texts:
        print(error_text,  file=sys.stderr)


if __name__ == '__main__':
    main()
