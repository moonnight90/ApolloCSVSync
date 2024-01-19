import os
import time
import httpx
from requests_toolbelt.multipart.encoder import MultipartEncoder
import json
import logging
import random
import getpass


# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s',datefmt='%Y-%m-%d %H:%M:%S')

# Define main headers
main_headers = {
    'authority': 'app.apollo.io',
    'accept': '*/*',
    'accept-language': 'en-GB,en;q=0.9,en-US;q=0.8',
    'content-type': 'application/json',
    'origin': 'https://app.apollo.io',
    'referer': 'https://app.apollo.io/',
    'sec-ch-ua': '"Not_A Brand";v="8", "Chromium";v="120", "Microsoft Edge";v="120"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Windows"',
    'sec-fetch-dest': 'empty',
    'sec-fetch-mode': 'cors',
    'sec-fetch-site': 'same-origin',
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0',
}

class Bot(httpx.Client):
    
    def __init__(self, email, password) -> None:
        
        self.timeout = httpx.Timeout(timeout=10,connect=60)
        super().__init__(timeout=self.timeout)
        
        # Set base URL and update headers
        self.BASE_URL = 'https://app.apollo.io/api/v1/'
        self.headers.update(main_headers)
        self.email = email
        self.password = password
        
        # Initialize logger and current_user_id
        self.logger = logging.getLogger('Scraper')
        self.current_user_id = None
        if not self.login(email, password):
            exit()

    # Lambda functions for convenience
    chunks = lambda self, l, n: [l[i:i+n] for i in range(0, len(l), n)]
    file_name = lambda self, file_path: os.path.basename(file_path)
    delay = lambda self: time.sleep(random.randint(2,5))

    def login(self, email, password):
        # Attempt login
        login_payload = {
            'email': email,
            'password': password,
            'timezone_offset': -300
        }

        response = self.post(self.BASE_URL+'auth/login', json=login_payload)
        if response.status_code == 401:
            # Log authentication failure
            
            self.logger.error(response.json().get('message', 'Login failed'))
            return False
        elif response.status_code == 200:
            # Log successful login
            users = response.json().get('bootstrapped_data', {}).get('users', [])
            if users:
                user_info = users[0]
                self.current_user_id = user_info['id']
                self.logger.info(f"Login Success: WELCOME {user_info['name']}")
            cookies = response.cookies
            response.headers.update({'X-CSRF-TOKEN': cookies.get('X-CSRF-TOKEN', '')})
            self.cookies.update(cookies)
            return True

    def analyze_file(self, file_path) -> tuple:
        try:
            # Analyze the CSV file
            payload = MultipartEncoder({'uploaded_file': (self.file_name(file_path), open(file_path, 'rb'), 'text/csv')})
            resp = self.post(self.BASE_URL+"account_imports/analyze",
                             data=payload.read().decode(),
                             headers={'content-type': f"multipart/form-data; boundary={payload.boundary_value}"})
            resp.raise_for_status()

            # Extract relevant information from the response
            resp_json = resp.json()
            columns = resp_json.get('columns', [])
            mapping = {column['csv_header']: column['apollo_field'] for column in columns}
            mapping.update({'Domain': 'organization_website'})
            return mapping, resp_json.get('attachment_id', '')

        except Exception as e:
            # Log and handle errors
            self.logger.error(f"Error analyzing file: {str(e)}")
            raise

    def get_import_id(self, file_path, mapping_data, attachment_id) -> str:
        try:
            # Initiate file import
            payload = MultipartEncoder({
                "name": self.file_name(file_path),
                "push_to_salesforce": "true",
                "owner_update_policy": "skip",
                "action_if_duplicate": "update",
                "try_to_find_account_domain": "true",
                "try_to_find_account_location": "undefined",
                "owner_id": self.current_user_id,
                "stage_id": "use_csv",
                "emailer_campaign_id": "null",
                "send_email_from_email_account_id": "undefined",
                "send_email_from_email_address": "undefined",
                "auto_assign_accounts": "update",
                "append_label_names": "null",
                "mapping":json.dumps(mapping_data),
                'uploaded_file': (self.file_name(file_path), open(file_path, 'rb'), 'text/csv'),
                "attachment_id":attachment_id })

            resp = self.post(self.BASE_URL + "account_imports/import",
                             data=payload.read().decode(),
                             headers={'content-type': f"multipart/form-data; boundary={payload.boundary_value}"})
            resp.raise_for_status()

            # Extract relevant information from the response
            account = resp.json().get('account_imports', [{}])[0]
            import_id = account.get('id', '')
            row_count = account.get('row_count', 0)
            self.logger.info(f"File Imported: {row_count} rows imported from file ")
            return import_id, row_count

        except Exception as e:
            # Log and handle errors
            self.logger.error(f"Error importing file: {str(e)}")
            raise

    def get_bulk_ids(self, import_id, row_count) -> list:
        try:
            # Retrieve bulk IDs
            payload = {"account_import_ids": [import_id], "page": 1, "per_page": row_count,
                       "context": "companies-index-page", "display_mode": "id_only_mode"}

            resp = self.post(self.BASE_URL + "mixed_companies/search", json=payload)
            resp_json = resp.json()
            self.delay()

            # Extract relevant information from the response
            payload = {"entity_ids": resp_json.get('model_ids', []), "field": "organization_id"}
            resp = self.post(self.BASE_URL + "mixed_companies/bulk_get_field", json=payload)
            field_values = resp.json().get('field_values', [])
            return field_values

        except Exception as e:
            # Log and handle errors
            self.logger.error(f"Error retrieving bulk IDs: {str(e)}")
            raise

    def search_lists(self, values) -> str:
        # Search for lists using specified values
        payload = {"values": values, "type": "organization_id"}
        resp = self.post(self.BASE_URL + "search_lists", json=payload)
        return resp.json().get('id', '')

    def people_list(self, id) -> list:
        # Retrieve a list of people using the specified ID
        payload = {"q_search_list_id": id, "page": 1, "display_mode": "metadata_mode", "per_page": 1,
                   "context": "people-index-page"}
        resp = self.post(self.BASE_URL + "mixed_people/search_metadata_mode", json=payload)

        # Retrieve model IDs
        total_pipeline = resp.json().get('pipeline_total', 0)
        total_pipeline = total_pipeline if total_pipeline<=50000 else 50000
        
        payload = {"q_search_list_id": id, "page": 1, "display_mode": "id_only_mode",
                   "per_page": total_pipeline, "context": "people-index-page"}

        resp = self.post(self.BASE_URL + "mixed_people/search", json=payload)
        model_ids = resp.json().get('model_ids', [])
        return model_ids

    def add_people_to_list(self, model_ids,list_name):
        count = 1
        for chunk in self.chunks(model_ids, 25):
            # Add people to the specified list in chunks
            payload = {"owner_id": self.current_user_id, "label_names": [list_name], "entity_ids": chunk,
                       "account_id": None, "async": True, "analytics_context": "Searcher: Selected People",
                       "view_mode": "table", "export_csv": False, "include_guessed_emails": True,
                       "update_existing_contacts_owner": False, "update_existing_contacts_account": False,
                       "prospect_dangerous_account_stages": False, "cta_name": "Save People"}

            resp = self.post(self.BASE_URL + "mixed_people/add_to_my_prospects", json=payload)
            if resp.status_code == 200:
                self.logger.info(f"{count * 25}/{len(model_ids)} people added to list...")
                count += 1
            else:
                self.logger.critical(msg="ratelimit error")
                exit()
            self.delay()

    def run(self, file):
        # Execute the complete workflow
        try:
            result = self.analyze_file(file)
            import_id, row_count = self.get_import_id(file, result[0], result[1])
            if row_count:
                self.delay()
                values = self.get_bulk_ids(import_id, row_count)
                self.delay()
                q_id = self.search_lists(values)
                model_ids = self.people_list(q_id)
                if len(model_ids):
                    list_name = input('[?] List_name? ')
                    self.add_people_to_list(model_ids,list_name)

        except Exception as e:
            # Log and handle unexpected errors
            self.logger.error(f"Unexpected error: {str(e)}")

# Main execution
if __name__ == "__main__":
    email = input('[?] Email: ')
    password = getpass.getpass(prompt='[?] Password: ')
    obj = Bot(email,password) 
    file_path = input('[?] File_path? ')
    obj.run(file_path)
