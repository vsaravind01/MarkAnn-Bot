<div align="center">
    <img src="assets/avatar.png" alt="Avatar" width="200" height="200" style="border-radius: 10px; border: 3px solid greenyellow;display: block">
    <h1 style="color: limegreen">MarkAnn Bot</h1>
    <p>
        An AI telegram bot that provides real-time press releases from the companies
        listed on the Bombay Stock Exchange (BSE).
    </p>
    <br/>
    <a href="https://t.me/MarkAnn_Bot" target="_blank">
        <img src="https://img.shields.io/badge/MarkAnn_Bot-Telegram-blue?logo=telegram" alt="Telegram">
    </a>
</div>

# Table of Contents

- [Introduction](#introduction)
- [Features](#features)
  * [Real-time Press Releases](#real-time-press-releases)
- [Installation](#installation)
  * [Prerequisites](#prerequisites)
  * [Setup](#setup)
  * [Docker](#docker)
- [Contributing](#contributing)
- [License](#license)

# Introduction

MarkAnn Bot is a Telegram bot that provides real-time press releases 
from the companies listed on the Bombay Stock Exchange (BSE). The bot 
monitors the BSE API for new press releases and sends them to the
subscribed users on Telegram.

# Features

## Real-time Press Releases

There are very few platforms that provide real-time information about
the listed companies in India. And out of them, there is hardly any
platform that provides quick and quality information. MarkAnn Bot
aims to fill this gap by providing real-time press releases from the
listed companies, and it goes a step further by summarizing the press
release document using Generative-AI models. This way, the users can
get a quick overview of the press release without having to read the
entire document.

The documents are classified into different categories
* Acquisition
* Orders or Contracts
* New Product Launch
* New Partnership or Collaboration

The bot also provides a link to the original document, the stock's page
on the BSE website, and a link to Google search results for the company.
The provides the users with all the necessary information to make an
informed and quick decision.

# Features in Development

- [ ] Volume spike detection
- [ ] Price spike detection
- [ ] EMA crossover detection
- [ ] Resistance and Support level crossing detection
- [ ] Bollinger Band crossing detection
- [ ] Volume Point of Control (VPoC) spike detection

# Installation

## Prerequisites

- Python 3.10 or higher (Recommended version: 3.12)
- Qdrant DB credentials
- Telegram Bot Token
- Cohere API Key
- Docker & Docker Compose (Optional)

## Setup

1. **Clone the repository**
    ```bash
    git clone https://github.com/vsaravind01/MarkAnn-Bot.git
    cd MarkAnn-Bot
    ```
2. **Install the dependencies (Recommended: Create a virtual environment)**
    ```bash
    pip install -r requirements.txt
    ```
3. **Add the required environment variables to `./scripts/start_telegram_server.sh`**
4. **Give execute permission to the script**
    ```bash
    chmod +x ./scripts/start_telegram_server.sh
    ```
5. **Start the Telegram server**
    ```bash
    ./scripts/start_telegram_server.sh
    ```

Alternatively, you can build and run the Docker container.

## Docker

1. **Build the Docker image**
    ```bash
    docker build -t markann-bot:latest -f ./docker/bot/Dockerfile .
    ```
2. **Set the environment variables in the `docker-compose.yml` file**
3. **Run the Docker container**
    ```bash
    docker-compose -f ./docker/bot/docker-compose.yml up -d
    ```

> [!NOTE]
> The logs are stored in the `./logs` directory.
> The logs is linked to the container's `/app/bot/logs` directory.
> The user.db file is stored in `./logs/user.db` directory.

# Contributing

Contributions are welcome from everyone. Whether you're a seasoned developer 
or just getting started with open-source, your contributions are invaluable 
to us. Together, we can create an amazing tool that keeps investors informed 
and helps them make better decisions.

Here are a few do's and don'ts that you should follow while contributing to this project.

- **Do's**
  * Raise an issue before starting to work on a new feature or any major bug fix.
  * Use [Black](https://github.com/psf/black) for code formatting.
  * Always create a new branch for your changes.
  * Always add docstrings to the functions and classes. (P.S. Grammar doesn't matter, but clarity does.)
  * Use [Google Style Docstrings](https://google.github.io/styleguide/pyguide.html) for documentation.
  * If you are new to open-source, you can start by fixing the issues labeled as `good first issue`.
- **Don'ts**
  * Do not add any new dependencies without discussing with the maintainers.
  * Do not add any new features without discussing with the maintainers.
  * Do not share any sensitive information such as API keys, passwords, etc., in the issues or PRs.

# License

This project is licensed under the GNU General Public License v2.0.
For more information, please refer to the [LICENSE](LICENSE) file.
