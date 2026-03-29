from django.shortcuts import render, get_object_or_404
from .models import Room


def index(request):
    rooms = Room.objects.all()
    return render(request, 'chat/index.html', {'rooms': rooms})


def room(request, room_slug):
    room = get_object_or_404(Room, slug=room_slug)
    messages = room.messages.all()
    return render(request, 'chat/room.html', {'room': room, 'messages': messages})
