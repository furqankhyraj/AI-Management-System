# admin.py
from django.contrib import admin
from .models import Task, TrelloMember, detail_of_everyday

admin.site.register(Task)
admin.site.register(TrelloMember)
admin.site.register(detail_of_everyday)