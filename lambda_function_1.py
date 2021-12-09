import json
import datetime

import os
import logging
import traceback

import boto3
from boto3.dynamodb.conditions import Key

from linebot import (LineBotApi, WebhookHandler)
from linebot.models import (MessageEvent, TextMessage, TextSendMessage, TemplateSendMessage, ButtonsTemplate, PostbackEvent)
from linebot.exceptions import (LineBotApiError, InvalidSignatureError)

# 環境変数
CHANNEL_TOKEN = os.environ.get('LINE_CHANNEL_TOKEN')
CHANNEL_SECRET = os.environ.get('LINE_CHANNEL_SECRET')

# ログ出力
logger = logging.getLogger()
logger.setLevel(logging.INFO)

handler = WebhookHandler(CHANNEL_SECRET)
line_bot_api = LineBotApi(channel_access_token=CHANNEL_TOKEN)

def getUserData(user_id):
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table('trash-disposal-notification')
    res = table.query(
        KeyConditionExpression=Key('id').eq(user_id)
    )
    return res['Items']

def createSettingMenu(user_data):
    return TemplateSendMessage(
        alt_text="alt text",
        template=ButtonsTemplate(
            title="Main Menu",
            text="下から１つ選んでね！",
            actions=[
                {
                    'type': 'postback',
                    'data': '{"mode":"setting","day":"mon"}',
                    'label': '通知設定', 
                },
                {
                    'type': 'postback',
                    'data': '{"mode":"guide"}',
                    'label': 'サービスについて', 
                },
            ]
        )
    )

def createGuide():
    text = """\
    プライバシーについて
    設定状態の保存のためLINEアカウントの識別IDを保存します。
    情報は暗号化されます。
    
    ver.1.0 © 2021 yuuki1036
    """
    
    return TextSendMessage(text=text)

def lambda_handler(event, context):
    
    logger.info(event)
    if "x-line-signature" in event["headers"]:
        signature = event["headers"]["x-line-signature"]
        
    body = event['body']
    
    ok_json = {"isBase64Encoded": False,
              "statusCode": 200,
              "headers": {},
              "body": "OK"}
    error_json = {"isBase64Encoded": False,
                  "statusCode": 500,
                  "headers": {},
                  "body": "Error"}
                  
    
        
    
    # 何かメッセージを送るとメインメニューを表示する
    @handler.add(MessageEvent, message=TextMessage)
    def onMessage(line_event):
        # 送信元id
        user_id = line_event.source.user_id
        # user情報取得
        user_data = getUserData(user_id)
        if user_data:
            message = createSettingMenu(user_data)
        line_bot_api.reply_message(line_event.reply_token, message)
        
    @handler.add(PostbackEvent)
    def onPostback(line_event):
        res = json.loads(line_event.postback.data)
        logger.info(f"POSTBACK RESPONSE => {res}")
        mode = res['mode']
        if mode == "guide":
            message = createGuide()
        else:
            message = TextSendMessage(text=f"{res}を選んだね！")
        line_bot_api.reply_message(line_event.reply_token, message)
        
    try:
        handler.handle(body, signature)
    except LineBotApiError as e:
        logger.error("Got exception from LINE Messaging API: %s\n" % e.message)
        for m in e.error.details:
            logger.error("  %s: %s" % (m.property, m.message))
        return error_json
    except InvalidSignatureError:
        return error_json
    
    return ok_json
    
    # weekday = 'tu'
    # targets = getUserData(weekday)
    
    # for target in targets:
    #     user_id = target['id']
    #     value = target.get(weekday, False)
    #     if not value: continue
    #     message = TextSendMessage(text=f"おはようございます。\n今日は{value}の日です。")
    #     line_bot_api.push_message(user_id, message)
    
    

    # return {
    #     'statusCode': 200,
    #     'body': json.dumps('ok', ensure_ascii=False)
    # }