from django.db import models
from django.contrib.auth.hashers import make_password, check_password
from django.db import transaction

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
    manual_score_override = models.FloatField(null=True, blank=True)  # NEW

    def get_delay_score(self):
        if self.manual_score_override is not None:
            return self.manual_score_override
        if not self.completed or not self.completed_on or not self.deadline:
            return None

        if self.completed_on <= self.deadline.date():
            return 10

        days_late = (self.completed_on - self.deadline.date()).days
        return max(0, 10 - (days_late * 0.5))
    def update_score_if_needed(self):
        if self.trello_member_id:
            try:
                member = TrelloMember.objects.get(trello_member_id=self.trello_member_id)
                # ✅ Always allow scoring if manual override is given and not counted yet
                if not self.score_counted or (self.manual_score_override is not None):
                    member.update_score_for_single_task(self)
            except TrelloMember.DoesNotExist:
                pass



    def save(self, *args, **kwargs):
        previous_manual_override = None
        previous_score_counted = False

        if self.pk:
            previous_task = Task.objects.get(pk=self.pk)
            previous_manual_override = previous_task.manual_score_override
            previous_score_counted = previous_task.score_counted

        is_being_completed = self.completed and self.completed_on and not self.score_counted
        override_changed = self.manual_score_override is not None and (
            self.manual_score_override != previous_manual_override or not previous_score_counted
        )

        super().save(*args, **kwargs)

        if is_being_completed or override_changed:
            self.update_score_if_needed()




class TrelloMember(models.Model):
    trello_member_id = models.CharField(max_length=255, unique=True)
    email = models.EmailField()
    name = models.CharField(max_length=100, null=True, blank=True)
    historical_score = models.FloatField(null=True, blank=True)  # allow None
    total_tasks_counted = models.PositiveIntegerField(default=0)



    def update_score_for_single_task(self, task):
        score = task.get_delay_score()
        if score is None:
            return

        with transaction.atomic():
            if self.historical_score is None:
                self.historical_score = score
                self.total_tasks_counted = 1
            else:
                combined_total_score = (self.historical_score * self.total_tasks_counted) + score
                self.total_tasks_counted += 1
                self.historical_score = round(combined_total_score / self.total_tasks_counted, 2)

            self.save()

            # Avoid triggering update_score_if_needed again
            Task.objects.filter(pk=task.pk).update(score_counted=True)




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