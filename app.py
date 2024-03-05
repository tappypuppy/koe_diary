from flask import Flask, request, abort
import os
import requests
from dotenv import load_dotenv
from linebot.v3 import (
    WebhookHandler
)
from linebot.v3.exceptions import (
    InvalidSignatureError
)
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage,
    AudioMessage
    
)
from linebot.v3.webhooks import (
    MessageEvent,
    AudioMessageContent,
)

from openai import OpenAI

load_dotenv()
API_KEY = os.getenv("API_KEY")
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
CHANNEL_SECRET = os.getenv("CHANNEL_SECRET")

app = Flask(__name__)

configuration = Configuration(access_token=ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)


@app.route("/callback", methods=['POST'])
def callback():
    # get X-Line-Signature header value
    signature = request.headers['X-Line-Signature']

    # get request body as text
    body = request.get_data(as_text=True)
    print(body)
    print('------------------')
    app.logger.info("Request body: " + body)

    # handle webhook body
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        app.logger.info("Invalid signature. Please check your channel access token/channel secret.")
        abort(400)

    return 'OK'

def get_message_contents(message_id):
    endpoint = f"https://api-data.line.me/v2/bot/message/{message_id}/content"
    headers = {
        "Authorization": "Bearer " + ACCESS_TOKEN 
        }
    res = requests.get(endpoint, headers=headers)
    return res

def audio_save(binary, filename):
    with open(filename, "wb") as f:
        f.write(binary)
    return None

def audio_to_text(audio_filename,client):
    with open(audio_filename, "rb") as audio_file:
        transcript = client.audio.transcriptions.create(
            model="whisper-1", 
            file=audio_file,
            language='ja'
            )
        audio_text = transcript.text
        print(audio_text)
        return audio_text

@handler.add(MessageEvent, message=AudioMessageContent)
def handle_message(event):
    print('------------------')
    print(event)

    res = get_message_contents(event.message.id)
    message_content = res.content

    audio_format = "m4a"
    audio_filename = f"audio_{event.message.id}.{audio_format}"

    audio_save(message_content, audio_filename)

    client = OpenAI(api_key=API_KEY)
    audio_text = audio_to_text(audio_filename,client)

    system_prompt = """あなたは、日記を書くプロです。入力を受け取って、文章を校正し、日記のように書き直してください。"""
    messages_for_gpt = []
    messages_for_gpt.append({"role": "system", "content": system_prompt})
    messages_for_gpt.append({"role": "user", "content": audio_text})
    
    gpt_model = "gpt-3.5-turbo"
    response = client.chat.completions.create(
                        model = gpt_model,
                        messages = messages_for_gpt,
                        temperature=0,
                    )
    
    reply_message = response.choices[0].message.content
    print(reply_message)

    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message_with_http_info(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=reply_message)]
            )
        )



if __name__ == "__main__":
    app.run()