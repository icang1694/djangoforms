from django.shortcuts import render, redirect
import time

# Create your views here.
from django.http import HttpResponse
from polls.forms import DataForm, EditDataForm, DeleteDataForm
import os
import json
import requests
import google.oauth2.id_token
import google.auth.transport.requests
from formtools.wizard.views import SessionWizardView
from datetime import datetime
from itertools import compress
from dateutil.parser import parse,isoparse
import re
import google.auth
from google.cloud import scheduler_v1
from google.cloud.scheduler_v1 import HttpTarget,OidcToken
from google.cloud import storage
from google.oauth2 import service_account
import json
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from .models import Post, DataEmail
from google.protobuf import duration_pb2, field_mask_pb2
from django.http import HttpResponse
from django.urls import reverse_lazy
from django.utils import timezone as djangotimezone
import sys
import os.path
from collections import defaultdict
from email.parser import Parser
from bs4 import BeautifulSoup
import aspose.email as ae
from aspose.email import MailMessage, SaveOptions, HtmlFormatOptions
import os
from dotenv import load_dotenv

load_dotenv()

sapath = os.getenv('sapath')
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = sapath
requestgcp = google.auth.transport.requests.Request()
audience = os.getenv('audience')
TOKEN = google.oauth2.id_token.fetch_id_token(requestgcp, audience)


class HomeView(ListView):
  model = DataEmail
  template_name = 'home.html'

  def updatestatus(request):
    client,projectid = get_cloud_scheduler_client(sapath)
    sch_list = DataEmail.objects.all()
    for obj in sch_list:
      if obj.scheduler is not None:
        updatesch = get_job_status(client,projectid,obj.scheduler,location='asia-southeast2')
      # obj = sch.save(commit=False)
        obj.schedulestatus = str(updatesch.state)
        if updatesch.last_attempt_time is not None:     
          obj.schedulelast = updatesch.last_attempt_time
        if updatesch.schedule_time is not None:
          obj.schedulenext = updatesch.schedule_time
        obj.save()
      print('success update')
    return redirect("/polls")
  
  def pauseschjob(request,pk):
    print('inside pausejob')
    client,projectid = get_cloud_scheduler_client(sapath)
    olddata = DataEmail.objects.get(id=pk)
    pause_schjob(client,projectid,olddata.scheduler,location='asia-southeast2')
    return redirect("/polls")

  def resumeschjob(request,pk):
    print('inside resumejob')
    client,projectid = get_cloud_scheduler_client(sapath)
    olddata = DataEmail.objects.get(id=pk)
    resume_schjob(client,projectid,olddata.scheduler,location='asia-southeast2')
    return redirect("/polls")

  def runschjob(request,pk):
    print('inside runjob')
    client,projectid = get_cloud_scheduler_client(sapath)
    olddata = DataEmail.objects.get(id=pk)
    run_schjob(client,projectid,olddata.scheduler,location='asia-southeast2')
    return redirect("/polls")

class ArticleView(DetailView):
  model = DataEmail
  template_name = 'index.html'
  fields = '__all__'
  def get_form(self):
    form = self.form_class(instance=self.object)
    return form

  def get_context_data(self, **kwargs):
    context = super(ArticleView, self).get_context_data(**kwargs)
    context
    return context

class AddPostView(CreateView):
  model = DataEmail
  template_name = 'addpost.html'

