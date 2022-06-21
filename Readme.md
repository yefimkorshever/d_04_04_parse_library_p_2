# Parse online library

The program parses [tululu.org](https://tululu.org/) library

## Prerequisites

Python 3.10 or higher required.

## Installing

- Download the project files
- Run:

```bash
pip install -r requirements.txt
```

## Running script

- Run:

```bash
python parse_tululu_category.py
```

- It's possible to input start and end book ID.
For example, to download books with IDs from 21 to 23, run:

```bash
python parse_tululu_category.py --start_page 21 --end_page 24
```

- You can input destination folder and JSON books catalog file paths,
skip downloading images or texts; to find out more, run:

```bash
python parse_tululu_category.py -h
```

## Project purposes

The project was created for educational purposes.
It's a lesson for python and web developers at [Devman](https://dvmn.org)
