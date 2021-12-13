import os
import logging
import boto3
from datetime import datetime, timedelta, timezone
from boto3.dynamodb.conditions import Key
from linebot import LineBotApi
from linebot.models import TextSendMessage
from linebot.exceptions import (LineBotApiError, InvalidSignatureError)

# 環境変数
CHANNEL_TOKEN = os.environ.get('LINE_CHANNEL_TOKEN')

# ログ出力
logger = logging.getLogger()
logger.setLevel(logging.INFO)

WEEK_MAP = {'mon': 0, 'tue': 1, 'wed': 2, 'thu': 3, 'fri': 4, 'sat': 5, 'sun': 6}

# 曜日index取得
JST = timezone(timedelta(hours=+9), 'JST')
now = datetime.now(JST)
weekday = f"{now:%a}".lower()
idx = WEEK_MAP[weekday]

# LINE BOT API
line_bot_api = LineBotApi(channel_access_token=CHANNEL_TOKEN)

# 全user情報取得
def getUserData():
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table('trash-disposal-notification')
    res = table.scan()
    return res['Items']


def lambda_handler(event, context):
    # 送信データ取得
    targets = getUserData()
    
    # 送信counter
    cnt = 0
    
    # 各userに通知
    for target in targets:
        user_id = target['id']
        setting = target['setting']
        # 本日の予定取得
        value = setting[idx]
        # 予定が設定されていたら送信する
        if value == 'なし': continue
        message = TextSendMessage(text=f"おはようございます。\n今日は{value}の日です。")
        line_bot_api.push_message(user_id, message)
        cnt += 1

    logger.info(f"{cnt}通送信しました。")

    return