class UpdatePostView(UpdateView):
  model = DataEmail
  form_class = EditDataForm
  template_name='edit.html'
  # fields = '__all__'

  # def checkemail(request, pk):
  #   return render(request, "email/index.html")

  def post(self,request, pk):
    context ={}
    form = EditDataForm(request.POST or None)
    context['form']= form

    bucket_name='xlemail'
    if 'check' in request.POST:
      print('ada check!')
      context = updaterequest(request,pk,'check')
      blobname = context['response'][1][2:-2]
      destination_file_name = str(os.getenv('temppath')) + str(blobname.split('/')[-1])
      downloadfromgcs(sapath,bucket_name,blobname,destination_file_name)
      saveto = os.getenv('saveto')
      parseemltohtml(destination_file_name,saveto)
      att = parseattachment(destination_file_name, 'tempattach/')
      if len(att)>0:
        addattachmenttohtml(saveto,saveto,att)
      return render(request, 'checkemail.html', context)
    elif 'submit' in request.POST:
      print('ada submit')
      context = updaterequest(request,pk,'submit')
    elif 'update' in request.POST:
      print('ada update')
      context = updaterequest(request,pk,'update')
    # context['form']= form
    return render(request, "edit.html", context)
  # fields = '__all__'

def updaterequest(request, pk, typerequest):
  context ={}
  form = EditDataForm(request.POST or None)
  print(form.data)
  if form.is_valid():
      jsondata = json.loads(form.data['items'])
      print(jsondata)
      retlis,datalis = mixmatch(jsondata['bodyhtml'],jsondata)
      jsonfinal = makejsonemaildata(jsondata,datalis,retlis,jsondata['bodyhtml'],typerequest)
      
      olddata = DataEmail.objects.get(id=pk)
      olddata.items = jsondata

      print(jsonfinal)
      if typerequest == 'update':
        olddata.save()
      else:
        if len(jsondata['schjobid'])>0:
          client,projectid = get_cloud_scheduler_client(sapath)
          jobid = jsondata['schjobid']
          schedule = makecron(jsondata)
          timezone = jsondata['schtimezone']
          description = jsondata['schdescription']
          try:
            job = update_job(client, projectid, jobid, schedule, jsonfinal, description, timezone, location='asia-southeast2')
            context['data']=job
            olddata.save()

          except Exception as e:
            print('Failed')
            print(e)
            context['data']=e
        elif len(jsondata['schjobid'])==0:
          try:
            r = requests.post(
                    audience, 
                    headers={'Authorization': f"Bearer {TOKEN}", "Content-Type": "application/json"},
                    data=json.dumps(jsonfinal)  # possible request parameters
                )
            if r.status_code==200:
              context['response']=r.status_code, r.text
              obj = olddata.save(commit=False)
              obj.schedulelast = djangotimezone.now()
              obj.save()
              print('saved in database')
              print(r.status_code, r.text)
            else:
              context['response']=r.status_code, r.text
          except Exception as e:
            print('Failed')
            print(e)
          context['data']=jsonfinal
  else:
      print("form is not valid!")
      print(form.errors.as_json())
      form = EditDataForm()
  context['form']= form
  return context

class DeletePostView(DeleteView):
  model = DataEmail
  template_name = 'delete_post.html'
  success_url=reverse_lazy('home')

  def deleteschjob(request, pk):
    print('inside deletejob')
    client,projectid = get_cloud_scheduler_client(sapath)
    olddata = DataEmail.objects.get(id=pk)
    delete_schjob(client,projectid,olddata.scheduler,location='asia-southeast2')
    olddata.delete()
    print('success delete job from cloud scheduler')
    return redirect("/polls")
  

def process_form_data(form_list):
    temp_data = []
    form_data_json = []
    for x in form_list:
        dicttemp = x.cleaned_data['items']
        temp_data.append(dicttemp)

    for y in temp_data[1]:
        y.update(temp_data[0])
        form_data_json.append(y)
        
    print(form_data_json)
    # form_data= json.dumps(form_data_json)
    return form_data_json

