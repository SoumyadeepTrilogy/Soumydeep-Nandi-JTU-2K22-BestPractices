# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from decimal import Decimal
import urllib.request
from datetime import datetime

import logging
logger=logging.getlogger(__name__)
logger.setLevel(logging.DEBUG)

formatter=logging.Formatter('%(asctime)s:%(levelname)s:%(message)s')

file_handler=logging.FileHandler('views.log')
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(formatter)

logger.addHandler(file_handler)

from django.http import HttpResponse
from django.contrib.auth.models import User

# Create your views here.
from rest_framework.permissions import AllowAny
from rest_framework.decorators import *
from rest_framework.viewsets import ModelViewSet
from rest_framework.response import Response
from rest_framework import status

from restapi.models import *
from restapi.serializers import *
from restapi.custom_exception import *



def index(_request)->HttpResponse:
    ''' 
        Returns Hello,world. You're at Rest Statement 
    '''
    return HttpResponse("Hello, world. You're at Rest.")


@api_view(['POST'])
def logout(request) -> Response:
    ''' 
        Deletes Authetication Token 
    '''
    request.user.auth_token.delete()
    logger.info("User Authentication Token deleted successfully")
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(['GET'])
def balance(request) -> Response:
    '''
        Used to get final balances
    '''
    logger.info("Final balance request initiated")
    user = request.user
    expenses = Expenses.objects.filter(users__in=user.expenses.all())
    final_balance = {}
    for expense in expenses:
        expense_balances = normalize(expense)
        for eb in expense_balances:
            from_user = eb['from_user']
            to_user = eb['to_user']
            if from_user == user.id:
                final_balance[to_user] = final_balance.get(to_user, 0) - eb['amount']
            if to_user == user.id:
                final_balance[from_user] = final_balance.get(from_user, 0) + eb['amount']
    final_balance = {k: v for k, v in final_balance.items() if v != 0}

    response = [{"user": k, "amount": int(v)} for k, v in final_balance.items()]
    logger.info("Final balance calculated and executed successfully")
    return Response(response, status=200)


def normalize(expense):
    '''
        Normalizes Expenses
    '''
    logger.info("Normalization of expense initiated")
    user_balances = expense.users.all()
    dues = {}
    for user_balance in user_balances:
        dues[user_balance.user] = dues.get(user_balance.user, 0) + user_balance.amount_lent \
                                  - user_balance.amount_owed
    dues = [(k, v) for k, v in sorted(dues.items(), key=lambda item: item[1])]
    start = 0
    end = len(dues) - 1
    balances = []
    while start < end:
        amount = min(abs(dues[start][1]), abs(dues[end][1]))
        user_balance = {"from_user": dues[start][0].id, "to_user": dues[end][0].id, "amount": amount}
        balances.append(user_balance)
        dues[start] = (dues[start][0], dues[start][1] + amount)
        dues[end] = (dues[end][0], dues[end][1] - amount)
        if dues[start][1] == 0:
            start += 1
        else:
            end -= 1
    logger.info("Normalization of expense executed")
    return balances


