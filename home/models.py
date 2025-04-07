# models.py
from django.db import models
from django.contrib.auth.models import User


class TrelloProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    trello_id = models.CharField(max_length=64, unique=True)


class Task(models.Model):
    title = models.CharField(max_length=255)
    description = models.TextField()
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    deadline = models.DateTimeField()
    completed = models.BooleanField(default=False)
    trello_card_id = models.CharField(max_length=255, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)