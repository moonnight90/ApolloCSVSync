# ApolloCSVSync

This Python script is designed to interact with the [Apollo.io](https://app.apollo.io/) API and automate certain tasks related to data import and user interactions. The script utilizes the [httpx](https://www.python-httpx.org/) library for HTTP requests and [Selenium](https://www.selenium.dev/) for browser automation.

## Prerequisites

Before running the script, ensure you have the following prerequisites installed:

- [Python](https://www.python.org/) (3.6 or higher)
- [Chrome WebDriver](https://sites.google.com/chromium.org/driver/) (ensure it's in your system's PATH)

## Installation

1. Install the required Python packages:

   ```bash
   pip install -r requirements.txt
   ```

## Usage

1. Open a terminal and navigate to the directory where the script is located.

2. Run the script:

   ```bash
   python main.py
   ```

3. Follow the prompts to input your email, password, and file path.

4. The script will then perform the following actions:
   - Log in to the Apollo.io platform.
   - Analyze a CSV file.
   - Import the file's data into the platform.
   - Retrieve bulk IDs from the imported data.
   - Search for lists using the retrieved values.
   - Interact with the Apollo.io web interface using Selenium:
     - Load the browser and navigate to a specific page.
     - Perform a series of actions in the browser.

## Notes

- The script utilizes the Apollo.io API for data import and retrieval.
- Browser automation is performed using Selenium, so ensure that Chrome WebDriver is installed and accessible.
- The script logs in with the provided email and password and performs a series of automated actions on the platform.

**Disclaimer:** Use this script responsibly and in compliance with the terms of service of the platforms you are interacting with. Automated actions may have implications, and excessive use could lead to account restrictions.