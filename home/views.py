# views.py
from django.shortcuts import render
from django.http import JsonResponse, Http404
from django.utils import timezone
from datetime import timedelta, datetime
from background_task.models import Task as BgTask
from .tasks import create_trello_webhook, sync_trello_tasks, check_tasks, assigned_task, task_completion, after_deadline, summarize_yesterday_
from .models import Task, detail_of_everyday, Boss, TrelloMember
import requests
from django.views.decorators.csrf import csrf_exempt, csrf_protect
from django.views.decorators.http import require_POST, require_GET
from django.conf import settings
import logging
import secrets
from dateutil.relativedelta import relativedelta  # requires python-dateutil

import json
from openai import OpenAI
from django.utils.dateparse import parse_datetime

# Schedule it to run every day at 8 AM


from django.shortcuts import render, redirect
from .trello_utils import get_board_members, create_or_update_card, delete_card


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

client = OpenAI(api_key=settings.OPENAI_API_KEY)


def members_list_api(request):
    members = get_board_members()
    members_list = [{'id': m['id'], 'fullName': m['fullName']} for m in members]
    return JsonResponse({'members': members_list})


def task_list(request):
    tasks = Task.objects.all()
    return render(request, 'task_list.html', {'tasks': tasks})

def task_list_api(request):
    tasks = Task.objects.all().values('title', 'deadline', 'trello_card_id', 'completed', 'full_name')
    return JsonResponse({'tasks': list(tasks)})

@csrf_exempt
@require_POST
def chatbot_api(request):
    try:
        body = json.loads(request.body)
        user_question = body.get('question')

        if not user_question:
            return JsonResponse({'error': 'Question not provided.'}, status=400)

        # Fetch tasks and summaries
        tasks = list(Task.objects.all().values('title', 'deadline', 'trello_card_id','description','completed', 'created_at', 'updated_at', 'trello_member_id','full_name', 'completed_on'))[-10:]
        summaries = list(detail_of_everyday.objects.all().values_list('description', flat=True))[-7:]
        details = list(TrelloMember.objects.all().values('trello_member_id', 'email', 'historical_score', 'name', 'total_tasks_counted'))


        # Prepare system content
        system_context = (
            f"Here are some details of tasks:\n{json.dumps(tasks, indent=2, default=str)}\n\n"
            f"And here are recent summaries:\n{json.dumps(summaries, indent=2)}"
            f"Other details:\n{json.dumps(details, indent=2)}"
        )

        # OpenAI GPT-3.5 Turbo call
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_context},
                {"role": "user", "content": user_question}
            ]
        )
        
        answer = response.choices[0].message.content.strip()

        return JsonResponse({'answer': answer})

    except Exception as e:
        logger.exception("Error in chatbot_api")
        return JsonResponse({'error': str(e)}, status=500)
'''
def get_summary_after_seven():
    return list(detail_of_everyday.objects.all().values_list('description', flat=True))[:7]

'''

@csrf_exempt
@require_POST
def login_view(request):
    data = json.loads(request.body)
    username = data.get('username')
    password = data.get('password')

    # Find the Boss instance by username
    try:
        boss = Boss.objects.get(username=username)
    except Boss.DoesNotExist:
        return JsonResponse({"error": "Invalid credentials"}, status=401)

    # Check if the password is correct
    if boss.check_password(password):  # Check using the check_password method
        token = secrets.token_urlsafe(32)
        response = JsonResponse({"message": "Login successful"})
        response.set_cookie("session_token", token, httponly=True)
        return response
    else:
        return JsonResponse({"error": "Invalid credentials"}, status=401)

@require_GET
def logout_view(request):
    response = JsonResponse({"message": "Logged out"})
    response.delete_cookie("session_token", path='/')
    return response


@csrf_exempt
def delete_trello_task_api(request, card_id):
    if request.method == 'DELETE':
        try:
            delete_card(card_id)  # Delete from Trello
            Task.objects.filter(trello_card_id=card_id).delete()  # Delete from DB
            return JsonResponse({'message': 'Task deleted successfully'})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    return JsonResponse({'error': 'Invalid method'}, status=405)

def get_task_by_card_id(request, card_id):
    try:
        task = Task.objects.get(trello_card_id=card_id)
        return JsonResponse({
            'title': task.title,
            'deadline': task.deadline.isoformat() if task.deadline else None,
            'trello_card_id': task.trello_card_id
        })
    except Task.DoesNotExist:
        raise Http404("Task not found")



@csrf_exempt
def update_task(request, card_id):
    if request.method == 'PUT':
        try:
            task = Task.objects.get(trello_card_id=card_id)
            data = json.loads(request.body)
            task.title = data.get('title', task.title)
            deadline_str = data.get('deadline')
            if deadline_str:
                task.deadline = parse_datetime(deadline_str)
            task.completed = data.get('completed', task.completed)
            task.trello_member_id = data.get('trello_member_id', task.trello_member_id)
            manual_score_override = data.get('manual_score_override')
            if manual_score_override is not None:
                task.manual_score_override = float(manual_score_override)

            
            task.save()
            create_or_update_card(
                card_id=card_id,
                name=task.title,
                desc=task.description,
                due=task.deadline.isoformat() if task.deadline else None,
                member_ids=[task.trello_member_id] if task.trello_member_id else [],
                completed=task.completed,
            )
            return JsonResponse({'status': 'updated'})
        except Task.DoesNotExist:
            return JsonResponse({'error': 'Task not found'}, status=404)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    return JsonResponse({'error': 'Invalid method'}, status=405)


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



# run_time = (now() + timedelta(days=1)).replace(hour=12, minute=38, second=0, microsecond=0)



# summarize_yesterday_(schedule=10, repeat=24*60*60)



# # Schedule `check_tasks()` only if not already running
# if not BgTask.objects.filter(task_name="home.tasks.check_tasks").exists():
#     logger.info("Scheduling check_tasks(): for every 60 seconds")
#     check_tasks(schedule=0, repeat=60)


# if not BgTask.objects.filter(task_name="home.tasks.after_deadline").exists():
#     logger.info("Scheduling after_deadline(): for every 60 seconds")
#     after_deadline(schedule=90, repeat=90)


# Helper to fetch one card
def get_trello_card(card_id):
    url = f"{settings.TRELLO_API_URL}/cards/{card_id}"
    params = {'key': settings.TRELLO_API_KEY, 'token': settings.TRELLO_API_TOKEN}
    response = requests.get(url, params=params)
    if response.status_code == 200:
        return response.json()
    return None


@csrf_exempt
def assign_trello_task(request, card_id=None):
    if request.method == 'POST':
        try:
            # Parse the JSON body
            data = json.loads(request.body)
            
            # Extract fields
            title = data.get('title')
            description = data.get('description')
            members = data.get('members', [])
            deadline = data.get('deadline')
            completed = data.get('completed', False)  

            if not deadline:
                default_deadline = datetime.utcnow() + relativedelta(months=1)
                deadline = default_deadline.isoformat() + "Z" # Trello expects ISO with Zulu time


            card = create_or_update_card(
                card_id=card_id,
                name=title,
                desc=description,
                due=deadline,
                member_ids=members,
                completed=completed  
            )



            return JsonResponse({'message': 'Task assigned successfully!'})

        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    
    else:
        return JsonResponse({'error': 'Only POST method allowed'}, status=405)

def task_list(request):
    tasks = Task.objects.all()
    return render(request, 'task_list.html', {'tasks': tasks})


def delete_trello_task(request, card_id):
    if request.method == 'POST':
        delete_card(card_id)
    return redirect('task_list')



