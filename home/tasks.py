# tasks.py
from background_task import background
from openai import OpenAI
import requests
from django.core.mail import send_mail
from django.utils import timezone
from django.conf import settings
from .models import Task, TrelloMember
from django.contrib.auth.models import User
from django.utils.dateparse import parse_datetime
import logging
from django.utils.timezone import localtime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)





def parse_trello_datetime(due_str):
    if due_str:
        dt = parse_datetime(due_str)
        if dt:
            return timezone.make_aware(dt) if timezone.is_naive(dt) else dt
    return None



client = OpenAI(api_key=settings.OPENAI_API_KEY)

TRELLO_API_URL = 'https://api.trello.com/1'

# Generate AI email content
def generate_email_content(task, recipient, is_boss=False):
    role = 'boss' if is_boss else 'employee'
    prompt = f'Write a professional email to {role} about the overdue task, which title is: {task.title}. '
    prompt += f'Task details: {task.description}. Deadline was {task.deadline}. '
    if is_boss:
        prompt += f'write in short/summarized form, to the boss name: "Furqan", that Employee {task.user_name} has not completed the task.'
    else:
        prompt += f'write in short/summarized form, to the employee name: "{task.full_name}", to Please complete the task as soon as possible and also tell your task scoring will also go down as you do more delay in task completion'

    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are a helpful management assistant, and you name is 'Douze-bot'."},
            {"role": "user", "content": prompt}
        ],
        max_tokens=280
    )

    return response.choices[0].message.content.strip()



# Generate AI email content
def generate_email_content_4(task, recipient, is_boss=False):
     
    role = 'boss' if is_boss else 'employee'
    prompt = f'Write a professional email to {role} about the overdue task, which title is: {task.title}. '
    overdue_duration = timezone.now() - task.deadline
    days_overdue = overdue_duration.days
    hours_overdue = overdue_duration.seconds // 3600

    prompt += f'Task details: {task.description}. Deadline was {task.deadline} and is already overdue by {days_overdue} days and {hours_overdue} hours.'
    if is_boss:
        prompt += f'write in short/summarized form, to the boss name: "Furqan", that Employee {task.user_name} has not completed the task.'
    else:
        prompt += f'write in short/summarized form, to the employee name: "{task.full_name}", to Please complete the task as soon as possible and also tell your task scoring will also go down as you do more delay in task completion.'

    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are a helpful management assistant, and you name is 'Douze-bot'."},
            {"role": "user", "content": prompt}
        ],
        max_tokens=280
    )

    return response.choices[0].message.content.strip()



def generate_email_content_2(task, recipient, is_boss=False):
    role = 'boss' if is_boss else 'employee'
    prompt = f'Write a professional email to {role} that the task is assigned which title is: {task.title}. '
    prompt += f'Task details: {task.description}. Deadline is {task.deadline}. '
    if is_boss:
        prompt += f'write in short/summarized form, to the boss name: "Furqan", that Employee {task.user_name} get a new assigned task.'
    else:
        prompt += f'write in short/summarized form, to the employee name: "{task.full_name}", about the task.'

    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are a helpful management assistant, and you name is 'Douze-bot'."},
            {"role": "user", "content": prompt}
        ],
        max_tokens=280
    )

    return response.choices[0].message.content.strip()


