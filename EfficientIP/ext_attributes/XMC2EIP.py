#!/usr/bin/python
##############################################################################
#
# Softwarename : XMC2EIP.py
# Last Updated : April 11, 2023
# Original version : https://github.com/extremenetworks/Integrations/tree/master/EfficientIP/ext_attributes
#
# Purpose:  
# - Send XMC data to EfficientIP IPAM.
# - Get data from EfficientIP IPAM and push to Extreme NAC. 
#
# Updated by: Philippe Dotremont (philippe.dotremont@westcon.com, philippe.dotremont@gmail.com)
#
# Changes: Added functionality to get Groupname from EIP and Push it to XMC
# tested with: python 2.7.17
##############################################################################


#############
## IMPORTS ##
#############

import requests
from requests.auth import HTTPBasicAuth
import re
import sys
import logging
import base64
import time

#############################################
## User data to connect to EfficientIP API ##
#############################################

varUser = "EIP_user"
varPassword = "EIP_password"
varEipIP = "EIP_IP"

################################################
## User data to connect to Extreme XIQ SE API ##
################################################

varXMCUser = "XMC_user"
varXMCPassword = "XMC_password"
varXMCIP = "XMC_IP"
varXMCPort = "8443"

###############################################################
## Set varDebug to "True" if you need more debug information ##
###############################################################

varDebug = False
varDebugFile = "XMC2EIP.log"

###################################
## Custom tuning above not below ##
###################################

varAttrStatus = "xmcstatus"
varAttrAuth = "xmcauthtype"
varAttrSwitchIP = "xmcswitchip"
varAttrSwitchPort = "xmcswitchport"
varAttrSwitchLocation = "xmcswitchlocation"
varAttrProfile = "xmcprofile"
varAttrUser = "xmcuser"
varAttrReason = "xmcreason"
varAttrTimeStamp = "xmcupdate"

##################################################
## Values above must match those in EfficientIP ##
##################################################

varAttrMemberOfGroups = "Unregistered"

if varDebug:
    logging.basicConfig(filename=varDebugFile,level=logging.DEBUG)

varMakeUpdate = False

t = time.localtime()
current_time = time.strftime("%H:%M:%S", t )

##########################################################
## Loading the arguments given from CloudIQ Site Engine ##
##########################################################

args = {}
i = 1
while i < len(sys.argv):
    args[sys.argv[i]] = sys.argv[i+1]
    i += 2
##############################################################################################	
## If debug is set to true print arguments given and arguments loaded in the debug log file ##
##############################################################################################

if varDebug:
    logging.debug("Attributes received:"+str(sys.argv[1:]))
    logging.debug("Loaded attributes:"+str(args))

#################################################################
## Check arguments and prepare Extensible Attributes Structure ##
#################################################################

varExtensibleAttr = {}

if "Mac" in args.keys():
    varMAC = str(args["Mac"])
else:
    if varDebug:
        logging.error("Missing mandatory argument Mac followed by value.")
    print ("Missing mandatory argument Mac followed by value.")
    sys.exit(1)

if "Group" in args.keys():
	varAttrMemberOfGroups = args["Group"]

if "Status" in args.keys():
    varExtensibleAttr.update({varAttrStatus:{"value":args["Status"]}})
    varMakeUpdate = True

if "Auth" in args.keys():
    varExtensibleAttr.update({varAttrAuth:{"value":args["Auth"]}})
    varMakeUpdate = True
    
if "SwitchIP" in args.keys():
    varExtensibleAttr.update({varAttrSwitchIP:{"value":args["SwitchIP"]}})
    varMakeUpdate = True

if "SwitchPort" in args.keys():
    varExtensibleAttr.update({varAttrSwitchPort:{"value":args["SwitchPort"].replace('"',"")}})
    varMakeUpdate = True

if "SwitchLocation" in args.keys():
    if args["SwitchLocation"].replace('"',"") == ' ':
        varExtensibleAttr.update({varAttrSwitchLocation:{"value":'-'}})
    else:
        varExtensibleAttr.update({varAttrSwitchLocation:{"value":args["SwitchLocation"].replace('"',"")}})
    varMakeUpdate = True
    
if "Profile" in args.keys():
    varExtensibleAttr.update({varAttrProfile:{"value":args["Profile"].replace('"',"")}})
    varMakeUpdate = True

if "User" in args.keys():
    if args["User"].replace('"',"") == ' ':
        varExtensibleAttr.update({varAttrUser:{"value":str(args["Mac"])}})
    else:
        varExtensibleAttr.update({varAttrUser:{"value":args["User"].replace('"',"")}})
    varMakeUpdate = True

if "Reason" in args.keys():
    varExtensibleAttr.update({varAttrReason:{"value":args["Reason"].replace('"',"")}})
    varMakeUpdate = True

if "Time" in args.keys():
    varExtensibleAttr.update({varAttrTimeStamp:{"value":args["Time"]}})
    varMakeUpdate = True

if varDebug:
	logging.debug("Attributes in the structure: " + str(varExtensibleAttr))
	logging.debug("End-System: " + str(args["Mac"]))
	logging.debug("Group found in XIQ SE: " + varAttrMemberOfGroups)

if varMakeUpdate == False:
    logging.error("At least one argument followed by value is needed: Status, Auth, SwitchIP, SwitchPort, SwitchLocation, Profile, User, Reason, Time")
    print ("At least one argument followed by value is needed: Status, Auth, SwitchIP, SwitchPort, SwitchLocation, Profile, User, Reason, Time")
    sys.exit(1)

if varDebug:
	logging.debug("Successfully collected attributes form XIQ SE")
	logging.debug("Start checking if MAC exists in EIP")

