import json
import os
from linebot import (LineBotApi, WebhookHandler)
from linebot.models import (MessageEvent, TextMessage, TextSendMessage)
from linebot.exceptions import (LineBotApiError, InvalidSignatureError)

# 環境変数
LINE_USER_ID = os.environ.get('LINE_USER_ID')
LINE_CHANNEL_TOKEN = os.environ.get('LINE_CHANNEL_TOKEN')

def lambda_handler(event, context):

    line_bot_api = LineBotApi(channel_access_token=LINE_CHANNEL_TOKEN)
    line_bot_api.push_message(LINE_USER_ID, TextSendMessage(text='Hello World!'))

    return {
        'statusCode': 200,
        'body': json.dumps('ok', ensure_ascii=False)
    }