def indexdata(request):
    context = {}
    form = DataForm(request.POST or None)
    context['form']= form
    bucket_name='xlemail'
    
    if 'check' in request.POST:
      print('ada check!')
      context = sendrequest(request,'check')
      print("CONTEXT")
      print(context)
      print("CONTEXT RESPONSE")
      print(context['response'][1])
      blobname = context['response'][1][2:-2]
      print("BLOBNAME")
      print(type(blobname))
      print(blobname)
      destination_file_name = str(os.getenv('temppath'))+ str(blobname.split('/')[-1])
      print("DESTINATION FILE NAME")
      print(destination_file_name)
      downloadfromgcs(sapath,bucket_name,blobname,destination_file_name)
      saveto = os.getenv('saveto')
      parseemltohtml(destination_file_name,saveto)
      att = parseattachment(destination_file_name, 'tempattach/')
      if len(att)>0:
        addattachmenttohtml(saveto,saveto,att)
      return render(request, 'checkemail.html', context)
    elif 'submit' in request.POST:
      print('ada submit')
      context = sendrequest(request,'submit')
    
    return render(request, "index.html", context)

def sendrequest(request, typerequest):
  context ={}
  form = DataForm(request.POST or None)
  print(form.data)
  if form.is_valid():
      jsondata = json.loads(form.data['items'])
      print(jsondata)
      retlis,datalis = mixmatch(jsondata['bodyhtml'],jsondata)
      jsonfinal = makejsonemaildata(jsondata,datalis,retlis,jsondata['bodyhtml'],typerequest)
      print(jsonfinal)

      if len(jsondata['schjobid'])>0:
        client,projectid = get_cloud_scheduler_client(sapath)
        jobid = jsondata['schjobid']
        schedule = makecron(jsondata)
        timezone = jsondata['schtimezone']
        description = jsondata['schdescription']
        try:
          output=create_job(client, projectid, jobid, schedule, jsonfinal, timezone, description, location='asia-southeast2')
          print('Success')
          print(output)
          checkjob = get_job_status(client,projectid,jobid,location='asia-southeast2')
          obj = form.save(commit=False)
          obj.scheduler = str(jobid)
          obj.schedulestatus = checkjob.state
          if checkjob.last_attempt_time is not None:     
            obj.schedulelast = checkjob.last_attempt_time
          if checkjob.schedule_time is not None:
            obj.schedulenext = checkjob.schedule_time
          obj.save()
          context['data']=output

        except Exception as e:
          print('Failed')
          print(e)
          context['data']=e
      elif len(jsondata['schjobid'])==0:
        try:
          r = requests.post(
                  audience, 
                  headers={'Authorization': f"Bearer {TOKEN}", "Content-Type": "application/json"},
                  data=json.dumps(jsonfinal)  # possible request parameters
          )
          if r.status_code==200:
            context['response']=r.status_code, r.text
            obj = form.save(commit=False)
            obj.schedulelast = djangotimezone.now()
            obj.save()
            print('saved in database')
            print(r.status_code, r.text)
          else:
            context['response']=r.status_code, r.text
            print('TESTING')
            print(context['response'][1])
        except Exception as e:
          print('Failed')
          print(e)
        context['data']=jsonfinal
  else:
      print("form is not valid!")
      print(form.errors.as_json())
      form = DataForm()
      
  context['form']= form
  return context

def checkschedule(request):
  context ={}
  client,project = get_cloud_scheduler_client(sapath)
  getlist = get_job_list(client, project, region='asia-southheast1')
  context['job']=getlist
  return render(request, "index.html", context)

def checkdataset(dname,query):
  a = []
  for y in query['dataset']:
    if y['dataset_name']==dname:
      a = y
    else:
      pass
  return a

def checktblname(name,data):
  a = []
  for y in data:
      if y['table_name']==name:
        a = y
      else:
        pass
  return a

def checkchartname(name,data):
  a = []
  for y in data:
    if y['chart_name']==name:
      a = y
    else:
      pass
  return a

def is_date(string):
    try: 
        isoparse(string)
        return True
    except ValueError:
        return False