def generate_email_content_3(task, recipient):
    prompt = f'Write a professional email to a boss that the task is completed which title is: {task.title}. '
    prompt += f'Task details: {task.description}. Deadline was {task.deadline}. '
    
    prompt += f'write in short/summarized form, to the boss name: "Furqan", that Employee {task.user_name} has completed its task.'

    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are a helpful management assistant, and you name is 'Douze-bot'."},
            {"role": "user", "content": prompt}
        ],
        max_tokens=280
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
                'deadline': parse_trello_datetime(card.get('due')) if card.get('due') else None,  # Example deadline
                'completed': False
            })
            
            # 🔁 Update task details
            task.title = card['name']
            task.description = card.get('desc', '')
            task.deadline = parse_trello_datetime(card.get('due')) if card.get('due') else None
            

            # ✅ Check if card is in "Done" list
            list_id = card.get('idList')
            if list_id:
                list_response = requests.get(
                    f"{TRELLO_API_URL}/lists/{list_id}",
                    params={"key": settings.TRELLO_API_KEY, "token": settings.TRELLO_API_TOKEN},
                )
                if list_response.status_code == 200:
                    list_data = list_response.json()
                    is_done = list_data['name'].lower() == "done"
                    
                    if is_done and not task.completed:
                        # Task just completed — set completed_on to today
                        task.completed = True
                        task.completed_on = timezone.now().date()
                    elif not is_done:
                        # Moved out of "Done" list — reset completed status
                        task.completed = False
                        task.completed_on = None
                else:
                    logger.warning(f"Failed to get list info for list_id: {list_id}")


            if 'idMembers' in card and card['idMembers']:
                trello_member_id = card['idMembers'][0]
                logger.info(f"Assigning Trello member with ID: {trello_member_id} to task: {task.title}")

                # Fetch full member details
                member_response = requests.get(
                    f"{TRELLO_API_URL}/members/{trello_member_id}",
                    params={"key": settings.TRELLO_API_KEY, "token": settings.TRELLO_API_TOKEN},
                )

                if member_response.status_code == 200:
                    logger.info(f"Fetched member info for ID: {trello_member_id}")
                    member_data = member_response.json()
                    task.trello_member_id = trello_member_id
                    task.full_name = member_data.get("fullName", "")
                    task.user_name = member_data.get("username", "")

                else:
                    logger.warning(f"Failed to get member info for member_id: {trello_member_id}")
                    task.trello_member_id = trello_member_id  # still assign ID
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



def check_tasks_():
    logger.info("Running check_tasks()...")
    logger.info(f"Local time: {localtime(timezone.now())}")
    for task in Task.objects.all():
        logger.info(f"{task.title} - Deadline: {task.deadline}")
    overdue_tasks = Task.objects.filter(completed=False, deadline__lt=timezone.now(), email_sent=False)
    logger.info(f"Found {overdue_tasks.count()} overdue tasks")  # <-- Add this line
    for task in overdue_tasks:
        # Fetch employee email based on trello_member_id
        if task.trello_member_id:
            try:
                trello_member = TrelloMember.objects.get(trello_member_id=task.trello_member_id)
                email = 'muhammad.mehdi@douzetech.com'
                
                # Send email to the member
                employee_email_content = generate_email_content(task, 'boss', is_boss=False)
                send_mail(
                    f'Task Overdue: {task.title}',
                    employee_email_content,
                    settings.EMAIL_HOST_USER,
                    [email],
                    fail_silently=False,
                )
            except TrelloMember.DoesNotExist:
                logger.error(f"No email found for trello_member_id: {task.trello_member_id}")
                # Handle case where the member's email is not registered

            # Notify boss
            boss_email_content = generate_email_content(task, 'boss', is_boss=True)
            send_mail(
                f'Employee Task Overdue: {task.title}',
                boss_email_content,
                settings.EMAIL_HOST_USER,
                ['muhdmehdi89@gmail.com'],  # You can replace this with the actual boss's email
                fail_silently=False,
            )
            task.email_sent = True
            task.save()
            logger.info(f"Marked email_sent=True for task: {task.title}")



def after_deadline_():
    logger.info("Checking for tasks past deadline + 1 day...")
    
    # Tasks that are not completed and deadline was more than 1 day ago
    deadline_crossed = Task.objects.filter(
        completed=False,
        deadline__lt=timezone.now() - timezone.timedelta(days=1)
    )

    logger.info(f"Found {deadline_crossed.count()} overdue tasks")

    for task in deadline_crossed:
        logger.warning(f"Task '{task.title}' assigned to {task.user_name} is overdue by more than 1 day!")
        if task.trello_member_id:
            try:
                trello_member = TrelloMember.objects.get(trello_member_id=task.trello_member_id)
                email = 'muhammad.mehdi@douzetech.com'
                
                # Send email to the member
                employee_email_content = generate_email_content_4(task, 'boss', is_boss=False)
                send_mail(
                    f'Task Overdue: {task.title}',
                    employee_email_content,
                    settings.EMAIL_HOST_USER,
                    [email],
                    fail_silently=False,
                )
            except TrelloMember.DoesNotExist:
                logger.error(f"No email found for trello_member_id: {task.trello_member_id}")
                # Handle case where the member's email is not registered

            # Notify boss
            boss_email_content = generate_email_content_4(task, 'boss', is_boss=True)
            send_mail(
                f'Employee Task Overdue: {task.title}',
                boss_email_content,
                settings.EMAIL_HOST_USER,
                ['muhdmehdi89@gmail.com'],  # You can replace this with the actual boss's email
                fail_silently=False,
            )
            logger.info(f"Mail sent")



