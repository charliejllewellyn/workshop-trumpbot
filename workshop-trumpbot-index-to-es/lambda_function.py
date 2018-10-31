import json
import urllib
import boto3
import uuid

import os
import docx2txt
import requests
from requests_aws4auth import AWS4Auth
from elasticsearch import Elasticsearch, RequestsHttpConnection


s3 = boto3.resource('s3')
dynamo = boto3.resource('dynamodb')
comprehend = boto3.client('comprehend')


region = 'us-east-1' ## Replace with your own region
host = 'https://' + os.environ.get('ES_ENDPOINT') ## Replace with your own elasticsearch domain, INCLUDE https://
index = 'speech-v1' ## Replace with your own elasticsearch index
service = 'es'

credentials = boto3.Session().get_credentials()
awsauth = AWS4Auth(credentials.access_key, credentials.secret_key, region, service, session_token=credentials.token)

type = 'speech'
url = host + '/' + index + '/' + type
    
headers = { "Content-Type": "application/json" }

es = Elasticsearch(
    hosts=[{'host': host, 'port': 443}],
    http_auth=awsauth,
    use_ssl=True,
    verify_certs=True,
    connection_class=RequestsHttpConnection
)

def index_to_elasticsearch(doc):
    r = requests.post(url, auth=awsauth, json=doc, headers=headers)
    
def push_to_dynamo(doc):
    speech_table = dynamo.Table("speech-table")
    r = speech_table.put_item(Item = doc)

def lambda_handler(event, context):
    
    bucket = event['Records'][0]['s3']['bucket']['name']
    key = urllib.unquote_plus(event['Records'][0]['s3']['object']['key'].encode('utf8'))
    
    s3.Bucket(bucket).download_file(key, '/tmp/document.docx')

    document = docx2txt.process("/tmp/document.docx")
    
    
    current_position = 0
    end_of_document = len(document)

    while True:
        next_position = document.find('\n\n\n', current_position, end_of_document)
        if next_position < 0:
            break
        
        paragraph = document[current_position:next_position]
        
        current_position = next_position+3


        entities = comprehend.detect_entities(
            Text=paragraph,
            LanguageCode='en')
        key_phrases = comprehend.detect_key_phrases(
            Text=paragraph,
            LanguageCode='en')

        
        
        id = str(uuid.uuid4())

        doc = {}
        doc['id'] = id
        doc['bucket'] = bucket
        doc['key'] = key
        doc['paragraph'] = paragraph
        
        push_to_dynamo(doc)
        
        doc = {}
        doc['id'] = id
        doc['bucket'] = bucket
        doc['key'] = key
        doc.update(entities)
        doc.update(key_phrases)
        
        index_to_elasticsearch(doc)

    
    return 'Execution Successful'
