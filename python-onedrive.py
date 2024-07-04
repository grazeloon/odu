import os
import msal
import glob
import json
import time
import yaml
import requests
from tqdm import tqdm
from pathlib import Path

def handleToken(client_id, client_secret, scopes):
    
    cachePath = "cache/tokenCache.json"

    CWD = Path.cwd()
    cachePath = CWD / cachePath

    if not os.path.isfile(cachePath):
        print("No Token File found, making one and logging in...")
        os.makedirs(os.path.dirname(cachePath), exist_ok=True)
        with open(cachePath, 'w', encoding="utf-8") as cache:
            tokenDictionary = GetAcccessToken(client_id, client_secret, scopes)
            tokenData = {
                'accessToken': {
                    'token': tokenDictionary['access_token'],
                    'expire': round(time.time()) + int(tokenDictionary['expires_in']),
                    'otherTokenData': tokenDictionary
                }
            }
            json.dump(tokenData, cache, indent=2)
            return [tokenDictionary['access_token']]
    else:
        with open(cachePath, 'r+', encoding="utf-8") as cache:
            cacheData = json.loads(cache.read())
            if int(cacheData['accessToken']['expire']) < int(time.time()):
                print("Cache token expired, generating a new one...")
                tokenDictionary = GetAcccessToken(client_id, client_secret, scopes)
                tokenData = {
                    'accessToken': {
                        'token': tokenDictionary['access_token'],
                        'expire': round(time.time()) + int(tokenDictionary['expires_in']),
                        'otherTokenData': tokenDictionary
                    }
                }
                cache.seek(0)
                cache.truncate()
                json.dump(tokenData, cache, indent=2)
                return [tokenDictionary['access_token']]
        
            else:
                print("Using the Cached token...")
                return [cacheData['accessToken']['token']]

def GetAcccessToken(client_id, client_secret, scopes):

    client = msal.ConfidentialClientApplication(
        client_id=client_id,
        client_credential=client_secret,
    )

    authorization_url = client.get_authorization_request_url(scopes)
    print(f"\nAuthorization Url: {str(authorization_url)}")
    authorization_code = input("Copy the above link, and enter the code from URL: ")
    access_token = client.acquire_token_by_authorization_code(
        code=authorization_code,
        scopes=scopes
    )
    return access_token


def createFolder(folderName, accessToken, remoteFolderPath, BASE_ENDPOINT):
    folder_url = BASE_ENDPOINT + '/me/drive/root:/' + remoteFolderPath + ':/children'
    folderReq = requests.post(
        url = folder_url,
        headers = {
            'Authorization': f'Bearer {accessToken}',
        },
        json = {
            "name": folderName,
            "folder": { },
            "@microsoft.graph.conflictBehavior": "rename"
        }
    ).json()

    if not 'createdBy' in folderReq:
        print(f"Unable to create folder in drive location {remoteFolderPath}")
        print(folderReq)
        exit()
    
    return folderReq['id']


def upload(filePath, accessToken, folder_id, BASE_ENDPOINT):

    fileName = str(os.path.basename(filePath))
    # url = BASE_ENDPOINT + f'/me/drive/items/root:/{remoteFolderPath}/{fileName}:/createUploadSession'
    url = BASE_ENDPOINT + f'/me/drive/items/{folder_id}:/{fileName}:/createUploadSession'
    
    # Creating Upload Session
    uploadSession = requests.post(
        url = url,
        headers = {
            'Authorization': f'Bearer {accessToken}',
        },
    )
    if 'uploadUrl' not in uploadSession.json():
        print(uploadSession.content.decode())
        print("Error creating Upload Session")
        exit()

    uploadUrl = uploadSession.json()['uploadUrl']

    # Preparing Data to upload
    totalFileSize = os.path.getsize(filePath)
    chunkSize = BASE_CHUNK_SIZE * REQ_MULTIPLE
    totalChunks = totalFileSize // chunkSize
    leftoverChunk = totalFileSize - (totalChunks * chunkSize)
    counter = 0

    # initiating tqdm
    pbar = tqdm(total=totalChunks)

    start_time = time.time()
    with open(filePath, 'rb') as data:
        while True:
            chunkData = data.read(chunkSize)
            startIndex = counter * chunkSize
            endIndex = startIndex + chunkSize

            if not chunkData:
                break
            if counter == totalChunks:
                endIndex = startIndex + leftoverChunk
            
            uploadHeaders = {
                'Content-Length': f'{chunkSize}',
                'Content-Range': f'bytes {startIndex}-{endIndex-1}/{totalFileSize}'
            }

            # Uploading Data
            uploadReq = requests.put(
                uploadUrl,
                headers = uploadHeaders,
                data = chunkData
            )

            if 'createdBy' in uploadReq.json():
                pbar.update(1)
                # print('File Uploaded Successfully.')
            else:
                counter += 1
                pbar.update(1)

    pbar.close()
    print(f" + File Size: {str(round(totalFileSize/1048576))} MB, Upload Time: {round(int(time.time() - start_time))} sec.")
    print("===========================================================")
    return 

def cancelUpload(uploadUrl):
    requests.delete(uploadUrl)
    return

with open('config.yml', 'r') as creds:
    app_creds = yaml.safe_load(creds)
    GRAPH_API_ENDPOINT = app_creds['graph_api_endpoint']
    CLIENT_ID = app_creds['ms_app']['client_id']
    CLIENT_SECRET = app_creds['ms_app']['client_secret']
    BASE_CHUNK_SIZE = app_creds['chunk_size']
    REQ_MULTIPLE = app_creds['req_multiple']
    remoteFolderPath = app_creds['remote_folder_path']

SCOPES = ['User.Read', 'Files.ReadWrite.All']
Items = []
files = []

accessToken = handleToken(CLIENT_ID, CLIENT_SECRET, SCOPES)[0]

print("Provide the files below, enter 0 to exit.")
while True:
    entity = str(input("Enter the path of the file/folder you want to upload: "))
    if entity == 0 or entity == '0':
        break
    else:
        Items.append(entity)
print("Starting Upload.")

for path in Items:
    files = []
    if os.path.isfile(path):
        files.append(path)
    elif os.path.isdir(path):
        for file in glob.glob(f'{path}/*.*'):
            files.append(file)
    else:
        print(f"Unknown Directory Provided: {path}")
        exit()

    # Creating Folder on Drive
    if len(files) != 1:
        folderId = createFolder(str(os.path.basename(path)), accessToken, remoteFolderPath, GRAPH_API_ENDPOINT)
    else:
        folderName = os.path.splitext(str(os.path.basename(files[0])))[0]
        folderId = createFolder(folderName, accessToken, remoteFolderPath, GRAPH_API_ENDPOINT)

    # Uploading all files one by one
    # print("Total items to upload: "+str(len(files))+"\n")
    for file in files:
        print(f" + Currently Uploading: {os.path.basename(file)}...")
        upload(file, accessToken, folderId, GRAPH_API_ENDPOINT)