import json
from channels.generic.websocket import AsyncWebsocketConsumer
# Django ORM은 기본이 동기 방식이므로 아래 패키지로 비동기 환경으로 변환
from channels.db import database_sync_to_async
from .models import Room, Message

# 외부 연결과 입출력이 많아 비동기 사용
# 각 유저마다 ChatConsumer 생성되어 동작
class ChatConsumer(AsyncWebsocketConsumer):
    # Websocket은 request대신 self.scope에 연결 정보가 담기고,
        # self.channel_name으로 연결을 식별함.

    async def connect(self):
        self.room_slug = self.scope['url_route']['kwargs']['room_slug'] #routing.py의 변수
        self.room_group_name = f'chat_{self.room_slug}'

        # 채널 그룹에 참가 (요청자를 그룹에 추가, 그룹 없을 시 생성)
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        await self.accept() # websocket 연결 최종수락 (3-way 핸쉐)

    async def disconnect(self, close_code):
        # 채널 그룹에서 퇴장
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
        # self.close_code 로 연결 끊긴 이유를 확인할 수 있음.

    async def receive(self, text_data):
        # loads() : Json 문자열을 파이썬 딕셔너리로 변환
        data = json.loads(text_data)
        message = data['message']
        author = data['author']

        # DB에 메시지 저장
        await self.save_message(author, message)

        # 그룹 내 모든 클라이언트에게 메시지 전송
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message', # 이벤트를 처리할 메서드 이름을 지정
                'message': message,
                'author': author,
            }
        )

    async def chat_message(self, event):
        # 각 클라이언트에게 WebSocket으로 전달
        await self.send(text_data=json.dumps({
            # dumps() : 파이썬 딕셔너리를 json 문자열로 변환 {'a':'b'} -> '{'a':'b'}'
            # websocket은 문자열만 주고받을 수 있어서 변환이 필수임.
            'message': event['message'],
            'author': event['author'],
        }))

    @database_sync_to_async # 동기 ORM 명령을 비동기 환경에서 실행가능
    def save_message(self, author, content):
        room = Room.objects.get(slug=self.room_slug)
        Message.objects.create(room=room, author=author, content=content)


"""
Django Channels Layer : Consumer 사이에서 메시지를 주고받는 통로

channel : Consumer 하나하나에 부여되는 고유 ID
사용자가 Websocket로 접속할 때, Consumer에 고유의 channel_name을 자동으로 부여

connect() - 사용자가 접속 시 그룹에 추가
receive() - 메시지를 그룹 전체에 전송
disconnect() - 사용자 탈주시 그룹서 제거

추가 : NotificationConsumer을 사용해 알림 기능을 추가할 수 있음. 별도의 urlpattern을 가지며,
    2개의 websocket이 1명의 사용자와 연결이 됨.
"""