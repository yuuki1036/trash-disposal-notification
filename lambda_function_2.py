import os
import boto3
from boto3.dynamodb.conditions import Key
from datetime import datetime, timedelta, timezone
from linebot import LineBotApi
from linebot.models import TextSendMessage
from linebot.exceptions import (LineBotApiError, InvalidSignatureError)

# 環境変数
CHANNEL_TOKEN = os.environ.get('LINE_CHANNEL_TOKEN')

# 曜日取得
JST = timezone(timedelta(hours=+9), 'JST')
now = datetime.now(JST)
weekday = f"{now:%a}".lower()

line_bot_api = LineBotApi(channel_access_token=CHANNEL_TOKEN)

def getUserData():
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table('trash-disposal-notification')
    res = table.scan()
    return res['Items']

def lambda_handler(event, context):
    # 送信データ取得
    targets = getUserData()
    
    for target in targets:
        user_id = target['id']
        value = target.get(weekday, False)
        # 予定が設定されていたら送信する
        if not value: continue
        message = TextSendMessage(text=f"おはようございます。\n今日は{value}の日です。")
        line_bot_api.push_message(user_id, message)

    return 0