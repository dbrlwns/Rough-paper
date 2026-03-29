from django.urls import re_path # 정규식 사용해 URL 매칭
from . import consumers
# HTTP가 urls.py를 사용한다면, websocket에서는 routing.py를 사용함.

websocket_urlpatterns = [ # asgi.py에서 사용
    re_path(r'ws/chat/(?P<room_slug>\w+)/$',
            consumers.ChatConsumer.as_asgi()),
]
"""
r'...' : raw string으로 백슬래시를 특수문자없이 그대로 사용
(?P<room_slug>\\w+) : url에서 해당부분을 room_slug 변수로 저장
\\w+ : 영문자, 숫자, _을 1개 이상 허용

ex:
ws/chat/general/ -> room_slug = "general"
ws/chat/한글/ -> error 

URL 매칭 시 ChatConsumer로 연결 (이때 room_slug 변수도 함께 전송)
"""
