from django import forms
from django.urls import reverse_lazy,reverse
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit
from polls.models import DataEmail

class DataForm(forms.ModelForm):
    class Meta:
        model = DataEmail
        fields = ['items']
    helper = FormHelper()
    helper.add_input(Submit('submit', 'Submit', css_class='btn-primary'))
    helper.add_input(Submit('check', 'Check', css_class='btn-primary'))
    helper.form_method = 'POST'

class EditDataForm(forms.ModelForm):
    class Meta:
        model = DataEmail
        fields = ['items']
    helper = FormHelper()
    helper.add_input(Submit('update', 'Update', css_class='btn-primary'))
    helper.add_input(Submit('submit', 'Submit', css_class='btn-primary'))
    helper.add_input(Submit('check', 'Check', css_class='btn-primary'))
    helper.form_method = 'POST'

class DeleteDataForm(forms.ModelForm):
    class Meta:
        model = DataEmail
        fields = ['items']
    helper = FormHelper()
    helper.add_input(Submit('delete', 'DELETE', css_class='btn-danger'))
    helper.form_method = 'POST'
