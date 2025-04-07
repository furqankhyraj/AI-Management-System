# views.py
from django.shortcuts import render
from django.http import JsonResponse
from django.utils import timezone
from background_task.models import Task as BgTask
from .tasks import create_trello_webhook, sync_trello_tasks, check_tasks
from .models import Task
import requests
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def task_list(request):
    tasks = Task.objects.all()
    return render(request, 'task_list.html', {'tasks': tasks})


@csrf_exempt
def trello_webhook(request):

    logger.info("Webhook received: %s", request.body)
    if request.method == "HEAD":
        return JsonResponse({"message": "Webhook registered!"})

    # Ensure Trello Webhook is registered (Call only if needed)
    trello_webhooks = requests.get(
        f"https://api.trello.com/1/tokens/{settings.TRELLO_API_TOKEN}/webhooks",
        params={"key": settings.TRELLO_API_KEY},
    ).json()

    existing_webhook = any(
        wh.get("callbackURL") == "https://your-django-app.com/trello-webhook/"
        for wh in trello_webhooks
    )

    if not existing_webhook:
        create_trello_webhook()  # Register only if it doesn’t exist

    # Sync Trello tasks immediately when webhook triggers
    sync_trello_tasks()

    return JsonResponse({"message": "Trello sync triggered!"})

# Schedule `check_tasks()` only if not already running
if not BgTask.objects.filter(task_name="home.tasks.check_tasks").exists():
    logger.info("Scheduling check_tasks(): for every 60 seconds")
    check_tasks(schedule=60, repeat=60)
