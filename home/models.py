from django.db import models
from django.contrib.auth.hashers import make_password, check_password

class Task(models.Model):
    title = models.CharField(max_length=255)
    email_sent = models.BooleanField(default=False)
    email_sent_2 = models.BooleanField(default=False)
    email_sent_3 = models.BooleanField(default=False)
    description = models.TextField()
    trello_member_id = models.CharField(max_length=255, null=True, blank=True)
    user_name = models.CharField(max_length=255, null=True, blank=True)
    full_name = models.CharField(max_length=255, null=True, blank=True)
    deadline = models.DateTimeField(null=True, blank=True)
    completed = models.BooleanField(default=False)
    completed_on = models.DateField(null=True, blank=True)
    trello_card_id = models.CharField(max_length=255, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    score_counted = models.BooleanField(default=False)

    def get_delay_score(self):
        if not self.completed or not self.completed_on or not self.deadline:
            return None

        if self.completed_on <= self.deadline.date():
            return 10

        days_late = (self.completed_on - self.deadline.date()).days
        return max(0, 10 - (days_late * 0.5))
    def update_score_if_needed(self):
        if self.completed and self.completed_on and not self.score_counted and self.trello_member_id:
            try:
                member = TrelloMember.objects.get(trello_member_id=self.trello_member_id)
                member.update_score_with_new_tasks()
            except TrelloMember.DoesNotExist:
                pass

    def save(self, *args, **kwargs):
        is_being_completed = self.completed and self.completed_on and not self.score_counted
        super().save(*args, **kwargs)  # Save the Task first
        if is_being_completed:
            self.update_score_if_needed()


class TrelloMember(models.Model):
    trello_member_id = models.CharField(max_length=255, unique=True)
    email = models.EmailField()
    name = models.CharField(max_length=100, null=True, blank=True)
    historical_score = models.FloatField(null=True, blank=True)  # allow None
    total_tasks_counted = models.PositiveIntegerField(default=0)

    def update_score_with_new_tasks(self):
        new_tasks = Task.objects.filter(
            trello_member_id=self.trello_member_id,
            completed=True
        ).exclude(id__in=self.get_task_ids_already_counted())

        if not new_tasks.exists():
            return

        new_score_total = sum(task.get_delay_score() for task in new_tasks)
        new_task_count = new_tasks.count()

        if new_task_count == 0:
            return

        if self.historical_score is None:
            # First time scoring
            self.historical_score = round(new_score_total / new_task_count, 2)
            self.total_tasks_counted = new_task_count
        else:
            # Update running average
            combined_total_score = (self.historical_score * self.total_tasks_counted) + new_score_total
            combined_total_tasks = self.total_tasks_counted + new_task_count
            self.historical_score = round(combined_total_score / combined_total_tasks, 2)
            self.total_tasks_counted = combined_total_tasks

        self.save()

        for task in new_tasks:
            task.score_counted = True
            task.save()


    def get_task_ids_already_counted(self):
        return Task.objects.filter(
            trello_member_id=self.trello_member_id,
            score_counted=True
        ).values_list('id', flat=True)
    
class detail_of_everyday(models.Model):
    date = models.DateField()
    description = models.TextField()


    def __str__(self):
        return f"Details for {self.date}"


class Boss(models.Model):
    username = models.CharField(max_length=150, unique=True)
    password = models.CharField(max_length=128)  # store hashed password

    def set_password(self, raw_password):
        self.password = make_password(raw_password)
        self.save()

    def check_password(self, raw_password):
        return check_password(raw_password, self.password)

    def __str__(self):
        return self.username