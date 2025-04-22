# views.py
from django.shortcuts import render
from django.http import JsonResponse
from django.utils import timezone
from datetime import timedelta
from background_task.models import Task as BgTask
from .tasks import create_trello_webhook, sync_trello_tasks, check_tasks, assigned_task, task_completion, after_deadline, summarize_yesterday_and_email_boss
from .models import Task
import requests
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
import logging


# Schedule it to run every day at 8 AM
from django.utils.timezone import now

from django.utils.dateparse import parse_datetime


from django.shortcuts import render, redirect
from .forms import TrelloTaskForm
from .trello_utils import get_board_members, create_or_update_card, delete_card

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

    assigned_task()

    task_completion()

    return JsonResponse({"message": "Trello sync triggered!"})



run_time = now().replace(hour=20, minute=24, second=0, microsecond=0)
logger.info("hello")
if not BgTask.objects.filter(task_name="home.tasks.summarize_yesterday_and_email_boss").exists():
    logger.info("Scheduling summarize_yesterday_and_email_boss: at every 8th hour")
    logger.info("....")
    logger.info("....")
    logger.info("....")
    logger.info("....")
    after_deadline(schedule=90, repeat=90)

    summarize_yesterday_and_email_boss(schedule=run_time)



# Schedule `check_tasks()` only if not already running
if not BgTask.objects.filter(task_name="home.tasks.check_tasks").exists():
    logger.info("Scheduling check_tasks(): for every 60 seconds")
    check_tasks(schedule=60, repeat=60)


if not BgTask.objects.filter(task_name="home.tasks.after_deadline").exists():
    logger.info("Scheduling after_deadline(): for every 60 seconds")
    after_deadline(schedule=90, repeat=90)




# Helper to fetch one card
def get_trello_card(card_id):
    url = f"{settings.TRELLO_API_URL}/cards/{card_id}"
    params = {'key': settings.TRELLO_API_KEY, 'token': settings.TRELLO_API_TOKEN}
    response = requests.get(url, params=params)
    if response.status_code == 200:
        return response.json()
    return None


def assign_trello_task(request, card_id=None):
    members_data = get_board_members()
    member_choices = [(member['id'], member['fullName']) for member in members_data]

    initial_data = {}

    if card_id and request.method == 'GET':
        card = get_trello_card(card_id)
        if card:
            initial_data = {
                'title': card['name'],
                'description': card['desc'],
                'deadline': parse_datetime(card['due']) if card.get('due') else None,
                'members': card.get('idMembers', [])
            }

    if request.method == 'POST':
        form = TrelloTaskForm(request.POST)
        form.fields['members'].choices = member_choices
        if form.is_valid():
            data = form.cleaned_data
            card = create_or_update_card(
                card_id=card_id,
                name=data['title'],
                desc=data['description'],
                due=data['deadline'].isoformat() if data['deadline'] else None,
                member_ids=data['members']
            )
            return redirect('assign_trello_task')  # You may want to pass card_id for edit redirect
    else:
        form = TrelloTaskForm(initial=initial_data)
        form.fields['members'].choices = member_choices

    return render(request, 'assign_trello_task.html', {'form': form})


def task_list(request):
    tasks = Task.objects.all()
    return render(request, 'task_list.html', {'tasks': tasks})


def delete_trello_task(request, card_id):
    if request.method == 'POST':
        delete_card(card_id)
    return redirect('task_list')