def extractdate(a,timespec):
  asp = a.split(" ")
  asp2 = list(map(lambda item: (item.replace("'","")), asp))
  result = map(is_date,asp2 )
  lis = list(compress(asp, list(result)))
  my_list = list(map(lambda item: (item.replace("'","")), lis))
  my_list.sort(key = lambda date: datetime.strptime(date, '%Y-%m-%d')) 
  my_list = list(map(lambda item: datetime.strptime(item, '%Y-%m-%d'),my_list))

  if timespec == 'day':
    
    my_list = [str(date.strftime('%Y'))+'-'+str(date.strftime('%m'))+'-'+str(date.strftime('%d')) for date in my_list]
    
  elif timespec == 'month':
    my_list = [str(date.strftime('%Y'))+'-'+str(date.strftime('%m')) for date in my_list]
  
  elif timespec == 'year':
    my_list = [str(date.strftime('%Y')) for date in my_list]
  else:
    my_list = ['please specify the time correctly "Tanggal(datasetname,day/month/year)"']

  return my_list

def makestringfromlis(lis):
  a = ""
  lis.sort()
  for x in lis:
    a = a + str(x) + " "
  return a


def getparenthesis(x):
      a = x[x.find("(")+1:x.find(")")].split(",")
      return a
      
def mixmatch(input,inputjson):
  regex = r"\{(.*?)\}"
  matches = re.finditer(regex, input, re.MULTILINE | re.DOTALL)
  lishttp = []
  for matchNum, match in enumerate(matches):
      for groupNum in range(0, len(match.groups())):
          lishttp.append(match.group(0))
  retlis = {}
  datalis = []

  for x in lishttp:
      e = {}
      if  'recepient' in x:
        retlis[x]='{{recepient}}'

      elif 'table(' in x:
        dsetname = getparenthesis(x)
        tbljsontemp = inputjson['preprocess_data']['Table']
        tbljson= checktblname(str(dsetname[0]),tbljsontemp)
        print(inputjson)
        print(type(inputjson))
        tbldset = checkdataset(tbljson['dataset_name'],inputjson)
        e['serve_type'] = 'table'
        e['dataset_name'] = tbljson['dataset_name']
        e['table_name'] = tbljson['table_name']
        e['preprocess_show_column_'] = tbljson['show_column']
        e['ref_column'] = tbldset['col_ref']
        if len(dsetname)==1:
          retlis[x]=" Table Data: \n"+"{{"+"table_"+str(dsetname[0])+"}}"
        else:
          retlis[x]=str(dsetname[1])+"\n"+"{{"+"table_"+str(dsetname[0])+str(dsetname[1].replace(" ",""))+"}}"
          e['title'] = str(dsetname[1])
        datalis.append(e)

      elif 'image(' in x:
        listem=[]
        for k,v in inputjson['preprocess_data'].items():
          for z in v:
            z['typee']=k
            listem.append(z)
        print(listem)
        bar = []
        linechart = []
        pie = []
        scatter = []
        for i in listem:
          if i['typee'] =='Bar Chart':
            bar.append(i)
          elif i['typee'] == 'Line Chart':
            linechart.append(i)
          elif i['typee'] =='Pie_chart':
            pie.append(i)
          elif i['typee'] == 'Scatter_Plot':
            scatter.append(i) 
        dsetname = getparenthesis(x)
        if len(bar) > 0: #ada bar chart
          pltjsontemp = bar
          pltjson = checkchartname(str(dsetname[0]),pltjsontemp)
          if len(pltjson) > 0: #nama chart ditemukan
            pltdset = checkdataset(pltjson['dataset_name'],inputjson)
            e['serve_type'] = 'image'
            e['preprocess_plot_type'] = 'barchart'
            e['dataset_name'] = pltjson['dataset_name']
            e['chart_name'] = pltjson['chart_name']
            e['preprocess_query'] = pltjson['query']
            e['preprocess_stacked_cluster'] = pltjson['stacked_cluster']
            e['preprocess_line'] = pltjson['line']
            e['preprocess_x_axis'] = pltjson['x_axis']
            e['preprocess_y_axis'] = pltjson['y_axis']
            e['preprocess_legend_position'] = pltjson['legend_position']
            e['preprocess_plot_title'] = pltjson['plot_title']
            e['ref_column'] = pltdset['col_ref']
            e['title'] = str(dsetname[1])
            datalis.append(e)
          else:
            pass
        else:
          pass
        if len(linechart) > 0:
          pltjsontemp = linechart
          pltjson = checkchartname(str(dsetname[0]),pltjsontemp)
          if len(pltjson) > 0: #nama chart ditemukan
            pltdset = checkdataset(pltjson['dataset_name'],inputjson)
            e['serve_type'] = 'image'
            e['preprocess_plot_type'] = 'linechart'
            e['dataset_name'] = pltjson['dataset_name']
            e['chart_name'] = pltjson['chart_name']
            e['preprocess_query'] = pltjson['query']
            e['preprocess_x_axis'] = pltjson['x_axis']
            e['preprocess_y_axis'] = pltjson['y_axis']
            e['preprocess_legend_position'] = pltjson['legend_position']
            e['preprocess_plot_title'] = pltjson['plot_title']
            e['ref_column'] = pltdset['col_ref']
            e['title'] = str(dsetname[1])
            datalis.append(e)
          else:
            pass
        else:
          pass
        if len(pie) > 0:
          pltjsontemp = pie
          pltjson = checkchartname(str(dsetname[0]),pltjsontemp)
          if len(pltjson) > 0: #nama chart ditemukan
            pltdset = checkdataset(pltjson['dataset_name'],inputjson)
            e['serve_type'] = 'image'
            e['dataset_name'] = pltjson['dataset_name']
            e['chart_name'] = pltjson['chart_name']
            e['preprocess_query'] = pltjson['query']
            e['preprocess_plot_type'] = 'pie'
            e['preprocess_y_axis'] = pltjson['slices value']
            e['preprocess_x_axis'] = pltjson['slices partition']
            e['preprocess_plot_title'] = pltjson['plot_title']
            e['preprocess_plot_label'] = pltjson['label']
            e['preprocess_legend_position'] = pltjson['legend_position']
            e['ref_column'] = pltdset['col_ref']
            e['title'] = str(dsetname[1])
            datalis.append(e)
          else:
            pass
        else:
          pass
        if len(scatter) > 0:
          pltjsontemp = scatter
          pltjson = checkchartname(str(dsetname[0]),pltjsontemp)
          if len(pltjson) > 0: #nama chart ditemukan
            pltdset = checkdataset(pltjson['dataset_name'],inputjson)
            e['serve_type'] = 'image'
            e['dataset_name'] = pltjson['dataset_name']
            e['chart_name'] = pltjson['chart_name']
            e['preprocess_query'] = pltjson['query']
            e['ref_column'] = pltdset['col_ref']
            e['preprocess_plot_type'] = 'scatter'
            e['preprocess_x_axis'] = pltjson['x_axis']
            e['preprocess_y_axis'] = pltjson['y_axis']
            e['preprocess_plot_title'] = pltjson['plot_title']
            e['preprocess_hue'] = pltjson['circle_color_wheel']
            e['preprocess_z'] = pltjson['z_axis']
            e['preprocess_size'] = pltjson['circle_size']
            e['preprocess_legend_position'] = pltjson['legend_position']
            e['title'] = str(dsetname[1])
            datalis.append(e)
          else:
            pass
        else:
          pass 
        if len(dsetname)==1:
          retlis[x]=" Plot Data: \n"+"{{"+"image_"+str(dsetname[0])+"}}"
        else:
          retlis[x]=str(dsetname[1])+"\n"+"{{"+"image_"+str(dsetname[0])+str(dsetname[1].replace(" ",""))+"}}"
          e['title'] = str(dsetname[1])
        #datalis.append(e)
        print(datalis)
  return retlis, datalis

