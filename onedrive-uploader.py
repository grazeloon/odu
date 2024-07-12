import os
import msal
import glob
import json
import time
import yaml
import shutil
import subprocess
import requests
from tqdm import tqdm
from pathlib import Path


def createFolder(folderName, remoteFolderPath):
    upload_dir = f"{remoteFolderPath}/{folderName}"
    cl_arg = [
        'onedrive-uploader',
        'mkdir',
        f"{remoteFolderPath}/{folderName}"
    ]

    p = subprocess.Popen(cl_arg, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    return_code = p.wait()
    if return_code != 0:
        print(f"Error creating the folder on onedrive: {upload_dir}")
        exit()
    return upload_dir


def upload(filePath, upload_dir, chunk_size: int):
    cl_arg = [
        'onedrive-uploader',
        '-u', str(chunk_size),
        '-v',
        'upload', str(filePath), str(upload_dir),
    ]

    p = subprocess.Popen(cl_arg)

    # p = subprocess.run(
    #     f"onedrive-uploader -v -u {chunk_size} upload '{filePath}' '{upload_dir}'"
    # )
    
    return_code = p.wait()
    if return_code != 0:
        print(f"Error uploading: {os.path.basename(filePath)}")
    return return_code

with open('config.yml', 'r') as creds:
    app_creds = yaml.safe_load(creds)
    tv_path = app_creds['tv_path']
    movie_path = app_creds['movie_path']
    chunk_size = app_creds['upload_chunks']

main_list = []
Items = []

print("Provide the files below, enter 0 to exit.")
while True:
    entity = str(input("Enter the path of the file/folder you want to upload: "))
    if entity == 0 or entity == '0':
        break
    else:
        Items.append(entity)


print("Starting Upload.")

for path in Items:
    if os.path.isfile(path):
        # Movie
        itm = {
            'type': 'movie',
            'folderName': os.path.splitext(str(os.path.basename(path)))[0],
            'rfp': movie_path,
            'files': [
                path
            ]
        }
        main_list.append(itm)

    elif os.path.isdir(path):
        # TV Series
        itm = {
            'type': 'tv',
            'folderName': str(os.path.basename(path)),
            'rfp': tv_path,
            'files': []
        }
        for file in glob.glob(f'{path}/*.*'):
            itm['files'].append(file)
        main_list.append(itm)

    else:
        print(f"Unknown Directory Provided: {path}")
        exit()

for content in main_list:
    if content['files'] == []:
        continue

    # Creating Folder on Drive
    up_dir = createFolder(content['folderName'], content['rfp'])

    # Uploading all files one by one
    for f in content['files']:
        upload(filePath=f, upload_dir=up_dir, chunk_size=chunk_size)