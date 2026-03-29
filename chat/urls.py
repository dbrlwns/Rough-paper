from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='chat_index'),
    path('<slug:room_slug>/', views.room, name='chat_room'),
]