def changematchtohtml(input,html):
  a = html
  for key,value in input.items():
    a = a.replace(key,value)
  k = a.split('\n')
  htmljadi = ""
  for x in k:
    htmljadi = htmljadi + "<p style='font-size:20px' >"+str(x)+"</p>"
  return htmljadi

def addbaru(item,inputjson):
  item["serve_type"]="attachment"
  item["attachment_name"]=item["attachment_name"].replace("{recepient}","{{recepient}}")
  tbldset = checkdataset(item['dataset_name'],inputjson)
  item['ref_column'] = tbldset['col_ref']
  # item["ref_column"]="receiver_id"
  return item

def addtbl(item):
   item["serve_type"]="table"
   return item

def changematch(input,html):
  a = html
  for key,value in input.items():
    a = a.replace(key,value)
  return a

def makejsonemaildata(jsonbaru,datalis,retlis,html,typerequest):
  retlist_a,datalis2 = mixmatch(jsonbaru['subject'],jsonbaru)
  subject_ready = changematch(retlist_a,jsonbaru['subject'])
  attachlist = [addbaru(item,jsonbaru) for item in jsonbaru['attachment']]
  # tbllist = [addtbl(item) for item in jsonbaru['preprocess_data'][0]['Table']]
  datalis.extend(attachlist)
  # datalis.extend(datalis2)
  b = {"data":datalis}
  baru = {
      "type": "email_data",
      "typerequest": typerequest,
      "sender": jsonbaru['sender'],
      "receiver": jsonbaru['receiver'],
      "receiver_table" : jsonbaru['receiver_table'],
      "cc": jsonbaru['cc'],
      "bcc": jsonbaru['bcc'],
      "subject": subject_ready,
      "bodyhtml": changematchtohtml(retlis,html)
  }
  baru.update(b)
  if len(jsonbaru['dataset'])>0:
    a = {"type":"dataset",
        "queries": jsonbaru['dataset']
        }
    retjson = [a,baru]
  else:
    retjson = [baru]
  return retjson