def assigned_task():
    logger.info("After webhook triggered")
    new_tasks = Task.objects.filter(completed=False, email_sent_2=False)
    for task in new_tasks:
        # Fetch employee email based on trello_member_id
        if task.trello_member_id:
            try:
                trello_member = TrelloMember.objects.get(trello_member_id=task.trello_member_id)
                email = 'muhammad.mehdi@douzetech.com'
                
                # Send email to the member
                employee_email_content = generate_email_content_2(task, 'boss', is_boss=False)
                send_mail(
                    f'Assigned task : {task.title}',
                    employee_email_content,
                    settings.EMAIL_HOST_USER,
                    [email],
                    fail_silently=False,
                )
            except TrelloMember.DoesNotExist:
                logger.error(f"No email found for trello_member_id: {task.trello_member_id}")
                # Handle case where the member's email is not registered

            # Notify boss
            boss_email_content = generate_email_content_2(task, 'boss', is_boss=True)
            send_mail(
                f'Task assigned to employee : {task.title}',
                boss_email_content,
                settings.EMAIL_HOST_USER,
                ['muhdmehdi89@gmail.com'],  # You can replace this with the actual boss's email
                fail_silently=False,
            )
            task.email_sent_2 = True
            task.save()
            logger.info(f"Marked email_sent=True for task: {task.title}")





def task_completion():
    logger.info("After webhook triggered")
    completed_tasks = Task.objects.filter(completed=True, email_sent_3=False)
    for task in completed_tasks:
        # Fetch employee email based on trello_member_id
        if task.trello_member_id:
            boss_email_content = generate_email_content_3(task, 'boss')
            send_mail(
                f'Task is completed : {task.title}',
                boss_email_content,
                settings.EMAIL_HOST_USER,
                ['muhdmehdi89@gmail.com'],  # You can replace this with the actual boss's email
                fail_silently=False,
            )
            task.email_sent_3= True
            task.save()
            logger.info(f"Marked email_sent=True for task: {task.title}")


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

@background(schedule=90)
def after_deadline():
    logger.info("Scheduling after_deadline()...")
    after_deadline_()



@background(schedule=60)
def summarize_yesterday_and_email_boss():
    logger.info("Running summarize_yesterday_and_email_boss...")

    # Get yesterday's date in YYYY-MM-DD format
    yesterday = (timezone.now() - timezone.timedelta(days=1)).date().isoformat()
    api_url = f"https://douzebook-api-seven.vercel.app/get-user-update-by-date?date={yesterday}"

    try:
        response = requests.get(api_url)
        response.raise_for_status()
        updates = response.json()
    except Exception as e:
        logger.error(f"Failed to fetch update data: {e}")
        return

    # Prepare GPT prompt
    prompt = f"Summarize the following work updates for the boss Furqan from {yesterday}:\n\n{updates}"

    try:
        gpt_response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful assistant who summarizes daily work for a boss."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=400
        )

        summary = gpt_response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"Failed to generate summary with GPT: {e}")
        return

    # Email it to boss
    try:
        send_mail(
            subject=f"Daily Work Summary for {yesterday}",
            message=summary,
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=['muhdmehdi89@gmail.com'],  # replace if needed
            fail_silently=False,
        )
        logger.info("Successfully sent daily summary to the boss.")
    except Exception as e:
        logger.error(f"Failed to send summary email: {e}")




