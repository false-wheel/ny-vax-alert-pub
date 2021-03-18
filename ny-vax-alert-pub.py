#!/usr/bin/env python

#######################################################################################################
# Author: false-wheel
#
# License: http://www.gnu.org/licenses/gpl-3.0.en.html
#
# Purpose: Ping the NY vaccine site every N seconds, if the any of the sites you want are available, 
# this will email you.  I recommend emailing your phone's SMS service - see https://resources.voyant.com/en/articles/3107728-sending-emails-to-sms-or-mms
#
# Usage: py -O ny-vax-alert-pub.py
# Search for "CHANGE BEFORE USE" and edit as needed for your use case
#
# Built with Python 3.9.x
# Install https://requests.readthedocs.io/en/master/
#######################################################################################################


#######################################################################################################
import datetime
from email.mime.text import MIMEText
import json
import requests
import smtplib
import socket
import subprocess
import sys
import time
import traceback


#######################################################################################################
# create message body
def create_message(desired_provider_available_list, provider_name_field):
  body_format = 'NY vaccine available! ({now})\n'
  date_format = '%Y-%m-%d %H:%M'
  now = datetime.datetime.now().strftime(date_format)
  msg_body = body_format.format(now=now)
  # add list of providers we found that match our desired provider list
  for provider in  desired_provider_available_list:
    msg_body += provider[provider_name_field] + '\n'
  return msg_body


#######################################################################################################
# send message
def send_message(msg):

  def dbg_notification_msg(mail_msg):
    if __debug__:
      print('Subject: ' + msg['Subject'])
      print('From: ' + msg['From'])
      print('From: ' + msg['From'])
      print('To: ' + msg['To'])
      print(msg.as_string())

  # set up smtp params
  msg_smtpserver = smtplib.SMTP(msg['smtp_api_url'], msg['smtp_api_port'])
  msg_smtpserver.ehlo()
  msg_smtpserver.starttls()
  msg_smtpserver.ehlo
  msg_smtpserver.login(msg['mail_user'], msg['mail_password'])

  # fill in message params
  mail_msg = MIMEText(msg['body'])
  mail_msg['From'] = msg['mail_user']
  mail_msg['To'] = msg['to']
  mail_msg['Subject'] = msg['subject']
  dbg_notification_msg(mail_msg)

  # send!
  msg_smtpserver.sendmail(msg['mail_user'], [msg['to']], mail_msg.as_string())
  msg_smtpserver.quit()


#######################################################################################################
# determine if there is availability at any of the desired providers
def desired_provider_match(provider, desired_provider_id_values, provider_id_field):
  is_desired_provider_match = any(desired_provider_id for desired_provider_id in desired_provider_id_values if desired_provider_id == provider[provider_id_field])
  return is_desired_provider_match
  

#######################################################################################################
# determine if vaccine is available at desired location
def check_vaccine_availability(vaccine_api, desired_provider_id_values):
  is_vaccine_available = False
  
  # get vaccine availability from API
  response = requests.get(vaccine_api['url'])
  
  # api may be down here an there, so just log it
  #if response.status_code != 200:
  #  print('Vaccine API error')
  #  if __debug__:
  #    print(response.text)
  #  return None
    
  # see if the provided we desire has availability
  # expected vaccine api response format - see bottom of file
  vaccine_availability_response = response.json()
  if __debug__:
    print(json.dumps(vaccine_availability_response, sort_keys=True, indent=4))

  # extract which providers are showing availability
  provider_list = vaccine_availability_response['providerList']
  available_provider_list = list(provider for provider in provider_list if provider[vaccine_api['available_appointments_field']] == vaccine_api['available_appointments_value'])
  
  # see if any providers with availability are the providers we are interested in
  desired_provider_available_list = list(provider for provider in available_provider_list if desired_provider_match(provider, desired_provider_id_values, vaccine_api['provider_id_field']))
  
  return desired_provider_available_list;


#######################################################################################################
# watch for vaccine availability until we find it
def watch_for_vaccine_availability(vaccine_api, desired_provider_id_values, counter):
  check_frequency = 30.0     # check availability every N seconds
  is_vaccine_available = False

  while (not is_vaccine_available):
    time.sleep(check_frequency)

    # just print the count of times we have checked so we know the script is still running
    counter += 1
    print('#' + str(counter))

    desired_provider_available_list = check_vaccine_availability(vaccine_api, desired_provider_id_values)
    is_vaccine_available = bool(desired_provider_available_list)  # is list empty or not

  return desired_provider_available_list