def get_cloud_scheduler_client(sa_credential_filepath):
    credentials, project_id = google.auth.load_credentials_from_file(sa_credential_filepath)
    client = scheduler_v1.CloudSchedulerClient(credentials=credentials)
    return client, project_id


def get_job_list(cs_client, project_id, region='asia-southheast1'):
    request = scheduler_v1.ListJobsRequest(parent = f"projects/{project_id}/locations/{region}")
    page_result = cs_client.list_jobs(request=request)
    return [r.name for r in page_result]


def create_job(cs_client, project_id, job_id, schedule, bodyreq, timezone, description, location='asia-southeast2'):
    # parent= cs_client.location_path(project_id, location)
    if len(timezone)==0:
      timezone='Asia/Jakarta'
    parent = f'projects/{project_id}/locations/{location}'
    job_name = f'projects/{project_id}/locations/{location}/jobs/{job_id}'
    ht = HttpTarget(
        http_method = "POST",
        uri         = os.getenv('audience'),
        headers     = {"Content-Type": "application/json"},
        # body        = base64.b64decode("{\"foo\":\"bar\"}")
        body        = json.dumps(bodyreq).encode("utf-8"),
        oidc_token  = OidcToken(service_account_email=os.getenv('service_account_email'))
    )
    job_dict = {
        'name': f'projects/{project_id}/locations/{location}/jobs/{job_id}',
        'http_target': ht,
        'schedule': schedule,
        'time_zone': timezone,
        'description': description
    }
    job = cs_client.create_job(parent=parent, job=job_dict)

    return job

