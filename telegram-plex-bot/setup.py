from setuptools import setup, find_packages

setup(
    name="telegram-plex-bot",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        'python-telegram-bot>=20.0',
        'python-dotenv',
        'qbittorrent-api',
        'plexapi',
        'pytest',
        'pytest-asyncio',
    ],
    entry_points={
        'console_scripts': [
            'plex-bot=bot:main',
        ],
    },
) 