#######################################################################################################
def main():
  # define vaccine api parameters and constants
  vaccine_api = {
    'url': 'https://am-i-eligible.covid19vaccine.health.ny.gov/api/list-providers',   # NY state vaccine API url
    'provider_id_field': 'providerId',        # name of the field for the provider's ID
    'available_appointments_field': 'availableAppointments',    # name of the field for the available appointments
    'available_appointments_value': 'Y',      # the code in the API for a provder with availability
    'provider_name_field': 'providerName'     # name of the field for the provider's name
  }

  # list of providers that are close to you, by provider ID (see API)
  desired_provider_id_values = [1000, 1004, 1019]     # !!! CHANGE BEFORE USE !!! - see providerIDs in expected vaccine api response format below
  
  # define notification msg parameters and constants
  msg = {
    'to': 'TBD',              # !!! CHANGE BEFORE USE !!! - who this notification message is to
    'mail_user': 'TBD',       # !!! CHANGE BEFORE USE !!! - who this notification message is from
    'mail_password': 'TBD',   # !!! CHANGE BEFORE USE !!! - password for email account
    'smtp_api_url': 'TBD',    # !!! CHANGE BEFORE USE !!! - SMTP url - update code as desired to support other email providers
    'smtp_api_port': 0,       # !!! CHANGE BEFORE USE !!! - SMTP port
    'subject': 'Alert - NY vaccine available',    # subject of notification message
    'body' : ''
  }

  # start watching for availability
  user_break = False
  counter = 0
  retry = 25  # retry a few times, service may be down now and then
  desired_provider_available_list = None
  while (retry > 0 and not user_break):
    try:
      desired_provider_available_list = watch_for_vaccine_availability(vaccine_api, desired_provider_id_values, counter)
      retry = 0
    except KeyboardInterrupt:
      print('User break - exiting')
      user_break = True
    except BaseException:
      retry -= 1;
      if __debug__:
        traceback.print_exc()
  
  # got something, or an error
  if desired_provider_available_list:
    # notify we have an availability match
    retry = 5   # retry a few times, service may be down now and then
    while (retry > 0 and not user_break):
      try:
        msg['body'] = create_message(desired_provider_available_list, vaccine_api['provider_name_field'])
        send_message(msg)
        print(msg['body'])
        print('Vaccine availability detected, exiting')
        retry = 0
      except KeyboardInterrupt:
        print('User break - exiting')
        user_break = True
      except BaseException:
        retry -= 1;
        if __debug__:
          traceback.print_exc()
  else:
    print('No vaccine availability detected, exiting')


#######################################################################################################
# stay safe!
main()