def update_job(cs_client, project_id, job_id, schedule, bodyreq, timezone, description, location='asia-southeast2'):
    # parent= cs_client.location_path(project_id, location)
    if len(timezone)==0:
      timezone='Asia/Jakarta'
    parent = f'projects/{project_id}/locations/{location}'
    job_name = f'projects/{project_id}/locations/{location}/jobs/{job_id}'
    # ht = HttpTarget(
    #     http_method = "POST",
    #     uri         = "https://asia-southeast2-celerates-playground-318603.cloudfunctions.net/xl_email_ready",
    #     headers     = {"Content-Type": "application/json"},
    #     # body        = base64.b64decode("{\"foo\":\"bar\"}")
    #     body        = json.dumps(bodyreq).encode("utf-8"),
    #     oidc_token  = OidcToken(service_account_email="querytobq@celerates-playground-318603.iam.gserviceaccount.com")
    # )
    # job_dict = {
    #     'http_target': ht,
    #     'schedule': schedule,
    #     'time_zone': timezone,
    #     'description': description
    # }
    # job = cs_client.create_job(parent=parent, job=job_dict)
    ht = scheduler_v1.HttpTarget()
    ht.http_method = "POST"
    ht.uri = os.getenv('audience')
    ht.headers = {"Content-Type": "application/json"}
    ht.body = json.dumps(bodyreq).encode("utf-8")
    ht.oidc_token = OidcToken(service_account_email=os.getenv('service_account_email'))
    jobedit = scheduler_v1.Job()
    jobedit.name = job_name
    jobedit.http_target = ht
    jobedit.schedule = schedule
    jobedit.description = description
    jobedit.time_zone = timezone
    update_mask = field_mask_pb2.FieldMask(paths=['http_target','schedule','time_zone','description'])
    request = scheduler_v1.UpdateJobRequest(
          job=jobedit,
          update_mask=update_mask
      )
    response = cs_client.update_job(request=request)
    return response

def makecron(jsonbaru):
  if len(jsonbaru['Custom'])>0:
    cronsch = jsonbaru['Custom']
  else:
    if len(jsonbaru['Daily']['time'])>0:
      timearr = jsonbaru['Daily']['time'].split(":")
      time = ' '.join([timearr[1],timearr[0]])
    else:
      time = ' '.join(['00','00'])
    if len(jsonbaru['Monthly'])>0:
      daymonth = jsonbaru['Monthly']
    else:
      daymonth = "*"
    if len(jsonbaru['Yearly'])>0:
      monthyear = ','.join(map(str,jsonbaru['Yearly']))
    else:
      monthyear = "*"
    if len(jsonbaru['Weekly'])>0:
      dayweek = ','.join(map(str,jsonbaru['Weekly']))
    else:
      dayweek = "*"
    cronsch=" ".join([time,daymonth,monthyear,dayweek])
  return cronsch

def get_job_status(client,project_id,jobname,location='asia-southeast2'):
    path = f"projects/{project_id}/locations/{location}/jobs/{jobname}"
    # Initialize request argument(s)
    request = scheduler_v1.GetJobRequest(
       name=path
    )
    # Make the request
    response = client.get_job(request=request)
    return response

def delete_schjob(client,project_id,jobname,location='asia-southeast2'):
    path = f"projects/{project_id}/locations/{location}/jobs/{jobname}"
    try:
      request = scheduler_v1.DeleteJobRequest(
          name=path,
      )
      print(path)
      client.delete_job(request=request)
    except Exception as e:
      return e

def pause_schjob(client,project_id,jobname,location='asia-southeast2'):
    path = f"projects/{project_id}/locations/{location}/jobs/{jobname}"
    request = scheduler_v1.PauseJobRequest(
        name=path,
    )
    client.pause_job(request=request)

def resume_schjob(client,project_id,jobname,location='asia-southeast2'):
    path = f"projects/{project_id}/locations/{location}/jobs/{jobname}"
    request = scheduler_v1.ResumeJobRequest(
        name=path,
    )
    client.resume_job(request=request)

def run_schjob(client,project_id,jobname,location='asia-southeast2'):
    path = f"projects/{project_id}/locations/{location}/jobs/{jobname}"
    request = scheduler_v1.RunJobRequest(
        name=path,
    )
    client.run_job(request=request)

