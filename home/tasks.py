# tasks.py
from background_task import background
from openai import OpenAI
import requests
from django.core.mail import send_mail
from django.utils import timezone
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from .models import Task, TrelloProfile
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


client = OpenAI(api_key=settings.OPENAI_API_KEY)

TRELLO_API_URL = 'https://api.trello.com/1'

# Generate AI email content
def generate_email_content(task, recipient, is_boss=False):
    role = 'boss' if is_boss else 'employee'
    prompt = f'Write a professional email to {role} about the overdue task: {task.title}. '
    prompt += f'Task details: {task.description}. Deadline was {task.deadline}. '
    if is_boss:
        prompt += f'Employee {task.trello_member_id.username} has not completed the task.'
    else:
        prompt += 'Please complete the task as soon as possible.'

    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are a helpful project manager assistant."},
            {"role": "user", "content": prompt}
        ],
        max_tokens=150
    )

    return response.choices[0].message.content.strip()


# Fetch tasks from Trello (Only triggered by webhook)
def sync_trello_tasks():
    logger.info("Starting sync_trello_tasks...")
    response = requests.get(
        f"{TRELLO_API_URL}/boards/{settings.TRELLO_BOARD_ID}/cards",
        params={"key": settings.TRELLO_API_KEY, "token": settings.TRELLO_API_TOKEN},
    )

    if response.status_code == 200:
        trello_cards = response.json()
        trello_card_ids = {card["id"] for card in trello_cards}

        for card in trello_cards:
            task, created = Task.objects.get_or_create(trello_card_id=card['id'], defaults={
                'title': card['name'],
                'description': card.get('desc', ''),
                'deadline': timezone.now() + timezone.timedelta(days=1),  # Example deadline
                'completed': False
            })

            # 🔥 Fetch assigned members
            if 'idMembers' in card and card['idMembers']:
                trello_id = card['idMembers'][0]
                try:
                    profile = TrelloProfile.objects.get(trello_id=trello_id)
                    task.assigned_to = profile.user
                except TrelloProfile.DoesNotExist:
                    task.assigned_to = None  # or skip assigning
                task.save()


            if not created:
                task.title = card['name']
                task.description = card.get('desc', '')
                task.save()

        # Delete tasks that no longer exist in Trello
        deleted_tasks = Task.objects.exclude(trello_card_id__in=trello_card_ids)
        deleted_tasks_count = deleted_tasks.count()
        deleted_tasks.delete()
        logger.info(f"Deleted {deleted_tasks_count} tasks that no longer exist in Trello")
    else:
        logger.error(f"Trello API error: {response.status_code} - {response.text}")

# Check overdue tasks and send notifications (Runs every 60s)
def check_tasks_():
    logger.info("Running check_tasks()...")
    overdue_tasks = Task.objects.filter(completed=False, deadline__lt=timezone.now())
    for task in overdue_tasks:
        if task.assigned_to:
            # Email to employee
            employee_email_content = generate_email_content(task, task.assigned_to)
            send_mail(
                f'Task Overdue: {task.title}',
                employee_email_content,
                settings.EMAIL_HOST_USER,
                [task.assigned_to.email],
                fail_silently=False,
            )
            
            # Notify boss
            boss_email_content = generate_email_content(task, 'boss', is_boss=True)
            send_mail(
                f'Employee Task Overdue: {task.title}',
                boss_email_content,
                settings.EMAIL_HOST_USER,
                ['muhdmehdi89@gmail.com.com'],
                fail_silently=False,
            )

# Register a Trello Webhook
def create_trello_webhook():
    url = "https://api.trello.com/1/webhooks"
    data = {
        "key": settings.TRELLO_API_KEY,
        "token": settings.TRELLO_API_TOKEN,
        "callbackURL": "https://your-django-app.com/trello-webhook/",
        "idModel": settings.TRELLO_BOARD_ID
    }
    response = requests.post(url, data=data)
    return response.json()

@background(schedule=60)
def check_tasks():
    logger.info("........")
    check_tasks_()