###############################
## Test if MAC exists in EIP ##
###############################


## Setting the authentication credentials for EIP's API ##

headers = {
	'X-IPM-Username': base64.standard_b64encode(varUser),
	'X-IPM-Password': base64.standard_b64encode(varPassword),
	'cache-control': 'no cache'}

## setting the API endpoint and defining the mac address as arguments in the querystring ##
	
url = "https://" + varEipIP + "/rest/ip_address_list"
querystring = {"WHERE":"mac_addr like '" + varMAC + "'"}

if varDebug:
	logging.debug("requesting: " + url + " with querystring: " + str(querystring))

## Sending the API call and storing the result on error exit the script ##	

try:
	varResponse = requests.request("GET", url, headers=headers, params=querystring, verify=False)
except requests.exceptions.RequestException as e:
	logging.error(str(e))
	sys.exit("RequestException")
	
if varDebug:
	logging.debug("response: " + varResponse.text)
	
if varResponse.raise_for_status():
	logging.error("ERROR communicating to EIP " + str(varResponse.status_code) + varResponse.text)
	sys.exit("ERROR communicating to EIP")

## If we found an entry for the mac address we're using a regular expression on the response to get the ip_id in EfficientIP if not we exit the script because there is no reservation in EIP for this mac ##
		
varSearchResult = re.search(r"ip_id\":\"(\d*)", varResponse.text)

if varSearchResult:
	varIpId = varSearchResult.group(1)
	print("IP_ID: " + varIpId)
else:
	logging.error("Can't find MAC-Address " + varMAC)
	logging.debug("Can't find MAC-Address exiting " + varMAC)
	sys.exit("UnknownMAC")

varIsStatic = False

if (re.search(r"&dhcpstatic=0&", varResponse.text)):
	logging.error("DynamicAddress ")
	sys.exit("DynamicAddress")
else:
	varIsStatic = True

varSearchResult = re.search(r"site_id\":\"(\d*)", varResponse.text)

if varSearchResult:
	varSiteId = varSearchResult.group(1)
	print("Site_ID: " + varSiteId)
else:
	logging.error("Can't find Site_ID")
	sys.exit("WrongSiteID")

class_param = ""
varParamCounter = 0

for key in varExtensibleAttr:
	if varParamCounter == 0:
		class_param = class_param + key + "=" + varExtensibleAttr[key]['value']
	else:
		class_param = class_param + "&" + key + "=" + varExtensibleAttr[key]['value']
	varParamCounter = 1

####################################################################################################################################################
## On the same response we received from EIP we can now also use a regular expression to find the NAC Group set in EIP and store it in a variable ##
####################################################################################################################################################

varSearchResult = re.search(r'(?<=xmcnacgroup=)\w+', varResponse.text)
varGroupFound = True

if varSearchResult:
	varDeviceType = varSearchResult.group(0)
	print("Device-type: " + varDeviceType)
	if varDebug:
		logging.debug("Device-type received from EIP: " + varDeviceType)
else:
	varGroupFound = False

################################################################################
## setting the querystring and URL to push the NAC information to the EIP API ##
################################################################################

if varIsStatic:
	class_param = class_param + "&dhcpstatic=1"
	querystring = {"ip_id":varIpId,"site_id":varSiteId,"mac_addr":varMAC,"ip_class_parameters":class_param}
else:
	querystring = {"ip_id":varIpId,"site_id":varSiteId,"ip_class_parameters":class_param}
	
url = "https://" + varEipIP + "/rest/ip_add"

if varDebug:
	logging.debug("requesting: " + url)

###############################################################
## Pushing the NAC data to the EIP API, exit script on error ##
###############################################################

try:
	varResponse = requests.request("PUT", url, headers=headers, params = querystring, verify=False)
except requests.exceptions.RequestException as e:
	logging.error(str(e))
	sys.exit("RequestException")

if varDebug:
	logging.debug ("response last: " + varResponse.text)

if varResponse.raise_for_status():
	logging.error("ERROR communicating to EIP "+str(varResponse.status_code) + varResponse.text)
	sys.exit("ERROR communicating to EIP")

if varDebug:
	logging.debug("Information sent to EIP Now start adding the MAC to the end-system group ")


##############################################################################################################
## Test if the group found in XIQ SE is the same as in EIP, if yes nothing needs to be done exit the script ##
##############################################################################################################

if varGroupFound:
	if varDeviceType in varAttrMemberOfGroups:
		if varDebug:
			logging.debug(varAttrMemberOfGroups)
			logging.debug(current_time + ": Already correct group " + varDeviceType + " Exit execution")
		sys.exit("Already correct group")
else:
	sys.exit("No Group found in EIP to set")

################################################################################
## Setting username and password for basic authentication used for XIQ SE API ##
################################################################################

varXIQAuth = HTTPBasicAuth(varXMCUser, varXMCPassword)
	
########################################################################################
## Set the XIQ SE API endpoint and parameters and push the mac to the group in XIQ SE ##
########################################################################################

varXMCURL = "https://" + varXMCIP + ":" + varXMCPort + "/axis/services/NACWebService/addMACToEndSystemGroup?endSystemGroup=" + varDeviceType + "&macAddress=" + varMAC + "&description=EIPautoadded&reauthenticate=true&removeFromOtherGroups=true"

try:
	response = requests.get(varXMCURL, auth=varXIQAuth, verify=False)
except requests.exceptions.RequestException as e:
	logging.error(str(e))
	sys.exit("RequestException")

if varDebug:
	logging.debug(current_time + ": Added to group: " + varDeviceType)
	logging.debug("End of Script")

#################
## Be Extreme! ##
#################