class user_view_set(ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = (AllowAny,)


class category_view_set(ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    http_method_names = ['get', 'post']


class group_view_set(ModelViewSet):
    queryset = Groups.objects.all()
    serializer_class = GroupSerializer

    def get_queryset(self):
        '''
            Gets Queryset of Users
        '''
        logger,info("get_queryset function initiated")
        user = self.request.user
        groups = user.members.all()
        if self.request.query_params.get('q', None) is not None:
            groups = groups.filter(name__icontains=self.request.query_params.get('q', None))
        logger,info("get_queryset function executed")
        return groups

    def create(self, request, *args, **kwargs)b -> Response:
        '''
            Adds user to a group
        '''
        logger.info("Creation of group initiated")
        user = self.request.user
        data = self.request.data
        group = Groups(**data)
        group.save()
        group.members.add(user)
        serializer = self.get_serializer(group)
        logger.info("Creation of group and addition of users to it executed")
        return Response(serializer.data, status=201)

    @action(methods=['put'], detail=True)
    def members(self, request, pk=None) -> Response:
        '''
            Adding members to a group
        '''
        logger.info("members function initiated")
        group = Groups.objects.get(id=pk)
        if group not in self.get_queryset():
            raise UnauthorizedUserException()
        body = request.data
        if body.get('add', None) is not None and body['add'].get('user_ids', None) is not None:
            added_ids = body['add']['user_ids']
            for user_id in added_ids:
                group.members.add(user_id)
        if body.get('remove', None) is not None and body['remove'].get('user_ids', None) is not None:
            removed_ids = body['remove']['user_ids']
            for user_id in removed_ids:
                group.members.remove(user_id)
        group.save()
        logger.info("logger function executed")
        return Response(status=204)

    @action(methods=['get'], detail=True)
    def expenses(self, _request, pk=None) -> Response:
        '''
            Group Expenses Returned
        '''
        logger.info("expenses function initiated")
        group = Groups.objects.get(id=pk)
        if group not in self.get_queryset():
            raise UnauthorizedUserException()
        expenses = group.expenses_set
        serializer = ExpensesSerializer(expenses, many=True)
        logger.info("expenses function executed")
        return Response(serializer.data, status=200)

    @action(methods=['get'], detail=True)
    def balances(self, _request, pk=None) -> Response:
        '''
            Returns balance
        '''
        logger.info("balance function initiated")
        group = Groups.objects.get(id=pk)
        if group not in self.get_queryset():
            raise UnauthorizedUserException()
        expenses = Expenses.objects.filter(group=group)
        dues = {}
        for expense in expenses:
            user_balances = UserExpense.objects.filter(expense=expense)
            for user_balance in user_balances:
                dues[user_balance.user] = dues.get(user_balance.user, 0) + user_balance.amount_lent \
                                          - user_balance.amount_owed
        dues = [(k, v) for k, v in sorted(dues.items(), key=lambda item: item[1])]
        start = 0
        end = len(dues) - 1
        balances = []
        while start < end:
            amount = min(abs(dues[start][1]), abs(dues[end][1]))
            amount = Decimal(amount).quantize(Decimal(10)**-2)
            user_balance = {"from_user": dues[start][0].id, "to_user": dues[end][0].id, "amount": str(amount)}
            balances.append(user_balance)
            dues[start] = (dues[start][0], dues[start][1] + amount)
            dues[end] = (dues[end][0], dues[end][1] - amount)
            if dues[start][1] == 0:
                start += 1
            else:
                end -= 1
        logger.info("balance function executed")
        return Response(balances, status=200)


class expenses_view_set(ModelViewSet):
    queryset = Expenses.objects.all()
    serializer_class = ExpensesSerializer

    def get_queryset(self):
        user = self.request.user
        if self.request.query_params.get('q', None) is not None:
            expenses = Expenses.objects.filter(users__in=user.expenses.all())\
                .filter(description__icontains=self.request.query_params.get('q', None))
        else:
            expenses = Expenses.objects.filter(users__in=user.expenses.all())
        return expenses

@api_view(['post'])
@authentication_classes([])
@permission_classes([])
def logProcessor(request) -> Response:
    '''
        Log_files processed
    '''
    logger.info("logprocessor initiated")
    data = request.data
    num_threads = data['parallelFileProcessingCount']
    log_files = data['logFiles']
    if num_threads <= 0 or num_threads > 30:
        return Response({"status": "failure", "reason": "Parallel Processing Count out of expected bounds"},
                        status=status.HTTP_400_BAD_REQUEST)
    if len(log_files) == 0:
        return Response({"status": "failure", "reason": "No log files provided in request"},
                        status=status.HTTP_400_BAD_REQUEST)
    logs = multiThreadedReader(urls=data['logFiles'], num_threads=data['parallelFileProcessingCount'])
    sorted_logs = sort_by_time_stamp(logs)
    cleaned = transform(sorted_logs)
    data = aggregate(cleaned)
    response = response_format(data)
    logger.info("logprocessor executed")
    return Response({"response":response}, status=status.HTTP_200_OK)

def sort_by_time_stamp(logs):
    '''
        Sorts log data by time
    '''
    logger.info("Sorting data by time initiated")
    data = []
    for log in logs:
        data.append(log.split(" "))
    # print(data)
    data = sorted(data, key=lambda elem: elem[1])
    logger.info("Sorting data by time executed")
    return data

def response_format(raw_data):
    '''
        Edits response format of raw_data
    '''
    logger.info("Editing response format of raw_data initiated")
    response = []
    for timestamp, data in raw_data.items():
        entry = {'timestamp': timestamp}
        logs = []
        data = {k: data[k] for k in sorted(data.keys())}
        for exception, count in data.items():
            logs.append({'exception': exception, 'count': count})
        entry['logs'] = logs
        response.append(entry)
    logger.info("Editing response format of raw_data executed")
    return response

def aggregate(cleaned_logs):
    '''
        Aggregates clean logs
    '''
    logger.info("Aggregation of clean logs initiated")
    data = {}
    for log in cleaned_logs:
        [key, text] = log
        value = data.get(key, {})
        value[text] = value.get(text, 0)+1
        data[key] = value
    logger.info("Aggregation of clean logs executed")
    return data


def transform(logs):
    '''
        Transforms logs
    '''
    logger.info("Trasformation of log initiated")
    result = []
    for log in logs:
        [_, timestamp, text] = log
        text = text.rstrip()
        timestamp = datetime.utcfromtimestamp(int(int(timestamp)/1000))
        hours, minutes = timestamp.hour, timestamp.minute
        key = ''

        if minutes >= 45:
            if hours == 23:
                key = "{:02d}:45-00:00".format(hours)
            else:
                key = "{:02d}:45-{:02d}:00".format(hours, hours+1)
        elif minutes >= 30:
            key = "{:02d}:30-{:02d}:45".format(hours, hours)
        elif minutes >= 15:
            key = "{:02d}:15-{:02d}:30".format(hours, hours)
        else:
            key = "{:02d}:00-{:02d}:15".format(hours, hours)

        result.append([key, text])
        print(key)
    logger.info("Trasformation of log executed")
    return result


def reader(url, timeout):
    with urllib.request.urlopen(url, timeout=timeout) as conn:
        return conn.read()


def multiThreadedReader(urls, num_threads):
    """
        Read multiple files through HTTP
    """
    logger.info("multithreadreader function initiated")
    result = []
    for url in urls:
        data = reader(url, 60)
        data = data.decode('utf-8')
        result.extend(data.split("\n"))
    result = sorted(result, key=lambda elem:elem[1])
    logger.info("multithreadreader function executed")
    return result