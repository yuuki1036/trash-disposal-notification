import json
import datetime
import os
import traceback
import boto3
from boto3.dynamodb.conditions import Key
from linebot import (LineBotApi, WebhookHandler)
from linebot.models import (MessageEvent, TextMessage, TextSendMessage, TemplateSendMessage, PostbackAction, ButtonsTemplate)
from linebot.exceptions import (LineBotApiError, InvalidSignatureError)

# 環境変数
LINE_USER_ID = os.environ.get('LINE_USER_ID')
LINE_CHANNEL_TOKEN = os.environ.get('LINE_CHANNEL_TOKEN')

def getUserData(weekday):
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table('trash-disposal-notification')
    res = table.scan()
    return res['Items']

def lambda_handler(event, context):
    weekday = 'th'
    targets = getUserData(weekday)
    print(targets)

    line_bot_api = LineBotApi(channel_access_token=LINE_CHANNEL_TOKEN)
    btn_temp_msg = TemplateSendMessage(
        alt_text="Buttons template",
        template=ButtonsTemplate(
            title="Menu",
            text=targets[0][weekday],
            actions=[
                PostbackAction(
                    label="postback",
                    display_text="postback text",
                    data="action=buy&itemis=1"
                )
            ]
        )
    )
    line_bot_api.push_message(LINE_USER_ID, btn_temp_msg)

    return {
        'statusCode': 200,
        'body': json.dumps('ok', ensure_ascii=False)
    }