from django.contrib import admin

from chat.models import Room, Message


# Register your models here.
@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    pass

@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    pass