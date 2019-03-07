#!/usr/bin/env python3
# vim: et sr sw=4 ts=4 smartindent:
"""
Interact with an NTLM AD server to provide federated AWS creds
"""
import sys
import boto.sts
import boto.s3
import requests
import getpass
import configparser
import base64
import os
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
from os.path import expanduser
from requests_ntlm import HttpNtlmAuth

##########################################################################
# Variables

# region: The default AWS region that this script will connect
# to for all API calls
defaultregion = 'eu-west-1'

# output format: The AWS CLI output format that will be configured in the
# saml profile (affects subsequent CLI calls)
outputformat = 'json'

# aws_configfile and aws_credentialsfile: The files where this script will store the temp
# credentials under the saml profile
aws_home = expanduser("~") + '/.aws'
aws_credentialsfile = aws_home + '/credentials'
aws_configfile = aws_home + '/config'
env_vars_file = aws_home + '/exportawsvars.sh'

if not os.path.exists(aws_home):
    os.makedirs(aws_home)

# SSL certificate verification: Whether or not strict certificate
# verification is done, False should only be used for dev/test
sslverification = True

# fully qualified domain name of your adfs
ad_host = 'ad_host.myorg.com'
idp_path = '/adfs/ls/IdpInitiatedSignOn.aspx?loginToRp=urn:amazon:webservices'
# idp_url: The initial URL that starts the authentication process.
default_idp_url = 'https://'+ad_host+idp_path

# END: Variables
##########################################################################

idp_url = os.environ.get('IDP_URL') or default_idp_url

desired_role_arn = os.environ.get('AWS_ROLE_ARN') or ""

# ... we only need this, because when script run in container, aws home
# might be on a mount - user can specify AWS_DIR to indicate this.
aws_creds_dir = os.environ.get('AWS_DIR') or aws_home

# Get the federated credentials from the user
region = os.environ.get('AWS_DEFAULT_REGION') or input("Region [eu-west-1] : ") or defaultregion

username = os.environ.get('AD_USER') or input("Username : ")

password = os.environ.get('AD_PWD') or getpass.getpass(prompt="Password : ")

# Initiate session handler
session = requests.Session()

# Programatically get the SAML assertion
# Set up the NTLM authentication handler by using the provided credential
session.auth = HttpNtlmAuth(username, password, session)

# Opens the initial AD FS URL and follows all of the HTTP302 redirects
# The adfs server I am using this script against returns me a form, not ntlm auth,
# so we cheat here giving it a browser header so it gives us the NTLM auth we wanted.
agent_str='Mozilla/5.0 (compatible, MSIE 11, Windows NT 6.3; Trident/7.0; rv:11.0) like Gecko'
headers = { 'User-Agent': agent_str }
response = session.get(idp_url, verify=sslverification, headers=headers)

# Debug the response if needed
# print(response)

# Exits if the authentication failed
if response.status_code != 200:
    print('Authentication failed!')
    sys.exit(1)

# Decode the response and extract the SAML assertion
soup = BeautifulSoup(response.text, "html.parser")
assertion = ''

# Look for the SAMLResponse attribute of the input tag (determined by
# analyzing the debug print lines above)
for inputtag in soup.find_all('input'):
    if inputtag.get('name') == 'SAMLResponse':
        # print(inputtag.get('value'))
        assertion = inputtag.get('value')

# Parse the returned assertion and extract the authorized roles
awsroles = []
root = ET.fromstring(base64.b64decode(assertion))

for saml2attribute in root.iter('{urn:oasis:names:tc:SAML:2.0:assertion}Attribute'):
    if saml2attribute.get('Name') == 'https://aws.amazon.com/SAML/Attributes/Role':
        for saml2attributevalue in saml2attribute.iter('{urn:oasis:names:tc:SAML:2.0:assertion}AttributeValue'):
            awsroles.append(saml2attributevalue.text)

# Note the format of the attribute value should be role_arn,principal_arn
# but lots of blogs list it as principal_arn,role_arn so let's reverse
# them if needed
for awsrole in awsroles:
    chunks = awsrole.split(',')
    if'saml-provider' in chunks[0]:
        newawsrole = chunks[1] + ',' + chunks[0]
        index = awsroles.index(awsrole)
        awsroles.insert(index, newawsrole)
        awsroles.remove(awsrole)

role_arn=""
principal_arn=""
config_profile=""