#######################################################################################################
# expected vaccine api response format
# ** means restricted to local residents
'''
Format 1
{
    "providerList": [{
            "providerId": 1003,
            "providerName": "SUNY Albany",
            "vaccineBrand": "Pfizer",
            "address": "Albany, NY",
            "availableAppointments": "Y"
        }, {
            "providerId": 1028,
            "providerName": "Suffolk CCC - Brentwood",
            "vaccineBrand": "Pfizer",
            "address": "Brentwood, NY",
            "availableAppointments": "Y",
            "isShowable": true
        }, {
            "providerId": 1024,
            "providerName": "Bronx - Bay Eden Senior Center",
            "vaccineBrand": "Pfizer",
            "address": "Bronx, NY",
            "availableAppointments": "Y",
            "isShowable": true
        }, {
            "providerId": 1025,
            "providerName": "SUNY Corning Community College",
            "vaccineBrand": "Pfizer",
            "address": "Corning, NY",
            "availableAppointments": "Y",
            "isShowable": true
        }, {
            "providerId": 1012,
            "providerName": "Rochester Dome Arena",
            "vaccineBrand": "Pfizer",
            "address": "Henrietta, NY",
            "availableAppointments": "Y"
        }, {
            "providerId": 1009,
            "providerName": "SUNY Binghamton",
            "vaccineBrand": "Pfizer",
            "address": "Johnson City, NY",
            "availableAppointments": "Y"
        }, {
            "providerId": 1031,
            "providerName": "SUNY Orange",
            "vaccineBrand": "Pfizer",
            "address": "Middletown, NY",
            "availableAppointments": "Y",
            "isShowable": true
        }, {
            "providerId": 1033,
            "providerName": "Ulster Fairgrounds in New Paltz",
            "vaccineBrand": "Pfizer",
            "address": "New Paltz, NY",
            "availableAppointments": "Y",
            "isShowable": true
        }, {
            "providerId": 1026,
            "providerName": "The Conference Center Niagara Falls",
            "vaccineBrand": "Pfizer",
            "address": "Niagara Falls, NY",
            "availableAppointments": "Y",
            "isShowable": true
        }, {
            "providerId": 1030,
            "providerName": "SUNY Oneonta",
            "vaccineBrand": "Pfizer",
            "address": "Oneonta, NY",
            "availableAppointments": "Y",
            "isShowable": true
        }, {
            "providerId": 1008,
            "providerName": "Plattsburgh International Airport",
            "vaccineBrand": "Pfizer",
            "address": "Plattsburgh, NY",
            "availableAppointments": "Y"
        }, {
            "providerId": 1006,
            "providerName": "SUNY Potsdam ",
            "vaccineBrand": "Pfizer",
            "address": "Potsdam, NY",
            "availableAppointments": "Y"
        }, {
            "providerId": 1027,
            "providerName": "Queensbury Aviation Mall - Sears",
            "vaccineBrand": "Pfizer",
            "address": "Queensbury, NY",
            "availableAppointments": "Y",
            "isShowable": true
        }, {
            "providerId": 1032,
            "providerName": "Stony Brook - Southhampton",
            "vaccineBrand": "Pfizer",
            "address": "Southhampton, NY",
            "availableAppointments": "Y",
            "isShowable": true
        }, {
            "providerId": 1005,
            "providerName": "SUNY Stony Brook ",
            "vaccineBrand": "Pfizer",
            "address": "Stony Brook, NY",
            "availableAppointments": "Y"
        }, {
            "providerId": 1002,
            "providerName": "State Fair Expo Center: NYS Fairgrounds ",
            "vaccineBrand": "Pfizer",
            "address": "Syracuse, NY",
            "availableAppointments": "Y"
        }, {
            "providerId": 1010,
            "providerName": "SUNY Polytechnic Institute",
            "vaccineBrand": "Pfizer",
            "address": "Utica, NY",
            "availableAppointments": "Y"
        }, {
            "providerId": 1016,
            "providerName": "**Washington Avenue Armory - Albany, Schenectady, Troy ",
            "vaccineBrand": "Pfizer",
            "address": "Albany, NY",
            "availableAppointments": "N"
        }, {
            "providerId": 1014,
            "providerName": "**Medgar Evers College - Brooklyn",
            "vaccineBrand": "Pfizer",
            "address": "Brooklyn, NY",
            "availableAppointments": "N"
        }, {
            "providerId": 1018,
            "providerName": "**Delavan Grider Community Center - Buffalo",
            "vaccineBrand": "Pfizer",
            "address": "Buffalo, NY",
            "availableAppointments": "N"
        }, {
            "providerId": 1011,
            "providerName": "University at Buffalo South Campus",
            "vaccineBrand": "Pfizer",
            "address": "Buffalo, NY",
            "availableAppointments": "N"
        }, {
            "providerId": 1013,
            "providerName": "**York College - Health and Physical Education Complex - Queens",
            "vaccineBrand": "Pfizer",
            "address": "Jamaica, NY",
            "availableAppointments": "N"
        }, {
            "providerId": 1000,
            "providerName": "Javits Center",
            "vaccineBrand": "Pfizer",
            "address": "New York, NY",
            "availableAppointments": "N"
        }, {
            "providerId": 1029,
            "providerName": "SUNY Old Westbury",
            "vaccineBrand": "Pfizer",
            "address": "Old Westbury, NY",
            "availableAppointments": "N",
            "isShowable": true
        }, {
            "providerId": 1017,
            "providerName": "**Former Kodak Hawkeye Parking Lot - Rochester",
            "vaccineBrand": "Pfizer",
            "address": "Rochester, NY",
            "availableAppointments": "N"
        }, {
            "providerId": 1007,
            "providerName": "Aqueduct Racetrack ",
            "vaccineBrand": "Pfizer",
            "address": "South Ozone Park, NY",
            "availableAppointments": "N"
        }, {
            "providerId": 1001,
            "providerName": "Jones Beach - Field 3 ",
            "vaccineBrand": "Pfizer",
            "address": "Wantagh, NY",
            "availableAppointments": "N"
        }, {
            "providerId": 1004,
            "providerName": "Westchester County Center",
            "vaccineBrand": "Pfizer",
            "address": "White Plains, NY",
            "availableAppointments": "N"
        }, {
            "providerId": 1015,
            "providerName": "**New York National Guard Armory - Yonkers and Mount Vernon",
            "vaccineBrand": "Pfizer",
            "address": "Yonkers, NY",
            "availableAppointments": "N"
        }
    ],
    "lastUpdated": "3/18/2021, 6:07:59 PM"
}
Format 0
{
    "providerList": [{
            "providerId": 1014,
            "providerName": "**Medgar Evers College - Brooklyn",
            "address": "Brooklyn, NY",
            "availableAppointments": "AA"
        }, {
            "providerId": 1013,
            "providerName": "**York College - Health and Physical Education Complex - Queens ",
            "address": "Jamaica, NY",
            "availableAppointments": "AA"
        }, {
            "providerId": 1008,
            "providerName": "Plattsburgh International Airport -Connecticut Building",
            "address": "Plattsburgh, NY",
            "availableAppointments": "AA"
        }, {
            "providerId": 1006,
            "providerName": "SUNY Potsdam Field House",
            "address": "Potsdam, NY",
            "availableAppointments": "AA"
        }, {
            "providerId": 1002,
            "providerName": "State Fair Expo Center: NYS Fairgrounds - 8:00am – 7:00pm",
            "address": "Syracuse, NY",
            "availableAppointments": "AA"
        }, {
            "providerId": 1010,
            "providerName": "SUNY Polytechnic Institute - Wildcat Field House",
            "address": "Utica, NY",
            "availableAppointments": "AA"
        }, {
            "providerId": 1016,
            "providerName": "**Washington Avenue Armory - Albany, Schenectady, Troy",
            "address": "Albany, NY",
            "availableAppointments": "NAC"
        }, {
            "providerId": 1003,
            "providerName": "SUNY Albany ",
            "address": "Albany, NY",
            "availableAppointments": "NAC"
        }, {
            "providerId": 1022,
            "providerName": "SUNY Genesee Community College - Batavia ",
            "address": "Batavia, NY",
            "availableAppointments": "NAC"
        }, {
            "providerId": 1018,
            "providerName": "**Delavan Grider Community Center - Buffalo",
            "address": "Buffalo, NY",
            "availableAppointments": "NAC"
        }, {
            "providerId": 1011,
            "providerName": "University at Buffalo South Campus - Harriman Hall",
            "address": "Buffalo, NY",
            "availableAppointments": "NAC"
        }, {
            "providerId": 1012,
            "providerName": "Rochester Dome Arena",
            "address": "Henrietta, NY",
            "availableAppointments": "NAC"
        }, {
            "providerId": 1009,
            "providerName": "SUNY Binghamton",
            "address": "Johnson City, NY",
            "availableAppointments": "NAC"
        }, {
            "providerId": 1000,
            "providerName": "Javits Center - 8:00am – 7:00pm",
            "address": "New York, NY",
            "availableAppointments": "NAC"
        }, {
            "providerId": 1019,
            "providerName": "Javits Center - 9:00pm – 6:00am",
            "address": "New York, NY",
            "availableAppointments": "NAC"
        }, {
            "providerId": 1023,
            "providerName": "Jamestown Community College - Olean Campus",
            "address": "Olean, NY",
            "availableAppointments": "NAC"
        }, {
            "providerId": 1021,
            "providerName": "Marist College - Poughkeepsie ",
            "address": "Poughkeepsie, NY",
            "availableAppointments": "NAC"
        }, {
            "providerId": 1017,
            "providerName": "**Former Kodak Hawkeye Parking Lot - Rochester",
            "address": "Rochester, NY",
            "availableAppointments": "NAC"
        }, {
            "providerId": 1007,
            "providerName": "Aqueduct Racetrack - Racing Hall",
            "address": "South Ozone Park, NY",
            "availableAppointments": "NAC"
        }, {
            "providerId": 1005,
            "providerName": "SUNY Stony Brook University Innovation and Discovery Center",
            "address": "Stony Brook, NY",
            "availableAppointments": "NAC"
        }, {
            "providerId": 1020,
            "providerName": "State Fair Expo Center: NYS Fairgrounds - 10:00pm – 6:00am",
            "address": "Syracuse, NY",
            "availableAppointments": "NAC"
        }, {
            "providerId": 1001,
            "providerName": "Jones Beach - Field 3",
            "address": "Wantagh, NY",
            "availableAppointments": "NAC"
        }, {
            "providerId": 1004,
            "providerName": "Westchester County Center",
            "address": "White Plains, NY",
            "availableAppointments": "NAC"
        }, {
            "providerId": 1015,
            "providerName": "**New York National Guard Armory - Yonkers and Mount Vernon",
            "address": "Yonkers, NY",
            "availableAppointments": "NAC"
        }
    ],
    "lastUpdated": "2/28/2021, 7:03:48 AM"
}
'''