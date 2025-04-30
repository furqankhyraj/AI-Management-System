# admin.py
from django.contrib import admin
from .models import Task, TrelloMember

admin.site.register(Task)
admin.site.register(TrelloMember)