def connectgcs(keypath):
    credentials = service_account.Credentials.from_service_account_file(
            keypath, scopes=["https://www.googleapis.com/auth/devstorage.full_control"],
        )
    # client = storage.Client(credentials=credentials, project=projectid)
    projectid = str(credentials.project_id)
    print("Success connecting to Cloud Storage On",projectid)
    os.environ["GOOGLE_CLOUD_PROJECT"] = projectid
    return credentials,projectid

def downloadfromgcs(keypath,bucket_name,source_blob_name,destination_file_name):
    gcscred,project = connectgcs(keypath)
    gcsclient = storage.Client(project, credentials=gcscred)
    bucket = gcsclient.bucket(bucket_name)
    blob = bucket.blob(source_blob_name)
    blob.download_to_filename(destination_file_name)
    return f'Downloaded storage object {source_blob_name} from bucket {bucket_name} to local file {destination_file_name}.'

def parse_message(filename):
    with open(filename) as f:
        return Parser().parse(f)

def find_attachments(message):
    """
    Return a tuple of parsed content-disposition dict, message object
    for each attachment found.
    """
    found = []
    for part in message.walk():
        if 'content-disposition' not in part:
            continue
        cdisp = part['content-disposition'].split(';')
        cdisp = [x.strip() for x in cdisp]
        if cdisp[0].lower() != 'attachment':
            continue
        parsed = {}
        for kv in cdisp[1:]:
            key, val = kv.split('=')
            if val.startswith('"'):
                val = val.strip('"')
            elif val.startswith("'"):
                val = val.strip("'")
            parsed[key] = val
        found.append((parsed, part))
    return found

def parseattachment(eml_filename, output_dir):
    attachlist = ''
    msg = parse_message(eml_filename)
    subject = eml_filename.split('/')[-1]
    attachments = find_attachments(msg)
    print ("Found {0} attachments...".format(len(attachments)))
    if not os.path.isdir(output_dir):
        os.mkdir(output_dir)
    for cdisp, part in attachments:
        cdisp_filename = os.path.normpath(cdisp['filename'])
        # prevent malicious crap
        if os.path.isabs(cdisp_filename):
            cdisp_filename = os.path.basename(cdisp_filename)
        cdisp_filename = str(subject)+'-'+str(cdisp_filename)
        towrite = os.path.join(output_dir, cdisp_filename)
        attachlist += f'<a href="{towrite}" download>{cdisp_filename}</a>\n'
        print( "Writing " + towrite)
        with open(towrite, 'wb') as fp:
            data = part.get_payload(decode=True)
            fp.write(data)
    return attachlist

def addattachmenttohtml(inputhtml,outputhtml,attachmentlink):
  with open(inputhtml, 'r') as f:

      contents = f.read()

      soup = BeautifulSoup(contents, 'lxml')
      soup.body.append(BeautifulSoup(attachmentlink, 'html.parser'))
      print(soup.html)

  with open(outputhtml, "w", encoding = 'utf-8') as file:
      
      # prettify the soup object and convert it into a string
      file.write(str(soup.prettify()))

def parseemltohtml(pathtoeml,saveto):
  # Load EML message
  eml = MailMessage.load(pathtoeml)

  # Set SaveOptions
  options = SaveOptions.default_html
  options.embed_resources = False
  options.html_format_options = HtmlFormatOptions.WRITE_HEADER | HtmlFormatOptions.WRITE_COMPLETE_EMAIL_ADDRESS
  # options.HtmlFormatOptions = HtmlFormatOptions.WRITE_HEADER | HtmlFormatOptions.WRITE_COMPLETE_EMAIL_ADDRESS #save the message headers to output HTML using the formatting options

  # Convert EML to HTML
  eml.save(saveto, options)
  return f'eml {pathtoeml} parsed to html {saveto}'


