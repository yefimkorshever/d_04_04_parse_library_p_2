import argparse
import os
import sys
from pathlib import Path
from time import sleep
from urllib.parse import unquote, urljoin, urlsplit

import requests
from bs4 import BeautifulSoup
from pathvalidate import sanitize_filename


def create_arg_parser():
    description = 'The program parses tululu.org library'
    parser = argparse.ArgumentParser(description=description)

    parser.add_argument('start_id',
                        help='start book id, by default: 1',
                        default=1,
                        nargs='?',
                        type=int,
                        )

    parser.add_argument('end_id',
                        help='end book id, by default: 10',
                        default=10,
                        nargs='?',
                        type=int,
                        )
    return parser


def check_for_redirect(response):
    if response.history:
        raise requests.HTTPError('redirected')


def parse_book_page(response):

    soup = BeautifulSoup(response.text, 'lxml')
    div_content = soup.find('div', id='content')
    title_text = div_content.find('h1').text
    title, author = title_text.split(sep='::')
    img_src = div_content.find('img')['src']

    comments_tags = soup.find_all('div', class_='texts')
    comments = [comment_tag.find('span').text for comment_tag in comments_tags]

    genres_links = soup.find('span', class_='d_book').find_all('a')
    genres = [genre_link.text for genre_link in genres_links]

    return {
        'title': title.strip(),
        'author': author.strip(),
        'image': urljoin(response.url, img_src),
        'comments': comments,
        'genres': genres,
    }


def download_image(url, folder):
    response = requests.get(url)
    response.raise_for_status()
    check_for_redirect(response)

    filename = urlsplit(url).path.split(sep='/')[-1]
    valid_filename = unquote(filename)
    file_path = os.path.join(folder, valid_filename)
    with open(file_path, 'wb') as file:
        file.write(response.content)


def download_txt(url, payload, filename, folder):
    response = requests.get(url, params=payload)
    response.raise_for_status()
    check_for_redirect(response)

    valid_filename = f'{sanitize_filename(filename)}.txt'
    file_path = os.path.join(folder, valid_filename)
    with open(file_path, 'w', encoding='utf-8') as file:
        file.write(response.text)


def main():
    arg_parser = create_arg_parser()
    namespace = arg_parser.parse_args()

    image_folder = 'images'
    txt_folder = 'books'
    Path(f'./{image_folder}').mkdir(exist_ok=True)
    Path(f'./{txt_folder}').mkdir(exist_ok=True)

    for book_id in range(namespace.start_id, namespace.end_id + 1):
        print('\n')
        head_url = 'https://tululu.org/'
        url = f'{head_url}b{book_id}/'

        try:
            response = requests.get(url)
            response.raise_for_status()
            check_for_redirect(response)

            book_card = parse_book_page(response)

            print(book_card['title'])
            print(book_card['genres'])

            title = book_card['title']
            payload = {'id': book_id}
            download_txt(
                f'{head_url}txt.php',
                payload,
                f'{book_id}.{title}',
                txt_folder
            )
            download_image(book_card['image'], image_folder)
        except requests.exceptions.HTTPError as http_fail:
            print(
                f'HTTP error occurred while downloading book {book_id}',
                http_fail,
                file=sys.stderr
            )
        except requests.exceptions.ConnectionError as connect_fail:
            print(
                f'Connection error occurred while downloading book {book_id}',
                connect_fail,
                file=sys.stderr
            )
            sleep(2)


if __name__ == '__main__':
    main()
