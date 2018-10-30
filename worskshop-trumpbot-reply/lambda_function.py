import boto3

from elasticsearch import Elasticsearch, RequestsHttpConnection
from requests_aws4auth import AWS4Auth

dynamo = boto3.resource('dynamodb')
comprehend = boto3.client('comprehend')

speech_table = dynamo.Table("speech-table")


host = 'search-trumpbot-workshop-ficalrtxnoxpxq2nohq6snp5na.us-east-1.es.amazonaws.com' ## Replace with your own elasticsearch domain, DON'T include https://
index= "speech-v1" ## Replace with your own elasticsearch index
region = 'us-east-1' ## Replace with your own region
service = 'es'

credentials = boto3.Session().get_credentials()
awsauth = AWS4Auth(credentials.access_key, credentials.secret_key, region, service, session_token=credentials.token)

es = Elasticsearch(
    hosts=[{'host': host, 'port': 443}],
    http_auth=awsauth,
    use_ssl=True,
    verify_certs=True,
    connection_class=RequestsHttpConnection
)


def lambda_handler(event, context):

    question = event['inputTranscript']

    response = comprehend.detect_key_phrases(
        Text=question,
        LanguageCode='en'
    )
    query = ""
    for keyphrase in response['KeyPhrases']:
        query += keyphrase['Text'] + " "

    response = es.search(index, body={"size" : 50, "query": { "simple_query_string": { "query": query, "default_operator": "and" } }})
    
    if response['hits']['total'] == 0:
        r = comprehend.detect_syntax(
            Text=question,
            LanguageCode='en'
        )
        query = ""
        for token in r['SyntaxTokens']:
            if token['PartOfSpeech']['Tag'] == 'NOUN':
                query += token['Text'] + " "
        response = es.search(index, body={"size" : 50, "query": { "simple_query_string": { "query": query, "default_operator": "and" } }})

    if response['hits']['total']:
        id = response['hits']['hits'][0]['_source']['id']
        response = speech_table.get_item(Key={'id': id})
        text = "Here is what I have found: \"" + response['Item']['paragraph'] + "\""
    else:
        text = "I'm sorry, I couldn't find something for you. Could you rephrase your question and try again?"
    
    response = {
        "dialogAction": {
            "type": "Close",
            "fulfillmentState": "Fulfilled",
            "message": {
              "contentType": "SSML",
              "content": text
            },
        }
    }
    return response
