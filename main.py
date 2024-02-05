import os
import time
import string
import httpx
from requests_toolbelt.multipart.encoder import MultipartEncoder
import json
import logging
import random
import getpass
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as ES
from urllib.parse import parse_qs, urlencode, urlparse

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
    delay = lambda self: time.sleep(random.randint(4,5))
    chache_key = lambda self: int(time.time()*1000)
    unique_code = lambda self: ''.join(random.choices(string.ascii_letters+string.digits,k=17))

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
    def safety_check(self,model_ids):
        payload = {"cacheKey":self.chache_key(),"emailer_campaign_id":None,"entity_ids":model_ids,
                   "use_new_deployment_safety_check":True}
        resp = self.post(self.BASE_URL+"mixed_people/safety_check",json=payload)
        print(resp.status_code)
        return True if resp.status_code == 200 else False
    def add_people_to_list(self, model_ids,list_name):
        count = 1
        for chunk in self.chunks(model_ids, 25):
            # Add people to the specified list in chunks
            if self.safety_check(chunk):
                self.logger.info("Safety Check: PASS")
                payload = {"owner_id": self.current_user_id, "label_names": [list_name], "entity_ids": chunk,
                        "account_id": None, "async": True, "analytics_context": "Searcher: Selected People",
                        "view_mode": "table", "export_csv": False, "include_guessed_emails": True,
                        "update_existing_contacts_owner": False, "update_existing_contacts_account": False,
                        "prospect_dangerous_account_stages": False, "cta_name": "Save People","cacheKey":self.chache_key(),
                        "signals":{"finder_view_id":"5b8050d050a3893c382e9360","pendo":"t6mU4Y6iEdhxX5MQid4c4G8N1hc"}}

                resp = self.post(self.BASE_URL + "mixed_people/add_to_my_prospects", json=payload)
                if resp.status_code == 200:
                    self.logger.info(f"{count * 25}/{len(model_ids)} people added to list...")
                    count += 1
                else:
                    self.logger.critical(msg="ratelimit error")
                    exit()
            else:
                self.logger.critical(msg="Safety Check Fails")
                exit()
            self.delay()
    def ping(self):
        data = {
            'app_id': 'dyws6i9m',
            'v': '3',
            'g': 'b2f78251325f3cfca8e557219326cf293ae80676',
            's': 'a7508c4d-5a55-4e9c-a1e6-3e19be8ad7b5',
            'r': '',
            'platform': 'web',
            'integration_type': 'js-snippet',
            'Idempotency-Key': 'a270b111c64f1e06',
            'internal': '{"hubspot_tracking_cookie":"95d9a65c69070041818c85d4de9d757f"}',
            'is_intersection_booted': 'false',
            'page_title': 'People - Apollo',
            'user_active_company_id': '-1',
            'user_data': '{"email":"richard@toplineemail.com","user_id":"65959905ecbfce03007f1de4","user_hash":"075b862c7a0a7c8778db22da098d0aa3acbf037cd7db0988ed796cd804bb7e98"}',
            'source': 'apiUpdate',
            'sampling': 'false',
            'referer': 'https://app.apollo.io/#/people?finderViewId=5b8050d050a3893c382e9360&qKeywords=atif&page=2&personTitles[]=teacher',
            'anonymous_session': 'eWdEUDFkanlmdjZPSHdEem9YRkcwTEZVbS94YlcyZE4zeFlLYU1iSWZieTBmRVJ3ME1uQWZzVUw2NnNaMU9PMy0tTmNTL0pyT0MzZ2hQTEZELytRMVZSZz09--14ef1ec10ceafc0fe829b218ca67164e21c424db',
            'device_identifier': 'f66b14fc-0233-4b92-9a6a-d96bd99ff716',}
        resp = self.post("https://api-iam.intercom.io/messenger/web/ping")
    def wait_n_ele(self,driver,selector):
        time.sleep(1)
        try:
            WebDriverWait(driver,30).until(ES.visibility_of_element_located((By.CSS_SELECTOR,selector)))
            return driver.find_element(By.CSS_SELECTOR,selector)
        except: return None
    
    def url_params_to_dict(self,url):
        # Parse the URL and extract the query parameters
        parsed_url = urlparse(url)
        query_params = parse_qs(parsed_url.query)

        # Convert the query parameters to a dictionary
        params_dict = {key: value[0] for key, value in query_params.items()}

        return params_dict
    def dict_to_url_params(self,params_dict):
        # Convert the dictionary to URL-encoded parameters
        url_params = urlencode(params_dict, doseq=True)

        return url_params
    def load_browser(self,q_id,list_name,total_pages):
        options = webdriver.ChromeOptions()
        options.add_argument('--start-maximized')
        driver = webdriver.Chrome(options=options)
        driver.get('https://app.apollo.io')
        for key in self.cookies:
            driver.add_cookie({"name": key, "value": self.cookies[key]})
        page = 1
        url = f'https://app.apollo.io/#/people?finderViewId=5b6dfc5a73f47568b2e5f11c&qSearchListId={q_id}&page={page}'
        driver.get(url)
        
        input('Apply Filter then press any key to continue')
        
        params = self.url_params_to_dict("https://g.com?"+driver.current_url.split('?')[1])
        

        while page<=int(total_pages):
            params['page'] = page
            driver.get("https://app.apollo.io/#/people?"+self.dict_to_url_params(params))
            driver.implicitly_wait(1)
            self.delay()
            self.wait_n_ele(driver,'button.finder-select-multiple-entities-button').click()
            self.wait_n_ele(driver,'a.zp-menu-item').click()
            self.wait_n_ele(driver,'button.zp-button.zp_Yeidq').click()
            self.wait_n_ele(driver,'div[role="dialog"] input.Select-input').send_keys(list_name)
            self.wait_n_ele(driver,'button[type="submit"]').click()
            while True:
                if not driver.find_elements(By.CSS_SELECTOR,'div.zp-modal-content'):break
                time.sleep(1)
            self.logger.info(f"ADDED: Page {page} added...")
            page +=1
        
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
                list_name = input('[?] List_name? ')
                total_page = input("[?] Total pages? ")
                self.load_browser(q_id,list_name,total_page)
                # model_ids = self.people_list(q_id)
                # if len(model_ids):
                #     list_name = input('[?] List_name? ')
                #     self.add_people_to_list(model_ids,list_name)

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