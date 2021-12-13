import os
import logging
import json
from datetime import datetime, timedelta, timezone
import boto3
from boto3.dynamodb.conditions import Key
from linebot import (LineBotApi, WebhookHandler)
from linebot.models import (MessageEvent, TextMessage, TextSendMessage, TemplateSendMessage, ButtonsTemplate, PostbackEvent, UnfollowEvent)
from linebot.exceptions import (LineBotApiError, InvalidSignatureError)

GUIDE_TEXT = """\
ごみすて支援ボット 53ST

毎朝７時にごみすて通知を送信するよ。
通知内容は曜日ごとに自由に設定できます。

トーク画面で何かメッセージを送信するとメニュー画面を開きます。

プライバシーについて
友だち追加時に発行される識別IDを用いて設定情報を管理します。
識別IDは通知の送信以外の用途には使用いたしません。
ブロックしたり友だち削除すると設定情報は削除されます。

ver.1.0 2021 yuuki1036"""

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

# LINE BOT API
line_bot_api = LineBotApi(channel_access_token=CHANNEL_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)

# dynamoDB接続
def connectDB(user_id):
    db = boto3.resource('dynamodb')
    table = db.Table('trash-disposal-notification')
    return table

# IDからuser情報取得
def getUserData(user_id):
    table = connectDB(user_id)
    res = table.query(KeyConditionExpression=Key('id').eq(user_id))
    return res['Items'][0] if res['Items'] else None

# user情報新規作成
def createUserData(user_id, user_name):
    setting = ['なし'] * 7
    item = {
        'id': user_id,
        'name': user_name,
        'setting': setting,
        'state': '99',
        'create': timestamp,
    }
    table = connectDB(user_id)
    res = table.put_item(Item=item)
    return

"""
state変更

stateはメッセージ受付処理の状態
0 - 6: 予定を設定する（曜日番号に対応）
99   : デフォルト（メニューを返す）

曜日設定に進んだ場合は
月曜から日曜まで設定し直したあと、デフォルトに戻る
"""
def changeState(user_data):
    # state変更
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
    table = connectDB(user_id)
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
    
    table = connectDB(user_id)
    table.update_item(
        Key={'id': user_id},
        UpdateExpression="set #setting=:s",
        ExpressionAttributeNames={'#setting': 'setting'},
        ExpressionAttributeValues={':s': setting}
    )
    return

# user情報削除
def deleteSetting(user_id):
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table('trash-disposal-notification')
    table.delete_item(Key={'id': user_id})
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
                    'data': 'setting',
                    'label': '通知設定', 
                },
                {
                    'type': 'postback',
                    'data': 'guide',
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
    text = f"{day_name}曜日の予定を10文字以内で入力してね。\n現在の設定は{now_text}です。\n通知が不要な場合は「なし」と入力してね。\n\n例：燃えるごみ, ダンボールなど"
    return TextSendMessage(text=text)

# ガイドメッセージ作成
def createGuide():
    return TextSendMessage(text=GUIDE_TEXT)


def lambda_handler(event, context):
    
    if "x-line-signature" in event["headers"]:
        signature = event["headers"]["x-line-signature"]
        
    body = event['body']
    
    # メッセージを受信したとき
    @handler.add(MessageEvent, message=TextMessage)
    def onMessage(line_event):
        # user情報取得
        user_id = line_event.source.user_id
        user_data = getUserData(user_id)
        
        if user_data:
            # stateを確認
            state = int(user_data['state'])
            if state == 99:
                # メインメニュー表示
                message = createMainMenu(user_data, "お呼びですか？")
            else:
                # 予定設定処理
                # 受信メッセージをuser情報に登録する
                value = line_event.message.text
                # 値は10文字以内
                value = value if len(value) <= 10 else value[:10]
                # DB更新
                updateSetting(user_data, value)
                # 更新後に再取得
                user_data = changeState(user_data)
                state = int(user_data['state'])
                if state == 99:
                    # 予定設定完了
                    message = createMainMenu(user_data, "設定が完了したよ！")
                    logger.info(f"{user_data['name']} 設定完了")
                else:
                    # 次の曜日の予定設定
                    message = createSettingMessage(user_data)
        else:
            # user情報作成
            user_name = line_bot_api.get_profile(user_id).display_name
            createUserData(user_id, user_name)
            user_data = getUserData(user_id)
            logger.info(f"{user_name} 新規作成")
            # メインメニュー表示
            message = createMainMenu(user_data, "まずは予定を設定してね！")
        
        # オウム返し
        # message = TextSendMessage(text=line_event.message.text)
        
        # 返答する
        line_bot_api.reply_message(line_event.reply_token, message)
    
    
    # 何らかの選択肢を選んだとき
    @handler.add(PostbackEvent)
    def onPostback(line_event):
        mode = line_event.postback.data
        if mode == "guide":
            # 使い方
            message = createGuide()
        elif mode == 'setting':
            # 予定設定
            # user情報取得
            user_id = line_event.source.user_id
            user_data = getUserData(user_id)
            # stateを予定設定に変更
            user_data = changeState(user_data)
            # 予定の入力を促すメッセージ作成
            message = createSettingMessage(user_data)
        
        # 返答する
        line_bot_api.reply_message(line_event.reply_token, message)
    
    # 友だち削除またはブロックされたとき    
    @handler.add(UnfollowEvent)
    def onUnFollow(line_event):
        # 送信元id
        user_id = line_event.source.user_id
        # user情報削除
        user_data = getUserData(user_id)
        if user_data:
            deleteSetting(user_id)
            logger.info(f"削除 {user_data['name']}")
        return
        
        
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
