import os
import sys
import logging
import json

import base64
import hashlib
import hmac

import urllib.request, urllib.parse

import datetime
from dateutil.tz import gettz

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# get channel_secret and channel_access_token from your environment variable
channel_secret = os.getenv('LINE_CHANNEL_SECRET', None)
channel_access_token = os.getenv('LINE_CHANNEL_ACCESS_TOKEN', None)
if channel_secret is None:
    logger.error('Specify LINE_CHANNEL_SECRET as environment variable.')
    sys.exit(1)
if channel_access_token is None:
    logger.error('Specify LINE_CHANNEL_ACCESS_TOKEN as environment variable.')
    sys.exit(1)

def lambda_handler(event, context):
    logger.info(json.dumps(event))
    
    channel_secret = os.getenv('LINE_CHANNEL_SECRET', None)
    body = event.get('body', '') # Request body string
    hash = hmac.new(channel_secret.encode('utf-8'), body.encode('utf-8'), hashlib.sha256).digest()
    signature = base64.b64encode(hash).decode('utf-8')
    # Compare X-Line-Signature request header and the signature
    if signature != event.get('headers').get('X-Line-Signature', '') and signature != event.get('headers').get('x-line-signature', ''):
        logger.error('Validate Error')
        return {'statusCode': 403, 'body': '{}'}
    
    for event_data in json.loads(body).get('events', []):
        if event_data['type'] != 'message':
            continue
        
        message_body = [{}]
        
        if event_data['message']['type'] == 'location':
            message_lat = event_data['message']['latitude']
            message_lng = event_data['message']['longitude']
            url = 'https://api.sunrise-sunset.org/json'
            req = urllib.request.Request(url + '?lat=' + str(message_lat) + '&lng=' + str(message_lng) + '&formatted=0')
            with urllib.request.urlopen(req) as res:
                res_body = res.read()
                logger.info(res_body)
                    
                if json.loads(res_body).get('status', '') != 'OK':
                    continue
                
                results = json.loads(res_body).get('results', '')
                sunrise_datetime, sunrise_time = convert_utc_to_jst(results['sunrise'])
                sunset_datetime, sunset_time = convert_utc_to_jst(results['sunset'])
                solar_noon_datetime, solar_noon_time = convert_utc_to_jst(results['solar_noon'])
                day_length = convert_seconds_to_time(results['day_length'])
                
                message_body = [{
                    'type': 'text',
                    'text': 'その地点は、\n日の出：' + str(sunrise_time) + '\n日の入り：' + str(sunset_time) + '\n南中時刻：' + str(solar_noon_time) + '\n昼の長さ：' + str(day_length) + '\nです。'
                }]
            
        elif event_data['message']['type'] == 'text':
            message_text = event_data['message']['text']
            if message_text == 'やめる':
                message_body = [{
                    'type': 'text',
                    'text': 'またね。'
                }]
            else:
                message_body = [{
                    'type': 'text',
                    'text': '日の出・日の入り時刻を調べるよ。地点を教えてね。',
                    'quickReply': {
                        'items': [{
                            'type': 'action',
                            'action': {
                                'type': 'message',
                                'label': 'やめる',
                                'text': 'やめる'
                            }
                        },
                        {
                            'type': 'action',
                            'action': {
                                'type': 'location',
                                'label': 'Location',
                            }
                        }]
                    }
                }]
            
        else:
            continue
        
        url = 'https://api.line.me/v2/bot/message/reply'
        headers = {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer ' + channel_access_token,
        }
        body = {
            'replyToken': event_data['replyToken'],
            'messages': message_body
        }
        req = urllib.request.Request(url, data=json.dumps(body).encode('utf-8'), method='POST', headers=headers)
        with urllib.request.urlopen(req) as res:
            res_body = res.read().decode('utf-8')
            if res_body != '{}':
                logger.info(res_body)
    
    return {'statusCode': 200, 'body': '{}'}


def convert_utc_to_jst(datetime_utc):
    timestamp_utc = datetime.datetime.strptime(datetime_utc, "%Y-%m-%dT%H:%M:%S%z")
    timestamp_jst = timestamp_utc.astimezone(gettz('Asia/Tokyo'))
    datetime_jst = datetime.datetime.strftime(timestamp_jst, '%Y-%m-%dT%H:%M:%S%z')
    time_jst = datetime.datetime.strftime(timestamp_jst, '%H:%M:%S')
    return datetime_jst, time_jst


def convert_seconds_to_time(seconds):
    time = datetime.timedelta(seconds=seconds)
    return time