if len(awsroles) > 1:
    if desired_role_arn == "":
        # ... let user choose unless an arn has been specified
        i = 0
        print("")
        print("Please choose the role you would like to assume:")
        for awsrole in awsroles:
            print ('[', i, ']: ', awsrole.split(',')[0])
            i += 1

        # Ensure input is a valid selection from the list
        while True:
            selectedroleindex = int(input("Selection: "))
            if (int(selectedroleindex) < 0) or (int(selectedroleindex) > int(len(awsroles) - 1)):
                print('You selected an invalid role index, please try again')
                continue
            else:
                role_arn = awsroles[int(selectedroleindex)].split(',')[0]
                principal_arn = awsroles[int(selectedroleindex)].split(',')[1]
                config_profile = region + '-' + principal_arn.split(':')[4] + "-" + role_arn.split('/')[1]
                break
    else:
        # ... find user-specified arn
        for awsrole in awsroles:
            if desired_role_arn == awsrole.split(',')[0]:
                role_arn = awsrole.split(',')[0]
                principal_arn = awsrole.split(',')[1]
                config_profile = region + '-' + principal_arn.split(':')[4] + "-" + role_arn.split('/')[1]
                break

        if not role_arn:
            print("No such role found:", desired_role_arn)
            print("User", username,"has the following available roles:")
            for role_arn in map(lambda x: x.split(',')[0], awsroles):
                print(role_arn)

            sys.exit(1)

else:
    role_arn = awsroles[0].split(',')[0]
    principal_arn = awsroles[0].split(',')[1]
    config_profile = region + '-' + principal_arn.split(':')[4] + "-" + role_arn.split('/')[1]

# Overwrite and delete the credential variables, just for safety
username = '##############################################'
password = '##############################################'
del username
del password

# Use the assertion to get an AWS STS token using Assume Role with SAML
conn = boto.sts.connect_to_region(region, anon=True)
token = conn.assume_role_with_saml(role_arn, principal_arn, assertion)

# Read in the existing config file
config = configparser.RawConfigParser()
# config = ConfigParser.RawConfigParser()
config.read(aws_configfile)

# Put the credentials into a specific profile instead of clobbering
# the default credentials
if not config.has_section("profile " + config_profile):
    config.add_section("profile " + config_profile)

    config.set("profile " + config_profile, 'output', outputformat)
    config.set("profile " + config_profile, 'region', region)

# Write the updated config file
with open(aws_configfile, 'w+') as configfile:
    config.write(configfile)
    configfile.close()

# Write the AWS STS token into the AWS credentials file
# Read in the existing config file
config = configparser.RawConfigParser()
# config = ConfigParser.RawConfigParser()
config.read(aws_credentialsfile)

# Put the credentials into a specific profile instead of clobbering
# the default credentials
if not config.has_section(config_profile):
    config.add_section(config_profile)

config.set(config_profile, 'aws_access_key_id', token.credentials.access_key)
config.set(config_profile, 'aws_secret_access_key', token.credentials.secret_key)
config.set(config_profile, 'aws_session_token', token.credentials.session_token)
config.set(config_profile, 'aws_session_token_expiration', token.credentials.expiration)

# Write the updated config file
with open(aws_credentialsfile, 'w+') as credentialsfile:
    config.write(credentialsfile)
    credentialsfile.close()

with open(env_vars_file, 'w+') as env_vars_fh:
    env_vars_fh.write("#!/bin/sh\n")
    env_vars_fh.write("export AWS_ACCESS_KEY_ID=\"" + token.credentials.access_key + "\"\n")
    env_vars_fh.write("export AWS_SECRET_ACCESS_KEY=\"" + token.credentials.secret_key + "\"\n")
    env_vars_fh.write("export AWS_SESSION_TOKEN=\"" + token.credentials.session_token + "\"\n")
    env_vars_fh.write("export AWS_DEFAULT_REGION=\"" + region + "\"\n")
    env_vars_fh.write("export TF_VAR_ACCESS_KEY=\"" + token.credentials.access_key + "\"\n")
    env_vars_fh.write("export TF_VAR_SECRET_KEY=\"" + token.credentials.secret_key + "\"\n")
    env_vars_fh.close()

# Give the user some basic info as to what has just happened
print('\n\n--------------------------------------------------------------------------------\n')
print('Your new access key pair has been stored in your AWS configuration files under the profile:\n\n\t' + format(config_profile) + '\n')
print('This will expire in 1 hour (' + token.credentials.expiration + '), after which you may safely rerun this script to refresh your access key pair.\n')
#print('\n')
print('To use this credential call the AWS CLI with the --profile option, e.g. :-\n')
print('\taws --profile {0} ec2 describe-instances'.format(config_profile) + '\n')
#print('\n')
print('Run the following to assign these environment variables in your current environment (Linux or Mac) :-', end='')
print('\n')
print('\tsource ' + aws_creds_dir + '/exportawsvars.sh')
print('\n--------------------------------------------------------------------------------\n\n')
