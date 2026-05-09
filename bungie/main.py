import time
import requests
import bungie_secrets
import base64
import multiprocessing
import typing
from enum import Enum

class DestinyComponentType(Enum):
    ProfileInventories = 102
    ItemInstances = 300
    
class MyProcess(multiprocessing.Process):
    def __init__(self, queue: multiprocessing.Queue, myFunction: typing.Callable, **kwargs):
        multiprocessing.Process.__init__(self)
        # self.token = token
        # self.hash = hash
        #queue video https://youtu.be/iwFGC_3sVio
        self.queue = queue
        self.myFunction = myFunction
        self.kwargs = kwargs
    def run(self):
        self.queue.put(self.myFunction(**self.kwargs))
    


#https://data.destinysets.com/api/User.GetMembershipDataById?membershipId=29161835&membershipType=all

#TODO: Change membership type to be variable, not just 3 for steam#
#TODO: Caching would be multiple differnt things, such as player info, item info, etc.
#TODO: change things up to remove redundant calls (caching?)
#TODO: consider making this all into a class that would likely be a singleton, or maybe one per user?

def get_token_request_headers(token: str) -> dict:
    return {
        'X-API-Key': bungie_secrets.api_key,
        'Authorization': f'Bearer {token}'
    }

def get_profile_inventory(token: str, membership_id: str, membership_type: int) -> dict:
    url = f'https://www.bungie.net/Platform/Destiny2/{membership_type}/Profile/{membership_id}/?components={DestinyComponentType.ProfileInventories.value}'
    headers = get_token_request_headers(token)
    response = requests.get(url, headers=headers)
    return response.json()


def getBungieNetUser(token: str) -> dict:
    url = 'https://www.bungie.net/Platform/User/GetCurrentBungieNetUser/'
    headers = get_token_request_headers(token)
    response = requests.get(url, headers=headers)
    return response.json()

def get_name(token: str) -> str:
    return getBungieNetUser(token)['Response']['uniqueName']

def get_membershipid(token: str) -> str:
    return getBungieNetUser(token)['Response']['membershipId']

def get_primary_membership_id(token: str, id: int) -> str:
    url = f'https://www.bungie.net/Platform/User/GetMembershipsById/{id}/all/'
    headers = get_token_request_headers(token)
    response = requests.get(url, headers=headers)
    return response.json()['Response']['primaryMembershipId']

def get_memberships_by_id(token, id):
    url = f'https://www.bungie.net/Platform/User/GetMembershipsById/{id}/all/'
    headers = get_token_request_headers(token)
    response = requests.get(url, headers=headers)
    return response.json()


#TODO: Add a cache for the token
def get_token_from_refresh(refresh_token: str) -> str:
    url = 'https://www.bungie.net/Platform/App/OAuth/Token/'
    #Encode the client id and secret in base64
    auth = f'{bungie_secrets.client_id}:{bungie_secrets.client_secret}'
    auth = base64.b64encode(auth.encode('utf-8')).decode('utf-8')
    headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Authorization': f"Basic {auth}"
        }
    #URL encode the data
    data = {
        'grant_type': 'refresh_token',
        'refresh_token': refresh_token
    }
    payload_str = "&".join(f"{k}={v}" for k,v in data.items())
    response = requests.post(url, headers=headers, data=payload_str)
    response_json = response.json()
    return response_json['access_token']

def get_vault(token: str, primary_membership_id: str, membership_type: int) -> list:
    url = f'https://www.bungie.net/Platform/Destiny2/{membership_type}/Profile/{primary_membership_id}/?components=102'
    headers = get_token_request_headers(token)
    response = requests.get(url, headers=headers)
    return response.json()['Response']['profileInventory']['data']['items']

#A function to get an item given an itemInstanceId, membershipType, and membershipId
def get_item(token: str, item_instance_id: str, membership_type: int, membership_id: str) -> dict:
    url = f'https://www.bungie.net/Platform/Destiny2/{membership_type}/Profile/{membership_id}/Item/{item_instance_id}/?components={DestinyComponentType.ItemInstances.value}'
    headers = get_token_request_headers(token)
    response = requests.get(url, headers=headers)
    return response.json()['Response']['instance']['data']

def get_item_definition(token: str, item_hash: int) -> dict:
    url = f'https://www.bungie.net/Platform/Destiny2/Manifest/DestinyInventoryItemDefinition/{item_hash}/'
    headers = get_token_request_headers(token)
    response = requests.get(url, headers=headers)
    if (
        response.json()['Response']['displayProperties']['name'] == 'Unknown'
        or response.json()['Response']['displayProperties']['name'] is None
    ):
        print(response.json())
    return response.json()['Response']

def get_item_name(token: str, item_hash: int) -> str:
    return get_item_definition(token, item_hash)['displayProperties']['name']

def print_item_name(token, item_hash: int):
    name = get_item_definition(token, item_hash)['displayProperties']['name']
    print(name)


if __name__ == '__main__':
    token = get_token_from_refresh('CPWKBRKGAgAgVNmC7EL/rkNDF/H/sPF9OSFOcqKMmtVqpNJ3GijZbzXgAAAATKOl24oVJmD7i2qRTOQBPaxQDyByCwqMXcupf1tDxKZNRWRt4mHZF3rOUN7cpFFE4zl964qFi/iSIJK/8p0BmvmkYViiWqhNayqYNP91G9oauPWJKmNmUPzADQBSz2RApcwB4k4krWdqyh4Zg28i4eAjyS5egjGCu6eAF+PlHtbxbYOS0SQa/bOdJUfyua84bZvScV3KPKtz0mCMrbW3lYfDdm7o7rP2I04CgHKGi2vhWpXMN8Mto3TzzlZEn6AWxIW2AQZr47ocgf5pG1vd0ae7MxnupDbyreEKDvwU4gg=')
    vault = get_vault( token, get_primary_membership_id(token, get_membershipid(token)), 3)
    processes = []
    process_counter = 0
    queue = multiprocessing.Queue(maxsize=10000)
    for item in vault:
        if 'itemInstanceId' not in item:
            continue
        processes.append(MyProcess(queue, get_item_name, token=token, item_hash=item['itemHash']))
        processes[process_counter].start()
        process_counter += 1
        # thing = get_item(token, item['itemInstanceId'], 3, get_primary_membership_id(token, get_membershipid(token)))
        # print_item_name(token, item['itemHash'])
        # print(thing)
    # process: MyProcess
    # for process in processes:
    #     process.join()
    while process_counter > 0:
        print(queue.get())
        process_counter -= 1
    # print(vault)