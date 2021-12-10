import json
from datetime import datetime, timedelta, timezone

import os
import logging
import traceback

import boto3
from boto3.dynamodb.conditions import Key

from linebot import (LineBotApi, WebhookHandler)
from linebot.models import (MessageEvent, TextMessage, TextSendMessage, TemplateSendMessage, ButtonsTemplate, PostbackEvent)
from linebot.exceptions import (LineBotApiError, InvalidSignatureError)


GUIDE_TEXT = """\
ごみ捨て支援BOT

毎朝７時にごみ捨て通知が届きます。
通知内容は曜日ごとに任意に設定できます。

プライバシーについて
設定状態の保持のためLINEアカウントの識別IDを暗号化して保存します。
友だち削除すると設定も削除されます。

ver.1.0 2021 yuuki1036
"""

WEEK_NAMES = ['月', '火', '水', '木', '金', '土', '日']

# 環境変数
CHANNEL_TOKEN = os.environ.get('LINE_CHANNEL_TOKEN')
CHANNEL_SECRET = os.environ.get('LINE_CHANNEL_SECRET')

# ログ出力
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# timestamp取得
JST = timezone(timedelta(hours=+9), 'JST')
now = datetime.now(JST)
timestamp = f"{now:%Y/%m/%d %H:%M:%S}"

handler = WebhookHandler(CHANNEL_SECRET)
line_bot_api = LineBotApi(channel_access_token=CHANNEL_TOKEN)

# user情報取得
def getUserData(user_id):
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table('trash-disposal-notification')
    res = table.query(
        KeyConditionExpression=Key('id').eq(user_id)
    )
    return res['Items'][0] if res['Items'] else None

# user情報作成
def createUserData(user_id, user_name):
    item = {
        'id': user_id,
        'name': user_name,
        'setting': ['なし', 'なし', 'なし', 'なし', 'なし', 'なし', 'なし'],
        'state': '99',
        'create': timestamp,
    }
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table('trash-disposal-notification')
    res = table.put_item(Item=item)
    return

# state更新
"""
0 - 6: 曜日設定中
99   : デフォルト
"""
def changeState(user_data):
    user_id = user_data['id']
    state = int(user_data['state'])
    if state == 99:
        state = 0
    elif state >= 6:
        state = 99
    else:
        state += 1
    user_data['state'] = str(state)
    
    # db更新
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table('trash-disposal-notification')
    table.update_item(
        Key={'id': user_id},
        UpdateExpression="set #state=:s",
        ExpressionAttributeNames={'#state': 'state'},
        ExpressionAttributeValues={':s': str(state)}
    )
    return user_data

# 予定更新
def updateSetting(user_data, value):
    user_id = user_data['id']
    setting = user_data['setting']
    state = int(user_data['state'])
    setting[state] = value
    
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table('trash-disposal-notification')
    table.update_item(
        Key={'id': user_id},
        UpdateExpression="set #setting=:s",
        ExpressionAttributeNames={'#setting': 'setting'},
        ExpressionAttributeValues={':s': setting}
    )
    return

# 設定状態テキスト作成
def displaySetting(user_data):
    setting = user_data['setting']
    arr = []
    for day, name in zip(WEEK_NAMES, setting):
        arr.append(f"{day}: {name}")
    return "\n".join(arr)

# メインメニュー作成
def createMainMenu(user_data, text):
    setting_text = displaySetting(user_data)
    return TemplateSendMessage(
        alt_text=text,
        template=ButtonsTemplate(
            text=f"{text}\n{setting_text}",
            actions=[
                {
                    'type': 'postback',
                    'data': '{"mode":"setting"}',
                    'label': '通知設定', 
                },
                {
                    'type': 'postback',
                    'data': '{"mode":"guide"}',
                    'label': '使い方', 
                },
            ]
        )
    )


# 設定入力メッセージ作成
def createSettingMessage(user_data):
    idx = int(user_data['state'])
    day_name = WEEK_NAMES[idx]
    now_value = user_data['setting'][idx]
    now_text = f"通知なし"  if now_value == 'なし' else f"「{now_value}」"
    text = f"{day_name}曜日の予定を入力してね。\n現在の設定は{now_text}です。\n通知が不要な場合は「なし」と入力してね。\n\n例：燃えるごみ, ダンボールなど"
    return TextSendMessage(text=text)

# ガイドメッセージ作成
def createGuide():
    return TextSendMessage(text=GUIDE_TEXT)


def lambda_handler(event, context):
    
    logger.info(event)
    if "x-line-signature" in event["headers"]:
        signature = event["headers"]["x-line-signature"]
        
    body = event['body']
    
    # メッセージを受信したとき
    @handler.add(MessageEvent, message=TextMessage)
    def onMessage(line_event):
        # 送信元id
        user_id = line_event.source.user_id
        # user情報取得
        user_data = getUserData(user_id)
        
        if user_data:
            state = int(user_data['state'])
            if state == 99:
                # user情報が存在するのでメインメニュー表示
                message = createMainMenu(user_data, "お呼びですか？")
            else:
                # 受信メッセージをuser情報に登録する
                value = line_event.message.text
                updateSetting(user_data, value)
                user_data = changeState(user_data)
                
                state = int(user_data['state'])
                if state == 99:
                    message = createMainMenu(user_data, "設定が完了したよ！")
                else:
                    message = createSettingMessage(user_data)
        else:
            # user情報作成後にメインメニュー表示
            user_name = line_bot_api.get_profile(user_id).display_name
            createUserData(user_id, user_name)
            user_data = getUserData(user_id)
            message = createMainMenu(user_data, "まずは予定を設定してね！")
        
        # オウム返し
        # message = TextSendMessage(text=line_event.message.text)
            
        line_bot_api.reply_message(line_event.reply_token, message)
    
    # 選択肢を選んだとき
    @handler.add(PostbackEvent)
    def onPostback(line_event):
        res = json.loads(line_event.postback.data)
        logger.info(f"POSTBACK RESPONSE => {res}")
        mode = res['mode']
        if mode == "guide":
            message = createGuide()
        elif mode == 'setting':
            # 送信元id
            user_id = line_event.source.user_id
            # user情報取得
            user_data = getUserData(user_id)
            user_data = changeState(user_data)
            message = createSettingMessage(user_data)
        
        line_bot_api.reply_message(line_event.reply_token, message)
        
        
    ok_json = {
        'statusCode': 200,
        'body': json.dumps('ok', ensure_ascii=False)
    }
    error_json = {
        'statusCode': 500,
        'body': json.dumps('error', ensure_ascii=False)
    }
    
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
