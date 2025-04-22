from django import forms

class TrelloTaskForm(forms.Form):
    title = forms.CharField(max_length=255)
    description = forms.CharField(widget=forms.Textarea, required=False)
    deadline = forms.DateTimeField(widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}), required=False)
    members = forms.MultipleChoiceField(widget=forms.CheckboxSelectMultiple)
