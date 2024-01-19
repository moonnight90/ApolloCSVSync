# ApolloCSVSync

This Python script utilizes the Apollo API to automate the process of importing and analyzing CSV files into the Apollo platform. The script is designed to perform the following tasks:

1. **Login**: Authenticate with the Apollo API using the provided email and password.
2. **Analyze File**: Upload a CSV file and analyze its structure to extract relevant information such as column headers and attachment ID.
3. **Import File**: Initiate the import process for the analyzed CSV file, including specifying import settings and mapping CSV columns to Apollo fields.
4. **Retrieve Bulk IDs**: Fetch organization IDs for the imported data.
5. **Search Lists**: Search for existing lists in Apollo using the retrieved organization IDs.
6. **Retrieve People**: Retrieve a list of people associated with the organization IDs.
7. **Add People to List**: Add the retrieved people to a specified list.

## Prerequisites
- Python 3.x
- Required Python packages: `httpx`, `requests_toolbelt`

## Usage
1. Install the required packages:

    ```bash
    pip install -r requirements.txt
    ```

2. Run the script:

    ```bash
    python main.py
    ```

3. Follow the prompts to enter your Apollo credentials, file path, and list name.

**Note:** Ensure that you have valid Apollo credentials and the necessary permissions to perform the specified actions.

## Configuration
- The `main_headers` dictionary in the script contains the default HTTP headers used for API requests. Update these headers if needed.

## Disclaimer
This script is provided as-is and may require adjustments based on changes to the Apollo API or specific use cases. Use it responsibly and adhere to Apollo's terms of service.

## License
This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.